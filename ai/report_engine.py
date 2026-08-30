"""
ai/report_engine.py
-------------------
Belirli bir tarih aralığındaki günlükleri analiz ederek
genel özetler veya özel sorulara yanıtlar üretir.
"""

from core.token_budget import fit_to_budget, prompt_budget
from database import Database
from ai.llm_engine import CONTEXT_WINDOW, LlamaEngine

# Yanıt için ayrılan token payı (chat_stream'deki max_tokens ile aynı olmalı)
RESPONSE_TOKENS = 1024

# Sistem promptunun kuralları ve başlıkları için ayrılan tahmini pay
SYSTEM_PROMPT_TOKENS = 400


class ReportEngine:
    def __init__(self, llm_engine: LlamaEngine = None):
        # Varsayılan olarak dışarıdan gelen (aynı) LLM engine'i kullan
        self.llm = llm_engine or LlamaEngine()

    def _entry_budget(self) -> int:
        """Günlük kayıtlarına ayrılabilecek token sayısı."""
        return prompt_budget(
            context_window=CONTEXT_WINDOW,
            reserved_for_response=RESPONSE_TOKENS,
            reserved_for_system=SYSTEM_PROMPT_TOKENS,
        )

    def generate_report_stream(self, start_date: str, end_date: str, db: Database, user_question: str = None):
        """
        Belirtilen tarih aralığındaki tüm kayıtları çeker,
        genel bir özet (veya user_question verilmişse spesifik yanıt) oluşturur.
        Stream olarak yield eder.
        """
        entries = db.get_entries_by_date_range(start_date, end_date)
        
        if not entries:
            yield f"{start_date} ile {end_date} tarihleri arasında hiç günlük kaydı bulunamadı."
            return
            
        # ── Duygu istatistiği (kırpmadan etkilenmez: tüm kayıtlardan hesaplanır) ──
        moods = [e["mood_score"] for e in entries if e["mood_score"] != 0]
        stats_context = ""
        if moods:
            avg_mood = sum(moods) / len(moods)
            stats_context = (
                f"Kullanıcının bu dönemdeki ortalama duygu puanı: "
                f"{avg_mood:.1f} (+10 en iyi, -10 en kötü)."
            )

        # ── Kayıtları bağlam penceresine sığdır ─────────────────────────────
        #
        # Eskiden tüm kayıtlar uç uca eklenip prompt'a konuyordu. Bir aylık
        # günlük 4096 token'lık pencereyi aştığı için model hata veriyordu.
        # Artık en yeni kayıtlardan başlanarak bütçeye sığan kadarı alınır.
        pieces = [
            f"[Tarih: {e['date']}]\n{e['content']}\n\n"
            for e in reversed(entries)  # en yeni gün en değerli bağlamdır
        ]
        fitted = fit_to_budget(pieces, self._entry_budget(), self.llm.count_tokens)

        if not fitted.kept:
            yield ("Bu dönemdeki kayıtlar tek seferde okunamayacak kadar uzun. "
                   "Lütfen daha dar bir tarih aralığı sor.")
            return

        # Okunabilenleri kronolojik sıraya geri çevir
        compiled_text = "".join(reversed(fitted.kept))

        if fitted.truncated:
            stats_context += (
                f"\nNOT: Bu dönemdeki {len(entries)} kaydın yalnızca en yeni "
                f"{len(fitted.kept)} tanesi okunabildi."
            )

        if user_question:
            # Spesifik bir soru sorulmuşsa
            system_prompt = f"""Sen benim kişisel dostum ve analistimsin. Sana {start_date} - {end_date} tarihleri arasındaki günlüklerimi veriyorum.
Lütfen SADECE aşağıdaki kayıtlara dayanarak soruma cevap ver.

KURALLAR:
1. Kayıtlarda olmayan hiçbir şeyi uydurma.
2. Mükemmel ve doğal bir Türkçe kullan.
3. ÇOK ÖNEMLİ: Geçmişi anlatırken bile daima ŞİMDİKİ ZAMAN kullan. Bana "sen" diye hitap et (Örnek: "Spor yapıyorsun", "Evde dinleniyorsun", "Ders çalışıyorsun"). Kesinlikle "-sındı", "-dın" gibi geçmiş zaman ekleri kullanma.
4. Benden gün gün liste yapmam istenmediği sürece genel bir özet paragrafı yaz.

{stats_context}

GÜNLÜK KAYITLARI:
---
{compiled_text.strip()}
---"""
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_question}
            ]
        else:
            # Genel özet isteniyorsa
            system_prompt = f"""Sen benim kişisel dostum ve analistimsin. Sana {start_date} - {end_date} tarihleri arasındaki günlüklerimi veriyorum.
Lütfen bu dönemi okuyarak genel ruh halimi, odaklandığım şeyleri ve neleri ertelediğimi özetle.

KURALLAR:
1. Kayıtlarda olmayan hiçbir şeyi uydurma.
2. Mükemmel ve doğal bir Türkçe kullan.
3. ÇOK ÖNEMLİ: Geçmişi anlatırken bile daima ŞİMDİKİ ZAMAN kullan. Bana "sen" diye hitap et (Örnek: "Spor yapıyorsun", "Evde dinleniyorsun", "Ders çalışıyorsun"). Kesinlikle "-sındı", "-dın" gibi geçmiş zaman ekleri kullanma.
4. Lütfen gün gün liste ÇIKARMA. Onun yerine akıcı paragraflar halinde genel durumumu anlat.

{stats_context}

GÜNLÜK KAYITLARI:
---
{compiled_text.strip()}
---"""
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{start_date} ile {end_date} arasındaki dönemimi özetler misin?"}
            ]

        # LLM'i çağır ve sonucu stream et
        for chunk in self.llm.chat_stream(messages):
            yield chunk
