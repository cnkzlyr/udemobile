# CanEditor 4 — Birleşik Hukuk Asistanı ve Editör: Mimari

CanEditor 4.0, sekiz ayrı depoyu tek uygulamada birleştirir. Gövde CanEditor'dur (Tauri masaüstü,
Android WebView, taşınabilir web). Diğer depolar, git geçmişindeki kaynak commit'leriyle bu depoya
alt dizin olarak taşındı.

| Kaynak depo | Yeni konum | Uygulamadaki karşılığı |
|---|---|---|
| `udemobile` (CanEditor) | depo kökü | Editör: UDF/DOCX/PDF/TIFF, e-imza, PDF, şablonlar |
| `avukatasistan` | `asistan/moduller/avukatasistan` | UETS e-tebligat → süre → TickTick/Notion/Telegram, dosya defteri |
| `uyap-evrak-indirici` | `asistan/moduller/evrak` | UYAP Avukat Portal evrak kataloğu, indirme, PDF dönüştürme, nöbetçi |
| `naps-uyap-thunar-tools` | `asistan/moduller/a4` | NAPS2 yöntemli A4 PDF motoru (+ Thunar sağ tık eylemleri) |
| `uyap-editor-modern` | `platform/uyap-editor-modern` | Resmî UYAP Editörü için modernleştirici + paketler (ayrı etiket) |
| `uyap-termux-pro` | `platform/termux` | Android/Termux'ta resmî UYAP Editörü + USB e-imza |
| UYAP Editör (resmî, Havelsan) | dağıtılmaz | CanEditor "Orijinal UYAP Editöründe Aç" ile çağırır; jar'lar lisanslıdır |
| `libreofficemobile` | — | Depo boştu. Ofis belgesi ihtiyacını CanEditor'un DOCX/ODT desteği karşılar |

## Katmanlar

```
┌──────────────────────────── CanEditor arayüzü (frontend/public) ────────────────────────────┐
│ editor.js · esign.js · pdfexport.js …            asistan.js  (Asistan menüsü / Ctrl+K)        │
│                                                  ├─ Süre hesabı   ┐ sunucusuz, her platformda  │
│                                                  ├─ A4 PDF        ┘ (Android ve web dahil)     │
│                                                  └─ Ajanda · UYAP Evrak · Görevler ──┐         │
└──────────────────────────────────────────────────────────────────────────────────────┼────────┘
        Tauri (src-tauri)  asistan.rs: sunucuyu bulur/başlatır, anahtarı verir          │ HTTP + anahtar
                                                                                        ▼
                 asistan/sunucu.py  (127.0.0.1:8765, yalnızca standart kütüphane)
                   ├─ /api/ajanda        defter.db (UETS süreleri, takvim) + uyap_katalog.db (duruşmalar)
                   ├─ /api/evrak/ara     uyap_katalog.db (Türkçe-duyarsız, -hariç)
                   ├─ /api/evrak/dosya   yalnızca katalogda kayıtlı indirilmiş dosya
                   ├─ /api/gorev/<ad>    izin listesindeki modül komutları (alt süreç + günlük)
                   └─ /api/a4            moduller/a4 motoru (yerel dosya yolları)
```

## Platformlara göre ne çalışır

| Özellik | Windows / macOS / Linux kurulum paketi | Android (APK) | Taşınabilir web |
|---|---|---|---|
| Editör, PDF/DOCX | ✓ | ✓ | ✓ |
| Süre hesabı, A4 PDF | ✓ | ✓ | ✓ |
| Ajanda, UYAP evrak kataloğu arama, defter | ✓ gömülü sunucu | ✓ APK içi Python, **Termux gerekmez** | Sunucu + eşleştirme |
| UETS / UYAP evrak indirme (tarayıcı otomasyonu) | ✓ gömülü görünmez Chrome | — (masaüstünde çalışır) | — |
| E-imza (akıllı kart / USB token) | ✓ sürücüsüz | ✓ sürücüsüz (APK) | — |
| UYAP oturumu | Kart takılıysa e-imza; değilse / kopunca bağlanana kadar Mobil İmza | Mobil İmza | — |

## Oturum kuralı (UYAP)

`UyapBrowserBridge.akilli_oturum_ac` tüm oturum açma/yenileme noktalarında (nöbetçi, evrak motoru, CLI
indirme döngüleri) tek kuraldır: e-İmza kartı takılıysa e-İmza; takılı değilse ya da e-İmza girişi
bağlantı/kart nedeniyle olmazsa Mobil İmza gönderilir ve oturum açılana kadar tekrarlanır. Telefon
bildirimle boğulmasın diye denemeler arasında 1 → 2 → 5 → 10 dk beklenir; beklerken kart takılırsa hemen
e-İmzaya dönülür. Kartın reddettiği PIN asla yeniden denenmez (kart bloke olmasın). Mobil İmza bilgileri:
`.uyap_config.json` (`tc`, `gsm`, `operator`) ya da `UYAP_TC` / `UYAP_GSM` / `UYAP_OPERATOR`.

## Gömülü görünmez tarayıcı (masaüstü)

Chrome for Testing `chrome-headless-shell` + uyumlu `chromedriver` pakete girer (`tarayici-<mimari>/`).
Penceresi yoktur; sunucu görevlere `CANASISTAN_GORUNMEZ=1` verir ve modüller (UETS Selenium yolu, UYAP
evrak CDP yolu) tarayıcıyı her durumda arka planda açar. Kullanıcının Chrome kurmasına gerek yoktur.

## Android: Termux'suz asistan

`scripts/asistan_android_hazirla.py` → `assets/asistan/asistan-rt-arm64.zip`: CPython 3.12 aarch64
(python-build-standalone), manylinux aarch64 tekerlekleri, Termux glibc'si ve `asistan/`. `AsistanServisi.java`
ilk açılışta bunu açar ve Python'u glibc yükleyicisiyle başlatır (UYAP Mobil'in Java için kullandığı
yöntemin aynısı; targetSdk 28). Editörün JS köprüsü (`asistanBaglanti`) anahtarı kendiliğinden verir.
CI, çalışma ortamını Android'deki başlatma komutunun aynısıyla qemu-aarch64 altında sınar.

## Kurulum gerektirmeyen bileşenler (masaüstü)

`scripts/masaustu_hazirla.py` CI'da her platform için şunları üretir; Tauri bunları pakete kaynak olarak koyar:

| Bileşen | Konum (paket içi) | Neden |
|---|---|---|
| Gömülü Java 21 (jlink, ~60 MB) | `eimza/jre` · macOS: `eimza/jre-aarch64`, `eimza/jre-x86_64` | Adalet E-İmza ve UDF→PDF görevleri |
| Hukuk Asistanı sunucusu (PyInstaller) | `sidecar/asistan-sunucu-<mimari>/` | UETS, UYAP evrak, A4 — Python'suz |

- **Sunucu:** `asistan.rs` önce gömülü ikiliyi başlatır; görevler aynı ikiliyle `--calistir betik.py`
  biçiminde çalışır. Modül kodu ilk açılışta kullanıcı veri dizinine eşitlenir (modüller verilerini kendi
  klasörüne yazar; paket klasörü salt okunurdur). Sürüm değişince kod güncellenir, `.env/.json/.db` korunur.
  `scripts/asistan_paketle.py` modüllerin tüm import'larını kaynak koddan çıkarıp gömer ve paketlemeden
  sonra Python'suz ortamda her import'u ve görev betiklerini çalıştırarak duman testi yapar.
- **E-imza sürücüsüz:** Resmî Adalet E-İmza (ilk kullanımda cdn.uyap.gov.tr'den) gömülü Java ile çalışır
  ve karta doğrudan APDU ile konuşur; okuyucuya işletim sisteminin PC/SC katmanıyla ulaşır:
  Windows `winscard` + yerleşik CCID, macOS yerleşik, Linux `pcscd` + `libccid` — **.deb/.rpm paketi bunları
  bağımlılık olarak otomatik kurar** (`tauri.linux.conf.json`). AppImage sistem hizmeti kuramadığı için
  orada bir kez `sudo apt install pcscd libccid` gerekir; CanEditor bunu hata mesajında söyler.
  Kart bulunamazsa kurulu bir PKCS#11 sürücüsü (AKİS/SafeNet) ikinci yol olarak denenir.
- **Lisans sınırı:** AKİS/ArkSigner PKCS#11 kütüphaneleri ve Havelsan UYAP Editör jar'ları dağıtılamaz;
  bu yüzden pakete konmaz, gerekirse yalnızca resmî adreslerinden çalışma anında indirilir.

## Güvenlik kuralları (sunucu)

- Yalnızca `127.0.0.1`'e bağlanır; `Host` başlığı yerel değilse 403 döner (DNS rebinding).
- Her `/api` isteğinde `X-Asistan-Anahtar` zorunludur. Özel başlık CORS ön kontrolünü tetikler;
  CORS yalnızca CanEditor kökenlerine açıktır (Tauri, `file://`/Android, localhost).
- Görevler sabit izin listesinden başlar; istemci komut veya yol gönderemez.
- Evrak dosyaları istemcinin verdiği yoldan değil, katalogdaki kayıttan çözülür.

## Süre hesabının tek kaynağı

Kural `asistan/moduller/avukatasistan/utils.py` (`calculate_deadlines`) içindedir. `asistan.js` bunun
JavaScript karşılığıdır; `tests/asistan_sure.test.cjs` 600 rastgele tarih/merci için iki uygulamanın
aynı sonucu verdiğini CI'da doğrular. Resmî ve adli tatiller tarihi ileri almaz, yalnızca uyarı olarak
gösterilir: hata yapılacaksa erken tarafta yapılır.

## Testler (CI: `.github/workflows/asistan-testleri.yml`)

```bash
python3 -m unittest discover -s asistan/testler -v                 # sunucu: güvenlik + gerçek şemalar
(cd asistan/moduller/avukatasistan && python3 -m pytest -q tests)  # UETS asistanı
TZ=Europe/Istanbul node --test tests/*.test.cjs                    # arayüz süre motoru ≡ Python
(cd platform/termux && python3 -m unittest discover -s testler)    # Termux paketi
```

## Yayınlar

| Etiket | İş akışı | Çıktı |
|---|---|---|
| `v*` | `desktop-release.yml` | CanEditor: APK, exe/msi, dmg, deb/rpm/AppImage, taşınabilir web |
| `evrak-v*` | `uyap-evrak-paketleri.yml` | Bağımsız UYAP Evrak Yöneticisi kurulumları |
| `editor-modern-v*` | `uyap-editor-modern.yml` | Resmî UYAP Editörü modernleştirici paketleri |
