"""
tests/test_vector_store.py
--------------------------
LanceDB vektör deposu.

Vektörler sahte gömücüden (FakeEmbedder) gelir; gerçek ONNX modeli
indirilmez. Testler yalnızca depolama/arama davranışını doğrular.
"""

import pytest

from ai.chunker import chunk_entry
from ai.vector_store import VECTOR_DIM


def parcala_ve_ekle(store, embedder, tarih, metin):
    """Yardımcı: bir günlüğü parçalayıp vektörleriyle birlikte depoya yazar."""
    parcalar = chunk_entry(tarih, metin)
    vektorler = embedder.embed_documents([p["text"] for p in parcalar])
    store.add_chunks(parcalar, vektorler)
    return parcalar


class TestKurulum:
    def test_bos_depo_olusur(self, temp_vector_store):
        assert temp_vector_store.table.count_rows() == 0
        assert temp_vector_store.get_indexed_dates() == set()

    def test_olmayan_klasor_olusturulur(self, tmp_path, monkeypatch):
        hedef = tmp_path / "yeni" / "lance"
        monkeypatch.setenv("DIARY_VECTOR_DB_PATH", str(hedef))
        from ai.vector_store import DiaryVectorStore
        DiaryVectorStore()
        assert hedef.exists()

    def test_ayni_klasor_yeniden_acilabilir(self, tmp_path, monkeypatch, fake_embedder):
        monkeypatch.setenv("DIARY_VECTOR_DB_PATH", str(tmp_path / "lance"))
        from ai.vector_store import DiaryVectorStore

        birinci = DiaryVectorStore()
        parcala_ve_ekle(birinci, fake_embedder, "2026-08-01", "spor yaptım")

        ikinci = DiaryVectorStore()
        assert ikinci.get_indexed_dates() == {"2026-08-01"}


class TestEkleme:
    def test_parca_eklenir(self, temp_vector_store, fake_embedder):
        parcala_ve_ekle(temp_vector_store, fake_embedder, "2026-08-01", "bugün spor yaptım")
        assert temp_vector_store.table.count_rows() == 1

    def test_bos_parca_listesi_sorun_cikarmaz(self, temp_vector_store):
        temp_vector_store.add_chunks([], [])
        assert temp_vector_store.table.count_rows() == 0

    def test_cok_paragrafli_gunluk_birden_fazla_satir_yazar(self, temp_vector_store, fake_embedder):
        metin = "Birinci paragraf.\n\nİkinci paragraf.\n\nÜçüncü paragraf."
        parcala_ve_ekle(temp_vector_store, fake_embedder, "2026-08-01", metin)
        assert temp_vector_store.table.count_rows() == 3

    def test_ayni_tarihi_yeniden_yazmak_eskisini_siler(self, temp_vector_store, fake_embedder):
        """Kullanıcı yazısını düzenlerse eski parçalar birikmemelidir."""
        parcala_ve_ekle(temp_vector_store, fake_embedder, "2026-08-01",
                        "Birinci.\n\nİkinci.\n\nÜçüncü.")
        assert temp_vector_store.table.count_rows() == 3

        parcala_ve_ekle(temp_vector_store, fake_embedder, "2026-08-01", "Tek paragraf.")
        assert temp_vector_store.table.count_rows() == 1

    def test_farkli_tarihler_birbirini_etkilemez(self, temp_vector_store, fake_embedder):
        parcala_ve_ekle(temp_vector_store, fake_embedder, "2026-08-01", "birinci gün")
        parcala_ve_ekle(temp_vector_store, fake_embedder, "2026-08-02", "ikinci gün")
        assert temp_vector_store.get_indexed_dates() == {"2026-08-01", "2026-08-02"}


class TestIndekslenmisTarihler:
    """
    Regresyon: main_window eskiden table.search().limit(10000) ile tüm
    satırları (384 boyutlu vektörleriyle) çekiyordu. Artık yalnızca
    "date" sütunu okunur ve sınır yoktur.
    """

    def test_bos_depoda_bos_kume(self, temp_vector_store):
        assert temp_vector_store.get_indexed_dates() == set()

    def test_tekrarlanan_tarihler_bir_kez_doner(self, temp_vector_store, fake_embedder):
        parcala_ve_ekle(temp_vector_store, fake_embedder, "2026-08-01",
                        "Birinci.\n\nİkinci.\n\nÜçüncü.")
        assert temp_vector_store.get_indexed_dates() == {"2026-08-01"}

    def test_silinen_tarih_listeden_cikar(self, temp_vector_store, fake_embedder):
        parcala_ve_ekle(temp_vector_store, fake_embedder, "2026-08-01", "birinci")
        parcala_ve_ekle(temp_vector_store, fake_embedder, "2026-08-02", "ikinci")

        temp_vector_store.delete_by_date("2026-08-01")

        assert temp_vector_store.get_indexed_dates() == {"2026-08-02"}

    def test_cok_sayida_kayitta_kirpilmaz(self, temp_vector_store, fake_embedder):
        # Eski kod 10.000 satırdan sonra sessizce kırpıyordu; sınır olmamalı
        parcalar = [
            {"id": f"2026-{ay:02d}-{gun:02d}_0",
             "text": f"gun {ay}-{gun}",
             "metadata": {"date": f"2026-{ay:02d}-{gun:02d}", "chunk_index": 0}}
            for ay in range(1, 13) for gun in range(1, 29)
        ]
        vektorler = fake_embedder.embed_documents([p["text"] for p in parcalar])
        temp_vector_store.add_chunks(parcalar, vektorler)

        assert len(temp_vector_store.get_indexed_dates()) == 12 * 28


class TestSilme:
    def test_olmayan_tarihi_silmek_hata_vermez(self, temp_vector_store):
        temp_vector_store.delete_by_date("2099-01-01")

    def test_bos_depoda_silmek_hata_vermez(self, temp_vector_store):
        temp_vector_store.delete_by_date("2026-08-01")
        assert temp_vector_store.table.count_rows() == 0


class TestArama:
    def test_bos_depoda_arama_bos_liste_doner(self, temp_vector_store):
        assert temp_vector_store.search([0.0] * VECTOR_DIM) == []

    def test_arama_beklenen_alanlari_doner(self, temp_vector_store, fake_embedder):
        parcala_ve_ekle(temp_vector_store, fake_embedder, "2026-08-01", "bugün spor yaptım")

        sonuc = temp_vector_store.search(fake_embedder.embed_query("spor"), limit=1)

        assert len(sonuc) == 1
        assert set(sonuc[0]) == {"id", "text", "date", "distance"}
        assert sonuc[0]["date"] == "2026-08-01"

    def test_limit_uygulanir(self, temp_vector_store, fake_embedder):
        for gun in range(1, 6):
            parcala_ve_ekle(temp_vector_store, fake_embedder, f"2026-08-0{gun}", f"gün {gun}")

        assert len(temp_vector_store.search(fake_embedder.embed_query("gün"), limit=3)) == 3

    def test_en_benzer_kayit_once_gelir(self, temp_vector_store, fake_embedder):
        parcala_ve_ekle(temp_vector_store, fake_embedder, "2026-08-01", "spor salonuna gittim")
        parcala_ve_ekle(temp_vector_store, fake_embedder, "2026-08-02", "zzzz yyyy xxxx")

        sonuc = temp_vector_store.search(fake_embedder.embed_query("spor salonuna gittim"))

        assert sonuc[0]["date"] == "2026-08-01"
        assert sonuc[0]["distance"] <= sonuc[-1]["distance"]

    def test_vektor_boyutu_sabiti_gomucuyle_uyumlu(self, fake_embedder):
        assert len(fake_embedder.embed_query("test")) == VECTOR_DIM
