# 📓 Personal Analyst: AI Destekli Akıllı Günlük Uygulaması

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-UI_Framework-green)](https://riverbankcomputing.com/software/pyqt/intro)
[![Llama-cpp](https://img.shields.io/badge/llama.cpp-Local_LLM-orange)](https://github.com/ggerganov/llama.cpp)
[![LanceDB](https://img.shields.io/badge/LanceDB-Vector_Store-blueviolet)](https://lancedb.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

Personal Analyst, klasik günlük tutma deneyimini tamamen yerel ve çevrimdışı çalışan bir Yapay Zeka (AI) asistanı ile birleştiren modern bir masaüstü (Windows) uygulamasıdır. 

Yazdığınız her cümle güvendedir ve asla internete gönderilmez. Gelişmiş yerel yapay zeka (RAG & Akıllı Yönlendirici) sayesinde, günlükleriniz sizinle konuşan, sizi analiz eden ve size içgörüler sunan bir kişisel psikoloğa dönüşür.

---

## ✨ Özellikler

### 🧠 Tamamen Yerel ve Gizli Yapay Zeka
Tüm yapay zeka işlemleri (LLM çıkarımları ve vektör aramaları) tamamen kendi bilgisayarınızda (çevrimdışı) çalışır. Verileriniz asla dışarı çıkmaz. Uygulama, Qwen2.5-3B modelini indirerek minimum RAM (8GB) ve CPU gereksinimiyle bile akıcı bir sohbet deneyimi sunar. Embedding motorunun altındaki onnxruntime telemetrisi de kapatılmıştır (`ORT_DISABLE_TELEMETRY`).

### 🔍 Analiz Motoru (Smart Query Router)
Sadece anahtar kelime araması değil; **sayan, sıralayan ve ilişki kuran** bir analiz katmanı. Soru üç rotadan birine yönlendirilir:

| Rota | Ne zaman | Örnek |
|---|---|---|
| **ANALİZ** | Toplu sayım / sıralama / ilişki isteniyorsa | *"Bu hafta en çok neyi erteledim?"* |
| **ÖZET** | Bir dönemin anlatılması isteniyorsa | *"Bu ayı özetle"* |
| **RAG** | Belirli bir anı aranıyorsa | *"Spora ne zaman başlamıştım?"* |

**Analiz rotası nasıl çalışır — mimarinin özü:**

```
YAZMA ZAMANI                          SORU ZAMANI
─────────────                         ───────────
günlük kaydı                          soru
    ↓  (kayıt başına bir kez,             ↓
        şema zorlamalı JSON)          ├─ zaman aralığı  (core/time_range.py)
yapısal veri                          └─ niyet          (core/query_intent.py)
  • duygu puanı, tek cümlelik özet         ↓
  • yapılanlar / ertelenenler          SQL ile SAYIM   (core/analytics.py)
  • iyi gelenler / zorlayanlar             ↓
  • duygular, kişiler, mekânlar        OLGU KAĞIDI (~500 token)
    ↓                                      ↓
entry_insights + entry_facets          model yalnızca akıcı Türkçeye çevirir
```

**Model hiçbir aşamada sayı üretmez, sayıları okur.** Bunun iki sonucu var:

- **Uydurma sayı riski yok.** "Spor 9 gün ertelenmiş" bilgisi SQL'den gelir; model onu cümleye döker.
- **Prompt boyutu dönem uzunluğundan bağımsız.** Bir yıllık analiz de bir haftalık kadar yer kaplar. Eskiden bir aylık dönem bile bağlam penceresini aşıyor ve soru hata veriyordu.

**Anlaşılan sorular:**
- *"Bu ay genel ruh halim nasıldı"* → ortalama, en iyi/en kötü gün, haftalık seyir, önceki ayla karşılaştırma
- *"Bu hafta en çok neyi erteledim"* → gün sayısıyla sıralama
- *"En sürekli yaptığım şey neydi"* → kapsama yüzdesi ve en uzun kesintisiz seri
- *"Stresli olduğumda bana ne iyi geliyor"* → zor günler bulunur, o günlerde iyi gelenler sayılır (zaman ifadesi gerekmez)
- Tek soruda birden fazla analiz: *"Mart'ta en çok ertelediğim **ve** en sürekli yaptığım şey"*

**Sohbet hafızası:** Ardışık sorularda (*"Peki neden böyle hissetmişim?"*) dönem hatırlanır.

**Anlaşılan zaman ifadeleri:** *bugün, dün, bu/geçen hafta, bu/geçen ay, bu/geçen yıl* ve ay adları — Türkçe ekleriyle birlikte (*"bu ayı"*, *"Mart'ta"*, *"geçen haftayı"*). Ay adı başka bir kelimenin içinde geçtiğinde (*"çekimser"*, *"smart"*, *"kasımpatı"*) yanlış eşleşme yapmaz.

### 🏷️ Etiket Birleştirme
*"yürüyüş"*, *"yürüyüşe çıkmak"* ve *"yürüdüm"* aynı şey sayılır. Zaten kurulu olan embedding modeli benzer etiketleri tek bir kanonik etikette toplar; böylece "en çok yaptığım şey" sıralaması üçe bölünüp yanıltıcı olmaz. Ham yazım her zaman saklanır, karar geri alınabilir.

### 📊 Isı Haritası (Heatmap) ve Duygu Analizi
GitHub tarzı ısı haritası takvimi ile hangi günlerde ne kadar yoğun yazdığınızı görebilirsiniz. Arka planda çalışan AI asistan, yazdığınız her günlüğe bir **Duygu Puanı (Mood Score)** atar. Puan bir kez hesaplandıktan sonra yazınızı düzenleseniz de korunur ve yalnızca puanı olmayan günlükler yeniden analiz edilir.

### 🛟 Yazdıklarınız Kaybolmaz
Kaydetmeden başka bir güne geçmeye çalışırsanız uygulama sizi uyarır; yazınızı kaydetmeyi, atmayı veya o günde kalmayı seçebilirsiniz.

### 🎨 Modern ve Şık Arayüz
Minimalist, Dark Mode odaklı, "Glassmorphism" (buzlu cam efekti) tasarımı, pürüzsüz geçişleri ve mikro animasyonlarıyla uygulamanın içinde vakit geçirmek oldukça keyiflidir. "Düşünüyor..." veya "Geçen ayki günlüklerin taranıyor..." gibi interaktif yükleme bildirimleri bulunur.

---

## 🚀 Kurulum & Çalıştırma

İki yol var: **Docker** (en kolay, tek komut — [aşağıdaki bölüme](#-docker-ile-çalıştırma) bakın)
veya doğrudan Windows üzerine kurulum.

### Yerel Kurulum (Windows)

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

## 🐳 Docker ile Çalıştırma

Uygulama bir PyQt6 masaüstü programı olduğu için konteynerin içinde sanal bir ekran
(Xvfb) çalıştırılır ve arayüz **noVNC** üzerinden tarayıcıya sunulur. Böylece kendi makinenize
Python, C++ Build Tools veya Qt bağımlılıkları kurmadan tek komutla çalışır.

### 1. Başlatma
```powershell
docker compose up --build
```
İlk derleme birkaç dakika sürer — `llama-cpp-python` konteyner içinde kaynaktan
derlenir (hazır Linux wheel'leri musl/Alpine için üretildiğinden Debian tabanlı bu
imajda çalışmıyor). Sonraki derlemeler önbellekten anında gelir.

Derleme bitince tarayıcıdan şu adresi açın:

**http://localhost:6080**

Uygulama otomatik olarak bağlanır — arayüzü doğrudan tarayıcıda kullanabilirsiniz.
AI asistanı ilk kez açtığınızda ~1.9 GB'lık dil modeli `diary-models` volume'üne iner
ve bir daha inmez.

Kapatmak için:
```powershell
docker compose down
```

### 2. Verilerin Saklandığı Yerler

| Ne | Konteyner içi yol | Host tarafı |
|---|---|---|
| Günlük veritabanı (SQLite) | `/app/data/diary.db` | `./data/diary.db` |
| Vektör veritabanı (LanceDB) | `/app/data/lance_db` | `./data/lance_db` |
| Dil modeli (~1.9 GB GGUF) | `/app/models` | `diary-models` volume'ü |
| Embedding önbelleği (~220 MB) | `/app/cache` | `diary-cache` volume'ü |

Günlükleriniz `./data` klasöründe host üzerinde durur; imajı yeniden derleseniz de
silinmez. Model dosyaları adlandırılmış volume'lerde tutulur, yani modeli **bir kez**
indirirsiniz.

> Mevcut bir `diary.db` dosyanız varsa, konteyneri ilk kez başlatmadan önce
> `data/` klasörünün içine kopyalayın.

### 3. Yapılandırma

Uygulama artık yolları ortam değişkenlerinden okuyabiliyor (`settings.json`'a göre
önceliklidir). `docker-compose.yml` içinden değiştirilebilir:

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `DIARY_DB_PATH` | `/app/data/diary.db` | SQLite dosyasının yolu |
| `DIARY_VECTOR_DB_PATH` | `/app/data/lance_db` | LanceDB klasörü |
| `DIARY_MODEL_PATH` | `/app/models/qwen2.5-3b-instruct-q4_k_m.gguf` | GGUF model dosyası |
| `DIARY_MODEL_URL` | Qwen2.5-3B (HuggingFace) | İndirilecek modelin adresi |
| `SCREEN_GEOMETRY` | `1400x900x24` | Sanal ekran çözünürlüğü |
| `VNC_PASSWORD` | *(boş)* | Tanımlanırsa VNC parola ister |
| `START_MAXIMIZED` | `1` | Pencereyi açılışta ekrana yayar (`0` ile kapatılır) |

### 4. Güvenlik Notu
Portlar varsayılan olarak yalnızca `127.0.0.1` üzerinden yayınlanır, yani arayüze
sadece kendi bilgisayarınızdan erişilebilir. Konteyneri bir ağ üzerinden erişilebilir
hale getirecekseniz mutlaka `VNC_PASSWORD` tanımlayın.

### 5. Linux'ta doğrudan X11 (noVNC'siz)
Linux host kullanıyorsanız arayüzü tarayıcı yerine doğrudan masaüstünüzde açabilirsiniz.
Bu durumda konteynerin kendi sanal ekranına gerek yoktur, `entrypoint` atlanır:

```bash
xhost +local:docker
docker run --rm \
  -e DISPLAY="$DISPLAY" \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v "$PWD/data:/app/data" \
  --entrypoint python \
  personal-analyst-diary:latest main.py
```

### 6. Faydalı Komutlar
```powershell
docker compose logs -f          # uygulama günlüklerini izle
docker compose down             # konteyneri durdur (veriler kalır)
docker compose down -v          # volume'leri de sil (model yeniden inecek!)
docker compose build --no-cache # imajı sıfırdan derle
```

---

## 🧪 Testler

Proje `pytest` ile test edilir. Testler gerçek dil modelini (1.9 GB) veya
embedding modelini (220 MB) **indirmez**: sahte bir LLM ve sahte bir gömücü
kullanılır. Her test kendi geçici veritabanında çalışır, kişisel günlüğe
asla dokunmaz.

```powershell
# Docker ile (önerilen — hiçbir şey kurmanız gerekmez)
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm tests

# Belirli bir dosya veya test
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm tests tests/test_database.py -v
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm tests -k time_range

# Yerel kurulumda
pip install -r requirements-dev.txt
pytest
```

Arayüz testleri Qt'nin `offscreen` platformuyla çalışır, ekran gerektirmez.

| Test dosyası | Kapsam |
|---|---|
| `test_date_utils.py` | Türkçe tarih biçimlendirme, Türkçe büyük harf |
| `test_time_range.py` | Akıllı Yönlendirici'nin zaman çözümleyicisi |
| `test_settings.py` | Ayar önceliği: ortam değişkeni > dosya > varsayılan |
| `test_database.py` | CRUD, arama, istatistik, duygu puanı korunması |
| `test_chunker.py` | Metin parçalama |
| `test_vector_store.py` | LanceDB: ekleme, silme, indeks tarihleri, arama |
| `test_rag_engine.py` | Prompt kurulumu, sohbet geçmişi, yanıt akışı |
| `test_report_engine.py` | Zaman bazlı raporlama ve duygu istatistiği |
| `test_worker.py` | Rota seçimi (RAG / SQL), bağlam hafızası, indeksleme |
| `test_editor_panel.py` | Editör, kaydetme, kaydedilmemiş değişiklik takibi |
| `test_rating_widget.py` | Mutluluk puanlama widget'ı |
| `test_search_dialog.py` | Arama sonuçları diyaloğu ve Türkçe tarih gösterimi |
| `test_token_budget.py` | Prompt token bütçesi ve bağlam taşması koruması |
| `test_labels.py` | Etiket normalleştirme (Türkçe büyük/küçük harf) |
| `test_insight_extractor.py` | Yapısal çıkarım, bozuk model çıktısına dayanıklılık |
| `test_label_merger.py` | Benzer etiketlerin birleştirilmesi |
| `test_analytics.py` | Duygu eğilimi, sıklık, süreklilik, korelasyon |
| `test_query_intent.py` | Niyet yönlendirici (dört örnek soru dahil) |
| `test_analysis_engine.py` | Olgu kağıdı içeriği ve boyut bağımsızlığı |
| `test_main_window.py` | Gün değiştirirken veri kaybı koruması (entegrasyon) |

---

## 🛠️ Mimari Altyapı

- **Çekirdek (`core/`):** Qt ve model bağımlılığı olmayan saf Python katmanı — Türkçe tarih biçimlendirme (`date_utils`), zaman ifadesi çözümleyici (`time_range`), niyet yönlendirici (`query_intent`), analiz hesapları (`analytics`), etiket normalleştirme (`labels`) ve prompt token bütçesi (`token_budget`). Arayüz başlatmadan test edilebilir.
- **Analiz katmanı (`ai/`):** Kayıtlardan yapısal veri çıkarımı (`insight_extractor`, şema zorlamalı JSON), etiket birleştirme (`label_merger`) ve olgu kağıdı + anlatım (`analysis_engine`).
- **UI Framework:** PyQt6 (Özelleştirilmiş stiller ve asenkron Thread Worker'lar).
- **Yerel LLM:** `llama-cpp-python` (Qwen2.5-3B-Instruct Q4_K_M GGUF).
- **Vektör Veritabanı:** `LanceDB` (Semantik arama ve RAG için).
- **İlişkisel Veritabanı:** `SQLite` — günlükler (`entries`), yapısal çıkarımlar (`entry_insights`), sayılabilir etiketler (`entry_facets`) ve etiket eş anlamlıları (`label_aliases`). Tüm analiz sayımları burada yapılır.
- **Embedding Modeli:** `paraphrase-multilingual-MiniLM-L12-v2` (Cümleleri anlam vektörlerine çevirmek için).
- **Asenkron İşlemler:** Model indirme, vektör indeksleme, duygu analizi ve AI chat cevapları QThread üzerinden arayüzü dondurmadan çalıştırılır.
- **Konteyner:** Çok aşamalı (multi-stage) Docker imajı — Xvfb sanal ekranı + x11vnc + noVNC ile arayüz tarayıcıya taşınır; uygulama konteyner içinde root olmayan `app` kullanıcısıyla çalışır.

---

## 🔮 Gelecek Planları
- [x] RAG (Vektör Tabanlı) Anı Araması
- [x] Zaman Bazlı Analiz ve Smart Router
- [x] Otomatik Duygu Analizi ve Skorlama
- [ ] Rapor Ekranı üzerinden Duygu Puanı Grafikleri (Trend Çizgileri)
- [ ] Gelişmiş PDF / Dışa Aktarma (Export) Özellikleri

---

*Not: Uygulama içerisinde kullanılan yapay zeka modelleri 3 Milyar (3B) parametreli olduğu için Türkçe gramer sınırlarını zaman zaman zorlayabilmektedir, ancak prompt mühendisliğiyle ('Şimdiki Zaman Kullan' kuralı vb.) maksimum verimliliğe optimize edilmiştir.*
