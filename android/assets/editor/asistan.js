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

  /** Masaüstünde Tauri sunucuyu başlatır ve anahtarı verir; diğer platformlarda kayıtlı eşleştirme kullanılır. */
  async function baglantiHazirla() {
    const inv = tauriInvoke();
    if (inv) {
      try {
        const b = await inv('asistan_baglanti');
        if (b && b.anahtar) { baglantiYaz({ port: b.port, anahtar: b.anahtar }); return b; }
      } catch (e) { /* Python yoksa elle eşleştirmeye düş */ }
    }
    const b = baglantiOku();
    return { port: b.port || 8765, anahtar: b.anahtar || '' };
  }

  async function api(yol, secenek) {
    const b = await baglantiHazirla();
    secenek = secenek || {};
    const r = await fetch(`http://127.0.0.1:${b.port}${yol}`, {
      method: secenek.method || 'GET',
      headers: Object.assign({ 'X-Asistan-Anahtar': b.anahtar || '' }, secenek.govde ? { 'Content-Type': 'application/json' } : {}),
      body: secenek.govde ? JSON.stringify(secenek.govde) : undefined
    });
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
  #ca-panel header{display:flex;align-items:center;gap:8px;padding:12px 16px;border-bottom:1px solid var(--ce-border,#e2e6ec)}
  #ca-panel header h2{margin:0;font-size:16px;flex:1}
  #ca-panel .ca-kapat{border:0;background:none;font-size:20px;cursor:pointer;color:inherit;padding:2px 8px}
  #ca-panel nav{display:flex;gap:4px;padding:8px 12px 0;border-bottom:1px solid var(--ce-border,#e2e6ec);overflow-x:auto}
  #ca-panel nav button{border:0;background:none;padding:8px 12px;border-bottom:2px solid transparent;cursor:pointer;color:var(--ce-muted,#6b7280);font:inherit;white-space:nowrap}
  #ca-panel nav button.secili{color:var(--ce-accent,#2563eb);border-bottom-color:var(--ce-accent,#2563eb);font-weight:600}
  #ca-panel .ca-icerik{padding:16px;overflow:auto}
  #ca-panel input:not([type=checkbox]):not([type=range]),#ca-panel select{width:100%!important;height:auto!important;min-height:38px;line-height:1.4!important;padding:8px 10px!important;font-size:14px!important;margin:0!important}
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
  #ca-panel table{width:100%;border-collapse:collapse;font-size:13px}
  #ca-panel td,#ca-panel th{text-align:left;padding:6px 8px;border-bottom:1px solid var(--ce-border,#eef0f3);vertical-align:top}
  #ca-panel .ca-soluk{color:var(--ce-muted,#6b7280);font-size:12px}
  #ca-panel pre{background:var(--ce-bg,#f6f7f9);padding:8px;border-radius:8px;max-height:220px;overflow:auto;font-size:12px;white-space:pre-wrap}
  @media (max-width:600px){#ca-panel .ca-kutu{width:100vw;max-height:100vh;height:100vh;border-radius:0}}
  `;

  let kok = null, aktifSekme = 'sure';
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const SEKMELER = [
    ['sure', '⏱️ Süre Hesapla'], ['a4', '📄 A4 PDF'], ['ajanda', '📅 Ajanda'], ['evrak', '🗂️ UYAP Evrak'], ['gorev', '⚙️ Görevler'], ['baglanti', '🔌 Bağlantı']
  ];

  function panelKur() {
    if (kok) return;
    const st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st);
    kok = document.createElement('div'); kok.id = 'ca-panel';
    kok.innerHTML = `<div class="ca-kutu" role="dialog" aria-modal="true" aria-label="Hukuk Asistanı">
      <header><h2>⚖️ Hukuk Asistanı</h2><button class="ca-kapat" type="button" aria-label="Kapat">×</button></header>
      <nav>${SEKMELER.map(([k, ad]) => `<button type="button" data-sekme="${k}">${ad}</button>`).join('')}</nav>
      <div class="ca-icerik"></div></div>`;
    document.body.appendChild(kok);
    kok.querySelector('.ca-kapat').onclick = kapat;
    kok.addEventListener('mousedown', e => { if (e.target === kok) kapat(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && kok.classList.contains('acik')) kapat(); });
    kok.querySelectorAll('nav button').forEach(b => { b.onclick = () => sekmeAc(b.dataset.sekme); });
  }

  function ac(sekme) { panelKur(); kok.classList.add('acik'); sekmeAc(sekme || aktifSekme); }
  function kapat() { if (kok) kok.classList.remove('acik'); gorevIzleDurdur(); }

  function sekmeAc(k) {
    aktifSekme = k;
    gorevIzleDurdur();
    kok.querySelectorAll('nav button').forEach(b => b.classList.toggle('secili', b.dataset.sekme === k));
    const ic = kok.querySelector('.ca-icerik');
    ({ sure: sureSekmesi, a4: a4Sekmesi, ajanda: ajandaSekmesi, evrak: evrakSekmesi, gorev: gorevSekmesi, baglanti: baglantiSekmesi })[k](ic);
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
  function sunucuHatasi(ic, e) {
    const anahtarYok = e && e.durum === 401;
    ic.innerHTML = `<div class="ca-kart"><b>${anahtarYok ? '🔑 Eşleştirme gerekli' : '🔌 Asistan sunucusuna ulaşılamadı'}</b>
      <p>${anahtarYok ? 'Sunucu çalışıyor ama bu cihaz eşleştirilmemiş.' : 'UETS, UYAP evrak ve ajanda özellikleri yerel asistan sunucusunu kullanır. Masaüstü uygulamasında bu sunucu otomatik başlar; başlamadıysa CanEditor\'u yeniden açın.'}</p>
      <pre>python3 asistan/sunucu.py</pre>
      <p class="ca-soluk">Masaüstü kurulum paketlerinde (Windows, macOS, Linux) sunucu pakete gömülüdür ve kendiliğinden başlar; Python kurmanız gerekmez. Taşınabilir web / Termux'ta sunucunun yazdırdığı anahtarı <b>Bağlantı</b> sekmesine girin.</p>
      <button class="ca-btn" type="button" id="ca-bagla">🔌 Bağlantı ayarları</button></div>`;
    ic.querySelector('#ca-bagla').onclick = () => sekmeAc('baglanti');
  }

  async function ajandaSekmesi(ic) {
    ic.innerHTML = '<p class="ca-soluk">Yükleniyor…</p>';
    try {
      const v = await api('/api/ajanda?gun=60');
      if (!v.olaylar.length) {
        ic.innerHTML = `<p>Önümüzdeki 60 günde kayıtlı süre sonu veya duruşma yok.</p><p class="ca-soluk">Kaynaklar: Avukat Asistanı defteri ${v.kaynaklar.defter ? '✓' : '— (henüz yok)'} · UYAP kataloğu ${v.kaynaklar.katalog ? '✓' : '— (henüz yok)'}</p>`;
        return;
      }
      const bugun = isoGun(new Date());
      ic.innerHTML = `<table><thead><tr><th>Tarih</th><th>Tür</th><th>Dosya</th><th>Açıklama</th></tr></thead><tbody>${v.olaylar.map(o => `
        <tr><td>${esc(o.tarih.split('-').reverse().join('.'))} ${esc(o.saat || '')}${o.tarih === bugun ? ' <b>(bugün)</b>' : ''}</td>
        <td>${o.tur === 'sure' ? '⏱️ Son gün' : '🏛️ Duruşma'}</td>
        <td>${esc(o.birim || '')}<div class="ca-soluk">${esc(o.esas || '')}</div></td>
        <td>${esc(o.baslik || '')}${o.yer ? `<div class="ca-soluk">${esc(o.yer)}</div>` : ''}<div class="ca-soluk">${esc(o.kaynak)}</div></td></tr>`).join('')}</tbody></table>`;
    } catch (e) { sunucuHatasi(ic, e); }
  }

  function evrakSekmesi(ic) {
    ic.innerHTML = `<label for="ca-evrak-q">Ara (taraf, evrak türü, açıklama, dosya no — Türkçe harf duyarsız; hariç tutmak için -kelime)</label>
      <input id="ca-evrak-q" placeholder='ör. bilirkişi -ek "ağır ceza"'><div id="ca-evrak-sonuc" class="ca-soluk" style="margin-top:12px">Aramak için yazın.</div>`;
    const q = ic.querySelector('#ca-evrak-q'), sonuc = ic.querySelector('#ca-evrak-sonuc');
    let zam = null;
    const ara = async () => {
      try {
        const v = await api('/api/evrak/ara?limit=150&q=' + encodeURIComponent(q.value));
        if (!v.hazir) { sonuc.innerHTML = esc(v.mesaj); return; }
        sonuc.innerHTML = `<div class="ca-soluk">${v.sonuclar.length} sonuç (katalogda ${v.toplam_evrak} evrak)</div><table>${v.sonuclar.map(r => `
          <tr><td>${esc((r.tarih || '').slice(0, 10))}</td><td><b>${esc(r.tur || '')}</b><div class="ca-soluk">${esc(r.aciklama || '')}</div></td>
          <td>${esc(r.birim || '')}<div class="ca-soluk">${esc(r.dosya_no || '')} ${r.muvekkil ? '· ' + esc(r.muvekkil) : ''}</div></td>
          <td>${r.yerel ? `<button class="ca-btn" type="button" data-skey="${esc(r.skey)}">Aç</button>` : '<span class="ca-soluk">indirilmedi</span>'}</td></tr>`).join('')}</table>`;
        sonuc.querySelectorAll('button[data-skey]').forEach(b => {
          b.onclick = async () => {
            try {
              const r = await api('/api/evrak/dosya?skey=' + encodeURIComponent(b.dataset.skey), { ham: true });
              const buf = await r.arrayBuffer();
              const cd = r.headers.get('Content-Disposition') || '';
              const ad = decodeURIComponent((cd.match(/filename\*=UTF-8''([^;]+)/) || [])[1] || 'Evrak.pdf');
              kapat();
              if (window.openDocumentFromBytes) await window.openDocumentFromBytes(buf, ad);
              else if (window.openPdfViewer) await window.openPdfViewer(buf, ad);
            } catch (e) { alert('Evrak açılamadı: ' + e.message); }
          };
        });
      } catch (e) { sunucuHatasi(ic, e); }
    };
    q.addEventListener('input', () => { clearTimeout(zam); zam = setTimeout(ara, 300); });
    q.focus();
  }

  let izleZam = null;
  function gorevIzleDurdur() { if (izleZam) { clearInterval(izleZam); izleZam = null; } }

  async function gorevSekmesi(ic) {
    ic.innerHTML = '<p class="ca-soluk">Yükleniyor…</p>';
    const ciz = async () => {
      const v = await api('/api/gorevler?satir=12');
      const acik = Array.from(ic.querySelectorAll('details[open]')).map(d => d.dataset.k);
      ic.innerHTML = v.gorevler.map(g => `<div class="ca-kart">
        <b>${esc(g.ad)}</b> ${g.calisiyor ? '<span class="ca-soluk">— çalışıyor…</span>' : (g.kod === null ? '' : (g.kod === 0 ? '<span class="ca-soluk">— ✓ tamamlandı</span>' : `<span class="ca-hata">— hata (kod ${g.kod})</span>`))}
        <div>${g.calisiyor ? `<button class="ca-btn" type="button" data-durdur="${g.kimlik}">⏹ Durdur</button>` : `<button class="ca-btn ana" type="button" data-baslat="${g.kimlik}">▶ ${g.pencere ? 'Aç' : 'Çalıştır'}</button>`}</div>
        ${g.gunluk.length ? `<details data-k="${g.kimlik}" ${acik.includes(g.kimlik) || g.calisiyor ? 'open' : ''}><summary class="ca-soluk">Günlük</summary><pre>${esc(g.gunluk.join('\n'))}</pre></details>` : ''}</div>`).join('');
      ic.querySelectorAll('[data-baslat]').forEach(b => { b.onclick = async () => { b.disabled = true; try { await api('/api/gorev/' + b.dataset.baslat, { method: 'POST', govde: {} }); } catch (e) { alert(e.message); } ciz(); }; });
      ic.querySelectorAll('[data-durdur]').forEach(b => { b.onclick = async () => { await api('/api/gorev/' + b.dataset.durdur + '/durdur', { method: 'POST', govde: {} }); ciz(); }; });
    };
    try { await ciz(); izleZam = setInterval(() => { ciz().catch(gorevIzleDurdur); }, 2500); } catch (e) { sunucuHatasi(ic, e); }
  }

  async function baglantiSekmesi(ic) {
    const b = baglantiOku();
    ic.innerHTML = `<div class="ca-satir">
        <div><label for="ca-port">Port</label><input id="ca-port" type="number" value="${esc(b.port || 8765)}"></div>
        <div><label for="ca-anahtar">Eşleştirme anahtarı</label><input id="ca-anahtar" value="${esc(b.anahtar || '')}" autocomplete="off" spellcheck="false"></div>
      </div>
      <button class="ca-btn ana" type="button" id="ca-kaydet">Kaydet ve sına</button>
      <div id="ca-bag-sonuc" class="ca-kart"></div>
      <p class="ca-soluk">Anahtarı görmek için: <code>python3 asistan/sunucu.py --anahtar</code>. Sunucu yalnızca bu cihazdan (127.0.0.1) erişilebilir.</p>`;
    const sonuc = ic.querySelector('#ca-bag-sonuc');
    const sina = async () => {
      sonuc.textContent = 'Sınanıyor…';
      try {
        const v = await api('/api/durum');
        const m = v.moduller;
        const isaret = x => x ? '✓' : '✗';
        sonuc.innerHTML = `<b>✓ Bağlı</b> — sunucu ${esc(v.surum)} (${esc(v.platform)}${v.termux ? ', Termux' : ''})
          <table><tr><th>UETS / Avukat Asistanı</th><td>bağımlılıklar ${isaret(m.avukatasistan.bagimliliklar)} · yapılandırma ${isaret(m.avukatasistan.yapilandirildi)}</td></tr>
          <tr><th>UYAP Evrak</th><td>bağımlılıklar ${isaret(m.evrak.bagimliliklar)} · katalog ${isaret(m.evrak.katalog)}</td></tr>
          <tr><th>A4 motoru (sunucu)</th><td>bağımlılıklar ${isaret(m.a4.bagimliliklar)}</td></tr></table>`;
      } catch (e) { sonuc.innerHTML = `<span class="ca-hata">${esc(e.durum === 401 ? 'Anahtar yanlış.' : 'Sunucuya ulaşılamadı: ' + e.message)}</span>`; }
    };
    ic.querySelector('#ca-kaydet').onclick = () => { baglantiYaz({ port: +ic.querySelector('#ca-port').value || 8765, anahtar: ic.querySelector('#ca-anahtar').value.trim() }); sina(); };
    sina();
  }

  window.CanAsistan = { ac, kapat, sureHesapla, uygulanacakGun, tatilUyarilari, a4Yerlesim, a4PdfOlustur, api };
  window.openHukukAsistani = ac;
})();
