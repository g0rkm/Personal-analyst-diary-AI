"""
settings.py
-----------
settings.json dosyasını okur ve uygulama genelinde
yapılandırma değerlerini sunar.
"""

import json
import os

# settings.json dosyasının konumu her zaman uygulamanın kök dizinidir
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

# Varsayılan ayarlar (settings.json bulunamazsa kullanılır)
_DEFAULTS = {
    "db_path": "diary.db",
    "model_path": "models/qwen2.5-3b-instruct-q4_k_m.gguf",
    "model_url": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"
}


def load_settings() -> dict:
    """settings.json dosyasını okur ve dict olarak döner."""
    if not os.path.exists(SETTINGS_FILE):
        # Dosya yoksa varsayılan değerlerle oluştur
        save_settings(_DEFAULTS)
        return dict(_DEFAULTS)

    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Eksik anahtarları varsayılanlarla tamamla
    for key, value in _DEFAULTS.items():
        data.setdefault(key, value)

    return data


def save_settings(settings: dict) -> None:
    """Verilen dict'i settings.json dosyasına yazar."""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)


def get_db_path() -> str:
    """
    Veritabanı yolunu döner.
    Göreli yollar uygulamanın kök dizinine göre çözümlenir,
    mutlak yollar (örn. OneDrive klasörü) olduğu gibi kullanılır.
    """
    settings = load_settings()
    raw_path = settings.get("db_path", "diary.db")

    if os.path.isabs(raw_path):
        return raw_path

    # Göreli yolu kök dizine göre çözümle
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, raw_path)
