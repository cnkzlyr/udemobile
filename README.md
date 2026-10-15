# ⚖️ UdeMobile — Mobil UYAP & Word Dilekçe Editörü

[![Android](https://img.shields.io/badge/Platform-Android_8.0+-3DDC84.svg?logo=android&logoColor=white)](https://android.com)
[![UYAP](https://img.shields.io/badge/Format-UYAP_UDF_v1.8-0D47A1.svg)](https://uyap.gov.tr)
[![Word](https://img.shields.io/badge/Format-MS_DOCX_OpenXML-2B579A.svg?logo=microsoft-word&logoColor=white)](https://microsoft.com)
[![Version](https://img.shields.io/badge/Version-v2.8-blue.svg)](release/udemobile-v2.8.apk)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**UdeMobile**, avukatlar, katipler ve hukukçular için geliştirilmiş; telefon ve tablette **Google Dokümanlar & Word konforunda** UYAP dilekçesi yazmayı, düzenlemeyi, okumayı, **elektronik imza doğrulamayı** ve **gerçek USB OTG token/kart ile imzalamayı** sağlayan yeni nesil bir mobil hukuk editörüdür.

Artık telefonda UYAP belgelerini açmak için karmaşık X11 masaüstü pencereleriyle, donan fare imleçleriyle veya terminal komutlarıyla uğraşmanıza gerek yok. UdeMobile, `.udf` ve `.docx` dosyalarını yerel olarak ayrıştırır, ekranda resmi A4 sayfa düzeniyle canlı gösterir, imzalarını kriptografik olarak doğrular ve tek dokunuşla resmi UYAP formatında kaydeder.

---

## 🌟 v2.8 ile Gelen Yeni Özellikler & Çözümler

### 🔍 1. Havelsan UYAP Uyumlu İmza Kontrolü & Doğrulama Motoru (Açıkken ve Listede)
* **Ana Ekran Dosya Listesinde Canlı Rozetler:** Açılan veya kaydedilen tüm UDF belgelerinin yanında imza durumu anında gösterilir:
  * `🟢 GEÇERLİ E-İMZA: Halil ÖZYOLCU (TÜRKTRUST)` (Bütünlüğü korunmuş geçerli imza)
  * `🔴 GEÇERSİZ İMZA (İçerik Değişmiş veya Hatalı)` (Bozulmuş veya özet uyuşmazlığı)
  * `⚪ İmzasız Belge` (İmza bulunmayan standart taslak)
* **Editör İçi İnteraktif İmza Banner'ı & "🔍 İmza Kontrolü" Butonu:** Belge açıkken tek tıkla imza raporunu açma ve canlı doğrulama.
* **Resmi UYAP Kontrolcü Raporu:**
  * `(+) İmza Matematiksel Doğrulama Kontrolcüsü`: Başarılı
  * `(+) İmzacı Sertifikası Kontrolcüsü`: Başarılı (Nitelikli Elektronik Sertifika - NES)
  * `(+) Sertifika Geçerlilik Süresi`: Başarılı (Geçerli Tarih Aralığında)
  * `(+) İçerik Özet Özelliği Kontrolcüsü`: İçerik özeti özelliğindeki değer hesaplanan değerle aynı. Kontrolcü sonucu başarılı.

### ⚡ 2. Gerçek USB Akıllı Kart İmzalama (Havelsan UYAP %100 Uyumlu)
* Havelsan UYAP Doküman Editörü v5.4.20 standardına uygun olarak, ZIP arşivi yerine doğrudan arşive yazılan `content.xml` dosyasının ham baytları SHA-256 ile imzalanır.
* Havelsan UYAP Editöründe açıldığında `Doküman üzerindeki imza geçerlidir!` onayı alınır; özet uyuşmazlığı hatası tamamen giderilmiştir.

---

## 🌟 Temel Yetenekler

### 1. 📏 Etkileşimli A4 Cetveli (Ruler - Word & UYAP Stili)
* **0 - 16 cm Hassas Milimetre Ölçeği:** A4 kağıt genişliğiyle birebir örtüşen yatay cetvel.
* **İlk Satır Girintisi İmi (▼):** Dokunarak veya sürükleyerek seçili paragrafın ilk satır girintisini (0.5 cm, 1.0 cm, 1.25 cm UYAP standardı) canlı ayarlama.
* **Sol / Asılı Girinti İmi (▲ + ▀):** Paragrafın sol kenarını ve asılı bendini ayarlama.
* **Sağ Kenar İmi (▲):** Paragrafın sağ marjini kontrol etme.
* **Otomatik Senkronizasyon:** İmleç hangi paragrafa gelirse cetvel imleri o paragrafın girintilerine anında konumlanır.

### 2. 📐 Seçili Paragraftan Önce / Sonra Boşluk & Detaylı Ayar Modali
* **Hedefli Paragraf Biçimlendirme:** Biçimlendirme tüm belgeyi bozmaz; doğrudan **seçili veya imlecin bulunduğu paragrafa** uygulanır.
* **Paragraftan Önceki Boşluk (Space Above):** 0 pt, 2 pt, 4 pt, 6 pt, 12 pt veya özel pt değeri (+/− butonları ile).
* **Paragraftan Sonraki Boşluk (Space Below):** 0 pt, 4 pt, 8 pt (Standart UYAP), 12 pt, 18 pt veya özel pt değeri.
* **Satır Aralığı (Line Spacing):** Tek (1.0), 1.15, UYAP Standart (1.35), 1.5, Çift (2.0).
* **Kapsam Seçimi:** Yapılan ayarları yalnızca geçerli paragrafa veya tüm belgeye uygulama seçeneği.
* **Canlı Önizleme:** Modal içerisindeki önizleme kutusunda paragrafın nasıl görüneceğini anlık takip etme.

### 3. 📑 Kalıcı Üstbilgi ve Altbilgi (Header & Footer)
* **Asla Kaybolmayan Yapı:** Sayfa başı ve sayfa sonu kalıcı olarak görüntülenir, işlem yapıldığında kaybolmaz.
* **Çift Yönlü UDF & DOCX Uyumluluğu:** Üstbilgi (Mahkeme adı, dosya no) ve altbilgi (iletişim, sayfa no) doğrudan UDF `<pageFormat>` ve DOCX yapısına kaydedilir, belge açıldığında geri yüklenir.
* **Hızlı Sayfa No Ekleme:** Tek tıkla altbilgiye tarih ve `Sayfa 1 / 1` formatında resmi numaralandırma.

### 4. 📱 Gerçek UYAP Mobil İmza (M-İmza) & ✍️ USB E-İmza + Çoklu İmza Desteği
* **Gerçek UYAP Mobil İmza Ağ Geçidi:** Adalet Bakanlığı UYAP Mobil İmza Web Servisi (`mimzaclient`) doğrudan entegre edilmiştir. Turkcell, Vodafone veya Türk Telekom operatörlerinden telefonunuza gelen onay bildirimindeki **Parfüm / Doğrulama Kodu** ekranda gösterilir, SIM kartınızdan PIN girildiğinde canlı imzalanır.
* **Birden Fazla İmza & Paraf (Çoklu İmza Koruması):** Belgede önceden atılmış imzalar varsa, yeni bir e-imza veya mobil imza atıldığında eski imzalar silinmez! TÜBİTAK UEKAE MA3 & CAdES-BES standardına uygun olarak yeni imzacının `SignerInfo` ve sertifikası mevcut `sign.sgn` arşivine eklenir. Doküman çift veya çok imzalı olarak eksiksiz saklanır.
* **Canlı İmza Doğrulama Motoru:** Hem ana dosya listesinde hem de editör içinde açılan dokümanın imzaları (imzacı adı, NES sertifika sağlayıcı, seri no, son geçerlilik tarihi) ve `content.xml` içerik bütünlüğü anlık doğrulanır. Çok imzalı belgelerde her imzacının kartı ayrı ayrı listelenir.
* **Token Desteği:** TÜRKTRUST, Kamu SM, AKİS, e-Tuğra akıllı kartları ve ACR39U vb. CCID kart okuyucuları.

### 5. 📱 Google Dokümanlar Stili Mobil A4 Çalışma Alanı
* **Görünüm Değiştirici (Kağıt / Mobil Mod):**
  * **📄 Kağıt Modu (A4):** Resmi dilekçe kenar boşlukları, gölgeli beyaz sayfa simülasyonu ve gerçek baskı önizlemesi.
  * **📱 Mobil Mod:** Küçük telefon ekranlarında tek elle rahat okuma ve yazma için kenarları dolduran esnek mobil düzen.
* **UYAP Tipografi Standardı:** Resmi adli yazışma standardı olan **Times New Roman 12 pt**, iki yana yaslı (justify) ve 1.35 satır aralığı.

### 2. ⚖️ Zengin Biçimlendirme & Hukuki Araç Çubuğu
* **Dilekçe Şablonları (Tek Tıkla Eklenir):**
  * *Dava Dilekçesi* (Mahkeme başlığı, taraflar, açıklamalar, hukuki sebepler, deliller, netice-i talep)
  * *Cevap Dilekçesi* (Esas no, cevaplar, itirazlar)
  * *Süre Uzatım Talebi* (HMK m. 127 uyarınca 2 haftalık ek süre talebi)
  * *Bilirkişi Raporuna İtiraz / Beyan Dilekçesi*
  * *İstinaf Başvuru Dilekçesi* (Bölge Adliye Mahkemesi'ne sunulmak üzere)
  * *İhtarname / Sözleşme Fesih Metni*
* **Yazı Tipi & Boyut Seçimi:** Times New Roman, Arial, Calibri, Georgia, Daktilo/Courier. `A-` ve `A+` butonlarıyla font boyutu kontrolü.
* **Metin Stilleri:** Kalın (**B**), İtalik (*I*), Altı Çizili (<u>U</u>), Üstü Çizili (~~S~~).
* **Renk & Fosforlu Vurgu:** Siyah, Koyu Mavi, Kırmızı ve Fosforlu Sarı/Yeşil metin vurgulama (ihtar ve dava notları için).
* **Paragraf Hizalama:** İki Yana Yasla (Justify), Ortala (Başlıklar), Sağa Yasla, Sola Yasla.
* **Paragraf Boşlukları & Satır Aralığı (UYAP Standardı):** Paragraf öncesi / sonrası boşluk (0 pt, 4 pt, 8 pt, 12 pt) ve satır aralığı (1.0, 1.15, 1.35, 1.5, 2.0).
* **Gelişmiş Numaralandırma & Maddeleme:**
  * Standart (1., 2., 3.)
  * **Hukuk Dava Maddeleri (1.1, 1.2, 1.3)**
  * Roma Rakamları (I., II., III.)
  * Harfli Bentler (a, b, c)
  * Madde İmleri (• Daire, ■ Kare, ➢ Ok)
* **📑 Üstbilgi & Altbilgi (Header / Footer):** Mahkeme adı, dosya no ve iletişim bilgilerini sayfa başı/sonu olarak tanımlayabilme.
* **🔢 Sayfa Numarası:** Altbilgiye otomatik sayfa numaralandırması ekleme.
* **🖼️ Resim & Delil Fotoğrafı Ekleme:** Galeriden veya kameradan dilekçeye delil fotoğrafı, vekâletname pulu, dekont veya keşif krokisi ekleme.
* **📊 Tablo Ekleme:** Dava alacak kalemleri, delil listeleri ve faiz hesaplamaları için tek dokunuşla tablo ekleme.

### 3. 📱 Mobil İmza & ✍️ USB E-İmza Entegrasyonu
* **📱 Mobil İmza (M-İmza):**
  * Turkcell, Vodafone ve Türk Telekom mobil imza akışı.
  * TCKN ve GSM numarasıyla 5070 Sayılı Elektronik İmza Kanunu uyumlu güvenli m-imza kaşesi, zaman damgası ve doğrulama kodu.
* **✍️ USB Akıllı Kart E-İmza:**
  * Type-C OTG üzerinden takılan TÜRKTRUST, e-Tuğra, AKİS, Kamu SM tokenları ile doğrudan mobil üzerinden veya Termux köprüsüyle imzalama.

### 4. 🔄 DOCX <-> UDF Çift Yönlü Dönüştürücü
* **Word Dilekçesini UDF'ye Çevirme:** WhatsApp'tan veya bilgisayardan gelen `.docx` uzantılı bir Word dilekçesini açıp düzenleyebilir ve tek tıkla resmi **.udf** formatında kaydedebilirsiniz.
* **UDF Belgesini Word Olarak Kaydetme:** Açtığınız bir UDF belgesini tek tıkla standart **.docx** dosyası olarak dışa aktarabilirsiniz.

### 5. 🔐 Uygulama İçi Arka Plan E-İmza & Akıllı Kart (X11 Ekranına Geçmeden)
* **Kalıcı Mobil İmza:** Operatör (Turkcell, Vodafone, TT), GSM No ve TCKN bilgileri kalıcı olarak hatırlanır; her seferinde tekrar yazma zahmeti biter.
* **Uygulama İçi E-İmza (Headless):** X11 masaüstü ekranına geçiş yapmadan doğrudan uygulama içi pencereden akıllı kart/token (AKİS, TÜRKTRUST, e-Tuğra, vb.) sertifikası görüntülenir, PIN girilerek 5070 Sayılı Kanuna uygun CAdES-BES imzası arka planda üretilir.
* **Bağımsız (Standalone) Çalışma:** Termux veya Termux:X11 kurulu olmayan cihazlarda da harici hiçbir gereksinime ihtiyaç duymadan resmi 5070 S.K. doğrulama kaşesi ve standart UDF üretimi kusursuz çalışır.

### 6. 📄 Resmi A4 PDF Çıktısı & Paylaşım
* **PDF Dışa Aktar:** Android sistem yazdırma servisi ile dilekçenizi saniyeler içinde A4 PDF formatında oluşturun ve kaydedin.
* **Doğrudan Paylaşım:** Oluşturulan dilekçeyi WhatsApp, UYAP Mobil, E-Posta veya Bulut depolamaya tek tıkla gönderin.

### 7. 🎯 Sistem Genelinde Varsayılan Uygulama
* **Samsung Dosyalarım, WhatsApp, TickTick, Telegram:** Herhangi bir `.udf` veya `.docx` dosyasına dokunulduğunda "Birlikte Aç" menüsünde listelenir. "Her Zaman" seçilerek telefonun kalıcı varsayılan belge yöneticisi yapılır.

### 8. 🖥️ Masaüstü UYAP (Termux:X11) Entegrasyonu
* İstenildiğinde tek dokunuşla dilekçeyi arka plandaki Termux ortamına aktarabilir ve Havelsan masaüstü editöründe açabilirsiniz.

---

## 🚀 Sıfırdan Kurulum Rehberi

### Adım 1: APK Kurulumu
1. Bu depodaki [release/udemobile-v2.7.apk](release/udemobile-v2.7.apk) (veya [release/udemobile-latest.apk](release/udemobile-latest.apk)) dosyasını telefonunuza indirin.
2. Dosyayı açıp **"Yükle"** onayına dokunun.

### Adım 2: İzinleri Ayarlama (Termux Entegrasyonu İçin)
1. Telefonunuzun **Ayarlar > Uygulamalar > UYAP Açıcı** sayfasına gidin.
2. **İzinler > Ek İzinler (veya Diğer İzinler)** menüsünü açın.
3. 👉 **"Termux ortamında komut çalıştırma" (Run commands in Termux environment)** seçeneğini **İzin Ver** olarak işaretleyin.

### Adım 3: Varsayılan Uygulama Yapma
1. Dosyalarım uygulamasından herhangi bir `.udf` dosyasına dokunun.
2. Açılan pencerede **"UYAP Açıcı & Mobil Editör"** uygulamasını seçip **"Her Zaman"** (Always) butonuna basın.
3. Artık telefonunuzdaki tüm dilekçeler doğrudan bu mobil editörle açılacaktır!

---

## 🔐 Gerçek Donanımsal E-İmza (USB OTG & CCID) Mimarisi

UdeMobile v2.7, **kesinlikle simülasyon veya sahte kart görseli kullanmaz**:
* **Fiziksel Kart Algılama:** Telefonunuza Type-C OTG adaptörüyle bir akıllı kart okuyucu veya USB Token (AKİS, Kamu SM, ArkSigner, TÜRKTRUST, E-Tuğra vb.) takılmadığı sürece arayüz `🔴 KART TAKILI DEĞİL` uyarısı verir ve PIN girişi ile imzalama butonu kilitli tutulur.
* **Canlı Durum Sorgulama:** Kart penceresi açıldığında sistem arka plandaki `127.0.0.1:5975` Adalet Bakanlığı E-İmza REST servisini periyodik olarak sorgular. Kart takıldığı an otomatik olarak yeşile döner (`🟢 KART AKTİF`), okuyucu adını ve çipteki geçerli sertifikaları (NES) listeler.
* **5070 Sayılı Kanun Uyumlu CAdES-BES İmzalama:** Kullanıcı PIN kodunu girdiğinde imza verisi doğrudan kartın mikroçipi üzerinde (TÜBİTAK UEKAE MA3 CAdES motoru) hesaplanır. Hatalı PIN girildiğinde kart çipinden dönen gerçek hata ekrana yansıtılır.
* **Orijinal `sign.sgn` Çıktısı:** Başarılı imzalama sonrası dönen ham DER CMS ikilisi doğrudan `.udf` zip arşivinin içine `sign.sgn` olarak gömülür. Bu sayede dosya resmi masaüstü UYAP Editöründe açıldığında "İmzalar Geçerli" olarak doğrulanır.

---

## 📂 Dizin Yapısı

```text
udemobile/
├── android/                         # Android Mobil Uygulama Kaynak Kodları
│   ├── AndroidManifest.xml          # UDF & DOCX intent filtreleri ve yetkiler
│   ├── src/com/agy/uyapacici/
│   │   ├── MainActivity.java        # Karşılama, dosya köprüsü ve geçmiş paneli
│   │   ├── EditorActivity.java      # Google Dokümanlar tarzı mobil editör & E-imza köprüsü
│   │   ├── UdfEngine.java           # UYAP 1.8 XML <-> HTML çevirici ve UDF/sign.sgn üretici
│   │   └── DocxEngine.java          # OpenXML Word <-> HTML çevirici ve DOCX üretici
│   ├── res/                         # Material kartlar, butonlar ve XML düzenleri
│   └── assets/editor/               # Mobil Editör Arayüzü (HTML5, CSS3, JS)
│       ├── editor.html              # HTML5 A4 çalışma alanı, canlı kart ve imza kartları
│       ├── editor.css               # Kağıt / Mobil görünüm ve modal stilleri
│       └── editor.js                # Zengin metin, m-imza, donanımsal e-imza, cetvel ve şablonlar
├── scripts/                         # Termux Entegrasyon Betikleri (uyap_baslat.sh, headless imza)
├── release/
│   ├── udemobile-v2.7.apk           # Donanımsal E-İmza destekli en güncel APK paketi
│   └── udemobile-latest.apk         # En güncel sürüme işaret eden doğrudan indirme paketi
└── README.md                        # Kullanım kılavuzu ve proje dokümantasyonu
```

---

## ⚖️ Lisans & Telif Hakları

* Bu proje **Av. Can KIZILYAR** tarafından geliştirilmiştir.
* UYAP® Adalet Bakanlığı Bilgi İşlem Genel Müdürlüğü'nün tescilli markasıdır.
