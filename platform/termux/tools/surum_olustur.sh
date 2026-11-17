#!/usr/bin/env bash
# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
# YAZAR ARACI: paketi Av. Can KIZILYAR'in ozel anahtariyla muhurler ve dagitim zip'ini uretir.
#   bash tools/surum_olustur.sh [SURUM]      ortam: CKZ_INDIRME=https://...  CKZ_CIKTI=~/cikti
# Gerekenler: python + cryptography (Termux: pkg install python-cryptography). Ozel anahtar: ~/.ckz-muhur/ed25519.pem
set -eu
KOK="$(cd "$(dirname "$0")/.." && pwd)"
SURUM="${1:-1.0}"
OUT="${CKZ_CIKTI:-$HOME/uyap-termux-cikti}"
python3 -c "import cryptography" 2>/dev/null || { echo "python-cryptography gerekli (Termux: pkg install python-cryptography)"; exit 1; }
KEY="$HOME/.ckz-muhur/ed25519.pem"
if [ ! -f "$KEY" ]; then
  echo "Muhur anahtari yok; olusturuluyor (parola belirlemeniz onerilir)."
  python3 "$KOK/tools/muhurle.py" --anahtar-olustur --sifreli
fi
PARMAK="$(python3 - <<'PY'
import hashlib, os
pub = bytes.fromhex(open(os.path.expanduser("~/.ckz-muhur/public.hex")).read().strip())
h = hashlib.sha256(pub).hexdigest()[:32].upper()
print("-".join(h[i:i+4] for i in range(0, 32, 4)))
PY
)"
INDIRME="${CKZ_INDIRME:-[RESMI-INDIRME-ADRESI]}"
B="$OUT/build/uyap-termux-$SURUM"
rm -rf "$B"; mkdir -p "$B"
cp -a "$KOK/." "$B/"
rm -rf "$B/MUHUR" "$B/.git"; rm -f "$B/YAZAR_ADIMLARI.txt"; mkdir -p "$B/MUHUR"
find "$B" \( -name __pycache__ -o -name '*.pyc' -o -name '*.class' \) -prune -exec rm -rf {} + 2>/dev/null || true
sed -i "s|@@SURUM@@|$SURUM|g; s|@@PARMAK@@|$PARMAK|g; s|@@INDIRME_ADRESI@@|$INDIRME|g" "$B/README.md"
sed -i "s|CKZ_SURUM=\"[^\"]*\"|CKZ_SURUM=\"$SURUM\"|" "$B/bilesenler/eimza/marka.sh"
echo "== muhurleniyor"
python3 "$B/tools/muhurle.py" --imzala "$B" --anahtar "$KEY"
echo "== dogrulaniyor"
python3 "$B/tools/dogrula.py" "$B" --pub-parmak "$PARMAK"
ZIP="$OUT/uyap-termux-$SURUM.zip"
python3 - "$B" "$ZIP" <<'PY'
import os, sys, zipfile
b, z = sys.argv[1:3]
with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
    for r, d, fs in os.walk(b):
        d.sort()
        for f in sorted(fs):
            p = os.path.join(r, f)
            zf.write(p, os.path.join(os.path.basename(b), os.path.relpath(p, b)))
PY
( cd "$OUT" && sha256sum "uyap-termux-$SURUM.zip" | tee "uyap-termux-$SURUM.zip.sha256" )
echo
echo "HAZIR: $ZIP"
echo "Yazar anahtar parmak izi: $PARMAK   (bunu resmi sayfanizda/README'de yayimlayin)"
echo "Kanit onerisi: zip'in .sha256 dosyasini UYAP Editor ile e-imzalayip zaman damgasi alin; ayrica bir noterde/telif kaydinda tescil ettirin."
