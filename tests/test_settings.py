"""
tests/test_settings.py
----------------------
Ayar çözümleme sırası: ortam değişkeni > settings.json > varsayılan.
"""

import json
import os

import pytest

import settings as settings_module
from settings import get_db_path, get_vector_db_path, load_settings, save_settings


@pytest.fixture
def izole_ayarlar(tmp_path, monkeypatch):
    """settings.json'u geçici klasöre taşır ve tüm ortam değişkenlerini temizler."""
    monkeypatch.setattr(settings_module, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    for env in settings_module._ENV_OVERRIDES.values():
        monkeypatch.delenv(env, raising=False)
    return tmp_path


class TestVarsayilanlar:
    def test_dosya_yokken_varsayilanlar_doner(self, izole_ayarlar):
        ayarlar = load_settings()
        assert ayarlar["db_path"] == "diary.db"
        assert ayarlar["vector_db_path"] == "lance_db"
        assert ayarlar["model_path"].endswith(".gguf")
        assert ayarlar["model_url"].startswith("https://")

    def test_load_settings_dosya_olusturmaz(self, izole_ayarlar):
        # Konteynerde salt-okunur bir dizine yazmaya çalışmamalı
        load_settings()
        assert not os.path.exists(settings_module.SETTINGS_FILE)


class TestDosyadanOkuma:
    def test_dosyadaki_deger_varsayilani_ezer(self, izole_ayarlar):
        save_settings({"db_path": "/veri/gunluk.db"})
        assert load_settings()["db_path"] == "/veri/gunluk.db"

    def test_eksik_anahtarlar_varsayilanla_tamamlanir(self, izole_ayarlar):
        save_settings({"db_path": "ozel.db"})
        ayarlar = load_settings()
        assert ayarlar["db_path"] == "ozel.db"
        assert ayarlar["vector_db_path"] == "lance_db"

    def test_turkce_karakterler_korunur(self, izole_ayarlar):
        save_settings({"db_path": "günlüğüm.db"})
        with open(settings_module.SETTINGS_FILE, encoding="utf-8") as f:
            assert json.load(f)["db_path"] == "günlüğüm.db"


class TestOrtamDegiskenleri:
    def test_ortam_degiskeni_dosyayi_ezer(self, izole_ayarlar, monkeypatch):
        save_settings({"db_path": "dosyadan.db"})
        monkeypatch.setenv("DIARY_DB_PATH", "/app/data/diary.db")
        assert load_settings()["db_path"] == "/app/data/diary.db"

    def test_bos_ortam_degiskeni_yok_sayilir(self, izole_ayarlar, monkeypatch):
        monkeypatch.setenv("DIARY_DB_PATH", "")
        assert load_settings()["db_path"] == "diary.db"

    def test_ortam_degiskeni_dosyaya_yazilmaz(self, izole_ayarlar, monkeypatch):
        save_settings({"db_path": "dosyadan.db"})
        monkeypatch.setenv("DIARY_DB_PATH", "/app/data/diary.db")
        load_settings()
        with open(settings_module.SETTINGS_FILE, encoding="utf-8") as f:
            assert json.load(f)["db_path"] == "dosyadan.db"

    @pytest.mark.parametrize("anahtar,env", [
        ("db_path", "DIARY_DB_PATH"),
        ("vector_db_path", "DIARY_VECTOR_DB_PATH"),
        ("model_path", "DIARY_MODEL_PATH"),
        ("model_url", "DIARY_MODEL_URL"),
    ])
    def test_tum_anahtarlar_ortamdan_ezilebilir(self, izole_ayarlar, monkeypatch, anahtar, env):
        monkeypatch.setenv(env, "ORTAMDAN")
        assert load_settings()[anahtar] == "ORTAMDAN"


class TestYolCozumleme:
    def test_mutlak_yol_oldugu_gibi_kullanilir(self, izole_ayarlar, monkeypatch, tmp_path):
        mutlak = str(tmp_path / "mutlak.db")
        monkeypatch.setenv("DIARY_DB_PATH", mutlak)
        assert get_db_path() == mutlak

    def test_goreli_yol_proje_kokune_gore_cozulur(self, izole_ayarlar, monkeypatch):
        monkeypatch.setenv("DIARY_DB_PATH", "goreli.db")
        yol = get_db_path()
        assert os.path.isabs(yol)
        assert yol.endswith("goreli.db")

    def test_vektor_yolu_da_cozulur(self, izole_ayarlar, monkeypatch, tmp_path):
        mutlak = str(tmp_path / "lance")
        monkeypatch.setenv("DIARY_VECTOR_DB_PATH", mutlak)
        assert get_vector_db_path() == mutlak
