# UYAP Editör — Android bağımsız uygulama (Termux / X11 / Termux:API OLMADAN)

Resmi **UYAP Doküman Editörü**'nü (5.4.20) telefonda **Java 14.0.2** ile, Termux ve X11 olmadan, dokunmatik olarak
çalıştıran bileşenler. Uygulama **CanEditor (UdeMobile)** içinde **"UYAP Editör"** simgesiyle gelir:
https://github.com/cnkzlyr/udemobile/releases (v3.19.0 ve sonrası).

## Nasıl çalışır

| Katman | Dosya | Görevi |
|---|---|---|
| glibc | Termux glibc deposu (Android için derlenmiş) | Resmi Linux JDK'sının ihtiyaç duyduğu C kitaplıkları |
| Java | AdoptOpenJDK 14.0.2+12 aarch64 (jlink, Nashorn dahil) | UYAP'ın desteklediği Java sürümü |
| Başlatıcı | `baslatici/uyapjava.c` | `libjvm.so`'yu doğrudan yükler (JNI_CreateJavaVM). JDK'nın `java` başlatıcısı kurulumunu `/proc/self/exe`'den bulur; glibc bağlayıcısı üzerinden çalıştırılınca bu yol bağlayıcının kendisi olur. |
| Ekran | `awtpatch14/` + Caciocavallo 1.11.1 | X sunucusu yerine pencereleri bellekte çizer. JDK 14 için `CTCGraphicsConfiguration` (JDK 14'te `BufferedImageGraphicsConfig` final) ve `MobilToolkit` (editör her tuşta `getLockingKeyState` sorar). |
| Köprü | `kopru/uyapmobil/Kopru.java` (-javaagent) | Ekranı değişen satırlarla paylaşılan belleğe yazar; dokunma/klavye/pano olaylarını editöre iletir; belge açar. |
| Bu depo | `core/src` (uyap-editor-modern ajanı) | Akıcı kaydırma, PDF yazı tipi düzeltmesi. Lisans denetimine dokunan `tr/gov/tubitak/**` sınıfları Android derlemesine alınmaz. |

Çalıştırma: `ld-linux-aarch64.so.1 --library-path glibc:jre/lib:jre/lib/server uyapjava jre/lib/server/libjvm.so <JVM seçenekleri> -- tr.com.havelsan.uyap.system.editor.common.WPAppManager getNewWPInstance EDITOR_TYPE_DOCUMENT`

## Köprü protokolü (127.0.0.1, ilk satır `AUTH jeton`)

`M x y` · `D x y düğme` · `U x y düğme` · `W x y adım` · `T metin(hex UTF-8)` · `K vk 1 değiştirici` · `Y pano(hex)` · `O yol(hex)` (belge aç) · `X` (kapat) · `P yol.png` (ekran görüntüsü)
Köprüden gelen: `PANO <hex>` (editörde kopyalanan metin).

## Derleme

`python3 uyapmobil_hazirla.py` (CanEditor deposunda `scripts/`): tüm bileşenleri SHA-256 sabit olarak indirir, jlink + glibc
bağımlılık taraması + `aarch64-linux-gnu-gcc` ile `uyapjava`. Resmi UYAP editörü dağıtılmaz; telefon ilk açılışta yalnızca
rayp.adalet.gov.tr'den indirir.

## Masaüstünde dene (x86, X'siz)

```
java --patch-module java.desktop=awt-patch14.jar --add-reads java.desktop=java.logging,ALL-UNNAMED \
  --add-opens java.desktop/com.github.caciocavallosilano.cacio.ctc=ALL-UNNAMED --add-opens java.desktop/com.github.caciocavallosilano.cacio.peer.managed=ALL-UNNAMED \
  --add-opens java.desktop/sun.font=ALL-UNNAMED -Dcacio.managed.screensize=1280x800 -Djava.awt.headless=false \
  -javaagent:uyapmobil-kopru.jar -Duyapmobil.port=47011 -Duyapmobil.jeton=t -Duyapmobil.ekran=ekran.bin \
  -cp "/usr/share/UYAPEditor/*" tr.com.havelsan.uyap.system.editor.common.WPAppManager getNewWPInstance EDITOR_TYPE_DOCUMENT
printf 'AUTH t\nP ekran.png\n' | nc 127.0.0.1 47011
```
