"""
ai/worker.py
------------
UI'nin donmasını önlemek için arka plan QThread işlemleri.
Model indirme, RAG sohbeti ve veritabanı indeksleme.
"""

import os
import requests
from PyQt6.QtCore import QThread, pyqtSignal

from core.query_intent import SUMMARY, parse_intents
from core.time_range import parse_time_range
from database import Database
from ai.analysis_engine import AnalysisEngine
from ai.chunker import chunk_entry
from ai.report_engine import ReportEngine

class ModelDownloadWorker(QThread):
    """Büyük model dosyasını arka planda indirir ve ilerlemeyi bildirir."""
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str) # success, message
    
    def __init__(self, model_url: str, output_path: str):
        super().__init__()
        self.model_url = model_url
        self.output_path = output_path
        self._is_cancelled = False
        
    def cancel(self):
        self._is_cancelled = True
        
    def run(self):
        try:
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
            
            with requests.get(self.model_url, stream=True) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                
                # Geçici dosyaya yazalım, yarıda kesilirse asıl dosya bozuk kalmasın
                temp_path = self.output_path + ".download"
                
                with open(temp_path, 'wb') as f:
                    downloaded = 0
                    for chunk in r.iter_content(chunk_size=8192 * 4):
                        if self._is_cancelled:
                            self.finished.emit(False, "İndirme iptal edildi.")
                            return
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = int((downloaded / total_size) * 100)
                                self.progress.emit(percent)
                                
            # İndirme başarıyla bitince adını düzelt
            if os.path.exists(self.output_path):
                os.remove(self.output_path)
            os.rename(temp_path, self.output_path)
                                
            self.finished.emit(True, "Model başarıyla indirildi.")
        except Exception as e:
            self.finished.emit(False, f"Hata: {str(e)}")

class RAGChatWorker(QThread):
    """RAG veya SQL çekimi üzerinden soru sorup gelen cevabı UI'ye stream eder."""
    token_received = pyqtSignal(str)
    mode_detected = pyqtSignal(str, str) # (mode, loading_message)
    finished = pyqtSignal(object) # Yeni last_date_range dönmek için
    error = pyqtSignal(str)
    
    # Cevap vermeden önce yerinde analiz edilecek azami kayıt sayısı.
    # Kullanıcı "hibrit" doldurmayı seçti: sorulan dönem öncelikli işlenir,
    # ama cevabın dakikalarca gecikmemesi için bir üst sınır gerekir.
    MAX_INLINE_INSIGHTS = 12

    def __init__(self, rag_engine, user_query: str, chat_history: list = None,
                 last_date_range: tuple = None, insight_extractor=None,
                 label_merger=None, db=None):
        super().__init__()
        self.rag_engine = rag_engine
        self.user_query = user_query
        self.chat_history = chat_history or []
        self.last_date_range = last_date_range # (start_date, end_date)
        # Analiz rotasında eksik çıkarımları yerinde tamamlamak için
        self.insight_extractor = insight_extractor
        self.label_merger = label_merger
        self._db = db
        
    def _parse_time_range(self, query: str):
        """
        Sorgudaki zaman ifadesini tarih aralığına çevirir.

        Asıl mantık core.time_range içindedir: Qt'den bağımsız olduğu için
        arayüz başlatmadan test edilebilir ve kelime sınırlarına saygı duyar
        ("çekimser" artık Ekim, "smart" artık Mart olarak algılanmaz).
        """
        return parse_time_range(query)

    def _fill_missing_insights(self, db, start_date, end_date) -> None:
        """
        Sorulan dönemdeki eksik çıkarımları cevap verilmeden önce tamamlar.

        Tümü değil, MAX_INLINE_INSIGHTS kadarı işlenir: 300 kayıtlık bir
        geçmişi beklemek kullanıcıyı dakikalarca oyalar. Kalanı arka planda
        tamamlanır ve olgu kağıdındaki "VERİ KAPSAMI" satırı eksikliği
        dürüstçe bildirir.
        """
        if self.insight_extractor is None:
            return

        bekleyen = db.get_entries_needing_insight(start_date, end_date)
        if not bekleyen:
            return

        bekleyen = bekleyen[: self.MAX_INLINE_INSIGHTS]
        toplam = len(bekleyen)

        for sira, entry in enumerate(bekleyen, start=1):
            self.mode_detected.emit(
                "ANALYSIS", f"Eksik günlükler analiz ediliyor: {sira}/{toplam}"
            )
            try:
                insight = self.insight_extractor.extract(entry["content"])
                facets = insight.facets
                if self.label_merger is not None:
                    facets = self.label_merger.merge_facets(facets)

                db.save_insight(
                    date=entry["date"],
                    content=entry["content"],
                    summary=insight.summary,
                    energy=insight.energy,
                    sleep_quality=insight.sleep_quality,
                    facets=facets,
                )
                db.update_mood_score(entry["date"], insight.mood)
            except Exception as e:
                print(f"Çıkarım atlandı ({entry['date']}):", e)

    def run(self):
        """
        Soruyu üç rotadan birine yönlendirir:

          ANALİZ — "en çok neyi erteledim", "ruh halim nasıldı" gibi toplu
                   sorular. Sayılar SQL ile hesaplanır, model yalnızca
                   anlatır (ai/analysis_engine.py).
          ÖZET   — "bu ayı özetle": dönemin günlükleri okunur.
          RAG    — "spora ne zaman başlamıştım": belirli bir anı aranır.
        """
        try:
            # 1. Sorudaki zaman aralığı
            date_range, loading_msg = self._parse_time_range(self.user_query)

            # 2. Zaman ifadesi yoksa önceki sorunun dönemini sürdür
            #    ("Peki neden böyle hissetmişim?" gibi takip soruları)
            if not date_range and self.last_date_range:
                date_range = self.last_date_range
                loading_msg = "Günlüklerin taranıyor..."

            start_date, end_date = date_range if date_range else (None, None)

            # 3. Soru hangi analizi istiyor?
            intents = parse_intents(self.user_query)
            analiz_istekleri = [i for i in intents if i.kind != SUMMARY]

            if analiz_istekleri:
                # ROTA 1: Analiz — sayılar SQL'den, anlatı modelden
                self.mode_detected.emit(
                    "ANALYSIS", loading_msg or "Günlüklerin analiz ediliyor..."
                )
                db = self._db or Database()

                # Sorulan dönemde analizi eksik kayıt varsa önce onları
                # tamamla; analiz edilmemiş günler cevaba giremez.
                self._fill_missing_insights(db, start_date, end_date)

                engine = AnalysisEngine(self.rag_engine.llm)
                stream = engine.analyze_stream(
                    db=db,
                    user_question=self.user_query,
                    intents=analiz_istekleri,
                    start_date=start_date,
                    end_date=end_date,
                )
                for token in stream:
                    self.token_received.emit(token)
                self.finished.emit(date_range)

            elif date_range:
                # ROTA 2: Dönem özeti — günlükler okunur
                self.mode_detected.emit("SQL", loading_msg)
                stream = ReportEngine(self.rag_engine.llm).generate_report_stream(
                    start_date=start_date,
                    end_date=end_date,
                    db=Database(),
                    user_question=self.user_query,
                )
                for token in stream:
                    self.token_received.emit(token)
                self.finished.emit(date_range)

            else:
                # ROTA 3: Belirli anı arama (vektör tabanlı RAG)
                self.mode_detected.emit("RAG", "Düşünüyor...")
                for token in self.rag_engine.chat_stream(self.user_query, self.chat_history):
                    self.token_received.emit(token)
                self.finished.emit(None)

        except Exception as e:
            self.error.emit(str(e))

class IndexWorker(QThread):
    """Kayıtları arka planda parçalara bölüp vektöre çevirir (UI'yi dondurmamak için)."""
    finished = pyqtSignal()
    
    def __init__(self, embedder, vector_store, entries: list[dict]):
        super().__init__()
        self.embedder = embedder
        self.vector_store = vector_store
        self.entries = entries # [{"date": "2026-05-30", "content": "..."}, ...]
        
    def run(self):
        try:
            chunks_to_add = []
            for entry in self.entries:
                chunks = chunk_entry(entry["date"], entry["content"])
                chunks_to_add.extend(chunks)
                
            if chunks_to_add:
                texts = [c["text"] for c in chunks_to_add]
                embeddings = self.embedder.embed_documents(texts)
                self.vector_store.add_chunks(chunks_to_add, embeddings)
        except Exception as e:
            print("IndexWorker Hatası:", e)
        finally:
            self.finished.emit()

class InsightWorker(QThread):
    """
    Arka planda günlüklerden yapısal veri çıkarır (duygu puanı, tek cümlelik
    özet, yapılanlar/ertelenenler/iyi gelenler etiketleri) ve SQLite'a yazar.

    Eskiden burada yalnızca duygu puanı hesaplayan MoodAnalysisWorker vardı.
    "En çok neyi erteledim?" gibi sorular sayma gerektirdiği ve model düz
    metinden güvenilir sayamadığı için, sayılabilir veriyi yazma anında
    üreten bu işçi onun yerini aldı.

    Kayıt başına bir çıkarım yapılır ve sonuç önbelleğe alınır; aynı kayıt
    (metni değişmedikçe) bir daha analiz edilmez.
    """

    progress = pyqtSignal(int, int)   # (tamamlanan, toplam)
    finished = pyqtSignal()

    def __init__(self, extractor, db, entries: list[dict], merger=None):
        super().__init__()
        self.extractor = extractor
        self.db = db
        self.entries = entries        # [{"date": "...", "content": "..."}, ...]
        # Etiket birleştirici (ai/label_merger.py). Verilmezse etiketler
        # yazıldıkları gibi saklanır.
        self.merger = merger
        self._cancelled = False

    def cancel(self):
        """Uygulama kapanırken ya da öncelik değişince işi durdurur."""
        self._cancelled = True

    def run(self):
        toplam = len(self.entries)
        try:
            for sira, entry in enumerate(self.entries, start=1):
                if self._cancelled:
                    break

                content = entry.get("content")
                if not content:
                    continue

                try:
                    insight = self.extractor.extract(content)

                    facets = insight.facets
                    if self.merger is not None:
                        # "yürüyüşe çıkmak" -> "yürüyüş": sayımların
                        # bölünmemesi için etiketler kanonik hale getirilir
                        facets = self.merger.merge_facets(facets)

                    self.db.save_insight(
                        date=entry["date"],
                        content=content,
                        summary=insight.summary,
                        energy=insight.energy,
                        sleep_quality=insight.sleep_quality,
                        facets=facets,
                    )
                    self.db.update_mood_score(entry["date"], insight.mood)
                except Exception as e:
                    # Tek bir sorunlu kayıt yüzünden geri kalan yüzlerce
                    # kaydın analizi durmamalı; bu kayıt bir sonraki turda
                    # yeniden denenir (çıkarımı kaydedilmediği için bekleyen
                    # listesinde kalır).
                    print(f"Çıkarım atlandı ({entry['date']}):", e)

                self.progress.emit(sira, toplam)
        except Exception as e:
            print("InsightWorker Hatası:", e)
        finally:
            self.finished.emit()
