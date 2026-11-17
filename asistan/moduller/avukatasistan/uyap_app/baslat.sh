#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# ⚖️ UYAP AVUKAT MOBİL - YEREL SUNUCU BAŞLATICI
# ==============================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "========================================================================"
echo "⚖️  UYAP AVUKAT MOBİL - REST API & PWA SUNUCUSU"
echo "========================================================================"

PORT="${1:-8080}"
echo "🚀 Sunucu port $PORT üzerinde başlatılıyor..."
python3 "$DIR/server.py" --port "$PORT"
