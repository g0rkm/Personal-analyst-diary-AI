"""
ai/vector_store.py
------------------
LanceDB kullanarak günlük parçalarının vektörlerini saklar ve arar.
LanceDB, yerel dosya sisteminde SQLite gibi çalışır, sunucu gerektirmez.
"""

import os
import lancedb
import pyarrow as pa

from settings import get_vector_db_path

# Embedding modelinin (paraphrase-multilingual-MiniLM-L12-v2) vektör boyutu.
# Model değiştirilirse burası da güncellenmelidir; aksi halde LanceDB şeması
# ile üretilen vektörler uyuşmaz ve ekleme sırasında hata alınır.
VECTOR_DIM = 384


class DiaryVectorStore:
    def __init__(self, db_path: str = None):
        # Yol verilmezse ayarlardan (veya DIARY_VECTOR_DB_PATH ortam değişkeninden) çözümlenir
        if db_path is None:
            db_path = get_vector_db_path()

        # Veritabanı klasörü yoksa LanceDB otomatik oluşturur
        os.makedirs(db_path, exist_ok=True)
        self.db = lancedb.connect(db_path)
        self.table_name = "diary_chunks"
        
        # Tablo yoksa oluştur
        if self.table_name not in self._existing_table_names():
            # LanceDB için PyArrow şeması tanımlıyoruz
            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), VECTOR_DIM)),
                pa.field("text", pa.string()),
                pa.field("date", pa.string()),
                pa.field("chunk_index", pa.int32())
            ])
            self.table = self.db.create_table(self.table_name, schema=schema)
        else:
            self.table = self.db.open_table(self.table_name)

    def _existing_table_names(self) -> list[str]:
        """
        Veritabanındaki tablo adlarını döner.

        LanceDB sürümleri arasında API değişti: eski sürümler table_names()
        ile düz bir liste dönerken (artık DeprecationWarning üretiyor), yeni
        sürümler list_tables() ile .tables alanı olan bir yanıt nesnesi döner.
        Bu uygulamada tek bir tablo bulunduğu için sayfalama gerekmez.
        """
        lister = getattr(self.db, "list_tables", None)
        if lister is None:
            return list(self.db.table_names())

        response = lister()
        return list(getattr(response, "tables", response))

    def add_chunks(self, chunks: list[dict], embeddings: list[list[float]]) -> None:
        """
        Metin parçalarını ve vektörlerini LanceDB'ye kaydeder.
        Aynı tarihe ait eski kayıtlar varsa önce temizler (UPSERT mantığı).
        """
        if not chunks:
            return
            
        # Varsa eski kayıtları tarihe göre temizle
        date_set = set([chunk["metadata"]["date"] for chunk in chunks])
        for d in date_set:
            self.delete_by_date(d)
            
        data = []
        for chunk, emb in zip(chunks, embeddings):
            data.append({
                "id": chunk["id"],
                "vector": emb,
                "text": chunk["text"],
                "date": chunk["metadata"]["date"],
                "chunk_index": chunk["metadata"]["chunk_index"]
            })
            
        # Verileri tabloya ekle
        self.table.add(data)

    def delete_by_date(self, date: str) -> None:
        """Belirli bir tarihe ait tüm parçaları siler."""
        if self.table.count_rows() > 0:
            try:
                self.table.delete(f"date = '{date}'")
            except Exception:
                pass # Silinecek bir şey yoksa veya tablo boşsa hata vermesin

    def get_indexed_dates(self) -> set[str]:
        """
        İndekslenmiş kayıtların tarihlerini döner.

        main_window eskiden bunun için table.search().limit(10000) çağırıp
        tüm satırları (384 boyutlu vektörleriyle birlikte) belleğe alıyordu;
        hem israftı hem de 10.000 parçadan sonra sessizce kırpılıyordu.
        Burada yalnızca "date" sütunu okunur, sınır yoktur.
        """
        if self.table.count_rows() == 0:
            return set()

        # Yalnızca "date" sütununu oku; 384 boyutlu vektörler belleğe alınmasın
        rows = self.table.search().select(["date"]).limit(None).to_list()
        return {row["date"] for row in rows}

    def search(self, query_vector: list[float], limit: int = 5) -> list[dict]:
        """Verilen sorgu vektörüne en yakın (semantik olarak benzer) parçaları bulur."""
        if self.table.count_rows() == 0:
            return []
            
        # Vektör araması yap ve listeye çevir
        results = self.table.search(query_vector).limit(limit).to_list()
        
        formatted_results = []
        for r in results:
            formatted_results.append({
                "id": r["id"],
                "text": r["text"],
                "date": r["date"],
                "distance": r.get("_distance", 0.0) # Mesafe (düşük olan daha benzerdir)
            })
            
        return formatted_results
