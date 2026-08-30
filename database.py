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

import hashlib
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from settings import get_db_path

# Çıkarım şemasının sürümü. Şema değişince eski çıkarımlar bayat sayılır
# ve ilgili kayıtlar yeniden analiz edilir.
INSIGHT_SCHEMA_VERSION = 1

# entry_facets.kind alanında kullanılabilecek değerler
FACET_KINDS = (
    "activity",    # yapılan şeyler
    "postponed",   # ertelenenler
    "helped",      # iyi gelenler
    "hindered",    # zorlayanlar
    "emotion",     # duygular
    "person",      # birlikte vakit geçirilen kişiler
    "place",       # mekânlar
    "physical",    # fiziksel durum (yorgunluk, hastalık vb.)
)


def content_hash(content: str) -> str:
    """
    Günlük içeriğinin parmak izi. Kullanıcı yazısını düzenlediğinde hash
    değişir ve o kaydın çıkarımı bayat sayılarak yeniden hesaplanır.
    """
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


class Database:
    """
    SQLite veritabanı ile tüm etkileşimleri yöneten sınıf.
    settings.json'dan gelen yol üzerinden bağlantı kurar.
    """

    def __init__(self):
        self.db_path = get_db_path()

        # Hedef klasör yoksa oluştur (Docker volume'u ilk açılışta boş olabilir)
        parent_dir = os.path.dirname(self.db_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        self._initialize_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Her işlem için yeni bir bağlantı döner (thread-safe)."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        # WAL: InsightWorker arka planda yazarken UI'nin okuması bloklanmasın
        conn.execute("PRAGMA journal_mode=WAL")
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
        # Yapay zekânın her kayıttan çıkardığı yapısal veriler.
        # Analiz soruları ("en çok neyi erteledim") günlük metnini okuyarak
        # değil, bu tablolar üzerinde SQL ile sayılarak yanıtlanır.
        insights_sql = """
        CREATE TABLE IF NOT EXISTS entry_insights (
            date            TEXT PRIMARY KEY,
            summary         TEXT DEFAULT '',
            energy          INTEGER DEFAULT -1,
            sleep_quality   INTEGER DEFAULT -1,
            content_hash    TEXT NOT NULL,
            schema_version  INTEGER NOT NULL,
            created_at      TEXT
        );
        """
        facets_sql = """
        CREATE TABLE IF NOT EXISTS entry_facets (
            date       TEXT NOT NULL,
            kind       TEXT NOT NULL,
            label      TEXT NOT NULL,
            raw_label  TEXT NOT NULL,
            PRIMARY KEY (date, kind, label)
        );
        """
        # Etiket eş anlamlıları: "yürüyüşe çıkmak" -> "yürüyüş".
        # Kanonik etiket entry_facets.label'a yazılır; bu tablo hangi ham
        # yazımın hangi kanonik etikete bağlandığının kaydını tutar.
        aliases_sql = """
        CREATE TABLE IF NOT EXISTS label_aliases (
            kind      TEXT NOT NULL,
            alias     TEXT NOT NULL,
            canonical TEXT NOT NULL,
            PRIMARY KEY (kind, alias)
        );
        """
        index_sqls = (
            "CREATE INDEX IF NOT EXISTS idx_facets_kind_label ON entry_facets(kind, label);",
            "CREATE INDEX IF NOT EXISTS idx_facets_date ON entry_facets(date);",
        )

        with self._get_connection() as conn:
            conn.execute(create_sql)
            # Sütun zaten varsa hata fırlatır, bunu yoksay
            try:
                conn.execute(migration_sql)
            except sqlite3.OperationalError:
                pass  # Sütun zaten mevcut

            conn.execute(insights_sql)
            conn.execute(facets_sql)
            conn.execute(aliases_sql)
            for index_sql in index_sqls:
                conn.execute(index_sql)
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

    def get_entries_without_mood(self) -> list[dict]:
        """
        Henüz AI duygu puanı hesaplanmamış kayıtları döner.

        Duygu analizi eskiden get_all_entries_content() ile TÜM kayıtları
        alıyordu; AI paneli her açıldığında bütün günlükler yeniden LLM'e
        gönderiliyordu. Bu sorgu işi yalnızca eksik kayıtlarla sınırlar.
        """
        sql = """
        SELECT date, content
        FROM entries
        WHERE content != '' AND content IS NOT NULL
          AND (mood_score IS NULL OR mood_score = 0)
        ORDER BY date DESC
        """
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
                   mood_score: Optional[int] = None,
                   happiness_score: int = 0) -> None:
        """
        Kaydı ekler veya günceller (UPSERT).

        happiness_score: Kullanıcının 1-10 arası verdiği puan.
        mood_score:
            None (varsayılan) -> mevcut kayıttaki AI duygu puanı KORUNUR.
            Bir sayı verilirse o değer yazılır.

        Not: Eskiden mood_score varsayılan olarak 0 yazılıyordu; bu yüzden
        kullanıcı bir yazıyı düzenleyip yeniden kaydettiğinde yapay zekânın
        hesapladığı duygu puanı siliniyordu (istatistikler bozuluyordu).
        """
        if mood_score is None:
            sql = """
            INSERT INTO entries (date, content, mood_score, happiness_score)
            VALUES (?, ?, 0, ?)
            ON CONFLICT(date) DO UPDATE SET
                content         = excluded.content,
                happiness_score = excluded.happiness_score
            """
            params = (date, content, happiness_score)
        else:
            sql = """
            INSERT INTO entries (date, content, mood_score, happiness_score)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                content         = excluded.content,
                mood_score      = excluded.mood_score,
                happiness_score = excluded.happiness_score
            """
            params = (date, content, mood_score, happiness_score)

        with self._get_connection() as conn:
            conn.execute(sql, params)
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

    @staticmethod
    def _escape_like(keyword: str) -> str:
        """
        LIKE için özel anlamı olan karakterleri kaçışlar.
        Kaçışlanmazsa "%" araması TÜM kayıtları, "_" araması herhangi bir
        tek karakteri eşleştirir; kullanıcı düz metin aradığını sanır.
        """
        return (
            keyword.replace("\\", "\\\\")
                   .replace("%", "\\%")
                   .replace("_", "\\_")
        )

    def search_entries(self, keyword: str) -> list[dict]:
        """İçerikte geçen kelimeyi LIKE ile arar, sonuçları listeler."""
        sql = r"""
        SELECT date, content, mood_score, happiness_score
        FROM entries
        WHERE content LIKE ? ESCAPE '\'
        ORDER BY date DESC
        """
        pattern = f"%{self._escape_like(keyword)}%"
        with self._get_connection() as conn:
            cursor = conn.execute(sql, (pattern,))
            return [dict(row) for row in cursor.fetchall()]

    # ── Yapısal çıkarım (analiz katmanı) ───────────────────────────────────

    def get_insight(self, date: str) -> Optional[dict]:
        """Belirtilen güne ait çıkarım kaydını döner. Yoksa None."""
        sql = "SELECT * FROM entry_insights WHERE date = ?"
        with self._get_connection() as conn:
            row = conn.execute(sql, (date,)).fetchone()
            return dict(row) if row else None

    def get_facets(self, date: str) -> list[dict]:
        """Belirtilen güne ait tüm etiketleri döner."""
        sql = "SELECT kind, label, raw_label FROM entry_facets WHERE date = ? ORDER BY kind, label"
        with self._get_connection() as conn:
            return [dict(r) for r in conn.execute(sql, (date,)).fetchall()]

    def save_insight(self, date: str, content: str, summary: str = "",
                     energy: int = -1, sleep_quality: int = -1,
                     facets: dict = None) -> None:
        """
        Bir günün çıkarımını (özet + etiketler) kaydeder.

        facets: {"activity": ["spor"], "postponed": ["rapor yazma"], ...}
        O güne ait eski etiketler tamamen silinip yenisi yazılır; kullanıcı
        yazısını düzenlediğinde eski etiketler birikmemelidir.
        """
        insight_sql = """
        INSERT INTO entry_insights
            (date, summary, energy, sleep_quality, content_hash, schema_version, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            summary        = excluded.summary,
            energy         = excluded.energy,
            sleep_quality  = excluded.sleep_quality,
            content_hash   = excluded.content_hash,
            schema_version = excluded.schema_version,
            created_at     = excluded.created_at
        """
        params = (
            date, summary, energy, sleep_quality,
            content_hash(content), INSIGHT_SCHEMA_VERSION,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

        rows = []
        for kind, labels in (facets or {}).items():
            if kind not in FACET_KINDS:
                continue
            for label in labels:
                # label ("spor") normalize edilmiş, raw ham hâli olabilir
                canonical, raw = label if isinstance(label, tuple) else (label, label)
                if canonical:
                    rows.append((date, kind, canonical, raw))

        with self._get_connection() as conn:
            conn.execute(insight_sql, params)
            conn.execute("DELETE FROM entry_facets WHERE date = ?", (date,))
            if rows:
                conn.executemany(
                    "INSERT OR REPLACE INTO entry_facets (date, kind, label, raw_label) "
                    "VALUES (?, ?, ?, ?)",
                    rows,
                )
            conn.commit()

    def get_entries_needing_insight(self, start_date: str = None,
                                    end_date: str = None) -> list[dict]:
        """
        Çıkarımı hiç yapılmamış ya da bayatlamış kayıtları döner.

        Bayat sayılma nedenleri:
          - kullanıcı yazıyı düzenledi (content_hash uyuşmuyor)
          - çıkarım şeması yenilendi (schema_version eski)

        Tarih verilmezse tüm geçmiş taranır. Sonuç yeniden eskiye sıralıdır;
        arka plan doldurma en taze günlerden başlar.
        """
        # content_hash karşılaştırması SQL'de yapılamaz (SQLite'ta sha256
        # yok), bu yüzden aday satırlar çekilip Python'da elenir.
        sql = """
        SELECT e.date, e.content, i.content_hash AS stored_hash,
               i.schema_version AS stored_version
        FROM entries e
        LEFT JOIN entry_insights i ON i.date = e.date
        WHERE e.content != '' AND e.content IS NOT NULL
        """
        params = []
        if start_date and end_date:
            sql += " AND e.date >= ? AND e.date <= ?"
            params = [start_date, end_date]
        sql += " ORDER BY e.date DESC"

        with self._get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()

        pending = []
        for row in rows:
            stale = (
                row["stored_hash"] is None
                or row["stored_version"] != INSIGHT_SCHEMA_VERSION
                or row["stored_hash"] != content_hash(row["content"])
            )
            if stale:
                pending.append({"date": row["date"], "content": row["content"]})
        return pending

    def get_insight_coverage(self, start_date: str = None,
                             end_date: str = None) -> dict:
        """
        Bir dönemdeki kayıtların ne kadarının analiz edildiğini döner.

        Analiz eksikken verilen cevap yanıltıcı olabileceği için, cevabın
        başında bu oran kullanıcıya bildirilir.
        """
        sql = """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN i.date IS NOT NULL AND i.schema_version = ?
                        THEN 1 ELSE 0 END) AS analyzed
        FROM entries e
        LEFT JOIN entry_insights i ON i.date = e.date
        WHERE e.content != '' AND e.content IS NOT NULL
        """
        params = [INSIGHT_SCHEMA_VERSION]
        if start_date and end_date:
            sql += " AND e.date >= ? AND e.date <= ?"
            params += [start_date, end_date]

        with self._get_connection() as conn:
            row = conn.execute(sql, params).fetchone()

        total = row["total"] or 0
        analyzed = row["analyzed"] or 0
        return {
            "total": total,
            "analyzed": analyzed,
            "ratio": (analyzed / total) if total else 1.0,
        }

    def get_summaries_by_date_range(self, start_date: str, end_date: str) -> list[dict]:
        """
        Dönemdeki günlerin tek cümlelik özetlerini döner (map-reduce'un
        "map" adımı). Ham metin yerine bunu kullanmak, bir yıllık dönemi
        bile bağlam penceresine sığdırır.
        """
        sql = """
        SELECT e.date, i.summary, e.mood_score, e.happiness_score
        FROM entries e
        JOIN entry_insights i ON i.date = e.date
        WHERE e.date >= ? AND e.date <= ?
          AND i.summary != '' AND i.summary IS NOT NULL
        ORDER BY e.date ASC
        """
        with self._get_connection() as conn:
            return [dict(r) for r in conn.execute(sql, (start_date, end_date)).fetchall()]

    def save_label_alias(self, kind: str, alias: str, canonical: str) -> None:
        """Bir ham etiketi kanonik karşılığına bağlar."""
        if not alias or not canonical or alias == canonical:
            return
        sql = """
        INSERT INTO label_aliases (kind, alias, canonical) VALUES (?, ?, ?)
        ON CONFLICT(kind, alias) DO UPDATE SET canonical = excluded.canonical
        """
        with self._get_connection() as conn:
            conn.execute(sql, (kind, alias, canonical))
            conn.commit()

    def get_label_aliases(self, kind: str = None) -> list[dict]:
        """Kaydedilmiş eş anlamlı etiketleri döner (gözden geçirme için)."""
        sql = "SELECT kind, alias, canonical FROM label_aliases"
        params = []
        if kind:
            sql += " WHERE kind = ?"
            params.append(kind)
        sql += " ORDER BY kind, canonical, alias"
        with self._get_connection() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    # ── Analitik toplamalar ────────────────────────────────────────────────
    #
    # "En çok neyi erteledim?" gibi sorular SAYMA gerektirir. Dil modeli düz
    # metinden güvenilir sayamadığı için sayım burada, SQL'de yapılır; modele
    # yalnızca hazır sayılar verilir.

    def get_mood_series(self, start_date: str, end_date: str) -> list[dict]:
        """Dönemdeki günlerin duygu ve mutluluk puanlarını kronolojik döner."""
        sql = """
        SELECT date, mood_score, happiness_score
        FROM entries
        WHERE date >= ? AND date <= ?
          AND content != '' AND content IS NOT NULL
        ORDER BY date ASC
        """
        with self._get_connection() as conn:
            return [dict(r) for r in conn.execute(sql, (start_date, end_date)).fetchall()]

    def count_facet_days(self, kind: str, start_date: str = None,
                         end_date: str = None, limit: int = None) -> list[dict]:
        """
        Bir etiket türünün en sık geçen değerlerini GÜN SAYISIYLA döner.

        Aynı gün içinde tekrar eden etiket bir kez sayılır (COUNT DISTINCT):
        "spor" 9 farklı günde ertelenmişse sonuç 9'dur.
        """
        sql = """
        SELECT label, COUNT(DISTINCT date) AS day_count
        FROM entry_facets
        WHERE kind = ?
        """
        params = [kind]
        if start_date and end_date:
            sql += " AND date >= ? AND date <= ?"
            params += [start_date, end_date]
        sql += " GROUP BY label ORDER BY day_count DESC, label ASC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        with self._get_connection() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def get_facet_dates(self, kind: str, label: str, start_date: str = None,
                        end_date: str = None) -> list[str]:
        """Bir etiketin geçtiği günleri kronolojik döner (seri hesabı için)."""
        sql = "SELECT DISTINCT date FROM entry_facets WHERE kind = ? AND label = ?"
        params = [kind, label]
        if start_date and end_date:
            sql += " AND date >= ? AND date <= ?"
            params += [start_date, end_date]
        sql += " ORDER BY date ASC"

        with self._get_connection() as conn:
            return [r["date"] for r in conn.execute(sql, params).fetchall()]

    def get_dates_with_emotion(self, labels: list[str], mood_max: int = None,
                               start_date: str = None,
                               end_date: str = None) -> list[str]:
        """
        Belirli duygu etiketlerini taşıyan ya da duygu puanı eşiğin altında
        kalan günleri döner.

        "Stresli olduğumda bana ne iyi geliyor?" sorusunun ilk adımıdır:
        önce stresli günler bulunur, sonra o günlerde ne iyi geldiği sayılır.
        """
        conditions = []
        params: list = []

        if labels:
            placeholders = ",".join("?" * len(labels))
            conditions.append(
                f"EXISTS (SELECT 1 FROM entry_facets f "
                f"WHERE f.date = e.date AND f.kind = 'emotion' "
                f"AND f.label IN ({placeholders}))"
            )
            params += list(labels)

        if mood_max is not None:
            # mood_score 0 "hesaplanmadı" demektir, gerçek bir nötr değer değil
            conditions.append("(e.mood_score != 0 AND e.mood_score <= ?)")
            params.append(mood_max)

        if not conditions:
            return []

        sql = f"""
        SELECT DISTINCT e.date
        FROM entries e
        WHERE e.content != '' AND e.content IS NOT NULL
          AND ({" OR ".join(conditions)})
        """
        if start_date and end_date:
            sql += " AND e.date >= ? AND e.date <= ?"
            params += [start_date, end_date]
        sql += " ORDER BY e.date ASC"

        with self._get_connection() as conn:
            return [r["date"] for r in conn.execute(sql, params).fetchall()]

    def count_facet_days_on_dates(self, kind: str, dates: list[str],
                                  limit: int = None) -> list[dict]:
        """Yalnızca verilen günler içinde bir etiket türünü sayar."""
        if not dates:
            return []

        placeholders = ",".join("?" * len(dates))
        sql = f"""
        SELECT label, COUNT(DISTINCT date) AS day_count
        FROM entry_facets
        WHERE kind = ? AND date IN ({placeholders})
        GROUP BY label ORDER BY day_count DESC, label ASC
        """
        params = [kind] + list(dates)
        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        with self._get_connection() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def count_entries_in_range(self, start_date: str, end_date: str) -> int:
        """Dönemdeki dolu günlük sayısı."""
        sql = """
        SELECT COUNT(*) FROM entries
        WHERE date >= ? AND date <= ? AND content != '' AND content IS NOT NULL
        """
        with self._get_connection() as conn:
            return conn.execute(sql, (start_date, end_date)).fetchone()[0]

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
