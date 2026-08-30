"""
tests/test_analytics.py
-----------------------
Analiz katmanı: duygu eğilimi, sıklık sıralaması, süreklilik ve korelasyon.

Bu katman kullanıcının dört örnek sorusunun sayısal cevabını üretir.
Model hiç devreye girmez — buradaki her sayı SQL ve saf Python hesabıdır.
"""

import pytest

from core.analytics import (
    STRESS_EMOTIONS,
    consistency,
    correlation,
    longest_streak,
    mood_trend,
    stressful_dates,
    top_facets,
)


def kayit_ekle(db, tarih, mood=0, happiness=5, **facets):
    """Yardımcı: bir günlük kaydı + çıkarımını tek adımda yazar."""
    db.save_entry(tarih, f"{tarih} kaydı", happiness_score=happiness)
    db.save_insight(tarih, f"{tarih} kaydı", summary=f"{tarih} özeti", facets=facets)
    if mood:
        db.update_mood_score(tarih, mood)


class TestEnUzunSeri:
    def test_bos_liste_sifir(self):
        assert longest_streak([]) == 0

    def test_tek_gun_bir(self):
        assert longest_streak(["2026-03-01"]) == 1

    def test_ardisik_gunler_sayilir(self):
        assert longest_streak(["2026-03-01", "2026-03-02", "2026-03-03"]) == 3

    def test_kesinti_seriyi_bolar(self):
        assert longest_streak(["2026-03-01", "2026-03-02", "2026-03-05"]) == 2

    def test_en_uzun_seri_secilir(self):
        tarihler = ["2026-03-01", "2026-03-02",
                    "2026-03-10", "2026-03-11", "2026-03-12", "2026-03-13"]
        assert longest_streak(tarihler) == 4

    def test_sirasiz_girdi_sorun_olmaz(self):
        assert longest_streak(["2026-03-03", "2026-03-01", "2026-03-02"]) == 3

    def test_tekrarli_tarihler_bir_kez_sayilir(self):
        assert longest_streak(["2026-03-01", "2026-03-01", "2026-03-02"]) == 2

    def test_ay_siniri_asilir(self):
        assert longest_streak(["2026-03-30", "2026-03-31", "2026-04-01"]) == 3

    def test_gecersiz_tarihler_atilir(self):
        assert longest_streak(["gecersiz", "2026-03-01", "2026-03-02"]) == 2


class TestDuyguEgilimi:
    """"Bu ay genel ruh halim nasıldı?" sorusunun sayısal temeli."""

    def test_bos_donem(self, temp_db):
        egilim = mood_trend(temp_db, "2026-03-01", "2026-03-31")
        assert egilim.average is None
        assert egilim.total_days == 0
        assert egilim.best_day is None

    def test_ortalama_hesaplanir(self, temp_db):
        kayit_ekle(temp_db, "2026-03-01", mood=6)
        kayit_ekle(temp_db, "2026-03-02", mood=-2)
        assert mood_trend(temp_db, "2026-03-01", "2026-03-31").average == 2.0

    def test_puansiz_gunler_ortalamaya_katilmaz(self, temp_db):
        """mood_score 0 'hesaplanmadı' demektir, nötr bir puan değil."""
        kayit_ekle(temp_db, "2026-03-01", mood=8)
        kayit_ekle(temp_db, "2026-03-02", mood=0)
        egilim = mood_trend(temp_db, "2026-03-01", "2026-03-31")
        assert egilim.average == 8.0
        assert egilim.scored_days == 1
        assert egilim.total_days == 2

    def test_en_iyi_ve_en_kotu_gun(self, temp_db):
        kayit_ekle(temp_db, "2026-03-01", mood=3)
        kayit_ekle(temp_db, "2026-03-14", mood=6)
        kayit_ekle(temp_db, "2026-03-22", mood=-7)
        egilim = mood_trend(temp_db, "2026-03-01", "2026-03-31")
        assert egilim.best_day == ("2026-03-14", 6)
        assert egilim.worst_day == ("2026-03-22", -7)

    def test_haftalik_kovalar(self, temp_db):
        for gun, puan in [(1, 4), (3, 2), (9, -4), (10, -2)]:
            kayit_ekle(temp_db, f"2026-03-{gun:02d}", mood=puan)
        haftalar = mood_trend(temp_db, "2026-03-01", "2026-03-31").weekly
        assert haftalar[0] == (1, 3.0, 2)   # 1 ve 3 Mart
        assert haftalar[1] == (2, -3.0, 2)  # 9 ve 10 Mart

    def test_onceki_donemle_karsilastirma(self, temp_db):
        kayit_ekle(temp_db, "2026-02-15", mood=6)   # önceki ay
        kayit_ekle(temp_db, "2026-03-15", mood=2)   # bu ay
        egilim = mood_trend(temp_db, "2026-03-01", "2026-03-31")
        assert egilim.previous_average == 6.0
        assert egilim.delta == -4.0
        assert egilim.direction == "düşüş"

    def test_onceki_donem_yoksa_yon_bilinmiyor(self, temp_db):
        kayit_ekle(temp_db, "2026-03-15", mood=2)
        assert mood_trend(temp_db, "2026-03-01", "2026-03-31").direction == "bilinmiyor"

    @pytest.mark.parametrize("bu,onceki,beklenen", [
        (5, 1, "yükseliş"), (1, 5, "düşüş"), (3, 3, "sabit"),
    ])
    def test_yon_esikleri(self, temp_db, bu, onceki, beklenen):
        kayit_ekle(temp_db, "2026-02-15", mood=onceki)
        kayit_ekle(temp_db, "2026-03-15", mood=bu)
        assert mood_trend(temp_db, "2026-03-01", "2026-03-31").direction == beklenen

    def test_kullanicinin_verdigi_mutluluk_puani_ayri_tutulur(self, temp_db):
        kayit_ekle(temp_db, "2026-03-01", mood=-5, happiness=9)
        egilim = mood_trend(temp_db, "2026-03-01", "2026-03-31")
        assert egilim.average == -5.0
        assert egilim.average_happiness == 9.0


class TestSiklikSiralamasi:
    """"Bu hafta en çok neyi erteledim?" sorusunun cevabı."""

    @pytest.fixture
    def dolu_db(self, temp_db):
        for gun in range(1, 10):
            ertelenen = ["spor"] if gun <= 6 else []
            if gun <= 3:
                ertelenen.append("rapor yazma")
            kayit_ekle(temp_db, f"2026-03-{gun:02d}", postponed=ertelenen)
        return temp_db

    def test_en_cok_ertelenen_ilk_sirada(self, dolu_db):
        sonuc = top_facets(dolu_db, "postponed", "2026-03-01", "2026-03-31")
        assert sonuc[0].label == "spor"
        assert sonuc[0].days == 6

    def test_ikinci_sira_dogru(self, dolu_db):
        sonuc = top_facets(dolu_db, "postponed", "2026-03-01", "2026-03-31")
        assert sonuc[1] == ("rapor yazma", 3)

    def test_tarih_araligi_uygulanir(self, dolu_db):
        sonuc = top_facets(dolu_db, "postponed", "2026-03-01", "2026-03-03")
        assert sonuc[0].days == 3

    def test_limit_uygulanir(self, dolu_db):
        assert len(top_facets(dolu_db, "postponed", "2026-03-01", "2026-03-31",
                              limit=1)) == 1

    def test_baska_tur_karismaz(self, dolu_db):
        assert top_facets(dolu_db, "activity", "2026-03-01", "2026-03-31") == []

    def test_ayni_gun_tekrari_bir_kez_sayilir(self, temp_db):
        # Çıkarım aynı etiketi iki kez üretse bile gün sayısı 1 olmalı
        kayit_ekle(temp_db, "2026-03-01", postponed=["spor", "Spor"])
        sonuc = top_facets(temp_db, "postponed", "2026-03-01", "2026-03-31")
        assert sonuc[0].days == 1

    def test_bos_veri_bos_sonuc(self, temp_db):
        assert top_facets(temp_db, "postponed", "2026-03-01", "2026-03-31") == []


class TestSureklilik:
    """"En sürekli yaptığım şey neydi?" sorusunun cevabı."""

    def test_seri_ve_kapsama_hesaplanir(self, temp_db):
        for gun in range(1, 11):
            kayit_ekle(temp_db, f"2026-03-{gun:02d}", activity=["kitap okuma"])

        sonuc = consistency(temp_db, "activity", "2026-03-01", "2026-03-10")[0]

        assert sonuc.days == 10
        assert sonuc.total_days == 10
        assert sonuc.longest_streak == 10
        assert sonuc.coverage == 1.0

    def test_daginik_gunler_dusuk_seri_verir(self, temp_db):
        for gun in (1, 3, 5, 7, 9):
            kayit_ekle(temp_db, f"2026-03-{gun:02d}", activity=["yürüyüş"])

        sonuc = consistency(temp_db, "activity", "2026-03-01", "2026-03-09")[0]

        assert sonuc.days == 5
        assert sonuc.longest_streak == 1

    def test_siralama_seriye_gore_yapilir(self, temp_db):
        """Sıklık eşitse üst üste yapılan daha 'sürekli' sayılır."""
        for gun in range(1, 6):            # 5 gün üst üste
            kayit_ekle(temp_db, f"2026-03-{gun:02d}", activity=["kitap okuma"])
        for gun in (10, 12, 14, 16, 18):   # 5 gün dağınık
            kayit_ekle(temp_db, f"2026-03-{gun:02d}", activity=["yürüyüş"])

        sonuc = consistency(temp_db, "activity", "2026-03-01", "2026-03-31")

        assert sonuc[0].label == "kitap okuma"
        assert sonuc[0].longest_streak == 5
        assert sonuc[1].longest_streak == 1

    def test_kapsama_orani(self, temp_db):
        for gun in range(1, 11):
            aktiviteler = ["spor"] if gun <= 4 else []
            kayit_ekle(temp_db, f"2026-03-{gun:02d}", activity=aktiviteler)

        sonuc = consistency(temp_db, "activity", "2026-03-01", "2026-03-10")[0]

        assert sonuc.days == 4
        assert sonuc.total_days == 10
        assert sonuc.coverage == pytest.approx(0.4)

    def test_bos_veri(self, temp_db):
        assert consistency(temp_db, "activity", "2026-03-01", "2026-03-31") == []


class TestKorelasyon:
    """"Stresli olduğumda bana ne iyi geliyor?" sorusunun cevabı."""

    @pytest.fixture
    def stresli_db(self, temp_db):
        # Stresli günler: yürüyüş iyi geliyor
        for gun in (1, 2, 3):
            kayit_ekle(temp_db, f"2026-03-{gun:02d}",
                       emotion=["stres"], helped=["yürüyüş"])
        # Bir stresli günde müzik de iyi gelmiş
        kayit_ekle(temp_db, "2026-03-04", emotion=["kaygı"], helped=["müzik"])
        # Sakin günler: kitap iyi gelmiş ama bunlar sayılmamalı
        for gun in (10, 11, 12, 13, 14):
            kayit_ekle(temp_db, f"2026-03-{gun:02d}",
                       emotion=["huzur"], helped=["kitap okuma"])
        return temp_db

    def test_stresli_gunler_duygu_etiketiyle_bulunur(self, stresli_db):
        gunler = stressful_dates(stresli_db, "2026-03-01", "2026-03-31")
        assert gunler == ["2026-03-01", "2026-03-02", "2026-03-03", "2026-03-04"]

    def test_dusuk_duygu_puani_da_stresli_sayilir(self, temp_db):
        kayit_ekle(temp_db, "2026-03-01", mood=-6, helped=["uyku"])
        assert stressful_dates(temp_db, "2026-03-01", "2026-03-31") == ["2026-03-01"]

    def test_sifir_mood_stresli_sayilmaz(self, temp_db):
        """0 'hesaplanmadı' demek; eşiğin altında görünse de sayılmamalı."""
        kayit_ekle(temp_db, "2026-03-01", mood=0)
        assert stressful_dates(temp_db, "2026-03-01", "2026-03-31") == []

    def test_stresli_gunlerde_ne_iyi_geldigi_siralanir(self, stresli_db):
        gunler = stressful_dates(stresli_db, "2026-03-01", "2026-03-31")
        sonuc = correlation(stresli_db, "helped", gunler)

        assert sonuc[0] == ("yürüyüş", 3)
        assert ("müzik", 1) in sonuc

    def test_sakin_gunlerin_etiketleri_karismaz(self, stresli_db):
        gunler = stressful_dates(stresli_db, "2026-03-01", "2026-03-31")
        etiketler = [s.label for s in correlation(stresli_db, "helped", gunler)]
        assert "kitap okuma" not in etiketler

    def test_zaman_araligi_verilmezse_tum_gecmis(self, stresli_db):
        # "Stresli olduğumda..." sorusunda zaman ifadesi yoktur
        assert len(stressful_dates(stresli_db)) == 4

    def test_kosul_gunu_yoksa_bos_sonuc(self, temp_db):
        assert correlation(temp_db, "helped", []) == []

    def test_stres_duygu_listesi_normalize_edilmis(self):
        # entry_facets etiketleri küçük harfle saklanır
        assert all(e == e.lower() for e in STRESS_EMOTIONS)
