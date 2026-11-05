# ⚖️ CanEditor (UdeMobile) — Çapraz Platform UYAP & Word Editörü

[![Sürüm](https://img.shields.io/badge/Sürüm-v3.11.0-blue.svg)](https://github.com/cnkzlyr/udemobile/releases/tag/v3.11.0)
[![Platformlar](https://img.shields.io/badge/Platformlar-Android%20%7C%20Windows%20%7C%20macOS%20%7C%20Linux%20%7C%20Web-success.svg)](https://github.com/cnkzlyr/udemobile/releases)
[![UYAP](https://img.shields.io/badge/Format-UYAP_UDF_v1.8-0D47A1.svg)](https://uyap.gov.tr)
[![Word](https://img.shields.io/badge/Format-MS_DOCX_OpenXML-2B579A.svg?logo=microsoft-word&logoColor=white)](https://microsoft.com)
[![5070 E-İmza](https://img.shields.io/badge/5070_S.K.-E--İmza_%26_Mobil_İmza-darkgreen.svg)](https://www.mevzuat.gov.tr/mevzuat?MevzuatNo=5070&MevzuatTur=1&MevzuatTertip=5)
[![Lisans](https://img.shields.io/badge/Lisans-MIT-green.svg)](LICENSE)

**CanEditor (UdeMobile)**; avukatlar, hakimler, savcılar, katipler ve tüm hukuk profesyonelleri için geliştirilmiş; mobil cihazlarda, masaüstünde (Windows, macOS, Linux) ve modern web tarayıcılarında **Google Dokümanlar & Word konforunda** UYAP dilekçesi hazırlamayı, düzenlemeyi, okumayı, **elektronik imza doğrulamayı** ve **5070 Sayılı Kanuna uygun gerçek Mobil İmza / USB Akıllı Kart ile mühürlemeyi** sağlayan yeni nesil, tam kapsamlı ve bağımsız bir hukuk editörüdür.

---

## 🚀 Hızlı İndirme (v3.11.0)

| Platform | Paket Dosyası | Açıklama |
| :--- | :--- | :--- |
| **Android (Telefon & Tablet)** | [**CanEditor-v3.11.0.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.11.0/CanEditor-v3.11.0.apk) | Güncel Android APK paketi (Termux gerektirmez) |
| **Android (Her Zaman En Son)** | [**CanEditor-latest.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.11.0/CanEditor-latest.apk) | Kalıcı son sürüm bağlantısı |
| **Taşınabilir Web & Masaüstü** | [**CanEditor-Portable-Web-GUI-v3.11.0.zip**](https://github.com/cnkzlyr/udemobile/releases/download/v3.11.0/CanEditor-Portable-Web-GUI-v3.11.0.zip) | **Kurulumsuz;** zipten çıkarıp `index.html` açarak tüm işletim sistemlerinde doğrudan çalışır |
| **Windows / macOS / Linux** | [**GitHub Releases Sayfası**](https://github.com/cnkzlyr/udemobile/releases/tag/v3.11.0) | GitHub Actions CI ile derlenen yerel ikili (.msi, .exe, .dmg, .AppImage, .deb, .rpm) paketleri |

---

## 🌟 v3.11.0 ile Gelen Devrimsel Yenilikler (1:1 e-UDF Standardı, Tam Fonksiyonel 1-Tık Kaydet/Farklı Kaydet/Paylaşım, Kesintisiz Klavye Odağı, Kalıcı Dokunmatik Cetvel, Dahili PDF/TIFF Görüntüleyici ve Termux'suz Yerel E-İmza)

### 🎨 1. e-UDF Standardı Birebir Kompakt Üst Panel & 1-Tık Kaydetme
- **e-UDF Birebir Kısayol Hapı (`[ 💾 | 📱 / 🖥️ | ☰ ]`):** Ekranın tam ortasında yer alan merkezlenmiş hap konteyneri sayesinde:
  - **💾 1-Tık Doğrudan Kaydet:** Açık olan belge üzerinde yapılan tüm değişiklikleri anında açık olan dosyaya veya `Downloads/UYAP_Belgelerim` klasörüne yazar. Orijinal dosya üzerinde yapılan değişikliklerin korunmaması sorunu (`isDocumentModified` köprü senkronizasyonu) %100 çözüldü.
  - **📱 / 🖥️ Görünüm Değiştir:** Kağıt baskı görünümünde iken `📱` gösterir (tek tıkla mobil akışa geçer), mobil akışta iken `🖥️` gösterir (tek tıkla A4 baskı düzenine döner).
  - **☰ Tüm İşlemler Çekmece Menüsü:** Yeni belge, dosya açma, farklı kaydet (UDF, PDF, DOCX, TIFF, ODT), paylaşım, yazdırma, e-imza ve ayarlar seçeneklerine anında erişim. En üstte belirgin yeşil 1-tık hızlı kaydetme butonu eklendi.
- **Kusursuz Farklı Kaydet & Paylaşım Motoru:** UDF, Adobe A4 PDF, Word DOCX, Çok Sayfalı TIFF, OpenDocument ODT ve Düz Metin formatlarının tamamı yerel Android paylaşım sayfasına (`shareBlobData`) ve Scoped Storage İndirilenler klasörüne doğrudan entegre edildi. WhatsApp, Gmail, Telegram ve Samsung Dosyalarım ile tek tıkla paylaşım sağlandı.

### ⌨️ 2. Kesintisiz Klavye Odak Koruması (Klavye Kapanması ve Titreme Engellendi)
- **Arka Plan Modallarının Odak Çalması Engellendi:** Düzenleme esnasında arka plandan gelen otomatik taslak kurtarma ve güncelleme denetimi pencerelerinin kullanıcının klavyesini aniden kapatması sorunu tamamen ortadan kaldırıldı (`isUserTypingActive` ve `isEditorFocused` koruması).
- **DOM Yıkımsız Paragraf ve Sayfa Ayrımı:** Sayfa bölme motorunun kullanıcının yazı yazma duraksamalarında DOM ağacını temizlemesi (`container.innerHTML = ''`) kesin olarak engellendi. Kullanıcı imleci içeride olduğu sürece sanal klavye (Gboard, Samsung Keyboard, SwiftKey) asla kapanmaz.
- **Tek-Gövde Kesintisiz Mobil Akış:** Mobil modda sayfalar arası yapay kutular ve bölünmeler yerine tek bir sürekli akış gövdesi kullanılarak sayfa sınırlarında klavye düşüşü önlendi.

### 📐 3. Sayfa Aşağı Kaydırılsa Dahi Kalıcı Çakılı (Sticky) Dokunmatik Cetvel
- **Bütünleşik Sabit Üst Kabuk (`#app-fixed-top-shell`):** Başlık, araç çubuğu ve cetvel tek bir sabit üst kabuk altında birleştirildi. Cetvel sayfa ne kadar aşağı kaydırılırsa kaydırılsın ekranın en üstünde toolbar'ın hemen altında sabit kalır.
- **-2 cm'den +18 cm'ye Sürekli Markaj:** Sol marj (-2 .. 0 cm), aktif metin alanı (0 .. 16 cm) ve sağ marj (16 .. 18 cm) kesintisiz milimetrik çizgilerle donatıldı.
- **Ergonomik 48px Ayrık Dokunmatik Hedefler:** Üst üçgen (İlk Satır Girintisi), alt üçgen (Asılı Girinti) ve kutu (Sol Girinti) için dikeyde ayrıştırılmış 48px dokunma alanları oluşturuldu; mobilde parmakla istenen im doğrudan tutulup kaydırılabilir hale getirildi. Canlı dikey kılavuz çizgisi ve anlık santimetre ipucu rozeti eklendi.

### 📕 4. Dahili Adli PDF ve Çok Sayfalı TIFF/TIF Görüntüleyici
- **Dahili PDF.js & UTIF.js Motorları:** Harici hiçbir uygulama gerekmeden, CanEditor doğrudan adli `.pdf` ve tekli/çoklu sayfalı adli `.tiff`/`.tif` evraklarını tam ekran kaydırmalı, yakınlaştırmalı (zoom +/-), sayfa sayaçlı (`1 / N`), yazdırmalı, indirmeli ve paylaşımlı olarak görüntüler.
- **Çok Sayfalı Mobil A4 Çıktı Üretimi:** Mobil görünümde dahi uzun metinler otomatik olarak sayfa sınırlarına (`getPageElementBuckets`) göre bölümlenerek A4 PDF ve TIFF olarak tam ve eksiksiz üretilir.

### 🏛️ 5. Rootsuz & Termux'suz Tam Bağımsız Yerel E-İmza & USB OTG Akıllı Kart Desteği
- **Android Yerel USB CCID Sürücüsü (`CcidDriver.java`):** Termux, harici konsol veya root gerektirmeden; SafeNet eToken 5110/5100 (Kırmızı Token / Barokart), ArkSigner, ACS ACR38/39 ve TÜBİTAK Akis kart okuyucuları doğrudan telefonun Type-C / USB OTG portuna takılarak çalışır.
- **Dahili Adalet Port Sunucusu (`EmbeddedAdaletServer.java` - Port 5975):** Android uygulaması içinde çalışan yerel Adalet E-İmza REST API sayesinde hem CanEditor içinden hem de UYAP Avukat Portal'dan doğrudan e-imza ile giriş ve belge imzalama gerçekleştirilir.
- **Headless Havelsan UYAP Dönüşüm Altyapısı (`UdeMobileServer.java`):** Termux veya masaüstü ortamlarında Havelsan UYAP resmi jar kütüphaneleri (`editor_lib.jar`, `jai_hvl.jar`) ile birebir adli vektör PDF ve ODT dönüşümleri sağlanır.

### ⌨️ 3. Sanal Klavyenin Kapanmasını Kesin Olarak Önleyen Mimari (Sıfır Klavye Kapanması)
- **Tek-Gövde Mobil Akış Düzeni (`switchToMobileViewFlow`):** Mobil görünüme geçildiğinde tüm sayfaların gövde paragrafları tek bir kesintisiz `<div id="editor-content">` konteynerinde birleştirilir. Sayfalar arası kart kopmaları ve çoklu contenteditable yapıları kaldırıldığı için Android IME sanal klavyesi (Gboard, Samsung Keyboard, SwiftKey) yazım esnasında ASLA kapanmaz.
- **Yazım Anında Sıfır DOM Yıkımı:** Aktif yazım esnasında veya imleç editör alanındayken DOM ağacının `container.innerHTML = ''` ile silinip yeniden inşa edilmesi kesin olarak engellendi.
- **O(1) Seçim ve Odak Koruma:** Normal yazım anında (`sel.isCollapsed === true`) tüm belge üzerinde yapılan ağır `querySelectorAll` ve `intersectsNode` sorgulamaları kaldırılarak yazım gecikmesi (jank) ve IME bağlantı kopmaları sıfırlandı.
- **Android Soft-Keyboard ConfigChanges:** `EditorActivity` üzerinde `orientation|screenSize|keyboardHidden|screenLayout|smallestScreenSize|keyboard` bayrakları ve `adjustResize` modu ile klavye açılıp kapandığında aktivitenin veya WebView'ın yeniden yüklenmesi önlendi.

### 💾 4. Eksiksiz 1-Tık Kaydet, Farklı Kaydet ve Yerel Paylaşım Motoru
- **Açık Olan Belgeyi Doğrudan 1-Tık Kaydet:** 💾 butonuna basıldığında açık dosya doğrudan güncellenir; harici veya ekten açılan dosyalarda Scoped Storage standartlarında `İndirilenler/UYAP_Belgelerim` klasörüne anında kayıt yapılır.
- **Farklı Kaydet (UDF, PDF, DOCX, TIFF, ODT):** Tüm formatlar 1 saniyelik hızlı arka plan kontrolü ve kesintisiz istemci motoruyla (Canvas PDF, JSZip Word/ODT, UTIF TIFF) sıfır bekleme ile dışa aktarılır.
- **Kusursuz Sistem Paylaşımı (`shareBlobData` & `<queries>`):** WhatsApp, Gmail, Telegram ve Samsung Files gibi alıcı uygulamalara yönelik Android 11-15 paket görünürlüğü (`<queries>`) ve `grantUriPermission` izinleri tanımlanarak paylaşım menüsündeki tüm formatların doğrudan ilgili uygulamada açılması sağlandı.

### 📕 5. Dahili PDF ve Çok Sayfalı Adli TIFF Görüntüleyici
- **PDF.js Dahili Görüntüleyici:** Harici bir uygulama açmaya gerek kalmadan uygulama içinde sayfa gezintisi, dinamik yakınlaştırma (%40 - %300) ve tek tıkla paylaşım.
- **UTIF.js Çok Sayfalı TIFF Görüntüleyici:** İcra ve mahkeme evraklarındaki tek veya çok sayfalı `.tiff` / `.tif` dosyalarını doğrudan açıp kaydırmalı, yüksek netlikte görüntüleme kabiliyeti.
- **Termux Bağımsız Tek Başına Çalışan APK:** Termux kurulu olmayan herhangi bir Android telefonda tüm özellikleriyle bağımsız çalışır.

### 🛡️ 6. Sıfır-Termux: Doğrudan Android Yerel USB Host CCID E-İmza Sürücüsü
- **Bağımsız Donanım Erişimi:** Android telefonunuza OTG kablo ile takılan her türlü USB token (SafeNet 5110 kırmızı token, ArkSigner, ACS ACR38/ACR39, Gemalto, AKİS) doğrudan Android SDK USB Host katmanında algılanır (`device_filter.xml` & `CcidDriver.java`).
- **Dahili Adalet Port 5975 Sunucusu:** CanEditor arka planda `127.0.0.1:5975` portunda Adalet Bakanlığı E-İmza REST API (`/api/v1/signature/getCertificates` ve `/api/v1/docsignature/signdigest`) sunar. Termux kurulumuna gerek olmadan telefonunuz bir e-imza merkezine dönüşür.

---

## 🌟 v3.9.0 ile Gelen Yenilikler (1:1 e-UDF Kompakt Arayüzü, Kalıcı Sticky Cetvel, Kesintisiz Klavye Odağı, Dahili PDF/TIFF Görüntüleyici ve Havelsan Headless Motoru)

### 🎨 1. e-UDF Standardı Birebir Kompakt Üst Panel & Kısayol Hapı
- **e-UDF Birebir Kısayol Hapı (`[ 💾 | 📱 / 🖥️ | ☰ ]`):** Ekranın tam ortasında yer alan merkezlenmiş hap konteyneri sayesinde:
  - **💾 1-Tık Doğrudan Kaydet:** Açık olan belge üzerinde yapılan tüm değişiklikleri anında diske kaydeder (Ctrl+S).
  - **📱 / 🖥️ Görünüm Değiştir:** Mobil akış görünümü ile 1:1 A4 kağıt baskı düzeni arasında tek dokunuşla geçiş yapar.
  - **☰ Tüm İşlemler Çekmece Menüsü:** Yeni belge, dosya açma, farklı kaydet, dışa aktar, e-imza ve ayarlar seçeneklerine anında erişim.
- **Modern Crimson Marka Rozeti & Mavi Profil Butonu:** Sol üstte kırmızı gradyan `⚖️ CanEditor` logo rozeti, sağ üstte tek dokunuşla tüm seçenekleri açan `👤` kullanıcı simgesi.
- **Kompakt Tek Satır Şerit Araç Çubuğu:** Mobilde yatay kaydırılabilir, sağındaki kırmızı `⌵` chevron butonuyla genişleyip daralabilen ergonomik araç şeridi.

### 📐 2. Sayfa Kaydırılsa Dahi Asla Kaybolmayan Sabit (Sticky) Dokunmatik Cetvel
- **Sayfa Üstünde Çakılı Kalan Mimari:** Cetvel belge kaydırma konteynerinin dışına (`#toolbar-container` altına) taşınarak sayfalar onlarca sayfa aşağı kaysa dahi ekranın üstünde kalıcı olarak sabitlendi (`position: sticky !important`).
- **-2 cm'den +18 cm'ye Tam Ölçekli Görsel Cetvel:** Sol kenar marjı (-2 .. 0), beyaz aktif yazı alanı (0 .. 16 cm) ve sağ marj (16 .. 18 cm) net biçimde renklendirildi ve sayfa kenar boşluklarıyla orantılı ölçeklendi.
- **48px Ergonomik Parmak Hedef Alanı:** İlk satır girintisi, asılı girinti ve sağ marj imleri dokunmatik ekranlarda parmakla kolayca tutulup sürüklenebilecek genişlikte (`touch-action: none !important`) yapılandırıldı.

### ⌨️ 3. Sanal Klavyenin Kapanmasına Karşı Kesin Odak Koruma Motoru
- **Sıfır Klavye Kapanması:** Yazı yazarken (Gboard, Samsung Keyboard, SwiftKey) IME kompozisyonu ve odak koruma motoru (`isUserTypingActive()` & `isEditorFocused()`) devreye girerek DOM ağacının yıkılmasını, gereksiz yeniden çizimleri ve seçim sıfırlamalarını %100 engeller.
- **Android Soft-Keyboard ConfigChanges:** `EditorActivity` üzerinde `orientation|screenSize|keyboardHidden|screenLayout|smallestScreenSize|keyboard` bayrakları tanımlanarak klavye açılıp kapandığında aktivitenin yeniden başlatılması önlendi.

### 📕 4. Dahili PDF ve Çok Sayfalı Adli TIFF Görüntüleyici
- **PDF.js Entegrasyonu:** Herhangi bir PDF dosyası CanEditor ile açıldığında, dahili sayfalı PDF görüntüleyici devreye girer; sayfalar arası geçiş, yakınlaştırma/uzaklaştırma, yerel indirme ve paylaşım sunar.
- **Çok Sayfalı TIFF / TIF Görüntüleyici (UTIF.js):** Tekli ve çok sayfalı adli tarama evrakları, icra dosyaları ve tapu/bilirkişi belgeleri tıpkı modern bir PDF okuyucu gibi sayfa sayfa kaydırılarak incelenebilir.

### 🏛️ 5. Havelsan UYAP Resmi Headless Dönüşüm Motoru (Port 5976) & İstemci Yedek Motoru
- **1:1 Vektörel A4 PDF:** Resmi Havelsan JAR sınıfları (`tr.com.havelsan.uyap.system.editor.b.b`) üzerinden birebir UYAP kalitesinde PDF dönüşümü.
- **Resmi ODT ve DOCX Desteği:** Havelsan'ın ODT ayrıştırıcısı (`tr.com.havelsan.uyap.system.editor.b.a.f`) ve `odt_to_docx.py` köprüsüyle mükemmel Microsoft Word dönüşümü.
- **Çevrimdışı İstemci Desteği:** Termux veya arka plan servisi bulunmayan ortamlarda dahili JS motoru otomatik olarak devreye girerek belgeleri kaydeder.

### 🛡️ 6. Sıfır-Termux: Doğrudan Android Yerel USB Host CCID E-İmza Sürücüsü
- **Bağımsız Donanım Erişimi:** Android telefonunuza OTG kablo ile takılan her türlü USB token (SafeNet 5110 kırmızı token, ArkSigner, ACS ACR38/ACR39, Gemalto, AKİS) doğrudan Android SDK USB Host katmanında algılanır (`device_filter.xml` & `CcidDriver.java`).
- **Dahili Adalet Port 5975 Sunucusu:** CanEditor arka planda `127.0.0.1:5975` portunda Adalet Bakanlığı E-İmza REST API (`/api/v1/signature/getCertificates` ve `/api/v1/docsignature/signdigest`) sunar. Termux kurulumuna gerek olmadan telefonunuz bir e-imza merkezine dönüşür.

### 📕 6. Dahili PDF ve Çok Sayfalı Adli TIFF Görüntüleyici
- **PDF.js Dahili Görüntüleyici:** Harici bir uygulama açmaya gerek kalmadan uygulama içinde sayfa gezintisi, dinamik yakınlaştırma (%40 - %300) ve tek tıkla paylaşım.
- **UTIF.js Çok Sayfalı TIFF Görüntüleyici:** İcra ve mahkeme evraklarındaki tek veya çok sayfalı `.tiff` / `.tif` dosyalarını doğrudan açıp kaydırmalı, yüksek netlikte görüntüleme kabiliyeti.
- **Termux Bağımsız Tek Başına Çalışan APK:** Termux kurulu olmayan herhangi bir Android telefonda tüm özellikleriyle bağımsız çalışır.

---

## 🌟 v3.7.1 ile Gelen Önemli Geliştirmeler (Resmi Havelsan Headless Çeviri Motoru, Dahili PDF & Çok Sayfalı TIFF Görüntüleyici)

### 🏛️ 1. Resmi Havelsan UYAP Headless Dönüştürücü Motoru (`UyapHeadlessConverter`)
- **1:1 Vektörel A4 PDF:** Resmi Havelsan `tr.com.havelsan.uyap.system.editor.b.b` motoru tersine mühendislikle çözülerek başsız (headless) Java CLI motoruna bağlandı. Raster tuval ekran görüntüleri yerine; seçilebilir, kopyalanabilir gerçek vektörel metin, Havelsan yazı tipleri ve birebir 10 sayfalık resmi UYAP düzeni oluşturulur (~196 KB dosya boyutu, karanlık mod uyumlu).
- **Resmi OpenDocument (ODT):** Resmi Havelsan `tr.com.havelsan.uyap.system.editor.b.a.f` motoru kullanılarak; tüm tabloları, hizalamaları ve stilleri içeren %100 uyumlu `.odt` evrakları üretilir (~29 KB).
- **Zengin Microsoft Word (DOCX):** Resmi ODT yapısı üzerinden tabloları, paragraf hizalamalarını, sekme duraklarını ve yazı tipi ağırlıklarını koruyan yüksek kaliteli DOCX belgeleri üretilir (~41 KB).
- **Termux & CLI Komut Desteği:** `uyap-convert <dosya.udf> <pdf|odt|docx>` komutu ile tüm dönüştürmeler sistem seviyesinde 2 saniye içinde gerçekleştirilebilir.

### 📕 2. Dahili PDF ve Çok Sayfalı TIFF Görüntüleyici Motoru (Uygulama İçi Önizleme)
- **PDF.js Tabanlı Dahili PDF Görüntüleyici:** Harici bir uygulama açmaya gerek kalmadan, uygulama içinde sayfa gezintisi (önceki/sonraki sayfa), dinamik yakınlaştırma/uzaklaştırma (%40 - %300), 1-tık indirme ve yerel paylaşım desteği.
- **UTIF.js Tabanlı Çok Sayfalı Adli TIFF Görüntüleyici:** İcra, tebligat ve mahkeme evraklarındaki tek veya çok sayfalı `.tiff` / `.tif` dosyalarını doğrudan açıp kaydırmalı, yüksek netlikte görüntüleme ve dışa aktarma kabiliyeti.
- **Termux Bağımsız Standart Çalışma:** Termux kurulu olmayan herhangi bir Android telefonda veya masaüstü bilgisayarda yerel dosya sistemine doğrudan erişim, dahili e-imza ve dosya işleme köprüleri.

### ⌨️ 3. Yazı Yazarken Sanal Klavyenin Kapanmasını %100 Önleyen Odak Koruması
- **Sıfır DOM Yıkımı:** Aktif yazım esnasında veya imleç editör alanındayken DOM ağacının `container.innerHTML = ''` ile silinip yeniden inşa edilmesi kesin olarak engellendi.
- **Kesintisiz Yazım Deneyimi:** Android sanal klavyesinin (Gboard, Samsung Keyboard) odak kaybı nedeniyle kapanması, harf yutulması ve imleç sıçraması tamamen ortadan kaldırıldı.
- **Yalnızca Odaktan Çıkıldığında Sayfalama:** Sayfa düzenleme ve bölünme işlemleri yalnızca kullanıcı yazımı bitirip alandan çıktığında (`blur`) çalıştırılır.

### 📱 3. Yeniden Yapılandırılmış Kesintisiz Mobil Görünüm
- **Akıcı Tek Akış Düzeni:** Mobil görünüme geçildiğinde tüm sayfaların gövde paragrafları tek bir kesintisiz akış konteynerinde birleştirilir; sayfa sınırları, boşluklar ve tekrarlayan üstbilgi/altbilgiler metni bölmez (Google Docs ve Word mobil standardı).
- **Kağıt Görünümüne Anında Dönüş:** `📄 Kağıt` butonuna tıklandığında belge anında 1:1 Havelsan A4 çok sayfalı baskı düzenine geri döner.

### 📐 4. Ekranın Üstüne Sabitlenen (Sticky) 44px Dokunmatik Cetvel
- **Sayfa Boyunca Sabit Kalan Cetvel:** Cetvel A4 kağıt kartının içinden çıkarılarak sayfa kaydırma alanının üstüne (`sticky`, `top: 0`, `z-index: 100`) sabitlendi. Sayfa 10 sayfa aşağı kaysa bile cetvel her an ekranın üstünde kalır.
- **38px Dokunmatik Etki Alanları:** İlk satır girintisi, asılı girinti, sol girinti ve sağ marj imleri 38px ergonomik dokunmatik alanlarla büyütüldü; parmakla kaydırma anında sayfa kaymasını engelleyen `touch-action: none` koruması eklendi.
- **Mobilde Tek Dokunuşla Sekme Durağı:** Cetvel ölçeğine mobilde dokunulduğunda doğrudan sekme durağı (tab stop) ekleme/kaldırma özelliği entegre edildi.

### 💾 5. Doğrudan 1-Tık Hızlı Kaydet & Taşmayan Ergonomik Üst Çubuk
- **Belirgin 1-Tık Kaydet Butonu:** Üst barda dosya adının hemen yanında canlı yeşil renkli **`💾 Kaydet`** butonu yer alır; açık olan belgenin üzerine doğrudan, tek tıkla ve hiçbir diyalog açmadan anında kayıt yapar.
- **Responsive Üst Bar:** Mobilde butonların ekrandan taşmasını ve başlığın ezilmesini önlemek amacıyla kompakt simge düzeni (`←`, `💾 Kaydet`, `Başlık`, `📱`, `📤`, `⋮`) uygulandı.
- **Eksiksiz Paylaşım ve Farklı Kaydet:** PDF, UDF, Word, TIFF, ODT ve Metin formatlarında paylaşım ve indirme köprüleri Android 10-15 Scoped Storage standartlarıyla tam uyumlu hale getirildi.

---

## 🌟 v3.6.5 ile Gelen Önemli Geliştirmeler (1-Tık Hızlı Kaydet, Mobil Görünüm & Klavye Odak Koruma Motoru, Sticky Dokunmatik Cetvel)

### 💾 1. Doğrudan 1-Tık Hızlı Kaydet Butonu (Ctrl+S & Android Doğrudan Kayıt)
- **Doğrudan Üzerine Kayıt:** Açılmış olan belgeyi anında kaydetmek için hem web üst araç çubuğuna hem de Android yerel eylem çubuğuna belirgin, yeşil renkli **`💾 Kaydet`** butonu eklendi.
- **Tek Dokunuşla UYAP Kaydı:** Masaüstünde `Ctrl+S`, mobilde ise tek dokunuşla açık olan `.udf` dosyasının üzerine doğrudan kayıt gerçekleştirilir.

### ⌨️ 2. Yazı Yazarken Klavyenin Kapanmasını Engelleyen Akıllı Odak Koruması
- **Klavye Açılma (adjustResize) Koruması:** Android'de sanal klavye açıldığında tetiklenen pencere yeniden boyutlandırma olayında (`window.resize`), aktif düzenleme odağı varsa otomatik yakınlaştırma (fit-zoom) engellendi; CSS zoom değişiminden kaynaklanan imleç ve klavye kaybı tamamen ortadan kaldırıldı.
- **Yazım Esnasında Sıfır DOM Yıkımı:** Aktif yazım esnasında sayfalamanın DOM ağacını yeniden kurması 2500ms bekleme süresine alındı ve dikey taşma olmadığı sürece DOM ağacının korunması sağlandı. Böylece yazı yazarken sanal klavyenin kendi kendine kapanması sorunu %100 çözüldü.

### 📐 3. Ekranın Üstüne Sabitlenen (Sticky) Dokunmatik Cetvel (42px)
- **Sayfa Kaydıkça Ekranda Kalan Cetvel:** Sayfa ne kadar aşağı kaydırılırsa kaydırılsın, cetvel ekranın en üstünde (`position: sticky; top: 0; z-index: 90;`) sabit kalarak her an görünür durumda kalır.
- **Parmakla Kontrol Edilebilen 44x44px Geniş Dokunmatik Alanlar:** Cetvel yüksekliği 42px'e çıkarıldı. 4 ayrı girinti imi (**İlk Satır Girintisi** - mavi ters üçgen, **Asılı Girinti** - mavi düz üçgen, **Sol Girinti** - lacivert kutu, **Sağ Marj** - koyu üçgen) için parmakla rahatça tutulup sürüklenebilen görünmez 44x44 piksellik dokunmatik etki alanları (`::before`) entegre edildi.

### 📱 4. Kusursuz Mobil Görünüm (Word & Google Docs Standardı)
- **Sıfır Yatay Taşma:** Dar mobil ekranlarda (`max-width: 820px`) `document.body` ve editör kapsayıcısının yatay taşması (`overflow-x: hidden`) tamamen önlendi (`bodyScrollW: 390px`).
- **Yatay Kaydırılabilir Araç Çubuğu:** Web araç çubuğu butonlarının mobilde alt alta 10 satır yığılması engellendi; Word ve `editor.e-udf.com` standardında tek satırda parmakla pürüzsüz kaydırılabilir hale getirildi.
- **Android Arayüz Bütünlüğü:** Android uygulamasında yerel başlık çubuğu bulunduğu için WebView içindeki masaüstü başlık çubuğu gizlendi; gereksiz dikey alan kaybı ve çift başlık görünümü önlendi.

### 📤 5. Android 10+ Harici Paylaşım ve Farklı Kaydet Onarımı
- **WhatsApp ve Gmail Paylaşım İzni Hatası Çözüldü:** `launchShareIntent` içinde `shareIntent.setClipData(...)` ve `FLAG_GRANT_READ_URI_PERMISSION` yetkileri tanımlanarak Android 10, 11, 12, 13, 14 ve 15 sürümlerinde harici uygulamaların paylaşılan dosyaları "erişim engellendi" hatası vermeden açması sağlandı.
- **Tüm Formatlarda Farklı Kaydet:** Menüdeki tüm seçenekler (**UDF, Adobe PDF, Microsoft Word DOCX, Çok Sayfalı TIFF, OpenDocument ODT**) Base64 veri köprüsüyle doğrudan `Downloads/UYAP_Belgelerim` klasörüne anında kaydedilir hale getirildi.

---

## 🌟 v3.6.4 ile Gelen Önemli Geliştirmeler (1:1 Resmi Havelsan UYAP Birebir Sayfalama ve Tipografi Motoru)

### 📄 1. 1:1 Resmi Havelsan UYAP Birebir Sayfalama ve Satır Satır Paragraf Bölme (Cross-Page Line-Splitting)
- **Sayfa Sonu Boşluğu Sorununa Kesin Çözüm:** Önceki sürümlerde uzun paragrafların (örneğin gerekçeli kararlardaki *"İDDİA: Ankara Cumhuriyet Başsavcılığı'nın..."* gibi çok satırlı bloklar) DOM seviyesinde bölünemeyip blok halinde bir sonraki sayfaya aktarılması ve ilk sayfada yarım sayfa boşluk kalması sorunu tamamen çözüldü.
- **DOM Range Tabanlı İkili Arama (Binary Search):** Sayfa sınırına taşan paragraflar, kelime sınırları gözetilerek piksel hassasiyetinde satır satır ikiye ayrılır. İlk parça mevcut sayfanın kalan alt boşluğuna yerleşir, devamı ise kesintisiz olarak bir sonraki sayfanın tepesine akar.
- **Dinamik Birleştirme & Düzenleme Koruması:** Sayfalama her güncellendiğinde (`updatePagination`), daha önce bölünmüş paragraflar (`data-split-continuation`) ilk haline birleştirilir ve yeniden hesaplanır; düzenleme esnasında metin kaybı veya çift paragraf oluşumu %100 engellenir.

### 📐 2. Akıllı Sekme (Tab) Daraltma ve Sağ Kenar Yaslama Kalibrasyonu
- **UYAP CDATA Sekme Desteği:** Resmi UYAP dosyalarında başlıklar arasındaki onlarca ardışık `\t` karakteri (`\t+`) tek bir akıllı sekme aralığına (`udf-tab-space`) daraltılarak satır taşmaları önlendi.
- **T.C. - BERAAT Birebir Uyum:** UYAP `TabSet="71.0:2:0"` gibi merkezli ve sağa dayalı sekme durakları tam desteklendi. Belgenin ilk satırındaki **T.C.** ve **BERAAT (Bozma Üzerine)** ibareleri resmi Havelsan UYAP editöründeki gibi tam aynı satırda, sağ kenara milimetrik olarak yaslanır.
- **Asılı Girinti (Hanging Indent) Desteği:** 2. satırdan itibaren başlayan mahkeme başlıkları ve sanık bilgileri resmi UYAP hizalamasıyla tam uyumlu hale getirildi.

### 🔍 3. Masaüstü Ekran Ölçekleme (Min-Zoom %75) ve A4 Marj Kalibrasyonu
- **Masaüstü Küçülme (%43 Zoom) Hatası Düzeltildi:** Windows'ta bölünmüş ekran (split screen) veya dar pencerelerde sayfanın aşırı küçülerek okunamaz hale gelmesi engellendi; masaüstü görünümü için asgari %75 fit ölçekleme tabanı tanımlandı.
- **Altbilgi (Footer) Alanı Kurtarıldı:** Sayfa altında gereksiz ayrılan ~80 piksellik aşırı dikey marj boşluğu, resmi UYAP 2.0 cm alt kenar boşluğu ile dengelenerek her sayfada tam metin kapasitesi elde edildi.

### 🛡️ 4. 4 Sütunlu Gerçekçi Havelsan UYAP Sicil Filigranı
- Resmi Havelsan Doküman Editörü ile birebir örtüşen 4 sütunlu, `#334155` renk tonunda ve `%12` opaklıkta kesintisiz çapraz sicil filigran matrisi (`uyapsicil`) entegre edildi.

---

## 🌟 v3.6.3 ile Gelen Önemli Geliştirmeler (Kesintisiz Yerel Undo/Redo, Akıllı Biçim Boyacısı ve Sıfır DOM Kaybı)

### ↶ 1. Kesintisiz Yerel Adım Adım (Step-by-Step) Geri Al & Yinele Motoru
- **Kaba HTML Yedekleme Yerine Hassas İşlem Yığını:** Önceki sürümlerde `history.js` motorunun tüm sayfa HTML'ini blok halinde yedekleyip `innerHTML` üzerinden geri yüklemesi sebebiyle oluşan "belgenin yedeğini alıp geri yüklüyor gibi çalışma" hissi tamamen ortadan kaldırıldı.
- **Yüzlerce Adım Derinlik:** Kelime arasına yazılan tek bir boşluk, silinen tek bir harf veya uygulanan tek bir kalınlaştırma işlemi doğrudan yerel hafızaya kaydedilir; `Ctrl+Z` (Geri Al) veya `Ctrl+Y` (Yinele) ile tam işlem anındaki imleç noktasında adım adım geri alınıp yinelenebilir.
- **Yinele (Redo) Dalı Artık Asla Silinmez:** Geri alma işlemleri sırasında arka planda çalışan mutasyon gözlemcisinin ileri adımları silmesi engellendi.

### ⚡ 2. DOM Sayfalama Koruması (Zero-DOM-Thrashing)
- **Gereksiz Sayfa Yıkımı Engellendi:** Düzenleyicide yazı yazarken, boşluk bırakırken veya silerken sayfa sayısı ve paragraf düzeni değişmediği sürece `container.innerHTML = ''` asla çalıştırılmaz. Böylece tarayıcının yerel Undo/Redo yığıtı, imleç seçimi ve aktif odak sıfır kayıpla %100 korunur.

### 🖌️ 3. Akıllı ve İki Yönlü Biçim Boyacısı (Format Painter)
- **Gerçek Yaprak Düğüm (Leaf Node) Analizi:** Boyacı artık kapsayıcı paragrafların varsayılan stillerini değil, seçili metnin gerçek `<strong>`, `<em>`, `<u>` ve punto değerlerini `document.queryCommandState` ile eksiksiz okur.
- **Akıllı Fark (Diff) Uygulama:** Hedef metinle kaynak metin arasındaki stiller karşılaştırılır; sadece farklı olan özellikler (örneğin yalnızca kalınlık veya yalnızca yazı rengi) uygulanır. Bu sayede gereksiz biçimlendirme komutları üretilmez ve boyacı işlemi `Geri Al` ile tek hamlede geri alınabilir.
- **Evrensel Sayfa Desteği:** Boyacı açıkken tüm sayfalarda kopyalama imleci (`cursor: copy !important`) gösterilir ve tıklanan veya seçilen tüm sayfalardaki metinlere sorunsuz uygulanır.

---

## 🌟 v3.6.2 ile Gelen Önemli Geliştirmeler (Gelişmiş İmleç Korumalı Geri Al/Yinele ve Odak Yönetimi)

### ↶ 1. Karakter ve Pozisyon Duyarlı Gelişmiş Geri Al / Yinele Motoru
- **İmlecin Başa Atlaması Engellendi:** Önceden geri al tuşuna basıldığında tüm DOM yenilendiği için imleç başlığın veya sayfanın en başına (offset 0) sıçramaktaydı. Yeni `saveCaretPosition` ve `restoreCaretPosition` motoru sayesinde imleç tam olarak yazılan boşluk veya harfin bulunduğu karakter ofsetine geri oturur.
- **Tek Tuş ve Boşluk Duyarlılığı:** Kelime arasına boşluk yazılıp hemen ardından Geri Al tuşuna basıldığında (`beforeinput` ön-kayıt mekanizması ile) yazılan boşluk anında geri alınır ve imleç kelimenin tam ortasında kalır.
- **Biçimlendirmelerin Anında Geri Alınabilmesi:** "B Kalın", "İtalik", "Altı Çizili" veya hizalama yapıldığında durum anında geçmiş yığıtına (`CanHistory`) işlenir. Geri Al ile kalınlaştırılan kelime hemen eski haline döner, Yinele ile tekrar kalınlaşır.

### 🎯 2. Araç Çubuğu Odak ve Seçim Koruması
- **Mousedown PreventDefault Güvencesi:** Araç çubuğundaki herhangi bir butona tıklandığında tarayıcının seçili metni kaybetmesi veya odağı düzenleyiciden çalması engellendi. Metin seçilip "B Kalın" butonuna tıklandığında seçim kaybolmaz, biçimlendirme kesintisiz uygulanır.

### 📊 3. Gerçek Zamanlı Kelime & Karakter Sayacı Güvencesi
- Sayfa ilk açıldığında alt durum çubuğundaki (status bar) kelime sayacının `0 kelime, 0 karakter` kalması hatası giderilerek ilk yükleme anında varsayılan metnin (137 kelime, 907 karakter) doğru yansıtılması sağlandı.

---

## 🌟 v3.6.1 ile Gelen Önemli Geliştirmeler (Kapsamlı E2E Doğrulama & Resmi UYAP/LibreOffice Uyumluluğu)

### 🧪 1. 29 Adımlı Uçtan Uca Otomasyon ve Round-Trip Doğrulama
- **Resmi Havelsan Doküman Editörü (`format_id="1.8"`) 1:1 Doğrulaması:** CanEditor ile oluşturulan zengin UDF dokümanları (tablolar, görsel deliller, sekme durakları, marjin ve girintiler) resmi Havelsan Doküman Editöründe (`dokuman.sh` / JDK 14.0.2) açılmış; sıfır hata ve sıfır XML ayrıştırma uyarısıyla tam uyumluluk kanıtlanmıştır.
- **LibreOffice DOCX & ODT Çift Yönlü Doğrulama:** CanEditor'ün ürettiği Word (`.docx`) ve OpenDocument (`.odt`) belgeleri headless LibreOffice (`soffice --headless --convert-to pdf`) ile kusursuz olarak PDF'e dönüştürülmüştür.
- **Doğrudan Vektörel PDF & Firefox Görüntüleyici:** Doğrudan üretilen ISO 32000-1 / PDF 1.4 A4 (595.28 × 841.89 pt) belgeleri Firefox PDF Viewer üzerinde pikseli pikseline doğrulanmıştır.
- **Çok Sayfalı TIFF Doğrulaması:** Little-Endian ikili IFD yapıları ve etiketleri adli arşiv standardında test edilip onaylanmıştır.

### 📄 2. Çok Sayfalı Doküman Mimarisi İyileştirmeleri
- **Çok Sayfalı Bul ve Değiştir:** Arama ve değiştirme motoru tüm sayfalardaki metin bloklarını tarar; eşleşmeleri sarı vurgular ve tek tıkla tüm sayfalardaki kelimeleri değiştirir (`doReplaceAll`).
- **Gerçek Çok Sayfalı İstatistikler:** Belge Bilgileri modalı (`openDocStatsModal`) tüm sayfaları tarayarak toplam kelime, karakter, paragraf ve gerçek sayfa sayısını tam doğrulukla raporlar.
- **Çok Sayfalı Deterministik AI Formatlama:** Hukuk dilekçe standartları (mahkeme başlığı ortalama, taraf blokları sekme durakları, iki yana yaslama, 1.0 cm girinti) sayfa sınırları gözetilmeksizin tüm sayfalara uygulanır.
- **Tüm Sayfalarda Biçim Boyacısı:** `Biçim Boyacısı` sayfa sınırlarından bağımsız olarak herhangi bir sayfadan biçim kopyalayıp diğer sayfalara uygular.
- **Kayıpsız Düz Metin Aktarımı (`getPlainText`):** Dokümanın tamamı sayfa atlamadan eksiksiz metin olarak panoya veya diğer uygulamalara kopyalanır.

### 🛠️ 3. Kullanılabilirlik & Araç Çubuğu Geliştirmeleri
- **Masaüstü ve Web Resim/Delil Seçici:** Android'in yanı sıra Windows, macOS, Linux ve Web ortamlarında da `🖼️ Resim` butonuna basıldığında yerel dosya seçici açılarak delil/belge görselleri anında dokümana eklenir.
- **Seçimden Bağımsız Tablo ve Resim Ekleme:** Düzenleyicide imleç veya aktif seçim bulunmasa dahi tablo veya resim eklendiğinde işlem sessizce başarısız olmak yerine imlecin bulunduğu paragrafa veya sayfanın sonuna güvenle eklenir.
- **OpenDocument ODT Tablo Desteği:** OpenDocument Metin Belgesi (`.odt`) dışa aktarımına yerel OASIS `<table:table>` desteği eklenerek LibreOffice ve OpenOffice'te tabloların 1:1 açılması sağlandı.
- **Şablon Geri Alma Desteği:** Yeni bir dilekçe şablonu yüklendiğinde eski sayfalar temizlenir, sayfalama anında yenilenir ve kullanıcı dilerse `Ctrl+Z` (Geri Al) ile önceki metnine geri dönebilir.

---

## 🌟 v3.6.0 ile Gelen Önemli Geliştirmeler (UYAP Avukat Portal Standardı)

### 📕 1. Doğrudan A4 PDF Vektörel Aktarım Motoru (ISO 32000-1 / PDF 1.4)
- **1-Tıkla Gerçek PDF İndirme:** Web tarayıcısı yazdırma penceresine (`window.print`) muhtaç kalmadan, A4 kağıt ölçülerinde (595.28 × 841.89 pt), keskin 192 DPI çözünürlükte, Türkçe karakter (ğ, Ğ, ı, İ, ş, Ş, ç, Ç, ö, Ö, ü, Ü) destekli gerçek ikili `.pdf` dosyası üretilir ve indirilir.
- **Android'de Doğrudan İndirilenler & Paylaşım:** Mobil uygulamada "PDF Olarak Kaydet" seçildiğinde dosya doğrudan `Downloads/UYAP_Belgelerim` klasörüne fiziki dosya olarak kaydedilir. "PDF Olarak Paylaş" ile WhatsApp, Telegram, Gmail veya UYAP sistemine tek dokunuşla aktarılır.
- **Akıllı Çift Katmanlı Tuval/SVG Çözümleyici:** Doküman sayfaları hem SVG ForeignObject tarayıcı motoru hem de özel tuval çizim motoruyla yedekli olarak işlenir; karmaşık tablolar, kenarlıklar (`borderSpec`), logolar ve üst/altbilgiler sıfır kayıpla PDF'e dökülür.

### 🏛️ 2. UYAP Avukat Portal Görünüm ve Araç Çubuğu Standartları
- **Belge İçi Hızlı Arama Barı (`.udv-search-box`):** UYAP Avukat Portalındaki gibi araç çubuğuna entegre arama kutusu; anlık sarı/turuncu vurgu eşleşmeleri, eşleşme sayacı (`X/Y`) ve Enter (Sonraki) / Shift+Enter (Önceki) kısayolları.
- **Akıllı Zoom & Sığdırma Butonları:** "↔ Sığdır" (Genişliğe Sığdır) ve "↕ Sayfa" (Sayfaya Sığdır) düğmeleriyle ekrana anında tam oturan ergonomik sayfa ölçekleme.
- **Resmi E-İmza Rozeti (`.signature-ribbon`):** Portaldaki yeşil mühür ve sertifika sayacı rozetiyle 5070 Sayılı Kanun kapsamındaki e-imzalar dokümanın sağ üst köşesinde zarifçe sergilenir; tıklandığında nitelikli elektronik sertifika ayrıntı kartı açılır.
- **Mikro Tipografi Optimizasyonu:** `font-feature-settings: "kern" off`, `font-kerning: none` ve `text-underline-offset: 4.56px` ile Havelsan Swing motoruyla pikseli pikseline aynı metin akışı sağlanır.

### 🏛️ 3. Resmi Havelsan UYAP Doküman Editörü (`format_id="1.8"`) ile 1:1 Birebir Uyumluluk
- **Unicode Rune (Karakter) Duyarlı Ofset Hesabı:** Türkçe karakterler ve astral düzlem sembollerinde oluşan UTF-16 surrogate pair ofset kaymaları giderildi; karakterler `Array.from(str).length` ile tam 1:1 Havelsan standardında hesaplanır.
- **Kusursuz XML Başlığı ve Şablon Yapısı:** Resmi Havelsan formatında `<?xml version="1.0" encoding="UTF-8"?>` ve `<template format_id="1.8">` blok sırası (`content` -> `properties` -> `elements` -> `styles`) güvenceye alındı. Boş paragraflar `length="1"` ve `\n` CDATA tutarlılığı ile korunur.
- **Birebir Girinti ve Cetvel Matematiği:** Havelsan UYAP `ParagraphView` / `RowView` (`LeftIndent`, `FirstLineIndent`, `Hanging`, `RightIndent`) hesaplama motoru tersine mühendislikle modellendi (`margin-left = LeftIndent + Hanging`, `text-indent = FirstLineIndent - Hanging`). Kaydetme sırasında asılı girintilerin (`Hanging`) ezilmesi önlendi.
- **Evrensel Belge Açıcı (Sıfır Hata Garantisi):** Standart ZIP UDF ve OOXML DOCX belgelerinin yanı sıra sıkıştırılmamış düz XML `.udf`, `.udf` uzantılı Word `.docx`, eski nesil OLE2 Word 97-2003 ikili `.doc` / `.doc.udf` (`FIB` + `Clx Piece Table` CP1254/UTF-16LE çözümleyici), `RTF`, UTF-8 BOM'lu XML ve 0 baytlık boş dosyaların tamamı hatasız açılır.
- **Masaüstü UDF/DOCX Birlikte Aç (Open With) Desteği:** Windows Dosya Gezgini'nde veya masaüstünde bir `.udf` ya da `.docx` dosyasına sağ tıklayıp "Birlikte Aç" seçildiğinde veya çift tıklandığında hedef belge otomatik yüklenir.

---

## 📖 Hiç Bilmeyenler İçin Adım Adım İndirme ve Kurulum Kılavuzu

Uygulamayı daha önce hiç kullanmamış veya bilgisayar/telefon ayarları konusunda deneyimli olmayan kullanıcılarımız için platform bazında adım adım rehber aşağıdadır:

### 📱 1. Android Telefon ve Tablet İçin Adım Adım Kurulum

1. **İndirme:** Telefonunuzun tarayıcısından (Chrome, Samsung Internet vb.) yukarıdaki [**CanEditor-latest.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.9.0/CanEditor-latest.apk) bağlantısına dokunun.
2. **Güvenlik Uyarısına Onay Verme:**
   - Chrome veya Samsung Internet, Google Play dışından indirilen her dosya için *"Bu türden bir dosya cihazınıza zarar verebilir"* veya *"Dosya zararlı olabilir"* uyarısı gösterebilir.
   - Bu standart bir Android güvenlik uyarısıdır. **"Yine de İndir"** (Download anyway) butonuna dokunun.
3. **Yükleme İzni:**
   - İndirme tamamlandığında bildirim çubuğundaki **CanEditor-latest.apk** dosyasına veya Dosyalarım/İndirilenler klasörüne dokunun.
   - Ekrana *"Güvenlik nedeniyle telefonunuzun bu kaynaktan bilinmeyen uygulamalar yüklemesine izin verilmez"* uyarısı gelirse:
     - **Ayarlar**'a dokunun.
     - **"Bu kaynaktan izin verin"** seçeneğini açık (mavi) duruma getirin ve geri gelin.
   - **"Yükle"** (Install) butonuna dokunun.
4. **UYAP Dosyalarını (.udf) Açma ve Varsayılan Yapma:**
   - WhatsApp, Telegram, E-posta veya İndirilenler klasöründeki herhangi bir `.udf` dosyasına dokunun.
   - Açılan *"Birlikte Aç"* menüsünde **CanEditor**'ü seçin ve **"Her Zaman"** (Always) seçeneğine tıklayın.
   - Artık tarafınıza iletilen tüm UYAP dilekçeleri ve kararları doğrudan CanEditor ile açılacaktır!
5. **PDF Olarak Kaydetme:**
   - Açtığınız belgede üst menüdeki **"Kaydet"** butonuna dokunun ve **"PDF Olarak Kaydet"** seçeneğini seçin. Belgeniz anında `İndirilenler/UYAP_Belgelerim` klasörüne A4 formatında kaydedilir.

---

### 💻 2. Windows (10 / 11) İçin Kurulum Rehberi

#### Yöntem A: Taşınabilir (Portable) Sürüm — En Kolay, Kurulumsuz!
1. [**CanEditor-Portable-Web-GUI-v3.9.0.zip**](https://github.com/cnkzlyr/udemobile/releases/download/v3.9.0/CanEditor-Portable-Web-GUI-v3.9.0.zip) dosyasını indirin.
2. İndirilen `.zip` dosyasına sağ tıklayıp **"Tümünü Ayıkla..."** (Extract All) seçeneğine basın.
3. Klasörün içindeki `index.html` dosyasına çift tıklayın.
4. Google Chrome, Microsoft Edge veya varsayılan tarayıcınızda CanEditor anında açılır. İnternet bağlantısı olmasa bile tamamen çevrimdışı ve güvenli çalışır.

#### Yöntem B: Kurulabilir Masaüstü Uygulaması (.msi veya .exe)
1. [Releases sayfasından](https://github.com/cnkzlyr/udemobile/releases/tag/v3.9.0) `CanEditor_3.9.0_x64-setup.exe` veya `CanEditor_3.9.0_x64_en-US.msi` dosyasını indirin.
2. İndirilen dosyaya çift tıklayın.
3. **Windows Defender SmartScreen Uyarısı Çıkarsa:**
   - Açık kaynak kodlu ve yeni yayınlanan bağımsız uygulamalarda Windows *"Kişisel bilgisayarınız korundu"* uyarısı gösterebilir.
   - Penceredeki **"Ek bilgi"** (More info) bağlantısına tıklayın.
   - Ardından açılan **"Yine de çalıştır"** (Run anyway) butonuna tıklayın.
4. Kurulum saniyeler içinde tamamlanır ve masaüstünüze CanEditor kısayolu eklenir.
5. Herhangi bir `.udf` dosyasına sağ tıklayıp **Birlikte Aç -> Başka bir uygulama seç -> CanEditor** seçerek *"Her zaman bu uygulamayı kullan"* kutucuğunu işaretleyebilirsiniz.

---

### 🍎 3. macOS (Apple Silicon M1/M2/M3/M4 & Intel) Kurulum Rehberi

1. [Releases sayfasından](https://github.com/cnkzlyr/udemobile/releases/tag/v3.9.0) `CanEditor_3.9.0_universal.dmg` dosyasını indirin (veya kurulumsuz Portable ZIP'i kullanın).
2. İndirilen `.dmg` dosyasına çift tıklayın ve açılan penceredeki **CanEditor** simgesini **Applications (Uygulamalar)** klasörüne sürükleyip bırakın.
3. **macOS Gatekeeper Uyarısı Çıkarsa:**
   - Apple, App Store dışı uygulamalarda *"Geliştirici doğrulanamadığı için açılamıyor"* uyarısı verebilir.
   - **Çözüm 1:** Uygulama simgesine klavyeden `Control` tuşuna basılı tutarak **sağ tıklayın** ve **"Aç"** (Open) seçeneğini seçin. Çıkan pencerede tekrar **"Aç"** butonuna basın.
   - **Çözüm 2:** **Sistem Ayarları -> Gizlilik ve Güvenlik** bölümüne gidin. En altta *"CanEditor uygulamasının açılması engellendi"* uyarısının yanındaki **"Yine de Aç"** (Open Anyway) butonuna tıklayın.

---

### 🐧 4. Linux (Ubuntu, Debian, Fedora, Arch, Pardus) Kurulum Rehberi

1. **AppImage ile Kurulumsuz Çalıştırma (Tüm Dağıtımlar):**
   - Releases sayfasından `CanEditor_3.9.0_amd64.AppImage` dosyasını indirin.
   - Dosyaya sağ tıklayıp **Özellikler -> İzinler -> "Dosyayı bir program gibi çalıştırmaya izin ver"** kutusunu işaretleyin (veya terminalde: `chmod +x CanEditor*.AppImage`).
   - Çift tıklayarak doğrudan çalıştırın.
2. **Debian / Ubuntu / Pardus (.deb):**
   - Terminalde: `sudo dpkg -i CanEditor_3.9.0_amd64.deb`
3. **Fedora / RedHat / openSUSE (.rpm):**
   - Terminalde: `sudo rpm -ivh CanEditor-3.9.0-1.x86_64.rpm`

---

### 🌐 5. Web Tarayıcısında Sıfır Kurulumla Doğrudan Kullanım

CanEditor, modern web teknolojileri (HTML5, WebAssembly, Canvas, SVG) üzerinde çalıştığı için herhangi bir yazılım kurmadan doğrudan kullanılabilir:
1. İndirdiğiniz `CanEditor-Portable-Web-GUI-v3.9.0.zip` içindeki `index.html` dosyasına çift tıklayın.
2. Açılan sayfaya bilgisayarınızdaki herhangi bir `.udf` veya `.docx` dosyasını **sürükleyip bırakın** ya da **"Belge Aç"** butonuna basın.
3. Dokümanınız anında UYAP standartlarında ekrana gelecektir.
4. Düzenlemenizi yaptıktan sonra tek tıkla **"UDF Kaydet"**, **"DOCX Kaydet"** veya **"📕 PDF İndir"** butonlarına basarak dosyanızı anında indirebilirsiniz.

---

## 🏛️ Temel Yetenekler & Özellikler

### 1. 📄 Çift Yönlü Belge Dönüştürme (UDF ⟷ DOCX)
- **Word Dilekçesini UDF Yapma:** Bilgisayardan veya mesajlaşma uygulamalarından gelen `.docx` dosyalarını açıp düzenleyebilir ve tek tıkla resmi **.udf** formatında kaydedebilirsiniz.
- **UDF'yi Word Olarak Dışa Aktarma:** Açtığınız bir UDF belgesini tek tıkla standart **.docx** formatına dönüştürebilirsiniz.
- **Resmi UYAP Tipografisi:** Times New Roman 12 pt, iki yana yaslı (justify) ve 1.16 - 1.35 satır aralığı standardı varsayılan olarak uygulanır.

### 2. 📏 Etkileşimli A4 Cetveli (Ruler) & Sayfa Boşlukları
- **0 - 16 cm Milimetre Ölçeği:** A4 kağıt genişliğiyle birebir uyumlu cetvel.
- **İlk Satır Girintisi İmi (▼):** Paragrafın ilk satır girintisini (0.5 cm, 1.0 cm, 1.25 cm UYAP standardı) sürükleyerek ayarlama.
- **Sol ve Asılı Girinti İmi (▲ + ▀):** Paragrafın sol kenarını ve asılı bendini bağımsız kontrol etme.
- **Sağ Kenar İmi (▲):** Paragrafın sağ marjinini ayarlama.

### 3. 📑 Kalıcı Üstbilgi ve Altbilgi (Header & Footer)
- Mahkeme adı, dosya no ve iletişim bilgileri sayfa başında ve sonunda kalıcı olarak görüntülenir.
- Otomatik tarih ve `Sayfa 1 / 1` biçiminde resmi sayfa numaralandırması ekleme.
- `content.xml` içindeki webID ile her sayfanın altbilgisine resmi UYAP doğrulama metni ve dinamik QR kod yerleştirme.

### 4. ✍️ Donanımsal E-İmza (USB OTG CCID) & Mobil İmza
- **Fiziksel Kart Desteği:** Type-C OTG adaptörüyle takılan TÜRKTRUST, Kamu SM, AKİS, E-Tuğra akıllı kartları ve ACR39U vb. CCID kart okuyucuları.
- **Çoklu İmza (Multi-Sign) Koruması:** Belgede önceden atılmış imzalar varsa yeni imza atıldığında eski imzalar korunur; CAdES-BES standardına uygun olarak yeni sertifika mevcut arşive eklenir.
- **Canlı İmza Doğrulama Motoru:** Açılan dokümanın imzaları (imzacı adı, NES sertifika sağlayıcı, seri no, son geçerlilik tarihi) ve içerik bütünlüğü anlık doğrulanır, UYAP Avukat Portal yeşil imza rozetiyle sergilenir.

### 5. ⚖️ Hukuki Araç Çubuğu & Şablonlar
- **Tek Tıkla Dilekçe Şablonları:** Dava Dilekçesi, Cevap Dilekçesi, Süre Uzatım Talebi (HMK m. 127), Bilirkişi Raporuna İtiraz, İstinaf Başvuru Dilekçesi, İhtarname.
- **Hukuki Madde Numaralandırma:** Hukuk Dava Maddeleri (1.1, 1.2, 1.3), Roma Rakamları (I., II., III.), Harfli Bentler (a, b, c) ve Madde İmleri.
- **Fosforlu Vurgulama & Renkler:** Sarı ve yeşil metin vurgulama, koyu mavi / kırmızı başlık ve ihtar notları.

---

## 🔒 Gizlilik, Güvenlik & Kişisel Veri Politikası (KVKK Uyumlu)

> [!IMPORTANT]
> **CanEditor (UdeMobile) hiçbir kişisel veriyi, kimlik numarasını (TCKN), telefon numarasını veya belge içeriğini üçüncü taraf sunucularda TOPLAMAZ ve SAKLAMAZ.**

1. **Yerel İşleme (Local-First):** Tüm UDF ve DOCX ayrıştırma, biçimlendirme ve dönüştürme işlemleri doğrudan cihazınızın belleğinde (RAM) yerel olarak gerçekleştirilir.
2. **Kriptografik Bütünlük:** Mobil İmza ve Elektronik İmza süreçlerinde kimlik doğrulama yalnızca kullanıcının talebiyle, doğrudan resmi Adalet Bakanlığı UYAP ağ geçitleri ve yetkili Elektronik Sertifika Hizmet Sağlayıcıları (ESHS / TÜBİTAK UEKAE) üzerinden yürütülür.
3. **Sıfır Telemetri:** Uygulama içinde reklam, kullanıcı takip kodu veya harici analiz kütüphanesi bulunmaz.

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
│   │   ├── desktop_bridge.js        # Vektörel PDF motoru, arama, sığdırma ve köprü
│   │   ├── editor.js                # Zengin editör, cetvel, sekme ve m-imza mantığı
│   │   └── updater.js               # Dahili GitHub güncelleme denetleyicisi
│   └── index.html                   # Ana düzenleyici arayüzü
├── src-tauri/                       # Masaüstü Native Çekirdeği (Rust / Tauri v2)
│   ├── Cargo.toml                   # Rust bağımlılıkları ve sürüm yapılandırması
│   ├── tauri.conf.json              # Windows, macOS, Linux pencere ve paket ayarları
│   └── src/                         # Rust Tauri komutları ve dosya motoru
├── scripts/                         # Paketleme, Headless UYAP ve Derleme Betikleri
│   ├── pack_release.py              # Otomatik release paketleyici ve varlık senkronizasyonu
│   └── UdeMobileServer.java         # Havelsan UYAP mikroservisi
├── release/                         # Derlenmiş hazır APK ve taşınabilir paketler
└── README.md                        # Güncel proje dokümantasyonu ve kullanım kılavuzu
```

---

## ⚖️ Lisans & Telif Hakları

- Bu proje **Av. Can KIZILYAR** tarafından geliştirilmiştir.
- UYAP®, T.C. Adalet Bakanlığı Bilgi İşlem Genel Müdürlüğü'nün tescilli markasıdır.
- Açık kaynak kodlu ve MIT lisansı altındadır.
