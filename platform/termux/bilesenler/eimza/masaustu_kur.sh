#!/data/data/com.termux/files/usr/bin/bash
# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
# UYAP Editor'u XFCE'de "uygulama" yapar: baslat menusu + masaustu simgesi + .udf/.usf dosyalarina cift tikla.
# Cift tiklanan dosya editorde ACILIR (bos pencere acilmaz); editor zaten aciksa belge onda acilir.
DIR="$(cd "$(dirname "$0")" && pwd)"
[ -f "$DIR/marka.sh" ] && . "$DIR/marka.sh"
HOME_DIR="${HOME}"
UE="${UYAP_UE_PY:-$HOME_DIR/ue.py}"
BIN="$HOME_DIR/.local/bin"
APPS="${XDG_DATA_HOME:-$HOME_DIR/.local/share}/applications"
MIMEDIR="${XDG_DATA_HOME:-$HOME_DIR/.local/share}/mime"
ICONDIR="${XDG_DATA_HOME:-$HOME_DIR/.local/share}/icons/hicolor/256x256/apps"
DESK="${XDG_DESKTOP_DIR:-$HOME_DIR/Desktop}"
[ -f "$UE" ] || { echo "ue.py bulunamadi: $UE"; exit 1; }
mkdir -p "$BIN" "$APPS" "$MIMEDIR/packages" "$ICONDIR" "$HOME_DIR/.uyap-editor"

# ---- simge: kullanicinin kendi editor JAR'indan ----
ICON="$ICONDIR/uyap-editor.png"
JARLIB="$(dirname "$UE")/jars/editor_lib.jar"
if [ -f "$JARLIB" ]; then unzip -p "$JARLIB" resources/ude2.png > "$ICON" 2>/dev/null; fi
[ -s "$ICON" ] || rm -f "$ICON"
[ -f "$ICON" ] && ICONREF="$ICON" || ICONREF="text-x-generic"

# ---- calistirici: ~/.local/bin/uyap-editor ----
cat > "$BIN/uyap-editor" <<WRAP
#!/data/data/com.termux/files/usr/bin/bash
# UYAP Doküman Editörü baslaticisi (dosya argumanlari: .udf/.usf yollari)
export DISPLAY="\${DISPLAY:-:0}"
mkdir -p "$HOME_DIR/.uyap-editor"
# e-imza koprusu + Adalet E-Imza arka planda hazir olsun (zaten calisiyorsa dokunmaz)
( nohup bash "$DIR/otobaslat.sh" >/dev/null 2>&1 & )
exec python3 "$UE" "\$@" >> "$HOME_DIR/.uyap-editor/editor.log" 2>&1
WRAP
chmod +x "$BIN/uyap-editor"
[ -d "${PREFIX:-/nonexistent}/bin" ] && ln -sf "$BIN/uyap-editor" "$PREFIX/bin/uyap-editor" 2>/dev/null

# ---- uyap komutu (menü, durum, ayarlar, panel ...) ----
if [ -f "$DIR/../uyap" ] || [ -f "$HOME_DIR/.ckz-kurulum/bilesenler/uyap" ]; then
  src="$DIR/../uyap"; [ -f "$src" ] || src="$HOME_DIR/.ckz-kurulum/bilesenler/uyap"
  cp -f "$src" "$BIN/uyap.yeni" && chmod +x "$BIN/uyap.yeni" && mv -f "$BIN/uyap.yeni" "$BIN/uyap"
  [ -d "${PREFIX:-/nonexistent}/bin" ] && ln -sf "$BIN/uyap" "$PREFIX/bin/uyap" 2>/dev/null
fi

# ---- uyap-hakkinda: telif bildirimi + muhur dogrulamasi ----
cat > "$BIN/uyap-hakkinda" <<HAK
#!/data/data/com.termux/files/usr/bin/bash
. "$DIR/marka.sh" 2>/dev/null && ckz_banner
if [ -f "$DIR/../.ckz-kurulum/tools/dogrula.py" ]; then python3 "$DIR/../.ckz-kurulum/tools/dogrula.py" "$DIR/../.ckz-kurulum" --kurulu; else echo "(muhur dogrulamasi icin kurulum klasoru bulunamadi)"; fi
[ -f "\$HOME/.ckz-durum/ONAYSIZ" ] && echo "!!! ONAYSIZ KURULUM: \$(cat "\$HOME/.ckz-durum/ONAYSIZ")"
[ -f "\$HOME/.ckz-durum/KURULUM.txt" ] && cat "\$HOME/.ckz-durum/KURULUM.txt"
HAK
chmod +x "$BIN/uyap-hakkinda"

# ---- MIME: .udf ve .usf ----
cat > "$MIMEDIR/packages/uyap-belge.xml" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-uyap-udf">
    <comment>UYAP Doküman (UDF)</comment>
    <comment xml:lang="tr">UYAP Doküman (UDF)</comment>
    <glob pattern="*.udf" weight="60"/>
    <icon name="uyap-editor"/>
  </mime-type>
  <mime-type type="application/x-uyap-usf">
    <comment>UYAP Belge (USF)</comment>
    <comment xml:lang="tr">UYAP Belge (USF)</comment>
    <glob pattern="*.usf" weight="60"/>
    <icon name="uyap-editor"/>
  </mime-type>
</mime-info>
XML
command -v update-mime-database >/dev/null 2>&1 && update-mime-database "$MIMEDIR" >/dev/null 2>&1 \
  || echo "(uyari) update-mime-database yok: pkg install shared-mime-info"

# ---- .desktop ----
DESKTOP="$APPS/uyap-editor.desktop"
cat > "$DESKTOP" <<EOT
[Desktop Entry]
Version=1.0
Type=Application
Name=UYAP Editör
GenericName=UYAP Doküman Editörü
Comment=UDF / USF belgelerini aç, düzenle ve e-imzala — © Av. Can KIZILYAR (resmî değildir)
Exec=$BIN/uyap-editor %F
Icon=$ICONREF
Terminal=false
Categories=Office;WordProcessor;
MimeType=application/x-uyap-udf;application/x-uyap-usf;
StartupNotify=false
StartupWMClass=uyap-editor
Keywords=uyap;udf;usf;editör;e-imza;
Actions=yeni;panel;

[Desktop Action yeni]
Name=Yeni belge
Exec=$BIN/uyap-editor

[Desktop Action panel]
Name=Kontrol Merkezi
Exec=$BIN/uyap panel
EOT
chmod +x "$DESKTOP"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" >/dev/null 2>&1

# ---- Kontrol Merkezi ----
cat > "$APPS/uyap-kontrol.desktop" <<EOT
[Desktop Entry]
Version=1.0
Type=Application
Name=UYAP Kontrol Merkezi
Comment=Editör, e-imza okuyucu ve Adalet E-İmza durumu; ayarlar
Exec=$BIN/uyap panel
Icon=$ICONREF
Terminal=false
Categories=Office;Settings;
StartupWMClass=uyaptermux-KontrolMerkezi
EOT
chmod +x "$APPS/uyap-kontrol.desktop"

# ---- fluxbox menusu (hafif masaustu) ----
if [ -d "$HOME_DIR/.fluxbox" ] || command -v fluxbox >/dev/null 2>&1; then
  mkdir -p "$HOME_DIR/.fluxbox"
  cat > "$HOME_DIR/.fluxbox/menu" <<EOT
[begin] (UYAP-Termux)
[encoding] {UTF-8}
  [exec] (UYAP Editör) {$BIN/uyap-editor}
  [exec] (Kontrol Merkezi) {$BIN/uyap panel}
  [exec] (Adalet E-İmza yeniden başlat) {bash $DIR/adalet_baslat.sh restart --ekran}
  [separator]
  [exec] (Terminal) {xterm}
  [exec] (Dosyalar) {thunar}
  [separator]
  [submenu] (Fluxbox)
    [config] (Ayarlar)
    [reconfig] (Yeniden yükle)
    [restart] (Yeniden başlat)
    [exit] (Çıkış)
  [end]
[endencoding]
[end]
EOT
fi

# ---- Adalet E-Imza baslat/durdur kisayolu (kuruluysa) ----
if [ -f "$DIR/adalet/eimza-tray.jar" ]; then
  AIC="$DIR/adalet/icon.png"; [ -f "$AIC" ] || AIC="$ICONREF"
  cat > "$APPS/adalet-eimza.desktop" <<EOT
[Desktop Entry]
Version=1.0
Type=Application
Name=Adalet E-İmza (başlat)
Comment=Tarayıcıdan UYAP Avukat Portal e-imza girişi için yerel servis (127.0.0.1:5975)
Exec=bash $DIR/adalet_baslat.sh restart --ekran
Icon=$AIC
Terminal=false
Categories=Utility;
EOT
  chmod +x "$APPS/adalet-eimza.desktop"
fi

# ---- varsayilan uygulama ----
if command -v xdg-mime >/dev/null 2>&1; then
  xdg-mime default uyap-editor.desktop application/x-uyap-udf application/x-uyap-usf 2>/dev/null
fi
ML="${XDG_CONFIG_HOME:-$HOME_DIR/.config}/mimeapps.list"
mkdir -p "$(dirname "$ML")"; touch "$ML"
grep -q '^\[Default Applications\]' "$ML" || printf '[Default Applications]\n' >> "$ML"
for t in application/x-uyap-udf application/x-uyap-usf; do
  if grep -q "^$t=" "$ML"; then sed -i "s|^$t=.*|$t=uyap-editor.desktop;|" "$ML"
  else sed -i "/^\[Default Applications\]/a $t=uyap-editor.desktop;" "$ML"; fi
done

# ---- masaustu simgesi (cift tiklanabilir) ----
if [ -d "$DESK" ] || mkdir -p "$DESK" 2>/dev/null; then
  cp "$DESKTOP" "$DESK/UYAP Editör.desktop"; chmod +x "$DESK/UYAP Editör.desktop"
  command -v gio >/dev/null 2>&1 && gio set "$DESK/UYAP Editör.desktop" metadata::trusted true 2>/dev/null
fi
type ckz_satir >/dev/null 2>&1 && ckz_satir
echo "UYAP Editör uygulama olarak kuruldu: menü + masaüstü simgesi + .udf/.usf çift tıklama."
