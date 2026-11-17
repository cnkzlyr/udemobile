// asistan.js süre motoru, avukatasistan (Python) referansıyla birebir aynı sonucu vermeli.
// Çalıştırma: node --test tests/  (Python 3 gerekir)
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { execFileSync } = require('node:child_process');

process.env.TZ = 'Europe/Istanbul';
const kok = path.resolve(__dirname, '..');
const ctx = { window: {}, console };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(kok, 'frontend/public/asistan.js'), 'utf8'), ctx);
const CA = ctx.window.CanAsistan;

test('süre hesabı Python referansıyla aynı (600 rastgele vaka)', () => {
  const ref = JSON.parse(execFileSync(process.env.PYTHON || 'python3', [path.join(kok, 'tests/sure_referans.py')], { encoding: 'utf8' }));
  assert.ok(ref.length >= 600);
  for (const r of ref) {
    const [t, s] = r.gelis.split('T');
    const [y, a, g] = t.split('-').map(Number); const [hh, mm] = s.split(':').map(Number);
    const j = CA.sureHesapla(new Date(y, a - 1, g, hh, mm), r.merci);
    const bilgi = `${r.gelis} | ${r.merci}`;
    assert.strictEqual(j.gun, r.gun, bilgi);
    assert.strictEqual(j.teblig_str, r.teblig, bilgi);
    assert.strictEqual(j.d7_str, r.d7, bilgi);
    assert.strictEqual(j.d14_str, r.d14, bilgi);
    assert.strictEqual(j.d30_str, r.d30, bilgi);
    assert.strictEqual(j.hedef_str, r.hedef, bilgi);
    assert.strictEqual(j.etiket, r.etiket, bilgi);
  }
});

test('son gün hiçbir zaman hafta sonuna düşmez', () => {
  for (let i = 0; i < 400; i++) {
    const j = CA.sureHesapla(new Date(2026, 0, 1 + i, 10, 0), 'Asliye Hukuk');
    assert.ok(![0, 6].includes(j.hedef.getDay()));
    assert.strictEqual(j.hedef.getHours(), 17);
  }
});

test('tatil uyarıları tarihi değiştirmez, yalnızca bilgi verir', () => {
  assert.ok(CA.tatilUyarilari(new Date(2026, 9, 29), 'Asliye Hukuk').some(u => u.includes('Cumhuriyet')));
  assert.ok(CA.tatilUyarilari(new Date(2026, 4, 28), 'Asliye Hukuk').some(u => u.includes('Kurban')));
  assert.ok(CA.tatilUyarilari(new Date(2026, 7, 10), 'Asliye Hukuk').some(u => u.includes('adli tatil')));
  assert.strictEqual(CA.tatilUyarilari(new Date(2026, 7, 10), 'Asliye Ceza Mahkemesi').length, 0);
  assert.strictEqual(CA.tatilUyarilari(new Date(2026, 10, 18), 'Asliye Hukuk').length, 0);
});

test('A4 yerleşimi: oran korunur, 5 mm kenar içinde kalır, yatay görsel yatay sayfa', () => {
  const dik = CA.a4Yerlesim(1000, 2000);
  assert.strictEqual(dik.yon, 'portrait');
  assert.ok(Math.abs(dik.w / dik.h - 0.5) < 1e-9);
  assert.ok(dik.x >= 14.17 - 1e-6 && dik.y >= 14.17 - 1e-6);
  const yatay = CA.a4Yerlesim(3000, 1000);
  assert.strictEqual(yatay.yon, 'landscape');
  assert.ok(yatay.sw > yatay.sh);
  assert.ok(yatay.x + yatay.w <= yatay.sw - 14.17 + 1e-6);
});
