#!/data/data/com.termux/files/usr/bin/bash
# ==========================================================
# UdeMobileServer (Havelsan UYAP Headless Mobil İmza & Çoklu İmza Birleştirici)
# Port: 5976
# ==========================================================
DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$HOME/eimza/udemobile.pid"
LOGFILE="$HOME/eimza/udemobile.log"
CP="$HOME/jars/*:$HOME/jars:$HOME/eimza"

pid_alive() {
    [ -f "$PIDFILE" ] && p=$(cat "$PIDFILE" 2>/dev/null) && [ -n "$p" ] && kill -0 "$p" 2>/dev/null
}

is_running() {
    curl -s --connect-timeout 1 http://127.0.0.1:5976/health 2>/dev/null | grep -q "UdeMobileServer"
}

start_server() {
    termux-wake-lock 2>/dev/null || true
    if is_running; then
        echo "[UdeMobileServer] Zaten çalışıyor (Port 5976)."
        return 0
    fi
    echo "[UdeMobileServer] Başlatılıyor (Havelsan UYAP Headless)..."
    setsid nohup java -Djava.awt.headless=true -Xms32m -Xmx256m -XX:+UseSerialGC -Dfile.encoding=UTF-8 -cp "$CP" com.ckz.udemobile.UdeMobileServer >> "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    for i in {1..20}; do
        sleep 0.3
        if is_running; then
            echo "[UdeMobileServer] Başarıyla açıldı (Port 5976)."
            return 0
        fi
    done
    echo "[UdeMobileServer] Başlatma zaman aşımı. Logları kontrol edin: $LOGFILE"
    return 1
}

stop_server() {
    echo "[UdeMobileServer] Durduruluyor..."
    if [ -f "$PIDFILE" ]; then
        kill $(cat "$PIDFILE" 2>/dev/null) 2>/dev/null
        rm -f "$PIDFILE"
    fi
    pkill -f "com.ckz.udemobile.UdeMobileServer" 2>/dev/null
}

case "$1" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        stop_server
        sleep 1
        start_server
        ;;
    ensure)
        if ! is_running; then
            start_server
        fi
        ;;
    status)
        if is_running; then
            echo "AKTİF (0.0.0.0:5976) [Havelsan UYAP Headless]"
        else
            echo "KAPALI"
        fi
        ;;
    *)
        echo "Kullanım: $0 {start|stop|restart|ensure|status}"
        exit 1
        ;;
esac
