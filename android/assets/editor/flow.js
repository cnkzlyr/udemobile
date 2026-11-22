/**
 * CanEditor — Canlı Sayfa Akışı (Live Pagination / Word-benzeri sayfa taşması)
 *
 * SORUN (v3.14.0 ve öncesi): updatePagination(), editör odaklıyken (yani kullanıcı yazarken)
 * Android klavyesinin kapanmaması için hiç çalışmıyordu. Sonuç: 1. sayfa dolunca yazılan metin
 * sabit yükseklikli `.page-body-box` (overflow:hidden) içinde GİZLENİYOR, yeni sayfa açılmıyor,
 * belge "tek sayfa" gibi görünüyor ve aşağı kaydırılamıyordu.
 *
 * ÇÖZÜM: DOM'u yıkmadan (container.innerHTML = '' YAPMADAN) yerinde akış:
 *   1) Taşan sayfanın son blokları sonraki sayfanın başına TAŞINIR (gerekirse yeni A4 sayfa açılır).
 *   2) Tek başına sayfaya sığmayan uzun paragraf satır sınırından bölünür (data-split-continuation).
 *   3) Sayfada yer açılınca sonraki sayfanın ilk blokları geri ÇEKİLİR; bölünmüş parça birleşir.
 *   4) Boşalan son sayfalar silinir, sayfa numaraları / altbilgiler güncellenir.
 *   5) İmleç, belge genelindeki karakter ofsetiyle kaydedilip geri yüklenir (düğüm bölünse bile doğru yer).
 * Odaklı düzenleme kutusu yok edilmediği için Android IME (klavye) kapanmaz.
 *
 * Ayrıca sayfalar ayrı contenteditable kutular olduğundan tarayıcı sayfa sınırını geçemez;
 * Backspace / Delete / ↑ / ↓ / PageUp / PageDown sayfalar arasında Word gibi çalışacak şekilde ele alınır.
 */
(function () {
  'use strict';

  const SKIP_CLASSES = ['auto-page-break', 'page-break-desk-gap', 'page-desk-gap', 'page-break-footer-area', 'page-break-header-area'];
  let busy = false;
  let scheduled = 0;
  let observer = null;

  // v3.17.0 — KAYDIRMADA GERİ SEKME DÜZELTMESİ / scroll bounce-back fix
  // Kullanıcı en son ne yaptı? Yazdıysa imleç görünür tutulur; kaydırdıysa ASLA imlece geri çekilmez.
  // (Önceki sürümde kendi kendini tetikleyen yeniden sayfalama döngüsü her ~80 ms'de keepCaretVisible()
  //  çağırıp kaydırmayı imlecin olduğu sayfaya geri atıyordu.)
  let lastEditTs = 0;     // son klavye/IME girişi (keydown, beforeinput, compositionend)
  let lastScrollTs = 0;   // son kullanıcı kaydırma hareketi (dokunma sürükleme, tekerlek, kaydırma çubuğu)
  const CARET_FOLLOW_MS = 1500;
  let reflowTurlari = 0;   // art arda "düzen değişti" turları (sabit noktaya yakınsama sınırı)

  const container = () => document.getElementById('pages-container') || document.getElementById('sheet-container');
  const isMobileFlow = () => {
    const w = document.getElementById('page-wrapper');
    return (typeof isMobileView !== 'undefined' && isMobileView) || (w && w.classList.contains('mobile-reflow-active'));
  };
  const bodies = () => {
    const c = container();
    return c ? Array.from(c.querySelectorAll('.a4-sheet-page > .page-body-box')) : [];
  };
  const isContent = (n) => n && n.nodeType === 1 && !SKIP_CLASSES.some(k => n.classList.contains(k));
  const contentChildren = (box) => Array.from(box.children).filter(isContent);
  const isHardBreak = (n) => n && n.classList && (n.classList.contains('page-break') || n.classList.contains('udf-page-break') || (n.getAttribute && n.getAttribute('data-udf-page-break') === 'true'));
  const isEmptyPara = (n) => n && /^(P|DIV)$/.test(n.tagName) && !n.querySelector('img,table') && n.textContent.replace(/​/g, '').trim() === '';

  // Bloğun kutu içindeki alt sınırı (alt boşluk/margin hariç — Word da son satırın altındaki boşluğu saymaz)
  function usedHeight(box) {
    const kids = contentChildren(box);
    if (!kids.length) return 0;
    const last = kids[kids.length - 1];
    return last.offsetTop + last.offsetHeight;
  }
  const overflows = (box) => usedHeight(box) > box.clientHeight + 0.5;

  // ---------------------------------------------------------------- imleç (karakter ofseti)
  function textLenBefore(box, node, offset) {
    const r = document.createRange();
    r.selectNodeContents(box);
    try { r.setEnd(node, offset); } catch (e) { return 0; }
    return r.toString().length;
  }
  function saveCaret() {
    const sel = window.getSelection();
    if (!sel || !sel.rangeCount) return null;
    const rg = sel.getRangeAt(0);
    const all = bodies();
    const host = (rg.startContainer.nodeType === 1 ? rg.startContainer : rg.startContainer.parentElement);
    const box = host && host.closest ? host.closest('.page-body-box') : null;
    if (!box) return null;
    const idx = all.indexOf(box);
    if (idx < 0) return null;
    let base = 0;
    for (let i = 0; i < idx; i++) base += all[i].textContent.length;
    const start = base + textLenBefore(box, rg.startContainer, rg.startOffset);
    const end = rg.collapsed ? start : base + textLenBefore(box, rg.endContainer, rg.endOffset);
    // Blok başında mı? (sayfa sınırındaki belirsizlikte sonraki bloğu tercih etmek için)
    let atBlockStart = false;
    const blk = host.closest('p,li,div,td,h1,h2,h3,h4,h5,h6');
    if (blk && box.contains(blk)) {
      const r2 = document.createRange();
      r2.selectNodeContents(blk);
      try { r2.setEnd(rg.startContainer, rg.startOffset); atBlockStart = r2.toString().length === 0; } catch (e) {}
    }
    return { start, end, atBlockStart, hadFocus: !!(document.activeElement && document.activeElement.closest && document.activeElement.closest('.page-body-box')) };
  }
  function locate(offset, preferNext) {
    const all = bodies();
    let acc = 0;
    let lastHit = null;
    for (const box of all) {
      const w = document.createTreeWalker(box, NodeFilter.SHOW_TEXT);
      let t;
      while ((t = w.nextNode())) {
        const len = t.textContent.length;
        if (offset < acc + len || (offset === acc + len && !preferNext)) return { node: t, off: offset - acc, box };
        if (offset === acc + len) lastHit = { node: t, off: len, box };
        acc += len;
      }
    }
    if (lastHit) return lastHit;
    // Metin düğümü yoksa (boş paragraf): son kutunun son bloğuna
    const box = all[all.length - 1];
    if (!box) return null;
    return { node: box, off: box.childNodes.length, box, empty: true };
  }
  function restoreCaret(saved) {
    if (!saved) return;
    try {
      const a = locate(saved.start, saved.atBlockStart);
      if (!a) return;
      // Boş paragraf (<p><br></p>) içindeki imleç: metin düğümü yok → blok başına koy
      let node = a.node, off = a.off;
      if (saved.atBlockStart && a.node.nodeType === 3 && a.off === a.node.textContent.length) {
        // tercih edilen sonraki metin düğümü bulunamadıysa boş paragraf olabilir
      }
      const sel = window.getSelection();
      if (saved.hadFocus && document.activeElement !== a.box) {
        try { a.box.focus({ preventScroll: true }); } catch (e) { a.box.focus(); }
      }
      if (saved.end !== saved.start) {
        const b = locate(saved.end, false) || a;
        const r = document.createRange();
        r.setStart(node, off);
        r.setEnd(b.node, b.off);
        sel.removeAllRanges();
        sel.addRange(r);
      } else {
        sel.collapse(node, off);
      }
      if (window.__flowDebug) window.__flowDebug.push('locate ' + (node.nodeType === 3 ? JSON.stringify(node.textContent.slice(0, 20)) : node.nodeName) + '@' + off + ' inbox=' + bodies().indexOf(a.box) + ' active=' + bodies().indexOf(document.activeElement));
    } catch (e) { if (window.__flowDebug) window.__flowDebug.push('restore error ' + e.message); }
  }
  // Boş paragraf içindeki imleç için kesin düğüm referansı (metin uzunluğu 0 olduğundan ofsetle bulunamaz)
  function caretEmptyBlock() {
    const sel = window.getSelection();
    if (!sel || !sel.rangeCount || !sel.isCollapsed) return null;
    const n = sel.anchorNode;
    const el = n && (n.nodeType === 1 ? n : n.parentElement);
    const blk = el && el.closest ? el.closest('p,li,div:not(.page-body-box)') : null;
    return blk && blk.closest('.page-body-box') && isEmptyPara(blk) ? blk : null;
  }

  // ---------------------------------------------------------------- sayfa oluşturma / silme
  function makePageAfter(sheet) {
    const all = bodies();
    const total = all.length + 1;
    const newNum = all.length + 1;
    const clone = sheet.cloneNode(false);
    clone.id = 'page-' + newNum;
    clone.setAttribute('data-page-number', String(newNum));
    // filigran varsa kopyala
    const wm = sheet.querySelector(':scope > .sheet-watermark-overlay');
    if (wm) clone.appendChild(wm.cloneNode(true));
    const srcHeader = sheet.querySelector(':scope > .page-header-box');
    const srcBody = sheet.querySelector(':scope > .page-body-box');
    const srcFooter = sheet.querySelector(':scope > .page-footer-box');
    if (srcHeader) {
      const h = srcHeader.cloneNode(true);
      h.removeAttribute('id');
      h.addEventListener('input', () => {
        if (typeof currentDocHeaderTemplate !== 'undefined') { try { currentDocHeaderTemplate = h.innerHTML; } catch (e) {} }
      });
      clone.appendChild(h);
    }
    const b = srcBody.cloneNode(false);
    b.removeAttribute('id');
    b.addEventListener('input', function () {
      if (typeof markDocumentUserEdited === 'function') markDocumentUserEdited();
      if (typeof debouncedUpdateCounts === 'function') debouncedUpdateCounts(800);
    });
    clone.appendChild(b);
    if (srcFooter) {
      const f = srcFooter.cloneNode(false);
      f.removeAttribute('id');
      clone.appendChild(f);
    }
    const gap = document.createElement('div');
    gap.className = 'page-desk-gap';
    gap.innerHTML = '<span class="page-desk-chip"></span>';
    // son sayfadan sonra ekle
    const c = container();
    const lastSheet = all.length ? all[all.length - 1].closest('.a4-sheet-page') : sheet;
    c.insertBefore(gap, lastSheet.nextSibling);
    c.insertBefore(clone, gap.nextSibling);
    void total;
    return b;
  }

  function removePage(box) {
    const sheet = box.closest('.a4-sheet-page');
    if (!sheet) return;
    const prev = sheet.previousElementSibling;
    if (prev && prev.classList.contains('page-desk-gap')) prev.remove();
    sheet.remove();
  }

  function renumber() {
    const all = bodies();
    const total = all.length;
    all.forEach((box, i) => {
      const sheet = box.closest('.a4-sheet-page');
      const num = i + 1;
      sheet.id = 'page-' + num;
      sheet.setAttribute('data-page-number', String(num));
      const footer = sheet.querySelector(':scope > .page-footer-box');
      if (footer && typeof getDocFooterHtml === 'function') {
        const html = getDocFooterHtml(num, total);
        if (footer.innerHTML !== html) footer.innerHTML = html;
      }
      const gap = sheet.previousElementSibling;
      if (gap && gap.classList.contains('page-desk-gap')) {
        gap.setAttribute('data-page-label', `Sayfa ${i} / ${total}`);
        const chip = gap.querySelector('.page-desk-chip');
        if (chip) chip.textContent = `Sayfa ${i} / ${total}`;
      }
    });
    const st = document.getElementById('stat-page-count');
    if (st) st.textContent = `Sayfa 1 / ${total}`;
  }

  // ---------------------------------------------------------------- paragraf bölme / birleştirme
  // Kutudaki tek (veya ilk) paragraf sayfaya sığmıyorsa sığan satırdan böl.
  function splitParagraphToFit(box, p) {
    if (!p || p.tagName !== 'P') return null;
    const avail = box.clientHeight - p.offsetTop;
    if (avail < 16) return null;
    const boxRect = box.getBoundingClientRect();
    const scale = box.offsetHeight ? (boxRect.height / box.offsetHeight) || 1 : 1;
    const cutoffY = boxRect.top + (p.offsetTop + avail) * scale;
    const walker = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
    const r = document.createRange();
    let splitNode = null, splitOff = 0, t;
    outer: while ((t = walker.nextNode())) {
      const len = t.textContent.length;
      for (let i = 0; i < len; i++) {
        r.setStart(t, i);
        r.setEnd(t, i + 1);
        const rects = r.getClientRects();
        const rc = rects.length ? rects[rects.length - 1] : null;
        if (rc && rc.bottom > cutoffY + 0.5) { splitNode = t; splitOff = i; break outer; }
      }
    }
    if (!splitNode) return null;
    // kelime başına geri git (satır kırılımı kelime sınırındadır)
    while (splitOff > 0 && !/\s/.test(splitNode.textContent[splitOff - 1])) splitOff--;
    if (splitOff === 0) {
      // düğüm başı: önceki metin düğümü boşlukla bitiyorsa düğüm başından böl, değilse olduğu gibi
    }
    const range = document.createRange();
    range.setStart(splitNode, splitOff);
    range.setEndAfter(p.lastChild);
    if (range.collapsed) return null;
    const frag = range.extractContents();
    if (!p.textContent.length && !p.querySelector('img')) { // her şey taşındıysa bölme anlamsız
      p.appendChild(frag);
      return null;
    }
    const cont = p.cloneNode(false);
    cont.removeAttribute('id');
    if (p.hasAttribute('data-split-pb')) { cont.style.paddingBottom = p.getAttribute('data-split-pb'); cont.removeAttribute('data-split-pb'); }
    cont.appendChild(frag);
    cont.setAttribute('data-split-continuation', 'true');
    cont.style.textIndent = '0cm';
    cont.style.marginTop = '0px';
    cont.style.paddingTop = '0px';
    if (!p.hasAttribute('data-split-mb')) p.setAttribute('data-split-mb', p.style.marginBottom || '');
    p.style.marginBottom = '0px';
    // son satır dolgusu (büyük puntolu paragraf sonu) yalnızca devam parçasında kalır
    if (p.style.paddingBottom) { if (!p.hasAttribute('data-split-pb')) p.setAttribute('data-split-pb', p.style.paddingBottom); p.style.paddingBottom = '0px'; }
    return cont;
  }
  function mergeContinuation(head, cont) {
    if (head.tagName === 'TABLE' && cont.tagName === 'TABLE') {
      const targetBody = head.tBodies[0] || head;
      Array.from(cont.rows || []).forEach(r => targetBody.appendChild(r));
      cont.remove();
    } else {
      if (head.lastChild && head.lastChild.nodeName === 'BR') head.lastChild.remove();
      while (cont.firstChild) head.appendChild(cont.firstChild);
      cont.remove();
      if (typeof window.mergeSplitSpansInBlock === 'function') {
        window.mergeSplitSpansInBlock(head);
      } else {
        head.normalize();
      }
    }
    if (head.hasAttribute('data-split-mb')) {
      head.style.marginBottom = head.getAttribute('data-split-mb');
      head.removeAttribute('data-split-mb');
    }
    if (head.hasAttribute('data-split-pb')) {
      head.style.paddingBottom = head.getAttribute('data-split-pb');
      head.removeAttribute('data-split-pb');
    }
  }

  // Gövde kutusunun doğrudan çocuklarını blok düzenine getir:
  //  - bloklar arası boşluk metin düğümlerini sil (sayfa taşımalarında yerinde kalıp imleç ofsetini kaydırıyorlardı)
  //  - kutuya doğrudan yazılmış satır içi metni/öğeleri <p> içine al (taşınabilir blok olsun)
  const INLINE = /^(SPAN|B|I|U|S|STRONG|EM|FONT|A|BR|SUB|SUP|IMG|MARK|CODE|SMALL|BIG)$/;
  function normalizeBoxes() {
    const sel = window.getSelection();
    const aN = sel && sel.rangeCount ? sel.anchorNode : null, aO = sel ? sel.anchorOffset : 0;
    let touched = false;
    bodies().forEach(box => {
      let run = null;
      Array.from(box.childNodes).forEach(n => {
        if (n.nodeType === 3 && !n.textContent.replace(/[\s​]/g, '').length && n !== aN) { n.remove(); run = null; touched = true; return; }
        if (n.nodeType === 8) { return; }
        const inline = n.nodeType === 3 || (n.nodeType === 1 && INLINE.test(n.tagName));
        if (inline) {
          if (!run) { run = document.createElement('p'); run.style.textAlign = 'justify'; box.insertBefore(run, n); }
          run.appendChild(n);
          touched = true;
        } else run = null;
      });
    });
    if (touched && aN && aN.isConnected) { try { sel.collapse(aN, aO); } catch (e) {} }
  }

  // ---------------------------------------------------------------- ana akış
  // Sayfa düzeninin parmak izi: her sayfadaki blok sayısı + karakter sayısı.
  // Böl-birleştir turları (3. adım) DOM düğümlerini değiştirse de sonuç aynıysa düzen DEĞİŞMEMİŞTİR.
  // Layout fingerprint: a merge-then-resplit round touches the DOM but yields the same pages.
  function layoutSignature() {
    return bodies().map(b => contentChildren(b).length + ':' + (b.textContent || '').length).join('|');
  }

  function reflow() {
    if (busy || isMobileFlow()) return false;
    const c = container();
    if (!c) return false;
    let all = bodies();
    if (!all.length) return false;
    busy = true;
    const sigBefore = layoutSignature();
    normalizeBoxes();
    const emptyCaretBlock = caretEmptyBlock();
    const saved = saveCaret();
    const dbg = window.__flowDebug ? (m) => window.__flowDebug.push(m) : null;
    if (dbg) { const s0 = window.getSelection(); const r0 = s0.rangeCount ? s0.getRangeAt(0) : null; dbg('start saved=' + JSON.stringify(saved) + ' empty=' + !!emptyCaretBlock + ' sel=' + (s0.anchorNode && s0.anchorNode.nodeName) + JSON.stringify((s0.anchorNode && s0.anchorNode.textContent || '').slice(0, 10)) + '@' + s0.anchorOffset + ' range=' + (r0 && r0.startContainer.nodeName + JSON.stringify((r0.startContainer.textContent || '').slice(0, 10)) + '@' + r0.startOffset) + ' stack=' + new Error().stack.split('\n').slice(2, 4).map(x => x.trim()).join('<')); }
    let changed = false;
    try {
      for (let i = 0; i < all.length; i++) {
        const box = all[i];
        // Aynı sayfa içinde yan yana kalmış bölünmüş parçaları (head + continuation) hemen birleştir
        {
          const sameKids = contentChildren(box);
          for (let k = sameKids.length - 1; k > 0; k--) {
            if (sameKids[k].getAttribute('data-split-continuation') === 'true' && sameKids[k - 1].tagName === sameKids[k].tagName) {
              mergeContinuation(sameKids[k - 1], sameKids[k]);
              changed = true;
            }
          }
        }
        let guard = 0;
        // 1) Taşanları sonraki sayfaya it
        while (overflows(box) && guard++ < 500) {
          const kids = contentChildren(box);
          if (kids.length > 1) {
            const last = kids[kids.length - 1];
            let next = all[i + 1];
            if (!next) { next = makePageAfter(box.closest('.a4-sheet-page')); all = bodies(); }
            const nk = contentChildren(next);
            next.insertBefore(last, nk[0] || null);
            if (nk[0] && nk[0].getAttribute('data-split-continuation') === 'true' && last.tagName === nk[0].tagName) {
              mergeContinuation(last, nk[0]);
            }
            changed = true;
            continue;
          }
          // tek blok sayfadan büyük → bölmeyi dene
          const cont = splitParagraphToFit(box, kids[0]);
          if (!cont) break;
          let next = all[i + 1];
          if (!next) { next = makePageAfter(box.closest('.a4-sheet-page')); all = bodies(); }
          next.insertBefore(cont, contentChildren(next)[0] || null);
          changed = true;
        }
        // 2) Elle konmuş sayfa sonundan sonrası her zaman sonraki sayfaya
        const kids = contentChildren(box);
        const brIdx = kids.findIndex(isHardBreak);
        if (brIdx >= 0 && brIdx < kids.length - 1) {
          let next = all[i + 1];
          if (!next) { next = makePageAfter(box.closest('.a4-sheet-page')); all = bodies(); }
          const anchor = contentChildren(next)[0] || null;
          kids.slice(brIdx + 1).forEach(k => next.insertBefore(k, anchor));
          changed = true;
        }
        // 3) Yer açıldıysa sonraki sayfadan geri çek
        let pullGuard = 0;
        while (i + 1 < all.length && pullGuard++ < 500) {
          const cur = contentChildren(box);
          if (cur.length && isHardBreak(cur[cur.length - 1])) break;
          // Sonraki DOLU sayfadan çek. Bir devam parçası tamamen birleştirilince arada boş sayfa kalabiliyor;
          // eskiden döngü orada duruyor ve sonraki tüm sayfalar bu turda hiç toparlanmıyordu (ÇUBUK FEZLEKE:
          // UYAP 143 sayfa, UdeMobile 179 — sayfa altlarında 500+ pt boşluk).
          // Pull from the next NON-EMPTY page: a fully merged continuation can leave an empty page behind.
          let ni = i + 1;
          while (ni < all.length && !contentChildren(all[ni]).length) ni++;
          if (ni >= all.length) break;
          const next = all[ni];
          const first = contentChildren(next)[0];
          if (!first) break;
          const lastHere = cur[cur.length - 1];
          if (first.getAttribute('data-split-continuation') === 'true' && lastHere && lastHere.tagName === first.tagName) {
            // bölünmüş paragrafın devamı: birleştir, taşarsa 1. adım bir sonraki turda yeniden böler
            mergeContinuation(lastHere, first);
            changed = true;
            if (overflows(box)) {
              const cont = splitParagraphToFit(box, lastHere);
              if (cont) next.insertBefore(cont, contentChildren(next)[0] || null);
              break;
            }
            continue;
          }
          if (isHardBreak(first)) break;
          // Önce ölç: aynı genişlikteki kutularda bloğun yüksekliği değişmez → deneme taşıması yapma
          // (deneme taşıması imleci bozuyordu). Kalan alan = kutu yüksekliği - kullanılan - aradaki boşluk.
          const fcs = getComputedStyle(first);
          const mt = parseFloat(fcs.marginTop) || 0;
          const prevMb = lastHere ? (parseFloat(getComputedStyle(lastHere).marginBottom) || 0) : 0;
          const need = first.offsetHeight + (lastHere ? (mt + prevMb) : mt);
          if (usedHeight(box) + need > box.clientHeight + 0.5) {
            // Paragraf tamamen sığmıyorsa Havelsan/Word gibi sayfa sonunda BÖL: sığan satırlar bu sayfaya gelir
            const lhPx = parseFloat(fcs.lineHeight) || 16;
            const avail = box.clientHeight - usedHeight(box) - (lastHere ? (mt + prevMb) : mt);
            if (first.tagName === 'P' && first.textContent.trim() && avail >= lhPx) {
              box.appendChild(first);
              const cont = splitParagraphToFit(box, first);
              if (cont) { next.insertBefore(cont, contentChildren(next)[0] || null); changed = true; }
              else next.insertBefore(first, contentChildren(next)[0] || null);
            }
            break;
          }
          box.appendChild(first);
          changed = true;
          if (overflows(box)) { next.insertBefore(first, contentChildren(next)[0] || null); break; }
        }
      }
      // 4) Boş kalan sondaki sayfaları sil (1. sayfa hariç)
      all = bodies();
      for (let i = all.length - 1; i > 0; i--) {
        const kids = contentChildren(all[i]);
        const onlyEmpty = kids.length === 0 || (kids.length === 1 && isEmptyPara(kids[0]) && kids[0] !== emptyCaretBlock && !all[i].contains(document.activeElement === all[i] ? null : null));
        const prevKids = contentChildren(all[i - 1]);
        const prevEndsWithBreak = prevKids.length && isHardBreak(prevKids[prevKids.length - 1]);
        if (onlyEmpty && !prevEndsWithBreak && !(kids.length === 1 && kids[0] === emptyCaretBlock)) {
          if (kids.length === 0) { removePage(all[i]); changed = true; continue; }
          // tek boş paragraf: önceki sayfaya sığıyorsa taşı, sonra sayfayı sil
          all[i - 1].appendChild(kids[0]);
          // Son sayfadaki tek boş paragraf (belge sonu) taşsa da önceki sayfada kalır (Havelsan yeni sayfa açmaz)
          if (overflows(all[i - 1]) && i !== all.length - 1) { all[i].appendChild(kids[0]); break; }
          removePage(all[i]);
          changed = true;
        } else break;
      }
      // Boş gövde kutusu bırakma
      bodies().forEach(b => { if (!contentChildren(b).length) b.innerHTML = '<p style="text-align: justify;"><br></p>'; });
      // Düğümler taşındı ama sayfa düzeni aynı kaldıysa (böl→birleştir→böl) gerçek değişiklik yok:
      // yeniden numaralandırma ve imlece kaydırma yapılmaz.
      if (changed && layoutSignature() === sigBefore) changed = 'nodes-only';
      if (changed === true) renumber();
    } finally {
      if (changed) {
        // Düğümler yeniden oluşmuş olabilir: imleç her durumda yerine konur
        if (emptyCaretBlock && emptyCaretBlock.isConnected) {
          const box = emptyCaretBlock.closest('.page-body-box');
          if (saved && saved.hadFocus && document.activeElement !== box) { try { box.focus({ preventScroll: true }); } catch (e) {} }
          try { window.getSelection().collapse(emptyCaretBlock, 0); } catch (e) {}
        } else {
          restoreCaret(saved);
        }
        if (dbg) { const s2 = window.getSelection(); dbg('restored -> ' + (s2.anchorNode && (s2.anchorNode.textContent || '').slice(0, 24)) + '@' + s2.anchorOffset); }
        // Yalnızca kullanıcı az önce YAZDIYSA ve o zamandan beri kaydırmadıysa imleci görünür tut
        if (changed === true && userIsTyping()) keepCaretVisible();
      }
      // Bu turun kendi DOM değişikliklerinin kayıtlarını at: aksi halde gözlemci (busy=false olduktan sonra
      // çalışınca) bunları kullanıcı düzenlemesi sanıp yeni bir reflow planlıyor → sonsuz döngü.
      // Drop the records produced by this reflow so the MutationObserver doesn't re-trigger it forever.
      if (observer) observer.takeRecords();
      busy = false;
    }
    // Düzen gerçekten değiştiyse bir tur daha: bir geçişte geri çekilemeyen içerik sonraki turda yerine oturur.
    // Parmak izi aynı kalınca durur (sonsuz döngü olmaz). Eski sürümde bu tekrarları kendi kendini tetikleyen
    // gözlemci sağlıyordu; gözlemci döngüsü kesilince sabit noktaya kadar burada yineleniyor.
    // Iterate to a fixed point: stop as soon as a pass leaves the layout fingerprint unchanged.
    if (changed === true) {
      reflowTurlari = (reflowTurlari || 0) + 1;
      if (reflowTurlari < 12) schedule(0); else reflowTurlari = 0;
    } else {
      reflowTurlari = 0;
    }
    return changed === true;
  }

  function userIsTyping() {
    return lastEditTs > lastScrollTs && (Date.now() - lastEditTs) < CARET_FOLLOW_MS;
  }

  function keepCaretVisible() {
    const sel = window.getSelection();
    if (!sel || !sel.rangeCount) return;
    const wrap = document.getElementById('page-wrapper');
    if (!wrap) return;
    let rect = sel.getRangeAt(0).getBoundingClientRect();
    if (!rect || (!rect.height && !rect.top)) {
      const n = sel.anchorNode;
      const el = n && (n.nodeType === 1 ? n : n.parentElement);
      if (!el) return;
      rect = el.getBoundingClientRect();
    }
    const wr = wrap.getBoundingClientRect();
    const margin = 40;
    if (rect.bottom > wr.bottom - margin) wrap.scrollTop += rect.bottom - wr.bottom + margin;
    else if (rect.top < wr.top + margin) wrap.scrollTop -= (wr.top + margin - rect.top);
  }

  function schedule(delay) {
    if (scheduled) clearTimeout(scheduled);
    scheduled = setTimeout(() => { scheduled = 0; requestAnimationFrame(reflow); }, delay == null ? 60 : delay);
  }

  // ---------------------------------------------------------------- sayfalar arası klavye
  function caretInfo() {
    const sel = window.getSelection();
    if (!sel || !sel.rangeCount) return null;
    const rg = sel.getRangeAt(0);
    const el = rg.startContainer.nodeType === 1 ? rg.startContainer : rg.startContainer.parentElement;
    const box = el && el.closest ? el.closest('.page-body-box') : null;
    if (!box || !box.closest('.a4-sheet-page')) return null;
    const all = bodies();
    return { sel, rg, box, idx: all.indexOf(box), all };
  }
  function atBoxStart(info) {
    if (!info.rg.collapsed) return false;
    return textLenBefore(info.box, info.rg.startContainer, info.rg.startOffset) === 0 && (() => {
      const first = contentChildren(info.box)[0];
      const el = info.rg.startContainer.nodeType === 1 ? info.rg.startContainer : info.rg.startContainer.parentElement;
      return !first || first.contains(el) || el === info.box;
    })();
  }
  function atBoxEnd(info) {
    if (!info.rg.collapsed) return false;
    const r = document.createRange();
    r.selectNodeContents(info.box);
    try { r.setStart(info.rg.endContainer, info.rg.endOffset); } catch (e) { return false; }
    if (r.toString().length !== 0) return false;
    const kids = contentChildren(info.box);
    const last = kids[kids.length - 1];
    const el = info.rg.endContainer.nodeType === 1 ? info.rg.endContainer : info.rg.endContainer.parentElement;
    return !last || last.contains(el) || el === info.box;
  }
  function placeAtEnd(el, box) {
    try { box.focus({ preventScroll: true }); } catch (e) { box.focus(); }
    const r = document.createRange();
    r.selectNodeContents(el);
    r.collapse(false);
    // <br> ile biten boş paragrafta <br>'nin önüne
    if (el.lastChild && el.lastChild.nodeName === 'BR') { r.setStartBefore(el.lastChild); r.collapse(true); }
    const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
  }
  function placeAtStart(el, box) {
    try { box.focus({ preventScroll: true }); } catch (e) { box.focus(); }
    const r = document.createRange();
    r.selectNodeContents(el);
    r.collapse(true);
    const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
  }
  function lineRect(rg) {
    const rs = rg.getClientRects();
    if (rs.length) return rs[0];
    const el = rg.startContainer.nodeType === 1 ? rg.startContainer : rg.startContainer.parentElement;
    if (el && el.nodeType === 1 && el.childNodes[rg.startOffset] && el.childNodes[rg.startOffset].getBoundingClientRect) return el.childNodes[rg.startOffset].getBoundingClientRect();
    return el ? el.getBoundingClientRect() : null;
  }

  function onKeyDown(e) {
    if (e.defaultPrevented || e.isComposing || e.ctrlKey || e.metaKey || e.altKey || isMobileFlow()) return;
    if (!['Backspace', 'Delete', 'ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End'].includes(e.key)) return;
    const info = caretInfo();
    if (!info || info.idx < 0) return;
    const { box, idx, all } = info;

    if (e.key === 'Home' || e.key === 'End') {
      const sel = window.getSelection();
      if (!sel || !sel.focusNode) return;
      const focusEl = sel.focusNode.nodeType === 1 ? sel.focusNode : sel.focusNode.parentElement;
      const p = focusEl && focusEl.closest ? focusEl.closest('p, li, h1, h2, h3, h4, h5, h6') : null;
      if (!p || !box.contains(p)) return;
      const walker = document.createTreeWalker(p, NodeFilter.SHOW_TEXT, {
        acceptNode(n) {
          const pe = n.parentElement;
          if (pe && pe.closest && pe.closest('.udf-list-prefix, .udf-tab-space')) return NodeFilter.FILTER_REJECT;
          return n.nodeValue && n.nodeValue.length > 0 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
        }
      });
      const tNodes = [];
      let tn;
      while ((tn = walker.nextNode())) tNodes.push(tn);
      if (!tNodes.length) return;

      const pRect = p.getBoundingClientRect();
      const lh = parseFloat(getComputedStyle(p).lineHeight) || 18;
      const scale = box.offsetHeight ? (box.getBoundingClientRect().height / box.offsetHeight) || 1 : 1;
      const isSingleLine = pRect.height <= lh * scale * 1.65;

      let targetNode, targetOff;
      if (isSingleLine) {
        if (e.key === 'Home') {
          targetNode = tNodes[0];
          targetOff = 0;
        } else {
          targetNode = tNodes[tNodes.length - 1];
          targetOff = targetNode.nodeValue.length;
        }
      } else {
        const focusRect = lineRect(info.rg) || pRect;
        const lineMidY = (focusRect.top + focusRect.bottom) / 2;
        const bandTol = Math.max(6, lh * scale * 0.55);
        const r = document.createRange();
        let firstOnLine = null;
        let lastOnLine = null;
        for (const t of tNodes) {
          const len = t.nodeValue.length;
          for (let ci = 0; ci < len; ci++) {
            r.setStart(t, ci);
            r.setEnd(t, ci + 1);
            const rc = r.getBoundingClientRect();
            if (!rc || (!rc.height && !rc.width)) continue;
            const cy = (rc.top + rc.bottom) / 2;
            if (Math.abs(cy - lineMidY) <= bandTol) {
              if (!firstOnLine) firstOnLine = { node: t, off: ci };
              lastOnLine = { node: t, off: ci + 1 };
            }
          }
        }
        if (e.key === 'Home') {
          targetNode = firstOnLine ? firstOnLine.node : tNodes[0];
          targetOff = firstOnLine ? firstOnLine.off : 0;
        } else {
          targetNode = lastOnLine ? lastOnLine.node : tNodes[tNodes.length - 1];
          targetOff = lastOnLine ? lastOnLine.off : targetNode.nodeValue.length;
        }
      }
      e.preventDefault();
      if (e.shiftKey && typeof sel.extend === 'function') {
        if (isSingleLine) {
          const aEl = sel.anchorNode && (sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement);
          if (!aEl || !p.contains(aEl) || (aEl.closest && aEl.closest('.udf-tab-space'))) {
            const startN = e.key === 'End' ? tNodes[0] : tNodes[tNodes.length - 1];
            const startO = e.key === 'End' ? 0 : startN.nodeValue.length;
            sel.collapse(startN, startO);
          }
        }
        sel.extend(targetNode, targetOff);
      } else {
        sel.collapse(targetNode, targetOff);
      }
      return;
    }

    if (e.key === 'Backspace' && idx > 0 && atBoxStart(info)) {
      const prevBox = all[idx - 1];
      const prevKids = contentChildren(prevBox);
      const last = prevKids[prevKids.length - 1];
      const first = contentChildren(box)[0];
      e.preventDefault();
      if (typeof markDocumentUserEdited === 'function') markDocumentUserEdited();
      if (!last) { placeAtStart(first, box); return; }
      if (isHardBreak(last)) { last.remove(); schedule(0); return; }
      if (first && /^(P|DIV|LI|H[1-6])$/.test(first.tagName) && /^(P|DIV|LI|H[1-6])$/.test(last.tagName)) {
        const caretChar = last.textContent.length;
        if (last.lastChild && last.lastChild.nodeName === 'BR') last.lastChild.remove();
        if (isEmptyPara(first)) first.remove();
        else { while (first.firstChild) last.appendChild(first.firstChild); first.remove(); }
        if (last.hasAttribute('data-split-mb')) { last.style.marginBottom = last.getAttribute('data-split-mb'); last.removeAttribute('data-split-mb'); }
        if (!last.firstChild) last.appendChild(document.createElement('br'));
        // imleci birleşim noktasına koy
        try { prevBox.focus({ preventScroll: true }); } catch (er) { prevBox.focus(); }
        const w = document.createTreeWalker(last, NodeFilter.SHOW_TEXT); let acc = 0, t, done = false;
        while ((t = w.nextNode())) { if (acc + t.textContent.length >= caretChar) { window.getSelection().collapse(t, caretChar - acc); done = true; break; } acc += t.textContent.length; }
        if (!done) placeAtEnd(last, prevBox);
      } else {
        placeAtEnd(last, prevBox);
      }
      schedule(0);
      return;
    }

    if (e.key === 'Delete' && idx < all.length - 1 && atBoxEnd(info)) {
      const nextBox = all[idx + 1];
      const first = contentChildren(nextBox)[0];
      const kids = contentChildren(box);
      const last = kids[kids.length - 1];
      if (!first || !last) return;
      e.preventDefault();
      if (typeof markDocumentUserEdited === 'function') markDocumentUserEdited();
      const sel = window.getSelection();
      const keepNode = sel.anchorNode, keepOff = sel.anchorOffset;
      if (/^(P|DIV|LI|H[1-6])$/.test(first.tagName) && /^(P|DIV|LI|H[1-6])$/.test(last.tagName)) {
        if (!isEmptyPara(first)) {
          if (last.lastChild && last.lastChild.nodeName === 'BR') last.lastChild.remove();
          while (first.firstChild) last.appendChild(first.firstChild);
        }
        first.remove();
      } else if (isHardBreak(first)) first.remove();
      try { sel.collapse(keepNode, Math.min(keepOff, keepNode.nodeType === 3 ? keepNode.textContent.length : keepNode.childNodes.length)); } catch (er) {}
      schedule(0);
      return;
    }

    if ((e.key === 'ArrowDown' || e.key === 'PageDown') && idx < all.length - 1) {
      const kids = contentChildren(box);
      const last = kids[kids.length - 1];
      const r = lineRect(info.rg);
      if (!last || !r) return;
      const lr = last.getBoundingClientRect();
      const lh = parseFloat(getComputedStyle(last).lineHeight) || 18;
      const scale = box.offsetHeight ? box.getBoundingClientRect().height / box.offsetHeight : 1;
      if (e.key === 'PageDown' || r.bottom >= lr.bottom - lh * scale * 0.75) {
        const first = contentChildren(all[idx + 1])[0];
        if (!first) return;
        e.preventDefault();
        placeAtStart(first, all[idx + 1]);
        keepCaretVisible();
      }
      return;
    }
    if ((e.key === 'ArrowUp' || e.key === 'PageUp') && idx > 0) {
      const first = contentChildren(box)[0];
      const r = lineRect(info.rg);
      if (!first || !r) return;
      const fr = first.getBoundingClientRect();
      const lh = parseFloat(getComputedStyle(first).lineHeight) || 18;
      const scale = box.offsetHeight ? box.getBoundingClientRect().height / box.offsetHeight : 1;
      if (e.key === 'PageUp' || r.top <= fr.top + lh * scale * 0.75) {
        const pk = contentChildren(all[idx - 1]);
        const last = pk[pk.length - 1];
        if (!last) return;
        e.preventDefault();
        placeAtEnd(last, all[idx - 1]);
        keepCaretVisible();
      }
    }
  }


  // ---------------------------------------------------------------- belge geneli seçim (Ctrl+A, sayfalar arası)
  // Her sayfa ayrı contenteditable olduğundan tarayıcının "tümünü seç"i yalnız odaklı sayfada kalır ve
  // sayfalar arası seçimde sil / yaz / yapıştır / kes / biçimlendir hiç çalışmaz. Bu katman seçimi sayfa
  // gövdelerine böler: her işlem her sayfanın kendi parçasına uygulanır (üst/altbilgiler hiç dokunulmaz).
  const BLOK = 'p, li, h1, h2, h3, h4, h5, h6, div.udf-paragraph, td, th';
  function govdeOf(n) {
    const el = n && (n.nodeType === 1 ? n : n.parentElement);
    const b = el && el.closest ? el.closest('.page-body-box') : null;
    return b && b.closest('.a4-sheet-page') ? b : null;
  }
  /** Seçim birden fazla sayfa gövdesine yayılıyorsa {aralik, parcalar:[{govde, aralik}]} döner. */
  function sayfalarArasi() {
    const sel = window.getSelection();
    if (!sel || !sel.rangeCount || sel.isCollapsed) return null;
    const rg = sel.getRangeAt(0);
    const all = bodies();
    let i0 = all.indexOf(govdeOf(rg.startContainer)), i1 = all.indexOf(govdeOf(rg.endContainer));
    // Başlangıç/bitiş gövde dışında (sayfa boşluğu, altbilgi) kalmışsa en yakın gövdeye kenetlenir
    if (i0 < 0) i0 = all.findIndex(b => rg.comparePoint(b, 0) >= 0 && rg.intersectsNode(b));
    if (i1 < 0) { for (let i = all.length - 1; i >= 0; i--) if (rg.intersectsNode(all[i])) { i1 = i; break; } }
    if (i0 < 0 || i1 < 0 || i1 <= i0) return null;
    const parcalar = [];
    for (let i = i0; i <= i1; i++) {
      const b = all[i], r = document.createRange();
      r.selectNodeContents(b);
      if (i === i0 && govdeOf(rg.startContainer) === b) r.setStart(rg.startContainer, rg.startOffset);
      if (i === i1 && govdeOf(rg.endContainer) === b) r.setEnd(rg.endContainer, rg.endOffset);
      parcalar.push({ govde: b, aralik: r });
    }
    return { aralik: rg, parcalar };
  }
  function secimYap(r) { const s = window.getSelection(); s.removeAllRanges(); s.addRange(r); }
  /**
   * Tüm belgeyi seçer (bütün sayfalar).
   * v4.9.1: Her sayfa ayrı contenteditable olduğu için Chromium GÖRÜNÜR seçimi odaktaki sayfaya kırpıyordu
   * (aralık tüm sayfaları kapsasa da yalnız o sayfa boyanıyor, Selection.toString() yalnız o sayfayı veriyordu).
   * Seçim sürdükçe sayfa kapsayıcısı geçici olarak tek düzenleme alanı yapılır; seçim tek sayfaya inince
   * (imleç konunca, tıklanınca) eski haline döner. / The container temporarily becomes the single editing host.
   */
  function tekAlanAc() {
    const c = container();
    if (!c || c.hasAttribute('data-tum-secim')) return;
    c.setAttribute('data-tum-secim', c.getAttribute('contenteditable') || '');
    c.setAttribute('contenteditable', 'true');
    // Sayfa araları, üst/altbilgi alanları düzenlenemez kalsın
    c.querySelectorAll('.' + SKIP_CLASSES.join(', .') + ', .page-header-box, .page-footer-box').forEach(n => {
      if (!n.hasAttribute('contenteditable')) { n.setAttribute('contenteditable', 'false'); n.setAttribute('data-tum-secim-kilit', '1'); }
    });
  }
  function tekAlanKapat() {
    const c = container();
    if (!c || !c.hasAttribute('data-tum-secim')) return;
    const eski = c.getAttribute('data-tum-secim');
    c.removeAttribute('data-tum-secim');
    if (eski) c.setAttribute('contenteditable', eski); else c.removeAttribute('contenteditable');
    c.querySelectorAll('[data-tum-secim-kilit]').forEach(n => { n.removeAttribute('contenteditable'); n.removeAttribute('data-tum-secim-kilit'); });
  }
  document.addEventListener('selectionchange', () => {
    const c = container();
    if (!c || !c.hasAttribute('data-tum-secim')) return;
    const s = window.getSelection();
    if (!s || !s.rangeCount || s.isCollapsed) { tekAlanKapat(); return; }
    const r = s.getRangeAt(0);
    if (govdeOf(r.startContainer) && govdeOf(r.startContainer) === govdeOf(r.endContainer)) tekAlanKapat();
  });
  function tumunuSec() {
    const all = bodies();
    if (!all.length) return false;
    if (all.length > 1) tekAlanAc();
    const r = document.createRange();
    r.setStart(all[0], 0);
    r.setEnd(all[all.length - 1], all[all.length - 1].childNodes.length);
    try { (all.length > 1 ? container() : all[0]).focus({ preventScroll: true }); } catch (e) { /* eski tarayıcı */ }
    secimYap(r);
    return true;
  }
  /** Seçili içeriği (yalnız gövdelerden, sayfa sırasıyla) HTML + düz metin olarak verir. */
  function secimIcerigi(x) {
    const kap = document.createElement('div');
    x.parcalar.forEach(({ aralik }) => {
      const parca = aralik.cloneContents();
      parca.querySelectorAll && parca.querySelectorAll('.' + SKIP_CLASSES.join(', .')).forEach(n => n.remove());
      kap.appendChild(parca);
    });
    // Sayfa sınırında bölünmüş paragrafın iki parçası tek paragraf olarak kopyalanır
    kap.querySelectorAll('[data-split-continuation]').forEach(n => {
      const onceki = n.previousElementSibling;
      if (onceki && onceki.tagName === n.tagName) { while (n.firstChild) onceki.appendChild(n.firstChild); n.remove(); }
    });
    // Düz metin: her blok (paragraf, liste öğesi, tablo satırı) ayrı satır
    const metin = [];
    const yaz = (n) => {
      n.childNodes.forEach(c => {
        if (c.nodeType === 3) { metin.length ? metin[metin.length - 1] += c.nodeValue : metin.push(c.nodeValue); return; }
        if (c.nodeType !== 1) return;
        if (c.tagName === 'BR') { metin.push(''); return; }
        const blok = /^(P|DIV|LI|H[1-6]|TR|TABLE|UL|OL)$/.test(c.tagName);
        if (blok) metin.push('');
        yaz(c);
        if (c.tagName === 'TD' || c.tagName === 'TH') metin[metin.length - 1] += '\t';
      });
    };
    yaz(kap);
    return { html: kap.innerHTML, metin: metin.map(t => t.replace(/\u200b/g, '').replace(/\t$/, '')).join('\n').replace(/^\n+|\n+$/g, '') };
  }
  /** Sayfalar arası seçimi siler; imleci silinen yerin başına koyar (Word gibi uç paragraflar birleşir). */
  function sayfalarArasiSil(x) {
    const ilk = x.parcalar[0], son = x.parcalar[x.parcalar.length - 1];
    const basEl = ilk.aralik.startContainer.nodeType === 1 ? ilk.aralik.startContainer : ilk.aralik.startContainer.parentElement;
    const basBlok = basEl && basEl.closest ? basEl.closest(BLOK) : null;
    const sonEl = son.aralik.endContainer.nodeType === 1 ? son.aralik.endContainer : son.aralik.endContainer.parentElement;
    const sonBlok = sonEl && sonEl.closest ? sonEl.closest(BLOK) : null;
    const sonKismi = sonBlok && son.govde.contains(sonBlok) && (() => {
      const r = document.createRange(); r.selectNodeContents(sonBlok); r.setStart(son.aralik.endContainer, son.aralik.endOffset);
      return r.toString().length > 0;
    })();
    busy = true;
    try {
      x.parcalar.forEach(({ aralik }) => aralik.deleteContents());
      // Bitişteki paragrafın kalan kısmı başlangıç paragrafına eklenir
      if (basBlok && sonBlok && sonKismi && basBlok !== sonBlok && basBlok.isConnected && sonBlok.isConnected &&
          ilk.govde.contains(basBlok) && !sonBlok.closest('td, th')) {
        if (basBlok.lastChild && basBlok.lastChild.nodeName === 'BR') basBlok.lastChild.remove();
        while (sonBlok.firstChild) basBlok.appendChild(sonBlok.firstChild);
        sonBlok.remove();
      }
      // Boş kalan gövdeler/paragraflar
      x.parcalar.forEach(({ govde }) => {
        govde.querySelectorAll(BLOK).forEach(b => { if (!b.textContent && !b.querySelector('img, br, table, hr')) b.appendChild(document.createElement('br')); });
        if (!contentChildren(govde).length) govde.innerHTML = '<p><br></p>';
      });
    } finally { busy = false; }
    const r = document.createRange();
    if (basBlok && basBlok.isConnected) {
      try { r.setStart(ilk.aralik.startContainer, Math.min(ilk.aralik.startOffset, ilk.aralik.startContainer.nodeType === 3 ? ilk.aralik.startContainer.length : ilk.aralik.startContainer.childNodes.length)); }
      catch (e) { r.selectNodeContents(basBlok); }
      if (!basBlok.contains(r.startContainer) && r.startContainer !== basBlok) r.selectNodeContents(basBlok);
    } else {
      const k = contentChildren(ilk.govde)[0] || ilk.govde;
      r.selectNodeContents(k);
    }
    r.collapse(true);
    try { ilk.govde.focus({ preventScroll: true }); } catch (e) { ilk.govde.focus(); }
    secimYap(r);
    schedule(0);
  }
  function kaydet() { if (window.CanHistory) { try { window.CanHistory.commit(); } catch (e) { /* geçmiş yoksa */ } } }

  // Biçimlendirme (kalın, italik, yazı tipi, boyut, hizalama, renk…) her sayfanın parçasına ayrı uygulanır
  const ozgunExec = document.execCommand.bind(document);
  const BICIMSIZ = new Set(['copy', 'cut', 'paste', 'undo', 'redo', 'selectall', 'inserttext', 'inserthtml', 'insertparagraph',
    'insertlinebreak', 'delete', 'forwarddelete', 'insertimage', 'inserthorizontalrule']);
  document.execCommand = function (komut, ui, deger) {
    const k = String(komut || '').toLowerCase();
    if (k === 'selectall' && bodies().length) { if (tumunuSec()) return true; }
    const x = !BICIMSIZ.has(k) && sayfalarArasi();
    if (!x) return ozgunExec(komut, ui, deger);
    let sonuc = false, bas = null, bit = null;
    busy = true;
    try {
      x.parcalar.forEach(({ govde, aralik }, i) => {
        try { govde.focus({ preventScroll: true }); } catch (e) { /* odak yok */ }
        secimYap(aralik);
        sonuc = ozgunExec(komut, ui, deger) || sonuc;
        const s = window.getSelection();
        if (s.rangeCount) {
          const r = s.getRangeAt(0);
          if (i === 0) bas = [r.startContainer, r.startOffset];
          bit = [r.endContainer, r.endOffset];
        }
      });
    } finally { busy = false; }
    try {
      const r = document.createRange();
      r.setStart(bas[0], bas[1]); r.setEnd(bit[0], bit[1]);
      secimYap(r);
    } catch (e) { /* seçim yeniden kurulamadı */ }
    schedule(0);
    return sonuc;
  };

  function secimKlavye(e) {
    if (e.defaultPrevented || e.isComposing) return;
    const mod = e.ctrlKey || e.metaKey;
    if (mod && !e.altKey && !e.shiftKey && (e.key === 'a' || e.key === 'A' || e.code === 'KeyA')) {
      // v4.9.1: mobil/tablet (harici klavye) dahil Ctrl+A TÜM belgeyi seçer; eskiden mobilde yalnız odaklı sayfa seçiliyordu
      if (!govdeOf(document.activeElement) && !govdeOf((window.getSelection() || {}).anchorNode)) return;
      e.preventDefault();
      tumunuSec();
      return;
    }
    const x = sayfalarArasi();
    if (!x) return;
    if (e.key === 'Backspace' || e.key === 'Delete') {
      e.preventDefault(); sayfalarArasiSil(x); kaydet(); return;
    }
    if (mod && !e.altKey && !e.shiftKey) {
      // Tarayıcının yerleşik biçim kısayolları yalnız odaklı sayfaya uygulanır: tüm parçalara biz uygularız
      const kisayol = { b: 'bold', i: 'italic', u: 'underline' }[(e.key || '').toLowerCase()];
      if (kisayol) { e.preventDefault(); document.execCommand(kisayol, false, null); kaydet(); }
      return;
    }
    if (mod || e.altKey) return;
    if (e.key === 'Enter') {
      e.preventDefault(); sayfalarArasiSil(x); ozgunExec(e.shiftKey ? 'insertLineBreak' : 'insertParagraph'); kaydet(); return;
    }
    if (e.key && e.key.length === 1) {
      e.preventDefault(); sayfalarArasiSil(x); ozgunExec('insertText', false, e.key); kaydet();
    }
  }
  function secimKopyala(e, kes) {
    const x = sayfalarArasi();
    if (!x || !e.clipboardData) return;
    const ic = secimIcerigi(x);
    e.preventDefault();
    e.clipboardData.setData('text/html', ic.html);
    e.clipboardData.setData('text/plain', ic.metin);
    if (kes) { sayfalarArasiSil(x); kaydet(); }
  }
  function secimYapistir(e) {
    const x = sayfalarArasi();
    if (!x || !e.clipboardData) return;
    e.preventDefault();
    const html = e.clipboardData.getData('text/html'), metin = e.clipboardData.getData('text/plain');
    sayfalarArasiSil(x);
    if (html) ozgunExec('insertHTML', false, html.replace(/<!--(Start|End)Fragment-->/g, ''));
    else if (metin) ozgunExec('insertText', false, metin);
    kaydet();
  }
  function secimGirdi(e) {
    // IME / sanal klavye / sürükle-bırak: keydown yakalanmadıysa beforeinput'ta seçim önce silinir
    if (e.defaultPrevented) return;
    const x = sayfalarArasi();
    if (!x) return;
    const t = e.inputType || '';
    if (/^(insert|delete)/.test(t) && !/^insertFromPaste/.test(t)) {
      e.preventDefault();
      sayfalarArasiSil(x);
      if (t === 'insertText' && e.data) ozgunExec('insertText', false, e.data);
      else if (t === 'insertParagraph') ozgunExec('insertParagraph');
      else if (t === 'insertLineBreak') ozgunExec('insertLineBreak');
      kaydet();
    }
  }

  // ---------------------------------------------------------------- bağlama
  function attach() {
    const c = container();
    if (!c || observer) return;
    observer = new MutationObserver((muts) => {
      if (busy) return;
      for (const m of muts) {
        const t = m.target.nodeType === 1 ? m.target : m.target.parentElement;
        if (t && t.closest && t.closest('.page-body-box')) { schedule(); return; }
        if (m.type === 'childList' && t === c) return; // tam yeniden inşa: updatePagination zaten düzenledi
      }
    });
    observer.observe(c, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['style', 'class'] });
    document.addEventListener('keydown', secimKlavye, true);
    document.addEventListener('keydown', onKeyDown, true);
    document.addEventListener('copy', e => secimKopyala(e, false), true);
    document.addEventListener('cut', e => secimKopyala(e, true), true);
    document.addEventListener('paste', secimYapistir, true);
    document.addEventListener('beforeinput', secimGirdi, true);
    // Kullanıcı niyeti: yazma mı kaydırma mı? (keepCaretVisible yalnızca yazarken)
    const yazdi = () => { lastEditTs = Date.now(); };
    const kaydirdi = () => { lastScrollTs = Date.now(); };
    document.addEventListener('keydown', yazdi, true);
    document.addEventListener('beforeinput', yazdi, true);
    document.addEventListener('compositionend', yazdi, true);
    const wrap = document.getElementById('page-wrapper');
    if (wrap) {
      wrap.addEventListener('touchmove', kaydirdi, { passive: true });
      wrap.addEventListener('wheel', kaydirdi, { passive: true });
      // kaydırma çubuğunu fareyle sürükleme: olayın hedefi sarmalayıcının kendisi
      wrap.addEventListener('mousedown', (e) => { if (e.target === wrap) kaydirdi(); }, { passive: true });
    }
    window.addEventListener('resize', () => schedule(200));
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => schedule(0));
  }

  window.CanFlow = { reflow, schedule, attach, tumunuSec, sayfalarArasi };
  window.liveReflow = reflow;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(attach, 0));
  else setTimeout(attach, 0);
})();
