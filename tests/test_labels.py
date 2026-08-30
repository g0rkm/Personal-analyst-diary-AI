"""
tests/test_labels.py
--------------------
Etiket normalleştirme.

Sayım sorguları etiketleri birebir eşleştirdiği için, "Spor" ile "spor "
aynı şeye indirgenmezse "en çok ertelediğim şey" sıralaması bölünür.
"""

import pytest

from core.labels import MAX_LABEL_LENGTH, clean_labels, lower_tr, normalize


class TestTurkceKucukHarf:
    @pytest.mark.parametrize("girdi,beklenen", [
        ("IĞDIR", "ığdır"),
        ("İSTANBUL", "istanbul"),
        ("Ilık", "ılık"),
        ("İyi", "iyi"),
    ])
    def test_noktali_ve_noktasiz_i_dogru_esler(self, girdi, beklenen):
        assert lower_tr(girdi) == beklenen

    def test_diger_turkce_harfler_bozulmaz(self):
        assert lower_tr("ÇĞÖŞÜ") == "çğöşü"


class TestNormalizasyon:
    def test_bosluklar_kirpilir(self):
        assert normalize("  spor  ") == "spor"

    def test_buyuk_harf_kucultulur(self):
        assert normalize("Rapor Yazma") == "rapor yazma"

    def test_ic_bosluklar_teklenir(self):
        assert normalize("rapor    yazma") == "rapor yazma"

    def test_satir_sonlari_bosluga_donusur(self):
        assert normalize("rapor\nyazma") == "rapor yazma"

    @pytest.mark.parametrize("girdi", ['"spor"', "spor.", "(spor)", "- spor -", "spor!"])
    def test_cevreleyen_noktalama_atilir(self, girdi):
        assert normalize(girdi) == "spor"

    @pytest.mark.parametrize("girdi", ["", "   ", "...", "-", None])
    def test_anlamsiz_girdi_bos_doner(self, girdi):
        assert normalize(girdi) == ""

    def test_ic_noktalama_korunur(self):
        # "dr. randevusu" gibi etiketlerde iç nokta anlamlıdır
        assert normalize("dr. randevusu") == "dr. randevusu"

    def test_cok_uzun_etiket_kisaltilir(self):
        sonuc = normalize("kelime " * 20)
        assert len(sonuc) <= MAX_LABEL_LENGTH

    def test_kisaltma_kelime_ortasindan_kesmez(self):
        sonuc = normalize("a" * 10 + " " + "b" * 60)
        assert sonuc == "a" * 10

    def test_unicode_birlesimi_teklenir(self):
        # "é" tek karakter ile "e + birleşik aksan" aynı etiket sayılmalı
        assert normalize("café") == normalize("café")


class TestListeTemizleme:
    def test_normalize_eder_ve_sirayi_korur(self):
        assert clean_labels(["Spor", "Yürüyüş"]) == ["spor", "yürüyüş"]

    def test_tekrarlari_teker(self):
        assert clean_labels(["Spor", "spor ", "SPOR"]) == ["spor"]

    def test_bos_ogeleri_atar(self):
        assert clean_labels(["", "  ", "...", "spor"]) == ["spor"]

    def test_metin_disi_ogeleri_atar(self):
        assert clean_labels(["spor", None, 42, [], "yürüyüş"]) == ["spor", "yürüyüş"]

    def test_limit_uygulanir(self):
        assert clean_labels([f"e{i}" for i in range(20)], limit=3) == ["e0", "e1", "e2"]

    def test_none_bos_liste_doner(self):
        assert clean_labels(None) == []

    def test_duz_metin_harflere_bolunmez(self):
        """Regresyon: model liste yerine metin döndürünce harfler etiket sanılıyordu."""
        assert clean_labels("spor") == []

    def test_sayi_gibi_yinelenemez_girdi_bos_doner(self):
        assert clean_labels(42) == []
