"""
ai/embedder.py
--------------
Metinleri vektörlere dönüştürür.
Model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (ONNX, ~220 MB)
Bu model prefix gerektirmez (query:/passage: eklemeye gerek yok).
"""

import warnings
warnings.filterwarnings("ignore")
import logging
logging.getLogger("fastembed").setLevel(logging.ERROR)

from typing import List, Union
import numpy as np
from fastembed import TextEmbedding

class DiaryEmbedder:
    def __init__(self):
        # İlk çalışmada modeli (~220 MB) otomatik indirir ve önbelleğe alır
        self.model = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        
    def embed_documents(self, documents: List[str]) -> List[List[float]]:
        """Günlük yazılarını vektöre çevirir."""
        # Bu model prefix gerektirmiyor, doğrudan metni gönder
        embeddings_gen = self.model.embed(documents)
        
        # NumPy array'den standart Python float listesine çevirelim
        return [embedding.tolist() for embedding in embeddings_gen]
        
    def embed_query(self, query: str) -> List[float]:
        """Arama sorgusunu vektöre çevirir."""
        embeddings_gen = self.model.embed([query])
        embeddings = list(embeddings_gen)
        return embeddings[0].tolist()
