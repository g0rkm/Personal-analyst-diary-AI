"""
settings.py
-----------
settings.json dosyasını okur ve uygulama genelinde
yapılandırma değerlerini sunar.

Öncelik sırası:  ortam değişkeni  >  settings.json  >  varsayılan değer
Ortam değişkenleri sayesinde uygulama Docker içinde dosya düzenlemeden
farklı yollara (volume'lere) yönlendirilebilir.
"""

import json
import os

# settings.json dosyasının konumu her zaman uygulamanın kök dizinidir
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

# Varsayılan ayarlar (settings.json bulunamazsa kullanılır)
_DEFAULTS = {
    "db_path": "diary.db",
    "vector_db_path": "lance_db",
    "model_path": "models/qwen2.5-3b-instruct-q4_k_m.gguf",
    "model_url": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"
}

# Ayar anahtarı -> ortam değişkeni eşlemesi (Docker/CI için)
_ENV_OVERRIDES = {
    "db_path": "DIARY_DB_PATH",
    "vector_db_path": "DIARY_VECTOR_DB_PATH",
    "model_path": "DIARY_MODEL_PATH",
    "model_url": "DIARY_MODEL_URL",
}


def load_settings() -> dict:
    """settings.json dosyasını okur, ortam değişkenlerini uygular ve dict döner."""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}

    # Eksik anahtarları varsayılanlarla tamamla
    for key, value in _DEFAULTS.items():
        data.setdefault(key, value)

    # Ortam değişkenleri dosyadaki değerleri ezer (settings.json'a yazılmaz)
    for key, env_name in _ENV_OVERRIDES.items():
        env_value = os.environ.get(env_name)
        if env_value:
            data[key] = env_value

    return data


def save_settings(settings: dict) -> None:
    """Verilen dict'i settings.json dosyasına yazar."""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)


def _resolve_path(raw_path: str) -> str:
    """
    Göreli yolları uygulamanın kök dizinine göre çözümler,
    mutlak yolları (örn. OneDrive klasörü veya Docker volume'u) olduğu gibi bırakır.
    """
    if os.path.isabs(raw_path):
        return raw_path

    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, raw_path)


def get_db_path() -> str:
    """SQLite veritabanı dosyasının tam yolunu döner."""
    return _resolve_path(load_settings().get("db_path", _DEFAULTS["db_path"]))


def get_vector_db_path() -> str:
    """LanceDB vektör veritabanı klasörünün tam yolunu döner."""
    return _resolve_path(load_settings().get("vector_db_path", _DEFAULTS["vector_db_path"]))
