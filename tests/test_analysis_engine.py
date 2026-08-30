"""
tests/test_analysis_engine.py
-----------------------------
Olgu kağıdı ve anlatım.

Buradaki en önemli test, olgu kağıdının boyutunun dönem uzunluğundan
BAĞIMSIZ kalmasıdır: bir yıllık analiz de bir haftalık kadar yer
kaplamalıdır. Eski yol (tüm günlükleri prompt'a yığmak) bir aylık dönemde
bile bağlam penceresini aşıyordu.
"""

import pytest

from ai.analysis_engine import FACT_SHEET_TOKEN_LIMIT, AnalysisEngine
from core.query_intent import Intent
from core.token_budget import count_tokens


@pytest.fixture
def motor(fake_llm):
    return AnalysisEngine(llm_engine=fake_llm)


def kayit_ekle(db, tarih, mood=0, happiness=5, ozet=None, **facets):
    db.save_entry(tarih, f"{tarih} kaydı", happiness_score=happiness)
    db.save_insight(tarih, f"{tarih} kaydı",
                    summary=ozet or f"{tarih} özeti", facets=facets)
    if mood:
        db.update_mood_score(tarih, mood)


@pytest.fixture
def mart_db(temp_db):
    """Mart 2026: spor 9 gün ertelenmiş, kitap okuma 21 gün sürdürülmüş."""
    for gun in range(1, 29):
        ertelenen = ["spor"] if gun <= 9 else []
        if gun <= 6:
            ertelenen.append("rapor yazma")
        yapilan = ["kitap okuma"] if gun <= 21 else []
        kayit_ekle(temp_db, f"2026-03-{gun:02d}",
                   mood=(6 if gun == 14 else (-7 if gun == 22 else -1)),
                   postponed=ertelenen, activity=yapilan)
    return temp_db


class TestOlguKagidiIcerigi:
    def test_donem_basligi_turkce(self, motor, mart_db):
        kagit = motor.build_fact_sheet(mart_db, [Intent("MOOD")],
                                       "2026-03-01", "2026-03-31")
        assert "1 Mart 2026" in kagit and "31 Mart 2026" in kagit

    def test_kayit_sayisi_yazilir(self, motor, mart_db):
        kagit = motor.build_fact_sheet(mart_db, [Intent("MOOD")],
                                       "2026-03-01", "2026-03-31")
        assert "28 günlük kaydı" in kagit

    def test_duygu_blogu_ortalama_icerir(self, motor, mart_db):
        kagit = motor.build_fact_sheet(mart_db, [Intent("MOOD")],
                                       "2026-03-01", "2026-03-31")
        assert "DUYGU DURUMU" in kagit
        assert "Ortalama" in kagit

    def test_duygu_blogu_en_iyi_en_kotu_gun(self, motor, mart_db):
        kagit = motor.build_fact_sheet(mart_db, [Intent("MOOD")],
                                       "2026-03-01", "2026-03-31")
        assert "14 Mart 2026" in kagit   # en iyi gün
        assert "22 Mart 2026" in kagit   # en kötü gün

    def test_siralama_blogu_sayilari_icerir(self, motor, mart_db):
        kagit = motor.build_fact_sheet(mart_db, [Intent("RANKING", "postponed")],
                                       "2026-03-01", "2026-03-31")
        assert "EN ÇOK ERTELENENLER" in kagit
        assert "spor — 9 gün" in kagit
        assert "rapor yazma — 6 gün" in kagit

    def test_surekliligin_serisi_yazilir(self, motor, mart_db):
        kagit = motor.build_fact_sheet(mart_db, [Intent("CONSISTENCY", "activity")],
                                       "2026-03-01", "2026-03-31")
        assert "EN SÜREKLİ YAPILANLAR" in kagit
        assert "kitap okuma" in kagit
        assert "en uzun kesintisiz seri 21 gün" in kagit

    def test_coklu_niyet_iki_blok_uretir(self, motor, mart_db):
        """4. örnek soru: 'en çok ertelediğim VE en sürekli yaptığım'."""
        kagit = motor.build_fact_sheet(
            mart_db,
            [Intent("RANKING", "postponed"), Intent("CONSISTENCY", "activity")],
            "2026-03-01", "2026-03-31",
        )
        assert "EN ÇOK ERTELENENLER" in kagit
        assert "EN SÜREKLİ YAPILANLAR" in kagit

    def test_ornek_gunler_ozet_kullanir(self, motor, mart_db):
        kagit = motor.build_fact_sheet(mart_db, [Intent("MOOD")],
                                       "2026-03-01", "2026-03-31")
        assert "ÖRNEK GÜNLER" in kagit
        assert "özeti" in kagit


class TestKorelasyonBlogu:
    @pytest.fixture
    def stresli_db(self, temp_db):
        for gun in (1, 2, 3):
            kayit_ekle(temp_db, f"2026-03-{gun:02d}",
                       emotion=["stres"], helped=["yürüyüş"])
        for gun in (10, 11):
            kayit_ekle(temp_db, f"2026-03-{gun:02d}",
                       emotion=["huzur"], helped=["kitap okuma"])
        return temp_db

    def test_zor_gunlerde_iyi_gelenler_listelenir(self, motor, stresli_db):
        kagit = motor.build_fact_sheet(stresli_db, [Intent("CORRELATION", "helped")],
                                       "2026-03-01", "2026-03-31")
        assert "Zor gün sayısı: 3" in kagit
        assert "yürüyüş — 3 zor günde" in kagit

    def test_sakin_gunlerin_etiketleri_karismaz(self, motor, stresli_db):
        kagit = motor.build_fact_sheet(stresli_db, [Intent("CORRELATION", "helped")],
                                       "2026-03-01", "2026-03-31")
        assert "kitap okuma" not in kagit.split("ÖRNEK GÜNLER")[0]

    def test_zor_gun_yoksa_durum_bildirilir(self, motor, temp_db):
        kayit_ekle(temp_db, "2026-03-01", mood=5, emotion=["huzur"])
        kagit = motor.build_fact_sheet(temp_db, [Intent("CORRELATION", "helped")],
                                       "2026-03-01", "2026-03-31")
        assert "bulunamadı" in kagit

    def test_zaman_araligi_olmadan_calisir(self, motor, stresli_db):
        """'Stresli olduğumda...' sorusunda zaman ifadesi yoktur."""
        kagit = motor.build_fact_sheet(stresli_db, [Intent("CORRELATION", "helped")])
        assert "Tüm zamanlar" in kagit
        assert "yürüyüş" in kagit


class TestTokenSiniri:
    """
    Regresyon: eski ReportEngine tüm günlükleri prompt'a yığdığı için
    bir aylık dönem bağlam penceresini aşıyordu.
    """

    def test_bir_yillik_donem_sinirin_altinda_kalir(self, motor, temp_db, fake_llm):
        for ay in range(1, 13):
            for gun in range(1, 29):
                kayit_ekle(temp_db, f"2026-{ay:02d}-{gun:02d}", mood=3,
                           postponed=[f"iş {gun % 7}"], activity=[f"uğraş {gun % 5}"])

        kagit = motor.build_fact_sheet(
            temp_db,
            [Intent("MOOD"), Intent("RANKING", "postponed"),
             Intent("CONSISTENCY", "activity")],
            "2026-01-01", "2026-12-31",
        )

        assert count_tokens(kagit, fake_llm.count_tokens) <= FACT_SHEET_TOKEN_LIMIT

    def test_kagit_boyutu_donem_uzunlugundan_bagimsiz(self, motor, temp_db, fake_llm):
        for ay in range(1, 13):
            for gun in range(1, 29):
                kayit_ekle(temp_db, f"2026-{ay:02d}-{gun:02d}", mood=3,
                           postponed=["spor"])

        bir_hafta = motor.build_fact_sheet(temp_db, [Intent("RANKING", "postponed")],
                                           "2026-03-01", "2026-03-07")
        bir_yil = motor.build_fact_sheet(temp_db, [Intent("RANKING", "postponed")],
                                         "2026-01-01", "2026-12-31")

        hafta_token = count_tokens(bir_hafta, fake_llm.count_tokens)
        yil_token = count_tokens(bir_yil, fake_llm.count_tokens)

        # Dönem 52 kat uzun ama kağıt neredeyse aynı boyutta olmalı
        assert yil_token < hafta_token * 2


class TestKapsamaUyarisi:
    def test_eksik_analiz_kagitta_belirtilir(self, motor, temp_db):
        kayit_ekle(temp_db, "2026-03-01", mood=4, postponed=["spor"])
        # Analiz edilmemiş iki kayıt
        temp_db.save_entry("2026-03-02", "analiz edilmemiş", happiness_score=5)
        temp_db.save_entry("2026-03-03", "analiz edilmemiş", happiness_score=5)

        kagit = motor.build_fact_sheet(temp_db, [Intent("RANKING", "postponed")],
                                       "2026-03-01", "2026-03-31")

        assert "VERİ KAPSAMI" in kagit
        assert "3 kaydın 1 tanesi" in kagit

    def test_tam_kapsamada_uyari_cikmaz(self, motor, mart_db):
        kagit = motor.build_fact_sheet(mart_db, [Intent("MOOD")],
                                       "2026-03-01", "2026-03-31")
        assert "VERİ KAPSAMI" not in kagit


class TestAnlatim:
    def test_model_olgu_kagidini_alir(self, motor, mart_db, fake_llm):
        list(motor.analyze_stream(mart_db, "en çok neyi erteledim",
                                  [Intent("RANKING", "postponed")],
                                  "2026-03-01", "2026-03-31"))

        sistem = fake_llm.received_messages[0][0]["content"]
        assert "spor — 9 gün" in sistem

    def test_kullanici_sorusu_iletilir(self, motor, mart_db, fake_llm):
        list(motor.analyze_stream(mart_db, "en çok neyi erteledim",
                                  [Intent("RANKING", "postponed")],
                                  "2026-03-01", "2026-03-31"))
        assert fake_llm.received_messages[0][-1]["content"] == "en çok neyi erteledim"

    def test_sayma_yasagi_prompta_yazilir(self, motor, mart_db, fake_llm):
        list(motor.analyze_stream(mart_db, "soru", [Intent("RANKING", "postponed")],
                                  "2026-03-01", "2026-03-31"))
        sistem = fake_llm.received_messages[0][0]["content"]
        assert "Kendin sayma" in sistem

    def test_yanit_akisi_uretilir(self, motor, mart_db, fake_llm):
        fake_llm.chunks = ["Sporu", " en çok", " ertelemişsin"]
        cikti = "".join(motor.analyze_stream(
            mart_db, "soru", [Intent("RANKING", "postponed")],
            "2026-03-01", "2026-03-31"))
        assert cikti == "Sporu en çok ertelemişsin"

    def test_veri_yoksa_model_cagrilmaz(self, motor, temp_db, fake_llm):
        cikti = "".join(motor.analyze_stream(
            temp_db, "soru", [Intent("RANKING", "postponed")],
            "2026-03-01", "2026-03-31"))

        assert "yeterli veri bulamadım" in cikti
        assert fake_llm.received_messages == []
