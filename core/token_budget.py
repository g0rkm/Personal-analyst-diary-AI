"""
core/token_budget.py
--------------------
Prompt'a konulacak metnin token bütçesini yönetir.

Neden gerekli: dil modelinin bağlam penceresi sabittir (n_ctx = 4096). Bir
aylık günlük kaydı uç uca eklendiğinde bu pencere aşılır ve llama.cpp hata
fırlatır — kullanıcı "Bu ay ruh halim nasıldı?" diye sorduğunda cevap yerine
hata görür. Burası, prompt'a giren metni ölçerek sınırın altında tutar.

Modül saf Python'dur; Qt, veritabanı veya model gerektirmez. Gerçek token
sayacı (LlamaEngine.count_tokens) dışarıdan verilir; verilmezse temkinli bir
tahmin kullanılır.
"""

import math
from typing import Callable, NamedTuple, Optional, Sequence

# Token sayacı: metni alır, token sayısını döner
TokenCounter = Callable[[str], int]

# Model yüklü değilken kullanılan tahmin oranı (karakter / token).
#
# Kurulu çok dilli tokenizer ile ölçüm: 420 karakterlik Türkçe metin -> 95 token
# (~4.4 karakter/token). Qwen'in BPE sözlüğü Türkçe için daha kötü olduğundan
# ve tahminin YUKARI yönlü sapması güvenli olduğundan (fazla kırpar, taşırmaz)
# bilinçli olarak daha düşük bir oran seçildi.
_CHARS_PER_TOKEN_ESTIMATE = 3.0


class FitResult(NamedTuple):
    """fit_to_budget sonucunu taşır."""

    kept: list[str]      # bütçeye sığan parçalar (verilen sırayla)
    dropped: int         # bütçe dolduğu için atılan parça sayısı
    used_tokens: int     # kept parçalarının toplam token sayısı

    @property
    def truncated(self) -> bool:
        """Bütçe yüzünden parça atıldı mı?"""
        return self.dropped > 0


def estimate_tokens(text: str) -> int:
    """
    Gerçek tokenizer yokken temkinli bir token tahmini üretir.
    Fazla tahmin etmek güvenlidir: sonuç gereğinden çok kırpar ama taşırmaz.
    """
    if not text:
        return 0
    return max(1, math.ceil(len(text) / _CHARS_PER_TOKEN_ESTIMATE))


def count_tokens(text: str, counter: Optional[TokenCounter] = None) -> int:
    """
    Metnin token sayısını döner.

    counter verilmişse (örn. LlamaEngine.count_tokens) gerçek sayım yapılır;
    sayaç hata verirse tahmine düşülür — bütçe hesabı hiçbir zaman çökmemeli.
    """
    if not text:
        return 0
    if counter is None:
        return estimate_tokens(text)
    try:
        return counter(text)
    except Exception:
        return estimate_tokens(text)


def fit_to_budget(
    pieces: Sequence[str],
    budget: int,
    counter: Optional[TokenCounter] = None,
) -> FitResult:
    """
    Parçaları sırayla ekleyerek token bütçesini aşmayan en uzun ön eki döner.

    Parçalar önem sırasına göre verilmelidir; bütçe dolunca sondakiler atılır.
    Tek bir parça bile bütçeye sığmıyorsa hiçbiri alınmaz (kept boş döner) —
    yarım cümle göndermektense çağıranın durumu bilmesi yeğdir.
    """
    if budget <= 0:
        return FitResult(kept=[], dropped=len(pieces), used_tokens=0)

    kept: list[str] = []
    used = 0

    for index, piece in enumerate(pieces):
        cost = count_tokens(piece, counter)
        if used + cost > budget:
            return FitResult(kept=kept, dropped=len(pieces) - index, used_tokens=used)
        kept.append(piece)
        used += cost

    return FitResult(kept=kept, dropped=0, used_tokens=used)


def prompt_budget(
    context_window: int,
    reserved_for_response: int,
    reserved_for_system: int = 0,
) -> int:
    """
    Bağlam penceresinden yanıt ve sistem promptu payını düşerek
    veriye ayrılabilecek token sayısını döner. Negatif sonuç 0'a çekilir.
    """
    return max(0, context_window - reserved_for_response - reserved_for_system)
