"""
tests/test_query_intent.py
--------------------------
Sorunun hangi analizi istediğinin belirlenmesi.

En önemli testler kullanıcının dört örnek sorusudur; bunların doğru
rotaya gitmesi tüm analiz sisteminin ön koşulu.
"""

import pytest

from core.query_intent import (
    CONSISTENCY,
    CORRELATION,
    MOOD,
    RANKING,
    SUMMARY,
    is_analytical,
    parse_intents,
)


def kisa(query):
    """Yardımcı: (tür, etiket) ikilileri."""
    return [(i.kind, i.facet) for i in parse_intents(query)]


class TestOrnekSorular:
    """Kullanıcının verdiği dört soru — sistemin varlık nedeni."""

    def test_bu_ay_genel_ruh_halim(self):
        assert kisa("Bu ay genel ruh halim nasıldı") == [(MOOD, None)]

    def test_stresli_oldugumda_ne_iyi_geliyor(self):
        assert kisa("Stresli olduğumda bana ne iyi geliyor") == [(CORRELATION, "helped")]

    def test_bu_hafta_en_cok_neyi_erteledim(self):
        assert kisa("Bu hafta en çok neyi erteledim") == [(RANKING, "postponed")]

    def test_mart_ayinda_iki_analiz_birden(self):
        sonuc = kisa("Mart ayında en çok ertelediğim ve en sürekli yaptığım şey neydi")
        assert sonuc == [(RANKING, "postponed"), (CONSISTENCY, "activity")]


class TestAnalizGerektirmeyenSorular:
    """Belirli bir anıyı arayan sorular RAG'a düşmeli."""

    @pytest.mark.parametrize("soru", [
        "Geçen ay spora ne zaman başlamıştım",
        "kendimi neden kötü hissediyorum",
        "dün akşam ne olmuştu",
        "o kitabın adı neydi",
        "",
        "   ",
    ])
    def test_bos_liste_doner(self, soru):
        assert parse_intents(soru) == []

    def test_none_sorgu(self):
        assert parse_intents(None) == []

    def test_is_analytical_bayragi(self):
        assert is_analytical("en çok neyi erteledim") is True
        assert is_analytical("spora ne zaman başladım") is False


class TestSiralama:
    @pytest.mark.parametrize("soru", [
        "en çok neyi erteledim",
        "en sık neyi erteledim",
        "en fazla neyi erteledim",
    ])
    def test_siklik_belirtecleri(self, soru):
        assert kisa(soru) == [(RANKING, "postponed")]

    def test_en_az_ters_siralama_ister(self):
        intent = parse_intents("en az neyi erteledim")[0]
        assert intent.kind == RANKING
        assert intent.ascending is True

    def test_en_cok_normal_siralama(self):
        assert parse_intents("en çok neyi erteledim")[0].ascending is False

    def test_etiket_belirtilmezse_aktivite_varsayilir(self):
        assert kisa("bu hafta en çok ne yaptım") == [(RANKING, "activity")]


class TestSureklilik:
    @pytest.mark.parametrize("soru", [
        "en sürekli yaptığım şey",
        "en düzenli yaptığım şey",
        "hangi alışkanlığımı sürdürdüm",
        "her gün yaptığım şey ne",
    ])
    def test_süreklilik_belirtecleri(self, soru):
        assert parse_intents(soru)[0].kind == CONSISTENCY

    def test_surekli_siklik_belirtecini_yener(self):
        """"en sürekli" hem RANKING hem CONSISTENCY işareti taşır."""
        assert parse_intents("en sürekli yaptığım şey")[0].kind == CONSISTENCY


class TestKorelasyon:
    @pytest.mark.parametrize("soru", [
        "stresli olduğumda ne iyi geliyor",
        "yorgun olunca bana ne iyi geliyor",
        "kötü hissettiğim zaman ne işe yarıyor",
    ])
    def test_korelasyon_belirtecleri(self, soru):
        assert parse_intents(soru)[0].kind == CORRELATION

    def test_varsayilan_hedef_iyi_gelenler(self):
        assert parse_intents("stresli olduğumda ne yapıyorum")[0].kind == CORRELATION


class TestEtiketTuruTespiti:
    @pytest.mark.parametrize("soru,beklenen", [
        ("en çok neyi erteledim", "postponed"),
        ("en çok ne yaptım", "activity"),
        ("en çok ne iyi geldi", "helped"),
        ("en çok ne zorladı", "hindered"),
        ("en çok kimlerle görüştüm", "person"),
        ("en çok nerede vakit geçirdim", "place"),
    ])
    def test_fiil_kokunden_etiket_turu(self, soru, beklenen):
        assert parse_intents(soru)[0].facet == beklenen

    @pytest.mark.parametrize("kelime", ["yaprak", "yapı", "yapışkan"])
    def test_yap_koku_alakasiz_kelimelerle_eslesmez(self, kelime):
        # "yapt" kökü seçildi; "yaprak" gibi kelimeler aktivite sanılmamalı
        assert parse_intents(f"en çok {kelime} gördüm")[0].facet == "activity"


class TestBelirsizSorular:
    """
    MOOD/SUMMARY dönemin geneliyle ilgilidir. Cümlede ayrıca belirli bir
    etiket türü soruluyorsa soru bu kalıplara oturmaz; yanlış analiz
    sunmaktansa RAG'a düşmek gerekir.
    """

    def test_kimlerle_gorusunce_moralim(self):
        assert parse_intents("kimlerle görüşünce moralim düzeliyor") == []

    def test_sade_ruh_hali_sorusu_calisir(self):
        assert kisa("bu ay ruh halim nasıldı") == [(MOOD, None)]


class TestOzet:
    @pytest.mark.parametrize("soru", ["bu ayı özetle", "genel bir özet ver"])
    def test_ozet_belirtecleri(self, soru):
        assert parse_intents(soru)[0].kind == SUMMARY


class TestCokluNiyet:
    def test_ve_ile_ayrilan_iki_istek(self):
        sonuc = kisa("en çok neyi erteledim ve en sürekli ne yaptım")
        assert len(sonuc) == 2

    def test_virgul_ile_ayrilan(self):
        sonuc = kisa("ruh halim nasıldı, en çok neyi erteledim")
        assert (MOOD, None) in sonuc
        assert (RANKING, "postponed") in sonuc

    def test_ayni_istek_tekrarlanmaz(self):
        sonuc = kisa("en çok neyi erteledim ve en çok neyi erteledim")
        assert len(sonuc) == 1

    def test_sira_korunur(self):
        sonuc = kisa("en çok neyi erteledim ve en sürekli yaptığım şey")
        assert sonuc[0][0] == RANKING
        assert sonuc[1][0] == CONSISTENCY
