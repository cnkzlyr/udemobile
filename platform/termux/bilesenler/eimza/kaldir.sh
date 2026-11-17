#!/data/data/com.termux/files/usr/bin/bash
# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
# Otomatik baslatmayi ve masaustu tumlesmesini geri alir (dosyalari silmez).
DIR="$(cd "$(dirname "$0")" && pwd)"
for rc in "$HOME/.bashrc" "$HOME/.profile" "$HOME/.zshrc"; do
  [ -f "$rc" ] && sed -i '/# >>> uyap-eimza otobaslat >>>/,/# <<< uyap-eimza otobaslat <<</d' "$rc"
done
rm -f "$HOME/.termux/boot/uyap-eimza.sh" "$HOME/.config/autostart/uyap-eimza.desktop"
rm -f "$HOME/.local/share/applications/uyap-editor.desktop" "$HOME/.local/share/applications/adalet-eimza.desktop" \
      "$HOME/.local/share/mime/packages/uyap-belge.xml" "$HOME/.local/bin/uyap-editor" "$HOME/Desktop/UYAP Editör.desktop"
command -v update-mime-database >/dev/null 2>&1 && update-mime-database "$HOME/.local/share/mime" >/dev/null 2>&1
bash "$DIR/adalet_baslat.sh" stop >/dev/null 2>&1; bash "$DIR/eimza_baslat.sh" stop >/dev/null 2>&1
echo "Geri alindi."
