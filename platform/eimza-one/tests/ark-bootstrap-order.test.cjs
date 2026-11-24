const assert = require('node:assert/strict');
const fs = require('node:fs');

const source = fs.readFileSync('app/src/main/java/app/eimza/mobile/MainActivity.java', 'utf8');
const method = source.slice(source.indexOf('private void installArkSdkAndRespond'),
  source.indexOf('private static org.json.JSONObject arkSuccess'));

assert(!method.includes('evaluateJavascript'),
  'initialize must not evaluate the bundled client before ArkSignerJS processes the response');
assert(!method.includes('directInstall'), 'early direct-install path must stay removed');
assert(method.includes('ArkBootstrap.cypher(sdk, nonce)'),
  'full client resource must be delivered in the encrypted nonce2 bootstrap');
console.log('PASS: ArkSigner client is delivered after 3.x initialize processing via nonce2');
