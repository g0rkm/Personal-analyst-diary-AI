"""
tests/test_label_merger.py
--------------------------
Anlamca aynı etiketlerin birleştirilmesi.

Birleştirme olmadan "yürüyüş" / "yürüyüşe çıkmak" / "yürüdüm" üç ayrı
etiket sayılır ve "en çok yaptığım şey" sıralaması bölünerek yanıltıcı
olur. Gerçek embedding modeli indirilmez; benzerlikler sahte gömücüyle
deterministik olarak üretilir.
"""

import pytest

from ai.label_merger import DEFAULT_THRESHOLD, LabelMerger, cosine_similarity


class KontrolluEmbedder:
    """
    Etiketleri önceden tanımlanmış kümelere göre vektörleştirir.

    Aynı kümedeki etiketler BENZER ama özdeş değildir (~0.87 kosinüs):
    gerçek bir gömücü de öyle davranır ve ancak böyle bir kurulumda eşik
    davranışı sınanabilir. Farklı kümeler birbirine çok uzaktır (~0.03).
    """

    KUMELER = {
        "yürüyüş": 0, "yürüyüşe çıkmak": 0, "yürüdüm": 0,
        "rapor yazma": 1, "rapor hazırlamak": 1,
        "kitap okuma": 2,
    }
    BOYUT = 16

    def _vector(self, text):
        vec = [0.01] * self.BOYUT
        kume = self.KUMELER.get(text)

        if kume is None:
            # Bilinmeyen etiket: hiçbir kümeye yakın olmayan kendi yönü
            vec[self.BOYUT - 1] = 1.0
            return vec

        vec[kume] = 1.0
        # Etikete özgü küçük sapma: aynı kümedekiler özdeş olmasın
        sira = list(self.KUMELER).index(text)
        vec[3 + sira] += 0.4
        return vec

    def embed_documents(self, documents):
        return [self._vector(d) for d in documents]

    def embed_query(self, query):
        return self._vector(query)


@pytest.fixture
def merger(temp_db):
    return LabelMerger(KontrolluEmbedder(), temp_db)


def facet_ekle(db, tarih, kind, labels):
    db.save_entry(tarih, f"{tarih} metni", happiness_score=5)
    db.save_insight(tarih, f"{tarih} metni", facets={kind: labels})


class TestKosinusBenzerligi:
    def test_ayni_vektor_bir(self):
        assert cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)

    def test_dik_vektorler_sifir(self):
        assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_olcek_farki_etkilemez(self):
        assert cosine_similarity([1, 1], [5, 5]) == pytest.approx(1.0)

    @pytest.mark.parametrize("a,b", [([], [1]), ([1], []), ([1, 2], [1])])
    def test_gecersiz_girdi_sifir(self, a, b):
        assert cosine_similarity(a, b) == 0.0

    def test_sifir_vektor_sifir(self):
        assert cosine_similarity([0, 0], [1, 1]) == 0.0


class TestKanonikEsleme:
    def test_bos_veritabaninda_etiket_kendisi_kanoniktir(self, merger):
        assert merger.canonical_for("activity", "yürüyüş") == "yürüyüş"

    def test_benzer_etiket_mevcut_olana_baglanir(self, merger, temp_db):
        facet_ekle(temp_db, "2026-03-01", "activity", ["yürüyüş"])

        assert merger.canonical_for("activity", "yürüyüşe çıkmak") == "yürüyüş"

    def test_alakasiz_etiket_baglanmaz(self, merger, temp_db):
        facet_ekle(temp_db, "2026-03-01", "activity", ["yürüyüş"])

        assert merger.canonical_for("activity", "rapor yazma") == "rapor yazma"

    def test_ayni_etiket_oldugu_gibi_doner(self, merger, temp_db):
        facet_ekle(temp_db, "2026-03-01", "activity", ["yürüyüş"])

        assert merger.canonical_for("activity", "yürüyüş") == "yürüyüş"

    def test_farkli_turler_karismaz(self, merger, temp_db):
        """"spor" hem aktivite hem ertelenen olabilir; ayrı sayılmalı."""
        facet_ekle(temp_db, "2026-03-01", "activity", ["yürüyüş"])

        # postponed türünde henüz hiçbir etiket yok
        assert merger.canonical_for("postponed", "yürüyüşe çıkmak") == "yürüyüşe çıkmak"

    def test_bos_etiket_oldugu_gibi_doner(self, merger):
        assert merger.canonical_for("activity", "") == ""

    def test_baglanma_alias_tablosuna_yazilir(self, merger, temp_db):
        facet_ekle(temp_db, "2026-03-01", "activity", ["yürüyüş"])
        merger.canonical_for("activity", "yürüyüşe çıkmak")

        aliases = temp_db.get_label_aliases("activity")
        assert {"kind": "activity", "alias": "yürüyüşe çıkmak",
                "canonical": "yürüyüş"} in aliases

    def test_ayni_etiket_alias_olarak_yazilmaz(self, merger, temp_db):
        facet_ekle(temp_db, "2026-03-01", "activity", ["yürüyüş"])
        merger.canonical_for("activity", "yürüyüş")

        assert temp_db.get_label_aliases("activity") == []


class TestEsik:
    def test_yuksek_esik_birlestirmeyi_engeller(self, temp_db):
        facet_ekle(temp_db, "2026-03-01", "activity", ["yürüyüş"])
        katı = LabelMerger(KontrolluEmbedder(), temp_db, threshold=0.999)

        assert katı.canonical_for("activity", "yürüyüşe çıkmak") == "yürüyüşe çıkmak"

    def test_dusuk_esik_daha_cok_birlestirir(self, temp_db):
        facet_ekle(temp_db, "2026-03-01", "activity", ["yürüyüş"])
        gevşek = LabelMerger(KontrolluEmbedder(), temp_db, threshold=0.0)

        assert gevşek.canonical_for("activity", "rapor yazma") == "yürüyüş"

    def test_varsayilan_esik_makul_aralikta(self):
        assert 0.5 < DEFAULT_THRESHOLD < 1.0


class TestFacetBirlestirme:
    def test_kanonik_ve_ham_ikilisi_doner(self, merger, temp_db):
        facet_ekle(temp_db, "2026-03-01", "activity", ["yürüyüş"])

        sonuc = merger.merge_facets({"activity": ["yürüyüşe çıkmak"]})

        assert sonuc == {"activity": [("yürüyüş", "yürüyüşe çıkmak")]}

    def test_ayni_kanonige_dusenler_tekillestirilir(self, merger, temp_db):
        facet_ekle(temp_db, "2026-03-01", "activity", ["yürüyüş"])

        sonuc = merger.merge_facets({"activity": ["yürüyüşe çıkmak", "yürüdüm"]})

        assert len(sonuc["activity"]) == 1

    def test_bos_sozluk(self, merger):
        assert merger.merge_facets({}) == {}
        assert merger.merge_facets(None) == {}

    def test_birden_fazla_tur(self, merger):
        sonuc = merger.merge_facets({
            "activity": ["yürüyüş"],
            "postponed": ["rapor yazma"],
        })
        assert set(sonuc) == {"activity", "postponed"}


class TestSayimaEtkisi:
    """Birleştirmenin asıl amacı: sıralamanın bölünmemesi."""

    def test_birlestirme_olmadan_sayim_bolunur(self, temp_db):
        from core.analytics import top_facets

        for tarih, etiket in [("2026-03-01", "yürüyüş"),
                              ("2026-03-02", "yürüyüşe çıkmak"),
                              ("2026-03-03", "yürüdüm")]:
            facet_ekle(temp_db, tarih, "activity", [etiket])

        sonuc = top_facets(temp_db, "activity", "2026-03-01", "2026-03-31")
        assert len(sonuc) == 3          # üçe bölünmüş
        assert sonuc[0].days == 1

    def test_birlestirme_ile_tek_satirda_toplanir(self, temp_db):
        from core.analytics import top_facets

        merger = LabelMerger(KontrolluEmbedder(), temp_db)
        for tarih, etiket in [("2026-03-01", "yürüyüş"),
                              ("2026-03-02", "yürüyüşe çıkmak"),
                              ("2026-03-03", "yürüdüm")]:
            temp_db.save_entry(tarih, f"{tarih} metni", happiness_score=5)
            temp_db.save_insight(tarih, f"{tarih} metni",
                                 facets=merger.merge_facets({"activity": [etiket]}))

        sonuc = top_facets(temp_db, "activity", "2026-03-01", "2026-03-31")
        assert len(sonuc) == 1
        assert sonuc[0] == ("yürüyüş", 3)
