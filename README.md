# Günlük — Kişisel Günlük Uygulaması: Proje Raporu

---

## Neden Bu Projeye Başladık?

Fikrin özü şu sorgudan doğdu: **"Telefon uygulamaları verilerimi bulutta saklıyor, ama ben kendi verimin sahibi olmak istiyorum."**

Piyasadaki dijital günlük uygulamalarının büyük çoğunluğu;
- Verilerini kendi sunucularında tutuyor (bulut bağımlılığı)
- Abonelik ücreti istiyor
- İnternet bağlantısı gerektiriyor
- Gizlilik konusunda soru işaretleri barındırıyor

Bu projeyle hedef net: **Tamamen yerel çalışan, verisi kullanıcının kendi bilgisayarında saklanan, açık ve genişletilebilir bir masaüstü günlük uygulaması.** Bunun ötesinde, ilerleyen aşamada yapay zekâ ile kişisel bir "içgörü motoru" oluşturmak — yani uygulama sadece yazmak için değil, geçmişe bakıp anlamak için de kullanılabilecek.

---

## Projenin Temel Felsefesi

Üç temel prensip üzerine inşa edildi:

1. **Veri Egemenliği:** Tüm veriler yerel bir SQLite dosyasında (`diary.db`) saklanır. Kullanıcı bu dosyayı OneDrive, Google Drive veya başka bir klasöre yönlendirerek iki bilgisayar arasında dosya tabanlı senkronizasyon yapabilir. Hiçbir sunucuya bağımlılık yok.

2. **Genişletilebilirlik:** Kod baştan yapay zekâ entegrasyonu düşünülerek yazıldı. Veritabanında `mood_score` (AI'ın dolduracağı) ve `happiness_score` (kullanıcının elle verdiği) sütunları şimdiden hazır.

3. **Modüler Mimari:** Her şey tek bir dosyaya sıkıştırılmadı. Her bileşenin kendi dosyası var, bakımı ve geliştirilmesi kolay.

---

## Kullanılan Teknoloji Yığını

| Teknoloji | Neden Seçildi |
|---|---|
| **Python 3.11** | Hızlı geliştirme, geniş kütüphane ekosistemi |
| **PyQt6** | Gerçek masaüstü uygulama, native görünüm, güçlü widget sistemi |
| **SQLite** | Sunucu gerektirmeyen, tek dosya veritabanı — taşınabilir ve güvenilir |
| **QSS (Qt Style Sheet)** | CSS benzeri söz dizimi ile karanlık tema ve modern görünüm |

---

## Proje Dosya Yapısı

```
diaryApp/
│
├── main.py                   # Uygulamanın giriş noktası
├── database.py               # Tüm SQLite işlemleri
├── settings.py               # Yapılandırma okuma/yazma
├── settings.json             # Veritabanı yolu ayarı
├── requirements.txt          # Bağımlılık listesi (PyQt6)
│
└── ui/                       # Tüm arayüz bileşenleri
    ├── __init__.py
    ├── styles.py             # Renk paleti ve QSS tema
    ├── calendar_widget.py    # Özelleştirilmiş takvim
    ├── editor_panel.py       # Metin yazma/okuma paneli
    ├── rating_widget.py      # 1-10 mutluluk puanlama
    ├── suggestion_widget.py  # Yatay kayan öneri kartları
    ├── ai_chat_panel.py      # AI sohbet paneli (placeholder)
    ├── full_calendar_view.py # Tam ekran takvim sekmesi
    ├── main_window.py        # Ana pencere ve koordinasyon
    └── search_dialog.py      # Arama sonuçları diyaloğu
```

---

## Tamamlanan Özellikler — Detaylı Anlatım

### 1. Dinamik Veritabanı Sistemi

Uygulama açıldığında ilk olarak `settings.json` dosyasını okur:

```json
{ "db_path": "diary.db" }
```

Bu yol göreli olabilir (uygulama klasöründe `diary.db`) ya da mutlak olabilir (`C:\Users\...\OneDrive\diary.db`). `settings.py` modülü bu yolu çözümler. Veritabanı yoksa otomatik oluşturulur. Bu yapı sayesinde kullanıcı isterse `settings.json`'ı düzenleyerek veritabanını bulut senkronizasyon klasörüne taşıyabilir — ve uygulama hiçbir ayar ekranı gerektirmeden o dosyayla çalışmaya devam eder.

---

### 2. Veritabanı Şeması

`entries` tablosu şu sütunları içeriyor:

| Sütun | Tür | Açıklama |
|---|---|---|
| `date` | TEXT (PK) | `YYYY-MM-DD` formatında birincil anahtar |
| `content` | TEXT | Günlük metni |
| `mood_score` | INTEGER | AI'ın hesaplayacağı duygu skoru (−10 ile +10 arası, şimdilik 0) |
| `happiness_score` | INTEGER | Kullanıcının verdiği mutluluk puanı (0-10 arası) |

Veritabanı migration sistemi de var: Eski `diary.db` dosyalarına `happiness_score` sütunu otomatik eklenir, mevcut veriler kaybolmaz. UPSERT mantığıyla aynı tarihe birden fazla yazılırsa kayıt güncellenir, yeni oluşturulmaz.

---

### 3. Karanlık Gradient Tasarım Sistemi

Tek renkli düz arka plan yerine derin bir gradient kullanıldı:

- **Ana arka plan:** `#0D0D1A` → `#1A1A2E` (koyu lacivert-siyah geçişi)
- **Widget yüzeyleri:** `rgba(255,255,255,0.04)` — glassmorphism efekti
- **Vurgu rengi:** `#E84545` (kırmızı) — dolu günler, butonlar, odak sınırları
- **Tüm köşeler:** 12–20px border-radius ile yumuşatılmış

`ui/styles.py` içinde tüm renkler sabit olarak tanımlandı. Tema değiştirmek istense yalnızca bu dosya düzenleniyor.

---

### 4. Özelleştirilmiş Takvim (Isı Haritası)

`QCalendarWidget` bileşeninin `paintCell()` metodu tamamen yeniden yazıldı. Standart Qt'nin varsayılan çizimi tamamen devre dışı bırakıldı; her hücre sıfırdan şu kurallara göre çiziliyor:

| Gün Durumu | Görünüm |
|---|---|
| **Boş gün** | Soluk beyaz kenarlıklı yuvarlak daire |
| **Dolu gün** | Radial gradient kırmızı dolgulu daire, beyaz rakam |
| **Bugün (boş)** | Kesik çizgili kırmızı kenarlık + alt kısmında küçük kırmızı nokta |
| **Seçili gün** | Parlak kırmızı kenarlık veya beyaz kenarlık (dolu ise) |
| **Farklı ay** | Çok soluk, neredeyse görünmez |
| **Hafta sonu** | Hafif kırmızımsı metin rengi |

Rakamlar her zaman dairenin **geometrik merkezine** hizalanır (`circle_rect.toRect()` ile). Veritabanındaki dolu tarihlerin listesi her kayıt işleminden sonra takvime iletilir, takvim `updateCells()` çağrısıyla tüm hücreleri yeniden çizer.

---

### 5. İki Sekme Sistemi

Üst başlık çubuğunda iki sekme bulunuyor:

**Yazı Sekmesi:** Sol takvim + orta editör + sağ AI paneli  
**Takvim Sekmesi:** Büyük boy tam ekran takvim + sağda bilgi/önizleme paneli

Tam ekran takvimde bir güne **çift tıklanınca** otomatik olarak Yazı sekmesine geçilir ve o günün kaydı editöre yüklenir. Sağdaki bilgi panelinde seçili günün önizlemesi, mutluluk skoru ve "Bu Güne Git" butonu görünür.

---

### 6. Açılır-Kapanır Sol Sidebar

Sol takvim paneli `Ctrl+B` veya üstteki toggle butonuyla gizlenip gösterilebilir. Kritik tasarım kararı: **Toggle butonu, sidebar içinde değil, her zaman görünür ayrı bir şeritte bulunuyor.** Bu sayede sidebar tamamen kapansa dahi buton kaybolmuyor — yeniden açmak her zaman mümkün.

---

### 7. Editör Paneli

Yazı ekranı dört ana bölümden oluşuyor:

1. **Tarih başlığı** — Seçili günün Türkçe adı (örn. "CUMA, 30 MAYIS 2026")
2. **Mutluluk puanlama widget'ı** — 1'den 10'a kadar yuvarlak butonlar
3. **Öneri kartları şeridi** — Boş günlerde gösterilir, dolu günlerde gizlenir
4. **Metin editörü** — Serbestçe yazma alanı + alt kısımda kelime/karakter sayacı

`DiaryTextEdit` adlı özel bir `QTextEdit` alt sınıfı oluşturuldu. `keyPressEvent` override edilerek `Ctrl+Arrow` (kelime kelime gezinme) ve `Ctrl+Shift+Arrow` (kelime kelime seçim) tuş kombinasyonlarının üst penceredeki klavye kısayolları tarafından yutulması engellendi.

---

### 8. Mutluluk Puanlama Sistemi (1-10)

Her günün yazısının üstünde bağımsız bir puanlama alanı var:

- 1'den 10'a kadar yuvarlak butonlar yatay sıralanmış
- Seçilen puan kırmızı gradient dolgulu hale gelir
- Puanın sağında ruh hali etiketi belirir (örn. "Harika (8/10)")
- Etiket rengi puana göre değişir: ≥7 yeşil, ≥4 sarı, <4 kırmızı
- Sıfırlama butonu her zaman görünür
- Puan veritabanına `happiness_score` sütununa kaydedilir
- Kayıt yeniden açıldığında puan doğru şekilde yüklenir

---

### 9. Öneri Kartları Sistemi

Kullanıcı boş bir gün seçtiğinde metinlerin doğrudan yazı formatında gelmesi yerine görsel **öneri kartları** gösteriliyor. Yatay kaydırılabilir 7 kart mevcut:

| Kart | Şablon Sorusu | Renk |
|---|---|---|
| Hissiyat | "Bugün ne hissettim:" | Mavi |
| Günün Özeti | "Ne yaptım:" | Sarı |
| Ertelemeler | "Neyi erteledim:" | Kırmızı |
| Iyi Gelenler | "Ne iyi geldi:" | Yeşil |
| Minnet | "Bugün minnettar olduğum şeyler:" | Mor |
| Öğrendiklerim | "Bugün öğrendiğim bir şey:" | Cyan |
| Yarın | "Yarın yapmak istediğim:" | Turuncu |

Karta tıklanınca o sorunun şablonu editöre eklenir. "Hepsini ekle" butonu tüm soruları birden ekler. Mevcut kayıt yüklendiğinde kartlar otomatik gizlenir.

---

### 10. Kelime Bazlı Arama

Üst çubukta arama alanı var. Yazılan kelime veritabanında `LIKE '%kelime%'` sorgusuyla aranır. Sonuçlar bir diyalog penceresinde listelenir:

- Her satırda tarih + içeriğin ilk 80 karakteri görünür
- Bir sonuca **çift tıklanınca** diyalog kapanır, uygulama o tarihe gider
- Sonuç yoksa bilgilendirici mesaj gösterilir

---

### 11. AI Chat Paneli (Altyapı Hazır)

Sağ kenarda açılır-kapanır bir AI sohbet paneli bulunuyor. Şu an gerçek bir AI bağlantısı yok, ancak **tüm mimari kuruldu:**

- `message_sent` PyQt sinyali — AI motoruna mesaj iletmek için
- `_add_bubble()` metodu — Hem kullanıcı hem AI mesajlarını görsel balonlarda göstermek için
- Örnek soru önerileri listelenmiş
- Placeholder mesajlar döndürülüyor

Gerçek AI entegrasyonu yapılacağında yalnızca `_send_message()` metodu güncellenerek bir LLM API'sine (OpenAI, Ollama, vb.) bağlanacak. Tüm UI ve iletişim altyapısı hazır.

---

## Planlanan Ama Henüz Yapılmayan Özellikler

Bu özellikler baştan tasarlanmış, veritabanı altyapısı hazır, kod mimarisi bekliyor:

### AI Özellikleri (Gelecek Aşama)

1. **Geçmişle Sohbet (RAG):**  
   "Geçen ay en çok neyi erteledim?" gibi sorular sorulduğunda AI, SQLite'daki `content` sütununu tarayıp özet yanıt üretecek.

2. **Şablonlar Arası Korelasyon:**  
   "Fark ettin mi? 'Proje ödevini ertelediğin' günlerin hepsinde 'stresli' hissetmişsin, ama 'yürüyüş yaptığını' yazdığın günlerde ruh halin çok daha iyi." türünde içgörüler.

3. **Otomatik Duygu Analizi:**  
   Kayıt yapılınca AI metni arka planda okuyup `mood_score` sütununu dolduracak. Takvim renk tonu bu skora göre değişecek (bordo = çok stresli, parlak kırmızı = çok mutlu).

4. **Haftalık/Aylık Rapor:**  
   "Bu ay 18 gün yazdın. En çok ertelediğin şey spor. Ortalama mutluluk puanın 6.2."

---

## Nasıl Çalıştırılır?

```powershell
cd c:\Projects\diaryApp
python -m pip install PyQt6
python main.py
```

### OneDrive/Google Drive Senkronizasyonu

`settings.json` dosyası düzenlenerek veritabanı bulut klasörüne yönlendirilebilir:

```json
{
    "db_path": "C:\\Users\\KullaniciAdi\\OneDrive\\diary.db"
}
```

İki farklı bilgisayarda aynı OneDrive klasörü ayarlandığında, her iki cihazda da aynı günlük verisine erişilir.
