# ⚖️ UYAP Evrak Yöneticisi (UYAP Avukat Portal Evrak İndirici & Hukuk Otomasyonu)

**© 2026 Av. Can KIZILYAR — Tüm hakları saklıdır.** (bkz. [LICENSE](LICENSE))

UYAP Avukat Portal (`https://avukat.uyap.gov.tr`) üzerindeki tüm derdest ve kapalı dava dosyalarının evraklarını ve eklerini **kataloglayan, filtreleyerek seçtiren, her evrakı yalnızca bir kez indiren, PDF'e dönüştüren ve görüntüleyen** masaüstü uygulaması. Windows, Linux, macOS (Intel + Apple Silicon) ve Android (Termux:X11) üzerinde çalışır.

---

## 🆕 Sürüm 3.0 — Neler var?

| Özellik | Açıklama |
|---|---|
| **Kurulabilir uygulama** | Windows kurulum dosyası (`UYAPEvrak-…-Windows-Kurulum.exe`), Linux AppImage/deb/rpm, macOS dmg. Python, Java (JRE), Pillow, pypdf, yazı tipleri dahil; ayrıca bir şey kurmak gerekmez. |
| **Evrak kataloğu** | Yüz binlerce evrak ve ek, indirmeden önce yerel veritabanına yazılır; saniyeler içinde süzülür. Katalog kalıcıdır, her açılışta yeniden taranmaz. |
| **Üç durumlu filtreler** | Evrak türü, kategori, indirme durumu, birim, dosya türü, yargı, açık/kapalı, uzantı listelerinde **1. tık yeşil = getir, 2. tık kırmızı = hariç tut, 3. tık = kaldır**. A→Z / sayıya göre sıralama. |
| **Metin aramada hariç tutma** | Taraf, müvekkil, açıklama, içerik, dosya no: `sungur -ahmet`, `"ağır ceza" -"sulh ceza"`. Türkçe harf duyarsız. |
| **Gerçek UYAP evrak türleri** | ~600 asıl evrak türü ve ~5.000 ek adından çıkarılmış 18 kategori (Tutuklama/Adli Kontrol, İfade/Tutanak/Keşif, Vekaletname, İcra/Haciz, Makbuz/Harç, Talimat, Üst Yazı …). |
| **Her evrak bir kez** | İstinaf/birleşen/talimat dosyalarındaki tekrarlar tek kayıt; başka evrakın ekinde gelen aynı belge içerik özetiyle tanınır ve ikinci kez yazılmaz. |
| **Görüntüleyici + önbellek** | Çift tık: indirilmişse PDF'i açılır; indirilmemişse UYAP'tan önbelleğe alınıp PDF'e çevrilerek açılır ("önbellekte"). Sonra indirilirse önbellekten taşınır. Ayrıntı panelinde evrakın tüm ekleri. |
| **Takılmayan indirme** | UYAP 40 sn içinde yanıt vermezse istek kesilip yeniden denenir (önceden dakikalarca bekleyebiliyordu). Oturum düşerse e-İmza/Mobil İmza ile yeniden girilir ve aynı evrak tekrar denenir; bozuk/HTML yanıt asla kaydedilmez. |
| **İlerleme ve süre tahmini** | Yüzde, kalan süre, indirilen MB, mükerrer/hata sayıları; 45 sn yanıt gelmezse "UYAP yanıtı bekleniyor" göstergesi. |
| **Ayrıntılı günlük** | Ekranda renkli günlük + `loglar/katalog.log` (bağlantı, oturum, her deneme, süre, dönüşüm). Yardım > *Günlükleri paketle* ile Masaüstüne zip. PIN asla yazılmaz. |
| **Sağ tık "PDF'e dönüştür"** | Dosya Gezgini'nde .udf .tif .tiff .docx .doc .rtf .odt .jpg .png (tekli/çoklu) → aynı adla PDF. UYAP Editör açmadan. |
| **Menüler** | İşlemlerim indirme, duruşma takvimi (.ics), tebligat & süre analizi, evrak zenginleştirme, toplu PDF dönüştürme, görünür tarayıcı, sağ tık menüsü kur/kaldır, kılavuz. |
| **Uyarlanabilir arayüz** | ☰ ile filtre paneli gizlenir; dar ekranda (Android/Termux:X11) otomatik gizlenir; yakınlaştır/uzaklaştır; ipuçları; yumuşak geçişli bildirimler. |

---

## ⚡ Sürüm 3.1 — Neler Yeni? (Bulut Mimarisi & Nöbetçi Bot)

| Modül / Özellik | Açıklama |
|---|---|
| **Nöbetçi Bot (`uyap_watcher.py`)** | UYAP'ı 7/24 arka planda izleyen akıllı servis. "İşlemlerim" yerine yalnızca **derdest (açık) 149 dosyayı** ve gelen tebligatları nazikçe sorgular; yeni evrak düştüğü an yakalar, indirir, PDF yapar ve **Telegram'dan anında PDF ekiyle avukata iletir**. |
| **Oturum Koruyucu (Keep-Alive Heartbeat)** | Her 3 dakikada bir UYAP'a hafif AJAX pinglemesi atarak oturumun gün boyu düşmesini engeller. Tek bir e-imza ile sistem kesintisiz canlı kalır. |
| **Hukuki Süre Analizcisi** | Gelen evrak tebligat, bilirkişi raporu, tensip zaptı veya gerekçeli karar ise; **Tebligat Kanunu m. 7/a** (elektronik tebligatta 5 gün kuralı), **HMK m. 281** (bilirkişiye 2 hafta itiraz) vb. yasal süreleri hesaplayıp Telegram bildirimine ekler. |
| **Google Drive Sıfır Kayıplı Aktarıcı (`drive_aktarici.py`)** | Bilgisayara daha önceden indirilmiş binlerce dosyayı (`UYAP_Indirilenler`) klasör hiyerarşisini milimetrik koruyarak Google Drive'a (`G:\Drive'ım\UYAP_Arsiv`) aktarır; `uyap_katalog.db` içindeki 4.400+ dosya yolunu otomatik olarak Drive yoluna günceller. |
| **Tek Veri Tabanı Mimarisi (`uyap_katalog.db`)** | Eski CSV/JSON kalıntıları kaldırılarak `tebligat` ve `durusma` tabloları SQLite'a dahil edildi. `cloud_backup()` API'si ile veritabanı kilitlenmeden anlık olarak Drive'a yedeklenir. |
| **Google Drive Hibrit Mimarisi** | Dosyalar bulutta Stream modunda durur; MacBook, Laptop ve telefonda **0 MB disk alanı kaplar**. Cihazlar mükerrer kontrolünü dosyalardan değil, sadece ~70 MB'lık `uyap_katalog_yedek.db` snapshot'ından yapar. |

---

## ☁️ Google Drive Hibrit Mimarisi: Her Cihazdan 0 MB Depolama ile Erişim

Bu sistemin en büyük avantajı, **hiçbir cihazınıza on binlerce dosyayı (onlarca GB arşivi) tek tek indirmek zorunda kalmamanızdır**:

1. **MacBook ve Dizüstü Bilgisayarlar:**
   - Google Drive masaüstü uygulamasında **"Dosyaları Akış Olarak Kullan (Stream files)"** seçilidir.
   - Tüm mahkemeler ve evraklar Finder/Dosya Gezgini'nde sanal sürücü (`G:\` veya `CloudStorage`) olarak görünür ancak **yerel SSD'de 0 MB yer kaplar**.
   - Bir PDF'e çift tıkladığınız anda Google Drive sadece o tek belgeyi saniyesinde internetten açar.
2. **Akıllı Telefonlar (Android & iPhone):**
   - Resmi Google Drive uygulamasında `UYAP_Arsiv` klasörüne girip dilediğiniz evrakı anında okuyabilirsiniz. Telefona hiçbir şey önceden indirilmez.
3. **Mükerrer Kontrolü Neden Dosya İndirmeden Çalışır?**
   - Telefondan (Termux) veya laptoptan program çalıştırıldığında, diskteki dosyalara bakmaz.
   - Google Drive'daki küçük `uyap_katalog_yedek.db` veritabanı snapshot'ını okur.
   - Hangi evrakın daha önce indirildiğini anında bilir; eski dosyaları indirmeden sadece yeni gelen evrakı çeker ve Drive'a yükler.

### 🔄 Eski İndirmeleri Google Drive'a Aktarma (`drive_aktarici.py`)
Eski yerel indirmelerinizi klasör yapısını ve veritabanı yollarını bozmadan aktarmak için:
```cmd
# 1. Simülasyon (Değişiklik yapmadan kontrol et):
python drive_aktarici.py --dry-run

# 2. Gerçek aktarımı başlat:
python drive_aktarici.py
```

---

## 🤖 Nöbetçi Bot & Telegram Bildirimleri (`uyap_watcher.py`)

Avukatın UYAP'ta beklemesine gerek kalmadan yeni evrakları ve duruşmaları telefona bildiren nöbetçi servis:

### 1. Telegram Bot Kurulumu (1 Seferlik)
```cmd
python uyap_watcher.py --setup
```
1. Telegram'da `@BotFather` ile bot açıp `Token` alın.
2. `@userinfobot` ile kendi `Chat ID` numaranızı öğrenin.
3. Sihirbaza girin; telefonunuza anında bir test bildirimi gönderilecektir.

### 2. Nöbetçiyi Çalıştırma
```cmd
# Normal Nöbetçi Modu (Her 30 dakikada bir kontrol eder, 3 dk'da bir oturumu canlı tutar):
python uyap_watcher.py

# Google Drive Eşitlemeli Mod (Yeni inenleri Drive'a kopyalar ve DB yedeğini tazeler):
python uyap_watcher.py --drive-dir "G:\Drive'ım\UYAP_Arsiv"
```

---

## 🗺️ Gelecek Yol Haritası (Neler Yapacağız?)

- [x] **Sürüm 3.0:** Masaüstü GUI, üç durumlu filtreler, Havelsan UDF->PDF, sağ tık dönüştürücü.
- [x] **Sürüm 3.1:** Tek SQLite veritabanı (`uyap_katalog.db`), Google Drive sıfır kayıplı aktarıcı (`drive_aktarici.py`), Nöbetçi Bot (`uyap_watcher.py`), Keep-Alive pinger, Telegram bildirimleri ve hukuki süre hesabı.
- [ ] **Yerel Hukuk AI & RAG Motoru:** İndirilen yüz binlerce sayfa PDF metni üzerinde yerel LLM (Ollama / Llama-3) veya Claude API ile semantik arama ("Tanık beyanlarındaki çelişkiler", "Hesap bilirkişi raporundaki hatalar").
- [ ] **Otomatik Duruşma / Ara Karar Ayıklayıcı:** Duruşma zaptı indiğinde içerisindeki kesin süreleri ve ara kararları regex/NLP ile ayıklayıp doğrudan takvime işleyen asistan.
- [ ] **Tailscale Özel Ağ Modu:** Bulut sağlayıcılarına ihtiyaç duymadan ofisteki bilgisayara doğrudan telefon/laptoptan uçtan uca şifreli VPN tüneli.

---

## 📥 Kurulum

### Windows 10/11 (önerilen)
1. [Releases](https://github.com/cnkzlyr/uyap-evrak-indirici/releases) sayfasından `UYAPEvrak-3.0.0-Windows-Kurulum.exe` dosyasını indirip çalıştırın (yönetici yetkisi istemez).
2. Kurulumda "sağ tık menüsü" kutusunu işaretli bırakın.
3. Başlat menüsünden **UYAP Evrak Yöneticisi**'ni açın.

> **UDF → PDF için:** Havelsan UYAP Editör kütüphaneleri lisanslıdır ve pakete konmaz. Bilgisayarınızda UYAP Editör kuruluysa otomatik bulunur. Bulunamazsa `editor_*.jar` dosyalarını `%LOCALAPPDATA%\UYAPEvrak\jars` klasörüne kopyalayın. TIF/DOCX/resim dönüşümü bundan bağımsızdır (DOCX için Word veya LibreOffice gerekir).

### Linux
- **AppImage:** `chmod +x UYAPEvrak-*.AppImage && ./UYAPEvrak-*.AppImage`
- **Debian/Ubuntu:** `sudo apt install ./uyap-evrak_3.0.0_amd64.deb` → menüde "UYAP Evrak Yöneticisi" veya `uyap-evrak`
- **Fedora/openSUSE:** `sudo dnf install ./uyap-evrak-3.0.0.x86_64.rpm`
- Chromium veya Google Chrome kurulu olmalıdır. Sağ tık menüsü (Nautilus/Dolphin): Araçlar > *Sağ tık menüsünü kur*.

### macOS (Intel ve Apple Silicon)
`UYAPEvrak-3.0.0-macOS-x86_64.dmg` (Intel) veya `…-arm64.dmg` (M1/M2/M3/M4) dosyasını açıp uygulamayı **Applications** klasörüne sürükleyin. İmzasız olduğu için ilk açılışta uygulamaya sağ tıklayıp **Aç** deyin. Google Chrome kurulu olmalıdır.

### Android (Termux + Termux:X11)
Android'de Tk arayüzü APK olarak paketlenemez; uygulama Termux içinde Termux:X11 ekranında tam arayüzüyle çalışır:
```bash
curl -fsSL https://raw.githubusercontent.com/cnkzlyr/uyap-evrak-indirici/main/packaging/android/termux_uygulama_kur.sh | bash
uyap-evrak
```
Termux:Widget ile ana ekrana "UYAP Evrak" kısayolu eklenebilir. Dar ekranda filtre paneli kendiliğinden gizlenir (☰ ile açılır). Android'de e-İmza (ArkSigner) yoktur; Mobil İmza kullanılır.

### Kaynak koddan çalıştırma (geliştirici)
```bash
pip install -r requirements.txt
python uygulama.py            # arayüz
python uygulama.py --cli      # eski komut satırı menüsü
```

---

## 🧭 Kısa kullanım

1. **Bağlan / Giriş** → tarayıcı arka planda açılır; oturum yoksa e-İmza (PIN yalnızca bellekte) veya Mobil İmza.
2. **UYAP'ı Tara** → evrak listesi kataloğa yazılır. Günlük kullanım: "yalnızca AÇIK dosyaları güncelle".
3. Soldan filtreleyin (yeşil getir / kırmızı hariç), sağda sonucu görün. Örnek: Evrak türünde "Genel Karar/Müzekkere"yi kırmızı yapmak, o müzekkerelere ek olarak gelmiş yüz binlerce dosya suretini dışarıda bırakır.
4. **Filtredekilerin tümünü indir** veya seçip **Seçilileri indir** (Ctrl+D). Çift tıkla aç; indirilmemişse önbelleğe alınır.
5. Ayrıntılı açıklamalar ve örnekler: uygulamada **Yardım > Kullanım kılavuzu**.

### Asıl evrak / ek nedir?
UYAP'ta her evrakın altında ekleri olabilir. Listede ekler `↳ EK03: …` diye girintili gösterilir; diskte asıl evrakın adıyla başlar:
```
2025-07-10_Talimat Üst Yazısı_no68987.udf            (+ .pdf)
2025-07-10_Talimat Üst Yazısı_no68987__EK01_İfade Tutanağı.tif   (+ .pdf)
```
"Dosya biçimi" listesindeki **"Henüz bilinmiyor"**: UYAP, indirilmemiş asıl evrakların biçimini önceden bildirmez (çoğu .udf'dir); indirilince gerçek biçim yazılır.

### PDF dönüşümü nasıl çalışır?
| Kaynak | Yöntem | Not |
|---|---|---|
| `.udf` | Havelsan UYAP Editör motoru (Java, `uyap.UdfBatchPdfConverter`) | Yazı tipleri PDF'e gömülür; Türkçe karakterler korunur. Her dosya grubunun indirmesi bitince arka planda, tek Java işlemiyle. |
| `.tif` / `.tiff` | Pillow | Çok sayfalı; her sayfa A4'e sığdırılır (yatay sayfa yatay A4). |
| `.jpg` `.png` `.bmp` `.gif` | Pillow | A4 PDF. |
| `.docx` `.doc` `.rtf` `.odt` | Microsoft Word (COM) → yoksa LibreOffice | Sağ tık menüsü ve toplu dönüştürmede. |

PDF her zaman kaynağın yanına **aynı adla** yazılır, var olanın üzerine yazılmaz. Dönüşüm başarısız olursa sebebi günlüğe yazılır (ör. UYAP Editör kütüphaneleri bulunamadı).

### Veri ve günlük klasörleri
| | Kaynak koddan | Kurulu uygulama |
|---|---|---|
| Katalog, ayarlar, önbellek, günlükler | proje klasörü | Windows `%LOCALAPPDATA%\UYAPEvrak`, macOS `~/Library/Application Support/UYAPEvrak`, Linux `~/.local/share/UYAPEvrak` |
| İndirilen evraklar | `../UYAP_Indirilenler` | `Belgeler/UYAP_Indirilenler` (Android: `Download/UYAP_Indirilenler`) |

Ortam değişkenleriyle değiştirilebilir: `UYAP_VERI_DIZINI`, `UYAP_INDIRME_DIZINI`, `UYAP_JARS`, `UYAP_FONT_DIR`.

---

## 🛠️ Paketleri derleme (geliştirici)

Tüm paketler GitHub Actions ile otomatik üretilir: [.github/workflows/paketler.yml](.github/workflows/paketler.yml). `v3.0.0` gibi bir etiket gönderildiğinde (veya Actions sekmesinden elle) Windows, Linux, macOS Intel ve macOS Apple Silicon derlenir ve Releases'e eklenir.

Yerelde:
```bash
pip install pyinstaller pillow pypdf requests websocket-client
pyinstaller packaging/uyap_evrak.spec          # dist/UYAPEvrak/ (UYAPEvrak + UYAPEvrakKonsol)
iscc packaging/windows/uyap_evrak.iss          # Windows kurulum dosyası (Inno Setup 6)
bash packaging/linux/build_linux.sh            # AppImage + deb + rpm (fpm gerekir)
bash packaging/macos/build_macos.sh            # dmg
```
Gömülü Java için `dist/UYAPEvrak/runtime/jre` klasörüne bir JRE 17 kopyalayın (CI bunu Eclipse Temurin ile yapar).

| Dosya | Görev |
|---|---|
| `uygulama.py` | Tek giriş noktası (arayüz, `--pdf`, `--cli`, `--donustur`, `--sag-tik-kur` …) |
| `katalog_gui.py`, `gui_ekler.py` | Arayüz, menüler, görüntüleyici, kılavuz, bildirimler |
| `evrak_katalog.py` | Katalog (SQLite), filtre motoru, tarama, indirme, önbellek, mükerrer kontrolü |
| `evrak_turleri.py` | Gerçek UYAP evrak türlerinden çıkarılmış kategori kuralları |
| `donusturucu.py`, `sag_tik.py` | PDF dönüştürme ve sağ tık menüsü |
| `uyap_indirici.py` | Tarayıcı köprüsü (CDP), e-İmza/Mobil İmza girişi, eski CLI modları |

---

## 📜 Önceki sürümlerin özellikleri (komut satırı modları)

1. **Dava Dosyalarından Akıllı Evrak Filtreleme (700+ Açık ve Kapalı Dosya):**
   * UYAP'taki 27 yargı birimini tarar; İcra dairelerini otomatik ayıklayarak hız kazandırır.
   * Hedefe yönelik evrak türleri:
     * **Duruşma Zabıtları (`durusma`):** Celse zabıtları ve SEGBİS tutanakları. (Müzekkere ekleri ve talimatlar mükerrerlik motoruyla elenir).
     * **Bilirkişi Raporları (`bilirkisi`):** Kök/ek raporlar, uzman mütalaaları, ATK ve kriminal raporlar (ekleriyle birlikte).
     * **Gerekçeli Karar ve İlamlar (`karar`):** Mahkeme hükümleri, BAM İstinaf ve Yargıtay ilamları.
     * **Tensip Zabıtları (`tensip`):** İlk ve talimat tensip tutanakları.
     * **Dava & Cevap Layihaları (`layihalar` / `dilekce`):** Dava, cevap, replik, düplik, delil, bilirkişi itiraz ve beyan dilekçeleri.
     * **Tebligatlar (`tebligat`):** Fiziki PTT mazbataları ve UETS e-Tebligat evrakları.
     * **Müzekkere & Kurum Cevapları (`muzekkere`):** Banka, Tapu, SGK, EGM, Polnet vb. kurum cevapları.
     * **İddianame & Fezleke (`iddianame`):** Ceza soruşturma/kovuşturma evrakları.
     * **Tüm Evraklar (`tumu`):** Dosyadaki istisnasız tüm ana evraklar ve alt ekler (`ekEvrakListesi`).

2. **UDF -> Vektörel PDF Dönüştürücü (Havelsan & TrueType Embedded):**
   * Resmi Havelsan editör çekirdeği ile çalışır.
   * `comments.xml` (açıklama/yorum) içeren UDF'lerde çökmeyi engelleyen bellek içi ayrıştırıcı içerir.
   * Windows ve Linux TrueType fontlarını (`Times New Roman`, `Arial`) PDF içine tam gömer; bozulma veya karakter kaybı yaşanmaz.

3. **Tebligat & UETS Yasal Süre Yöneticisi:**
   * İndirilen fiziki PTT mazbatalarındaki barkodları (13 haneli) ve tebliğ sonuçlarını tespit eder.
   * UETS (Ulusal Elektronik Tebligat) delil kayıtlarını ve elektronik tebliğ tarihlerini okur.
   * **7201 sayılı Tebligat Kanunu Madde 7/a f.4** kuralını uygulayarak yasal tebliğ tarihini (ulaşmayı izleyen 5. günün sonu) ve itiraz sürelerini otomatik hesaplar.
   * Sonuçları Excel uyumlu `tebligat_takip_listesi.csv` kütüğüne işler.

4. **Akıllı Evrak Zenginleştirme ve İsimlendirme:**
   * UDF `content.xml` içeriğini okuyarak Mahkeme, Esas No, Karar No, Duruşma Tarihi ve temsil edilen **Müvekkil** bilgisini çıkarır.
   * UDF dosyasının dahili `documentproperties.xml` meta verilerini günceller.
   * Dosyaları tek başına %100 tanımlayıcı isimlerle yeniden adlandırır:  
     `{Tarih}_{Birim}_{Esas}_{Muv-Muvekkil}_{EvrakTuru}_{EvrakId}.udf`

5. **Duruşma Takvimi Oluşturucu (.ics / CSV):**
   * Geçmiş ve gelecek tüm duruşmaları sorgular.
   * Google Takvim, Outlook ve Apple Takvim uyumlu `durusma_takvimi.ics` üretir.
   * Duruşma saati, mahkeme, dosya no, taraflar ve e-Duruşma bağlantısını takvim kaydına işler.

6. **Tam Güvenlik & Oturum Kurtarma:**
   * Oturum düşmelerinde dönen sahte HTML sayfalarını asla UDF/PDF olarak kaydetmez.
   * Atomik dosya yazımı (`.part` doğrulaması) ile bozuk indirmeleri engeller.
   * ArkSigner (Port 5975) ve Mobil İmza desteği ile kesintisiz oturum yeniler.

7. **Evrak Kataloğu: Tara → Filtrele → Seç → Bir Kez İndir** (`python uyap_indirici.py --katalog`, menü 12):
   * Tüm açık/kapalı dosyaların evrak ve ek listesi indirmeden yerel bir veritabanına (`uyap_katalog.db`) yazılır; yüz binlerce kayıt saniyeler içinde süzülür.
   * Filtreler: taraf, müvekkil (taraf/vekil bilgisinden otomatik), açıklama, evrak türü (dahil / hariç kelimeler), içerik (indirilenlerde tam metin), tarih aralığı (takvimden) veya son N gün, birim, dosya no, dosya türü, yargı, açık/kapalı, evrak kategorisi (dahil/hariç), uzantı (udf/tif/pdf/eyp…), asıl/ek, indirme durumu.
   * **Her evrak bir kez:** kalıcı anahtar (birim evrak no + tarih + tür; ekler için UYAP ana evrak no + sıra) sayesinde istinaf/birleşen/talimat dosyalarında tekrar görünen evrak tek kayıttır. Başka evrakın ekinde tekrar gelen aynı belge içerik özetiyle (UDF'de `content.xml` + imza) yakalanır ve ikinci kez diske yazılmaz.
   * UDF'ler aynı adla PDF'e, TIF/TIFF'ler (çok sayfalı) A4 PDF'e dönüştürülür.
   * Ekler ait oldukları evrakın adıyla başlar: `2025-07-10_Talimat Üst Yazısı_[…]_no68987__EK03_İfade Tutanağı.tif`
   * Tarayıcı arka planda (gizli) açılır; oturum yoksa e-İmza (PIN yalnızca bellekte) veya Mobil İmza ile girilir, oturum düşerse aynı yöntemle yenilenir.
   * Sunucu/zamanlanmış görev için: `python uyap_indirici.py --katalog-tara --headless` (yalnız kataloğu günceller).

---

## 🖥️ Windows 11 Kurulumu ve Kullanımı

### 1. Ön Gereksinimler
* **Python 3.10+:** [python.org](https://www.python.org) adresinden indirilebilir (Kurulumda *"Add Python to PATH"* seçilmelidir).
* **Java 17+ (JRE veya JDK):** UDF -> PDF dönüştürücü için gereklidir (`java -version` ile kontrol edebilirsiniz).
* **Google Chrome** veya **Microsoft Edge**.

Gerekli Python kütüphanelerini yükleyin:
```powershell
pip install requests websocket-client playwright pydantic
```

---

### 2. Adım 1: Chrome veya Edge'i Hata Ayıklama Modunda Başlatma (Port 9223)

UYAP oturumunun güvenli yönetilebilmesi için tarayıcınızı Port 9223 ile başlatıp UYAP Avukat Portal'a e-İmza veya Mobil İmza ile giriş yapınız:

**Google Chrome için:**
```cmd
chrome.exe --remote-debugging-port=9223 --user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data UYAP" https://avukat.uyap.gov.tr
```

**Microsoft Edge için:**
```cmd
msedge.exe --remote-debugging-port=9223 --user-data-dir="%LOCALAPPDATA%\Microsoft\Edge\User Data UYAP" https://avukat.uyap.gov.tr
```

> **Not:** Portal açıldığında normal şekilde e-İmzanızla veya Mobil İmzanızla UYAP ana sayfasına girmeniz yeterlidir. Tarayıcıyı kapatmayınız.

---

### 3. Adım 2: İnteraktif Windows Menüsü ile Kullanım (`baslat_windows.bat`)

Proje klasöründeki **`baslat_windows.bat`** dosyasına çift tıklayarak tüm işlemleri menüden yönetebilirsiniz:

```text
==================================================================
   UYAP Avukat Portal Evrak Indirici - Windows 11
==================================================================

  1) Islemlerim Indirici (Son 1 Yil - Hizli)
  2) Islemlerim Indirici (Gecmis Yillar / Ozel Tarih Araligi)
  3) Dava Dosyalarindan Belirli Evrak Indir (Durusma, Rapor, Karar vb.)
  4) Dava Dosyalarindan TUM Evraklari ve EKLERI Indir (Toplu Arsiv)
  5) Dava & Cevap Layihalari (Dava, Cevap, Bilirkisi Itiraz, Beyan)
  6) Tebligat & Mazbatalar (Fiziki PTT + UETS - 5 Gün, 1-2 Hafta, 30-90 Gün Seçimli)
  7) Durusma Takvimi Olustur (.ics / Google & Outlook Takvim + CSV)
  8) Indirilen UDF'leri PDF'e Donustur (TrueType Embedded PDF)
  9) Tebligat & Sure Analizi Calistir (tebligat_takip_listesi.csv)
 10) Evrak Zenginlestirme & Akilli Isimlendirme (enrich_and_rename)
 11) Chrome / Edge UYAP Oturumu Baslat (Port 9223)
==================================================================
```

---

### 4. Adım 3: Doğrudan Komut Satırı (PowerShell / CMD) Kullanımı

Terminalden doğrudan hedefli görevler çalıştırmak için aşağıdaki komutları kullanabilirsiniz:

#### ⚖️ Dava Dosyalarından Evrak İndirme (`--mode dosyalar`)

```powershell
# 1. Tüm dosyalardaki Duruşma Tutanaklarını indir (Açık + Kapalı / Karara Çıkmış):
python uyap_indirici.py --cli --mode dosyalar --evrak-turu durusma --scope all

# 2. Yalnızca belirli bir mahkeme veya esas numarasına ait duruşmaları indir:
python uyap_indirici.py --cli --mode dosyalar --evrak-turu durusma --filter-birim "erzurum"
python uyap_indirici.py --cli --mode dosyalar --evrak-turu durusma --filter-birim "2025/506"

# 3. Bilirkişi Raporlarını ve altındaki ek belgeleri indir (Yalnızca açık dosyalar):
python uyap_indirici.py --cli --mode dosyalar --evrak-turu bilirkisi --include-attachments --scope acik

# 4. Gerekçeli Kararları, BAM İstinaf ve Yargıtay İlamlarını indir:
python uyap_indirici.py --cli --mode dosyalar --evrak-turu karar --scope all

# 5. Dava, Cevap, Delil, Bilirkişi İtiraz ve Beyan Layihalarını indir:
python uyap_indirici.py --cli --mode dosyalar --evrak-turu layihalar --scope all

# 6. Fiziki PTT Mazbatalarını ve UETS Elektronik Tebligatlarını İndir:
# Son 5 günlük (Acil Yasal Süreli Tebligatlar) - Hukuk Mahkemeleri:
python uyap_indirici.py --cli --mode dosyalar --evrak-turu tebligat --yargi-turu hukuk --days 5

# Son 1 haftalık (7 gün) - Ceza Mahkemeleri:
python uyap_indirici.py --cli --mode dosyalar --evrak-turu tebligat --yargi-turu ceza --days 7

# Son 2 haftalık (14 gün) - Tüm Mahkemeler:
python uyap_indirici.py --cli --mode dosyalar --evrak-turu tebligat --days 14

# Son 30, 60 veya 90 günlük tebligatlar:
python uyap_indirici.py --cli --mode dosyalar --evrak-turu tebligat --days 30
python uyap_indirici.py --cli --mode dosyalar --evrak-turu tebligat --days 60
python uyap_indirici.py --cli --mode dosyalar --evrak-turu tebligat --days 90

# Belirli bir tarihten günümüze olan tebligatlar:
python uyap_indirici.py --cli --mode dosyalar --evrak-turu tebligat --start-date 01.10.2026

# 7. Kurum cevaplarını (Banka ekstreleri, SGK, Tapu, EGM müzekkereleri) indir:
python uyap_indirici.py --cli --mode dosyalar --evrak-turu muzekkere --scope all

# 8. Ceza dosyalarındaki İddianame ve Fezlekeleri indir:
python uyap_indirici.py --cli --mode dosyalar --evrak-turu iddianame --scope all

# 9. Tensip Zabıtlarını indir:
python uyap_indirici.py --cli --mode dosyalar --evrak-turu tensip --scope all

# 10. Tüm derdest dava dosyalarının tüm evraklarını ve eklerini eksiksiz arşivle:
python uyap_indirici.py --cli --mode dosyalar --evrak-turu tumu --include-attachments --scope all
```

#### 📅 Duruşma Takvimi Oluşturma (`--mode durusmalar`)

```powershell
# Geçmiş 3 ay ve gelecek 6 ayın duruşma takvimini .ics ve CSV olarak çıkar:
python uyap_indirici.py --cli --mode durusmalar

# Belirli bir tarih aralığındaki duruşmaları takvime dök:
python uyap_indirici.py --cli --mode durusmalar --start-date 01.01.2025 --end-date 31.12.2026
```

#### 📂 İşlemlerim Portalı Toplu Evrak İndirme (`--mode islemlerim`)

```powershell
# Son 1 yılın portaldan yapılan işlemlerini indir:
python uyap_indirici.py --cli --mode islemlerim

# 2020 - 2026 arası tüm geçmiş evrakları indir:
python uyap_indirici.py --cli --mode islemlerim --start-date 01.01.2020 --end-date 14.11.2026
```

---

### 5. Adım 4: Toplu UDF -> Vektörel PDF Dönüştürme

İndirilen UDF dosyalarını topluca PDF'e çevirmek için:

```cmd
udf_toplu_pdf.bat
```
veya doğrudan Java komutuyla:
```cmd
java -Xmx1024m -Djava.awt.headless=true --add-opens=java.base/java.util=ALL-UNNAMED --add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.desktop/java.awt=ALL-UNNAMED --add-opens=java.desktop/javax.swing=ALL-UNNAMED -cp ".;jars/*" uyap.UdfBatchPdfConverter
```

> **Özellik:** Mevcut PDF'leri atlar; yalnızca yeni indirilen veya eksik kalan UDF'leri dönüştürür.

---

### 6. Adım 5: Tebligat & Yasal Süre Analizini Çalıştırma

İndirilen tüm fiziki mazbataları ve UETS evraklarını analiz edip Excel CSV tablosuna işlemek için:

```powershell
python tebligat_yoneticisi.py
```
* **Çıktı Dosyası:** `UYAP_Indirilenler/TEBLIGATLAR/tebligat_takip_listesi.csv`
* **İçerik:** PTT Barkod No, Muhatap, Muvekkil Eşleştirmesi, Tebligat Sonucu, UETS Delil ID, Tebligat Kanunu m.7/a 5 günlük yasal tebliğ tarihi ve süre uyarıları.

---

### 7. Adım 6: Evrak Zenginleştirme ve Akıllı Yeniden Adlandırma

Evrakların içeriklerini (content.xml) okuyup standart isimlendirmeye dönüştürmek için:

```powershell
# Önizleme (değişiklik yapmadan simüle eder):
python enrich_and_rename_documents.py --dry-run

# Gerçek uygulama:
python enrich_and_rename_documents.py
```

---

## 📱 Android / Termux Kullanımı

Android cihazınızda Termux üzerinden çalıştırmak için:

```bash
cd ~/uyap-evrak-indirici
./baslat_termux.sh
```

Açılan interaktif menüden dilediğiniz indirme modunu seçebilirsiniz. Mobil İmza veya e-İmza ile oturum yenileme arka planda otomatik gerçekleşir.

---

## 📂 Dosya ve Klasör Hiyerarşisi

İndirilen tüm evraklar mahkeme ve dosya hiyerarşisine uygun şekilde düzenlenir:

```
UYAP_Indirilenler /
├── DURUSMA_TUTANAKLARI /
│   ├── ai_case_manifest.json          <-- Yapay Zeka Dava Kütüphanesi
│   ├── ai_durusma_kronolojisi.csv     <-- Kronolojik Duruşma Tablosu
│   └── Ceza_Yargisi /
│       └── Erzurum_1._Agir_Ceza_Mahkemesi /
│           └── 2025_506 /
│               ├── 2025-12-17_Durusma_Zapti_1._Celse.udf
│               └── 2025-12-17_Durusma_Zapti_1._Celse.pdf
│
├── BILIRKISI_RAPORLARI /
├── GEREKCELI_KARARLAR /
├── DAVA_VE_CEVAP_LAYIHALARI /
├── TEBLIGATLAR /
│   └── tebligat_takip_listesi.csv     <-- Tebligat & Yasal Süre Tablosu
│
├── durusma_takvimi.ics                <-- Google & Outlook Takvim Dosyası
└── durusma_listesi.csv                <-- Duruşma Tablosu
```

---

## 🔒 Gizlilik, KVKK ve Güvenlik

* Bu yazılım **üçüncü taraf hiçbir sunucuya veri göndermez**. Tüm haberleşme doğrudan yerel bilgisayarınız ile Adalet Bakanlığı UYAP sunucuları (`avukat.uyap.gov.tr`) arasında gerçekleşir.
* Kişisel T.C. Kimlik, GSM ve dosya şifreleme anahtarları yerel ortamda korunur ve GitHub reposuna dahil edilmez (`.gitignore`).

---

## 📄 Lisans

© 2026 Av. Can KIZILYAR. **Tüm hakları saklıdır.** Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz ve ticari amaçla kullanılamaz. Ayrıntılar ve üçüncü taraf bileşen lisansları: [LICENSE](LICENSE).

Bu yazılım Adalet Bakanlığı'nın veya UYAP'ın resmi bir ürünü değildir.
