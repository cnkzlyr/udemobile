#!/data/data/com.termux/files/usr/bin/bash
# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
# Tek komutla kurulum: bash ~/eimza/kur.sh
#  - Termux her acildiginda e-imza koprusu (+ Adalet E-Imza) otomatik baslar
#  - UYAP Editor: XFCE uygulamasi + .udf/.usf cift tiklama
#  - Adalet E-Imza (deb Download'da ise) kurulur
DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "$DIR/marka.sh" ] && . "$DIR/marka.sh"
HOME_DIR="$HOME"
chmod +x "$DIR"/*.sh "$DIR"/*.py 2>/dev/null

echo "== 1/5 paketler"
pkg install -y python libusb termux-api xdg-utils desktop-file-utils shared-mime-info >/dev/null 2>&1 || echo "(bazi paketler kurulamadi; devam)"
pkg install -y xorg-server-xvfb >/dev/null 2>&1 || echo "(bilgi) xorg-server-xvfb yok: Adalet uygulamasi yalnizca XFCE/X11 aciksa calisir"

echo "== 2/5 Termux acilisinda otomatik baslatma"
BLOCK_BEGIN="# >>> uyap-eimza otobaslat >>>"
BLOCK_END="# <<< uyap-eimza otobaslat <<<"
for rc in "$HOME_DIR/.bashrc" "$HOME_DIR/.profile" "$HOME_DIR/.zshrc"; do
  if [ "$rc" = "$HOME_DIR/.zshrc" ] && ! command -v zsh >/dev/null 2>&1; then continue; fi
  touch "$rc"
  sed -i "/$BLOCK_BEGIN/,/$BLOCK_END/d" "$rc"
  cat >> "$rc" <<HOOK
$BLOCK_BEGIN
if [ -f "$DIR/otobaslat.sh" ] && [ -z "\$UYAP_EIMZA_HOOK" ]; then
  export UYAP_EIMZA_HOOK=1
  ( nohup bash "$DIR/otobaslat.sh" >/dev/null 2>&1 & )
fi
$BLOCK_END
HOOK
done
mkdir -p "$HOME_DIR/.termux/boot"
cat > "$HOME_DIR/.termux/boot/uyap-eimza.sh" <<BOOT
#!/data/data/com.termux/files/usr/bin/bash
# Termux:Boot: telefon acilinca
termux-wake-lock
bash "$DIR/otobaslat.sh"
BOOT
chmod +x "$HOME_DIR/.termux/boot/uyap-eimza.sh"
mkdir -p "$HOME_DIR/.config/autostart"
cat > "$HOME_DIR/.config/autostart/uyap-eimza.desktop" <<AUTO
[Desktop Entry]
Type=Application
Name=UYAP E-İmza otomatik başlat
Exec=bash $DIR/otobaslat.sh --ekran
Terminal=false
X-GNOME-Autostart-enabled=true
AUTO

echo "== 3/5 Adalet E-Imza"
if [ -f "$DIR/adalet/eimza-tray.jar" ]; then echo "(Adalet E-Imza zaten kurulu)"; elif bash "$DIR/adalet_kur.sh"; then :; else echo "(Adalet E-Imza simdilik kurulmadi; deb'i Download'a koyup: bash ~/eimza/adalet_kur.sh)"; fi

echo "== 4/5 UYAP Editor uygulamasi"
bash "$DIR/masaustu_kur.sh"

echo "== 5/5 simdi baslatiliyor"
bash "$DIR/otobaslat.sh"
echo
echo "Hazir. Durum: bash $DIR/adalet_baslat.sh durum ; okuyucu: cat ~/.eimza/izle.log"
