#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
TASK_TMP=$(mktemp -d)
trap 'rm -rf "$TASK_TMP"' EXIT
CP=app/libs/bcprov-jdk18on-1.78.jar
if command -v cygpath >/dev/null 2>&1; then
  CP_WIN=$(cygpath -wp "$CP")
  TMP_WIN=$(cygpath -w "$TASK_TMP")
  java -m jdk.compiler/com.sun.tools.javac.Main -cp "$CP_WIN" -d "$TASK_TMP" app/src/main/java/app/eimza/mobile/AdaletDeviceInfo.java tests/AdaletDeviceInfoHarness.java
  java -cp "$TMP_WIN;$CP_WIN" app.eimza.mobile.AdaletDeviceInfoHarness
else
  java -m jdk.compiler/com.sun.tools.javac.Main -cp "$CP" -d "$TASK_TMP" app/src/main/java/app/eimza/mobile/AdaletDeviceInfo.java tests/AdaletDeviceInfoHarness.java
  java -cp "$TASK_TMP:$CP" app.eimza.mobile.AdaletDeviceInfoHarness
fi
