#!/data/data/com.termux/files/usr/bin/bash
# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
# Adalet E-Imza uygulamasini (127.0.0.1:5975) baslatir/durdurur. Kart erisimi e-imza koprusu uzerinden yapilir.
#   bash ~/eimza/adalet_baslat.sh [start|stop|durum|restart] [--sessiz] [--ekran]
# --ekran: uygulama gorunmez (Xvfb) ekranda calisiyorsa ve gercek X11 ekrani (XFCE) acildiysa oraya tasir.
DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "$DIR/marka.sh" ] && . "$DIR/marka.sh"
STATE="${EIMZA_DIR:-$HOME/.eimza}"
APPDIR="$DIR/adalet"
JAR="$APPDIR/eimza-tray.jar"
AGENT="$DIR/eimza-agent.jar"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
X11_DIR="${X11_DIR:-$PREFIX/tmp/.X11-unix}"
J21="${EIMZA_JAVA21:-$PREFIX/lib/jvm/java-21-openjdk/bin/java}"
PIDF="$STATE/adalet.pid"; DISPF="$STATE/adalet.display"; LOG="$STATE/adalet.log"; XPID="$STATE/xvfb.pid"
PORT="${EIMZA_TRAY_PORT:-5975}"
mkdir -p "$STATE"; chmod 700 "$STATE" 2>/dev/null

CMD="start"; SESSIZ=0; EKRAN=0
for a in "$@"; do
  case "$a" in
    start|stop|durum|restart) CMD="$a" ;;
    --sessiz) SESSIZ=1 ;;
    --ekran) EKRAN=1 ;;
  esac
done
say() { [ "$SESSIZ" = "1" ] || echo "$@" >&2; }

pid_alive() { [ -n "$1" ] && kill -0 "$1" 2>/dev/null; }
tray_pid() { [ -f "$PIDF" ] && p=$(cat "$PIDF") && pid_alive "$p" && echo "$p"; }
port_open() { python3 - "$PORT" <<'PY'
import socket,sys
s=socket.socket(); s.settimeout(1)
try:
    s.connect(("127.0.0.1",int(sys.argv[1]))); sys.exit(0)
except Exception:
    sys.exit(1)
PY
}
x_alive() { python3 - "$1" "$X11_DIR" <<'PY'
import socket,sys,os
s=socket.socket(socket.AF_UNIX); s.settimeout(1)
try:
    s.connect(os.path.join(sys.argv[2],"X"+sys.argv[1])); sys.exit(0)
except Exception:
    sys.exit(1)
PY
}

choose_display() {
  if [ -n "$EIMZA_DISPLAY" ]; then echo "$EIMZA_DISPLAY"; return 0; fi
  if [ -n "$DISPLAY" ]; then n="${DISPLAY#:}"; n="${n%%.*}"; x_alive "$n" && { echo ":$n"; return 0; }; fi
  x_alive 0 && { echo ":0"; return 0; }
  if command -v Xvfb >/dev/null 2>&1; then
    if ! x_alive 99; then
      say "Gorunmez X ekrani (Xvfb :99) baslatiliyor ..."
      nohup Xvfb :99 -screen 0 1024x768x24 -nolisten tcp -ac >>"$LOG" 2>&1 &
      echo $! > "$XPID"
      for _ in $(seq 1 20); do x_alive 99 && break; sleep 0.3; done
    fi
    x_alive 99 && { echo ":99"; return 0; }
  fi
  return 1
}

do_stop() {
  p=$(tray_pid) && { kill "$p" 2>/dev/null; for _ in 1 2 3 4 5 6 7 8; do pid_alive "$p" || break; sleep 0.5; done; pid_alive "$p" && kill -9 "$p" 2>/dev/null; }
  rm -f "$PIDF" "$DISPF"
}

do_status() {
  if p=$(tray_pid); then
    if port_open; then echo "Adalet E-Imza CALISIYOR (pid $p, ekran $(cat "$DISPF" 2>/dev/null), 127.0.0.1:$PORT)"; return 0; fi
    echo "Adalet E-Imza baslatiliyor/yanit yok (pid $p). Gunluk: $LOG"; return 1
  fi
  echo "Adalet E-Imza CALISMIYOR"; return 1
}

case "$CMD" in
  stop) do_stop; echo "Adalet E-Imza durduruldu."; exit 0 ;;
  durum) do_status; exit $? ;;
  restart) do_stop ;;
esac

# ---- start ----
[ -f "$JAR" ] || { say "Adalet E-Imza kurulu degil: bash ~/eimza/adalet_kur.sh"; exit 2; }
[ -x "$J21" ] || { say "Java 21 yok: bash ~/eimza/adalet_kur.sh (pkg install openjdk-21 openjdk-21-x)"; exit 2; }
[ -f "$AGENT" ] || { say "eimza-agent.jar eksik"; exit 2; }

if tray_pid >/dev/null; then
  cur=$(cat "$DISPF" 2>/dev/null)
  if [ "$EKRAN" = "1" ] && [ "$cur" = ":99" ] && x_alive 0; then
    say "Gercek ekran (:0) acildi: uygulama oraya tasiniyor ..."; do_stop
  else
    say "Adalet E-Imza zaten calisiyor."; exit 0
  fi
fi
# port baska bir surec tarafindan tutuluyorsa (or. eski kopya) ikinci kopya acma
if port_open; then say "Port $PORT zaten kullanimda (uygulama baska bir surecte calisiyor)."; exit 0; fi

DSP=$(choose_display) || { say "X ekrani yok: XFCE/Termux:X11'i acin ya da 'pkg install xorg-server-xvfb'"; exit 3; }
[ -f "$LOG" ] && [ "$(wc -c < "$LOG")" -gt 5000000 ] && : > "$LOG"
TMPD="${TMPDIR:-$PREFIX/tmp}"

type ckz_satir >/dev/null 2>&1 && [ "$SESSIZ" != "1" ] && ckz_satir
say "Adalet E-Imza baslatiliyor (ekran $DSP) ..."
DISPLAY="$DSP" \
EIMZA_DIR="$STATE" \
JAVA_TOOL_OPTIONS="-javaagent:$AGENT -Deimza.dir=$STATE" \
nohup "$J21" -Xms64m -Xmx512m -XX:+UseSerialGC -Djava.awt.headless=false -Dfile.encoding=UTF-8 \
  -Djava.io.tmpdir="$TMPD" \
  --add-opens=java.smartcardio/sun.security.smartcardio=ALL-UNNAMED \
  --add-exports=jdk.crypto.cryptoki/sun.security.pkcs11.wrapper=ALL-UNNAMED \
  -jar "$JAR" >>"$LOG" 2>&1 &
echo $! > "$PIDF"; echo "$DSP" > "$DISPF"

if [ "$SESSIZ" = "1" ]; then exit 0; fi
for _ in $(seq 1 120); do
  port_open && { echo "Hazir: http://127.0.0.1:$PORT  (tarayicidan UYAP Avukat Portal -> e-imza ile giris)"; exit 0; }
  tray_pid >/dev/null || { echo "Uygulama kapandi. Gunluk: tail -30 $LOG"; exit 1; }
  sleep 1
done
echo "Zaman asimi: gunluk: $LOG"; exit 1
