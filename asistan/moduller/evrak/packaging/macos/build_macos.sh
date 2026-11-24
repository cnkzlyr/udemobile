#!/usr/bin/env bash
# UYAP Evrak Yöneticisi — macOS .app ve .dmg (Intel x86_64 ve Apple Silicon arm64)
# Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır.
#
# Mimari, betiği çalıştıran Python'un mimarisidir: Intel Mac (veya macos-13 runner) -> x86_64,
# Apple Silicon (macos-14 runner) -> arm64. İmzasız paket: ilk açılışta sağ tık > Aç.
set -euo pipefail
cd "$(dirname "$0")/../.."
VER="${VER:-3.0.0}"
ARCH="$(uname -m)"
APP="dist/UYAP Evrak Yöneticisi.app"
[ -d "$APP" ] || { echo "Önce: pyinstaller packaging/uyap_evrak.spec"; exit 1; }
# PyInstaller BUNDLE, COLLECT içeriğini Contents/MacOS altına koyar; JRE ve fontlar orada olmalı
for extra in runtime fonts; do
  if [ -d "dist/UYAPEvrak/$extra" ] && [ ! -d "$APP/Contents/MacOS/$extra" ]; then
    cp -a "dist/UYAPEvrak/$extra" "$APP/Contents/MacOS/"
  fi
done
STAGE=build/dmg
rm -rf "$STAGE"; mkdir -p "$STAGE"
cp -a "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cat > "$STAGE/OKUBENI.txt" <<'EOF'
UYAP Evrak Yöneticisi — © 2026 Av. Can KIZILYAR. Tüm hakları saklıdır.
Kurulum: uygulamayı Applications klasörüne sürükleyin. İlk açılışta macOS uyarı verirse
uygulamaya sağ tıklayıp "Aç" deyin. UDF -> PDF için UYAP Editör kütüphanelerini
~/Library/Application Support/UYAPEvrak/jars klasörüne koyun.
EOF
sync 2>/dev/null || true
sleep 3

DMG_TARGET="dist/UYAPEvrak-${VER}-macOS-${ARCH}.dmg"
rm -f "$DMG_TARGET"

SUCCESS=0
for i in 1 2 3 4 5; do
  echo "DMG oluşturuluyor (Deneme $i/5)..."
  if hdiutil create -volname "UYAP Evrak Yöneticisi" -srcfolder "$STAGE" -ov -format UDZO "$DMG_TARGET"; then
    SUCCESS=1
    break
  fi
  echo "hdiutil meşgul (Resource busy), beklenip tekrar denenecek..."
  sleep 4
done

if [ $SUCCESS -ne 1 ]; then
  echo "Hata: 5 denemede de DMG oluşturulamadı!"
  exit 1
fi

ls -la dist

