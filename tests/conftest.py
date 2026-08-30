"""
tests/conftest.py
-----------------
Testler için ortak hazırlıklar.

Önemli: Testler kullanıcının gerçek günlüğüne ASLA dokunmaz. Her test
kendi geçici klasöründe yeni bir SQLite/LanceDB oluşturur; bu, ortam
değişkenleri (DIARY_DB_PATH, DIARY_VECTOR_DB_PATH) üzerinden sağlanır.
"""

import os
import sys
from datetime import date

import pytest

# Proje kökünü import yoluna ekle (uygulama main.py'de de aynısını yapıyor)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Boş, geçici bir veritabanı ile Database örneği döner."""
    db_file = tmp_path / "test_diary.db"
    monkeypatch.setenv("DIARY_DB_PATH", str(db_file))

    from database import Database
    return Database()


@pytest.fixture
def temp_vector_store(tmp_path, monkeypatch):
    """Boş, geçici bir LanceDB ile DiaryVectorStore örneği döner."""
    monkeypatch.setenv("DIARY_VECTOR_DB_PATH", str(tmp_path / "lance_db"))

    from ai.vector_store import DiaryVectorStore
    return DiaryVectorStore()


@pytest.fixture
def today():
    """
    Testlerin bugüne göre değişmemesi için sabit bir referans tarih.
    29 Ağustos 2026, Cumartesi.
    """
    return date(2026, 8, 29)


class FakeLLM:
    """
    LlamaEngine yerine geçen sahte motor.

    Gerçek model 1.9 GB'lık bir dosyadır ve testlerde kullanılamaz;
    bu sınıf sadece kendisine verilen mesajları kaydeder ve sabit
    parçalar üretir.
    """

    def __init__(self, chunks=None, mood=5, chars_per_token=4, json_responses=None):
        self.chunks = chunks if chunks is not None else ["Merhaba", " dünya"]
        self.mood = mood
        self.chars_per_token = chars_per_token
        # complete_json çağrılarında sırayla döndürülecek sahte yanıtlar.
        # Liste tükenirse son yanıt tekrar edilir; hiç verilmezse boş dict.
        self.json_responses = list(json_responses or [])
        self.received_messages = []
        self.received_schemas = []

    def complete_json(self, messages, schema, max_tokens=512):
        """Şema zorlamalı çıkarımın sahtesi: sıradaki hazır yanıtı döner."""
        self.received_messages.append(messages)
        self.received_schemas.append(schema)
        if not self.json_responses:
            return {}
        if len(self.json_responses) == 1:
            return self.json_responses[0]
        return self.json_responses.pop(0)

    def count_tokens(self, text):
        """Deterministik sahte token sayacı (gerçek model gerekmez)."""
        if not text:
            return 0
        return max(1, -(-len(text) // self.chars_per_token))

    def chat_stream(self, messages):
        self.received_messages.append(messages)
        for chunk in self.chunks:
            yield chunk

    def analyze_mood(self, text):
        return self.mood


class FakeEmbedder:
    """
    DiaryEmbedder yerine geçen sahte gömücü.
    Metinden deterministik ama farklılaşan vektörler üretir; böylece
    testler ~220 MB'lık ONNX modelini indirmek zorunda kalmaz.
    """

    DIM = 384

    def _vector(self, text: str):
        vec = [0.0] * self.DIM
        for i, ch in enumerate(text[: self.DIM]):
            vec[i] = (ord(ch) % 17) / 17.0
        return vec

    def embed_documents(self, documents):
        return [self._vector(d) for d in documents]

    def embed_query(self, query):
        return self._vector(query)


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def fake_embedder():
    return FakeEmbedder()
