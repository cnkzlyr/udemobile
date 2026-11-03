/* CanEditor — Geri Al / Yinele (Anlık Görüntü Tabanlı Geçmiş Motoru)
 *
 * Çok sayfalı A4 mimarisi (.a4-sheet-page / .page-body-box) ile %100 uyumlu.
 * Tüm sayfaların gövde içeriğini kayıpsız olarak saklar ve geri yükler.
 */
(function () {
  'use strict';

  const MAX_STEPS = 100;
  const QUIET_MS = 350; // Yazım duraklaması eşiği (ms)

  const H = {
    stack: [],
    idx: -1,
    timer: null,
    suppress: false,
    observer: null
  };

  let isUserAction = false;

  // Tüm sayfalardaki temiz gövde HTML'ini birleştirerek anlık görüntü alır
  function getDocHtml() {
    if (typeof getHtmlContent === 'function') {
      try {
        const h = getHtmlContent();
        if (h && h.trim()) return h;
      } catch (e) {}
    }
    const bodyBoxes = Array.from(document.querySelectorAll('.page-body-box'));
    if (bodyBoxes.length > 0) {
      return bodyBoxes.map(b => {
        const c = b.cloneNode(true);
        c.querySelectorAll('.auto-page-break, .page-break-desk-gap, .page-desk-gap').forEach(n => n.remove());
        return c.innerHTML;
      }).join('');
    }
    const ed = document.getElementById('editor-content');
    if (!ed) return '';
    const clone = ed.cloneNode(true);
    clone.querySelectorAll('.auto-page-break, .page-break-desk-gap, .page-desk-gap').forEach(n => n.remove());
    return clone.innerHTML;
  }

  function commit(isManual) {
    clearTimeout(H.timer);
    H.timer = null;
    if (H.suppress) return false;

    const html = getDocHtml();
    // Tamamen boş başlangıç içeriğini ezme
    if (!html && H.stack.length > 0) return false;

    const cur = H.stack[H.idx];
    if (cur && cur.html === html) {
      return false;
    }

    // Kullanıcı geri almışken otomatik commit gelirse yinele dalını kesme
    if (!isManual && !isUserAction && H.idx < H.stack.length - 1) {
      return false;
    }
    isUserAction = false;

    // Yeni dal başlat: ileri adımları sil
    H.stack.length = H.idx + 1;
    H.stack.push({ html });
    if (H.stack.length > MAX_STEPS) H.stack.shift();
    H.idx = H.stack.length - 1;
    return true;
  }

  function schedule(fromUser) {
    if (H.suppress) return;
    if (fromUser) isUserAction = true;
    clearTimeout(H.timer);
    H.timer = setTimeout(() => commit(false), QUIET_MS);
  }

  function apply(entry) {
    if (!entry) return;
    H.suppress = true;
    clearTimeout(H.timer);
    H.timer = null;
    isUserAction = false;

    try {
      if (typeof setHtmlContent === 'function') {
        setHtmlContent(entry.html);
      } else {
        const p1 = document.getElementById('editor-content') || document.querySelector('.page-body-box');
        if (p1) p1.innerHTML = entry.html;
        if (typeof updatePagination === 'function') updatePagination();
      }

      if (typeof updateCounts === 'function') updateCounts();
      if (typeof realignAllTabs === 'function') realignAllTabs();
      if (typeof updateRulerFromActiveParagraph === 'function') updateRulerFromActiveParagraph();
      if (H.observer) H.observer.takeRecords();
    } catch (err) {
      console.warn('History apply hatası:', err);
    } finally {
      setTimeout(() => {
        if (H.observer) H.observer.takeRecords();
        H.suppress = false;
      }, 300);
    }

    try {
      if (typeof showEditorToast === 'function') {
        const msg = H.idx === 0
          ? '↶ En eski sürüme dönüldü'
          : (H.idx === H.stack.length - 1 ? '↷ En son sürüme gelindi' : '✓ Adım geri / ileri alındı');
        showEditorToast(msg);
      }
    } catch (x) {}
  }

  function undo() {
    if (H.timer) {
      clearTimeout(H.timer);
      H.timer = null;
      if (isUserAction) commit(true);
    }
    if (H.idx <= 0) return false;
    H.idx--;
    apply(H.stack[H.idx]);
    return true;
  }

  function redo() {
    if (H.timer) {
      clearTimeout(H.timer);
      H.timer = null;
    }
    if (H.idx >= H.stack.length - 1) return false;
    H.idx++;
    apply(H.stack[H.idx]);
    return true;
  }

  function reset() {
    clearTimeout(H.timer);
    H.timer = null;
    H.stack = [];
    H.idx = -1;
    H.suppress = false;
    isUserAction = false;
    if (H.observer) H.observer.takeRecords();
    commit(true);
  }

  function init() {
    // Event delegation: Kullanıcının herhangi bir sayfada yazması
    document.body.addEventListener('input', (ev) => {
      if (H.suppress) return;
      const target = ev.target;
      if (target && target.closest && (target.closest('.page-body-box') || target.closest('#editor-content') || target.closest('.page-header-box'))) {
        isUserAction = true;
        schedule(true);
      }
    }, true);

    document.body.addEventListener('beforeinput', (ev) => {
      if (ev.inputType === 'historyUndo') {
        ev.preventDefault();
        undo();
      } else if (ev.inputType === 'historyRedo') {
        ev.preventDefault();
        redo();
      } else if (!H.suppress) {
        isUserAction = true;
      }
    }, true);

    // Klavye Kısayolları (Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z)
    document.addEventListener('keydown', (ev) => {
      if (!(ev.ctrlKey || ev.metaKey) || ev.altKey) return;
      const k = (ev.key || '').toLowerCase();
      const isUndo = k === 'z' && !ev.shiftKey;
      const isRedo = k === 'y' || (k === 'z' && ev.shiftKey);
      if (!isUndo && !isRedo) return;

      const active = document.activeElement;
      // Sadece düzenlenebilir alanlardayken kısayolu yakala
      if (active && (active.isContentEditable || (active.closest && active.closest('[contenteditable="true"]')))) {
        ev.preventDefault();
        ev.stopPropagation();
        isUndo ? undo() : redo();
      }
    }, true);

    // DOM Mutation Observer: Sekme hizalama, boyacı, vb. kodsal değişiklikleri yakalar
    const container = document.getElementById('pages-container') || document.getElementById('sheet-container') || document.body;
    if (container) {
      H.observer = new MutationObserver((records) => {
        if (H.suppress) return;
        const real = records.some(r => {
          const t = r.target && (r.target.nodeType === 1 ? r.target : r.target.parentElement);
          if (t && t.closest && (t.closest('.auto-page-break') || t.closest('.page-break-desk-gap') || t.closest('.official-doc-seal'))) return false;
          if (r.type === 'attributes' && t && t.classList && t.classList.contains('udf-tab-space')) return false;
          return true;
        });
        if (real) schedule(false);
      });
      H.observer.observe(container, { subtree: true, childList: true, characterData: true });
    }

    // Başlangıç anlık görüntüsünü al
    setTimeout(() => {
      commit(true);
    }, 250);
  }

  window.CanHistory = {
    undo,
    redo,
    reset,
    commit: () => commit(true),
    init,
    get isApplying() { return H.suppress; },
    get size() { return H.stack.length; },
    get index() { return H.idx; },
    canUndo: () => H.idx > 0,
    canRedo: () => H.idx < H.stack.length - 1
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
