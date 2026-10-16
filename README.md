# ⚖️ CanEditor (UdeMobile) — Çapraz Platform UYAP & Word Editörü

[![Sürüm](https://img.shields.io/badge/Sürüm-v3.4.5-blue.svg)](https://github.com/cnkzlyr/udemobile/releases/tag/v3.4.5)
[![Platformlar](https://img.shields.io/badge/Platformlar-Android%20%7C%20Windows%20%7C%20macOS%20%7C%20Linux%20%7C%20Web-success.svg)](https://github.com/cnkzlyr/udemobile/releases)
[![UYAP](https://img.shields.io/badge/Format-UYAP_UDF_v1.8-0D47A1.svg)](https://uyap.gov.tr)
[![Word](https://img.shields.io/badge/Format-MS_DOCX_OpenXML-2B579A.svg?logo=microsoft-word&logoColor=white)](https://microsoft.com)
[![5070 E-İmza](https://img.shields.io/badge/5070_S.K.-E--İmza_%26_Mobil_İmza-darkgreen.svg)](https://www.mevzuat.gov.tr/mevzuat?MevzuatNo=5070&MevzuatTur=1&MevzuatTertip=5)
[![Lisans](https://img.shields.io/badge/Lisans-MIT-green.svg)](LICENSE)

**CanEditor (UdeMobile)**; avukatlar, hakimler, savcılar, katipler ve tüm hukuk profesyonelleri için geliştirilmiş; mobil cihazlarda, masaüstünde (Windows, macOS, Linux) ve modern web tarayıcılarında **Google Dokümanlar & Word konforunda** UYAP dilekçesi hazırlamayı, düzenlemeyi, okumayı, **elektronik imza doğrulamayı** ve **5070 Sayılı Kanuna uygun gerçek Mobil İmza / USB Akıllı Kart ile mühürlemeyi** sağlayan yeni nesil, tam kapsamlı ve bağımsız bir hukuk editörüdür.

---

## 🚀 Hızlı İndirme (v3.4.5)

| Platform | Paket Dosyası | Açıklama |
| :--- | :--- | :--- |
| **Android (Telefon & Tablet)** | [**CanEditor-v3.4.5.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.4.5/CanEditor-v3.4.5.apk) | Güncel mobil uygulama paketi |
| **Android (Her Zaman En Son)** | [**CanEditor-latest.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.4.5/CanEditor-latest.apk) | Kalıcı son sürüm bağlantısı |
| **Taşınabilir Web & Masaüstü** | [**CanEditor-Portable-Web-GUI-v3.4.5.zip**](https://github.com/cnkzlyr/udemobile/releases/download/v3.4.5/CanEditor-Portable-Web-GUI-v3.4.5.zip) | Kurulumsuz; zipten çıkarıp `index.html` açarak tüm işletim sistemlerinde doğrudan çalışır |
| **Windows / macOS / Linux** | [**GitHub Releases Sayfası**](https://github.com/cnkzlyr/udemobile/releases/tag/v3.4.5) | GitHub Actions CI ile derlenen yerel ikili (.msi, .exe, .dmg, .AppImage, .deb, .rpm) paketleri |

---

## 🌟 v3.4.5 ile Gelen Önemli Geliştirmeler

### 🎯 1. Milimetrik Sekme & Durak Hizalaması (Multi-Stop TabSet)
- **Kusursuz İki Nokta (Colon) ve Sicil Hizası:** Çoklu durak yerleri (`TabSet="146.0:0:0,241.0:0:0"`) artık virgülle ayrılarak eksiksiz ayrıştırılır. `DOSYA NO`, `DURUŞMA TARİHİ`, `CELSE NO`, `HAKİM`, `CUMHURİYET SAVCISI`, `KATİP` satırlarındaki tüm iki noktalar (`:`) masaüstü UYAP editörüyle birebir aynı şekilde `5.15 cm` (`146.0 pt`) hizasında kilitlenir. Sicil numaraları ise `8.50 cm` (`241.0 pt`) sütununda tam dikey hizada yer alır; zig-zag oluşması tamamen engellenmiştir.

### 🏷️ 2. Akıllı Üstbilgi Motoru (`<header startPage="2">`)
- Resmi UYAP belgelerinde 1. sayfada üstbilgi gösterilmez. 2. sayfadan itibaren her sayfanın başında mahkeme adı ve dosya/duruşma bilgisi (`T.C. ... MAHKEMESİ / Dosya No: ...`) iki yana yaslı zarif bir üstbilgi bandı olarak otomatik eklenir.

### 🛡️ 3. Resmi UYAP Doğrulama Metni & Dinamik QR / Barkod
- `content.xml` içindeki `<webID>` ve `documentproperties.xml` içindeki `uyapdogrulamakodu` otomatik okunarak her sayfanın altbilgisine resmi doğrulama metni (`UYAP Bilişim Sistemindeki bu dokümana http://vatandas.uyap.gov.tr adresinden [kod] ile erişebilirsiniz.`) ve sağ köşede `{PAGE_NUM}/{TOTAL_PAGES}` ile dinamik SVG QR kod yerleştirilir.

### 📄 4. Hassas Sayfalama & Satır Kayması Koruması
- Resmi UYAP `pageFormat` kenar boşlukları (`1.5 cm` kenarlar, `0.5 cm` alt) ve `1.2` satır aralığı standardı uygulanarak sayfa sonu satır kayması giderilmiş, resmi 18 sayfa düzeni birebir yakalanmıştır.

---

## 🏛️ Temel Yetenekler & Özellikler

### 1. 📄 Çift Yönlü Belge Dönüştürme (UDF ⟷ DOCX)
- **Word Dilekçesini UDF Yapma:** Bilgisayardan veya mesajlaşma uygulamalarından gelen `.docx` dosyalarını açıp düzenleyebilir ve tek tıkla resmi **.udf** formatında kaydedebilirsiniz.
- **UDF'yi Word Olarak Dışa Aktarma:** Açtığınız bir UDF belgesini tek tıkla standart **.docx** formatına dönüştürebilirsiniz.
- **Resmi UYAP Tipografisi:** Times New Roman 12 pt, iki yana yaslı (justify) ve 1.35 satır aralığı standardı varsayılan olarak uygulanır.

### 2. 📏 Etkileşimli A4 Cetveli (Ruler) & Sayfa Boşlukları
- **0 - 16 cm Milimetre Ölçeği:** A4 kağıt genişliğiyle birebir uyumlu cetvel.
- **İlk Satır Girintisi İmi (▼):** Paragrafın ilk satır girintisini (0.5 cm, 1.0 cm, 1.25 cm UYAP standardı) sürükleyerek ayarlama.
- **Sol ve Asılı Girinti İmi (▲ + ▀):** Paragrafın sol kenarını ve asılı bendini kontrol etme.
- **Sağ Kenar İmi (▲):** Paragrafın sağ marjinini ayarlama.

### 3. 📑 Kalıcı Üstbilgi ve Altbilgi (Header & Footer)
- Mahkeme adı, dosya no ve iletişim bilgileri sayfa başında ve sonunda kalıcı olarak görüntülenir.
- Otomatik tarih ve `Sayfa 1 / 1` biçiminde resmi sayfa numaralandırması ekleme.

### 4. ✍️ Donanımsal E-İmza (USB OTG CCID) & Çoklu İmza
- **Fiziksel Kart Desteği:** Type-C OTG adaptörüyle takılan TÜRKTRUST, Kamu SM, AKİS, E-Tuğra akıllı kartları ve ACR39U vb. CCID kart okuyucuları.
- **Çoklu İmza (Multi-Sign) Koruması:** Belgede önceden atılmış imzalar varsa, yeni bir e-imza veya mobil imza atıldığında eski imzalar silinmez; CAdES-BES standardına uygun olarak yeni imzacının sertifikası mevcut `sign.sgn` arşivine eklenir.
- **Canlı İmza Doğrulama Motoru:** Açılan dokümanın imzaları (imzacı adı, NES sertifika sağlayıcı, seri no, son geçerlilik tarihi) ve `content.xml` içerik bütünlüğü anlık doğrulanır.

### 5. ⚖️ Hukuki Araç Çubuğu & Şablonlar
- **Tek Tıkla Dilekçe Şablonları:** Dava Dilekçesi, Cevap Dilekçesi, Süre Uzatım Talebi (HMK m. 127), Bilirkişi Raporuna İtiraz, İstinaf Başvuru Dilekçesi, İhtarname.
- **Hukuki Madde Numaralandırma:** Hukuk Dava Maddeleri (1.1, 1.2, 1.3), Roma Rakamları (I., II., III.), Harfli Bentler (a, b, c) ve Madde İmleri.
- **Fosforlu Vurgulama & Renkler:** Sarı ve yeşil metin vurgulama, koyu mavi / kırmızı başlık ve ihtar notları.

### 6. 📄 A4 PDF Çıktısı & Sistem Entegrasyonu
- Android yazdırma servisi ile tek tıkla resmi A4 PDF çıktısı alma.
- Samsung Dosyalarım, WhatsApp, Telegram ve E-Posta uygulamalarında `.udf` ve `.docx` dosyaları için varsayılan görüntüleyici olarak çalışabilme.

---

## 🔒 Gizlilik, Güvenlik & Kişisel Veri Politikası (KVKK Uyumlu)

> [!IMPORTANT]
> **CanEditor (UdeMobile) hiçbir kişisel veriyi, kimlik numarasını (TCKN), telefon numarasını veya belge içeriğini üçüncü taraf sunucularda TOPLAMAZ ve SAKLAMAZ.**

1. **Yerel İşleme (Local-First):** Tüm UDF ve DOCX ayrıştırma, biçimlendirme ve dönüştürme işlemleri doğrudan cihazınızın belleğinde (RAM) yerel olarak gerçekleştirilir.
2. **Kriptografik Bütünlük:** Mobil İmza ve Elektronik İmza süreçlerinde kimlik doğrulama yalnızca kullanıcının talebiyle, doğrudan resmi Adalet Bakanlığı UYAP ağ geçitleri ve yetkili Elektronik Sertifika Hizmet Sağlayıcıları (ESHS / TÜBİTAK UEKAE) üzerinden yürütülür.
3. **Sıfır Telemetri:** Uygulama içinde reklam, kullanıcı takip kodu veya harici analiz kütüphanesi bulunmaz.

---

## 🛠️ Kurulum & Kullanım Rehberi

### Android Kurulumu
1. [Releases sayfasından](https://github.com/cnkzlyr/udemobile/releases/tag/v3.4.4) `CanEditor-v3.4.4.apk` dosyasını indirin.
2. İndirilen APK dosyasına dokunup **"Yükle"** onayını verin.
3. Dosyalarım uygulamasından herhangi bir `.udf` veya `.docx` dosyasına tıklayıp **"CanEditor"** uygulamasını seçerek **"Her Zaman"** butonuna basın.

### Masaüstü & Web Kurulumu
1. [CanEditor-Portable-Web-GUI-v3.4.4.zip](https://github.com/cnkzlyr/udemobile/releases/download/v3.4.4/CanEditor-Portable-Web-GUI-v3.4.4.zip) dosyasını indirin.
2. Arşivi bir klasöre çıkartın ve `index.html` dosyasına çift tıklayarak Chrome, Edge, Safari veya Firefox tarayıcınızda kurulum gerektirmeden hemen kullanın.
3. Yerel masaüstü uygulaması olarak çalıştırmak için işletim sisteminize uygun (.msi, .dmg, .AppImage) paketi [Releases sayfasından](https://github.com/cnkzlyr/udemobile/releases/tag/v3.4.4) indirebilirsiniz.

---

## 📂 Proje Dizin Yapısı

```text
udemobile/
├── android/                         # Android Mobil Uygulama Kaynak Kodları
│   ├── AndroidManifest.xml          # UDF/DOCX intent filtreleri ve izinler
│   ├── src/com/agy/uyapacici/
│   │   ├── MainActivity.java        # Karşılama, dosya açma köprüsü ve liste
│   │   ├── EditorActivity.java      # A4 editör etkinliği ve imza köprüsü
│   │   ├── UyapMobileSignClient.java# Çift katmanlı M-İmza & UYAP SOAP motoru
│   │   ├── UdfEngine.java           # UYAP XML ayrıştırma, üretme ve imza doğrulama
│   │   └── DocxEngine.java          # OpenXML Word dönüştürücü
│   ├── res/                         # Android XML arayüz kaynakları
│   └── assets/editor/               # Mobil editör web varlıkları (HTML/CSS/JS)
├── frontend/                        # Çapraz Platform Web & Masaüstü Arayüzü
│   ├── public/                      # Taşınabilir JS, CSS ve köprü kütüphaneleri
│   │   ├── desktop_bridge.js        # Masaüstü ve tarayıcı dosya/imza köprüsü
│   │   ├── editor.js                # Zengin editör, cetvel, sekme ve m-imza mantığı
│   │   └── updater.js               # Dahili GitHub güncelleme denetleyicisi
│   └── index.html                   # Ana düzenleyici arayüzü
├── src-tauri/                       # Masaüstü Native Çekirdeği (Rust / Tauri v2)
│   ├── Cargo.toml                   # Rust bağımlılıkları ve sürüm yapılandırması
│   ├── tauri.conf.json              # Windows, macOS, Linux pencere ve paket ayarları
│   └── src/                         # Rust Tauri komutları ve dosya motoru
├── scripts/                         # Headless Havelsan UYAP ve Termux Betikleri
│   ├── UdeMobileServer.java         # 0.0.0.0:5976 Havelsan UYAP mikroservisi
│   └── udemobile_baslat.sh          # Setsid ve wake-lock destekli arka plan başlatıcı
├── release/                         # Derlenmiş hazır APK ve taşınabilir paketler
└── README.md                        # Güncel proje dokümantasyonu
```

---

## ⚖️ Lisans & Telif Hakları

- Bu proje **Av. Can KIZILYAR** tarafından geliştirilmiştir.
- UYAP®, T.C. Adalet Bakanlığı Bilgi İşlem Genel Müdürlüğü'nün tescilli markasıdır.
- Açık kaynak kodlu ve MIT lisansı altındadır.
