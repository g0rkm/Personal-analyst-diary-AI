"""
ai/vector_store.py
------------------
LanceDB kullanarak günlük parçalarının vektörlerini saklar ve arar.
LanceDB, yerel dosya sisteminde SQLite gibi çalışır, sunucu gerektirmez.
"""

import os
import lancedb
import pyarrow as pa

class DiaryVectorStore:
    def __init__(self, db_path="lance_db"):
        # Veritabanı klasörü yoksa LanceDB otomatik oluşturur
        self.db = lancedb.connect(db_path)
        self.table_name = "diary_chunks"
        
        # Tablo yoksa oluştur
        if self.table_name not in self.db.table_names():
            # LanceDB için PyArrow şeması tanımlıyoruz
            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), 384)), # multilingual-e5-small 384 boyutludur
                pa.field("text", pa.string()),
                pa.field("date", pa.string()),
                pa.field("chunk_index", pa.int32())
            ])
            self.table = self.db.create_table(self.table_name, schema=schema)
        else:
            self.table = self.db.open_table(self.table_name)

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
