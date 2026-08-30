"""
tests/test_insight_extractor.py
-------------------------------
Günlük kayıtlarından yapısal veri çıkarımı.

Gerçek model kullanılmaz: FakeLLM.complete_json hazır yanıtlar döndürür.
Buradaki testlerin asıl işi, modelin bozuk/eksik/aşırı çıktı verdiği
durumlarda çıkarımın çökmeden makul varsayılanlara düşmesini güvence
altına almak.
"""

import pytest

from ai.insight_extractor import (
    CORE_FACET_FIELDS,
    CORE_SCHEMA,
    EXTENDED_SCHEMA,
    MAX_LABELS_PER_KIND,
    InsightExtractor,
)
from tests.conftest import FakeLLM

TAM_CEKIRDEK = {
    "mood": 4,
    "energy": 6,
    "summary": "Spor yapmış ama raporu ertelemiş.",
    "activities": ["Spor", "kitap okuma"],
    "postponed": ["Rapor yazma"],
    "helped": ["yürüyüş"],
    "hindered": ["uykusuzluk"],
    "emotions": ["yorgunluk"],
}
TAM_GENIS = {
    "sleep_quality": 3,
    "people": ["annem"],
    "places": ["ofis"],
    "physical": ["baş ağrısı"],
}


def cikarici(cekirdek=None, genis=None, extended=True):
    yanitlar = [cekirdek if cekirdek is not None else TAM_CEKIRDEK]
    if extended:
        yanitlar.append(genis if genis is not None else TAM_GENIS)
    return InsightExtractor(FakeLLM(json_responses=yanitlar), extended=extended)


class TestBasariliCikarim:
    def test_sayisal_alanlar_okunur(self):
        sonuc = cikarici().extract("bugün spor yaptım")
        assert sonuc.mood == 4
        assert sonuc.energy == 6
        assert sonuc.sleep_quality == 3

    def test_ozet_okunur(self):
        assert cikarici().extract("metin").summary == "Spor yapmış ama raporu ertelemiş."

    def test_cekirdek_etiketler_kind_e_eslenir(self):
        facets = cikarici().extract("metin").facets
        assert facets["activity"] == ["spor", "kitap okuma"]
        assert facets["postponed"] == ["rapor yazma"]
        assert facets["helped"] == ["yürüyüş"]
        assert facets["hindered"] == ["uykusuzluk"]
        assert facets["emotion"] == ["yorgunluk"]

    def test_genisletilmis_etiketler_de_eslenir(self):
        facets = cikarici().extract("metin").facets
        assert facets["person"] == ["annem"]
        assert facets["place"] == ["ofis"]
        assert facets["physical"] == ["baş ağrısı"]

    def test_etiketler_normalize_edilir(self):
        # "Spor" -> "spor"; sayım birebir eşleştirdiği için şart
        assert "spor" in cikarici().extract("metin").facets["activity"]

    def test_bos_degil(self):
        assert cikarici().extract("metin").is_empty is False


class TestGenisletilmisGecisKapali:
    def test_ikinci_cagri_yapilmaz(self):
        llm = FakeLLM(json_responses=[TAM_CEKIRDEK])
        InsightExtractor(llm, extended=False).extract("metin")
        assert len(llm.received_messages) == 1

    def test_genisletilmis_alanlar_bos_kalir(self):
        sonuc = InsightExtractor(
            FakeLLM(json_responses=[TAM_CEKIRDEK]), extended=False
        ).extract("metin")
        assert "person" not in sonuc.facets
        assert sonuc.sleep_quality == -1

    def test_iki_gecis_iki_cagri_yapar(self):
        llm = FakeLLM(json_responses=[TAM_CEKIRDEK, TAM_GENIS])
        InsightExtractor(llm, extended=True).extract("metin")
        assert len(llm.received_messages) == 2

    def test_iki_gecis_farkli_semalar_kullanir(self):
        llm = FakeLLM(json_responses=[TAM_CEKIRDEK, TAM_GENIS])
        InsightExtractor(llm, extended=True).extract("metin")
        assert llm.received_schemas == [CORE_SCHEMA, EXTENDED_SCHEMA]


class TestBozukCikti:
    """Model bozuk veri verdiğinde çıkarım çökmemeli."""

    def test_bos_sozluk_varsayilanlara_duser(self):
        sonuc = cikarici(cekirdek={}, genis={}).extract("metin")
        assert sonuc.mood == 0
        assert sonuc.summary == ""
        assert sonuc.facets == {}
        assert sonuc.is_empty is True

    def test_eksik_alanlar_tolere_edilir(self):
        sonuc = cikarici(cekirdek={"mood": 2}, genis={}).extract("metin")
        assert sonuc.mood == 2
        assert sonuc.summary == ""

    @pytest.mark.parametrize("bozuk_mood", ["çok iyi", None, [], {"a": 1}])
    def test_sayisal_olmayan_mood_varsayilana_duser(self, bozuk_mood):
        sonuc = cikarici(cekirdek={"mood": bozuk_mood}, genis={}).extract("metin")
        assert sonuc.mood == 0

    @pytest.mark.parametrize("girdi,beklenen", [(99, 10), (-99, -10), (7, 7)])
    def test_mood_araliga_sikistirilir(self, girdi, beklenen):
        sonuc = cikarici(cekirdek={"mood": girdi}, genis={}).extract("metin")
        assert sonuc.mood == beklenen

    def test_metin_olmayan_ozet_bos_doner(self):
        sonuc = cikarici(cekirdek={"summary": 42}, genis={}).extract("metin")
        assert sonuc.summary == ""

    def test_cok_uzun_ozet_kisaltilir(self):
        sonuc = cikarici(cekirdek={"summary": "kelime " * 100}, genis={}).extract("metin")
        assert len(sonuc.summary) <= 165
        assert sonuc.summary.endswith("...")

    def test_liste_olmayan_etiket_alani_atlanir(self):
        sonuc = cikarici(cekirdek={"activities": "spor"}, genis={}).extract("metin")
        # str üzerinde gezinip harfleri etiket sanmamalı
        assert sonuc.facets.get("activity") in (None, [])

    def test_etiket_listesindeki_metin_disi_ogeler_atilir(self):
        sonuc = cikarici(
            cekirdek={"activities": ["spor", None, 42, "yürüyüş"]}, genis={}
        ).extract("metin")
        assert sonuc.facets["activity"] == ["spor", "yürüyüş"]

    def test_bos_etiketler_atilir(self):
        sonuc = cikarici(cekirdek={"activities": ["", "  ", "...", "spor"]},
                         genis={}).extract("metin")
        assert sonuc.facets["activity"] == ["spor"]

    def test_tekrarlanan_etiketler_tekillestirilir(self):
        sonuc = cikarici(cekirdek={"activities": ["Spor", "spor", "SPOR"]},
                         genis={}).extract("metin")
        assert sonuc.facets["activity"] == ["spor"]

    def test_asiri_uzun_etiket_listesi_sinirlanir(self):
        sonuc = cikarici(
            cekirdek={"activities": [f"aktivite {i}" for i in range(50)]}, genis={}
        ).extract("metin")
        assert len(sonuc.facets["activity"]) == MAX_LABELS_PER_KIND


class TestBosGirdi:
    @pytest.mark.parametrize("icerik", ["", "   ", "\n\n", None])
    def test_bos_kayit_model_cagirmaz(self, icerik):
        llm = FakeLLM(json_responses=[TAM_CEKIRDEK])
        sonuc = InsightExtractor(llm).extract(icerik)
        assert llm.received_messages == []
        assert sonuc.is_empty is True


class TestPrompt:
    def test_gunluk_metni_kullaniciya_mesaji_olarak_gider(self):
        llm = FakeLLM(json_responses=[TAM_CEKIRDEK, TAM_GENIS])
        InsightExtractor(llm).extract("bugün koşuya çıktım")
        assert llm.received_messages[0][-1]["content"] == "bugün koşuya çıktım"

    def test_uydurma_yasagi_prompta_yazilir(self):
        llm = FakeLLM(json_responses=[TAM_CEKIRDEK, TAM_GENIS])
        InsightExtractor(llm).extract("metin")
        assert "uydurma" in llm.received_messages[0][0]["content"].lower()

    def test_cok_uzun_kayit_kirpilir(self):
        llm = FakeLLM(json_responses=[TAM_CEKIRDEK, TAM_GENIS])
        InsightExtractor(llm).extract("a" * 50_000)
        assert len(llm.received_messages[0][-1]["content"]) <= 4000


class TestSemaTutarliligi:
    def test_cekirdek_sema_alanlari_facet_eslemesiyle_uyumlu(self):
        for field in CORE_FACET_FIELDS:
            assert field in CORE_SCHEMA["properties"]

    def test_zorunlu_alanlar_tanimli(self):
        for field in CORE_SCHEMA["required"]:
            assert field in CORE_SCHEMA["properties"]
