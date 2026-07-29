# 📓 Personal Analyst: AI Destekli Akıllı Günlük Uygulaması

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-UI_Framework-green)](https://riverbankcomputing.com/software/pyqt/intro)
[![Llama-cpp](https://img.shields.io/badge/llama.cpp-Local_LLM-orange)](https://github.com/ggerganov/llama.cpp)
[![LanceDB](https://img.shields.io/badge/LanceDB-Vector_Store-blueviolet)](https://lancedb.com/)

Personal Analyst, klasik günlük tutma deneyimini tamamen yerel ve çevrimdışı çalışan bir Yapay Zeka (AI) asistanı ile birleştiren modern bir masaüstü (Windows) uygulamasıdır. 

Yazdığınız her cümle güvendedir ve asla internete gönderilmez. Gelişmiş yerel yapay zeka (RAG & Akıllı Yönlendirici) sayesinde, günlükleriniz sizinle konuşan, sizi analiz eden ve size içgörüler sunan bir kişisel psikoloğa dönüşür.

---

## ✨ Özellikler

### 🧠 Tamamen Yerel ve Gizli Yapay Zeka
Tüm yapay zeka işlemleri (LLM çıkarımları ve vektör aramaları) tamamen kendi bilgisayarınızda (çevrimdışı) çalışır. Verileriniz asla dışarı çıkmaz. Uygulama, Qwen2.5-3B modelini indirerek minimum RAM (8GB) ve CPU gereksinimiyle bile akıcı bir sohbet deneyimi sunar.

### 🔍 Akıllı Yönlendirici (Smart Query Router)
Sadece anahtar kelime araması değil, bağlam ve zaman farkındalığına sahip hibrit bir sohbet altyapısı:
- **Spesifik Anı Arama (RAG):** *"Geçen ay spora ne zaman başlamıştım?"* gibi sorularda LanceDB (Vektör Veritabanı) devreye girerek semantik eşleşme bulur.
- **Zaman Bazlı Raporlama (SQL):** *"Geçen ay ruh halim nasıldı?"* veya *"Bu hafta en çok neyi erteledim?"* dediğinizde, sistem zaman dilimini algılar ve arama motorunu devre dışı bırakarak o ayın tamamını okuyup size özel bir analiz raporu çıkarır.
- **Sohbet Hafızası:** Ardışık sorularda (Örn: *"Peki neden böyle hissetmişim?"*) bağlamı ve zamanı hatırlar.

### 📊 Isı Haritası (Heatmap) ve Duygu Analizi
GitHub tarzı ısı haritası takvimi ile hangi günlerde ne kadar yoğun yazdığınızı görebilirsiniz. Arka planda çalışan AI asistan, yazdığınız her günlüğe bir **Duygu Puanı (Mood Score)** atar.

### 🎨 Modern ve Şık Arayüz
Minimalist, Dark Mode odaklı, "Glassmorphism" (buzlu cam efekti) tasarımı, pürüzsüz geçişleri ve mikro animasyonlarıyla uygulamanın içinde vakit geçirmek oldukça keyiflidir. "Düşünüyor..." veya "Geçen ayki günlüklerin taranıyor..." gibi interaktif yükleme bildirimleri bulunur.

---

## 🚀 Kurulum & Çalıştırma

Proje, Windows üzerinde CPU tabanlı olarak sorunsuz çalışması için tasarlandı.

### 1. Gereksinimler
- **Python 3.10+** (Ortam değişkenlerine (PATH) eklendiğinden emin olun).
- Gerekli derleme araçları (C++ Build Tools).

### 2. Kurulum Adımları
```powershell
# Depoyu klonlayın ve klasöre girin
git clone https://github.com/g0rkm/Personal-analyst-diary-AI.git
cd Personal-analyst-diary-AI

# Bağımlılıkları yükleyin
pip install -r requirements.txt
```
*(Eğer `llama-cpp-python` yüklerken hata alırsanız, C++ Build Tools eksik olabilir veya doğrudan Wheel dosyası kurmanız gerekebilir).*

### 3. Çalıştırma
```powershell
python main.py
```
Uygulamayı ilk başlattığınızda ve AI Asistan panelini açtığınızda, yaklaşık 1.9 GB boyutundaki yerel dil modeli (GGUF formatında) otomatik olarak `models/` klasörüne indirilecektir.

---

## 🛠️ Mimari Altyapı

- **UI Framework:** PyQt6 (Özelleştirilmiş stiller ve asenkron Thread Worker'lar).
- **Yerel LLM:** `llama-cpp-python` (Qwen2.5-3B-Instruct Q4_K_M GGUF).
- **Vektör Veritabanı:** `LanceDB` (Semantik arama ve RAG için).
- **İlişkisel Veritabanı:** `SQLite` (Hızlı tarih sorguları ve veri saklama).
- **Embedding Modeli:** `paraphrase-multilingual-MiniLM-L12-v2` (Cümleleri anlam vektörlerine çevirmek için).
- **Asenkron İşlemler:** Model indirme, vektör indeksleme, duygu analizi ve AI chat cevapları QThread üzerinden arayüzü dondurmadan çalıştırılır.

---

## 🔮 Gelecek Planları
- [x] RAG (Vektör Tabanlı) Anı Araması
- [x] Zaman Bazlı Analiz ve Smart Router
- [x] Otomatik Duygu Analizi ve Skorlama
- [ ] Rapor Ekranı üzerinden Duygu Puanı Grafikleri (Trend Çizgileri)
- [ ] Gelişmiş PDF / Dışa Aktarma (Export) Özellikleri

---

*Not: Uygulama içerisinde kullanılan yapay zeka modelleri 3 Milyar (3B) parametreli olduğu için Türkçe gramer sınırlarını zaman zaman zorlayabilmektedir, ancak prompt mühendisliğiyle ('Şimdiki Zaman Kullan' kuralı vb.) maksimum verimliliğe optimize edilmiştir.*
