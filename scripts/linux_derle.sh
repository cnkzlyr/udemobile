#!/usr/bin/env bash
# CanEditor — Linux paketleri (.deb, .rpm, .AppImage) + Android asistan çalışma ortamı
#
# Ubuntu 22.04/24.04'te (Windows'ta WSL Ubuntu dahil) çalışır; eksik her şeyi kurar.
#   bash scripts/linux_derle.sh              # Linux paketleri + Android asistan çalışma ortamı
#   bash scripts/linux_derle.sh --android-yok   # yalnız Linux paketleri
# Çıktılar: dist-linux/  (deb, rpm, AppImage) ve build/asistan-android/ (APK'ya giren çalışma ortamı)
set -euo pipefail
KOK="$(cd "$(dirname "$0")/.." && pwd)"
cd "$KOK"
ANDROID=1
[ "${1:-}" = "--android-yok" ] && ANDROID=0
bilgi() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

bilgi "1/5 Sistem paketleri"
export DEBIAN_FRONTEND=noninteractive
$SUDO apt-get update -qq
$SUDO apt-get install -y -qq libwebkit2gtk-4.1-dev build-essential curl wget file libxdo-dev libssl-dev \
  libayatana-appindicator3-dev librsvg2-dev patchelf rpm python3 python3-venv python3-pip python3-tk \
  binutils qemu-user openjdk-21-jdk-headless ca-certificates git >/dev/null
if [ "$ANDROID" = 1 ]; then   # UYAP Mobil başlatıcısı (aarch64 C) ve Android ELF araçları
  $SUDO apt-get install -y -qq gcc-aarch64-linux-gnu binutils-aarch64-linux-gnu >/dev/null
fi
if ! command -v node >/dev/null || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 20 ]; then
  # root iken (WSL) SUDO boştur: "-E" tek başına komut sanılmasın
  if [ -n "$SUDO" ]; then curl -fsSL https://deb.nodesource.com/setup_22.x | $SUDO -E bash - >/dev/null
  else curl -fsSL https://deb.nodesource.com/setup_22.x | bash - >/dev/null; fi
  $SUDO apt-get install -y -qq nodejs >/dev/null
fi
if ! command -v cargo >/dev/null; then
  curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal >/dev/null
fi
# shellcheck disable=SC1091
[ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"

bilgi "2/5 Python ortamı (asistan sunucusu paketleme)"
# tkinter'ı (python3-tk: pencereli görevler) gerçekten yükleyebilen Python seçilir
SPY=""
for aday in /usr/bin/python3.12 /usr/bin/python3.13 /usr/bin/python3 python3; do
  if command -v "$aday" >/dev/null && "$aday" -c "import tkinter" 2>/dev/null; then SPY="$aday"; break; fi
done
[ -n "$SPY" ] || { echo "tkinter'lı Python bulunamadı (python3-tk)"; exit 1; }
echo "Python: $SPY ($("$SPY" --version))"
rm -rf "$KOK/build/venv"
"$SPY" -m venv "$KOK/build/venv"
# shellcheck disable=SC1091
. "$KOK/build/venv/bin/activate"
pip install -q --upgrade pip
pip install -q -r asistan/requirements.txt pyinstaller

bilgi "3/5 Gömülü Java + Hukuk Asistanı sunucusu + görünmez Chrome"
python scripts/masaustu_hazirla.py --java-home /usr/lib/jvm/java-21-openjdk-amd64

if [ "$ANDROID" = 1 ]; then
  bilgi "4/5 Android: e-imza Java'sı + Termux'suz asistan çalışma ortamı (qemu ile doğrulanır)"
  # Android adımları Linux paketlerini engellemesin: biri başarısız olursa uyarı verilir, derleme sürer
  for b in jre_hazirla uyapmobil_hazirla asistan_android_hazirla; do
    python "scripts/$b.py" || { echo "UYARI: $b başarısız; Linux paketleriyle devam ediliyor"; ANDROID_HATA=1; }
  done
else
  bilgi "4/5 Android asistan çalışma ortamı atlandı"
fi

bilgi "5/5 Linux paketleri (Tauri: deb, rpm, AppImage)"
npm install --no-audit --no-fund
(cd frontend && npm install --no-audit --no-fund && npm run build)
export APPIMAGE_EXTRACT_AND_RUN=1   # WSL/konteynerde FUSE olmadan AppImage araçları
# AppImage aracı (linuxdeploy) gömülü bileşenlerin ELF bağımlılıklarını çözer: libjvm.so gibi kendi
# klasörlerindeki kitaplıklar arama yolunda olmalı (yoksa "Could not find dependency: libjvm.so").
T="$KOK/src-tauri"
export LD_LIBRARY_PATH="$T/eimza/jre/lib/server:$T/eimza/jre/lib:$T/sidecar/asistan-sunucu-x86_64/_internal:$T/tarayici-x86_64/chrome${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
npx tauri build --bundles deb rpm appimage
mkdir -p dist-linux
B="${CARGO_TARGET_DIR:-src-tauri/target}/release/bundle"
cp -f "$B"/deb/*.deb "$B"/rpm/*.rpm "$B"/appimage/*.AppImage dist-linux/
ls -la dist-linux/
bilgi "TAMAM: dist-linux/"
[ "${ANDROID_HATA:-0}" = 0 ] || { echo "UYARI: Android çalışma ortamlarından biri hazırlanamadı (yukarıya bakın)"; exit 3; }
