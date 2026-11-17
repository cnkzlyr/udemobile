# NAPS2 & UYAP Thunar Araçları (Linux & Termux XFCE)

[![Platform: Linux / Termux](https://img.shields.io/badge/Platform-Linux%20%7C%20Termux-blue.svg)](https://github.com/cnkzlyr/naps-uyap-thunar-tools)
[![Python: 3.8+](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg)](https://python.org)
[![Java: OpenJDK 11-21](https://img.shields.io/badge/Java-OpenJDK%2011--21-orange.svg)](https://openjdk.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Linux XFCE (Thunar) ve Android Termux X11 masaüstü ortamları için geliştirilmiş; **NAPS2 tarama/A4 mizanpaj yöntemleriyle** tüm görsel, PDF ve çok sayfalı belgeleri A4 kağıt standartlarında PDF'e dönüştüren/birleştiren ve **resmi UYAP Doküman Editörü motorunu** kullanarak UDF belgelerini birebir **PDF, DOCX ve ODT** formatlarına çeviren sağ tık araç seti.

---

## 🚀 Özellikler

### 1. NAPS2 Yöntemleriyle A4 PDF Dönüştürme ve Birleştirme
* **Geniş Format Desteği:** `TIF`, `TIFF` (çok sayfalı), `JPG`, `JPEG`, `PNG`, `BMP`, `WEBP`, `PDF` ve `UDF`.
* **Otomatik Sayfa Yönlendirme (Auto-Orientation):** Yatay görseller otomatik olarak **Yatay A4**, dikey belgeler ise **Dikey A4** olarak ayarlanır.
* **Oran Korumalı Sığdırma (Aspect Ratio Preserved):** Belgeler asla esnetilmez veya basıklaştırılmaz; sayfa ortalanarak 5 mm yazıcı güvenli kenar payı bırakılır.
* **Sağ Tık: "Tümünü PDF'ye Dönüştür (A4)":** Çoklu veya tekli seçilen her belgeyi ayrı ayrı standart A4 PDF'e çevirir.
* **Sağ Tık: "Tümünü Tek PDF'de Birleştir (A4)":** Seçilen farklı formattaki tüm sayfaları sırasıyla tek bir A4 PDF dosyasında birleştirir.

### 2. UYAP Doküman Editörü Resmi Motoru ile UDF Dönüştürme
UYAP Doküman Editörünün kendi orijinal JAR kütüphaneleri (`editor_lib.jar`, `jai_hvl.jar`, `jdom.jar`) kullanılarak:
* **Sağ Tık: "PDF'ye Çevir (UYAP)":** `tr.com.havelsan.uyap.system.editor.b.b` vektör sınıfı ile editördeki "PDF Olarak Kaydet" seçeneğinin birebir aynısı, pikselsiz, aranabilir vektör PDF üretir.
* **Sağ Tık: "ODT'ye Çevir (UYAP)":** `tr.com.havelsan.uyap.system.editor.b.a.f` sınıfı ve OdfToolkit ile birebir OpenDocument formatında ODT üretir.
* **Sağ Tık: "DOCX'e Çevir (UYAP)":** UYAP'ın ürettiği ODT belgesini LibreOffice Writer motoru üzerinden hiçbir biçimlendirme bozulmadan Word (`.docx`) formatına dönüştürür.
* **Headless Çalışma:** Ekran açık olsun veya olmasın, arka planda hızlı ve sessiz çalışır. Masaüstü bildirimi (`notify-send`) ile anlık bilgi verir.

### 3. NAPS2 (Not Another PDF Scanner 2) Entegrasyonu
* Termux X11 ortamında NAPS2 GUI tarayıcı uygulaması başlatıcı ve masaüstü menü entegrasyonu hazır haldedir.

---

## 📂 Dizin Yapısı

```
naps-uyap-thunar-tools/
├── bin/
│   ├── a4-pdf-tools           # A4 dönüştürme ve birleştirme CLI aracı
│   ├── uyap-convert           # UDF -> PDF / DOCX / ODT dönüştürücü CLI aracı
│   └── naps2                  # NAPS2 başlatıcı wrapper
├── python/
│   └── a4_pdf_engine.py       # Pillow + ReportLab + PyPDF A4 motoru
├── java/
│   ├── UyapVectorExporter.java # UYAP JAR'larını çağıran Java köprüsü
│   └── uyap-exporter.jar      # Derlenmiş Java paketi
├── desktop/
│   ├── naps2.desktop          # XFCE Whisker / Uygulama Menüsü kısayolu
│   ├── uca_template.xml       # Thunar sağ tık XML şablonu
│   └── icons/                 # NAPS2 ve araç simgeleri
├── docs/
│   ├── UDF_STRUCTURE_AND_ENGINE.md   # UDF belge yapısı ve JAR analizi
│   └── NAPS2_AND_A4_PDF_METHODS.md   # NAPS2 A4 mizanpaj ilkeleri
├── install.sh                 # Tek tıkla otomatik kurulum scripti
└── uninstall.sh               # Kaldırma scripti
```

---

## 🛠️ Kurulum

### Gereksinimler
* **Java:** OpenJDK 11, 17 veya 21
* **Python:** Python 3.8+ (`pillow`, `reportlab`, `pypdf`)
* **Ofis:** LibreOffice (`soffice` - DOCX dönüşümü için)
* **UYAP Kütüphaneleri:** `~/jars` klasörünüzde UYAP editörünün jar dosyaları (`editor_lib.jar`, `jai_hvl.jar`, `jdom.jar` vb.)

### Tek Tıkla Kurulum
```bash
git clone https://github.com/cnkzlyr/naps-uyap-thunar-tools.git
cd naps-uyap-thunar-tools
chmod +x install.sh
./install.sh
```

Kurulum scripti:
1. Gerekli Python kütüphanelerini kurar.
2. Java dışa aktarım köprüsünü derler.
3. Komut satırı araçlarını `~/.local/bin` dizinine bağlar.
4. Thunar sağ tık menüsünü (`~/.config/Thunar/uca.xml`) günceller.
5. Thunar servisini yenileyerek seçenekleri anında aktif eder.

---

## 💻 Komut Satırından Kullanım (CLI)

Sağ tık menüsünün yanı sıra terminalden de doğrudan kullanabilirsiniz:

### UDF Dönüştürme:
```bash
# UDF -> PDF (Birebir Vektörel)
uyap-convert --pdf dava_dilekcesi.udf

# UDF -> DOCX (Word Belgesi)
uyap-convert --docx durusma_zapti.udf

# UDF -> ODT (OpenDocument)
uyap-convert --odt karar.udf

# Çoklu Dosya Dönüştürme
uyap-convert --pdf *.udf
```

### A4 PDF Dönüştürme ve Birleştirme:
```bash
# Tekil veya çoklu dosyaları A4 PDF'e çevirme
a4-pdf-tools --convert belge1.jpg tutanak.tif mahkeme.udf

# Farklı formattaki tüm dosyaları tek bir A4 PDF'de birleştirme
a4-pdf-tools --merge fotograf.jpg sayfa1.png coklu_tutanak.tiff ek.pdf belge.udf
# -> Klasörde "Birlestirilmis_Belge_YYYYAAGG_SSDDSS.pdf" üretilir.
```

### NAPS2 Tarayıcıyı Başlatma:
```bash
naps2
```

---

## 📖 Teknik Dokümantasyon
* **[UDF Yapısı ve JAR Bytecode Analizi](docs/UDF_STRUCTURE_AND_ENGINE.md):** ZIP yapısı, XML şemaları, `tr.com.havelsan.uyap.system.editor.b.b` sınıfı ve Java 21 modül parametreleri.
* **[NAPS2 Mizanpaj ve A4 Yöntemleri](docs/NAPS2_AND_A4_PDF_METHODS.md):** Sayfa ölçekleme, en-boy oranı koruma, otomatik yönlendirme ve çok sayfalı TIFF/PDF işleme kuralları.

---

## 📄 Lisans
Bu proje [MIT Lisansı](LICENSE) altında dağıtılmaktadır. UYAP kütüphaneleri Adalet Bakanlığı mülkiyetindedir.
