# UYAP Editör Modern ⚡

Resmi **UYAP Doküman & Şablon Editörü** için geliştirilmiş çoklu platform (Linux, Windows, macOS, Android), 120Hz/240Hz akıcı kaydırma (smooth scroll), modern tema desteği (FlatLaf), sorunsuz `.udf` / `.usf` dosya ilişkilendirmesi ve tam e-imza (AKİS / Arkİmza / TBB Token) entegrasyonuna sahip modernizasyon paketi.

---

## 🚀 Öne Çıkan Özellikler

* **📄 Çift Tıklama ile Doğrudan Dosya Açma (.udf & .usf):**
  * Masaüstü veya dosya yöneticisinde (GNOME Nautilus, KDE Dolphin, Windows Explorer, macOS Finder) `.udf` ve `.usf` dosyalarına çift tıklandığında belgenin boş sayfa yerine eksiksiz olarak açılması.
  * `file://` URI çözümleme, URL-decode (`%20` ve Türkçe karakterler) ve otomatik mutlak yol dönüşümü.
  * Çoklu dosya seçimi desteği (birden fazla dosya seçilip Enter'a basıldığında tüm pencerelerin açılması).
  * `.udf` açılırken Doküman Editörü, `.usf` açılırken Şablon Editörü modunun otomatik devreye girmesi.
* **🎯 120Hz & 240Hz Akıcı Kaydırma (Word/Edge Stili):**
  * Ekran yenileme hızına duyarlı momentum ve üstel sönümleme algoritması.
  * Klavyeden tek tuşla açma/kapatma (**`F9`**).
* **🖊️ Tam E-İmza & Akıllı Kart Desteği:**
  * **Arkİmza** (ArkSigner / NES ECC) ve **TBB Kırmızı Token** (ACS ACR39U / TÜRKTRUST) otomatik sürücü ve slot algılama.
* **🎨 Modern Arayüz Temaları (FlatLaf Entegre):**
  * Modern Açık (Flat Light) ve Modern Koyu (Flat Dark) tema seçenekleri.
  * Subpixel LCD font antialiasing ile keskin yazı tipi kalitesi.
* **🔤 Kusursuz PDF Dışa Aktarımı & Yazı Tipi Eşleme (Times New Roman Düzeltmesi):**
  * UYAP Editörü'nün Linux ve modern sistemlerde standart yazı tipi dizinlerini taramaması sebebiyle Times New Roman ile yazılan metinlerin PDF'e aktarılırken Helvetica (sans-serif) olarak bozulması sorununun kökten çözümü.
  * Sistemdeki tüm yazı tipi dizinlerini (`/usr/share/fonts`, `/usr/local/share/fonts`, `~/.local/share/fonts` vb.) otomatik tarayan akıllı `PdfFontFixer` motoru.
  * Times New Roman ve diğer fontların PDF çıktısında orijinal biçimiyle (Regular, Bold, Italic) birebir korunması.
* **📂 Kararlı ve Güvenilir Özgün Dosya Seçici:**
  * UYAP'ın tüm dosya türü filtrelerini (`*.udf`, `*.usf`, `*.pdf`, `*.*`) ve belge önizlemelerini destekleyen eksiksiz özgün dosya seçici.
* **🌐 Çoklu Platform Desteği:**
  * **Linux:** Fedora, Ubuntu, Debian, Pardus, Arch Linux (MIME tanımları ve HiDPI ikon seti dahil).
  * **Windows:** Windows 10 & 11 (PowerShell tek tıkla kurulum, sessiz VBS başlatıcı, `.udf`/`.usf` kayıt defteri eşleme).
  * **macOS:** Apple Silicon (M1/M2/M3/M4) ve Intel işlemcili Mac'ler (Doküman ve Şablon başlatıcıları).
  * **Android:** Termux & Termux:X11 + Fluxbox üzerinden tablet ve telefonlarda tam masaüstü UYAP deneyimi.
  * **Android (bağımsız, YENİ):** Termux / X11 / Termux:API **olmadan**, Java 14.0.2 ile dokunmatik UYAP Editör — CanEditor içindeki
    "UYAP Editör" simgesi; .udf/.usf her uygulamadan doğrudan açılır. Ayrıntılar: [`platforms/android-uygulama`](platforms/android-uygulama/README.md)

---

## 🆕 v2.2.0

* **Java 14.0.2 paketlerin içinde** (Linux, Windows, macOS): resmi OpenJDK 14.0.2, jlink ile küçültülmüş; ayrıca indirmeye gerek yok.
* **Windows yazı tipleri Linux ve macOS'ta:** Times New Roman, Arial, Courier New, Georgia, Verdana, Trebuchet, Comic Sans,
  Impact, Andale Mono, Arial Black, Webdings. Microsoft'un lisansı gereği **orijinal Core Fonts kurulum dosyaları (.exe)**
  değiştirilmeden pakete konur; `install.sh` bunları kurulumda yalnızca sizin bilgisayarınıza açar (Linux: cabextract / bsdtar / 7z,
  macOS: yerleşik tar). Belge ve PDF çıktısı Windows'takiyle aynı yazı tipiyle görünür.
* **E-imza:** Windows'ta adında Türkçe karakter olan okuyucular (ArkSigner: "Microsoft Usbccid Akıllı Kart Okuyucusu (WUDF)")
  JDK'nın PC/SC katmanında açılamıyordu → `uyap-pcsc-agent.jar` (Unicode PC/SC, JNA). AKİS kartlar editörün **APDU kipiyle**
  sürücüsüz imzalanır (Araçlar menüsü); Linux'ta `pcscd` + `ccid` gerekir (`drivers/setup-eimza.sh`).
* **Düzeltmeler:** ajan Java 14 uyumlu derlenir (v2.1.0 jar'ı Java 17 sınıf sürümüyleydi ve Java 14'te yüklenmiyordu);
  yayın paketlerinden kurulum (`bin/` klasörü olmadan) Linux ve Windows'ta çalışır; macOS kurulumu resmi editör dosyalarını da yerleştirir.
* **Lisans:** ESYA lisans denetimine dokunan sınıflar (`core/src/tr/gov/tubitak/**`) artık derlenmez ve dağıtılmaz.
* **Android (Termux/X11'siz):** bağımsız "UYAP Editör" uygulaması — [`platforms/android-uygulama`](platforms/android-uygulama/README.md).

## 📦 Kurulum ve Kullanım

### 1. Linux (Fedora, Ubuntu, Debian, Pardus, Arch)
Terminali açın ve tek satırda kurulumu gerçekleştirin:
```bash
git clone https://github.com/cnkzlyr/uyap-editor-modern.git
cd uyap-editor-modern/platforms/linux
chmod +x install.sh
./install.sh
```
Kurulum sonrasında uygulama menünüzden **UYAP Doküman Editörü Modern** veya **UYAP Şablon Editörü Modern**'i açabilir, herhangi bir `.udf` ya da `.usf` dosyasına çift tıklayabilir veya terminalden şu komutları kullanabilirsiniz:
* Doküman Editörü: `uyap-dokuman [dosya.udf]`
* Şablon Editörü: `uyap-sablon [dosya.usf]`

### 2. Windows 10 & 11 (x64 / AMD64 & ARM64)

#### Seçenek A: Tek Tıkla Setup (.exe) Kurulumu (Önerilen)
Releases sayfasından **`UYAP-Editor-Modern-Setup.exe`** dosyasını indirin ve kurun:
* **Tam Bağımsız (Self-Contained):** OpenJDK 14.0.2 ve resmi UYAP kütüphaneleri kurulum paketinin içine gömülüdür.
* **Yerel .exe Başlatıcılar:** Konsol penceresi açılmaksızın doğrudan çalışan yüksek performanslı modern başlatıcılar (`UYAP Dokuman Editoru.exe` ve `UYAP Sablon Editoru.exe`).
* **Otomatik Dosya İlişkilendirme:** `.udf` ve `.usf` uzantıları ikonlarıyla birlikte sisteme kaydedilir.

#### Seçenek B: PowerShell Otomatik Kurulum
PowerShell'i açın ve çalıştırın:
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
.\platforms\windows\install.ps1
```

*(Geliştiriciler için kendi Setup .exe paketini derlemek: `.\platforms\windows\build-setup.ps1`)*

### 3. macOS (Apple Silicon & Intel)
Terminalden çalıştırın:
```bash
cd platforms/macos
chmod +x install.sh
./install.sh
```

### 4. Android (Tablet & Telefon)
Android tabletlerde masaüstü UYAP Editör'ü çalıştırmak için:
1. **F-Droid**'den **Termux** ve **Termux:X11** uygulamalarını indirin.
2. Termux'a şu komutu yapıştırın:
   ```bash
   curl -sL https://raw.githubusercontent.com/cnkzlyr/uyap-editor-modern/main/platforms/android/termux-install.sh | bash
   ```
3. Kurulum bitince `uyap` yazarak tam editörü kullanın.

---

## 📝 Sürüm Notları (Changelog)

### v2.1.0 (2026-11-03)
* **⚡ Başlatıcı ve Symlink Yolu Düzeltmesi:**
  * `uyap-dokuman` ve `uyap-sablon` sembolik bağ (symlink) üzerinden çalıştırıldığında `BASH_SOURCE` yolunun `~/.local/bin` kalması ve `uyap-modernizer.jar` dosyasını bulamayıp uygulamanın açılmaması sorunu giderildi.
  * Kanonik dizin çözümleme (`readlink -f` / `dirname`) ve otomatik çoklu dizin tarama mantığı eklendi.
* **📂 Çift Tıklama Boş Sayfa Sorunu Giderildi:**
  * Dosya yöneticilerinde `.udf` ve `.usf` belgelerine çift tıklandığında editörün boş sayfa ile açılmasına sebep olan argüman iletim sorunu kökten çözüldü.
  * `file://` URI şemaları, URL encoding (`%20`, Türkçe karakter kodlamaları) ve bağıl yollar otomatik olarak sistem dosya yoluna dönüştürülüyor.
  * Çoklu dosya açma (birden fazla dosya seçilip açıldığında her biri için ayrı pencere oluşturulması) desteği eklendi.
* **🗂️ Eksiksiz MIME ve İkon Entegrasyonu:**
  * `udf.xml` Shared-MIME veritabanı tanımı Linux paketine dahil edildi (`.udf`, `.UDF`, `.usf`, `.USF`).
  * 16x16'dan 256x256'ya kadar tüm HiDPI belge ve şablon ikonları yerleştirildi.
  * Masaüstü kısayollarında `Categories` ve `StartupNotify` standartlaştırıldı.
* **🖼️ Dock İkonu, Başlık ve Canlı Önizleme Düzeltmesi:**
  * `-javaagent` kullanımı sebebiyle pencere sınıfının (`WM_CLASS`) `sun-instrument-InstrumentationImpl` olarak belirlenmesi, dock'ta mavi dişli (fallback) ikonu çıkması ve fare üzerine gelince yanlış isim yazması sorunu çözüldü.
  * Java AWT `XToolkit.awtAppClassName` ve pencere eşi (`setWMClass`) dinamik olarak `uyap-dokuman` ve `uyap-sablon` olarak ayarlandı; `StartupWMClass` ile tam uyum sağlandı.
  * `JFrame` pencerelerine çoklu boyutlu (16x16, 32x32, 48x48, 128x128, 256x256) ikonlar gömülerek GNOME Shell / Dash-to-Dock ve KDE görev çubuğunda canlı pencere önizlemeleri sağlandı.
* **🖥️ Windows, macOS ve Android İyileştirmeleri:**
  * Windows `dokuman.bat` ve `sablon.bat` içindeki `BASE_DIR` dizin tespiti ve tırnaklı dosya argümanı çözümlemesi güncellendi.
  * macOS için hem Doküman hem Şablon başlatıcıları ve Gatekeeper temizliği yapılandırıldı.
  * Android Termux başlatıcısına argüman çözümleme ve şablon/doküman algılama eklendi.

---

## 🛠️ Derleme (Geliştiriciler İçin)

Modernizer ajanını yeniden derlemek için:
```bash
chmod +x tools/build-agent.sh
./tools/build-agent.sh
```
Derlenen `uyap-modernizer.jar` dosyası `dist/` klasörüne oluşturulur.

---

## 🤖 Otomatik GitHub Sürüm Dağıtımı (CI/CD)

Yeni bir sürüm yayınlamak için depoya etiket (tag) göndermeniz yeterlidir:
```bash
git tag v2.1.0
git push origin v2.1.0
```
GitHub Actions iş akışı (`release.yml`) otomatik olarak devreye girerek Linux, Windows ve macOS için tüm kurulum paketlerini derler ve GitHub Releases sayfasına ekler.

---

## 📄 Lisans
Bu proje [Apache License 2.0](LICENSE) ile lisanslanmıştır. UYAP resmi kütüphanelerinin tüm hakları T.C. Adalet Bakanlığı'na aittir.
