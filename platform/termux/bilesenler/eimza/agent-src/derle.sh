#!/data/data/com.termux/files/usr/bin/bash
# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
# eimza-agent.jar'i kaynaktan yeniden uretir (JDK 11+ gerekir). Kullanim: bash ~/eimza/agent-src/derle.sh
set -e
D="$(cd "$(dirname "$0")" && pwd)"
T="$(mktemp -d)"
mkdir -p "$T/src/eimza" "$T/src/tr/gov/adalet/service/framework/adalet/eimza/eimzatray/gui" "$T/out"
cp "$D/../TermuxCcidProvider.java" "$D/Agent.java" "$D/Kimlik.java" "$T/src/eimza/"
cp "$D/gui/e.java" "$T/src/tr/gov/adalet/service/framework/adalet/eimza/eimzatray/gui/e.java"
find "$T/src" -name '*.java' > "$T/kaynaklar.txt"
javac --release 11 -encoding UTF-8 -d "$T/out" @"$T/kaynaklar.txt"
printf 'Premain-Class: eimza.Agent\nCan-Redefine-Classes: false\nCan-Retransform-Classes: false\nImplementation-Title: UYAP-Termux\nImplementation-Version: 1.0\nImplementation-Vendor: Av. Can KIZILYAR\nCopyright: (c) 2026 Av. Can KIZILYAR - Tum haklari saklidir\n' > "$T/manifest.txt"
jar cfm "$D/../eimza-agent.jar" "$T/manifest.txt" -C "$T/out" .
rm -rf "$T"
echo "eimza-agent.jar yenilendi."
