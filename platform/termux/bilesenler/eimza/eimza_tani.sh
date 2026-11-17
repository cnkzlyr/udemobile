#!/data/data/com.termux/files/usr/bin/bash
# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
# Tani: takili her USB cihazin CCID/kart bilgisini toplar, ~/.eimza/tani.txt'ye yazar ve panoya kopyalar.
#   1) izleyiciyi durdurur   2) okuyucuyu (ArkSigner vb.) takili tutun   3) bash ~/eimza/eimza_tani.sh
DIR="$(cd "$(dirname "$0")" && pwd)"
STATE="${EIMZA_DIR:-$HOME/.eimza}"
mkdir -p "$STATE"
chmod +x "$DIR/tani_run.sh" 2>/dev/null
bash "$DIR/eimza_baslat.sh" stop >/dev/null 2>&1
OUT="$STATE/tani.txt"
{
  echo "eimza tani $(date '+%F %T')  paket=0.2"
  echo "java: $(java -version 2>&1 | head -1)"
  echo "cihazlar: $(termux-usb -l 2>&1)"
  for d in $(termux-usb -l 2>/dev/null | python3 -c "import sys,json
try:
    print(' '.join(json.load(sys.stdin)))
except Exception:
    pass"); do
    echo; echo "##### $d"
    timeout 40 termux-usb -r -e "$DIR/tani_run.sh" "$d" 2>&1
  done
} > "$OUT" 2>&1
cat "$OUT"
termux-clipboard-set < "$OUT" 2>/dev/null && echo && echo ">> Yukaridaki metin panoya kopyalandi: sohbete yapistirin."
