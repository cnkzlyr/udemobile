'use strict';
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const source = fs.readFileSync('app/src/main/assets/edevlet-bridge.js', 'utf8');
const clientSource = fs.readFileSync(
  'app/src/main/java/app/eimza/mobile/EdevletClient.java', 'utf8');
const activitySource = fs.readFileSync(
  'app/src/main/java/app/eimza/mobile/MainActivity.java', 'utf8');
let delivered = null;
const captcha = {
  id: 'guvenlikKodu', name: 'securityCode', value: 'ZX90ab', textContent: '',
  getAttribute() { return ''; }
};
const labelled = {
  id: 'islemKodu', name: 'transactionCode', value: 'aB12cD3456', textContent: '',
  getAttribute() { return ''; }
};
const document = {
  readyState: 'complete',
  documentElement: {},
  body: { innerText: 'Elektronik imza işlem kodu: aB12cD3456' },
  querySelectorAll() { return [captcha, labelled]; },
  addEventListener() {}
};
class MutationObserver { observe() {} }
const window = {
  EimzaNative: { edevletTransactionCode(origin, code) { delivered = {origin, code}; } }
};
const context = { window, document, MutationObserver, location: {origin: 'https://giris.turkiye.gov.tr'}, setInterval() {}, setTimeout() {} };
vm.runInNewContext(source, context);
assert.deepStrictEqual(delivered, {origin: 'https://giris.turkiye.gov.tr', code: 'aB12cD3456'});

let copiedDelivery = null;
const copiedInput = {
  id: 'generated-value', name: '', value: 'Zx81Qa729B', textContent: '', className: '',
  getAttribute() { return ''; }, closest() { return null; }
};
const captchaInput = {
  id: 'captcha', name: 'securityCode', value: 'BAD999', textContent: '', className: '',
  getAttribute() { return ''; }, closest() { return null; }
};
const copyButton = {
  id: '', name: '', value: '', textContent: 'Kopyala', className: 'btn-copy',
  getAttribute(name) { return name === 'data-clipboard-target' ? '#generated-value' : ''; },
  closest() { return null; }
};
const clipboardDocument = {
  readyState: 'complete', documentElement: {},
  body: { innerText: 'Elektronik imza işlem kodu hazır' },
  querySelector(selector) { return selector === '#generated-value' ? copiedInput : null; },
  querySelectorAll(selector) {
    return selector.includes('data-clipboard-text') ? [copyButton] : [captchaInput];
  },
  addEventListener() {}
};
const clipboardWindow = {
  EimzaNative: {
    edevletTransactionCode(origin, code) { copiedDelivery = {origin, code}; }
  }
};
vm.runInNewContext(source, {
  window: clipboardWindow, document: clipboardDocument, MutationObserver,
  location: {origin: 'https://giris.turkiye.gov.tr'}, setInterval() {}, setTimeout() {}
});
assert.deepStrictEqual(copiedDelivery,
  {origin: 'https://giris.turkiye.gov.tr', code: 'Zx81Qa729B'},
  'copy control must deliver its target value without confusing captcha');
clipboardWindow.__eimzaDetectEdevletCode();
assert.deepStrictEqual(copiedDelivery,
  {origin: 'https://giris.turkiye.gov.tr', code: 'Zx81Qa729B'},
  'the same DOM code must not start a duplicate flow');

let transIdDelivery = null;
const transIdNode = {
  id: 'transid', name: '', className: '', textContent: '881642', innerText: '881642',
  getAttribute() { return ''; }, closest() { return null; }
};
const transIdDocument = {
  readyState: 'complete', documentElement: {}, body: {innerText: ''},
  getElementById(id) { return id === 'transid' ? transIdNode : null; },
  querySelectorAll() { return []; }, addEventListener() {}
};
vm.runInNewContext(source, {
  window: {EimzaNative: {edevletTransactionCode(origin, code) {
    transIdDelivery = {origin, code};
  }}},
  document: transIdDocument, MutationObserver,
  location: {origin: 'https://giris.turkiye.gov.tr'}, setInterval() {}, setTimeout() {}
});
assert.deepStrictEqual(transIdDelivery,
  {origin: 'https://giris.turkiye.gov.tr', code: '881642'},
  'the exact #transid content must start the automatic flow');

assert.strictEqual(window.__eimzaEdevletSessionCode, undefined,
  'the browser page polls its own session; no invented session-code form must be submitted');
assert(clientSource.includes('response.optString("fileInput", "")'),
  'e-Devlet must sign fileInput');
assert(!clientSource.includes('String content = response.optString("sozlesme", "")'),
  'human-readable sozlesme must never be signed');
assert(clientSource.includes('response.optJSONArray("sonuc")'),
  'success must require the official session result');
assert(activitySource.includes('SSO sayfa tanısı:'),
  'OBS callback must report its visible error state without logging token values');
assert(activitySource.includes('addDocumentStartJavaScript(webView, obsSsoDiagnosticsHook'),
  'OBS callback errors must be captured before page scripts execute');
assert(activitySource.includes('errorContext:c'),
  'OBS syntax diagnostics must include redacted source context');
assert(activitySource.includes('serverMessage:sm'),
  'OBS malformed inline error message must be extracted safely');
console.log('PASS: e-Devlet bridge reads the copy-code DOM, ignores captcha, and leaves browser polling intact');
