/**
 * CanEditor — Hukuki hesaplama motoru (vekâlet ücreti, faiz, harç, serbest meslek makbuzu, CMK makbuzu).
 *
 * Kaynak: hayfahukuk sitesinin hesaplayıcıları (assets/js/hesap.js) ve 2026 tarifeleri (inc/tarifeler.php);
 * hesap kuralları birebir aynıdır. Saf işlevlerdir, DOM'a dokunmaz: her platformda internetsiz çalışır.
 * Her hesap [{ad, tutar, ref, vurgu}] satırları ve notlar döndürür; arayüz (asistan.js → Hesaplamalar) çizer.
 *
 * TARİFELER YILLIK GÜNCELLENİR. Güncelleme: aşağıdaki TARIFE nesnesi (hayfahukuk inc/tarifeler.php ile aynı tutun).
 */
(function () {
  'use strict';

  const TARIFE = {
    surum: '2026',
    kaynak: {
      aaut: 'AAÜT 2026 (RG 03.11.2026)', cmk: 'CMK 2026 Ödeme Tarifesi (RG 08.01.2026)',
      harc: '492 s.K. (1) s. Tarife — 2026 tutarları', avans: 'TCMB avans faizi (son: RG 20.12.2025)',
      kanuni: '3095 s.K. m.1 — %31 (RG 31.07.2026)', ttk1530: 'TTK 1530 — 2026 (RG 02.01.2026)'
    },
    aautMaktu: {
      'icra-takip': ['İcra dairelerinde yapılan takipler', 12500],
      'icra-mah-is': ['İcra mahkemelerinde takip edilen işler', 15000],
      'icra-mah-dava': ['İcra mahkemelerinde dava ve duruşmalı işler', 23000],
      'tahliye-icra': ['Tahliyeye ilişkin icra takipleri', 26000],
      'icra-ceza': ['İcra mahkemelerinde ceza işleri', 20000],
      'sorusturma': ['Ceza soruşturma evresi', 15000],
      'sulh-hukuk': ['Sulh hukuk mahkemeleri', 40000],
      'sulh-ceza': ['Sulh ceza / infaz hâkimlikleri', 23000],
      'asliye': ['Asliye mahkemeleri (hukuk, iş, aile, ticaret, ceza)', 62000],
      'tuketici': ['Tüketici mahkemeleri', 30000],
      'fsmh': ['Fikri ve sınai haklar mahkemeleri', 70000],
      'agir-ceza': ['Ağır ceza mahkemeleri', 86000],
      'cocuk': ['Çocuk mahkemeleri', 62000],
      'cocuk-agir': ['Çocuk ağır ceza mahkemeleri', 86000],
      'idare-durusmasiz': ['İdare ve vergi mahkemeleri (duruşmasız)', 40000],
      'idare-durusmali': ['İdare ve vergi mahkemeleri (duruşmalı)', 52000],
      'bam-ilk': ['BAM / BİM — ilk derece davaları', 45000],
      'bam-istinaf-1': ['BAM / BİM — istinaf, bir duruşmalı', 28000],
      'bam-istinaf-2': ['BAM / BİM — istinaf, birden fazla duruşma / keşif', 55000],
      'yargitay-ilk': ["Yargıtay'da ilk derece davaları", 85000],
      'danistay-durusmasiz': ["Danıştay'da ilk derece (duruşmasız)", 50000],
      'danistay-durusmali': ["Danıştay'da ilk derece (duruşmalı)", 80000],
      'temyiz-durusma': ['Yargıtay / Danıştay / Sayıştay temyiz duruşması', 50000],
      'aym-bb-durusmasiz': ['AYM bireysel başvuru (duruşmasız)', 55000],
      'aym-bb-durusmali': ['AYM bireysel başvuru (duruşmalı)', 100000]
    },
    // [dilim tutarı (null = kalan), oran] — AAÜT Üçüncü Kısım
    aautNispi: [[800000, 0.16], [800000, 0.15], [1600000, 0.14], [1600000, 0.13], [2400000, 0.11],
      [3200000, 0.08], [4000000, 0.05], [4800000, 0.03], [5600000, 0.02], [null, 0.01]],
    aautIcraEsik: 78125,
    cmk: {
      'sorusturma': ['Soruşturma evresi', 4027], 'sulh-ceza': ['Sulh ceza hâkimliği', 6273],
      'asliye': ['Asliye ceza mahkemesi', 6904], 'seri': ['Asliye ceza — seri muhakeme', 2883],
      'agir': ['Ağır ceza mahkemesi', 12387], 'cocuk': ['Çocuk mahkemesi', 6904], 'cocuk-agir': ['Çocuk ağır ceza mahkemesi', 12387],
      'diger': ['İcra ceza / FSHM ceza / infaz hâkimliği', 6904], 'bam': ['Bölge adliye (duruşmalı)', 12387], 'yargitay': ["Yargıtay (duruşmalı)", 13945]
    },
    harc: {
      basvurma_sulh: 335.20, basvurma_asliye: 732.00, basvurma_ust: 1124.50, maktu_karar: 732.00, tedbir_haciz: 1206.00,
      istinaf: 2002.00, temyiz: 3608.50, kesif: 5188.00, vekalet_suret: 104.00, nispi_karar: 0.06831, pesin_oran: 0.25,
      icra_basvurma: 732.00, icra_pesin: 0.005, tahsil_hacizden_once: 0.0455, tahsil_satistan_once: 0.0910, tahsil_satis: 0.1138, cezaevi: 0.02
    },
    avans: { '2023-12-01': 41.75, '2023-12-23': 44.25, '2024-04-01': 51.75, '2024-12-28': 49.25, '2025-03-08': 44.25, '2025-09-17': 42.25, '2025-12-20': 39.75 },
    kanuni: { '2006-01-01': 9.0, '2024-06-01': 24.0, '2026-07-31': 31.0 },
    ttk1530: { yil: 2026, oran: 43.00, giderim: 2020.00 },
    smm: { kdv: 0.20, stopaj: 0.20, tevkifat_sinir: 12000, tevkifat_oran: 0.5 }
  };

  const yuvarla = v => Math.round(v * 100) / 100;
  const TL = v => yuvarla(v).toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' TL';
  const satir = (ad, tutar, ref, vurgu) => ({ ad, tutar, ref: ref || '', vurgu: !!vurgu });
  const D = s => { const p = String(s).split('-'); return new Date(+p[0], +p[1] - 1, +p[2]); };
  const gunFarki = (a, b) => Math.round((b - a) / 86400000);

  /** AAÜT nispi ücret (Üçüncü Kısım dilimleri). */
  function aautNispi(tutar) {
    let kalan = tutar, toplam = 0, alt = 0;
    const adim = [];
    for (const [dilimTutari, oran] of TARIFE.aautNispi) {
      if (kalan <= 0) break;
      const dilim = dilimTutari === null ? kalan : Math.min(kalan, dilimTutari);
      const u = dilim * oran;
      toplam += u; kalan -= dilim;
      adim.push(satir(`${TL(alt)} – ${TL(alt + dilim)} × %${(oran * 100).toLocaleString('tr-TR')}`, u, ''));
      alt += dilim;
    }
    return { toplam, adim };
  }

  /** Asgari vekâlet ücreti. tur: 'maktu' | 'nispi' | 'icra'; yarisi: ön inceleme tutanağından önce sona erdi (m.7/1). */
  function vekalet({ tur, mahkeme, deger, yarisi }) {
    const m = TARIFE.aautMaktu[mahkeme] || ['', 0], maktu = m[1], satirlar = [];
    let ucret = 0;
    if (tur === 'maktu') {
      ucret = maktu;
      satirlar.push(satir(m[0], maktu, 'AAÜT İkinci Kısım İkinci Bölüm'));
    } else if (tur === 'nispi') {
      if (!(deger > 0)) return { hata: 'Dava değerini girin.' };
      const n = aautNispi(deger);
      satirlar.push(...n.adim, satir('Nispi ücret toplamı', n.toplam, 'AAÜT Üçüncü Kısım'));
      ucret = Math.max(n.toplam, maktu);
      if (n.toplam < maktu) satirlar.push(satir('Mahkeme maktu ücretinin altında kalamaz → ' + m[0], maktu, 'AAÜT m.13/1'));
      if (ucret > deger) { ucret = deger; satirlar.push(satir('Hükmedilen ücret, kabul/ret miktarını geçemez', deger, 'AAÜT m.13/2')); }
    } else {
      if (!(deger > 0)) return { hata: 'Takip miktarını girin.' };
      const maktuIcra = TARIFE.aautMaktu['icra-takip'][1];
      if (deger <= TARIFE.aautIcraEsik) {
        ucret = Math.min(maktuIcra, deger);
        satirlar.push(satir(`Takip miktarı ${TL(TARIFE.aautIcraEsik)}'ye kadar: maktu ücret`, maktuIcra, 'AAÜT m.11/1'));
        if (deger < maktuIcra) satirlar.push(satir('Takipte kesinleşen miktarı geçemez', deger, 'AAÜT m.11/1'));
      } else {
        const n = aautNispi(deger);
        satirlar.push(...n.adim);
        ucret = n.toplam;
        satirlar.push(satir('Nispi ücret', ucret, 'AAÜT m.11/1, Üçüncü Kısım'));
      }
    }
    if (yarisi && tur !== 'icra') { ucret /= 2; satirlar.push(satir('Ön inceleme tutanağı imzalanmadan sona erdi: yarısı', ucret, 'AAÜT m.7/1')); }
    satirlar.push(satir('Asgari vekâlet ücreti', ucret, '', true));
    return { ucret, satirlar, not: 'Mahkeme işin niteliğine göre üç katına kadar hükmedebilir (AAÜT m.3/1). Akdi ücret bu tutarın altında kararlaştırılamaz.' };
  }

  /** Faiz. tur: 'kanuni' | 'avans' (ticari temerrüt) | 'ttk' (TTK 1530) | 'ozel'. Basit faiz, 365 gün, son gün hariç. */
  function faiz({ anapara, bas, bit, tur, oran, giderim }) {
    if (!(anapara > 0) || !bas || !bit) return { hata: 'Anapara ve tarihleri girin.' };
    const b0 = D(bas), b1 = D(bit);
    if (b1 <= b0) return { hata: 'Bitiş tarihi başlangıçtan sonra olmalı.' };
    let donemler, ref;
    if (tur === 'ozel') { donemler = [[b0, b1, +oran || 0, 'Sözleşme / özel oran']]; ref = 'Sözleşmesel faiz'; }
    else if (tur === 'ttk') { donemler = [[b0, b1, TARIFE.ttk1530.oran, 'TTK m.1530/7 — ' + TARIFE.ttk1530.yil]]; ref = 'TTK 1530'; }
    else {
      const tablo = tur === 'kanuni' ? TARIFE.kanuni : TARIFE.avans, anahtar = Object.keys(tablo).sort();
      if (b0 < D(anahtar[0])) return { hata: `Bu araçta ${tur === 'kanuni' ? 'kanuni' : 'avans'} faizi oranları ${anahtar[0]} tarihinden itibaren kayıtlı. Daha eski dönem için "özel oran" seçin.` };
      donemler = [];
      for (let i = 0; i < anahtar.length; i++) {
        const s = D(anahtar[i]), e = anahtar[i + 1] ? D(anahtar[i + 1]) : null;
        const a = s > b0 ? s : b0, b = e && e < b1 ? e : b1;
        if (b > a) donemler.push([a, b, tablo[anahtar[i]], '']);
      }
      ref = tur === 'kanuni' ? '3095 s.K. m.1' : '3095 s.K. m.2/2 (avans faizi)';
    }
    let toplam = 0;
    const tablo = donemler.map(([a, b, o, k]) => {
      const g = gunFarki(a, b), f = anapara * o / 100 * g / 365;
      toplam += f;
      return { bas: a, bit: b, gun: g, oran: o, faiz: f, kaynak: k };
    });
    const satirlar = [satir('Toplam faiz', toplam, ref)];
    if (tur === 'ttk' && giderim) { satirlar.push(satir('Asgari giderim tutarı', TARIFE.ttk1530.giderim, 'TTK m.1530/7')); toplam += TARIFE.ttk1530.giderim; }
    satirlar.push(satir('Anapara + faiz', anapara + toplam, '', true));
    return { faiz: toplam, tablo, satirlar, not: 'Basit faiz, 365 gün esasıyla; son gün hesaba dahil edilmez.' };
  }

  /** Harç. tur: 'dava' | 'icra' | 'kanunyolu'; mahkeme: 'sulh' | 'asliye'. */
  function harc({ tur, deger, mahkeme, vekaletname }) {
    const H = TARIFE.harc, satirlar = [];
    let toplam = 0;
    if (tur === 'dava') {
      const basv = mahkeme === 'sulh' ? H.basvurma_sulh : H.basvurma_asliye;
      toplam += basv;
      satirlar.push(satir(`Başvurma harcı (${mahkeme === 'sulh' ? 'sulh / icra mahkemesi' : 'asliye / idare'})`, basv, '492 s.K. Tarife A-I'));
      if (deger > 0) {
        const nispi = deger * H.nispi_karar, pesin = nispi * H.pesin_oran;
        satirlar.push(satir('Peşin karar ve ilam harcı (değer × binde 68,31 × ¼)', pesin, '492 s.K. m.28/a; Tarife A-III'));
        toplam += pesin;
        satirlar.push(satir(`Karar sonunda tamamı (binde 68,31, en az ${TL(H.maktu_karar)})`, Math.max(nispi, H.maktu_karar), 'Tarife A-III-1'));
      } else {
        satirlar.push(satir('Peşin maktu karar ve ilam harcı', H.maktu_karar, 'Tarife A-III-2'));
        toplam += H.maktu_karar;
      }
      if (vekaletname) { satirlar.push(satir('Vekâletname suret harcı', H.vekalet_suret, 'Tarife A-VI')); toplam += H.vekalet_suret; }
      satirlar.push(satir('Dava açılışında ödenecek harç', toplam, '', true));
      return { toplam, satirlar, not: 'Gider avansı (tebligat, bilirkişi, tanık) dahil değildir; HMK Gider Avansı Tarifesine göre ayrıca yatırılır.' };
    }
    if (tur === 'icra') {
      const d = deger || 0;
      toplam = H.icra_basvurma + d * H.icra_pesin;
      satirlar.push(satir('İcraya başvurma harcı', H.icra_basvurma, 'Tarife B-I'), satir('Peşin harç (binde 5)', d * H.icra_pesin, 'Tarife B-I'),
        satir('Takip açılışında ödenecek', toplam, '', true),
        satir('Tahsil harcı — tebliğden sonra, hacizden önce (%4,55)', d * H.tahsil_hacizden_once, 'Tarife B-I'),
        satir('Tahsil harcı — hacizden sonra, satıştan önce (%9,10)', d * H.tahsil_satistan_once, 'Tarife B-I'),
        satir('Tahsil harcı — satış yoluyla (%11,38)', d * H.tahsil_satis, 'Tarife B-I'),
        satir("Cezaevleri harcı (tahsil edilenin %2'si)", d * H.cezaevi, ''));
      return { toplam, satirlar };
    }
    satirlar.push(satir('İstinaf başvurma + karar harcı', H.istinaf + H.basvurma_ust, 'Tarife A-I, A-IV'),
      satir('Temyiz başvurma + karar harcı', H.temyiz + H.basvurma_ust, 'Tarife A-I, A-IV'),
      satir('Keşif harcı', H.kesif, 'Tarife A-V'), satir('İhtiyati tedbir / haciz / delil tespiti karar harcı', H.tedbir_haciz, 'Tarife A-III'));
    return { toplam: 0, satirlar };
  }

  /** Serbest meslek makbuzu. giris: 'brut' | 'net' | 'tahsil'; sorumlu: müşteri vergi sorumlusu (stopaj keser). */
  function smm({ tutar, giris, sorumlu }) {
    const A = TARIFE.smm;
    if (!(tutar > 0)) return { hata: 'Tutarı girin.' };
    const st = sorumlu ? A.stopaj : 0;
    const brut = giris === 'brut' ? tutar : giris === 'net' ? tutar / (1 - st) : tutar / (1 - st + A.kdv);
    const stopaj = brut * st, kdv = brut * A.kdv, net = brut - stopaj, tahsil = brut - stopaj + A.kdv * brut;
    return {
      brut, stopaj, kdv, net, tahsil, satirlar: [
        satir('Brüt ücret', brut, ''),
        satir(`Gelir vergisi stopajı (%${st * 100})`, stopaj, sorumlu ? 'GVK m.94/2-b — müşteri keser' : 'Gerçek kişi müşteride stopaj yoktur'),
        satir('Net ücret', net, ''), satir('KDV (%20)', kdv, '3065 s. KDV K. m.28'),
        satir('Müvekkilden tahsil edilecek', tahsil, '', true)]
    };
  }

  /** CMK görevlendirme makbuzu: tarife KDV dahil → ücret = tarife ÷ 1,20; stopaj %20; sınır aşılırsa 5/10 KDV tevkifatı. */
  function cmkMakbuz({ kalem, adet }) {
    const A = TARIFE.smm, k = TARIFE.cmk[kalem];
    if (!k) return { hata: 'Görevlendirme türünü seçin.' };
    const tarife = k[1] * Math.max(1, adet || 1);
    const ucret = tarife / (1 + A.kdv), kdv = ucret * A.kdv, stopaj = ucret * A.stopaj;
    const tevk = tarife > A.tevkifat_sinir ? kdv * A.tevkifat_oran : 0, odenen = ucret + kdv - stopaj - tevk;
    return {
      odenen, satirlar: [
        satir(`Tarife tutarı (KDV dahil) — ${k[0]}${adet > 1 ? ' × ' + adet : ''}`, tarife, 'CMK 2026 Tarifesi m.4'),
        satir('Ücret (matrah)', ucret, 'Tarife ÷ 1,20'), satir('KDV (%20)', kdv, '3065 s. KDV K. m.28'),
        satir('Gelir vergisi stopajı (%20)', -stopaj, 'GVK m.94/2-b — baro keser'),
        ...(tevk ? [satir('KDV tevkifatı (5/10)', -tevk, `KDV dahil tutar ${TL(A.tevkifat_sinir)} sınırını aşıyor`)] : []),
        satir('Baronun ödeyeceği', odenen, '', true)]
    };
  }

  /** İnfaz (5275 s.K.): oran '1/2' | '2/3' | '3/4', yil/ay/gun, mahsupGun, denetimliYil (varsayılan 1). */
  function infaz({ yil, ay, gun, oran, mahsupGun, denetimliYil }) {
    const toplamGun = (Math.max(0, +yil || 0) * 365) + (Math.max(0, +ay || 0) * 30) + Math.max(0, +gun || 0);
    if (toplamGun <= 0) return { hata: 'Hükmedilen ceza süresini (yıl/ay/gün) girin.' };
    const carpan = oran === '3/4' ? 0.75 : (oran === '2/3' ? (2 / 3) : 0.5);
    const kosulluGun = Math.ceil(toplamGun * carpan);
    const mahsup = Math.max(0, Math.floor(+mahsupGun || 0));
    const dsGun = Math.max(0, Math.round((denetimliYil == null ? 1 : +denetimliYil) * 365));
    const kalanKosullu = Math.max(0, kosulluGun - mahsup);
    const cezaevindeYatacak = Math.max(0, kalanKosullu - dsGun);
    const fmt = g => {
      const y = Math.floor(g / 365), a = Math.floor((g % 365) / 30), gn = (g % 365) % 30;
      return [y ? y + ' yıl' : '', a ? a + ' ay' : '', (gn || (!y && !a)) ? gn + ' gün' : ''].filter(Boolean).join(' ') + ` (${g} gün)`;
    };
    return {
      toplamGun, kosulluGun, kalanKosullu, cezaevindeYatacak,
      metinSatirlar: [
        { ad: 'Toplam hükmedilen ceza', deger: fmt(toplamGun), ref: 'TCK / 5275 s.K.' },
        { ad: `Koşullu salıverilme süresi (${oran || '1/2'})`, deger: fmt(kosulluGun), ref: '5275 s.K. m.107' },
        ...(mahsup ? [{ ad: 'Tutukluluk / gözaltı mahsubu', deger: `-${fmt(mahsup)}`, ref: 'TCK m.63' }] : []),
        { ad: 'Denetimli serbestlik süresi', deger: fmt(dsGun), ref: '5275 s.K. m.105/A' },
        { ad: 'Cezaevinde geçirilecek tahmini süre', deger: fmt(cezaevindeYatacak), ref: '', vurgu: true }
      ],
      satirlar: [],
      not: 'Bilgilendirme amaçlıdır. Suç tarihi, mükerrirlik, 7242/7456 s.K. geçici maddeleri ve iyi hal değerlendirmesi infaz hâkimliğince belirlenir.'
    };
  }

  // -------------------------------------------------------------------------------------------------
  // İNFAZ — SUÇ TARİHİNE GÖRE UYGULANACAK DÜZENLEME (bilgilendirme; infaz hâkimliği/savcılık hesabı esastır)
  // Kanun değişiklikleri (yürürlük ve suç tarihi eşikleri):
  //  * 5275 s.K. (01.06.2005): koşullu salıverilme kural olarak 1/2 (m.107/2); mükerrirlerde 2/3 (m.108);
  //    terör suçlarında 3/4 (3713 m.17); müebbet 24 yıl, ağırlaştırılmış müebbet 30 yıl (terörde 30/36).
  //  * 7242 s.K. (RG 15.04.2020): bazı suçlarda oran 2/3'e çıktı (kasten öldürme, cinsel dokunulmazlık, uyuşturucu
  //    imal/ticareti, örgüt kurma/yönetme, devletin güvenliği vb.); geçici m.6: 30.03.2020'den ÖNCE işlenen suçlarda
  //    denetimli serbestlik süresi 3 yıl (istisna suçlar hariç).
  //  * 7456 s.K. (RG 15.11.2023) geçici madde: 31.07.2023'ten ÖNCE işlenen suçlarda denetimli serbestlik 3 yıl
  //    (istisna suçlar hariç).
  //  * Genel kural (m.105/A): koşullu salıverilmeye 1 yıl kalan hükümlü denetimli serbestlikle infaz edilebilir;
  //    terör, örgüt, cinsel dokunulmazlık suçları ve kasten öldürme gibi istisnalarda uygulanmaz.
  //  * 765 s. TCK / 647 s.K. dönemi (01.06.2005 öncesi): lehe kanun karşılaştırması gerekir.
  const INFAZ_KANUNLAR = [
    { tarih: '2005-06-01', ad: '5275 s. İnfaz Kanunu', ozet: 'Koşullu salıverilme 1/2; mükerrir 2/3; terör 3/4; müebbet 24 yıl, ağırlaştırılmış müebbet 30 yıl.' },
    { tarih: '2020-04-15', ad: '7242 s.K. (infaz düzenlemesi)', ozet: 'Belirli suçlarda 2/3 oranı; 30.03.2020 öncesi suçlarda denetimli serbestlik 3 yıl (geçici m.6).', esik: '2020-03-30' },
    { tarih: '2023-11-15', ad: '7456 s.K. (geçici madde)', ozet: '31.07.2023 öncesi suçlarda denetimli serbestlik 3 yıl (istisna suçlar hariç).', esik: '2023-07-31' },
  ];
  const INFAZ_TURLER = {
    genel: { ad: 'Genel suçlar (hırsızlık, dolandırıcılık, yaralama vb.)', oran: '1/2', ds: true },
    ikiucte: { ad: '7242 ile 2/3\'e çıkan suçlar (kasten öldürme, uyuşturucu ticareti, örgüt kurma/yönetme, devlet güvenliği)', oran7242: '2/3', oran: '1/2', ds: false },
    cinsel: { ad: 'Cinsel dokunulmazlığa karşı suçlar / çocuğun cinsel istismarı', oran7242: '2/3', oran: '1/2', ds: false },
    teror: { ad: 'Terör suçları / örgüt faaliyeti kapsamında suç', oran: '3/4', ds: false },
  };
  function infazDetay(f) {
    const sucT = f.sucTarihi ? new Date(f.sucTarihi + 'T00:00:00') : null;
    if (!sucT || isNaN(sucT)) return { hata: 'Suç tarihini girin: uygulanacak oran ve denetimli serbestlik süresi suç tarihine göre belirlenir.' };
    const tur = INFAZ_TURLER[f.sucTuru] || INFAZ_TURLER.genel;
    const iso = f.sucTarihi;
    const muebbet = f.cezaTipi === 'muebbet' || f.cezaTipi === 'agir';
    let toplamGun = (Math.max(0, +f.yil || 0) * 365) + (Math.max(0, +f.ay || 0) * 30) + Math.max(0, +f.gun || 0);
    if (!muebbet && toplamGun <= 0) return { hata: 'Hükmedilen ceza süresini (yıl/ay/gün) girin.' };
    const uyarilar = [], gerekce = [];
    if (iso < '2005-06-01') uyarilar.push('Suç tarihi 01.06.2005 öncesi (765 s. TCK / 647 s.K. dönemi): lehe kanun karşılaştırması yapılmalı; aşağıdaki hesap 5275 s.K. kurallarıyla yapılmıştır.');
    // ORAN
    let oran = tur.oran;
    if (tur.oran7242 && iso >= '2020-03-30') { oran = tur.oran7242; gerekce.push(`Suç tarihi (${iso.split('-').reverse().join('.')}) 7242 s.K. eşiği 30.03.2020'den sonra: bu suç türünde koşullu salıverilme oranı 2/3.`); }
    else if (tur.oran7242) gerekce.push('Suç tarihi 30.03.2020 öncesi: 7242 s.K. ile getirilen 2/3 oranı uygulanmaz (lehe olan 1/2).');
    if (f.sucTuru === 'teror') gerekce.push('Terör suçlarında koşullu salıverilme oranı 3/4 (3713 s.K. m.17).');
    if (f.mukerrir === '1') { const sira = { '1/2': 0, '2/3': 1, '3/4': 2 }; if (sira[oran] < 1) oran = '2/3'; gerekce.push('Mükerrir: koşullu salıverilme oranı en az 2/3 (5275 s.K. m.108).'); }
    if (f.mukerrir === '2') uyarilar.push('İkinci kez mükerrir hükümlü koşullu salıverilmez (5275 s.K. m.108/2); ceza tamamen infaz edilir.');
    const carpan = { '1/2': 0.5, '2/3': 2 / 3, '3/4': 0.75 }[oran];
    // KOŞULLU SALIVERİLME SÜRESİ
    let kosulluGun;
    if (muebbet) {
      const yilK = f.cezaTipi === 'agir' ? (f.sucTuru === 'teror' ? 36 : 30) : (f.sucTuru === 'teror' ? 30 : 24);
      kosulluGun = yilK * 365; toplamGun = kosulluGun;
      gerekce.push(`${f.cezaTipi === 'agir' ? 'Ağırlaştırılmış müebbet' : 'Müebbet'} hapiste koşullu salıverilme için ${yilK} yıl (5275 s.K. m.107/2${f.sucTuru === 'teror' ? ', 3713 m.17' : ''}).`);
    } else {
      kosulluGun = f.mukerrir === '2' ? toplamGun : Math.ceil(toplamGun * carpan);
    }
    // ÇOCUK HÜKÜMLÜ: suç tarihinde 15 yaşını doldurmamış → 1 gün 3 gün; 15-18 → 1 gün 2 gün (5275 m.107/14, 7242 ile)
    let yasCarpani = 1;
    if (f.yas === '15alti') { yasCarpani = 3; gerekce.push('Suç tarihinde 15 yaşını doldurmamış: cezaevinde geçen 1 gün 3 gün sayılır (5275 s.K. m.107 — güncel metni kontrol edin).'); }
    if (f.yas === '15-18') { yasCarpani = 2; gerekce.push('Suç tarihinde 15-18 yaş arası: cezaevinde geçen 1 gün 2 gün sayılır (5275 s.K. m.107 — güncel metni kontrol edin).'); }
    const mahsup = Math.max(0, Math.floor(+f.mahsupGun || 0));
    // DENETİMLİ SERBESTLİK
    let dsYil = 1, dsGerekce = '5275 s.K. m.105/A: koşullu salıverilmeye 1 yıl kalan hükümlü';
    if (!tur.ds || f.sucTuru === 'teror') { dsYil = 0; dsGerekce = 'Bu suç türünde denetimli serbestlik uygulanmaz (m.105/A istisnaları)'; }
    else if (iso < '2020-03-30') { dsYil = 3; dsGerekce = '7242 s.K. geçici m.6: 30.03.2020 öncesi suç → 3 yıl'; }
    else if (iso < '2023-07-31') { dsYil = 3; dsGerekce = '7456 s.K. geçici madde: 31.07.2023 öncesi suç → 3 yıl'; }
    if (f.mukerrir === '2') { dsYil = 0; dsGerekce = 'İkinci kez mükerrir: koşullu salıverilme ve DS yok'; }
    const dsGun = Math.round(dsYil * 365);
    const kalanKosullu = Math.max(0, kosulluGun - mahsup * yasCarpani);
    const dsKullanilan = Math.min(dsGun, kalanKosullu);
    const cezaevindeGercek = Math.ceil(Math.max(0, kalanKosullu - dsKullanilan) / yasCarpani);
    const fmt = g => { const y = Math.floor(g / 365), a = Math.floor((g % 365) / 30), gn = (g % 365) % 30; return [y ? y + ' yıl' : '', a ? a + ' ay' : '', (gn || (!y && !a)) ? gn + ' gün' : ''].filter(Boolean).join(' ') + ` (${g} gün)`; };
    // TARİHLER
    let tarihler = null;
    if (f.baslangic) {
      const b = new Date(f.baslangic + 'T00:00:00');
      if (!isNaN(b)) {
        const ekle = n => { const d = new Date(b.getTime()); d.setDate(d.getDate() + n); return d; };
        const fm = d => d.toLocaleDateString('tr-TR');
        const dsBas = ekle(cezaevindeGercek), ks = ekle(cezaevindeGercek + dsKullanilan), son = ekle(Math.ceil(Math.max(0, toplamGun - mahsup * yasCarpani) / 1));
        tarihler = { dsBaslangic: fm(dsBas), kosullu: fm(ks), cezaSonu: muebbet ? 'Müebbet' : fm(son) };
      }
    }
    const kanunlar = INFAZ_KANUNLAR.map(k => ({ ...k, uygulanir: iso >= k.tarih || (k.esik && iso < k.esik && iso >= '2005-06-01') }));
    const metinSatirlar = [
      { ad: 'Suç tarihi / suç türü', deger: `${iso.split('-').reverse().join('.')} · ${tur.ad.split(' (')[0]}`, ref: '' },
      { ad: 'Hükmedilen ceza', deger: muebbet ? (f.cezaTipi === 'agir' ? 'Ağırlaştırılmış müebbet' : 'Müebbet') : fmt(toplamGun), ref: 'TCK m.49-50' },
      { ad: `Koşullu salıverilme oranı`, deger: f.mukerrir === '2' ? 'Yok (2. kez mükerrir)' : (muebbet ? 'Sabit süre' : oran), ref: '5275 s.K. m.107-108' },
      { ad: 'Koşullu salıverilme süresi', deger: fmt(kosulluGun), ref: '' },
      ...(mahsup ? [{ ad: 'Tutukluluk / gözaltı mahsubu', deger: `-${fmt(mahsup)}${yasCarpani > 1 ? ` × ${yasCarpani}` : ''}`, ref: 'TCK m.63' }] : []),
      { ad: `Denetimli serbestlik`, deger: dsKullanilan ? fmt(dsKullanilan) : 'Uygulanmaz', ref: dsGerekce },
      { ad: 'Cezaevinde geçirilecek tahmini süre', deger: fmt(cezaevindeGercek), ref: yasCarpani > 1 ? `Gerçek gün (1 gün = ${yasCarpani} gün sayılır)` : '', vurgu: true },
      ...(tarihler ? [{ ad: 'Denetimli serbestliğe çıkış (tahmini)', deger: tarihler.dsBaslangic, ref: '' }, { ad: 'Koşullu salıverilme tarihi (tahmini)', deger: tarihler.kosullu, ref: '' }, { ad: 'Cezanın tamamen bitişi', deger: tarihler.cezaSonu, ref: '' }] : []),
    ];
    return {
      metinSatirlar, satirlar: [], gerekce, uyarilar, kanunlar,
      gorsel: { cezaevi: cezaevindeGercek * yasCarpani, ds: dsKullanilan, mahsup: Math.min(mahsup * yasCarpani, kosulluGun), kosullu: kosulluGun,
                sonrasi: muebbet ? 0 : Math.max(0, toplamGun - kosulluGun), toplam: muebbet ? kosulluGun : toplamGun },
      not: 'Bilgilendirme amaçlıdır. İyi hal, disiplin cezaları, açık cezaevine ayrılma, sağlık/yaş durumları ve güncel kanun değişiklikleri infaz hâkimliği ve Cumhuriyet başsavcılığınca değerlendirilir; somut hesap için müddetnameyi esas alın.'
    };
  }

  /** Ceza artırım/indirim hesabı (TCK m.61 sırası): temel gün (yıl*365+ay*30+gun) üzerinde adımlar [{tip:'artir'|'indir', pay, payda, ad}]. */
  function ceza({ yil, ay, gun, adimlar }) {
    let g = (Math.max(0, +yil || 0) * 365) + (Math.max(0, +ay || 0) * 30) + Math.max(0, +gun || 0);
    if (g <= 0) return { hata: 'Temel ceza süresini girin.' };
    const fmt = n => {
      const y = Math.floor(n / 365), a = Math.floor((n % 365) / 30), gn = (n % 365) % 30;
      return [y ? y + ' yıl' : '', a ? a + ' ay' : '', (gn || (!y && !a)) ? gn + ' gün' : ''].filter(Boolean).join(' ');
    };
    const metinSatirlar = [{ ad: 'Temel ceza', deger: fmt(g), ref: 'TCK m.61' }];
    for (const a of (adimlar || [])) {
      const pay = +a.pay || 0, payda = +a.payda || 1;
      if (pay <= 0 || payda <= 0) continue;
      const fark = Math.floor(g * pay / payda);
      g = a.tip === 'artir' ? (g + fark) : Math.max(0, g - fark);
      metinSatirlar.push({ ad: `${a.ad || (a.tip === 'artir' ? 'Artırım' : 'İndirim')} (${a.tip === 'artir' ? '+' : '-'}${pay}/${payda})`, deger: fmt(g), ref: '' });
    }
    metinSatirlar.push({ ad: 'Sonuç ceza', deger: fmt(g), ref: '', vurgu: true });
    return { sonucGun: g, metinSatirlar, satirlar: [], not: 'TCK m.61 sırasına göre (artırımlar → indirimler → TCK m.62) uygulanır.' };
  }

  const API = { TARIFE, TL, aautNispi, vekalet, faiz, harc, smm, cmkMakbuz, infaz, infazDetay, INFAZ_TURLER, INFAZ_KANUNLAR, ceza };
  if (typeof window !== 'undefined') window.HukukHesap = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})();
