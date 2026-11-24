#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
javac -encoding UTF-8 -d "$TMP" app/src/main/java/app/eimza/mobile/RsaDigestInfo.java tests/TokenIdentificationHarness.java
java -cp "$TMP" app.eimza.mobile.TokenIdentificationHarness
