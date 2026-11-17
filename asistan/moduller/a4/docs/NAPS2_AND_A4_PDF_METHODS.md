# NAPS2 Tarama İlkeleri ve A4 PDF Dönüştürme/Birleştirme Yöntemleri

Bu dokümantasyon; açık kaynak belge tarama yazılımı **NAPS2** (Not Another PDF Scanner 2)'nin temel mizanpaj algoritmalarını ve çok formatlı belgelerin (TIF, TIFF, JPG, JPEG, PNG, BMP, WEBP, PDF, UDF) standart A4 kağıt boyutuna kusursuz şekilde dönüştürülüp birleştirilme yöntemlerini açıklamaktadır.

---

## 1. NAPS2 Mizanpaj ve PDF Motorunun Temel İlkeleri

NAPS2; tarayıcılardan (WIA, TWAIN, SANE, eSCL) veya yerel dosyalardan gelen her türlü sayfayı bağımsız bir sayfa nesnesi olarak modeller. Bu sayfalar PDF'e aktarılırken belirli geometrik kurallar uygulanır:

1. **Kağıt Standardı (ISO 216 - A4):**
   - Dikey A4 Boyutu: `210 mm x 297 mm` (72 DPI'da `595.28 x 841.89 pt`, 300 DPI'da `2480 x 3508 px`)
   - Yatay A4 Boyutu: `297 mm x 210 mm` (72 DPI'da `841.89 x 595.28 pt`, 300 DPI'da `3508 x 2480 px`)

2. **Otomatik Sayfa Yönlendirme (Auto-Orientation):**
   - Taranan veya içe aktarılan görselin en/boy oranı incelenir.
   - Eğer `Genişlik > Yükseklik` ise: Sayfa otomatik olarak **Yatay A4 (Landscape)** seçilir.
   - Eğer `Yükseklik >= Genişlik` ise: Sayfa **Dikey A4 (Portrait)** seçilir.
   - Böylece yatay çekilmiş tutanaklar, mahkeme kararları veya geniş şemalar dikey sayfaya sıkıştırılıp küçültülmez.

3. **Oran Korumalı Sığdırma (Aspect Ratio Preserved Fit):**
   - Görsel asla esnetilmez, basıklaştırılmaz veya uzatılmaz.
   - Ölçekleme katsayısı:
     $$\text{scale} = \min\left(\frac{\text{Kullanılabilir Genişlik}}{\text{Görsel Genişliği}}, \frac{\text{Kullanılabilir Yükseklik}}{\text{Görsel Yüksekliği}}\right)$$

4. **Yazıcı Güvenli Kenar Boşluğu (Safe Print Margins):**
   - Fiziksel yazıcıların kenar tutucuları genellikle 3-5 mm'lik alanlara baskı yapamaz.
   - NAPS2 yaklaşımı gereği sayfada 5 mm (~14.17 pt) güvenli kenar payı bırakılır.

5. **Otomatik Ortalama (Centering):**
   - Ölçeklenen görsel sayfanın tam ortasına yerleştirilir:
     $$x = \text{margin} + \frac{\text{avail\_w} - \text{draw\_w}}{2}$$
     $$y = \text{margin} + \frac{\text{avail\_h} - \text{draw\_h}}{2}$$

---

## 2. Çoklu Formatların İşlenme Mantığı

Geliştirdiğimiz `a4_pdf_engine.py` motoru, NAPS2'nin bu mantığını tüm dosya uzantılarına uygular:

### 2.1. Çok Sayfalı TIFF / TIF Dosyaları
TIFF formatı tek bir dosya içinde birden fazla kare (frame) barındırabilir.
Pillow'un `ImageSequence.Iterator(im)` mekanizması ile her kare tek tek açılır:
- 1. Sayfa -> A4 Sayfası 1
- 2. Sayfa -> A4 Sayfası 2
- ...
Her sayfanın kendi boyutuna göre yönlendirmesi bağımsız belirlenir.

### 2.2. Mobil Kamera ve Resim Formatları (JPG, JPEG, PNG, BMP, WEBP)
Mobil telefonlarla çekilen belgelerde sıklıkla EXIF yönlendirme etiketi bulunur (Orientation = 6 veya 8). Bu etiket dikkate alınmazsa PDF'te belge yan veya baş aşağı çıkar.
Motorumuz `ImageOps.exif_transpose` ile EXIF açısını çözer ve sayfayı doğru açıyla yerleştirir.

### 2.3. PDF Dosyaları
PDF dosyaları içeri aktarılırken `pypdf` kütüphanesi kullanılır:
- Sayfa zaten A4 boyutundaysa: Vektörel netliğini ve metin aranabilirliğini kaybetmemesi için dönüştürmeden doğrudan yeni PDF'e aktarılır.
- Sayfa standart dışı bir boyuttaysa (örneğin ABD Letter, fatura fişi, 2 metrelik rulo tarama): Sayfa içeriği vektörel ölçekleme ile orantılı olarak standart A4 sayfaya küçültülür/büyütülür ve ortalanır.

### 2.4. UDF Dosyaları
UDF dosyaları seçildiğinde sistem önce UYAP'ın kendi resmi vektör motorunu tetikler (`UyapVectorExporter.exportToPdf`). Üretilen 100% orijinal A4 PDF sayfaları alınıp dönüştürme veya birleştirme sürecine kesintisiz dahil edilir.

---

## 3. Sağ Tık Menüsü Eylemleri

### A) Tümünü PDF'ye Dönüştür
- Kullanıcı tek bir dosya veya yüzlerce dosya seçebilir.
- Her dosya kendi adına sahip bir `<dosya_adi>.pdf` haline gelir.
- Çok sayfalı TIFF'ler ve PDF'ler tüm sayfalarını korur.

### B) Tümünü Tek PDF'de Birleştir
- Seçilen tüm dosyalar (örneğin 3 adet JPG, 1 adet çok sayfalı TIFF, 2 adet UDF ve 1 adet PDF) tek seferde taranır.
- Tüm sayfalar sırayla tek bir A4 PDF dosyasında birleştirilir (`Birlestirilmis_Belge_YYYYAAGG_SSDDSS.pdf`).
- Avukatlar, katipler ve ofis çalışanları için adliyeye veya resmi kurumlara tek bir ek yüklemek gerektiğinde saniyeler içinde hazır hale gelir.
