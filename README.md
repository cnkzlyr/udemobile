# ⚖️ CanEditor (UdeMobile) — Çapraz Platform UYAP & Word Editörü

[![Sürüm](https://img.shields.io/badge/Sürüm-v3.26.1-blue.svg)](https://github.com/cnkzlyr/udemobile/releases/tag/v3.26.1)
[![Platformlar](https://img.shields.io/badge/Platformlar-Android%20%7C%20Windows%20%7C%20macOS%20%7C%20Linux%20%7C%20Web-success.svg)](https://github.com/cnkzlyr/udemobile/releases)
[![UYAP](https://img.shields.io/badge/Format-UYAP_UDF_v1.8-0D47A1.svg)](https://uyap.gov.tr)
[![Word](https://img.shields.io/badge/Format-MS_DOCX_OpenXML-2B579A.svg?logo=microsoft-word&logoColor=white)](https://microsoft.com)
[![5070 E-İmza](https://img.shields.io/badge/5070_S.K.-E--İmza_%26_Mobil_İmza-darkgreen.svg)](https://www.mevzuat.gov.tr/mevzuat?MevzuatNo=5070&MevzuatTur=1&MevzuatTertip=5)
[![Lisans](https://img.shields.io/badge/Lisans-MIT-green.svg)](LICENSE)

**CanEditor (UdeMobile)**; avukatlar, hakimler, savcılar, katipler ve tüm hukuk profesyonelleri için geliştirilmiş; mobil cihazlarda, masaüstünde (Windows, macOS, Linux) ve modern web tarayıcılarında **Google Dokümanlar & Word konforunda** UYAP dilekçesi hazırlamayı, düzenlemeyi, okumayı, **elektronik imza doğrulamayı** ve **5070 Sayılı Kanuna uygun gerçek Mobil İmza / USB Akıllı Kart ile mühürlemeyi** sağlayan yeni nesil, tam kapsamlı ve bağımsız bir hukuk editörüdür.

---

## 🚀 Hızlı İndirme (v3.26.1)

| Platform | Paket Dosyası | Açıklama |
| :--- | :--- | :--- |
| **Android (Telefon & Tablet)** | [**CanEditor-v3.26.1.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.26.1/CanEditor-v3.26.1.apk) | Güncel Android APK paketi (Termux gerektirmez) |
| **Android (Her Zaman En Son)** | [**CanEditor-latest.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.26.1/CanEditor-latest.apk) | Kalıcı son sürüm bağlantısı |
| **Taşınabilir Web & Masaüstü** | [**CanEditor-Portable-Web-GUI-v3.26.1.zip**](https://github.com/cnkzlyr/udemobile/releases/download/v3.26.1/CanEditor-Portable-Web-GUI-v3.26.1.zip) | **Kurulumsuz;** zipten çıkarıp `index.html` açarak tüm işletim sistemlerinde doğrudan çalışır |
| **Windows / macOS / Linux** | [**GitHub Releases Sayfası**](https://github.com/cnkzlyr/udemobile/releases/tag/v3.26.1) | GitHub Actions CI ile derlenen yerel ikili (.msi, .exe, .dmg, .AppImage, .deb, .rpm) paketleri |

---

## ⚠️ Android: v3.16.0 ve öncesinden geçerken bir kerelik yeniden kurulum

v3.17.0'dan itibaren APK yeni ve kalıcı bir proje anahtarıyla imzalanır (sertifika `CN=CanEditor`, SHA-256
`BA:80:78:89:12:28:35:C0:58:3B:C9:72:3B:C0:90:5C:C8:6F:49:A8:1A:92:BA:F9:D0:96:33:77:71:BB:D4:F0`). Telefonunuzda
v3.16.0 ya da öncesi kuruluysa bir kez **kaldırıp** yeni APK'yı kurun (aksi halde Android "paket çakışıyor" hatası
verir). Sonraki güncellemeler kaldırmadan, üzerine kurulur.

## 🌟 v3.26.1: UYAP Editör — imleç dokunulan yere gider

- **Düzeltme:** kağıt görünümünde imleç dokunulan yere gitmiyordu; resmi editörün %98 iç yakınlaştırması hesaba
  katılmıyordu (sapma belge sonuna doğru büyüyordu). Artık dokunulan kelimeye konur, imleç satırla hizalıdır.
- Mobil görünüm boş belgede de tam sayfa görünür; uygulama her açılışta kağıt görünümüyle başlar.

## 🌟 v3.26.0: UYAP Editör — anında yazma, tüm Windows yazı tipleri, düzgün sayfa sayısı

- **Yazma gecikmesi giderildi:** görünüm artık artımlı güncellenir (yalnızca değişen paragraf); basılan harf motor
  yanıtını beklemeden anında görünür. Kağıt görünümünde yazma çalışır; uzun belgelerde yalnızca ekrandaki sayfalar çizilir.
- **Windows yazı tipleri:** Times New Roman, Arial, Arial Black, Courier New, Georgia, Verdana, Trebuchet MS,
  Comic Sans MS, Impact, Andale Mono, Webdings — ilk açılışta Microsoft'un orijinal kurulum dosyalarından bu cihaza
  kurulur; yazı tipi listesinde gerçek adlarıyla, kendi görünümleriyle çıkar.
- **Düzeltmeler:** fazladan boş sayfalar, büyük imleç; ek tuş satırı yalnızca klavye açıkken (klavyenin üstünde),
  yakınlaştırma kapsülü klavye açıkken gizli; görünüm düğmesi mevcut görünümü gösterir; "Dialog" → "Varsayılan".

## 🌟 v3.25.0: UYAP Editör — CanEditor arayüzü + arkada orijinal Havelsan motoru (Kağıt / Mobil)

- **Kağıt görünümü (varsayılan):** resmi motorun kendi sayfa, satır ve kelime konumlarıyla birebir A4 sayfalar —
  satır kırılımı, iki yana yaslama, sekmeler, üst/alt bilgi ve sayfa sonları orijinalle aynı; metin HTML olduğu için
  her yakınlaştırmada keskin. Dokunduğunuz yer motorda imleç olur, uzun basıp sürükleyince seçilir, yazdıklarınız ve
  araç çubuğu komutları orijinal belgede uygulanır.
- **📱 Mobil ⇄ 📄 Kağıt anında**, kaydetmeden. Orijinal ekran ☰ menüde (ya da 📱'ya uzun basın).
- **Motorun pencereleri** (imza, mobil imza, yazdırma önizlemesi, uyarılar) açılınca büyütülerek gösterilir, kapanınca
  görünüm geri gelir; pencere metinleri günlüğe yazılır.
- **Düzeltme — internet:** gömülü glibc DNS ayarını Termux klasöründe arıyordu; motor hiçbir sunucuya ulaşamıyordu
  (mobil imza hatası, "Sertifika Zinciri Sorunlu / geçersiz imza"). Artık telefonun DNS sunucuları kullanılır.
- Yakınlaştırma kapsülü ve ek tuşlar opak; PDF/ODT olarak kaydederken belgenin adı önerilir.

## 🌟 v3.24.1: UYAP Editör — Türkçe harfli dosyalar açılıyor

- **Düzeltme:** adında İ, ş, ç, ı, ğ, ö, ü olan belgeler açılmıyor, Aç/Kaydet pencereleri hata veriyordu
  ("Malformed input or input contains unmappable characters"). Telefonda Java'nın dosya adı kodlaması ASCII
  kalıyordu; başlatıcı artık her zaman UTF-8 kullanır.

## 🌟 v3.24.0: UYAP Editör — anlık mobil görünüm (kaydetmeden, imzalara dokunmadan)

- **📱 ⇄ 📄 anında:** mobil görünüm, resmi editörün BELLEKTEKİ belgesini telefon genişliğinde satır kırarak gösterir.
  Kaydetme, dönüştürme ya da başka editöre aktarma yok: belge, imzalar ve dosya olduğu gibi kalır.
- **Mobilde düzenleme:** dokunduğunuz yer resmi editörde imleç olur, klavyeyle yazdıklarınız resmi editöre gider ve mobil
  görünüm anında güncellenir; araç çubuğu (K, T, A, hizalama…) seçili metne resmi editörde uygulanır.
- **Belge açılmazsa** neden ekranda gösterilir (açık uyarı penceresi, hata, dosya durumu) ve "Günlüğü gönder" ile
  WhatsApp/e-posta üzerinden tek dokunuşla iletilir.
- "CanEditor'da düzenle" isteğe bağlı olarak menüde (dosyayı kaydeder).

## 🌟 v3.23.0: UYAP Editör — CanEditor düzeninde orijinal editör, anında Mobil ⇄ Sayfa

- **Düzeltme:** 3.22.0'da bulanık zemin tüm ekranı kaplıyor, üst çubuk ve editör görünmüyordu.
- **CanEditor düzeni:** üstte 🏛 · belge adı · mavi 💾 Kaydet · 📱 Mobil · ☰; ikinci satırda geri al/yinele, yazı tipi ve
  boyut kutuları, K T A S, renk, vurgu, hizalama, listeler, girinti. Altta yakınlaştırma kapsülü
  (− %100 Sığdır + ↔ Sığdır ↕ Sayfa, bulanık cam) ve mavi klavye düğmesi.
- **☰ Menü (CanEditor gibi):** Kaydet (1-tık), Belge Aç, Yeni, Mobil görünüm; Farklı kaydet (UDF/PDF/ODT), Yazdır,
  E-imza araçları ve resmi editörün TÜM menüleri.
- **Sayfa görünümü = orijinal UYAP Editör** (pencere başlığı gizli, üstte cetvel). **📱 Mobil** ile belge kaydedilip
  CanEditor'ın akış görünümünde açılır; "🏛 Orijinal Sayfa Görünümü" ile kaydedip geri dönülür, belge yeniden yüklenir.

## 🌟 v3.22.0: UYAP Editör — yeni arayüz (Google Dokümanlar tarzı) ve mobil görünüm

- **Yeni arayüz:** üstte belge adı, geri al / yinele, mobil görünüm; altta biçim çubuğu (K, T, A, renk, vurgu, hizalama,
  listeler, girinti). Çubuklar yarı saydam **bulanık cam**: belge altlarından kayar (Android 12+). Çekmece menü, alttan
  kayan sayfalar ve dokunma efektleri animasyonlu.
- **"A" biçim sayfası:** Metin (yazı tipi, boyut −/+, K T A S, alt/üst simge, renk, vurgu, temizle, stil) ve
  Paragraf (hizalama, listeler, girinti, satır aralığı) sekmeleri.
- **Mobil görünüm:** belge UdeMobile'ın telefon ekranına göre satır kıran editöründe açılır; orada kaydedip dönünce
  UYAP Editör'de yeniden yüklenir.
- **Düzeltme:** telefondan açılan belge için yanlış "Kaydedildi: İndirilenler/UYAP" mesajı ve gereksiz kopya kaldırıldı;
  belge açılınca arkadaki boş pencere kapatılır, açılırken "Belge açılıyor…" göstergesi çıkar.

## 🌟 v3.21.0: UYAP Editör — dokunmatik menüler ve telefonun dosya seçicisi

- **☰ Menü:** Resmi editörün TÜM komutları (Dosya, Giriş, Düzenle, Ekle, Biçim, Araçlar, Görünüm) büyük, dokunmaya
  uygun satırlarla soldan açılan menüde. Komutlar editörün kendi menü öğelerine tıklanarak çalışır (birebir aynı davranış).
- **Aa biçim çubuğu:** Stil, yazı tipi, boyut, Kalın/İtalik/Altı çizili, renk, hizalama ve listeler büyük düğmelerle.
- **Şerit menü gizlenir** (☰ > Şeridi göster ile geri gelir): belgeye daha çok yer kalır.
- **Aç / Kaydet / Farklı kaydet / Resim ekle** artık telefonun kendi dosya seçicisini açar (İndirilenler, sdcard, Drive,
  WhatsApp…; depolama izni gerekmez). Kaydedilen belge seçtiğiniz yere yazılır.

## 🌟 v3.20.1: UYAP Editör — dosyaya dokununca belge açılıyor, Aç/Kaydet /sdcard'da

- **Düzeltme:** Dosya yöneticisinden / WhatsApp'tan .udf'ye dokununca UYAP Editör boş belge açıyordu. Telefonda editörün
  ana penceresi geç kurulduğu için belge çok erken isteniyor ve kayboluyordu; artık ana pencere hazır olana kadar beklenir.
- **Aç / Kaydet / Farklı kaydet** pencereleri telefonun depolamasında (`/sdcard`) başlar (ilk açılışta depolama izni istenir).
- İndirme: `UYAP-Editor-v3.20.1.apk`, `CanEditor-v3.20.1.apk`.

## 🌟 v3.20.0: 🏛️ UYAP Editör artık AYRI uygulama (UYAP-Editor-v3.20.0.apk)

- Bazı telefonların "Şununla aç" penceresi aynı uygulamanın iki ekranını tek simgede birleştirdiği için .udf açılırken yalnızca
  CanEditor görünüyordu. Resmi UYAP Doküman Editörü (Java 14, Termux/X11'siz) artık **ayrı bir uygulama**:
  **UYAP Editör** (paket `com.agy.uyapeditor`, kırmızı belge simgesi). İki uygulama yan yana kurulur ve "Şununla aç"
  penceresinde ayrı ayrı görünür; hangisi "Her zaman" seçilirse .udf/.usf dosyaları onunla açılır.
- **İndirme:** `UYAP-Editor-v3.20.0.apk` (≈42 MB) — `CanEditor-v3.20.0.apk` ≈45 MB'a küçüldü.
- CanEditor'daki "🏛️ Orijinal UYAP Editör'de aç" belgeyi UYAP Editör uygulamasına gönderir (kurulu değilse indirme sayfasını önerir).
- Not: UYAP Editör ayrı uygulama olduğu için resmi editör (rayp.adalet.gov.tr) ilk açılışta bir kez yeniden indirilir.

## 🌟 v3.19.1: UYAP Editör ekranına dokununca çökme giderildi

- Telefonda resmi UYAP Editör (Java 14) açıldı; ancak ekrana ilk dokunuşta CanEditor kapanıyordu: dokunma komutları
  editöre giden yerel sokete ana (arayüz) iş parçacığında yazılıyordu (Android: NetworkOnMainThreadException).
  Komutlar artık kuyruğa alınıp ayrı iş parçacığında sırayla gönderilir.
- Çökme sonrası arkada kalan eski Java süreci bir sonraki açılışta kapatılır (bellek boşa gitmez).
- Varsayılan ölçek büyütüldü (kısa kenar 820 px); Menü > Ekran ölçeği 5 kademe. İlk açılışta kısa kullanım ipucu.
- UYAP Editör ekranına çökme kaydı eklendi (İndirilenler/com.agy.uyapacici_crash.log).

## 🌟 v3.19.0: 🏛️ Orijinal UYAP Editör — telefonda Termux / X11 / Termux:API OLMADAN, dokunmatik

CanEditor'un yanına **"UYAP Editör"** adlı ikinci bir simge gelir: resmi **UYAP Doküman Editörü 5.4.20**'nin kendisi,
UYAP'ın desteklediği **Java 14.0.2** ile telefonda çalışır. Belge görünümü, PDF ve UDF çıktısı masaüstündeki UYAP Editör ile
birebir aynıdır (aynı program).

- **.udf / .usf her yerden açılır:** dosya yöneticisi, WhatsApp, Celse, tarayıcı, e-posta → "Birlikte aç" → **UYAP Editör**
  ("Her zaman" ile varsayılan yapılabilir). Kaydedince belge geldiği yere (yazılabiliyorsa) ya da İndirilenler/UYAP'a yazılır.
- **Dokunmatik:** dokun = tıkla · çift dokun = çift tıkla · uzun bas = sağ tık · tek parmak = kaydır (ivmeli) ·
  🖱 kipinde sürükleyerek seç · iki parmak = yakınlaştır / kaydır · fare, kalem ve donanım klavyesi desteklenir.
- **Kendi klavye çubuğu:** ⌨ (klavye) · Esc · Tab · Ctrl · Alt · ⇧ (yapışkan) · oklar · Home/End · Del · 💾 Kaydet ·
  ↶ Geri al · ↷ Yinele · 📋 Yapıştır (Android panosu) · ⤢ Sığdır · ⋮ Menü. Editörde kopyalanan metin Android panosuna geçer.
- **Ölçek:** kısa kenar ~900 px (şerit menü ve A4 sayfa sığar); Menü > Ekran ölçeği ile Büyük/Orta/Küçük.
- **Yazı tipleri:** Times New Roman / Arial / Courier New yerine ölçüleri birebir aynı Liberation yazı tipleri (satır ve sayfa
  kırılımları değişmez). Menü > Yazı tipi ekle ile kendi (ör. Windows'taki gerçek Times New Roman) TTF dosyalarınızı ekleyebilirsiniz.
- **Resmi editör dağıtılmaz:** ilk açılışta yalnızca rayp.adalet.gov.tr'den indirilir (ya da elinizdeki uyapeditor_*.zip/.deb seçilir).
- **CanEditor'da "🏛️ Orijinal UYAP Editör'de aç"** (Dosya menüsü / mobil menü): açık belge resmi editörde açılır.
  Masaüstünde bilgisayarda kurulu UYAP Editör (resmi, uyap-editor-modern) bulunur; yoksa resmi editör jar'ları
  (rayp.adalet.gov.tr) ve resmi OpenJDK 14.0.2 (download.java.net, SHA-256 doğrulamalı) bir kez kurulup belge açılır.

**Nasıl çalışıyor (teknik):** Termux glibc deposunun Android için derlenmiş glibc'si + resmi AdoptOpenJDK 14.0.2 aarch64
(jlink, Nashorn dahil) uygulama içinde; `libjvm.so`'yu doğrudan yükleyen küçük başlatıcı (`uyapjava`, JNI_CreateJavaVM) glibc
bağlayıcısıyla çalıştırılır. X sunucusu yoktur: Caciocavallo 1.11.1 (JDK 14 için `CTCGraphicsConfiguration` ve
`getLockingKeyState` yamalı) pencereleri bellekte çizer; köprü ajanı ekranı değişen satırlarla paylaşılan belleğe yazar,
dokunma/klavye olaylarını editöre iletir. uyap-editor-modern ajanı (akıcı kaydırma, PDF yazı tipi düzeltmesi) dahildir;
lisans denetimine dokunan sınıflar alınmamıştır. Doğrulama: x86 ve aarch64 (qemu) üzerinde resmi editör açıldı, Türkçe yazı,
Enter, tıklama, belge açma ve dikey 900×1600 ekran denendi.

## 🌟 v3.18.8: Windows'ta ArkSigner (Türkçe adlı okuyucular) görünür

- **Neden görünmüyordu:** Windows ArkSigner'ı kendi sürücüsüyle tanıyor (VID 33B6 / PID 0001, "Microsoft Usbccid Akıllı
  Kart Okuyucusu (WUDF)"), ama okuyucu adında Türkçe "ı" var. JDK'nın Windows PC/SC katmanı ANSI işlevlerini
  (SCardListReadersA/SCardConnectA) çağırıp adları UTF-8'miş gibi çeviriyor; Türkçe karakterli ad bozuluyor ve okuyucu
  açılamıyordu. ACR39'un adı ASCII olduğu için o çalışıyordu.
- **Çözüm:** CanEditor'un Adalet E-İmza'ya verdiği `eimza-win-agent.jar` (Unicode PC/SC sağlayıcısı) Windows'un Unicode
  işlevlerini (…W) JNA ile çağırır; JDK sağlayıcısının davranışı (T=0 GET RESPONSE, 6Cxx, hata metinleri) birebir korunur.
  Kart tarayan alt süreçler de `JAVA_TOOL_OPTIONS` ile aynı sağlayıcıyı kullanır. Birden fazla okuyucu birlikte çalışır.
- 3.18.7'nin arka planda bıraktığı eski Adalet süreci (yalnızca CanEditor'un kendi başlattığı) yeni ayarlarla yeniden başlatılır.
- Test: pcscd + sanal okuyucu "Sanal Akıllı Kart Okuyucusu" ile resmi Adalet 1.0.17 (ana süreç + kart tarama süreci)
  okuyucuyu Türkçe adıyla listeledi ve ATR'yi okudu; bağlanma/komut/özel erişim/kart çıkarma JDK ile aynı sonucu verdi.

## 🌟 v3.18.7: Windows'ta sürücüsüz e-imza (ArkSigner, ACR39 + AKİS kart)

- **Kart sürücüsü ve Java GEREKMEZ:** Windows kurulum paketine Java 21 gömülüdür (CI'da jlink). Kart, CanEditor'un
  arka planda çalıştırdığı resmi Adalet E-İmza ile okunur. PKCS#11 kütüphanesi (akisp11.dll vb.) bulunmayınca resmi
  uygulama kartla doğrudan APDU ile konuşur; okuyucuya Windows'un kendi PC/SC katmanı ve CCID sürücüsüyle ulaşılır.
- **İlk kullanım:** "Kartı Tara"da resmi Adalet E-İmza bir kez ve yalnızca cdn.uyap.gov.tr'den kendiliğinden indirilip
  kurulur (~80 MB). Sonraki açılışlarda doğrudan başlar. Bilgisayarda resmi uygulama zaten çalışıyorsa o kullanılır.
- Servis 127.0.0.1:5975'te çalışır; Chrome'daki UYAP portallarına e-imzayla giriş de aynı servisle yapılır.
- Kart bulunamazsa kurulu PKCS#11 sürücüsü (AKİS/SafeNet) yine denenir.
- Android ve masaüstü aynı imza kodunu kullanır (`adaletIstek`, `adaletSertifikalari`).

## 🌟 v3.18.6: İmzalı belgede "Kaydet" imzaları korur, yeniden imzalama ek imza olarak eklenir

**Kural:** İmzalı bir UDF değiştirilmeden kaydedilirse ya da yeniden imzalanırsa önceki imzaların hiçbiri kaybolmaz.
- **Kaydet = Farklı Kaydet:** İmzalı ve değiştirilmemiş belgede ikisi de belgeyi yeniden üretmez, orijinal baytları aynen
  yazar. Android'de "Kaydet" eskiden belgeyi yeniden oluşturup TÜM imzaları siliyordu (belge editör içinden açıldığında
  açık dosya bilgisi boş kalıyordu); "Farklı Kaydet" koruyordu. Artık her iki yol (üst çubuk ve menü) aynı kontrolü kullanır.
- **Ek imza:** Değiştirilmemiş imzalı belge yeniden imzalanınca yeni imza öncekilere EKLENİR (3 imza + sizin imzanız = 4).
  Adalet E-İmza, mobil imza ve doğrudan kart yollarında sonuç doğrulanır: önceki imzacıların hepsi + 1 yoksa belge kaydedilmez.
- Belge değiştirildiyse önceki imzalar hukuken geçersiz olacağından ek imza yine engellenir (uyarı verilir).
- Test: 3 gerçek imzalı UDF'ye test sertifikasıyla imza eklendi → imzacı sayısı N→N+1, content.xml bayt bayt aynı, tüm imzalar geçerli.

## 🌟 v3.18.5: Gömülü Java telefonda açılmıyordu (libc++_shared.so eksikti)

- Telefon günlüğü: `dlopen failed: library "libc++_shared.so" not found: needed by .../libandroid-spawn.so` → Java
  sanal makinesi hiç başlamıyor, Adalet E-İmza hiç açılmıyordu (önceki sürümlerdeki "okuyucu var kart yok" belirtilerinin
  temel nedeni). Termux `libc++` paketi JRE'ye eklendi.
- `scripts/jre_hazirla.py` artık elle yazılmış listeye güvenmez: JRE'deki TÜM ELF dosyalarının bağımlılıklarını (DT_NEEDED)
  `readelf` ile özyinelemeli tarar, eksikleri Termux önekinden kopyalar; çözülemeyen bağımlılık kalırsa derleme durur.

## 🌟 v3.18.4: Termux'ta çalışan e-imza köprüsüyle birebir davranış

Termux v3 kitindeki (ACR39 ve ArkSigner ile çalışan) `ccid_bridge.py` ile Android köprüsü satır satır karşılaştırıldı:
- **Kart gücü 3 sn gecikmeli kesilir:** Adalet E-İmza 1.0.17 kartı ayrı bir "probe" Java sürecinde tarar, hemen ardından
  ana süreç bağlanır. Köprü son bağlantı kapanır kapanmaz kartın gücünü kesiyordu; kart sıfırlanıyor, PIN doğrulanmış
  oturum düşüyordu. Artık Termux köprüsü gibi 3 sn beklenir; bu sürede yeni bağlantı gelirse kart açık kalır.
- **Kart tarayan alt Java süreci:** ev/geçici klasör, bellek sınırı ve (tanı açıkken) DEBUG günlüğü `JAVA_TOOL_OPTIONS`
  ile alt sürece de geçer (Termux Java'sının varsayılan geçici klasörü bu uygulamaya kapalıdır).
- Tanı günlüğüne köprü istemcilerinin bağlanma/ayrılma ve kart gücünün kesilme anları eklendi.
- Doğrulama: Termux kitinin donanımsız kart simülatörü (`ccid_bridge.py --sim`) ile resmi Adalet E-İmza 1.0.17 +
  UdeMobile ajanı uçtan uca denendi: okuyucu listelendi, kart bağlandı, APDU yolu çalıştı.

## 🌟 v3.18.3: 🐞 E-imza tanı günlüğü

Ana ekran ya da 🏛️ Adalet E-İmza ekranı > **🔴 Tanı günlüğünü BAŞLAT** → sorunu yaşayın → **⏹ DURDUR ve gönder**.
Günlük (İndirilenler/CanEditor/tani/eimza_tani_*.log) şunları yazar: cihaz/Android/izinler, USB cihazları (VID/PID,
sınıf, arayüz, uç noktalar, izin, köprüye uygun mu), Java'nın çıkarılması ve başlatma komutu, resmi Adalet E-İmza'nın
ayrıntılı (DEBUG) çıktısı, köprüye gelen her komut (INFO/STATUS/CONNECT/TRANSMIT: APDU başlığı, uzunluk, SW), CCID
okuyucu özellikleri/ATR/hata baytları, PIN penceresi (PIN'in kendisi değil), editördeki e-imza adımları, çökmeler.
**PIN, APDU verisi ve belge içeriği yazılmaz.**

## 🌟 v3.18.2 (düzeltme)

- **Adalet E-İmza ekranı açılır açılmaz kapanıyordu:** durum satırı servisi (127.0.0.1:5975) ana iş parçacığından
  yokluyordu; Android buna izin vermez. Denetim arka plana alındı.
- Kurulum sorusu artık tarayıcı onay kutusu ("file:// adresindeki sayfa...") yerine Android penceresiyle sorulur.

## 🌟 v3.18.1 ile Gelenler (E-imza kartı: yalnızca resmi Adalet E-İmza)

1. **Uydurma sertifika kaldırıldı:** Eski tahmini USB sürücüsü kartı okuyamayınca "Nitelikli Elektronik Sertifika /
   NES-… / 31.12.2028" gibi uydurma değerlerle "kart aktif" gösteriyordu; PIN girilince "kart bulunamadı" çıkıyordu.
   Android'de kart artık **yalnızca resmi Adalet E-İmza** ile okunur ve imzalanır; okunamazsa açıkça söylenir.
2. **"CanEditor yanıt vermiyor" donması giderildi:** USB işlemleri ana iş parçacığında yapılıyordu.
3. Adalet E-İmza kurulu değilse e-imza penceresi kurulum ekranını önerir; kapalıysa kendisi başlatıp bekler.
4. Üreticiye özel USB sınıfıyla görünen tokenlar (ör. ArkSigner) köprüde tanınır; izin penceresi her takılışta bir kez.
5. Termux çağrıları tamamen kaldırıldı (editör artık Termux betiklerini çalıştırmaz).

## 🌟 v3.18.0 ile Gelenler (Termux'suz Adalet E-İmza)

1. **Adalet E-İmza artık UdeMobile'ın içinde (Android, Termux gerekmez):** Chrome'dan UYAP Avukat Portalı'na
   e-imza ile giriş ve imzalama için gereken **resmi Adalet E-İmza** uygulaması, APK'nın içindeki **Java 21** ile
   telefonda çalışır (`127.0.0.1:5975`, resmi uygulamadakiyle aynı adres). Ana ekran > **🏛️ Adalet E-İmza** >
   **Resmi uygulamayı indir** (Adalet'in sunucusundan, cdn.uyap.gov.tr; UdeMobile resmi uygulamayı dağıtmaz).
2. **USB e-imza okuyucu köprüsü (Termux'suz):** Okuyucu OTG ile takılır; kart, resmi uygulamaya UdeMobile'ın USB CCID
   köprüsünden görünür (APDU ve TPDU/T=1 okuyucular). Kart komutlarını resmi uygulamanın TÜBİTAK kütüphanesi gönderir.
3. **PIN penceresi:** Sayfa PIN'i sormazsa Android penceresi açılır (ekran görüntüsü alınamaz, PIN kaydedilmez).
4. **Editörde kartla imza** Android'de önce resmi Adalet E-İmza servisiyle (signUdf) yapılır; dönen imza belgeyle
   doğrulanmadan kaydedilmez. Servis kapalıysa eski doğrudan USB yolu kullanılır.
5. Ekran yok: resmi uygulamanın Swing pencereleri Caciocavallo ile bellekte çizilir; Android sistem kök sertifikaları
   Java güven deposuna eklenir (Adalet sunucularına HTTPS).
6. Android hedef SDK 28 (gömülü Java uygulama klasöründen çalışabilsin; Termux da 28 hedefler). APK ~44 MB.

> **Bilinen sınırlar:** Gerçek telefon + gerçek kartla uçtan uca henüz denenmedi (x86 Linux'ta resmi uygulama aynı
> ajan ve yamayla açılıp 5975'te yanıt verdi). AKİS (Kamu SM) kartları beklenir; üretici PKCS#11 sürücüsü isteyen
> bazı SafeNet/ArkSigner tokenlar Android'de çalışmayabilir.

## 🌟 v3.17.1 ile Gelenler (Mobil İmza Düzeltmesi)

1. **Mobil imza "imza belgenin içeriğiyle eşleşmiyor" hatası:** UYAP mobil imza servisi, bizim isteğimizde imzalanacak
   verinin ilk 100 baytını sıfırlanmış olarak imzalıyordu; belge (doğru şekilde) kaydedilmiyordu. Havelsan Doküman
   Editörü'nün (Apache Axis 1.3) isteği sahte bir sunucuyla yakalanıp karşılaştırıldı: gönderilen veri aynıydı, fark
   SOAP başlıklarındaydı (`SOAPAction` boş gidiyordu, ad alanı önekliydi, Axis'in `Accept`/`User-Agent` başlıkları
   yoktu). İstek artık Havelsan'ınkiyle **bayt bayt aynı** (Android, Windows, macOS, Linux).
2. **Ayrıntılı teşhis dosyası:** Mobil imza yine eşleşmezse belge kaydedilmez ve İndirilenler'e
   `mobil_imza_tani_*.json` yazılır (gönderilen veri, sunucudan dönen imza, fark özeti) — geliştiriciye gönderilebilir.
3. Önceki imzalar korunur; yeni imza belgeyle doğrulanmadan asla kaydedilmez.

## 🌟 v3.17.0 ile Gelenler (Kaydırırken Geri Sekme, Gerçek UYAP ile Sayfa Uyumu, Tutarı Yazıyla)

Bu sürümdeki sayfalama düzeltmeleri, 9 gerçek UDF'nin **gerçek UYAP Editör** (durum çubuğundaki "Sayfa : x / N"
ve paragraf ölçüleri) ve Havelsan PDF çıktılarıyla birebir karşılaştırılmasıyla bulundu.

| Belge | UYAP | v3.16.0 | v3.17.0 |
|---|---|---|---|
| Fezleke (uzun, karekodlu) | 143 | 179 | 142 |
| Fezleke (uzun, karekodlu) | 145 | 181 | 145 |
| İtirazın iptali dilekçesi | 5 | 6 | 5 |
| Diğer 6 belge | 1, 2, 5, 12, 18 … | aynı | aynı |

- **Kaydırırken imlece geri sekme düzeltildi:** Belge açıkken kendi kendini tetikleyen yeniden sayfalama döngüsü
  her ~80 ms'de imleci görünür yapmaya çalışıyor, tablette kaydırınca sayfa imlecin olduğu yere geri sıçrıyordu.
  Artık imleç yalnızca **yazarken** takip edilir; boşta sayfalama 0 kez çalışır.
- **Sayfa altlarında boş kalan alan:** Bölünen paragrafın devamı birleşince arada kalan boş sayfa, sonraki tüm
  sayfaların toparlanmasını durduruyordu (uzun belgelerde 30+ fazla sayfa).
- **Satır yükseklikleri:** paragraf sonundaki büyük puntolu satır sonu artık yalnızca son satırı büyütür;
  sekmeli satırlar 1.5 pt uzamaz; karekodlu altbilgide gövde Havelsan gibi 51 satır alır;
  "Dialog" yazı tipi Windows'taki UYAP gibi Arial ile çizilir.
- **Yeni: Tutarı Yazıyla** (Ekle menüsü ve mobil menü): seçili ya da girilen tutarı
  `1.250.000,50 TL (Birmilyonikiyüzellibin Türk Lirası Elli Kuruş)` biçiminde yazar.

## 🌟 v3.16.0 ile Gelenler (Havelsan ile Sayfa Uyumu, Cetvel, E-İmza Takınca Donma, Mobil İmza Doğrulaması)

Sayfa düzeni, cihazdaki 13 gerçek UYAP belgesinin **Havelsan UYAP Editörü'nün kendi çevrim motoruyla** üretilen PDF'leriyle sayfa sayfa karşılaştırılarak ayarlandı.

1. **Satır aralığı Havelsan ile aynı:** Havelsan (Java Swing) satır yüksekliğini tam sayıya yuvarlar ve `LineSpacing` payını satır yüksekliğinin tam sayı katı olarak ekler. Eskiden `1 + LineSpacing` oranı kullanılıyordu ve 12 pt'lik satırlar 16 pt yerine 14 pt çıkıyordu; bu yüzden sayfalar kayıyordu. Aynı satırdaki farklı puntolar artık satırı büyütmüyor.
2. **Paragraf boşlukları toplanıyor:** Havelsan önceki paragrafın alt boşluğu ile sonrakinin üst boşluğunu toplar. Tarayıcı ise bunları çakıştırıyordu; her paragraf geçişinde birkaç punto kayıyordu.
3. **Altbilgi, karekod ve sayfa numarası:** Sayfa numarası UDF'deki biçimle yazılıyor ("1/2", "Sayfa:1/10"; Arial 11). Karekod Havelsan boyutunda (51 pt) ve sağ altta; doğrulama metni çizginin altında. Logolu altbilgide logo, sayfa numarası ve karekod aynı satırda. Gövdenin alt sınırı gerçek altbilgi yüksekliğine göre hesaplanıyor; eski formül alt kenar boşluğu geniş belgelerde 1. sayfayı ~40 pt erken kesiyordu.
4. **Sayfa sonunda paragraf bölme:** Sonraki sayfadan geri çekilen paragraf, sığan satırları kadar bölünüyor. Belge sonundaki boş satırlar yeni sayfa açmıyor.
5. **Cetvel:** Asılı girinti üçgeni sol girinti dikdörtgeninin altında kalıp kullanılamıyordu. Artık ▼ ilk satır, ▲ asılı girinti ve ▭ tüm paragraf ayrı ayrı tutulup sürüklenebiliyor.
6. **Android: e-imza takınca yeni pencere ve donma giderildi:** Editör ekranı her USB takılışında yeni bir kopyasını açıyordu (`USB_DEVICE_ATTACHED` filtresi). Kaldırıldı; editör tek örnek çalışıyor.
7. **Android: USB izin sonucu artık alınıyor:** Android 14'te izin/tak-çıkar alıcısı bayraksız kaydedildiği için sessizce başarısız oluyordu. İzin `PendingIntent`'i de değiştirilemez (immutable) olduğundan sistem sonucu yazamıyordu. İkisi düzeltildi ve izin penceresinin tekrar tekrar açılması önlendi.
8. **Mobil imza:** UYAP'tan gelen içerik gömülü imza Havelsan gibi ayrılıyor (`detachContent`). İmza belgeyle doğrulanmadan **asla kaydedilmiyor**; eşleşmezse ayrıntılı tanı veriliyor.

> **Bilinen sınırlar:** Android'de USB akıllı kartla (AKİS, ArkSigner) imza, kartın kendine özgü komut setini gerektirir ve henüz gerçek kartla doğrulanmadı; Android'de **mobil imza**, masaüstünde **kart ile e-imza** (PKCS#11) önerilir. Çok sayfalı belgelerde bazı sayfa sonları Havelsan'dan hâlâ ±1 satır farklı olabilir.

## 🌟 v3.15.0 ile Gelenler (Arayüz Hataları, Canlı Sayfalama, Tüm Platformlarda Gerçek E-İmza / Mobil İmza, Yeni PDF·TIFF·ODT Motoru)

Tüm düzeltmeler otomatik tarayıcı testleriyle (masaüstü + mobil dokunmatik) ve **Havelsan UYAP Doküman Editörü 5.4.20** ile karşılaştırılarak doğrulanmıştır.

**Arayüz**
1. **Menüler artık üst üste binmiyor:** "Dosya > Yeni / Aç / Kaydet" öğeleri biçim çubuğunun ve cetvelin altında kalıp tıklanamıyordu (katman/z-index hatası). Menü çubuğu en üst katmana alındı.
2. **Alt menüler açılıyor:** "Farklı Kaydet / Paylaş / Yazdır" alt menüleri bir kez tıklandıktan sonra bir daha hiç açılmıyordu. Düzeltildi; dokunmatik ekranda tıklayınca açılır.
3. **Masaüstü kendini Android sanıyordu:** Masaüstü/Web sürümü sahte bir Android köprüsü yüzünden Android gibi davranıyordu (paylaşım, alt çubuk). Düzeltildi.
4. **Cetvel rakamları ("8 17 9") üst üste binmiyor**, dar ekranda alt durum çubuğu yüzen düğmenin üstüne çıkmıyor.
5. **Dosya > Yeni** artık gerçekten yeni belge açar (Ctrl+N); kaydedilmemiş değişiklik varsa sorar. Yeni belgede görünmeyen örnek üst bilgi UDF'ye yazılmıyor.

**Sayfalama ve kaydırma (Word gibi)**
6. **Yazarken yeni sayfa açılıyor:** Eskiden 1. sayfa dolunca yazılan metin gizleniyor, belge "tek sayfa" kalıyor ve aşağı kaydırılamıyordu. Yeni canlı sayfa akışı taşan paragrafları sonraki sayfaya taşır, gerekirse yeni sayfa açar, silince geri çeker; imleç ve Android klavyesi korunur.
7. **Sayfalar arası düzenleme:** Sayfa başında Backspace önceki sayfayla birleştirir, sayfa sonunda Delete sonraki sayfayı çeker; ↑ ↓ PageUp PageDown sayfalar arasında geçer.

**Biçimlendirme / kaydetme / dönüştürme**
8. **Punto ve yazı tipi:** Seçim yokken punto değiştirmek TÜM belgenin puntosunu değiştiriyordu; artık Word gibi imleçten sonra yazılacak metne uygulanır.
9. **PDF baştan yazıldı:** Ekrandaki sayfanın birebir yerleşiminden **vektör PDF** (seçilebilir/aranabilir Türkçe metin, gömülü Times New Roman/Arial, sekme hizaları, tablo çizgileri, logo ve UYAP karekodu). Dosya boyutu ~8 kat küçüldü.
10. **TIFF:** Aynı yerleşimden 192 DPI, gri tonlamalı, PackBits sıkıştırmalı çok sayfalı TIFF (eskisi sıkıştırmasız ve ~7 kat büyüktü).
11. **ODT yazma/okuma yeniden yazıldı:** Sekmeler, sekme durakları, girintiler, satır aralığı, punto/renk, tablolar, görseller, üst/alt bilgi ve kenar boşlukları korunuyor (eskisi hepsini kaybediyordu). DOCX okurken punto/renk/yazı tipi de alınıyor.
12. **Masaüstünde Kaydet gerçekten kaydediyor:** Tauri (Windows/macOS/Linux) içinde indirme bağlantısı çalışmadığından kaydetme sessizce başarısız oluyordu. Artık yerel "Aç / Kaydet / Farklı Kaydet" pencereleri kullanılır, "Kaydet" açık dosyanın üzerine yazar.

**E-İmza ve Mobil İmza — tüm platformlarda tek motor**
13. **Mobil imza artık çalışıyor (Android + Windows + macOS + Linux):** UYAP mobil imza servisi (`vatandas.uyap.gov.tr/mimzaclient`) Havelsan editörüyle birebir aynı biçimde çağrılır. Eski Android sürümü telefon numarasının başındaki 0'ı siliyor ve SOAP alan adlarını yanlış gönderiyordu. Termux/yerel sunucu gerekmez.
14. **Akıllı kart e-imza (masaüstü):** PKCS#11 ile AKİS (Kamu SM, TürkTrust, E-Güven), SafeNet/eToken (E-Tuğra, e-imzaTR), SafeSign, CardOS, Gemalto/Thales, ArkSigner, OpenSC sürücüleri işletim sistemine göre otomatik bulunur. Sürücü yoksa uygulama resmi indirme bağlantılarını gösterir. Özel sürücü yolu için `CANEDITOR_PKCS11` ortam değişkeni kullanılabilir.
15. **Akıllı kart e-imza (Android):** USB OTG CCID okuyucu ile, Termux olmadan.
16. **UYAP uyumlu imza:** CAdES-BES (contentType, signingTime, messageDigest, signingCertificateV2), sha256WithRSA / ECDSA; mevcut imzalar korunarak paralel imza eklenir. Üretilen imzalar TÜBİTAK ESYA kütüphanesiyle `TYPE_BES, özet doğrulaması başarılı` olarak doğrulandı; mahkeme imzalı belgelere eklenen imzalarda önceki imzalar geçerli kalır.
17. **İmzayı Doğrula** her platformda yerel kriptografik doğrulama yapar (özet + imza; RSA ve ECDSA).

> Not: E-imza kartı sürücüleri (AKİS vb.) üreticilerine ait lisanslı yazılımlar olduğundan uygulamanın içine gömülemez; uygulama kurulu sürücüyü otomatik bulur, yoksa resmi indirme adresine yönlendirir. Web (taşınabilir zip) sürümünde tarayıcı güvenlik kısıtları nedeniyle e-imza/mobil imza yapılamaz; masaüstü veya Android uygulamasını kullanın.

## 🌟 v3.14.0 ile Gelenler (Havelsan UYAP ile Birebir Uyum, Tek Motor, Yeni Arayüz)

Tüm iyileştirmeler, gerçek UYAP belgeleri (27 UDF) Havelsan'ın kendi çevrim motoruyla üretilen referans PDF'lerle karşılaştırılarak doğrulanmıştır.

1. **UYAP şablon belgeleri doğru açılıyor:** Takip Talebi, Portal evrakı gibi alanlı (`<data>`) belgelerde alacaklı/borçlu/vekil grupları, tekrar eden alacak satırları ve `eol`/`ceol` satır sonları Havelsan kurallarıyla çözülür. Metin uyumu %70 → %99,4.
2. **Kaydederken biçim kaybı yok:** Paragraf, tablo, satır ve hücrelerin tüm orijinal öznitelikleri (sekme hizaları, satır bazlı sütun genişlikleri, stiller, sayfa ayarları, üst/altbilgi ayarları, doğrulama kodu) korunur; yalnızca değiştirdiğiniz yerler yeniden yazılır. Kaydedilen 27 belgenin tamamı Havelsan'da aynı sayfa sayısıyla açılır.
3. **Sekmeler Havelsan ile aynı:** Ardışık sekmelerin teke inmesi giderildi; sekme yerleşimi Java Swing kuralıyla birebir (T.C. … BERAAT başlıkları, "BAŞKAN : …" hizaları).
4. **Doğru sayfalama:** Altbilgi payı hesaba katılır, tablolar satır sınırından bölünür, küçük puntolu metinde satır yüksekliği doğru hesaplanır; sayfa sınırında bölünen paragraflar kayıtta tek paragraf kalır.
5. **Mobil ve masaüstü tek motor:** Android artık UDF'yi masaüstüyle aynı motorla açar ve kaydeder; iki platformda çıktı aynıdır.
6. **Yeni arayüz:** UYAP Doküman Editörü ile aynı menü çubuğu (Dosya, Düzen, Görünüm, Ekle, Biçim, Araçlar, İmza) ve tek satırlık modern biçim çubuğu; mobilde tek satır, yana kayan, parmakla kolay basılan düğmeler; gerçek renk seçici.

## 🌟 v3.13.0 ile Gelen Devrimsel Yenilikler (Orijinal Havelsan UYAP Headless Çevrim Motoru, iText Vektörel PDF, ODFDOM ODT & CLI Desteği)

1. **Orijinal Havelsan UYAP Headless Çevrim Motoru Entegrasyonu:**
   * Orijinal UYAP Editör JAR'ları tersine mühendislikle decompile edilerek `tr.com.havelsan.uyap.system.editor.b.b` (vektörel iText PDF) ve `tr.com.havelsan.uyap.system.editor.b.a.f` (ODFDOM ODT) motorları headless olarak CanEditor'e bağlandı.
   * `scripts/HavelsanConverter.java` ve tek tıkla çalışan `scripts/havelsan-convert` CLI aracı projeye eklendi.
   * CanEditor içinden "Farklı Kaydet" veya "Paylaş" yapıldığında yerel 5976 portu üzerinden 1:1 orijinal UYAP kalitesinde PDF, ODT ve DOCX çıktısı alınması sağlandı.
2. **1:1 editor.e-udf.com Mobil Tasarım ve Ergonomi:**
   * Üst yuvarlak hap (pill) kapsülü: `[ 💾 Kaydet | 📱 Görünüm Değiştir | ☰ Tüm Menü ]`.
   * Alt araç çubuğu: Girinti, Geri Al, Yinele, Yazı Tipi ve Punto kontrolleri.
3. **Kalıcı Sticky Cetvel:**
   * Sayfa aşağı kaysa da üst panelin hemen altında daima sabit kalan `-2 ... +18cm` ölçekli cetvel.
4. **Sıfır Klavye Kapanması (IME Focus Protection):**
   * Android WebView üzerinde yazı yazarken veya imleç hareket ederken klavyenin aniden kapanmasına yol açan tüm senkron layout ve reflow tetikleyicileri engellendi.
5. **SAF Doğrudan Geri Yazma (1-Tık Kaydet 💾):**
   * WhatsApp veya Dosyalarım'dan açılan dosyalara yapılan değişiklikler `content://` URI'sine doğrudan geri yazılır (`openOutputStream(originDataUri, "wt")`).
6. **Termux Bağımsız USB E-İmza & Görüntüleme:**
   * Yerel `CcidDriver.java` USB Host sürücüsü, 5975 portundaki yerel Adalet e-imza köprüsü ve dahili PDF/TIFF görüntüleyiciler ile Termux gerektirmeyen %100 bağımsız mobil deneyim.

### 🎨 1. e-UDF Birebir Ergonomik Üst Arayüz & Görünüm Modu
- **e-UDF Birebir Kısayol Hapı (`[ 💾 | 📱 / 🖥️ | ☰ ]`):**
  - **💾 1-Tık Doğrudan Kaydet:** Açık olan belge üzerinde yapılan tüm değişiklikleri anında açık olan dosyaya veya `Downloads/UYAP_Belgelerim` klasörüne kaydeder.
  - **📱 / 🖥️ Görünüm Değiştir:** Kağıt baskı düzenindeyken `📱` gösterir (tek dokunuşla mobil akışa geçer), mobil akıştayken `🖥️` gösterir (tek dokunuşla gerçek A4 kağıt baskı düzenine döner).
  - **☰ Çekmece Menüsü:** Dosya açma, Farklı Kaydet (UDF, PDF, DOCX, TIFF, ODT), Paylaş, Yazdır, E-İmza ve Ayarlar seçeneklerine tek tıkla erişim.
- **e-UDF Stili Kompakt İkinci Araç Şeridi:** `⇥` Sekme (Tab), `↶` Geri Al, `↷` Yinele, `Times New Roman ▾`, `12 ▾` Punto, `B`, `I`, `U`, `A` renk seçici ve sağ başta kırmızı `⌵` genişletme oku.
- **Göz Yormayan Açık Gri Kağıt Zemini:** e-UDF ve modern ofis paketleri standardında `#F1F5F9` zemin üzerinde keskin beyaz A4 kağıt sunumu.

### ⚡ 2. DOM Yıkımsız Kesintisiz Mobil Akış (Sıfır İçerik ve Biçim Kaybı)
- **DOM Ağacının Korunması (`mobile-reflow-active`):** Mobil görünüme geçildiğinde veya kağıt görünümüne dönüldüğünde sayfalar artık `innerHTML = ''` ile silinmez. Tüm mahkeme başlıkları, esas/karar numaraları, üstbilgiler, altbilgiler, karekodlar ve imzalar %100 korunarak ekrana tam oturur.
- **Sıfır Marj Sıkışması:** Mobil modda metinlerin ekran kenarlarına yapışması önlendi; 18px okuma ve yazma boşluğuyla konforlu akış sağlandı.

### ⌨️ 3. Kesin Klavye Odak Koruması (Yazarken Klavyenin Kapanması Engellendi)
- **Yazım Anında Sıfır Reflow:** Tıklamalarda ve yazım anında senkronize CSS hesaplaması (`window.getComputedStyle`) yapılarak IME bağlantısının kopması engellendi.
- **Yüzen Menü Sıçraması Önleme:** Yalnızca kullanıcı açıkça bir metin bloğunu seçtiğinde yüzen baloncuk açılır; normal yazım ve imleç tıklamalarında klavyenin kapanmasına sebep olan yüzen menü gizli kalır.

### 💾 4. Farklı Kaydet ve Paylaş Butonlarının %100 Çalışır Hale Getirilmesi
- **Eksik Köprü Fonksiyonları Çözüldü:** `window.getStructuredDocument`, `window.getPlainText`, `window.getHtmlContent` ve `window.setHtmlContent` fonksiyonları global kapsama bağlanarak Farklı Kaydet menüsündeki tüm seçenekler (UDF, PDF, DOCX, TIFF, ODT) ve Paylaş menüsündeki tüm eylemler (WhatsApp, Gmail, Telegram, Samsung Files) anında çalışır hale getirildi.
- **SAF (Storage Access Framework) Doğrudan Geri Yazma:** WhatsApp, Dosyalarım veya buluttan açılan dosyalarda değişiklikler hem doğrudan açılan orijinal `content://` URI hedefine yazılır hem de `Downloads/UYAP_Belgelerim` klasörüne otomatik yedeklenir.

### 📐 5. Kalıcı Çakılı (Sticky) Dokunmatik Cetvel
- **Sayfa Kaydırılsa Dahi Ekranda Sabit:** Sayfa onlarca sayfa aşağı kaydırılsa dahi cetvel toolbar'ın hemen altında ekranın üstünde kalıcı olarak çakılı kalır.
- **-2cm .. +18cm Kesintisiz Ölçek:** Sol kenar marjı (-2 .. 0 cm), aktif yazı alanı (0 .. 16 cm) ve sağ marj (16 .. 18 cm) A4 kağıt genişliğiyle birebir hizalanır. 44px dokunmatik hedeflerle parmakla girinti ayarı yapmak kolaylaştırıldı.

### 📕 6. Dahili PDF ve Çok Sayfalı TIFF/TIF Görüntüleyici
- **PDF.js & UTIF.js Entegrasyonu:** Adli PDF'ler ve çok sayfalı TIFF icra/tarama evrakları CanEditor içinde sayfalı, yakınlaştırmalı (zoom), indirmeli ve paylaşımlı olarak açılır.

### 🛡️ 7. Rootsuz & Termux'suz Yerel USB OTG E-İmza & Adalet Port 5975
- **Android Yerel CCID USB Host Sürücüsü:** SafeNet eToken 5110 (kırmızı token), ArkSigner, ACS ve Akis kartlar doğrudan telefonun Type-C portuna takılarak çalışır.
- **Dahili Adalet Port Sunucusu (Port 5975):** CanEditor içinde çalışan yerel servis sayesinde UYAP Avukat Portal ve yerel e-imza işlemleri Termux gerektirmeden bağımsız çalışır.

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
