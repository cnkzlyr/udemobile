<!-- CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır. -->
<!-- CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt -->
<!-- CKZ-MUHUR/1 MUHURSUZ -->
# UYAP e-imza + Adalet E-İmza + UYAP Editör (Termux native / XFCE)

## Kurulum
Ana kurulum depo kökündeki `kur.sh` ile yapılır (bkz. üst klasördeki README). Yalnızca bu klasörü yeniden
tümleştirmek için: `bash ~/eimza/kur.sh`. Durum ve işlemler için: `uyap` / `uyap panel`.

`~/eimza/kur.sh` şunları yapar: paketleri kurar → Termux her açıldığında otomatik başlatmayı ekler → Adalet E-İmza'yı
(Download'daki `adalet-eimza-tray*.deb`'den) kurar → UYAP Editör'ü XFCE uygulaması yapar → hepsini başlatır.
Geri almak: `bash ~/eimza/kaldir.sh` (dosyaları silmez).

## Otomatik başlatma (Termux ne zaman açılırsa)
* Her Termux oturumu açılışında `~/.bashrc`/`~/.profile` kancası `otobaslat.sh`'i arka planda çalıştırır.
  İdempotenttir: çalışan bileşene dokunmaz.
* Telefon açılışında: **Termux:Boot** kuruluysa `~/.termux/boot/uyap-eimza.sh` çalışır.
* XFCE oturumu açılınca: `~/.config/autostart/uyap-eimza.desktop` (Adalet uygulaması görünmez ekrandaysa gerçek ekrana taşır).
* Kapatmak için: `EIMZA_OTO=0` (hepsi), `EIMZA_TRAY=0` (yalnız Adalet uygulaması).
* Android'de Termux için pil optimizasyonunu kapat; `termux-dialog` için "diğer uygulamaların üzerinde göster" izni ver.

## E-imza köprüsü (USB okuyucu)
Okuyucuyu OTG ile tak; izleyici arka planda bağlanır, çıkar-tak'ta yeniden bağlanır. Durum: `cat ~/.eimza/izle.log`.
Sorun olursa: `bash ~/eimza/eimza_tani.sh`.

## Adalet E-İmza (Chrome ile UYAP Avukat Portal girişi)
* Resmî uygulama (Java 21) Termux'ta `127.0.0.1:5975`'te çalışır; kartı bizim köprü üzerinden okur.
* Chrome'da (telefon) portalda e-imza ile giriş yap; Chrome "yerel ağa erişim" izni sorarsa izin ver.
* PIN sayfadan gelmezse Android'in PIN penceresi açılır (`EIMZA_PIN_MODE=swing` ile eski pencere).
* Komutlar: `bash ~/eimza/adalet_baslat.sh durum|stop|restart`; günlük: `~/.eimza/adalet.log`.
* Gerekenler: `pkg install openjdk-21 openjdk-21-x` (kur.sh ister), görünmez ekran için `xorg-server-xvfb`.
* Yeni sürüm: yeni `.deb`'i Download'a koy → `bash ~/eimza/adalet_kur.sh`.

## UYAP Editör uygulaması
* Menüde/masaüstünde **UYAP Editör**; `.udf` ve `.usf` çift tıklayınca editörde açılır (boş pencere açılmaz).
  `.desktop` içindeki `%F`, dosya yollarını `uyap-editor`'e verir.
* Editör zaten açıksa belge onda açılır (yeni JVM açılmaz). Kapatmak için `UYAP_TEK_ORNEK=0`.
* Elle: `uyap editor belge.udf` (ya da `python ~/ue.py belge.udf`). Günlük: `~/.uyap-editor/editor.log`.

## Sınırlar
* Test: x86 Linux'ta JDK 11/21 + sahte CCID okuyucuyla. Gerçek Termux'ta (aarch64) tam akış denenmedi.
* ACR39 (TBB) ve ArkSigner köprü testleri önceki sürümlerde gerçek donanımda yapıldı.
* Adalet uygulamasının tepsi simgesi Termux'ta görünmeyebilir; servis simgeden bağımsız çalışır.
