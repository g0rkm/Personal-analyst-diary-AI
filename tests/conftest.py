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

    def __init__(self, chunks=None, mood=5):
        self.chunks = chunks if chunks is not None else ["Merhaba", " dünya"]
        self.mood = mood
        self.received_messages = []

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
