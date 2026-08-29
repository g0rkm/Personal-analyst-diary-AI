"""
tests/test_chunker.py
---------------------
Günlük metinlerinin vektör deposu için parçalara bölünmesi.
"""

import pytest

from ai.chunker import chunk_entry


class TestBosGirdiler:
    @pytest.mark.parametrize("icerik", ["", "   ", "\n\n", "\t \n  "])
    def test_bos_metin_parca_uretmez(self, icerik):
        assert chunk_entry("2026-08-29", icerik) == []


class TestParagrafBolme:
    def test_kisa_metin_tek_parca(self):
        parcalar = chunk_entry("2026-08-29", "Bugün güzel bir gündü.")
        assert len(parcalar) == 1
        assert parcalar[0]["text"] == "Bugün güzel bir gündü."

    def test_paragraflar_ayri_parcalara_bolunur(self):
        metin = "Birinci paragraf.\n\nİkinci paragraf.\n\nÜçüncü paragraf."
        parcalar = chunk_entry("2026-08-29", metin)
        assert len(parcalar) == 3
        assert parcalar[1]["text"] == "İkinci paragraf."

    def test_tek_satir_sonu_bolmez(self):
        # Tek "\n" paragraf ayracı değildir
        parcalar = chunk_entry("2026-08-29", "birinci satır\nikinci satır")
        assert len(parcalar) == 1

    def test_bos_paragraflar_atlanir(self):
        metin = "Birinci.\n\n\n\n\n\nİkinci."
        assert len(chunk_entry("2026-08-29", metin)) == 2

    def test_paragraf_kenar_bosluklari_temizlenir(self):
        parcalar = chunk_entry("2026-08-29", "   boşluklu paragraf   ")
        assert parcalar[0]["text"] == "boşluklu paragraf"


class TestUzunParagraflar:
    def test_uzun_paragraf_kelime_sinirinda_bolunur(self):
        metin = " ".join(["kelime"] * 400)
        parcalar = chunk_entry("2026-08-29", metin, max_words=150)
        assert len(parcalar) == 3  # 150 + 150 + 100

    def test_bolme_sirasinda_kelime_kaybolmaz(self):
        kelimeler = [f"k{i}" for i in range(320)]
        parcalar = chunk_entry("2026-08-29", " ".join(kelimeler), max_words=100)
        birlesik = " ".join(p["text"] for p in parcalar).split()
        assert birlesik == kelimeler

    def test_max_words_sinirina_uyulur(self):
        metin = " ".join(["kelime"] * 250)
        parcalar = chunk_entry("2026-08-29", metin, max_words=100)
        assert all(len(p["text"].split()) <= 100 for p in parcalar)

    def test_tam_sinirdaki_paragraf_bolunmez(self):
        metin = " ".join(["kelime"] * 150)
        assert len(chunk_entry("2026-08-29", metin, max_words=150)) == 1


class TestUstVeri:
    def test_id_tarih_ve_sira_icerir(self):
        parcalar = chunk_entry("2026-08-29", "Birinci.\n\nİkinci.")
        assert parcalar[0]["id"] == "2026-08-29_0"
        assert parcalar[1]["id"] == "2026-08-29_1"

    def test_idler_benzersizdir(self):
        metin = "\n\n".join(f"Paragraf {i}." for i in range(10))
        parcalar = chunk_entry("2026-08-29", metin)
        assert len({p["id"] for p in parcalar}) == len(parcalar)

    def test_metadata_tarihi_tasir(self):
        parcalar = chunk_entry("2026-08-29", "metin")
        assert parcalar[0]["metadata"]["date"] == "2026-08-29"
        assert parcalar[0]["metadata"]["chunk_index"] == 0

    def test_sira_numarasi_paragraf_ve_bolme_boyunca_artar(self):
        metin = "Kısa paragraf.\n\n" + " ".join(["kelime"] * 300)
        parcalar = chunk_entry("2026-08-29", metin, max_words=150)
        assert [p["metadata"]["chunk_index"] for p in parcalar] == [0, 1, 2]
