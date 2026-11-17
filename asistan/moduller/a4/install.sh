#!/usr/bin/env bash
# ==============================================================================
# NAPS2 & UYAP Thunar Araçları - Kurulum Scripti (Linux & Termux Destekli)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SCRIPT_DIR
BIN_DIR="$HOME/.local/bin"
THUNAR_UCA="$HOME/.config/Thunar/uca.xml"

echo "=========================================================="
echo "  NAPS2 & UYAP Thunar Sağ Tık Dönüştürme Araçları Kurulumu"
echo "=========================================================="

# 1. ~/.local/bin dizinini garanti et
mkdir -p "$BIN_DIR"

# 2. Python bağımlılıklarını kontrol et / kur
echo "[1/6] Python bağımlılıkları kontrol ediliyor (Pillow, reportlab, pypdf)..."
python3 -c "import PIL, reportlab, pypdf" 2>/dev/null || {
    echo "[BİLGİ] Eksik Python paketleri yükleniyor..."
    pip install reportlab pypdf pillow
}

# 3. UYAP Jar klasörünü ara
echo "[2/6] UYAP Doküman Editörü kütüphaneleri (JAR) aranıyor..."
JARS_FOUND=0
for cand in "$HOME/jars" "/opt/uyap/jars" "/usr/share/uyap/jars" "/data/data/com.termux/files/home/jars"; do
    if [ -f "$cand/editor_lib.jar" ]; then
        echo "[BAŞARILI] UYAP JAR kütüphaneleri bulundu: $cand"
        JARS_FOUND=1
        UYAP_DIR="$cand"
        break
    fi
done

if [ $JARS_FOUND -eq 0 ]; then
    echo "[UYARI] UYAP jar dosyaları varsayılan konumlarda bulunamadı."
    echo "       Lütfen 'editor_lib.jar', 'jai_hvl.jar' vb. dosyalarınızı '$HOME/jars' klasörüne koyun."
fi

# 4. Java Köprüsünü Derle ve Paketle
echo "[3/6] UYAP Java Vektörel Dışa Aktarım Köprüsü derleniyor..."
cd "$SCRIPT_DIR/java"
javac -d . UyapVectorExporter.java -cp "${UYAP_DIR:-$HOME/jars}/*" 2>/dev/null || {
    echo "[UYARI] javac ile derleme tamamlanamadı (önceden derlenmiş jar kullanılacak)."
}
if [ -d "uyap" ]; then
    jar cvf uyap-exporter.jar uyap/*.class >/dev/null 2>&1 || true
fi
cd "$SCRIPT_DIR"

# 5. Çalıştırılabilir Dosyaları Bağla (~/.local/bin ve Termux /usr/bin)
echo "[4/6] CLI araçları sistem yollarına bağlanıyor..."
chmod +x "$SCRIPT_DIR/bin/"* "$SCRIPT_DIR/python/"*
ln -sf "$SCRIPT_DIR/bin/uyap-convert" "$BIN_DIR/uyap-convert"
ln -sf "$SCRIPT_DIR/bin/a4-pdf-tools" "$BIN_DIR/a4-pdf-tools"

if [ -d "/data/data/com.termux/files/usr/bin" ]; then
    ln -sf "$SCRIPT_DIR/bin/uyap-convert" "/data/data/com.termux/files/usr/bin/uyap-convert"
    ln -sf "$SCRIPT_DIR/bin/a4-pdf-tools" "/data/data/com.termux/files/usr/bin/a4-pdf-tools"
fi

if [ -f "$SCRIPT_DIR/bin/naps2" ]; then
    ln -sf "$SCRIPT_DIR/bin/naps2" "$BIN_DIR/naps2"
    if [ -d "/data/data/com.termux/files/usr/bin" ]; then
        ln -sf "$SCRIPT_DIR/bin/naps2" "/data/data/com.termux/files/usr/bin/naps2"
    fi
fi

# 6. Thunar Sağ Tık Menüsünü (uca.xml) Güncelle
echo "[5/6] Thunar sağ tık eylemleri entegre ediliyor..."
mkdir -p "$HOME/.config/Thunar"

python3 - << 'EOF'
import os
import xml.etree.ElementTree as ET

uca_path = os.path.expanduser("~/.config/Thunar/uca.xml")
script_dir = os.environ.get("SCRIPT_DIR", os.path.dirname(os.path.abspath(__file__ if "__file__" in locals() else ".")))
template_path = os.path.join(script_dir, "desktop/uca_template.xml")

if not os.path.exists(uca_path):
    with open(template_path, "r", encoding="utf-8") as f_in, open(uca_path, "w", encoding="utf-8") as f_out:
        f_out.write(f_in.read())
    print("[BAŞARILI] uca.xml oluşturuldu.")
else:
    try:
        uca_tree = ET.parse(uca_path)
        uca_root = uca_tree.getroot()
        tmpl_tree = ET.parse(template_path)
        tmpl_root = tmpl_tree.getroot()

        # Var olan aksiyonları isim ve unique-id'ye göre indeksle
        existing_names = set()
        existing_ids = set()
        for act in uca_root.findall("action"):
            name = act.find("name")
            if name is not None and name.text:
                existing_names.add(name.text.strip())
            uid = act.find("unique-id")
            if uid is not None and uid.text:
                existing_ids.add(uid.text.strip())

        added = 0
        for act in tmpl_root.findall("action"):
            name = act.find("name")
            name_txt = name.text.strip() if (name is not None and name.text) else ""
            if name_txt and name_txt not in existing_names:
                uca_root.append(act)
                existing_names.add(name_txt)
                added += 1

        if added > 0:
            uca_tree.write(uca_path, encoding="UTF-8", xml_declaration=True)
            print(f"[BAŞARILI] {added} adet yeni sağ tık eylemi uca.xml dosyasına eklendi.")
        else:
            print("[BİLGİ] Sağ tık eylemleri zaten uca.xml dosyasında mevcut.")
    except Exception as e:
        print(f"[HATA] uca.xml güncellenemedi: {e}")
EOF

# 7. Thunar'ı Yeniden Başlat
echo "[6/6] Thunar dosya yöneticisi önbelleği yenileniyor..."
thunar -q 2>/dev/null || true
(DISPLAY=:0.0 thunar --daemon &) 2>/dev/null || true

echo ""
echo "=========================================================="
echo "  [TAMAMLANDI] Kurulum başarıyla tamamlandı!"
echo "  Sağ tık seçenekleriniz Thunar menüsünde aktiftir:"
echo "   1) Tümünü PDF'ye Dönüştür (A4)"
echo "   2) Tümünü Tek PDF'de Birleştir (A4)"
echo "   3) PDF'ye Çevir (UYAP)"
echo "   4) DOCX'e Çevir (UYAP)"
echo "   5) ODT'ye Çevir (UYAP)"
echo "=========================================================="
