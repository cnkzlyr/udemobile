#!/data/data/com.termux/files/usr/bin/bash
# =============================================================================
#  UYAP Evrak Yöneticisi — Android kurulumu (Termux + Termux:X11)
#  Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır.
#
#  Android'de Python/Tk uygulamaları APK olarak paketlenemez; uygulama Termux içinde, Termux:X11
#  ekranında tam arayüzüyle çalışır. Bu betik:
#    1) Python, Tk, Chromium, OpenJDK 17, Pillow, yazı tiplerini kurar,
#    2) Depoyu ~/uyap-evrak-indirici altına indirir/günceller,
#    3) "uyap-evrak" komutunu ve Termux:Widget kısayolunu (ana ekrana eklenebilir) oluşturur.
#  Gerekli uygulamalar (F-Droid / GitHub): Termux, Termux:X11, (isteğe bağlı) Termux:Widget.
# =============================================================================
set -e
REPO="${REPO:-https://github.com/cnkzlyr/uyap-evrak-indirici.git}"
DIR="$HOME/uyap-evrak-indirici"

echo "[1/5] Paketler güncelleniyor..."
pkg update -y
pkg install -y x11-repo tur-repo
pkg install -y python python-pip python-tkinter python-pillow git chromium openjdk-17 termux-x11-nightly \
               fontconfig ttf-dejavu || true

echo "[2/5] Uygulama indiriliyor..."
if [ -d "$DIR/.git" ]; then git -C "$DIR" pull --ff-only; else git clone --depth 1 "$REPO" "$DIR"; fi
cd "$DIR"
pip install --break-system-packages requests websocket-client pypdf 2>/dev/null || pip install requests websocket-client pypdf

echo "[3/5] Depolama izni..."
[ -d "$HOME/storage" ] || termux-setup-storage || true

echo "[4/5] Yazı tipleri (Times/Arial uyumlu Liberation) ..."
mkdir -p "$HOME/.fonts"
pkg install -y liberation-fonts 2>/dev/null || true

echo "[5/5] Başlatıcı oluşturuluyor..."
cat > "$PREFIX/bin/uyap-evrak" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
# Termux:X11 ekranında başlatır (gerekirse X11 sunucusunu açar). © Av. Can KIZILYAR
export DISPLAY=:0
if ! pgrep -f termux-x11 >/dev/null; then
  termux-x11 :0 >/dev/null 2>&1 &
  sleep 2
  am start -n com.termux.x11/com.termux.x11.MainActivity >/dev/null 2>&1 || true
fi
export UYAP_INDIRME_DIZINI="\$HOME/storage/downloads/UYAP_Indirilenler"
export UYAP_FONT_DIR="$PREFIX/share/fonts"
cd "$DIR" && exec python uygulama.py "\$@"
EOF
chmod +x "$PREFIX/bin/uyap-evrak"
mkdir -p "$HOME/.shortcuts"
printf '#!/data/data/com.termux/files/usr/bin/bash\nuyap-evrak\n' > "$HOME/.shortcuts/UYAP Evrak"
chmod +x "$HOME/.shortcuts/UYAP Evrak"

cat <<'EOF'

==================================================================
  ✓ Kurulum tamamlandı.  © Av. Can KIZILYAR
  Başlatmak için:   uyap-evrak
  Ana ekran kısayolu: Termux:Widget > "UYAP Evrak"
  Dar ekranda filtre paneli otomatik gizlenir; ☰ düğmesiyle açılır.
  UDF -> PDF için UYAP Editör jar dosyalarını ~/jars klasörüne koyun.
==================================================================
EOF
