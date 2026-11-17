#!/data/data/com.termux/files/usr/bin/bash
# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
# Termux her acildiginda cagrilir (kabuk kancasi / Termux:Boot / XFCE otomatik baslat). Idempotenttir:
# zaten calisan bilesenlere dokunmaz. Ortam: EIMZA_OTO=0 (tumunu kapat), EIMZA_TRAY=0 (Adalet uygulamasini kapat)
DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "$DIR/marka.sh" ] && . "$DIR/marka.sh"
STATE="${EIMZA_DIR:-$HOME/.eimza}"
mkdir -p "$STATE"; chmod 700 "$STATE" 2>/dev/null
[ "${EIMZA_OTO:-1}" = "0" ] && exit 0
LCK="$STATE/otobaslat.lck"
if ! mkdir "$LCK" 2>/dev/null; then
  # 3 dakikadan eski kilit = onceki calisma olmus; temizle
  if [ -n "$(find "$LCK" -maxdepth 0 -mmin +3 2>/dev/null)" ]; then rm -rf "$LCK"; mkdir "$LCK" 2>/dev/null || exit 0; else exit 0; fi
fi
trap 'rm -rf "$LCK"' EXIT
{ type ckz_satir >/dev/null 2>&1 && ckz_satir; } >> "$STATE/otobaslat.log" 2>/dev/null
EK=""; for a in "$@"; do [ "$a" = "--ekran" ] && EK="--ekran"; done

# 1) e-imza okuyucu izleyicisi (USB okuyucu takilinca/cikarilinca kendiliginden baglanir)
bash "$DIR/eimza_baslat.sh" ensure >/dev/null 2>&1
# 2) Adalet E-Imza uygulamasi (yalnizca kuruluysa)
if [ "${EIMZA_TRAY:-1}" != "0" ] && [ -f "$DIR/adalet/eimza-tray.jar" ]; then
  bash "$DIR/adalet_baslat.sh" start --sessiz $EK >/dev/null 2>&1
fi
exit 0
