#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
CP=app/libs/akiscif-3.3.18.jar:app/libs/bcprov-jdk18on-1.78.jar:app/libs/slf4j-api-2.0.17.jar
if command -v cygpath >/dev/null 2>&1; then
  CP_WIN=$(cygpath -wp "$CP")
  TMP_WIN=$(cygpath -w "$TMP")
  java -m jdk.compiler/com.sun.tools.javac.Main -cp "$CP_WIN" -d "$TMP" app/src/main/java/app/eimza/mobile/AkisPkcs15.java app/src/main/java/app/eimza/mobile/AkisV25Signing.java tests/AkisV25Harness.java
  java -cp "$TMP_WIN;$CP_WIN" app.eimza.mobile.AkisV25Harness
else
  java -m jdk.compiler/com.sun.tools.javac.Main -cp "$CP" -d "$TMP" app/src/main/java/app/eimza/mobile/AkisPkcs15.java app/src/main/java/app/eimza/mobile/AkisV25Signing.java tests/AkisV25Harness.java
  java -cp "$TMP:$CP" app.eimza.mobile.AkisV25Harness
fi
