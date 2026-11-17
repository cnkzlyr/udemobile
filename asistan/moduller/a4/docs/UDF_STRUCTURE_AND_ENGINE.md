# UDF Belge Mimarisi ve UYAP Doküman Editörü JAR Sistemleri Teknik İnceleme

Bu dokümantasyon; Adalet Bakanlığı UYAP (Ulusal Yargı Ağı Bilişim Sistemi) bünyesinde kullanılan **UDF** (UYAP Doküman Formatı) belge yapısını, editörün orijinal JAR kütüphanelerinin iç işleyişini, tersine mühendislik ile elde edilen sınıf mimarisini ve Java 21+ ortamında sorunsuz vektörel dönüştürme mekanizmalarını detaylı olarak açıklamaktadır.

---

## 1. UDF (UYAP Doküman Formatı) Dosya Yapısı

UDF dosyaları, standart bir metin dosyası olmayıp temelinde özel bir **ZIP Arşivi (Container)** formatıdır. 

### 1.1. Arşiv İçeriği
Bir `.udf` dosyası ZIP açıcı (unzip / python zipfile) ile incelendiğinde şu bileşenlerden oluşur:
1. `content.xml`: Belgenin tüm metin, paragraf, biçimlendirme, sayfa yapısı, üstbilgi/altbilgi ve tablo verilerini içeren ana XML ağacı.
2. `meta.xml` / metadata (varsa): Belgeye ait sürüm, oluşturulma tarihi, yazar bilgileri.
3. Resimler ve İmzalar: Belge içerisine eklenen taramalar, vesikalıklar veya mühürler XML içine doğrudan Base64 olarak gömülebilir veya arşiv içerisinde binary akış olarak saklanır.
4. E-İmza Paketleri (PKCS#7 / CAdES / PAdES / XAdES): Yetkili imzalayanın (avukat, hakim, katip) sertifikası ve sayısal imza verisi.

### 1.2. `content.xml` XML Şeması
`content.xml` dosyasının hiyerarşisi genel olarak şu şekildedir:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<template format_version="1.9">
    <elements>
        <!-- Belge Özellikleri ve Sayfa Yapısı -->
        <page-format leftMargin="42.5" rightMargin="42.5" topMargin="42.5" bottomMargin="42.5" paperOrientation="1" />
        
        <!-- Üstbilgi ve Altbilgi Tanımları -->
        <header startPage="1">
            <paragraph alignment="center">
                <content size="12" bold="true" font="Times New Roman">T.C. ANKARA ADLİYESİ</content>
            </paragraph>
        </header>

        <!-- Gövde Paragrafları -->
        <paragraph lineSpacing="1.15" leftIndent="0" rightIndent="0" firstLineIndent="28.3">
            <content size="11" italic="false" bold="false" font="Times New Roman">
                Mahkemenizin yukarıda belirtilen esasına kayden...
            </content>
        </paragraph>

        <!-- Tablo Yapıları -->
        <table rowCount="2" colCount="3">
            ...
        </table>
    </elements>
</template>
```

---

## 2. UYAP Doküman Editörü JAR Mimarisi ve Bytecode Analizi

UYAP Doküman Editörü, Havelsan ve Adalet Bakanlığı tarafından Java Swing üzerinde geliştirilmiştir. Temel işlevler şu arşivlerde yer alır:

| JAR Dosyası | Rolü ve İşlevi |
|---|---|
| `editor_lib.jar` | Ana editör motoru, kelime işlemci Swing panelleri, belge dönüştürücüler (`b`, `lo`, `J`, `f`), e-imza arayüzleri. |
| `jai_hvl.jar` | Java Advanced Imaging (JAI) modülleri ve gömülü **iText 2.1.7** PDF vektör oluşturma motoru. |
| `jdom.jar` | UDF XML ağacını ayrıştıran JDOM 0.9/1.0 motoru. |
| `editor_lib2.jar` | TÜBİTAK UEKAE / Kamu SM Akis akıllı kart e-imza kütüphaneleri, PAdES sağlayıcıları ve loglama. |
| `editor_utility.jar`| XStream, XML parser'lar ve platform yardımcıları. |
| `flatlaf.jar` | Modern Flat Look and Feel arayüz motoru. |

---

## 3. Vektörel PDF Dönüştürme Motoru: `tr.com.havelsan.uyap.system.editor.b.b`

Birçok gayriresmi araç UDF'leri PDF'e çevirirken metni sadece düz yazı olarak çıkarıp fontları, tabloları ve antetleri bozar. Oysa UYAP'ın kendi kütüphaneleri içerisinde doğrudan **birebir vektörel PDF** üreten özel bir sınıf bulunur:

### 3.1. Sınıf İmzası ve Yöntemleri
```java
package tr.com.havelsan.uyap.system.editor.b;

public class b {
    public b();
    public void a(OutputStream out, ByteArrayInputStream in);
    public void a(OutputStream out, ByteArrayInputStream in, int maxPages);
    public void a(OutputStream out, ByteArrayInputStream in, int maxPages, boolean fitToPage);
}
```

### 3.2. Çalışma Prensibi
1. `WPDocumentPanel` oluşturulur ve `panel.a(in)` ile UDF akışı yüklenir.
2. Editör belgenin satır sonlarını, sayfa kırılımlarını ve mizanpajını hesaplar (`Pageable pageable = panel.a()`).
3. Her bir sayfa için `PageFormat` alınır (A4: 595.28 x 841.89 pt).
4. İlgili sayfa iText'in `PdfWriter` doğrudan içerik katmanına (`PdfContentByte`) aktarılır:
   ```java
   PdfTemplate tp = cb.createTemplate(width, height);
   Graphics2D g2 = tp.createGraphics(width, height, fontMapper);
   pageable.getPrintable(pageIndex).print(g2, pageFormat, pageIndex);
   g2.dispose();
   cb.addTemplate(tp, 0, 0);
   ```
5. Bu yöntem pikselli bir resim üretmez; **orijinal vektörel PDF** üretir. Metinler aranabilir, seçilebilir, fontlar net ve dosya boyutu son derece küçüktür.
6. **Headless Uyumluluğu:** Bu sınıf `-Djava.awt.headless=true` modunda arka planda hiçbir X11 ekranı gerektirmeden çalışabilir!

---

## 4. ODT ve DOCX Dışa Aktarım Mekanizmaları

### 4.1. ODT Dönüştürücü: `tr.com.havelsan.uyap.system.editor.b.a.f`
UYAP Doküman Editöründe "ODT Olarak Kaydet" seçeneği tıklandığında:
1. `lo.a(InputStream)` ile UDF belgesi bir Swing `DocumentEx` modeline dönüştürülür.
2. `J.b(DocumentEx, OutputStream)` bu modeli standart bir XML ara formatına döker.
3. `tr.com.havelsan.uyap.system.editor.b.a.f` sınıfı, gömülü **OdfToolkit (OdfDOM)** kütüphanesini kullanarak `template.odt` iskeleti üzerine metinleri, başlıkları, tabloları ve resimleri yerleştirir:
   ```java
   tr.com.havelsan.uyap.system.editor.b.a.f f = new tr.com.havelsan.uyap.system.editor.b.a.f();
   f.a(baos);       // XML ara verisi
   f.b(targetFile); // .odt dosyası kaydedilir
   ```

### 4.2. DOCX Dönüştürme Pipeline'ı
Resmi UYAP editöründe doğrudan DOCX yazıcı sınıfı yerine ODT formatı üretilir ve arka plandaki office köprüsü üzerinden iletilir. 
Geliştirdiğimiz motor bu süreci şu şekilde otomatikleştirir:
1. `UyapVectorExporter.exportToOdt(udf, tempOdt)` ile birebir UYAP ODT'si üretilir.
2. `soffice --headless --convert-to docx tempOdt --outdir targetDir` komutuyla LibreOffice Writer üzerinden tam uyumlu Office Open XML (`.docx`) formatına dönüştürülür.
3. Sonuç olarak Word içerisinde açıldığında sayfa kenar boşlukları, tablolar, antetler ve mühürler bozulmadan aynen korunur.

---

## 5. Modern Java (Java 11, 17, 21) Uyumluluk Çözümleri

UYAP JAR'ları aslen Java 8 döneminde tasarlandığı için Java 9 ve üzerinde gelen Java Modül Sistemi (JPMS) sebebiyle reflection kısıtlamalarına takılır.

Bu kısıtlamaları aşmak için Java sanal makinesi şu parametrelerle başlatılmalıdır:
```bash
java -Djava.awt.headless=true \
  --add-opens=java.base/java.util=ALL-UNNAMED \
  --add-opens=java.base/java.lang=ALL-UNNAMED \
  --add-opens=java.desktop/java.awt=ALL-UNNAMED \
  --add-opens=java.desktop/javax.swing=ALL-UNNAMED \
  -cp "uyap-exporter.jar:$UYAP_JARS/*" \
  uyap.UyapVectorExporter <pdf|odt> <dosya.udf>
```
Bu bayraklar sayesinde Java 21 LTS üzerinde sıfır hata ve maksimum hızla çalışır.
