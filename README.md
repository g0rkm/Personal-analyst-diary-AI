# Günlük Uygulaması

Bu proje, günlük tutmayı daha düzenli ve anlamlı hale getirmek amacıyla geliştirdiğim bir masaüstü uygulamasıdır. Temel hedefim, kullanıcıların günlük kayıtlarını güvenli bir şekilde saklayabilmesi ve zaman içinde bu kayıtlar üzerinden çeşitli analizler yapabilmesidir.

Uzun vadede uygulamaya yapay zeka desteği ekleyerek, sadece yazı saklayan bir günlük yerine geçmiş kayıtları yorumlayabilen ve kullanıcıya faydalı bilgiler sunabilen bir sistem oluşturmayı planlıyorum.

## Mevcut Özellikler

* **Yerel Veritabanı:** Tüm veriler SQLite kullanılarak bilgisayarda saklanır. İstenirse veritabanı dosyası OneDrive veya Google Drive gibi servislerle senkronize edilebilir.
* **Karanlık Tema ve Takvim Görünümü:** Günlük giriş yoğunluğunu gösterebilen, ısı haritası mantığında çalışan bir takvim ekranı bulunmaktadır.
* **Yazma Yardımcıları:** Yazmaya başlamakta zorlanan kullanıcılar için öneri kartları ve günlük mutluluk puanı sistemi eklenmiştir.
* **Arama Özelliği:** Eski kayıtlar içerisinde anahtar kelime araması yapılabilir.
* **AI Sohbet Bölümü:** Gelecekte eklenecek yapay zeka özellikleri için sohbet panelinin arayüzü hazırlanmıştır.

## Kurulum

Projeyi çalıştırmak için aşağıdaki komutlar yeterlidir:

```powershell
python -m pip install PyQt6
python main.py
```

## Planlanan Yapay Zeka Özellikleri

Yapay zeka entegrasyonu tamamlandığında uygulamaya aşağıdaki özelliklerin eklenmesi planlanmaktadır:

* **Geçmiş Kayıtlar Üzerinde Soru-Cevap:** Kullanıcı geçmiş günlükleri hakkında sorular sorabilecek ve sistem ilgili kayıtları inceleyerek cevap üretebilecektir.
* **Örüntü ve Alışkanlık Analizi:** Günlüklerde tekrar eden davranışlar, alışkanlıklar ve duygu değişimleri tespit edilmeye çalışılacaktır.
* **Duygu Analizi:** Günlük kayıtlarının genel duygu durumu analiz edilerek zaman içindeki değişimler takip edilebilecektir.
* **Haftalık ve Aylık Özetler:** Kullanıcının günlük yazma alışkanlıkları ve genel duygu eğilimleri hakkında özet raporlar oluşturulabilecektir.

Bu proje hâlen geliştirme aşamasındadır ve yeni özellikler eklenmeye devam etmektedir.
