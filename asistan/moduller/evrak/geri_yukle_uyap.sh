#!/data/data/com.termux/files/usr/bin/bash
# =============================================================================
#  UYAP Avukat Portal Evrak İndirici - Otomatik Geri Yükleme (Restore) Scripti
# =============================================================================

set -e

BACKUP_TAR="/sdcard/Download/uyap_indirici_yedek.tar.gz"
TARGET_DIR="/data/data/com.termux/files/home/uyap-evrak-indirici"
HOME_DIR="/data/data/com.termux/files/home"

echo ""
echo "=================================================================="
echo "    UYAP Avukat Portal İndirici - Yedekten Geri Yükleme           "
echo "=================================================================="
echo ""

if [ ! -f "$BACKUP_TAR" ]; then
    echo "[x] HATA: Yedek dosyası bulunamadı!"
    echo "    Aranan yol: $BACKUP_TAR"
    echo "    Lütfen yedek dosyasının Downloads klasöründe olduğundan emin olun."
    exit 1
fi

echo "[*] Yedek dosyası doğrulandı: $BACKUP_TAR"

# Eğer hedef dizin mevcutsa güvenlik amacıyla önceki halini .bak olarak sakla
if [ -d "$TARGET_DIR" ]; then
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BAK_DIR="${TARGET_DIR}_onceki_${TIMESTAMP}"
    echo "[!] Mevcut kurulum klasörü bulundu."
    echo "[*] Güvenlik amacıyla mevcut klasör şuraya yedekleniyor:"
    echo "    $BAK_DIR"
    mv "$TARGET_DIR" "$BAK_DIR"
fi

echo "[*] Yedek arşivi açılıyor..."
cd "$HOME_DIR"
tar -xzf "$BACKUP_TAR"

if [ -d "$TARGET_DIR" ]; then
    chmod +x "$TARGET_DIR"/*.sh "$TARGET_DIR"/*.py 2>/dev/null || true
    echo ""
    echo "=================================================================="
    echo "  [✓] TEBRİKLER! Geri yükleme başarıyla tamamlandı."
    echo "=================================================================="
    echo ""
    echo "  Yeniden başlatmak için Termux'ta şu komutu çalıştırabilirsiniz:"
    echo ""
    echo "    cd ~/uyap-evrak-indirici && ./baslat_termux.sh"
    echo ""
    echo "=================================================================="
else
    echo "[x] HATA: Arşiv açıldı fakat $TARGET_DIR klasörü oluşmadı."
    exit 1
fi
