"""
ai/rag_engine.py
----------------
RAG (Retrieval-Augmented Generation) sürecini yönetir.
Girdi alır -> vektör arar -> LLM promptunu hazırlar -> stream döner.
Sohbet geçmişini de modele aktararak bağlam takibini sağlar.
"""

from ai.embedder import DiaryEmbedder
from ai.vector_store import DiaryVectorStore
from ai.llm_engine import LlamaEngine

class RAGEngine:
    def __init__(self, embedder=None, vector_store=None, llm_engine=None):
        # Bağımlılıkları dışarıdan da alabiliriz (tekilliği sağlamak için)
        self.embedder = embedder or DiaryEmbedder()
        self.vector_store = vector_store or DiaryVectorStore()
        self.llm = llm_engine or LlamaEngine()
        
    def build_messages(self, user_query: str, retrieved_chunks: list[dict],
                       chat_history: list[dict] = None) -> list[dict]:
        """
        Bulunan parçaları sistem promptuyla birleştirip OpenAI ChatML formatına çevirir.
        chat_history: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
        """
        
        context_text = ""
        if retrieved_chunks:
            for chunk in retrieved_chunks:
                text = chunk["text"]
                context_text += f"[Tarih: {chunk['date']}]\n{text}\n\n"
        else:
            context_text = "Eşleşen günlük kaydı bulunamadı."
            
        system_prompt = f"""Sen kullanıcının yakın bir dostu ve kişisel günlük asistanısın.
Kullanıcı sana geçmişiyle ilgili sorular soracak. Aşağıda kullanıcının geçmiş günlüğünden bulunan ilgili kayıtlar (ALINTILAR) verilmiştir.

KURALLAR:
1. Sadece aşağıdaki ALINTILAR'a dayanarak cevap ver. Eğer alıntılarda bilgi yoksa "Günlüklerinde bundan bahsetmemişsin" de.
2. Türkçe konuş. Karşında bir arkadaşın varmış gibi "sen" hitabıyla samimi ve doğal cevaplar ver. Asla "siz" deme.
3. Cevaplarında "Bağlama göre", "Alıntılara göre", "Kayıtlarında" gibi robotik kelimeler KULLANMA. Doğrudan cevap ver. (Örnek: "1 Temmuz'da yürüyüş yapmışsın.")
4. Kısa ve net ol.

ALINTILAR:
---
{context_text.strip()}
---"""
        messages = [{"role": "system", "content": system_prompt}]
        
        # Önceki sohbet geçmişini ekle (son 10 mesajla sınırla — bağlam taşmasını önlemek için)
        if chat_history:
            recent_history = chat_history[-10:]
            messages.extend(recent_history)
        
        # Son olarak mevcut kullanıcı sorusunu ekle
        messages.append({"role": "user", "content": user_query})
        
        return messages

    def chat_stream(self, user_query: str, chat_history: list[dict] = None):
        """Kullanıcının sorusuna parçaları bulup LLM üzerinden stream olarak yanıt üretir."""
        # 1. Soruyu vektöre çevir
        query_vector = self.embedder.embed_query(user_query)
        
        # 2. Vektör DB'de ara
        chunks = self.vector_store.search(query_vector, limit=5)
        
        # 3. Mesaj dizisini oluştur (geçmişle birlikte)
        messages = self.build_messages(user_query, chunks, chat_history)
        
        # 4. LLM üzerinden yanıtı token token alıp yield et
        for token in self.llm.chat_stream(messages):
            yield token

