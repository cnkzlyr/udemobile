#!/usr/bin/env bash
# ==============================================================================
# ⚖️ AVUKAT ASİSTANI - X11 CANLI YÖNETİM PANELİ BAŞLATICI
# ==============================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "========================================================================"
echo "⚖️  AVUKAT ASİSTANI - X11 GRAFİKSEL YÖNETİM ARAYÜZÜ (GUI)"
echo "========================================================================"

# Termux veya Linux Masaüstü ortam kontrolü
IS_TERMUX=false
if [ -d "/data/data/com.termux" ] || [ -n "$TERMUX_VERSION" ]; then
    IS_TERMUX=true
fi

if [ "$IS_TERMUX" = true ]; then
    if [ -z "$DISPLAY" ] || [ "$DISPLAY" = ":99" ]; then
        export DISPLAY=:0
    fi
    if [ ! -e "/data/data/com.termux/files/usr/tmp/.X11-unix/X0" ]; then
        echo "🌐 Termux:X11 ekranı (:0) arka planda başlatılıyor..."
        if command -v termux-x11 >/dev/null 2>&1; then
            termux-x11 :0 >/dev/null 2>&1 &
            sleep 1.5
        fi
    fi
    if command -v am >/dev/null 2>&1; then
        am start --user 0 -n com.termux.x11/com.termux.x11.MainActivity >/dev/null 2>&1 &
    fi
    echo "🖥️  DISPLAY=$DISPLAY"
    echo "🚀 Arayüz açılıyor... (Lütfen Termux:X11 uygulamasını açın)"
else
    # Linux / macOS masaüstü
    if [ -z "$DISPLAY" ] && [ -n "$WAYLAND_DISPLAY" ]; then
        export DISPLAY=:0
    fi
    echo "🖥️  Masaüstü Ekranı: DISPLAY=${DISPLAY:-:0}"
    echo "🚀 Avukat Asistanı Yönetim Masası açılıyor..."
fi

# Sanal ortam varsa sanal ortam python'unu, yoksa python3 kullan
if [ -f "$DIR/.venv/bin/python3" ]; then
    PY_BIN="$DIR/.venv/bin/python3"
else
    PY_BIN="python3"
fi

"$PY_BIN" "$DIR/avukat_gui.py" "$@"
