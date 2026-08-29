"""
tests/test_database.py
----------------------
SQLite katmanı: CRUD, arama, istatistik ve düzeltilen hataların regresyonları.
"""

import pytest


class TestKurulum:
    def test_bos_veritabani_olusur(self, temp_db):
        assert temp_db.get_all_entry_dates() == []
        assert temp_db.get_stats() == {"total_entries": 0, "avg_happiness": 0}

    def test_eksik_klasor_otomatik_olusturulur(self, tmp_path, monkeypatch):
        # Docker volume'u ilk açılışta boş olabilir
        hedef = tmp_path / "olmayan" / "klasor" / "diary.db"
        monkeypatch.setenv("DIARY_DB_PATH", str(hedef))
        from database import Database
        Database()
        assert hedef.parent.exists()

    def test_ikinci_kez_acmak_veriyi_bozmaz(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DIARY_DB_PATH", str(tmp_path / "d.db"))
        from database import Database
        Database().save_entry("2026-01-01", "metin", happiness_score=5)
        assert Database().get_entry("2026-01-01")["content"] == "metin"


class TestYazmaVeOkuma:
    def test_kaydet_ve_oku(self, temp_db):
        temp_db.save_entry("2026-08-29", "Bugün koşuya çıktım.", happiness_score=8)
        kayit = temp_db.get_entry("2026-08-29")
        assert kayit["content"] == "Bugün koşuya çıktım."
        assert kayit["happiness_score"] == 8

    def test_olmayan_kayit_none_doner(self, temp_db):
        assert temp_db.get_entry("2099-01-01") is None

    def test_ayni_tarihe_yazmak_gunceller(self, temp_db):
        temp_db.save_entry("2026-08-29", "ilk", happiness_score=3)
        temp_db.save_entry("2026-08-29", "ikinci", happiness_score=9)
        kayit = temp_db.get_entry("2026-08-29")
        assert kayit["content"] == "ikinci"
        assert kayit["happiness_score"] == 9
        assert len(temp_db.get_all_entry_dates()) == 1

    def test_silme(self, temp_db):
        temp_db.save_entry("2026-08-29", "metin", happiness_score=5)
        temp_db.delete_entry("2026-08-29")
        assert temp_db.get_entry("2026-08-29") is None

    def test_bos_icerikli_kayit_listelenmez(self, temp_db):
        temp_db.save_entry("2026-08-29", "", happiness_score=5)
        assert temp_db.get_all_entry_dates() == []

    def test_turkce_karakterler_korunur(self, temp_db):
        metin = "Çığır açan bir gün: şöyle böyle, çok üşüdüm."
        temp_db.save_entry("2026-08-29", metin, happiness_score=6)
        assert temp_db.get_entry("2026-08-29")["content"] == metin


class TestMoodScoreKorunmasi:
    """
    Regresyon: save_entry eskiden mood_score'u varsayılan 0 ile eziyordu.
    Kullanıcı yazısını düzenleyip kaydettiğinde yapay zekânın hesapladığı
    duygu puanı siliniyor, istatistikler bozuluyordu.
    """

    def test_yeniden_kaydetmek_mood_score_u_silmez(self, temp_db):
        temp_db.save_entry("2026-08-29", "ilk metin", happiness_score=7)
        temp_db.update_mood_score("2026-08-29", 8)

        temp_db.save_entry("2026-08-29", "düzeltilmiş metin", happiness_score=7)

        assert temp_db.get_entry("2026-08-29")["mood_score"] == 8

    def test_negatif_mood_score_da_korunur(self, temp_db):
        temp_db.save_entry("2026-08-29", "metin", happiness_score=2)
        temp_db.update_mood_score("2026-08-29", -6)
        temp_db.save_entry("2026-08-29", "yeni metin", happiness_score=2)
        assert temp_db.get_entry("2026-08-29")["mood_score"] == -6

    def test_acikca_verilen_mood_score_yazilir(self, temp_db):
        temp_db.save_entry("2026-08-29", "metin", happiness_score=5)
        temp_db.update_mood_score("2026-08-29", 8)
        temp_db.save_entry("2026-08-29", "metin", mood_score=-2, happiness_score=5)
        assert temp_db.get_entry("2026-08-29")["mood_score"] == -2

    def test_yeni_kayitta_mood_score_sifirdir(self, temp_db):
        temp_db.save_entry("2026-08-29", "metin", happiness_score=5)
        assert temp_db.get_entry("2026-08-29")["mood_score"] == 0

    def test_happiness_score_ayri_bir_alandir(self, temp_db):
        # happiness kullanıcının verdiği puan, mood yapay zekânın hesabı
        temp_db.save_entry("2026-08-29", "metin", happiness_score=9)
        temp_db.update_mood_score("2026-08-29", -4)
        kayit = temp_db.get_entry("2026-08-29")
        assert kayit["happiness_score"] == 9
        assert kayit["mood_score"] == -4


class TestMoodBekleyenKayitlar:
    def test_yalnizca_puansiz_kayitlar_doner(self, temp_db):
        temp_db.save_entry("2026-08-01", "birinci", happiness_score=5)
        temp_db.save_entry("2026-08-02", "ikinci", happiness_score=5)
        temp_db.update_mood_score("2026-08-01", 7)

        bekleyen = temp_db.get_entries_without_mood()

        assert [k["date"] for k in bekleyen] == ["2026-08-02"]

    def test_hepsi_puanliysa_bos_liste(self, temp_db):
        temp_db.save_entry("2026-08-01", "metin", happiness_score=5)
        temp_db.update_mood_score("2026-08-01", 3)
        assert temp_db.get_entries_without_mood() == []

    def test_bos_icerik_dahil_edilmez(self, temp_db):
        temp_db.save_entry("2026-08-01", "", happiness_score=5)
        assert temp_db.get_entries_without_mood() == []

    def test_icerik_alani_da_doner(self, temp_db):
        temp_db.save_entry("2026-08-01", "analiz edilecek metin", happiness_score=5)
        assert temp_db.get_entries_without_mood()[0]["content"] == "analiz edilecek metin"


class TestArama:
    def test_kelime_bulur(self, temp_db):
        temp_db.save_entry("2026-08-01", "bugün spor yaptım", happiness_score=7)
        temp_db.save_entry("2026-08-02", "kitap okudum", happiness_score=6)
        assert len(temp_db.search_entries("spor")) == 1

    def test_sonuclar_tarihe_gore_yeniden_eskiye(self, temp_db):
        for gun in ("01", "02", "03"):
            temp_db.save_entry(f"2026-08-{gun}", "ortak kelime", happiness_score=5)
        tarihler = [k["date"] for k in temp_db.search_entries("ortak")]
        assert tarihler == ["2026-08-03", "2026-08-02", "2026-08-01"]

    def test_eslesme_yoksa_bos_liste(self, temp_db):
        temp_db.save_entry("2026-08-01", "metin", happiness_score=5)
        assert temp_db.search_entries("bulunmayan") == []

    # ── Regresyon: LIKE joker karakterleri kaçışlanmıyordu ────────────────
    def test_yuzde_isareti_her_seyi_eslestirmez(self, temp_db):
        temp_db.save_entry("2026-08-01", "sıradan bir gün", happiness_score=5)
        temp_db.save_entry("2026-08-02", "başka bir gün", happiness_score=5)
        assert temp_db.search_entries("%") == []

    def test_alt_cizgi_tek_karakter_eslestirmez(self, temp_db):
        temp_db.save_entry("2026-08-01", "sıradan bir gün", happiness_score=5)
        assert temp_db.search_entries("_") == []

    def test_joker_karakter_duz_metin_olarak_aranir(self, temp_db):
        temp_db.save_entry("2026-08-01", "markette %50 indirim vardı", happiness_score=5)
        temp_db.save_entry("2026-08-02", "indirim yoktu", happiness_score=5)
        sonuc = temp_db.search_entries("%50")
        assert len(sonuc) == 1
        assert sonuc[0]["date"] == "2026-08-01"

    def test_ters_bolu_arama_cokmez(self, temp_db):
        temp_db.save_entry("2026-08-01", r"C:\Users klasörünü temizledim", happiness_score=5)
        assert len(temp_db.search_entries(r"C:\Users")) == 1


class TestTarihAraligi:
    @pytest.fixture
    def dolu_db(self, temp_db):
        for gun, puan in [("01", 5), ("15", 8), ("28", 3)]:
            temp_db.save_entry(f"2026-08-{gun}", f"{gun} numaralı gün", happiness_score=puan)
        return temp_db

    def test_aralik_icindekiler_doner(self, dolu_db):
        sonuc = dolu_db.get_entries_by_date_range("2026-08-01", "2026-08-20")
        assert [k["date"] for k in sonuc] == ["2026-08-01", "2026-08-15"]

    def test_sinirlar_dahildir(self, dolu_db):
        sonuc = dolu_db.get_entries_by_date_range("2026-08-15", "2026-08-15")
        assert len(sonuc) == 1

    def test_kronolojik_sirada_doner(self, dolu_db):
        sonuc = dolu_db.get_entries_by_date_range("2026-08-01", "2026-08-31")
        assert [k["date"] for k in sonuc] == ["2026-08-01", "2026-08-15", "2026-08-28"]

    def test_bos_aralik(self, dolu_db):
        assert dolu_db.get_entries_by_date_range("2027-01-01", "2027-12-31") == []


class TestIstatistik:
    def test_toplam_ve_ortalama(self, temp_db):
        temp_db.save_entry("2026-08-01", "metin", happiness_score=6)
        temp_db.save_entry("2026-08-02", "metin", happiness_score=8)
        istatistik = temp_db.get_stats()
        assert istatistik["total_entries"] == 2
        assert istatistik["avg_happiness"] == 7.0

    def test_puansiz_kayitlar_ortalamaya_katilmaz(self, temp_db):
        temp_db.save_entry("2026-08-01", "metin", happiness_score=10)
        temp_db.save_entry("2026-08-02", "metin", happiness_score=0)
        assert temp_db.get_stats()["avg_happiness"] == 10.0

    def test_skorlu_liste_yeniden_eskiye(self, temp_db):
        temp_db.save_entry("2026-08-01", "metin", happiness_score=5)
        temp_db.save_entry("2026-08-05", "metin", happiness_score=5)
        assert [k["date"] for k in temp_db.get_all_entries_with_scores()] == \
               ["2026-08-05", "2026-08-01"]
