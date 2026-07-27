"""
ai/worker.py
------------
UI'nin donmasını önlemek için arka plan QThread işlemleri.
Model indirme, RAG sohbeti ve veritabanı indeksleme.
"""

import os
import requests
from datetime import datetime, timedelta
import calendar
from PyQt6.QtCore import QThread, pyqtSignal

from database import Database
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
    
    def __init__(self, rag_engine, user_query: str, chat_history: list = None, last_date_range: tuple = None):
        super().__init__()
        self.rag_engine = rag_engine
        self.user_query = user_query
        self.chat_history = chat_history or []
        self.last_date_range = last_date_range # (start_date, end_date)
        
    def _parse_time_range(self, query: str):
        """Basit bir sorgu yönlendirici. 'geçen ay', 'bu ay' gibi anahtar kelimeleri algılar."""
        q = query.lower()
        today = datetime.now()
        
        # Basit ay isimleri haritası
        aylar = {
            "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6,
            "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12
        }
        
        if "geçen ay" in q:
            first = today.replace(day=1)
            last_month = first - timedelta(days=1)
            start_date = last_month.replace(day=1).strftime("%Y-%m-%d")
            end_date = last_month.strftime("%Y-%m-%d")
            return (start_date, end_date), "Geçen ayki günlüklerin taranıyor..."
            
        elif "bu ay" in q:
            start_date = today.replace(day=1).strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")
            return (start_date, end_date), "Bu ayki günlüklerin taranıyor..."
            
        elif "geçen hafta" in q:
            start_date = (today - timedelta(days=today.weekday() + 7)).strftime("%Y-%m-%d")
            end_date = (today - timedelta(days=today.weekday() + 1)).strftime("%Y-%m-%d")
            return (start_date, end_date), "Geçen haftaki günlüklerin taranıyor..."
            
        elif "bu hafta" in q:
            start_date = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")
            return (start_date, end_date), "Bu haftaki günlüklerin taranıyor..."
            
        # Ay isimlerini kontrol et
        for ay_adi, ay_no in aylar.items():
            if ay_adi in q:
                # O ayın ilk günü ve son gününü bul
                start_date = today.replace(month=ay_no, day=1).strftime("%Y-%m-%d")
                son_gun = calendar.monthrange(today.year, ay_no)[1]
                
                # Eğer o ay şu anki aysa, sadece bugüne kadar olanı al
                if ay_no == today.month:
                    end_date = today.strftime("%Y-%m-%d")
                else:
                    end_date = today.replace(month=ay_no, day=son_gun).strftime("%Y-%m-%d")
                    
                return (start_date, end_date), f"{ay_adi.capitalize()} ayı günlüklerin taranıyor..."
                
        return None, None
        
    def run(self):
        try:
            # 1. Yeni bir tarih aralığı soruluyor mu?
            date_range, loading_msg = self._parse_time_range(self.user_query)
            
            # 2. Eğer yeni bir tarih sorulmuyorsa ama önceki soru takvimle ilgiliyse bağlamı koru
            if not date_range and self.last_date_range:
                # "Neden kötüymüşüm?" gibi takip eden sorular için
                date_range = self.last_date_range
                loading_msg = "Günlüklerin taranıyor..."
                
            if date_range:
                # ROUTE 1: SQL Tabanlı Zaman Analizi (Report Engine Mantığı)
                self.mode_detected.emit("SQL", loading_msg)
                
                db = Database()
                report_engine = ReportEngine(self.rag_engine.llm)
                
                # Tüm dönemi okuyup spesifik soruya (user_query) cevap verecek
                stream = report_engine.generate_report_stream(
                    start_date=date_range[0],
                    end_date=date_range[1],
                    db=db,
                    user_question=self.user_query
                )
                
                for token in stream:
                    self.token_received.emit(token)
                    
                self.finished.emit(date_range)
                
            else:
                # ROUTE 2: Normal Vektör Arama (RAG)
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

class MoodAnalysisWorker(QThread):
    """Arka planda günlük metinlerinin duygu puanını (mood_score: -10..+10) hesaplar ve SQLite'a yazar."""
    finished = pyqtSignal()
    
    def __init__(self, llm_engine, db, entries: list[dict]):
        super().__init__()
        self.llm_engine = llm_engine
        self.db = db
        self.entries = entries # [{"date": "...", "content": "..."}, ...]
        
    def run(self):
        try:
            for entry in self.entries:
                if entry.get("content"):
                    score = self.llm_engine.analyze_mood(entry["content"])
                    self.db.update_mood_score(entry["date"], score)
        except Exception as e:
            print("MoodAnalysisWorker Hatası:", e)
        finally:
            self.finished.emit()
