#!/usr/bin/env bash
# CanEditor Hukuk Asistanı — yerel sunucu kurulumu (Android/Termux, Linux, macOS)
#
#   bash asistan/kur.sh            # bağımlılıkları kurar, "canasistan" komutunu oluşturur
#   canasistan                     # sunucuyu başlatır (http://127.0.0.1:8765)
#   canasistan --anahtar           # CanEditor'a girilecek eşleştirme anahtarını gösterir
#
# Windows'ta: Python 3 kurulu ise CanEditor masaüstü uygulaması sunucuyu kendisi başlatır;
# bağımlılıklar için:  py -3 -m pip install -r asistan\requirements.txt
set -euo pipefail

KOK="$(cd "$(dirname "$0")" && pwd)"
TERMUX=0
case "${PREFIX:-}" in /data/data/com.termux/*) TERMUX=1 ;; esac

bilgi() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }

if [ "$TERMUX" = 1 ]; then
  bilgi "Termux paketleri (python, Pillow, lxml derleme araçları)"
  pkg install -y python python-pillow libxml2 libxslt clang make >/dev/null
  # sqlalchemy'nin C eklentisi Termux'ta derlenmez; saf Python sürümü yeterli
  pip install --no-deps "sqlalchemy>=2.0,<2.1" typing-extensions
  grep -v -E '^(pillow|sqlalchemy)' "$KOK/requirements.txt" | pip install -r /dev/stdin
  HEDEF="$PREFIX/bin"
else
  command -v python3 >/dev/null || { echo "Python 3 gerekli (https://www.python.org/downloads/)"; exit 1; }
  bilgi "Python bağımlılıkları (kullanıcı ortamına)"
  python3 -m pip install --user -r "$KOK/requirements.txt" || python3 -m pip install --user --break-system-packages -r "$KOK/requirements.txt"
  HEDEF="$HOME/.local/bin"
fi

mkdir -p "$HEDEF"
cat > "$HEDEF/canasistan" <<EOF
#!/usr/bin/env bash
exec python3 "$KOK/sunucu.py" "\$@"
EOF
chmod +x "$HEDEF/canasistan"

bilgi "Kuruldu: $HEDEF/canasistan"
case ":$PATH:" in *":$HEDEF:"*) ;; *) echo "Not: $HEDEF PATH'te değil; kabuk yapılandırmanıza ekleyin." ;; esac
echo
echo "Başlatmak için:  canasistan"
echo "Eşleştirme:      CanEditor → Asistan → Bağlantı → anahtar: \$(canasistan --anahtar)"
echo "UETS/TickTick/Notion ayarları: $KOK/moduller/avukatasistan/README.md"
echo "UYAP evrak indirici ayarları:  $KOK/moduller/evrak/README.md"
