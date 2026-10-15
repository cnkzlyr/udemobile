/* CanEditor — Geri Al / Yinele (anlık görüntü tabanlı)
 *
 * Tarayıcının yerel execCommand('undo') geçmişi, kod ile yapılan DOM değişikliklerinde
 * (sekme hizalama, cetvel durakları, biçim boyacısı, AI formatlama, şablon ekleme...) bozulur.
 * Bu modül editördeki HER değişikliği MutationObserver ile yakalar, belge HTML'ini
 * (otomatik sayfa bölücüler hariç) ve imleç konumunu saklar.
 */
(function () {
  'use strict';

  const MAX_STEPS = 300;
  const QUIET_MS = 400; // Bu kadar duraksayınca yazılanlar tek adım sayılır

  const H = { stack: [], idx: -1, timer: null, suppress: false, observer: null, ed: null };

  function ed() {
    if (!H.ed) H.ed = document.getElementById('editor-content');
    return H.ed;
  }

  function cleanHtml() {
    const e = ed();
    if (!e) return '';
    const c = e.cloneNode(true);
    c.querySelectorAll('.auto-page-break').forEach(n => n.remove());
    return c.innerHTML;
  }

  function textOffset(node, off) {
    const e = ed();
    const r = document.createRange();
    r.selectNodeContents(e);
    try { r.setEnd(node, off); } catch (x) { return 0; }
    const frag = r.cloneContents();
    frag.querySelectorAll && frag.querySelectorAll('.auto-page-break').forEach(n => n.remove());
    return (frag.textContent || '').length;
  }

  function captureSelection() {
    const e = ed();
    const sel = window.getSelection();
    if (!e || !sel || sel.rangeCount === 0 || !e.contains(sel.anchorNode) || !e.contains(sel.focusNode)) return null;
    return {
      a: textOffset(sel.anchorNode, sel.anchorOffset),
      f: textOffset(sel.focusNode, sel.focusOffset)
    };
  }

  function locate(offset) {
    const e = ed();
    const walker = document.createTreeWalker(e, NodeFilter.SHOW_TEXT, {
      acceptNode: n => (n.parentNode && n.parentNode.closest && n.parentNode.closest('.auto-page-break'))
        ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT
    });
    let n, left = offset, last = null;
    while ((n = walker.nextNode())) {
      last = n;
      const len = n.nodeValue.length;
      if (left <= len) return { node: n, offset: left };
      left -= len;
    }
    return last ? { node: last, offset: last.nodeValue.length } : { node: e, offset: 0 };
  }

  function restoreSelection(s) {
    const e = ed();
    if (!e) return;
    try {
      e.focus({ preventScroll: true });
      const sel = window.getSelection();
      const r = document.createRange();
      if (!s) {
        r.selectNodeContents(e);
        r.collapse(false);
      } else {
        const a = locate(s.a), f = locate(s.f);
        r.setStart(a.node, a.offset);
        r.setEnd(a.node, a.offset);
        sel.removeAllRanges();
        sel.addRange(r);
        if (s.f !== s.a) sel.extend(f.node, f.offset);
        return;
      }
      sel.removeAllRanges();
      sel.addRange(r);
    } catch (x) { /* seçim geri yüklenemezse sessizce geç */ }
  }

  function commit() {
    clearTimeout(H.timer);
    H.timer = null;
    if (H.suppress || !ed()) return false;
    const html = cleanHtml();
    const cur = H.stack[H.idx];
    if (cur && cur.html === html) {
      cur.sel = captureSelection() || cur.sel;
      return false;
    }
    H.stack.length = H.idx + 1; // yinele dalını at
    H.stack.push({ html, sel: captureSelection() });
    if (H.stack.length > MAX_STEPS) H.stack.shift();
    H.idx = H.stack.length - 1;
    return true;
  }

  function schedule() {
    if (H.suppress) return;
    clearTimeout(H.timer);
    H.timer = setTimeout(commit, QUIET_MS);
  }

  function apply(entry) {
    const e = ed();
    H.suppress = true;
    try {
      e.innerHTML = entry.html;
      restoreSelection(entry.sel);
      if (H.observer) H.observer.takeRecords();
    } finally {
      H.suppress = false;
    }
    try { if (typeof updatePagination === 'function') updatePagination(); } catch (x) {}
    try { if (typeof updateRulerFromActiveParagraph === 'function') updateRulerFromActiveParagraph(); } catch (x) {}
    try { if (typeof updateCounts === 'function') updateCounts(); } catch (x) {}
    try { if (typeof showEditorToast === 'function') showEditorToast(H.idx === 0 ? '↶ En eski sürüme dönüldü' : '✓ Geri alındı / yinelendi'); } catch (x) {}
  }

  function undo() {
    commit(); // bekleyen yazım varsa önce onu bir adım olarak kaydet
    if (H.idx <= 0) return false;
    H.idx--;
    apply(H.stack[H.idx]);
    return true;
  }

  function redo() {
    commit();
    if (H.idx >= H.stack.length - 1) return false;
    H.idx++;
    apply(H.stack[H.idx]);
    return true;
  }

  function reset() {
    clearTimeout(H.timer);
    H.stack = [];
    H.idx = -1;
    H.suppress = false;
    if (H.observer) H.observer.takeRecords();
    commit();
  }

  // Odak üst/altbilgideyse tarayıcının yerel geçmişi kullanılsın
  function focusInBody() {
    const a = document.activeElement, e = ed();
    return !a || a === document.body || (e && (a === e || e.contains(a)));
  }

  function init() {
    const e = ed();
    if (!e || H.observer) return;
    H.observer = new MutationObserver(records => {
      // Otomatik sayfa bölücü değişiklikleri kullanıcı değişikliği değildir: zamanlayıcıyı uzatmasın
      const real = records.some(r => {
        const t = r.target && (r.target.nodeType === 1 ? r.target : r.target.parentElement);
        if (t && t.closest && t.closest('.auto-page-break')) return false;
        // Sekme aralıklarının otomatik yeniden hesaplanması (genişlik) kullanıcı değişikliği değildir
        if (r.type === 'attributes' && t && t.classList && t.classList.contains('udf-tab-space')) return false;
        if (r.type === 'characterData' && t && t.classList && t.classList.contains('udf-tab-space')) return false;
        const nodes = Array.from(r.addedNodes).concat(Array.from(r.removedNodes));
        if (nodes.length && nodes.every(n => n.nodeType === 1 && n.classList && n.classList.contains('auto-page-break'))) return false;
        return true;
      });
      if (real) schedule();
    });
    H.observer.observe(e, { subtree: true, childList: true, characterData: true, attributes: true });
    commit();

    document.addEventListener('keydown', ev => {
      if (!(ev.ctrlKey || ev.metaKey) || ev.altKey) return;
      const k = (ev.key || '').toLowerCase();
      const isUndo = k === 'z' && !ev.shiftKey;
      const isRedo = k === 'y' || (k === 'z' && ev.shiftKey);
      if (!isUndo && !isRedo) return;
      if (!focusInBody()) return;
      ev.preventDefault();
      ev.stopPropagation();
      isUndo ? undo() : redo();
    }, true);

    // Ekran klavyesi / sistem menüsü geri al
    e.addEventListener('beforeinput', ev => {
      if (ev.inputType === 'historyUndo') { ev.preventDefault(); undo(); }
      else if (ev.inputType === 'historyRedo') { ev.preventDefault(); redo(); }
    });
  }

  window.CanHistory = { undo, redo, reset, commit, init, get size() { return H.stack.length; }, get index() { return H.idx; } };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
