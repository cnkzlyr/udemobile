#!/data/data/com.termux/files/usr/bin/bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CP="$DIR:/data/data/com.termux/files/home/jars/*"
exec java -Xmx512m -Djava.awt.headless=true \
    --add-opens=java.base/java.util=ALL-UNNAMED \
    --add-opens=java.base/java.lang=ALL-UNNAMED \
    --add-opens=java.desktop/java.awt=ALL-UNNAMED \
    --add-opens=java.desktop/javax.swing=ALL-UNNAMED \
    -cp "$CP" uyap.UdfBatchPdfConverter "$@"
