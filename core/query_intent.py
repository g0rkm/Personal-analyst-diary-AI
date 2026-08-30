"""
core/query_intent.py
--------------------
Kullanıcının sorusunun NE TÜR bir analiz istediğini belirler.

core/time_range.py sorudaki zaman aralığını çözer; bu modül ise ne
hesaplanacağını çözer. İkisi birlikte Akıllı Yönlendirici'yi oluşturur:

    "Bu hafta en çok neyi erteledim"
      time_range  -> (2026-08-24, 2026-08-29)
      query_intent-> [RANKING(postponed)]

Bir soru birden fazla analiz isteyebilir; bu yüzden liste döner:

    "Mart'ta en çok ertelediğim ve en sürekli yaptığım şey neydi"
      -> [RANKING(postponed), CONSISTENCY(activity)]

core/time_range.py ile aynı disiplin: kelime sınırlı regex, Türkçe eklere
duyarlı, saf ve test edilebilir. Küçük bir modelin sınıflandırmasına
güvenmek yerine kurallı eşleme tercih edildi — hem daha isabetli hem de
davranışı testlerle sabitlenebilir.
"""

import re
from typing import NamedTuple, Optional

# ── Analiz türleri ───────────────────────────────────────────────────────
RANKING = "RANKING"          # "en çok neyi erteledim"
CONSISTENCY = "CONSISTENCY"  # "en sürekli yaptığım şey"
CORRELATION = "CORRELATION"  # "stresli olduğumda ne iyi geliyor"
MOOD = "MOOD"                # "genel ruh halim nasıldı"
SUMMARY = "SUMMARY"          # "bu ayı özetle"


class Intent(NamedTuple):
    """Sorudan çıkarılan tek bir analiz isteği."""

    kind: str                      # RANKING / CONSISTENCY / ...
    facet: Optional[str] = None    # activity / postponed / helped / ...
    ascending: bool = False        # "en az" gibi ters sıralama isteniyor mu


def _pattern(*alternatives: str) -> re.Pattern:
    """Kelime sınırlarına saygılı, Türkçe ek toleranslı desen kurar."""
    birlesik = "|".join(alternatives)
    return re.compile(rf"(?<!\w)(?:{birlesik})", re.IGNORECASE | re.UNICODE)


# ── Etiket türü belirteçleri ─────────────────────────────────────────────
#
# Fiil kökleri Türkçe eklerle çok değiştiği için kök + serbest ek deseni
# kullanılır. Kökler başka kelimelerin içinde geçmeyecek şekilde seçildi:
# "ertel" yalnızca ertelemek ailesinde, "yapt" ise "yaprak"ta bulunmaz.
_FACET_PATTERNS = (
    ("postponed", _pattern(r"ertel\w*", r"sarkıt\w*", r"sonraya b\w*")),
    ("helped", _pattern(r"iyi gel\w*", r"rahatlat\w*", r"işe yara\w*",
                        r"iyi hissettir\w*", r"faydas\w*")),
    ("hindered", _pattern(r"zorla\w*", r"yor\w*du", r"kötü etkile\w*",
                          r"zorlan\w*", r"bunalt\w*")),
    ("person", _pattern(r"kimler\w*", r"kiminle", r"kişiler\w*")),
    ("place", _pattern(r"nerede\w*", r"nereler\w*", r"mekan\w*", r"mekân\w*")),
    ("emotion", _pattern(r"hissett\w*", r"duygular\w*")),
    # activity en sona: diğerleri eşleşmediyse "yaptığım şey" sorulmuştur
    ("activity", _pattern(r"yapt\w*", r"yapıyor\w*", r"yapmış\w*",
                          r"uğraş\w*", r"aktivite\w*")),
)

# ── Analiz türü belirteçleri ─────────────────────────────────────────────
_CORRELATION_RE = _pattern(
    r"olduğum\w*", r"olunca", r"olduğu zaman", r"hissettiğim\w* zaman",
    r"ne iyi gel\w*", r"neler iyi gel\w*", r"ne işe yara\w*",
)
_CONSISTENCY_RE = _pattern(
    r"sürekli", r"düzenli", r"istikrarl\w*", r"alışkanl\w*",
    r"her gün", r"aksatma\w*", r"kesintisiz",
)
_RANKING_RE = _pattern(r"en çok", r"en sık", r"en fazla", r"en az")
_RANKING_ASC_RE = _pattern(r"en az")
_MOOD_RE = _pattern(
    r"ruh hal\w*", r"moral\w*", r"nasıldı\w*", r"nasıldım", r"nasıl geçt\w*",
    r"duygu durum\w*", r"psikoloj\w*", r"modum", r"keyf\w*",
)
_SUMMARY_RE = _pattern(r"özetle\w*", r"özet\w*", r"genel olarak", r"genel bir")

# Soruyu birden fazla isteğe bölen bağlaçlar
_CLAUSE_SPLIT_RE = re.compile(
    r"(?<!\w)(?:ve|ayrıca|bir de|hem de)(?!\w)|[,;]", re.IGNORECASE | re.UNICODE
)

# Analiz türü belirtilmediğinde kullanılan varsayılan etiketler
_DEFAULT_FACETS = {
    RANKING: "activity",
    CONSISTENCY: "activity",
    CORRELATION: "helped",
}


def _detect_facet(clause: str) -> Optional[str]:
    """Cümlecikte hangi etiket türünün sorulduğunu belirler."""
    for facet, pattern in _FACET_PATTERNS:
        if pattern.search(clause):
            return facet
    return None


def _detect_kind(clause: str) -> Optional[str]:
    """
    Cümlecikteki analiz türünü belirler.

    Öncelik sırası daha özgül olandan genele doğrudur: "en sürekli yaptığım"
    hem RANKING hem CONSISTENCY belirteci taşır, doğru olan CONSISTENCY'dir.
    """
    if _CORRELATION_RE.search(clause):
        return CORRELATION
    if _CONSISTENCY_RE.search(clause):
        return CONSISTENCY
    if _RANKING_RE.search(clause):
        return RANKING
    if _MOOD_RE.search(clause):
        return MOOD
    if _SUMMARY_RE.search(clause):
        return SUMMARY
    return None


def parse_intents(query: str) -> list:
    """
    Sorudan analiz isteklerini çıkarır.

    Analiz gerektirmeyen sorular için boş liste döner; çağıran bu durumda
    mevcut RAG (belirli anı arama) yoluna düşmelidir.
    """
    if not query or not query.strip():
        return []

    intents: list = []
    seen: set = set()

    for clause in _CLAUSE_SPLIT_RE.split(query):
        if not clause or not clause.strip():
            continue

        kind = _detect_kind(clause)
        if kind is None:
            continue

        facet = _detect_facet(clause)

        # MOOD ve SUMMARY dönemin geneliyle ilgilidir; cümlecikte belirli bir
        # etiket türü de soruluyorsa ("kimlerle görüşünce moralim düzeliyor")
        # soru bu iki kalıbın hiçbirine tam oturmuyor demektir. Yanlış bir
        # analiz sunmaktansa RAG'a düşülür.
        if kind in (MOOD, SUMMARY):
            if facet is not None:
                continue
        else:
            facet = facet or _DEFAULT_FACETS[kind]

        intent = Intent(
            kind=kind,
            facet=facet,
            ascending=(kind == RANKING and bool(_RANKING_ASC_RE.search(clause))),
        )
        key = (intent.kind, intent.facet)
        if key not in seen:
            seen.add(key)
            intents.append(intent)

    return intents


def is_analytical(query: str) -> bool:
    """Soru toplu analiz mi istiyor (True) yoksa belirli bir anı mı (False)?"""
    return bool(parse_intents(query))
