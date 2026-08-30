"""
ai/analysis_engine.py
---------------------
Analiz sorularını yanıtlar: "Bu ay ruh halim nasıldı?", "En çok neyi
erteledim?", "Stresli olduğumda ne iyi geliyor?"

Çalışma biçimi — mimarinin özü:

    1. core.query_intent  soruyu analiz isteklerine çevirir
    2. core.analytics     SQL ile SAYIYI hesaplar
    3. burada bir OLGU KAĞIDI kurulur (~500 token)
    4. model yalnızca bu kağıdı akıcı Türkçeye çevirir

Model hiçbir aşamada sayı üretmez, sayıları okur. Bunun iki sonucu var:
uydurma sayı riski ortadan kalkar ve prompt'un boyutu dönemin uzunluğundan
BAĞIMSIZ hale gelir — bir yıllık analiz de bir haftalık kadar yer kaplar.

Eski yol (tüm günlükleri prompt'a yığmak) bir aylık dönemde bile bağlam
penceresini aşıyordu ve model zaten güvenilir sayamıyordu.
"""

from core.analytics import (
    consistency,
    correlation,
    mood_trend,
    stressful_dates,
    top_facets,
)
from core.date_utils import format_short
from core.query_intent import (
    CONSISTENCY,
    CORRELATION,
    MOOD,
    RANKING,
    SUMMARY,
)
from core.token_budget import count_tokens
from ai.llm_engine import CONTEXT_WINDOW, LlamaEngine

# Olgu kağıdının aşamaması gereken token sınırı.
# Dönem uzunluğundan bağımsızdır; aşılırsa örnek günler kırpılır.
FACT_SHEET_TOKEN_LIMIT = 900

RESPONSE_TOKENS = 1024

# Sıralamalarda gösterilecek azami satır
TOP_N = 5

# Kapsama bunun altındaysa cevabın eksik olabileceği kullanıcıya söylenir
COVERAGE_WARNING_THRESHOLD = 0.9

# Etiket türlerinin Türkçe başlıkları
_FACET_TITLES = {
    "activity": ("EN ÇOK YAPILANLAR", "EN SÜREKLİ YAPILANLAR"),
    "postponed": ("EN ÇOK ERTELENENLER", "EN DÜZENLİ ERTELENENLER"),
    "helped": ("EN ÇOK İYİ GELENLER", "EN SÜREKLİ İYİ GELENLER"),
    "hindered": ("EN ÇOK ZORLAYANLAR", "EN SÜREKLİ ZORLAYANLAR"),
    "emotion": ("EN SIK HİSSEDİLENLER", "EN SÜREKLİ HİSSEDİLENLER"),
    "person": ("EN ÇOK BİRLİKTE OLUNAN KİŞİLER", "EN DÜZENLİ GÖRÜŞÜLENLER"),
    "place": ("EN ÇOK BULUNULAN YERLER", "EN DÜZENLİ GİDİLEN YERLER"),
    "physical": ("EN SIK FİZİKSEL DURUMLAR", "EN SÜREKLİ FİZİKSEL DURUMLAR"),
}

_SYSTEM_PROMPT = """Sen kullanıcının kişisel analistisin. Aşağıda günlüklerinden
HESAPLANMIŞ veriler var. Bu verilere bakarak sorusunu Türkçe yanıtla.

KURALLAR:
1. Sayıları OLDUĞU GİBİ kullan. Kendin sayma, hesaplama yapma, tahmin etme.
2. Verilerde olmayan hiçbir şeyi uydurma.
3. Doğal ve akıcı bir Türkçe kullan. Madde listesi değil, akıcı paragraf yaz.
4. Kullanıcıya "sen" diye hitap et.
5. Geçmişi anlatırken bile ŞİMDİKİ ZAMAN kullan.
   Doğru: "Sporu en çok ertelediğin şey olarak görüyorum, dokuz gün ertelemişsin."
6. Kısa tut: en fazla iki paragraf.
7. VERİ KAPSAMI uyarısı varsa bunu bir cümleyle mutlaka belirt.

HESAPLANMIŞ VERİLER:
---
{fact_sheet}
---"""


def _format_period(start_date, end_date) -> str:
    if not start_date or not end_date:
        return "Tüm zamanlar"
    if start_date == end_date:
        return format_short(start_date)
    return f"{format_short(start_date)} – {format_short(end_date)}"


class AnalysisEngine:
    """Analiz sorularını olgu kağıdı üzerinden yanıtlar."""

    def __init__(self, llm_engine: LlamaEngine = None):
        self.llm = llm_engine or LlamaEngine()

    # ── Olgu kağıdı blokları ─────────────────────────────────────────────

    def _block_mood(self, db, start, end) -> list:
        trend = mood_trend(db, start, end) if start and end else None
        if trend is None or trend.average is None:
            return []

        satirlar = ["DUYGU DURUMU",
                    f"  Ortalama: {trend.average} (+10 en iyi, -10 en kötü), "
                    f"{trend.scored_days} günden hesaplandı"]

        if trend.average_happiness is not None:
            satirlar.append(
                f"  Kendi verdiğin mutluluk puanı ortalaması: "
                f"{trend.average_happiness}/10"
            )
        if trend.previous_average is not None:
            satirlar.append(
                f"  Önceki eşit dönem: {trend.previous_average} "
                f"({trend.direction})"
            )
        if trend.best_day:
            satirlar.append(
                f"  En iyi gün: {format_short(trend.best_day[0])} ({trend.best_day[1]:+d})"
            )
        if trend.worst_day:
            satirlar.append(
                f"  En kötü gün: {format_short(trend.worst_day[0])} ({trend.worst_day[1]:+d})"
            )
        if len(trend.weekly) > 1:
            haftalar = " | ".join(f"{no}. hafta {ort:+.1f}" for no, ort, _ in trend.weekly)
            satirlar.append(f"  Haftalık: {haftalar}")

        return satirlar

    def _block_ranking(self, db, facet, start, end, ascending) -> list:
        sonuclar = top_facets(db, facet, start, end, limit=TOP_N)
        if not sonuclar:
            return []

        if ascending:
            sonuclar = sorted(sonuclar, key=lambda s: s.days)

        baslik = _FACET_TITLES.get(facet, (facet.upper(), facet.upper()))[0]
        if ascending:
            baslik = baslik.replace("EN ÇOK", "EN AZ").replace("EN SIK", "EN SEYREK")

        return [baslik] + [
            f"  {i}. {s.label} — {s.days} gün"
            for i, s in enumerate(sonuclar, start=1)
        ]

    def _block_consistency(self, db, facet, start, end) -> list:
        sonuclar = consistency(db, facet, start, end, limit=TOP_N)
        if not sonuclar:
            return []

        baslik = _FACET_TITLES.get(facet, (facet.upper(), facet.upper()))[1]
        satirlar = [baslik]
        for i, s in enumerate(sonuclar, start=1):
            parca = f"  {i}. {s.label} — {s.days} gün"
            if s.total_days:
                parca += f"/{s.total_days} (%{round(s.coverage * 100)})"
            parca += f", en uzun kesintisiz seri {s.longest_streak} gün"
            satirlar.append(parca)
        return satirlar

    def _block_correlation(self, db, facet, start, end) -> list:
        zor_gunler = stressful_dates(db, start, end)
        if not zor_gunler:
            return ["ZOR GÜNLER", "  Bu dönemde stresli ya da düşük duygu puanlı gün bulunamadı."]

        sonuclar = correlation(db, facet, zor_gunler, limit=TOP_N)
        baslik = _FACET_TITLES.get(facet, (facet.upper(), facet.upper()))[0]

        satirlar = [f"ZOR GÜNLERDE {baslik}",
                    f"  Zor gün sayısı: {len(zor_gunler)}"]
        if not sonuclar:
            satirlar.append("  Bu günlerde kayda geçmiş bir şey bulunamadı.")
        else:
            satirlar += [
                f"  {i}. {s.label} — {s.days} zor günde"
                for i, s in enumerate(sonuclar, start=1)
            ]
        return satirlar

    def _block_examples(self, db, start, end, limit: int = 3) -> list:
        """Birkaç günün tek cümlelik özeti — anlatıya renk katar."""
        if not start or not end:
            return []

        ozetler = db.get_summaries_by_date_range(start, end)
        if not ozetler:
            return []

        # En uç duygulu günler en anlatılası olanlardır
        secilen = sorted(ozetler, key=lambda o: abs(o["mood_score"]), reverse=True)[:limit]
        secilen.sort(key=lambda o: o["date"])

        return ["ÖRNEK GÜNLER"] + [
            f"  [{format_short(o['date'])}] {o['summary']}" for o in secilen
        ]

    # ── Olgu kağıdı ──────────────────────────────────────────────────────

    def build_fact_sheet(self, db, intents: list, start_date=None,
                         end_date=None) -> str:
        """
        İstenen analizleri hesaplayıp modele verilecek olgu kağıdını kurar.

        Kağıdın boyutu dönemin uzunluğundan bağımsızdır; sınır aşılırsa
        önce örnek günler, sonra sondaki bloklar kırpılır.
        """
        toplam = (db.count_entries_in_range(start_date, end_date)
                  if start_date and end_date else None)

        basliklar = [f"DÖNEM: {_format_period(start_date, end_date)}"]
        if toplam is not None:
            basliklar[0] += f" · {toplam} günlük kaydı"

        kapsama = db.get_insight_coverage(start_date, end_date)
        if kapsama["total"] and kapsama["ratio"] < COVERAGE_WARNING_THRESHOLD:
            basliklar.append(
                f"VERİ KAPSAMI: {kapsama['total']} kaydın {kapsama['analyzed']} tanesi "
                f"analiz edildi. Analiz sürüyor, sonuç eksik olabilir."
            )

        bloklar = []
        for intent in intents:
            if intent.kind == MOOD:
                blok = self._block_mood(db, start_date, end_date)
            elif intent.kind == RANKING:
                blok = self._block_ranking(db, intent.facet, start_date,
                                           end_date, intent.ascending)
            elif intent.kind == CONSISTENCY:
                blok = self._block_consistency(db, intent.facet, start_date, end_date)
            elif intent.kind == CORRELATION:
                blok = self._block_correlation(db, intent.facet, start_date, end_date)
            elif intent.kind == SUMMARY:
                blok = self._block_mood(db, start_date, end_date)
            else:
                blok = []

            if blok:
                bloklar.append("\n".join(blok))

        ornekler = self._block_examples(db, start_date, end_date)
        if ornekler:
            bloklar.append("\n".join(ornekler))

        # Token sınırını aşmamak için sondaki bloklardan başlayarak kırp
        bas = "\n".join(basliklar)
        while bloklar:
            aday = bas + "\n\n" + "\n\n".join(bloklar)
            if count_tokens(aday, self.llm.count_tokens) <= FACT_SHEET_TOKEN_LIMIT:
                return aday
            bloklar.pop()

        return bas

    # ── Genel API ────────────────────────────────────────────────────────

    def analyze_stream(self, db, user_question: str, intents: list,
                       start_date=None, end_date=None):
        """Analizi hesaplar ve modelin anlatısını token token yield eder."""
        fact_sheet = self.build_fact_sheet(db, intents, start_date, end_date)

        # Hiçbir analiz veri üretemediyse modeli boşuna çalıştırma
        if "\n\n" not in fact_sheet:
            yield ("Bu dönem için analiz edilecek yeterli veri bulamadım. "
                   "Günlüklerin analiz edilmiş olması gerekiyor; "
                   "AI panelini açık tutarsan arka planda tamamlanır.")
            return

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT.format(fact_sheet=fact_sheet)},
            {"role": "user", "content": user_question},
        ]

        for token in self.llm.chat_stream(messages):
            yield token
