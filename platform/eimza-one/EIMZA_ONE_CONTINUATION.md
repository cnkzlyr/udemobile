# E-İmza One — Devam Dokümanı

## 0.3.0 Üçlü Token Desteği (ArkSigner, TÜRKTRUST TBB, Kamu SM) & Detaylı TXT Tanı Checkpoint'i

- **ArkSigner Arkİmza Token Desteği**:
  - `ArkSignerTokenBackend.java` ve `ArkSignerTokenDriver.java` ile ArkSigner tokenları (Feitian ePass2003, CardOS 5, Gemalto/SafeNet IDPrime) için bağımsız ISO 7816-4 / PKCS#15 APDU motoru eklendi.
  - AID (`A000000063504B43532D3135`), EF.Cert (`2F02`, `C001`, `2F04` CDF) taranarak sertifikalar okunur.
  - PIN doğrulama (`00 20`), kalan deneme hakkı sayımı (`63 CX`) ve bloke koruması (`69 83`/`69 84`) sağlandı.
  - PSO CDS (`00 2A 9E 9A`) ile donanımsal dijital imzalama ve açık anahtar ile yerel doğrulama yapıldı.
- **TÜRKTRUST / TBB Kırmızı Token**: SafeNet eToken 5110 donanımı ve TBB AKİS profilleri otomatik tanınıp yönlendirilir.
- **Kamu SM / TÜBİTAK (ATR19)**: Mevcut AKİS CIF V20/V25/Gezgin sürücüleri tam kararlılıkla korundu.
- **Hibrit CCID Ulaşım (`UsbCcidTransport`)**:
  - `dwFeatures` okunarak doğrudan APDU (`LEVEL_SHORT` / `LEVEL_EXT`) ve T=1 TPDU blok seviyeleri otomatik seçilir.
  - `supportsT1` ATR zorlaması kaldırılarak T=0 / doğrudan APDU tokenlarının engellenmesi önlendi.
- **Detaylı Tanı & TXT Export (`DiagnosticLogger`)**:
  - USB cihazı, CCID özellikleri, ATR, seçilen sürücü, sertifika kimlikleri ve olay logları içeren `.txt` debug raporu üretilir.
  - Tek tıkla cihaz hafızasına kaydetme, panoya kopyalama ve Android Paylaşım Menüsü (WhatsApp/E-posta) ile gönderme sağlandı.
- Sürüm: `versionCode 35`, `versionName 0.3.0`.
- Harness: `tests/TokenIdentificationHarness.java` çalıştırılarak doğrulandı.

## 0.2.11 OBS SSO URL checkpoint'i

- 0.2.10 telefon logunda ArkSigner imzası kod=0 döndü ve OBS
  `/Account/SsoLogin?q=...` sayfasına ulaştı; ancak ham `+`, `/`, `=` içeren
  standart-Base64 `q` farklı değerlerle döngüye girdi. Mevcut normalizasyon
  metodu yazılmış fakat navigasyondan hiç çağrılmıyordu.
- Ana/popup `shouldOverrideUrlLoading` ve `onPageStarted` artık ham `q`
  değerini yüzde-kodlu biçime çevirir. Kodlu değer yeniden yazılmaz.
- e-Devlet işlem kodu tarayıcı menüsünden elle de başlatılabilir;
  sonraki testte `e-Devlet ...` tanı satırları ayrıca alınmalıdır.
- Sürüm: `versionCode 24`, `versionName 0.2.11`.

## 0.2.10 OBS/e-Devlet/Reçetem düzeltme checkpoint'i

- OGN ve OGN Portal ArkSigner imzaları için gömülü CAdES zorlanır. 0.2.9
  telefon testindeki `signedMimeLen=3772`, kaybolan attached-CMS kuralını
  gösteriyordu; yeni testte admin tanısı `gömülü=true` yazmalı ve zarf
  uzunluğu içerik boyuna göre artmalıdır.
- `arksigner:open` ana ve popup WebView navigasyonlarında tüketilir; buna ait
  `ERR_UNKNOWN_URL_SCHEME` ana sayfayı hata ekranına çevirmemelidir.
- e-Devlet'in açık tarayıcı sayfası işlem kodu oturumunu kendisi yoklar.
  Başarılı JNLP protokol gönderiminden sonra sayfa yenilenmez, başka URL'ye
  gidilmez ve `sonuc` değeri varsayımsal DOM alanına yazılmaz. Captcha/
  güvenlik kodu alanları işlem kodu algılamasından çıkarılmıştır.
- BouncyCastle algoritma bulucusuna `SHA-256withRSA` yerine desteklenen
  `SHA256withRSA` (EC için `SHA256withECDSA`) verilir.
- Sürüm: `versionCode 23`, `versionName 0.2.10`.

## 0.2.9 e-Devlet/OBS protocol checkpoint'i

- Resmî JNLP incelemesi, başarılı `actionName=imzala` yanıtındaki `sonuc[0]`
  değerinin bir URL parametresi değil, açık e-Devlet sayfasında kullanılacak
  **oturum kodu** olduğunu gösterdi. Uygulama artık `/Giris/gir?oturumKodu=...`
  yoluna gitmez; bu kodu açık sayfadaki görünür oturum-kodu alanına yerleştirir
  ve sayfanın kendi gönderim denetimini çalıştırır.
- `EdevletClient` JNLP form taşımasına eşitlendi: WebView çerezi ve ek HTTP
  başlıkları gönderilmez.
- `EdevletCmsSupport`, JNLP'nin açık signed-attribute profilini üretir:
  `contentType`, `messageDigest`, `SigningCertificate[/V2]`, `DERUTCTime`.
  CMS gönderilmeden önce gömülü içerik ve imza yerelde doğrulanır.
- ArkSigner yalnızca `obs.saglik.gov.tr/Account/SsoLogin` callback yolundan
  dışlanır; OGN'deki imza talep sayfasında çalışmaya devam eder. Böylece OBS'nin
  kendi inline SSO betiğine dokunulmaz.
- Sürüm: `versionCode 22`, `versionName 0.2.9`.
- JS köprü testleri: `node --test tests/*.test.cjs` (geçti). Bu çalışma
  ortamında `javac` ve Gradle wrapper bulunmadığından Android derlemesi Termux
  ortamında yapılmalıdır.

## 0.2.8 AKİS çoklu sürüm checkpoint'i

- ACR39U bir okuyucudur. ArkSigner, UYAP, e-Devlet ve UDF'de aynı
  `UnsupportedVersionException (verify)` görülmesi portal hatası değil ortak
  AKİS kart backend hatasıydı.
- AKİS CIF 3.3.18 bytecode incelemesinde V20, V25 ve Gezgin sınıflarının eski
  login/key-info metotlarının stub olduğu doğrulandı. Bu üç aile artık ortak
  PKCS#15 CDF/PrKDF + PIN ref `0x81` + MSE/PSO yolunu kullanır.
- Özel `javax.smartcardio.ATR` sınıfının tarihsel bayt ofseti ISO 7816 arayüz
  grupları yürünerek hesaplanır; eski sondan kesme ve TA1/TCK karışıklığı
  kaldırıldı.
- `AkisV25Harness` artık V20 ve V25 profillerini; `AtrHarness` çok gruplu ATR
  ayrıştırmasını test eder.
- Sürüm: `versionCode 21`, `versionName 0.2.8`.

## 0.2.7 e-Devlet CMS ve OBS oturum checkpoint'i

- Resmî `elektronik-imza.jar` bytecode'u incelendi. JNLP, indirilen ham veriyi
  Base64'ten çözüp içeriği gömülü CMS olarak imzalıyor ve SHA-256 için
  `SigningCertificateV2`, ayrıca `contentType`, `messageDigest` ve `signingTime`
  özniteliklerini koyuyor. `EdevletCmsSupport.java` bu ayrı profili uygular;
  e-Devlet akışında genel `CadesSupport` kullanılmaz.
- `tests/SigningHarness.java`, e-Devlet CMS içeriğini, matematiksel imzayı ve
  zorunlu öznitelikleri doğrular.
- Sağlık portallarında mobil kimlik gerçek Chromium WebView UA'sıdır; masaüstü
  modu Chromium masaüstü UA kullanır. OBS kök girişinde OBS/OGN çerezleri
  temizlenerek eski OAuth/PKCE bağlamının yeni girişle karışması engellenir.
- Admin logunda `ArkSigner ... CMS: içerik=...; zarf=...; gömülü=true/false`
  satırı portalın gerçekten attached CMS alıp almadığını gösterir.
- Sürüm: `versionCode 20`, `versionName 0.2.7`.

## 0.2.6 giriş ve güvenlik checkpoint'i

- e-Devlet kabul sonrası WebView yenilemesi kaldırıldı; tamamlanan işlem kodu
  beş dakika tekrar işlenmiyor. Sayfanın kendi oturum yoklaması korunuyor.
- OGN/OBS için `isAttached=false` dahil gömülü CAdES zorlanıyor. Test logunda
  `Sağlık SSO CAdES: gömülü içerik modu zorlandı` satırı ve önceki 3772 Base64
  karakterinden farklı/uzun bir `signedMimeLen` beklenmelidir.
- Admin tanısı SSO çerezlerinin yalnız adlarını yazar; değerler loglanmaz.
- Adres otomatik tamamlama ayarı eklendi.
- `usesCleartextTraffic=false`; network security config yalnız localhost ve
  127.0.0.1 için cleartext istisnası taşır. WebView mixed content ve file/content
  erişimleri kapalıdır.
- Sürüm: `versionCode 19`, `versionName 0.2.6`.

## 0.2.5 giriş ve tarayıcı checkpoint'i

- e-Devlet `transId` artık büyük/küçük harfi değiştirilmeden gönderilir. DOM
  algılaması doğrudan gönderim yapmak yerine düzenlenebilir doğrulama penceresi açar.
- OGN/OBS görevi `isAttached` göndermediğinde sağlık SSO için gömülü CAdES
  üretilir. Açıkça gönderilen `isAttached` değeri her zaman önceliklidir.
- Adres geçmişi (200 kayıt), otomatik tamamlama, temizleme ve ayrı adres
  düzenleyicisi eklendi; `about:blank` adres çubuğunda boş gösterilir.
- Sekme yöneticisi önizleme kartları, sekme başına kapatma, sürükleyerek
  sıralama, grup hedefleri ve grup adlandırma içerir.
- GeckoView/Firefox geçiş taslağı `BROWSER_ENGINE_ROADMAP.md` içindedir.
- Sürüm: `versionCode 18`, `versionName 0.2.5`.

## 0.2.3 TSA entegrasyonu

- KamuSM üretim adresi resmî belgelerde `http://zd.kamusm.gov.tr` / TCP 80 olarak doğrulandı; HTTPS/443 kullanılmıyor.
- KamuSM profili projedeki TÜBİTAK ESYA `TSClient` + `TSSettings` ile müşteri numarası/parola kullanır; genel Basic Auth yolundan geçirilmez.
- UYAP/Adalet için kamuya açık ayrı TSA bulunamadı; sağlayıcı seçicide açıkça KamuSM profiline eşlendi.
- Arkİmza zaman damgası sunuyor fakat endpoint/auth ayrıntılarını kamuya açıklamıyor; sözleşmede verilen HTTPS endpoint kullanıcı tarafından giriliyor.
- Yeni logo beyaz e-imza, gri USB ucu ve `eimza-one` yazısından oluşur.

Bu dosya, sonraki çalışmalarda projeyi kaldığı yerden devam ettirmek için kısa
ama teknik kaynak kaydıdır.

## Projenin amacı

Android + USB OTG/CCID okuyucu üzerinde KamuSM/AKİS kartını kullanarak:

- ArkSignerJS 3.0.2 kullanan e-Nabız/Reçetem akışlarını,
- Adalet/UYAP yerel istemci protokolünü,
- kart sertifikası okuma ve imzalamayı,
- UYAP UDF dosyasını açıp detached CAdES-BES imzası üretmeyi

tek uygulamada yürütmek.

AKİS yalnız kart/sertifika katmanıdır; hedef ArkSigner ve Adalet portal
protokolleridir. Gerçek portalda test için telefon, okuyucu ve kart gerekir.

## Destek sınırı

Şu anda desteklenen profil:

| Katman | Durum |
|---|---|
| ArkSigner / Arkİmza Token | Destekli; yerel `ArkSignerTokenBackend` ISO 7816-4/15 APDU ve PKCS#15 sürücüsü gömülü |
| TÜRKTRUST / TBB Kırmızı Token | Destekli; TBB AKİS ve SafeNet profilleri otomatik algılanıp yönlendirilir |
| KamuSM / AKİS (ATR19) | Destekli; TÜBİTAK CIF V20/V25/Gezgin ve T=1 blok katmanı |
| USB CCID Taşıma | Destekli; dwFeatures ile doğrudan APDU ve TPDU (T=1 / T=0) otomatik seçim |
| T=1 & T=0 | Destekli; ATR ve CCID özelliklerine göre otomatik müzakere |
| RSA (2048 / 4096) | Destekli; DigestInfo PKCS#1 v1.5 ve ham RSA |
| EC / ECDSA | Destekli; P-256 eğrisi ve SHA-256 |
| Tanı ve Debug Çıktısı | Destekli; `DiagnosticLogger` ile tek tıkla detaylı sansürlü TXT raporu |

Başka üreticilerin DLL/PKCS#11 dosyalarını tersine mühendislikle Android'e
taşımak hedef değildir. Yasal SDK veya açık APDU/PKCS#11 dokümantasyonu olursa
ayrı `SignerBackend` implementasyonu eklenmelidir.

## Önemli dosyalar

- `app/src/main/java/app/eimza/mobile/MainActivity.java`
  - modern menü, tarayıcı paneli, adres çubuğu, masaüstü modu, yardım, admin
    debugger ve UDF paneli.
- `app/src/main/java/app/eimza/mobile/AkisSignerBackend.java`
  - AndroidCCID oturumu, AKİS sertifika taraması, RSA/EC anahtar seçimi,
    imza ve sertifika ile doğrulama.
- `app/src/main/java/app/eimza/mobile/AkisV25Signing.java`
  - V25 RSA MSE/PSO yolu ve ECC mekanizma çağrısı.
- `app/src/main/java/app/eimza/mobile/CadesSupport.java`
  - ESYA CAdES-BES üretimi; RSA veya ECDSA algoritma adı seçimi.
- `app/src/main/java/app/eimza/mobile/SignerBackend.java`
  - ilerideki provider backend'leri için dar arayüz.
- `app/src/main/assets/arksigner-bridge.js`
  - ArkSigner connector, JSONP, fetch/XHR ve Firefox postMessage emülasyonu.
- `app/src/main/assets/adalet-bridge.js`
  - Adalet localhost `/client/info`, sertifika ve imza isteklerini köprüler.
- `app/src/main/AndroidManifest.xml`
  - internet izni ve geçici olarak `usesCleartextTraffic=true`.

## AKİS imza şeması

RSA ve EC kesinlikle aynı veri yoluna sokulmaz:

```text
RSA payload
  -> SHA-256 DigestInfo
  -> AKİS RSA PSO / native MSE
  -> RSA signature
  -> SHA256withRSA certificate verification

EC payload
  -> CIF Algorithm.ECC + Algorithm.SHA_256
  -> AKİS EC signing mechanism
  -> ASN.1 ECDSA signature
  -> SHA256withECDSA certificate verification
```

`signRawPkcs1` yalnız RSA içindir; EC sertifikasında açık hata döndürmelidir.
`CadesSupport` EC sertifikasında `SIGNATURE_ECDSA_SHA256` seçer.

## AKİS kart uyumluluğu için mevcut önlemler

- T=1 başarısızsa T=0 denenir.
- Sertifika FID taraması ilk iki boş dosyada kesilmez; `0x2F:0x05` ile
  `0x2F:0x7F` arası taranır ve 16 ardışık eksik dosyada durur.
- Opsiyonel X.509 KeyUsage yoksa sertifika reddedilmez.
- `digitalSignature` veya `nonRepudiation/contentCommitment` kullanım biti kabul
  edilir.
- RSA özel anahtarı sertifika modulus eşleşmesiyle seçilir.
- EC özel anahtarı tek EC özel anahtar varsa seçilir; birden fazla EC anahtarda
  belirsiz eşleşme hatası döndürülür.
- İmza sonrasında PIN char array temizlenir ve kart oturumu kapatılır.
- APDU tanılarına komut başlığı/SW yazılabilir; PIN, komut verisi, DER, payload
  ve imza yazılmaz.

Başka AKİS kartı hâlâ çalışmazsa debugger'dan şu sırayla bak:

1. okuyucu görüldü mü,
2. ATR ve protokol bağlantısı T=1/T=0 oldu mu,
3. sertifika listesi kaç adet,
4. seçilen sertifika RSA mı EC mi,
5. `MSE anahtar seçimi`, `PSO imza`, `SW=xxxx` hangi adımda kaldı,
6. sertifika ile private-key eşleşmesi bulunabildi mi.

## Browser ve portal akışları

Not: Önceki konuşmadaki `Fognportal` ifadesi kullanıcı yazım hatasıdır; uygulamaya
eklenecek ayrı bir Fognportal adresi yoktur. Sağlık SSO akışında gerçek hostlar
`obs.saglik.gov.tr`, `ogn.saglik.gov.tr` ve `ognportal.saglik.gov.tr` olarak
kalır.

- Başlangıç sayfası artık `about:blank`; hazır portal butonları kaldırıldı.
- Adres çubuğu şema yoksa `https://` ekler.
- `Masaüstü` seçeneği Android/WebView parçasını masaüstü Firefox/Chromium UA'ya
  çevirip sayfayı yeniler. `openDesktop()` da aynı flag'i kullanır.
- Reçetem dahil tüm adresler aynı tarayıcı panelinden açılabilir.
- WebView içindeki ArkSigner köprüsü, gerçek Firefox eklentisini yüklemeden
  `from-page-script`/`from-firefox-content-script` mesaj yolunu emüle eder.
- Dış tarayıcı düğmesi yalnızca URL'yi ACTION_VIEW ile açar. Dış process'te
  `EimzaNative` bulunmadığı için imza köprüsü henüz dış sekmeye taşınmış değildir.
  Tam destek için sonraki adım kontrollü loopback HTTP bridge'dir; varsayılan
  portlar ArkSigner için 16356/16357, Adalet için 5975'tir.

## UDF akışı

`UYAP UDF` paneli:

1. `ACTION_OPEN_DOCUMENT` ile dosyayı seçer.
2. İlk 16 KB UTF-8 önizleme gösterir.
3. Kart sertifikasını seçtirir ve native PIN dialog açar.
4. ESYA `BaseSignedData` ile detached CAdES-BES üretir.
5. `ACTION_CREATE_DOCUMENT` ile `content.xml + sign.sgn` içeren `<dosya>.udf` kaydeder.

## 2026-10-11 WebView/UDF test notları

- Popup artık ayrı bir WebView olarak tarayıcı panelinde tutuluyor; ArkSigner
  ve Adalet yanıtları aktif WebView'e gönderiliyor.
- Masaüstü modu sabit Linux/Chrome User-Agent, geniş görünüm, yüzde 100 metin
  yakınlaştırması ve ilk ölçek ayarıyla ana sayfaya ve popup'a uygulanıyor.
- Üç nokta menüsünde boş sayfa, masaüstü/mobil geçişi, UDF, yardım, debugger,
  dış tarayıcı ve çerez temizleme seçenekleri var.
- `examples/ornek-test.udf`, `content.xml` içeren açılabilir test ZIP'idir.
  Uygulama bunu önizler; kartla imzaladığında `sign.sgn` içeren yeni `.udf`
  paketi üretir. Sabit örneğin geçerli imzalı olması için gerçek kart özel
  anahtarı gerekir; bu nedenle örnek dosya imzasız test girdisidir.
- OBS testinde `initialize`, kart/sertifika listesi ve `signCAdES_BES` kod=0
  dönüyor. Yeni tanı, redirect sonrası JavaScript hatasının kaynak dosyasını
  ve portal callback istisnasını ayrıntısıyla gösterir; PIN, DER ve imza
  içeriği loglanmaz.

Bu çıktı UDF gövdesini değiştirmez; UDF için detached imza dosyasıdır. UYAP'ın
beklediği özel zarf farklı çıkarsa, sonraki geliştirme `UdfSigner` sınıfında
portalın gerçek formatına göre yapılmalıdır.

## Debugger/admin

Ana menü başlığına yedi kez dokunmak `admin_debug` tercihini açıp kapatır.
Debugger seçeneği yalnız açıkken görünür/erişilebilir. Tanılar bellekte sınırlı
bir tamponda tutulur ve uygulama kapanınca silinir. Üretim sürümünden önce:

- `adminTap`, `debugTrace`, `debugLog` ve Debugger paneli kaldırılabilir veya
  `BuildConfig.DEBUG` ile koşullandırılabilir.
- `traceArk` içeriği payload/sertifika/PIN eklememelidir.

## Test komutları

Kaynak kökünde:

```sh
bash tools/test-signing.sh
bash tools/test-akis-v25.sh
bash tools/test-ccid-transport.sh
bash tools/test-adalet-device-info.sh
bash tools/test-portal-origins.sh
for t in tests/*.test.cjs; do node "$t" || exit 1; done
```

Bu çalışma turunda tüm bu testler geçti. Android SDK/Gradle ve gerçek kart
olmadığı için APK derlemesi ve EC kartla canlı portal testi bu ortamda doğrulanmış
değildir.

## Sonraki mantıklı işler

1. Android SDK ile APK derle; gerçek AKİS RSA kartta mevcut akışı tekrar doğrula.
2. EC sertifikalı gerçek AKİS kartla `SHA256withECDSA` imzasını doğrula.
3. Çalışmayan ikinci AKİS kartın debugger kaydını al; özellikle ATR, sertifika
   FID, key type ve son SW kodunu karşılaştır.
4. Dış Firefox için önce yalnız loopback `/client/info` ve sertifika listeleme,
   sonra PIN onaylı sign endpoint'i ekle; browser'dan gelen origin ve istek
   boyutlarını kısıtla.
5. UDF'nin UYAP'ta kabul ettiği gerçek imza zarfını canlı örnekle doğrula.
6. Üretimden önce geçici cleartext ve admin debugger özelliklerini kapat.

# 0.2.2 checkpoint (2026-10-11)

- `https://arkimza.com` is a product website, not an RFC 3161 endpoint; its
  HTTP 405 response is now diagnosed explicitly. TSA configuration accepts a
  full HTTPS endpoint plus optional Basic username/password. The password is
  not persisted.
- UDF save names are normalized from Android document IDs
  (`primary:Download/name.udf` -> `name.udf`).
- Browser supports multiple WebView tabs, switching/closing, runtime groups
  and persistent favorites. Chromium `.crx` extensions remain unsupported by
  Android System WebView; replacing the engine is a separate architecture job.
- OBS now reaches the OAuth `code/state/session_state` callback, proving the
  earlier Base64-q corruption is fixed. A 30-second duplicate callback guard,
  cookie flush and explicit session reset were added for the subsequent 500.
  A physical phone retest is still required.

# 0.2.4 checkpoint — e-Devlet e-imza girişi

Resmî `edevlet-eimza.jnlp` yalnız `elektronik-imza.jar` uygulamasını başlatır;
işlem kodunu JNLP argümanı olarak taşımaz. Üretim JAR'ındaki protokol incelendi:

- `POST https://www.turkiye.gov.tr/elektronik-imza-yeni?actionName=kayitKontrol&lan=tr`
  (`kimlikNo`, `transId`) ile `sozlesme`, `mimeType`, `islemTip` alınır.
- Girişte Base64 sözleşme çözülür ve gömülü SHA-256 CMS/CAdES olarak imzalanır.
- `POST https://giris.turkiye.gov.tr/Giris/Elektronik-Imza?actionName=imzala`
  (`signedData`, `transId`) çağrısından sonra tarayıcı oturumu yönlenir.

Uygulamada `EdevletClient`, `edevlet-bridge.js`, JNLP indirme yakalama,
sertifika seçimi ve açık PIN onayı eklendi. Köprü yalnız resmî e-Devlet HTTPS
kökenlerinde çalışır. `xml` ve `imz` belge-imza işlemleri giriş kapsamı dışında
olduğu için açık hata verir. Gerçek işlem kodu ve fiziksel kartla canlı test
henüz yapılmadı.

