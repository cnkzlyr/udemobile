#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
: "${DEX2C_DIR:?DEX2C_DIR must point to an audited rufusin/Dex2C checkout}"

GRADLE_CMD=${GRADLE_CMD:-gradle}
INPUT="$ROOT/app/build/outputs/apk/release/app-release-unsigned.apk"
OUTPUT="$ROOT/app/build/outputs/apk/release/app-release-dex2c.apk"

cd "$ROOT"
"$GRADLE_CMD" assembleRelease --no-daemon
test -f "$INPUT" || { echo "Missing R8 release APK: $INPUT" >&2; exit 1; }
test -f "$DEX2C_DIR/dcc.py" || { echo "Missing $DEX2C_DIR/dcc.py" >&2; exit 1; }

cp "$DEX2C_DIR/filter.txt" "$DEX2C_DIR/filter.txt.eimza-backup" 2>/dev/null || true
trap 'if test -f "$DEX2C_DIR/filter.txt.eimza-backup"; then mv "$DEX2C_DIR/filter.txt.eimza-backup" "$DEX2C_DIR/filter.txt"; fi' EXIT
cp "$ROOT/tools/dex2c-filter.txt" "$DEX2C_DIR/filter.txt"

cd "$DEX2C_DIR"
python3 dcc.py -a "$INPUT" -o "$OUTPUT"

echo "Dex2C output: $OUTPUT"
echo "Sign this APK with the Play upload key, then run apksigner verify --verbose."

