#!/bin/bash
# ==============================================================================
# UYAP Doküman Editörü - Modern Linux Başlatıcı
# Geliştirici: Can Kızılyar (github.com/cnkzlyr)
# ==============================================================================

# Gerçek betik yolunu ve dizinini symlink'leri izleyerek çöz
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
    DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
    SOURCE="$(readlink "$SOURCE")"
    [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"

# UYAP kütüphaneleri ana dizin tespiti
if [ -f "$SCRIPT_DIR/editor_lib.jar" ]; then
    BASE_DIR="$SCRIPT_DIR"
elif [ -f "$SCRIPT_DIR/../editor_lib.jar" ]; then
    BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
elif [ -f "$HOME/.local/share/uyap-editor-modern/editor_lib.jar" ]; then
    BASE_DIR="$HOME/.local/share/uyap-editor-modern"
elif [ -f "/usr/share/UYAPEditor/editor_lib.jar" ]; then
    BASE_DIR="/usr/share/UYAPEditor"
else
    BASE_DIR="$SCRIPT_DIR"
fi

# Modernizer JAR tespiti
MODERNIZER_JAR=""
if [ -f "$BASE_DIR/uyap-modernizer.jar" ]; then
    MODERNIZER_JAR="$BASE_DIR/uyap-modernizer.jar"
elif [ -f "$HOME/.local/share/uyap-editor-modern/uyap-modernizer.jar" ]; then
    MODERNIZER_JAR="$HOME/.local/share/uyap-editor-modern/uyap-modernizer.jar"
elif [ -f "/usr/share/UYAPEditor/uyap-modernizer.jar" ]; then
    MODERNIZER_JAR="/usr/share/UYAPEditor/uyap-modernizer.jar"
elif [ -f "$SCRIPT_DIR/../../dist/uyap-modernizer.jar" ]; then
    MODERNIZER_JAR="$(cd "$SCRIPT_DIR/../../dist" && pwd)/uyap-modernizer.jar"
fi

# Kullanıcı yapılandırması
[ -f "$HOME/.uki/uyap.conf" ] && . "$HOME/.uki/uyap.conf"

# Java 14.0.2 Arama Önceliği
if [ -x "$BASE_DIR/jdk-14.0.2/bin/java" ]; then
    JAVA_CMD="$BASE_DIR/jdk-14.0.2/bin/java"
elif [ -x "$HOME/.local/share/uyap-editor-modern/jdk-14.0.2/bin/java" ]; then
    JAVA_CMD="$HOME/.local/share/uyap-editor-modern/jdk-14.0.2/bin/java"
elif [ -x "/usr/share/UYAPEditor/jdk-14.0.2/bin/java" ]; then
    JAVA_CMD="/usr/share/UYAPEditor/jdk-14.0.2/bin/java"
elif [ -x "$HOME/.local/share/jvm/jdk-14.0.2/bin/java" ]; then
    JAVA_CMD="$HOME/.local/share/jvm/jdk-14.0.2/bin/java"
elif [ -n "$JAVA_HOME" ] && [ -x "$JAVA_HOME/bin/java" ]; then
    JAVA_CMD="$JAVA_HOME/bin/java"
else
    JAVA_CMD="java"
fi

# Classpath Oluşturma
CP_PATH="$BASE_DIR/."
if [ -n "$MODERNIZER_JAR" ]; then
    CP_PATH="$MODERNIZER_JAR:$CP_PATH"
fi
for jar in "$BASE_DIR"/*.jar; do
    if [ "$jar" != "$BASE_DIR/*.jar" ] && [ "$jar" != "$MODERNIZER_JAR" ]; then
        CP_PATH="$CP_PATH:$jar"
    fi
done

# PC/SC Kütüphanesi Tespiti (Fedora, Debian, Ubuntu, Pardus, Arch)
PCSC_LIB=""
for lib in /usr/lib64/libpcsclite.so.1 /usr/lib/x86_64-linux-gnu/libpcsclite.so.1 /usr/lib/libpcsclite.so.1 /lib64/libpcsclite.so.1 /usr/lib64/libpcsclite.so; do
    if [ -f "$lib" ]; then
        PCSC_LIB="$lib"
        break
    fi
done

# E-İmza & Akıllı Kart Yolları (AKİS / ArkSigner / ACR39U)
export LD_LIBRARY_PATH="$HOME/.local/lib:$BASE_DIR:$BASE_DIR/jdk-14.0.2/lib:/usr/lib64:/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
PKCS11_OPTS="-Djava.library.path=$HOME/.local/lib:$BASE_DIR:$BASE_DIR/jdk-14.0.2/lib:/usr/lib64:/usr/lib/x86_64-linux-gnu:/usr/lib"
[ -n "$PCSC_LIB" ] && PKCS11_OPTS="-Dsun.security.smartcardio.library=$PCSC_LIB $PKCS11_OPTS"

# PDF Font Optimizasyonu (UYAP'ın iText motorunun sistem fontlarını doğrudan bulması için)
if [ -z "$windir" ]; then
    if [ -d "/usr/local/share/fonts" ]; then
        export windir="/usr/local/share"
    elif [ -d "/usr/share/fonts" ]; then
        export windir="/usr/share"
    fi
fi

# UI & Performans Ayarları
if [ -n "$UYAP_SCALE" ] && [ "$UYAP_SCALE" != "auto" ]; then
    SCALE_OPTS="-Dsun.java2d.uiScale=$UYAP_SCALE"
else
    # Wayland / Xwayland oturumunda GNOME pencereyi 200% ölçekte zaten kendisi 2x büyütür.
    # Java'ya da uiScale=2 verilirse çift ölçekleme (4x) oluşup butonlar devasa hale gelir.
    # Bu yüzden Wayland altında Java ölçeği 1.0 olarak tutulur, X11'de ise otomatik bırakılır.
    if [ "$XDG_SESSION_TYPE" = "wayland" ]; then
        SCALE_OPTS="-Dsun.java2d.uiScale=1.0"
    else
        SCALE_OPTS="-Dsun.java2d.uiScale.enabled=true"
    fi
fi

# Font ve Kenar Yumuşatma Ayarları (Sistem/GNOME font ayarlarıyla eşitle)
AA_SETTING="on"
GNOME_AA="$(gsettings get org.gnome.desktop.interface font-antialiasing 2>/dev/null | tr -d "'")"
if [ "$GNOME_AA" = "rgba" ]; then
    AA_SETTING="lcd"
elif [ "$GNOME_AA" = "grayscale" ]; then
    AA_SETTING="on"
elif [ "$GNOME_AA" = "none" ]; then
    AA_SETTING="off"
fi

FONT_OPTS="-Dawt.useSystemAAFontSettings=$AA_SETTING -Dswing.aatext=true -Dsun.java2d.renderer=sun.java2d.marlin.MarlinRenderingEngine"
ACCEL_OPTS="-Dsun.java2d.xrender=false"
GC_OPTS="-XX:+UseG1GC -XX:+UseStringDeduplication"
MEM_OPTS="-Xms${UYAP_XMS:-256m} -Xmx${UYAP_XMX:-1024m}"

if [ -n "$MODERNIZER_JAR" ]; then
    AGENT_OPTS="-javaagent:$MODERNIZER_JAR=dokuman"
else
    AGENT_OPTS=""
fi

WM_OPTS="-Dawt.app.class.name=uyap-dokuman"

ALL_OPTS="$PKCS11_OPTS $MEM_OPTS $GC_OPTS $SCALE_OPTS $FONT_OPTS $ACCEL_OPTS $WM_OPTS $AGENT_OPTS"

# Argüman temizleme: file:// önekini kaldır, URL çözümle (%20 vb.), mutlak yola çevir
CLEAN_ARGS=()
for raw_arg in "$@"; do
    [ -z "$raw_arg" ] && continue
    arg="$raw_arg"
    arg="${arg#\"}"
    arg="${arg%\"}"
    arg="${arg#\'}"
    arg="${arg%\'}"
    if [[ "$arg" =~ ^file:// ]]; then
        arg="${arg#file://}"
        if command -v python3 >/dev/null 2>&1; then
            arg="$(python3 -c 'import sys, urllib.parse; print(urllib.parse.unquote(sys.argv[1]))' "$arg" 2>/dev/null || echo "$arg")"
        fi
    fi
    if [ -e "$arg" ]; then
        arg="$(readlink -f "$arg" 2>/dev/null || realpath "$arg" 2>/dev/null || echo "$arg")"
    fi
    CLEAN_ARGS+=("$arg")
done

if [ ${#CLEAN_ARGS[@]} -eq 0 ]; then
    exec "$JAVA_CMD" $ALL_OPTS -cp "$CP_PATH" tr.com.havelsan.uyap.system.editor.common.WPAppManager "getNewWPInstance" "EDITOR_TYPE_DOCUMENT"
else
    if [ ${#CLEAN_ARGS[@]} -gt 1 ]; then
        for extra in "${CLEAN_ARGS[@]:1}"; do
            "$0" "$extra" &
        done
    fi
    TARGET_FILE="${CLEAN_ARGS[0]}"
    if [[ "$TARGET_FILE" =~ \.(usf|USF)$ ]]; then
        EDITOR_TYPE="EDITOR_TYPE_TEMPLATE"
    else
        EDITOR_TYPE="EDITOR_TYPE_DOCUMENT"
    fi
    exec "$JAVA_CMD" $ALL_OPTS -cp "$CP_PATH" tr.com.havelsan.uyap.system.editor.common.WPAppManager "getNewWPInstance" "$EDITOR_TYPE" "$TARGET_FILE"
fi
