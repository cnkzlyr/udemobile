#!/bin/bash
# ==============================================================================
# UYAP Şablon Editörü - Modern macOS Başlatıcı
# Apple Silicon (M1/M2/M3/M4) ve Intel Uyumlu
# ==============================================================================

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
    DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
    SOURCE="$(readlink "$SOURCE")"
    [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"

if [ -f "$SCRIPT_DIR/../Java/editor_lib.jar" ]; then
    BASE_DIR="$(cd "$SCRIPT_DIR/../Java" && pwd)"
elif [ -f "$SCRIPT_DIR/editor_lib.jar" ]; then
    BASE_DIR="$SCRIPT_DIR"
elif [ -f "$SCRIPT_DIR/../editor_lib.jar" ]; then
    BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
elif [ -d "/Applications/UYAP Sablon Editoru.app/Contents/Java" ]; then
    BASE_DIR="/Applications/UYAP Sablon Editoru.app/Contents/Java"
elif [ -d "/Applications/UYAP Dokuman Editoru.app/Contents/Java" ]; then
    BASE_DIR="/Applications/UYAP Dokuman Editoru.app/Contents/Java"
else
    BASE_DIR="$SCRIPT_DIR"
fi

MODERNIZER_JAR=""
if [ -f "$BASE_DIR/uyap-modernizer.jar" ]; then
    MODERNIZER_JAR="$BASE_DIR/uyap-modernizer.jar"
elif [ -f "$SCRIPT_DIR/../Java/uyap-modernizer.jar" ]; then
    MODERNIZER_JAR="$(cd "$SCRIPT_DIR/../Java" && pwd)/uyap-modernizer.jar"
fi

[ -f "$HOME/.uki/uyap.conf" ] && . "$HOME/.uki/uyap.conf"

if [ -x "$BASE_DIR/jdk-14.0.2/bin/java" ]; then
    JAVA_CMD="$BASE_DIR/jdk-14.0.2/bin/java"
elif [ -x "$BASE_DIR/../Home/bin/java" ]; then
    JAVA_CMD="$BASE_DIR/../Home/bin/java"
elif [ -x "$BASE_DIR/Contents/Home/bin/java" ]; then
    JAVA_CMD="$BASE_DIR/Contents/Home/bin/java"
elif [ -n "$JAVA_HOME" ] && [ -x "$JAVA_HOME/bin/java" ]; then
    JAVA_CMD="$JAVA_HOME/bin/java"
else
    JAVA_CMD="java"
fi

CP_PATH="$BASE_DIR/."
if [ -n "$MODERNIZER_JAR" ]; then
    CP_PATH="$MODERNIZER_JAR:$CP_PATH"
fi
for jar in "$BASE_DIR"/*.jar; do
    if [ "$jar" != "$BASE_DIR/*.jar" ] && [ "$jar" != "$MODERNIZER_JAR" ]; then
        CP_PATH="$CP_PATH:$jar"
    fi
done

PKCS11_OPTS="-Djava.library.path=/usr/local/lib:/opt/homebrew/lib:$BASE_DIR"
MAC_OPTS="-Dapple.laf.useScreenMenuBar=true -Dcom.apple.mrj.application.apple.menu.about.name=UYAP_Sablon_Editor -Dapple.awt.application.appearance=system"
FONT_OPTS="-Dawt.useSystemAAFontSettings=on -Dswing.aatext=true"
MEM_OPTS="-Xms256m -Xmx1024m -XX:+UseG1GC -XX:+UseStringDeduplication"

if [ -n "$MODERNIZER_JAR" ]; then
    AGENT_OPTS="-javaagent:$MODERNIZER_JAR"
else
    AGENT_OPTS=""
fi

ALL_OPTS="$PKCS11_OPTS $MAC_OPTS $MEM_OPTS $FONT_OPTS $AGENT_OPTS"

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
    exec "$JAVA_CMD" $ALL_OPTS -cp "$CP_PATH" tr.com.havelsan.uyap.system.editor.common.WPAppManager "getNewWPInstance" "EDITOR_TYPE_TEMPLATE"
else
    TARGET_FILE="${CLEAN_ARGS[0]}"
    if [[ "$TARGET_FILE" =~ \.(udf|UDF)$ ]]; then
        EDITOR_TYPE="EDITOR_TYPE_DOCUMENT"
    else
        EDITOR_TYPE="EDITOR_TYPE_TEMPLATE"
    fi
    exec "$JAVA_CMD" $ALL_OPTS -cp "$CP_PATH" tr.com.havelsan.uyap.system.editor.common.WPAppManager "getNewWPInstance" "$EDITOR_TYPE" "$TARGET_FILE"
fi
