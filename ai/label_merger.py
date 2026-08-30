"""
ai/label_merger.py
------------------
Anlamca aynı ama farklı yazılmış etiketleri tek bir kanonik etikette
birleştirir.

Neden gerekli: sayım sorguları etiketleri birebir eşleştirir. Kullanıcı
bir gün "yürüyüş", başka gün "yürüyüşe çıkmak", bir başka gün "yürüdüm"
yazdığında bunlar üç ayrı etiket olur ve "en çok yaptığım şey" sıralaması
3+2+2 diye bölünerek yanıltıcı hale gelir. Birleştirme sayesinde tek bir
"yürüyüş" satırı 7 gün olarak görünür.

Benzerlik ölçümü için uygulamada zaten kurulu olan embedding modeli
(ai/embedder.py) kullanılır; ek bir bağımlılık ya da indirme gerekmez.

Ham etiket (raw_label) her zaman saklandığı için eşik değiştirilirse
birleştirmeler yeniden üretilebilir; bilgi kaybı olmaz.
"""

import math
from typing import Optional

# Bu değerin üstündeki kosinüs benzerliği "aynı şey" sayılır.
# Deneysel olarak seçildi: 0.85 "yürüyüş"/"yürüyüşe çıkmak" ikilisini
# birleştirir, "yürüyüş"/"rapor yazma" ikilisini birleştirmez.
DEFAULT_THRESHOLD = 0.85


def cosine_similarity(a, b) -> float:
    """İki vektör arasındaki kosinüs benzerliği (-1.0 ile 1.0 arası)."""
    if not a or not b or len(a) != len(b):
        return 0.0

    nokta = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return nokta / (norm_a * norm_b)


class LabelMerger:
    """
    Yeni etiketleri mevcut kanonik etiketlerle eşleştirir.

    Aynı `kind` içinde karşılaştırma yapılır: "spor" bir aktivite ve bir
    ertelenen olarak ayrı ayrı var olabilir, bunlar karıştırılmamalıdır.
    """

    def __init__(self, embedder, db, threshold: float = DEFAULT_THRESHOLD):
        self.embedder = embedder
        self.db = db
        self.threshold = threshold
        # {kind: {label: vektör}} — aynı oturumda tekrar tekrar gömme yapılmaz
        self._vector_cache: dict = {}

    def _vectors_for(self, kind: str) -> dict:
        """Bir türdeki mevcut kanonik etiketlerin vektörlerini döner."""
        if kind not in self._vector_cache:
            mevcut = [r["label"] for r in self.db.count_facet_days(kind)]
            self._vector_cache[kind] = (
                dict(zip(mevcut, self.embedder.embed_documents(mevcut)))
                if mevcut else {}
            )
        return self._vector_cache[kind]

    def canonical_for(self, kind: str, label: str) -> str:
        """
        Etiketin kanonik karşılığını döner.

        Yeterince benzer bir etiket zaten varsa onun adı, yoksa etiketin
        kendisi döner (ve bundan sonra o da kanonik kabul edilir).
        """
        if not label:
            return label

        mevcut = self._vectors_for(kind)
        if label in mevcut:
            return label

        if mevcut:
            vektor = self.embedder.embed_query(label)
            en_iyi, en_iyi_skor = None, 0.0
            for aday, aday_vektor in mevcut.items():
                skor = cosine_similarity(vektor, aday_vektor)
                if skor > en_iyi_skor:
                    en_iyi, en_iyi_skor = aday, skor

            if en_iyi is not None and en_iyi_skor >= self.threshold:
                self.db.save_label_alias(kind, label, en_iyi)
                return en_iyi
        else:
            vektor = self.embedder.embed_query(label)

        # Yeni kanonik etiket: sonraki karşılaştırmalar için önbelleğe al
        mevcut[label] = vektor
        return label

    def merge_facets(self, facets: dict) -> dict:
        """
        Çıkarımdan gelen etiket sözlüğünü kanonik etiketlere çevirir.

        Girdi:  {"activity": ["yürüyüşe çıkmak"]}
        Çıktı:  {"activity": [("yürüyüş", "yürüyüşe çıkmak")]}
                          (kanonik, ham) — ham hâli veritabanında saklanır
        """
        sonuc: dict = {}
        for kind, labels in (facets or {}).items():
            eslenen = []
            gorulen = set()
            for label in labels:
                kanonik = self.canonical_for(kind, label)
                if kanonik in gorulen:
                    continue
                gorulen.add(kanonik)
                eslenen.append((kanonik, label))
            if eslenen:
                sonuc[kind] = eslenen
        return sonuc
