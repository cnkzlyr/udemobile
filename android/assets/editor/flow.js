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
    cont.appendChild(frag);
    cont.setAttribute('data-split-continuation', 'true');
    cont.style.textIndent = '0cm';
    cont.style.marginTop = '0px';
    cont.style.paddingTop = '0px';
    if (!p.hasAttribute('data-orig-mb')) p.setAttribute('data-orig-mb', p.style.marginBottom || '');
    p.style.marginBottom = '0px';
    return cont;
  }
  function mergeContinuation(head, cont) {
    while (cont.firstChild) head.appendChild(cont.firstChild);
    cont.remove();
    if (head.hasAttribute('data-orig-mb')) {
      head.style.marginBottom = head.getAttribute('data-orig-mb');
      head.removeAttribute('data-orig-mb');
    }
    head.normalize();
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
  function reflow() {
    if (busy || isMobileFlow()) return false;
    const c = container();
    if (!c) return false;
    let all = bodies();
    if (!all.length) return false;
    busy = true;
    normalizeBoxes();
    const emptyCaretBlock = caretEmptyBlock();
    const saved = saveCaret();
    const dbg = window.__flowDebug ? (m) => window.__flowDebug.push(m) : null;
    if (dbg) { const s0 = window.getSelection(); const r0 = s0.rangeCount ? s0.getRangeAt(0) : null; dbg('start saved=' + JSON.stringify(saved) + ' empty=' + !!emptyCaretBlock + ' sel=' + (s0.anchorNode && s0.anchorNode.nodeName) + JSON.stringify((s0.anchorNode && s0.anchorNode.textContent || '').slice(0, 10)) + '@' + s0.anchorOffset + ' range=' + (r0 && r0.startContainer.nodeName + JSON.stringify((r0.startContainer.textContent || '').slice(0, 10)) + '@' + r0.startOffset) + ' stack=' + new Error().stack.split('\n').slice(2, 4).map(x => x.trim()).join('<')); }
    let changed = false;
    try {
      for (let i = 0; i < all.length; i++) {
        const box = all[i];
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
          const next = all[i + 1];
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
      if (changed) renumber();
    } finally {
      if (changed) {
        if (emptyCaretBlock && emptyCaretBlock.isConnected) {
          const box = emptyCaretBlock.closest('.page-body-box');
          if (saved && saved.hadFocus && document.activeElement !== box) { try { box.focus({ preventScroll: true }); } catch (e) {} }
          try { window.getSelection().collapse(emptyCaretBlock, 0); } catch (e) {}
        } else {
          restoreCaret(saved);
        }
        if (dbg) { const s2 = window.getSelection(); dbg('restored -> ' + (s2.anchorNode && (s2.anchorNode.textContent || '').slice(0, 24)) + '@' + s2.anchorOffset); }
        keepCaretVisible();
      }
      busy = false;
    }
    return changed;
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
    if (!['Backspace', 'Delete', 'ArrowUp', 'ArrowDown', 'PageUp', 'PageDown'].includes(e.key)) return;
    const info = caretInfo();
    if (!info || info.idx < 0) return;
    const { box, idx, all } = info;

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
        if (last.hasAttribute('data-orig-mb')) { last.style.marginBottom = last.getAttribute('data-orig-mb'); last.removeAttribute('data-orig-mb'); }
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
    document.addEventListener('keydown', onKeyDown, true);
    window.addEventListener('resize', () => schedule(200));
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => schedule(0));
  }

  window.CanFlow = { reflow, schedule, attach };
  window.liveReflow = reflow;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(attach, 0));
  else setTimeout(attach, 0);
})();
