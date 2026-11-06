/**
 * CanEditor — Birebir Sayfa Dışa Aktarma Motoru (PDF vektör / TIFF raster)
 *
 * ESKİ SORUN: generatePdfBlob() metni kendi basit çizicisiyle yeniden diziyordu: sekme hizaları
 * (": değer" sütunları) kayboluyor, punto/kalınlık bozuluyor, üst/alt bilgi ve karekod düşüyordu.
 *
 * YENİ YÖNTEM: Ekranda görünen A4 sayfanın GERÇEK yerleşimi ölçülür (her kelimenin konumu Range
 * dikdörtgenlerinden), yani tarayıcının yaptığı dizgi (iki yana yaslama, sekmeler, girintiler,
 * tablo, üst/alt bilgi) aynen korunur. Aynı ölçüm iki çıktıya verilir:
 *   - PDF: jsPDF + gömülü Times New Roman / Arial TTF → seçilebilir, aranabilir, Türkçe karakterli vektör metin
 *   - TIFF / raster: aynı öğeler <canvas>'a çizilir (UYAP'ın kabul ettiği çok sayfalı TIFF için)
 */
(function () {
  'use strict';

  const PAGE = { portrait: [794, 1123], landscape: [1123, 794] }; // 96 DPI CSS px
  const PX2PT = 72 / 96;
  const SKIP_SEL = '.sheet-watermark-overlay, .official-doc-seal, .page-desk-chip, script, style, [data-export-skip]';
  const FONT_FILES = {
    times: { normal: 'TimesNewRoman.TTF', bold: 'Timesbd.TTF', italic: 'Timesi.TTF', bolditalic: 'Timesbi.TTF' },
    arial: { normal: 'Arial.TTF', bold: 'Arialbd.TTF', italic: 'Ariali.TTF', bolditalic: 'Arialbi.TTF' }
  };
  // Yazı tipi metrikleri (em oranı) — taban çizgisi hesabı için
  const METRICS = { times: { ascent: 0.891, descent: 0.216 }, arial: { ascent: 0.905, descent: 0.212 } };

  const famKey = (ff) => /arial|helvetica|sans|verdana|tahoma|segoe|roboto|calibri/i.test(ff || '') ? 'arial' : 'times';
  const styleKey = (bold, italic) => bold && italic ? 'bolditalic' : bold ? 'bold' : italic ? 'italic' : 'normal';

  function parseColor(c) {
    const m = /rgba?\(([^)]+)\)/.exec(c || '');
    if (!m) return null;
    const p = m[1].split(',').map(x => parseFloat(x));
    if (p.length === 4 && p[3] === 0) return null;
    return { r: p[0], g: p[1], b: p[2], a: p.length === 4 ? p[3] : 1 };
  }

  // ------------------------------------------------------------------ yerleşim ölçümü
  function measureSheet(sheet) {
    const landscape = sheet.classList.contains('landscape');
    const [W, H] = landscape ? PAGE.landscape : PAGE.portrait;
    const sr = sheet.getBoundingClientRect();
    const scale = sr.width / W || 1;
    const rel = (r) => ({ x: (r.left - sr.left) / scale, y: (r.top - sr.top) / scale, w: r.width / scale, h: r.height / scale });
    const items = { W, H, landscape, texts: [], lines: [], rects: [], images: [], svgs: [] };

    // Metin: kelime kelime (iki yana yaslı satırlarda kelime aralıkları tarayıcıdaki gibi kalır)
    const walker = document.createTreeWalker(sheet, NodeFilter.SHOW_TEXT, {
      acceptNode(n) {
        const el = n.parentElement;
        if (!el || el.closest(SKIP_SEL)) return NodeFilter.FILTER_REJECT;
        if (!n.textContent.trim()) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    const range = document.createRange();
    let t;
    while ((t = walker.nextNode())) {
      const el = t.parentElement;
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) === 0) continue;
      const size = parseFloat(cs.fontSize) || 16;
      const bold = (parseInt(cs.fontWeight, 10) || 400) >= 600;
      const italic = cs.fontStyle === 'italic' || cs.fontStyle === 'oblique';
      const fam = famKey(cs.fontFamily);
      const col = parseColor(cs.color) || { r: 0, g: 0, b: 0, a: 1 };
      // Alt çizgi / üstü çizili ebeveynlerden gelebilir (text-decoration kalıtsal değildir ama çizimi kapsar)
      let underline = false, strike = false;
      for (let a = el; a && !a.classList.contains('page-body-box') && !a.classList.contains('a4-sheet-page'); a = a.parentElement) {
        const d = getComputedStyle(a).textDecorationLine || '';
        if (d.includes('underline')) underline = true;
        if (d.includes('line-through')) strike = true;
      }
      const vAlign = cs.verticalAlign; // sup/sub
      const text = t.textContent;
      const re = /\S+/g;
      let m;
      while ((m = re.exec(text))) {
        range.setStart(t, m.index);
        range.setEnd(t, m.index + m[0].length);
        const rs = range.getClientRects();
        if (!rs.length) continue;
        // Kelime satır sonunda bölündüyse (nadiren) karakter karakter yerleştir
        if (rs.length > 1) {
          for (let i = 0; i < m[0].length; i++) {
            range.setStart(t, m.index + i); range.setEnd(t, m.index + i + 1);
            const r1 = range.getClientRects()[0]; if (!r1) continue;
            const R = rel(r1);
            items.texts.push({ s: m[0][i], x: R.x, y: R.y, w: R.w, h: R.h, size, bold, italic, fam, col, vAlign });
          }
          continue;
        }
        const R = rel(rs[0]);
        if (R.w <= 0) continue;
        items.texts.push({ s: m[0], x: R.x, y: R.y, w: R.w, h: R.h, size, bold, italic, fam, col, vAlign });
      }
      if (underline || strike) {
        range.selectNodeContents(t);
        for (const r of range.getClientRects()) {
          const R = rel(r);
          if (R.w <= 0.5) continue;
          const m2 = METRICS[fam];
          const base = R.y + R.h - m2.descent * size;
          if (underline) items.lines.push({ x1: R.x, y1: base + size * 0.1, x2: R.x + R.w, y2: base + size * 0.1, w: Math.max(0.6, size / 16), col });
          if (strike) items.lines.push({ x1: R.x, y1: base - size * 0.28, x2: R.x + R.w, y2: base - size * 0.28, w: Math.max(0.6, size / 16), col });
        }
      }
    }

    // Kenarlıklar ve arka planlar (tablolar, çizgiler, vurgular)
    sheet.querySelectorAll('*').forEach(el => {
      if (el.closest(SKIP_SEL)) return;
      if (el.classList.contains('page-header-box') || el.classList.contains('page-body-box') || el.classList.contains('page-footer-box')) return;
      const tagL = el.tagName.toLowerCase();
      if (tagL !== 'svg' && el.closest('svg')) return; // SVG iç öğeleri: SVG bütün olarak işlenir
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') return;
      if (tagL === 'svg') {
        const r = el.getBoundingClientRect();
        if (r.width > 1 && r.height > 1) items.svgs.push({ svg: el, ...rel(r) });
        return;
      }
      if (el.tagName === 'IMG') {
        const r = el.getBoundingClientRect();
        if (r.width > 1 && r.height > 1 && el.complete && el.naturalWidth) items.images.push({ el, ...rel(r) });
        return;
      }
      const bg = parseColor(cs.backgroundColor);
      if (bg && !(bg.r > 250 && bg.g > 250 && bg.b > 250)) {
        const rects = cs.display === 'inline' ? Array.from(el.getClientRects()) : [el.getBoundingClientRect()];
        rects.forEach(r => { const R = rel(r); if (R.w > 0 && R.h > 0) items.rects.push({ ...R, col: bg }); });
      }
      const r = el.getBoundingClientRect();
      if (r.width <= 0 || r.height <= 0) return;
      const R = rel(r);
      [['Top', R.x, R.y, R.x + R.w, R.y], ['Bottom', R.x, R.y + R.h, R.x + R.w, R.y + R.h], ['Left', R.x, R.y, R.x, R.y + R.h], ['Right', R.x + R.w, R.y, R.x + R.w, R.y + R.h]].forEach(([side, x1, y1, x2, y2]) => {
        const w = parseFloat(cs['border' + side + 'Width']) || 0;
        const st = cs['border' + side + 'Style'];
        if (w > 0 && st && st !== 'none' && st !== 'hidden') {
          const col = parseColor(cs['border' + side + 'Color']) || { r: 0, g: 0, b: 0, a: 1 };
          const half = w / scale / 2;
          const off = side === 'Top' || side === 'Left' ? half : -half;
          if (side === 'Top' || side === 'Bottom') items.lines.push({ x1, y1: y1 + off, x2, y2: y2 + off, w: w / scale, col, dash: st === 'dashed' || st === 'dotted' });
          else items.lines.push({ x1: x1 + off, y1, x2: x2 + off, y2, w: w / scale, col, dash: st === 'dashed' || st === 'dotted' });
        }
      });
      // Liste işaretleri (::marker metin düğümü değildir)
      if (el.tagName === 'LI' && cs.listStyleType && cs.listStyleType !== 'none') {
        const li = el; const idx = Array.prototype.indexOf.call(li.parentElement.children, li);
        const start = parseInt(li.parentElement.getAttribute('start') || '1', 10);
        const t2 = cs.listStyleType;
        const mark = /decimal/.test(t2) ? (start + idx) + '.' : /lower-alpha|lower-latin/.test(t2) ? String.fromCharCode(97 + idx) + '.' : /upper-alpha|upper-latin/.test(t2) ? String.fromCharCode(65 + idx) + '.' : t2 === 'circle' ? '◦' : t2 === 'square' ? '▪' : '•';
        const size = parseFloat(cs.fontSize) || 16;
        items.texts.push({ s: mark, x: R.x - size * 1.2, y: R.y, w: size, h: size * 1.15, size, bold: false, italic: false, fam: famKey(cs.fontFamily), col: { r: 0, g: 0, b: 0, a: 1 }, vAlign: 'baseline', marker: true });
      }
    });
    return items;
  }


  // Satır içi SVG'leri (UYAP karekodu vb.) yüksek çözünürlüklü tuvale çevirip görsel listesine ekler
  function svgToCanvas(svg, w, h) {
    return new Promise((resolve) => {
      try {
        const clone = svg.cloneNode(true);
        clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
        if (!clone.getAttribute('width')) clone.setAttribute('width', w);
        if (!clone.getAttribute('height')) clone.setAttribute('height', h);
        const xml = new XMLSerializer().serializeToString(clone);
        const img = new Image();
        img.onload = () => {
          const k = 4; const c = document.createElement('canvas');
          c.width = Math.max(1, Math.round(w * k)); c.height = Math.max(1, Math.round(h * k));
          const ctx = c.getContext('2d'); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, c.width, c.height);
          ctx.imageSmoothingEnabled = false; ctx.drawImage(img, 0, 0, c.width, c.height);
          resolve(c);
        };
        img.onerror = () => resolve(null);
        img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(xml)));
      } catch (e) { resolve(null); }
    });
  }
  async function rasterizeSvgs(pages) {
    for (const p of pages) {
      for (const s of p.svgs) {
        const c = await svgToCanvas(s.svg, s.w, s.h);
        if (c) p.images.push({ el: c, x: s.x, y: s.y, w: s.w, h: s.h, canvas: true });
      }
    }
    return pages;
  }

  function pageSheets() {
    if (typeof updatePagination === 'function') { try { updatePagination(); } catch (e) {} }
    if (typeof window.liveReflow === 'function') { try { window.liveReflow(); } catch (e) {} }
    return Array.from(document.querySelectorAll('#pages-container .a4-sheet-page, #sheet-container .a4-sheet-page'));
  }

  // Ölçüm sırasında ekran durumları (seçim, imleç, arama vurgusu) çıktıya karışmasın
  async function withCleanView(fn) {
    const wrap = document.getElementById('page-wrapper');
    const mobile = wrap && wrap.classList.contains('mobile-reflow-active');
    const sel = window.getSelection();
    const saved = sel && sel.rangeCount ? sel.getRangeAt(0).cloneRange() : null;
    try {
      if (mobile && typeof switchToPaperViewFlow === 'function') { switchToPaperViewFlow(); await new Promise(r => setTimeout(r, 250)); }
      document.body.classList.add('exporting-document');
      if (document.fonts && document.fonts.ready) await document.fonts.ready;
      return await fn();
    } finally {
      document.body.classList.remove('exporting-document');
      if (mobile && typeof switchToMobileViewFlow === 'function') switchToMobileViewFlow();
      if (saved) { try { sel.removeAllRanges(); sel.addRange(saved); } catch (e) {} }
    }
  }

  // ------------------------------------------------------------------ yazı tipi baytları
  const fontCache = {};
  function bytesToB64(u8) { let s = ''; for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000)); return btoa(s); }
  async function loadFontB64(file) {
    if (fontCache[file]) return fontCache[file];
    // Android WebView'de file:// fetch yasak → köprüden oku
    if (window.AndroidBridge && !window.AndroidBridge.__stub && window.AndroidBridge.readAssetBase64) {
      const b = window.AndroidBridge.readAssetBase64('editor/fonts/' + file);
      if (b) return (fontCache[file] = b);
    }
    const r = await fetch('fonts/' + file);
    if (!r.ok) throw new Error('Yazı tipi okunamadı: ' + file);
    return (fontCache[file] = bytesToB64(new Uint8Array(await r.arrayBuffer())));
  }

  // ------------------------------------------------------------------ PDF (vektör)
  async function buildPdf(title) {
    if (!window.jspdf || !window.jspdf.jsPDF) throw new Error('jsPDF yüklenmedi');
    return withCleanView(async () => {
      const sheets = pageSheets();
      if (!sheets.length) throw new Error('Sayfa bulunamadı');
      const pages = await rasterizeSvgs(sheets.map(measureSheet));
      const { jsPDF } = window.jspdf;
      const first = pages[0];
      const doc = new jsPDF({ unit: 'pt', format: 'a4', orientation: first.landscape ? 'landscape' : 'portrait', compress: true, putOnlyUsedFonts: true });
      // Kullanılan yazı tiplerini göm
      const used = new Set();
      pages.forEach(p => p.texts.forEach(t => used.add(t.fam + ':' + styleKey(t.bold, t.italic))));
      try {
        for (const u of used) {
          const [fam, st] = u.split(':');
          const file = FONT_FILES[fam][st];
          const vfsName = file.replace(/\.TTF$/i, '.ttf');
          doc.addFileToVFS(vfsName, await loadFontB64(file));
          doc.addFont(vfsName, fam === 'arial' ? 'CE-Arial' : 'CE-Times', st, 'Identity-H');
        }
      } catch (fontErr) {
        // Taşınabilir sürüm file:// ile açıldığında tarayıcı yazı tipi dosyasının okunmasını engeller.
        // Bu durumda aynı birebir yerleşimden 200 DPI görüntü-PDF üretilir (görünüm yine ekranla aynıdır).
        console.warn('Yazı tipi gömülemedi, görüntü tabanlı PDF üretiliyor:', fontErr && fontErr.message);
        const rdoc = new jsPDF({ unit: 'pt', format: 'a4', orientation: first.landscape ? 'landscape' : 'portrait', compress: true });
        pages.forEach((p, i) => {
          if (i > 0) rdoc.addPage('a4', p.landscape ? 'landscape' : 'portrait');
          const c = drawToCanvas(p, 2.1);
          rdoc.addImage(c.toDataURL('image/jpeg', 0.9), 'JPEG', 0, 0, p.W * PX2PT, p.H * PX2PT, undefined, 'FAST');
        });
        rdoc.setProperties({ title: title || 'Belge', creator: 'CanEditor' });
        return rdoc.output('blob');
      }
      pages.forEach((p, i) => {
        if (i > 0) doc.addPage('a4', p.landscape ? 'landscape' : 'portrait');
        p.rects.forEach(r => { doc.setFillColor(r.col.r, r.col.g, r.col.b); doc.rect(r.x * PX2PT, r.y * PX2PT, r.w * PX2PT, r.h * PX2PT, 'F'); });
        p.images.forEach(im => {
          try {
            const src = im.canvas ? '' : (im.el.currentSrc || im.el.src || '');
            const fmt = /^data:image\/jpe?g/i.test(src) || /\.jpe?g($|\?)/i.test(src) ? 'JPEG' : 'PNG';
            doc.addImage(im.el, fmt, im.x * PX2PT, im.y * PX2PT, im.w * PX2PT, im.h * PX2PT, undefined, 'FAST');
          } catch (e) { console.warn('PDF görsel atlandı:', e); }
        });
        p.texts.forEach(t => {
          const st = styleKey(t.bold, t.italic);
          doc.setFont(t.fam === 'arial' ? 'CE-Arial' : 'CE-Times', st);
          let size = t.size;
          const m = METRICS[t.fam];
          let base = t.y + t.h - m.descent * size;
          if (t.marker) base = t.y + m.ascent * size;
          doc.setFontSize(size * PX2PT);
          doc.setTextColor(t.col.r, t.col.g, t.col.b);
          // Kelimeyi tarayıcıdaki genişliğe oturt (yazı tipi farklarında taşma/kayma olmasın)
          const natural = doc.getTextWidth(t.s);
          const target = t.w * PX2PT;
          const opts = { baseline: 'alphabetic' };
          if (natural > 0 && t.s.length > 1 && Math.abs(natural - target) > 0.3) opts.charSpace = (target - natural) / (t.s.length - 1) * 0.98;
          doc.text(t.s, t.x * PX2PT, base * PX2PT, opts);
        });
        p.lines.forEach(l => {
          doc.setDrawColor(l.col.r, l.col.g, l.col.b);
          doc.setLineWidth(Math.max(0.35, l.w * PX2PT));
          if (l.dash) doc.setLineDashPattern([2, 2], 0); else doc.setLineDashPattern([], 0);
          doc.line(l.x1 * PX2PT, l.y1 * PX2PT, l.x2 * PX2PT, l.y2 * PX2PT);
        });
        doc.setLineDashPattern([], 0);
      });
      doc.setProperties({ title: title || 'Belge', creator: 'CanEditor', producer: 'CanEditor (jsPDF)' });
      return doc.output('blob');
    });
  }

  // ------------------------------------------------------------------ raster (TIFF / önizleme)
  function drawToCanvas(p, scale) {
    const c = document.createElement('canvas');
    c.width = Math.round(p.W * scale); c.height = Math.round(p.H * scale);
    const ctx = c.getContext('2d');
    ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, c.width, c.height);
    ctx.scale(scale, scale);
    p.rects.forEach(r => { ctx.fillStyle = `rgba(${r.col.r},${r.col.g},${r.col.b},${r.col.a})`; ctx.fillRect(r.x, r.y, r.w, r.h); });
    p.images.forEach(im => { try { ctx.drawImage(im.el, im.x, im.y, im.w, im.h); } catch (e) {} });
    ctx.textBaseline = 'alphabetic';
    p.texts.forEach(t => {
      const fam = t.fam === 'arial' ? '"Arial", sans-serif' : '"Times New Roman", Times, serif';
      ctx.font = `${t.italic ? 'italic ' : ''}${t.bold ? 'bold ' : ''}${t.size}px ${fam}`;
      ctx.fillStyle = `rgb(${t.col.r},${t.col.g},${t.col.b})`;
      const m = METRICS[t.fam];
      const base = t.marker ? t.y + m.ascent * t.size : t.y + t.h - m.descent * t.size;
      const natural = ctx.measureText(t.s).width;
      if (natural > 0 && Math.abs(natural - t.w) > 0.5 && t.s.length > 1) {
        ctx.save(); ctx.translate(t.x, base); ctx.scale(t.w / natural, 1); ctx.fillText(t.s, 0, 0); ctx.restore();
      } else ctx.fillText(t.s, t.x, base);
    });
    p.lines.forEach(l => {
      ctx.strokeStyle = `rgb(${l.col.r},${l.col.g},${l.col.b})`; ctx.lineWidth = Math.max(0.5, l.w);
      ctx.setLineDash(l.dash ? [2, 2] : []);
      ctx.beginPath(); ctx.moveTo(l.x1, l.y1); ctx.lineTo(l.x2, l.y2); ctx.stroke();
    });
    return c;
  }
  async function renderCanvases(scale) {
    return withCleanView(async () => (await rasterizeSvgs(pageSheets().map(measureSheet))).map(p => drawToCanvas(p, scale || 2)));
  }

  window.CanExport = { buildPdf, renderCanvases, measureSheet };
})();

/* --------------------------------------------------------------------------
 * Çok sayfalı TIFF kodlayıcı: 8 bit gri, PackBits (32773) sıkıştırma, 192 DPI.
 * Eski sürüm sıkıştırmasız RGBA yazıyordu (2 sayfa ≈ 7 MB); metin sayfaları burada ~%90 küçülür.
 * -------------------------------------------------------------------------- */
(function () {
  'use strict';
  function packBitsRow(src, off, len, out) {
    let i = 0;
    while (i < len) {
      // tekrar dizisi
      let run = 1;
      while (i + run < len && run < 128 && src[off + i + run] === src[off + i]) run++;
      if (run >= 3) { out.push(257 - run, src[off + i]); i += run; continue; }
      // ham dizi
      let start = i; let lit = 0;
      while (i < len && lit < 128) {
        let r2 = 1;
        while (i + r2 < len && r2 < 3 && src[off + i + r2] === src[off + i]) r2++;
        if (r2 >= 3) break;
        i++; lit++;
      }
      out.push(lit - 1);
      for (let k = start; k < start + lit; k++) out.push(src[off + k]);
    }
  }
  function encodeTiffGray(pages, dpi) {
    const strips = pages.map(p => {
      const out = [];
      for (let y = 0; y < p.h; y++) packBitsRow(p.gray, y * p.w, p.w, out);
      return Uint8Array.from(out);
    });
    const NT = 13;
    const ifdSize = 2 + NT * 12 + 4 + 16; // + 2 RATIONAL (X/Y çözünürlük)
    let total = 8;
    pages.forEach((p, i) => { total += ifdSize + strips[i].length + (strips[i].length & 1); });
    const buf = new ArrayBuffer(total); const dv = new DataView(buf); const u8 = new Uint8Array(buf);
    dv.setUint8(0, 0x49); dv.setUint8(1, 0x49); dv.setUint16(2, 42, true); dv.setUint32(4, 8, true);
    let pos = 8;
    pages.forEach((p, i) => {
      const ifd = pos; const ratOff = ifd + 2 + NT * 12 + 4; const dataOff = ratOff + 16;
      const next = i === pages.length - 1 ? 0 : dataOff + strips[i].length + (strips[i].length & 1);
      dv.setUint16(ifd, NT, true);
      let o = ifd + 2;
      const tag = (t, type, count, val) => { dv.setUint16(o, t, true); dv.setUint16(o + 2, type, true); dv.setUint32(o + 4, count, true); if (type === 3 && count === 1) dv.setUint16(o + 8, val, true); else dv.setUint32(o + 8, val, true); o += 12; };
      tag(254, 4, 1, 2);            // NewSubfileType: çok sayfalı belgenin sayfası
      tag(256, 4, 1, p.w);
      tag(257, 4, 1, p.h);
      tag(258, 3, 1, 8);
      tag(259, 3, 1, 32773);        // PackBits
      tag(262, 3, 1, 1);            // BlackIsZero
      tag(273, 4, 1, dataOff);
      tag(277, 3, 1, 1);
      tag(278, 4, 1, p.h);
      tag(279, 4, 1, strips[i].length);
      tag(282, 5, 1, ratOff);
      tag(283, 5, 1, ratOff + 8);
      tag(296, 3, 1, 2);            // inç
      dv.setUint32(o, next, true);
      dv.setUint32(ratOff, dpi, true); dv.setUint32(ratOff + 4, 1, true);
      dv.setUint32(ratOff + 8, dpi, true); dv.setUint32(ratOff + 12, 1, true);
      u8.set(strips[i], dataOff);
      pos = dataOff + strips[i].length + (strips[i].length & 1);
    });
    return new Blob([buf], { type: 'image/tiff' });
  }
  async function buildTiff() {
    const canvases = await window.CanExport.renderCanvases(2);
    const pages = canvases.map(c => {
      const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
      const g = new Uint8Array(c.width * c.height);
      for (let i = 0, j = 0; j < g.length; i += 4, j++) g[j] = (d[i] * 299 + d[i + 1] * 587 + d[i + 2] * 114) / 1000;
      return { w: c.width, h: c.height, gray: g };
    });
    return encodeTiffGray(pages, 192);
  }
  window.CanExport.buildTiff = buildTiff;
  window.CanExport.encodeTiffGray = encodeTiffGray;
})();
