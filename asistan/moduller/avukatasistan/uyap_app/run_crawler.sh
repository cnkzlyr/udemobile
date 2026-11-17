#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# ⚖️ UYAP AVUKAT PORTALI - FAZ 1 KEŞİF & API HARİTALAMA BAŞLATICI
# ==============================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "========================================================================"
echo "⚖️  UYAP AVUKAT PORTALI - REVERSE ENGINEERING & API CRAWLER"
echo "========================================================================"

export DISPLAY=:0
export TMPDIR="/data/data/com.termux/files/usr/tmp"
export XDG_RUNTIME_DIR="${TMPDIR}"
mkdir -p "$XDG_RUNTIME_DIR"

# 1. E-İmza & Arka plan servislerini kontrol et / tetikle
if [ -f "$HOME/eimza/otobaslat.sh" ]; then
    bash "$HOME/eimza/otobaslat.sh" >/dev/null 2>&1 &
fi

# 2. Termux-X11 sunucusu çalışmıyorsa başlat
X11_SOCKET="${XDG_RUNTIME_DIR}/.X11-unix/X0"
if [ ! -e "$X11_SOCKET" ]; then
    echo "🌐 Termux:X11 (:0) sunucusu başlatılıyor..."
    termux-x11 :0 >/dev/null 2>&1 &
    
    # X11 soketinin oluşmasını bekle (maksimum 3 sn)
    for i in {1..30}; do
        [ -e "$X11_SOCKET" ] && break
        sleep 0.1
    done
fi

# 3. Fluxbox pencere yöneticisi çalışmıyorsa başlat
if ! pgrep -x "fluxbox" >/dev/null 2>&1; then
    echo "🪟 Pencere yöneticisi (fluxbox) başlatılıyor..."
    fluxbox >/dev/null 2>&1 &
    sleep 0.5
fi

# 4. Termux:X11 uygulamasını ön plana getir
echo "📱 Termux:X11 uygulaması ekrana getiriliyor..."
if command -v am >/dev/null 2>&1; then
    am start --user 0 -n com.termux.x11/com.termux.x11.MainActivity >/dev/null 2>&1
    sleep 1
fi

echo "🖥️  DISPLAY=$DISPLAY (Socket: $X11_SOCKET)"
echo "🚀 Keşif motoru başlatılıyor..."
echo ""

python3 "$DIR/crawler.py" "$@"
