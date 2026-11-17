#!/data/data/com.termux/files/usr/bin/bash
# =============================================================================
#  UYAP Avukat Portal İndirici - Android / Termux Otomatik Kurulum Betiği
# =============================================================================

set -e

echo ""
echo "=================================================================="
echo "  UYAP Avukat Portal İndirici - Termux Kurulumu Başlatılıyor      "
echo "=================================================================="
echo ""

# 1. Depoları ve temel paketleri güncelle
echo "[1/5] Paket listeleri ve depolar güncelleniyor..."
pkg update -y
pkg install -y python python-pip git tur-repo x11-repo

# 2. Chromium ve Tkinter kurulumu
echo "[2/5] Chromium ve Python modülleri kuruluyor..."
pkg install -y chromium
pkg install -y python-tkinter termux-x11-nightly || true

# 3. Python Bağımlılıkları
echo "[3/5] Python kütüphaneleri (requests, websocket-client) yükleniyor..."
pip install --break-system-packages -r requirements.txt || pip install -r requirements.txt || pip install requests websocket-client

# 4. Telefon Hafızasına Erişim İzni
echo "[4/5] Telefon dahili depolama erişim izni kontrol ediliyor..."
if [ ! -d "$HOME/storage" ]; then
    echo "(Lütfen ekranda çıkacak izne 'İzin Ver' / 'Allow' deyiniz)"
    termux-setup-storage || true
else
    echo "  ✓ Depolama erişimi zaten tanımlı (~/storage mevcut)."
fi

# 5. Çalıştırma İzinleri
echo "[5/5] Betik çalıştırma izinleri ayarlanıyor..."
chmod +x baslat_termux.sh baslat.sh uyap_indirici.py

echo ""
echo "=================================================================="
echo "  ✓ Kurulum Başarıyla Tamamlandı!                                 "
echo "=================================================================="
echo ""
echo "Programı çalıştırmak için:"
echo "  ./baslat_termux.sh"
echo ""
