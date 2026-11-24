# E-İmza One

## GitHub Actions ile Otomatik APK Derleme ve Release (v0.3.0)

Projede GitHub Actions CI/CD hattı yapılandırılmıştır (`.github/workflows/build-and-release.yml`):
- **Tetikleyiciler:**
  - `main` dalına her `git push` yapıldığında veya yeni bir versiyon etiketi (`v*`) gönderildiğinde otomatik çalışır.
  - GitHub web arayüzündeki **Actions** sekmesinden **Run workflow** butonuna basılarak manuel olarak da tetiklenebilir.
- **İşlemler:**
  - Java 17 ve Gradle 8.10.2 ortamını hazırlar.
  - 6 donanımsal token sürücü doğrulama testini (`tools/test-*.sh`) otomatik çalıştırır.
  - Android APK'larını (imzalı Release APK ve Debug APK) derler.
  - Üretilen APK'ları GitHub Releases altında yayınlar (`E-Imza-One-v0.3.0.apk` ve `E-Imza-One-v0.3.0-debug.apk`) ve Workflow Artifacts olarak 90 gün boyunca saklar.

## Version 0.3.0 — Üçlü Donanım Sürücüsü (ArkSigner, TÜRKTRUST TBB, Kamu SM) & Detaylı TXT Tanı Sistemi

- **ArkSigner Arkİmza Token Gömülü Sürücüsü**:
  - Feitian ePass2003, CardOS 5.x, SafeNet/Gemalto IDPrime ve standart PKCS#15 ISO 7816-4 APDU sürücüsü (`ArkSignerTokenBackend` ve `ArkSignerTokenDriver`) doğrudan uygulamaya gömüldü.
  - AID (`A0 00 00 00 63 50 4B 43 53 2D 31 35`), DF (`50 15`) ve EF (`2F 02`, `C0 01`, `2F 04`, vb.) taraması ile kart içindeki X.509 Nitelikli Elektronik Sertifikalar otomatik okunur.
  - Donanımsal PIN doğrulama (`00 20`), kalan deneme hakkı sorgulama (`63 CX`) ve PIN bloke kontrolü (`69 83`/`69 84`) eklendi.
  - Donanımsal MSE ve PSO Compute Digital Signature (`00 2A 9E 9A`) ve açık anahtar yerel matematiksel imza doğrulaması uygulandı.
- **TÜRKTRUST / TBB Kırmızı Token (Baro Kart) Desteği**:
  - Hem SafeNet eToken 5110 donanım mimarisi hem de TBB AKİS profilleri otomatik algılanır ve uygun sürücüye yönlendirilir.
- **Kamu SM / TÜBİTAK (ATR19 Mini Okuyucu) Desteği**:
  - USB CCID T=1 ve AKİS CIF / PKCS#15 V20/V25/Gezgin sürücüleri tam kararlılıkla korunur.
- **Hibrit USB CCID Ulaşım Katmanı (`UsbCcidTransport`)**:
  - CCID sınıf tanımlayıcısının `dwFeatures` değerine göre hem **doğrudan APDU** (`LEVEL_SHORT` / `LEVEL_EXT` — ArkSigner ve SafeNet tokenları için) hem de **TPDU T=1 blok katmanı** (ATR19 / ACS okuyucular için) otomatik olarak seçilir.
  - `UsbCcidProbe` içindeki katı T=1 zorlaması kaldırıldı; T=0 ve doğrudan APDU kullanan tokenların bağlantısı güvenceye alındı.
- **Detaylı Tanı ve TXT Günlük Dışa Aktarma Motoru (`DiagnosticLogger`)**:
  - Merkezi ring-buffer ile USB bağlantıları, CCID tanımlayıcıları, ATR dökümü, kart sağlayıcısı, sertifika özetleri, APDU durum kodları ve web köprüsü olayları sansürlenmiş (PIN/özel anahtar asla yazılmaz, TCKN maskelenir) şekilde tutulur.
  - Tek dokunuşla cihaz bilgisi, donanım durumu ve kronolojik logları içeren detaylı `.txt` raporu oluşturulur.
  - Android Share Intent (WhatsApp, E-posta, Telegram, Drive) ile anında paylaşma, dosyaya kaydetme veya panoya kopyalama desteği eklendi.
- **Arayüz ve Kullanılabilirlik Geliştirmeleri**:
  - Debugger ekranı gizli 7 dokunma kilidinden çıkarılıp doğrudan ana menüye ve araç çubuğuna taşındı.
  - Ana ekranda takılı token modeli (`ArkSigner Arkİmza Token`, `TÜRKTRUST / TBB Kırmızı Token`, `Kamu SM ATR19`) rozet olarak anlık gösterilir.
- Sürüm: `versionCode 35`, `versionName 0.3.0`.
- Birim Testi: `TokenIdentificationHarness` ile üç donanım ailesinin ATR ve PKCS#1 v1.5 DigestInfo matematiksel imzası test edilip doğrulandı.

## Version 0.2.19 — OBS sunucu ret mesajını çıkarma

- OBS’nin bozuk inline JavaScript’i içindeki, `248 51 51` destek numarasıyla
  biten sunucu mesajı çalıştırılmadan metin olarak çıkarılır.
- Mesaj tanıya `serverMessage` alanıyla eklenir; TCKN/e-posta biçimleri ve uzun
  tokenlar kaydedilmeden önce gizlenir. Sunucu reddinin yetki/kullanıcı kaydı mı
  yoksa SSO verisi mi olduğu böylece doğrudan görülebilir.

Sürüm: `versionCode 32`, `versionName 0.2.19`.

## Version 0.2.18 — OBS bozuk JavaScript satırı yakalama

- OBS callback’inde görülen `SyntaxError: Invalid or unexpected token`
  hatasının satır/sütun bilgisi belge başlangıcında saklanır.
- Sayfa tamamlandığında hatalı satırın iki önceki ve iki sonraki satırı tanıya
  eklenir. `q` tokenı, uzun kodlar, TCKN/e-posta biçimleri ve form değerleri
  kayda girmeden önce otomatik gizlenir.

Sürüm: `versionCode 31`, `versionName 0.2.18`.

## Version 0.2.17 — OBS callback kesin tanısı

- Başarısız olan `q` yeniden kodlama ve ana sayfaya zorlama denemeleri tamamen
  kaldırıldı; OAuth yönlendirmesi artık değiştirilmeden bırakılır.
- OBS callback sayfası belge başlangıcında yalnız hata dinleyicisiyle izlenir.
  JavaScript hata türü, satır ve kaynak kaydedilir; token, form değerleri,
  sertifika ve çerez değerleri kaydedilmez.
- Sayfa tamamlandığında görünen hata metni, form method/hedefleri, yalnız input
  adları/türleri, meta-refresh ve yalnız çerez adları tanıya eklenir. Böylece
  script listesinin tanıyı kesmesi yerine gerçek son SSO cevabı görülür.

Sürüm: `versionCode 30`, `versionName 0.2.17`.

## Version 0.2.16 — OBS `q` tokenında yalnız artı koruması

- 0.2.15 denemesi, ham `q` yanıtının geçerli OBS oturumu oluşturmadığını;
  kök adrese geçildiğinde yeniden `Account/Login` açılmasıyla doğruladı.
- Standart Base64 tokenındaki yalnız ham `+` karakterleri `%2B` yapılır.
  Eski denemedeki HTTP 500’e neden olan `/ -> %2F` ve `= -> %3D`
  dönüşümleri kaldırılmıştır.
- Düzeltme, OAuth yönlendirmesi ve çerez yazımı tamamen bittikten sonra aynı
  WebView’de bir kez uygulanır. Düzeltilmiş yanıt yüklendikten sonra portal
  köküne geçilir; tekrar döngüsü engellenir.

Sürüm: `versionCode 29`, `versionName 0.2.16`.

## Version 0.2.15 — OBS SSO sonlandırma geçişi

- OGN OAuth imzası ve OBS `SsoLogin?q=...` yanıtı başarıyla tamamlandıktan
  sonra, yanıtın oluşturduğu oturum çerezinin WebView’e yazılması beklenir ve
  aynı WebView bir kez OBS ana adresine geçirilir.
- `q` tokenı hâlâ değiştirilmez; `stopLoading`, yeniden kodlama veya yeni
  WebView kullanılmaz. Geçiş yalnız HTTP 200 ile tamamen yüklenmiş `q`
  sayfasından sonra ve aynı URL hâlâ açıksa çalışır; döngü oluşturmaz.

Sürüm: `versionCode 28`, `versionName 0.2.15`.

## Version 0.2.14 — OBS OAuth callback’ini değiştirmeden izleme

- OGN imzasından sonra üretilen OBS `/Account/SsoLogin?q=...` adresi artık
  durdurulup yeniden yüklenmiyor ve `q` tokenındaki karakterler uygulama
  tarafından yeniden kodlanmıyor. Telefon logunda değiştirilmiş `%2B/%2F/%3D`
  adresinin doğrudan HTTP 500 verdiği doğrulandı.
- OAuth `code/state/session_state` callback’i, yönlendirme başlıkları ve yeni
  oturum çerezleri WebView tarafından tek akışta işleniyor. Böylece callback
  yanıtı sırasında oluşturulan OBS oturumu manuel `stopLoading/loadUrl`
  geçişiyle bölünmüyor.

Sürüm: `versionCode 27`, `versionName 0.2.14`.

## Version 0.2.13 — doğru e-Devlet `fileInput` verisi

- e-Devlet kayıt yanıtındaki insan tarafından okunabilir `sozlesme` metni
  artık imzalanmıyor. Resmî masaüstü istemcisi gibi yalnız Base64 kodlu
  `fileInput` alanı çözülüp CMS içine gömülüyor. `sozlesme` alanını imzalamak,
  CMS kriptografik olarak geçerli olsa bile sunucuda “imzalanan veri içeriğinde
  bozulma / NOT_TRUSTED” hatasına neden oluyordu.
- Başarı yanıtı artık yalnız `errorCode == 0` ile varsayılmıyor; resmî protokoldeki
  `sonuc[0]` oturum kodu da zorunlu. Böylece reddedilen işlem “imza kabul edildi”
  şeklinde kaydedilmiyor.

Sürüm: `versionCode 26`, `versionName 0.2.13`.

## Version 0.2.12 — e-Devlet resmî RSA/CMS profili

- e-Devlet `NOT_TRUSTED` / “imzalanan veri içeriğinde bozulma” hatasının
  nedeni giderildi. Önceki sürüm imzalı öznitelikleri karta standart
  `SHA256withRSA` olarak gönderiyor ve SignerInfo içinde aynı birleşik algoritma
  kimliğini yazıyordu.
- Resmî e-Devlet masaüstü istemcisindeki akış birebir uygulanır: DER sıralı
  öznitelikler SHA-256 ile özetlenir, `DigestInfo` karta ham RSA PKCS#1 işlemi
  için gönderilir ve CMS SignerInfo algoritması `rsaEncryption` olarak yazılır.
- CMS gönderilmeden önce gömülü içerik ve kart imzası seçilen sertifikayla
  yerelde yeniden doğrulanır. Tanı kaydı yalnız profil ve bayt uzunluklarını
  gösterir; işlem verisi, imza ve PIN kaydedilmez.

Sürüm: `versionCode 25`, `versionName 0.2.12`.

## Version 0.2.11 — OBS SSO Base64 URL düzeltmesi

- OBS'nin `/Account/SsoLogin?q=...` yönlendirmesinde ham standart-Base64
  karakterleri artık sunucuya gitmeden önce `+ -> %2B`, `/ -> %2F`,
  `= -> %3D` olarak kodlanır. 0.2.10 telefon logunda aynı sayfanın farklı
  ham `q` değerleriyle tekrar tekrar açılması bu eksik çağrıyı gösterdi.
- Normalizasyon ana ve popup WebView navigasyonunda, redirect yakalanamadığı
  durumlar için de `onPageStarted` yedeğiyle uygulanır; zaten `%xx` kodlu
  değerler ikinci kez kodlanmaz.
- Tarayıcı menüsüne `e-Devlet işlem kodu gir` eklendi. e-Devlet tanısı
  işlem türü, MIME türü ve yalnızca içerik uzunluğunu kaydeder.

Sürüm: `versionCode 24`, `versionName 0.2.11`.

## Version 0.2.10 — OBS attached CMS, e-Devlet polling, ArkSigner launch guard

- OGN/OBS SSO imzalarında portal `isAttached` alanını atlasa veya `false`
  gönderse bile içerik CMS zarfına gömülür. Bu, 0.2.9 testindeki değişmeyen
  `signedMimeLen=3772` regresyonunu giderir; admin tanısında `gömülü=true`
  görülmelidir.
- `arksigner:open` masaüstü uygulama başlatma isteği hem ana hem popup
  WebView'de tüketilir. Yerel Android köprüsü korunur ve Reçetem sayfası
  `ERR_UNKNOWN_URL_SCHEME` hata ekranına düşmez.
- e-Devlet başarılı imza gönderiminden sonra açık giriş sayfası yeniden
  yüklenmez ve `sonuc` değeri varsayımsal bir forma yazılmaz. Tarayıcının
  mevcut işlem kodu için kendi oturum yoklaması beklenir. Güvenlik/captcha
  alanları artık e-imza işlem kodu olarak algılanmaz.
- e-Devlet CMS imza algoritması BouncyCastle'ın kabul ettiği
  `SHA256withRSA` / `SHA256withECDSA` biçiminde üretilir; tireli
  `SHA-256withRSA` adının imzalama öncesi oluşturduğu hata giderildi.

Sürüm: `versionCode 23`, `versionName 0.2.10`.

## Version 0.2.8 — AKİS V20/V25/Gezgin kart uyumluluğu

- ACR39U/ACR39U ICC Reader'ın kart sağlayıcısı değil CCID okuyucu olduğu
  doğrulandı. Okuyucu içindeki AKİS kartın gerçek CIF sürümüne göre işlem
  seçiliyor.
- AKİS CIF'de V20, V25 ve Gezgin sınıflarının genel `verify(byte[], ...)`,
  `getKeyInfos()` ve bazı `sign(...)` yolları kasıtlı olarak
  `UnsupportedVersionException` üretir. Bu ailelerin tamamı artık PIN referansı
  `0x81`, PKCS#15 CDF/PrKDF sertifika–anahtar eşlemesi ve uyumlu MSE/PSO yolu
  üzerinden çalışır. Önceden yalnız V25 bu özel yola giriyordu.
- ISO 7816 ATR tarihsel bayt ayrıştırması düzeltildi. AKİS sürüm fabrikasına
  artık arayüz baytları yerine doğru tarihsel baytlar verilir.
- İmza hatası tanısı kart profilini (`CommandsV20/V22...` gibi) ve güvenli
  PKCS#15 anahtar referansını gösterir; PIN veya APDU verisi yazılmaz.

## Version 0.2.7 — resmî e-Devlet CMS profili ve temiz OBS oturumu

- e-Devlet imzası artık genel portal CAdES üreticisinden ayrıdır. Resmî JNLP'nin
  `SmartCard.signContent()` akışına uygun olarak içerik CMS içine gömülür;
  `contentType`, `messageDigest`, `signingTime` ve SHA-256
  `SigningCertificateV2` imzalı öznitelikleri eklenir. RSA ve EC sertifikaları
  seçilen kart backend'i üzerinden imzalanır.
- Sağlık portalları Firefox kimliğiyle çalışan Chromium WebView gibi
  gösterilmiyor. Mobilde gerçek WebView kimliği, masaüstünde Chromium masaüstü
  kimliği kullanılıyor.
- OBS ana girişinden başlatılan yeni akışta yalnız OBS/OGN oturum çerezleri
  süresi dolmuş olarak işaretleniyor. Böylece eski OAuth/PKCE oturumunun yeni
  `state` ve `code_verifier` ile karışması önleniyor.
- Admin tanısında CAdES zarfının girdi/zarf uzunluğu ve içeriğin gerçekten
  gömülü olup olmadığı yazılıyor; veri, PIN, imza ve çerez değerleri yazılmıyor.

## Version 0.2.3 — TSA sağlayıcıları ve yeni marka

- **KamuSM üretim:** `http://zd.kamusm.gov.tr` (TCP 80). Satın alma sonrası verilen sayısal müşteri numarası ve parola gerekir. Bu profilde ESYA `TSClient` kullanılarak KamuSM'ye özgü müşteri kimliği üretilir.
- **UYAP / Adalet:** Kamuya açık ayrı bir Adalet TSA uç noktası yayımlanmadığı için KamuSM üretim profiline yönlenir. UDF'nin UYAP belgesi olması ücretsiz zaman damgası sağlamaz.
- **Arkİmza / ArkSigner:** Zaman damgası hizmeti vardır; kamuya açık RFC 3161 uç noktası ve doğrulama şeması yayımlanmadığından sözleşmede verilen HTTPS adresi/hesap girilir.
- **Özel RFC 3161:** Standart HTTPS TSA ve varsa HTTP Basic kimlik doğrulaması içindir.

TSA parolası diske yazılmaz; yalnız uygulama oturumunda tutulur ve imzalama sonrasında temizlenir.

## Version 0.2.2 — TSA credentials, tabs, favorites and OBS callback safety

- TSA settings now distinguish an RFC 3161 service endpoint from a normal web
  page, support optional HTTP Basic credentials, reject non-timestamp response
  content types and explain HTTP 405/401/403 failures. Passwords are kept only
  in memory and are cleared after the signing attempt.
- Storage-provider document identifiers such as `primary:Download/file.udf`
  are reduced to `file.udf` before `ACTION_CREATE_DOCUMENT` is opened.
- Browser tabs are separate WebView instances with switching, closing and
  runtime group names. Favorites persist in app preferences.
- OBS one-use OAuth callback URLs are de-duplicated for 30 seconds and cookies
  are flushed before code exchange. An explicit “OBS oturumunu sıfırla” action
  removes stale session cookies and restarts the login flow.
- Android System WebView cannot load Chromium `.crx` / Manifest V2/V3
  extensions. The UI reports that boundary rather than claiming incompatible
  extension support; full support requires replacing WebView with a maintained
  Chromium browser fork.

## Version 0.2.1 — OBS callback, CAdES-T, loopback and browser chrome

- OBS `/Account/SsoLogin?q=...` callbacks now percent-encode literal Base64
  `+`, `/` and `=` characters before navigation so form-query decoding cannot
  corrupt the encrypted SSO value.
- Loopback health probes no longer enter the ArkSigner JSON parser. Direct JSON,
  form and raw Base64 jobs are normalized; native `([ ... ])` envelopes and
  Base64 wire fields match the in-app connector.
- The browser uses a compact dark omnibox and bottom navigation bar inspired by
  modern privacy browsers; desktop mode and utilities live in the overflow menu.
- UDF signing can remain CAdES-BES or be upgraded to real CAdES-T with a configured
  RFC 3161 HTTPS TSA. Signature inspection reads the timestamp from unsigned
  attributes and displays the profile and generation time.
- Release hardening can optionally run the open-source Apache-2.0 Dex2C AOT/JNI
  pass after R8 using `tools/harden-release-dex2c.sh`.

## Version 0.2.0 — EC/ECDSA, modern browser shell and UDF workspace

- AKİS signing now distinguishes RSA and EC/ECDSA certificates. RSA keeps the
  DigestInfo/PKCS#1 path; EC sends the raw content through the CIF ECC + SHA-256
  mechanism and verifies the returned ASN.1 ECDSA signature with the selected
  certificate.
- The Android manifest keeps `android:usesCleartextTraffic="true"` temporarily,
  while portal TLS errors are still rejected by the WebView client.
- The old portal shortcut buttons were replaced by a browser workspace with an
  address bar, back/forward/reload/home, desktop User-Agent mode, and external
  browser launch. Reçetem and other portal URLs can be opened manually.
- A card/help screen documents ATR19 as a reader, not a card provider, and
  explicitly reports that only KamuSM/AKİS is implemented. The signer boundary
  remains provider-oriented so additional legal vendor SDK/APDU profiles can be
  added without exposing PINs or raw APDUs to page JavaScript.
- An admin debugger is enabled by tapping the main title seven times. It keeps
  bounded timestamped transport/card diagnostics and intentionally excludes PINs,
  payloads, DER and signatures. It is a temporary diagnostic feature.
- The UDF workspace opens a local `.udf` file, renders `content.xml` in a safe
  visual preview, signs that content with CAdES-BES and saves a new UDF ZIP
  containing `content.xml` and `sign.sgn`. A plain `.p7s` is no longer
  mislabeled as a UDF. CAdES-BES has no timestamp; CAdES-T/LT/LTA needs a
  configured trusted TSA and policy.

- An Android loopback ArkSigner HTTP service listens on `127.0.0.1:16356` and
  `127.0.0.1:16357` while the app is open. This enables a Firefox/Chrome page
  on the same device to reach the card backend; the browser still needs to use
  ArkSigner's normal local HTTP transport and provide its PIN. External desktop
  browsers on another device cannot reach this loopback service.
- A visual first-run tutorial, theme/settings/about panels, a corrected top-right
  overflow anchor, UDF signature inspection, optional Firebase telemetry and an
  admin-only three-day offline test policy are included. Firebase remains inert
  until `app/google-services.json`, `-PfirebaseEnabled=true` and consent are
  supplied.

The in-app WebView continues to emulate the supplied ArkSignerJS 3.0.2 Firefox
message contract. The app also exposes plain HTTP loopback ports 16356/16357
with POST, GET-query and JSONP handling for same-device browser connectors.
Stock Firefox connectors that require HTTPS or the hostname
`local.pwsigner.ark-teknoloji.com` still need a browser-side helper; opening a
page externally alone does not transfer the Android `EimzaNative` bridge.

Release builds enable R8 shrinking/optimization/renaming and resource shrinking.
`tools/harden-release-dex2c.sh` adds an optional, open-source Dex2C AOT/JNI pass for
a narrow audited method whitelist after R8. It is not falsely presented as PairIP or
a full VMRunner; setup, signing and operational limits are documented in
`HARDENING.md`.

## Version 0.1.12 — SocketV13 native HTTP response envelope

- The original ArkSigner 2.3.17 service was run in isolation and queried with the same HTTP contract. Without a JSONP callback it returns `([ ... ])`, not bare JSON. ArkSignerJS 3.0.2 removes the outer parentheses before processing the array.
- The WebView HTTP/XHR adapter now reproduces that exact envelope. Previously it returned `[ ... ]`; ArkSignerJS stripped the square brackets, received an object instead of an array, and failed at `[0].responseCode`.
- JSONP remains `callback([ ... ])`. Explicit XHR `responseType=json` is parsed from the inner array while `responseText` retains the native-service envelope.

## Version 0.1.11 — ArkSigner 3.x bootstrap order

- The bundled ArkSigner client is no longer evaluated before the portal's ArkSignerJS 3.0.2 `initialize` response handler runs. That early evaluation replaced 3.0.2's `processResponseObject` while its SocketV13 `onload` handler was active and caused `Cannot read properties of undefined (reading 'responseCode')`.
- Initialization now follows the native service contract: the client resource is encrypted into `nonce2`, returned with the response, and evaluated by the portal's own initialize callback.
- Adalet/UYAP and the health-domain iframe policy are unchanged.

## Version 0.1.10 — health iframe origin routing

- Reçetem/e-Nabız may host the ArkSigner UI on another approved Sağlık Bakanlığı subdomain (for example, an `enabiz.gov.tr` page with a `saglik.gov.tr` signing frame). The native bridge now accepts that health-to-health route while continuing to reject HTTP, unrelated sites, ArkSigner test-host embedding and cross-host Adalet requests.
- Rejected ArkSigner origins now leave a safe diagnostic entry instead of failing silently.
- UYAP/Adalet behavior is unchanged from 0.1.9.

Validation: the origin-policy harness covers e-Nabız ↔ Sağlık frame routing and negative boundaries; all existing ArkSigner, frame, Adalet, signing and CCID tests pass locally. The supplied console export contains only the successful UYAP flow, so the health fix still requires a phone test.

## Version 0.1.9 — ESYA-compatible UYAP signature and ArkSigner bootstrap

- UYAP CAdES-BES is now generated by the same bundled ESYA `BaseSignedData` API and call sequence used by the supplied Adalet desktop client. The supplied encrypted ESYA licence is decrypted and loaded with that client's own configuration algorithm; certificate validation before signing remains disabled exactly as in the original local client.
- The successful UYAP `sign` response omits the nullable `signedECorrespondenceData` property, matching the original client's NON_NULL response DTO.
- ArkSigner terminal, slot and certificate properties are returned as ordinary JSON strings instead of being incorrectly Base64-wrapped.
- During `initialize`, the supplied ArkSigner SDK is returned through the native service's encrypted `nonce2` bootstrap contract.
- Safe page diagnostics now include the JavaScript error message, line and column without logging card data, PINs, certificates or signatures.

Validation: ESYA-generated attached/detached CMS signatures verify with the selected certificate and reject altered content. ArkSigner JSONP, fetch, XHR, Firefox-message emulation, nested-frame routing, Adalet fetch/XHR and response-object tests pass locally. A real portal session still requires installation and phone testing because those authenticated systems are not available to the local test harness.

Android single-app integration for USB CCID cards. The app takes Android USB permission, transports T=1 APDUs directly, reads AKİS certificates, and signs through the supplied AKİS/ESYA card libraries. It has no Termux, pcscd, proot, or Box64 runtime dependency.

## Portal adapters in this source

- ArkSigner page messages are handled in the WebView using the Firefox add-on message contract, its native JavaScript connector, and loopback JSONP bootstrap interception. The adapter currently covers initialize, slot/card listing, certificate listing, raw PKCS#1 v1.5 signing, and CAdES-BES signing. Signing always asks for native confirmation and PIN. Allowed origins are limited to the health portal and ArkSigner test hosts.
- Adalet's desktop tray protocol is adapted inside the WebView. A document-start hook replaces the tray's loopback calls for certificate listing, certificate lookup, and `/api/v1/signature/sign`. Content-to-be-signed is fetched from the Adalet API using the full DER certificate, as the supplied tray does; the Android app then builds a CMS/CAdES signature with the card and returns the tray response envelope.
- No portal request, APDU, PIN, or signing payload is written to logs.
- The WebView opens e-Nabız after it attaches to the activity. It routes popup links into the same view, upgrades HTTP redirects on `gov.tr` to HTTPS, and shows a readable in-view error page for top-level load failures. Reçetem uses a desktop Chromium user agent through its redirects; other portal buttons restore the mobile user agent.
- AKİS CIF 3.3.18 assumes every X.509 certificate has a KeyUsage extension and crashes when it is absent. Some ATR19 cards also report unused certificate FIDs as zero-length files. The Android backend keeps the AKİS FID scan and serial-to-slot map, skips empty FIDs, and accepts certificates whose optional KeyUsage extension is absent.

## Build on Termux

Install a JDK, Gradle, Android SDK platform 34 and build-tools 34.0.0. Set `ANDROID_HOME` to the SDK directory. Then run:

```sh
cd ~/src/eimza-one
gradle assembleDebug --no-daemon --max-workers=2
```

The app uses AndroidX WebKit's document-start injection API, so Gradle needs access to Google Maven for `androidx.webkit:webkit:1.12.1`.

## Verification and current limits

Version 0.1.1 separates the scrollable card/menu screen from a full-height browser panel. Portal buttons explicitly show the browser. JavaScript bridge origin checks use a UI-thread snapshot instead of calling WebView.getUrl from a bridge thread.

Verified locally:
- `bash tools/test-ccid-transport.sh`: simulated CCID slot, ATR, T=1 transfer and chaining.
- `node tests/portal-bridge.test.cjs`: Adalet fetch/Request bodies, XHR read-only properties, request headers, response events, abort and nonlocal passthrough.
- `bash tools/test-signing.sh`: attached/detached CAdES signatures verified using a generated test RSA certificate; altered content rejected; AKIS DigestInfo/padding contract verified with software RSA; Java bootstrap nonce and XOR checked against the JavaScript resource extracted from the supplied ArkSigner executable.
- Android-independent adapters compiled with the supplied AKIS JARs and Android USB compile stubs; MainActivity syntax parsed. These checks are not a full Android APK build.

The ArkSigner bootstrap now supplies nonce2, a cyphered copy of the supplied executable's JavaScript resource; slot IDs are Base64-encoded strings and certificate responses are rows as in that executable. Adalet certificate responses use its original envelope and Base64 DER format; signing uses literal UTF-8 content and detached CAdES. AKIS SHA-256 signatures send DigestInfo to the card, while ArkSigner raw PKCS#1 sends the input unchanged.

There is no Android device, SDK or real portal session available in this environment. An APK and successful portal login have **not** been verified here. The WebView adapters still need a phone build and real end-to-end portal test with a card. The current implementation supports Adalet's `/signature` routes; `docsignature/signdigest` and `/signkep`, ArkSigner digest-CAdES, ECDSA cards, and Firefox cross-browser-to-app transport are not implemented here. It does not claim those flows work yet.

## Version 0.1.2 — health portal transport

The page hook now adapts `pwsigner.connector.send` directly and delivers responses through the original SDK's `processResponse`, preserving its transaction callbacks. Local JSONP script requests carrying `parameters` and `callback` on the known ArkSigner hosts at ports 16356/16357 are intercepted before network access. Nonlocal scripts pass through. The Firefox postMessage path remains supported. Responses echo jobUUID; an empty certificate list returns an explicit error with transactionUUID instead of an uncorrelatable empty array.

The Kart / Menü screen contains a bounded diagnostic view with action names, response codes and record counts. It does not record task bodies, PINs, signing data or certificate contents. If the health portal still stays at kart yükleniyor, copy this diagnostic view; it distinguishes no transport request, an unsupported action and a returned certificate response.

Run `node tests/arksigner-transport.test.cjs` from the project root. It tests JSONP initialize dispatch, connector takeover, callback processing using the actual supplied ArkSigner JS resource, Firefox response delivery and nonlocal script passthrough. These are local protocol tests with a mocked Android bridge, not a real health portal login. UYAP and certificate reading are confirmed by the user's phone report for 0.1.1. Version 0.1.2 still requires phone validation for Reçetem/e-Nabız.

## Version 0.1.8 — Adalet device-info contract and frame response delivery

UYAP uses the Adalet adapter; health portals use ArkSigner. The JavaScript hooks now enforce that separation. The supplied Adalet JAR's `/client/info` returns encrypted `SystemInfoDTO`, not a plaintext version JSON string. This version reproduces its `ENC(...)` envelope, PBEWITHHMACSHA512ANDAES_256 / 1000 iterations / random 16-byte salt and IV using the already bundled Bouncy Castle library; no extra service or Jasypt runtime is added. Device fields identify Android honestly and no network-interface identifiers are collected.

Native WebView replies previously reached only the main frame. Both transports now register the requesting child frame and relay replies through nested frames to that transaction's callback. Early replies are retained until registration reaches the parent. Replies target the registered frame's exact origin; unrelated frames receive no certificate/signature data. Adalet response data types are preserved: certificate/info strings, reader arrays, signature objects. The supplied JAR's HTTP 200 plus metadata error convention is retained.

Diagnostics distinguish Adalet request paths and response data types from ArkSigner actions and callback delivery. JavaScript error types are reported without exception messages, PINs, payloads or certificate contents.

Validation: the new device-info encoder decrypted successfully with the supplied JAR's actual Jasypt 1.9.3 implementation; a retained fixture and independent SunJCE test verify the format. Nested-frame tests cover replies arriving before route registration, signature-object preservation and unrelated-frame exclusion. Existing transport and CAdES tests pass. Card backend Java compilation and MainActivity syntax checks pass. No Android SDK/device is available here: no APK build or completed live UYAP/health login is claimed. The frame fix applies if the portal uses an iframe; the cause of the reported live `JSONObject [data]` error still requires the new Adalet diagnostics to confirm.

Build in your existing Termux checkout after replacing these source files:

```sh
cd ~/src/eimza-one
JAVA_HOME="$PREFIX/lib/jvm/java-21-openjdk" PATH="$HOME/gradle-8.9/bin:$PATH" gradle assembleDebug --no-daemon --max-workers=2
```

APK output: `app/build/outputs/apk/debug/app-debug.apk`. Install it over the existing app, fully reopen the app, and reload each portal. Card / Menu now shows separate `Adalet istek`, `Adalet yanıt` and ArkSigner callback entries.

## Version 0.2.4 — e-Devlet JNLP yerine yerel giriş

- e-Devlet e-imza sayfasındaki 6–10 karakterlik işlem kodu DOM üzerinden
  algılanır; JNLP indirme bağlantısı uygulama içinde karşılanır. Algılama
  başarısızsa ana menüdeki **İşlem kodu** düğmesiyle elle girilebilir.
- Resmî masaüstü istemcisinin üretim protokolü uygulanır: işlem kodu ve
  sertifikadaki TCKN ile imzalanacak veri alınır, kullanıcı sertifika/PIN
  onayından sonra gömülü SHA-256 CAdES/CMS üretilir ve yalnız
  `giris.turkiye.gov.tr` adresine gönderilir. PIN hiçbir HTTP isteğine girmez.
- Başarılı gönderimden sonra açık e-Devlet sekmesi yenilenmeden sunucunun bağlı
  tarayıcı oturumunu yönlendirmesi beklenir. XML ve mevcut `.imz` dosyasına
  ek imza türleri bu ilk giriş entegrasyonunda bilinçli olarak reddedilir.
- Köprü yalnız `https://*.turkiye.gov.tr` kökenlerinde etkinleşir; benzer adlı
  alan adları reddedilir ve standart Android TLS doğrulaması değiştirilmez.


## Version 0.1.7 — native RSA MSE and HTTP body formats

Replaces CIF's generic V25 sign method (algorithm 82, unscoped key index) with the supplied native ArkSigner's RSA MSE path: legacy 00 22 C3 22 <key-index>; for unsupported/not-found MSE status, use 00 22 41 B6 with algorithm 92 and local key reference 80|index. The key still comes from the certificate/PrKDF association. A failed PSO is never repeated. Signature verification with the selected certificate remains mandatory. Failures include the metadata keyRef, never key material.

HTTP parameters can now arrive as URL/form fields, a JSON parameters wrapper, a direct action JSON task or raw Base64. Malformed/missing fields get specific diagnostic labels instead of a generic transfer failure. This does not establish which form the live health portal uses.

Validation: production native MSE helper exercised through real CIF with a simulated card accepting the native legacy/92-local formats and rejecting CIF's 82/plain-index PSO; failed PSO is sent once. JavaScript transport tests cover supported body formats, invalid fields and Adalet coexistence. Actual card/portal success is unverified and no APK build is available in this environment.

## Version 0.1.6 — PIN before protected metadata; HTTP bootstrap

Corrects the earlier ordering error: select signing DF, verify PIN once, read CDF/PrKDF, associate key, then MSE/PSO. The supplied ArkSigner signWithAKISCertificate function calls VerifyPIN before RetrievePKCS15FromCerts and RetrievePKCS15PrivateKeyIndex. Earlier versions attempted directory reads before authentication. Diagnostic failures now include INS/P1/P2/SW only, with no command payload.

ArkSigner HTTP bootstrap now supports fetch and XMLHttpRequest, including encoded `parameters` in GET queries and POST form bodies, in addition to connector, Firefox and script JSONP transports. Only known ArkSigner loopback hosts on ports 16356/16357 are intercepted. No validity responses are fabricated and portal certificate validation is not bypassed.

Tests use the production V25 prepare method and reject directory reads before authentication; real CIF emits the verification/signing commands. HTTP transport tests cover GET, POST, XHR, JSONP, external requests and coexistence with Adalet. Card backend compiles using Android stubs and MainActivity syntax checks pass. Actual Android APK build and physical-card/live-portal signing remain unverified here; simulated tests establish ordering and message transport, not live success.

## Version 0.1.5 — signing DF restoration and first ArkSigner request

V25 authentication now reselects the PKCS-15 signing DF after directory reads, before verifying the local PIN. The supplied native ArkSigner also selects the signing DF immediately before PIN verification. Previously the directory EF remained selected. Card failures now identify SELECT, VERIFY, MSE or PSO without logging PINs or APDU contents.

ArkSigner transport binding now runs synchronously when the global signer or its connector is assigned, and survives send-function reassignment during initialization. Polling remains a fallback. Diagnostics include safe action names at the JavaScript send boundary and callback-delivery failures.

Validation: production authentication helper tested with real CIF V25 and simulated card context (6982 without DF selection); original ArkSigner SDK tested for immediate requests and connector replacement without waiting for polling. Backend Java compiles with Android stubs; MainActivity syntax checked. The phone's actual 6982 command and live health portal behavior have not been verified. These changes do not establish end-to-end portal signing success.

## Version 0.1.4 — AKIS V25 signing and health portal startup

The supplied CIF implements the legacy V25 PIN verification and key-list methods as UnsupportedVersionException stubs. Signing now uses the supported explicit PIN reference and MSE/PSO commands. It reads CDF (2F04) and PrKDF (2F01) metadata to associate the selected certificate with its key reference; it does not guess key indices or retry PINs. Other card versions retain their existing path.

Health portals open with a desktop Firefox user agent to select the ArkSigner message transport at startup. This is a compatibility change to test on the phone, not proof that the live portals work.

Validation: test-akis-v25.sh exercises PKCS15 association, reordered keys and malformed metadata rejection, and the supported commands in the supplied real CIF jar using a simulated card transport. CMS and JavaScript bridge regressions pass. Card backend Java compilation passes with Android stubs; MainActivity syntax is checked. No APK build or physical-card/portal signing was possible in this environment.

## Version 0.1.3 — ArkSigner wire encoding and UYAP PIN/CMS

The supplied ELF calls QByteArray::toBase64 immediately before writing terminal, slotId, library, smartCardType, providesPINReader, isCardInserted and cardType. Those fields are now Base64 UTF-8 strings; smartCardType encodes the native literal token. Its certificate-list implementation likewise encodes serialNumber, commonName, isExpired, issuer, issuerCommonName, notAfter, notBefore, subject and subjectCommonName. certificateHex remains hex and subjectSerialNumber remains plain, as in the native response. monitorSmartCardActivity now returns monitoringResult=MA==, matching the supplied implementation's Base64 zero result; this is compatibility with its stub, not a new event-monitoring service.

The supplied Adalet SignDataReqDto contains password. ClientDigitalSigningServiceImpl.resolvePin uses that password if provided and asks for PIN only when absent. The Android adapter now follows that behavior: it still asks for confirmation of the signing request, but shows no second PIN entry when the portal supplied it. The PIN is scoped to that request and its mutable copy is cleared after completion/cancel.

CAdES generation now selects the complete bundled BouncyCastleProvider by object rather than the BC name, which is already occupied by Android's reduced built-in provider. A regression test generates and verifies the signature while a reduced provider already has that name and verifies that the OS provider is not replaced. Card-signing failures expose only exception classes and an AKIS status word in the diagnostic screen, not PINs or APDU payloads.

Validation: local ArkSigner transport tests with the supplied SDK, Adalet transport tests, CMS signed-content/tamper tests and reduced-BC collision test pass. Java syntax parsed. No Android APK build or real portal signing is verified here; 0.1.3 must be tested on the phone. The earlier phone report established reader/certificate detection, not completed UYAP login.

## Version 0.2.5 — giriş uyumluluğu ve sekme deneyimi

- e-Devlet işlem kodu resmî JNLP gibi büyük/küçük harfi değiştirilmeden gönderilir ve kullanıcıya doğrulatılır.
- OGN/OBS girişinde eksik `isAttached` alanı için gömülü CAdES içeriği kullanılır; detached CMS kaynaklı SSO 500 yolu giderilmiştir.
- Boş sekmede adres çubuğu boş görünür; temizleme, ayrı adres düzenleyici, geçmiş ve otomatik tamamlama eklendi.
- Sekmeler önizleme kartı, kapatma düğmesi, sürükle-bırak sıralama ve grup hedefleriyle yönetilir.
- USB fişi merkezde ve daha görünür olan yeni uygulama logosu eklendi.
- GeckoView/Firefox geçiş planı `BROWSER_ENGINE_ROADMAP.md` dosyasındadır.

## Version 0.2.6 — giriş döngüsü ve WebView güvenliği

- e-Devlet imzası kabul edildikten sonra sayfa zorla yenilenmez. Kabul edilmiş
  işlem kodu beş dakika boyunca tekrar işlenmeyerek aynı kod/PIN döngüsü önlenir.
- OGN/OBS imzasında sağlık giriş bildirimi, portal `isAttached=false` gönderse
  bile gömülü CAdES olarak üretilir. Admin tanısı yalnız SSO çerez adlarını
  kaydeder; çerez değerlerini veya kimlik doğrulama sırlarını yazmaz.
- Adres otomatik tamamlama Ayarlar ekranından kapatılabilir.
- Genel cleartext izni kaldırıldı. Uzak HTTP ve WebView karma içeriği engellenir;
  yalnız yerel ArkSigner uyumluluğu için `localhost`/`127.0.0.1` HTTP istisnası
  bırakılmıştır. Dosya/içerik URL erişimi ve coğrafi konum da kapatılmıştır.
