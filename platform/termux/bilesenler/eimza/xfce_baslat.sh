#!/data/data/com.termux/files/usr/bin/bash
# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
# Termux:X11 + XFCE masaustunu baslatir (Termux:X11 uygulamasi otomatik acilir). Kullanim: bash ~/eimza/xfce_baslat.sh
# Hafif masaustu icin: MASAUSTU=fluxbox bash ~/eimza/xfce_baslat.sh
DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "$DIR/marka.sh" ] && . "$DIR/marka.sh" && ckz_satir
kill -9 $(pgrep -f "termux.x11") 2>/dev/null
export XDG_RUNTIME_DIR="${TMPDIR:-$PREFIX/tmp}"
termux-x11 :0 >/dev/null 2>&1 &
sleep 3
am start --user 0 -n com.termux.x11/com.termux.x11.MainActivity >/dev/null 2>&1
sleep 1
export DISPLAY=:0
# Klavye: Termux:X11 tarama kodu modu + Turkce Q duzeni (Ctrl/Alt kisayollari, AltGr). Oturum ayarlarini
# ezebilecegi icin XFCE basladiktan sonra bir kez daha uygulanir. Kapatmak: UYAP_KLAVYE=0
if [ "${UYAP_KLAVYE:-1}" != "0" ] && [ -f "$DIR/klavye.sh" ]; then
  bash "$DIR/klavye.sh" xfce-xml >/dev/null 2>&1
  ( sleep 6; bash "$DIR/klavye.sh" >> "${EIMZA_DIR:-$HOME/.eimza}/klavye.log" 2>&1 ) &
fi
if [ "${MASAUSTU:-xfce}" = "fluxbox" ]; then
  exec fluxbox
else
  exec dbus-launch --exit-with-session xfce4-session
fi
