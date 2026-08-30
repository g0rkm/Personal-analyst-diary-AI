"""
ai/llm_engine.py
----------------
llama-cpp-python kütüphanesini sarmalar.
Modelin GPU/CPU üzerinde tembel yüklenmesini (lazy load)
ve akıcı (streaming) şekilde metin üretmesini sağlar.

ÖNEMLİ: llama.cpp C++ nesnesi thread-safe DEĞİLDİR.
Aynı anda birden fazla QThread (MoodAnalysis + Chat) erişirse segfault olur.
Bu yüzden tüm erişimler threading.Lock ile sıraya alınır.
"""

import json
import os
import threading
from llama_cpp import Llama

from core.token_budget import estimate_tokens
from settings import load_settings

# Modelin bağlam penceresi. Prompt + yanıt bu sınırın altında kalmalıdır;
# core.token_budget bu değere göre bütçe hesaplar.
CONTEXT_WINDOW = 4096

class LlamaEngine:
    def __init__(self, model_path: str = None, gpu_layers: int = 0):
        if model_path is None:
            settings = load_settings()
            self.model_path = settings.get("model_path", "models/qwen2.5-3b-instruct-q4_k_m.gguf")
        else:
            self.model_path = model_path
            
        self.gpu_layers = gpu_layers
        self.llm = None
        self._lock = threading.Lock()  # C++ nesnesine eşzamanlı erişimi engeller
        
    def is_loaded(self) -> bool:
        return self.llm is not None
        
    def load_model(self):
        """Modeli belleğe veya VRAM'e yükler. İlk çağrıda çalışır."""
        if self.llm is None:
            with self._lock:
                # Double-check locking: lock aldıktan sonra tekrar kontrol et
                if self.llm is None:
                    if not os.path.exists(self.model_path):
                        raise FileNotFoundError(f"Model dosyası bulunamadı: {self.model_path}")
                    
                    self.llm = Llama(
                        model_path=self.model_path,
                        n_gpu_layers=self.gpu_layers,
                        n_ctx=CONTEXT_WINDOW,
                        verbose=False
                    )
            
    def count_tokens(self, text: str) -> int:
        """
        Metnin modelin kendi tokenizer'ına göre token sayısını döner.

        Model henüz yüklenmemişse MODEL YÜKLENMEZ — sadece tahmin döner.
        Bütçe hesabı için 1.9 GB'lık modeli belleğe almak gereksizdir ve
        arayüzü kilitler. Model zaten yüklüyse gerçek sayım yapılır.
        """
        if not text:
            return 0

        if self.llm is None:
            return estimate_tokens(text)

        try:
            with self._lock:
                return len(self.llm.tokenize(text.encode("utf-8"), add_bos=False))
        except Exception:
            # Tokenizer beklenmedik bir şekilde hata verirse bütçe hesabı
            # çökmesin; temkinli tahmine düş.
            return estimate_tokens(text)

    def chat_stream(self, messages: list[dict]):
        """
        Gelen mesaj geçmişine göre yanıtı token token (stream) üretir.
        Lock alır, tüm tokenler üretilene kadar bırakmaz.
        """
        self.load_model()
        
        with self._lock:
            stream = self.llm.create_chat_completion(
                messages=messages,
                stream=True,
                temperature=0.15,
                top_p=0.9,
                repeat_penalty=1.15,
                max_tokens=1024
            )
            
            for chunk in stream:
                delta = chunk['choices'][0].get('delta', {})
                if 'content' in delta:
                    yield delta['content']

    def complete_json(self, messages: list[dict], schema: dict,
                      max_tokens: int = 512) -> dict:
        """
        Modeli verilen JSON şemasına UYMAYA ZORLAYARAK yapısal çıktı üretir.

        llama.cpp, şemayı bir GBNF dilbilgisine çevirip üretimi kısıtlar;
        yani model şema dışında bir token üretemez. 3B'lik küçük bir modelden
        güvenilir yapısal veri almanın tek pratik yolu budur — serbest metin
        istenirse bozuk JSON, eksik alan ve uydurma anahtar dönüyor.

        Şema ihlali ya da çözümleme hatası durumunda boş sözlük döner;
        çağıran tarafın varsayılanlara düşmesi beklenir.
        """
        self.load_model()

        with self._lock:
            try:
                response = self.llm.create_chat_completion(
                    messages=messages,
                    stream=False,
                    temperature=0.1,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object", "schema": schema},
                )
                content = response["choices"][0]["message"]["content"]
            except Exception as e:
                print("Yapısal çıkarım hatası:", e)
                return {}

        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return {}

        return parsed if isinstance(parsed, dict) else {}

    def analyze_mood(self, text: str) -> int:
        """Metnin duygu puanını -10 ile +10 arasında puanlar. Lock ile korunur."""
        self.load_model()
        
        messages = [
            {
                "role": "system", 
                "content": "Sen bir duygu analitiği uzmanısın. Sana verilen günlük metnini oku ve yazarın genel ruh halini -10 (çok üzgün/öfkeli/stresli) ile +10 (çok mutlu/coşkulu/huzurlu) arasında tek bir tam sayı ile puanla. SADECE TEK BİR TAM SAYI YAZ. Başka hiçbir kelime yazma. Örnekler: 6 veya -4 veya 0."
            },
            {"role": "user", "content": text[:1000]}
        ]
        
        with self._lock:
            try:
                response = self.llm.create_chat_completion(
                    messages=messages,
                    stream=False,
                    temperature=0.1,
                    max_tokens=10
                )
                content = response['choices'][0]['message']['content'].strip()
                import re
                match = re.search(r'[-+]?\d+', content)
                if match:
                    val = int(match.group())
                    return max(-10, min(10, val))
            except Exception as e:
                print("Mood analizi hatası:", e)
            
        return 0

