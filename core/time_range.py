"""
core/time_range.py
------------------
Akıllı Yönlendirici'nin (Smart Query Router) zaman çözümleyicisi.

Kullanıcının sorusunda bir zaman ifadesi ("geçen ay", "bu hafta", "Mart'ta")
varsa bunu bir tarih aralığına çevirir. RAGChatWorker bu sonuca bakarak
vektör araması yerine SQL tabanlı rapor motorunu seçer.

Daha önce bu mantık RAGChatWorker içinde bir metottu ve şu iki sorunu vardı:

1. Ay adları düz "içinde geçiyor mu" (substring) kontrolüyle aranıyordu.
   Bu yüzden "çekimser" -> Ekim, "smart" -> Mart, "kasımpatı" -> Kasım
   olarak algılanıyor; sıradan sorular yanlışlıkla aylık rapor moduna
   düşüyordu. Artık kelime sınırı ve Türkçe ek deseni kullanılıyor.

2. Sorulan ay içinde bulunulan aydan sonraysa (Ağustos'tayken "Aralık")
   henüz yaşanmamış bir tarih aralığı dönüyordu. Artık bir önceki yılın
   aynı ayı alınır — kullanıcının kastettiği en yakın geçmiş dönemdir.

Modül saf Python'dur; Qt, veritabanı veya model gerektirmez.
"""

import calendar
import re
from datetime import date, timedelta
from typing import Optional

from core.date_utils import TURKISH_MONTHS, month_name, to_iso

# Aralık: (başlangıç, bitiş) ISO tarih ikilisi; mesaj: arayüzde gösterilen metin
TimeRange = tuple[str, str]
ParseResult = tuple[Optional[TimeRange], Optional[str]]

# Ay adlarından sonra gelebilecek Türkçe çekim ekleri.
# "kasımpatı" gibi başka bir kelimenin eşleşmemesi için ek listesi kapalıdır.
_MONTH_SUFFIX = (
    r"(?:'?(?:t[ae]n|d[ae]n|t[ae]|d[ae]|[ıi]nd[ae]ki|[ıi]nd[ae]n|[ıi]nd[ae]|"
    r"[ıi]n|[ıiuü]|[ae]|l[ae]r[ıi])?)"
)


# Göreli zaman ifadelerinden sonra gelebilecek Türkçe çekim ekleri.
# "bu ayı özetle", "geçen haftayı", "dünkü günlüğüm" gibi kullanımlar
# yakalanmalı; "bu ayakkabı", "bu ayna" gibi kelimeler yakalanmamalı.
_RELATIVE_SUFFIX = (
    r"(?:'?(?:nd[ae]n|nd[ae]|n[ıi]n|y[ıiuü]|[ıiuü]n|d[ae]n|d[ae]|"
    r"t[ae]n|t[ae]|k[ıiuü]|[ıiuü]|[ae])?)"
)


def _word_pattern(word: str) -> re.Pattern:
    """
    İfadeyi harf sınırlarıyla ve Türkçe çekim ekleriyle birlikte arar.

    Ek desteği olmadan "bu ayı özetle" sorusunda "bu ay" ifadesi
    yakalanamıyor ve soru dönemsiz kabul ediliyordu.
    """
    return re.compile(
        rf"(?<!\w){re.escape(word)}{_RELATIVE_SUFFIX}(?!\w)",
        re.IGNORECASE | re.UNICODE,
    )


def _month_pattern(name: str) -> re.Pattern:
    """Ay adını Türkçe ekleriyle birlikte, kelime sınırlarına saygıyla arar."""
    return re.compile(
        rf"(?<!\w){re.escape(name.lower())}{_MONTH_SUFFIX}(?!\w)",
        re.IGNORECASE | re.UNICODE,
    )


_MONTH_PATTERNS = [(i + 1, _month_pattern(name)) for i, name in enumerate(TURKISH_MONTHS)]

# Göreli ifadeler — sıra önemlidir: "geçen ay", "bu ay"dan önce denenmelidir.
_RELATIVE_KEYS = (
    "geçen yıl", "geçen sene", "bu yıl", "bu sene",
    "geçen ay", "bu ay",
    "geçen hafta", "bu hafta",
    "dün", "bugün",
)
_RELATIVE_PATTERNS = [(key, _word_pattern(key)) for key in _RELATIVE_KEYS]


def _month_bounds(year: int, month: int) -> TimeRange:
    """Verilen ayın ilk ve son gününü ISO metin olarak döner."""
    last_day = calendar.monthrange(year, month)[1]
    return to_iso(date(year, month, 1)), to_iso(date(year, month, last_day))


def _clamp_end(end: str, today: date) -> str:
    """Bitiş tarihini bugünden ileriye taşımaz (gelecek gün okunamaz)."""
    return min(end, to_iso(today))


def parse_time_range(query: str, today: Optional[date] = None) -> ParseResult:
    """
    Sorgudaki zaman ifadesini (tarih_aralığı, yükleniyor_mesajı) olarak döner.
    Zaman ifadesi yoksa (None, None) döner.

    today parametresi testler içindir; verilmezse bugünün tarihi kullanılır.
    """
    if not query:
        return None, None

    today = today or date.today()
    q = query.casefold()

    matched = {key for key, pattern in _RELATIVE_PATTERNS if pattern.search(q)}

    # ── Yıl ────────────────────────────────────────────────────────────────
    if "geçen yıl" in matched or "geçen sene" in matched:
        year = today.year - 1
        return (to_iso(date(year, 1, 1)), to_iso(date(year, 12, 31))), \
               "Geçen yılın günlükleri taranıyor..."

    if "bu yıl" in matched or "bu sene" in matched:
        return (to_iso(date(today.year, 1, 1)), to_iso(today)), \
               "Bu yılki günlüklerin taranıyor..."

    # ── Ay ─────────────────────────────────────────────────────────────────
    if "geçen ay" in matched:
        first_of_month = today.replace(day=1)
        last_month = first_of_month - timedelta(days=1)
        start, end = _month_bounds(last_month.year, last_month.month)
        return (start, end), "Geçen ayki günlüklerin taranıyor..."

    if "bu ay" in matched:
        start, _ = _month_bounds(today.year, today.month)
        return (start, to_iso(today)), "Bu ayki günlüklerin taranıyor..."

    # ── Hafta ──────────────────────────────────────────────────────────────
    if "geçen hafta" in matched:
        this_monday = today - timedelta(days=today.weekday())
        start = this_monday - timedelta(days=7)
        end = this_monday - timedelta(days=1)
        return (to_iso(start), to_iso(end)), "Geçen haftaki günlüklerin taranıyor..."

    if "bu hafta" in matched:
        this_monday = today - timedelta(days=today.weekday())
        return (to_iso(this_monday), to_iso(today)), "Bu haftaki günlüklerin taranıyor..."

    # ── Gün ────────────────────────────────────────────────────────────────
    if "dün" in matched:
        yesterday = to_iso(today - timedelta(days=1))
        return (yesterday, yesterday), "Dünkü günlüğün okunuyor..."

    if "bugün" in matched:
        current = to_iso(today)
        return (current, current), "Bugünkü günlüğün okunuyor..."

    # ── Ay adı ("Mart'ta", "Ekimde", "Ocak ayında") ────────────────────────
    for month, pattern in _MONTH_PATTERNS:
        if not pattern.search(q):
            continue

        # Sorulan ay henüz gelmediyse bir önceki yılın aynı ayı kastediliyordur
        year = today.year if month <= today.month else today.year - 1
        start, end = _month_bounds(year, month)
        return (start, _clamp_end(end, today)), \
               f"{month_name(month)} ayı günlüklerin taranıyor..."

    return None, None
