#!/bin/bash
set -e

# ==============================================================================
# UYAP Editör Modern - Linux Tek Tıkla Kurulum Betiği
# ==============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== UYAP Editör Modern Kurulumu ===${NC}"

INSTALL_DIR="$HOME/.local/share/uyap-editor-modern"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
MIME_DIR="$HOME/.local/share/mime"
ICONS_DIR="$HOME/.local/share/icons/hicolor"

mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$DESKTOP_DIR" "$MIME_DIR/packages" "$ICONS_DIR"

echo -e "[1/6] Editör dosyaları hazırlanıyor..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Depodan (platforms/linux/bin) ya da yayın paketinden (dosyalar kökte) kurulum
if [ -d "$SCRIPT_DIR/bin" ]; then BIN_SRC="$SCRIPT_DIR/bin"; else BIN_SRC="$SCRIPT_DIR"; fi
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
# yapılandırma: depoda config/, yayın paketinde paketin içindeki config/
if [ -d "$SCRIPT_DIR/config" ]; then CONF_DIR="$SCRIPT_DIR/config"; else CONF_DIR="$ROOT_DIR/config"; fi

# JAR dosyalarını kopyala
if [ -d "/usr/share/UYAPEditor" ]; then
    cp -rf /usr/share/UYAPEditor/*.jar "$INSTALL_DIR/" 2>/dev/null || true
    [ -d "/usr/share/UYAPEditor/images" ] && cp -rf /usr/share/UYAPEditor/images "$INSTALL_DIR/"
fi

# Sistemde resmi UYAPEditor yoksa doğrudan resmi paketten temin et
if [ ! -f "$INSTALL_DIR/editor_lib.jar" ]; then
    TMP_UYAP=$(mktemp -d)
    if [ -f "$SCRIPT_DIR/uyapeditor_5.4.20_amd64.deb" ]; then
        echo "Resmi UYAP paketi (paketin içinden) açılıyor..."
        cp -f "$SCRIPT_DIR/uyapeditor_5.4.20_amd64.deb" "$TMP_UYAP/"
        HAZIR=1
    else
        echo "Resmi UYAP paketleri indiriliyor (Adalet Bakanlığı)..."
        HAZIR=0
    fi
    if [ "$HAZIR" = "1" ] || curl -fL --progress-bar "https://rayp.adalet.gov.tr/resimler/2/dosya/uyapeditor_5.4.20_amd64.zip" -o "$TMP_UYAP/uyap.zip"; then
        [ -f "$TMP_UYAP/uyap.zip" ] && unzip -q -o "$TMP_UYAP/uyap.zip" -d "$TMP_UYAP"
        if [ -f "$TMP_UYAP/uyapeditor_5.4.20_amd64.deb" ]; then
            cd "$TMP_UYAP"
            if command -v dpkg-deb >/dev/null 2>&1; then
                dpkg-deb -x uyapeditor_5.4.20_amd64.deb "$TMP_UYAP/deb_out"
            elif command -v ar >/dev/null 2>&1; then
                ar x uyapeditor_5.4.20_amd64.deb data.tar.xz 2>/dev/null || ar x uyapeditor_5.4.20_amd64.deb data.tar.gz 2>/dev/null
                mkdir -p "$TMP_UYAP/deb_out"
                [ -f data.tar.xz ] && tar -xf data.tar.xz -C "$TMP_UYAP/deb_out"
                [ -f data.tar.gz ] && tar -xf data.tar.gz -C "$TMP_UYAP/deb_out"
            fi
            if [ -d "$TMP_UYAP/deb_out/usr/share/UYAPEditor" ]; then
                cp -rf "$TMP_UYAP/deb_out/usr/share/UYAPEditor/"*.jar "$INSTALL_DIR/" 2>/dev/null || true
                [ -d "$TMP_UYAP/deb_out/usr/share/UYAPEditor/images" ] && cp -rf "$TMP_UYAP/deb_out/usr/share/UYAPEditor/images" "$INSTALL_DIR/"
            fi
            cd "$SCRIPT_DIR"
        fi
    fi
    rm -rf "$TMP_UYAP"
fi

# Modernizer JAR'ı kopyala
if [ -f "$ROOT_DIR/dist/uyap-modernizer.jar" ]; then
    cp -f "$ROOT_DIR/dist/uyap-modernizer.jar" "$INSTALL_DIR/"
    if [ -w "/usr/share/UYAPEditor" ]; then
        cp -f "$ROOT_DIR/dist/uyap-modernizer.jar" "/usr/share/UYAPEditor/" 2>/dev/null || true
    fi
fi

# Başlatıcıları kopyala
cp -f "$BIN_SRC/dokuman.sh" "$INSTALL_DIR/"
cp -f "$BIN_SRC/sablon.sh" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/dokuman.sh" "$INSTALL_DIR/sablon.sh"

if [ -w "/usr/share/UYAPEditor" ]; then
    cp -f "$BIN_SRC/dokuman.sh" "/usr/share/UYAPEditor/" 2>/dev/null || true
    cp -f "$BIN_SRC/sablon.sh" "/usr/share/UYAPEditor/" 2>/dev/null || true
fi

ln -sf "$INSTALL_DIR/dokuman.sh" "$BIN_DIR/uyap-dokuman"
ln -sf "$INSTALL_DIR/sablon.sh" "$BIN_DIR/uyap-sablon"

echo -e "[2/6] Java 14.0.2 kontrol ediliyor..."
# Paketle gelen Java 14.0.2 (jlink, resmi OpenJDK) varsa o kullanılır: indirme gerekmez
if [ -x "$SCRIPT_DIR/jdk-14.0.2/bin/java" ]; then
    rm -rf "$INSTALL_DIR/jdk-14.0.2"
    cp -a "$SCRIPT_DIR/jdk-14.0.2" "$INSTALL_DIR/"
    echo "  Paketteki Java 14.0.2 kuruldu."
fi
[ -f "$SCRIPT_DIR/uyap-modernizer.jar" ] && cp -f "$SCRIPT_DIR/uyap-modernizer.jar" "$INSTALL_DIR/"
if [ ! -d "$INSTALL_DIR/jdk-14.0.2" ]; then
    if [ -d "/usr/share/UYAPEditor/jdk-14.0.2" ]; then
        ln -sf /usr/share/UYAPEditor/jdk-14.0.2 "$INSTALL_DIR/jdk-14.0.2"
    elif [ -d "$HOME/.local/share/jvm/jdk-14.0.2" ]; then
        ln -sf "$HOME/.local/share/jvm/jdk-14.0.2" "$INSTALL_DIR/jdk-14.0.2"
    else
        echo "OpenJDK 14.0.2 indiriliyor..."
        TMP_JDK=$(mktemp -d)
        curl -fL --progress-bar "https://download.java.net/java/GA/jdk14.0.2/205943a0976c4ed48cb16f1043c5c647/12/GPL/openjdk-14.0.2_linux-x64_bin.tar.gz" | tar -xz -C "$TMP_JDK"
        mv "$TMP_JDK/jdk-14.0.2" "$INSTALL_DIR/"
        rm -rf "$TMP_JDK"
    fi
fi

echo -e "[3/6] E-İmza sürücü ve kütüphane bağlantıları..."
mkdir -p "$HOME/.local/lib"
if [ -f "$HOME/.local/opt/Akia/libakisp11.so" ]; then
    ln -sf "$HOME/.local/opt/Akia/libakisp11.so" "$HOME/.local/lib/libakisp11.so"
elif [ -f "/usr/share/UYAPEditor/libakisp11.so" ]; then
    ln -sf "/usr/share/UYAPEditor/libakisp11.so" "$HOME/.local/lib/libakisp11.so"
fi

# Microsoft Core Fonts (Times New Roman, Arial, Courier New ...): paketteki ORİJİNAL .exe kurulum dosyalarından
# yalnızca bu bilgisayara açılır (lisans: değiştirilmemiş .exe biçiminde dağıtılabilir). UYAP belgeleri ve PDF çıktısı
# Windows'takiyle aynı yazı tipiyle görünür.
ms_fontlari() {
    local kaynak="$1" hedef="$HOME/.local/share/fonts/uyap-msfonts" gecici
    [ -d "$kaynak" ] || return 0
    mkdir -p "$hedef"; gecici=$(mktemp -d)
    for exe in "$kaynak"/*.exe; do
        [ -f "$exe" ] || continue
        if command -v cabextract >/dev/null 2>&1; then cabextract -q -L -d "$gecici" "$exe" >/dev/null 2>&1
        elif command -v bsdtar >/dev/null 2>&1; then bsdtar -xf "$exe" -C "$gecici" >/dev/null 2>&1
        elif command -v 7z >/dev/null 2>&1; then 7z e -y -o"$gecici" "$exe" >/dev/null 2>&1
        else echo "  (uyarı) cabextract / bsdtar / 7z yok: sudo apt install cabextract (ya da dnf install cabextract)"; break; fi
    done
    find "$gecici" -iname '*.ttf' -exec cp -f {} "$hedef/" \; 2>/dev/null
    local n; n=$(ls "$hedef" 2>/dev/null | wc -l)
    if [ "$n" -gt 0 ]; then
        mkdir -p "$INSTALL_DIR/jdk-14.0.2/lib/fonts" 2>/dev/null && cp -f "$hedef"/* "$INSTALL_DIR/jdk-14.0.2/lib/fonts/" 2>/dev/null || true
        command -v fc-cache >/dev/null 2>&1 && fc-cache -f "$hedef" >/dev/null 2>&1 || true
        echo "  Windows yazı tipleri kuruldu ($n dosya): $hedef"
    fi
    rm -rf "$gecici"
}
ms_fontlari "$SCRIPT_DIR/fonts-ms"

echo -e "[4/6] İkonlar kopyalanıyor..."
if [ -d "$SCRIPT_DIR/icons/hicolor" ]; then
    cp -rf "$SCRIPT_DIR/icons/hicolor/"* "$ICONS_DIR/" 2>/dev/null || true
elif [ -d "/usr/share/icons/hicolor" ]; then
    for size in 16x16 32x32 48x48 128x128 256x256; do
        mkdir -p "$ICONS_DIR/$size/apps" "$ICONS_DIR/$size/mimetypes"
        cp -f /usr/share/icons/hicolor/$size/apps/uyap-editor.png "$ICONS_DIR/$size/apps/" 2>/dev/null || true
        cp -f /usr/share/icons/hicolor/$size/mimetypes/application-*.png "$ICONS_DIR/$size/mimetypes/" 2>/dev/null || true
    done
fi

for size in 16x16 32x32 48x48 128x128 256x256; do
    mkdir -p "$ICONS_DIR/$size/apps" "$ICONS_DIR/$size/mimetypes"
    [ -f "$ICONS_DIR/$size/mimetypes/application-udf.png" ] && cp -f "$ICONS_DIR/$size/mimetypes/application-udf.png" "$ICONS_DIR/$size/apps/uyap-dokuman.png" 2>/dev/null || true
    [ -f "$ICONS_DIR/$size/mimetypes/application-usf.png" ] && cp -f "$ICONS_DIR/$size/mimetypes/application-usf.png" "$ICONS_DIR/$size/apps/uyap-sablon.png" 2>/dev/null || true
done
gtk-update-icon-cache -f -t "$ICONS_DIR" 2>/dev/null || true

echo -e "[5/6] Masaüstü kısayolları ve MIME ilişkilendirmeleri..."
cp -f "$SCRIPT_DIR/desktop/"*.desktop "$DESKTOP_DIR/" 2>/dev/null || true
cp -f "$SCRIPT_DIR/desktop/"*.xml "$MIME_DIR/packages/" 2>/dev/null || true

# GNOME / KDE dock ve uygulama yöneticisi için ek takma ad symlink'leri
ln -sf "$DESKTOP_DIR/dokuman.desktop" "$DESKTOP_DIR/uyap-dokuman.desktop"
ln -sf "$DESKTOP_DIR/sablon.desktop" "$DESKTOP_DIR/uyap-sablon.desktop"

update-mime-database "$MIME_DIR" 2>/dev/null || true
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

# Öntanımlı dosya açıcıları ayarla (.udf -> dokuman, .usf -> sablon)
xdg-mime default dokuman.desktop application/udf 2>/dev/null || true
xdg-mime default dokuman.desktop application/x-udf 2>/dev/null || true
xdg-mime default sablon.desktop application/usf 2>/dev/null || true
xdg-mime default sablon.desktop application/x-usf 2>/dev/null || true

echo -e "[6/6] Yapılandırma dosyaları..."
mkdir -p "$HOME/.uki"
[ ! -f "$HOME/.uki/modernizer.properties" ] && cp -f "$CONF_DIR/modernizer.properties" "$HOME/.uki/"
[ ! -f "$HOME/.uki/uyap.conf" ] && cp -f "$CONF_DIR/uyap.conf" "$HOME/.uki/"

# UYAP'ın eski Linux font arama yolu için sembolik bağlantı (yazma izni varsa)
if [ -w "/usr/share/fonts" ] && [ ! -e "/usr/share/fonts/allFonts" ]; then
    ln -sf /usr/share/fonts /usr/share/fonts/allFonts 2>/dev/null || true
fi

echo -e "${GREEN}✓ Kurulum başarıyla tamamlandı!${NC}"
echo -e "Çalıştırmak için: ${BLUE}uyap-dokuman${NC} veya ${BLUE}uyap-sablon${NC}"
