#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# UYAP Editör Modern - Android Tablet / Telefon Kurulum Betiği
# Termux + Termux:X11 + Fluxbox Üzerinde 120Hz Akıcı Masaüstü UYAP Editörü
# ==============================================================================

set -e

echo "=== Android UYAP Editör Modern Kurulumu ==="

# 1. Gerekli paketleri güncelle ve yükle (Fluxbox pencere yöneticisi dahil)
pkg update -y
pkg install -y x11-repo wget tar unzip
pkg update -y
pkg install -y openjdk-17 termux-x11-nightly pulseaudio fluxbox

# 2. Çalışma klasörü oluştur
mkdir -p ~/uyap-editor ~/.uki
cd ~/uyap-editor

# 3. UYAP Editör paketini indir ve aç
if [ ! -f "editor_lib.jar" ]; then
    echo "UYAP Editör paketleri indiriliyor..."
    wget -c -O uyap.zip "https://rayp.adalet.gov.tr/resimler/2/dosya/uyapeditor_5.4.20_amd64.zip"
    unzip -q -o uyap.zip
    rm -f uyap.zip
    
    echo "DEB paketi açılıyor..."
    dpkg -x uyapeditor_5.4.20_amd64.deb . 2>/dev/null || (ar -x uyapeditor_5.4.20_amd64.deb && tar -xf data.tar.*)
    mv usr/share/UYAPEditor/*.jar .
    [ -d "usr/share/UYAPEditor/images" ] && mv usr/share/UYAPEditor/images .
    rm -rf usr cups-bsd* uyapeditor* data.tar.* control.tar.* debian-binary 2>/dev/null || true
fi

# 4. Modernizasyon Kütüphanesini (FlatLaf, 120Hz Smooth Scroll, Modern UI) İndir
echo "Modernizasyon kütüphanesi (120Hz Smooth Scroll & FlatLaf) indiriliyor..."
curl -sL -o ~/uyap-editor/uyap-modernizer.jar "https://raw.githubusercontent.com/cnkzlyr/uyap-editor-modern/main/dist/uyap-modernizer.jar"

# 5. Java sürüm kontrolü kilidini kaldır (UYAP'ın yapay 'Sürümünüz 6 ila 14 Arasında Olmalı' sınırını aşar)
cat << 'P_EOF' > ~/uyap-editor/Patch.java
import java.io.*;
import java.util.*;
import java.util.zip.*;

public class Patch {
    public static void main(String[] args) throws Exception {
        File jar = new File("editor_lib.jar");
        if (!jar.exists()) return;
        File temp = new File("editor_lib_temp.jar");
        byte[] oldB = new byte[]{ (byte)0xb8, 0, (byte)0xa6, 0x3b, 0x1a, 0x10, 0x06, (byte)0xa1, 0, 0x0b, 0x1a, 0x10, 0x0e, (byte)0xa3, 0, 0x05, 0x04, (byte)0xac, 0x03, (byte)0xac };
        byte[] newB = new byte[]{ 0x04, (byte)0xac, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
        try (ZipFile zin = new ZipFile(jar);
             ZipOutputStream zout = new ZipOutputStream(new FileOutputStream(temp))) {
            Enumeration<? extends ZipEntry> en = zin.entries();
            while (en.hasMoreElements()) {
                ZipEntry ze = en.nextElement();
                zout.putNextEntry(new ZipEntry(ze.getName()));
                byte[] data = zin.getInputStream(ze).readAllBytes();
                if (ze.getName().endsWith("WPAppManager.class")) {
                    for (int i = 0; i <= data.length - oldB.length; i++) {
                        boolean match = true;
                        for (int j = 0; j < oldB.length; j++) {
                            if (data[i + j] != oldB[j]) { match = false; break; }
                        }
                        if (match) {
                            System.arraycopy(newB, 0, data, i, newB.length);
                            break;
                        }
                    }
                }
                zout.write(data);
                zout.closeEntry();
            }
        }
        jar.delete();
        temp.renameTo(jar);
    }
}
P_EOF
cd ~/uyap-editor && java Patch.java 2>/dev/null && rm -f Patch.java

# 6. 120Hz & FlatLaf Yapılandırmasını Kaydet
cat << 'C_EOF' > ~/.uki/modernizer.properties
smoothScroll=true
targetHz=120
scrollStep=70.0
scrollDecay=14.0
theme=flat-light
C_EOF

# 7. Android başlatıcı betiği oluştur (Fluxbox WM ile birlikte)
cat << 'EOF' > ~/uyap-editor/run-android.sh
#!/data/data/com.termux/files/usr/bin/bash
export DISPLAY=:0
export PULSE_SERVER=127.0.0.1

# X11 Sunucusu ve Ekranı Başlat
if ! pgrep -f "termux-x11" >/dev/null; then
    termux-x11 :0 >/dev/null 2>&1 &
    sleep 1
fi
am start --user 0 -n com.termux.x11/com.termux.x11.MainActivity 2>/dev/null || true
sleep 1

# Fluxbox Pencere Yöneticisini Başlat (Pencere başlıkları, taşıma, tam ekran, görev çubuğu)
if ! pgrep -f "fluxbox" >/dev/null; then
    fluxbox >/dev/null 2>&1 &
    sleep 1
fi

cd ~/uyap-editor
CP="uyap-modernizer.jar:."
for j in *.jar; do
    if [ "$j" != "uyap-modernizer.jar" ]; then
        CP="$CP:$j"
    fi
done

CLEAN_ARGS=()
for raw_arg in "$@"; do
    [ -z "$raw_arg" ] && continue
    arg="$raw_arg"
    arg="${arg#\"}"
    arg="${arg%\"}"
    arg="${arg#\'}"
    arg="${arg%\'}"
    if [[ "$arg" =~ ^file:// ]]; then
        arg="${arg#file://}"
        if command -v python3 >/dev/null 2>&1; then
            arg="$(python3 -c 'import sys, urllib.parse; print(urllib.parse.unquote(sys.argv[1]))' "$arg" 2>/dev/null || echo "$arg")"
        fi
    fi
    if [ -e "$arg" ]; then
        arg="$(readlink -f "$arg" 2>/dev/null || realpath "$arg" 2>/dev/null || echo "$arg")"
    fi
    CLEAN_ARGS+=("$arg")
done

EDITOR_TYPE="EDITOR_TYPE_DOCUMENT"
TARGET=""
if [ ${#CLEAN_ARGS[@]} -gt 0 ]; then
    TARGET="${CLEAN_ARGS[0]}"
    if [[ "$TARGET" =~ \.(usf|USF)$ ]]; then
        EDITOR_TYPE="EDITOR_TYPE_TEMPLATE"
    fi
fi

if [ -n "$TARGET" ]; then
    java --add-opens java.base/java.lang=ALL-UNNAMED \
         --add-opens java.base/java.lang.reflect=ALL-UNNAMED \
         --add-opens java.base/java.util=ALL-UNNAMED \
         --add-opens java.base/java.text=ALL-UNNAMED \
         --add-opens java.base/java.io=ALL-UNNAMED \
         --add-opens java.desktop/java.awt=ALL-UNNAMED \
         --add-opens java.desktop/java.awt.font=ALL-UNNAMED \
         --add-opens java.desktop/javax.swing=ALL-UNNAMED \
         --add-opens java.desktop/javax.swing.plaf.basic=ALL-UNNAMED \
         --add-opens java.desktop/sun.awt=ALL-UNNAMED \
         --add-opens java.desktop/sun.swing=ALL-UNNAMED \
         --add-opens java.desktop/sun.font=ALL-UNNAMED \
         -javaagent:uyap-modernizer.jar \
         -Xms128m -Xmx1024m \
         -Dsun.java2d.uiScale=1.25 \
         -Dawt.useSystemAAFontSettings=on \
         -Dswing.aatext=true \
         -cp "$CP" tr.com.havelsan.uyap.system.editor.common.WPAppManager "getNewWPInstance" "$EDITOR_TYPE" "$TARGET"
else
    java --add-opens java.base/java.lang=ALL-UNNAMED \
         --add-opens java.base/java.lang.reflect=ALL-UNNAMED \
         --add-opens java.base/java.util=ALL-UNNAMED \
         --add-opens java.base/java.text=ALL-UNNAMED \
         --add-opens java.base/java.io=ALL-UNNAMED \
         --add-opens java.desktop/java.awt=ALL-UNNAMED \
         --add-opens java.desktop/java.awt.font=ALL-UNNAMED \
         --add-opens java.desktop/javax.swing=ALL-UNNAMED \
         --add-opens java.desktop/javax.swing.plaf.basic=ALL-UNNAMED \
         --add-opens java.desktop/sun.awt=ALL-UNNAMED \
         --add-opens java.desktop/sun.swing=ALL-UNNAMED \
         --add-opens java.desktop/sun.font=ALL-UNNAMED \
         -javaagent:uyap-modernizer.jar \
         -Xms128m -Xmx1024m \
         -Dsun.java2d.uiScale=1.25 \
         -Dawt.useSystemAAFontSettings=on \
         -Dswing.aatext=true \
         -cp "$CP" tr.com.havelsan.uyap.system.editor.common.WPAppManager "getNewWPInstance" "EDITOR_TYPE_DOCUMENT"
fi
EOF

chmod +x ~/uyap-editor/run-android.sh
ln -sf ~/uyap-editor/run-android.sh $PREFIX/bin/uyap

echo "✓ Kurulum tamamlandı!"
echo "Çalıştırmak için: 'uyap' komutunu yazmanız ve ekranda açılan Termux:X11 penceresine geçmeniz yeterlidir."
