#!/bin/bash
# ==============================================================================
# E-İmza & AKİS Sürücü Yapılandırma Betiği
# ==============================================================================

set -e

echo "=== Linux E-İmza Sürücü Kurulumu ==="

if command -v dnf &>/dev/null; then
    echo "Fedora paketleri kontrol ediliyor..."
    sudo dnf install -y pcsc-lite pcsc-lite-ccid pcsc-lite-libs opensc || true
elif command -v apt-get &>/dev/null; then
    echo "Debian/Ubuntu paketleri kontrol ediliyor..."
    sudo apt-get update && sudo apt-get install -y pcscd pcsc-tools libccid opensc || true
elif command -v pacman &>/dev/null; then
    echo "Arch Linux paketleri kontrol ediliyor..."
    sudo pacman -S --noconfirm pcsclite ccid opensc || true
fi

echo "pcscd servisi başlatılıyor..."
sudo systemctl enable --now pcscd || true

echo "Udev kuralları yükleniyor..."
sudo cp -f "$(dirname "$0")/99-eimza-smartcard.rules" /etc/udev/rules.d/ 2>/dev/null || true
sudo udevadm control --reload-rules && sudo udevadm trigger || true

echo "Tamamlandı. Takılı kartları görmek için: opensc-tool -l veya pcsc_scan"
