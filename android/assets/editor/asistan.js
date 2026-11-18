/**
 * CanEditor Hukuk Asistanı paneli — birleşik uygulamanın asistan yüzü.
 *
 * Her platformda (Windows/macOS/Linux masaüstü, Android, taşınabilir web) sunucusuz çalışanlar:
 *   • Yasal Süre Hesaplayıcı — avukatasistan/utils.py calculate_deadlines() ile birebir aynı kural
 *     (UETS: gelişten sonraki 5. gün tebliğ, merciye göre 7/14/30 gün, hafta sonu → Pazartesi, 17:00).
 *     Resmî tatil / adli tatil yalnızca UYARI olarak gösterilir; tarih ihtiyaten ileri alınmaz.
 *   • A4 PDF Birleştirici — naps-uyap-thunar-tools a4_pdf_engine.py yöntemi (5 mm güvenli kenar,
 *     oran korumalı sığdırma, yataya otomatik dönüş); görsel, TIFF (çok sayfalı) ve PDF kabul eder.
 *
 * Yerel asistan sunucusu (asistan/sunucu.py — masaüstü ve Termux) açıksa ek olarak:
 *   • Ajanda (UETS süre sonları + UYAP/Takvim duruşmaları, tekilleştirilmiş)
 *   • UYAP Evrak Kataloğu araması (Türkçe-duyarsız, "-kelime" hariç tutar) ve evrakı editörde açma
 *   • Görevler: UETS senkronu, UYAP evrak indirme, nöbetçi tarama, Asistan/Katalog pencereleri
 *
 * DOM'a yalnızca panel ilk açıldığında dokunulur; saf işlevler window.CanAsistan altında dışa açıktır
 * (tests/asistan_sure.test.cjs bunları Python referansıyla karşılaştırır).
 */
(function () {
  'use strict';

  // =========================================================================
  // 1. YASAL SÜRE MOTORU (saf işlevler)
  // =========================================================================
  const AYAR = { UETS_TEBLIG_GUN: 5, KISA: 7, VARSAYILAN: 14, IDARI: 30, SON_SAAT: 17 };

  /** Python normalize_tr ile aynı: İ→i, I→ı, sonra küçük harf. */
  function normTr(s) { return String(s || '').replace(/İ/g, 'i').replace(/I/g, 'ı').toLowerCase(); }

  /** utils.get_applicable_deadline_days ile birebir. */
  function uygulanacakGun(merci) {
    const c = normTr(merci);
    if (['icra', 'kira'].some(k => c.includes(k))) return 7;
    if (['ceza', 'soruşturma', 'sorusturma', 'hazırlık', 'hazirlik', 'savcılık', 'savcilik'].some(k => c.includes(k))) return 7;
    if (['idare', 'vergi', 'danıştay', 'danistay', 'bim', 'bölge idare'].some(k => c.includes(k))) return 30;
    return 14;
  }

  function gunEkle(d, n) { const x = new Date(d.getTime()); x.setDate(x.getDate() + n); return x; }

  /** HMK 93 / CMK 39 / İİK 19: son gün Cumartesi/Pazar ise Pazartesi. */
  function haftaSonuUzat(d) {
    const g = d.getDay(); // 0 Pazar, 6 Cumartesi
    return g === 6 ? gunEkle(d, 2) : (g === 0 ? gunEkle(d, 1) : d);
  }

  function sonGun(teblig, n) {
    const d = haftaSonuUzat(gunEkle(teblig, n));
    d.setHours(AYAR.SON_SAAT, 0, 0, 0);
    return d;
  }

  function tarihStr(d) {
    return String(d.getDate()).padStart(2, '0') + '.' + String(d.getMonth() + 1).padStart(2, '0') + '.' + d.getFullYear();
  }
  function isoGun(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }

  /**
   * utils.calculate_deadlines ile aynı sonuç.
   * @param {Date} gelis UETS'ye düşme anı (yerel saat)
   * @param {string} merci Mahkeme / daire / büro adı
   * @param {{elden?: boolean}} [secenek] elden=true: tebliğ tarihi doğrudan "gelis" kabul edilir (5 gün eklenmez)
   */
  function sureHesapla(gelis, merci, secenek) {
    secenek = secenek || {};
    const teblig = secenek.elden ? new Date(gelis.getTime()) : gunEkle(gelis, AYAR.UETS_TEBLIG_GUN);
    const d7 = sonGun(teblig, AYAR.KISA), d14 = sonGun(teblig, AYAR.VARSAYILAN), d30 = sonGun(teblig, AYAR.IDARI);
    const gun = uygulanacakGun(merci);
    const hedef = gun === 7 ? d7 : (gun === 30 ? d30 : d14);
    const etiket = gun === 7 ? '7 Günlük Yasal Süre (İcra/Ceza)' : (gun === 30 ? '30 Günlük Yasal Süre (İdari Yargı)' : '14 Günlük / 2 Haftalık Yasal Süre (HMK)');
    return {
      gelis, teblig, d7, d14, d30, hedef, gun, etiket,
      gelis_str: tarihStr(gelis), teblig_str: tarihStr(teblig), d7_str: tarihStr(d7), d14_str: tarihStr(d14),
      d30_str: tarihStr(d30), hedef_str: tarihStr(hedef), uyarilar: tatilUyarilari(hedef, merci)
    };
  }

  // Sabit resmî tatiller (2429 s.K.) ve dinî bayramlar (Diyanet takvimi; arife yarım gün).
  const SABIT_TATIL = { '01-01': 'Yılbaşı', '04-23': 'Ulusal Egemenlik ve Çocuk Bayramı', '05-01': 'Emek ve Dayanışma Günü',
    '05-19': "Atatürk'ü Anma, Gençlik ve Spor Bayramı", '07-15': 'Demokrasi ve Millî Birlik Günü', '08-30': 'Zafer Bayramı',
    '10-29': 'Cumhuriyet Bayramı' };
  const BAYRAM = {
    // [arife, bayram günleri...]
    2025: [['2025-03-29', '2025-03-30', '2025-03-31', '2025-04-01', 'Ramazan Bayramı'], ['2025-06-05', '2025-06-06', '2025-06-07', '2025-06-08', '2025-06-09', 'Kurban Bayramı']],
    2026: [['2026-03-19', '2026-03-20', '2026-03-21', '2026-03-22', 'Ramazan Bayramı'], ['2026-05-26', '2026-05-27', '2026-05-28', '2026-05-29', '2026-05-30', 'Kurban Bayramı']],
    2027: [['2027-03-08', '2027-03-09', '2027-03-10', '2027-03-11', 'Ramazan Bayramı'], ['2027-05-15', '2027-05-16', '2027-05-17', '2027-05-18', '2027-05-19', 'Kurban Bayramı']]
  };

  /** Son gün bir tatile veya adli tatile denk geliyorsa bilgilendirici uyarılar (tarih DEĞİŞTİRİLMEZ). */
  function tatilUyarilari(d, merci) {
    const u = [], ay = isoGun(d).slice(5), iso = isoGun(d);
    if (SABIT_TATIL[ay]) u.push(`Son gün resmî tatile denk geliyor (${SABIT_TATIL[ay]}). HMK 93 / CMK 39 uyarınca süre ilk iş gününe uzayabilir; ihtiyaten gösterilen tarihi esas alın.`);
    if (ay === '10-28') u.push('Son gün 28 Ekim (Cumhuriyet Bayramı arifesi, yarım gün). Öğleden sonra kalem kapanabilir.');
    (BAYRAM[d.getFullYear()] || []).forEach(b => {
      const ad = b[b.length - 1], gunler = b.slice(0, -1);
      const i = gunler.indexOf(iso);
      if (i === 0) u.push(`Son gün ${ad} arifesi (yarım gün). İşlemi öğleden önce yapın.`);
      else if (i > 0) u.push(`Son gün ${ad} tatiline denk geliyor. Süre ilk iş gününe uzayabilir; ihtiyaten gösterilen tarihi esas alın.`);
    });
    const ayGun = (d.getMonth() + 1) * 100 + d.getDate();
    if (ayGun >= 720 && ayGun <= 831) {
      const c = normTr(merci);
      if (!/(ceza|soruşturma|sorusturma|savcılık|savcilik|icra)/.test(c)) {
        u.push('Son gün adli tatil dönemine (20 Temmuz–31 Ağustos) denk geliyor. Adli tatilde işlemeyen işlerde süre 7 Eylül\'e uzar (HMK 104); işin adli tatilde görülen işlerden olup olmadığını kontrol edin.');
      }
    }
    return u;
  }

  // =========================================================================
  // 2. A4 PDF MOTORU (NAPS2 yöntemi, tarayıcıda)
  // =========================================================================
  const A4 = { w: 595.2756, h: 841.8898, kenar: 14.1732 }; // pt; ~5 mm yazıcı güvenli alanı

  /** Görseli A4 sayfaya oran korumalı sığdırma geometrisi (a4_pdf_engine.image_to_a4_pdf_pages ile aynı). */
  function a4Yerlesim(gw, gh) {
    const yatay = gw > gh;
    const sw = yatay ? A4.h : A4.w, sh = yatay ? A4.w : A4.h;
    const aw = sw - 2 * A4.kenar, ah = sh - 2 * A4.kenar;
    const o = Math.min(aw / gw, ah / gh);
    const w = gw * o, h = gh * o;
    return { yon: yatay ? 'landscape' : 'portrait', sw, sh, x: (sw - w) / 2, y: (sh - h) / 2, w, h };
  }

  function canvasSB(canvas, esik) {
    const ctx = canvas.getContext('2d');
    const im = ctx.getImageData(0, 0, canvas.width, canvas.height), p = im.data;
    for (let i = 0; i < p.length; i += 4) {
      const v = (0.299 * p[i] + 0.587 * p[i + 1] + 0.114 * p[i + 2]) >= esik ? 255 : 0;
      p[i] = p[i + 1] = p[i + 2] = v;
    }
    ctx.putImageData(im, 0, 0);
  }

  async function dosyaCanvaslari(file) {
    const ad = (file.name || '').toLowerCase(), buf = await file.arrayBuffer();
    const out = [];
    if (ad.endsWith('.pdf')) {
      const lib = window.pdfjsLib || window['pdfjs-dist/build/pdf'];
      if (!lib) throw new Error('PDF okuyucu yüklenemedi');
      if (lib.GlobalWorkerOptions && !lib.GlobalWorkerOptions.workerSrc) lib.GlobalWorkerOptions.workerSrc = 'pdf.worker.min.js';
      const pdf = await lib.getDocument({ data: new Uint8Array(buf) }).promise;
      for (let i = 1; i <= pdf.numPages; i++) {
        const sayfa = await pdf.getPage(i), vp = sayfa.getViewport({ scale: 2 });
        const c = document.createElement('canvas'); c.width = vp.width; c.height = vp.height;
        await sayfa.render({ canvasContext: c.getContext('2d'), viewport: vp }).promise;
        out.push(c);
      }
    } else if (/\.tiff?$/.test(ad) && window.UTIF) {
      const ifds = UTIF.decode(buf);
      for (const ifd of ifds) {
        UTIF.decodeImage(buf, ifd);
        const rgba = UTIF.toRGBA8(ifd);
        const c = document.createElement('canvas'); c.width = ifd.width; c.height = ifd.height;
        c.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(rgba.buffer), ifd.width, ifd.height), 0, 0);
        out.push(c);
      }
    } else {
      const url = URL.createObjectURL(new Blob([buf]));
      try {
        const img = await new Promise((ok, hata) => { const i = new Image(); i.onload = () => ok(i); i.onerror = () => hata(new Error('Görsel okunamadı: ' + file.name)); i.src = url; });
        const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight;
        const ctx = c.getContext('2d'); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, c.width, c.height); ctx.drawImage(img, 0, 0);
        out.push(c);
      } finally { URL.revokeObjectURL(url); }
    }
    return out;
  }

  /** Dosyaları tek A4 PDF'te birleştirir → Uint8Array. */
  async function a4PdfOlustur(dosyalar, secenek, ilerleme) {
    secenek = secenek || {};
    const J = window.jspdf && window.jspdf.jsPDF;
    if (!J) throw new Error('PDF motoru (jsPDF) yüklenemedi');
    let doc = null, sayfa = 0;
    for (let i = 0; i < dosyalar.length; i++) {
      ilerleme && ilerleme(`${i + 1}/${dosyalar.length}: ${dosyalar[i].name}`);
      for (const c of await dosyaCanvaslari(dosyalar[i])) {
        if (secenek.sb) canvasSB(c, secenek.esik || 160);
        const y = a4Yerlesim(c.width, c.height);
        if (!doc) doc = new J({ orientation: y.yon, unit: 'pt', format: 'a4', compress: true });
        else doc.addPage('a4', y.yon);
        doc.addImage(c.toDataURL(secenek.sb ? 'image/png' : 'image/jpeg', 0.9), secenek.sb ? 'PNG' : 'JPEG', y.x, y.y, y.w, y.h, undefined, 'FAST');
        sayfa++;
      }
    }
    if (!doc) throw new Error('Dönüştürülecek sayfa bulunamadı');
    return { bayt: new Uint8Array(doc.output('arraybuffer')), sayfa };
  }

  // =========================================================================
  // 3. YEREL ASİSTAN SUNUCUSU İSTEMCİSİ
  // =========================================================================
  const DEPO = 'canasistan.baglanti';
  function baglantiOku() {
    try { return JSON.parse(localStorage.getItem(DEPO) || '{}'); } catch (e) { return {}; }
  }
  function baglantiYaz(b) { try { localStorage.setItem(DEPO, JSON.stringify(b)); } catch (e) { /* özel pencere */ } }

  function tauriInvoke() {
    return (window.__TAURI__ && window.__TAURI__.core && window.__TAURI__.core.invoke) ||
      (window.__TAURI_INTERNALS__ && window.__TAURI_INTERNALS__.invoke) || null;
  }

  const bekle = ms => new Promise(r => setTimeout(r, ms));

  /** Masaüstünde Tauri, Android'de APK içi Python (Termux'suz) sunucuyu başlatır ve anahtarı verir;
   *  taşınabilir web'de kayıtlı eşleştirme kullanılır. Hiçbir yol arayüzü bloklamaz. */
  async function baglantiBul() {
    const ab = window.AndroidBridge;
    if (ab && !ab.__stub && typeof ab.asistanHazirla === 'function') {
      // Android: hazırlık Java tarafında arka planda yürür (ilk açılışta Python ortamı açılır, ~10-40 sn);
      // eşzamanlı köprü çağrısı WebView'i kilitlemesin diye durum sorularak beklenir.
      ab.asistanHazirla();
      for (let i = 0; i < 240; i++) {
        let d = {};
        try { d = JSON.parse(ab.asistanBaglantiDurum() || '{}'); } catch (e) { /* yarım yanıt */ }
        if (d.anahtar) { baglantiYaz({ port: d.port, anahtar: d.anahtar }); return d; }
        if (d.hata) throw Object.assign(new Error(d.hata), { durum: 503 });
        await bekle(250);
      }
      throw Object.assign(new Error('Asistan sunucusu hazırlanamadı (zaman aşımı)'), { durum: 503 });
    }
    const inv = tauriInvoke();
    if (inv) {
      try {
        const b = await inv('asistan_baglanti');   // Rust tarafında arka plan iş parçacığında çalışır
        if (b && b.anahtar) { baglantiYaz({ port: b.port, anahtar: b.anahtar }); return b; }
      } catch (e) {
        // Gömülü sunucu henüz açılmadı/çöktü: gerçek nedeni göster (kayıtlı eşleştirme varsa onu dene)
        if (!baglantiOku().anahtar) throw Object.assign(new Error(String(e && e.message || e)), { durum: 503 });
      }
    }
    const b = baglantiOku();
    return { port: b.port || 8765, anahtar: b.anahtar || '' };
  }

  // Bağlantı bir kez kurulur ve hatırlanır; her istekte yeniden kurulması (eski davranış) masaüstünde
  // arayüz iş parçacığını, Android'de WebView'i her tuş vuruşunda kilitliyordu.
  let baglantiSozu = null;
  function baglantiUnut() { baglantiSozu = null; }
  function baglantiHazirla() {
    if (!baglantiSozu) baglantiSozu = baglantiBul().catch(e => { baglantiSozu = null; throw e; });
    return baglantiSozu;
  }

  async function api(yol, secenek, _tekrar) {
    secenek = secenek || {};
    const b = await baglantiHazirla();
    let r;
    try {
      r = await fetch(`http://127.0.0.1:${b.port}${yol}`, {
        method: secenek.method || 'GET',
        signal: secenek.signal,
        headers: Object.assign({ 'X-Asistan-Anahtar': b.anahtar || '' }, secenek.govde ? { 'Content-Type': 'application/json' } : {}),
        body: secenek.govde ? JSON.stringify(secenek.govde) : undefined
      });
    } catch (e) {
      if (e.name === 'AbortError') throw e;
      // Sunucu kapanmış / yeniden başlamış olabilir: bağlantıyı bir kez yeniden kur
      baglantiUnut();
      if (!_tekrar) return api(yol, secenek, true);
      throw e;
    }
    if (r.status === 401 && !_tekrar) { baglantiUnut(); return api(yol, secenek, true); }
    if (secenek.ham) { if (!r.ok) throw new Error('HTTP ' + r.status); return r; }
    const v = await r.json().catch(() => ({}));
    if (!r.ok) throw Object.assign(new Error(v.hata || ('HTTP ' + r.status)), { durum: r.status });
    return v;
  }

  // =========================================================================
  // 4. ARAYÜZ
  // =========================================================================
  const CSS = `
  #ca-panel{position:fixed;inset:0;z-index:100000;display:none;align-items:center;justify-content:center;background:rgba(15,23,42,.45)}
  #ca-panel.acik{display:flex}
  #ca-panel .ca-kutu{background:var(--ce-surface,#fff);color:var(--ce-text,#1f2937);width:min(860px,calc(100vw - 24px));max-height:calc(100vh - 32px);display:flex;flex-direction:column;border-radius:12px;box-shadow:0 20px 50px rgba(0,0,0,.25);font:14px/1.5 var(--ce-font-ui,system-ui,sans-serif);overflow:hidden}
  #ca-panel header{display:flex;align-items:center;gap:8px;padding:12px 16px;border-bottom:1px solid var(--ce-border,#e2e6ec);flex-shrink:0}
  #ca-panel header h2{margin:0;font-size:16px;flex:1}
  #ca-panel .ca-kapat{border:0;background:none;font-size:20px;cursor:pointer;color:inherit;padding:2px 8px}
  #ca-panel nav{display:flex;gap:4px;padding:0 8px;border-bottom:1px solid var(--ce-border,#e2e6ec);overflow-x:auto;overflow-y:hidden;flex-shrink:0;min-height:46px;height:46px;align-items:center;white-space:nowrap;-webkit-overflow-scrolling:touch;scrollbar-width:none}
  #ca-panel nav::-webkit-scrollbar{display:none}
  #ca-panel nav button{border:0;background:none;padding:0 12px;height:36px;line-height:36px;border-bottom:2px solid transparent;cursor:pointer;color:var(--ce-muted,#6b7280);font:inherit;white-space:nowrap;flex-shrink:0;display:inline-flex;align-items:center;justify-content:center}
  #ca-panel nav button.secili{color:var(--ce-accent,#2563eb);border-bottom-color:var(--ce-accent,#2563eb);font-weight:600}
  #ca-panel .ca-icerik{padding:16px;overflow-y:auto;overflow-x:hidden;flex:1 1 0%;min-height:0;-webkit-overflow-scrolling:touch}
  #ca-panel input:not([type=checkbox]):not([type=range]),#ca-panel select{width:100%!important;max-width:none!important;min-width:0!important;height:auto!important;min-height:38px;line-height:1.4!important;padding:8px 10px!important;font-size:14px!important;margin:0!important}
  #ca-panel th{background:transparent!important;font-weight:600;width:auto}
  #ca-panel label{display:block;font-size:12px;color:var(--ce-muted,#6b7280);margin:10px 0 4px}
  #ca-panel input,#ca-panel select{width:100%;box-sizing:border-box;padding:8px 10px;border:1px solid var(--ce-border,#d0d5dd);border-radius:8px;background:var(--ce-bg,#fff);color:inherit;font:inherit}
  #ca-panel .ca-satir{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
  #ca-panel .ca-btn{display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:8px;border:1px solid var(--ce-border,#d0d5dd);background:var(--ce-surface,#fff);color:inherit;cursor:pointer;font:inherit;margin:8px 8px 0 0}
  #ca-panel .ca-btn.ana{background:var(--ce-accent,#2563eb);border-color:var(--ce-accent,#2563eb);color:#fff}
  #ca-panel .ca-btn:disabled{opacity:.5;cursor:default}
  #ca-panel .ca-kart{border:1px solid var(--ce-border,#e2e6ec);border-radius:10px;padding:12px;margin-top:12px}
  #ca-panel .ca-hedef{font-size:22px;font-weight:700;color:var(--ce-accent,#2563eb)}
  #ca-panel .ca-uyari{background:#fff7e6;color:#7a4b00;border-radius:8px;padding:8px 10px;margin-top:8px;font-size:13px}
  body.ce-dark-mode #ca-panel .ca-uyari{background:#3a2a07;color:#f5d48a}
  #ca-panel .ca-hata{color:#b42318}
  #ca-yuzen{position:fixed;right:84px;bottom:22px;z-index:99990;display:flex;align-items:center;gap:6px;padding:9px 14px;border-radius:22px;border:1px solid var(--ce-border,#d0d5dd);background:var(--ce-surface,#fff);color:var(--ce-text,#1f2937);box-shadow:0 6px 18px rgba(0,0,0,.18);font:600 13px/1 var(--ce-font-ui,system-ui,sans-serif);cursor:pointer}
  #ca-yuzen .ca-nokta{width:9px;height:9px;border-radius:50%;background:#9ca3af}
  #ca-yuzen .ca-sayi{color:#dc2626}
  @media print{#ca-yuzen{display:none}}
  .ca-rozet{display:inline-block;min-width:18px;height:18px;line-height:18px;padding:0 5px;margin-left:5px;border-radius:9px;background:#dc2626;color:#fff;font-size:11px;font-weight:700;text-align:center;vertical-align:1px}
  #ca-panel table{width:100%;border-collapse:collapse;font-size:13px}
  #ca-panel td,#ca-panel th{text-align:left;padding:6px 8px;border-bottom:1px solid var(--ce-border,#eef0f3);vertical-align:top}
  #ca-panel .ca-soluk{color:var(--ce-muted,#6b7280);font-size:12px}
  #ca-panel pre{background:var(--ce-bg,#f6f7f9);padding:8px;border-radius:8px;max-height:220px;overflow:auto;font-size:12px;white-space:pre-wrap}
  @media (max-width:720px){
    #ca-panel .ca-kutu{width:100vw!important;max-height:100dvh!important;height:100dvh!important;border-radius:0!important;display:flex!important;flex-direction:column!important;overflow:hidden!important}
    #ca-panel header{flex-shrink:0!important;min-height:48px!important;height:48px!important}
    #ca-panel nav{flex-shrink:0!important;min-height:46px!important;height:46px!important;overflow-x:auto!important;overflow-y:hidden!important;white-space:nowrap!important;position:sticky!important;top:0!important;z-index:25!important}
    #ca-panel nav button{flex-shrink:0!important;height:34px!important;line-height:34px!important;padding:0 12px!important;font-size:12.5px!important;white-space:nowrap!important}
    #ca-panel .ca-icerik{flex:1 1 0%!important;min-height:0!important;overflow-y:auto!important;-webkit-overflow-scrolling:touch!important;padding:12px!important}
  }
  `;

  let kok = null, aktifSekme = (() => { try { return localStorage.getItem('canasistan.sonSekme') || 'sure'; } catch (e) { return 'sure'; } })(), stilVar = false;
  function stilEkle() {
    if (stilVar || !document.head) return;
    const st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st); stilVar = true;
  }
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // Sekmeler işlevine göre gruplanır (v4.3): masaüstünde solda gruplu kenar çubuğu, telefonda kaydırılabilir çipler.
  const SEKME_GRUPLARI = [
    ['Takip', [['uyap', '🔐 UYAP Giriş'], ['yeni', '🔔 Yeni Evrak'], ['dosyalar', '📁 Dosyalar'], ['ajanda', '📅 Ajanda'], ['evrak', '🗂️ Evrak Ara']]],
    ['Süre & Hesap', [['sure', '⏱️ Süre'], ['hesap', '🧮 Hesapla'], ['hesaplar', '💰 Dosya Hesapları']]],
    ['Belge', [['a4', '📄 A4 PDF'], ['jar', '🔄 JAR Dönüştür'], ['hayfa', '📰 HAYFA']]],
    ['Bağlantılar', [['drive', '☁️ Drive'], ['entegrasyon', '📋 Notion / TickTick'], ['gorev', '⚙️ Görevler'], ['baglanti', '🔌 Bağlantı']]]
  ];
  const SEKMELER = SEKME_GRUPLARI.flatMap(([, l]) => l);

  async function driveDurumunuGuncelle() {
    const el = kok ? kok.querySelector('#ca-hdr-drive-durum') : null;
    if (!el) return;
    try {
      const v = await api('/api/drive');
      if (v.yapilandirildi) {
        if (v.mod === 'webhook') {
          el.innerHTML = '🟢 Drive Sync: Bulut';
          el.style.background = 'rgba(34,197,94,.18)';
          el.style.borderColor = 'rgba(34,197,94,.4)';
          el.style.color = '#86efac';
        } else if (v.dizin_var && v.yazilabilir) {
          el.innerHTML = '🟢 Drive Sync: Bağlı';
          el.style.background = 'rgba(34,197,94,.18)';
          el.style.borderColor = 'rgba(34,197,94,.4)';
          el.style.color = '#86efac';
        } else {
          el.innerHTML = '🟠 Drive: Salt Okunur';
          el.style.background = 'rgba(245,158,11,.18)';
          el.style.borderColor = 'rgba(245,158,11,.4)';
          el.style.color = '#fde68a';
        }
      } else {
        el.innerHTML = '⚪ Drive: Yapılandırılmadı';
        el.style.background = 'rgba(200,164,90,.18)';
        el.style.borderColor = 'rgba(200,164,90,.4)';
        el.style.color = '#f5ecd9';
      }
    } catch (e) {
      el.innerHTML = '🔴 Drive: Çevrimdışı';
      el.style.background = 'rgba(239,68,68,.18)';
      el.style.borderColor = 'rgba(239,68,68,.4)';
      el.style.color = '#fca5a5';
    }
  }

  function dosyaDetayAc(dkey) {
    sekmeAc('dosyalar');
    const bekle = () => {
      if (window.CanHayfa && window.CanHayfa.detayAc) {
        window.CanHayfa.detayAc(dkey);
      } else {
        setTimeout(bekle, 80);
      }
    };
    setTimeout(bekle, 50);
  }

  // v4.3 yerleşim katmanı: HAYFA stilinden SONRA eklenir ve daha özgül seçicilerle onu ezer.
  const CSS_YERLESIM = `
  #ca-panel{backdrop-filter:blur(2px)}
  #ca-panel .ca-kutu{width:min(1180px,calc(100vw - 32px))!important;height:min(860px,calc(100vh - 32px))!important;max-height:none!important}
  #ca-panel .ca-govde{display:grid;grid-template-columns:212px minmax(0,1fr);flex:1 1 auto;min-height:0}
  #ca-panel .ca-govde>nav{display:flex!important;flex-direction:column!important;align-items:stretch!important;gap:2px!important;height:auto!important;min-height:0!important;
    overflow-y:auto!important;overflow-x:hidden!important;padding:10px 8px 16px!important;border-bottom:0!important;border-right:1px solid var(--ce-border,#e2e6ec)!important;position:static!important;white-space:normal!important}
  #ca-panel .ca-govde>nav .ca-grup{font:700 10.5px/1 var(--ce-font-ui,system-ui,sans-serif);letter-spacing:.08em;text-transform:uppercase;color:var(--ce-muted,#94a3b8);padding:14px 10px 6px}
  #ca-panel .ca-govde>nav .ca-grup:first-child{padding-top:4px}
  #ca-panel .ca-govde>nav button{justify-content:flex-start!important;width:100%!important;height:36px!important;padding:0 12px!important;text-align:left!important;border-radius:8px!important}
  #ca-panel .ca-govde>nav button:hover:not(.secili){background:rgba(100,116,139,.10)!important;color:var(--ce-text,#1f2937)!important}
  #ca-panel .ca-govde>nav button:focus-visible{outline:2px solid var(--hf-gold,#c8a45a);outline-offset:1px}
  #ca-panel .ca-govde>.ca-icerik{padding:18px 22px!important;scroll-behavior:smooth}
  #ca-panel .ca-icerik>.ca-kart:first-child{margin-top:0}
  #ca-panel .ca-kart{border-radius:12px;padding:14px 16px;background:var(--ce-surface,#fff)}
  #ca-panel .ca-btn{transition:background .15s,border-color .15s,transform .05s}
  #ca-panel .ca-btn:active:not(:disabled){transform:translateY(1px)}
  #ca-panel .ca-btn:hover:not(:disabled):not(.ana):not(.altin){border-color:var(--hf-gold,#c8a45a)}
  #ca-panel .ca-satir{grid-template-columns:repeat(auto-fit,minmax(180px,1fr))}
  #ca-panel .ca-yukleniyor{display:flex;align-items:center;gap:10px;color:var(--ce-muted,#64748b);padding:18px 4px}
  #ca-panel .ca-yukleniyor::before{content:"";width:16px;height:16px;border-radius:50%;border:2px solid currentColor;border-right-color:transparent;animation:ca-don .8s linear infinite}
  @keyframes ca-don{to{transform:rotate(360deg)}}
  @media (max-width:900px){
    #ca-panel .ca-kutu{width:100vw!important;height:100dvh!important;border-radius:0!important;border:0!important}
    #ca-panel .ca-govde{grid-template-columns:1fr;grid-template-rows:auto minmax(0,1fr)}
    #ca-panel .ca-govde>nav{flex-direction:row!important;align-items:center!important;overflow-x:auto!important;overflow-y:hidden!important;white-space:nowrap!important;
      padding:6px 8px!important;border-right:0!important;border-bottom:2px solid var(--hf-gold,#c8a45a)!important;gap:6px!important;
      -webkit-mask-image:linear-gradient(90deg,#000 92%,transparent);mask-image:linear-gradient(90deg,#000 92%,transparent)}
    #ca-panel .ca-govde>nav .ca-grup{display:none}
    #ca-panel .ca-govde>nav button{width:auto!important;flex-shrink:0!important;height:34px!important;border:1px solid var(--ce-border,#e2e6ec)!important;border-radius:999px!important}
    #ca-panel .ca-govde>.ca-icerik{padding:12px!important}
    #ca-panel header .hf-badge{display:none}
    #ca-panel header h2{font-size:14px!important;gap:6px!important;min-width:0}
    #ca-panel header h2>span:first-child{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    #ca-panel #ca-hdr-drive-durum{white-space:nowrap;font-size:11px!important;padding:3px 8px!important}
    #ca-panel .ca-satir{grid-template-columns:repeat(auto-fit,minmax(140px,1fr))!important}
  }
  @media (max-width:720px){
    #ca-panel th{display:block!important;border:0!important;padding:0 0 2px!important;font-size:12px!important;color:var(--ce-muted,#64748b)!important}
    #ca-panel td{font-size:14px}
  }
  @media (max-width:420px){
    #ca-panel .ca-satir{grid-template-columns:1fr!important}
    #ca-panel .ca-btn{padding:9px 12px}
  }`;

  function panelKur() {
    if (kok) return;
    stilEkle();
    if (window.CanHayfa && window.CanHayfa.stilYukle) window.CanHayfa.stilYukle();
    if (!document.getElementById('ca-yerlesim-css')) {
      const st = document.createElement('style'); st.id = 'ca-yerlesim-css'; st.textContent = CSS_YERLESIM; document.head.appendChild(st);
    }
    kok = document.createElement('div'); kok.id = 'ca-panel';
    kok.innerHTML = `<div class="ca-kutu" role="dialog" aria-modal="true" aria-label="CanEditor Hukuk Asistanı">
      <header>
        <h2>
          <span>⚖️ CanEditor Hukuk Asistanı</span>
          <span class="hf-badge">HAYFA · v${esc(window.CANEDITOR_VERSION || '')}</span>
          <span id="ca-hdr-drive-durum" style="font-size:11.5px;font-weight:normal;padding:3px 9px;border-radius:12px;background:rgba(200,164,90,.18);color:#f5ecd9;border:1px solid rgba(200,164,90,.4);cursor:pointer;margin-left:6px" title="Google Drive Senkronizasyon Durumu (Açmak için tıklayın)">☁️ Drive: Denetleniyor…</span>
        </h2>
        <button class="ca-kapat" type="button" aria-label="Kapat">×</button>
      </header>
      <div class="ca-govde">
        <nav aria-label="Asistan bölümleri">${SEKME_GRUPLARI.map(([g, l]) => `<div class="ca-grup">${esc(g)}</div>` + l.map(([k, ad]) => `<button type="button" data-sekme="${k}">${ad}</button>`).join('')).join('')}</nav>
        <div class="ca-icerik" tabindex="-1"></div>
      </div></div>`;
    document.body.appendChild(kok);
    kok.querySelector('.ca-kapat').onclick = kapat;
    kok.querySelector('#ca-hdr-drive-durum').onclick = () => sekmeAc('drive');
    kok.addEventListener('mousedown', e => { if (e.target === kok) kapat(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && kok.classList.contains('acik')) kapat(); });
    kok.querySelectorAll('nav button').forEach(b => { b.onclick = () => sekmeAc(b.dataset.sekme); });
    driveDurumunuGuncelle();
  }

  function ac(sekme) { panelKur(); kok.classList.add('acik'); sekmeAc(sekme || aktifSekme); driveDurumunuGuncelle(); }
  function kapat() { if (kok) kok.classList.remove('acik'); gorevIzleDurdur(); }

  function hayfaCtx() {
    return { api, esc, sunucuHatasi, evrakAc, kapat, sekmeAc };
  }

  function sekmeAc(k) {
    aktifSekme = k;
    gorevIzleDurdur();
    const btn = kok ? kok.querySelector(`nav button[data-sekme="${k}"]`) : null;
    kok.querySelectorAll('nav button').forEach(b => b.classList.toggle('secili', b.dataset.sekme === k));
    if (btn && typeof btn.scrollIntoView === 'function') {
      try { btn.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' }); } catch (e) {}
    }
    const ic = kok.querySelector('.ca-icerik');
    const hf = window.CanHayfa || {};
    const harita = {
      uyap: uyapSekmesi,
      dosyalar: el => hf.dosyalarSekmesi ? hf.dosyalarSekmesi(el, hayfaCtx()) : (el.textContent = 'Modül yüklenmedi'),
      hesaplar: el => {
        if (hf.dosyalarSekmesi) {
          // Doğrudan Dosya Hesapları görünümünü açar
          window.dosyaGorunumModu = 'hesaplar';
          hf.dosyalarSekmesi(el, hayfaCtx());
          const hBtn = el.querySelector('[data-gorunum="hesaplar"]');
          if (hBtn) hBtn.click();
        } else {
          el.textContent = 'Modül yüklenmedi';
        }
      },
      yeni: yeniSekmesi,
      drive: el => hf.driveProSekmesi ? hf.driveProSekmesi(el, hayfaCtx()) : driveSekmesi(el),
      entegrasyon: el => hf.entegrasyonSekmesi ? hf.entegrasyonSekmesi(el, hayfaCtx()) : (el.textContent = 'Modül yüklenmedi'),
      jar: el => hf.jarSekmesi ? hf.jarSekmesi(el, hayfaCtx()) : (el.textContent = 'Modül yüklenmedi'),
      hayfa: el => hf.hayfaSekmesi ? hf.hayfaSekmesi(el, hayfaCtx()) : (el.textContent = 'Modül yüklenmedi'),
      sure: sureSekmesi,
      hesap: hesapSekmesi,
      a4: a4Sekmesi,
      ajanda: ajandaSekmesi,
      evrak: evrakSekmesi,
      gorev: gorevSekmesi,
      baglanti: baglantiSekmesi
    };
    // Sekme değişince içerik başa sarılır, yükleme göstergesi çıkar ve son sekme hatırlanır.
    ic.scrollTop = 0;
    ic.innerHTML = '<div class="ca-yukleniyor">Yükleniyor…</div>';
    try { localStorage.setItem('canasistan.sonSekme', k); } catch (e) {}
    try {
      const r = (harita[k] || sureSekmesi)(ic);
      if (r && typeof r.catch === 'function') r.catch(e => { ic.innerHTML = `<div class="ca-kart"><span class="ca-hata">Bu bölüm açılamadı: ${esc(e && e.message || e)}</span></div>`; });
    } catch (e) {
      ic.innerHTML = `<div class="ca-kart"><span class="ca-hata">Bu bölüm açılamadı: ${esc(e && e.message || e)}</span></div>`;
    }
    driveDurumunuGuncelle();
  }

  // --- Süre ---
  function sureSekmesi(ic) {
    const simdi = new Date(); simdi.setSeconds(0, 0);
    const yerel = new Date(simdi.getTime() - simdi.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    ic.innerHTML = `
      <div class="ca-satir">
        <div><label for="ca-gelis">Tebligatın geliş anı (UETS'ye düştüğü)</label><input id="ca-gelis" type="datetime-local" value="${yerel}"></div>
        <div><label for="ca-merci">Merci</label><input id="ca-merci" list="ca-merciler" placeholder="ör. İstanbul 3. Asliye Hukuk Mahkemesi"></div>
        <div><label for="ca-tur">Tebliğ şekli</label><select id="ca-tur"><option value="uets">Elektronik (UETS: 5. gün tebliğ)</option><option value="elden">Fiziki / tebliğ tarihi biliniyor</option></select></div>
      </div>
      <datalist id="ca-merciler"><option value="Asliye Hukuk Mahkemesi"><option value="Asliye Ticaret Mahkemesi"><option value="İş Mahkemesi"><option value="Aile Mahkemesi"><option value="Tüketici Mahkemesi"><option value="Sulh Hukuk Mahkemesi"><option value="İcra Hukuk Mahkemesi"><option value="İcra Dairesi"><option value="Asliye Ceza Mahkemesi"><option value="Ağır Ceza Mahkemesi"><option value="Cumhuriyet Başsavcılığı Soruşturma Bürosu"><option value="İdare Mahkemesi"><option value="Vergi Mahkemesi"><option value="Bölge Adliye Mahkemesi Hukuk Dairesi"><option value="Yargıtay Hukuk Dairesi"></datalist>
      <div id="ca-sure-sonuc"></div>
      <p class="ca-soluk">Kural: UETS'de tebliğ, gelişi izleyen 5. gün sayılır (Tebligat K. 7/a); süre tebliğden sonraki günden başlar, son gün hafta sonuna denk gelirse Pazartesi 17:00'ye uzar. Resmî/adli tatil tarihi ileri almaz, yalnızca uyarı olarak gösterilir. Bu bir yardımcı hesaptır; somut süreyi kanun metniyle doğrulayın.</p>`;
    const hesapla = () => {
      const v = ic.querySelector('#ca-gelis').value;
      if (!v) return;
      const s = sureHesapla(new Date(v), ic.querySelector('#ca-merci').value, { elden: ic.querySelector('#ca-tur').value === 'elden' });
      const gunler = ['Pazar', 'Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi'];
      ic.querySelector('#ca-sure-sonuc').innerHTML = `<div class="ca-kart">
        <div class="ca-soluk">${esc(s.etiket)}</div>
        <div class="ca-hedef">${s.hedef_str} ${gunler[s.hedef.getDay()]} 17:00</div>
        <table><tr><th>Tebliğ sayılan gün</th><td>${s.teblig_str}</td></tr>
        <tr><th>7 gün</th><td>${s.d7_str}</td></tr><tr><th>14 gün / 2 hafta</th><td>${s.d14_str}</td></tr><tr><th>30 gün</th><td>${s.d30_str}</td></tr></table>
        ${s.uyarilar.map(u => `<div class="ca-uyari">⚠️ ${esc(u)}</div>`).join('')}
        <button class="ca-btn" type="button" id="ca-sure-ekle">📝 Belgeye ekle</button></div>`;
      ic.querySelector('#ca-sure-ekle').onclick = () => {
        const metin = `Tebliğ: ${s.teblig_str} — Son gün: ${s.hedef_str} (${s.etiket})`;
        try { document.execCommand('insertText', false, metin); } catch (e) { navigator.clipboard && navigator.clipboard.writeText(metin); }
        kapat();
      };
    };
    ic.querySelectorAll('input,select').forEach(el => el.addEventListener('input', hesapla));
    hesapla();
  }

  // --- A4 ---
  function a4Sekmesi(ic) {
    ic.innerHTML = `
      <p>Taranmış görselleri, fotoğrafları, çok sayfalı TIFF'leri ve PDF'leri <b>tek bir A4 PDF</b>'te birleştirir (NAPS2 yöntemi: 5 mm güvenli kenar, oran korumalı sığdırma, yataya otomatik dönüş). UYAP'a yüklemeye uygundur. İşlem tamamen cihazınızda yapılır.</p>
      <label for="ca-a4-dosya">Dosyalar (seçim sırasıyla birleştirilir)</label>
      <input id="ca-a4-dosya" type="file" multiple accept="image/*,.tif,.tiff,.pdf,application/pdf">
      <div class="ca-satir">
        <div><label><input id="ca-a4-sb" type="checkbox" style="width:auto"> Siyah-beyaz (tarama temizliği, küçük dosya)</label></div>
        <div><label for="ca-a4-esik">Eşik (koyuluk)</label><input id="ca-a4-esik" type="range" min="90" max="220" value="160"></div>
      </div>
      <button class="ca-btn ana" type="button" id="ca-a4-yap" disabled>📄 A4 PDF oluştur</button>
      <button class="ca-btn" type="button" id="ca-a4-ac" disabled>👁️ Oluştur ve editörde aç</button>
      <div id="ca-a4-durum" class="ca-soluk"></div>`;
    const giris = ic.querySelector('#ca-a4-dosya'), durum = ic.querySelector('#ca-a4-durum');
    const yap = ic.querySelector('#ca-a4-yap'), acB = ic.querySelector('#ca-a4-ac');
    giris.onchange = () => { yap.disabled = acB.disabled = !giris.files.length; durum.textContent = giris.files.length ? `${giris.files.length} dosya seçildi` : ''; };
    const calistir = async (editordeAc) => {
      yap.disabled = acB.disabled = true;
      try {
        const r = await a4PdfOlustur(Array.from(giris.files), { sb: ic.querySelector('#ca-a4-sb').checked, esik: +ic.querySelector('#ca-a4-esik').value }, m => { durum.textContent = 'İşleniyor ' + m; });
        const ad = (giris.files[0].name.replace(/\.[^.]+$/, '') || 'Belge') + '_A4.pdf';
        durum.textContent = `✓ ${r.sayfa} sayfa hazır.`;
        if (editordeAc && window.openPdfViewer) { kapat(); await window.openPdfViewer(r.bayt.buffer, ad); }
        else if (window.saveBytesSmart) await window.saveBytesSmart(r.bayt, ad, 'application/pdf');
      } catch (e) { durum.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
      yap.disabled = acB.disabled = false;
    };
    yap.onclick = () => calistir(false);
    acB.onclick = () => calistir(true);
  }

  // --- Sunucu gerektiren sekmeler ---
  // Paketli uygulama mı (sunucu kendiliğinden başlar) yoksa taşınabilir web mi (elle eşleştirme)?
  function paketli() {
    const ab = window.AndroidBridge;
    return !!(tauriInvoke() || (ab && !ab.__stub && typeof ab.asistanHazirla === 'function'));
  }
  let yenidenZam = null, yenidenSayac = 0;
  function sunucuHatasi(ic, e) {
    const anahtarYok = e && e.durum === 401;
    const sekme = aktifSekme;
    const kalici = e && (e.kalici || /çalışma ortamı yok|kapandı|pakette bulunamadı|başlatılamadı/i.test(e.message || ''));
    if (paketli() && !anahtarYok && (kalici || yenidenSayac >= 25)) {
      // Kendiliğinden düzelmeyecek durum: sonsuz "başlatılıyor" yerine gerçek neden gösterilir
      clearTimeout(yenidenZam);
      ic.innerHTML = `<div class="ca-kart"><b>⚠️ Hukuk Asistanı başlatılamadı</b>
        <p>${esc(e && e.message || 'Sunucu yanıt vermiyor.')}</p>
        <p class="ca-soluk">Editör normal çalışmaya devam eder. Sorun sürerse bu yazıyı geliştiriciye iletin.</p>
        <button class="ca-btn ana" type="button" id="ca-tekrar">🔄 Yeniden dene</button></div>`;
      ic.querySelector('#ca-tekrar').onclick = () => { yenidenSayac = 0; baglantiUnut(); sekmeAc(sekme); };
      return;
    }
    if (paketli() && !anahtarYok) {
      // Paketli uygulamada kullanıcıya komut gösterilmez: sunucu arka planda açılıyor, kendiliğinden yeniden denenir
      yenidenSayac++;
      ic.innerHTML = `<div class="ca-kart"><b>⏳ Hukuk Asistanı başlatılıyor…</b>
        <p>İlk açılışta bu 10-60 saniye sürebilir. Hazır olunca bu sayfa kendiliğinden açılır; bir şey yapmanız gerekmez.</p>
        <p class="ca-soluk">Deneme ${yenidenSayac}${e && e.message ? ' · son durum: ' + esc(e.message) : ''}</p></div>`;
      clearTimeout(yenidenZam);
      yenidenZam = setTimeout(() => {
        if (kok && kok.classList.contains('acik') && aktifSekme === sekme) { baglantiUnut(); sekmeAc(sekme); }
      }, Math.min(3000 + yenidenSayac * 1000, 10000));
      return;
    }
    ic.innerHTML = `<div class="ca-kart"><b>${anahtarYok ? '🔑 Eşleştirme gerekli' : '🔌 Asistan sunucusuna ulaşılamadı'}</b>
      <p>${anahtarYok ? 'Sunucu çalışıyor ama bu cihaz eşleştirilmemiş.' : 'Bu taşınabilir web sürümüdür: asistan özellikleri için bilgisayarda asistan sunucusunu başlatın. (Windows, Linux, macOS ve Android uygulamalarında sunucu gömülüdür ve kendiliğinden başlar.)'}</p>
      <pre>python3 asistan/sunucu.py</pre>
      <p class="ca-soluk">Sunucunun yazdırdığı anahtarı <b>Bağlantı</b> sekmesine girin.</p>
      <button class="ca-btn" type="button" id="ca-bagla">🔌 Bağlantı ayarları</button></div>`;
    ic.querySelector('#ca-bagla').onclick = () => sekmeAc('baglanti');
  }

  // --- UYAP Giriş: e-İmza takılıysa e-İmza, değilse Mobil İmza; oturum sürekli açık tutulur ---
  function zamanYaz(t) { return t ? new Date(t * 1000).toLocaleString('tr-TR') : '—'; }
  async function uyapSekmesi(ic) {
    ic.innerHTML = '<p class="ca-soluk">Yükleniyor…</p>';
    let v;
    try { v = await api('/api/uyap'); } catch (e) { sunucuHatasi(ic, e); return; }
    yenidenSayac = 0;
    const a = v.ayar || {};
    ic.innerHTML = `<div class="ca-kart" id="ca-uyap-durum"></div>
      <div class="ca-kart"><b>Giriş bilgileri</b>
        <p class="ca-soluk">e-İmza kartı takılıysa PIN ile e-İmza; takılı değilse ya da bağlantı koparsa Mobil İmza gönderilir ve oturum açılana kadar denenir. Bilgiler yalnızca bu cihazda saklanır.</p>
        <div class="ca-satir">
          <div><label>T.C. Kimlik No (Mobil İmza)</label><input id="ca-u-tc" inputmode="numeric" maxlength="11" placeholder="${a.tc_var ? esc(a.tc) + ' (kayıtlı)' : '11 hane'}"></div>
          <div><label>GSM</label><input id="ca-u-gsm" inputmode="tel" placeholder="${a.gsm_var ? esc(a.gsm) + ' (kayıtlı)' : '5321234567'}"></div>
          <div><label>Operatör</label><select id="ca-u-op">${[['turkcell', 'Turkcell'], ['turktelekom', 'Türk Telekom'], ['vodafone', 'Vodafone']].map(([k, ad]) => `<option value="${k}"${a.operator === k ? ' selected' : ''}>${ad}</option>`).join('')}</select></div>
          <div><label>e-İmza PIN</label><input id="ca-u-pin" type="password" autocomplete="off" placeholder="${a.pin_var ? '•••• (kayıtlı)' : 'isteğe bağlı'}"></div>
        </div>
        <label style="display:flex;gap:8px;align-items:center;color:inherit;font-size:14px"><input type="checkbox" id="ca-u-tut" style="width:auto"${a.bagli_tut !== false ? ' checked' : ''}> Oturumu sürekli açık tut (koptukça yeniden bağlan)</label>
        <div style="max-width:220px"><label>Kontrol aralığı (dakika)</label><input id="ca-u-ara" type="number" min="3" max="240" value="${a.aralik_dk || 10}"></div>
        <button class="ca-btn ana" type="button" id="ca-u-kaydet">💾 Kaydet ve bağlan</button>
        <button class="ca-btn" type="button" id="ca-u-simdi">🔄 Şimdi bağlan</button>
        <span id="ca-u-mesaj" class="ca-soluk"></span></div>`;
    const durumCiz = d => {
      const k = ic.querySelector('#ca-uyap-durum'); if (!k) return;
      const rozet = d.oturum === true ? '🟢 UYAP oturumu açık' : d.calisiyor ? '⏳ Bağlanılıyor…' : d.oturum === false ? '🔴 Oturum açılamadı — yeniden denenecek' : d.etkin ? '⚪ Sıradaki kontrol bekleniyor' : /kapalı/.test(d.neden || '') ? '⚪ Bağlı tut kapalı' : '⚪ Giriş bilgisi girilmedi';
      k.innerHTML = `<div class="ca-hedef" style="font-size:18px">${rozet}</div>
        ${d.neden ? `<div class="ca-uyari">${esc(d.neden)}</div>` : ''}
        ${d.son_hata ? `<div class="ca-uyari" style="border-color:#dc2626">⚠️ Son turda hata: ${esc(d.son_hata)}</div>` : ''}
        <p class="ca-soluk">Son deneme: ${zamanYaz(d.son_baslangic)} · Sonraki: ${d.sonraki ? zamanYaz(d.sonraki) : '—'}</p>
        ${d.gunluk && d.gunluk.length ? `<pre style="white-space:pre-wrap;max-height:160px;overflow:auto">${esc(d.gunluk.join('\n'))}</pre>` : ''}`;
      oturumNoktasi(d);
    };
    durumCiz(v);
    const mesaj = ic.querySelector('#ca-u-mesaj');
    ic.querySelector('#ca-u-kaydet').onclick = async () => {
      const g = { operator: ic.querySelector('#ca-u-op').value, bagli_tut: ic.querySelector('#ca-u-tut').checked, aralik_dk: +ic.querySelector('#ca-u-ara').value || 10 };
      const tc = ic.querySelector('#ca-u-tc').value.trim(), gsm = ic.querySelector('#ca-u-gsm').value.trim(), pin = ic.querySelector('#ca-u-pin').value;
      if (tc) g.tc = tc; if (gsm) g.gsm = gsm; if (pin) g.pin = pin;
      mesaj.textContent = 'Kaydediliyor…';
      try { await api('/api/uyap/ayar', { method: 'POST', govde: g }); mesaj.textContent = '✓ Kaydedildi; bağlantı başlatılıyor.'; uyapSekmesi(ic); }
      catch (e) { mesaj.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
    };
    ic.querySelector('#ca-u-simdi').onclick = async () => {
      try { durumCiz(await api('/api/uyap/simdi', { method: 'POST', govde: {} })); mesaj.textContent = '✓ Bağlantı denemesi başlatıldı.'; }
      catch (e) { mesaj.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
    };
    gorevIzleDurdur();
    izleZam = setInterval(() => { api('/api/uyap').then(durumCiz).catch(() => {}); }, 4000);
  }

  async function ajandaSekmesi(ic) {
    ic.innerHTML = `
      <div class="ca-kart">
        <b>📅 Ajanda & Süreli İşler Filtresi</b>
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin:8px 0;" id="ca-aj-hizli">
          <button class="ca-btn kucuk" type="button" data-gun="1">Bugün & 1 Gün</button>
          <button class="ca-btn kucuk" type="button" data-gun="3">3 Gün</button>
          <button class="ca-btn kucuk ana" type="button" data-gun="7">1 Hafta</button>
          <button class="ca-btn kucuk" type="button" data-gun="14">2 Hafta</button>
          <button class="ca-btn kucuk" type="button" data-gun="30">1 Ay</button>
          <button class="ca-btn kucuk" type="button" data-gun="90">3 Ay</button>
          <button class="ca-btn kucuk" type="button" data-gun="180">6 Ay</button>
          <button class="ca-btn kucuk" type="button" data-gun="-1">Tümü</button>
        </div>
        <div class="ca-satir" style="grid-template-columns:1fr 1fr 1fr auto;gap:8px;">
          <div><label>Başlangıç</label><input type="date" id="ca-aj-bas"></div>
          <div><label>Bitiş</label><input type="date" id="ca-aj-bit"></div>
          <div><label>Tür</label>
            <select id="ca-aj-tur">
              <option value="">Tümü (Duruşma + Süre)</option>
              <option value="sure">⏱️ Yalnızca Süreli İşler (Son Gün)</option>
              <option value="durusma">🏛️ Yalnızca Duruşmalar</option>
            </select>
          </div>
          <div style="display:flex;align-items:flex-end;"><button class="ca-btn ana" type="button" id="ca-aj-yenile">🔍 Filtrele</button></div>
        </div>
        <div style="margin-top:8px;">
          <input type="text" id="ca-aj-ara" placeholder="Ajandada ara (mahkeme, dosya no, açıklama, barkod)..." style="width:100%;">
        </div>
      </div>
      <div id="ca-aj-liste"><p class="ca-soluk">Yükleniyor…</p></div>`;

    const basIn = ic.querySelector('#ca-aj-bas');
    const bitIn = ic.querySelector('#ca-aj-bit');
    const turSel = ic.querySelector('#ca-aj-tur');
    const araIn = ic.querySelector('#ca-aj-ara');
    const listeEl = ic.querySelector('#ca-aj-liste');

    let aktifGun = 7;
    let sonOlaylar = [];

    const cizTablo = () => {
      const q = araIn.value.trim().toLowerCase();
      const secilenTur = turSel.value;
      const bugun = isoGun(new Date());

      const filtrelenen = sonOlaylar.filter(o => {
        if (secilenTur && o.tur !== secilenTur) return false;
        if (q) {
          const metin = [o.birim, o.esas, o.baslik, o.yer, o.barkod].filter(Boolean).join(' ').toLowerCase();
          if (!metin.includes(q)) return false;
        }
        return true;
      });

      if (!filtrelenen.length) {
        listeEl.innerHTML = '<div class="ca-kart"><p class="ca-soluk">Seçili tarih aralığında ve filtrede duruşma veya süre sonu bulunamadı.</p></div>';
        return;
      }

      listeEl.innerHTML = `
        <div class="ca-soluk" style="margin-bottom:6px;">Toplam <b>${filtrelenen.length}</b> kayıt listelendi</div>
        <table>
          <thead>
            <tr><th>Durum & Kalan</th><th>Tarih & Saat</th><th>Tür</th><th>Mahkeme & Esas</th><th>Açıklama & Kaynak</th></tr>
          </thead>
          <tbody>
            ${filtrelenen.map(o => {
              const k = o.kalan_gun !== undefined ? o.kalan_gun : 0;
              let rozet = '';
              if (k < 0) rozet = `<span class="hf-etiket" style="background:#FFCDD2;color:#B71C1C;">🔴 ${Math.abs(k)} gün önce</span>`;
              else if (k === 0) rozet = `<span class="hf-etiket" style="background:#FFE082;color:#E65100;font-weight:bold;">⚠️ BUGÜN</span>`;
              else if (k <= 3) rozet = `<span class="hf-etiket" style="background:#FFF9C4;color:#F57F17;font-weight:bold;">🟡 ${k} gün kaldı</span>`;
              else rozet = `<span class="hf-etiket" style="background:#C8E6C9;color:#1B5E20;">🟢 ${k} gün var</span>`;

              return `<tr>
                <td>${rozet}</td>
                <td style="white-space:nowrap;"><b>${esc((o.tarih || '').split('-').reverse().join('.'))}</b> <span class="ca-soluk">${esc(o.saat || '')}</span></td>
                <td>${o.tur === 'sure' ? '⏱️ <span style="color:#C62828;font-weight:bold;">Süre Sonu</span>' : '🏛️ Duruşma'}</td>
                <td><b>${esc(o.birim || '')}</b><div class="ca-soluk">${esc(o.esas || '')}</div></td>
                <td>${esc(o.baslik || '')}${o.yer ? `<div class="ca-soluk">📍 ${esc(o.yer)}</div>` : ''}<div class="ca-soluk">📌 Kaynak: ${esc(o.kaynak || '')}</div></td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>`;
    };

    const yukle = async () => {
      listeEl.innerHTML = '<p class="ca-soluk">Ajanda verileri alınıyor…</p>';
      try {
        let url = `/api/ajanda?gun=${aktifGun}`;
        if (basIn.value) url += `&baslangic=${encodeURIComponent(basIn.value)}`;
        if (bitIn.value) url += `&bitis=${encodeURIComponent(bitIn.value)}`;
        const v = await api(url);
        sonOlaylar = v.olaylar || [];
        cizTablo();
      } catch (e) {
        sunucuHatasi(listeEl, e);
      }
    };

    ic.querySelectorAll('#ca-aj-hizli button').forEach(btn => {
      btn.onclick = () => {
        ic.querySelectorAll('#ca-aj-hizli button').forEach(b => b.classList.remove('ana'));
        btn.classList.add('ana');
        aktifGun = parseInt(btn.dataset.gun, 10);
        basIn.value = '';
        bitIn.value = '';
        yukle();
      };
    });

    ic.querySelector('#ca-aj-yenile').onclick = yukle;
    turSel.onchange = cizTablo;
    araIn.oninput = cizTablo;

    yukle();
  }

  /** Katalogdaki indirilmiş evrakı editörde açar. */
  async function evrakAc(skey) {
    try {
      const r = await api('/api/evrak/dosya?skey=' + encodeURIComponent(skey), { ham: true });
      const buf = await r.arrayBuffer();
      const cd = r.headers.get('Content-Disposition') || '';
      const ad = decodeURIComponent((cd.match(/filename\*=UTF-8''([^;]+)/) || [])[1] || 'Evrak.pdf');
      kapat();
      if (window.openDocumentFromBytes) await window.openDocumentFromBytes(buf, ad);
      else if (window.openPdfViewer) await window.openPdfViewer(buf, ad);
    } catch (e) { alert('Evrak açılamadı: ' + e.message); }
  }
  function evrakDugmeleri(kap) {
    kap.querySelectorAll('button[data-skey]').forEach(b => { b.onclick = () => evrakAc(b.dataset.skey); });
  }

  function evrakSekmesi(ic) {
    ic.innerHTML = `<label for="ca-evrak-q">Ara (taraf, evrak türü, açıklama, dosya no — Türkçe harf duyarsız; hariç tutmak için -kelime)</label>
      <input id="ca-evrak-q" placeholder='ör. bilirkişi -ek "ağır ceza"'><div id="ca-evrak-sonuc" class="ca-soluk" style="margin-top:12px">Aramak için yazın.</div>`;
    const q = ic.querySelector('#ca-evrak-q'), sonuc = ic.querySelector('#ca-evrak-sonuc');
    let zam = null, kontrol = null, sira = 0;
    const ara = async () => {
      // Önceki arama sürüyorsa iptal edilir; geç gelen eski sonuç yenisinin üstüne yazılmaz
      if (kontrol) kontrol.abort();
      kontrol = new AbortController();
      const benim = ++sira;
      const metin = q.value.trim();
      if (metin && metin.replace(/[-"\s]/g, '').length < 2) { sonuc.textContent = 'En az 2 harf yazın.'; return; }
      sonuc.innerHTML = '<span class="ca-soluk">Aranıyor…</span>';
      try {
        const v = await api('/api/evrak/ara?limit=150&q=' + encodeURIComponent(metin), { signal: kontrol.signal });
        if (benim !== sira) return;
        if (!v.hazir) { sonuc.innerHTML = esc(v.mesaj); return; }
        sonuc.innerHTML = `<div class="ca-soluk">${v.sonuclar.length} sonuç (katalogda ${v.toplam_evrak} evrak)</div><table>${v.sonuclar.map(r => `
          <tr><td>${esc((r.tarih || '').slice(0, 10))}</td><td><b>${esc(r.tur || '')}</b><div class="ca-soluk">${esc(r.aciklama || '')}</div></td>
          <td>${esc(r.birim || '')}<div class="ca-soluk">${esc(r.dosya_no || '')} ${r.muvekkil ? '· ' + esc(r.muvekkil) : ''}</div></td>
          <td>${r.yerel ? `<button class="ca-btn" type="button" data-skey="${esc(r.skey)}">Aç</button>` : '<span class="ca-soluk">indirilmedi</span>'}</td></tr>`).join('')}</table>`;
        evrakDugmeleri(sonuc);
      } catch (e) { if (e.name !== 'AbortError' && benim === sira) sunucuHatasi(ic, e); }
    };
    q.addEventListener('input', () => { clearTimeout(zam); zam = setTimeout(ara, 350); });
    q.focus();
  }

  let izleZam = null;
  function gorevIzleDurdur() { if (izleZam) { clearInterval(izleZam); izleZam = null; } }

  const GOREV_ACIKLAMALARI = {
    "uets-senkron": "Ulusal Elektronik Tebligat Sistemi'ne (UETS) bağlanarak yeni tebligatları indirir, PTT delil kayıtlarını doğrular ve HMK/CMK yasal sürelerini otomatik hesaplar.",
    "uets-cevrimdisi": "İnternet veya portal bağlantısı olmadan, daha önce indirilmiş yerel CSV ve tebligat kayıtları üzerinden süre defterini günceller.",
    "uets-otokontrol": "Tebligat sürelerinde çakışma, kaçırılma riski veya eksik evrak olup olmadığını denetleyen güvenlik raporu üretir.",
    "evrak-nobetci": "UYAP Avukat Portalını nöbetçi modunda arka planda periyodik olarak tarar. Büronuzun tüm derdest dosyalarındaki yeni evrakları anında yakalar ve indirir.",
    "evrak-islemlerim": "UYAP Avukat Portalındaki 'İşlemlerim' sekmesini tarar; son yapılan havaleler, tensip zaptı onayları ve ara kararları anında günceller.",
    "evrak-tebligat": "UYAP sistemine düşen tebligat mazbatalarını ve tebellüğ belgelerini toplu olarak indirip yerel kataloğa ekler.",
    "evrak-durusmalar": "Büronuzun tüm mahkemelerdeki duruşma tarihlerini, saatlerini ve duruşma salonlarını UYAP'tan çeker.",
    "evrak-giris": "UYAP portalına güvenli elektronik imza veya mobil imza ile otomatik yetkilendirme ve oturum tazeleme işlemi yapar.",
    "asistan-gui": "Masaüstü Avukat Asistanı bağımsız yönetim penceresini açar.",
    "evrak-katalog": "İndirilen tüm evrakları yerel SQLite veritabanına indeksler ve A4 PDF dönüşüm kuyruğunu yönetir."
  };

  async function gorevSekmesi(ic) {
    ic.innerHTML = '<p class="ca-soluk">Görevler ve servisler yükleniyor…</p>';
    const ciz = async () => {
      const v = await api('/api/gorevler?satir=20');
      const acik = Array.from(ic.querySelectorAll('details[open]')).map(d => d.dataset.k);
      ic.innerHTML = `
        <div class="ca-kart" style="margin-bottom:12px;background:#E3F2FD;border:1px solid #90CAF9;">
          <b>⚙️ CanEditor Otomasyon & Arka Plan Görev Yöneticisi</b>
          <p class="ca-soluk" style="margin:4px 0 0 0;">Buradaki görevler UETS tebligat senkronizasyonunu, UYAP nöbetçi evrak takibini ve dosya indekslemeyi yürütür. İstediğiniz görevi tek tıkla başlatabilir veya durdurabilirsiniz.</p>
        </div>
        ${v.gorevler.map(g => {
          const aciklama = GOREV_ACIKLAMALARI[g.kimlik] || 'Arka plan otomasyon görevi.';
          let durumRozeti = '';
          if (g.calisiyor) durumRozeti = '<span class="hf-etiket" style="background:#C8E6C9;color:#1B5E20;font-weight:bold;">🟢 ÇALIŞIYOR</span>';
          else if (g.kod === 0) durumRozeti = '<span class="hf-etiket" style="background:#E8F5E9;color:#2E7D32;">✓ Tamamlandı</span>';
          else if (g.kod !== null) durumRozeti = `<span class="hf-etiket" style="background:#FFEBEE;color:#C62828;">❌ Hata (Kod ${g.kod})</span>`;
          else durumRozeti = '<span class="hf-etiket" style="background:#F5F5F5;color:#616161;">⚪ Beklemede</span>';

          return `<div class="ca-kart" style="margin-bottom:10px;">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
              <div>
                <b style="font-size:14px;">${esc(g.ad)}</b> ${durumRozeti}
              </div>
              <div>
                ${g.kullanilamaz ? `<span class="ca-soluk">🖥️ ${esc(g.kullanilamaz)}</span>` : (g.calisiyor ? `<button class="ca-btn kucuk" style="background:#D32F2F;color:#fff;" type="button" data-durdur="${g.kimlik}">⏹ Durdur</button>` : `<button class="ca-btn ana kucuk" type="button" data-baslat="${g.kimlik}">▶ ${g.pencere ? 'Pencereyi Aç' : 'Çalıştır'}</button>`)}
              </div>
            </div>
            <p style="font-size:12px;color:#455A64;margin:6px 0 8px 0;line-height:1.4;">${esc(aciklama)}</p>
            ${g.gunluk.length ? `<details data-k="${g.kimlik}" ${acik.includes(g.kimlik) || g.calisiyor ? 'open' : ''} style="margin-top:6px;"><summary class="ca-soluk" style="cursor:pointer;font-size:12px;">📄 Konsol Günlüğü (${g.gunluk.length} satır)</summary><pre style="max-height:180px;background:#263238;color:#ECEFF1;padding:8px;border-radius:4px;font-size:11px;overflow-x:auto;">${esc(g.gunluk.join('\n'))}</pre></details>` : ''}
          </div>`;
        }).join('')}`;

      ic.querySelectorAll('[data-baslat]').forEach(b => {
        b.onclick = async () => {
          b.disabled = true;
          try { await api('/api/gorev/' + b.dataset.baslat, { method: 'POST', govde: {} }); } catch (e) { alert(e.message); }
          ciz();
        };
      });
      ic.querySelectorAll('[data-durdur]').forEach(b => {
        b.onclick = async () => {
          await api('/api/gorev/' + b.dataset.durdur + '/durdur', { method: 'POST', govde: {} });
          ciz();
        };
      });
    };
    try { await ciz(); izleZam = setInterval(() => { ciz().catch(gorevIzleDurdur); }, 3000); } catch (e) { sunucuHatasi(ic, e); }
  }

  async function baglantiSekmesi(ic) {
    const b = baglantiOku();
    ic.innerHTML = `
      <div id="ca-bag-saglik" class="ca-kart" style="margin-bottom:12px;background:#FAFAFA;">
        <b>🔌 Canlı Bağlantı & Sistem Sağlık Durumu</b>
        <p class="ca-soluk">Sorgulanıyor…</p>
      </div>

      <div class="ca-kart">
        <b>⚙️ Yerel Sunucu ve Eşleştirme Yapılandırması</b>
        <div class="ca-satir" style="grid-template-columns:1fr 2fr;margin-top:8px;">
          <div><label for="ca-port">Yerel Port</label><input id="ca-port" type="number" value="${esc(b.port || 8765)}"></div>
          <div><label for="ca-anahtar">Eşleştirme Anahtarı</label><input id="ca-anahtar" value="${esc(b.anahtar || '')}" autocomplete="off" spellcheck="false"></div>
        </div>
        <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;">
          <button class="ca-btn ana" type="button" id="ca-kaydet">💾 Kaydet ve Sına</button>
          <button class="ca-btn" type="button" id="ca-log-indir">📥 Teşhis ve Hata Loglarını İndir (Zip)</button>
        </div>
      </div>

      <div id="ca-bag-sonuc" class="ca-kart" style="margin-top:12px;"></div>
      <p class="ca-soluk" style="margin-top:8px;">Anahtarı terminalden görmek için: <code>python3 asistan/sunucu.py --anahtar</code>. Sunucu yalnızca cihaz içinden (127.0.0.1) erişilebilir, dış ağa kapalıdır.</p>`;

    const saglikEl = ic.querySelector('#ca-bag-saglik');
    const sonuc = ic.querySelector('#ca-bag-sonuc');

    const saglikYukle = async () => {
      try {
        const s = await api('/api/baglanti/istatistik');
        saglikEl.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
            <b>🔌 Canlı Bağlantı & Sistem Sağlık Durumu</b>
            <span class="hf-etiket" style="background:#C8E6C9;color:#1B5E20;font-weight:bold;">🟢 KESİNTİSİZ AKTİF</span>
          </div>
          <table style="margin-top:8px;">
            <tr><th>Kesintisiz Çalışma Süresi</th><td><b>${esc(s.calisma_suresi)}</b></td></tr>
            <tr><th>İşlenen İstek Sayısı</th><td>${esc(s.toplam_istek)} istek</td></tr>
            <tr><th>Ağ Gecikmesi (Ping)</th><td>${s.ping_ms == null ? "UYAP'a ulaşılamadı" : esc(s.ping_ms) + " ms (UYAP Avukat Portal)"}</td></tr>
            <tr><th>Bağlantı Kesinti Kaydı</th><td>${esc(s.son_kesinti)} (${s.kesinti_sayisi} kesinti)</td></tr>
            <tr><th>Google Drive Webhook</th><td>${s.drive_webhook_tanimli ? '🟢 Tanımlı ve Hazır' : '⚪ Webhook linki girilmedi (Drive sekmesinden ayarlayabilirsiniz)'}</td></tr>
            <tr><th>Sunucu Saati</th><td>${esc(s.sunucu_zamani)}</td></tr>
          </table>`;
      } catch (e) {
        saglikEl.innerHTML = `<b>🔌 Canlı Bağlantı Durumu</b><div class="ca-soluk">Bağlantı istatistikleri alınamadı: ${esc(e.message)}</div>`;
      }
    };

    const sina = async () => {
      sonuc.textContent = 'Sınanıyor…';
      try {
        const v = await api('/api/durum');
        const m = v.moduller;
        const isaret = x => x ? '✓' : '✗';
        sonuc.innerHTML = `<b>✓ Yerel Asistan Sunucusu Bağlı</b> — sürüm ${esc(v.surum)} (${esc(v.platform)}${v.termux ? ', Termux' : ''})
          <table style="margin-top:8px;">
            <tr><th>UETS / Avukat Asistanı</th><td>bağımlılıklar ${isaret(m.avukatasistan.bagimliliklar)} · yapılandırma ${isaret(m.avukatasistan.yapilandirildi)}</td></tr>
            <tr><th>UYAP Evrak Kataloğu</th><td>bağımlılıklar ${isaret(m.evrak.bagimliliklar)} · katalog ${isaret(m.evrak.katalog)}</td></tr>
            <tr><th>A4 PDF Motoru</th><td>bağımlılıklar ${isaret(m.a4.bagimliliklar)}</td></tr>
          </table>`;
        saglikYukle();
      } catch (e) {
        sonuc.innerHTML = `<span class="ca-hata">${esc(e.durum === 401 ? 'Eşleştirme anahtarı yanlış.' : 'Sunucuya ulaşılamadı: ' + e.message)}</span>`;
      }
    };

    ic.querySelector('#ca-kaydet').onclick = () => {
      baglantiYaz({ port: +ic.querySelector('#ca-port').value || 8765, anahtar: ic.querySelector('#ca-anahtar').value.trim() });
      sina();
    };

    ic.querySelector('#ca-log-indir').onclick = async () => {
      try {
        const res = await api('/api/loglar/indir', { ham: true });
        const buf = await res.arrayBuffer();
        if (window.saveBytesSmart) {
          await window.saveBytesSmart(buf, 'CanEditor_Tehis_Loglari.zip', 'application/zip');
        } else {
          downloadBlob(new Blob([buf], { type: 'application/zip' }), 'CanEditor_Tehis_Loglari.zip');
        }
        alert('✓ Tüm teşhis ve hata logları CanEditor_Tehis_Loglari.zip olarak başarıyla indirildi.');
      } catch (e) {
        alert('Loglar indirilemedi: ' + e.message);
      }
    };

    sina();
  }


  // =========================================================================
  // 5. YENİ EVRAK İZLEYİCİSİ (rozet + uygulama içi ve sistem bildirimi) ve DRIVE DURUMU
  // =========================================================================
  const GORULEN = 'canasistan.gorulen';
  let sonYenilik = { evrak_sayisi: 0, tebligat_sayisi: 0, evraklar: [], tebligatlar: [] }, sonToplam = 0;
  const gorulenOku = () => { try { return localStorage.getItem(GORULEN) || ''; } catch (e) { return ''; } };
  const gorulenYaz = v => { try { localStorage.setItem(GORULEN, v); } catch (e) { /* özel pencere */ } };
  function yerelIso(d) { return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 19); }

  function rozetCiz(n) {
    stilEkle();
    const baslik = Array.from(document.querySelectorAll('.ce-menu-title')).find(b => b.textContent.trim().startsWith('Asistan'));
    const y0 = yuzenKur(); if (y0 && !n) y0.querySelector('.ca-sayi').textContent = '';
    if (!baslik) return;
    let r = baslik.querySelector('.ca-rozet');
    if (!n) { if (r) r.remove(); return; }
    if (!r) { r = document.createElement('span'); r.className = 'ca-rozet'; baslik.appendChild(r); }
    r.textContent = n > 99 ? '99+' : String(n);
    r.title = n + ' yeni evrak / tebligat';
    const y = yuzenKur(); if (y) y.querySelector('.ca-sayi').textContent = n ? ' ' + (n > 99 ? '99+' : n) : '';
    const sek = kok && kok.querySelector('nav button[data-sekme="yeni"]');
    if (sek) sek.textContent = '🔔 Yeni (' + n + ')';
  }

  // Her ekranda görünen Asistan düğmesi: yeni evrak sayısı + UYAP oturum durumu tek bakışta
  let yuzenDugme = null;
  function yuzenKur() {
    if (yuzenDugme || !document.body) return yuzenDugme;
    stilEkle();
    yuzenDugme = document.createElement('button');
    yuzenDugme.type = 'button'; yuzenDugme.id = 'ca-yuzen'; yuzenDugme.title = 'Hukuk Asistanı';
    yuzenDugme.innerHTML = '<span class="ca-nokta"></span>⚖️ Asistan<span class="ca-sayi"></span>';
    yuzenDugme.onclick = () => ac(aktifSekme === 'sure' ? 'uyap' : aktifSekme);
    document.body.appendChild(yuzenDugme);
    return yuzenDugme;
  }
  function oturumNoktasi(d) {
    const b = yuzenKur(); if (!b) return;
    const n = b.querySelector('.ca-nokta');
    n.style.background = d.oturum === true ? '#16a34a' : d.calisiyor ? '#f59e0b' : d.oturum === false ? '#dc2626' : '#9ca3af';
    b.title = 'Hukuk Asistanı — ' + (d.oturum === true ? 'UYAP oturumu açık' : d.calisiyor ? 'UYAP\'a bağlanılıyor' : d.oturum === false ? 'UYAP oturumu kapalı' : 'UYAP oturumu bilinmiyor');
  }

  function bildir(baslik, govde) {
    if (window.showToast) window.showToast('🔔 ' + baslik);
    try {
      if ('Notification' in window && Notification.permission === 'granted') new Notification(baslik, { body: govde });
    } catch (e) { /* WebView bildirim desteklemiyor olabilir */ }
  }

  async function yenilikDenetle() {
    let sonra = gorulenOku();
    if (!sonra) { sonra = yerelIso(new Date(Date.now() - 86400000)); gorulenYaz(sonra); }
    const v = await api('/api/yenilikler?limit=50&sonra=' + encodeURIComponent(sonra));
    sonYenilik = v;
    const toplam = (v.evrak_sayisi || 0) + (v.tebligat_sayisi || 0);
    if (toplam > sonToplam) {
      const ilk = (v.evraklar[0] || v.tebligatlar[0] || {});
      bildir(`UYAP'a ${toplam - sonToplam} yeni evrak/tebligat düştü`,
             [ilk.birim, ilk.dosya_no || ilk.esas, ilk.tur || ilk.baslik].filter(Boolean).join(' · '));
    }
    sonToplam = toplam;
    rozetCiz(toplam);
    return v;
  }

  // Sunucu varsa 2 dakikada bir; ulaşılamazsa 10 dakikaya kadar seyrekleşir (pil/ağ dostu)
  let izleAralik = 120000;
  function yenilikIzle() {
    yenilikDenetle().then(() => { izleAralik = 120000; })
      .catch(() => { izleAralik = Math.min(izleAralik * 2, 600000); })
      .finally(() => setTimeout(yenilikIzle, izleAralik));
  }

  function yeniSekmesi(ic) {
    ic.innerHTML = '<p class="ca-soluk">Yeni evraklar ve tebligatlar taranıyor…</p>';

    let mevcutOffset = 0;
    const sayfaBoyutu = 50;
    let tumEvraklar = [];
    let seciliSkeys = new Set();
    let sonVeri = null;

    async function yukleVeCiz(ekle = false) {
      if (!ekle) {
        ic.innerHTML = '<p class="ca-soluk">Yükleniyor…</p>';
        mevcutOffset = 0;
        tumEvraklar = [];
        seciliSkeys.clear();
      }

      let sonra = gorulenOku();
      if (!sonra) { sonra = yerelIso(new Date(Date.now() - 86400000)); gorulenYaz(sonra); }

      const qVal = ic.querySelector('#ca-yeni-q') ? ic.querySelector('#ca-yeni-q').value.trim() : '';
      const durumVal = ic.querySelector('#ca-yeni-durum') ? ic.querySelector('#ca-yeni-durum').value : '';

      try {
        const v = await api(`/api/yenilikler?limit=${sayfaBoyutu}&offset=${mevcutOffset}&sonra=${encodeURIComponent(sonra)}&q=${encodeURIComponent(qVal)}&durum=${encodeURIComponent(durumVal)}`);
        sonVeri = v;
        const yeniGelenler = v.evraklar || [];
        if (ekle) {
          tumEvraklar = tumEvraklar.concat(yeniGelenler);
        } else {
          tumEvraklar = yeniGelenler;
        }

        const tb = v.tebligatlar || [];

        if (!tumEvraklar.length && !tb.length && !qVal && !durumVal) {
          ic.innerHTML = `
            <div class="ca-kart">
              <p>✅ Son bakıştan (<b>${esc((v.sonra || '').replace('T', ' '))}</b>) beri yeni evrak veya tebligat düşmedi.</p>
              <p class="ca-soluk">Arka plandaki UYAP nöbetçisi <b>Görevler</b> sekmesinde çalışmaktadır; yeni evrak düştüğünde burada listelenir.</p>
              <button class="ca-btn ana" type="button" id="ca-yeni-tekrar-tara">↻ Şimdi Yeniden Tara</button>
            </div>`;
          ic.querySelector('#ca-yeni-tekrar-tara').onclick = () => yukleVeCiz(false);
          return;
        }

        ic.innerHTML = `
          <div class="ca-satir" style="grid-template-columns:2fr 1fr auto;margin-bottom:8px">
            <div>
              <label>Yeni Evraklarda Ara (esas no, mahkeme, tür, müvekkil)</label>
              <input id="ca-yeni-q" value="${esc(qVal)}" placeholder="ör. 2026/171, talimat, tanık, Aksaray...">
            </div>
            <div>
              <label>İndirme Durumu</label>
              <select id="ca-yeni-durum">
                <option value=""${!durumVal ? ' selected' : ''}>Tümü</option>
                <option value="yerel"${durumVal === 'yerel' ? ' selected' : ''}>Yalnız İndirilenler (Yerel)</option>
                <option value="indirilmedi"${durumVal === 'indirilmedi' ? ' selected' : ''}>İndirilmeyi Bekleyenler</option>
              </select>
            </div>
            <div style="display:flex;align-items:flex-end">
              <button class="ca-btn ana" type="button" id="ca-yeni-filtre-btn">🔍 Filtrele</button>
            </div>
          </div>

          <div class="hf-toplu-bar">
            <label style="display:inline-flex;align-items:center;gap:6px;cursor:pointer;color:#fff;margin:0;font-weight:600">
              <input type="checkbox" id="ca-yeni-sec-tum" style="width:18px;height:18px"> Tümünü Seç
            </label>
            <span id="ca-yeni-secili-sayi" style="font-size:13px;opacity:.9">(${seciliSkeys.size} seçili)</span>
            <div style="display:inline-flex;gap:6px;flex-wrap:wrap;margin-left:auto">
              <button class="ca-btn kucuk altin" type="button" id="ca-toplu-indir">📥 Seçilenleri İndir</button>
              <button class="ca-btn kucuk" type="button" id="ca-toplu-pdf">📄 PDF'e Çevir</button>
              <button class="ca-btn kucuk" type="button" id="ca-toplu-drive">☁️ Drive'a Gönder</button>
              <button class="ca-btn kucuk" type="button" id="ca-toplu-okundu">✓ Görüldü Say</button>
              <button class="ca-btn kucuk" type="button" id="ca-yeni-tum-goruldu">✓ Tüm Listeyi Görüldü Say</button>
            </div>
          </div>

          <div class="ca-soluk" style="margin:6px 0 10px">
            🕒 <b>${esc((v.sonra || '').replace('T', ' '))}</b> sonrası: 
            Toplam <b>${v.evrak_sayisi}</b> yeni evrak, <b>${v.tebligat_sayisi}</b> tebligat 
            (Şu an listelenen: <b>${tumEvraklar.length}</b> evrak)
          </div>

          ${tb.length ? `
            <div class="ca-kart" style="border-left:4px solid #ef4444;margin-bottom:12px">
              <b>📨 Yeni Tebligatlar (${tb.length})</b>
              <table>
                <thead><tr><th>Zaman</th><th>Kaynak</th><th>Mahkeme / Esas</th><th>Evrak / Süre</th></tr></thead>
                <tbody>
                  ${tb.map(t => `
                    <tr>
                      <td style="white-space:nowrap">${esc((t.zaman || '').replace('T', ' ').slice(0, 16))}</td>
                      <td><span class="hf-etiket ${t.kaynak === 'UETS' ? 'acik' : ''}">${esc(t.kaynak)}</span></td>
                      <td><b>${esc(t.birim || '')}</b><div style="font-weight:700;color:var(--hf-navy)">${esc(t.esas || '')}</div></td>
                      <td>
                        <b>${esc(t.baslik || '')}</b>
                        ${t.son_gun ? `<div style="color:#dc2626;font-weight:700">⏳ Son gün: ${esc(t.son_gun)}</div>` : ''}
                      </td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>` : ''}

          <div id="ca-yeni-evrak-kutusu">
            ${tumEvraklar.map(r => `
              <div class="ca-kart" style="display:flex;align-items:flex-start;gap:10px;margin-bottom:8px">
                <input type="checkbox" data-skey-chk="${esc(r.skey)}" ${seciliSkeys.has(r.skey) ? 'checked' : ''} style="width:18px;height:18px;margin-top:4px">
                <div style="flex:1">
                  <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:4px">
                    <span class="ca-soluk">🕒 ${esc((r.ilk_gorulme || r.tarih || '').replace('T', ' ').slice(0, 16))}</span>
                    <span class="hf-etiket ${r.yerel ? 'acik' : ''}">${r.yerel ? '🟢 İndirildi' : '🟠 İndirilmedi'}</span>
                  </div>
                  <div style="font-size:15px;font-weight:700;margin:3px 0 2px">${esc(r.tur || 'Evrak')}</div>
                  <div class="ca-soluk" style="line-height:1.4">${esc(r.aciklama || '')}</div>
                  <div style="margin-top:6px;font-size:13px">
                    🏛️ <button class="ca-btn kucuk" type="button" data-git-dkey="${esc(r.dkey)}" title="Dosyayı aç">
                      <b>${esc(r.birim || 'Mahkeme')}</b> — <span style="color:var(--hf-navy);font-weight:700">${esc(r.dosya_no || '—')}</span>
                    </button>
                    ${r.muvekkil ? `<span class="ca-soluk">· Müvekkil: <b>${esc(r.muvekkil)}</b></span>` : ''}
                  </div>
                </div>
                <div style="display:flex;flex-direction:column;gap:4px;flex-shrink:0">
                  ${r.yerel ? `
                    <button class="ca-btn kucuk ana" type="button" data-ac-skey="${esc(r.skey)}">👁️ Aç</button>
                    <button class="ca-btn kucuk" type="button" data-pdf-skey="${esc(r.skey)}">📄 PDF</button>
                  ` : `
                    <button class="ca-btn kucuk altin" type="button" data-indir-skey="${esc(r.skey)}">⬇️ İndir</button>
                    <button class="ca-btn kucuk" type="button" data-git-dkey="${esc(r.dkey)}">📁 Dosya</button>
                  `}
                </div>
              </div>
            `).join('') || '<div class="ca-kart"><p class="ca-soluk">Kriterlere uygun yeni evrak bulunamadı.</p></div>'}
          </div>

          ${v.filtrelenen_evrak > tumEvraklar.length ? `
            <div style="text-align:center;margin:16px 0">
              <button class="ca-btn ana" type="button" id="ca-yeni-daha-fazla">
                📥 +50 Evrak Daha Yükle (Kalan: ${v.filtrelenen_evrak - tumEvraklar.length})
              </button>
            </div>
          ` : ''}

          <div style="margin-top:14px;display:flex;gap:8px;flex-wrap:wrap">
            <button class="ca-btn" type="button" id="ca-yeni-gorudum-alt">✓ Tümünü Görüldü Say</button>
            ${('Notification' in window && Notification.permission === 'default') ? '<button class="ca-btn" type="button" id="ca-bildirim-izin">🔔 Masaüstü bildirimlerine izin ver</button>' : ''}
          </div>
        `;

        // Event listener bağlamaları
        const secTum = ic.querySelector('#ca-yeni-sec-tum');
        const secSayi = ic.querySelector('#ca-yeni-secili-sayi');

        const guncelleSeciliSayi = () => {
          secSayi.textContent = `(${seciliSkeys.size} seçili)`;
          if (secTum) secTum.checked = tumEvraklar.length > 0 && seciliSkeys.size === tumEvraklar.length;
        };

        if (secTum) {
          secTum.onchange = () => {
            if (secTum.checked) {
              tumEvraklar.forEach(e => seciliSkeys.add(e.skey));
            } else {
              seciliSkeys.clear();
            }
            ic.querySelectorAll('[data-skey-chk]').forEach(c => { c.checked = secTum.checked; });
            guncelleSeciliSayi();
          };
        }

        ic.querySelectorAll('[data-skey-chk]').forEach(c => {
          c.onchange = () => {
            const skey = c.dataset.skeyChk;
            if (c.checked) seciliSkeys.add(skey); else seciliSkeys.delete(skey);
            guncelleSeciliSayi();
          };
        });

        // Tekil işlemler
        ic.querySelectorAll('[data-ac-skey]').forEach(b => {
          b.onclick = () => evrakAc(b.dataset.acSkey);
        });

        ic.querySelectorAll('[data-pdf-skey]').forEach(b => {
          b.onclick = async () => {
            try {
              const res = await api('/api/evrak/toplu_islem', { method: 'POST', govde: { eylem: 'pdf', skeys: [b.dataset.pdfSkey] } });
              alert(res.mesaj || 'PDF dönüştürme tamamlandı.');
              yukleVeCiz(false);
            } catch (e) { alert(e.message); }
          };
        });

        ic.querySelectorAll('[data-indir-skey]').forEach(b => {
          b.onclick = async () => {
            try {
              const res = await api('/api/evrak/toplu_islem', { method: 'POST', govde: { eylem: 'indir', skeys: [b.dataset.indirSkey] } });
              alert(res.mesaj || 'İndirme kuyruğuna alındı.');
            } catch (e) { alert(e.message); }
          };
        });

        ic.querySelectorAll('[data-git-dkey]').forEach(b => {
          b.onclick = () => {
            if (b.dataset.gitDkey) dosyaDetayAc(b.dataset.gitDkey);
          };
        });

        // Toplu Eylemler
        const calistirToplu = async (eylem) => {
          const skeys = Array.from(seciliSkeys);
          if (!skeys.length) return alert('Lütfen en az bir evrak seçin.');
          try {
            const res = await api('/api/evrak/toplu_islem', { method: 'POST', govde: { eylem, skeys } });
            alert(res.mesaj || `${skeys.length} evrak işlendi.`);
            if (eylem === 'okundu') {
              yukleVeCiz(false);
            }
          } catch (e) { alert(e.message); }
        };

        const topIndir = ic.querySelector('#ca-toplu-indir');
        if (topIndir) topIndir.onclick = () => calistirToplu('indir');

        const topPdf = ic.querySelector('#ca-toplu-pdf');
        if (topPdf) topPdf.onclick = () => calistirToplu('pdf');

        const topDrive = ic.querySelector('#ca-toplu-drive');
        if (topDrive) topDrive.onclick = () => calistirToplu('drive');

        const topOkundu = ic.querySelector('#ca-toplu-okundu');
        if (topOkundu) topOkundu.onclick = () => calistirToplu('okundu');

        const gorulduTumu = () => {
          gorulenYaz(sonVeri && sonVeri.en_yeni ? sonVeri.en_yeni : yerelIso(new Date()));
          sonToplam = 0;
          rozetCiz(0);
          yukleVeCiz(false);
        };

        const tumGorulduBtn = ic.querySelector('#ca-yeni-tum-goruldu');
        if (tumGorulduBtn) tumGorulduBtn.onclick = gorulduTumu;

        const gorudumAlt = ic.querySelector('#ca-yeni-gorudum-alt');
        if (gorudumAlt) gorudumAlt.onclick = gorulduTumu;

        const filtreBtn = ic.querySelector('#ca-yeni-filtre-btn');
        if (filtreBtn) filtreBtn.onclick = () => yukleVeCiz(false);

        const qInput = ic.querySelector('#ca-yeni-q');
        if (qInput) {
          qInput.onkeydown = e => { if (e.key === 'Enter') yukleVeCiz(false); };
        }

        const dInput = ic.querySelector('#ca-yeni-durum');
        if (dInput) dInput.onchange = () => yukleVeCiz(false);

        const dahaFazlaBtn = ic.querySelector('#ca-yeni-daha-fazla');
        if (dahaFazlaBtn) {
          dahaFazlaBtn.onclick = () => {
            mevcutOffset += sayfaBoyutu;
            yukleVeCiz(true);
          };
        }

        const iz = ic.querySelector('#ca-bildirim-izin');
        if (iz) iz.onclick = () => Notification.requestPermission().then(() => yukleVeCiz(false));

      } catch (e) { sunucuHatasi(ic, e); }
    }

    yukleVeCiz(false);
  }

  async function driveSekmesi(ic) {
    ic.innerHTML = '<p class="ca-soluk">Yükleniyor…</p>';
    try {
      const v = await api('/api/drive');
      const tarih = t => t ? esc(t.replace('T', ' ').slice(0, 16)) : '—';
      const durum = !v.yapilandirildi ? '⚪ Yapılandırılmadı' : (v.mod === 'webhook' ? '🟢 Bulut (webhook)' : (v.dizin_var ? (v.yazilabilir ? '🟢 Bağlı' : '🟠 Salt okunur') : '🔴 Klasör yok'));
      const k = v.katalog || {}, n = v.nobetci, kl = v.klasor;
      ic.innerHTML = `<div class="ca-kart"><div class="ca-hedef" style="font-size:18px">${durum}</div>
        <table>
          <tr><th>Eşitleme yöntemi</th><td>${v.mod === 'yerel' ? 'Google Drive masaüstü klasörü' : v.mod === 'webhook' ? 'Google Drive webhook' : '—'}</td></tr>
          ${v.dizin ? `<tr><th>Drive klasörü</th><td><code>${esc(v.dizin)}</code></td></tr>` : ''}
          ${kl ? `<tr><th>Klasördeki dosyalar</th><td>${kl.dosya.toLocaleString('tr-TR')}${kl.tam_sayim ? '' : '+'} dosya · ${kl.boyut_mb.toLocaleString('tr-TR')} MB · son değişiklik ${tarih(kl.son_degisiklik)}</td></tr>` : ''}
          <tr><th>Katalog yedeği (Drive)</th><td>${v.yedek ? tarih(v.yedek.zaman) + ' · ' + v.yedek.boyut_mb + ' MB' : '—'}</td></tr>
          ${k.indirilen !== undefined ? `<tr><th>İndirilen evrak</th><td>${k.indirilen.toLocaleString('tr-TR')}${k.drivede !== null && k.drivede !== undefined ? ` · Drive'da ${k.drivede.toLocaleString('tr-TR')} · <b>${k.driveda_olmayan.toLocaleString('tr-TR')}</b> Drive dışında` : ''}</td></tr>
          <tr><th>İndirilmeyi bekleyen</th><td>${k.indirilmeyi_bekleyen.toLocaleString('tr-TR')}</td></tr>` : ''}
          <tr><th>Nöbetçi son tur</th><td>${n ? `${tarih(n.son_tur)} (${n.dakika_once} dk önce, her ${n.aralik_dk} dk) ${n.gecikti ? '🔴' : '🟢'} · yeni indirilen: ${(n.istatistik || {}).new_downloaded || 0}` : '—'}</td></tr>
        </table>
        ${(v.uyarilar || []).map(u => `<div class="ca-uyari">⚠️ ${esc(u)}</div>`).join('')}
        <button class="ca-btn" type="button" id="ca-drive-yenile">↻ Yenile</button>
        <button class="ca-btn" type="button" id="ca-drive-nobet">▶ Nöbetçi turunu şimdi çalıştır</button></div>
        <p class="ca-soluk">Drive klasörü UYAP evrak indiricinin ayarlarından (watcher_config.json → google_drive_dir) gelir.</p>`;
      ic.querySelector('#ca-drive-yenile').onclick = () => driveSekmesi(ic);
      ic.querySelector('#ca-drive-nobet').onclick = async () => {
        try { await api('/api/gorev/evrak-nobetci', { method: 'POST', govde: {} }); sekmeAc('gorev'); } catch (e) { alert(e.message); }
      };
    } catch (e) { sunucuHatasi(ic, e); }
  }

  // Masaüstü / Android uygulamasında (ya da web'de eşleştirme yapılmışsa) izleyici kendiliğinden başlar
  function izleyiciBaslasinMi() {
    const ab = window.AndroidBridge;
    return !!(tauriInvoke() || (ab && !ab.__stub && ab.asistanHazirla) || baglantiOku().anahtar);
  }
  if (typeof document !== 'undefined' && document.addEventListener) {
    const oturumIzle = () => { api('/api/uyap').then(oturumNoktasi).catch(() => {}).finally(() => setTimeout(oturumIzle, 30000)); };
    const basla = () => { if (izleyiciBaslasinMi()) { yuzenKur(); setTimeout(yenilikIzle, 4000); setTimeout(oturumIzle, 6000); } };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', basla); else basla();
  }


  // =========================================================================
  // 6. HUKUKİ HESAPLAMALAR (hukuk_hesap.js — hayfahukuk hesaplayıcılarıyla aynı kurallar, 2026 tarifeleri)
  // =========================================================================
  let hesapTur = 'vekalet';
  function hesapSekmesi(ic) {
    const H = window.HukukHesap;
    if (!H) { ic.innerHTML = '<p class="ca-hata">Hesaplama motoru (hukuk_hesap.js) yüklenemedi.</p>'; return; }
    const bugun = isoGun(new Date());
    const secenek = (nesne, sec) => Object.entries(nesne).map(([k, v]) => `<option value="${k}"${k === sec ? ' selected' : ''}>${esc(v[0])} — ${H.TL(v[1])}</option>`).join('');
    const FORM = {
      vekalet: `<div class="ca-satir"><div><label>Ücret türü</label><select name="tur"><option value="nispi">Nispi (dava değeri)</option><option value="maktu">Maktu</option><option value="icra">İcra takibi</option></select></div>
        <div><label>Yargı yeri (maktu alt sınır)</label><select name="mahkeme">${secenek(H.TARIFE.aautMaktu, 'asliye')}</select></div>
        <div><label>Dava değeri / takip miktarı (TL)</label><input name="deger" inputmode="decimal" placeholder="ör. 250.000"></div></div>
        <label><input type="checkbox" name="yarisi" style="width:auto"> Ön inceleme tutanağı imzalanmadan sona erdi (yarısı, m.7/1)</label>`,
      faiz: `<div class="ca-satir"><div><label>Faiz türü</label><select name="tur"><option value="kanuni">Kanuni faiz (3095 m.1)</option><option value="avans">Ticari temerrüt — avans faizi (m.2/2)</option><option value="ttk">TTK 1530 geç ödeme</option><option value="ozel">Sözleşme / özel oran</option></select></div>
        <div><label>Anapara (TL)</label><input name="anapara" inputmode="decimal" placeholder="ör. 100.000"></div>
        <div><label>Başlangıç</label><input type="date" name="bas"></div><div><label>Bitiş</label><input type="date" name="bit" value="${bugun}"></div>
        <div><label>Özel yıllık oran (%)</label><input name="oran" inputmode="decimal" placeholder="yalnız özel oranda"></div></div>
        <label><input type="checkbox" name="giderim" style="width:auto"> TTK 1530 asgari giderim tutarını ekle</label>`,
      harc: `<div class="ca-satir"><div><label>Harç türü</label><select name="tur"><option value="dava">Dava açılışı</option><option value="icra">İcra takibi</option><option value="kanunyolu">Kanun yolu / diğer</option></select></div>
        <div><label>Mahkeme</label><select name="mahkeme"><option value="asliye">Asliye / idare</option><option value="sulh">Sulh / icra mahkemesi</option></select></div>
        <div><label>Dava değeri / takip miktarı (TL, maktu için boş)</label><input name="deger" inputmode="decimal"></div></div>
        <label><input type="checkbox" name="vekaletname" style="width:auto" checked> Vekâletname suret harcı</label>`,
      smm: `<div class="ca-satir"><div><label>Girilen tutar</label><select name="giris"><option value="brut">Brüt ücret</option><option value="net">Net (elime geçecek)</option><option value="tahsil">Müvekkilden tahsil edilecek</option></select></div>
        <div><label>Tutar (TL)</label><input name="tutar" inputmode="decimal" placeholder="ör. 20.000"></div>
        <div><label>Müvekkil</label><select name="sorumlu"><option value="1">Şirket / vergi sorumlusu (stopaj keser)</option><option value="">Gerçek kişi (stopaj yok)</option></select></div></div>`,
      cmk: `<div class="ca-satir"><div><label>Görevlendirme</label><select name="kalem">${secenek(H.TARIFE.cmk, 'agir')}</select></div>
        <div><label>Adet (tek makbuz)</label><input name="adet" type="number" min="1" value="1"></div></div>`,
      infaz: `<div class="ca-satir">
        <div><label>Yıl</label><input name="yil" type="number" min="0" value="3"></div>
        <div><label>Ay</label><input name="ay" type="number" min="0" value="0"></div>
        <div><label>Gün</label><input name="gun" type="number" min="0" value="0"></div>
        <div><label>Koşullu Salıverilme Oranı</label><select name="oran"><option value="1/2">1/2 (Genel)</option><option value="2/3">2/3 (İstisna / Mükerrir)</option><option value="3/4">3/4 (Ağır / Terör / Uyuşturucu)</option></select></div>
        <div><label>Mahsup (Tutukluluk gün)</label><input name="mahsupGun" type="number" min="0" value="0"></div>
        <div><label>Denetimli Serbestlik (yıl)</label><input name="denetimliYil" type="number" min="0" max="3" step="0.5" value="1"></div>
      </div>`,
      ceza: `<div class="ca-satir">
        <div><label>Temel Ceza — Yıl</label><input name="yil" type="number" min="0" value="2"></div>
        <div><label>Ay</label><input name="ay" type="number" min="0" value="0"></div>
        <div><label>Gün</label><input name="gun" type="number" min="0" value="0"></div>
        <div><label>Artırım (TCK 43 vb.)</label><select name="artir"><option value="">Yok</option><option value="1/4">+1/4</option><option value="1/3">+1/3</option><option value="1/2">+1/2</option><option value="3/4">+3/4</option></select></div>
        <div><label>İndirim (Tahrik/Teşebbüs)</label><select name="indir"><option value="">Yok</option><option value="1/4">-1/4</option><option value="1/3">-1/3</option><option value="1/2">-1/2</option><option value="3/4">-3/4</option></select></div>
      </div><label style="display:flex;gap:8px;align-items:center;color:inherit"><input type="checkbox" name="tck62" style="width:auto" checked> TCK m.62 takdiri indirim (-1/6) uygula</label>`
    };
    const ADLAR = { vekalet: '⚖️ Vekâlet', faiz: '📈 Faiz', harc: '🏛️ Harç', smm: '🧾 SMM', cmk: '🛡️ CMK', infaz: '⛓️ İnfaz', ceza: '⚖️ Ceza' };
    ic.innerHTML = `<div class="ca-satir" style="grid-template-columns:1fr"><div>${Object.entries(ADLAR).map(([k, a]) =>
        `<button class="ca-btn${k === hesapTur ? ' ana' : ''}" type="button" data-hesap="${k}">${a}</button>`).join('')}</div></div>
      <form id="ca-hesap-form" onsubmit="return false">${FORM[hesapTur]}</form><div id="ca-hesap-sonuc"></div>
      <p class="ca-soluk">Tarifeler: ${esc(Object.values(H.TARIFE.kaynak).join(' · '))}. Asgari tutarlardır; somut olayda mevzuatla doğrulayın.</p>`;
    ic.querySelectorAll('[data-hesap]').forEach(b => { b.onclick = () => { hesapTur = b.dataset.hesap; hesapSekmesi(ic); }; });
    const form = ic.querySelector('#ca-hesap-form'), kutu = ic.querySelector('#ca-hesap-sonuc');
    const sayi = v => parseFloat(String(v || '').replace(/\./g, '').replace(',', '.').replace(/[^\d.\-]/g, '')) || 0;
    const hesapla = () => {
      const f = Object.fromEntries(new FormData(form).entries());
      ['deger', 'anapara', 'tutar', 'oran'].forEach(k => { if (k in f && hesapTur !== 'infaz') f[k] = sayi(f[k]); });
      f.yarisi = !!form.querySelector('[name=yarisi]:checked'); f.giderim = !!form.querySelector('[name=giderim]:checked');
      f.vekaletname = !!form.querySelector('[name=vekaletname]:checked'); f.sorumlu = !!f.sorumlu; f.adet = +f.adet || 1;
      if (hesapTur === 'ceza') {
        f.adimlar = [];
        if (f.artir) { const [p, d] = f.artir.split('/'); f.adimlar.push({ tip: 'artir', pay: +p, payda: +d, ad: 'Kanuni artırım' }); }
        if (f.indir) { const [p, d] = f.indir.split('/'); f.adimlar.push({ tip: 'indir', pay: +p, payda: +d, ad: 'Kanuni indirim' }); }
        if (form.querySelector('[name=tck62]:checked')) f.adimlar.push({ tip: 'indir', pay: 1, payda: 6, ad: 'TCK m.62 takdiri indirim' });
      }
      const r = H[{ vekalet: 'vekalet', faiz: 'faiz', harc: 'harc', smm: 'smm', cmk: 'cmkMakbuz', infaz: 'infaz', ceza: 'ceza' }[hesapTur]](f);
      if (r.hata) { kutu.innerHTML = `<p class="ca-soluk">${esc(r.hata)}</p>`; return; }
      const tablo = r.tablo ? `<table><tr><th>Dönem</th><th>Gün</th><th>Oran</th><th>Faiz</th></tr>${r.tablo.map(t =>
        `<tr><td>${t.bas.toLocaleDateString('tr-TR')} – ${t.bit.toLocaleDateString('tr-TR')}</td><td>${t.gun}</td><td>%${t.oran.toLocaleString('tr-TR')}</td><td>${H.TL(t.faiz)}</td></tr>`).join('')}</table>` : '';
      const satirHtml = (r.metinSatirlar && r.metinSatirlar.length)
        ? r.metinSatirlar.map(x => `<tr${x.vurgu ? ' style="font-weight:700"' : ''}><td>${esc(x.ad)}${x.ref ? `<div class="ca-soluk">${esc(x.ref)}</div>` : ''}</td><td style="text-align:right;white-space:nowrap">${x.vurgu ? '<span class="ca-hedef" style="font-size:16px">' : ''}${esc(x.deger)}${x.vurgu ? '</span>' : ''}</td></tr>`).join('')
        : r.satirlar.map(x => `<tr${x.vurgu ? ' style="font-weight:700"' : ''}><td>${esc(x.ad)}${x.ref ? `<div class="ca-soluk">${esc(x.ref)}</div>` : ''}</td><td style="text-align:right;white-space:nowrap">${x.vurgu ? '<span class="ca-hedef" style="font-size:18px">' : ''}${H.TL(x.tutar)}${x.vurgu ? '</span>' : ''}</td></tr>`).join('');
      kutu.innerHTML = `<div class="ca-kart">${tablo}<table>${satirHtml}</table>
        ${r.not ? `<p class="ca-soluk">${esc(r.not)}</p>` : ''}<button class="ca-btn" type="button" id="ca-hesap-ekle">📝 Belgeye ekle</button></div>`;
      kutu.querySelector('#ca-hesap-ekle').onclick = () => {
        const metin = (r.metinSatirlar && r.metinSatirlar.length)
          ? r.metinSatirlar.map(x => `${x.ad}: ${x.deger}${x.ref ? ' (' + x.ref + ')' : ''}`).join('\n')
          : r.satirlar.map(x => `${x.ad}: ${H.TL(x.tutar)}${x.ref ? ' (' + x.ref + ')' : ''}`).join('\n');
        try { document.execCommand('insertText', false, metin); } catch (e) { navigator.clipboard && navigator.clipboard.writeText(metin); }
        kapat();
      };
    };
    form.addEventListener('input', hesapla); form.addEventListener('change', hesapla);
    hesapla();
  }

  window.CanAsistan = { yenilikDenetle, ac, kapat, sureHesapla, uygulanacakGun, tatilUyarilari, a4Yerlesim, a4PdfOlustur, api };
  window.openHukukAsistani = ac;
})();
