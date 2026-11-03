/* CanEditor — Geri Al / Yinele (Anlık Görüntü Tabanlı Gelişmiş Geçmiş Motoru)
 *
 * Çok sayfalı A4 mimarisi (.a4-sheet-page / .page-body-box) ile %100 uyumlu.
 * Her anlık görüntüde sayfa içerikleriyle birlikte tam imleç ve seçim (caret)
 * konumunu pikseli ve karakterine kadar saklar ve geri yükler.
 * İmlecin başa atlamasını engeller.
 */
(function () {
  'use strict';

  const MAX_STEPS = 100;
  const QUIET_MS = 300; // Yazım duraklaması eşiği (ms)

  const H = {
    stack: [],
    idx: -1,
    timer: null,
    suppress: false,
    observer: null
  };

  let isUserAction = false;

  // Aktif imleç veya metin seçimi (caret/selection) konumunu karakter ofseti olarak kaydeder
  function saveCaretPosition() {
    try {
      const sel = window.getSelection();
      if (!sel || sel.rangeCount === 0) return null;
      const range = sel.getRangeAt(0);
      const startContainer = range.startContainer;
      const el = startContainer.nodeType === 1 ? startContainer : startContainer.parentElement;
      const bodyBox = el ? el.closest('.page-body-box') : null;
      if (!bodyBox) return null;

      let startOffset = 0;
      try {
        const preRange = range.cloneRange();
        preRange.selectNodeContents(bodyBox);
        preRange.setEnd(range.startContainer, range.startOffset);
        startOffset = preRange.toString().length;
      } catch (e) {
        startOffset = 0;
      }
      const page = bodyBox.closest('.a4-sheet-page');
      const pageNum = page ? parseInt(page.getAttribute('data-page-number') || '1', 10) : 1;
      return {
        pageNum,
        startOffset,
        length: range.toString().length
      };
    } catch (err) {
      return null;
    }
  }

  // Saklanan imleç ve seçim konumunu tam olarak ilgili metin düğümüne geri yükler
  function restoreCaretPosition(saved) {
    if (!saved) return;
    try {
      const page = document.querySelector(`.a4-sheet-page[data-page-number="${saved.pageNum}"]`) ||
                   document.getElementById(`page-${saved.pageNum}`) ||
                   document.querySelector('.a4-sheet-page');
      if (!page) return;
      const bodyBox = page.querySelector('.page-body-box') || document.getElementById('editor-content');
      if (!bodyBox) return;

      bodyBox.focus();
      const sel = window.getSelection();
      if (!sel) return;

      let currentOffset = 0;
      let startNode = null;
      let startNodeOffset = 0;
      let endNode = null;
      let endNodeOffset = 0;
      const targetStart = saved.startOffset;
      const targetEnd = saved.startOffset + (saved.length || 0);

      const walker = document.createTreeWalker(bodyBox, NodeFilter.SHOW_TEXT, null, false);
      let textNode;
      while ((textNode = walker.nextNode())) {
        const nodeLen = textNode.nodeValue.length;
        if (!startNode && currentOffset + nodeLen >= targetStart) {
          startNode = textNode;
          startNodeOffset = Math.max(0, targetStart - currentOffset);
        }
        if (!endNode && currentOffset + nodeLen >= targetEnd) {
          endNode = textNode;
          endNodeOffset = Math.max(0, targetEnd - currentOffset);
          break;
        }
        currentOffset += nodeLen;
      }

      if (startNode) {
        const range = document.createRange();
        range.setStart(startNode, Math.min(startNodeOffset, startNode.nodeValue.length));
        if (endNode) {
          range.setEnd(endNode, Math.min(endNodeOffset, endNode.nodeValue.length));
        } else {
          range.setEnd(startNode, Math.min(startNodeOffset, startNode.nodeValue.length));
        }
        sel.removeAllRanges();
        sel.addRange(range);
      }
    } catch (e) {
      // Sessizce yut
    }
  }

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
    if (!html && H.stack.length > 0) return false;

    const cur = H.stack[H.idx];
    if (cur && cur.html === html) {
      // İçerik aynıysa güncel imleç pozisyonunu kaydet
      const c = saveCaretPosition();
      if (c) cur.caret = c;
      return false;
    }

    // Kullanıcı geri almışken otomatik arka plan tetiklemesi gelirse yinele dalını ezme
    if (!isManual && !isUserAction && H.idx < H.stack.length - 1) {
      return false;
    }
    isUserAction = false;

    const caret = saveCaretPosition();
    // Yeni dal başlat: ileri adımları sil
    H.stack.length = H.idx + 1;
    H.stack.push({ html, caret });
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
      const p1 = document.getElementById('editor-content') || document.querySelector('.page-body-box');
      if (p1) {
        p1.innerHTML = entry.html;
      }
      // Sayfalamayı ve fazlalık sayfaları düzenle
      const extraPages = Array.from(document.querySelectorAll('.a4-sheet-page')).slice(1);
      extraPages.forEach(p => p.remove());

      if (typeof updatePagination === 'function') {
        updatePagination();
      }

      // İmleci tam olarak işlem anındaki yerine oturt
      if (entry.caret) {
        restoreCaretPosition(entry.caret);
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
      }, 150);
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
      if (isUserAction) {
        commit(true);
      }
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
    // DOM Mutation Observer: Sadece makro düzeyde yapısal değişiklikleri kaydetmek için hazır tutulur
    const container = document.getElementById('pages-container') || document.getElementById('sheet-container') || document.body;
    if (container) {
      H.observer = new MutationObserver((records) => {
        if (H.suppress) return;
      });
      H.observer.observe(container, { subtree: true, childList: true });
    }

    // Başlangıç anlık görüntüsünü al
    setTimeout(() => {
      commit(true);
    }, 300);
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
