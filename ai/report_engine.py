"""
ai/report_engine.py
-------------------
Belirli bir tarih aralığındaki günlükleri analiz ederek
genel özetler veya özel sorulara yanıtlar üretir.
"""

from database import Database
from ai.llm_engine import LlamaEngine

class ReportEngine:
    def __init__(self, llm_engine: LlamaEngine = None):
        # Varsayılan olarak dışarıdan gelen (aynı) LLM engine'i kullan
        self.llm = llm_engine or LlamaEngine()

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
            
        # Kayıtları uç uca ekle
        compiled_text = ""
        total_mood = 0
        valid_mood_count = 0
        
        for e in entries:
            compiled_text += f"[Tarih: {e['date']}]\n{e['content']}\n\n"
            if e['mood_score'] != 0:
                total_mood += e['mood_score']
                valid_mood_count += 1
                
        # İstatistiksel özet oluştur (LLM'e ek bağlam olarak vermek için)
        stats_context = ""
        if valid_mood_count > 0:
            avg_mood = total_mood / valid_mood_count
            stats_context = f"Kullanıcının bu dönemdeki ortalama duygu puanı: {avg_mood:.1f} / 10 (10 en iyi, -10 en kötü)."

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
