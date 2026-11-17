#!/usr/bin/env bash
# Java bilesenlerini derler ve birim testlerini calistirir. Gerekenler: JDK 11+ (UYAP jar'lari GEREKMEZ).
set -eu
KOK="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
find "$KOK/bilesenler/java" "$KOK/testler/java" -name '*.java' > "$T/kaynaklar.txt"
echo "$KOK/bilesenler/eimza/TermuxCcidProvider.java" >> "$T/kaynaklar.txt"
javac --release 11 -encoding UTF-8 -Xlint:-options -d "$T/out" @"$T/kaynaklar.txt"
java -cp "$T/out" uyaptermux.BirimTestleri
bash "$KOK/bilesenler/eimza/agent-src/derle.sh" >/dev/null
unzip -l "$KOK/bilesenler/eimza/eimza-agent.jar" | grep -q 'gui/e.class' && echo "eimza-agent.jar derlendi"
rm -f "$KOK/bilesenler/eimza/eimza-agent.jar"
