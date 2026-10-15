#!/data/data/com.termux/files/usr/bin/bash
# ==========================================================
# UdeMobileServer (Mobil İmza & Çoklu İmza Birleştirici)
# Port: 5976
# ==========================================================
PIDFILE="$HOME/eimza/udemobile.pid"
LOGFILE="$HOME/eimza/udemobile.log"
CP="$HOME/jars/editor_utility.jar:$HOME/jars/editor_lib.jar:$HOME/jars/editor_lib2.jar:$HOME/eimza"

is_running() {
    curl -s --connect-timeout 1 http://127.0.0.1:5976/health | grep -q "UdeMobileServer"
}

start_server() {
    if is_running; then
        echo "[UdeMobileServer] Zaten çalışıyor (Port 5976)."
        return 0
    fi
    echo "[UdeMobileServer] Başlatılıyor..."
    nohup java -cp "$CP" com.ckz.udemobile.UdeMobileServer < /dev/null >> "$LOGFILE" 2>&1 &
    PID=$!
    echo $PID > "$PIDFILE"
    disown $PID 2>/dev/null
    for i in {1..12}; do
        sleep 0.5
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
        kill $(cat "$PIDFILE") 2>/dev/null
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
            echo "AKTİF (127.0.0.1:5976)"
        else
            echo "KAPALI"
        fi
        ;;
    *)
        echo "Kullanım: $0 {start|stop|restart|ensure|status}"
        exit 1
        ;;
esac
