#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
java -m jdk.compiler/com.sun.tools.javac.Main \
  --patch-module java.smartcardio=app/src/main/java/javax/smartcardio -d "$TMP" \
  app/src/main/java/javax/smartcardio/ATR.java tests/AtrHarness.java
java --patch-module java.smartcardio="$TMP" -cp "$TMP" AtrHarness
