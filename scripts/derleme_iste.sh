#!/usr/bin/env bash
# Derleme ajanına istek gönderir / sonucu okur (derleme_ajani.ps1 ile eşleşir).
#   bash scripts/derleme_iste.sh iste [sürüm] [Yeniden|LinuxYok|AndroidYok ...]
#   bash scripts/derleme_iste.sh sonuc [kimlik]     # son (ya da verilen) isteğin özetini ve günlük sonunu yazar
set -euo pipefail
KOK="$(cd "$(dirname "$0")/.." && pwd)"; cd "$KOK"
case "${1:-}" in
  iste)
    surum="${2:-$(python3 -c 'import json;print(json.load(open("package.json"))["version"])')}"; shift 2 2>/dev/null || shift $#
    kimlik="$(date -u +%Y%m%d-%H%M%S)"
    secenek="[]"
    if [ $# -gt 0 ]; then secenek="$(printf '"%s",' "$@")"; secenek="[${secenek%,}]"; fi
    ana="$(git rev-parse origin/main 2>/dev/null || git rev-parse HEAD)"
    # Çalışma ağacına dokunmadan tek dosyalık commit (istek.json) üretip derleme-istek dalına yazar
    blob="$(printf '{"kimlik": "%s", "surum": "%s", "secenekler": %s, "main": "%s"}\n' "$kimlik" "$surum" "$secenek" "$ana" | git hash-object -w --stdin)"
    agac="$(printf '100644 blob %s\tistek.json\n' "$blob" | git mktree)"
    commit="$(GIT_AUTHOR_NAME=CanEditor GIT_AUTHOR_EMAIL=noreply@caneditor.local GIT_COMMITTER_NAME=CanEditor GIT_COMMITTER_EMAIL=noreply@caneditor.local \
              git commit-tree "$agac" -m "derleme isteği $kimlik")"
    git push --quiet --force "${UZAK:-origin}" "$commit:refs/heads/derleme-istek"
    echo "istek gönderildi: $kimlik (sürüm $surum, seçenekler $secenek)";;
  sonuc)
    git fetch --quiet --depth 1 "${UZAK:-origin}" +refs/heads/derleme-sonuc:refs/remotes/origin/derleme-sonuc
    kimlik="${2:-$(git ls-tree --name-only origin/derleme-sonuc sonuc/ | sed -n 's#sonuc/\(.*\)\.json#\1#p' | sort | tail -1)}"
    git show "origin/derleme-sonuc:sonuc/$kimlik.json"; echo "----- günlüğün sonu -----"
    git show "origin/derleme-sonuc:sonuc/$kimlik.log" | tail -n "${SATIR:-60}";;
  *) echo "kullanım: $0 iste [sürüm] [seçenek...] | sonuc [kimlik]"; exit 2;;
esac
