#!/data/data/com.termux/files/usr/bin/bash
# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
# Adalet E-Imza (https://eimza.adalet.gov.tr) uygulamasini Termux'a kurar.
# Resmi Linux .deb paketinin icindeki platformdan bagimsiz JAR'i cikarir (paketin x86 Java'si KULLANILMAZ;
# uygulama Java 21 ister, Termux'un openjdk-21'i kullanilir).
#   bash ~/eimza/adalet_kur.sh                      -> Download klasorunde adalet-eimza-tray*.deb arar
#   bash ~/eimza/adalet_kur.sh /yol/adalet-eimza-tray_1_0_13_amd64.deb
DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "$DIR/marka.sh" ] && . "$DIR/marka.sh"
APPDIR="$DIR/adalet"
mkdir -p "$APPDIR"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"

DEB="$1"
if [ -z "$DEB" ]; then
  for d in "$HOME/storage/downloads" /sdcard/Download "$HOME/storage/shared/Download" "$HOME"; do
    f=$(ls -1 "$d"/adalet-eimza-tray*.deb 2>/dev/null | sort -V | tail -1)
    [ -n "$f" ] && { DEB="$f"; break; }
  done
fi
if [ -z "$DEB" ] || [ ! -f "$DEB" ]; then
  echo "adalet-eimza-tray*.deb bulunamadi."
  echo "1) https://eimza.adalet.gov.tr adresinden Linux (.deb) surumunu indirin (Download klasorune)."
  echo "2) Tekrar: bash ~/eimza/adalet_kur.sh   (ya da dosya yolunu arguman verin)"
  exit 1
fi
echo "Paket: $DEB"

J21="${EIMZA_JAVA21:-$PREFIX/lib/jvm/java-21-openjdk/bin/java}"
if [ ! -x "$J21" ]; then
  echo "Java 21 kuruluyor (pkg install openjdk-21) ..."
  pkg install -y openjdk-21 || { echo "openjdk-21 kurulamadi"; exit 1; }
  pkg install -y openjdk-21-x 2>/dev/null || echo "(uyari) openjdk-21-x kurulamadi: x11-repo acik mi? -> pkg install x11-repo"
fi

member=$(dpkg-deb --fsys-tarfile "$DEB" | tar -t 2>/dev/null | grep -E 'lib/app/eimza-tray-[^/]*\.jar$' | head -1)
[ -n "$member" ] || { echo "Paketin icinde eimza-tray JAR'i bulunamadi."; exit 1; }
echo "JAR cikariliyor: $member"
dpkg-deb --fsys-tarfile "$DEB" | tar -xO "$member" > "$APPDIR/eimza-tray.jar.tmp" || { echo "Cikarma hatasi"; exit 1; }
if ! unzip -p "$APPDIR/eimza-tray.jar.tmp" META-INF/MANIFEST.MF 2>/dev/null | grep -q "JarLauncher"; then
  echo "Cikarilan dosya beklenen Spring Boot JAR'i degil."; rm -f "$APPDIR/eimza-tray.jar.tmp"; exit 1
fi
mv -f "$APPDIR/eimza-tray.jar.tmp" "$APPDIR/eimza-tray.jar"
unzip -p "$APPDIR/eimza-tray.jar" META-INF/MANIFEST.MF | tr -d '\r' | grep -E '^Implementation-Version' | sed 's/.*: //' > "$APPDIR/surum.txt"
ic=$(dpkg-deb --fsys-tarfile "$DEB" | tar -t 2>/dev/null | grep -E 'hicolor/256x256/apps/.*\.png$' | head -1)
[ -n "$ic" ] && dpkg-deb --fsys-tarfile "$DEB" | tar -xO "$ic" > "$APPDIR/icon.png" 2>/dev/null
echo "Adalet E-Imza kuruldu: surum $(cat "$APPDIR/surum.txt")"
echo "Baslatmak icin: bash ~/eimza/adalet_baslat.sh   (Termux acilinca zaten otomatik baslar)"
