# Günlük Uygulaması

Selamlar! 👋 Bu proje, temelinde kendi verinizin kontrolünü tamamen size bırakan, **yapay zeka destekli ve kişisel analiz yapabilen bir günlük uygulaması** geliştirmek amacıyla yola çıktı. 

Amacımız sadece bir şeyler yazıp geçeceğiniz sıradan bir uygulama değil; aksine geçmiş kayıtlarınızı analiz edip ruh halinizi anlayan ve size anlamlı içgörüler sunabilen akıllı bir asistan yaratmak.

## Şu Ana Kadar Neler Yaptık?

Projenin temel iskeletini ve kullanıcı deneyimini büyük ölçüde oturttuk. Şu an için hazır olan özellikler şunlar:

- **Yerel ve Güvenli Veritabanı:** Verileriniz tamamen kendi bilgisayarınızda (SQLite) kalıyor. İsterseniz dosyanızı OneDrive veya Google Drive gibi bir bulut klasörüne yönlendirip cihazlar arası kolayca senkronize edebilirsiniz.
- **Modern Arayüz:** Göz yormayan karanlık tema (dark mode) ve özel olarak tasarlanmış, günleri doluluk oranına göre renklendiren ısı haritası tarzı bir takvim geliştirdik.
- **Pratik Editör ve Öneriler:** Boş günlerde size ne yazacağınız konusunda ilham veren şablon kartları ve günlük 1-10 arası mutluluk puanı verebileceğiniz özel bir sistem kurduk.
- **Hızlı Arama:** Geçmiş notlarınız arasında kolayca kelime araması yapabiliyorsunuz.
- **AI Sohbet Altyapısı:** Yapay zeka asistanıyla konuşacağımız sağ panelin arayüzü ve altyapısı tamamen hazır.

## Nasıl Çalıştırılır?

Projeyi denemek isterseniz aşağıdaki komutları terminalde çalıştırmanız yeterli:

```powershell
python -m pip install PyQt6
python main.py
```

## Yapay Zeka (AI) Bize Neler Sunacak?

Projenin asıl can alıcı ve heyecan verici kısmı olan gerçek yapay zeka (LLM) entegrasyonu tamamlandığında, uygulamanın sıradan bir günlük olmaktan çıkıp kişisel bir asistana dönüşmesini planlıyoruz. AI'ın yapacağı temel şeyler şunlar olacak:

- **Geçmişinizle Sohbet Etme (RAG):** Günlüğünüze "Geçen ay en çok neyi ertelemişim?" veya "Hangi günlerde daha motive hissetmişim?" gibi sorular sorabileceksiniz ve AI geçmiş kayıtlarınızı tarayıp size kendi kelimelerinizle cevap verecek.
- **Gizli Bağlantıları (Korelasyon) Keşfetme:** AI, yazdıklarınız arasındaki örüntüleri yakalayacak. Örneğin, *"Fark ettin mi? Spordan kaytardığın günlerde stresin artmış ama erken uyandığın günlerde çok daha mutlusun."* gibi harika içgörüler sunacak.
- **Otomatik Duygu Analizi:** Siz günlüğünüzü yazdıktan sonra AI, metninizin genel hissiyatını analiz edecek ve o günkü duygu durumunuza otomatik bir skor verecek. Böylece takvime baktığınızda hangi günlerde modunuzun düştüğünü veya yükseldiğini renklerden direkt anlayabileceksiniz.
- **Haftalık ve Aylık Psikolojik Özetler:** *"Bu ay 18 gün kayıt girdin, ortalama mutluluğun 6.5. En çok sporu aksatmışsın ama arkadaşlarınla vakit geçirmek sana çok iyi gelmiş."* tarzında, kendi kendinizi daha iyi tanımanızı sağlayacak tatlı ve anlamlı raporlar oluşturacak. 🚀
