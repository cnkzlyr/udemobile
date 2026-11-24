#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
TASK_TMP=$(mktemp -d)
trap 'rm -rf "$TASK_TMP"' EXIT
java -m jdk.compiler/com.sun.tools.javac.Main -d "$TASK_TMP" \
  app/src/main/java/app/eimza/mobile/PortalOrigins.java tests/PortalOriginsHarness.java
java -cp "$TASK_TMP" app.eimza.mobile.PortalOriginsHarness
