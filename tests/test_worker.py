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

    def test_zaman_ifadeli_soru_sql_rotasina_gider(self, qtbot, sahte_rag, temp_db, monkeypatch):
        from ai import worker as worker_module
        from ai.worker import RAGChatWorker

        monkeypatch.setattr(worker_module, "Database", lambda: temp_db)
        temp_db.save_entry("2026-08-01", "koşuya çıktım", happiness_score=8)

        worker = RAGChatWorker(sahte_rag, "bu ay ruh halim nasıldı")
        toplayici = SinyalToplayici(worker)

        worker.run()

        assert toplayici.modes[0][0] == "SQL"
        assert toplayici.finished_with[0] is not None

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


class TestMoodAnalysisWorker:
    def test_hesaplanan_puan_veritabanina_yazilir(self, qtbot, fake_llm, temp_db):
        from ai.worker import MoodAnalysisWorker

        fake_llm.mood = 6
        temp_db.save_entry("2026-08-01", "güzel bir gün", happiness_score=8)

        MoodAnalysisWorker(fake_llm, temp_db,
                           [{"date": "2026-08-01", "content": "güzel bir gün"}]).run()

        assert temp_db.get_entry("2026-08-01")["mood_score"] == 6

    def test_icerik_alani_kullanicinin_metnidir(self, qtbot, fake_llm, temp_db):
        from ai.worker import MoodAnalysisWorker

        gelen = []
        fake_llm.analyze_mood = lambda metin: (gelen.append(metin), 5)[1]
        temp_db.save_entry("2026-08-01", "analiz edilecek metin", happiness_score=5)

        MoodAnalysisWorker(fake_llm, temp_db,
                           [{"date": "2026-08-01", "content": "analiz edilecek metin"}]).run()

        assert gelen == ["analiz edilecek metin"]

    def test_bos_icerik_analiz_edilmez(self, qtbot, fake_llm, temp_db):
        from ai.worker import MoodAnalysisWorker

        cagrildi = []
        fake_llm.analyze_mood = lambda metin: (cagrildi.append(metin), 5)[1]

        MoodAnalysisWorker(fake_llm, temp_db, [{"date": "2026-08-01", "content": ""}]).run()

        assert cagrildi == []
