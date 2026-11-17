#!/bin/bash
# ==============================================================================
# UYAP Editör Modern — çoklu platform paketleri (CI: .github/workflows/release.yml)
#
# Her pakete:
#   * Java 14.0.2 (resmi OpenJDK, download.java.net, SHA-256 sabit) — jlink ile küçültülmüş (Nashorn dahil);
#     Linux x64 jlink'i ile Windows ve macOS jmod'larından çapraz bağlanır (aynı sürüm şart).
#   * E-imza: Unicode PC/SC ajanı (uyap-pcsc-agent.jar, JNA) — Windows'ta adında Türkçe karakter olan okuyucular
#     (ArkSigner: "Microsoft Usbccid Akıllı Kart Okuyucusu (WUDF)") JDK'nın PC/SC katmanında açılamıyordu. Linux'ta
#     pcsclite ile de çalışır. Resmi editörün APDU kipi AKİS kartı sürücüsüz imzalar (Araçlar menüsü).
#   * Linux / macOS: Microsoft Core Fonts for the Web (Times New Roman, Arial, Courier New, Georgia, Verdana,
#     Trebuchet, Comic Sans, Impact, Andale Mono, Arial Black, Webdings) — lisans gereği ORİJİNAL kurulum dosyaları
#     (.exe) değiştirilmeden konur; kurulum betiği bunları kullanıcının bilgisayarında açar (cabextract / bsdtar / 7z).
#
# Çıktı: release-assets/
# ==============================================================================
set -euo pipefail
KOK="$(cd "$(dirname "$0")/.." && pwd)"
cd "$KOK"
ON="$KOK/build/onbellek"; mkdir -p "$ON" release-assets pkg
JDK_ON="https://download.java.net/java/GA/jdk14.0.2/205943a0976c4ed48cb16f1043c5c647/12/GPL"

indir() {   # indir URL SHA256 HEDEF
  if [ ! -f "$3" ] || [ "$(sha256sum "$3" | cut -d' ' -f1)" != "$2" ]; then
    curl -fsSL --retry 3 -o "$3.tmp" "$1"; mv "$3.tmp" "$3"
  fi
  [ "$(sha256sum "$3" | cut -d' ' -f1)" = "$2" ] || { echo "SHA256 uyuşmuyor: $3"; exit 1; }
}

# ---------------------------------------------------------------- Java 14.0.2
indir "$JDK_ON/openjdk-14.0.2_linux-x64_bin.tar.gz"   91310200f072045dc6cef2c8c23e7e6387b37c46e9de49623ce0fa461a24623d "$ON/jdk-linux.tgz"
indir "$JDK_ON/openjdk-14.0.2_osx-x64_bin.tar.gz"     386a96eeef63bf94b450809d69ceaa1c9e32a97230e0a120c1b41786b743ae84 "$ON/jdk-mac.tgz"
indir "$JDK_ON/openjdk-14.0.2_windows-x64_bin.zip"    20600c0bda9d1db9d20dbe1ab656a5f9175ffb990ef3df6af5d994673e4d8ff9 "$ON/jdk-win.zip"
rm -rf build/jdk && mkdir -p build/jdk/linux build/jdk/mac build/jdk/win
tar -xzf "$ON/jdk-linux.tgz" -C build/jdk/linux
tar -xzf "$ON/jdk-mac.tgz" -C build/jdk/mac
unzip -q "$ON/jdk-win.zip" -d build/jdk/win
HOSTJDK="$KOK/build/jdk/linux/jdk-14.0.2"
JMODS_LINUX="$HOSTJDK/jmods"
JMODS_MAC="$(find build/jdk/mac -type d -name jmods | head -1)"
JMODS_WIN="build/jdk/win/jdk-14.0.2/jmods"
MODULLER="java.base,java.desktop,java.datatransfer,java.xml,java.xml.crypto,java.logging,java.naming,java.prefs,java.sql,java.sql.rowset,java.scripting,jdk.scripting.nashorn,jdk.dynalink,java.security.jgss,java.security.sasl,java.smartcardio,jdk.crypto.cryptoki,jdk.crypto.ec,java.net.http,java.management,jdk.management,jdk.unsupported,jdk.charsets,jdk.localedata,jdk.zipfs,jdk.naming.dns,java.instrument,java.transaction.xa,java.rmi,jdk.httpserver,jdk.xml.dom,jdk.accessibility,jdk.net,jdk.security.auth,java.compiler,jdk.jsobject"
jre() {   # jre JMODS ÇIKTI [ek modüller]
  rm -rf "$2"
  env -u JAVA_TOOL_OPTIONS "$HOSTJDK/bin/jlink" --module-path "$1" --add-modules "$MODULLER${3:-}" \
    --include-locales=tr,en --strip-java-debug-attributes --no-header-files --no-man-pages --compress=2 --output "$2"
}

# ---------------------------------------------------------------- e-imza ajanı (Unicode PC/SC)
JNA="$ON/jna-5.14.0.jar"
indir https://repo1.maven.org/maven2/net/java/dev/jna/jna/5.14.0/jna-5.14.0.jar 34ed1e1f27fa896bca50dbc4e99cf3732967cec387a7a0d5e3486c09673fe8c6 "$JNA"
rm -rf build/ajan && mkdir -p build/ajan/c
env -u JAVA_TOOL_OPTIONS "$HOSTJDK/bin/javac" --release 11 -encoding UTF-8 -nowarn -cp "$JNA" -d build/ajan/c $(find tools/eimza-agent/src -name '*.java')
( cd build/ajan/c && unzip -q -o "$JNA" 'com/sun/jna/*.class' 'com/sun/jna/ptr/*' 'com/sun/jna/internal/*' \
    'com/sun/jna/win32-x86-64/*' 'com/sun/jna/win32-aarch64/*' 'com/sun/jna/linux-x86-64/*' 'com/sun/jna/linux-aarch64/*' \
    'com/sun/jna/win32/*' 'META-INF/LICENSE' 2>/dev/null || true; rm -f META-INF/MANIFEST.MF; [ -f META-INF/LICENSE ] && mv META-INF/LICENSE META-INF/JNA-LICENSE || true )
printf 'Manifest-Version: 1.0\nPremain-Class: eimzawin.Agent\nImplementation-Title: UYAP Editor Modern Unicode PC/SC\n' > build/ajan/m.txt
env -u JAVA_TOOL_OPTIONS "$HOSTJDK/bin/jar" cfm build/uyap-pcsc-agent.jar build/ajan/m.txt -C build/ajan/c .

# ---------------------------------------------------------------- Microsoft Core Fonts (orijinal .exe)
mkdir -p build/msfonts
while read -r ad sha; do
  indir "https://downloads.sourceforge.net/corefonts/$ad" "$sha" "build/msfonts/$ad"
done <<'EOF'
andale32.exe 0524fe42951adc3a7eb870e32f0920313c71f170c859b5f770d82b4ee111e970
arial32.exe 85297a4d146e9c87ac6f74822734bdee5f4b2a722d7eaa584b7f2cbf76f478f6
arialb32.exe a425f0ffb6a1a5ede5b979ed6177f4f4f4fdef6ae7c302a7b7720ef332fec0a8
comic32.exe 9c6df3feefde26d4e41d4a4fe5db2a89f9123a772594d7f59afd062625cd204e
courie32.exe bb511d861655dde879ae552eb86b134d6fae67cb58502e6ff73ec5d9151f3384
georgi32.exe 2c2c7dcda6606ea5cf08918fb7cd3f3359e9e84338dc690013f20cd42e930301
impact32.exe 6061ef3b7401d9642f5dfdb5f2b376aa14663f6275e60a51207ad4facf2fccfb
times32.exe db56595ec6ef5d3de5c24994f001f03b2a13e37cee27bc25c58f6f43e8f807ab
trebuc32.exe 5a690d9bb8510be1b8b4fe49f1f2319651fe51bbe54775ddddd8ef0bd07fdac9
verdan32.exe c1cb61255e363166794e47664e2f21af8e3a26cb6346eb8d2ae2fa85dd5aad96
webdin32.exe 64595b5abc1080fba8610c5c34fab5863408e806aafe84653ca8575bed17d75a
EOF
cat > build/msfonts/OKU.txt <<'EOF'
Microsoft Core Fonts for the Web (Times New Roman, Arial, Courier New, ...)
Bu klasördeki .exe dosyaları Microsoft'un ORİJİNAL, değiştirilmemiş kurulum dosyalarıdır (lisans yalnızca bu biçimde
dağıtıma izin verir; her .exe'nin içindeki Licen.TXT lisans metnidir). install.sh bunları kurulum sırasında açar ve
yazı tiplerini yalnızca sizin bilgisayarınıza kurar. Kaynak: https://sourceforge.net/projects/corefonts/
EOF

# ---------------------------------------------------------------- resmi UYAP Editör (Linux paketi)
mkdir -p build/upstream/deb
indir_esnek() { [ -f "$2" ] || curl -fsSL --retry 3 -o "$2" "$1" || true; }
indir_esnek "https://rayp.adalet.gov.tr/resimler/2/dosya/uyapeditor_5.4.20_amd64.zip" build/upstream/uyap_linux.zip
if [ -s build/upstream/uyap_linux.zip ]; then
  unzip -q -o build/upstream/uyap_linux.zip -d build/upstream/deb
  if [ -f build/upstream/deb/uyapeditor_5.4.20_amd64.deb ]; then
    ( cd build/upstream/deb && ( ar x uyapeditor_5.4.20_amd64.deb data.tar.xz 2>/dev/null || ar x uyapeditor_5.4.20_amd64.deb data.tar.gz 2>/dev/null || true ) && tar -xf data.tar.* -C . ./usr/share/UYAPEditor/ 2>/dev/null || true )
  fi
fi

# ---------------------------------------------------------------- 1) bağımsız ajan
cp dist/uyap-modernizer.jar release-assets/uyap-modernizer.jar
cp build/uyap-pcsc-agent.jar release-assets/uyap-pcsc-agent.jar

# ---------------------------------------------------------------- 2) Linux
rm -rf pkg/linux && mkdir -p pkg/linux
[ -s build/upstream/uyap_linux.zip ] && unzip -q -o build/upstream/uyap_linux.zip -d pkg/linux || true
cp dist/uyap-modernizer.jar build/uyap-pcsc-agent.jar pkg/linux/
cp platforms/linux/bin/* pkg/linux/
cp -r platforms/linux/desktop platforms/linux/drivers platforms/linux/icons pkg/linux/
cp platforms/linux/install.sh pkg/linux/
cp -r config pkg/linux/
cp -r build/msfonts pkg/linux/fonts-ms
jre "$JMODS_LINUX" pkg/linux/jdk-14.0.2
chmod +x pkg/linux/*.sh
tar -czf release-assets/uyap-editor-modern-linux-x86_64.tar.gz -C pkg/linux .

# ---------------------------------------------------------------- 3) Windows
rm -rf pkg/windows && mkdir -p pkg/windows
cp dist/uyap-modernizer.jar build/uyap-pcsc-agent.jar pkg/windows/
cp platforms/windows/bin/* pkg/windows/
cp platforms/windows/install.ps1 pkg/windows/
cp -r platforms/windows/src pkg/windows/
cp -r platforms/windows/icons pkg/windows/
cp platforms/windows/icons/*.ico pkg/windows/ 2>/dev/null || true
cp -r config pkg/windows/
if [ -d build/upstream/deb/usr/share/UYAPEditor ]; then
  cp -r build/upstream/deb/usr/share/UYAPEditor/*.jar pkg/windows/ 2>/dev/null || true
fi
jre "$JMODS_WIN" pkg/windows/jdk-14.0.2 ",jdk.crypto.mscapi"
( cd pkg && zip -q -r ../release-assets/uyap-editor-modern-windows-x64.zip windows )

# ---------------------------------------------------------------- 4) macOS (Intel; Apple Silicon'da Rosetta 2)
rm -rf pkg/macos && mkdir -p pkg/macos
cp dist/uyap-modernizer.jar build/uyap-pcsc-agent.jar pkg/macos/ 2>/dev/null || true
cp -r platforms/macos/* pkg/macos/
cp -r config pkg/macos/
cp -r build/msfonts pkg/macos/fonts-ms
if [ -d build/upstream/deb/usr/share/UYAPEditor ]; then
  cp -r build/upstream/deb/usr/share/UYAPEditor/*.jar pkg/macos/ 2>/dev/null || true
fi
jre "$JMODS_MAC" pkg/macos/jdk-14.0.2
( cd pkg && zip -q -r -y ../release-assets/uyap-editor-modern-macos.zip macos )

ls -lh release-assets/
