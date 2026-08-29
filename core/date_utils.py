"""
core/date_utils.py
------------------
Türkçe tarih biçimlendirme yardımcıları.

Ay ve gün adı listeleri daha önce editor_panel, full_calendar_view ve
worker içinde üç ayrı yerde kopyalanmıştı. Tek kaynak burasıdır.

Modül Qt'ye bağımlı değildir; tarihler her yerde "YYYY-MM-DD" biçimindeki
düz metinlerle (veritabanındaki birincil anahtar biçimi) taşınır.
"""

from datetime import date, datetime
from typing import Optional

ISO_FORMAT = "%Y-%m-%d"

# 1 = Ocak ... 12 = Aralık
TURKISH_MONTHS: tuple[str, ...] = (
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
)

# 1 = Pazartesi ... 7 = Pazar (ISO hafta günü numaralandırması)
TURKISH_DAYS: tuple[str, ...] = (
    "Pazartesi", "Salı", "Çarşamba", "Perşembe",
    "Cuma", "Cumartesi", "Pazar",
)


def upper_tr(text: str) -> str:
    """
    Metni Türkçe kurallarına uygun biçimde büyük harfe çevirir.

    Python'un str.upper() metodu yerelden bağımsızdır ve 'i' harfini 'I'
    yapar; Türkçede doğrusu noktalı 'İ'dir. Bu yüzden "Cumartesi" başlığı
    "CUMARTESI", "Nisan" ise "NISAN" olarak görünüyordu.
    """
    return text.replace("i", "İ").replace("ı", "I").upper()


def month_name(month: int) -> str:
    """1-12 arası ay numarasını Türkçe ay adına çevirir."""
    if not 1 <= month <= 12:
        raise ValueError(f"Ay numarası 1-12 arasında olmalı: {month}")
    return TURKISH_MONTHS[month - 1]


def day_name(iso_weekday: int) -> str:
    """1 (Pazartesi) - 7 (Pazar) arası gün numarasını Türkçe gün adına çevirir."""
    if not 1 <= iso_weekday <= 7:
        raise ValueError(f"Gün numarası 1-7 arasında olmalı: {iso_weekday}")
    return TURKISH_DAYS[iso_weekday - 1]


def parse_iso(date_str: str) -> Optional[date]:
    """'YYYY-MM-DD' metnini date nesnesine çevirir; geçersizse None döner."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, ISO_FORMAT).date()
    except (ValueError, TypeError):
        return None


def to_iso(value: date) -> str:
    """date nesnesini 'YYYY-MM-DD' metnine çevirir."""
    return value.strftime(ISO_FORMAT)


def format_long(date_str: str) -> str:
    """
    'Cumartesi, 29 Ağustos 2026' biçiminde uzun tarih döner.
    Tarih çözümlenemezse girdi olduğu gibi geri verilir.
    """
    parsed = parse_iso(date_str)
    if parsed is None:
        return date_str
    return f"{day_name(parsed.isoweekday())}, {parsed.day} {month_name(parsed.month)} {parsed.year}"


def format_short(date_str: str) -> str:
    """
    '29 Ağustos 2026' biçiminde kısa tarih döner.
    Tarih çözümlenemezse girdi olduğu gibi geri verilir.
    """
    parsed = parse_iso(date_str)
    if parsed is None:
        return date_str
    return f"{parsed.day} {month_name(parsed.month)} {parsed.year}"


def format_day_and_date(date_str: str) -> str:
    """
    'Cumartesi' ve '29 Ağustos 2026' satırlarını alt alta döner
    (tam ekran takvimdeki bilgi paneli için).
    """
    parsed = parse_iso(date_str)
    if parsed is None:
        return date_str
    return f"{day_name(parsed.isoweekday())}\n{format_short(date_str)}"
