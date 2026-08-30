"""
tests/test_token_budget.py
--------------------------
Prompt token bütçesi.

Bu katman olmadan bir aylık günlük bağlam penceresini aşıyor ve model
"Requested tokens exceed context window" hatası veriyordu.
"""

import pytest

from core.token_budget import (
    count_tokens,
    estimate_tokens,
    fit_to_budget,
    prompt_budget,
)


def sayac(chars_per_token=4):
    """Deterministik sahte tokenizer: her N karakter = 1 token."""
    return lambda metin: max(1, -(-len(metin) // chars_per_token))


class TestTahmin:
    def test_bos_metin_sifir(self):
        assert estimate_tokens("") == 0

    def test_tahmin_pozitif(self):
        assert estimate_tokens("merhaba dünya") > 0

    def test_uzun_metin_daha_cok_token(self):
        assert estimate_tokens("a" * 300) > estimate_tokens("a" * 30)

    def test_tahmin_temkinli_yani_yukari_saparr(self):
        # 420 karakterlik Türkçe metin gerçekte ~95-140 token;
        # tahmin bunun altına DÜŞMEMELİ (taşma riski doğar)
        assert estimate_tokens("a" * 420) >= 95


class TestSayim:
    def test_sayac_verilmezse_tahmin_kullanilir(self):
        assert count_tokens("merhaba", None) == estimate_tokens("merhaba")

    def test_sayac_verilirse_o_kullanilir(self):
        assert count_tokens("abcdefgh", sayac(4)) == 2

    def test_bos_metin_sifir(self):
        assert count_tokens("", sayac()) == 0

    def test_patlayan_sayac_tahmine_duser(self):
        def patlayan(_):
            raise RuntimeError("tokenizer bozuk")

        # Bütçe hesabı asla çökmemeli
        assert count_tokens("merhaba", patlayan) == estimate_tokens("merhaba")


class TestButceyeSigdirma:
    def test_hepsi_sigiyorsa_hepsi_alinir(self):
        sonuc = fit_to_budget(["abcd", "efgh"], budget=100, counter=sayac(4))
        assert sonuc.kept == ["abcd", "efgh"]
        assert sonuc.dropped == 0
        assert sonuc.truncated is False

    def test_butce_dolunca_sondakiler_atilir(self):
        # her parça 1 token, bütçe 2
        sonuc = fit_to_budget(["abcd", "efgh", "ijkl"], budget=2, counter=sayac(4))
        assert sonuc.kept == ["abcd", "efgh"]
        assert sonuc.dropped == 1
        assert sonuc.truncated is True

    def test_kullanilan_token_raporlanir(self):
        sonuc = fit_to_budget(["abcd", "efgh"], budget=10, counter=sayac(4))
        assert sonuc.used_tokens == 2

    def test_tam_sinirda_parca_alinir(self):
        sonuc = fit_to_budget(["abcd", "efgh"], budget=2, counter=sayac(4))
        assert sonuc.dropped == 0

    def test_tek_parca_bile_sigmazsa_hicbiri_alinmaz(self):
        sonuc = fit_to_budget(["a" * 100], budget=2, counter=sayac(4))
        assert sonuc.kept == []
        assert sonuc.dropped == 1

    def test_bos_liste(self):
        sonuc = fit_to_budget([], budget=100, counter=sayac())
        assert sonuc.kept == [] and sonuc.dropped == 0 and sonuc.used_tokens == 0

    @pytest.mark.parametrize("butce", [0, -5])
    def test_sifir_veya_negatif_butce_hicbir_sey_almaz(self, butce):
        sonuc = fit_to_budget(["abcd"], budget=butce, counter=sayac(4))
        assert sonuc.kept == [] and sonuc.dropped == 1

    def test_sira_korunur(self):
        parcalar = ["bir", "iki", "uc"]
        assert fit_to_budget(parcalar, 100, sayac(4)).kept == parcalar


class TestPromptButcesi:
    def test_paylar_dusulur(self):
        assert prompt_budget(4096, reserved_for_response=1024,
                             reserved_for_system=400) == 2672

    def test_sistem_payi_istege_bagli(self):
        assert prompt_budget(4096, reserved_for_response=1024) == 3072

    def test_negatif_sonuc_sifira_cekilir(self):
        assert prompt_budget(1000, reserved_for_response=2000) == 0
