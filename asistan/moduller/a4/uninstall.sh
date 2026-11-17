#!/usr/bin/env bash
# ==============================================================================
# NAPS2 & UYAP Thunar Araçları - Kaldırma Scripti
# ==============================================================================

BIN_DIR="$HOME/.local/bin"
THUNAR_UCA="$HOME/.config/Thunar/uca.xml"

echo "Araçlar kaldırılıyor..."

rm -f "$BIN_DIR/uyap-convert" "$BIN_DIR/a4-pdf-tools"

# uca.xml içinden bu eylemleri temizle
if [ -f "$THUNAR_UCA" ]; then
python3 - << 'EOF'
import os
import xml.etree.ElementTree as ET

uca_path = os.path.expanduser("~/.config/Thunar/uca.xml")
if os.path.exists(uca_path):
    try:
        tree = ET.parse(uca_path)
        root = tree.getroot()
        removed = 0
        for act in list(root.findall("action")):
            cmd = act.find("command")
            if cmd is not None and cmd.text:
                if "a4-pdf-tools" in cmd.text or "uyap-convert" in cmd.text:
                    root.remove(act)
                    removed += 1
        if removed > 0:
            tree.write(uca_path, encoding="UTF-8", xml_declaration=True)
            print(f"[BAŞARILI] {removed} eylem uca.xml dosyasından kaldırıldı.")
    except Exception as e:
        print(f"[HATA] {e}")
EOF
fi

thunar -q 2>/dev/null || true
(thunar --daemon &) 2>/dev/null || true

echo "Kaldırma işlemi tamamlandı."
