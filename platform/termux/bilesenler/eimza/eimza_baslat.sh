#!/data/data/com.termux/files/usr/bin/bash
# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
# E-imza okuyucu izleyicisini (ve koprusunu) arka planda baslatir. Okuyucu cikarilip takilinca kendiliginden baglanir.
#   bash ~/eimza/eimza_baslat.sh        -> baslat
#   bash ~/eimza/eimza_baslat.sh stop   -> durdur (karti da kapatir)
#   bash ~/eimza/eimza_baslat.sh ensure -> calismiyorsa baslat, calisiyorsa dokunma (otomatik baslatma icin)
DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "$DIR/marka.sh" ] && . "$DIR/marka.sh"
STATE="${EIMZA_DIR:-$HOME/.eimza}"
mkdir -p "$STATE"; chmod 700 "$STATE"
chmod +x "$DIR/bridge_run.sh" "$DIR/tani_run.sh" "$DIR/ccid_bridge.py" "$DIR/eimza_izle.py" 2>/dev/null

pid_of() { python3 -c "import json,sys
try: print(json.load(open('$1')).get('pid',''))
except Exception: print('')" 2>/dev/null; }

stop_all() {
  if [ -f "$STATE/izle.pid" ]; then kill "$(cat "$STATE/izle.pid")" 2>/dev/null; rm -f "$STATE/izle.pid"; fi
  if [ -f "$STATE/bridge.json" ]; then
    old=$(pid_of "$STATE/bridge.json"); [ -n "$old" ] && kill "$old" 2>/dev/null
    sleep 0.7; rm -f "$STATE/bridge.json"
  fi
}

if [ "$1" = "stop" ]; then stop_all; echo "E-imza izleyicisi ve koprusu durduruldu."; exit 0; fi
if [ "$1" = "ensure" ]; then
  if [ -f "$STATE/izle.pid" ] && kill -0 "$(cat "$STATE/izle.pid")" 2>/dev/null; then exit 0; fi
  ENSURE=1
fi

need() { command -v "$1" >/dev/null 2>&1 || { echo "Eksik: $1   ->  pkg install $2"; exit 1; }; }
need termux-usb termux-api
need python3 python
[ -e "${PREFIX:-/data/data/com.termux/files/usr}/lib/libusb-1.0.so" ] || { echo "Eksik: libusb   ->  pkg install libusb"; exit 1; }

stop_all
termux-wake-lock 2>/dev/null
: > "$STATE/bridge.log"
nohup python3 "$DIR/eimza_izle.py" >> "$STATE/izle.log" 2>&1 &
disown 2>/dev/null

[ "$ENSURE" = "1" ] && exit 0
type ckz_satir >/dev/null 2>&1 && ckz_satir
echo "E-imza izleyicisi basladi. Okuyucuyu takin; Android izin sorarsa 'Izin ver'"
echo "(mumkunse 'varsayilan olarak kullan' kutusunu isaretleyin). Cikarip takarsaniz kendiliginden baglanir."
for _ in $(seq 1 60); do
  if [ -f "$STATE/bridge.json" ]; then echo "Kopru hazir. ($(grep -o 'okuyucu:.*' "$STATE/bridge.log" | head -1))"; exit 0; fi
  sleep 0.5
done
echo "(Henuz okuyucu baglanmadi; izleyici arka planda bekliyor. Durum: cat $STATE/izle.log)"
exit 0
