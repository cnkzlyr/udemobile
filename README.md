# ⚖️ UdeMobile — Mobil UYAP & Word Dilekçe Editörü

[![Android](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?logo=android&logoColor=white)](https://android.com)
[![UYAP](https://img.shields.io/badge/Format-UYAP_UDF_v1.8-0D47A1.svg)](https://uyap.gov.tr)
[![Word](https://img.shields.io/badge/Format-MS_DOCX_OpenXML-2B579A.svg?logo=microsoft-word&logoColor=white)](https://microsoft.com)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**UdeMobile**, avukatlar, katipler ve hukukçular için geliştirilmiş; telefon ve tablette **Google Dokümanlar & Word konforunda** UYAP dilekçesi yazmayı, düzenlemeyi, okumayı ve imzalamayı sağlayan yeni nesil bir mobil hukuk editörüdür.

Artık telefonda UYAP belgelerini açmak için karmaşık X11 masaüstü pencereleriyle, donan fare imleçleriyle veya terminal komutlarıyla uğraşmanıza gerek yok. UdeMobile, `.udf` ve `.docx` dosyalarını yerel olarak ayrıştırır, ekranda resmi A4 sayfa düzeniyle canlı gösterir ve tek dokunuşla resmi UYAP formatında kaydeder.

---

## 🌟 Öne Çıkan Özellikler

### 1. 📱 Google Dokümanlar Stili Mobil A4 Çalışma Alanı
* **Görünüm Değiştirici (Kağıt / Mobil Mod):**
  * **📄 Kağıt Modu (A4):** Resmi dilekçe kenar boşlukları, gölgeli beyaz sayfa simülasyonu ve gerçek baskı önizlemesi.
  * **📱 Mobil Mod:** Küçük telefon ekranlarında tek elle rahat okuma ve yazma için kenarları dolduran esnek mobil düzen.
* **UYAP Tipografi Standardı:** Resmi adli yazışma standardı olan **Times New Roman 12 pt**, iki yana yaslı (justify) ve 1.45 satır aralığı.

### 2. ⚖️ Zengin Biçimlendirme & Hukuki Araç Çubuğu
* **Dilekçe Şablonları (Tek Tıkla Eklenir):**
  * *Dava Dilekçesi* (Mahkeme başlığı, taraflar, açıklamalar, hukuki sebepler, deliller, netice-i talep)
  * *Cevap Dilekçesi* (Esas no, cevaplar, itirazlar)
  * *Süre Uzatım Talebi* (HMK m. 127 uyarınca 2 haftalık ek süre talebi)
  * *Bilirkişi Raporuna İtiraz / Beyan Dilekçesi*
  * *İstinaf Başvuru Dilekçesi* (Bölge Adliye Mahkemesi'ne sunulmak üzere)
  * *İhtarname / Sözleşme Fesih Metni*
* **Yazı Tipi & Boyut Seçimi:** Times New Roman, Arial, Calibri, Georgia, Daktilo/Courier. `A-` ve `A+` butonlarıyla anında font boyutu kontrolü.
* **Metin Stilleri:** Kalın (**B**), İtalik (*I*), Altı Çizili (<u>U</u>), Üstü Çizili (~~S~~).
* **Renk & Fosforlu Vurgu:** Siyah, Koyu Mavi, Kırmızı ve Fosforlu Sarı/Yeşil metin vurgulama (ihtar ve dava notları için).
* **Paragraf Hizalama:** İki Yana Yasla (Justify), Ortala (Başlıklar), Sağa Yasla, Sola Yasla.
* **📊 Tablo Ekleme:** Dava alacak kalemleri, delil listeleri ve faiz hesaplamaları için tek dokunuşla tablo ekleme.
* **✍️ Güvenli E-İmza Alanı:** Belgenin sağına güncel tarihli, *"Davacı/Davalı Vekili Av. [Ad Soyad]"* ve *"5070 Sayılı Elektronik İmza Kanunu Uyarınca Güvenli E-İmzalıdır"* bloğu ekleme.
* **Listeler & Girintiler:** Numaralı liste (1, 2, 3), madde imleri (•), paragraf başı girintisi (Tab).

### 3. 🔄 DOCX <-> UDF Çift Yönlü Dönüştürücü
* **Word Dilekçesini UDF'ye Çevirme:** WhatsApp'tan veya bilgisayardan gelen `.docx` uzantılı bir Word dilekçesini açıp düzenleyebilir ve tek tıkla resmi **.udf** formatında kaydedebilirsiniz.
* **UDF Belgesini Word Olarak Kaydetme:** Açtığınız bir UDF belgesini tek tıkla standart **.docx** dosyası olarak dışa aktarabilirsiniz.

### 4. 📄 Resmi A4 PDF Çıktısı & Paylaşım
* **PDF Dışa Aktar:** Android sistem yazdırma servisi ile dilekçenizi saniyeler içinde A4 PDF formatında oluşturun ve kaydedin.
* **Doğrudan Paylaşım:** Oluşturulan dilekçeyi WhatsApp, UYAP Mobil, E-Posta veya Bulut depolamaya tek tıkla gönderin.

### 5. 🎯 Sistem Genelinde Varsayılan Uygulama
* **Samsung Dosyalarım, WhatsApp, TickTick, Telegram:** Herhangi bir `.udf` veya `.docx` dosyasına dokunulduğunda "Birlikte Aç" menüsünde listelenir. "Her Zaman" seçilerek telefonun kalıcı varsayılan belge yöneticisi yapılır.

### 6. 🖥️ Masaüstü UYAP (Termux:X11) Entegrasyonu
* Dilediğiniz an tek bir dokunuşla (`🖥️ X11` butonu) üzerinde çalıştığınız dilekçeyi arka plandaki Termux ortamına aktarabilir, Havelsan masaüstü editöründe açabilir ve USB CCID e-imza okuyucunuzla kart takıp imzalayabilirsiniz.

---

## 🚀 Sıfırdan Kurulum Rehberi

### Adım 1: APK Kurulumu
1. Bu depodaki [release/udemobile-v2.1.apk](release/udemobile-v2.1.apk) dosyasını telefonunuza indirin.
2. Dosyayı açıp **"Yükle"** onayına dokunun.

### Adım 2: İzinleri Ayarlama (Termux Entegrasyonu İçin)
1. Telefonunuzun **Ayarlar > Uygulamalar > UYAP Açıcı** sayfasına gidin.
2. **İzinler > Ek İzinler (veya Diğer İzinler)** menüsünü açın.
3. 👉 **"Termux ortamında komut çalıştırma" (Run commands in Termux environment)** seçeneğini **İzin Ver** olarak işaretleyin.
4. *(Termux kullanıyorsanız)* `~/.termux/termux.properties` dosyanızda `allow-external-apps = true` satırının aktif olduğundan emin olun.

### Adım 3: Varsayılan Uygulama Yapma
1. Dosyalarım uygulamasından herhangi bir `.udf` dosyasına dokunun.
2. Açılan pencerede **"UYAP Açıcı & Mobil Editör"** uygulamasını seçip **"Her Zaman"** (Always) butonuna basın.
3. Artık telefonunuzdaki tüm dilekçeler doğrudan bu mobil editörle açılacaktır!

---

## 📂 Dizin Yapısı

```text
udemobile/
├── android/                         # Android Mobil Uygulama Kaynak Kodları
│   ├── AndroidManifest.xml          # UDF/DOCX intent filtreleri ve yetkiler
│   ├── src/com/agy/uyapacici/
│   │   ├── MainActivity.java        # Karşılama, dosya köprüsü ve geçmiş paneli
│   │   ├── EditorActivity.java      # Google Dokümanlar tarzı mobil editör aktivitesi
│   │   ├── UdfEngine.java           # UYAP 1.8 XML <-> HTML çevirici ve UDF üretici
│   │   └── DocxEngine.java          # OpenXML Word <-> HTML çevirici ve DOCX üretici
│   ├── res/                         # Material kartlar, butonlar ve XML düzenleri
│   └── assets/editor/               # Mobil Editör Arayüzü
│       ├── editor.html              # HTML5 A4 çalışma alanı
│       ├── editor.css               # Kağıt / Mobil görünüm stilleri
│       └── editor.js                # Zengin metin motoru ve dilekçe şablonları
├── scripts/                         # Termux Entegrasyon Betikleri
│   └── uyap_baslat.sh               # Optimize edilmiş kiosk Termux:X11 başlatıcı
├── release/
│   └── udemobile-v2.1.apk           # İmzalı ve kullanıma hazır Android APK paketi
└── README.md                        # Kullanım kılavuzu ve proje dokümantasyonu
```

---

## ⚖️ Lisans & Telif Hakları

* Bu proje **Av. Can KIZILYAR** tarafından geliştirilmiştir.
* UYAP® Adalet Bakanlığı Bilgi İşlem Genel Müdürlüğü'nün tescilli markasıdır.
