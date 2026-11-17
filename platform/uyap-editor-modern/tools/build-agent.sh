#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build"
SRC_DIR="$ROOT_DIR/core/src"
DIST_DIR="$ROOT_DIR/dist"

echo "[1/4] Temizlik yapılıyor..."
rm -rf "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$BUILD_DIR/classes" "$DIST_DIR"

echo "[2/4] FlatLaf kütüphanesi kontrol ediliyor..."
FLATLAF_JAR="/tmp/flatlaf-3.5.4.jar"
if [ ! -f "$FLATLAF_JAR" ]; then
    curl -sL -o "$FLATLAF_JAR" "https://repo1.maven.org/maven2/com/formdev/flatlaf/3.5.4/flatlaf-3.5.4.jar"
fi

# FlatLaf sınıflarını build klasörüne aç
unzip -q -o "$FLATLAF_JAR" -d "$BUILD_DIR/classes"
rm -rf "$BUILD_DIR/classes/META-INF"
rm -f "$BUILD_DIR/classes/module-info.class"

echo "[3/4] Java kaynak kodları ve kaynak dosyalar hazırlanıyor..."
find "$SRC_DIR" -name "*.java" -not -path "*/tr/gov/tubitak/*" > "$BUILD_DIR/sources.txt"   # ESYA lisans denetimine dokunan sınıflar derlenmez

# İkonları paket içine kopyala (Pencere ve dock için HiDPI ikonlar)
mkdir -p "$BUILD_DIR/classes/icons"
if [ -d "$ROOT_DIR/platforms/linux/icons/hicolor" ]; then
    for size in 16 32 48 128 256; do
        s="${size}x${size}"
        [ -f "$ROOT_DIR/platforms/linux/icons/hicolor/$s/mimetypes/application-udf.png" ] && \
            cp -f "$ROOT_DIR/platforms/linux/icons/hicolor/$s/mimetypes/application-udf.png" "$BUILD_DIR/classes/icons/application-udf-$size.png"
        [ -f "$ROOT_DIR/platforms/linux/icons/hicolor/$s/mimetypes/application-usf.png" ] && \
            cp -f "$ROOT_DIR/platforms/linux/icons/hicolor/$s/mimetypes/application-usf.png" "$BUILD_DIR/classes/icons/application-usf-$size.png"
    done
fi

# Sistemde yüklü olan veya UYAP içindeki javac'ı bul
if [ -x "/usr/share/UYAPEditor/jdk-14.0.2/bin/javac" ]; then
    JAVAC="/usr/share/UYAPEditor/jdk-14.0.2/bin/javac"
    JAR="/usr/share/UYAPEditor/jdk-14.0.2/bin/jar"
elif [ -x "$HOME/.local/share/jvm/jdk-14.0.2/bin/javac" ]; then
    JAVAC="$HOME/.local/share/jvm/jdk-14.0.2/bin/javac"
    JAR="$HOME/.local/share/jvm/jdk-14.0.2/bin/jar"
else
    JAVAC="javac"
    JAR="jar"
fi

"$JAVAC" --release 11 -encoding UTF-8 -cp "$BUILD_DIR/classes:/usr/share/UYAPEditor/*" -d "$BUILD_DIR/classes" @"$BUILD_DIR/sources.txt"

echo "[4/4] uyap-modernizer.jar paketleniyor..."
cat << 'EOF' > "$BUILD_DIR/MANIFEST.MF"
Manifest-Version: 1.0
Premain-Class: tr.gov.uyap.modernizer.ModernizerAgent
Can-Redefine-Classes: true
Can-Retransform-Classes: true
EOF

"$JAR" cfm "$DIST_DIR/uyap-modernizer.jar" "$BUILD_DIR/MANIFEST.MF" -C "$BUILD_DIR/classes" .

echo "Tamamlandı: $DIST_DIR/uyap-modernizer.jar"
ls -lh "$DIST_DIR/uyap-modernizer.jar"
