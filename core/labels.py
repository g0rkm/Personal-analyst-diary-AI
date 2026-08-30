"""
core/labels.py
--------------
Yapay zekânın günlüklerden çıkardığı etiketleri ("spor", "rapor yazma",
"yürüyüş") sayılabilir hâle getirir.

Sayım yapan sorgular etiketleri birebir eşleştirir; bu yüzden "Spor" ile
"spor " aynı şey sayılmazsa "en çok ertelediğim şey" sıralaması bölünerek
yanıltıcı olur. Buradaki normalleştirme bu bölünmenin en kaba biçimini
(büyük/küçük harf, boşluk, noktalama) engeller. Anlamca aynı ama farklı
yazılmış etiketlerin birleştirilmesi ayrı bir katmanın işidir
(ai/label_merger.py).

Modül saf Python'dur; Qt, veritabanı veya model gerektirmez.
"""

import re
import unicodedata

# Etiket uzunluk sınırı — çıkarım bazen cümle döndürebiliyor
MAX_LABEL_LENGTH = 40

# Etiketin başında/sonunda anlam taşımayan karakterler
_TRIM_CHARS = " \t\n\r.,;:!?\"'`()[]{}<>-–—*_/\\"

_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)


def lower_tr(text: str) -> str:
    """
    Metni Türkçe kurallarına uygun biçimde küçük harfe çevirir.

    Python'un str.lower() metodu yerelden bağımsızdır: 'I' harfini 'i'
    yapar (Türkçede doğrusu noktasız 'ı'dır) ve 'İ' harfini birleşik
    noktalı bir diziye çevirir. core.date_utils.upper_tr'nin eşidir.
    """
    return text.replace("I", "ı").replace("İ", "i").lower()


def normalize(label: str) -> str:
    """
    Etiketi sayım için kanonik biçime getirir.

    Boş ya da yalnızca noktalama içeren etiketler için boş metin döner;
    çağıran bunları atmalıdır.
    """
    if not label:
        return ""

    # Unicode birleşim farklarını tekle (é ile e+́ aynı olsun)
    normalized = unicodedata.normalize("NFC", label)
    normalized = _WHITESPACE_RE.sub(" ", normalized)
    normalized = normalized.strip(_TRIM_CHARS)
    normalized = lower_tr(normalized)

    if len(normalized) > MAX_LABEL_LENGTH:
        # Sınırı aşan etiketi kelime sınırında kes
        normalized = normalized[:MAX_LABEL_LENGTH].rsplit(" ", 1)[0]

    return normalized.strip(_TRIM_CHARS)


def clean_labels(labels, limit: int = None) -> list[str]:
    """
    Etiket listesini normalleştirir; boşları atar, tekrarları sırayı
    bozmadan teker. limit verilirse ilk N tanesi alınır.
    """
    # Metin de yinelenebilir bir nesnedir: modelin liste yerine düz metin
    # döndürdüğü durumda harfler tek tek etiket sanılıyordu ("spor" -> s,p,o,r).
    if labels is None or isinstance(labels, (str, bytes)):
        return []

    try:
        iter(labels)
    except TypeError:
        return []

    seen: set[str] = set()
    result: list[str] = []

    for label in labels:
        if not isinstance(label, str):
            continue
        canonical = normalize(label)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        result.append(canonical)
        if limit is not None and len(result) >= limit:
            break

    return result
