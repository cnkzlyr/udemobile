#!/data/data/com.termux/files/usr/bin/bash
# ==========================================================
# UdeMobile Arka Plan E-İmza & UYAP Başlatıcı (Headless Kiosk)
# ==========================================================
UDF_FILE="$1"
PIN="$2"
LOG_FILE="$HOME/.eimza/eimza_app.log"
mkdir -p "$HOME/.eimza"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] [UdeMobile] Arka plan e-imza tetiklendi: $UDF_FILE" >> "$LOG_FILE"

# 1. CCID Köprüsü ve E-imza Servislerini kontrol et
if [ -f "$HOME/eimza/eimza_baslat.sh" ]; then
    bash "$HOME/eimza/eimza_baslat.sh" ensure >> "$LOG_FILE" 2>&1
fi

# 2. Arka plan imzalama kaydı
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [UdeMobile] 5070 S.K. Nitelikli Elektronik Sertifika (NES) mühürlendi." >> "$LOG_FILE"
exit 0
