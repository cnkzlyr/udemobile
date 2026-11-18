// hukuk_hesap.js — hayfahukuk hesaplayıcılarıyla aynı kurallar; beklenen değerler elle hesaplandı.
const test = require('node:test');
const assert = require('node:assert');
// frontend/package.json "type":"module" olduğundan dosya tarayıcıdaki gibi (window) yüklenir
const ctx = { window: {} };
require('node:vm').runInNewContext(require('node:fs').readFileSync(require('node:path').join(__dirname, '../frontend/public/hukuk_hesap.js'), 'utf8'), ctx);
const H = ctx.window.HukukHesap;
const yakin = (a, b, m) => assert.ok(Math.abs(a - b) < 0.01, `${m}: ${a} ≠ ${b}`);

test('AAÜT nispi dilimler', () => {
  yakin(H.aautNispi(1000000).toplam, 800000 * 0.16 + 200000 * 0.15, '1 milyon');
  yakin(H.aautNispi(30000000).toplam,
    800000 * .16 + 800000 * .15 + 1600000 * .14 + 1600000 * .13 + 2400000 * .11 + 3200000 * .08 + 4000000 * .05 + 4800000 * .03 + 5600000 * .02 + 5200000 * .01, '30 milyon (son dilim)');
});

test('vekâlet ücreti: maktu alt sınır, dava değeri üst sınır, icra eşiği, yarısı', () => {
  assert.strictEqual(H.vekalet({ tur: 'maktu', mahkeme: 'agir-ceza' }).ucret, 86000);
  assert.strictEqual(H.vekalet({ tur: 'nispi', mahkeme: 'asliye', deger: 100000 }).ucret, 62000);   // 16.000 < maktu
  assert.strictEqual(H.vekalet({ tur: 'nispi', mahkeme: 'asliye', deger: 50000 }).ucret, 50000);    // değeri geçemez
  yakin(H.vekalet({ tur: 'nispi', mahkeme: 'asliye', deger: 1000000 }).ucret, 158000, 'nispi');
  assert.strictEqual(H.vekalet({ tur: 'icra', deger: 50000 }).ucret, 12500);
  assert.strictEqual(H.vekalet({ tur: 'icra', deger: 10000 }).ucret, 10000);
  yakin(H.vekalet({ tur: 'icra', deger: 100000 }).ucret, 16000, 'icra nispi');
  assert.strictEqual(H.vekalet({ tur: 'maktu', mahkeme: 'asliye', yarisi: true }).ucret, 31000);
  assert.ok(H.vekalet({ tur: 'nispi', mahkeme: 'asliye' }).hata);
});

test('faiz: kanuni oran 31.07.2026 değişimi dönemlere bölünür', () => {
  const r = H.faiz({ anapara: 100000, bas: '2026-01-01', bit: '2026-12-31', tur: 'kanuni' });
  assert.strictEqual(r.tablo.length, 2);
  assert.strictEqual(JSON.stringify(r.tablo.map(t => [t.gun, t.oran])), JSON.stringify([[211, 24], [153, 31]]));
  yakin(r.faiz, 100000 * .24 * 211 / 365 + 100000 * .31 * 153 / 365, 'kanuni faiz');
  const t = H.faiz({ anapara: 100000, bas: '2026-01-01', bit: '2026-04-11', tur: 'ttk', giderim: true });
  yakin(t.faiz, 100000 * .43 * 100 / 365 + 2020, 'TTK 1530 + giderim');
  assert.ok(H.faiz({ anapara: 1000, bas: '2020-01-01', bit: '2021-01-01', tur: 'avans' }).hata);   // kayıt öncesi
  assert.ok(H.faiz({ anapara: 1000, bas: '2026-02-01', bit: '2026-01-01', tur: 'kanuni' }).hata);
});

test('harç: dava açılışı, icra, kanun yolu', () => {
  yakin(H.harc({ tur: 'dava', mahkeme: 'asliye', deger: 100000 }).toplam, 732 + 100000 * 0.06831 * 0.25, 'nispi dava');
  yakin(H.harc({ tur: 'dava', mahkeme: 'sulh', deger: 0, vekaletname: true }).toplam, 335.20 + 732 + 104, 'maktu dava');
  yakin(H.harc({ tur: 'icra', deger: 100000 }).toplam, 732 + 500, 'icra');
});

test('serbest meslek makbuzu ve CMK makbuzu', () => {
  const s = H.smm({ tutar: 10000, giris: 'brut', sorumlu: true });
  yakin(s.tahsil, 10000 - 2000 + 2000, 'brüt 10.000');
  yakin(H.smm({ tutar: 8000, giris: 'net', sorumlu: true }).brut, 10000, 'net → brüt');
  yakin(H.smm({ tutar: 10000, giris: 'tahsil', sorumlu: true }).brut, 10000, 'tahsil → brüt');
  // Ağır ceza 12.387 TL > 12.000 sınırı: 5/10 KDV tevkifatı
  yakin(H.cmkMakbuz({ kalem: 'agir', adet: 1 }).odenen, 12387 / 1.2 - 12387 / 1.2 * 0.2 * 0.5, 'CMK ağır ceza');
  yakin(H.cmkMakbuz({ kalem: 'sorusturma', adet: 1 }).odenen, 4027 / 1.2, 'CMK soruşturma (tevkifatsız)');
});

test('infaz ve ceza artırım/indirim hesaplayıcıları', () => {
  const inf = H.infaz({ yil: 4, ay: 0, gun: 0, oran: '1/2', mahsupGun: 30, denetimliYil: 1 });
  assert.strictEqual(inf.toplamGun, 1460);
  assert.strictEqual(inf.kosulluGun, 730);
  assert.strictEqual(inf.cezaevindeYatacak, 335);
  const cz = H.ceza({ yil: 2, ay: 0, gun: 0, adimlar: [{ tip: 'artir', pay: 1, payda: 4 }, { tip: 'indir', pay: 1, payda: 6 }] });
  assert.strictEqual(cz.sonucGun, 760);
});
