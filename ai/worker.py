"""
ai/worker.py
------------
UI'nin donmasını önlemek için arka plan QThread işlemleri.
Model indirme, RAG sohbeti ve veritabanı indeksleme.
"""

import os
import requests
from PyQt6.QtCore import QThread, pyqtSignal

from ai.chunker import chunk_entry

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
    """RAG üzerinden soru sorup gelen cevabı UI'ye stream eder."""
    token_received = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, rag_engine, user_query: str, chat_history: list = None):
        super().__init__()
        self.rag_engine = rag_engine
        self.user_query = user_query
        self.chat_history = chat_history or []
        
    def run(self):
        try:
            for token in self.rag_engine.chat_stream(self.user_query, self.chat_history):
                self.token_received.emit(token)
            self.finished.emit()
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
