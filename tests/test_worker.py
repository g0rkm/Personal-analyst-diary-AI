"""
tests/test_worker.py
--------------------
Arka plan QThread'leri: Akıllı Yönlendirici'nin rota seçimi, indeksleme
ve duygu analizi.

QThread'ler burada start() ile değil doğrudan run() çağrılarak sınanır;
böylece testler senkron kalır ve olay döngüsüne bağımlı olmaz.
"""

import pytest

pytestmark = pytest.mark.qt


@pytest.fixture
def sahte_rag(fake_llm, fake_embedder, temp_vector_store):
    from ai.rag_engine import RAGEngine
    return RAGEngine(fake_embedder, temp_vector_store, fake_llm)


class SinyalToplayici:
    """QThread sinyallerine bağlanıp yayılan değerleri biriktirir."""

    def __init__(self, worker):
        self.tokens = []
        self.modes = []
        self.finished_with = []
        self.errors = []
        worker.token_received.connect(self.tokens.append)
        worker.mode_detected.connect(lambda m, msg: self.modes.append((m, msg)))
        worker.finished.connect(self.finished_with.append)
        worker.error.connect(self.errors.append)

    @property
    def metin(self):
        return "".join(self.tokens)


class TestYonlendirme:
    """
    Regresyon: ay adları substring ile aranıyordu; "çekimser" -> Ekim,
    "smart" -> Mart olarak algılanıyor ve sıradan sorular RAG yerine
    aylık rapor moduna düşüyordu.
    """

    def test_zaman_ifadesiz_soru_rag_rotasina_gider(self, qtbot, sahte_rag):
        from ai.worker import RAGChatWorker
        worker = RAGChatWorker(sahte_rag, "spora ne zaman başlamıştım")
        toplayici = SinyalToplayici(worker)

        worker.run()

        assert toplayici.modes[0][0] == "RAG"
        assert toplayici.finished_with == [None]

    def test_ozet_sorusu_sql_rotasina_gider(self, qtbot, sahte_rag, temp_db, monkeypatch):
        """"Özetle" toplu sayım değil, dönemin okunmasını ister."""
        from ai import worker as worker_module
        from ai.worker import RAGChatWorker

        monkeypatch.setattr(worker_module, "Database", lambda: temp_db)
        temp_db.save_entry("2026-08-01", "koşuya çıktım", happiness_score=8)

        worker = RAGChatWorker(sahte_rag, "bu ayı özetle")
        toplayici = SinyalToplayici(worker)

        worker.run()

        assert toplayici.modes[0][0] == "SQL"
        assert toplayici.finished_with[0] is not None

    @pytest.mark.parametrize("soru", [
        "Bu ay genel ruh halim nasıldı",
        "Bu hafta en çok neyi erteledim",
        "Mart ayında en çok ertelediğim ve en sürekli yaptığım şey neydi",
    ])
    def test_analiz_sorulari_analiz_rotasina_gider(self, qtbot, sahte_rag,
                                                   temp_db, monkeypatch, soru):
        """
        Kullanıcının örnek soruları toplu SAYIM gerektirir; günlükleri
        prompt'a yığan eski yol yerine analiz motoruna gitmelidir.
        """
        from ai import worker as worker_module
        from ai.worker import RAGChatWorker

        monkeypatch.setattr(worker_module, "Database", lambda: temp_db)
        temp_db.save_entry("2026-08-01", "koşuya çıktım", happiness_score=8)

        worker = RAGChatWorker(sahte_rag, soru)
        toplayici = SinyalToplayici(worker)

        worker.run()

        assert toplayici.modes[0][0] == "ANALYSIS"

    def test_zaman_ifadesiz_analiz_sorusu_da_calisir(self, qtbot, sahte_rag,
                                                     temp_db, monkeypatch):
        """"Stresli olduğumda ne iyi geliyor" — zaman ifadesi yok, tüm geçmiş."""
        from ai import worker as worker_module
        from ai.worker import RAGChatWorker

        monkeypatch.setattr(worker_module, "Database", lambda: temp_db)

        worker = RAGChatWorker(sahte_rag, "stresli olduğumda bana ne iyi geliyor")
        toplayici = SinyalToplayici(worker)

        worker.run()

        assert toplayici.modes[0][0] == "ANALYSIS"

    def test_analiz_sorusunda_sayilar_prompta_hazir_gider(self, qtbot, sahte_rag,
                                                          temp_db, monkeypatch, fake_llm):
        """Model sayı üretmemeli; sayılar SQL'den hesaplanıp verilmeli."""
        from ai import worker as worker_module
        from ai.worker import RAGChatWorker

        monkeypatch.setattr(worker_module, "Database", lambda: temp_db)
        for gun in range(1, 5):
            temp_db.save_entry(f"2026-08-0{gun}", "metin", happiness_score=5)
            temp_db.save_insight(f"2026-08-0{gun}", "metin",
                                 summary="özet", facets={"postponed": ["spor"]})

        worker = RAGChatWorker(sahte_rag, "bu ay en çok neyi erteledim")
        worker.run()

        sistem = fake_llm.received_messages[-1][0]["content"]
        assert "spor — 4 gün" in sistem

    @pytest.mark.parametrize("sorgu", [
        "çekimser kaldığım günler",
        "smart saat aldım",
        "kasımpatı çiçeği aldım",
    ])
    def test_yanlis_ay_eslesmesi_sql_rotasini_tetiklemez(self, qtbot, sahte_rag, sorgu):
        from ai.worker import RAGChatWorker
        worker = RAGChatWorker(sahte_rag, sorgu)
        toplayici = SinyalToplayici(worker)

        worker.run()

        assert toplayici.modes[0][0] == "RAG"

    def test_yukleme_mesaji_yayilir(self, qtbot, sahte_rag):
        from ai.worker import RAGChatWorker
        worker = RAGChatWorker(sahte_rag, "normal bir soru")
        toplayici = SinyalToplayici(worker)

        worker.run()

        assert toplayici.modes[0][1] == "Düşünüyor..."


class TestBaglamHafizasi:
    def test_onceki_tarih_araligi_takip_sorusunda_korunur(
        self, qtbot, sahte_rag, temp_db, monkeypatch
    ):
        """'Peki neden böyle hissetmişim?' sorusu önceki dönemi hatırlamalı."""
        from ai import worker as worker_module
        from ai.worker import RAGChatWorker

        monkeypatch.setattr(worker_module, "Database", lambda: temp_db)
        temp_db.save_entry("2026-07-15", "yorgun bir gün", happiness_score=3)

        worker = RAGChatWorker(
            sahte_rag, "peki neden böyle hissetmişim",
            last_date_range=("2026-07-01", "2026-07-31"),
        )
        toplayici = SinyalToplayici(worker)

        worker.run()

        assert toplayici.modes[0][0] == "SQL"
        assert toplayici.finished_with[0] == ("2026-07-01", "2026-07-31")

    def test_baglam_yoksa_rag_rotasi(self, qtbot, sahte_rag):
        from ai.worker import RAGChatWorker
        worker = RAGChatWorker(sahte_rag, "peki neden", last_date_range=None)
        toplayici = SinyalToplayici(worker)

        worker.run()

        assert toplayici.modes[0][0] == "RAG"

    def test_yeni_zaman_ifadesi_eski_baglami_ezer(self, qtbot, sahte_rag, temp_db, monkeypatch):
        from ai import worker as worker_module
        from ai.worker import RAGChatWorker

        monkeypatch.setattr(worker_module, "Database", lambda: temp_db)
        temp_db.save_entry("2026-08-01", "metin", happiness_score=5)

        worker = RAGChatWorker(
            sahte_rag, "bu ay nasıldım",
            last_date_range=("2020-01-01", "2020-12-31"),
        )
        toplayici = SinyalToplayici(worker)

        worker.run()

        assert toplayici.finished_with[0] != ("2020-01-01", "2020-12-31")


class TestHataYonetimi:
    def test_llm_hatasi_error_sinyaline_donusur(self, qtbot, sahte_rag, fake_llm):
        from ai.worker import RAGChatWorker

        def patlayan_stream(messages):
            raise RuntimeError("model yüklenemedi")
            yield  # pragma: no cover

        fake_llm.chat_stream = patlayan_stream

        worker = RAGChatWorker(sahte_rag, "bir soru")
        toplayici = SinyalToplayici(worker)

        worker.run()

        assert toplayici.errors == ["model yüklenemedi"]


class TestIndexWorker:
    def test_kayitlar_vektor_deposuna_yazilir(self, qtbot, fake_embedder, temp_vector_store):
        from ai.worker import IndexWorker

        worker = IndexWorker(fake_embedder, temp_vector_store, [
            {"date": "2026-08-01", "content": "birinci gün"},
            {"date": "2026-08-02", "content": "ikinci gün"},
        ])
        worker.run()

        assert temp_vector_store.get_indexed_dates() == {"2026-08-01", "2026-08-02"}

    def test_bos_liste_hata_vermez(self, qtbot, fake_embedder, temp_vector_store):
        from ai.worker import IndexWorker
        IndexWorker(fake_embedder, temp_vector_store, []).run()
        assert temp_vector_store.table.count_rows() == 0

    def test_bos_icerikli_kayit_atlanir(self, qtbot, fake_embedder, temp_vector_store):
        from ai.worker import IndexWorker
        IndexWorker(fake_embedder, temp_vector_store,
                    [{"date": "2026-08-01", "content": "   "}]).run()
        assert temp_vector_store.table.count_rows() == 0


class TestInsightWorker:
    """
    Yapısal çıkarım işçisi: kayıt başına bir çıkarım yapar, duygu puanını
    ve etiketleri veritabanına yazar.
    """

    @pytest.fixture
    def cikarici(self):
        from ai.insight_extractor import InsightExtractor
        from tests.conftest import FakeLLM

        return InsightExtractor(
            FakeLLM(json_responses=[{
                "mood": 6,
                "energy": 7,
                "summary": "Spor yapmış, raporu ertelemiş.",
                "activities": ["spor"],
                "postponed": ["rapor yazma"],
                "helped": ["yürüyüş"],
                "hindered": [],
                "emotions": ["huzur"],
            }]),
            extended=False,
        )

    def test_duygu_puani_veritabanina_yazilir(self, qtbot, cikarici, temp_db):
        from ai.worker import InsightWorker

        temp_db.save_entry("2026-08-01", "güzel bir gün", happiness_score=8)
        InsightWorker(cikarici, temp_db,
                      [{"date": "2026-08-01", "content": "güzel bir gün"}]).run()

        assert temp_db.get_entry("2026-08-01")["mood_score"] == 6

    def test_ozet_ve_etiketler_yazilir(self, qtbot, cikarici, temp_db):
        from ai.worker import InsightWorker

        temp_db.save_entry("2026-08-01", "metin", happiness_score=5)
        InsightWorker(cikarici, temp_db,
                      [{"date": "2026-08-01", "content": "metin"}]).run()

        insight = temp_db.get_insight("2026-08-01")
        assert insight["summary"] == "Spor yapmış, raporu ertelemiş."
        assert insight["energy"] == 7

        etiketler = {(f["kind"], f["label"]) for f in temp_db.get_facets("2026-08-01")}
        assert ("activity", "spor") in etiketler
        assert ("postponed", "rapor yazma") in etiketler

    def test_analiz_edilen_kayit_bir_daha_beklemez(self, qtbot, cikarici, temp_db):
        from ai.worker import InsightWorker

        temp_db.save_entry("2026-08-01", "metin", happiness_score=5)
        assert len(temp_db.get_entries_needing_insight()) == 1

        InsightWorker(cikarici, temp_db,
                      [{"date": "2026-08-01", "content": "metin"}]).run()

        assert temp_db.get_entries_needing_insight() == []

    def test_kayit_duzenlenince_yeniden_analiz_bekler(self, qtbot, cikarici, temp_db):
        from ai.worker import InsightWorker

        temp_db.save_entry("2026-08-01", "ilk metin", happiness_score=5)
        InsightWorker(cikarici, temp_db,
                      [{"date": "2026-08-01", "content": "ilk metin"}]).run()

        temp_db.save_entry("2026-08-01", "düzenlenmiş metin", happiness_score=5)

        assert [e["date"] for e in temp_db.get_entries_needing_insight()] == ["2026-08-01"]

    def test_ilerleme_sinyali_yayilir(self, qtbot, cikarici, temp_db):
        from ai.worker import InsightWorker

        kayitlar = []
        for gun in (1, 2, 3):
            temp_db.save_entry(f"2026-08-0{gun}", "metin", happiness_score=5)
            kayitlar.append({"date": f"2026-08-0{gun}", "content": "metin"})

        worker = InsightWorker(cikarici, temp_db, kayitlar)
        gelen = []
        worker.progress.connect(lambda d, t: gelen.append((d, t)))
        worker.run()

        assert gelen == [(1, 3), (2, 3), (3, 3)]

    def test_bos_icerik_analiz_edilmez(self, qtbot, cikarici, temp_db):
        from ai.worker import InsightWorker

        InsightWorker(cikarici, temp_db,
                      [{"date": "2026-08-01", "content": ""}]).run()

        assert temp_db.get_insight("2026-08-01") is None

    def test_iptal_edilen_is_durur(self, qtbot, cikarici, temp_db):
        from ai.worker import InsightWorker

        kayitlar = []
        for gun in (1, 2, 3):
            temp_db.save_entry(f"2026-08-0{gun}", "metin", happiness_score=5)
            kayitlar.append({"date": f"2026-08-0{gun}", "content": "metin"})

        worker = InsightWorker(cikarici, temp_db, kayitlar)
        worker.cancel()
        worker.run()

        assert temp_db.get_insight_coverage()["analyzed"] == 0

    def test_tek_kaydin_hatasi_kalan_kayitlari_durdurmaz(self, qtbot, temp_db):
        """
        Arka plan doldurma yüzlerce kaydı işler; ikinci kayıt patlarsa
        üçüncü ve sonrası yine de analiz edilmelidir.
        """
        from ai.insight_extractor import InsightExtractor
        from ai.worker import InsightWorker

        iyi_yanit = {
            "mood": 3, "energy": 5, "summary": "sıradan bir gün",
            "activities": ["spor"], "postponed": [], "helped": [],
            "hindered": [], "emotions": [],
        }

        class BazenPatlayanLLM:
            def __init__(self):
                self.cagri = 0

            def complete_json(self, messages, schema, max_tokens=512):
                self.cagri += 1
                if self.cagri == 2:
                    raise RuntimeError("ikinci kayıtta çöktü")
                return iyi_yanit

        kayitlar = []
        for gun in (1, 2, 3):
            temp_db.save_entry(f"2026-08-0{gun}", f"metin {gun}", happiness_score=5)
            kayitlar.append({"date": f"2026-08-0{gun}", "content": f"metin {gun}"})

        InsightWorker(
            InsightExtractor(BazenPatlayanLLM(), extended=False), temp_db, kayitlar
        ).run()

        # Üçüncü kayıt işlenmiş olmalı
        assert temp_db.get_insight("2026-08-03") is not None
        assert temp_db.get_insight_coverage()["analyzed"] == 3

    def test_cikarim_hatasi_isi_cokertmez(self, qtbot, temp_db):
        from ai.insight_extractor import InsightExtractor
        from ai.worker import InsightWorker

        class PatlayanLLM:
            def complete_json(self, messages, schema, max_tokens=512):
                raise RuntimeError("model çöktü")

        temp_db.save_entry("2026-08-01", "metin", happiness_score=5)
        worker = InsightWorker(
            InsightExtractor(PatlayanLLM(), extended=False), temp_db,
            [{"date": "2026-08-01", "content": "metin"}],
        )
        bitti = []
        worker.finished.connect(lambda: bitti.append(True))

        worker.run()   # istisna dışarı sızmamalı

        assert bitti == [True]


class TestOncelikliDoldurma:
    """
    Hibrit doldurma: soru sorulduğunda o dönemdeki eksik çıkarımlar cevap
    verilmeden önce tamamlanır. Analiz edilmemiş günler cevaba giremez.
    """

    @pytest.fixture
    def cikarici(self):
        from ai.insight_extractor import InsightExtractor
        from tests.conftest import FakeLLM

        return InsightExtractor(
            FakeLLM(json_responses=[{
                "mood": 4, "energy": 5, "summary": "özet",
                "activities": [], "postponed": ["spor"],
                "helped": [], "hindered": [], "emotions": [],
            }]),
            extended=False,
        )

    def test_eksik_kayitlar_cevaptan_once_analiz_edilir(
        self, qtbot, sahte_rag, temp_db, cikarici
    ):
        from ai.worker import RAGChatWorker

        for gun in (1, 2, 3):
            temp_db.save_entry(f"2026-08-0{gun}", f"metin {gun}", happiness_score=5)
        assert temp_db.get_insight_coverage()["analyzed"] == 0

        worker = RAGChatWorker(
            sahte_rag, "bu ay en çok neyi erteledim",
            insight_extractor=cikarici, db=temp_db,
        )
        worker.run()

        assert temp_db.get_insight_coverage()["analyzed"] == 3

    def test_analiz_sonrasi_sayilar_cevaba_girer(
        self, qtbot, sahte_rag, temp_db, cikarici, fake_llm
    ):
        from ai.worker import RAGChatWorker

        for gun in (1, 2, 3):
            temp_db.save_entry(f"2026-08-0{gun}", f"metin {gun}", happiness_score=5)

        RAGChatWorker(sahte_rag, "bu ay en çok neyi erteledim",
                      insight_extractor=cikarici, db=temp_db).run()

        sistem = fake_llm.received_messages[-1][0]["content"]
        assert "spor — 3 gün" in sistem

    def test_ilerleme_kullaniciya_bildirilir(
        self, qtbot, sahte_rag, temp_db, cikarici
    ):
        from ai.worker import RAGChatWorker

        for gun in (1, 2):
            temp_db.save_entry(f"2026-08-0{gun}", f"metin {gun}", happiness_score=5)

        worker = RAGChatWorker(sahte_rag, "bu ay en çok neyi erteledim",
                               insight_extractor=cikarici, db=temp_db)
        toplayici = SinyalToplayici(worker)
        worker.run()

        mesajlar = [m for _, m in toplayici.modes]
        assert "Eksik günlükler analiz ediliyor: 1/2" in mesajlar
        assert "Eksik günlükler analiz ediliyor: 2/2" in mesajlar

    def test_ust_sinir_asilmaz(self, qtbot, sahte_rag, temp_db, cikarici):
        """300 kayıtlık geçmiş için dakikalarca beklenmemeli."""
        from ai.worker import RAGChatWorker

        for gun in range(1, 26):
            temp_db.save_entry(f"2026-08-{gun:02d}", f"metin {gun}", happiness_score=5)

        RAGChatWorker(sahte_rag, "bu ay en çok neyi erteledim",
                      insight_extractor=cikarici, db=temp_db).run()

        analiz_edilen = temp_db.get_insight_coverage()["analyzed"]
        assert analiz_edilen == RAGChatWorker.MAX_INLINE_INSIGHTS

    def test_eksik_kapsama_cevapta_belirtilir(
        self, qtbot, sahte_rag, temp_db, cikarici, fake_llm
    ):
        from ai.worker import RAGChatWorker

        for gun in range(1, 26):
            temp_db.save_entry(f"2026-08-{gun:02d}", f"metin {gun}", happiness_score=5)

        RAGChatWorker(sahte_rag, "bu ay en çok neyi erteledim",
                      insight_extractor=cikarici, db=temp_db).run()

        assert "VERİ KAPSAMI" in fake_llm.received_messages[-1][0]["content"]

    def test_cikarici_yoksa_analiz_yine_de_calisir(
        self, qtbot, sahte_rag, temp_db
    ):
        from ai.worker import RAGChatWorker

        temp_db.save_entry("2026-08-01", "metin", happiness_score=5)
        temp_db.save_insight("2026-08-01", "metin", summary="özet",
                             facets={"postponed": ["spor"]})

        worker = RAGChatWorker(sahte_rag, "bu ay en çok neyi erteledim", db=temp_db)
        toplayici = SinyalToplayici(worker)
        worker.run()

        assert toplayici.modes[0][0] == "ANALYSIS"
        assert toplayici.errors == []

    def test_analiz_tamamsa_yeniden_yapilmaz(
        self, qtbot, sahte_rag, temp_db, cikarici
    ):
        from ai.worker import RAGChatWorker

        temp_db.save_entry("2026-08-01", "metin", happiness_score=5)
        temp_db.save_insight("2026-08-01", "metin", summary="özet",
                             facets={"postponed": ["spor"]})

        worker = RAGChatWorker(sahte_rag, "bu ay en çok neyi erteledim",
                               insight_extractor=cikarici, db=temp_db)
        toplayici = SinyalToplayici(worker)
        worker.run()

        assert not any("Eksik günlükler" in m for _, m in toplayici.modes)
