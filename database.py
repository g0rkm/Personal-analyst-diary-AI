"""
database.py
-----------
Tüm SQLite veritabanı işlemlerini yönetir.
CRUD (Create, Read, Update, Delete) ve arama fonksiyonlarını içerir.

Sütunlar:
  date            TEXT PK   — YYYY-MM-DD
  content         TEXT      — Günlük metni
  mood_score      INTEGER   — AI tarafından hesaplanacak duygu skoru (-10..+10)
  happiness_score INTEGER   — Kullanıcının elle verdiği günlük mutluluk puanı (0..10)
"""

import sqlite3
from typing import Optional
from settings import get_db_path


class Database:
    """
    SQLite veritabanı ile tüm etkileşimleri yöneten sınıf.
    settings.json'dan gelen yol üzerinden bağlantı kurar.
    """

    def __init__(self):
        self.db_path = get_db_path()
        self._initialize_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Her işlem için yeni bir bağlantı döner (thread-safe)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_db(self) -> None:
        """
        Tabloyu oluşturur (yoksa) ve eksik sütunları ekler.
        Mevcut verilere zarar vermez (ALTER TABLE IF NOT EXISTS mantığı).
        """
        create_sql = """
        CREATE TABLE IF NOT EXISTS entries (
            date            TEXT PRIMARY KEY,
            content         TEXT DEFAULT '',
            mood_score      INTEGER DEFAULT 0,
            happiness_score INTEGER DEFAULT 0
        );
        """
        # Eski veritabanlarına happiness_score sütunu ekle (migration)
        migration_sql = """
        ALTER TABLE entries ADD COLUMN happiness_score INTEGER DEFAULT 0;
        """
        with self._get_connection() as conn:
            conn.execute(create_sql)
            # Sütun zaten varsa hata fırlatır, bunu yoksay
            try:
                conn.execute(migration_sql)
            except sqlite3.OperationalError:
                pass  # Sütun zaten mevcut
            conn.commit()

    # ── Okuma ──────────────────────────────────────────────────────────────

    def get_entry(self, date: str) -> Optional[sqlite3.Row]:
        """Belirtilen tarihe ait kaydın tamamını döner. Yoksa None."""
        sql = "SELECT * FROM entries WHERE date = ?"
        with self._get_connection() as conn:
            cursor = conn.execute(sql, (date,))
            return cursor.fetchone()

    def get_all_entry_dates(self) -> list[str]:
        """İçeriği dolu olan tüm tarihleri döner (ısı haritası için)."""
        sql = "SELECT date FROM entries WHERE content != '' AND content IS NOT NULL"
        with self._get_connection() as conn:
            cursor = conn.execute(sql)
            return [row["date"] for row in cursor.fetchall()]

    def get_all_entries_with_scores(self) -> list[dict]:
        """
        Tüm kayıtları tarih + happiness_score + mood_score ile döner.
        Tam ekran takvim ve AI analizi için kullanılır.
        """
        sql = """
        SELECT date, happiness_score, mood_score
        FROM entries
        WHERE content != '' AND content IS NOT NULL
        ORDER BY date DESC
        """
        with self._get_connection() as conn:
            cursor = conn.execute(sql)
            return [dict(row) for row in cursor.fetchall()]

    def get_all_entries_content(self) -> list[dict]:
        """Tüm günlük içeriklerini tarih ve içerik olarak döner (İndeksleme için)."""
        sql = "SELECT date, content FROM entries WHERE content != '' AND content IS NOT NULL"
        with self._get_connection() as conn:
            cursor = conn.execute(sql)
            return [dict(row) for row in cursor.fetchall()]

    def get_entries_by_date_range(self, start_date: str, end_date: str) -> list[dict]:
        """
        Belirtilen tarih aralığındaki tüm kayıtları kronolojik sırayla döner.
        Raporlama ve özet motoru (ReportEngine) için kullanılır.
        """
        sql = """
        SELECT date, content, mood_score, happiness_score 
        FROM entries 
        WHERE date >= ? AND date <= ? AND content != '' AND content IS NOT NULL
        ORDER BY date ASC
        """
        with self._get_connection() as conn:
            cursor = conn.execute(sql, (start_date, end_date))
            return [dict(row) for row in cursor.fetchall()]

    # ── Yazma ──────────────────────────────────────────────────────────────

    def save_entry(self, date: str, content: str,
                   mood_score: int = 0,
                   happiness_score: int = 0) -> None:
        """
        Kaydı ekler veya günceller (UPSERT).
        happiness_score: Kullanıcının 1-10 arası verdiği puan.
        mood_score: AI tarafından doldurulacak (-10..+10), şimdilik 0.
        """
        sql = """
        INSERT INTO entries (date, content, mood_score, happiness_score)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            content         = excluded.content,
            mood_score      = excluded.mood_score,
            happiness_score = excluded.happiness_score
        """
        with self._get_connection() as conn:
            conn.execute(sql, (date, content, mood_score, happiness_score))
            conn.commit()

    def update_mood_score(self, date: str, mood_score: int) -> None:
        """Yapay zeka tarafından hesaplanan duygu puanını (-10..+10) günceller."""
        sql = "UPDATE entries SET mood_score = ? WHERE date = ?"
        with self._get_connection() as conn:
            conn.execute(sql, (mood_score, date))
            conn.commit()

    def delete_entry(self, date: str) -> None:
        """Belirtilen tarihe ait kaydı siler."""
        sql = "DELETE FROM entries WHERE date = ?"
        with self._get_connection() as conn:
            conn.execute(sql, (date,))
            conn.commit()

    # ── Arama ──────────────────────────────────────────────────────────────

    def search_entries(self, keyword: str) -> list[dict]:
        """İçerikte geçen kelimeyi LIKE ile arar, sonuçları listeler."""
        sql = """
        SELECT date, content, mood_score, happiness_score
        FROM entries
        WHERE content LIKE ?
        ORDER BY date DESC
        """
        pattern = f"%{keyword}%"
        with self._get_connection() as conn:
            cursor = conn.execute(sql, (pattern,))
            return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> dict:
        """
        Uygulama geneli istatistikleri döner.
        AI rapor özelliği için hazır.
        """
        with self._get_connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM entries WHERE content != ''"
            ).fetchone()[0]
            avg_happiness = conn.execute(
                "SELECT AVG(happiness_score) FROM entries "
                "WHERE content != '' AND happiness_score > 0"
            ).fetchone()[0]
        return {
            "total_entries": total,
            "avg_happiness": round(avg_happiness, 1) if avg_happiness else 0,
        }
