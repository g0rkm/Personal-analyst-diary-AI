"""
core/analytics.py
-----------------
Günlük verisinden sayısal analiz üretir.

Buradaki her sonuç SQL sayımlarına ve saf Python hesabına dayanır; dil
modeli hiçbir aşamada sayı üretmez. Model yalnızca burada hesaplanan
sayıları akıcı Türkçeye çevirir (bkz. ai/analysis_engine.py).

Bu ayrımın nedeni: "Bu ay en çok neyi erteledim?" sorusu sıralama ister.
3B'lik bir modele bir aylık düz metin verip saydırmak hem bağlam
penceresine sığmaz hem de güvenilir değildir.

Modül Qt ve model bağımsızdır; yalnızca Database nesnesine ihtiyaç duyar.
"""

from datetime import timedelta
from typing import NamedTuple, Optional

from core.date_utils import parse_iso, to_iso

# "Stresli olduğumda ne iyi geliyor?" sorusunda stresli sayılacak duygular.
# Etiketler entry_facets'e normalize edilmiş (küçük harf) yazıldığı için
# burada da öyle tutulur.
STRESS_EMOTIONS = (
    "stres", "kaygı", "gerginlik", "endişe", "baskı",
    "sıkıntı", "huzursuzluk", "panik", "tedirginlik",
)

# Bu değerin altındaki duygu puanı da "zor gün" sayılır
STRESS_MOOD_THRESHOLD = -3


class FacetCount(NamedTuple):
    """Bir etiketin dönem içindeki gün sayısı."""

    label: str
    days: int


class ConsistencyItem(NamedTuple):
    """Bir etiketin ne kadar düzenli tekrarlandığı."""

    label: str
    days: int              # etiketin geçtiği gün sayısı
    total_days: int        # dönemdeki dolu günlük sayısı
    longest_streak: int    # en uzun kesintisiz gün serisi

    @property
    def coverage(self) -> float:
        """Dönemin yüzde kaçında yapılmış (0.0 - 1.0)."""
        return (self.days / self.total_days) if self.total_days else 0.0


class MoodTrend(NamedTuple):
    """Dönemin duygu durumu özeti."""

    average: Optional[float]         # puanlanmış günlerin ortalaması
    scored_days: int                 # duygu puanı hesaplanmış gün sayısı
    total_days: int                  # dönemdeki dolu günlük sayısı
    best_day: Optional[tuple]        # (tarih, puan)
    worst_day: Optional[tuple]       # (tarih, puan)
    weekly: list                     # [(hafta_no, ortalama, gün_sayısı), ...]
    previous_average: Optional[float]  # önceki eşit uzunluktaki dönem
    average_happiness: Optional[float]  # kullanıcının kendi verdiği puan

    @property
    def delta(self) -> Optional[float]:
        """Önceki döneme göre değişim; karşılaştırılamıyorsa None."""
        if self.average is None or self.previous_average is None:
            return None
        return self.average - self.previous_average

    @property
    def direction(self) -> str:
        """'yükseliş', 'düşüş' ya da 'sabit'."""
        fark = self.delta
        if fark is None:
            return "bilinmiyor"
        if fark >= 0.5:
            return "yükseliş"
        if fark <= -0.5:
            return "düşüş"
        return "sabit"


def longest_streak(dates: list[str]) -> int:
    """
    Sıralı ISO tarih listesindeki en uzun kesintisiz gün serisini döner.

    Ardışıklık takvim günü üzerinden hesaplanır: 01-02-03 üç günlük seridir,
    01-02-04 ise en fazla iki gündür.
    """
    parsed = sorted({d for d in (parse_iso(t) for t in dates) if d is not None})
    if not parsed:
        return 0

    en_uzun = mevcut = 1
    for onceki, simdiki in zip(parsed, parsed[1:]):
        if (simdiki - onceki).days == 1:
            mevcut += 1
            en_uzun = max(en_uzun, mevcut)
        else:
            mevcut = 1
    return en_uzun


def _previous_period(start_date: str, end_date: str) -> Optional[tuple]:
    """Verilen dönemin hemen öncesindeki eşit uzunluktaki dönemi döner."""
    bas, son = parse_iso(start_date), parse_iso(end_date)
    if bas is None or son is None or son < bas:
        return None
    uzunluk = (son - bas).days + 1
    return to_iso(bas - timedelta(days=uzunluk)), to_iso(bas - timedelta(days=1))


def _weekly_buckets(series: list[dict], start_date: str) -> list:
    """
    Günleri dönem başlangıcından itibaren 7 günlük kovalara böler ve
    her kovanın duygu ortalamasını döner.
    """
    bas = parse_iso(start_date)
    if bas is None:
        return []

    kovalar: dict = {}
    for row in series:
        gun = parse_iso(row["date"])
        if gun is None or row["mood_score"] == 0:
            continue
        hafta = (gun - bas).days // 7
        kovalar.setdefault(hafta, []).append(row["mood_score"])

    return [
        (hafta + 1, round(sum(puanlar) / len(puanlar), 1), len(puanlar))
        for hafta, puanlar in sorted(kovalar.items())
    ]


def mood_trend(db, start_date: str, end_date: str) -> MoodTrend:
    """Dönemin duygu durumunu istatistiksel olarak özetler."""
    series = db.get_mood_series(start_date, end_date)

    # mood_score 0 "henüz hesaplanmadı" demektir, gerçek bir nötr değer değil
    puanlanan = [r for r in series if r["mood_score"] != 0]
    puanlar = [r["mood_score"] for r in puanlanan]

    mutluluk = [r["happiness_score"] for r in series if r["happiness_score"]]

    onceki_ortalama = None
    onceki = _previous_period(start_date, end_date)
    if onceki:
        onceki_puanlar = [
            r["mood_score"] for r in db.get_mood_series(*onceki) if r["mood_score"] != 0
        ]
        if onceki_puanlar:
            onceki_ortalama = round(sum(onceki_puanlar) / len(onceki_puanlar), 1)

    return MoodTrend(
        average=round(sum(puanlar) / len(puanlar), 1) if puanlar else None,
        scored_days=len(puanlanan),
        total_days=len(series),
        best_day=max(((r["date"], r["mood_score"]) for r in puanlanan),
                     key=lambda x: x[1], default=None),
        worst_day=min(((r["date"], r["mood_score"]) for r in puanlanan),
                      key=lambda x: x[1], default=None),
        weekly=_weekly_buckets(series, start_date),
        previous_average=onceki_ortalama,
        average_happiness=round(sum(mutluluk) / len(mutluluk), 1) if mutluluk else None,
    )


def top_facets(db, kind: str, start_date: str = None, end_date: str = None,
               limit: int = 5) -> list:
    """
    Bir etiket türünün en sık geçenlerini sıralar.
    "Bu hafta en çok neyi erteledim?" sorusunun cevabı budur.
    """
    rows = db.count_facet_days(kind, start_date, end_date, limit=limit)
    return [FacetCount(label=r["label"], days=r["day_count"]) for r in rows]


def consistency(db, kind: str, start_date: str = None, end_date: str = None,
                limit: int = 5) -> list:
    """
    Bir etiket türünün ne kadar DÜZENLİ tekrarlandığını sıralar.

    "En sürekli yaptığım şey" sorusu sıklıktan farklıdır: 20 gün üst üste
    yapılan bir şey, dağınık 20 güne yayılandan daha süreklidir. Bu yüzden
    gün sayısının yanında en uzun kesintisiz seri de hesaplanır.
    """
    toplam_gun = (
        db.count_entries_in_range(start_date, end_date)
        if start_date and end_date else 0
    )

    sonuc = []
    for row in db.count_facet_days(kind, start_date, end_date, limit=limit):
        tarihler = db.get_facet_dates(kind, row["label"], start_date, end_date)
        sonuc.append(ConsistencyItem(
            label=row["label"],
            days=row["day_count"],
            total_days=toplam_gun,
            longest_streak=longest_streak(tarihler),
        ))

    # Önce en uzun seri, sonra gün sayısı: "süreklilik" sorusunun ölçütü budur
    sonuc.sort(key=lambda i: (i.longest_streak, i.days), reverse=True)
    return sonuc


def stressful_dates(db, start_date: str = None, end_date: str = None) -> list:
    """Duygu etiketi ya da duygu puanı 'zor gün' işaret eden günler."""
    return db.get_dates_with_emotion(
        labels=list(STRESS_EMOTIONS),
        mood_max=STRESS_MOOD_THRESHOLD,
        start_date=start_date,
        end_date=end_date,
    )


def correlation(db, target_kind: str, condition_dates: list,
                limit: int = 5) -> list:
    """
    Koşulu sağlayan günlerde hangi etiketlerin öne çıktığını sıralar.

    "Stresli olduğumda bana ne iyi geliyor?" sorusu:
      condition_dates = stressful_dates(db)
      target_kind     = "helped"
    """
    rows = db.count_facet_days_on_dates(target_kind, condition_dates, limit=limit)
    return [FacetCount(label=r["label"], days=r["day_count"]) for r in rows]
