#!/bin/bash
set -e

# ==============================================================================
# UYAP Editör Modern - macOS Kurulum ve Gatekeeper Yapılandırma Betiği
# ==============================================================================

echo "=== UYAP Editör Modern - macOS Kurulumu ==="

APP_DIR="/Applications/UYAP Dokuman Editoru.app"
SABLON_APP_DIR="/Applications/UYAP Sablon Editoru.app"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
# yapılandırma: depoda config/, yayın paketinde paketin içindeki config/
if [ -d "$SCRIPT_DIR/config" ]; then CONF_DIR="$SCRIPT_DIR/config"; else CONF_DIR="$ROOT_DIR/config"; fi

mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources" "$APP_DIR/Contents/Java"
mkdir -p "$SABLON_APP_DIR/Contents/MacOS" "$SABLON_APP_DIR/Contents/Resources" "$SABLON_APP_DIR/Contents/Java"

echo "[1/4] Editör ve Modernizer dosyaları kopyalanıyor..."
cp -f "$SCRIPT_DIR/bin/dokuman.sh" "$APP_DIR/Contents/MacOS/dokuman"
chmod +x "$APP_DIR/Contents/MacOS/dokuman"

if [ -f "$SCRIPT_DIR/bin/sablon.sh" ]; then
    cp -f "$SCRIPT_DIR/bin/sablon.sh" "$SABLON_APP_DIR/Contents/MacOS/sablon"
    chmod +x "$SABLON_APP_DIR/Contents/MacOS/sablon"
fi

if [ -f "$ROOT_DIR/dist/uyap-modernizer.jar" ]; then
    cp -f "$ROOT_DIR/dist/uyap-modernizer.jar" "$APP_DIR/Contents/Java/"
    cp -f "$ROOT_DIR/dist/uyap-modernizer.jar" "$SABLON_APP_DIR/Contents/Java/"
fi

# Resmi UYAP Editör dosyaları (jar'lar tüm platformlarda aynıdır): Adalet Bakanlığı'nın Linux paketinden
for HEDEF in "$APP_DIR/Contents/Java" "$SABLON_APP_DIR/Contents/Java"; do
    [ -f "$SCRIPT_DIR/uyap-modernizer.jar" ] && cp -f "$SCRIPT_DIR/uyap-modernizer.jar" "$HEDEF/"
done
if [ ! -f "$APP_DIR/Contents/Java/editor_lib.jar" ]; then
    echo "  Resmi UYAP Editör dosyaları indiriliyor (rayp.adalet.gov.tr)..."
    TMP_UYAP=$(mktemp -d)
    if curl -fL --progress-bar "https://rayp.adalet.gov.tr/resimler/2/dosya/uyapeditor_5.4.20_amd64.zip" -o "$TMP_UYAP/uyap.zip"; then
        (cd "$TMP_UYAP" && unzip -q -o uyap.zip && tar -xf uyapeditor_5.4.20_amd64.deb data.tar.xz && mkdir -p d && tar -xf data.tar.xz -C d)
        cp -f "$TMP_UYAP"/d/usr/share/UYAPEditor/*.jar "$APP_DIR/Contents/Java/" 2>/dev/null || true
        cp -f "$TMP_UYAP"/d/usr/share/UYAPEditor/*.jar "$SABLON_APP_DIR/Contents/Java/" 2>/dev/null || true
    fi
    rm -rf "$TMP_UYAP"
fi
# Paketle gelen Java 14.0.2 (resmi OpenJDK; Apple Silicon'da Rosetta 2 ile)
if [ -x "$SCRIPT_DIR/jdk-14.0.2/bin/java" ]; then
    for HEDEF in "$APP_DIR/Contents/Java" "$SABLON_APP_DIR/Contents/Java"; do
        rm -rf "$HEDEF/jdk-14.0.2"; cp -a "$SCRIPT_DIR/jdk-14.0.2" "$HEDEF/"
    done
    echo "  Paketteki Java 14.0.2 kuruldu."
    if [ "$(uname -m)" = "arm64" ] && ! /usr/bin/pgrep -q oahd 2>/dev/null; then
        echo "  Apple Silicon: Java 14 için Rosetta 2 gerekir → softwareupdate --install-rosetta --agree-to-license"
    fi
fi
# Microsoft Core Fonts: ORİJİNAL .exe dosyalarından (macOS'un yerleşik tar'ı = bsdtar açar) ~/Library/Fonts'a
if [ -d "$SCRIPT_DIR/fonts-ms" ]; then
    G=$(mktemp -d)
    for exe in "$SCRIPT_DIR"/fonts-ms/*.exe; do /usr/bin/tar -xf "$exe" -C "$G" 2>/dev/null || true; done
    mkdir -p "$HOME/Library/Fonts"
    find "$G" -iname '*.ttf' -exec cp -n {} "$HOME/Library/Fonts/" \; 2>/dev/null || true
    for HEDEF in "$APP_DIR/Contents/Java" "$SABLON_APP_DIR/Contents/Java"; do
        [ -d "$HEDEF/jdk-14.0.2/lib" ] && mkdir -p "$HEDEF/jdk-14.0.2/lib/fonts" && find "$G" -iname '*.ttf' -exec cp -f {} "$HEDEF/jdk-14.0.2/lib/fonts/" \;
    done
    echo "  Windows yazı tipleri kuruldu ($(find "$G" -iname '*.ttf' | wc -l | tr -d ' ') dosya)."
    rm -rf "$G"
fi

echo "[2/4] Gatekeeper karantina özellikleri temizleniyor..."
xattr -cr "$APP_DIR" 2>/dev/null || true
xattr -cr "$SABLON_APP_DIR" 2>/dev/null || true

echo "[3/4] PKCS#11 e-imza bağlantıları..."
mkdir -p /usr/local/lib
if [ -f "/Library/Application Support/Akis/libakisp11.dylib" ]; then
    ln -sf "/Library/Application Support/Akis/libakisp11.dylib" /usr/local/lib/libakisp11.dylib
fi

echo "[4/4] Yapılandırma dosyaları..."
mkdir -p "$HOME/.uki"
[ ! -f "$HOME/.uki/modernizer.properties" ] && cp -f "$CONF_DIR/modernizer.properties" "$HOME/.uki/"
[ ! -f "$HOME/.uki/uyap.conf" ] && cp -f "$CONF_DIR/uyap.conf" "$HOME/.uki/"

echo "✓ macOS kurulumu tamamlandı. Uygulamalarınızdan UYAP Doküman Editörü ve Şablon Editörü'nü başlatabilirsiniz."
