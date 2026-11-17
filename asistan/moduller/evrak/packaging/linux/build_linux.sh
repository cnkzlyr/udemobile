#!/usr/bin/env bash
# UYAP Evrak Yöneticisi — Linux paketleri: AppImage, .deb, .rpm
# Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır.
#
# Ön koşul: dist/UYAPEvrak (PyInstaller çıktısı; runtime/jre ve fonts/ CI tarafından eklenir)
# Gerekenler: fpm (gem install fpm), rpm, appimagetool (betik indirir)
set -euo pipefail
cd "$(dirname "$0")/../.."
VER="${VER:-3.0.0}"
ARCH="$(uname -m)"
APP=dist/UYAPEvrak
OUT=dist
[ -d "$APP" ] || { echo "Önce PyInstaller çalıştırın: pyinstaller packaging/uyap_evrak.spec"; exit 1; }

# --- .desktop ve simge
mkdir -p build/linux
cat > build/linux/uyap-evrak.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=UYAP Evrak Yöneticisi
GenericName=UYAP evrak kataloğu ve indirici
Comment=© Av. Can KIZILYAR — UYAP evraklarını filtrele, indir, görüntüle, PDF'e dönüştür
Exec=uyap-evrak %F
Icon=uyap-evrak
Terminal=false
Categories=Office;Utility;
MimeType=application/x-udf;image/tiff;
EOF

# --- deb / rpm (fpm): /opt/uyap-evrak + /usr/bin/uyap-evrak
STAGE=build/linux/root
rm -rf "$STAGE"
mkdir -p "$STAGE/opt/uyap-evrak" "$STAGE/usr/bin" "$STAGE/usr/share/applications" "$STAGE/usr/share/icons/hicolor/256x256/apps"
cp -a "$APP/." "$STAGE/opt/uyap-evrak/"
ln -sf /opt/uyap-evrak/UYAPEvrak "$STAGE/usr/bin/uyap-evrak"
ln -sf /opt/uyap-evrak/UYAPEvrakKonsol "$STAGE/usr/bin/uyap-evrak-konsol"
cp build/linux/uyap-evrak.desktop "$STAGE/usr/share/applications/"
cp assets/uyap_evrak_256.png "$STAGE/usr/share/icons/hicolor/256x256/apps/uyap-evrak.png"
COMMON=(-s dir -n uyap-evrak -v "$VER" --license "Proprietary - Av. Can KIZILYAR" --vendor "Av. Can KIZILYAR"
        --maintainer "Av. Can KIZILYAR" --url "https://github.com/cnkzlyr/uyap-evrak-indirici"
        --description "UYAP Evrak Yöneticisi: UYAP evrak kataloğu, filtreli toplu indirme, görüntüleyici ve PDF dönüştürücü. © Av. Can KIZILYAR"
        -C "$STAGE")
fpm "${COMMON[@]}" -t deb -d "libx11-6" -d "chromium | chromium-browser | google-chrome-stable" -p "$OUT/uyap-evrak_${VER}_amd64.deb" .
fpm "${COMMON[@]}" -t rpm -p "$OUT/uyap-evrak-${VER}.${ARCH}.rpm" .

# --- AppImage
AD=build/linux/UYAPEvrak.AppDir
rm -rf "$AD"
mkdir -p "$AD/usr/bin"
cp -a "$APP/." "$AD/usr/bin/"
cp build/linux/uyap-evrak.desktop "$AD/uyap-evrak.desktop"
cp assets/uyap_evrak_256.png "$AD/uyap-evrak.png"
cat > "$AD/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/UYAPEvrak" "$@"
EOF
chmod +x "$AD/AppRun"
if [ ! -x build/appimagetool ]; then
  curl -fsSL -o build/appimagetool "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
  chmod +x build/appimagetool
fi
ARCH="$ARCH" APPIMAGE_EXTRACT_AND_RUN=1 build/appimagetool "$AD" "$OUT/UYAPEvrak-${VER}-${ARCH}.AppImage"
ls -la "$OUT"
