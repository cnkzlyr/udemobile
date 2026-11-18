# Antigravity Oturum Özeti ve Evdeki Bilgisayar Devir Belgesi (CanEditor v4.1.0)

> **Tarih:** 18 Kasım 2026  
> **Repo:** `https://github.com/cnkzlyr/udemobile` (dal: `main`)  
> **Yerel Çalışma Dizini (Ofis PC):** `C:\Users\C\.gemini\antigravity\scratch\udemobile`  
> **Amaç:** Evdeki bilgisayarda yeni bir Antigravity sohbeti açıldığında tüm bağlamı, Claude'un v4.0.1'de yarım/hatalı bıraktığı noktaları, yaptığımız düzeltmeleri, eklenen birleşik platform özelliklerini ve sıradaki adımları eksiksiz aktarmak.

---

## 1. Claude'un v4.0.1 Denemesinde Neler Bozuktu? (Kök Neden Teşhisi)

Depoyu, commit'leri (`f56eaf7`, `77a0759`, `bc04c52`), GitHub Actions günlüklerini ve `v4.0.1` sürüm dosyalarını tek tek inceledik ve şu **7 somut sorunu** tespit edip giderdik:

1. **GitHub Actions'ın tamamının çalışmama nedeni:**  
   `cnkzlyr/udemobile` özel (private) depo olduğu için ücretsiz Actions dakikası / ödeme sınırı dolmuş (*"recent account payments have failed or your spending limit needs to be increased"*). Bu yüzden tüm CI işleri daha ilk saniyede duruyordu. Çözüm: Ya GitHub Billing'den limit güncellenecek ya da paketleme yerel makinede `.\scripts\windows_yayin.ps1` ile yapılacak.
2. **Android `CanEditor-v4.0.1.apk` (43 MB) içinde Asistan Python çalışma ortamı YOKTU:**  
   WSL adımı tamamlanmadan derlendiği için `windows_yayin.ps1` `CANEDITOR_ASISTAN_ANDROID=0` ile devam etmiş; APK içinde `assets/asistan/asistan-rt-arm64.zip` olmadığı için Android'de Asistan ya sonsuz "Başlatılıyor" döngüsüne giriyor ya da *"Bu APK derlemesinde asistan çalışma ortamı yok"* hatası veriyordu.
3. **`uyap_watcher.py` başlangıçta çöküyordu (Drive + PIN hataları):**  
   - `G:\Drive'ım\UYAP_Arsiv` varsayılan yol olarak verildiği için `G:\` takılı olmayan her bilgisayarda `Path.mkdir()` `FileNotFoundError` ile nöbetçiyi anında çökertiyordu → **Düzeltildi:** erişilemeyen sürücüde yerel yedek klasöre güvenle düşer.
   - `_kayitli_pin()` yalnızca çalışma dizinindeki `./pin.txt`'e bakıyordu, `sunucu.py`'nin yazdığı `DATA_DIR/pin.txt`'i okumuyordu → **Düzeltildi.**
4. **`chrome-headless-shell` + `--headless=new` uyumsuzluğu:**  
   Paketle gelen görünmez tarayıcı `chrome-headless-shell` olmasına rağmen `uyap_indirici.py` ve `uets_downloader.py` buna `--headless=new` parametresi veriyordu. Ayrıca Windows'ta `CREATE_NO_WINDOW` bayrağı eksikti → **Düzeltildi.**
5. **Android `GizliTarayici` CDP WebSocket & Sekme Hatası:**  
   - Android WebView DevTools soyut UNIX soketinden döndüğü için `webSocketDebuggerUrl` içinde port (`:9223`) eksik gelebiliyordu (`ws://localhost/devtools/page/1`). `_ws_url()` artık her koşulda `ws://127.0.0.1:<port><path>` biçimine normalize ediyor.
   - `_open_uyap_tab()` Android WebView'da desteklenmeyen `PUT /json/new` çağırıyordu → artık mevcut WebView sayfasını `Page.navigate` ile yönlendiriyor.
   - `GizliTarayici.java`'ya `WebChromeClient` eklendi (e-Devlet / UYAP'ın JS `alert`/`confirm` pencereleri arka plan oturumunu kilitlemesin).
6. **Resmî Havelsan JAR Dönüştürücülerde Java 21 Bytecode Hatası (`UnsupportedClassVersionError`):**  
   `asistan/moduller/a4/java/uyap-exporter.jar` Java 21 (class version 65.0) ile derlendiği için Java 11/14/17 makinelerinde çalışmıyordu → Hem `uyap-exporter.jar` hem `UdfBatchPdfConverter.class` **Java 8 bytecode (`-source 8 -target 8`)** olarak yeniden derlendi; gerçek bir UYAP `.udf` dosyası üzerinde **UDF → PDF (118 KB), UDF → ODT (9 KB), UDF → DOCX (35 KB)** canlı test edilerek doğrulandı!
   Ayrıca `donusturucu.py` artık `%LOCALAPPDATA%\UYAPEditorModern` ve `%APPDATA%\com.caneditor.app\uyap-editor\editor` klasörlerindeki JAR'ları da otomatik buluyor.
7. **SQLite Windows Dosya Kilidi Sızıntıları (`WinError 32`) ve İkili Uygulama Karmaşası:**  
   - `sunucu.py` (`_KapananConn`), `drive_indeks.py`, `hayfa_kopru.py` ve `avukatasistan/defter.py` (`_ENGINE.dispose()`) düzeltilerek Windows'taki tüm SQLite dosya kilitleri giderildi.
   - İstek üzerine ayrı `UYAP-Editor-v*.apk` üretimi ve menüdeki *"Orijinal UYAP Editör'de aç"* karmaşası kaldırıldı; **CanEditor tek başına birleşik uygulama** haline getirildi.

---

## 2. v4.1.0 ile Eklenen Birleşik Platform Modülleri

### Arka Uç (`asistan/`)
| Dosya | Ne Yapar? |
|---|---|
| `asistan/jar_donustur.py` | Tamamen resmî Havelsan JAR sınıflarıyla (`editor.b.b`, `editor.b.a.f`) UDF → PDF / ODT / DOCX ve NAPS2 A4 PDF motoru (`POST /api/donustur`, `GET /api/donustur/durum`). |
| `asistan/drive_indeks.py` | Google Drive klasörünü artımlı olarak `drive_indeks.db` (SQLite) veritabanına alır; Türkçe-duyarsız arama, otomatik esas no çıkarımı, path-traversal korumalı dosya açma, eksik yerel evrakları yerel Drive'a veya Bulut Apps Script Webhook'una eşitleme (`/api/drive/*`). |
| `asistan/entegrasyon.py` | Notion (`Tüm Dosyalar Düzenli` DB) & TickTick canlı API istemcisi + güvenli yerel `.env` (`0600`) yapılandırması + UYAP yeni evrak/tebligat düştüğünde otomatik Notion not/sütun güncellemesi ve mahkeme listesine göre TickTick görevi oluşturma (`/api/entegrasyon/*`, `/api/notion/*`, `/api/ticktick/*`). |
| `asistan/hayfa_kopru.py` | `hayfahukuk.com` canlı veri köprüsü + SQLite çevrimdışı önbellek (`hayfa_cache.db`): Hukuk Haberleri, günlük Resmî Gazete bülteni, Yargıtay İçtihat Karar Arama (tam metin okuma + 1 tıkla dilekçeye ekleme), Mevzuat arama ve **%100 çevrimdışı** Adliye & İcra Dairesi IBAN Rehberi (`asistan/veri/adliye-veri.json` — 15 bina, 131 birim). |
| `asistan/sunucu.py` | Tüm bu modüllere ek olarak **UYAP Dosya Yönetim Merkezi** (`/api/dosyalar`, `/api/dosya/detay`, `/api/dosya/not`) ve yerel dosya notları veritabanı (`dosya_notlar.db`). |

### Ön Yüz (`frontend/public/`)
- **`frontend/public/hayfa.js`**: HAYFA Hukuk kurumsal tasarım dili (Lacivert `#0f2341`, Altın `#c8a45a`, mobil uyumlu kart/tablo ızgarası, dokunmatik sekmeler) + şu sekmeler:
  - `📁 Dosyalar` (UYAP Dava Yönetimi + Notlar + Drive Eşleşmesi + Tek Tıkla Notion/TT + JAR PDF/DOCX)
  - `☁️ Drive` (Canlı durum + Klasör/Webhook/Telegram ayarları + Drive→SQLite İndeksle + Eksikleri Eşitle + Drive Veritabanında Ara & Aç)
  - `📋 Notion/TT` (Canlı TickTick görevleri & ekle/tamamla + Canlı Notion davaları & not ekle + Güvenli API Ayarları)
  - `🔄 JAR Dönüştür` (Açık CanEditor belgesini veya cihazdan seçilen UDF'yi resmî JAR ile PDF/ODT/DOCX dönüştür & paylaş)
  - `📰 HAYFA` (İçtihat Ara + Dilekçeye Ekle · Haberler · Resmî Gazete · Mevzuat · Çevrimdışı Adliye & IBAN Kopyala)
- **`frontend/public/hukuk_hesap.js`**: Vekâlet, Faiz, Harç, SMM, CMK'ye ek olarak **İnfaz (5275 s.K.)** ve **Ceza Artırım/İndirim (TCK m.61/62)** hesaplayıcıları eklendi (7/7 hesaplayıcı çevrimdışı).

---

## 3. Doğrulanan Test Sonuçları (18 Kasım 2026)

Tüm 4 test paketi ofis Windows PC'sinde çalıştırıldı ve **%100 BAŞARILI** geçti:
- `python -m unittest discover -s asistan/testler` → **40 test** (39 OK, 1 skipped Windows'ta soyut UNIX soket)
- `node --test tests/*.test.cjs` → **10/10 PASS** (600 rastgele UETS süre vakası + 7 hukuk hesaplayıcısı + A4 yerleşim)
- `asistan/moduller/avukatasistan`: `python -m pytest -q tests` → **55/55 PASS**
- `platform/termux`: `python -m unittest discover -s testler` → **16 test** (14 OK, 2 Linux-only skipped)
- Canlı Havelsan JAR testi (gerçek `.udf` ile): **UDF → PDF ✓ · UDF → ODT ✓ · UDF → DOCX ✓**
- Canlı `hayfahukuk.com` testi: Haberler ✓ · Resmî Gazete ✓ · 10.694+ Yargıtay Kararı ✓ · Çevrimdışı Adliye/IBAN ✓

---

## 4. Evdeki Bilgisayardan Devam Etme Rehberi

Evdeki bilgisayarda Antigravity'yi açtığında şu komutu/mesajı vermen yeterli:
> *"github.com/cnkzlyr/udemobile reposunu çek, `docs/ANTIGRAVITY_HANDOFF.md` dosyasını oku ve kaldığımız yerden devam edelim."*

### Evde Yapılacak İlk Adımlar (Sırayla)
1. **Repoyu güncelle:**
   ```powershell
   git pull origin main
   ```
2. **Yerel gizli ayarları yapılandır (git'e ASLA girmez):**
   CanEditor → Asistan → **📋 Notion/TT → 🔑 API Anahtarları** sekmesinden (veya `asistan/moduller/avukatasistan/.env` dosyasına) Notion, TickTick, Telegram ve UETS bilgilerini gir; **🔐 UYAP Giriş** sekmesinden TC/GSM/Operatör ve (varsa) e-İmza PIN'ini kaydet; **☁️ Drive** sekmesinden `G:\Drive'ım\UYAP_Arsiv` klasörünü ve (mobil için) Apps Script Webhook URL'sini kaydet.
3. **Tüm Platform Paketlerini Derle ve Yayınla (Windows + Linux + Tam Asistanlı Android APK):**
   Evdeki bilgisayarda WSL (`Ubuntu-24.04`) kurulu/hazır olduğundan:
   ```powershell
   .\scripts\windows_yayin.ps1
   ```
   > **Önemli:** Android APK'sının içinde Termux'suz Python Asistan çalışma ortamının (`asistan-rt-arm64.zip`) yer alması için Adım 4 (WSL) başarıyla tamamlanmalı; oluşan APK yaklaşık ~85-100 MB olacaktır (43 MB çıkıyorsa WSL adımı atlanmış demektir!).
4. **Sıradaki Geliştirme Fikirleri (Evde Birlikte Yapabileceğimiz Faz 2):**
   - **Depo Temizliği / İnce Repo:** `udemobile` deposu `release/` içindeki eski APK'lar nedeniyle ~730 MB boyutunda; istenirse `git filter-repo` veya temiz bir birleşik repo ile <20 MB'a indirilebilir (veya Actions için public/self-hosted runner kurulabilir).
   - **CanEditor Doğrudan Bulut/UYAP Gönderimi & Akıllı Dilekçe Asistanı:** Dosya detayından tek tıkla o dosyanın mahkeme/esas/taraf bilgileri dolu şablon dilekçe oluşturma (`CanEditor` yeni belgeye otomatik doldurma!).
   - **Android Ön Plan Servisi (Foreground Service):** Telefon ekranı kilitliyken bile `AsistanServisi` + `GizliTarayici` + Mobil İmza oturum koruyucusunun Android tarafından öldürülmemesi için kalıcı bildirimli `ForegroundService` eklenmesi.
   - **İki Yönlü Google Drive API (OAuth2) Desteği:** Masaüstü Google Drive uygulaması olmayan Linux/Android cihazlarda doğrudan Google Drive REST API v3 ile iki yönlü dosya listeleme/indirme/yükleme.
   - **Canlı Masaüstü + Mobil Görsel Tasarım Cilası:** CanEditor ana düzenleyicisinin üst barı ve mobil alt gezinme çubuğunun da HAYFA Hukuk tasarım diliyle bütünleştirilmesi.

---

## 5. Güvenlik Hatırlatması
* API anahtarları (`GitHub PAT`, `TickTick Token`, `Notion Token`) **kesinlikle git deposuna yazılmadı**; yalnızca yerel `.env` / kullanıcı veri dizininde (`0600`) tutulmalıdır.
* Sohbet geçmişinde paylaşılan token'ları işin bittiğinde yenilemen (rotate) iyi bir güvenlik pratiğidir.
