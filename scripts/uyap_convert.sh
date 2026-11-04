#!/data/data/com.termux/files/usr/bin/bash
# ==========================================================
# Havelsan UYAP Resmi Headless Donusturucu
# Kullanim: bash scripts/uyap_convert.sh <input.udf> <pdf|odt> <output_path>
# ==========================================================
DIR="$(cd "$(dirname "$0")" && pwd)"
CP="$HOME/jars/*:$HOME/jars"

java -Djava.awt.headless=true -Xms32m -Xmx256m -cp "$CP" com.ckz.udemobile.UyapHeadlessConverter "$@"
