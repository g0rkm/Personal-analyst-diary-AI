"""
tests/test_rag_engine.py
------------------------
RAG akışı: soru -> vektör araması -> prompt kurulumu -> yanıt akışı.

Gerçek LLM (1.9 GB) ve gerçek gömücü (220 MB) yerine conftest'teki
sahteler kullanılır; testler ağa çıkmaz.
"""

import pytest

from ai.rag_engine import RAGEngine


@pytest.fixture
def motor(fake_embedder, fake_llm, temp_vector_store):
    return RAGEngine(
        embedder=fake_embedder,
        vector_store=temp_vector_store,
        llm_engine=fake_llm,
    )


class TestPromptKurulumu:
    def test_ilk_mesaj_sistem_mesajidir(self, motor):
        mesajlar = motor.build_messages("nasılım", [])
        assert mesajlar[0]["role"] == "system"

    def test_son_mesaj_kullanici_sorusudur(self, motor):
        mesajlar = motor.build_messages("bugün nasılım", [])
        assert mesajlar[-1] == {"role": "user", "content": "bugün nasılım"}

    def test_bulunan_parcalar_sistem_mesajina_girer(self, motor):
        parcalar = [{"date": "2026-08-01", "text": "sabah koşuya çıktım"}]
        sistem = motor.build_messages("spor", parcalar)[0]["content"]
        assert "sabah koşuya çıktım" in sistem
        assert "2026-08-01" in sistem

    def test_parca_yoksa_bilgi_notu_yazilir(self, motor):
        sistem = motor.build_messages("spor", [])[0]["content"]
        assert "Eşleşen günlük kaydı bulunamadı" in sistem

    def test_birden_fazla_parca_hepsi_eklenir(self, motor):
        parcalar = [
            {"date": "2026-08-01", "text": "birinci anı"},
            {"date": "2026-08-02", "text": "ikinci anı"},
        ]
        sistem = motor.build_messages("soru", parcalar)[0]["content"]
        assert "birinci anı" in sistem and "ikinci anı" in sistem


class TestSohbetGecmisi:
    def test_gecmis_sistem_ile_soru_arasina_girer(self, motor):
        gecmis = [
            {"role": "user", "content": "geçen ay nasıldım"},
            {"role": "assistant", "content": "yorgun görünüyorsun"},
        ]
        mesajlar = motor.build_messages("peki neden", [], gecmis)

        assert mesajlar[0]["role"] == "system"
        assert mesajlar[1:3] == gecmis
        assert mesajlar[-1]["content"] == "peki neden"

    def test_gecmis_yoksa_yalnizca_sistem_ve_soru(self, motor):
        assert len(motor.build_messages("soru", [])) == 2

    def test_gecmis_son_on_mesajla_sinirlanir(self, motor):
        """Bağlam penceresinin taşmaması için geçmiş kırpılır."""
        gecmis = [{"role": "user", "content": f"mesaj {i}"} for i in range(30)]
        mesajlar = motor.build_messages("son soru", [], gecmis)

        # 1 sistem + 10 geçmiş + 1 güncel soru
        assert len(mesajlar) == 12
        assert mesajlar[1]["content"] == "mesaj 20"

    def test_tam_on_mesajli_gecmis_kirpilmaz(self, motor):
        gecmis = [{"role": "user", "content": f"m{i}"} for i in range(10)]
        assert len(motor.build_messages("soru", [], gecmis)) == 12


class TestYanitAkisi:
    def test_tokenlar_sirayla_uretilir(self, motor, fake_llm):
        fake_llm.chunks = ["Bu", " bir", " yanıt"]
        assert list(motor.chat_stream("nasılım")) == ["Bu", " bir", " yanıt"]

    def test_llm_e_dogru_mesajlar_gonderilir(self, motor, fake_llm):
        list(motor.chat_stream("spor yaptım mı"))

        gonderilen = fake_llm.received_messages[0]
        assert gonderilen[0]["role"] == "system"
        assert gonderilen[-1]["content"] == "spor yaptım mı"

    def test_depodaki_kayit_baglama_girer(self, motor, fake_embedder, temp_vector_store, fake_llm):
        from ai.chunker import chunk_entry
        parcalar = chunk_entry("2026-08-01", "sabah spor salonuna gittim")
        temp_vector_store.add_chunks(
            parcalar, fake_embedder.embed_documents([p["text"] for p in parcalar])
        )

        list(motor.chat_stream("sabah spor salonuna gittim"))

        sistem = fake_llm.received_messages[0][0]["content"]
        assert "spor salonuna gittim" in sistem

    def test_bos_depoda_da_yanit_uretilir(self, motor, fake_llm):
        fake_llm.chunks = ["Kayıt", " yok"]
        assert "".join(motor.chat_stream("soru")) == "Kayıt yok"

    def test_gecmis_llm_e_iletilir(self, motor, fake_llm):
        gecmis = [{"role": "user", "content": "önceki soru"},
                  {"role": "assistant", "content": "önceki yanıt"}]
        list(motor.chat_stream("takip sorusu", gecmis))

        icerikler = [m["content"] for m in fake_llm.received_messages[0]]
        assert "önceki soru" in icerikler
        assert "önceki yanıt" in icerikler


class TestBagimlilikEnjeksiyonu:
    def test_verilen_bilesenler_kullanilir(self, fake_embedder, fake_llm, temp_vector_store):
        motor = RAGEngine(fake_embedder, temp_vector_store, fake_llm)
        assert motor.embedder is fake_embedder
        assert motor.vector_store is temp_vector_store
        assert motor.llm is fake_llm
