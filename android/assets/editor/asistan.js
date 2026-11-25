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
    if (secenek.ham) {
      if (!r.ok) { const v = await r.json().catch(() => ({})); throw Object.assign(new Error(v.hata || ('HTTP ' + r.status)), { durum: r.status }); }
      return r;
    }
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
  #ca-panel pre{background:var(--ce-bg,#f6f7f9);color:var(--ce-text,#1f2937);padding:8px;border-radius:8px;max-height:220px;overflow:auto;font-size:12px;white-space:pre-wrap}
  /* v4.9.3 günlük kutuları: "#ca-panel pre" (ID seçicisi) ".gv-log pre"yi eziyor, açık gri zemine açık gri yazı
     düşüyordu — yazı ancak seçince görünüyordu. Günlükler artık tek sınıfla, yüksek karşıtlıkla çizilir. */
  #ca-panel pre.ca-gunluk,#ca-panel .gv-log pre,#ca-panel pre.hf-d-log{background:#0f172a!important;color:#e5e7eb!important;font:12px/1.5 ui-monospace,Consolas,monospace;user-select:text;-webkit-user-select:text;overscroll-behavior:contain}
  #ca-panel .ca-muv{position:relative;border:1px solid var(--ce-border,#e2e6ec);border-radius:10px;padding:6px 8px;margin:8px 0;background:var(--ce-surface,#fff)}
  #ca-panel .ca-muv-ust{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
  #ca-panel .ca-muv-et{font-size:12.5px;font-weight:600;color:var(--ce-muted,#64748b)}
  #ca-panel .ca-muv-q{flex:1 1 200px;min-width:160px;border:0!important;outline:0;background:transparent!important;padding:4px!important;margin:0!important}
  #ca-panel .ca-muv-cip{display:inline-flex;align-items:center;gap:4px;background:#e0e7ff;color:#1e3a8a;border-radius:999px;padding:2px 4px 2px 10px;font-size:12.5px;border:0}
  #ca-panel .ca-muv-cip button{border:0;background:transparent;cursor:pointer;font-size:15px;line-height:1;color:inherit;padding:0 4px}
  #ca-panel .ca-muv-cip.oneri{background:#fef3c7;color:#78350f;padding:3px 10px;cursor:pointer;margin:2px}
  #ca-panel .ca-muv-temizle{border:0;background:transparent;color:#b91c1c;cursor:pointer;font-size:12px}
  #ca-panel .ca-muv-liste{position:absolute;left:0;right:0;top:100%;z-index:30;max-height:300px;overflow:auto;background:var(--ce-surface,#fff);border:1px solid var(--ce-border,#d0d5dd);border-radius:10px;box-shadow:0 10px 24px rgba(0,0,0,.15);padding:4px}
  #ca-panel .ca-muv-satir{display:flex;justify-content:space-between;gap:8px;padding:6px 8px;border-radius:6px;cursor:pointer;font-size:13px}
  #ca-panel .ca-muv-satir:hover{background:var(--ce-bg,#f1f5f9)}
  #ca-panel .ca-muv-benzer{margin-top:6px;font-size:12.5px;background:#fffbeb;border:1px solid #fcd34d;border-radius:8px;padding:6px 8px;color:#78350f}
  body.ce-dark-mode #ca-panel .ca-muv-benzer{background:#3a2a07;color:#f5d48a}
  #ca-panel .ca-filtre-cipler{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0}
  #ca-panel .ca-filtre-cipler button{border:1px solid var(--ce-border,#d0d5dd);background:var(--ce-surface,#fff);color:inherit;border-radius:999px;padding:4px 10px;font-size:12.5px;cursor:pointer}
  #ca-panel .ca-filtre-cipler button.secili{background:#0f2341;color:#fff;border-color:#0f2341}
  /* v4.9.3: koyu toplu işlem çubuğunda düğmeler beyaz zemine beyaz yazı olup boş kutu gibi görünüyordu */
  #ca-panel .hf-toplu-bar .ca-btn:not(.ana):not(.altin){color:#0f172a;background:#fff}
  body.ce-dark-mode #ca-panel .hf-toplu-bar .ca-btn:not(.ana):not(.altin){color:#e5e7eb;background:#1e293b}
  #ca-panel .ca-gunluk-not{font-size:11.5px;color:#b45309;margin:2px 0 0;cursor:pointer}
  @media (max-width:720px){
    #ca-panel .ca-kutu{width:100vw!important;max-height:100dvh!important;height:100dvh!important;border-radius:0!important;display:flex!important;flex-direction:column!important;overflow:hidden!important}
    #ca-panel header{flex-shrink:0!important;min-height:48px!important;height:48px!important}
    #ca-panel nav{flex-shrink:0!important;min-height:46px!important;height:46px!important;overflow-x:auto!important;overflow-y:hidden!important;white-space:nowrap!important;position:sticky!important;top:0!important;z-index:25!important}
    #ca-panel nav button{flex-shrink:0!important;height:34px!important;line-height:34px!important;padding:0 12px!important;font-size:12.5px!important;white-space:nowrap!important}
    #ca-panel .ca-icerik{flex:1 1 0%!important;min-height:0!important;overflow-y:auto!important;-webkit-overflow-scrolling:touch!important;padding:12px!important}
  }
  `;

  let kok = null, aktifSekme = 'ana', stilVar = false;
  function stilEkle() {
    if (stilVar || !document.head) return;
    const st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st); stilVar = true;
  }
  // v4.9.3 Günlük kutusu güncelleyici (tek yer): metin YERİNDE güncellenir, sayfa yeniden çizilmez.
  //  • En alttaysanız yeni satırları izler.
  //  • Yukarı kaydırdıysanız ya da metin seçtiyseniz kutu DONAR (satırlar kaymaz, seçim bozulmaz);
  //    altında "⏸ duraklatıldı — en alta inmek için tıklayın" yazar. En alta inince yeniden canlanır.
  function gunlukYaz(pre, satirlar, bos) {
    if (!pre) return;
    const metin = (Array.isArray(satirlar) ? satirlar.join('\n') : String(satirlar || '')) || (bos || '');
    pre.classList.add('ca-gunluk');
    let not = pre.nextElementSibling && pre.nextElementSibling.classList.contains('ca-gunluk-not') ? pre.nextElementSibling : null;
    const sec = window.getSelection && window.getSelection();
    const secimVar = sec && !sec.isCollapsed && sec.anchorNode && pre.contains(sec.anchorNode);
    const altta = pre.scrollHeight - pre.scrollTop - pre.clientHeight < 30 || pre.clientHeight === 0;
    if (pre.textContent === metin) { if (not && altta && !secimVar) not.remove(); return; }
    if (!pre.textContent || (altta && !secimVar)) {
      pre.textContent = metin; pre.scrollTop = pre.scrollHeight;
      if (not) not.remove();
      return;
    }
    if (!not) {
      not = document.createElement('div'); not.className = 'ca-gunluk-not';
      not.textContent = '⏸ Günlük okumanız için duraklatıldı — yeni satırlar için en alta inin ya da buraya tıklayın.';
      not.onclick = () => { if (window.getSelection) window.getSelection().removeAllRanges(); pre.scrollTop = pre.scrollHeight; gunlukYaz(pre, satirlar, bos); };
      pre.after(not);
    }
  }
  window.CanGunluk = gunlukYaz;

  // ===================================================================================================
  // v4.9.3 MÜVEKKİL SEÇİCİ — her sekmede aynı, ortak seçim (bir sekmede seçince hepsinde geçerli).
  // Aynı müvekkil UYAP'ta farklı yazılmış olabilir ("ABC İNŞ. LTD. ŞTİ." / "ABC INSAAT LIMITED SIRKETI",
  // "AHMET SUNGUR (Sanık)"): sunucu benzer adları gruplar, seçici "benzer yazılmış N ad daha — birlikte seç" önerir.
  // ===================================================================================================
  const MUV_DEPO = 'ca-muvekkil-secim';
  let muvSecim = (() => { try { const v = JSON.parse(localStorage.getItem(MUV_DEPO) || '[]'); return Array.isArray(v) ? v : []; } catch (e) { return []; } })();
  let muvVeri = null, muvSoz = null;
  const katla = s => String(s || '').replace(/İ/g, 'i').replace(/I/g, 'ı').toLocaleLowerCase('tr')
    .replace(/ı/g, 'i').replace(/ş/g, 's').replace(/ğ/g, 'g').replace(/ü/g, 'u').replace(/ö/g, 'o').replace(/ç/g, 'c').replace(/[âàá]/g, 'a').replace(/[îí]/g, 'i').replace(/[ûú]/g, 'u')
    .replace(/[^a-z0-9/]+/g, ' ').trim();
  function muvYukle(tazele) {
    if (muvVeri && !tazele) return Promise.resolve(muvVeri);
    if (!muvSoz || tazele) muvSoz = api('/api/muvekkiller').then(v => { muvVeri = v; return v; }).catch(e => { muvSoz = null; throw e; });
    return muvSoz;
  }
  function muvSecimYaz(l) {
    muvSecim = [...new Set(l)];
    try { localStorage.setItem(MUV_DEPO, JSON.stringify(muvSecim)); } catch (e) { /* özel pencere */ }
    document.dispatchEvent(new CustomEvent('ca-muvekkil', { detail: muvSecim }));
  }
  const muvParam = () => muvSecim.length ? '&muvekkil=' + encodeURIComponent(muvSecim.join('|')) : '';
  // İstemci tarafı süzgeç: seçili müvekkillerin dosyaları (dkey ya da "mahkeme|esas")
  function muvSuzgec() {
    if (!muvSecim.length || !muvVeri) return null;
    const dk = new Set(), bn = new Set();
    for (const m of muvVeri.muvekkiller || []) {
      if (!muvSecim.includes(m.ad)) continue;
      (m.dkeyler || []).forEach(x => dk.add(x));
      (m.dosyalar || []).forEach(x => { const [b, n] = x.split('|'); bn.add(katla(b) + '|' + katla(n)); });
    }
    return r => {
      if (r.dkey && dk.has(r.dkey)) return true;
      const b = katla(r.birim || r.mahkeme || ''), n = katla(r.dosya_no || r.esas || '');
      if (bn.has(b + '|' + n)) return true;
      // mahkeme adı kısaltılmış olabilir: esas no aynı ve mahkeme adı birbirini içeriyorsa eşleşir
      if (n) for (const k of bn) { const [kb, kn] = k.split('|'); if (kn === n && (kb.includes(b) || b.includes(kb))) return true; }
      return false;
    };
  }
  function muvekkilSecici(kap, degisti) {
    if (!kap) return;
    kap.classList.add('ca-muv');
    kap.innerHTML = `<div class="ca-muv-ust"><span class="ca-muv-et">👤 Müvekkil</span><span class="ca-muv-cipler"></span>
        <input class="ca-muv-q" placeholder="Müvekkil seçin (tümü için boş bırakın)…" autocomplete="off"></div>
      <div class="ca-muv-liste" hidden></div><div class="ca-muv-benzer" hidden></div>`;
    const cipler = kap.querySelector('.ca-muv-cipler'), q = kap.querySelector('.ca-muv-q'),
      liste = kap.querySelector('.ca-muv-liste'), benzer = kap.querySelector('.ca-muv-benzer');
    const bilgi = ad => (muvVeri && (muvVeri.muvekkiller || []).find(m => m.ad === ad)) || null;
    const benzerGoster = ad => {
      const m = bilgi(ad); const eksik = m ? (m.grup || []).filter(x => !muvSecim.includes(x)) : [];
      if (!eksik.length) { benzer.hidden = true; return; }
      benzer.hidden = false;
      benzer.innerHTML = `💡 <b>${esc(ad)}</b> ile benzer yazılmış ${eksik.length} ad var, aynı müvekkil olabilir:
        ${eksik.map(x => `<button type="button" class="ca-muv-cip oneri" data-ekle="${esc(x)}">+ ${esc(x)} <small>${(bilgi(x) || {}).dkeyler ? bilgi(x).dkeyler.length + ' dosya' : ''}</small></button>`).join('')}
        <button type="button" class="ca-btn kucuk ana" data-hepsi="${esc(ad)}">Hepsini birlikte seç</button>
        <button type="button" class="ca-btn kucuk" data-kapat>Hayır</button>`;
    };
    const cipCiz = () => {
      cipler.innerHTML = muvSecim.map(a => `<span class="ca-muv-cip">${esc(a)} <button type="button" data-cikar="${esc(a)}" title="Kaldır">×</button></span>`).join('')
        + (muvSecim.length > 1 ? '<button type="button" class="ca-muv-temizle" data-temizle>Temizle</button>' : '');
      q.placeholder = muvSecim.length ? 'Başka müvekkil ekle…' : 'Müvekkil seçin (tümü için boş bırakın)…';
    };
    const listeCiz = () => {
      const t = katla(q.value);
      if (!muvVeri) { liste.hidden = false; liste.innerHTML = '<div class="ca-soluk">Müvekkiller yükleniyor…</div>'; return; }
      const l = (muvVeri.muvekkiller || []).filter(m => !muvSecim.includes(m.ad) && (!t || katla(m.ad).includes(t))).slice(0, 40);
      liste.hidden = false;
      liste.innerHTML = l.length ? l.map(m => `<div class="ca-muv-satir" data-sec="${esc(m.ad)}"><span>${esc(m.ad)}</span>
          <span class="ca-soluk">${m.dkeyler.length} dosya${m.grup && m.grup.length ? ` · ≈ ${m.grup.length} benzer yazım` : ''}</span></div>`).join('')
        : `<div class="ca-soluk">${(muvVeri.muvekkiller || []).length ? 'Eşleşen müvekkil yok.' : 'Katalogda müvekkil bilgisi henüz yok (dosya tarafları Senkron ile alınır).'}</div>`;
    };
    const sec = ad => { muvSecimYaz([...muvSecim, ad]); q.value = ''; liste.hidden = true; benzerGoster(ad); };
    q.addEventListener('focus', () => { muvYukle().then(listeCiz).catch(() => {}); listeCiz(); });
    q.addEventListener('input', listeCiz);
    q.addEventListener('keydown', e => { if (e.key === 'Escape') { liste.hidden = true; q.blur(); }
      if (e.key === 'Enter') { const ilk = liste.querySelector('[data-sec]'); if (ilk) { e.preventDefault(); sec(ilk.dataset.sec); } } });
    q.addEventListener('blur', () => setTimeout(() => { liste.hidden = true; }, 200));
    kap.addEventListener('mousedown', e => { if (e.target.closest('[data-sec]')) e.preventDefault(); });
    kap.addEventListener('click', e => {
      const t = e.target.closest('[data-sec],[data-cikar],[data-ekle],[data-hepsi],[data-kapat],[data-temizle]'); if (!t) return;
      if (t.dataset.sec) sec(t.dataset.sec);
      else if (t.dataset.cikar) { muvSecimYaz(muvSecim.filter(x => x !== t.dataset.cikar)); benzer.hidden = true; }
      else if (t.dataset.ekle) { muvSecimYaz([...muvSecim, t.dataset.ekle]); benzerGoster(muvSecim[0]); }
      else if (t.dataset.hepsi) { const m = bilgi(t.dataset.hepsi); muvSecimYaz([...muvSecim, ...((m && m.grup) || [])]); benzer.hidden = true; }
      else if (t.dataset.kapat !== undefined) benzer.hidden = true;
      else if (t.dataset.temizle !== undefined) { muvSecimYaz([]); benzer.hidden = true; }
    });
    const dinle = () => { if (!document.body.contains(kap)) { document.removeEventListener('ca-muvekkil', dinle); return; } cipCiz(); if (degisti) degisti(muvSecim); };
    document.addEventListener('ca-muvekkil', dinle);
    cipCiz();
    muvYukle().catch(() => {});
  }
  window.CanMuvekkil = { secici: muvekkilSecici, param: muvParam, suzgec: muvSuzgec, yukle: muvYukle, secim: () => muvSecim.slice() };
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // Sekmeler işlevine göre gruplanır (v4.3): masaüstünde solda gruplu kenar çubuğu, telefonda kaydırılabilir çipler.
  // v4.5 sadeleştirme: görünür olan yalnız 3 bölüm; diğer her şey "Diğer araçlar" altında katlı.
  const SEKME_GRUPLARI = [
    ['', [['ana', '🏠 Ana Ekran'], ['dosyalar', '📁 Dosyalar'], ['tebligat', '📨 Tebligatlar']]],
    ['Diğer araçlar', [['uyap', '🔐 UYAP Giriş'], ['yeni', '🔔 Yeni Evrak'], ['ajanda', '📅 Ajanda'], ['evrak', '🗂️ Evrak Ara'],
      ['sure', '⏱️ Süre'], ['hesap', '🧮 Hesapla'], ['hesaplar', '💰 Dosya Hesapları'], ['a4', '📄 A4 PDF'], ['jar', '🔄 JAR Dönüştür'],
      ['hayfa', '📰 HAYFA / İçtihat'], ['drive', '☁️ Drive Ayarları'], ['entegrasyon', '📋 Notion / TickTick / Telegram'],
      ['gorev', '⚙️ Görevler'], ['baglanti', '🔌 Bağlantı'], ['saglik', '🩺 Sağlık / Günlük']]]
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
    // Önceki çalışma yeri kapanmasın: dosya her zaman ayrı pencerede açılır
    if (typeof dosyaPenceresi === 'function') return dosyaPenceresi(dkey);
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
  #ca-panel .ca-govde>nav .ca-diger{display:none;flex-direction:inherit;gap:inherit}
  #ca-panel .ca-govde>nav.diger-acik .ca-diger{display:flex}
  #ca-panel .ca-govde>nav .ca-diger-ac{color:var(--ce-muted,#64748b)!important;font-size:12.5px!important}
  /* Ana ekran kartları */
  .pn-izgara{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
  .pn-kart{border-radius:16px;padding:18px;background:var(--ce-surface,#fff);border:1px solid var(--ce-border,#e2e6ec);box-shadow:0 1px 2px rgba(15,23,42,.04)}
  .pn-kart h3{margin:0 0 4px;font-size:17px;display:flex;align-items:center;gap:8px}
  .pn-alt{color:var(--ce-muted,#64748b);font-size:13px;margin:0 0 12px}
  .pn-dugme{width:100%;padding:16px;border-radius:12px;border:0;font-size:16px;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:10px;transition:filter .15s}
  .pn-dugme:hover{filter:brightness(1.06)}
  .pn-dugme.kapali{background:#0f2744;color:#fff}
  .pn-dugme.acik{background:#16a34a;color:#fff}
  .pn-dugme:disabled{opacity:.55;cursor:not-allowed}
  .pn-nokta{width:10px;height:10px;border-radius:50%;background:#94a3b8;display:inline-block}
  .pn-nokta.yesil{background:#22c55e;box-shadow:0 0 0 0 rgba(34,197,94,.6);animation:pn-nabiz 1.8s infinite}
  .pn-nokta.sari{background:#f59e0b}.pn-nokta.kirmizi{background:#ef4444}
  @keyframes pn-nabiz{70%{box-shadow:0 0 0 8px rgba(34,197,94,0)}100%{box-shadow:0 0 0 0 rgba(34,197,94,0)}}
  .pn-cubuk{height:12px;border-radius:8px;background:rgba(100,116,139,.15);overflow:hidden;margin:12px 0 6px}
  .pn-cubuk>div{height:100%;background:linear-gradient(90deg,#c8a45a,#e0c27d);transition:width .6s}
  .pn-sayilar{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}
  .pn-sayi{background:rgba(100,116,139,.07);border-radius:10px;padding:8px 10px}
  .pn-sayi b{display:block;font-size:17px;font-variant-numeric:tabular-nums}
  .pn-sayi span{font-size:11.5px;color:var(--ce-muted,#64748b)}
  .pn-simdi{font-size:12.5px;color:var(--ce-muted,#64748b);margin-top:10px;min-height:2.6em;line-height:1.3;word-break:break-word}
  .pn-uyari{background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;border-radius:10px;padding:8px 10px;font-size:13px;margin-top:10px}
  body.ce-dark-mode .pn-uyari{background:#3b2410;border-color:#7c2d12;color:#fed7aa}
  /* Asistan modu: editör hiç görünmez, panel tam ekran ana ekrandır */
  body.ce-asistan-modu > *:not(#ca-panel):not(script):not(style){display:none!important}
  body.ce-asistan-modu #ca-panel{background:var(--ce-bg,#f4f6f9)!important;backdrop-filter:none}
  body.ce-asistan-modu #ca-panel .ca-kutu{width:100vw!important;height:100dvh!important;max-width:none!important;border-radius:0!important;border:0!important}
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
        <nav aria-label="Asistan bölümleri">${SEKME_GRUPLARI.map(([g, l], gi) => (gi === 0 ? '' : `<button type="button" class="ca-diger-ac">⋯ ${esc(g)}</button><div class="ca-diger">`)
          + l.map(([k, ad]) => `<button type="button" data-sekme="${k}">${ad}</button>`).join('') + (gi === 0 ? '' : '</div>')).join('')}</nav>
        <div class="ca-icerik" tabindex="-1"></div>
      </div></div>`;
    document.body.appendChild(kok);
    kok.querySelector('.ca-kapat').onclick = kapat;
    kok.querySelector('#ca-hdr-drive-durum').onclick = () => sekmeAc('drive');
    kok.addEventListener('mousedown', e => { if (e.target === kok) kapat(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && kok.classList.contains('acik')) kapat(); });
    kok.querySelectorAll('nav button[data-sekme]').forEach(b => { b.onclick = () => sekmeAc(b.dataset.sekme); });
    kok.querySelector('.ca-diger-ac').onclick = () => kok.querySelector('nav').classList.toggle('diger-acik');
    driveDurumunuGuncelle();
  }

  function ac(sekme) { panelKur(); kok.classList.add('acik'); sekmeAc(sekme || aktifSekme); driveDurumunuGuncelle(); }
  function kapat() {
    // Asistan modunda (uygulama ana ekranından açıldıysa) kapatınca editöre değil, ana ekrana dönülür
    if (document.body.classList.contains('ce-asistan-modu') && window.AndroidBridge && window.AndroidBridge.asistanKapat) {
      window.AndroidBridge.asistanKapat(); return;
    }
    document.body.classList.remove('ce-asistan-modu');
    if (kok) kok.classList.remove('acik'); gorevIzleDurdur();
    if (anaZamanlayici) { clearInterval(anaZamanlayici); anaZamanlayici = null; }
  }

  // ===================================================================== 🏠 ANA EKRAN
  // İki büyük düğme (UYAP → Drive senkronu, Tebligat izleyici), canlı göstergeler ve içtihat sayacı.
  let anaZamanlayici = null;
  const sayi = n => (n == null ? '—' : Number(n).toLocaleString('tr-TR'));
  const sure = sn => { if (!sn) return ''; const d = Math.floor(sn / 60); return d < 60 ? `${d} dk` : `${Math.floor(d / 60)} sa ${d % 60} dk`; };
  const saatOnce = t => { if (!t) return ''; const ms = Date.now() - new Date(String(t).replace(' ', 'T')).getTime(); if (!(ms >= 0)) return ''; const d = Math.round(ms / 60000); return d < 1 ? 'az önce' : d < 60 ? `${d} dk önce` : d < 1440 ? `${Math.round(d / 60)} sa önce` : `${Math.round(d / 1440)} gün önce`; };

  async function anaEkran(ic) {
    ic.innerHTML = `<div class="pn-izgara">
      <div class="pn-kart" id="pn-senkron"><h3>☁️ UYAP → Google Drive</h3><p class="pn-alt">Tüm UYAP evrakları PDF'e dönüştürülüp, mükerrerler ayıklanarak, düzenli adlarla Drive'a sürekli aktarılır.</p><div class="ca-yukleniyor">Yükleniyor…</div></div>
      <div class="pn-kart" id="pn-tebligat"><h3>📨 Tebligat İzleyici</h3><p class="pn-alt">UETS'e arka planda girer; tebligatları EYP ekleri, üst yazısı ve etiketleriyle TickTick'e, ilgili dosyaya Notion'a işler.</p><div class="ca-yukleniyor">Yükleniyor…</div></div>
      <div class="pn-kart" id="pn-duzen"><h3>🗂️ Notion &amp; TickTick Düzeni</h3><p class="pn-alt">UYAP dosyaları, tarafları ve konularıyla Notion'a; her dosyaya TickTick kartı; mükerrer ve eksik görev denetimi.</p><div class="ca-yukleniyor">Yükleniyor…</div></div>
      <div class="pn-kart" id="pn-ictihat"><h3>⚖️ İçtihat Veritabanı</h3><p class="pn-alt">hayfahukuk.com karar veritabanının canlı durumu.</p><div class="ca-yukleniyor">Ölçülüyor…</div></div>
    </div>`;
    // Yeni kurulum (anahtar yok): ayar yedeğinden tek adımda geri yükleme kartı en üstte
    api('/api/ayar/yedek').then(y => {
      if (!y.bos_kurulum || !document.body.contains(ic) || !window.CanAyarYedek) return;
      const d = document.createElement('div'); d.style.marginBottom = '12px'; ic.prepend(d);
      window.CanAyarYedek(d, { api, esc, yenile: () => anaEkran(ic) });
    }).catch(() => {});
    const ciz = async () => {
      let p;
      try { p = await api('/api/pano'); } catch (e) { ic.querySelector('#pn-senkron').innerHTML = `<h3>☁️ UYAP → Google Drive</h3><span class="ca-hata">${esc(e.message)}</span>`; return; }
      if (!document.body.contains(ic)) return;
      senkronCiz(ic.querySelector('#pn-senkron'), p);
      tebligatCiz(ic.querySelector('#pn-tebligat'), p);
      duzenCiz(ic.querySelector('#pn-duzen'), p);
    };
    const duzenCiz = (el, p) => {
      const z = p.duzen || {}, n = z.notion || {}, t = z.ticktick || {};
      const calisiyor = n.calisiyor || t.calisiyor;
      const ns = n.sonuc || {}, ts = t.sonuc || {};
      const nokta = !z.hazir ? '' : calisiyor ? 'yesil' : 'sari';
      el.innerHTML = `<h3>🗂️ Notion &amp; TickTick Düzeni <span class="pn-nokta ${nokta}"></span><span style="font-size:13px;font-weight:500;color:var(--ce-muted,#64748b)">${!z.hazir ? 'Bağlı değil' : calisiyor ? 'Çalışıyor' : 'Otomatik (6 saatte bir)'}</span></h3>
        <p class="pn-alt">UYAP dosyaları, tarafları ve konularıyla Notion'a; her dosyaya TickTick kartı; mükerrer ve eksik görev denetimi.</p>
        <button class="pn-dugme kapali" type="button" id="pn-d-dugme" ${z.hazir && !calisiyor ? '' : 'disabled'}>${calisiyor ? '🔄 Düzenleniyor…' : '▶ Şimdi düzenle'}</button>
        ${!z.hazir ? '<div class="pn-uyari">⚠️ Notion ve TickTick anahtarları girilmemiş. <a href="#" data-git="entegrasyon">Bilgileri girin</a></div>' : ''}
        <div class="pn-sayilar">
          <div class="pn-sayi"><b>${ns.yeni_dosya ?? '—'}</b><span>Notion'a yeni dosya</span></div>
          <div class="pn-sayi"><b>${ns.konu ?? '—'}</b><span>konu özeti yazıldı</span></div>
          <div class="pn-sayi"><b>${ns.muvekkil_bag != null ? (ns.muvekkil_bag + ns.karsi_bag) : '—'}</b><span>taraf bağlandı</span></div>
          <div class="pn-sayi"><b>${ts.kapatilan ?? '—'}</b><span>mükerrer kapatıldı</span></div>
          <div class="pn-sayi"><b>${ts.yeni_kart ?? '—'}</b><span>dosya kartı açıldı</span></div>
          <div class="pn-sayi"><b style="${ts.eksik ? 'color:#dc2626' : ''}">${ts.eksik ?? '—'}</b><span>eksik görev</span></div>
        </div>
        ${ns.engel ? `<div class="pn-uyari">⚠️ ${esc(ns.engel)}</div>` : ''}
        <div class="pn-simdi">${calisiyor ? '🔄 ' + esc((n.calisiyor ? n.simdi : t.simdi) || '') : (t.son_bitis ? 'Son düzen: ' + saatOnce(new Date(t.son_bitis * 1000).toISOString()) : '')}${!calisiyor && z.sonraki ? ' · Sonraki: ' + new Date(z.sonraki * 1000).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }) : ''}</div>`;
      const b = el.querySelector('#pn-d-dugme');
      if (b) b.onclick = async e => {
        e.currentTarget.disabled = true;
        try { const r = await api('/api/pano/duzen', { method: 'POST', govde: {} }); duzenCiz(el, r); }
        catch (er) { el.querySelector('.pn-simdi').innerHTML = `<span class="ca-hata">${esc(er.message)}</span>`; }
      };
      el.querySelectorAll('[data-git]').forEach(a => { a.onclick = ev => { ev.preventDefault(); sekmeAc(a.dataset.git); }; });
    };
    const senkronCiz = (el, p) => {
      const s = p.senkron, k = p.katalog || {}, d = p.drive || {};
      const islenen = (k.indirildi || 0) + (k.mukerrer || 0) + (k.yok || 0);
      const yuzde = k.evrak ? Math.min(100, Math.round(100 * islenen / k.evrak)) : 0;
      const drvYuzde = d.indirilen ? Math.min(100, Math.round(100 * (d.drivede || 0) / d.indirilen)) : 0;
      const nokta = !s.acik ? '' : (s.calisiyor ? (s.oturum === false ? 'sari' : 'yesil') : 'sari');
      const durumYazi = !s.acik ? 'Kapalı' : !s.calisiyor ? 'Başlatılıyor…' : s.oturum === false ? 'UYAP oturumu açılıyor…' : 'Çalışıyor';
      el.innerHTML = `<h3>☁️ UYAP → Google Drive <span class="pn-nokta ${nokta}"></span><span style="font-size:13px;font-weight:500;color:var(--ce-muted,#64748b)">${durumYazi}</span></h3>
        <p class="pn-alt">Tüm UYAP evrakları PDF'e dönüştürülüp, mükerrerler ayıklanarak, düzenli adlarla Drive'a sürekli aktarılır.</p>
        <button class="pn-dugme ${s.acik ? 'acik' : 'kapali'}" type="button" id="pn-s-dugme" ${s.ayarli ? '' : 'disabled'}>${s.acik ? '⏸ Senkronizasyonu Durdur' : '▶ Senkronizasyonu Başlat'}</button>
        ${!s.ayarli ? `<div class="pn-uyari">⚠️ ${esc(s.neden || 'UYAP giriş bilgisi yok')}. <a href="#" data-git="uyap">Giriş bilgilerini girin</a></div>` : ''}
        ${!d.ayar ? `<div class="pn-uyari">⚠️ Google Drive bağlı değil. <a href="#" data-git="drive">Drive'ı bağlayın</a></div>` : ''}
        ${k.evrak ? `<div class="pn-cubuk" title="UYAP arşivi işlendi"><div style="width:${yuzde}%"></div></div>
          <div style="display:flex;justify-content:space-between;font-size:13px"><span><b>%${yuzde}</b> arşiv işlendi</span><span>${sayi(islenen)} / ${sayi(k.evrak)} evrak</span></div>
          <div class="pn-sayilar">
            <div class="pn-sayi"><b>${sayi(k.indirildi)}</b><span>indirildi</span></div>
            <div class="pn-sayi"><b>${sayi(k.bekleyen)}</b><span>sırada</span></div>
            <div class="pn-sayi"><b>${sayi(d.drivede)}</b><span>Drive'da (%${drvYuzde})</span></div>
            <div class="pn-sayi"><b>${sayi(k.mukerrer)}</b><span>mükerrer ayıklandı</span></div>
            <div class="pn-sayi"><b>${sayi(k.dosya)}</b><span>dosya</span></div>
            <div class="pn-sayi"><b>${sayi(k.yok + k.hata)}</b><span>UYAP'ta yok / hatalı</span></div>
          </div>` : '<p class="ca-soluk" style="margin-top:12px">Henüz katalog yok — senkronizasyonu başlatınca UYAP dosyalarınız taranır.</p>'}
        <div class="pn-simdi">${s.calisiyor && s.simdi ? '🔄 ' + esc(s.simdi) : ''}${k.son_indirme ? `<br>Son indirme: ${saatOnce(k.son_indirme)}` : ''}${s.nabiz && s.nabiz.son ? ` · Oturum ${s.nabiz.oturum_acik === false ? '<b style="color:#dc2626">düştü</b>' : 'açık'}` : ''}</div>
        ${s.son_hata ? `<div class="pn-uyari">⚠️ ${esc(s.son_hata)}</div>` : ''}`;
      el.querySelector('#pn-s-dugme').onclick = async e => {
        e.currentTarget.disabled = true;
        try { const r = await api('/api/pano/senkron', { method: 'POST', govde: { ac: !s.acik } }); senkronCiz(el, r); tebligatCiz(ic.querySelector('#pn-tebligat'), r); }
        catch (er) { el.querySelector('.pn-simdi').innerHTML = `<span class="ca-hata">${esc(er.message)}</span>`; e.currentTarget.disabled = false; }
      };
      el.querySelectorAll('[data-git]').forEach(a => { a.onclick = ev => { ev.preventDefault(); sekmeAc(a.dataset.git); }; });
    };
    const tebligatCiz = (el, p) => {
      const t = p.tebligat, acik = (t.aralik_dk || 0) > 0;
      const nokta = acik ? (t.calisiyor ? 'yesil' : 'sari') : '';
      el.innerHTML = `<h3>📨 Tebligat İzleyici <span class="pn-nokta ${nokta}"></span><span style="font-size:13px;font-weight:500;color:var(--ce-muted,#64748b)">${acik ? (t.calisiyor ? 'UETS kontrol ediliyor' : 'Açık') : 'Kapalı'}</span></h3>
        <p class="pn-alt">UETS'e arka planda girer; tebligatları EYP ekleri, üst yazısı ve etiketleriyle TickTick'e, ilgili dosyaya Notion'a işler.</p>
        <button class="pn-dugme ${acik ? 'acik' : 'kapali'}" type="button" id="pn-t-dugme" ${t.hazir ? '' : 'disabled'}>${acik ? '⏸ İzleyiciyi Durdur' : '▶ İzleyiciyi Başlat'}</button>
        ${!t.hazir ? '<div class="pn-uyari">⚠️ UETS T.C. ve şifresi girilmemiş. <a href="#" data-git="entegrasyon">Bilgileri girin</a></div>' : ''}
        ${t.kullanilamaz ? `<div class="pn-uyari">⚠️ ${esc(t.kullanilamaz)}</div>` : ''}
        <div class="pn-sayilar" style="grid-template-columns:repeat(2,1fr)">
          <div class="pn-sayi"><b>${acik ? (t.aralik_dk >= 60 ? (t.aralik_dk / 60) + ' saatte' : t.aralik_dk + ' dk\'da') + ' bir' : '—'}</b><span>kontrol sıklığı</span></div>
          <div class="pn-sayi"><b>${t.son_bitis ? saatOnce(new Date(t.son_bitis * 1000).toISOString()) : '—'}</b><span>son kontrol ${t.son_kod === 0 ? '✓' : t.son_kod ? '⚠️' : ''}</span></div>
        </div>
        <div class="pn-simdi">${t.calisiyor && t.simdi ? '🔄 ' + esc(t.simdi) : acik && t.sonraki ? 'Sonraki kontrol: ' + new Date(t.sonraki * 1000).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }) : ''}</div>
        <div style="margin-top:8px"><a href="#" data-git="tebligat">Tebligat listesini ve ayrıntıları aç →</a></div>`;
      el.querySelector('#pn-t-dugme').onclick = async e => {
        e.currentTarget.disabled = true;
        try { const r = await api('/api/pano/tebligat', { method: 'POST', govde: { ac: !acik, aralik_dk: 60 } }); tebligatCiz(el, r); senkronCiz(ic.querySelector('#pn-senkron'), r); }
        catch (er) { el.querySelector('.pn-simdi').innerHTML = `<span class="ca-hata">${esc(er.message)}</span>`; e.currentTarget.disabled = false; }
      };
      el.querySelectorAll('[data-git]').forEach(a => { a.onclick = ev => { ev.preventDefault(); sekmeAc(a.dataset.git); }; });
    };
    const ictihat = async (yenile) => {
      const el = ic.querySelector('#pn-ictihat');
      try {
        const r = await api('/api/hayfa/karar-istatistik' + (yenile ? '?yenile=1' : ''));
        if (!document.body.contains(el)) return;
        el.innerHTML = `<h3>⚖️ İçtihat Veritabanı <span class="pn-nokta yesil"></span></h3><p class="pn-alt">hayfahukuk.com karar veritabanının canlı durumu.</p>
          <div class="pn-sayilar" style="grid-template-columns:repeat(3,1fr)">
            <div class="pn-sayi"><b>${sayi(r.en_son_karar_no)}</b><span>karar (toplam arşiv)</span></div>
            <div class="pn-sayi"><b>${r.son_24s_artis == null ? '—' : '+' + sayi(r.son_24s_artis)}</b><span>son 24 saat</span></div>
            <div class="pn-sayi"><b>${r.son_7g_artis == null ? '—' : '+' + sayi(r.son_7g_artis)}</b><span>son 7 gün</span></div>
          </div>
          <div class="pn-simdi">Ölçüm: ${esc(r.olcum_zamani)} · <a href="${esc(r.son_karar_url)}" target="_blank" rel="noopener">en son eklenen karar</a> · <a href="#" data-git="hayfa">Karar ara →</a></div>`;
        el.querySelectorAll('[data-git]').forEach(a => { a.onclick = ev => { ev.preventDefault(); sekmeAc(a.dataset.git); }; });
      } catch (e) { if (document.body.contains(el)) el.innerHTML = `<h3>⚖️ İçtihat Veritabanı <span class="pn-nokta kirmizi"></span></h3><p class="pn-alt">hayfahukuk.com karar veritabanının canlı durumu.</p><span class="ca-soluk">${esc(e.message)}</span>`; }
    };
    await ciz();
    ictihat(false);
    // Canlı: 5 sn'de bir pano, 10 dk'da bir içtihat sayacı
    let tur = 0;
    anaZamanlayici = setInterval(() => { if (!document.body.contains(ic) || aktifSekme !== 'ana') return; ciz(); if (++tur % 120 === 0) ictihat(true); }, 5000);
  }

  function hayfaCtx() {
    return { api, esc, sunucuHatasi, evrakAc, kapat, sekmeAc };
  }

  function sekmeAc(k) {
    aktifSekme = k;
    gorevIzleDurdur();
    if (kok && !['ana', 'dosyalar', 'tebligat'].includes(k)) kok.querySelector('nav').classList.add('diger-acik');
    if (anaZamanlayici) { clearInterval(anaZamanlayici); anaZamanlayici = null; }
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
      tebligat: tebligatSekmesi,
      ana: anaEkran,
      baglanti: baglantiSekmesi,
      saglik: saglikSekmesi
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
  // [ad, birim ('gun' | 'ay' | 'oto' | 'ozel'), miktar, dayanak]. Süreler tebliğden sonraki günden işler.
  const SURE_TURLERI = [
    ['Merciye göre otomatik (7 / 14 / 30 gün)', 'oto', 0, ''],
    ['HMK — İstinaf başvurusu', 'gun', 14, 'HMK m.345: 2 hafta'],
    ['HMK — Temyiz başvurusu', 'ay', 1, 'HMK m.361: 1 ay'],
    ['HMK — Cevap dilekçesi', 'gun', 14, 'HMK m.127: 2 hafta'],
    ['HMK — Bilirkişi raporuna itiraz', 'gun', 14, 'HMK m.281: 2 hafta'],
    ['İİK — Ödeme emrine itiraz (ilamsız)', 'gun', 7, 'İİK m.62'],
    ['İİK — Kambiyo ödeme emrine itiraz / şikâyet', 'gun', 5, 'İİK m.168/5'],
    ['İİK — İcra memuru işlemine şikâyet', 'gun', 7, 'İİK m.16'],
    ['İİK — İcra mahkemesi kararına istinaf', 'gun', 10, 'İİK m.363'],
    ['İİK — İcra emrine itiraz / ödeme (ilamlı)', 'gun', 7, 'İİK m.33'],
    ['CMK — İstinaf', 'gun', 14, 'CMK m.273: 2 hafta (7499 s.K. ile)'],
    ['CMK — Temyiz', 'gun', 14, 'CMK m.291: 2 hafta (7499 s.K. ile)'],
    ['CMK — Kararlara itiraz', 'gun', 7, 'CMK m.268 — güncel metni kontrol edin'],
    ['İYUK — İptal / tam yargı davası açma', 'gun', 60, 'İYUK m.7 (vergi davalarında 30 gün)'],
    ['İYUK — Vergi davası açma', 'gun', 30, 'İYUK m.7'],
    ['İYUK — İstinaf', 'gun', 30, 'İYUK m.45'],
    ['İYUK — Temyiz', 'gun', 30, 'İYUK m.46'],
    ['İş — Arabuluculuk sonrası işe iade davası', 'gun', 14, 'İş K. m.20: son tutanaktan itibaren 2 hafta'],
    ['Kesin süre (mahkemenin verdiği gün)', 'ozel', 0, 'HMK m.94'],
  ];

  // Somut dosyalar: UETS tebligat son günleri (Ajanda) + icra kesinleşme / itiraz son günleri ve 1 yıllık
  // işlemsizlik eşiği (icra_analiz) tek listede, kalan güne göre sıralı. "📂" dosyayı ayrı pencerede açar.
  async function dosyaSureleriCiz(kap) {
    if (!kap) return;
    try {
      const [aj, ia] = await Promise.all([api('/api/ajanda?gun=60').catch(() => ({ olaylar: [] })), api('/api/icra/analiz').catch(() => ({ dosyalar: [] }))]);
      const bugun = new Date(); bugun.setHours(0, 0, 0, 0);
      const kalan = iso => Math.round((new Date(iso + 'T00:00:00') - bugun) / 86400000);
      const l = [];
      (aj.olaylar || []).filter(o => o.tur === 'sure').forEach(o => l.push({ tarih: o.tarih, kalan: o.kalan_gun ?? kalan(o.tarih), tur: 'Tebligat süresi', birim: o.birim, esas: o.esas, aciklama: o.baslik || '', kaynak: o.kaynak }));
      (ia.dosyalar || []).forEach(a => {
        if (a.kesinlesme && a.kesinlesme.son_gun) l.push({ tarih: a.kesinlesme.son_gun, kalan: kalan(a.kesinlesme.son_gun), tur: a.kesinlesme.durum === 'kesinlestirilebilir' ? 'İtiraz süresi doldu → kesinleştir' : 'İcra itiraz süresi', birim: a.birim, esas: a.dosya_no, dkey: a.dkey, aciklama: a.kesinlesme.aciklama });
        if (a.takipsizlik && a.takipsizlik.son_islem_tarihi && ['sari', 'turuncu', 'kirmizi'].includes(a.takipsizlik.seviye)) {
          const d = new Date(a.takipsizlik.son_islem_tarihi + 'T00:00:00'); d.setFullYear(d.getFullYear() + 1);
          const iso = isoGun(d);
          l.push({ tarih: iso, kalan: kalan(iso), tur: '1 yıllık işlemsizlik', birim: a.birim, esas: a.dosya_no, dkey: a.dkey, aciklama: a.takipsizlik.aciklama });
        }
      });
      l.sort((a, b) => a.kalan - b.kalan);
      // v4.9.3: seçili müvekkil filtresi burada da geçerli
      await muvYukle().catch(() => {});
      const ms = muvSuzgec();
      if (ms) { const t = l.filter(ms); l.length = 0; l.push(...t); }
      if (!kap.dataset.muvDinle) { kap.dataset.muvDinle = '1'; const dinle = () => { if (!document.body.contains(kap)) return document.removeEventListener('ca-muvekkil', dinle); dosyaSureleriCiz(kap); }; document.addEventListener('ca-muvekkil', dinle); }
      const renk = k => k < 0 ? ['#fee2e2', '#991b1b'] : k <= 3 ? ['#ffedd5', '#9a3412'] : k <= 10 ? ['#fef9c3', '#854d0e'] : ['#dcfce7', '#166534'];
      kap.innerHTML = `<b>📌 Dosyalarımdaki işleyen süreler</b> <span class="ca-soluk">${l.length} kayıt · tebligatlar (60 gün) ve icra dosyaları${muvSecim.length ? ' · müvekkil: ' + esc(muvSecim.join(', ')) : ''}</span>
        ${l.length ? `<div style="max-height:380px;overflow:auto;margin-top:6px"><table>${l.slice(0, 300).map(x => { const r = renk(x.kalan); return `<tr>
          <td style="white-space:nowrap"><span style="background:${r[0]};color:${r[1]};padding:1px 8px;border-radius:999px;font-size:12px;font-weight:700">${x.kalan < 0 ? Math.abs(x.kalan) + ' gün geçti' : x.kalan === 0 ? 'BUGÜN' : x.kalan + ' gün'}</span><div class="ca-soluk">${esc((x.tarih || '').split('-').reverse().join('.'))}</div></td>
          <td><b>${esc(x.tur)}</b><div class="ca-soluk" style="font-size:12px">${esc((x.aciklama || '').slice(0, 220))}</div></td>
          <td><b>${esc(x.birim || '')}</b><div class="ca-soluk">${esc(x.esas || '')}</div></td>
          <td>${x.dkey ? `<button class="cw-mini" type="button" data-dk="${esc(x.dkey)}">📂</button>` : x.esas ? `<button class="cw-mini" type="button" data-bb="${esc(x.birim || '')}" data-bn="${esc(x.esas)}">📂</button>` : ''}</td></tr>`; }).join('')}</table></div>`
          : '<p class="ca-soluk">İşleyen süre yok (UETS ve icra verisi geldikçe burada listelenir).</p>'}`;
      kap.onclick = e => { const b = e.target.closest('[data-dk],[data-bn]'); if (!b) return; if (b.dataset.dk) dosyaPenceresi(b.dataset.dk); else dosyaPenceresiBul(b.dataset.bb, b.dataset.bn); };
    } catch (e) { kap.innerHTML = `<b>📌 Dosyalarımdaki işleyen süreler</b><div class="ca-soluk">${esc(e.message)}</div>`; }
  }

  function sureSekmesi(ic) {
    const simdi = new Date(); simdi.setSeconds(0, 0);
    const yerel = new Date(simdi.getTime() - simdi.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    ic.innerHTML = `
      <div class="ca-satir">
        <div><label for="ca-gelis">Tebligatın geliş anı (UETS'ye düştüğü)</label><input id="ca-gelis" type="datetime-local" value="${yerel}"></div>
        <div><label for="ca-merci">Merci</label><input id="ca-merci" list="ca-merciler" placeholder="ör. İstanbul 3. Asliye Hukuk Mahkemesi"></div>
        <div><label for="ca-tur">Tebliğ şekli</label><select id="ca-tur"><option value="uets">Elektronik (UETS: 5. gün tebliğ)</option><option value="elden">Fiziki / tebliğ tarihi biliniyor</option></select></div>
      </div>
      <div class="ca-satir" style="margin-top:6px">
        <div><label for="ca-suretur">Süre türü (somut kanun yolu / işlem)</label><select id="ca-suretur">${SURE_TURLERI.map((t, i) => `<option value="${i}">${esc(t[0])}</option>`).join('')}</select></div>
        <div><label for="ca-ozelgun">Mahkemenin verdiği kesin süre (gün)</label><input id="ca-ozelgun" type="number" min="1" placeholder="yalnız 'Kesin süre' seçiliyse"></div>
      </div>
      <datalist id="ca-merciler"><option value="Asliye Hukuk Mahkemesi"><option value="Asliye Ticaret Mahkemesi"><option value="İş Mahkemesi"><option value="Aile Mahkemesi"><option value="Tüketici Mahkemesi"><option value="Sulh Hukuk Mahkemesi"><option value="İcra Hukuk Mahkemesi"><option value="İcra Dairesi"><option value="Asliye Ceza Mahkemesi"><option value="Ağır Ceza Mahkemesi"><option value="Cumhuriyet Başsavcılığı Soruşturma Bürosu"><option value="İdare Mahkemesi"><option value="Vergi Mahkemesi"><option value="Bölge Adliye Mahkemesi Hukuk Dairesi"><option value="Yargıtay Hukuk Dairesi"></datalist>
      <div id="ca-sure-sonuc"></div>
      <div id="ca-sure-muv"></div><div class="ca-kart" id="ca-dosya-sureleri"><b>📌 Dosyalarımdaki işleyen süreler</b> <span class="ca-soluk">yükleniyor…</span></div>
      <p class="ca-soluk">Kural: UETS'de tebliğ, gelişi izleyen 5. gün sayılır (Tebligat K. 7/a); süre tebliğden sonraki günden başlar, son gün hafta sonuna denk gelirse Pazartesi 17:00'ye uzar. Resmî/adli tatil tarihi ileri almaz, yalnızca uyarı olarak gösterilir. Bu bir yardımcı hesaptır; somut süreyi kanun metniyle doğrulayın.</p>`;
    const hesapla = () => {
      const v = ic.querySelector('#ca-gelis').value;
      if (!v) return;
      const s = sureHesapla(new Date(v), ic.querySelector('#ca-merci').value, { elden: ic.querySelector('#ca-tur').value === 'elden' });
      const st = SURE_TURLERI[+ic.querySelector('#ca-suretur').value] || SURE_TURLERI[0];
      if (st[1] !== 'oto') {
        let n = st[2];
        if (st[1] === 'ozel') n = Math.max(1, +ic.querySelector('#ca-ozelgun').value || 0);
        if (st[1] === 'ay') { const d = new Date(s.teblig.getTime()); d.setMonth(d.getMonth() + n); s.hedef = sonGun(d, 0); }
        else s.hedef = sonGun(s.teblig, n);
        s.hedef_str = tarihStr(s.hedef); s.etiket = `${st[0]} — ${st[1] === 'ay' ? n + ' ay' : n + ' gün'}${st[3] ? ' (' + st[3] + ')' : ''}`;
        s.uyarilar = tatilUyarilari(s.hedef, ic.querySelector('#ca-merci').value);
      }
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
    dosyaSureleriCiz(ic.querySelector('#ca-dosya-sureleri'));
    muvekkilSecici(ic.querySelector('#ca-sure-muv'));
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
    // v4.9.3: kart her 4 sn'de innerHTML ile YENİDEN ÇİZİLİYORDU → günlük başa zıplıyor, okunamıyordu; ayrıca
    // sürekli senkron "çalışıyor" olduğu için oturum açıkken bile "Bağlanılıyor…" yazıyordu. Artık iskelet bir kez
    // kurulur, yalnız metinler güncellenir; oturum durumu sunucunun kalıcı izlediği değerden okunur.
    const durumCiz = d => {
      const k = ic.querySelector('#ca-uyap-durum'); if (!k) return;
      if (!k.dataset.kurulu) {
        k.innerHTML = `<div class="ca-hedef" style="font-size:18px" data-r></div><div class="ca-uyari" data-n hidden></div>
          <div class="ca-uyari" style="border-color:#dc2626" data-h hidden></div><p class="ca-soluk" data-z></p>
          <details data-l><summary class="ca-soluk" style="cursor:pointer">Günlük</summary><pre class="ca-gunluk" style="max-height:220px"></pre></details>`;
        k.dataset.kurulu = '1';
      }
      const rozet = d.oturum === true ? '🟢 UYAP oturumu açık'
        : d.oturum === false ? (d.calisiyor ? '🟠 Oturum düştü — yeniden bağlanılıyor (e-İmza / Mobil İmza)…' : '🔴 Oturum açılamadı — yeniden denenecek')
        : d.calisiyor ? '⏳ Oturum kontrol ediliyor…'
        : d.etkin ? '⚪ Sıradaki kontrol bekleniyor' : /kapalı/.test(d.neden || '') ? '⚪ Bağlı tut kapalı' : '⚪ Giriş bilgisi girilmedi';
      k.querySelector('[data-r]').textContent = rozet;
      const n = k.querySelector('[data-n]'); n.hidden = !d.neden; n.textContent = d.neden || '';
      const h = k.querySelector('[data-h]'); h.hidden = !d.son_hata; h.textContent = d.son_hata ? '⚠️ Son turda hata: ' + d.son_hata : '';
      k.querySelector('[data-z]').textContent = (d.oturum_zaman ? `Oturum durumu: ${zamanYaz(d.oturum_zaman)} — ${d.oturum_satir || ''} · ` : '')
        + `Senkron başlangıcı: ${zamanYaz(d.son_baslangic)}` + (d.nabiz && d.nabiz.son ? ` · Son nabız: ${zamanYaz(d.nabiz.son)}` : '');
      gunlukYaz(k.querySelector('pre'), d.gunluk || [], 'Henüz çıktı yok.');
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
      <div id="ca-aj-muv"></div>
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

      const ms = muvSuzgec();
      const filtrelenen = sonOlaylar.filter(o => {
        if (secilenTur && o.tur !== secilenTur) return false;
        if (ms && !ms(o)) return false;
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
                <td><b>${esc(o.birim || '')}</b><div class="ca-soluk">${esc(o.esas || '')}</div>${o.esas ? `<button class="cw-mini" type="button" data-bul-birim="${esc(o.birim || '')}" data-bul-no="${esc(o.esas || '')}">📂 Dosyayı gör</button>` : ''}</td>
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
    muvekkilSecici(ic.querySelector('#ca-aj-muv'), cizTablo);
    muvYukle().then(cizTablo).catch(() => {});
    listeEl.addEventListener('click', e => {
      const b = e.target.closest('[data-bul-no]');
      if (b) dosyaPenceresiBul(b.dataset.bulBirim, b.dataset.bulNo);
    });
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

  // EVRAK ARA: UYAP evrak kataloğunun TAMAMI (kapalı dosyalar dahil arşiv listesi) + Drive indeksi.
  // Yazdıkça aranır (eski istek iptal edilir); sonuçlarda indirmeden Önizle / Orijinal / Drive / Dosyaya git (pencere).
  // v4.9.3: Evrak Ara filtreleri — müvekkil seçici, hızlı tür çipleri (📨 Tebligatlar, Karar, Duruşma, Bilirkişi...),
  // açık/kapalı dosya ve tarih aralığı. Kategori listesi artık sabittir (eskiden ilk sonuçlardan doluyordu).
  const EVRAK_KATEGORILERI = [['tebligat', '📨 Tebligat / Mazbata'], ['karar', '⚖️ Karar / Hüküm'], ['durusma', '🗓️ Duruşma Zaptı'],
    ['tensip', 'Tensip Zaptı'], ['bilirkisi', '🔬 Bilirkişi / Rapor'], ['iddianame', 'İddianame'], ['dilekce', '✍️ Dilekçe / Talep'],
    ['muzekkere', 'Müzekkere / Cevap'], ['talimat', 'Talimat'], ['icra', 'İcra / Haciz'], ['mali', 'Makbuz / Harç'],
    ['kesinlesme', 'Kesinleşme'], ['tutuklama', 'Tutuklama / Adli Kontrol'], ['ifade', 'İfade / Tutanak'], ['vekalet', 'Vekaletname'],
    ['form', 'Form / Cetvel'], ['yazisma', 'Üst Yazı']];
  function evrakSekmesi(ic) {
    ic.innerHTML = `<div class="cw-izgara" id="ca-ev-say" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px"></div>
      <div id="ca-ev-muv"></div>
      <div class="ca-filtre-cipler" id="ca-ev-cip">${[['', 'Tümü'], ['tebligat', '📨 Tebligatlar'], ['karar', '⚖️ Kararlar'], ['durusma', '🗓️ Duruşma zaptı'], ['bilirkisi', '🔬 Bilirkişi'], ['dilekce', '✍️ Dilekçeler']].map(([k, a]) => `<button type="button" data-k="${k}">${a}</button>`).join('')}</div>
      <div style="display:grid;grid-template-columns:3fr 1fr 1fr;gap:8px;margin-top:4px">
        <input id="ca-evrak-q" placeholder='Ara: taraf, evrak türü, mahkeme, esas no… (ör. bilirkişi -ek "ağır ceza")'>
        <select id="ca-ev-d"><option value="">Tüm evrak</option><option value="indirildi">İndirilmiş</option><option value="indirilmedi">İndirilmemiş</option></select>
        <select id="ca-ev-k"><option value="">Tüm kategoriler</option>${EVRAK_KATEGORILERI.map(([k, a]) => `<option value="${k}">${a}</option>`).join('')}</select></div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:6px">
        <select id="ca-ev-dd"><option value="">Açık + kapalı dosyalar</option><option value="acik">Yalnız açık (derdest) dosyalar</option><option value="kapali">Yalnız kapalı dosyalar</option></select>
        <input id="ca-ev-t1" type="date" title="Bu tarihten itibaren">
        <input id="ca-ev-t2" type="date" title="Bu tarihe kadar"></div>
      <div id="ca-evrak-sonuc" style="margin-top:10px"><span class="ca-soluk">Aramak için yazın; boş bırakırsanız en yeni evraklar listelenir.</span></div>`;
    const q = ic.querySelector('#ca-evrak-q'), sonuc = ic.querySelector('#ca-evrak-sonuc'), dSel = ic.querySelector('#ca-ev-d'), kSel = ic.querySelector('#ca-ev-k');
    const sayi = ic.querySelector('#ca-ev-say');
    let zam = null, kontrol = null, sira = 0, offset = 0, birikim = [];
    evrakDugmeBagla(sonuc);
    const sayiCiz = v => {
      if (!document.getElementById('cw-stil')) { const st = document.createElement('style'); st.id = 'cw-stil'; st.textContent = PENCERE_CSS; document.head.appendChild(st); }
      sayi.innerHTML = `<div><span>UYAP evrakı (katalog)</span><b>${(v.toplam_evrak || 0).toLocaleString('tr-TR')}</b><span>${(v.indirilen || 0).toLocaleString('tr-TR')} indirildi</span></div>
        <div><span>Dosya</span><b>${(v.dosya_sayisi || 0).toLocaleString('tr-TR')}</b><span>${(v.taranan_dosya || 0).toLocaleString('tr-TR')} dosyanın evrak listesi alındı</span></div>
        <div><span>Drive indeksi</span><b>${v.drive && v.drive.toplam != null ? v.drive.toplam.toLocaleString('tr-TR') : '—'}</b><span>${v.drive ? 'dosya' : 'aramada gösterilir'}</span></div>`;
      if (v.dosya_sayisi && v.taranan_dosya < v.dosya_sayisi) sayi.insertAdjacentHTML('beforeend', `<div style="grid-column:1/-1" class="ca-uyari">Arşivin tamamı henüz listelenmedi: ${v.dosya_sayisi - v.taranan_dosya} dosyanın evrak listesi Senkron açıkken arka planda alınıyor (1,5 dakikada bir 40 dosya; yeni dosyalar önce). Bitince tüm UYAP evrakı burada aranır. Bir dosyayı hemen istiyorsanız dosyayı açıp "UYAP'tan şimdi getir"e basın.</div>`);
    };
    const ara = async (devam) => {
      if (kontrol) kontrol.abort();
      kontrol = new AbortController();
      const benim = ++sira;
      const metin = q.value.trim();
      if (metin && metin.replace(/[-"\s]/g, '').length < 2) { sonuc.innerHTML = '<span class="ca-soluk">En az 2 harf yazın.</span>'; return; }
      if (!devam) { offset = 0; birikim = []; sonuc.innerHTML = '<span class="ca-soluk">Aranıyor…</span>'; }
      try {
        const ek = `&dosya_durum=${ic.querySelector('#ca-ev-dd').value}&baslangic=${ic.querySelector('#ca-ev-t1').value}&bitis=${ic.querySelector('#ca-ev-t2').value}${muvParam()}`;
        const v = await api(`/api/evrak/ara?limit=100&offset=${offset}&durum=${dSel.value}&kategori=${encodeURIComponent(kSel.value)}&drive=${offset ? 0 : 1}&q=${encodeURIComponent(metin)}${ek}`, { signal: kontrol.signal });
        if (benim !== sira) return;
        if (!v.hazir) { sonuc.innerHTML = `<div class="cw-kart">${esc(v.mesaj)}</div>`; return; }
        if (!offset) { sayiCiz(v); birikim = []; ic._drive = v.drive; }
        birikim = birikim.concat(v.sonuclar);
        offset += v.sonuclar.length;
        const dr = ic._drive;
        if (!devam) ic._dosyalar = v.dosyalar || [];
        const ds = ic._dosyalar || [];
        sonuc.innerHTML = `${ds.length ? `<h4 style="margin:6px 0 4px">📂 Eşleşen dosyalar (${ds.length})</h4><table class="cw-tablo">${ds.map(x => `<tr>
            <td><a href="#" data-dosya-ac="${esc(x.dkey)}"><b>${esc(x.birim || '')}</b></a><div class="ca-soluk">${esc(x.dosya_no || '')} · ${esc(x.durum || '')}</div></td>
            <td class="ca-soluk">${esc((x.taraflar || '').slice(0, 220))}</td>
            <td style="white-space:nowrap">${x.evrak_sayisi ? x.evrak_sayisi + ' evrak' : '<span class="cw-cip gri">liste alınmadı</span>'}</td>
            <td><button class="cw-mini" type="button" data-dosya-ac="${esc(x.dkey)}">📂 Aç</button></td></tr>`).join('')}</table>` : ''}
          <div class="ca-soluk">${birikim.length}${v.sonuclar.length === 100 ? '+' : ''} UYAP evrakı${dr && dr.sonuclar ? ` · ${dr.sonuclar.length} Drive dosyası` : ''}</div>
          <table class="cw-tablo">${birikim.map(r => `<tr>
            <td style="white-space:nowrap">${esc(trT(r.tarih))}</td>
            <td><b>${esc(r.tur || '')}</b><div class="ca-soluk">${esc(r.aciklama || '')}</div></td>
            <td><a href="#" data-dosya-ac="${esc(r.dkey)}">${esc(r.birim || '')}</a><div class="ca-soluk">${esc(r.dosya_no || '')}${r.muvekkil ? ' · ' + esc(r.muvekkil) : ''}${r.dosya_durum && r.dosya_durum !== 'Açık' ? ' · kapalı' : ''}</div></td>
            <td style="white-space:nowrap">${r.yerel ? '<span class="cw-cip yesil">indirildi</span>' : '<span class="cw-cip gri">UYAP\'ta</span>'} ${r.drive ? '<span class="cw-cip mavi">☁</span>' : ''}</td>
            <td>${evrakDugme(r, r.drive_url)} <button class="cw-mini" type="button" data-dosya-ac="${esc(r.dkey)}">📂 Dosya</button></td></tr>`).join('')}</table>
          ${v.sonuclar.length === 100 ? '<button class="ca-btn kucuk" type="button" id="ca-ev-daha">Daha fazla göster</button>' : ''}
          ${dr && dr.sonuclar && dr.sonuclar.length ? `<h4 style="margin:14px 0 4px">☁️ Google Drive'da (${dr.toplam.toLocaleString('tr-TR')} dosyalık indekste)</h4><table class="cw-tablo">${dr.sonuclar.map(f => `<tr><td>${esc(f.ad)}</td><td class="ca-soluk">${esc(f.klasor || '')}</td><td>${f.url ? `<a class="cw-mini" href="${esc(f.url)}" target="_blank" rel="noopener">☁️ Aç</a>` : ''}</td></tr>`).join('')}</table>` : ''}`;
        const daha = sonuc.querySelector('#ca-ev-daha');
        if (daha) daha.onclick = () => ara(true);
      } catch (e) { if (e.name !== 'AbortError' && benim === sira) sonuc.innerHTML = `<div class="cw-kart ca-hata">${esc(e.message)}</div>`; }
    };
    sonuc.addEventListener('click', e => { if (e.target.closest('a[data-dosya-ac]')) e.preventDefault(); });
    q.addEventListener('input', () => { clearTimeout(zam); zam = setTimeout(() => ara(false), 300); });
    const cipCiz = () => ic.querySelectorAll('#ca-ev-cip [data-k]').forEach(b => b.classList.toggle('secili', b.dataset.k === kSel.value));
    ic.querySelector('#ca-ev-cip').onclick = e => { const b = e.target.closest('[data-k]'); if (!b) return; kSel.value = b.dataset.k; cipCiz(); ara(false); };
    dSel.onchange = () => ara(false); kSel.onchange = () => { cipCiz(); ara(false); };
    ['#ca-ev-dd', '#ca-ev-t1', '#ca-ev-t2'].forEach(x => { ic.querySelector(x).onchange = () => ara(false); });
    muvekkilSecici(ic.querySelector('#ca-ev-muv'), () => ara(false));
    cipCiz();
    ara(false);
    q.focus();
  }

  let izleZam = null;
  function gorevIzleDurdur() { if (izleZam) { clearInterval(izleZam); izleZam = null; } }

  const GOREV_ACIKLAMALARI = {
    "hesap-tara": "UYAP'tan tüm dosyaların gerçek hesaplarını çeker: icra kapak hesabı, tahsilat/reddiyat, harç kalemleri ve davalarda artan avans. Gizli oturumla çalışır, tarayıcı açmaz.",
    "notion-esitle": "UYAP kataloğundaki dosyaları Notion'a işler: eksik dosyalar, açılış tarihi, durum, müvekkil ve karşı taraf bağlantıları, aynı ikonlar ve 5-10 cümlelik dosya konusu. Elle yazılmış konu ezilmez.",
    "ticktick-duzen": "TickTick'i düzenler: aktif, tamamlanan ve yapılmayacak görevlerle mükerrer kontrolü; eksik tebligat (üstyazı/ek/bilgi) işaretleme; Notion'daki her açık dosyaya kart ve dosya konusu.",
    "uets-senkron": "Her çalışmada UETS'ye girip GÜNCEL tebligat listesini (CSV) indirir; listedeki tebligatlardan EYP paketi yerelde olmayanları indirir (olanları indirmez), TickTick'e eksiksiz aktarır ve yasal süreleri hesaplar. Liste indirilemezse eski yerel liste KULLANILMAZ.",
    "uets-otokontrol": "Tebligat sürelerinde çakışma, kaçırılma riski veya eksik evrak olup olmadığını denetleyen güvenlik raporu üretir.",
    "evrak-nobetci": "UYAP Avukat Portalını nöbetçi modunda arka planda periyodik olarak tarar. Büronuzun tüm derdest dosyalarındaki yeni evrakları anında yakalar ve indirir.",
    "evrak-islemlerim": "UYAP Avukat Portalındaki 'İşlemlerim' sekmesini tarar; son yapılan havaleler, tensip zaptı onayları ve ara kararları anında günceller.",
    "evrak-tebligat": "Katalogdaki tüm tebligat, mazbata ve tebellüğ belgelerini ÖNCELİKLE indirir: Senkron o an ne yapıyorsa bırakıp önce bunları indirir, PDF'e çevirir ve Drive'a eşitler. Burada ilerleme görünür.",
    "evrak-durusmalar": "Büronuzun tüm mahkemelerdeki duruşma tarihlerini, saatlerini ve duruşma salonlarını UYAP'tan çeker.",
    "evrak-giris": "UYAP portalına güvenli elektronik imza veya mobil imza ile otomatik yetkilendirme ve oturum tazeleme işlemi yapar.",
    "asistan-gui": "Masaüstü Avukat Asistanı bağımsız yönetim penceresini açar.",
    "evrak-katalog": "İndirilen tüm evrakları yerel SQLite veritabanına indeksler ve A4 PDF dönüşüm kuyruğunu yönetir."
  };

  // 📨 Tebligatlar: masaüstündeki "Avukat Asistanı penceresi"nin (Tk) telefonda da çalışan karşılığı.
  // UETS'ten taze CSV + EYP indirme, TickTick'e eklerle aktarma, Notion eşleşmesi ve durum tablosu.
  async function tebligatSekmesi(ic) {
    const gunlukKutu = id => `<pre id="${id}" class="ca-gunluk" style="display:none;max-height:240px;overflow:auto;padding:10px;border-radius:8px;white-space:pre-wrap"></pre>`;
    ic.innerHTML = `<div class="ca-kart">
        <b>📨 UETS Tebligatları → TickTick (EYP ekleriyle) + Notion</b>
        <p class="ca-soluk" style="margin:6px 0">UETS'e arka planda (görünmez tarayıcıyla) girer, güncel CSV'yi ve eksik EYP paketlerini indirir; her tebligatı ilgili Notion dosyasıyla eşleştirip TickTick'e ekleriyle ekler.</p>
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          <button class="ca-btn ana" type="button" id="tb-uets">🌐 UETS'ten İndir & Senkronize Et</button>
          <button class="ca-btn" type="button" id="tb-yenile">🔄 Durumu Yenile</button>
          <button class="ca-btn" type="button" id="tb-temizle">🧹 TickTick Mükerrer Temizle</button>
          <button class="ca-btn" type="button" id="tb-excel">📑 UYAP Excel</button>
        </div>
        <div style="margin-top:8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap"><label style="margin:0">🔁 Arka planda otomatik:</label>
          <select id="tb-oto" style="max-width:220px"><option value="0">Kapalı</option><option value="30">30 dakikada bir</option><option value="60">Saatte bir</option><option value="120">2 saatte bir</option><option value="240">4 saatte bir</option><option value="720">12 saatte bir</option></select>
          <span id="tb-oto-bilgi" class="ca-soluk"></span></div>
        <div id="tb-islem" class="ca-soluk" style="margin-top:8px"></div>
        <div id="tb-otp" style="display:none;margin-top:8px" class="ca-uyari">📬 UETS giriş kodu bekleniyor. Gmail ayarlıysa otomatik okunur; değilse telefonunuza/e-postanıza gelen kodu yazın:
          <div style="display:flex;gap:6px;margin-top:6px"><input id="tb-otp-kod" inputmode="numeric" autocomplete="one-time-code" placeholder="6 haneli kod" style="max-width:160px"><button class="ca-btn ana" type="button" id="tb-otp-gonder">Gönder</button></div></div>
        ${gunlukKutu('tb-gunluk')}
      </div>
      <div class="ca-kart"><div id="tb-muv"></div>
        <div style="display:grid;grid-template-columns:2fr 1fr;gap:8px"><input id="tb-q" placeholder="Mahkeme, esas no, barkod, müvekkil ara…">
          <select id="tb-f"><option value="">Tüm tebligatlar</option><option value="sure">Süresi işleyenler (son gün geçmemiş)</option><option value="gecmis">Son günü geçmiş</option><option value="eksik">TickTick'te eksik / ek bekleyen</option><option value="eypyok">EYP paketi inmemiş</option></select></div>
        <div id="tb-liste" style="margin-top:8px" class="ca-soluk">Tebligat durumu yükleniyor…</div></div>`;
    const islem = ic.querySelector('#tb-islem'), liste = ic.querySelector('#tb-liste'), gl = ic.querySelector('#tb-gunluk');
    liste.addEventListener('click', e => { const b = e.target.closest('[data-bul-no]'); if (b) dosyaPenceresiBul(b.dataset.bulBirim, b.dataset.bulNo); });
    let veri = [];
    const renk = { green: '#16a34a', blue: '#2563eb', orange: '#d97706', red: '#dc2626', gray: '#64748b' };
    const ciz = () => {
      const q = (ic.querySelector('#tb-q').value || '').toLocaleLowerCase('tr');
      const f = ic.querySelector('#tb-f').value, ms = muvSuzgec();
      const bugun = new Date().toISOString().slice(0, 10);
      const sgIso = d => { const m = String(d.son_gun || '').match(/(\d{2})\.(\d{2})\.(\d{4})/); return m ? `${m[3]}-${m[2]}-${m[1]}` : String(d.son_gun || '').slice(0, 10); };
      const l = veri.filter(d => (!q || `${d.mahkeme} ${d.esas} ${d.barkod} ${d.muvekkil} ${d.durum}`.toLocaleLowerCase('tr').includes(q))
        && (!ms || ms(d) || muvSecim.some(a => katla(d.muvekkil || '').includes(katla(a))))
        && (!f || (f === 'sure' && d.son_gun && sgIso(d) >= bugun) || (f === 'gecmis' && d.son_gun && sgIso(d) < bugun)
          || (f === 'eksik' && /MISSING|PENDING/.test(d.durum_kodu || '')) || (f === 'eypyok' && !d.eyp)));
      const say = k => veri.filter(d => (d.durum_kodu || '').includes(k)).length;
      liste.innerHTML = `<div class="ca-soluk" style="margin-bottom:6px">${veri.length} tebligat · ✓ ${say('SYNCED') + say('COMPLETED')} TickTick'te · ⚠️ ${say('MISSING')} eksik · 📎 ${say('PENDING_ATTACHMENT')} ek bekliyor</div>
        <table>${l.map(d => `<tr>
          <td><b>${esc(d.mahkeme)}</b> <span class="ca-soluk">${esc(d.esas)}</span><div class="ca-soluk">Barkod ${esc(d.barkod)} · geliş ${esc((d.gelis || '').slice(0, 10))}${d.muvekkil ? ' · ' + esc(d.muvekkil) : ''}</div></td>
          <td style="white-space:nowrap">${d.son_gun ? '⏰ ' + esc(d.son_gun) : '—'}</td>
          <td><span style="color:${renk[d.renk] || '#64748b'};font-weight:600">${esc(d.durum)}</span><div class="ca-soluk">${d.eyp ? '📦 EYP var' : '❌ EYP yok'}</div></td>
          <td style="white-space:nowrap"><button class="ca-btn kucuk ana" type="button" data-zorla="${esc(d.barkod)}">⚡ TickTick'e ekle</button>
            ${d.notion_url ? `<a class="ca-btn kucuk" href="${esc(d.notion_url)}" target="_blank" rel="noopener">Notion</a>` : ''}
            <button class="ca-btn kucuk" type="button" data-bul-birim="${esc(d.mahkeme || '')}" data-bul-no="${esc(d.esas || '')}">📂 Dosya</button></td></tr>`).join('') || '<tr><td>Kayıt yok. Önce "UETS\'ten İndir" çalıştırın.</td></tr>'}</table>`;
      liste.querySelectorAll('[data-zorla]').forEach(b => { b.onclick = () => calistir('zorla', { barkod: b.dataset.zorla }, b); });
    };
    // v4.9.3: sunucu son listeyi hemen döndürür, eskiyse arka planda tazeler; tazelenince kendiliğinden yeniden çizilir
    const yukle = async (tazele) => {
      if (!veri.length) liste.innerHTML = '<span class="ca-soluk">⏳ Tebligatlar, TickTick ve Notion taranıyor (ilk açılışta bir kez sürer)…</span>';
      try {
        const r = await api('/api/tebligat/liste', { method: 'POST', govde: tazele ? { tazele: true } : {} });
        veri = r.tebligatlar || []; ciz();
        const not = r.tazeleniyor ? '🔄 Liste arka planda tazeleniyor…' : (r.zaman ? 'Son güncelleme: ' + new Date(r.zaman * 1000).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }) : '');
        liste.insertAdjacentHTML('afterbegin', `<div class="ca-soluk" style="margin-bottom:4px">${not}${r.son_hata ? ' · ⚠️ ' + esc(r.son_hata) : ''}</div>`);
        if (r.tazeleniyor) setTimeout(() => { if (document.body.contains(liste)) yukle(); }, 8000);
      } catch (e) { liste.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
    };
    const calistir = async (komut, govde, btn) => {
      if (btn) btn.disabled = true;
      islem.textContent = '⏳ Çalışıyor…';
      try {
        const r = await api('/api/tebligat/' + komut, { method: 'POST', govde: govde || {} });
        islem.innerHTML = `✓ ${esc(r.sonuc || 'Tamam')}`;
        if (r.gunluk && r.gunluk.length) { gl.style.display = 'block'; gl.textContent = r.gunluk.join('\n'); }
        yukle();
      } catch (e) { islem.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
      finally { if (btn) btn.disabled = false; }
    };
    // UETS indirme uzun sürer: mevcut "uets-senkron" görevi başlatılır, günlüğü canlı izlenir
    ic.querySelector('#tb-uets').onclick = async () => {
      try { await api('/api/gorev/uets-senkron', { method: 'POST', govde: {} }); }
      catch (e) { islem.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; return; }
      gl.style.display = 'block';
      for (;;) {
        let g;
        try { g = (await api('/api/gorevler')).gorevler.find(x => x.kimlik === 'uets-senkron'); } catch (e) { break; }
        if (!g) break;
        gunlukYaz(gl, g.gunluk || []);
        const kodBekliyor = g.calisiyor && (g.gunluk || []).slice(-6).some(x => /OTP|Doğrulama kodu|kod henüz gelmedi/i.test(x));
        ic.querySelector('#tb-otp').style.display = kodBekliyor ? 'block' : 'none';
        islem.textContent = g.calisiyor ? '⏳ UETS senkronizasyonu sürüyor (paneli kapatabilirsiniz)…' : (g.kod === 0 ? '✓ UETS senkronizasyonu tamamlandı' : `⚠️ UETS görevi ${g.kod} koduyla bitti`);
        if (!g.calisiyor) { yukle(); break; }
        await new Promise(r => setTimeout(r, 2500));
        if (!document.body.contains(gl)) return;
      }
    };
    ic.querySelector('#tb-otp-gonder').onclick = async () => {
      const kod = ic.querySelector('#tb-otp-kod').value.replace(/\D/g, '');
      try { await api('/api/uets/otp', { method: 'POST', govde: { kod } }); islem.textContent = '✓ Kod gönderildi, giriş yapılıyor…'; ic.querySelector('#tb-otp-kod').value = ''; }
      catch (e) { islem.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
    };
    const oto = ic.querySelector('#tb-oto'), otoBilgi = ic.querySelector('#tb-oto-bilgi');
    const otoYaz = a => { oto.value = String(a.aralik_dk || 0); if (![...oto.options].some(o => o.value === oto.value)) oto.value = '60';
      otoBilgi.textContent = !a.hazir ? '⚠️ Önce Notion/TickTick sekmesinde UETS TC ve şifresini girin' : (a.aralik_dk && a.sonraki ? 'sonraki: ' + new Date(a.sonraki * 1000).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }) : ''); };
    api('/api/uets/ayar').then(otoYaz).catch(() => {});
    oto.onchange = async () => { try { otoYaz(await api('/api/uets/ayar', { method: 'POST', govde: { aralik_dk: +oto.value } })); } catch (e) { otoBilgi.textContent = e.message; } };
    ic.querySelector('#tb-yenile').onclick = () => yukle(true);
    ic.querySelector('#tb-temizle').onclick = e => calistir('temizle', {}, e.currentTarget);
    ic.querySelector('#tb-excel').onclick = e => calistir('excel', {}, e.currentTarget);
    ic.querySelector('#tb-q').oninput = ciz;
    ic.querySelector('#tb-f').onchange = ciz;
    muvekkilSecici(ic.querySelector('#tb-muv'), ciz);
    muvYukle().then(() => { if (veri.length) ciz(); }).catch(() => {});
    yukle();
  }

  // Görevler: OTOMATİK çalışanlar üstte (durum + son satır), elle çalıştırılanlar altta. Sayfa her 3 sn'de
  // YENİDEN ÇİZİLMEZ; yalnızca rozet, düğme ve günlük metni yerinde güncellenir. Günlükte yukarı kaydırdıysanız
  // yerinde kalır (eskiden her yenilemede başa zıplıyordu); en alttaysanız yeni satırları izler.
  const OTOMATIK_GOREVLER = ['evrak-akis', 'uets-senkron', 'hesap-tara', 'notion-esitle', 'ticktick-duzen'];
  const GIZLI_GOREVLER = ['asistan-gui', 'evrak-katalog'];   // eski masaüstü pencereleri: yerlerini paneller aldı
  // v4.10.0 — 🩺 SAĞLIK / GÜNLÜK: öz-denetim raporu (oz_denetim.py) + tüm modüllerin birleşik günlüğü.
  // Uygulama her 3 saatte bir kendini sınar ve onarır (PDF motoru, bozuk PDF'ler, veritabanı bütünlüğü, katalog,
  // TickTick düzeni...). Bu sekme son raporu gösterir, elle çalıştırır ve günlüğü kaynak/seviye/metinle süzer.
  // Terminal karşılığı: `caneditor oz-denetim` ve `caneditor log -f`.
  // EN: health tab — last self-test report, run now, unified log with level/source/text filters.
  async function saglikSekmesi(ic) {
    const SEV = { tamam: ['✓', 'tamam'], uyari: ['⚠', 'uyari'], hata: ['✕', 'hata'] };
    ic.innerHTML = `<div class="ca-kart">
        <h3 style="margin-top:0">🩺 Öz-denetim</h3>
        <p class="ca-soluk">CanEditor kendini düzenli aralıklarla sınar ve bulduğu tutarsızlıkları onarır. Hiçbir belge silinmez;
        onarımlar tekrar tekrar çalıştırılabilir. Terminal: <code>caneditor oz-denetim</code></p>
        <div class="ca-sira" style="display:flex;gap:8px;flex-wrap:wrap">
          <button class="ca-btn ana" type="button" id="sg-onar" data-ipucu="Tüm denetimleri çalıştırır ve bulunan sorunları onarır: bozuk/boş PDF'leri resmî motorla yeniden üretir, diskte olmayan evrakları yeniden indirme kuyruğuna alır, veritabanını onarır, TickTick düzenini başlatır.">🛠️ Şimdi denetle ve onar</button>
          <button class="ca-btn" type="button" id="sg-oku" data-ipucu="Yalnız rapor üretir; hiçbir şeyi değiştirmez.">🔍 Yalnız denetle</button>
        </div>
        <div id="sg-rapor" style="margin-top:10px"><p class="ca-soluk">Rapor yükleniyor…</p></div>
      </div>
      <div class="ca-kart">
        <h3 style="margin-top:0">📜 Birleşik günlük</h3>
        <div class="ca-filtre-cipler" id="sg-sev">${[['', 'Tümü'], ['HATA', '✕ Hatalar'], ['UYARI', '⚠ Uyarılar'], ['BILGI', 'ℹ Bilgi']].map(([k, a]) => `<button type="button" data-k="${k}">${a}</button>`).join('')}</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin:6px 0">
          <select id="sg-kaynak" data-ipucu="Günlüğü üreten modüle göre süz (sunucu, görevler, dönüştürücü, imza, CLI...)"><option value="">Tüm kaynaklar</option></select>
          <input id="sg-q" placeholder="Günlükte ara (Türkçe karakter duyarsız)…" style="flex:1;min-width:180px" data-ipucu="Yazdığınız kelimeleri içeren satırlar kalır; -kelime yazarsanız o kelimeyi içerenler çıkarılır.">
          <button class="ca-btn kucuk" type="button" id="sg-yenile" data-ipucu="Günlüğü yeniden yükle (her 5 sn'de kendiliğinden de yenilenir)">⟳</button>
        </div>
        <pre id="sg-log" style="max-height:420px;overflow:auto;white-space:pre-wrap;font-size:12px"></pre>
      </div>`;
    const raporEl = ic.querySelector('#sg-rapor'), logEl = ic.querySelector('#sg-log');
    let satirlar = [], sev = '';
    const katla = t => String(t || '').toLocaleLowerCase('tr').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/ı/g, 'i');
    const raporCiz = v => {
      const r = (v && v.rapor) || {};
      if (!r.denetimler) { raporEl.innerHTML = '<p class="ca-soluk">Henüz rapor yok. “Şimdi denetle ve onar”a basın.</p>'; return; }
      const o = r.ozet || {};
      raporEl.innerHTML = `<div class="ca-soluk" style="margin-bottom:6px">Son denetim: <b>${esc((r.zaman || '').replace('T', ' '))}</b> · ✓ ${o.tamam || 0} · ⚠ ${o.uyari || 0} · ✕ ${o.hata || 0} · 🛠️ onarılan ${o.onarilan || 0}${v.calisiyor ? ' · <b>şu an çalışıyor…</b>' : ''}</div>
        <table class="ca-tablo"><tr><th>Denetim</th><th>Durum</th><th>Ayrıntı</th></tr>${Object.entries(r.denetimler).map(([ad, d]) => {
          const [ik, sn] = SEV[d.durum] || ['?', ''];
          const ayr = Object.entries(d).filter(([k]) => !['durum', 'sure_sn'].includes(k)).map(([k, x]) => `${esc(k)}: ${esc(typeof x === 'object' ? JSON.stringify(x) : x)}`).join(' · ');
          return `<tr><td><b>${esc(ad)}</b></td><td><span class="gv-rozet ${sn === 'tamam' ? 'tamam' : sn === 'hata' ? 'hata' : 'calisiyor'}">${ik} ${esc(d.durum)}</span></td><td class="ca-soluk" style="font-size:12px">${ayr.slice(0, 600)}</td></tr>`;
        }).join('')}</table>`;
    };
    const logCiz = () => {
      const q = ic.querySelector('#sg-q').value, ks = ic.querySelector('#sg-kaynak').value;
      const art = katla(q).split(/\s+/).filter(x => x && !x.startsWith('-')), eks = katla(q).split(/\s+/).filter(x => x.length > 1 && x.startsWith('-')).map(x => x.slice(1));
      const l = satirlar.filter(s => (!sev || s.includes(`[${sev}]`)) && (!ks || s.includes(`] ${ks}`))
        && art.every(x => katla(s).includes(x)) && !eks.some(x => katla(s).includes(x)));
      logEl.textContent = l.slice(-600).join('\n') || 'Eşleşen günlük satırı yok.';
      logEl.scrollTop = logEl.scrollHeight;
    };
    const yukle = async () => {
      try {
        const v = await api('/api/oz-denetim?satir=1500');
        raporCiz(v);
        satirlar = v.gunluk || [];
        const sel = ic.querySelector('#sg-kaynak'), mevcut = sel.value;
        const kaynaklar = [...new Set(satirlar.map(s => (s.match(/\] ([^:]+):/) || [])[1]).filter(Boolean))].sort();
        sel.innerHTML = '<option value="">Tüm kaynaklar</option>' + kaynaklar.map(k => `<option${k === mevcut ? ' selected' : ''}>${esc(k)}</option>`).join('');
        logCiz();
      } catch (e) { raporEl.innerHTML = `<div class="ca-hata">${esc(e.message || e)}</div>`; }
    };
    ic.querySelectorAll('#sg-sev button').forEach(b => b.onclick = () => {
      sev = b.dataset.k; ic.querySelectorAll('#sg-sev button').forEach(x => x.classList.toggle('secili', x === b)); logCiz();
    });
    ic.querySelector('#sg-sev button').classList.add('secili');
    ic.querySelector('#sg-q').oninput = logCiz;
    ic.querySelector('#sg-kaynak').onchange = logCiz;
    ic.querySelector('#sg-yenile').onclick = yukle;
    const calistir = async salt => {
      raporEl.innerHTML = '<p class="ca-soluk">Denetim çalışıyor (PDF motoru, veritabanları, katalog, TickTick)…</p>';
      try { raporCiz({ rapor: await api('/api/oz-denetim', { method: 'POST', govde: { bekle: true, salt_oku: salt } }) }); } catch (e) { raporEl.innerHTML = `<div class="ca-hata">${esc(e.message || e)}</div>`; }
      yukle();
    };
    ic.querySelector('#sg-onar').onclick = () => calistir(false);
    ic.querySelector('#sg-oku').onclick = () => calistir(true);
    await yukle();
    const z = setInterval(() => { if (!document.body.contains(ic) || aktifSekme !== 'saglik') return clearInterval(z); yukle(); }, 5000);
  }

  async function gorevSekmesi(ic) {
    ic.innerHTML = '<p class="ca-soluk">Görevler yükleniyor…</p>';
    let kurulu = false;
    const rozet = g => g.calisiyor ? '<span class="gv-rozet calisiyor">● Çalışıyor</span>'
      : g.kod === 0 ? '<span class="gv-rozet tamam">✓ Tamamlandı</span>'
      : (g.kod !== null && g.kod !== undefined) ? `<span class="gv-rozet hata">✕ Hata (kod ${g.kod})</span>`
      : '<span class="gv-rozet bos">Beklemede</span>';
    // v4.9.3: asıl hata satırı gösterilir. Eskiden son satır alınıyordu: PyInstaller'ın genel "Failed to execute
    // script 'sunucu'" satırı ya da ham @@SONUC@@ JSON'u hata diye görünüyordu. 🛑 güvenlik durdurmaları da gösterilir.
    const sonHata = g => {
      const l = (g.gunluk || []).filter(x => !/@@SONUC@@|Failed to execute script|^\s*File "|^\s*\^+\s*$|Traceback \(most recent/.test(x));
      const dur = l.filter(x => x.includes('🛑')).slice(-1)[0];
      if (g.calisiyor || !g.kod) return dur ? dur.replace(/^.*?🛑/, '🛑') : '';
      const s = l.filter(x => /^\s*[\w.]+(Error|Exception|Hatasi|Kesildi)\b.*:/.test(x)).slice(-1)[0]
        || l.filter(x => /error|hata|exception|❌|\[x\]|\[!\]|🛑/i.test(x)).slice(-1)[0] || l.slice(-1)[0] || '';
      return s.replace(/^.*?\] /, '').trim().slice(0, 300);
    };
    const kart = g => `<div class="gv-kart" data-g="${g.kimlik}">
        <div class="gv-ust"><div><b>${esc(g.ad)}</b> <span class="gv-r"></span></div><div class="gv-d"></div></div>
        <p class="gv-acik">${esc(GOREV_ACIKLAMALARI[g.kimlik] || '')}</p>
        <div class="gv-hata ca-hata" hidden></div>
        <details class="gv-log"><summary>Günlük</summary><pre></pre></details>
      </div>`;
    const guncelle = (el, g) => {
      el.querySelector('.gv-r').innerHTML = rozet(g);
      const d = el.querySelector('.gv-d');
      const dugme = g.kullanilamaz ? `<span class="ca-soluk">${esc(g.kullanilamaz)}</span>`
        : g.calisiyor ? `<button class="ca-btn kucuk" style="background:#D32F2F;color:#fff" type="button" data-durdur="${g.kimlik}">⏹ Durdur</button>`
        : `<button class="ca-btn ana kucuk" type="button" data-baslat="${g.kimlik}">▶ Çalıştır</button>`;
      if (d.dataset.h !== dugme) { d.innerHTML = dugme; d.dataset.h = dugme; }
      const h = el.querySelector('.gv-hata');
      const sh = sonHata(g);
      h.hidden = !sh; h.textContent = sh;
      gunlukYaz(el.querySelector('pre'), g.gunluk || [], 'Henüz çıktı yok.');
      if (g.calisiyor && !el.dataset.acildi) { el.querySelector('details').open = true; el.dataset.acildi = '1'; }
    };
    const ciz = async () => {
      const [v, p] = await Promise.all([api('/api/gorevler?satir=200'), api('/api/pano').catch(() => ({}))]);
      const gs = v.gorevler.filter(g => !GIZLI_GOREVLER.includes(g.kimlik));
      if (!kurulu) {
        const oto = gs.filter(g => OTOMATIK_GOREVLER.includes(g.kimlik));
        const elle = gs.filter(g => !OTOMATIK_GOREVLER.includes(g.kimlik));
        ic.innerHTML = `<style>
          .gv-kart{border:1px solid var(--ce-border,#e2e8f0);border-radius:10px;padding:10px 12px;margin-bottom:8px;background:var(--ce-surface,#fff)}
          .gv-ust{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
          .gv-acik{font-size:12px;color:var(--ce-muted,#64748b);margin:4px 0}
          .gv-rozet{font-size:11.5px;padding:2px 8px;border-radius:999px;font-weight:600}
          .gv-rozet.calisiyor{background:#dcfce7;color:#166534}.gv-rozet.tamam{background:#eef2ff;color:#3730a3}
          .gv-rozet.hata{background:#fee2e2;color:#991b1b}.gv-rozet.bos{background:#f1f5f9;color:#475569}
          .gv-log summary{cursor:pointer;font-size:12px;color:var(--ce-muted,#64748b)}
          .gv-log pre{max-height:320px;overflow:auto;padding:8px;border-radius:6px;white-space:pre-wrap}
          .gv-hata{font-size:12px;margin:2px 0 4px}
          .gv-ozet{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:8px;margin-bottom:12px}
          .gv-ozet div{border:1px solid var(--ce-border,#e2e8f0);border-radius:10px;padding:8px 10px}
          .gv-ozet b{display:block;font-size:13px}.gv-ozet span{font-size:12px;color:var(--ce-muted,#64748b)}
        </style>
        <div class="gv-ozet" id="gv-ozet"></div>
        <h3 style="margin:6px 0">⚙️ Otomatik çalışanlar</h3>
        <p class="ca-soluk" style="margin-top:0">Bunlar kendiliğinden çalışır; burada yalnızca izlenir. Elle başlatmanız gerekmez.</p>
        ${oto.map(kart).join('')}
        <details style="margin-top:14px"><summary style="cursor:pointer;font-weight:600">🛠️ Elle çalıştırılan araçlar (${elle.length})</summary>
          <div style="margin-top:8px">${elle.map(kart).join('')}</div></details>`;
        ic.addEventListener('click', async e => {
          const b = e.target.closest('[data-baslat],[data-durdur]');
          if (!b) return;
          b.disabled = true;
          try {
            if (b.dataset.baslat) await api('/api/gorev/' + b.dataset.baslat, { method: 'POST', govde: {} });
            else await api('/api/gorev/' + b.dataset.durdur + '/durdur', { method: 'POST', govde: {} });
          } catch (er) { alert(er.message); }
          ciz().catch(() => {});
        });
        kurulu = true;
      }
      gs.forEach(g => { const el = ic.querySelector(`.gv-kart[data-g="${g.kimlik}"]`); if (el) guncelle(el, g); });
      const t = p.tebligat || {}, s = p.senkron || {}, z = p.duzen || {};
      const oz = ic.querySelector('#gv-ozet');
      if (oz) oz.innerHTML = `
        <div><b>${s.acik ? '🟢' : '⚪'} UYAP → Drive</b><span>${s.acik ? 'Sürekli açık' : 'Kapalı (Ana Ekran\'dan başlatın)'}</span></div>
        <div><b>${t.aralik_dk ? '🟢' : '⚪'} UETS tebligat</b><span>${t.aralik_dk ? t.aralik_dk + ' dk\'da bir' : 'Otomatik kapalı'}</span></div>
        <div><b>${z.hazir ? '🟢' : '⚪'} Notion & TickTick</b><span>${z.hazir ? '6 saatte bir düzen' : 'Anahtarlar girilmemiş'}</span></div>
        <div><b>🟢 Dosya hesapları</b><span>Senkron boştayken azar azar</span></div>`;
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

    // CANLI: tüm servisler gerçekten denenir (UYAP oturumu + imza yöntemi, UETS, Gmail kodu, Drive, Notion,
    // TickTick, Telegram), arşiv sayıları ve kopma/yeniden bağlanma kayıtları. 30 sn'de bir kendiliğinden tazelenir.
    const RENK = { ok: ['#dcfce7', '#166534', '● Bağlı'], hata: ['#fee2e2', '#991b1b', '● Hata'], uyari: ['#fef9c3', '#854d0e', '● Bekliyor'], yok: ['#f1f5f9', '#475569', '○ Ayarlanmadı'] };
    const sayiK = (a, x, alt) => `<div style="border:1px solid var(--ce-border,#e2e8f0);border-radius:10px;padding:8px 10px"><span style="font-size:12px;color:var(--ce-muted,#64748b)">${a}</span><b style="display:block;font-size:18px">${x == null ? '—' : Number(x).toLocaleString('tr-TR')}</b>${alt ? `<span style="font-size:11.5px;color:var(--ce-muted,#64748b)">${alt}</span>` : ''}</div>`;
    const saglikYukle = async (zorla) => {
      try {
        const v = await api('/api/baglanti/canli' + (zorla ? '?yenile=1' : ''));
        const sy = v.sayilar || {};
        const sa = Math.floor((v.calisma_sn || 0) / 3600), dk = Math.floor(((v.calisma_sn || 0) % 3600) / 60);
        saglikEl.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
            <b>🔌 Canlı Bağlantılar</b><span class="ca-soluk">${esc(v.zaman)} · sunucu ${sa} sa ${dk} dk açık · v${esc(v.surum)}
            <button class="ca-btn kucuk" type="button" id="ca-canli-yenile" style="margin:0 0 0 6px">↻ Şimdi ölç</button></span></div>
          <table style="margin-top:8px">${(v.servisler || []).map(x => { const r = RENK[x.durum] || RENK.yok; return `<tr>
            <td style="white-space:nowrap"><b>${esc(x.ad)}</b></td>
            <td style="white-space:nowrap"><span style="background:${r[0]};color:${r[1]};padding:1px 8px;border-radius:999px;font-size:12px;font-weight:600">${r[2]}</span></td>
            <td>${esc(x.mesaj || '')}</td><td class="ca-soluk" style="white-space:nowrap;text-align:right">${x.ms} ms</td></tr>`; }).join('')}</table>
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin-top:12px">
            ${sayiK('Drive\'daki dosya (UYAP arşivi)', sy.drive_dosya, `${(sy.drive_yuklenen || 0).toLocaleString('tr-TR')} evrak bu cihazdan yüklendi`)}
            ${sayiK('UYAP dosyası', sy.dosya, `${(sy.acik_dosya || 0).toLocaleString('tr-TR')} açık`)}
            ${sayiK('UYAP evrakı (katalog)', sy.evrak, `${(sy.indirilen || 0).toLocaleString('tr-TR')} indirildi · son 7 gün ${(sy.son7_evrak || 0).toLocaleString('tr-TR')}`)}
            ${sayiK('Tebligat (UETS)', sy.tebligat, `son 7 gün ${(sy.son7_tebligat || 0).toLocaleString('tr-TR')}`)}
            ${sayiK('Süresi 3 gün içinde dolan', sy.sure_3gun, 'Ajanda\'da ayrıntı')}
            ${sayiK('7 gün içinde duruşma', sy.durusma_7gun)}
            ${sayiK('Yargıtay kararı (hayfahukuk)', sy.yargitay_karar, 'toplam arşiv')}
          </div>
          <div style="margin-top:12px"><b>Kopma / yeniden bağlanma kayıtları</b>
            ${(v.kesintiler || []).length ? `<table>${v.kesintiler.slice(0, 20).map(k => `<tr><td class="ca-soluk" style="white-space:nowrap">${esc(k.zaman)}</td><td><b>${esc(k.servis)}</b></td><td>${esc(k.olay)}</td><td class="ca-soluk">${esc(k.mesaj || '')}</td></tr>`).join('')}</table>` : '<div class="ca-soluk">Bu oturumda kopma olmadı.</div>'}
            <div class="ca-soluk">UYAP oturum kesintisi: ${v.uyap_kesinti && v.uyap_kesinti.sayi ? v.uyap_kesinti.sayi + ' kez (son ' + esc(v.uyap_kesinti.son) + ')' : 'yok'} · HTTPS sertifikaları: ${esc(v.ssl_sertifika)}</div></div>`;
        const yb = saglikEl.querySelector('#ca-canli-yenile');
        if (yb) yb.onclick = () => { yb.disabled = true; yb.textContent = 'Ölçülüyor…'; saglikYukle(true); };
      } catch (e) {
        saglikEl.innerHTML = `<b>🔌 Canlı Bağlantılar</b><div class="ca-hata">Alınamadı: ${esc(e.message)}</div>`;
      }
    };
    izleZam = setInterval(() => { if (document.body.contains(saglikEl)) saglikYukle(false); else gorevIzleDurdur(); }, 30000);

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

        // v4.9.3: müvekkil seçiliyse yalnız o müvekkilin dosyalarına düşen evrak/tebligat gösterilir
        await muvYukle().catch(() => {});
        const ms = muvSuzgec();
        const tb = (v.tebligatlar || []).filter(t => !ms || ms(t));
        const gorunen = ms ? tumEvraklar.filter(ms) : tumEvraklar;

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

          <div id="ca-yeni-muv"></div>
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
            ${gorunen.map(r => `
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
              gorunen.forEach(e => seciliSkeys.add(e.skey));
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
          b.onclick = () => hemenIndir([b.dataset.indirSkey], b);
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
        if (topIndir) topIndir.onclick = () => { const l = Array.from(seciliSkeys); if (!l.length) return alert('Lütfen en az bir evrak seçin.'); hemenIndir(l, topIndir); };

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
        muvekkilSecici(ic.querySelector('#ca-yeni-muv'), () => yukleVeCiz(false));

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
        <div><label>Suç tarihi</label><input type="date" name="sucTarihi" value="2023-01-15"></div>
        <div><label>Suç türü</label><select name="sucTuru">${Object.entries(H.INFAZ_TURLER || {}).map(([k, v]) => `<option value="${k}">${esc(v.ad)}</option>`).join('')}</select></div>
        <div><label>Ceza türü</label><select name="cezaTipi"><option value="sureli">Süreli hapis</option><option value="muebbet">Müebbet</option><option value="agir">Ağırlaştırılmış müebbet</option></select></div>
        <div><label>Yıl</label><input name="yil" type="number" min="0" value="3"></div>
        <div><label>Ay</label><input name="ay" type="number" min="0" value="0"></div>
        <div><label>Gün</label><input name="gun" type="number" min="0" value="0"></div>
        <div><label>Tutukluluk / gözaltı (gün)</label><input name="mahsupGun" type="number" min="0" value="0"></div>
        <div><label>Tekerrür</label><select name="mukerrir"><option value="0">Mükerrir değil</option><option value="1">Mükerrir (1. kez)</option><option value="2">İkinci kez mükerrir</option></select></div>
        <div><label>Suç tarihinde yaş</label><select name="yas"><option value="18ustu">18 ve üstü</option><option value="15-18">15-18</option><option value="15alti">15'ten küçük</option></select></div>
        <div><label>İnfaza başlama (teslim) tarihi — isteğe bağlı</label><input type="date" name="baslangic"></div>
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
      const r = H[{ vekalet: 'vekalet', faiz: 'faiz', harc: 'harc', smm: 'smm', cmk: 'cmkMakbuz', infaz: H.infazDetay ? 'infazDetay' : 'infaz', ceza: 'ceza' }[hesapTur]](f);
      if (r.hata) { kutu.innerHTML = `<p class="ca-soluk">${esc(r.hata)}</p>`; return; }
      if (hesapTur === 'infaz' && r.gorsel) {
        // Görsel: hükmedilen cezanın tamamı tek çubukta — mahsup, cezaevi, denetimli serbestlik, koşullu salıverilme sonrası
        const g = r.gorsel, T = Math.max(1, g.toplam), yuz = n => Math.max(0, n / T * 100);
        const parca = (n, renk, ad) => n > 0 ? `<div title="${ad}: ${n} gün" style="width:${yuz(n)}%;background:${renk};height:100%;display:flex;align-items:center;justify-content:center;color:#fff;font-size:11px;overflow:hidden;white-space:nowrap">${yuz(n) > 9 ? ad : ''}</div>` : '';
        const cubuk = `<div style="display:flex;height:34px;border-radius:8px;overflow:hidden;border:1px solid var(--ce-border,#e2e8f0);margin:8px 0">
            ${parca(g.mahsup, '#64748b', 'Mahsup')}${parca(g.cezaevi, '#b91c1c', 'Cezaevi')}${parca(g.ds, '#d97706', 'Denetimli serbestlik')}${parca(g.sonrasi, '#16a34a', 'Koşullu salıverilme sonrası')}</div>
          <div style="display:flex;gap:12px;flex-wrap:wrap;font-size:12px">${[['#64748b', 'Mahsup', g.mahsup], ['#b91c1c', 'Cezaevi', g.cezaevi], ['#d97706', 'Denetimli serbestlik', g.ds], ['#16a34a', 'Koşullu salıverilme sonrası (denetim)', g.sonrasi]].map(([c, a, n]) => `<span><span style="display:inline-block;width:10px;height:10px;background:${c};border-radius:2px"></span> ${a}: <b>${n}</b> gün</span>`).join('')}</div>`;
        const kanun = `<div style="margin-top:10px"><b>Suç tarihine göre uygulanan düzenlemeler</b>
          <div style="position:relative;margin:10px 0 4px;padding-left:18px;border-left:3px solid #c8a45a">${(r.kanunlar || []).map(k => `
            <div style="margin-bottom:8px;opacity:${k.uygulanir ? 1 : .55}"><span style="position:absolute;left:-8px;width:13px;height:13px;border-radius:50%;background:${k.uygulanir ? '#16a34a' : '#cbd5e1'};margin-top:4px"></span>
              <b>${esc(k.tarih.split('-').reverse().join('.'))} · ${esc(k.ad)}</b> ${k.uygulanir ? '<span style="color:#166534;font-size:12px">✓ bu suça etkili</span>' : '<span class="ca-soluk" style="font-size:12px">etkisiz</span>'}<div class="ca-soluk" style="font-size:12.5px">${esc(k.ozet)}</div></div>`).join('')}</div></div>`;
        const ger = (r.gerekce || []).map(x => `<div style="font-size:13px">• ${esc(x)}</div>`).join('');
        const uy = (r.uyarilar || []).map(x => `<div class="ca-uyari">⚠️ ${esc(x)}</div>`).join('');
        kutu.innerHTML = `<div class="ca-kart">${uy}${cubuk}<table style="margin-top:8px">${r.metinSatirlar.map(x => `<tr${x.vurgu ? ' style="font-weight:700"' : ''}><td>${esc(x.ad)}${x.ref ? `<div class="ca-soluk">${esc(x.ref)}</div>` : ''}</td><td style="text-align:right;white-space:nowrap">${x.vurgu ? '<span class="ca-hedef" style="font-size:16px">' : ''}${esc(x.deger)}${x.vurgu ? '</span>' : ''}</td></tr>`).join('')}</table>
          ${ger ? `<div style="margin-top:8px"><b>Gerekçe</b>${ger}</div>` : ''}${kanun}
          <p class="ca-soluk">${esc(r.not)}</p><button class="ca-btn" type="button" id="ca-hesap-ekle">📝 Belgeye ekle</button></div>`;
        kutu.querySelector('#ca-hesap-ekle').onclick = () => {
          const metin = r.metinSatirlar.map(x => `${x.ad}: ${x.deger}${x.ref ? ' (' + x.ref + ')' : ''}`).join('\n');
          try { document.execCommand('insertText', false, metin); } catch (e) { navigator.clipboard && navigator.clipboard.writeText(metin); }
          kapat();
        };
        return;
      }
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

  // =========================================================================
  // 5. PENCERELER: evrak önizleme ve "Dosya Görüntüle" — açık çalışmanızı kapatmadan üstte açılır
  // =========================================================================
  // Her pencere asistan panelinin üstünde ayrı, sürüklenebilir bir katmandır; altındaki sekme (arama sonuçları,
  // ajanda, liste) olduğu gibi kalır. Birden çok pencere üst üste açılabilir; Esc en üsttekini kapatır.
  const PENCERE_CSS = `
  .cw-pencere{position:fixed;z-index:100010;display:flex;flex-direction:column;background:var(--ce-surface,#fff);color:var(--ce-text,#1f2937);
    border-radius:12px;box-shadow:0 24px 60px rgba(0,0,0,.35);border:1px solid var(--ce-border,#e2e6ec);overflow:hidden;
    width:min(1100px,calc(100vw - 24px));height:min(88vh,calc(100vh - 24px));font:14px/1.5 var(--ce-font-ui,system-ui,sans-serif)}
  .cw-pencere.tam{inset:8px!important;width:auto!important;height:auto!important}
  .cw-bas{display:flex;align-items:center;gap:8px;padding:8px 12px;background:#0f2341;color:#fff;cursor:move;user-select:none;flex-shrink:0}
  .cw-bas b{flex:1;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .cw-bas button{border:0;background:rgba(255,255,255,.12);color:#fff;border-radius:6px;padding:3px 9px;cursor:pointer;font:inherit}
  .cw-govde{flex:1;min-height:0;overflow:auto;padding:12px 14px}
  .cw-arac{display:flex;gap:6px;flex-wrap:wrap;align-items:center;padding:8px 12px;border-bottom:1px solid var(--ce-border,#e2e6ec);flex-shrink:0}
  .cw-arac .ca-btn{margin:0}
  .cw-sayfa{display:block;margin:0 auto 12px;max-width:100%;box-shadow:0 2px 10px rgba(0,0,0,.18);background:#fff}
  .cw-udf{background:#fff;color:#111;max-width:820px;margin:0 auto;padding:48px 56px;box-shadow:0 2px 10px rgba(0,0,0,.18);font-family:'Times New Roman',serif;font-size:15px}
  .cw-sekmeler{display:flex;gap:2px;padding:0 10px;border-bottom:1px solid var(--ce-border,#e2e6ec);overflow-x:auto;flex-shrink:0}
  .cw-sekmeler button{border:0;background:none;padding:9px 12px;cursor:pointer;color:var(--ce-muted,#64748b);border-bottom:2px solid transparent;font:inherit;white-space:nowrap}
  .cw-sekmeler button.secili{color:#0f2341;border-bottom-color:#c8a45a;font-weight:600}
  .cw-izgara{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin-bottom:10px}
  .cw-izgara div{border:1px solid var(--ce-border,#e2e6ec);border-radius:10px;padding:8px 10px}
  .cw-izgara b{display:block;font-size:17px}.cw-izgara span{font-size:12px;color:var(--ce-muted,#64748b)}
  .cw-tablo{width:100%;border-collapse:collapse;font-size:13px}
  .cw-tablo th,.cw-tablo td{padding:6px 8px;border-bottom:1px solid var(--ce-border,#eef0f3);text-align:left;vertical-align:top}
  .cw-tablo tr:hover td{background:rgba(200,164,90,.07)}
  .cw-mini{border:1px solid var(--ce-border,#d0d5dd);background:var(--ce-surface,#fff);border-radius:6px;padding:2px 7px;cursor:pointer;font-size:12px;margin:1px;color:inherit}
  .cw-mini.ana{background:#0f2341;color:#fff;border-color:#0f2341}
  .cw-cip{display:inline-block;font-size:11.5px;padding:1px 8px;border-radius:999px;font-weight:600;white-space:nowrap}
  .cw-cip.yesil{background:#dcfce7;color:#166534}.cw-cip.sari{background:#fef9c3;color:#854d0e}.cw-cip.turuncu{background:#ffedd5;color:#9a3412}
  .cw-cip.kirmizi{background:#fee2e2;color:#991b1b}.cw-cip.mavi{background:#dbeafe;color:#1e40af}.cw-cip.gri{background:#f1f5f9;color:#475569}
  .cw-kart{border:1px solid var(--ce-border,#e2e6ec);border-radius:10px;padding:10px 12px;margin-bottom:10px}
  `;
  let cwZ = 100010, cwSayi = 0;
  const cwListe = [];
  function pencereAc(baslik) {
    if (!document.getElementById('cw-stil')) { const st = document.createElement('style'); st.id = 'cw-stil'; st.textContent = PENCERE_CSS; document.head.appendChild(st); }
    const kok = document.getElementById('ca-panel') || document.body;
    const p = document.createElement('div');
    p.className = 'cw-pencere';
    const kay = (cwSayi++ % 6) * 22;
    p.style.left = `calc(50vw - min(550px, 50vw - 12px) + ${kay}px)`;
    p.style.top = `calc(6vh + ${kay}px)`;
    p.style.zIndex = ++cwZ;
    p.innerHTML = `<div class="cw-bas"><b></b><button type="button" data-cw="tam" title="Tam ekran">⤢</button><button type="button" data-cw="kapat" title="Kapat (Esc)">✕</button></div><div class="cw-ic" style="display:flex;flex-direction:column;flex:1;min-height:0"></div>`;
    p.querySelector('.cw-bas b').textContent = baslik;
    kok.appendChild(p);
    cwListe.push(p);
    const kapatP = () => { p.remove(); const i = cwListe.indexOf(p); if (i >= 0) cwListe.splice(i, 1); (p._temizle || []).forEach(f => { try { f(); } catch (e) { /* */ } }); };
    p.querySelector('[data-cw="kapat"]').onclick = kapatP;
    p.querySelector('[data-cw="tam"]').onclick = () => p.classList.toggle('tam');
    p.addEventListener('mousedown', () => { p.style.zIndex = ++cwZ; });
    const bas = p.querySelector('.cw-bas');
    bas.addEventListener('pointerdown', e => {
      if (e.target.closest('button') || p.classList.contains('tam')) return;
      const r = p.getBoundingClientRect(), dx = e.clientX - r.left, dy = e.clientY - r.top;
      const tasi = ev => { p.style.left = Math.max(0, Math.min(innerWidth - 80, ev.clientX - dx)) + 'px'; p.style.top = Math.max(0, Math.min(innerHeight - 40, ev.clientY - dy)) + 'px'; };
      const birak = () => { removeEventListener('pointermove', tasi); removeEventListener('pointerup', birak); };
      addEventListener('pointermove', tasi); addEventListener('pointerup', birak);
    });
    if (innerWidth < 700) p.classList.add('tam');
    return { el: p, ic: p.querySelector('.cw-ic'), kapat: kapatP, baslik: t => { p.querySelector('.cw-bas b').textContent = t; } };
  }
  if (typeof document !== 'undefined') document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && cwListe.length) { e.stopPropagation(); e.preventDefault(); cwListe[cwListe.length - 1].querySelector('[data-cw="kapat"]').click(); }
  }, true);

  const evrakAdi = r => {
    const cd = r.headers.get('Content-Disposition') || '';
    return decodeURIComponent((cd.match(/filename\*=UTF-8''([^;]+)/) || [])[1] || 'Evrak');
  };
  const sihir = u8 => (u8[0] === 0x25 && u8[1] === 0x50) ? 'pdf' : ((u8[0] === 0x49 && u8[1] === 0x49) || (u8[0] === 0x4D && u8[1] === 0x4D)) ? 'tiff'
    : (u8[0] === 0x50 && u8[1] === 0x4B) ? 'udf' : (u8[0] === 0xFF && u8[1] === 0xD8) ? 'jpg' : (u8[0] === 0x89 && u8[1] === 0x50) ? 'png' : 'diger';

  /** Bayt dizisini pencere içinde çizer: PDF (pdf.js, sayfalar tembel), TIFF (UTIF), UDF (editörün kendi ayrıştırıcısı). */
  async function bicimCiz(kap, buf, ad) {
    const u8 = new Uint8Array(buf);
    const tur = sihir(u8);
    kap.innerHTML = '';
    if (tur === 'pdf') {
      const lib = window.pdfjsLib || window['pdfjs-dist/build/pdf'];
      if (!lib) throw new Error('PDF görüntüleyici yüklenemedi');
      if (lib.GlobalWorkerOptions && !lib.GlobalWorkerOptions.workerSrc) lib.GlobalWorkerOptions.workerSrc = 'pdf.worker.min.js';
      const pdf = await lib.getDocument({ data: u8.slice() }).promise;
      const bilgi = document.createElement('div'); bilgi.className = 'ca-soluk'; bilgi.style.marginBottom = '6px';
      bilgi.textContent = `${pdf.numPages} sayfa · PDF`; kap.appendChild(bilgi);
      const genis = Math.min(kap.clientWidth - 8 || 800, 1000);
      const yuvalar = [];
      for (let i = 1; i <= pdf.numPages; i++) {
        const c = document.createElement('canvas'); c.className = 'cw-sayfa'; c.dataset.s = i; c.style.width = genis + 'px'; c.style.height = Math.round(genis * 1.414) + 'px';
        kap.appendChild(c); yuvalar.push(c);
      }
      const ciz = async c => {
        if (c.dataset.cizildi) return; c.dataset.cizildi = '1';
        const sayfa = await pdf.getPage(+c.dataset.s);
        const v1 = sayfa.getViewport({ scale: 1 }), olcek = genis / v1.width * (window.devicePixelRatio || 1);
        const vp = sayfa.getViewport({ scale: olcek });
        c.width = vp.width; c.height = vp.height; c.style.height = Math.round(vp.height / (window.devicePixelRatio || 1)) + 'px';
        await sayfa.render({ canvasContext: c.getContext('2d'), viewport: vp }).promise;
      };
      if ('IntersectionObserver' in window) {
        const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) ciz(e.target); }), { root: kap.closest('.cw-govde'), rootMargin: '600px' });
        yuvalar.forEach(c => io.observe(c));
      } else { for (const c of yuvalar.slice(0, 8)) await ciz(c); }
      return 'pdf';
    }
    if (tur === 'tiff') {
      if (!window.UTIF) throw new Error('TIFF görüntüleyici yüklenemedi');
      const ifds = UTIF.decode(buf);
      const bilgi = document.createElement('div'); bilgi.className = 'ca-soluk'; bilgi.textContent = `${ifds.length} sayfa · TIFF (orijinal)`; kap.appendChild(bilgi);
      for (const ifd of ifds) {
        UTIF.decodeImage(buf, ifd);
        const rgba = UTIF.toRGBA8(ifd);
        const c = document.createElement('canvas'); c.className = 'cw-sayfa'; c.width = ifd.width; c.height = ifd.height; c.style.width = Math.min(ifd.width, 1000) + 'px';
        c.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(rgba.buffer), ifd.width, ifd.height), 0, 0);
        kap.appendChild(c);
      }
      return 'tiff';
    }
    if (tur === 'udf' && typeof window.parseUdfArrayBuffer === 'function') {
      const onceki = window.__udfSource;   // editörde açık belgenin UDF kaynağı bozulmasın
      let r;
      try { r = await window.parseUdfArrayBuffer(buf.slice(0)); } finally { window.__udfSource = onceki; }
      const d = document.createElement('div'); d.className = 'cw-udf'; d.innerHTML = (r && r.html) || '<p>(boş belge)</p>';
      const bilgi = document.createElement('div'); bilgi.className = 'ca-soluk'; bilgi.style.marginBottom = '6px'; bilgi.textContent = 'UDF (orijinal)' + (r && r.signature && r.signature.hasSignature ? ' · e-imzalı' : '');
      kap.appendChild(bilgi); kap.appendChild(d);
      return 'udf';
    }
    if (tur === 'jpg' || tur === 'png') {
      const img = document.createElement('img'); img.className = 'cw-sayfa'; img.src = URL.createObjectURL(new Blob([buf])); kap.appendChild(img);
      return tur;
    }
    kap.innerHTML = `<div class="cw-kart">Bu biçim (${esc(ad)}) burada önizlenemiyor. İndirip açabilirsiniz.</div>`;
    return 'diger';
  }

  /** İndirmeden önizleme: önce PDF'e çevrilmiş hali; "Orijinali göster" UDF/TIFF'i olduğu gibi (önbelleğe alınır). */
  function evrakOnizle(skey, baslik, bicim) {
    const w = pencereAc('👁 ' + (baslik || 'Evrak önizleme'));
    w.ic.innerHTML = `<div class="cw-arac">
        <button class="ca-btn ana kucuk" type="button" data-b="pdf">📄 PDF önizleme</button>
        <button class="ca-btn kucuk" type="button" data-b="orijinal">🗂️ Orijinali göster (UDF/TIFF)</button>
        <button class="ca-btn kucuk" type="button" data-b="indir">⬇ İndir</button>
        <button class="ca-btn kucuk" type="button" data-b="editor">✏️ Editörde aç</button>
        <span class="ca-soluk cw-durum" style="margin-left:auto"></span></div>
      <div class="cw-govde"><div class="cw-alan"><p class="ca-soluk">Hazırlanıyor… (yerelde yoksa UYAP'tan önbelleğe alınıyor)</p></div></div>`;
    const alan = w.ic.querySelector('.cw-alan'), durum = w.ic.querySelector('.cw-durum');
    let son = null;
    const yukle = async b => {
      w.ic.querySelectorAll('[data-b="pdf"],[data-b="orijinal"]').forEach(x => x.classList.toggle('ana', x.dataset.b === b));
      alan.innerHTML = `<p class="ca-soluk">${b === 'pdf' ? 'PDF hazırlanıyor…' : 'Orijinal alınıyor…'} (yerelde yoksa UYAP'tan önbelleğe alınır, ilk açılış birkaç saniye sürebilir)</p>`;
      const t0 = Date.now();
      try {
        const r = await api(`/api/evrak/onizle?skey=${encodeURIComponent(skey)}&bicim=${b}`, { ham: true });
        const buf = await r.arrayBuffer();
        son = { buf, ad: evrakAdi(r) };
        const tur = await bicimCiz(alan, buf, son.ad);
        durum.textContent = `${tur.toUpperCase()} · ${(buf.byteLength / 1024).toFixed(0)} KB · ${((Date.now() - t0) / 1000).toFixed(1)} sn`;
      } catch (e) {
        alan.innerHTML = `<div class="cw-kart ca-hata">Önizleme alınamadı: ${esc(e.message)}</div>`;
      }
    };
    w.ic.querySelector('[data-b="pdf"]').onclick = () => yukle('pdf');
    w.ic.querySelector('[data-b="orijinal"]').onclick = () => yukle('orijinal');
    w.ic.querySelector('[data-b="indir"]').onclick = async () => {
      try {
        if (!son) { const r = await api(`/api/evrak/onizle?skey=${encodeURIComponent(skey)}&bicim=orijinal`, { ham: true }); son = { buf: await r.arrayBuffer(), ad: evrakAdi(r) }; }
        if (window.saveBytesSmart) await window.saveBytesSmart(new Uint8Array(son.buf), son.ad, 'application/octet-stream');
        else { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([son.buf])); a.download = son.ad; a.click(); }
      } catch (e) { alert('İndirilemedi: ' + e.message); }
    };
    w.ic.querySelector('[data-b="editor"]').onclick = async () => {
      try {
        const r = await api(`/api/evrak/onizle?skey=${encodeURIComponent(skey)}&bicim=orijinal`, { ham: true });
        const buf = await r.arrayBuffer();
        kapat();
        if (window.openDocumentFromBytes) await window.openDocumentFromBytes(buf, evrakAdi(r));
      } catch (e) { alert('Açılamadı: ' + e.message); }
    };
    yukle(bicim || 'pdf');
    return w;
  }

  const TLc = n => (n === null || n === undefined || n === '') ? '—' : '₺' + Number(n || 0).toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const trT = s => { const m = String(s || '').match(/(\d{4})-(\d{2})-(\d{2})/); return m ? `${m[3]}.${m[2]}.${m[1]}` : String(s || '').slice(0, 10); };
  const KES_CIP = { kesin: ['yesil', 'Kesinleşmiş'], kesinlestirilebilir: ['turuncu', 'Kesinleştirilebilir'], sure_isliyor: ['mavi', 'Süre işliyor'],
    itiraz: ['kirmizi', 'İtiraz'], teblig_bekleniyor: ['sari', 'Tebliğ bekleniyor'], bilinmiyor: ['gri', 'Bilinmiyor'] };
  const TK_CIP = { kirmizi: 'kirmizi', turuncu: 'turuncu', sari: 'sari', yesil: 'yesil', kapali: 'gri', bilinmiyor: 'gri' };

  /** Evrak satırı düğmeleri (önizle / orijinal / indir / Drive) — tüm listelerde aynı. */
  function evrakDugme(e, driveUrl) {
    return `<span style="white-space:nowrap">
      <button class="cw-mini ana" type="button" data-onizle="${esc(e.skey)}" data-ad="${esc(e.tur || 'Evrak')}">👁 Önizle</button>
      <button class="cw-mini" type="button" data-orijinal="${esc(e.skey)}" data-ad="${esc(e.tur || 'Evrak')}">🗂️ Orijinal</button>
      ${e.yerel ? '' : `<button class="cw-mini" type="button" data-hemen="${esc(e.skey)}" title="Sıra beklemeden şimdi indir ve Drive'a eşitle">⚡ İndir</button>`}
      ${driveUrl ? `<a class="cw-mini" href="${esc(driveUrl)}" target="_blank" rel="noopener" title="Drive'da aç">☁️ Drive</a>` : ''}
      </span>`;
  }
  // v4.9.3: tek tek ya da seçerek "indir" denen evraklar öncelik kuyruğuna girer; Senkron o an ne yapıyorsa
  // bırakıp önce bunları indirir ve Drive'a eşitler. Düğme ilerlemeyi gösterir.
  async function hemenIndir(skeys, btn) {
    if (!skeys.length) return;
    const eski = btn ? btn.textContent : '';
    if (btn) { btn.disabled = true; btn.textContent = '⚡ Sırada…'; }
    try {
      const r = await api('/api/evrak/toplu_islem', { method: 'POST', govde: { eylem: 'indir', skeys } });
      if (window.showToast) window.showToast(r.mesaj || 'Öncelikle indiriliyor');
      const bas = Date.now();
      const zam = setInterval(async () => {
        if ((btn && !document.body.contains(btn)) || Date.now() - bas > 30 * 60000) return clearInterval(zam);
        try {
          const d = await api('/api/oncelik/durum?skeyler=' + encodeURIComponent(skeys.slice(0, 300).join(',')));
          if (btn) btn.textContent = d.kalan ? `⚡ ${d.inen}/${d.toplam}` : (d.hata && !d.inen ? '⚠️ Alınamadı' : '✅ İndi');
          if (!d.kalan && !d.sirada) { clearInterval(zam); if (window.showToast) window.showToast(`✅ ${d.inen} evrak indi ve Drive'a eşitlendi`); }
        } catch (e) { /* anlık kopma */ }
      }, 2500);
    } catch (e) { if (btn) { btn.disabled = false; btn.textContent = eski; } alert(e.message); }
  }

  function evrakDugmeBagla(kap) {
    kap.addEventListener('click', e => {
      const b = e.target.closest('[data-onizle],[data-orijinal],[data-dosya-ac],[data-hemen]');
      if (!b) return;
      if (b.dataset.hemen) { hemenIndir([b.dataset.hemen], b); return; }
      if (b.dataset.onizle) evrakOnizle(b.dataset.onizle, b.dataset.ad, 'pdf');
      else if (b.dataset.orijinal) evrakOnizle(b.dataset.orijinal, b.dataset.ad, 'orijinal');
      else if (b.dataset.dosyaAc) dosyaPenceresi(b.dataset.dosyaAc);
    });
  }

  /** DOSYA GÖRÜNTÜLE: Notion sayfası gibi tek pencerede her şey — konu, taraflar, hesap, tahsilat/reddiyat,
   *  safahat, tüm evraklar (aranır/süzülür, önizlenir), duruşma/tebligat, Drive eşitleme, icra analizi, notlar. */
  async function dosyaPenceresi(dkey, ipucu) {
    const w = pencereAc('📂 ' + (ipucu || 'Dosya'));
    w.ic.innerHTML = '<div class="cw-govde"><p class="ca-soluk">Dosya yükleniyor…</p></div>';
    let v;
    try { v = await api('/api/dosya/detay?dkey=' + encodeURIComponent(dkey)); }
    catch (e) { w.ic.innerHTML = `<div class="cw-govde"><div class="cw-kart ca-hata">${esc(e.message)}</div></div>`; return w; }
    const d = v.dosya || {}, h = v.hesap || {}, ev = v.evraklar || [], defter = v.drive_defter || {};
    w.baslik(`📂 ${d.birim || ''} · ${d.dosya_no || ''}`);
    const drivede = ev.filter(e => defter[String(e.id)]).length;
    const indirilen = ev.filter(e => e.yerel).length;
    const sekmeler = [['genel', '📌 Genel'], ['evrak', `📄 Evraklar (${ev.length})`], ['hesap', '💰 Hesap'], ['safahat', `🧭 Safahat (${(v.safahat || []).length})`],
      ['taraf', `👥 Taraflar (${(v.taraf_listesi || []).length})`], ['durusma', '📅 Duruşma & Tebligat'], ['drive', `☁️ Drive (${drivede}/${ev.length})`], ['not', '📝 Notlar']];
    const eksik = v.eksik || {};
    const eksikMetin = [eksik.taraf && 'taraflar', eksik.evrak && 'evrak listesi', eksik.hesap && 'hesap'].filter(Boolean).join(', ');
    w.ic.innerHTML = `<div class="cw-eylem" style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:8px 10px;border-bottom:1px solid #e5e7eb">
        <button class="ca-btn kucuk" type="button" id="cw-tazele">🔄 UYAP'tan şimdi getir</button>
        <button class="ca-btn kucuk ana" type="button" id="cw-drive-indir" title="Senkron o an ne yapıyorsa bırakır, önce bu dosyanın evraklarını indirip Drive'a eşitler">⚡ Hemen indir + Drive'a eşitle${v.indirilmemis ? ` (${v.indirilmemis})` : ''}</button>
        <span class="ca-soluk" id="cw-tazele-d" style="flex:1;min-width:160px">${eksikMetin ? '⚠️ Eksik: ' + esc(eksikMetin) : ''}</span></div>
      <div class="cw-sekmeler">${sekmeler.map(([k, a], i) => `<button type="button" data-s="${k}" class="${i ? '' : 'secili'}">${a}</button>`).join('')}</div><div class="cw-govde"></div>`;
    const govde = w.ic.querySelector('.cw-govde');
    // Taraf / evrak listesi / hesap eksikse dosya açılınca UYAP'tan kendiliğinden getirilir (gizli oturumla)
    const tzD = w.ic.querySelector('#cw-tazele-d'), tzB = w.ic.querySelector('#cw-tazele');
    let tzZam = null;
    const tazeleIzle = () => {
      clearInterval(tzZam);
      tzB.disabled = true;
      tzZam = setInterval(async () => {
        if (!document.body.contains(w.ic)) return clearInterval(tzZam);
        try {
          const t = await api('/api/dosya/tazele?dkey=' + encodeURIComponent(dkey));
          if (t.calisiyor) { tzD.textContent = '⏳ ' + (t.mesaj || 'UYAP\'tan alınıyor…'); return; }
          clearInterval(tzZam); tzB.disabled = false;
          if (t.hata) { tzD.innerHTML = `<span class="ca-hata">${esc(t.hata)}</span>`; return; }
          const r = t.sonuc || {};
          tzD.textContent = `✓ ${r.taraf || 0} taraf, ${r.evrak || 0} evrak${r.hesap ? ', hesap' : ''}${r.safahat ? ', safahat' : ''} alındı`;
          setTimeout(() => { w.kapat(); dosyaPenceresi(dkey, ipucu); }, 900);
        } catch (e) { /* bağlantı anlık kopabilir */ }
      }, 2000);
    };
    const tazeleBaslat = async () => {
      try { await api('/api/dosya/tazele', { method: 'POST', govde: { dkey } }); tzD.textContent = '⏳ UYAP\'a bağlanılıyor…'; tazeleIzle(); }
      catch (e) { tzD.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
    };
    tzB.onclick = tazeleBaslat;
    if ((v.tazele || {}).calisiyor) tazeleIzle();
    else if (eksikMetin && !(v.tazele || {}).hata && !(v.tazele || {}).bitis) tazeleBaslat();
    // v4.9.3 ÖNCELİKLİ İNDİRME: Senkron o an ne yapıyorsa bırakır (1-2 sn içinde), önce bu dosyanın evrakını
    // indirip PDF'e çevirir ve Drive'a eşitler. İlerleme burada canlı görünür.
    const dib = w.ic.querySelector('#cw-drive-indir');
    let oncZam = null;
    const oncelikIzle = () => {
      clearInterval(oncZam);
      const tur = async () => {
        if (!document.body.contains(w.ic)) return clearInterval(oncZam);
        try {
          const d = await api('/api/oncelik/durum?dkey=' + encodeURIComponent(dkey));
          const yuzde = d.toplam ? Math.round(d.inen * 100 / d.toplam) : 0;
          tzD.innerHTML = d.tarama !== 'tamam' && d.sirada && !d.toplam ? '⚡ Öncelikli: önce UYAP\'tan evrak listesi alınıyor…'
            : `⚡ <b>${d.inen}/${d.toplam}</b> evrak indi (%${yuzde})${d.drive ? ` · ☁️ ${d.drive} Drive'a yüklendi` : ''}${d.kalan ? ` · ${d.kalan} kaldı` : ''}${d.hata ? ` · ${d.hata} alınamadı` : ''}`
              + (d.son ? `<div class="ca-soluk" style="font-size:11.5px">${esc(d.son)}</div>` : '')
              + (!d.senkron_calisiyor && d.kalan ? '<div class="ca-hata">Senkron çalışmıyor; Ana Ekran\'dan başlatın.</div>' : '');
          if (!d.sirada && !d.kalan) { clearInterval(oncZam); dib.disabled = false; tzD.innerHTML = `✅ Hepsi indi: ${d.inen}/${d.toplam} evrak${d.hata ? ` (${d.hata} tanesi UYAP'tan alınamadı)` : ''}. Drive'a eşitlendi.`; }
        } catch (e) { /* bağlantı anlık kopabilir */ }
      };
      tur(); oncZam = setInterval(tur, 2000);
    };
    dib.onclick = async () => {
      dib.disabled = true;
      try {
        const r = await api('/api/dosya/drive_indir', { method: 'POST', govde: { dkey } });
        tzD.textContent = `⚡ Öncelikle indiriliyor${r.senkron_acildi ? ' (Senkron başlatıldı, oturum açılıyor…)' : '…'}`;
        oncelikIzle();
      } catch (er) { tzD.innerHTML = `<span class="ca-hata">${esc(er.message)}</span>`; dib.disabled = false; }
    };
    api('/api/oncelik/durum?dkey=' + encodeURIComponent(dkey)).then(d => { if (d.sirada) { dib.disabled = true; oncelikIzle(); } }).catch(() => {});
    evrakDugmeBagla(govde);
    const ia = v.icra;
    const genel = () => `
      <div class="cw-izgara">
        <div><span>Durum</span><b>${esc(d.durum || '—')}</b></div>
        <div><span>Açılış</span><b>${esc(trT(d.acilis))}</b></div>
        <div><span>Evrak</span><b>${ev.length}</b><span>${indirilen} indirildi · ${drivede} Drive'da</span></div>
        <div><span>${h.is_icra ? 'Kalan bakiye' : 'Artan avans'}</span><b>${h.cekildi ? TLc(h.is_icra ? h.kalan_borc : h.artan_avans) : '—'}</b><span>${h.cekildi ? 'UYAP: ' + esc((h.son_guncelleme || '').slice(0, 16)) : 'hesap çekilmedi'}</span></div>
      </div>
      ${v.konu && v.konu.metin ? `<div class="cw-kart"><b>📌 Dosya konusu</b> <span class="ca-soluk">(${esc(v.konu.kaynak || '')})</span>${v.konu.url ? ` · <a href="${esc(v.konu.url)}" target="_blank" rel="noopener">Notion sayfası</a>` : ''}<div style="margin-top:4px;line-height:1.5">${esc(v.konu.metin)}</div></div>` : ''}
      ${ia ? `<div class="cw-kart"><b>⚖️ İcra takibi</b> <span class="cw-cip ${KES_CIP[ia.kesinlesme.durum][0]}">${KES_CIP[ia.kesinlesme.durum][1]}</span>
          <span class="cw-cip ${TK_CIP[ia.takipsizlik.seviye] || 'gri'}">${ia.takipsizlik.gun != null ? ia.takipsizlik.gun + ' gün işlemsiz' : 'işlem bilgisi yok'}</span>
          <div style="margin-top:6px"><b>${esc(ia.kesinlesme.baslik)}</b><div>${esc(ia.kesinlesme.aciklama || '')}</div></div>
          <div style="margin-top:6px" class="ca-soluk">${esc(ia.takipsizlik.aciklama || '')} · Takip türü: ${esc(ia.kesinlesme.takip_turu)} (itiraz süresi ${ia.kesinlesme.itiraz_suresi} gün)</div></div>` : ''}
      <div class="cw-kart"><b>Son evraklar</b><table class="cw-tablo">${ev.slice(0, 8).map(e => `<tr><td>${esc(trT(e.tarih))}</td><td><b>${esc(e.tur || '')}</b><div class="ca-soluk">${esc(e.aciklama || '')}</div></td><td>${evrakDugme(e, (defter[String(e.id)] || {}).url)}</td></tr>`).join('')}</table></div>`;
    const evrakSekme = () => {
      const katlar = [...new Set(ev.map(e => e.kategori).filter(Boolean))].sort();
      setTimeout(() => {
        const q = govde.querySelector('#cw-eq'), ks = govde.querySelector('#cw-ek'), ds = govde.querySelector('#cw-ed'), tb = govde.querySelector('#cw-et');
        const fold = s => String(s || '').toLocaleLowerCase('tr').replace(/[ıi̇]/g, 'i').replace(/ş/g, 's').replace(/ğ/g, 'g').replace(/ü/g, 'u').replace(/ö/g, 'o').replace(/ç/g, 'c');
        const ciz = () => {
          const t = fold(q.value.trim()).split(/\s+/).filter(Boolean);
          const l = ev.filter(e => (!ks.value || e.kategori === ks.value)
            && (!ds.value || (ds.value === 'indi' ? e.yerel : ds.value === 'indirilmedi' ? !e.yerel : ds.value === 'drive' ? defter[String(e.id)] : !defter[String(e.id)]))
            && t.every(x => fold(`${e.tur} ${e.aciklama} ${e.tarih} ${e.kategori}`).includes(x)));
          tb.innerHTML = `<tr><th>Tarih</th><th>Evrak</th><th>Durum</th><th></th></tr>` + l.slice(0, 1500).map(e => {
            const dr = defter[String(e.id)];
            return `<tr><td style="white-space:nowrap">${esc(trT(e.tarih))}</td><td>${e.is_ek ? '↳ ' : ''}<b>${esc(e.tur || '')}</b><div class="ca-soluk">${esc(e.aciklama || '')}${e.kategori ? ' · ' + esc(e.kategori) : ''}</div></td>
              <td>${e.yerel ? '<span class="cw-cip yesil">indirildi</span>' : '<span class="cw-cip gri">UYAP\'ta</span>'} ${dr ? '<span class="cw-cip mavi">☁ Drive</span>' : ''}</td><td>${evrakDugme(e, dr && dr.url)}</td></tr>`;
          }).join('') + (l.length > 1500 ? `<tr><td colspan="4" class="ca-soluk">… ${l.length - 1500} evrak daha (aramayı daraltın)</td></tr>` : '');
          govde.querySelector('#cw-esay').textContent = `${l.length} / ${ev.length} evrak`;
        };
        [q, ks, ds].forEach(x => x.addEventListener('input', ciz)); ciz();
      });
      return `<div style="display:grid;grid-template-columns:2fr 1fr 1fr;gap:8px;margin-bottom:8px">
        <input id="cw-eq" placeholder="Evraklarda ara (tür, açıklama, tarih)…"><select id="cw-ek"><option value="">Tüm kategoriler</option>${katlar.map(k => `<option>${esc(k)}</option>`).join('')}</select>
        <select id="cw-ed"><option value="">Tümü</option><option value="indi">İndirilmiş</option><option value="indirilmedi">İndirilmemiş</option><option value="drive">Drive'da</option><option value="drivesiz">Drive'da olmayan</option></select></div>
        <div class="ca-soluk" id="cw-esay"></div><table class="cw-tablo" id="cw-et"></table>`;
    };
    const kalemTablo = (l, bas) => !l.length ? `<p class="ca-soluk">${bas} kaydı yok.</p>` : `<table class="cw-tablo"><tr><th>Tarih</th><th>Tür / açıklama</th><th>Kişi</th><th style="text-align:right">Tutar</th></tr>${l.map(x => `<tr>
        <td>${esc(trT(x.tahsilatTarihi || x.reddiyatTarihi || x.tarih || x.islemTarihi || ''))}</td>
        <td>${esc(x.tahsilatTuru || x.reddiyatTuru || x.harcMasrafAdi || x.aciklama || x.turu || '')}</td>
        <td>${esc(x.odeyenAdi || x.alanAdi || x.adSoyad || x.kisiAdi || '')}</td>
        <td style="text-align:right;white-space:nowrap">${TLc(x.miktar ?? x.tutar ?? x.tahsilatTutari ?? x.reddiyatTutari)}</td></tr>`).join('')}</table>`;
    const hesapSekme = () => `
      <div class="cw-kart">${h.cekildi ? `<div class="cw-izgara">${(h.is_icra ? [['Asıl alacak', h.asil_alacak], ['Faiz', h.islemis_faiz], ['Vekâlet', h.vekalet_ucreti], ['Masraf+harç', h.masraf_harc], ['Toplam', h.toplam_borc], ['Tahsilat', h.tahsilat], ['Reddiyat', h.reddiyat], ['Kasada', h.kasada_bekleyen], ['Bakiye', h.kalan_borc]]
        : [['Yatırılan', h.tahsilat], ['Kullanılan', h.reddiyat], ['Harçlar', h.masraf_harc], ['Artan avans', h.artan_avans]]).map(([a, x]) => `<div><span>${a}</span><b>${TLc(x)}</b></div>`).join('')}</div>
        ${(h.harc_kalemleri || []).length ? `<b>Harç kalemleri</b><table class="cw-tablo">${h.harc_kalemleri.map(k => `<tr><td>${esc(k.ad)}</td><td style="text-align:right">${TLc(k.tutar)}</td></tr>`).join('')}</table>` : ''}`
        : '<p class="ca-soluk">Bu dosyanın hesabı henüz UYAP\'tan çekilmedi.</p>'}
        <button class="ca-btn kucuk" type="button" id="cw-hesap-yenile">🔄 UYAP'tan yenile</button> <span class="ca-soluk" id="cw-hesap-d"></span></div>
      <div class="cw-kart"><b>💵 Tahsilatlar</b>${kalemTablo(v.tahsilat || [], 'Tahsilat')}</div>
      <div class="cw-kart"><b>📤 Reddiyatlar</b>${kalemTablo(v.reddiyat || [], 'Reddiyat')}</div>`;
    const safahatSekme = () => (v.safahat || []).length ? `<input id="cw-sq" placeholder="Safahatta ara…" style="margin-bottom:8px"><table class="cw-tablo" id="cw-st">${(v.safahat || []).map(s => `<tr data-m="${esc((s.tur + ' ' + s.aciklama).toLocaleLowerCase('tr'))}"><td style="white-space:nowrap">${esc(s.tarih || '')}</td><td><b>${esc(s.tur || '')}</b><div class="ca-soluk">${esc(s.aciklama || '')}</div></td><td class="ca-soluk">${esc(s.birim || '')}</td></tr>`).join('')}</table>`
      : '<p class="ca-soluk">Safahat henüz çekilmedi (Senkron açıkken icra dosyalarında hesapla birlikte, diğerlerinde yeni evrakla gelir). "Hesap" sekmesinden "UYAP\'tan yenile" de safahatı çeker.</p>';
    const tarafSekme = () => `<table class="cw-tablo"><tr><th>Ad</th><th>Rol</th><th>Vekil</th></tr>${(v.taraf_listesi || []).map(t => `<tr><td>${t.muvekkil ? '<span class="cw-cip yesil">Müvekkil</span> ' : ''}<b>${esc(t.ad)}</b></td><td>${esc(t.rol)}</td><td class="ca-soluk">${esc(t.vekil)}</td></tr>`).join('')}</table>`;
    const durusmaSekme = () => `<div class="cw-kart"><b>📅 Duruşmalar</b>${(v.durusmalar || []).length ? `<table class="cw-tablo">${v.durusmalar.map(x => `<tr><td>${esc(trT(x.tarih))} ${esc(x.saat || '')}</td><td>${esc(x.yer || '')}</td><td>${esc(x.aciklama || '')}</td><td>${esc(x.durum || '')}</td></tr>`).join('')}</table>` : '<p class="ca-soluk">Kayıt yok.</p>'}</div>
      <div class="cw-kart"><b>📮 Tebligat süreçleri (UYAP)</b>${(v.tebligat_surecleri || []).length ? `<table class="cw-tablo"><tr><th>Tarih</th><th>Tebligat</th><th>Muhatap</th><th>Sonuç / tebliğ tarihi</th><th></th></tr>${v.tebligat_surecleri.map(x => `<tr>
          <td style="white-space:nowrap">${esc(trT(x.tarih))}</td><td><b>${esc(x.tur)}</b><div class="ca-soluk">${esc(x.evrak)}${x.barkod ? ' · ' + esc(x.barkod) : ''}</div></td>
          <td>${esc(x.muhatap)}${x.rol ? `<div class="ca-soluk">${esc(x.rol)}</div>` : ''}</td>
          <td>${x.sonuc ? `<span class="cw-cip ${/bila|iade|edilemedi/i.test(x.sonuc) ? 'kirmizi' : /tebli|bizzat|21|35|muhtar|vekil/i.test(x.sonuc) ? 'yesil' : 'gri'}">${esc(x.sonuc)}</span>` : ''}${x.teblig_tarihi ? `<div><b>${esc(x.teblig_tarihi)}</b></div>` : ''}${x.sure_notu ? `<div class="ca-soluk">${esc(x.sure_notu)}</div>` : ''}</td>
          <td>${x.skey ? `<button class="cw-mini" type="button" data-onizle="${esc(x.skey)}">👁</button>` : ''}</td></tr>`).join('')}</table>` : '<p class="ca-soluk">Bu dosyada tebligat evrakı yok ya da evrak listesi henüz alınmadı.</p>'}</div>
      <div class="cw-kart"><b>📨 Tebligatlar</b>${(v.tebligatlar || []).length ? `<table class="cw-tablo">${v.tebligatlar.map(x => `<tr><td>${esc(trT(x.eklenme))}</td><td>${esc(x.tebligat_turu || '')}</td><td>${esc(x.evrak_adi || '')}</td></tr>`).join('')}</table>` : '<p class="ca-soluk">Kayıt yok.</p>'}</div>
      ${ia ? `<div class="cw-kart"><b>🧭 İcra zaman çizelgesi</b><table class="cw-tablo">${(ia.zaman_cizelgesi || []).slice().reverse().map(o => `<tr><td>${esc(trT(o.tarih))}</td><td><span class="cw-cip gri">${esc(o.kaynak)}</span></td><td>${esc(o.metin)}</td></tr>`).join('')}</table></div>` : ''}`;
    const driveSekme = () => `<div class="cw-izgara"><div><span>Drive'a yüklenen</span><b>${drivede} / ${ev.length}</b></div><div><span>İndirilen</span><b>${indirilen}</b></div><div><span>Drive'daki dosyalar (esas no)</span><b>${(v.drive_dosyalar || []).length}</b></div></div>
      <div style="height:8px;border-radius:6px;background:#e5e7eb;overflow:hidden;margin-bottom:10px"><div style="height:100%;width:${ev.length ? Math.round(drivede / ev.length * 100) : 0}%;background:#16a34a"></div></div>
      <table class="cw-tablo">${(v.drive_dosyalar || []).map(f => `<tr><td>${esc(f.ad)}</td><td class="ca-soluk">${esc(f.klasor || '')}</td><td>${f.url ? `<a class="cw-mini" href="${esc(f.url)}" target="_blank" rel="noopener">☁️ Aç</a>` : ''}</td></tr>`).join('') || '<tr><td class="ca-soluk">Drive indeksinde bu esas numarasına ait dosya yok (Drive Ayarları → İndeksle).</td></tr>'}</table>`;
    const notSekme = () => `${(v.notlar || []).map(n => `<div class="cw-kart"><b>${esc(n.baslik)}</b> <span class="ca-soluk">${esc(n.zaman)}</span><div style="white-space:pre-wrap">${esc(n.metin)}</div></div>`).join('') || '<p class="ca-soluk">Not yok.</p>'}
      <input id="cw-nb" placeholder="Başlık" style="margin-top:8px"><textarea id="cw-nm" rows="4" style="width:100%;margin-top:6px;box-sizing:border-box" placeholder="Not"></textarea>
      <button class="ca-btn ana kucuk" type="button" id="cw-nk">💾 Notu kaydet</button>`;
    const SEK = { genel, evrak: evrakSekme, hesap: hesapSekme, safahat: safahatSekme, taraf: tarafSekme, durusma: durusmaSekme, drive: driveSekme, not: notSekme };
    const goster = k => {
      w.ic.querySelectorAll('.cw-sekmeler button').forEach(b => b.classList.toggle('secili', b.dataset.s === k));
      govde.innerHTML = SEK[k]();
      govde.scrollTop = 0;
      const hy = govde.querySelector('#cw-hesap-yenile');
      if (hy) hy.onclick = async () => {
        hy.disabled = true; govde.querySelector('#cw-hesap-d').textContent = 'UYAP\'tan çekiliyor…';
        try { await api('/api/dosya/hesap_yenile', { method: 'POST', govde: { dkey } }); w.kapat(); dosyaPenceresi(dkey, ipucu); }
        catch (e) { govde.querySelector('#cw-hesap-d').textContent = e.message; hy.disabled = false; }
      };
      const sq = govde.querySelector('#cw-sq');
      if (sq) sq.oninput = () => { const t = sq.value.toLocaleLowerCase('tr'); govde.querySelectorAll('#cw-st tr').forEach(tr => { tr.style.display = !t || tr.dataset.m.includes(t) ? '' : 'none'; }); };
      const nk = govde.querySelector('#cw-nk');
      if (nk) nk.onclick = async () => {
        const metin = govde.querySelector('#cw-nm').value.trim(); if (!metin) return;
        try { await api('/api/dosya/not', { method: 'POST', govde: { dkey, esas_no: d.dosya_no, birim: d.birim, baslik: govde.querySelector('#cw-nb').value.trim() || 'Dosya Notu', metin } });
          v.notlar = [{ baslik: govde.querySelector('#cw-nb').value.trim() || 'Dosya Notu', metin, zaman: new Date().toLocaleString('tr-TR') }, ...(v.notlar || [])]; goster('not'); }
        catch (e) { alert(e.message); }
      };
    };
    w.ic.querySelector('.cw-sekmeler').onclick = e => { const b = e.target.closest('[data-s]'); if (b) goster(b.dataset.s); };
    goster('genel');
    return w;
  }

  /** birim + esas no ile (ajanda, tebligat, yenilikler satırları) dosya penceresi. */
  async function dosyaPenceresiBul(birim, dosyaNo) {
    try {
      const r = await api(`/api/dosya/bul?birim=${encodeURIComponent(birim || '')}&dosya_no=${encodeURIComponent(dosyaNo || '')}`);
      if (r.dkey) return dosyaPenceresi(r.dkey, `${birim} · ${dosyaNo}`);
      alert('Bu dosya UYAP kataloğunda henüz yok (Senkron açıkken kataloğa eklenir).');
    } catch (e) { alert(e.message); }
  }
  window.CanPencere = { ac: pencereAc, evrakOnizle, dosya: dosyaPenceresi, dosyaBul: dosyaPenceresiBul, evrakDugme, evrakDugmeBagla };


  window.CanAsistan = { yenilikDenetle, ac, kapat, sureHesapla, uygulanacakGun, tatilUyarilari, a4Yerlesim, a4PdfOlustur, api };
  window.openHukukAsistani = ac;
  // ?asistan=1 (Android ana ekrandaki "Hukuk Asistanı" / ayrı başlatıcı simgesi): editör hiç gösterilmez
  try {
    if (/[?&]asistan=1\b/.test(location.search)) {
      document.documentElement.classList.add('ce-asistan-modu');
      const basla = () => {
        document.body.classList.add('ce-asistan-modu'); ac('ana');
        // Asistandan bir evrak açılırsa editöre geç (asistan modu biter, × artık uygulamayı kapatmaz)
        ['openDocumentFromBytes', 'openPdfViewer'].forEach(ad => {
          const asil = window[ad];
          if (typeof asil !== 'function') return;
          window[ad] = function () {
            document.body.classList.remove('ce-asistan-modu'); document.documentElement.classList.remove('ce-asistan-modu');
            if (kok) kok.classList.remove('acik');
            try { window.AndroidBridge && window.AndroidBridge.asistanModuBitti && window.AndroidBridge.asistanModuBitti(); } catch (e) {}
            return asil.apply(this, arguments);
          };
        });
      };
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', basla); else basla();
    }
  } catch (e) {}
})();
