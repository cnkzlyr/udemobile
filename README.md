# ⚖️ CanEditor (UdeMobile) — Birleşik Hukuk Platformu & Çapraz Platform UYAP Editörü

[![Sürüm](https://img.shields.io/badge/Sürüm-v4.10.0-c8a45a.svg)](https://github.com/cnkzlyr/udemobile/releases/tag/v4.10.0)
[![CLI](https://img.shields.io/badge/Terminal-caneditor-333.svg)](#3-️-caneditor--arayüzün-yaptığı-her-şey-terminalde-windows--macos--linux--androidtermux)
[![Platformlar](https://img.shields.io/badge/Platformlar-Android%20%7C%20Windows%20%7C%20macOS%20%7C%20Linux%20%7C%20Web-0f2341.svg)](https://github.com/cnkzlyr/udemobile/releases)
[![UYAP](https://img.shields.io/badge/Format-UYAP_UDF_v1.8-0D47A1.svg)](https://uyap.gov.tr)
[![Word](https://img.shields.io/badge/Format-MS_DOCX_OpenXML-2B579A.svg?logo=microsoft-word&logoColor=white)](https://microsoft.com)
[![5070 E-İmza](https://img.shields.io/badge/5070_S.K.-E--İmza_%26_Mobil_İmza-darkgreen.svg)](https://www.mevzuat.gov.tr/mevzuat?MevzuatNo=5070&MevzuatTur=1&MevzuatTertip=5)
[![Lisans](https://img.shields.io/badge/Lisans-MIT-green.svg)](LICENSE)

**CanEditor (UdeMobile)**; avukatlar, hakimler, savcılar ve hukuk profesyonelleri için geliştirilmiş **tek çatı birleşik hukuk platformudur**. Masaüstünde (Windows, macOS, Linux), Android'de (Termux'suz) ve web tarayıcısında:
- **%100 Havelsan UYAP uyumlu UDF & Word editörü** (tek başına CanEditor — ikinci editör uygulaması gerekmez)
- **Çoklu E-İmza & Birlikte İmza (Co-signing)** desteği (aynı anda takılı birden fazla akıllı kart/token arasında geçiş, imzalı belgede bozulma olmadan ek imza ekleme)
- **Resmî Havelsan JAR ve Saf Python PDF motoru** (UDF → PDF / ODT / DOCX + paylaşım)
- **UYAP Dosya Yönetim Merkezi & Dosya Hesapları** (tüm davalar, icra takipleri, finansal alacak/tahsilat/bakiye/avans dökümleri, kart, tablo ve ağaç hiyerarşisi)
- **Yeni Evrak Toplu Yönetimi** (toplu indirme, PDF dönüştürme, Drive'a gönderme, görüldü sayma ve sayfalama)
- **Görünmez arka plan UYAP oturumu** (e-İmza takılıyken e-İmza, değilken hiç tarayıcı penceresi göstermeden Mobil İmza ile sürekli bağlı)
- **Google Drive sürekli eşitleme & kesintisiz durum göstergesi** (Drive dosyalarında anlık arama ve doğrudan açma)
- **Notion & TickTick canlı yönetimi + otomatik aktarım**
- **`hayfahukuk.com` entegrasyonu** (Yargıtay İçtihat Arama, uygulama içi Mevzuat Okuyucusu, Hukuk Haberleri, günlük Resmî Gazete, **%100 çevrimdışı Adliye & IBAN Rehberi**, 7 hukuki hesaplayıcı)

> [!TIP]
> 📖 **Adım Adım Kolay Tutorial:** Tek komutla dosya arşivleme (`uyap-arsiv`) ve sessiz e-imza (`uyap-imzala`) adım adım resimli kullanım kılavuzu için: **[docs/KILAVUZ_VE_TUTORIAL.md](docs/KILAVUZ_VE_TUTORIAL.md)**

---

## 🧩 v4.10.0: Tek Depo, Tek Uygulama — Birleşik Terminal (`caneditor`), Bozuk PDF'in Kökten Çözümü, Gömülü Resmî UYAP Jar'ları, Öz-Denetim ve Ayrıntılı İpuçları

Bu sürümde dağınık depolardaki (`uyap-evrak-indirici`, `avukatasistan`, `eimza-one`, `hayfahukuk`, `uyap-editor-modern`, `uyap-termux-pro`, `naps-uyap-thunar-tools`) **bütün özellikler CanEditor'da toplandı**; grafik arayüzün yaptığı her şey artık **her platformda terminalden** de yapılabiliyor.

### 1. 📦 Depolar birleştirildi
| Kaynak depo | CanEditor içindeki yeri | Bu sürümde gelen |
|---|---|---|
| `uyap-evrak-indirici` | `asistan/moduller/evrak` | Drive arşiv denetimi/eşitleyici (`drive_arsiv_denetle.py`, `drive_arsiv_esitle.py`, `uyap-drive-*`), `tarama_tamamla.py`, öncelik kilitlenmesi, Windows MAX_PATH ve Google Drive kilit düzeltmeleri, Java 8 uyumlu dönüştürücü, GUI/Terminal başlatıcıları (3 yönlü birleştirme; CanEditor'daki yerel düzeltmeler korundu) |
| `eimza-one` | `platform/eimza-one` | Android'de ArkSigner / TÜRKTRUST TBB / Kamu SM tokenları için ara yazılımsız e-imza uygulaması: kaynak + **tüm jar'lar**. Her `v*` sürümünde `E-Imza-One-v<sürüm>.apk` olarak aynı Release'e eklenir (`.github/workflows/eimza-one.yml`) |
| `hayfahukuk` | `asistan/hayfa_kopru.py` | Mevzuat arşivinde **madde metni içinde** arama (`yer=madde`) |
| `uyap-editor-modern`, `uyap-termux-pro`, `naps-uyap-thunar-tools`, `avukatasistan` | `platform/…`, `asistan/moduller/…` | Farklar denetlendi: CanEditor kopyaları güncel |

### 2. 📄 "PDF bozuk çevriliyor" — kök neden bulundu ve giderildi
Üç ayrı hata üst üste biniyordu:
1. **Yanlış argüman:** `sunucu.py` dönüştürücüyü `udf_to_pdf(udf, hedef_pdf)` diye çağırıyordu; işlevin ikinci parametresi `timeout` olduğu için hedef yol zaman aşımı sanılıyor, Java çağrısı `TypeError` ile düşüyor, hata **sessizce yutuluyor** ve her UDF yedek motora gidiyordu.
2. **Bozuk yedek motor:** Yedek (ReportLab) motor `content.xml`'deki bütün metni tek paragraf olarak **Helvetica** ile basıyordu: satır sonları kayboluyor, `ş ğ ı İ` kara kutu oluyor, hizalama/kalın/girinti yok sayılıyordu. Baştan yazıldı: UDF'in UTF-16 ofset modeli, hizalama (0/1/2/3), sol/sağ/ilk satır girintisi, önce/sonra boşluk, satır aralığı, kalın/italik/altı çizili, tablolar ve sayfa kenar boşlukları okunur; Times New Roman/Arial TTF gömülür.
3. **Font eşleşmesi:** Resmî Havelsan motoru, Times New Roman sistemde kurulu değilse (Linux/macOS/Android başsız Java) gömülmemiş Helvetica'ya düşüyordu. `UdfBatchPdfConverter` artık pakete gömülü TTF'leri JVM'e kaydediyor → **Times New Roman gömülü, Türkçe birebir**. Hatalar artık gizlenmiyor; 0 baytlık PDF bırakılmıyor; çıkış kodu anlamlı.

**Resmî UYAP Editör jar'ları (5.4.20) depoya ve tüm masaüstü paketlerine gömüldü** (`asistan/jars/uyap-editor`, ~46 MB) — UDF→PDF/ODT/DOCX için UYAP Editör kurmak gerekmez. Daha önce bozuk üretilmiş PDF'ler öz-denetim tarafından bulunup **resmî motorla yeniden üretilir**.

### 3. ⌨️ `caneditor` — arayüzün yaptığı her şey terminalde (Windows · macOS · Linux · Android/Termux)
Arayüzdeki her düğme yerel Hukuk Asistanı sunucusunun bir `/api` uç noktasını çağırır; `caneditor` **aynı uç noktaları** çağırır. Açık bir CanEditor varsa ona bağlanır; yoksa sunucuyu kendi içinde geçici olarak açar. Python yoksa paketteki Python'suz ikiliyle çalışır.

```bash
caneditor durum                                   # sunucu, UYAP/UETS oturumu, e-imza, Java/jar
caneditor uyap giris                              # arka planda: kart takılıysa e-imza, yoksa Mobil İmza
caneditor evrak ara "bilirkişi" --kategori bilirkisi --baslangic 2026-11-01 --muvekkil "Ahmet"
caneditor pdf ~/UYAP_Indirilenler                 # klasördeki UDF/TIFF/görüntü/Office → PDF
caneditor donustur dilekce.udf --bicim docx       # resmî Havelsan motoru
caneditor imzala dilekce.udf                      # oto: kart → sessiz e-imza, yoksa Mobil İmza
caneditor uets senkron                            # UETS tebligatları → süre → TickTick/Notion
caneditor ticktick denetle                        # mükerrer/eksik raporu (değişiklik yapmaz)
caneditor ticktick duzenle                        # uygular (tamamlanan + yapılmayacak görevler dahil)
caneditor gorev evrak-nobetci --izle              # Görevler sekmesindeki herhangi bir görev
caneditor hayfa mevzuat "kira" --madde            # HAYFA mevzuat arşivinde madde metninde ara
caneditor ajanda --gun 30 · caneditor sure 20.11.2026 · caneditor a4 *.jpg -o ek.pdf
caneditor oz-denetim                              # kendini test et + onar
caneditor log -f --kaynak gorev/uets-senkron      # birleşik günlüğü canlı izle
caneditor api GET /api/dosyalar q=2026/12         # her uç nokta doğrudan
caneditor --json …                                # betikler için ham JSON
```

### 4. 🩺 Kendi kendini denetleyen ve onaran uygulama + birleşik günlük
`asistan/oz_denetim.py` sunucu açıkken **her 3 saatte bir** çalışır (Asistan → **🩺 Sağlık / Günlük** ya da `caneditor oz-denetim`): Python modülleri, Java + resmî jar + fontlar, örnek UDF ile **gerçek PDF testi** (Türkçe metin + gömülü font doğrulanır), eski bozuk/0 baytlık PDF'lerin yeniden üretilmesi, SQLite bütünlüğü (bozuksa yedek + REINDEX), katalog tutarlılığı (diskte olmayan indirmeler yeniden kuyruğa, mükerrer ekler işaretlenir — kataloğun kendi onarımları çağrılır, dosya silinmez), kişisel ayarların varlığı, TickTick düzeninin 6 saatten eski olmaması ve disk alanı. Bütün modüllerin çıktısı tek günlükte (`gunluk/caneditor.log`, dönerli), kaynak/seviye/metinle süzülebilir; PIN'ler maskelenir.

### 5. ✅ TickTick: başlık değişse de mükerrer açılmaz, evrak başına görev açılmaz
- Eşleşme başlıktan **bağımsızdır**: kimlik satırı + **barkod** (+ UETS no). Kullanıcı başlığı değiştirse ya da kimlik satırını silse bile **tamamlanan** ve **yapılmayacak** (status −1) görevler tanınır; aynı tebligat için yeni görev açılmaz (`gorev_anahtarlari`, `_ayni_is_mi`). EK alt görevi tebligatı engellemez.
- **Evrak başına görev açılmaz:** UYAP evrakları dosya başına TEK bir "📥 UYAP evrakları (N)" görevinin kontrol listesinde toplanır (aynı evrak iki kez eklenmez; kapanmış toplu görevlerdeki evraklar yeniden listelenmez).
- **Sahte son gün yok:** Tahmini yasal son gün artık evrak tarihinden hesaplanır; 45 günden eski evraka son gün yazılmaz (eskiden yıllar önceki evraka bugünden hesaplanmış son gün yazılıyordu).
- Düzen turu yalnız TickTick bağlıyken de çalışır (öz-denetim başlatır).

### 6. 🖱️ Arayüz: her düğmede ayrıntılı açıklama, her listede pratik süzgeç
- **İpuçları (`ipucu.js`):** Fareyle üzerine gelince (dokunmatikte uzun basınca) "ne yapar · klavye kısayolu · terminal karşılığı" kartı. Editördeki 317 kontrolün 315'i ayrıntılı açıklamalı (UYAP paragraf seçeneklerinin nk/cm karşılıkları ve UYAP varsayılanları dahil).
- **Her tabloda süzgeç + sıralama:** Asistan/HAYFA tablolarının üstünde "bu tabloda süz" kutusu (Türkçe-duyarsız, `-kelime` hariç tutar); sütun başlığına tıklayınca tarih/sayı/metin olarak sıralar.
- **Hızlı tarih çipleri:** İki tarih alanı olan her süzgece "Bugün · Son 7/30 gün · Önümüzdeki 7/30 gün · Bu ay · Geçen ay · Bu yıl · Temizle". Ayrıntılı süzgeçler (müvekkil, kategori, tür, durum, dosya durumu) aynen duruyor.

### 7. 🔐 Kişisel bilgiler koddan çıkarıldı
E-imza PIN'i, TC, GSM, Telegram bot anahtarı ve Drive webhook adresi bazı betiklerde **sabit yazılıydı**. Hepsi `asistan/kisisel_ayar.py` üzerinden ortam değişkeni ya da `~/.caneditor/kisisel.json` (izin 600) / `.uyap_config.json` / `~/.uki/mobileConfig`'den okunur. PIN tanımlı değilse kart **hiç denenmez** (bloke riski yok), doğrudan Mobil İmza kullanılır.

```json
// ~/.caneditor/kisisel.json
{ "pin": "<e-imza PIN>", "tc": "<TC>", "gsm": "05XXXXXXXXX", "operator": "turktelekom",
  "telegram_token": "<bot token>", "telegram_chat": "<chat id>", "drive_webhook": "<Apps Script URL>" }
```

---

## 🔐 v4.9.5: Sessiz (Headless) USB E-İmza & Çapraz Platform UDF İmzalatıcı

CanEditor Hukuk Asistanı ve komut satırı aracı (`uyap-imzala`), **Termux (Android)**, **Windows**, **Linux (Ubuntu / Fedora)** ve **macOS** üzerinde UDF belgelerini tek komutta resmi CAdES-BES formatında imzalar ve doğrular.

```
                         ┌─────────────────────────────────────────────────────────┐
                         │              CANEDİTÖR İMZA MOTORU                     │
                         │              (uyap-imzala / asistan / imza.py)          │
                         └────────────────────────────┬────────────────────────────┘
                                                      │
                       ┌──────────────────────────────┴──────────────────────────────┐
                       ▼                                                             ▼
         ┌───────────────────────────┐                                 ┌───────────────────────────┐
         │   USB E-İMZA (ArkSigner)  │                                 │   UYAP MOBİL İMZA (SIM)   │
         │  (Port 5975 / CCID / APDU)│                                 │  (Port 5976 / Havelsan)   │
         └─────────────┬─────────────┘                                 └─────────────┬─────────────┘
                       │                                                             │
         ┌─────────────┴─────────────┐                                 ┌─────────────┴─────────────┐
         │ • Sıfır popup, sıfır onay │                                 │ • OTA Binary SMS / STK    │
         │ • APDU VERIFY PIN (******)│                                 │ • Ekranda zorunlu PIN     │
         │ • 0.3 sn sürede imzalama  │                                 │ • 5070 s. Kanun gereği    │
         │ • %100 Arka Planda Sessiz │                                 │ • Donanım yokken Yedek    │
         └─────────────┬─────────────┘                                 └─────────────┬─────────────┘
                       │                                                             │
                       └──────────────────────────────┬──────────────────────────────┘
                                                      ▼
                                       ┌─────────────────────────────┐
                                       │   Resmi CAdES-BES sign.sgn  │
                                       │    + content.xml -> .UDF    │
                                       │    + İsteğe bağlı .PDF      │
                                       └─────────────────────────────┘
```

### 1. Teknik ve Yasal Nedenler

#### ❓ Mobil İmza (SIM Kart) Neden Arka Planda Sessizce İmzalanayamaz?
* **SIM Kart İçi Güvenli Çip (Secure Element):** Mobil imzanın özel anahtarı (private key) telefonun işletim sisteminde veya dosya sisteminde değil, doğrudan SIM kartın çipinin içindeki kriptografik donanım alanında kilitlidir. Android, iOS veya Termux bu anahtara asla erişemez.
* **Operatörün SIM Toolkit (STK) Protokolü & ETSI TS 102 204:** UYAP imza talebini operatöre (Türk Telekom, Turkcell, Vodafone) ilettiğinde, operatör baz istasyonundan SIM karta özel bir ikili (binary) OTA SMS gönderir. SIM kart çipi bu sinyali aldığında donanımsal olarak işletim sistemine `GET INPUT` komutu verir ve Android o tanıdık SIM Toolkit modal ekranını zorunlu olarak ekrana basar.
* **5070 Sayılı Elektronik İmza Kanunu & Güvenlik Kuralı:** 5070 Sayılı Kanun gereğince inkar edilemezlik (non-repudiation) ilkesi esastır. SIM kart çipinin donanım yazılımı (firmware), o ekrandan PIN girilip "Tamam" denmediği sürece `COMPUTE SIGNATURE` işlemini yapmayı fiziksel olarak reddeder.
* **Android Güvenlik Duvarı:** SIM Toolkit ekranı Android'in en yüksek güvenlikli katmanında açıldığı için, arka plandaki hiçbir programın o ekrana gizlice tuş basması (`INJECT_EVENTS` kısıtlaması) mümkün değildir. Bu sayede zararlı yazılımların kullanıcının haberi olmadan işlem yapması engellenir.

#### ⚡ USB E-İmzada (ArkSigner / CCID SmartCard) Neden %100 Sessiz İmza Mümkündür?
İşte tam olarak bu nedenle USB E-İmza (ArkSigner, Akis vb.) otomasyon ve arka plan işleri için biçilmiş kaftandır:
* **Doğrudan CCID / PC/SC APDU İletişimi:** Telefona OTG ile veya bilgisayara USB portundan bağlanan token ile doğrudan standart ISO 7816 akıllı kart APDU komutlarıyla haberleşilir.
* **Sıfır Ekran, Sıfır Popup:** PIN kodunuz (ör. `<PIN>`) komut satırından veya arka uç API'sinden karta doğrudan kriptografik APDU paketi olarak gönderilir (`VERIFY PIN`). Ekranda hiçbir onay kutusu, bildirim veya açılır pencere belirmez.
* **Sub-second (0.3 saniye) Hız:** Dosyayı gönderdiğiniz an 0.3 - 0.5 saniye içinde tamamen sessizce CAdES-BES imzası üretilir.
* **UYAP & CanEditor Birebir Uyumluluğu:** Adalet E-İmza servisinin `POST /api/v1/docsignature/signdigest` uç noktası doğrudan `content.xml` belgesinin SHA-256 özetini imzalar; bu sayede CanEditor veya UYAP Editör'de açıldığında **"İçerik özeti uyuşmuyor"** hatası asla yaşanmaz.

---

### 2. Çapraz Platform (Cross-Platform) Terminal Desteği

`uyap-imzala`, Python 3 standart kütüphaneleriyle yazılmış olup harici derleme gerektirmeden tüm platformlarda yerel olarak çalışır:

| Platform | Çalışma Ortamı | E-İmza Altyapısı | Komut Örneği |
|---|---|---|---|
| **Android (Termux)** | Termux CLI / Widget | CCID Köprüsü (`ccid_bridge.py`) + Adalet Servisi | `uyap-imzala dilekce.udf` |
| **Windows 10/11** | PowerShell / CMD / Terminal | Windows SmartCard (WinSCard) + Adalet E-İmza Tray | `uyap-imzala.bat dilekce.udf` veya `python uyap_imzala.py dilekce.udf` |
| **Linux (Ubuntu/Debian)** | Bash / Zsh | pcsc-lite (`pcscd`) + Adalet E-İmza | `./uyap-imzala dilekce.udf` |
| **Linux (Fedora/RHEL)** | Bash / Zsh | pcsc-lite (`pcscd`) + Adalet E-İmza | `./uyap-imzala dilekce.udf` |
| **macOS (Darwin)** | Terminal / iTerm2 | CryptoTokenKit / PCSC + Adalet E-İmza | `./uyap-imzala dilekce.udf` |

---

### 3. Komut Satırı Kullanım Kılavuzu

```bash
# 1. Otomatik İmzalama (Kart takılıysa sessiz e-imza, takılı değilse Mobil İmza fallback)
uyap-imzala dilekce.udf

# 2. Özel PIN belirterek imzalama
uyap-imzala dilekce.udf --pin <PIN>

# 3. Donanım kartını atlayıp doğrudan UYAP Mobil İmza ile imzalama
uyap-imzala dilekce.udf --mobil --operator 2 --gsm 05XXXXXXXXX

# 4. İmzalandıktan sonra anında vektörel PDF önizlemesini de üretme
uyap-imzala dilekce.udf --pdf

# 5. UDF dosyasındaki imzanın geçerliliğini ve SHA-256 özetini doğrulama
uyap-imzala dilekce_IMZALI.udf --dogrula

# 6. Takılı akıllı kart, sertifika sahibi ve servis durumlarını sorgulama
uyap-imzala --durum

# 7. Çoklu / toplu imzalama
uyap-imzala evrak1.udf evrak2.udf klasor/*.udf
```

---

### 4. CanEditor Hukuk Asistanı REST API Uç Noktaları

CanEditor Asistan (`sunucu.py`) arka ucuna tam entegre edilen uç noktalar:

* `GET /api/imza/durum` → Takılı kartı, sertifika sahibini, mobil servis ve sessiz imza hazır olma durumunu JSON olarak döner.
* `POST /api/imza/imzala` → Belirtilen UDF belgesini sessizce imzalar, `_IMZALI.udf` (ve isteğe bağlı PDF) üretir:
  ```json
  {
    "udf": "C:/Dava/Dilekce.udf",
    "pin": "<PIN>",
    "yontem": "oto",
    "pdf": true
  }
  ```
* `POST /api/imza/dogrula` → Belgenin imzasını ve içerik özetini (`content.xml` vs `sign.sgn`) denetler:
  ```json
  {
    "udf": "C:/Dava/Dilekce_IMZALI.udf"
  }
  ```

---

## 📨 v4.9.4: Tebligat EYP'leri ve Ekler Eksiksiz

- **EYP paketleri inmiyordu (401 / HTTP 0):** UETS erişim anahtarı liste alınırken bir kez okunuyordu. TickTick kontrolü dakikalarca sürünce anahtarın süresi doluyordu ve ilkinden sonraki EYP'ler inmiyordu. Artık her EYP'den önce portalın tazelediği güncel anahtar okunuyor. Oturum düşmüşse UETS'e yeniden giriş yapılıyor (Gmail'den kod otomatik alınıyor) ve indirme bir kez daha deneniyor.
- **Ekler TickTick'e gitmiyordu:** TickTick'e dosya yalnızca e-postayla eklenebiliyor. Bunun için gereken **TickTick e-posta adresi** arayüzde hiç sorulmuyordu. Bu yüzden ekler "E-posta ile görev gönderilemedi" uyarısıyla düşüyordu. Adres alanı Notion / TickTick / Telegram → API Anahtarları bölümüne eklendi; eksikse kırmızı uyarı gösteriliyor. Eksik ekler adres girildikten sonraki turda gönderiliyor.
- **Görev hiç açılmıyordu:** E-posta gönderilemeyince yeni tebligatın görevi 6 saat boyunca açılmıyordu (süre riski). Artık görev hemen eksiz açılıyor, ekler sonra altına ekleniyor.

---

## 🧭 v4.9.3: Okunur Günlükler, Kendiliğinden Bağlanan UYAP, Müvekkil Seçici ve Sade Drive Senkronu

- **Günlükler okunuyor:** Görevler ve UYAP Giriş sekmelerindeki günlük kutuları açık gri zemine açık gri yazıyla çiziliyordu; yazı ancak seçince görünüyordu. Artık koyu zemin üzerinde açık yazıyla gösteriliyor. Yukarı kaydırdığınızda ya da metin seçtiğinizde kutu donuyor, satırlar kaymıyor ve sayfa başa zıplamıyor. En alta inince canlı akış devam ediyor.
- **UYAP oturumu "Bağlanılıyor…"da kalmıyor:** Oturum durumu yalnızca son 400 günlük satırında aranıyordu. Hesap satırları bu tamponu birkaç dakikada doldurduğu için oturum açıkken bile durum kayboluyordu. Durum artık satır satır izleniyor ve kalıcı tutuluyor; oturum nabzının sonucu da hesaba katılıyor.
- **"UYAP oturum aç (e-imza)" görevi çalışıyor:** Görev `--mode login` ile çağrılıyordu ama indirici bu modu tanımıyordu (`invalid choice: 'login'`). Mod eklendi: yalnızca oturumu açıp doğruluyor.
- **TickTick HTTP 429 seli bitti:** UETS, TickTick düzeni ve otokontrol, kapalı görev listesini ayrı ayrı onlarca istekle çekiyordu. Her süreç her denemeyi günlüğe yazıyordu. Artık istek sınırı tüm süreçler arasında paylaşılıyor, `Retry-After` dikkate alınıyor ve günlüğe tek satır yazılıyor. Kapalı görev listesi diskte 30 dakika önbelleğe alınıyor; sınıra takılınca bölerek çekme duruyor.
- **İşlemlerim indirmesi Windows'ta çökmüyor:** Uzun klasör adları (`Avukat Evrak Kaydi (İstinaf Ba…`) 260 karakter yol sınırını aşıyordu. Yol artık sınıra sığacak şekilde kısaltılıyor; benzersiz evrak numarası korunuyor.
- **Notion/TickTick denetimi:** Ham Python hatası ya da "Failed to execute script" yerine anlaşılır tek satır gösteriliyor. Notion güvenlik durdurması (🛑) "Hata" sayılmıyor, uyarı olarak görünüyor.
- **Diğer:** Hesap satırları iki kez yazılmıyor, sıfır tutarlı satırlar günlüğe düşmüyor. Uzun Telegram özetleri bölünerek gönderiliyor (eskiden "message is too long" hatası alınıyordu). Katalog yedeği Drive'da `.tmp.db` olarak yarım kalmıyor (WinError 32). UETS CSV temizliğinde yanlış "Silinemedi" uyarısı çıkmıyor. Drive aramasında uygulamanın iç dosyaları gösterilmiyor. Yeni Evrak sekmesindeki toplu işlem düğmelerinin yazısı artık görünüyor.

### ⚡ Elle "indir" dediğiniz her şey öncelikli
- Dosya penceresindeki **"⚡ Hemen indir + Drive'a eşitle"**, her evrak satırındaki **"⚡ İndir"** ve Yeni Evrak sekmesindeki **"Seçilenleri İndir"** artık ortak bir öncelik kuyruğuna yazıyor. Senkron bu kuyruğa her evraktan önce bakıyor. O an arşiv paketi indiriyor, katalog listeliyor ya da açık dosyaları tarıyor olsa bile 1-2 saniye içinde işi bırakıyor. Önce sizin istediklerinizi indirip PDF'e çeviriyor ve Drive'a eşitliyor, sonra kaldığı yerden devam ediyor. Evrak listesi henüz alınmamış bir dosyada önce liste alınıyor.
- İlerleme dosya penceresinde canlı görünüyor ("⚡ 34/117 evrak indi · ☁️ 30 Drive'a yüklendi · 83 kaldı"). Tek evrak düğmeleri de "⚡ 1/1 → ✅ İndi" diye ilerliyor.
- Eskiden "Seçilenleri İndir" yalnızca nöbetçiyi uyandırıyordu; seçilen evraklar hiçbir sıraya girmiyordu.

### 📨 Tebligat indirme düzeltmeleri
- **UETS:** CSV iniyordu, ama TickTick'e aktarma HTTP 429 döngüsünde saatlerce takılıyordu (paylaşılan istek sınırı ve 30 dakikalık önbellekle çözüldü). Tamamlanan görev listesi her tebligatta değil, 10 dakikada bir çekiliyor.
- **"UYAP: tebligat evraklarını indir":** 731 dosyanın hepsini UYAP'ta yeniden listeliyordu (147 paket, saatler). Senkron'la aynı gizli tarayıcıyı paylaştığı için ikisini de yavaşlatıyordu. Artık katalogdaki tüm indirilmemiş tebligat, mazbata ve tebellüğ belgeleri öncelik kuyruğuna alınıyor; Senkron bunları her şeyden önce indirip Drive'a eşitliyor. Görev kartı ilerlemeyi gösteriyor. Bu sırada elle istenen tek bir dosya yine araya girebiliyor (100'lük parçalar).

### 👤 Her yerde müvekkil seçici
- **Dosyalar, Evrak Ara, Tebligatlar, Yeni Evrak, Ajanda, Süre ve Dosya Hesapları** sekmelerinin hepsinde aynı müvekkil seçici var. Bir sekmede seçtiğiniz müvekkil hepsinde geçerli oluyor ve seçim hatırlanıyor.
- **Benzer yazılmış adlar birlikte önerilir:** UYAP'ta aynı müvekkil farklı yazılmış olabilir (ör. "ABC İNŞ. LTD. ŞTİ." ve "ABC İNŞAAT LİMİTED ŞİRKETİ", rol ekleri, fazladan boşluk ya da tek harf farkı). Seçicide bu adlar "≈ benzer yazım" diye işaretleniyor ve "Hepsini birlikte seç" öneriliyor.

### 🔎 Yeni filtreler
- **Evrak Ara:** 📨 Tebligatlar, ⚖️ Kararlar, 🗓️ Duruşma zaptı, 🔬 Bilirkişi ve ✍️ Dilekçeler için hızlı çipler var. Tebligat filtresi tür ya da açıklamasında tebligat/mazbata geçen evrakları da buluyor. Açık/kapalı dosya ve tarih aralığı filtreleri eklendi. Kategori listesi artık sabit ve eksiksiz.
- **Tebligatlar:** Süresi işleyenler, son günü geçmiş olanlar, TickTick'te eksik ya da eki bekleyenler ve EYP paketi inmemiş olanlar ayrı ayrı süzülebiliyor. Liste artık hemen açılıyor: son liste gösteriliyor, arka planda tazeleniyor.

### ☁️ Sade Google Drive senkronu
- Drive sekmesinde artık tek bir durum satırı ve tek bir **"Şimdi eşitle"** düğmesi var. Senkron açıkken bütün UYAP evrakı kendiliğinden Drive'a gidiyor. Ayrıntılar, indeksleme ve kurulum ayarları katlı "Gelişmiş" bölümünde duruyor.
- **Drive'a "bir türlü aktarmıyor" sorunu:** Drive tarafı tıkalı değildi; inen her evrak zaten Drive'a gidiyordu ("0 Drive'a aktarılacak"). Darboğaz UYAP'tan indirmeydi. Örnek bir 15 dakikada indirme yalnızca bir kez, 1,5 dakika çalışmış, 50 evrağın 44'ü indirildikten sonra mükerrer çıkıp atılmıştı. Kalan süreyi katalog listeleme (90 sn'de bir), hesap çekme (5 dk'da bir) ve açık dosya taraması alıyordu. Artık her turda yaklaşık 4 dakika kesintisiz indirme yapılıyor (100'lük paketler). Bekleyen evrak varken katalog 6 dakikada, hesaplar 30 dakikada bir çekiliyor. Önce asıl evraklar indiriliyor, ekler sonra geliyor; ekler çoğunlukla başka bir evrakın kopyası.
- **Mükerrerler liste okunurken ayıklanıyor:** Bir dosyanın evrak listesi kataloğa yazılırken aynı dosya adı anahtarı ve daha önce aynı içerikle gelmiş ek kalıpları hemen mükerrer işaretleniyor. İndirme döngüsü mükerrer aramak için beklemiyor. Eskiden her mükerrerde 247 bin satırlık tablo yeniden taranıyordu ve her indirme partisinden önce on binlerce yol Drive diskinde tek tek yoklanıyordu (artık en çok 6 saatte bir).

---

## ✍️ v4.9.2: Editörde Tümünü Seç ve Biçimlendirme Düzeltmeleri

- **Ctrl+A tüm belgeyi seçer:** Her sayfa ayrı bir düzenleme alanı olduğu için tarayıcı seçimi yalnızca odaktaki sayfada gösteriyordu; mobil ve tablette (harici klavye) de yalnızca o sayfa seçiliyordu. Artık seçim sürdükçe sayfalar geçici olarak tek bir düzenleme alanı oluyor, yani bütün sayfalar seçili görünüyor. Kalın, hizalama, yazı tipi, kopyala/kes ve "yaz, tamamını değiştir" işlemleri tüm belgeye uygulanıyor. İmleç tek bir sayfaya inince eski haline dönüyor.
- **Hizalama seçimin tamamına uygulanır:** Tarayıcının kendi hizalama komutu artık kullanılmıyor. Eskiden yalnızca imlecin bulunduğu paragrafın kayıtlı hizalaması (`data-orig-align`) güncelleniyordu; bu yüzden mobil düzende ve UDF kaydında seçimdeki diğer paragraflar eski hizalamaya dönüyordu. Ayrıca komut paragrafları `<div>` içine sarıp yapıyı bozuyordu. Artık seçimle kesişen bütün paragraflara, sayfalar arası dahil, hizalama doğrudan yazılıyor.
- **Yazılar üst üste binmez:** Biçim, hizalama, yazı tipi ya da punto değişince UYAP sekme genişlikleri (`udf-tab-space`) yeni ölçüye göre yeniden hesaplanıyor ve sayfa düzeni tazeleniyor.

---

## 🩹 v4.9.1: Mobil İmza Girişi Düzeltmesi (Android)

- **Mobil İmza yeniden çalışıyor:** v4.9.0'da UYAP/UETS yalnızca pencereye hiç eklenmemiş bir WebView'da çalıştırıldı. Chromium bu sayfaları gizli sekme sayıp zamanlayıcılarını kısıyor (5 dakika sonra dakikada bir). Bu yüzden UYAP giriş ve e-Devlet Mobil İmza sayfaları ilerlemedi, form gönderilmedi ve süre doldu. Otomasyon WebView'ları artık uygulama penceresine **ekran dışında** ekleniyor: tam hızda çalışıyorlar ama ekranda görünmüyorlar ve dokunulamıyorlar.
- **Görünür ekran yine korunuyor:** Editör, Asistan ve UYAP mobil görünümü yerel adreslerden açıldığı için DevTools köprüsünde yerel adresleri üzerinden ayıklanıyor; otomasyon bu ekranlara hiç dokunmuyor.
- **Tanı:** Giriş sırasında hangi adımda kalındığı (UYAP giriş, e-Devlet formu, onay bekleme, OAuth) günlüğe yazılıyor. Tanı dosyasına son 40 satır ekleniyor.

---

## 🛰️ v4.9.0: Tamamen Arka Planda UYAP/UETS, Tüm Arşivin Kataloğu, Dosya Penceresinde Eksiksiz Bilgi ve Denetim

- **Görünür tarayıcı yok:** Telefonda UYAP Avukat Portal ve UETS giriş sayfaları artık ekrana gelmez. Sebep, DevTools köprüsünün uygulamadaki tüm WebView'ları listelemesi ve otomasyonun görünür Asistan ekranını UYAP/UETS'e yönlendirmesiydi. Köprü artık yalnızca ekrana hiç eklenmemiş (`never_attached`) gizli WebView'ları gösterir ve `/json/new` isteğini reddeder. UETS için ayrı bir gizli WebView açılır, böylece UETS girişi UYAP oturumunu düşürmez.
- **Tüm UYAP arşivinin kataloğu:** Arşiv listesi takılıp kalıyordu (732 dosyadan 3'ü listelenmişti). Sebep, UYAP'ın kalıcı hata verdiği dosyaların sıranın başında kalıp her turu tüketmesiydi. Yeni sıra: önce öne alınan dosyalar, sonra hiç denenmemişler; geçici hatalılar 2 saat, kalıcı hatalılar 14 gün bekler. Katalog her turda değil 1,5 dakikada bir 40 dosya ilerler. Büyük icra dosyalarının evrak sayfaları 5'erli paralel çekilir (600 sayfaya kadar).
- **Taraflar ve hesaplar:** Tarafı boş dosyaların tarafları hızlı ayrı bir geçişle tamamlanır (turda 120 dosya). Dosya hesapları (icra kapak hesabı, tahsilat/reddiyat, safahat) arşiv indirmesi sürerken de 5 dakikada bir 25 dosya tazelenir; eskiden arşiv bitene kadar hiç çekilmiyordu. Dosyaların oturuma özgü kimlikleri her turda yenilenir.
- **Dosya penceresi:**
  - **🔄 UYAP'tan şimdi getir:** Taraflar, tüm evrak listesi, hesap ve safahat gizli oturumla getirilir. Eksik bir bölüm varsa pencere açılınca kendiliğinden başlar.
  - **☁️ Evraklarını Drive'a indir:** Dosya, indirme sırasının başına alınır; Senkron kapalıysa açılır.
  - **📮 Tebligat süreçleri:** UYAP mazbatalarından muhatap, sonuç, yasal tebliğ tarihi ve süre notu ile katalogdaki tebligat evrakları birlikte gösterilir.
- **Evrak Ara:** Taraf, müvekkil, birim ya da esasa göre eşleşen dosyalar da gösterilir; evrak listesi henüz alınmamış dosyalar dahil. "Murat Ertek" gibi taraf adıyla arama artık sonuç verir.
- **Google Drive indeksi:** Eski Apps Script betiğinin hatası ("Bağımsız değişken boş olamaz: data") tanınır. Ekranda tek tıkla betik kopyalama ve "Yeni sürüm" ile dağıtma yönergesi çıkar; web uygulaması adresi değişmez.
- **Yargıtay karar sayısı:** Karar kimlikleri ardışık olmadığı için 2.559 görünüyordu. Sayı artık hayfahukuk.com'un kendi arşiv sayacından okunur (~160 bin) ve 24 saatlik / 7 günlük artış gösterilir.
- **UETS giriş kodu (Gmail):** Uygulama şifresi 16 harf değilse ekranda anında uyarı çıkar. Giriş hatasında kullanılan adres gösterilir. Bağlantı testi, UETS iletilerinin o Gmail hesabına gelip gelmediğini denetler.
- **🔍 Denetim (Entegrasyonlar → Düzen & Durum):** Tek düğmeyle, hiçbir şeyi değiştirmeden karşılaştırma yapılır:
  - UYAP: listesi alınan dosya, tarafsız dosya, hesabı çekilen dosya, kategorisiz evrak.
  - Drive: indirilen ve yüklenen evrak, indeks.
  - Notion: eşleşen dosya, Notion'da olmayan dosya, mükerrer sayfa, taraf bağı ya da konusu eksik sayfa.
  - TickTick: mükerrer görev, kartı olmayan dosya, biçimi bozuk görev.

---

## 🩹 v4.8.1: Android'de Dosya Seçme Düzeltmesi

- **Android dosya seçici:** `.cnayar` (ayar yedeği) ve `.udf` gibi Android'in tanımadığı uzantılı dosyalar seçicide gri görünüp seçilemiyordu. Seçici artık bilinmeyen uzantıda tüm dosyaları gösteriyor, dosyanın doğruluğunu uygulama kontrol ediyor. Çoklu seçim desteklenir.
- **Ayar yedeği:** Yanlış şifreden sonra aynı `.cnayar` dosyası yeniden seçilebilir.

---

## 🔐 v4.8.0: Anahtarları Bir Kez Girin — Şifreli Ayar Yedeği ve Tek Adımda Geri Yükleme

- **Otomatik şifreli yedek:** Entegrasyonlar → API Anahtarları'nda bir yedek şifresi belirleyin. Sonrasında her ayar değişikliğinden 15 sn sonra tüm ayarlar yedeklenir: Notion, TickTick, Telegram, Gmail uygulama şifresi, UETS, yapay zekâ özeti, Drive webhook/klasör ve UYAP T.C./GSM. Yedek iki yere yazılır: Google Drive'ınıza (`UYAP_Arsiv/_CanEditor_Ayar`, mevcut Apps Script ile; betikte değişiklik gerekmez) ve masaüstünde `~/CanEditor/ayar-yedegi.cnayar` dosyasına (uygulama kaldırılsa da kalır).
- **Tek adımda geri yükleme:** Yeni kurulumda Ana Ekran'da "Ayarlarınızı geri yükleyin" kartı çıkar. Kaynak seçenekleri: bu cihazdaki yedek, Google Drive (webhook + şifre) ya da `.cnayar` dosyası. Var olan ayarlar korunur.
- **Dosyaya yedek:** `.cnayar` dosyası telefona, USB'ye ya da e-postaya konabilir. e-İmza PIN'i yalnızca kutucuk işaretlenirse eklenir.
- **Güvenlik:** Yedek her zaman şifrelidir: PBKDF2-HMAC-SHA256 (300.000 tur) ve HMAC mühür; yalnızca standart kütüphane, tüm platformlarda aynı dosya açılır. Yanlış şifre ya da değiştirilmiş dosya reddedilir. Yedek şifresi yalnızca cihazdaki `.env` dosyasında durur, yedeğe girmez. Hiçbir anahtar uygulamanın içine ya da (herkese açık) depoya gömülmez.
- **Android'de ayarların silinmemesi için:** Depoya kalıcı imza anahtarı gizlileri (`ANDROID_KEYSTORE_B64`, `ANDROID_KEYSTORE_PASS`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASS`) eklendiğinde her APK eskisinin üstüne güncellenir ve uygulama verisi (ayarlar dahil) korunur.

---

## 🔎 v4.7.0: Önizleme, Dosya Penceresi, Tüm Arşivde Arama, İcra Kesinleşme/Takipsizlik, Canlı Bağlantılar

**Masaüstünde (Fedora/RPM, macOS) HTTPS düzeldi.** Paketli sunucu sistemin sertifika deposunu bulamadığı için Notion, TickTick, Telegram, Drive indeksi, İçtihat/Haber/Mevzuat/Resmî Gazete "CERTIFICATE_VERIFY_FAILED" ile düşüyordu. Artık sistem deposu (yoksa certifi) kullanılıyor.

**UETS giriş kodu (OTP) yeniden bulunuyor (`gmail_otp.py`).** Kod; 'UETS Giriş Kodu' etiketinde, Tüm Postalar'da ve Gelen Kutusu'nda, giriş anından sonra gelen ve daha önce kullanılmamış iletiden, HTML temizlenerek okunuyor. Gmail girişi reddedilirse, IMAP kapalıysa ya da ağ/SSL sorunu varsa açık Türkçe uyarı veriliyor (eskiden hepsi "kod gelmedi" görünüyordu).

**İndirmeden önizleme.** Her evrakta 👁 Önizle (PDF'e çevrilmiş hali) ve 🗂️ Orijinal (UDF / TIFF / PDF olduğu gibi) düğmeleri. Yerelde yoksa UYAP'tan önbelleğe alınır; UDF editörün kendi ayrıştırıcısıyla, TIFF sayfa sayfa, PDF tembel yüklemeyle çizilir. İndir ve Editörde aç da aynı pencerede.

**Dosya penceresi.** "Dosyaya git / Dosyayı gör" artık ayrı, sürüklenebilir bir pencerede açılıyor; çalıştığınız sekme kapanmıyor. Sekmeler: Genel (konu, icra durumu, son evraklar), Evraklar (aranır/süzülür, önizlenir), Hesap (tahsilat, reddiyat, harç kalemleri), Safahat, Taraflar, Duruşma & Tebligat, Drive (eşitleme göstergesi), Notlar. Ajanda, Tebligatlar, Yenilikler, Evrak Ara ve Dosyalar'dan açılabiliyor.

**Evrak Ara: UYAP arşivinin tamamı + Drive.** Nöbetçi her turda 60 dosyanın (kapalılar dahil) evrak listesini indirmeden kataloğa ekliyor; arama bütün UYAP evrakında ve Drive indeksinde birlikte yapılıyor. Arama sorgusu hızlandı (yüz binlerce evrakta donmuyor). Katalog, dosya ve Drive sayıları üstte gösteriliyor.

**İcra: kesinleşme ve takipsizlik (`icra_analiz.py`).** Safahat, evraklar (tensip/karar/talep), tebligat mazbataları ve UYAP borçlu bilgisiyle her açık icra dosyası için:
- "Kesinleştirilebilir": hangi tarihli ödeme/icra emrinin kime, ne zaman tebliğ edildiği ve itiraz süresinin (ilamsız 7 gün, kambiyo 5 gün, icra emri 7 gün) ne zaman dolduğu yazılı.
- İtiraz, süre işliyor, tebliğ bekleniyor durumları.
- Takipsizlik: son talep/işlemden bu yana geçen gün; 6 ay sarı, 9 ay turuncu, 1 yıl kırmızı uyarı.
- Dosya Hesapları sekmesinde ve dosya penceresinde; safahat artık hesapla birlikte düzenli çekiliyor.

**Süre ekranı.** Somut kanun yolu / işlem seçilerek hesap (HMK istinaf/temyiz/cevap/bilirkişi, İİK itiraz/şikâyet/istinaf, CMK, İYUK, işe iade, kesin süre) ve "Dosyalarımdaki işleyen süreler": tebligat son günleri, icra itiraz süreleri ve 1 yıllık işlemsizlik eşikleri tek listede, kalan güne göre.

**İnfaz: suç tarihine göre.** Suç tarihi, suç türü, ceza türü (süreli / müebbet / ağırlaştırılmış), tekerrür, yaş, mahsup ve teslim tarihi girilir; uygulanacak oran ve denetimli serbestlik süresi 5275, 7242 (30.03.2020 eşiği) ve 7456 (31.07.2023 eşiği) düzenlemelerine göre gerekçesiyle gösterilir. Renkli çubukta mahsup, cezaevi, denetimli serbestlik ve koşullu salıverilme sonrası dönem; kanun zaman çizelgesinde bu suça etkili olanlar işaretli. Tahmini tarihler (DS'ye çıkış, koşullu salıverilme, cezanın bitişi).

**Görevler sekmesi.** Otomatik çalışanlar üstte, elle araçlar katlanmış. Günlük artık yukarı zıplamıyor (yukarı kaydırdıysanız yerinde kalır). Linux'ta çalışmayan eski masaüstü pencereleri kaldırıldı.

**Bağlantı sekmesi canlı.** UYAP (oturum, e-İmza/Mobil İmza), UETS, Gmail (UETS kodu), Google Drive, Notion, TickTick, Telegram gerçekten deneniyor (Telegram'a mesaj atılmadan). Drive'daki dosya sayısı, UYAP dosya/evrak, tebligat, 3 gün içinde dolan süre, 7 gün içinde duruşma, Yargıtay karar sayısı ve kopma/yeniden bağlanma kayıtları gösteriliyor.

**Drive.** Webhook tanımlıysa Drive indeksi boşken hemen, sonra 12 saatte bir arka planda kendiliğinden yenileniyor; Drive'daki arşivin dosya sayısı her yerde görünüyor.

**Notion & TickTick sekmesi.** Yeni "Düzen & Durum" ekranı: TickTick temizliği ve UYAP → Notion eşitleme tek tıkla, canlı günlük ve son sonuç sayılarıyla. Kapatılan her kopya günlükte tek tek yazıyor. TickTick okuma zaman aşımları uzatıldı.

---

## 🛠️ v4.6.1: Linux (Fedora/RPM) ve paketli masaüstünde arka plan görevleri yeniden çalışıyor

- **Kök neden:** paketli masaüstü sürümünde UYAP nöbetçisi, sürekli senkron, Drive aktarıcı ve hesap tarama görevleri günlük ve veri klasörü olarak programın kurulu olduğu **salt-okunur** klasörü (`/usr/lib/CanEditor/...`) seçiyordu. Açılışta `Permission denied` ile anında çöktükleri için UYAP oturumu, senkron, tebligat ve hesaplar hiç çalışmıyordu.
- Görevler artık her zaman kullanıcının yazılabilir veri klasörünü kullanıyor (`UYAP_VERI_DIZINI` sunucu tarafından tüm görevlere veriliyor).
- Modüllerin kullanıcı klasörüne eşitlenen kopyaları, kaynak salt-okunur kurulmuş olsa da yazılabilir yapılıyor; sürüm yükseltmesindeki yeniden eşitleme de çökmüyor.
- Paketli ikili artık `python -c` karşılığını destekliyor (DNS tanısı "-c" dosya adı sanılıp çöküyordu).
- "UYAP → Notion eşitle" görevi paketli kurulumda da çalışıyor (betik diskte olmasa da modül olarak çalıştırılıyor; Notion/TickTick anahtarları eşitlenmiş klasörden okunuyor).
- Salt-okunur kuruluma birebir benzeyen ortamda (ayrı kullanıcı, izinleri kaldırılmış PyInstaller paketi) tüm görevlerin açıldığı doğrulandı; 3 yeni gerileme testi.

---

## 🗂️ v4.6.0: Gerçek Dosya Hesapları, UYAP → Notion Eşitleme, Dosya Konuları, Temiz TickTick

**Dosya hesapları artık UYAP'tan gelen gerçek rakamlar.** Önceki "Dosya Hesapları" ekranı UYAP'a hiç sormadan uydurma tutarlar gösteriyordu; icra dosyaları hiç çıkmıyor, artan avans ve harçlar yanlıştı.

- **İcra kapak hesabı:** asıl alacak (takipte kesinleşen), işlemiş faiz, vekâlet ücreti, masraf + tahsil harcı, toplam alacak, tahsil edilen, kasada bekleyen ve kalan bakiye; kesinleşme durumu ve borçlular (`dosya_hesap_bilgileri`, `dosya_tahsilat_reddiyat_bilgileri`, `dosya_borclu_list`).
- **Dava dosyaları:** yatırılan (tahsilat), kullanılan (reddiyat), ödenen harçlar kalem kalem ve **artan avans** (kasada kalan para).
- **İcra dosyaları listede:** dosya taraması avukatın yetkili olduğu tüm birim türlerini UYAP'tan dinamik alıyor (icra daireleri dahil); açık/kapalı ayrımı UYAP'ın kendi `dosyaDurum` alanından.
- Hesabı henüz çekilmemiş dosyada rakam gösterilmez ("UYAP'tan çekilmedi"). Senkron açıkken boşta her turda 10 dosyanın hesabı tazelenir; "🔄 Hesapları UYAP'tan çek" tümünü gizli oturumla çeker.
- **Dosyaya tıklayınca tek ekranda:** dosya konusu, taraflar (müvekkil işaretli, rol ve vekil), hesap kartı ("UYAP'tan yenile" düğmesiyle), evraklar, duruşmalar ve Drive dosyaları.

**UYAP → Notion sürekli eşitleme (`notion_uyap.py`).**
- Katalogdaki her dosya Notion "Tüm Dosyalar"a işlenir: eksik sayfa açılır, boş açılış tarihi doldurulur, durum Açık↔Kapalı eşitlenir.
- Taraflar: müvekkiller **Müvekkiller**'e, karşı taraflar **Diğer Taraflar**'a eklenir ve dosyaya bağlanır (var olan ilişki asla silinmez).
- **Aynı ikonlar:** üç veritabanında her sayfanın ikonu kendi veritabanının ikonu yapılır (📁 / 👨🏻 / 🧟‍♂️).
- Güvenlik: Notion okunamazsa hiçbir şey yazılmaz; olağandışı çok yeni dosya varsa onaysız açılmaz.

**Dosya konusu (5-10 cümle).**
- Her dosya için konu özeti Notion "DOSYA KONUSU" sütununa ve TickTick dosya kartının "📌 Dosya konusu" bölümüne yazılır.
- Entegrasyonlar'a **isteğe bağlı yapay zekâ anahtarı** (Claude ya da OpenAI) girilirse özet evrak metinlerinden yazdırılır. Anahtar yoksa dosya türü, taraflar, dava dilekçesi/iddianamedeki "KONU", önemli aşamalar ve son durumdan çıkarımsal özet kurulur; uydurma bilgi yok.
- **Elle yazdığınız konu asla ezilmez.**

**TickTick: mükerrer yok, eksik görev yok, her dosyaya kart (`ticktick_duzen.py`).**
- Mükerrer kontrolü artık **aktif + tamamlanan + YAPILMAYACAK** görevlerin tamamına bakıyor (yapılmayacaklar TickTick filtre ucundan okunur). Kapatılmış bir işin kopyası hangi yoldan gelirse gelsin açılmıyor.
- Yeni mükerrerlerin kaynağı kapatıldı: UYAP'a düşen her evrak kimliksiz "📄 ..." görevi açıyordu. Artık dosya kartının alt görevi olarak, kimlik satırıyla ve bir kez açılıyor. Eski kopyalar birleştirilip kapatılıyor (silinmiyor; notlar ve alt görevler asıl göreve taşınıyor).
- **Standart biçim:** tebligat, duruşma ve dosya kartının zorunlu öğeleri tanımlı. Eksik görev "⚠️ EKSİK: ..." satırı ve `eksik` etiketi alıyor; tamamlanınca kalkıyor.
- Üstyazısı ya da eki olmayan tebligatlar bir sonraki UETS turunda yeniden indirilip tamamlanıyor.
- Notion'da açık her dosyanın TickTick dosya kartı var; yoksa açılıyor. Bilgi notları da "📝 Bilgi Notu" kartı ve konusunu alıyor.
- Ana ekrana **🗂️ Notion & TickTick Düzeni** kartı eklendi: 6 saatte bir otomatik çalışıyor, "Şimdi düzenle" ile hemen çalıştırılabiliyor.

---

## 🏠 v4.5.0: Sade Asistan, Sürekli UYAP → Drive Akışı, 10 Dakikalık İmza İsteği Bitti

- **Ayrı "Hukuk Asistanı" simgesi** ve ana ekrandaki Asistan düğmesi editörü hiç açmadan doğrudan asistanı açar; kapatınca ana ekrana dönülür.
- **Yeni ana ekran**, iki büyük düğme: *UYAP → Google Drive senkronizasyonu* (başlat/durdur, arşivin yüzde kaçı işlendi, indirilen / sırada / Drive'da / ayıklanan mükerrer / UYAP'ta olmayan, şu an ne yaptığı, son indirme, oturum durumu) ve *Tebligat İzleyici* (UETS arka plan, sıklık, son kontrol). **İçtihat veritabanı** kartı: en son karar numarası, son 24 saat / 7 gün artışı (10 dk'da bir canlı).
- Menüde yalnız *Ana Ekran, Dosyalar, Tebligatlar*; diğer tüm araçlar "Diğer araçlar" altında katlı.
- **Telefona 10 dk'da bir gelen Mobil İmza isteği bitti**: nöbetçi turları arasında UYAP oturumu gizli tarayıcıdan 4 dk'da bir canlı tutulur; yeniden giriş yalnız oturum gerçekten düşerse yapılır (kart takılıysa e-İmza ile). UETS bitince gizli tarayıcı UYAP'a geri döner.
- **Sürekli akış**: eskiden 10 dk'da bir tur atıp yalnız 50 arşiv evrakı indiriyordu (700 bin evrak ≈ 97 gün). Artık senkron açıkken arşiv durmadan iner ve Drive'a gider; açık dosya taraması / duruşma / süre analizi aralıkla yapılır.

## 🩺 v4.4.2: Saha Testi Düzeltmeleri (4.4.0 tanı günlüğünden)

- **Telefonda nöbetçi hâlâ "ad çözülemedi" diyordu** (Drive yüklemesi ve Telegram bildirimi gitmiyordu) — sunucu çözebiliyor, görev süreci çözemiyordu. Bağımsız DNS çözücü artık her görev betiğinin (nöbetçi, UYAP indirici, UETS, Tebligatlar) başında doğrudan kuruluyor; tüm DNS sunucularına aynı anda sorgu (eskiden sırayla, tek çözümleme ~3 sn), TCP/53 ve daha fazla DoH yedeği, sıkıştırılmış DNS yanıtlarının doğru okunması.
- **Tanı dosyasına DNS testi**: hem sunucu hem görev süreci için hangi yöntemle (UDP/TCP/DoH), kaç ms'de çözüldüğü.
- **Tek evrak 8 dakika takılıyordu**: UYAP aynı boş (<128 bayt) yanıtı iki kez verirse evrak "UYAP'ta içerik yok" sayılır; yeniden giriş evrak başına en çok bir kez.

## ⚡ v4.4.1: İndirmeden Önce Toplu Mükerrer Kontrolü

- **UYAP evrak indirme (nöbetçi, Evrak Kataloğu, eksikleri tamamla):** İndirme başlamadan, tek sorguda plan çıkarılır: *"N evrak: A zaten var, B mükerrer olacağı bilindiği için indirilmeyecek, C indirilecek"*. Aynı dosyada aynı gönderenden aynı adlı ek (ör. her dilekçeye eklenen vekaletname) iki kez aynı içerikle geldiyse, sonrakiler **hiç indirilmeden** mükerrer işaretlenir; eskiden her biri UYAP bekleme süresiyle tek tek indirilip sonra atılıyordu. Aynı çalışma içinde de öğrenilir. Tahminler nöbetçi boştayken birkaçar birkaçar gerçekten indirilip doğrulanır; içerik farklı çıkarsa evrak indirilir ve o kalıp bir daha kullanılmaz.
- **Tebligat / İşlemlerim / Duruşma evrakları indirme:** Daha önce indirilenleri bulan kontrol her evrak için tüm geçmişi baştan tarıyordu; artık dizinle anında. Aynı içerik ikinci kez inerse diske yazılmaz.
- **UETS:** TickTick kontrolü her tebligat için ayrı internet isteği atmak yerine listeleri bir kez çekip toplu yapar; diskteki EYP'ler kalıcı barkod dizininden okunur (yalnız yeni paketler açılır); indirmeden önce *"X tanesinin EYP'si zaten var, Y indirilecek"* planı yazılır.

## 📨 v4.4.0: Telefonda UETS, TickTick/Notion/Telegram Gerçekten Çalışıyor

**Telefonda internet "yok" sanılıyordu (asıl sorun)**
- APK içindeki asistan, Termux'tan alınmış glibc ile çalışıyor ve DNS ayarını `/data/data/com.termux/…/resolv.conf` yolunda arıyordu. Termux kurulu olmayan telefonda bu dosya olmadığı için **Notion, TickTick, Telegram, UETS ve Gmail "internet yok / ad çözülemedi"** hatası veriyordu. Artık: (1) uygulama bu glibc'yi kendi resolv.conf'una yönlendirir ve telefonun DNS sunucularını kullanır, (2) yedek DNS çözücü yalnız sunucuda değil **bütün alt görevlerde** (UETS, TickTick, Notion, nöbetçi) devrededir.

**UETS telefonda, arka planda**
- UETS görevi telefonda "masaüstünde çalışır" diye kapalıydı. Yeni `cdp_surucu`, uygulamanın gizli tarayıcısını Selenium gibi sürer: UETS'e girer, güncel CSV'yi ve eksik EYP paketlerini indirir, TickTick'e **eklerle** gönderir, Notion dosyasıyla eşleştirir. Chrome/Termux gerekmez.
- **Arka planda otomatik**: Tebligatlar sekmesinden 30 dk / 1 / 2 / 4 / 12 saatte bir.
- UETS giriş kodu (OTP) Gmail'den otomatik okunur (Gmail adresi + uygulama şifresi alanları eklendi); Gmail yoksa kod panelden yazılır.

**Masaüstüne özel pencereler telefonda**
- Yeni **📨 Tebligatlar** sekmesi: Avukat Asistanı penceresinin tüm işlevleri (durum tablosu, tek tıkla TickTick'e ekle, mükerrer temizliği, UYAP Excel). Görevler sekmesindeki pencereler telefonda "Panelde Aç" ile açılır.

**Google Drive**
- "Eksikleri Drive'a Eşitle" telefonda **her basışta son 150 evrakı yeniden yüklüyordu** (Drive'da kopyalar birikiyordu) ve Apps Script hata verse bile "başarılı" sayıyordu. Artık her evrak bir kez yüklenir (yükleme defteri), Apps Script de aynı ad+boyuttaki dosyayı yeniden oluşturmaz; canlı ilerleme çubuğu, "Drive'da X / Y evrak" sayacı ve **🧹 kopyaları temizle** düğmesi (çöp kutusuna, 30 gün geri alınabilir).

**İçtihat arama**
- Yargıtay 1–23 Hukuk ve 1–23 Ceza daireleri, HGK/CGK/BGK/İBK, Danıştay 1–17. daireler ve kurullar, AYM, BAM, BİM, Uyuşmazlık, Sayıştay. Site bir daire kodunu tanımazsa sonuçlar daire adına göre süzülür. **Daha fazla karar yükle** ile sonraki sayfalar.

> Telefonda Apps Script kodunu güncellemeyi unutmayın (Drive sekmesi → *📋 Google Apps Script Kodunu Kopyala* → script.google.com'a yapıştır → *Dağıt › Dağıtımları yönet › ✏️ › Yeni sürüm*).

## ☁️ v4.3.1: Google Drive'ın Tamamı Gerçekten İndeksleniyor

- **Telefonda "Drive'ı İndeksle" aslında Google Drive'ı değil, telefonun İndirilenler klasörünü tarıyordu** (Drive telefonda klasör olarak bağlı olmadığı için). Ekranda "10.000 dosya" yazması bundan kaynaklanıyordu. Artık Drive'ın **tamamı** Apps Script üzerinden klasör klasör, sayfa sayfa okunur; dosya sayısı sınırı yoktur.
- İndeksleme arka planda çalışır, ilerleme canlı gösterilir ("… dosya okundu"); panel kapatılsa da sürer. Telefon klasöründen gelmiş eski kayıtlar temizlenir.
- Arama sonuçlarında **Aç** (dosya Drive'dan indirilip editörde açılır) ve **Drive'da** (tarayıcıda açar) düğmeleri. Google Dokümanlar/E-Tablolar da listelenir.
- **Önemli:** Bu özellik için Apps Script kodunun güncellenmesi gerekir: Drive sekmesi → *📋 Google Apps Script Kodunu Kopyala* → script.google.com'da eski kodun yerine yapıştır → *Dağıt › Dağıtımları yönet › ✏️ › Sürüm: Yeni sürüm › Dağıt*. Webhook adresi değişmez. Eski betikte uygulama ne yapılacağını açıkça söyler.
- CI: `.github/apk-yayinla` dosyasıyla (etiket + `tam`) tüm platformlar için yayın başlatılabilir.

## 🛠️ v4.3.0: Hata Düzeltmeleri ve Yeni Asistan Arayüzü

**Düzeltilen hatalar**
- **UYAP nöbetçi döngüsü her turda çöküyordu** (`'sqlite3.Row' object has no attribute 'get'`): arşiv eşitlemesi bitince Drive'a yükleme adımı hata veriyordu. Düzeltildi; hata artık arayüzde "Son turda hata" olarak da görünür ve görev çıkış kodu hatayı bildirir.
- **Arşiv eşitlemesi sonsuz döngüdeydi**: UYAP'ta artık bulunmayan (`yok`) evraklar her 3 saniyede yeniden deneniyor, bekleme moduna hiç geçilmiyordu. `yok` evraklar atlanır, hata verenler kuyruğun sonuna alınır.
- **Yeni kurulumda tüm asistan sekmeleri 500 hatası veriyordu** (`no such table: evrak`): tarama yapılmamış katalogda artık "henüz tarama yapılmadı" mesajı gösterilir.
- **Telegram iki ayrı yerde, iki ayrı dosyaya kaydediliyordu**; nöbetçi yalnızca birini okuyordu. Artık tek kaynak: hangi ekrandan girilirse girilsin nöbetçi, UETS ve otomatik aktarım aynı bilgiyi kullanır. Otomatik aktarım Telegram'a da gönderir.
- **Genişliğe Sığdır / Sayfaya Sığdır düğmeleri hiçbir şey yapmıyordu** (tanımsız `setCustomZoom`). Baskı görünümü düğmesi geniş ekranda hiç baskı görünümüne geçmiyordu.
- **Açılan pencereler Esc ile ya da dışına tıklanarak kapanmıyordu**; açık kalan pencere tüm araç çubuğunu kilitliyordu.
- **Android arka plan imzası tamamlanınca JS hatası** (tanımsız `insertSignatureSeal`): Android'e "imzalandı" bilgisi gitmiyordu.
- **HAYFA → "Açık belgeyi JAR ile dönüştür" her zaman hata veriyordu** (tanımsız `buildUdfZipBytes`).
- Tablo/görsel ekleme gibi değişiklikler "kaydedilmemiş" sayılmıyordu (tanımsız `markDirty`).
- Mobilde cetvel gizleme düğmesi çalışmıyordu; tercih artık hatırlanır.
- Tanı ekranındaki istek sayısı hep 0, ping hep "1 ms" yazıyordu: artık gerçek değerler (UYAP'a gerçek bağlantı süresi, oturum kesinti sayısı).
- Alt bilgi çubuğundaki ve asistan başlığındaki sürüm etiketi eski kalıyordu; artık tek kaynaktan yazılır.

**Arayüz ve işlev geliştirmeleri**
- **Hukuk Asistanı paneli yeniden tasarlandı**: masaüstünde 15 sekme tek satıra sıkışmak yerine solda gruplu kenar çubuğu (Takip · Süre & Hesap · Belge · Bağlantılar), sabit yükseklik (sekme değişince pencere zıplamıyor), yükleme göstergesi, son açılan sekmeyi hatırlama.
- Telefonda tam ekran panel, kaydırılabilir yuvarlak sekme çipleri, tek sütun formlar, okunur tablolar.
- **Notion / TickTick / Telegram için "Bağlantıları test et"** düğmesi: her servisi gerçekten dener, sonucu 🟢/🔴 gösterir. Hiçbir servis bağlı değilse doğrudan anahtar ekranı açılır.
- Mobil araç çubuğunda "devamı var" solma ipucu, en az 40 px dokunma hedefleri, klavye odak halkaları.
- İmzacı adları imza şeridinde HTML olarak yorumlanmaz (güvenlik).

## 🧩 v4.2.0: Büyük Güncelleme — Çoklu E-İmza, Dosya Hesapları, Ağaç Görünümü ve Toplu Evrak Yönetimi

Ayrıntılı mimari: [`docs/BIRLESIK_MIMARI.md`](docs/BIRLESIK_MIMARI.md) · Handoff: [`docs/ANTIGRAVITY_HANDOFF.md`](docs/ANTIGRAVITY_HANDOFF.md)

| Modül / Özellik | Yenilikler |
|---|---|
| **E-İmza & Co-signing** | Çift smart kart/token takılıyken anında algılama, çıkarılan kartı temizleme, imzalı belgelere ikinci imza ekleme (birlikte imzalama) |
| **A4 Sayfalama** | "NETİCE-İ TALEP" ve başlıkların sayfa dibinde tek satır kalması önlendi (Keep-with-next motoru) |
| **PDF & TIFF Okuyucu** | Büyük taranmış evraklarda (CamScanner vb.) Android GPU doku sınırını aşan beyaz sayfa sorunu giderildi |
| **Saf Python UDF → PDF** | Java yüklü olmayan cihazlarda ReportLab ile %100 yerel ve hızlı PDF çıktısı |
| **Evrak Arama** | Türkçe İ/ı duyarsızlaştırma; dosya no, mahkeme, birim, taraf ve müvekkil alanlarının tamamında arama |
| **Yeni Evraklar Toplu Yönetimi** | Toplu onay kutuları (checkbox), Seçilenleri İndir / PDF Yap / Drive'a Gönder / Görüldü Say butonları ve sayfalama |
| **Dosyalar & Ağaç Görünümü** | Kart, Tablo ve Ağaç (Ceza/Hukuk/İcra/İdare hiyerarşisi) olmak üzere 3 farklı görünüm ve gelişmiş filtreler |
| **Dosya Hesapları & İcra** | İcra ve dava dosyalarında anapara, işlemiş faiz, vekalet ücreti, harç/masraf, tahsilat, bakiye borç ve mahkeme gider avansı dökümü + CSV indirme |
| **HAYFA & İçtihat & Mevzuat** | Yargıtay daire ve hızlı konu filtreleri, anonimleştirilmeyen tam metin, uygulama içi Mevzuat Okuyucusu |
| **Ajanda & Süreli İşler** | Hızlı zaman filtreleri (1 gün, 3 gün, 1 hafta, 2 hafta, 1 ay, 3 ay, 6 ay) ve UETS 5. gün yasal süre sayacı |
| **Bağlantı & Rolling Log** | Sistem sağlık paneli, kesintisiz Google Drive sync göstergesi, 2MB rotasyonlu otomatik loglama ve tek tıkla Log ZIP indirme |
| **Android Başlatıcı & USF** | Ana ekrandan tek tıkla Hukuk Asistanı'nı açan buton, sistemde `.udf` ve `.usf` varsayılan açıcı ilişkilendirmesi |

## 🚀 Hızlı İndirme (v4.10.0)

Kurulum paketleri **her şeyi içinde taşır**: Python, Java, görünmez Chrome ve sürücüsüz e-imza altyapısı. Ayrıca bir şey kurmanız gerekmez.

| Platform | Paket Dosyası | Açıklama |
| :--- | :--- | :--- |
| **Windows 10 / 11 (64-bit)** | [**CanEditor_4.9.4_x64-setup.exe**](https://github.com/cnkzlyr/udemobile/releases/download/v4.9.4/CanEditor_4.9.4_x64-setup.exe) · [MSI](https://github.com/cnkzlyr/udemobile/releases/download/v4.9.4/CanEditor_4.9.4_x64_en-US.msi) | Standart kurulum (NSIS) · kurumsal MSI |
| **macOS (Apple Silicon & Intel)** | [**CanEditor_4.9.4_universal.dmg**](https://github.com/cnkzlyr/udemobile/releases/download/v4.9.4/CanEditor_4.9.4_universal.dmg) | Universal (M1/M2/M3/M4 + Intel) — Applications'a sürükleyin |
| **Linux Debian / Ubuntu / Pardus** | [**CanEditor_4.9.4_amd64.deb**](https://github.com/cnkzlyr/udemobile/releases/download/v4.9.4/CanEditor_4.9.4_amd64.deb) | `sudo apt install ./CanEditor_4.9.4_amd64.deb` (e-imza kart hizmeti otomatik kurulur) |
| **Linux Fedora / RHEL / openSUSE** | [**CanEditor-4.9.4-1.x86_64.rpm**](https://github.com/cnkzlyr/udemobile/releases/download/v4.9.4/CanEditor-4.9.4-1.x86_64.rpm) | `sudo dnf install ./CanEditor-4.9.4-1.x86_64.rpm` |
| **Linux (tüm dağıtımlar)** | [**CanEditor_4.9.4_amd64.AppImage**](https://github.com/cnkzlyr/udemobile/releases/download/v4.9.4/CanEditor_4.9.4_amd64.AppImage) | `chmod +x` ile çalıştırın (e-imza için bir kez `sudo apt install pcscd libccid`) |
| **Android (Telefon & Tablet)** | [**CanEditor-v4.9.4.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v4.9.4/CanEditor-v4.9.4.apk) · [en son](https://github.com/cnkzlyr/udemobile/releases/download/v4.9.4/CanEditor-latest.apk) | Tek uygulama · Termux gerektirmez; gömülü Python asistan APK içinde |
| **Taşınabilir Web & Masaüstü** | [**CanEditor-Portable-Web-GUI-v4.9.4.zip**](https://github.com/cnkzlyr/udemobile/releases/download/v4.9.4/CanEditor-Portable-Web-GUI-v4.9.4.zip) | **Kurulumsuz;** `index.html` ile her sistemde çalışır |

Tüm dosyalar ve sürümler: [GitHub Releases — v4.9.4](https://github.com/cnkzlyr/udemobile/releases/tag/v4.9.4) · [Tüm Sürümler](https://github.com/cnkzlyr/udemobile/releases)

---

## ⚠️ Android: v3.16.0 ve öncesinden geçerken bir kerelik yeniden kurulum

v3.17.0'dan itibaren APK yeni ve kalıcı bir proje anahtarıyla imzalanır (sertifika `CN=CanEditor`, SHA-256
`BA:80:78:89:12:28:35:C0:58:3B:C9:72:3B:C0:90:5C:C8:6F:49:A8:1A:92:BA:F9:D0:96:33:77:71:BB:D4:F0`). Telefonunuzda
v3.16.0 ya da öncesi kuruluysa bir kez **kaldırıp** yeni APK'yı kurun (aksi halde Android "paket çakışıyor" hatası
verir). Sonraki güncellemeler kaldırmadan, üzerine kurulur.

## 🌟 v3.31.1: CanEditor — Mobil Akış Görünümü (Tensip/Zapt) Düzen Düzeltmesi & %100 Havelsan UYAP Kaynak Koruma Motoru

- **📱 Mobil Akış Görünümü (`Mobil Görünüm`) Düzeltmeleri (v3.31.1):**
  - **Mahkeme Başlığı Dikey Kırılma Düzeltmesi (`T.C. / ANKARA / 29. AĞIR CEZA MAHKEMESİ`):** A4 sol yarıya ortalamak için yüksek `RightIndent` (`10.08cm`) kullanılan mahkeme başlıklarının mobil ekranda harf harf dikey kırılması giderildi.
  - **Sağa İtilmiş Alt Başlıklar (`(ADLİ KONTROL)`):** Yüksek `LeftIndent` (`13.06cm`) ile sağa yerleştirilen alt başlıkların mobil ekranda taşması ve boşluk bırakması önlendi.
  - **Asılı Girintili ve Sekmeli Üstveri Satırları (`DOSYA NO`, `BAŞKAN`, `ÜYE`, `KATİP`, `DAVACI`, `SANIK`, `SUÇ`, `SUÇ TARİHİ`):** Mobil görünümde tüm `:` hizaları korunarak etiket sütunu `2.60cm` olarak ölçeklenir, değer sütununa ekranın **%68'i** ayrılır ve dar sütundaki yapay `justify` kelime boşlukları giderilir.
  - **%100 Havelsan UYAP Kayıt Garantisi (`data-orig-ml / mr / ti / align`):** Belge Mobil Görünüm'de düzenlenip kaydedildiğinde bile orijinal A4 girinti ve sekme öznitelikleri **%100 bayt-bayt birebir** korunur.

- **%100 Havelsan UYAP Uyumluluk & Kaynak Koruma Motoru (`Layer-1 + Layer-2 XML Span Splicer`):**
  - **Dokunulmadan Kaydedilen Belgeler (%100 Bayt-Bayt Birebir):** Bir `.udf` belgesi açılıp düzenlenmeden kaydedildiğinde `content.xml`, `documentproperties.xml` ve `sign.sgn` (e-imza zarfı) **%100 bayt-bayt birebir** korunur.
  - **Kısmi Düzenlenen Belgeler (Katman-1 & Katman-2 Kaynak Ekleme):** Belgedeki bir paragraf veya satır düzenlendiğinde, dokunulmayan tüm paragraflar, tablolar, çoklu `<header>` / `<footer>` blokları, `<styles>` tanımları, `<field>`, `<space>`, `<tab>` etiketleri ve hassas kayan nokta girintileri (`SpaceAbove="5.67"`, `FirstLineIndent="35.4375"`, `Hanging="151.42857"`) orijinal XML kaynağından **birebir** korunur; yalnızca düzenlenen metin parçasının `startOffset` ve `length` değerleri yerinde güncellenir.
  - **Sıfır Yapay Biçim Bozulması:** Sabit punto satır yüksekliğinin (`data-udf-pitch`) kaydetme sırasında yapay `LineSpacing="12.85"` olarak yazılması ve sayfa bölme (`flow.js` / `editor.js`) sırasında `SpaceBelow` (`data-orig-mb`) niteliğinin silinmesi tamamen giderildi.
  - **Sekmeli Paragraflarda Klavye Seçimi (`Home` / `Shift+End`):** `.udf-tab-space[contenteditable="false"]` içeren satırlarda `Home` / `End` / `Shift+Home` / `Shift+End` tuşlarının 9 paragraf birden seçmesine yol açan tarayıcı hatası giderildi.
- **Yeni Modern Arayüz Özellikleri (UYAP Uyumluluğunu Bozmadan):**
  - **⚡ Komut Paleti (`Ctrl+K` / `⌘K`):** Dosya, UYAP/Havelsan, e-imza, dilekçe şablonları, AI formatlama ve görünüm komutlarına anında arama ile erişim.
  - **📑 Belge Anahattı & Hukuki Bölüm Gezgini:** Mahkeme başlığı, Dosya/Esas/Karar No, Davacı/Davalı/Sanık, Konu, Açıklamalar, Hukuki Sebepler, Deliller, Sonuç ve İstem / Hüküm bölümlerini otomatik algılayan ve tek tıkla ilgili sayfaya/paragrafa kaydıran yan çekmece.
  - **🏛️ Havelsan UYAP %100 Uyumluluk Raporu & Canlı Doğrulama:** Üst çubuktaki `🏛️ UYAP %100` rozetiyle belgenin kaynak koruma istatistiklerini ve tek tıkla çalışan canlı ZIP/XML doğrulama testini görüntüleme.
  - **🧘 Odak Modu (Zen) & 🌙 Gece Modu / 📜 Gece Kağıdı:** Kaydedilen `.udf` dosyalarının iç stillerini hiçbir şekilde etkilemeyen, salt CSS tabanlı gece arayüzü, koyu kağıt ve dikkat dağıtmayan tam ekran yazım modu.
  - **Chrome E-İmza Köprüsü, Yerel E-İmza & Gömülü Java Korundu:** Chrome UYAP/Celse e-imza köprüsü (`Adalet E-İmza`), editör içi Akıllı Kart (PKCS#11 / CCID), Mobil İmza ve gömülü OpenJDK 14 çalışma ortamı eksiksiz korundu.

## 🌟 v3.30.0: UYAP Editör — CanEditor ile aynı, sürüklenebilir 3 ayarlı cetvel

- **Görünüm CanEditor'ınkiyle aynı:** 40 px açık zemin, gri kenar boşlukları, beyaz metin alanı, alttan yükselen mm / yarım cm / cm çizgileri ve sol kenar boşluğundan iki yana sayan kalın santimetre numaraları. Kağıtta sayfaya ve yakınlaştırmaya, mobilde metin genişliğine ölçeklenir.
- **Üç ayarlı (Word / UYAP standardı) + sağ girinti, parmakla sürüklenir:** ▼ ilk satır girintisi, ▲ asılı girinti (sonraki satırlar), ■ sol girinti (tüm paragrafı taşır), sağda ▲ sağ girinti. 0,25 cm adımla oturur; sürüklerken mavi kesikli kılavuz çizgisi ve "İlk satır: 2,00 cm" gibi ölçü rozeti görünür.
- **Gerçekten uygulanır:** Bırakınca resmi motor seçimdeki tüm paragraflara UDF'nin kendi özniteliklerini yazar (`PAR sol ilk asılı sağ` → `LeftIndent` / `FirstLineIndent` / `Hanging` / `RightIndent`, Paragraf Özellikleri penceresinin yazdığıyla aynı). Değişiklik geri alınabilir ve sayfa anında yeniden dizilir. İmleç başka paragrafa geçince işaretler o paragrafın değerlerine gelir (`MPAR sol ilk asılı sağ hizalama`). İşaret dışına dokunmak Paragraf Özellikleri'ni açar.

## 🌟 v3.29.0: UYAP Editör — cetvel, sayfa süsleri (sayfa no / karekod / filigran), üst-alt bilgi, yeni simge, varsayılan açıcı

- **Cetvel (kağıt ve mobil):** Kağıt görünümünde sayfa genişliğine ve yakınlaştırmaya göre ölçeklenen santimetre cetveli; kenar boşlukları gri, bölmeler sol kenar boşluğundan başlar. Mobilde metin genişliğine ölçeklenir. İmlecin bulunduğu paragrafın sol / ilk satır / sağ girintileri mavi üçgenlerle gösterilir (köprü: `MPAR sol ilk sağ hizalama`). Cetvele dokununca resmi editörün **Paragraf Özellikleri** penceresi açılır; çekmeceden gizlenebilir.
- **Sayfa süsleri eksiksiz:** Resmi editörün sayfayı boyarken eklediği ama belge modelinde bulunmayan öğeler — **sayfa numarası, e-imza doğrulama satırı ve karekod, barkod, filigran** — artık kağıt görünümünde de görünür. Köprü, sayfayı motorun kendi çizimiyle saydam bir PNG'ye döker (`SR k ölçek → SRESIM k sürüm png`); belgenin metni, resimleri ve her sayfada yinelenen üst/alt yazı yaprakları süzgeçten (`Suzgec`, Graphics2D sarmalayıcı) geçirilip atılır, yalnızca süsler kalır ve metnin altına yerleşir. Editörün iç yakınlaştırması (0.98) ve sayfa ortalaması telafi edilir. Yazmayı aksatmamak için istekler tek tek ve görünen sayfalar için gider; belge değişince yazmaya ara verilince yenilenir, yenisi gelene kadar eskisi kalır.
- **Üst bilgi / alt bilgi / sayfa no kolay düzenleme:** Çekmecede yeni **ÜST / ALT BİLGİ · SAYFA NO** bölümü (Üst bilgi, Alt bilgi — belgede varsa “Düzenle”, yoksa “Ekle” penceresi; Sayfa numarası ekle / düzenle; Paragraf özellikleri; Barkod ekle). Kağıtta üst ya da alt kenar boşluğuna **çift dokunmak** doğrudan ilgili düzenleyiciyi açar.
- **CanEditor tarzı simge:** UYAP Editör uygulaması artık CanEditor'ın mavi terazili karosunu “UYAP Editör” yazısıyla kullanır (tüm yoğunluklar); üst çubukta da uygulama simgesi görünür.
- **.udf / .usf için varsayılan uygulama:** Uygulama menüsünde “UDF / USF için varsayılan uygulama yap”: Android'in seçicisini örnek bir belgeyle açar, “Her zaman” seçilince tüm .udf / .usf dosyaları (WhatsApp, e-posta, dosya yöneticisi, tarayıcı) doğrudan burada açılır. Başka bir uygulama varsayılansa onun “Varsayılan olarak aç” ayarına yönlendirir. İlk açılışta bir kez önerilir.

## 🌟 v3.28.0: UYAP Editör — belge içi arama, sayfa göstergesi, açık belgeler, paylaşma, uyumluluk

- **Uyumluluk taraması:** örnek belgeler kağıt görünümünde resmi editörle yan yana karşılaştırıldı; satır kırılımı,
  hizalama, logo, vurgular birebir. UYAP form alanları artık resmi editördeki gibi düz gösterilir.
- **Belgede ara:** ☰ > Belgede ara — tüm eşleşmeler boyalı, sayaç, ileri/geri; kağıt görünümünde çizilmemiş sayfalar da
  taranır. Orijinal ekranda editörün "Bul"u açılır.
- **Sayfa göstergesi:** kaydırırken "3 / 12" rozeti; dokununca "Sayfaya git".
- **Açık belgeler:** birden çok belge açıksa ☰ menüde listelenir, dokununca geçilir. **Son belgeler** listesi.
- **Belgeyi paylaş:** WhatsApp / e-posta (değişiklik varsa önce kaydeder). Başlıkta "•" ve "Kaydedilmedi" uyarısı.
- Görünüm ilk içeriği kaçırırsa tam içeriği yeniden ister (boş görünüm kalmaz).

## 🌟 v3.27.0: UYAP Editör — tam dokunmatik seçim, yerel pencere paneli (mobil imza / e-imza), iki parmakla yakınlaştırma

- **Seçim:** çift dokunma kelimeyi seçer; basılı tutup sürükleme kelime kelime genişletir (büyüteçle); mavi tutamaçlar
  seçimin uçlarını sürükler; seçimin üstünde **Kes · Kopyala · Yapıştır · Tümünü seç** çubuğu. Hem kağıt hem mobil görünümde.
- **Yerel pencere paneli:** resmi editörün pencereleri (Mobil İmza, e-imza PIN'i, sertifika/imza seçimi, uyarı ve soru
  pencereleri, İmzalar) alttan kayan, dokunmaya uygun bir panel olarak açılır: büyük alanlar, sayısal klavye, radyo ve
  onay seçenekleri, listeler; yazılanlar orijinal pencereye gider, düğmeler orijinal düğmeye basar. Pencere değişince
  (ör. doğrulama kodu gelince) panel yerinde güncellenir. Yansıtılamayan pencereler (yazdırma önizlemesi) büyütülerek
  gösterilir; "Orijinal" ile her zaman asıl pencereye geçilebilir.
- **İki parmakla yakınlaştırma** kağıt ve mobil görünümde (odak noktası sabit); sayfalar yumuşak belirir.

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

### ⌨️ 6. Terminalden Kullanım (`caneditor`) — Tüm Platformlar

Arayüzün yaptığı her şey terminalde de yapılabilir. Komutların tam listesi: `caneditor --help`, her komutun ayrıntısı: `caneditor <komut> --help`.

* **Linux (.deb / .rpm):** Kurulumla `/usr/bin/caneditor` gelir. Terminalde `caneditor durum` yazın.
* **Linux AppImage / macOS / kaynak kod:** Python 3.9+ ile depo kökünden:
  ```bash
  git clone https://github.com/cnkzlyr/udemobile && cd udemobile
  pip install -r asistan/requirements.txt
  ./caneditor durum
  ```
  Kalıcı kısayol: `sudo ln -s "$PWD/caneditor" /usr/local/bin/caneditor`
* **Windows:** Kurulum klasöründeki `asistan\caneditor.bat` (ya da depo kökündeki `caneditor.bat`). PowerShell'de `.\caneditor.ps1 durum`. Python yoksa paketteki `asistan-sunucu.exe` kendiliğinden kullanılır.
* **Android (Termux):**
  ```bash
  pkg install python git openjdk-17
  git clone https://github.com/cnkzlyr/udemobile ~/udemobile
  pip install -r ~/udemobile/asistan/requirements.txt
  ln -s ~/udemobile/caneditor $PREFIX/bin/caneditor
  caneditor durum
  ```
* **Kişisel ayarlar (bir kez):** `~/.caneditor/kisisel.json` dosyasına PIN/TC/GSM/operatör yazın ya da `EIMZA_PIN`, `UYAP_TC`, `UYAP_GSM`, `UYAP_OPERATOR` ortam değişkenlerini tanımlayın. PIN yoksa giriş ve imza Mobil İmza ile yapılır.

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
