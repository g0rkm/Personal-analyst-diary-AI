"""
tests/test_report_engine.py
---------------------------
Zaman bazlı rapor motoru: bir tarih aralığındaki günlükleri okuyup
LLM'e özet/analiz için sunar.
"""

import pytest

from ai.report_engine import ReportEngine


@pytest.fixture
def motor(fake_llm):
    return ReportEngine(llm_engine=fake_llm)


@pytest.fixture
def dolu_db(temp_db):
    temp_db.save_entry("2026-08-01", "Sabah koşuya çıktım.", happiness_score=8)
    temp_db.save_entry("2026-08-15", "Ders çalıştım ama erteledim.", happiness_score=4)
    temp_db.save_entry("2026-08-28", "Arkadaşlarla buluştum.", happiness_score=9)
    return temp_db


class TestKayitYokken:
    def test_bos_aralikta_bilgilendirme_doner(self, motor, temp_db):
        cikti = "".join(motor.generate_report_stream("2026-01-01", "2026-01-31", temp_db))
        assert "bulunamadı" in cikti

    def test_bos_aralikta_llm_cagrilmaz(self, motor, temp_db, fake_llm):
        list(motor.generate_report_stream("2026-01-01", "2026-01-31", temp_db))
        assert fake_llm.received_messages == []

    def test_bilgilendirme_tarihleri_icerir(self, motor, temp_db):
        cikti = "".join(motor.generate_report_stream("2026-03-01", "2026-03-31", temp_db))
        assert "2026-03-01" in cikti and "2026-03-31" in cikti


class TestGenelOzet:
    def test_yanit_akisi_uretilir(self, motor, dolu_db, fake_llm):
        fake_llm.chunks = ["Genel", " olarak", " iyisin"]
        cikti = "".join(motor.generate_report_stream("2026-08-01", "2026-08-31", dolu_db))
        assert cikti == "Genel olarak iyisin"

    def test_aralikataki_tum_gunlukler_prompta_girer(self, motor, dolu_db, fake_llm):
        list(motor.generate_report_stream("2026-08-01", "2026-08-31", dolu_db))

        sistem = fake_llm.received_messages[0][0]["content"]
        assert "Sabah koşuya çıktım." in sistem
        assert "Ders çalıştım ama erteledim." in sistem
        assert "Arkadaşlarla buluştum." in sistem

    def test_aralik_disindakiler_prompta_girmez(self, motor, dolu_db, fake_llm):
        list(motor.generate_report_stream("2026-08-01", "2026-08-10", dolu_db))

        sistem = fake_llm.received_messages[0][0]["content"]
        assert "Sabah koşuya çıktım." in sistem
        assert "Arkadaşlarla buluştum." not in sistem

    def test_tarihler_prompta_yazilir(self, motor, dolu_db, fake_llm):
        list(motor.generate_report_stream("2026-08-01", "2026-08-31", dolu_db))
        sistem = fake_llm.received_messages[0][0]["content"]
        assert "2026-08-01" in sistem and "2026-08-31" in sistem


class TestSpesifikSoru:
    def test_soru_kullanici_mesaji_olarak_gonderilir(self, motor, dolu_db, fake_llm):
        list(motor.generate_report_stream(
            "2026-08-01", "2026-08-31", dolu_db, user_question="neyi erteledim"
        ))

        mesajlar = fake_llm.received_messages[0]
        assert mesajlar[-1] == {"role": "user", "content": "neyi erteledim"}

    def test_soru_yokken_varsayilan_ozet_istenir(self, motor, dolu_db, fake_llm):
        list(motor.generate_report_stream("2026-08-01", "2026-08-31", dolu_db))

        son_mesaj = fake_llm.received_messages[0][-1]
        assert son_mesaj["role"] == "user"
        assert "özetler misin" in son_mesaj["content"]

    def test_iki_modda_da_sistem_mesaji_vardir(self, motor, dolu_db, fake_llm):
        list(motor.generate_report_stream("2026-08-01", "2026-08-31", dolu_db))
        list(motor.generate_report_stream("2026-08-01", "2026-08-31", dolu_db, user_question="s"))

        assert all(m[0]["role"] == "system" for m in fake_llm.received_messages)


class TestDuyguIstatistigi:
    def test_mood_puanlari_varsa_ortalama_prompta_eklenir(self, motor, dolu_db, fake_llm):
        dolu_db.update_mood_score("2026-08-01", 6)
        dolu_db.update_mood_score("2026-08-15", -2)

        list(motor.generate_report_stream("2026-08-01", "2026-08-31", dolu_db))

        sistem = fake_llm.received_messages[0][0]["content"]
        assert "ortalama duygu puanı" in sistem
        assert "2.0" in sistem  # (6 + -2) / 2

    def test_mood_puani_yoksa_istatistik_eklenmez(self, motor, dolu_db, fake_llm):
        list(motor.generate_report_stream("2026-08-01", "2026-08-31", dolu_db))
        assert "ortalama duygu puanı" not in fake_llm.received_messages[0][0]["content"]

    def test_sifir_mood_puanlari_ortalamaya_katilmaz(self, motor, dolu_db, fake_llm):
        # 0 "hesaplanmadı" anlamına gelir, gerçek bir nötr puan değildir
        dolu_db.update_mood_score("2026-08-01", 8)

        list(motor.generate_report_stream("2026-08-01", "2026-08-31", dolu_db))

        assert "8.0" in fake_llm.received_messages[0][0]["content"]


class TestPromptKurallari:
    def test_uydurma_yasagi_prompta_yazilir(self, motor, dolu_db, fake_llm):
        list(motor.generate_report_stream("2026-08-01", "2026-08-31", dolu_db))
        assert "uydurma" in fake_llm.received_messages[0][0]["content"].lower()

    def test_simdiki_zaman_kurali_prompta_yazilir(self, motor, dolu_db, fake_llm):
        list(motor.generate_report_stream("2026-08-01", "2026-08-31", dolu_db))
        assert "ŞİMDİKİ ZAMAN" in fake_llm.received_messages[0][0]["content"]


class TestBaglamButcesi:
    """
    Regresyon: ReportEngine bir tarih aralığındaki TÜM kayıtları uç uca
    ekleyip prompt'a koyuyordu. Bir aylık günlük 4096 token'lık bağlam
    penceresini aşıyor, llama.cpp hata fırlatıyor ve kullanıcı
    "Bu ay ruh halim nasıldı?" sorusuna cevap yerine hata görüyordu.
    """

    @pytest.fixture
    def bir_aylik_db(self, temp_db):
        uzun_metin = (
            "Bugün sabah erken kalktım ama yine de kendimi yorgun hissediyordum. "
            "İşe gidince toplantı uzadı ve rapor yazma işini yine erteledim. "
            "Öğle arasında kısa bir yürüyüş yaptım, bu iyi geldi. Akşam spor "
            "salonuna gitmeyi planlamıştım ama vazgeçtim, kitap okudum. "
        ) * 2
        for gun in range(1, 31):
            temp_db.save_entry(f"2026-03-{gun:02d}", uzun_metin, happiness_score=5)
        return temp_db

    def test_bir_aylik_kayit_promptu_tasirmaz(self, motor, bir_aylik_db, fake_llm):
        from ai.report_engine import RESPONSE_TOKENS, SYSTEM_PROMPT_TOKENS
        from ai.llm_engine import CONTEXT_WINDOW

        list(motor.generate_report_stream("2026-03-01", "2026-03-31", bir_aylik_db))

        sistem = fake_llm.received_messages[0][0]["content"]
        kullanilan = fake_llm.count_tokens(sistem)

        assert kullanilan <= CONTEXT_WINDOW - RESPONSE_TOKENS, (
            f"sistem promptu {kullanilan} token — yanıt için yer kalmıyor"
        )

    def test_kirpma_kullaniciya_bildirilir(self, motor, bir_aylik_db, fake_llm):
        list(motor.generate_report_stream("2026-03-01", "2026-03-31", bir_aylik_db))
        assert "okunabildi" in fake_llm.received_messages[0][0]["content"]

    def test_en_yeni_kayitlar_oncelikli_tutulur(self, motor, bir_aylik_db, fake_llm):
        bir_aylik_db.save_entry("2026-03-30", "EN YENI GUN ISARETI", happiness_score=5)

        list(motor.generate_report_stream("2026-03-01", "2026-03-31", bir_aylik_db))

        assert "EN YENI GUN ISARETI" in fake_llm.received_messages[0][0]["content"]

    def test_ortalama_duygu_kirpmadan_etkilenmez(self, motor, bir_aylik_db, fake_llm):
        # Kırpılan günlerin puanı da ortalamaya girmeli
        for gun in range(1, 31):
            bir_aylik_db.update_mood_score(f"2026-03-{gun:02d}", 4)

        list(motor.generate_report_stream("2026-03-01", "2026-03-31", bir_aylik_db))

        assert "4.0" in fake_llm.received_messages[0][0]["content"]

    def test_kisa_donem_kirpilmaz(self, motor, temp_db, fake_llm):
        for gun in range(1, 4):
            temp_db.save_entry(f"2026-03-0{gun}", "kısa bir gün", happiness_score=5)

        list(motor.generate_report_stream("2026-03-01", "2026-03-03", temp_db))

        assert "okunabildi" not in fake_llm.received_messages[0][0]["content"]

    def test_hicbir_kayit_sigmazsa_anlasilir_mesaj(self, motor, temp_db, fake_llm):
        temp_db.save_entry("2026-03-01", "x" * 100_000, happiness_score=5)

        cikti = "".join(motor.generate_report_stream("2026-03-01", "2026-03-31", temp_db))

        assert "daha dar bir tarih aralığı" in cikti
        assert fake_llm.received_messages == []
