<!-- CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır. -->
<!-- CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt -->
<!-- CKZ-MUHUR/1 MUHURSUZ -->
# UYAP-Termux Pro

**© 2026 Av. Can KIZILYAR — Tüm hakları saklıdır.** · Resmî değildir (bkz. `LICENSE.txt`, `NOTICE.txt`).

Android tablet ve telefonda (Termux + Termux:X11) **UYAP Doküman / Şablon Editörü**'nü masaüstündeki gibi
kullanmak, `.udf`/`.usf` dosyalarını çift tıklayarak açmak ve **USB e-imza okuyucusuyla** (TBB kırmızı token,
ArkSigner, ACR39 …) tarayıcıdan **UYAP Avukat Portal**'a girmek için kurulum paketi.

Bu depo tabletteki **v3 yedeği sonrası** kurulumdan (21.09.2026) ve `uyap-termux` 1.0/1.1 paketlerinden
türetilmiştir; geçmiş, commit'ler halinde korunmuştur (`git log`).

## 2.0'da neler var

| | |
|---|---|
| **Java 17/21 ile çalışır** | Editörün "Java sürümünüz 6–14 arası olmalı" engeli açılışta aşılır (jar'lar değiştirilmez). openjdk-11 artık zorunlu değil. |
| **`uyap` komutu** | Tek komut: menü, durum, masaüstü, editör, ayarlar, e-imza, Adalet, yedek, tanı. |
| **Kontrol Merkezi** | `uyap panel`: editör / okuyucu / Adalet E-İmza / Java durum kartları, tek dokunuşla işlemler, grafik ayarlar. |
| **Ayarlar dosyası** | Tema (açık, koyu, macOS), ölçek (ya da DPI'ya göre otomatik), vurgu rengi, **dokunmatik mod**, kaydırma, bellek. |
| **Word gibi akıcı kaydırma** | Kritik sönümlü yay; Ctrl/Shift+tekerlek artık editöre geçer; F9 ile aç/kapa. |
| **PDF'te Times New Roman** | Editörün yazı tipi eşlemecisi Termux klasörlerini görür; `uyap yazitipi` ile birebir Times. |
| **`.usf` → Şablon Editörü** | Şablonlar artık Doküman Editörü'nde açılmıyor. |
| **Güvenli yedek** | Tarayıcı parolaları, belge otomatik kayıtları ve özel anahtarlar varsayılan olarak yedeğe girmez. |

Tüm düzeltmelerin listesi: [DEGISIKLIKLER.md](DEGISIKLIKLER.md).

## Gerekenler

* Android 8+ ve OTG destekli tablet/telefon, USB e-imza okuyucu; ~3 GB boş yer, internet.
* **Termux**, **Termux:X11**, **Termux:API** (isteğe bağlı **Termux:Boot**, **Termux:Widget**) — hepsi **aynı
  kaynaktan** (hepsi F-Droid ya da hepsi GitHub). Play Store sürümleri uyumsuzdur.

## Kurulum

```bash
termux-setup-storage                    # izin penceresinde "İzin ver"
pkg install -y git
git clone https://github.com/cnkzlyr/uyap-termux-pro ~/uyap-termux-pro
bash ~/uyap-termux-pro/kur.sh --yine-de # git kopyası mühürsüzdür; mühürlü sürüm zip'inde --yine-de gerekmez
```

Kurulum resmî UYAP Editör'ü `uyap.gov.tr`'den, Adalet E-İmza'yı `cdn.uyap.gov.tr`'den indirir (pakette yoktur).
Otomatik indirme olmazsa: `bash kur.sh --editor-zip /sdcard/Download/uyapeditor_*_amd64.zip --adalet-deb /sdcard/Download/adalet-eimza-tray*.deb`

Seçenekler: `--hafif` (XFCE yerine fluxbox) · `--yazitipleri` (Microsoft Times/Arial) · `--deneme` (hiçbir şey
değiştirmeden adımları yazar) · `--kabul` (soru sormaz).

Sonra Android'de: Termux, Termux:X11, Termux:API için **pil optimizasyonunu kapatın**; Termux'a **"diğer
uygulamaların üzerinde göster"** izni verin; Termux:API'yi bir kez açın.

## Kullanım

```
uyap                  menü (durum özeti + işlemler)
uyap masaustu         Termux:X11 + XFCE masaüstü
uyap editor X.udf     belgeyi aç (editör açıksa aynı pencerede açılır)
uyap panel            Kontrol Merkezi
uyap durum            ● UYAP Editör  ● E-imza okuyucu  ● Adalet E-İmza  ● Java …
uyap ayarlar          tema, ölçek, dokunmatik mod, kaydırma, bellek
uyap yazitipi         PDF için Times New Roman
uyap yedek            gizli verileri dışlayan tam yedek
uyap tani             sorun giderme raporu (jetonlar gizlenmiş, panoya kopyalanır)
```

Editörde: **F9** akıcı kaydırmayı aç/kapa · **Ctrl+Shift+F12** UYAP-Termux bilgisi.

**E-imza ile portal girişi:** okuyucuyu takın → "İzin ver" → `uyap durum`'da okuyucu ve Adalet E-İmza yeşil →
telefonun Chrome'unda portala e-imza ile girin ("yerel ağ" izni sorulursa verin). PIN Android penceresinde sorulur.

## Fiziksel klavye (Galaxy Tab Book Cover Keyboard vb.)

`uyap masaustu` her açılışta klavyeyi bilgisayar gibi ayarlar (`uyap klavye` ile elle de çalışır):
Termux:X11'de **"Prefer scancodes"** açılır ve X düzeni **Türkçe Q** yapılır. Böylece Ctrl+A/C/V/X/Z/S, Alt+Tab,
AltGr+Q = @, AltGr+E = € ve ğ ü ş ı ö ç doğrudan çalışır. Türkçe F için: `uyap klavye f`. Durum: `uyap klavye durum`.

Editörde **tek başına Alt'a basmak** artık şeritte kısayol harflerini açmaz (yanlışlıkla Alt'a basınca yazı
bölünmez). Eski davranış için `ayarlar.ini` → `[klavye] alt_menu = evet`.

**Dokunmatik ekran:** Termux:X11 "Simulated touchscreen" moduna alınır: dokunduğunuz yere tıklar, sürükleyerek
metin seçer/taşır, uzun basma sağ tıktır. Ekran klavyesinde kaydırarak yazma ve öneriler açık kalır. Fare ya da
dokunmatik yüzey bağlarsanız bilgisayardaki gibi çalışır. Dizüstü touchpad davranışı için
`ayarlar.ini` → `[klavye] dokunma = touchpad`.

Android tarafında (bir kez): Ayarlar → Genel yönetim → Fiziksel klavye → Türkçe Q. Samsung'un yakaladığı
kısayollar (Alt+Tab, Ctrl+Boşluk) için Termux:X11 → Ayarlar → Klavye → "Enable Accessibility service".

## Ayarlar

`~/.config/uyap-termux/ayarlar.ini` (ilk açılışta oluşur; `uyap ayarlar` ya da Kontrol Merkezi ile düzenlenir):

```ini
[arayuz]
tema = acik          ; acik | koyu | macos-acik | macos-koyu | sistem
olcek = 1.2          ; 1.0–3.0 ya da otomatik. Tüm pencere ölçeklenir (şerit + belge); Tab S10+ için 1.75–2
vurgu =              ; #RRGGBB
dokunmatik = hayir   ; evet: kalın kaydırma çubuğu, geniş menüler
[kaydirma]
akici = evet
adim = 75
[java]
yol =                ; boş = otomatik (11 > 17 > 21)
bellek = otomatik    ; RAM'in ~%40'ı (768–4096 MB)
surum_taklidi = evet
[eimza]
aktif = evet
```

Ortam değişkenleri ayarları ezer: `UYAP_TEMA`, `UYAP_OLCEK`, `UYAP_JAVA`, `UYAP_BELLEK`; `UYAP_TEK_ORNEK=0`
(her belge ayrı JVM), `UYAP_AYRINTI=1` (ayrıntılı günlük), `EIMZA_PIN_MODE=android|swing`.

## Gizlilik

* PIN'ler kaydedilmez, iletilmez; yazara hiçbir veri gönderilmez.
* `uyap yedek` tarayıcı profillerini (kayıtlı parolalar, çerezler) yalnızca `--tarayici`, editörün belge otomatik
  kayıtlarını yalnızca `--belgeler` ile alır; `~/.ssh`, `~/.gnupg`, mühür özel anahtarı (`~/.ckz-muhur`) hiç alınmaz.
  Yedek zip'i 600 izniyle yazılır. **Yedeği "bağlantıya sahip herkes" ile paylaşmayın.**

## Klasörler (kurulumdan sonra)

| Yol | İçerik |
|---|---|
| `~/ue.py`, `~/java/` | Editör başlatıcısı ve Java kaynakları (`~/.uyap-editor/siniflar`'a derlenir) |
| `~/jars/` | Resmî UYAP Editör jar'ları + FlatLaf (SHA-256 doğrulamalı) |
| `~/eimza/` | USB CCID köprüsü, Adalet E-İmza başlatıcısı, `-javaagent`, otomatik başlatma |
| `~/.local/bin/uyap*` | `uyap`, `uyap-editor`, `uyap-masaustu`, `uyap-hakkinda` |
| `~/.eimza/*.log`, `~/.uyap-editor/editor.log` | Günlükler (`uyap gunluk`) |

## Geliştirme

```bash
python3 -m unittest discover -s testler     # ue.py birim testleri
python3 bilesenler/eimza/selftest.py        # köprü: sahte CCID okuyucu + T=1 kart
bash testler/java_testleri.sh               # Java bileşenleri + birim testleri + eimza-agent.jar
shellcheck -S warning $(git ls-files '*.sh') bilesenler/uyap
```

Hepsi GitHub Actions'ta (`.github/workflows/test.yml`) çalışır. Mühürlü dağıtım zip'i yazarın cihazında
`bash tools/surum_olustur.sh 2.0` ile üretilir (özel anahtar `~/.ckz-muhur/` — depoya ve yedeğe asla girmez).

## Sınırlar

* Bu sürümdeki değişiklikler x86_64 Linux'ta JDK 21 + Xvfb ve **gerçek UYAP Editör 5.4.19 jar'larıyla** sınandı;
  Termux (aarch64) üzerinde gerçek okuyucuyla tam akış ayrıca denenmelidir.
* Koyu temada editörün kendi araç çubuğu simgelerinin bazıları soluk görünür (simgeler UYAP'a ait).
* Editör Java 8 için yazıldığından Java 9+ modül kısıtlamaları başlatıcıda açılır (bkz. ue.py `MODUL_IZINLERI`).

## JDK 14.0.2 (isteğe bağlı)

Varsayılan Termux'un openjdk-21'idir (başlatıcı editörün 6-14 sürüm kontrolünü açılışta ve imzalamada geçer).
Editörü UYAP'ın desteklediği JDK 14.0.2 ile çalıştırmak için:

```bash
uyap jdk14            # glibc paketleri + resmî AdoptOpenJDK 14.0.2+12 aarch64 (SHA-256 doğrulamalı) + yama + deneme
uyap jdk14 --arsiv /sdcard/Download/OpenJDK14U-jdk_aarch64_linux_hotspot_14.0.2_12.tar.gz   # çevrimdışı
uyap jdk14 dene       # java -version + AWT/X11 denemesi
uyap jdk14 birak      # tekrar Java 21
```

JDK ~200 MB olduğundan depoya konmaz (GitHub 100 MB sınırı); kurulum her zaman aynı resmî arşivi indirip özetini
doğrular. Resmî Linux JDK'sı glibc ister: Termux glibc deposu kurulur, `bin/` dosyaları glibc bağlayıcısına yamanır
ve başlatıcı onu Termux'un `LD_PRELOAD`'u olmadan çalıştırır (`grun` kullanılmaz: Java kendi klasörünü bulamaz).
* Termux:X11'de dokunmatik "parmakla kaydırma" fare tekerleği gibi davranmaz; Termux:X11 ayarlarından
  "Touchpad" ya da iki parmakla kaydırma kullanın.
