"""
ai/insight_extractor.py
-----------------------
Bir günlük kaydından yapısal veri çıkarır.

Neden gerekli: "Bu ay en çok neyi erteledim?" sorusu SAYMA gerektirir.
3B'lik bir modele bir aylık düz metin verip saydırmak hem bağlam
penceresine sığmaz hem de güvenilir değildir. Çözüm, işi tersine
çevirmek: her kayıt yazıldığında bir kez analiz edilip küçük ve yapısal
bir özet çıkarılır; sayma işini sonra SQL yapar.

Çıkarım iki geçişlidir:
  • ÇEKİRDEK  — duygu, özet, yapılanlar, ertelenenler, iyi gelenler,
                zorlayanlar, duygular. Her zaman çalışır.
  • GENİŞLETİLMİŞ — kişiler, mekânlar, fiziksel durum, uyku.
                Ayarla kapatılabilir.

İkiye bölünmesinin nedeni doğruluk: küçük modeller az sayıda alan istenince
belirgin biçimde daha isabetli çalışır. Genişletilmiş alanlar ayrı bir
çağrıda toplanınca çekirdek dördün kalitesini bozmaz.

Şema zorlaması (LlamaEngine.complete_json) sayesinde model şema dışına
çıkamaz; yine de tüm alanlar savunmacı biçimde okunur — bozuk çıktı
uygulamayı çökertmemelidir.
"""

from typing import NamedTuple, Optional

from core.labels import clean_labels

# ── Şemalar ──────────────────────────────────────────────────────────────
# Alanlar bilinçli olarak az ve kısa tutuldu; büyük şema küçük modelde
# doğruluğu düşürüyor.

_LABEL_ARRAY = {
    "type": "array",
    "items": {"type": "string"},
    "maxItems": 5,
}

CORE_SCHEMA = {
    "type": "object",
    "properties": {
        "mood": {"type": "integer", "minimum": -10, "maximum": 10},
        "energy": {"type": "integer", "minimum": 0, "maximum": 10},
        "summary": {"type": "string"},
        "activities": _LABEL_ARRAY,
        "postponed": _LABEL_ARRAY,
        "helped": _LABEL_ARRAY,
        "hindered": _LABEL_ARRAY,
        "emotions": _LABEL_ARRAY,
    },
    "required": [
        "mood", "energy", "summary",
        "activities", "postponed", "helped", "hindered", "emotions",
    ],
}

EXTENDED_SCHEMA = {
    "type": "object",
    "properties": {
        "sleep_quality": {"type": "integer", "minimum": -1, "maximum": 10},
        "people": _LABEL_ARRAY,
        "places": _LABEL_ARRAY,
        "physical": _LABEL_ARRAY,
    },
    "required": ["sleep_quality", "people", "places", "physical"],
}

# Şemadaki alan adı -> entry_facets.kind eşlemesi
CORE_FACET_FIELDS = {
    "activities": "activity",
    "postponed": "postponed",
    "helped": "helped",
    "hindered": "hindered",
    "emotions": "emotion",
}
EXTENDED_FACET_FIELDS = {
    "people": "person",
    "places": "place",
    "physical": "physical",
}

# Bir günden çıkarılacak azami etiket sayısı (tür başına)
MAX_LABELS_PER_KIND = 5

# Çok uzun kayıtlarda çıkarım için okunacak azami karakter.
# Tek bir kaydın bağlam penceresini doldurmaması için sınırlanır.
MAX_CONTENT_CHARS = 4000

SUMMARY_MAX_CHARS = 160


_CORE_SYSTEM_PROMPT = """Sen bir günlük analiz asistanısın. Sana bir günlük kaydı verilecek.
Kayıttan aşağıdaki bilgileri çıkar ve SADECE JSON döndür.

KURALLAR:
1. Kayıtta AÇIKÇA yazmayan hiçbir şeyi uydurma. Bilgi yoksa listeyi boş bırak.
2. Etiketler kısa olsun: 1-3 kelime, isim hâlinde.
   Doğru: "rapor yazma", "spor", "yürüyüş"
   Yanlış: "raporu yazmayı erteledim", "bugün spor yapmadım"
3. activities  = kişinin gerçekten YAPTIĞI şeyler
   postponed   = ERTELEDİĞİ, yapmadığı, sonraya bıraktığı şeyler
   helped      = kendisine İYİ GELEN, rahatlatan şeyler
   hindered    = onu ZORLAYAN, yoran, olumsuz etkileyen şeyler
   emotions    = hissettiği duygular ("stres", "huzur", "yorgunluk")
4. mood: genel ruh hâli, -10 (çok kötü) ile +10 (çok iyi) arası tam sayı.
5. energy: enerji düzeyi, 0 ile 10 arası tam sayı.
6. summary: tek cümlelik Türkçe özet, en fazla 20 kelime.
7. Tüm etiketler Türkçe olmalı."""

_EXTENDED_SYSTEM_PROMPT = """Sen bir günlük analiz asistanısın. Sana bir günlük kaydı verilecek.
Kayıttan aşağıdaki bilgileri çıkar ve SADECE JSON döndür.

KURALLAR:
1. Kayıtta AÇIKÇA yazmayan hiçbir şeyi uydurma. Bilgi yoksa listeyi boş bırak.
2. Etiketler kısa olsun: 1-3 kelime.
3. people   = birlikte vakit geçirdiği kişiler (isim ya da "annem", "iş arkadaşı")
   places   = bulunduğu mekânlar ("ev", "ofis", "spor salonu")
   physical = fiziksel durumu ("baş ağrısı", "yorgunluk", "hastalık")
4. sleep_quality: uyku kalitesi 0-10 arası tam sayı.
   Kayıtta uykudan HİÇ söz edilmiyorsa -1 yaz.
5. Tüm etiketler Türkçe olmalı."""


class ExtractedInsight(NamedTuple):
    """Bir günlük kaydından çıkarılan yapısal veri."""

    mood: int
    energy: int
    sleep_quality: int
    summary: str
    facets: dict          # {"activity": ["spor"], "postponed": [...], ...}

    @property
    def is_empty(self) -> bool:
        """Çıkarım hiçbir işe yarar veri üretmedi mi?"""
        return not self.summary and not any(self.facets.values())


def _as_int(value, default: int, low: int, high: int) -> int:
    """Modelden gelen sayıyı güvenle tam sayıya çevirip aralığa sıkıştırır."""
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _as_summary(value) -> str:
    if not isinstance(value, str):
        return ""
    summary = " ".join(value.split())
    if len(summary) > SUMMARY_MAX_CHARS:
        summary = summary[:SUMMARY_MAX_CHARS].rsplit(" ", 1)[0] + "..."
    return summary


class InsightExtractor:
    """Günlük kayıtlarından yapısal veri çıkarır."""

    def __init__(self, llm_engine, extended: bool = True):
        self.llm = llm_engine
        self.extended = extended

    # ── İç yardımcılar ───────────────────────────────────────────────────

    def _messages(self, system_prompt: str, content: str) -> list[dict]:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content[:MAX_CONTENT_CHARS]},
        ]

    def _safe_complete(self, system_prompt: str, content: str, schema: dict) -> dict:
        """
        Modeli çağırır; her tür hatada boş sözlük döner.

        Bu metot istisna fırlatmamalıdır: arka plandaki toplu çıkarım
        yüzlerce kaydı işler ve tek bir sorunlu kayıt yüzünden durmamalıdır.
        """
        try:
            result = self.llm.complete_json(
                self._messages(system_prompt, content), schema
            )
        except Exception as e:
            print("Çıkarım çağrısı başarısız:", e)
            return {}

        return result if isinstance(result, dict) else {}

    def _collect_facets(self, data: dict, field_map: dict) -> dict:
        """Şema alanlarını normalize edilmiş etiket listelerine çevirir."""
        facets = {}
        for field, kind in field_map.items():
            labels = clean_labels(data.get(field), limit=MAX_LABELS_PER_KIND)
            if labels:
                facets[kind] = labels
        return facets

    # ── Genel API ────────────────────────────────────────────────────────

    def extract(self, content: str) -> ExtractedInsight:
        """
        Bir günlük kaydından çıkarım yapar.

        Model bozuk ya da eksik çıktı verirse varsayılanlara düşülür;
        bu metot istisna fırlatmaz — arka plan işçisini durdurmamalıdır.
        """
        boş = ExtractedInsight(mood=0, energy=-1, sleep_quality=-1,
                               summary="", facets={})
        if not content or not content.strip():
            return boş

        core = self._safe_complete(_CORE_SYSTEM_PROMPT, content, CORE_SCHEMA)

        facets = self._collect_facets(core, CORE_FACET_FIELDS)
        sleep_quality = -1

        if self.extended:
            extra = self._safe_complete(_EXTENDED_SYSTEM_PROMPT, content, EXTENDED_SCHEMA)
            facets.update(self._collect_facets(extra, EXTENDED_FACET_FIELDS))
            sleep_quality = _as_int(extra.get("sleep_quality"), -1, -1, 10)

        return ExtractedInsight(
            mood=_as_int(core.get("mood"), 0, -10, 10),
            energy=_as_int(core.get("energy"), -1, -1, 10),
            sleep_quality=sleep_quality,
            summary=_as_summary(core.get("summary")),
            facets=facets,
        )
