#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
CP=$(printf '%s:' app/libs/*.jar)
CP=${CP%:}
if command -v cygpath >/dev/null 2>&1; then
  CP_WIN=$(cygpath -wp "$CP")
  TMP_WIN=$(cygpath -w "$TMP")
  java -m jdk.compiler/com.sun.tools.javac.Main -cp "$CP_WIN" -d "$TMP" app/src/main/java/app/eimza/mobile/SignerBackend.java app/src/main/java/app/eimza/mobile/CadesSupport.java app/src/main/java/app/eimza/mobile/EdevletCmsSupport.java app/src/main/java/app/eimza/mobile/AdaletEsyaConfig.java app/src/main/java/app/eimza/mobile/ArkBootstrap.java app/src/main/java/app/eimza/mobile/RsaDigestInfo.java tests/SigningHarness.java
  java -cp "$TMP_WIN;$CP_WIN" app.eimza.mobile.SigningHarness > "$TMP/bootstrap.txt"
else
  java -m jdk.compiler/com.sun.tools.javac.Main -cp "$CP" -d "$TMP" app/src/main/java/app/eimza/mobile/SignerBackend.java app/src/main/java/app/eimza/mobile/CadesSupport.java app/src/main/java/app/eimza/mobile/EdevletCmsSupport.java app/src/main/java/app/eimza/mobile/AdaletEsyaConfig.java app/src/main/java/app/eimza/mobile/ArkBootstrap.java app/src/main/java/app/eimza/mobile/RsaDigestInfo.java tests/SigningHarness.java
  java -cp "$TMP:$CP" app.eimza.mobile.SigningHarness > "$TMP/bootstrap.txt"
fi

if command -v node >/dev/null 2>&1; then
  node - "$TMP/bootstrap.txt" <<'JS'
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const [nonce,encrypted]=fs.readFileSync(process.argv[2],'utf8').trim().split('\n');
function PWSigner(){};const c=vm.createContext({PWSigner,Base64:{encode:s=>Buffer.from(s,'utf8').toString('base64')}});
vm.runInContext(fs.readFileSync('app/src/main/assets/arksigner-sdk.js','utf8'),c);
assert.equal(c.PWSigner.prototype.isnonce(nonce),true);
assert.equal(c.PWSigner.prototype.cypher('bootstrap-test',nonce),encrypted);
console.log('PASS: Java bootstrap nonce and XOR compatible with supplied ArkSigner JavaScript');
JS
else
  echo "PASS: Java CAdES and e-Devlet CMS signing harness passed (Node.js check skipped)"
fi
