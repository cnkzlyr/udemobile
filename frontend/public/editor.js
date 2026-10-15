// UdeMobile Profesyonel Mobil Editör Motoru
let currentFontSize = 12;
let isMobileView = false;
let isRulerVisible = true;
let activeDragMarker = null;
let savedSelectionRange = null;

// Paragraf Ayarları Değişkenleri
let paragraphScope = 'selected';
let currentPAlign = 'justify';

let currentMargins = {
  top: 2.5,
  right: 2.5,
  bottom: 2.5,
  left: 2.5,
  header: 1.25,
  footer: 1.25,
  orientation: 'portrait' // 'portrait' or 'landscape'
};

// --- Sayfa Numarası ve Biçim Boyacısı Durum Değişkenleri ---
let currentDocPageNumberPos = 'bottom-right';
let isFormatPainterActive = false;
let isFormatPainterPersistent = false;
let copiedFormat = null;

// --- Google Dokümanlar Yazdırma Düzeni & Zoom Motoru ---
let currentDocFooterTemplate = '';
let currentZoom = 0.48;
let isFitMode = true; // true = Google Dokümanlar stili uzaktan genel görünüm (A4 sığdır)
let lastSelectedParagraphs = [];
let lastActiveParagraph = null;

function recordCurrentSelection() {
  const sel = window.getSelection();
  const editor = document.getElementById('editor-content');
  if (!sel || sel.rangeCount === 0 || !editor) return;

  const anchor = sel.anchorNode;
  if (!editor.contains(anchor)) {
    // Odak editör dışında ise (örneğin araç çubuğuna tıklandıysa), seçimi koru ve silme!
    return;
  }

  try {
    savedSelectionRange = sel.getRangeAt(0).cloneRange();
  } catch (e) {}

  // Aktif paragrafı bul
  let node = anchor;
  let activeP = null;
  while (node && node !== editor && node !== document.body) {
    if (node.nodeType === Node.ELEMENT_NODE) {
      const tag = node.tagName.toLowerCase();
      if (tag === 'p' || tag === 'li' || tag === 'blockquote' || (tag === 'div' && node.parentNode === editor)) {
        activeP = node;
        break;
      }
    }
    node = node.parentNode;
  }
  if (activeP) lastActiveParagraph = activeP;

  // Seçili paragrafları bul
  try {
    const range = sel.getRangeAt(0);
    const allBlocks = Array.from(editor.querySelectorAll('p, li, blockquote'));
    const intersected = allBlocks.filter(b => range.intersectsNode(b));
    if (intersected.length > 0) {
      lastSelectedParagraphs = intersected;
    } else if (activeP) {
      lastSelectedParagraphs = [activeP];
    }
  } catch (e) {}
}

// --- BİLDİRİM VE TOAST MOTORU ---
function showEditorToast(msg) {
  let toast = document.getElementById('editor-toast-notification');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'editor-toast-notification';
    toast.style.position = 'fixed';
    toast.style.bottom = '46px';
    toast.style.left = '50%';
    toast.style.transform = 'translateX(-50%) translateY(20px)';
    toast.style.backgroundColor = 'rgba(26, 43, 76, 0.94)';
    toast.style.color = '#ffffff';
    toast.style.padding = '8px 18px';
    toast.style.borderRadius = '20px';
    toast.style.fontSize = '12px';
    toast.style.fontWeight = '600';
    toast.style.boxShadow = '0 4px 16px rgba(0,0,0,0.3)';
    toast.style.zIndex = '99999';
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
    toast.style.pointerEvents = 'none';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.style.opacity = '1';
  toast.style.transform = 'translateX(-50%) translateY(0)';
  clearTimeout(toast._timeout);
  toast._timeout = setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(-50%) translateY(15px)';
  }, 2200);
}
window.showToast = showEditorToast;

document.addEventListener('DOMContentLoaded', () => {
  const editor = document.getElementById('editor-content');
  
  editor.addEventListener('input', () => {
    const ap = getActiveParagraph();
    if (ap && ap.querySelector('.udf-tab-space')) realignTabsInParagraph(ap);
    updateCounts();
    debouncedPagination();
  });

  document.addEventListener('selectionchange', () => {
    recordCurrentSelection();
    updateActiveButtons();
    updateRulerFromActiveParagraph();
    if (!isFormatPainterActive) {
      setTimeout(updateFloatingContextMenu, 120);
    }
  });

  editor.addEventListener('mouseup', () => {
    recordCurrentSelection();
    if (isFormatPainterActive) {
      applyCopiedFormatToTarget();
    } else {
      setTimeout(updateFloatingContextMenu, 60);
    }
  });

  editor.addEventListener('touchend', () => {
    recordCurrentSelection();
    if (isFormatPainterActive) {
      applyCopiedFormatToTarget();
    } else {
      setTimeout(updateFloatingContextMenu, 100);
    }
  });

  editor.addEventListener('keyup', () => {
    recordCurrentSelection();
  });

  editor.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      handleTabAction();
    }
  });

  // Tıklama ile aktif paragrafı algılama
  editor.addEventListener('click', () => {
    recordCurrentSelection();
    updateRulerFromActiveParagraph();
  });

  // Sayfa dışına veya araç çubuğuna tıklayınca context bubble gizle
  document.addEventListener('mousedown', (e) => {
    const bubble = document.getElementById('floating-context-menu');
    if (bubble && !bubble.contains(e.target) && !editor.contains(e.target)) {
      hideFloatingContextMenu();
    }
  });

  // Araç çubuğu butonlarının editördeki metin seçimini kaybetmesini engelle:
  const toolbar = document.querySelector('.toolbar');
  if (toolbar) {
    toolbar.addEventListener('mousedown', (e) => {
      recordCurrentSelection();
      // <select> ve <input> dışındaki tüm buton/ikon tıklamalarında seçimi koru
      if (e.target.tagName !== 'SELECT' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'OPTION') {
        e.preventDefault();
      }
    });
    toolbar.addEventListener('touchstart', (e) => {
      recordCurrentSelection();
    }, { passive: true });
  }

  // Başlangıçta kenar boşlukları ve kağıt ölçeğini uygula
  applyPageSetup(currentMargins.left, currentMargins.right, currentMargins.top, currentMargins.bottom, currentMargins.orientation, currentMargins.header, currentMargins.footer);
  initPinchToZoom();
  initDynamicScrollBlur();
  updateCounts();
  
  setTimeout(() => {
    applyAutoFitZoom();
    updatePagination();
    updateRulerFromActiveParagraph();
  }, 200);
});

// Kağıt Görünümü (Yazdırma Düzeni) / Mobil Görünüm Geçişi
function toggleViewMode() {
  const wrapper = document.getElementById('page-wrapper');
  const btn = document.getElementById('btn-toggle-view');
  
  isMobileView = !isMobileView;
  if (isMobileView) {
    wrapper.classList.remove('paper-view');
    wrapper.classList.add('mobile-view');
    if (btn) btn.textContent = '📄';
    const oldBreaks = document.querySelectorAll('.auto-page-break');
    oldBreaks.forEach(b => b.remove());
  } else {
    wrapper.classList.remove('mobile-view');
    wrapper.classList.add('paper-view');
    if (btn) btn.textContent = '📱';
    applyAutoFitZoom();
    setTimeout(updatePagination, 100);
  }
}

// Otomatik A4 Sayfa Ayrımı (Havelsan UYAP Çoklu Sayfa Düzeni)
let paginationTimer = null;
function getDocFooterHtml(pageNum, totalPages) {
  let pageNumHtml = '';
  if (currentDocPageNumberPos === 'bottom-right') {
    pageNumHtml = `<span class="udf-footer-page-label" style="position: absolute; right: 0;">Sayfa: ${pageNum} / ${totalPages}</span>`;
  } else if (currentDocPageNumberPos === 'bottom-center') {
    pageNumHtml = `<span class="udf-footer-page-label" style="position: absolute; left: 50%; transform: translateX(-50%);">Sayfa: ${pageNum} / ${totalPages}</span>`;
  } else if (currentDocPageNumberPos === 'bottom-left') {
    pageNumHtml = `<span class="udf-footer-page-label" style="position: absolute; left: 0;">Sayfa: ${pageNum} / ${totalPages}</span>`;
  } else if (currentDocPageNumberPos === 'none') {
    pageNumHtml = '';
  }

  if (currentDocFooterTemplate) {
    let tpl = currentDocFooterTemplate
      .replace(/\{PAGE_NUM\}/g, pageNum)
      .replace(/\{TOTAL_PAGES\}/g, totalPages);
    if (!tpl.includes('udf-footer-page-label') && currentDocPageNumberPos !== 'none' && pageNumHtml) {
      if (tpl.includes('</div>')) {
        tpl = tpl.replace('</div>', pageNumHtml + '</div>');
      } else {
        tpl += pageNumHtml;
      }
    }
    return tpl;
  }
  const dateStr = new Date().toLocaleDateString('tr-TR');
  return `<div class="udf-footer-layout">` +
         `<span class="udf-footer-text">Belge Düzenleme Tarihi: ${dateStr}</span>` +
         pageNumHtml +
         `</div>`;
}

function applyPageNumberChoice(choice) {
  currentDocPageNumberPos = choice || 'bottom-right';
  updatePagination();
  showEditorToast('Sayfa numarası konumu güncellendi');
}

function updatePagination() {
  try { realignAllTabs(); } catch (e) {}
  if (isMobileView) return;
  const editor = document.getElementById('editor-content');
  if (!editor) return;

  // Önceki otomatik sayfa bölücüleri temizle
  const oldBreaks = editor.querySelectorAll('.auto-page-break');
  oldBreaks.forEach(b => b.remove());

  // A4 Sayfa kullanılabilir yükseklik hesabı:
  const topCm = currentMargins.top || 2.0;
  const bottomCm = currentMargins.bottom || 2.5;
  const isLandscape = currentMargins.orientation === 'landscape';
  const pageHeight = isLandscape ? 794 : 1123;
  const marginPx = (topCm + bottomCm) * 37.8; // cm to px
  const printableHeight = Math.max(450, pageHeight - marginPx);

  // 1. Geçiş: Toplam sayfa sayısını ve bölünecek çocuk indekslerini hesapla
  let currentAccumHeight = 0;
  const children = Array.from(editor.children);
  const breakIndices = [];

  for (let i = 0; i < children.length; i++) {
    const child = children[i];
    if (child.classList && (child.classList.contains('auto-page-break') || child.classList.contains('page-break'))) continue;
    const h = child.offsetHeight || 28;
    if (currentAccumHeight + h >= printableHeight && currentAccumHeight > 0) {
      breakIndices.push(i);
      currentAccumHeight = h;
    } else {
      currentAccumHeight += h;
    }
  }

  const totalPages = breakIndices.length + 1;

  // 2. Geçiş: Sayfa ayırıcıları ekle
  let pageIndex = 1;
  for (let b = 0; b < breakIndices.length; b++) {
    const child = children[breakIndices[b]];
    if (!child) continue;

    const pageBreak = document.createElement('div');
    pageBreak.className = 'auto-page-break';
    pageBreak.setAttribute('contenteditable', 'false');

    // Biten sayfanın altbilgisi (UYAP logolu veya numaralı)
    const footerArea = document.createElement('div');
    footerArea.className = 'page-break-footer-area';
    footerArea.innerHTML = getDocFooterHtml(pageIndex, totalPages);
    pageBreak.appendChild(footerArea);

    // Fiziksel kağıtlar arası Havelsan masaüstü gri boşluğu (Üstteki sayfa numarasını gösterir)
    const deskGap = document.createElement('div');
    deskGap.className = 'page-break-desk-gap';
    deskGap.setAttribute('data-page-label', `Sayfa ${pageIndex}`);
    pageBreak.appendChild(deskGap);
    pageIndex++;

    // Yeni sayfanın üst kenar boşluğu
    const headerArea = document.createElement('div');
    headerArea.className = 'page-break-header-area';
    const docHeader = document.getElementById('doc-header');
    const headerRawText = docHeader ? (docHeader.innerText || '').replace(/[\r\n\t\s]+/g, ' ').trim() : '';
    const hasHeader = docHeader && headerRawText.length > 0 && docHeader.style.display !== 'none';
    if (hasHeader) {
      headerArea.classList.add('has-header');
      const hClone = document.createElement('div');
      hClone.className = 'header-footer-box';
      hClone.style.borderBottom = 'none';
      hClone.style.padding = '0';
      hClone.style.margin = '0';
      hClone.innerHTML = docHeader.innerHTML.trim();
      headerArea.appendChild(hClone);
    } else {
      headerArea.classList.add('no-header');
    }
    pageBreak.appendChild(headerArea);

    editor.insertBefore(pageBreak, child);
  }

  // Son sayfanın altbilgisini güncelle
  const footerEl = document.getElementById('doc-footer');
  if (footerEl) {
    footerEl.innerHTML = getDocFooterHtml(totalPages, totalPages);
    footerEl.style.display = 'block';
    footerEl.style.border = 'none';
  }

  // Durum çubuğunda sayfa sayısını göster
  const statusEl = document.getElementById('stat-page-count');
  if (statusEl) {
    statusEl.textContent = `Sayfa 1 / ${totalPages}`;
  }
}

function debouncedPagination() {
  clearTimeout(paginationTimer);
  paginationTimer = setTimeout(updatePagination, 250);
}

// Üstbilgi ve Altbilgiye Odaklanma (Asla kaybolmaz, doğrudan düzenlenir)
function focusHeaderFooter() {
  const header = document.getElementById('doc-header');
  const footer = document.getElementById('doc-footer');
  if (document.activeElement === header) {
    footer.focus();
    footer.scrollIntoView({ behavior: 'smooth', block: 'center' });
  } else {
    header.focus();
    header.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

// Sayfa Numarası Ekleme (Altbilgiye güvenle ekler, üst/altbilgiyi kapatmaz)
function insertPageNumber() {
  const footer = document.getElementById('doc-footer');
  const now = new Date().toLocaleDateString('tr-TR');
  footer.innerHTML = `<span>Belge Düzenleme Tarihi: ${now}</span> <span style="float: right; font-weight: bold;">Sayfa 1 / 1</span>`;
  footer.focus();
  updateCounts();
}

// Temel Biçimlendirme
function format(cmd, val = null) {
  // Geri al / yinele: tüm değişiklikleri (sekme, cetvel, biçim boyacısı...) kapsayan kendi geçmişimiz
  if ((cmd === 'undo' || cmd === 'redo') && window.CanHistory) {
    const a = document.activeElement;
    const inHeaderFooter = a && (a.id === 'doc-header' || a.id === 'doc-footer');
    if (!inHeaderFooter) {
      cmd === 'undo' ? CanHistory.undo() : CanHistory.redo();
      document.getElementById('editor-content').focus();
      return;
    }
  }
  document.execCommand(cmd, false, val);
  document.getElementById('editor-content').focus();
  updateActiveButtons();
  updateCounts();
}

// Yazı Tipi Ailesi
function changeFontFamily(font) {
  const selection = window.getSelection();
  if (selection.rangeCount > 0 && !selection.isCollapsed) {
    document.execCommand('fontName', false, font);
  } else {
    document.getElementById('editor-content').style.fontFamily = font;
  }
}

// Yazı Boyutu
function adjustFontSize(delta) {
  currentFontSize = Math.max(9, Math.min(26, currentFontSize + delta));
  document.getElementById('font-size-label').textContent = currentFontSize + 'pt';
  
  const selection = window.getSelection();
  if (selection.rangeCount > 0 && !selection.isCollapsed) {
    document.execCommand('fontSize', false, '7');
    const fontElements = document.getElementsByTagName('font');
    for (let el of fontElements) {
      if (el.size === '7') {
        el.removeAttribute('size');
        el.style.fontSize = currentFontSize + 'pt';
      }
    }
  } else {
    document.getElementById('editor-content').style.fontSize = currentFontSize + 'pt';
  }
}

// --- PARAGRAF BULMA VE HEDEFLİ SEÇİM ---
function getActiveParagraph() {
  const selection = window.getSelection();
  const editor = document.getElementById('editor-content');
  if (selection && selection.rangeCount > 0 && editor && editor.contains(selection.anchorNode)) {
    let node = selection.anchorNode;
    while (node && node !== editor && node !== document.body) {
      if (node.nodeType === Node.ELEMENT_NODE) {
        const tag = node.tagName.toLowerCase();
        if (tag === 'p' || tag === 'li' || tag === 'blockquote' || (tag === 'div' && node.parentNode === editor)) {
          lastActiveParagraph = node;
          return node;
        }
      }
      node = node.parentNode;
    }
  }
  if (lastActiveParagraph && editor && editor.contains(lastActiveParagraph)) {
    return lastActiveParagraph;
  }
  const ps = editor ? editor.querySelectorAll('p, li, blockquote') : [];
  return ps.length > 0 ? ps[0] : null;
}

function getSelectedParagraphs() {
  const selection = window.getSelection();
  const editor = document.getElementById('editor-content');
  // İmleç editörde ve seçim yoksa: sadece imlecin bulunduğu paragraf (eski çoklu seçime dönme)
  if (selection && selection.rangeCount > 0 && selection.isCollapsed && editor && editor.contains(selection.anchorNode)) {
    const cp = getActiveParagraph();
    return cp ? [cp] : [];
  }
  if (selection && selection.rangeCount > 0 && !selection.isCollapsed && editor && editor.contains(selection.anchorNode)) {
    try {
      const range = selection.getRangeAt(0);
      const allBlocks = Array.from(editor.querySelectorAll('p, li, blockquote'));
      const intersected = allBlocks.filter(b => range.intersectsNode(b));
      if (intersected.length > 0) {
        lastSelectedParagraphs = intersected;
        return intersected;
      }
    } catch(e) {}
  }

  // Seçim araç çubuğuna tıklanması nedeniyle odak kaybında önceden kaydedilen seçimi kullan:
  if (lastSelectedParagraphs && lastSelectedParagraphs.length > 0 && editor) {
    const valid = lastSelectedParagraphs.filter(p => editor.contains(p));
    if (valid.length > 0) return valid;
  }

  const p = getActiveParagraph();
  return p ? [p] : [];
}

// Hızlı Paragraf Boşluğu (Önce & Sonra - Yalnızca Seçili Paragraflara Uygulanır)
function changeParagraphSpacing(val) {
  if (val === 'custom') {
    openParagraphModal();
    return;
  }
  const parts = val.split(',');
  if (parts.length !== 2) return;
  const beforePt = parts[0] + 'pt';
  const afterPt = parts[1] + 'pt';

  const targets = getSelectedParagraphs();
  targets.forEach(p => {
    p.style.marginTop = beforePt;
    p.style.marginBottom = afterPt;
  });
  updateCounts();
  debouncedPagination();
  setTimeout(restoreCurrentSelection, 50);
}

// Satır Aralığı (Yalnızca Seçili Paragraflara Uygulanır)
function changeLineSpacing(val) {
  const targets = getSelectedParagraphs();
  targets.forEach(p => {
    p.style.lineHeight = val;
  });
  updateCounts();
  debouncedPagination();
  setTimeout(restoreCurrentSelection, 50);
}

// --- SAYFA YAPISI VE KENAR BOŞLUKLARI MOTORU ---
function applyPageSetup(left, right, top, bottom, orientation, header, footer) {
  if (left !== undefined && left !== null) currentMargins.left = parseFloat(left) || 2.5;
  if (right !== undefined && right !== null) currentMargins.right = parseFloat(right) || 2.5;
  if (top !== undefined && top !== null) currentMargins.top = parseFloat(top) || 2.5;
  if (bottom !== undefined && bottom !== null) currentMargins.bottom = parseFloat(bottom) || 2.5;
  if (header !== undefined && header !== null) currentMargins.header = parseFloat(header) || 1.25;
  if (footer !== undefined && footer !== null) currentMargins.footer = parseFloat(footer) || 1.25;
  if (orientation) currentMargins.orientation = orientation;

  const root = document.documentElement;
  root.style.setProperty('--page-margin-top', currentMargins.top + 'cm');
  root.style.setProperty('--page-margin-right', currentMargins.right + 'cm');
  root.style.setProperty('--page-margin-bottom', currentMargins.bottom + 'cm');
  root.style.setProperty('--page-margin-left', currentMargins.left + 'cm');
  root.style.setProperty('--header-margin', currentMargins.header + 'cm');
  root.style.setProperty('--footer-margin', currentMargins.footer + 'cm');

  const isLandscape = currentMargins.orientation === 'landscape';
  root.style.setProperty('--sheet-width', isLandscape ? '1123px' : '794px');
  root.style.setProperty('--sheet-min-height', isLandscape ? '794px' : '1123px');

  initRuler();

  if (isFitMode && !isMobileView) {
    applyAutoFitZoom();
  }

  updateCounts();
  debouncedPagination();
}

function openPageSetupModal() {
  const mLeft = document.getElementById('m-left');
  const mRight = document.getElementById('m-right');
  const mTop = document.getElementById('m-top');
  const mBottom = document.getElementById('m-bottom');
  const mHeader = document.getElementById('m-header');
  const mFooter = document.getElementById('m-footer');

  if (mLeft) mLeft.value = currentMargins.left;
  if (mRight) mRight.value = currentMargins.right;
  if (mTop) mTop.value = currentMargins.top;
  if (mBottom) mBottom.value = currentMargins.bottom;
  if (mHeader) mHeader.value = currentMargins.header !== undefined ? currentMargins.header : 1.25;
  if (mFooter) mFooter.value = currentMargins.footer !== undefined ? currentMargins.footer : 1.25;

  setPageOrientation(currentMargins.orientation || 'portrait');
  updateMarginPreview();
  openModal('modal-page-setup');
}

function setMarginPreset(preset) {
  if (preset === 'petition') {
    document.getElementById('m-left').value = 2.5;
    document.getElementById('m-right').value = 2.5;
    document.getElementById('m-top').value = 2.5;
    document.getElementById('m-bottom').value = 2.5;
    if (document.getElementById('m-header')) document.getElementById('m-header').value = 1.25;
    if (document.getElementById('m-footer')) document.getElementById('m-footer').value = 1.25;
  } else if (preset === 'uyap') {
    document.getElementById('m-left').value = 1.5;
    document.getElementById('m-right').value = 1.5;
    document.getElementById('m-top').value = 1.5;
    document.getElementById('m-bottom').value = 1.5;
    if (document.getElementById('m-header')) document.getElementById('m-header').value = 1.0;
    if (document.getElementById('m-footer')) document.getElementById('m-footer').value = 1.0;
  } else if (preset === 'binding') {
    document.getElementById('m-left').value = 3.0;
    document.getElementById('m-right').value = 1.5;
    document.getElementById('m-top').value = 2.5;
    document.getElementById('m-bottom').value = 2.0;
    if (document.getElementById('m-header')) document.getElementById('m-header').value = 1.25;
    if (document.getElementById('m-footer')) document.getElementById('m-footer').value = 1.25;
  } else if (preset === 'narrow') {
    document.getElementById('m-left').value = 1.0;
    document.getElementById('m-right').value = 1.0;
    document.getElementById('m-top').value = 1.5;
    document.getElementById('m-bottom').value = 1.5;
    if (document.getElementById('m-header')) document.getElementById('m-header').value = 0.8;
    if (document.getElementById('m-footer')) document.getElementById('m-footer').value = 0.8;
  }
  updateMarginPreview();
}

function stepMargin(side, delta) {
  const input = document.getElementById('m-' + side);
  if (!input) return;
  let val = parseFloat(input.value) || 2.5;
  val = Math.max(0.5, Math.min(8.0, Math.round((val + delta) * 100) / 100));
  input.value = val;
  updateMarginPreview();
}

let modalOrientation = 'portrait';
function setPageOrientation(orient) {
  modalOrientation = orient;
  const btnP = document.getElementById('btn-orient-portrait');
  const btnL = document.getElementById('btn-orient-landscape');
  if (orient === 'landscape') {
    if (btnP) btnP.classList.remove('active');
    if (btnL) btnL.classList.add('active');
  } else {
    if (btnP) btnP.classList.add('active');
    if (btnL) btnL.classList.remove('active');
  }
  updateMarginPreview();
}

function updateMarginPreview() {
  const previewSheet = document.getElementById('margin-preview-sheet');
  const previewBox = document.getElementById('preview-margin-box');
  if (!previewSheet || !previewBox) return;

  const left = parseFloat(document.getElementById('m-left').value) || 2.5;
  const right = parseFloat(document.getElementById('m-right').value) || 2.5;
  const top = parseFloat(document.getElementById('m-top').value) || 2.5;
  const bottom = parseFloat(document.getElementById('m-bottom').value) || 2.5;

  const isL = modalOrientation === 'landscape';
  if (isL) {
    previewSheet.style.width = '155px';
    previewSheet.style.height = '110px';
  } else {
    previewSheet.style.width = '110px';
    previewSheet.style.height = '155px';
  }

  const pageW = isL ? 29.7 : 21.0;
  const pageH = isL ? 21.0 : 29.7;

  const leftPct = (left / pageW) * 100;
  const rightPct = (right / pageW) * 100;
  const topPct = (top / pageH) * 100;
  const bottomPct = (bottom / pageH) * 100;

  previewBox.style.left = leftPct + '%';
  previewBox.style.right = rightPct + '%';
  previewBox.style.top = topPct + '%';
  previewBox.style.bottom = bottomPct + '%';
}

function applyPageSetupFromModal() {
  const left = parseFloat(document.getElementById('m-left').value) || 2.5;
  const right = parseFloat(document.getElementById('m-right').value) || 2.5;
  const top = parseFloat(document.getElementById('m-top').value) || 2.5;
  const bottom = parseFloat(document.getElementById('m-bottom').value) || 2.5;
  const header = parseFloat(document.getElementById('m-header')?.value) || 1.25;
  const footer = parseFloat(document.getElementById('m-footer')?.value) || 1.25;

  applyPageSetup(left, right, top, bottom, modalOrientation, header, footer);
  closeModal('modal-page-setup');
}

// --- GOOGLE DOKÜMANLAR YAZDIRMA DÜZENİ & ZOOM MOTORU ---
function calculateFitScale() {
  const availableWidth = window.innerWidth - 16;
  const sheetWidth = currentMargins.orientation === 'landscape' ? 1123 : 794;
  const fit = Math.min(1.0, Math.max(0.3, availableWidth / sheetWidth));
  return Math.round(fit * 100) / 100;
}

function applyAutoFitZoom() {
  isFitMode = true;
  const fit = calculateFitScale();
  setZoom(fit, true);
}

function setZoom(scale, isFit = false) {
  currentZoom = Math.min(2.0, Math.max(0.35, scale));
  document.documentElement.style.setProperty('--doc-zoom', currentZoom);
  const sheetContainer = document.getElementById('sheet-container');
  if (sheetContainer && !isMobileView) {
    sheetContainer.style.zoom = currentZoom;
  }

  const ind = document.getElementById('zoom-indicator');
  if (ind) {
    ind.textContent = (isFit ? '%' + Math.round(currentZoom * 100) + ' Sığdır' : '%' + Math.round(currentZoom * 100));
  }

  const fab = document.getElementById('fab-view-toggle');
  if (fab) {
    if (currentZoom < 0.8) {
      fab.innerHTML = `<svg viewBox="0 0 24 24"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>`;
      fab.title = "✏️ Düzenleme Modu (%100 Yakınlaştır)";
    } else {
      fab.innerHTML = `<svg viewBox="0 0 24 24"><path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>`;
      fab.title = "📄 Baskı Görünümü (Sayfaya Sığdır)";
    }
  }
}

function toggleFabView() {
  if (isMobileView) {
    toggleViewMode();
    applyAutoFitZoom();
    return;
  }
  if (currentZoom < 0.8) {
    isFitMode = false;
    setZoom(1.0, false);
    const editor = document.getElementById('editor-content');
    if (editor) editor.focus();
  } else {
    applyAutoFitZoom();
  }
}

function cycleZoomMode() {
  if (isMobileView) return;
  if (isFitMode) {
    isFitMode = false;
    setZoom(0.75, false);
  } else if (currentZoom < 0.9) {
    setZoom(1.0, false);
  } else {
    applyAutoFitZoom();
  }
}

function stepZoom(delta) {
  if (isMobileView) return;
  isFitMode = false;
  setZoom(Math.round((currentZoom + delta) * 100) / 100, false);
}

function initPinchToZoom() {
  const wrapper = document.getElementById('page-wrapper');
  if (!wrapper) return;

  let initialDistance = 0;
  let initialZoom = currentZoom;

  wrapper.addEventListener('touchstart', (e) => {
    if (e.touches.length === 2 && !isMobileView) {
      initialDistance = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      initialZoom = currentZoom;
    }
  }, { passive: true });

  wrapper.addEventListener('touchmove', (e) => {
    if (e.touches.length === 2 && !isMobileView && initialDistance > 0) {
      const currentDistance = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      const factor = currentDistance / initialDistance;
      isFitMode = false;
      setZoom(initialZoom * factor, false);
    }
  }, { passive: true });

  wrapper.addEventListener('touchend', (e) => {
    if (e.touches.length < 2) {
      initialDistance = 0;
    }
  });

  window.addEventListener('resize', () => {
    if (isFitMode && !isMobileView) {
      applyAutoFitZoom();
    }
  });
}

// --- DİNAMİK CETVEL MOTORU ---
function initRuler() {
  const ticksContainer = document.getElementById('ruler-ticks');
  if (!ticksContainer) return;
  ticksContainer.innerHTML = '';

  const isLandscape = currentMargins.orientation === 'landscape';
  const totalPageCm = isLandscape ? 29.7 : 21.0;
  const activeCm = Math.max(5, totalPageCm - (currentMargins.left || 2.5) - (currentMargins.right || 2.5));
  const totalMm = Math.round(activeCm * 10);

  for (let mm = 0; mm <= totalMm; mm++) {
    const pct = (mm / totalMm) * 100;
    const tick = document.createElement('div');
    tick.style.left = pct + '%';

    if (mm % 10 === 0) {
      tick.className = 'ruler-tick cm';
      const cmNum = mm / 10;
      if (cmNum >= 0 && cmNum <= activeCm) {
        const numLabel = document.createElement('div');
        numLabel.className = 'ruler-number';
        numLabel.style.left = pct + '%';
        numLabel.textContent = cmNum;
        ticksContainer.appendChild(numLabel);
      }
    } else if (mm % 5 === 0) {
      tick.className = 'ruler-tick half-cm';
    } else {
      tick.className = 'ruler-tick mm';
    }
    ticksContainer.appendChild(tick);
  }

  setupMarkerDragging('marker-first-line', 'firstLine', activeCm);
  setupMarkerDragging('marker-left-indent', 'leftIndent', activeCm);
  setupMarkerDragging('marker-right-indent', 'rightIndent', activeCm);

  const rulerScale = document.getElementById('ruler-scale');
  rulerScale.addEventListener('mousedown', (e) => {
    // Editördeki metin seçiminin cetvele tıklanınca kaybolmaması için mousedown'u engelle
    e.preventDefault();
  });
  rulerScale.onclick = (e) => {
    if (activeDragMarker) return;
    
    // Eğer tıklanan bir sekme durağı ise setupTabStopDragging ele alacaktır
    if (e.target && e.target.classList.contains('ruler-tab-stop')) {
      return;
    }

    const rect = rulerScale.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = Math.max(0, Math.min(1, x / rect.width));
    const cm = Math.round((pct * activeCm) * 10) / 10;
    
    toggleTabStop(cm);
  };
}

let currentTabStops = [];

function toggleTabStop(cm) {
  const existingIdx = currentTabStops.findIndex(s => Math.abs(s - cm) < 0.35);
  if (existingIdx !== -1) {
    currentTabStops.splice(existingIdx, 1);
  } else {
    currentTabStops.push(cm);
    currentTabStops.sort((a, b) => a - b);
  }
  syncTabStopsToActiveParagraph();
  renderTabStopsOnRuler();
}

function removeTabStop(cm) {
  currentTabStops = currentTabStops.filter(s => Math.abs(s - cm) >= 0.1);
  syncTabStopsToActiveParagraph();
  renderTabStopsOnRuler();
}

function syncTabStopsToActiveParagraph() {
  const targets = getSelectedParagraphs();
  const val = currentTabStops.length > 0 ? currentTabStops.map(v => Math.round(v * 100) / 100).join(',') : '';
  targets.forEach(p => {
    if (val) {
      p.dataset.tabStops = val;
    } else {
      delete p.dataset.tabStops;
    }
    realignTabsInParagraph(p);
  });
  if (window.CanHistory) CanHistory.commit();
}

// ---- Word / UYAP tarzı sekme (tab) motoru ----
// Sekme konumları cm cinsinden, metin alanının (editor-content) SOL kenarından ölçülür; cetvelle birebir aynı sıfır noktası.
const DEFAULT_TAB_INTERVAL_CM = 1.25;

function getTabMetrics() {
  const ed = document.getElementById('editor-content');
  if (!ed) return null;
  const r = ed.getBoundingClientRect();
  const scale = ed.offsetWidth > 0 ? (r.width / ed.offsetWidth) : 1;
  const ppc = 37.795275 * (scale || 1);
  const cs = window.getComputedStyle(ed);
  const padL = (parseFloat(cs.paddingLeft) || 0) * (scale || 1);
  const padR = (parseFloat(cs.paddingRight) || 0) * (scale || 1);
  return { left: r.left + padL, ppc, widthCm: (r.width - padL - padR) / ppc };
}

function getParagraphTabStops(p) {
  if (!p || !p.dataset || !p.dataset.tabStops) return [];
  return p.dataset.tabStops.split(',').map(s => parseFloat(s)).filter(s => !isNaN(s)).sort((a, b) => a - b);
}

// Word mantığı: özel durak varsa önce ona gider; özel duraklardan sonra varsayılan 1.25 cm ızgarası
function computeNextTabStop(stops, curCm) {
  const EPS = 0.05;
  const custom = stops.find(s => s > curCm + EPS);
  if (custom !== undefined) return custom;
  return (Math.floor(curCm / DEFAULT_TAB_INTERVAL_CM + 1e-6) + 1) * DEFAULT_TAB_INTERVAL_CM;
}

function realignTabsInParagraph(p) {
  if (!p) return;
  const tabSpaces = Array.from(p.querySelectorAll('.udf-tab-space'));
  const tabLabel = p.querySelector('.udf-tab-label');
  const stops = getParagraphTabStops(p);

  // "ETİKET : değer" tipi (asılı girintili) paragraflarda ilk durak etiketin genişliğini belirler
  if (tabLabel) {
    if (stops.length > 0) {
      const first = Math.max(1, stops[0]);
      p.style.setProperty('padding-left', first + 'cm', 'important');
      p.style.setProperty('text-indent', (-first) + 'cm', 'important');
      const lw = Math.max(0.5, first - 0.5) + 'cm';
      tabLabel.style.width = lw;
      tabLabel.style.minWidth = lw;
      tabLabel.style.maxWidth = lw;
    } else {
      p.style.removeProperty('padding-left');
      p.style.removeProperty('text-indent');
      tabLabel.style.width = '';
      tabLabel.style.minWidth = '';
      tabLabel.style.maxWidth = '';
    }
  }

  if (tabSpaces.length === 0) return;
  const m = getTabMetrics();
  if (!m) return;

  tabSpaces.forEach(ts => {
    ts.setAttribute('contenteditable', 'false');
    if (ts.textContent !== '\u200B') ts.textContent = '\u200B';
    ts.style.display = 'inline-block';
    ts.style.width = '0px';
    ts.style.minWidth = '0px';
    const tsRect = ts.getBoundingClientRect();
    const curCm = Math.max(0, (tsRect.left - m.left) / m.ppc);
    let target = computeNextTabStop(stops, curCm);
    let gap = target - curCm;
    // Satır sonuna taşmasın
    const room = m.widthCm - curCm;
    if (room > 0.1 && gap > room) gap = room;
    gap = Math.max(0.1, gap);
    ts.style.width = (Math.round(gap * 1000) / 1000) + 'cm';
    ts.dataset.targetStop = String(Math.round((curCm + gap) * 100) / 100);
  });
}

function realignAllTabs() {
  const ed = document.getElementById('editor-content');
  if (!ed) return;
  ed.querySelectorAll('p, li, blockquote').forEach(p => {
    if (p.querySelector('.udf-tab-space') || (p.dataset && p.dataset.tabStops && p.querySelector('.udf-tab-label'))) {
      realignTabsInParagraph(p);
    }
  });
}

function setupTabStopDragging(marker, originalCm, activeCm) {
  const scale = document.getElementById('ruler-scale');
  if (!marker || !scale) return;

  function onStart(e) {
    e.preventDefault();
    e.stopPropagation();
    activeDragMarker = 'tab-stop';
    let currentCm = originalCm;
    let didMove = false;
    const startX = e.touches ? e.touches[0].clientX : e.clientX;

    const moveHandler = (moveEvent) => {
      const clientX = moveEvent.touches ? moveEvent.touches[0].clientX : moveEvent.clientX;
      if (Math.abs(clientX - startX) > 4) {
        didMove = true;
      }
      const rect = scale.getBoundingClientRect();
      const x = clientX - rect.left;
      const pct = Math.max(0, Math.min(1, x / rect.width));
      currentCm = Math.round((pct * activeCm) * 10) / 10;
      marker.style.left = (pct * 100) + '%';
      marker.dataset.cm = currentCm;
      marker.title = `Sekme Durağı: ${currentCm} cm (Taşımak için sürükleyin, kaldırmak için dokunun)`;
    };

    const upHandler = () => {
      window.removeEventListener('mousemove', moveHandler);
      window.removeEventListener('mouseup', upHandler);
      window.removeEventListener('touchmove', moveHandler);
      window.removeEventListener('touchend', upHandler);

      if (didMove) {
        const idx = currentTabStops.indexOf(originalCm);
        if (idx !== -1) {
          currentTabStops[idx] = currentCm;
        } else {
          currentTabStops.push(currentCm);
        }
        currentTabStops.sort((a, b) => a - b);
        syncTabStopsToActiveParagraph();
        renderTabStopsOnRuler();
        showEditorToast(`Sekme durağı taşındı: ${currentCm} cm`);
      } else {
        removeTabStop(originalCm);
      }
      setTimeout(() => { activeDragMarker = null; }, 120);
    };

    window.addEventListener('mousemove', moveHandler);
    window.addEventListener('mouseup', upHandler);
    window.addEventListener('touchmove', moveHandler, { passive: false });
    window.addEventListener('touchend', upHandler);
  }

  marker.addEventListener('mousedown', onStart);
  marker.addEventListener('touchstart', onStart, { passive: false });
}

function renderTabStopsOnRuler() {
  const scale = document.getElementById('ruler-scale');
  if (!scale) return;
  scale.querySelectorAll('.ruler-tab-stop').forEach(el => el.remove());

  const isLandscape = currentMargins.orientation === 'landscape';
  const totalPageCm = isLandscape ? 29.7 : 21.0;
  const activeCm = Math.max(5, totalPageCm - (currentMargins.left || 2.5) - (currentMargins.right || 2.5));

  currentTabStops.forEach(cm => {
    if (cm > activeCm || cm < 0) return;
    const pct = (cm / activeCm) * 100;
    const marker = document.createElement('div');
    marker.className = 'ruler-tab-stop';
    marker.dataset.cm = cm;
    marker.style.left = pct + '%';
    marker.title = `Sekme Durağı: ${cm} cm (Taşımak için sürükleyin, kaldırmak için dokunun)`;
    setupTabStopDragging(marker, cm, activeCm);
    scale.appendChild(marker);
  });
}

function handleTabAction() {
  const p = getActiveParagraph();
  if (!p) return;

  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return;

  const range = sel.getRangeAt(0);
  range.deleteContents();

  const span = document.createElement('span');
  span.className = 'udf-tab-space';
  span.setAttribute('contenteditable', 'false');
  span.style.display = 'inline-block';
  span.style.width = '0px';
  span.textContent = '\u200B';

  range.insertNode(span);
  range.setStartAfter(span);
  range.setEndAfter(span);
  sel.removeAllRanges();
  sel.addRange(range);

  // Paragrafın durakları yoksa ama cetvelde durak görünüyorsa (aynı paragraf) kalıcı yap
  if ((!p.dataset.tabStops) && currentTabStops && currentTabStops.length > 0) {
    p.dataset.tabStops = currentTabStops.map(v => Math.round(v * 100) / 100).join(',');
  }

  // Bu paragraftaki tüm sekmeleri soldan sağa yeniden hizala
  realignTabsInParagraph(p);

  updateCounts();
  debouncedPagination();
  if (typeof markDirty === 'function') markDirty();
  if (window.CanHistory) CanHistory.commit();
}

function setupMarkerDragging(markerId, type, activeCm) {
  const marker = document.getElementById(markerId);
  const scale = document.getElementById('ruler-scale');
  if (!marker || !scale) return;

  function onStart(e) {
    e.preventDefault();
    e.stopPropagation();
    activeDragMarker = markerId;

    const moveHandler = (moveEvent) => {
      const clientX = moveEvent.touches ? moveEvent.touches[0].clientX : moveEvent.clientX;
      const rect = scale.getBoundingClientRect();
      const x = clientX - rect.left;
      const pct = Math.max(0, Math.min(1, x / rect.width));
      const cm = Math.round((pct * activeCm) * 4) / 4;

      if (type === 'firstLine') {
        marker.style.left = (pct * 100) + '%';
        setFirstLineIndent(cm);
      } else if (type === 'leftIndent') {
        marker.style.left = (pct * 100) + '%';
        setLeftIndent(cm);
      } else if (type === 'rightIndent') {
        const rightPct = 1 - pct;
        marker.style.right = (rightPct * 100) + '%';
        marker.style.left = 'auto';
        const rightCm = Math.round((rightPct * activeCm) * 4) / 4;
        setRightIndent(rightCm);
      }
    };

    const upHandler = () => {
      window.removeEventListener('mousemove', moveHandler);
      window.removeEventListener('mouseup', upHandler);
      window.removeEventListener('touchmove', moveHandler);
      window.removeEventListener('touchend', upHandler);
      setTimeout(() => { activeDragMarker = null; }, 120);
    };

    window.addEventListener('mousemove', moveHandler);
    window.addEventListener('mouseup', upHandler);
    window.addEventListener('touchmove', moveHandler, { passive: false });
    window.addEventListener('touchend', upHandler);
  }

  marker.addEventListener('mousedown', onStart);
  marker.addEventListener('touchstart', onStart, { passive: false });
}

function toggleRuler() {
  const container = document.getElementById('ruler-container');
  const btn = document.getElementById('btn-toggle-ruler');
  isRulerVisible = !isRulerVisible;
  if (isRulerVisible) {
    container.classList.remove('hidden');
    btn.classList.add('active');
  } else {
    container.classList.add('hidden');
    btn.classList.remove('active');
  }
}

function updateRulerFromActiveParagraph() {
  const p = getActiveParagraph();
  if (!p) return;

  const firstMarker = document.getElementById('marker-first-line');
  const leftMarker = document.getElementById('marker-left-indent');
  const rightMarker = document.getElementById('marker-right-indent');
  if (!firstMarker || !leftMarker || !rightMarker) return;

  const isLandscape = currentMargins.orientation === 'landscape';
  const totalPageCm = isLandscape ? 29.7 : 21.0;
  const activeCm = Math.max(5, totalPageCm - (currentMargins.left || 2.5) - (currentMargins.right || 2.5));

  let firstCm = parseToCm(p.style.textIndent || window.getComputedStyle(p).textIndent);
  let leftCm = parseToCm(p.style.marginLeft || window.getComputedStyle(p).marginLeft);
  let rightCm = parseToCm(p.style.marginRight || window.getComputedStyle(p).marginRight);

  firstMarker.style.left = Math.min(100, Math.max(0, (firstCm / activeCm) * 100)) + '%';
  leftMarker.style.left = Math.min(100, Math.max(0, (leftCm / activeCm) * 100)) + '%';
  rightMarker.style.right = Math.min(100, Math.max(0, (rightCm / activeCm) * 100)) + '%';
  rightMarker.style.left = 'auto';

  // Paragrafın sekme duraklarını güncelle
  if (p.dataset && p.dataset.tabStops) {
    currentTabStops = p.dataset.tabStops.split(',').map(s => parseFloat(s)).filter(s => !isNaN(s));
  } else if (p.querySelector('.udf-tab-label')) {
    currentTabStops = [4.94];
  } else {
    currentTabStops = [];
  }
  renderTabStopsOnRuler();
}

function parseToCm(valStr) {
  if (!valStr) return 0;
  valStr = (valStr + '').trim();
  if (valStr.endsWith('cm')) {
    return parseFloat(valStr) || 0;
  }
  if (valStr.endsWith('px')) {
    return Math.round((parseFloat(valStr) / 37.8) * 4) / 4;
  }
  if (valStr.endsWith('pt')) {
    return Math.round((parseFloat(valStr) / 28.35) * 4) / 4;
  }
  return parseFloat(valStr) || 0;
}

function setFirstLineIndent(cm) {
  const targets = getSelectedParagraphs();
  targets.forEach(p => {
    p.style.textIndent = cm + 'cm';
  });
  updateCounts();
}

function setLeftIndent(cm) {
  const targets = getSelectedParagraphs();
  targets.forEach(p => {
    p.style.marginLeft = cm + 'cm';
  });
  updateCounts();
}

function setRightIndent(cm) {
  const targets = getSelectedParagraphs();
  targets.forEach(p => {
    p.style.marginRight = cm + 'cm';
  });
  updateCounts();
}

// --- PARAGRAF AYARLARI MODAL MOTORU ---
function openParagraphModal() {
  saveCurrentSelection();
  const p = getActiveParagraph();
  
  let before = 4;
  let after = 8;
  let firstLine = 1.25;
  let left = 0;
  let lineSpacing = '1.35';
  let align = 'justify';

  if (p) {
    if (p.style.marginTop) before = parseFloat(p.style.marginTop) || 0;
    if (p.style.marginBottom) after = parseFloat(p.style.marginBottom) || 0;
    if (p.style.textIndent) firstLine = parseToCm(p.style.textIndent);
    if (p.style.marginLeft) left = parseToCm(p.style.marginLeft);
    if (p.style.lineHeight) lineSpacing = p.style.lineHeight;
    if (p.style.textAlign) align = p.style.textAlign;
  }

  document.getElementById('p-space-before').value = before;
  document.getElementById('p-space-after').value = after;
  document.getElementById('p-first-line').value = firstLine;
  document.getElementById('p-left-indent').value = left;
  document.getElementById('p-line-spacing').value = lineSpacing;
  setPAlign(align);
  setParagraphScope('selected');

  updateParagraphPreview();
  openModal('modal-paragraph-settings');
}

function setParagraphScope(scope) {
  paragraphScope = scope;
  document.getElementById('btn-scope-selected').classList.toggle('active', scope === 'selected');
  document.getElementById('btn-scope-all').classList.toggle('active', scope === 'all');
}

function setPAlign(align) {
  currentPAlign = align;
  ['left', 'center', 'right', 'justify'].forEach(a => {
    const btn = document.getElementById('p-align-' + a);
    if (btn) btn.classList.toggle('active', a === align);
  });
  updateParagraphPreview();
}

function stepParagraphValue(id, delta) {
  const input = document.getElementById('p-' + id);
  if (!input) return;
  let val = parseFloat(input.value) || 0;
  val = Math.max(0, Math.round((val + delta) * 100) / 100);
  input.value = val;
  updateParagraphPreview();
}

function setStepperVal(inputId, val) {
  const input = document.getElementById(inputId);
  if (input) {
    input.value = val;
    updateParagraphPreview();
  }
}

function updateParagraphPreview() {
  const preview = document.getElementById('p-live-preview');
  if (!preview) return;

  const before = document.getElementById('p-space-before').value + 'pt';
  const after = document.getElementById('p-space-after').value + 'pt';
  const firstLine = document.getElementById('p-first-line').value + 'cm';
  const left = document.getElementById('p-left-indent').value + 'cm';
  const lineSpacing = document.getElementById('p-line-spacing').value;

  preview.style.marginTop = before;
  preview.style.marginBottom = after;
  preview.style.textIndent = firstLine;
  preview.style.marginLeft = left;
  preview.style.lineHeight = lineSpacing;
  preview.style.textAlign = currentPAlign;
}

function applyParagraphSettings() {
  const before = document.getElementById('p-space-before').value + 'pt';
  const after = document.getElementById('p-space-after').value + 'pt';
  const firstLine = document.getElementById('p-first-line').value + 'cm';
  const left = document.getElementById('p-left-indent').value + 'cm';
  const lineSpacing = document.getElementById('p-line-spacing').value;

  let targets = [];
  if (paragraphScope === 'all') {
    targets = Array.from(document.getElementById('editor-content').querySelectorAll('p, li, blockquote'));
  } else {
    targets = getSelectedParagraphs();
  }

  targets.forEach(p => {
    p.style.marginTop = before;
    p.style.marginBottom = after;
    p.style.textIndent = firstLine;
    p.style.marginLeft = left;
    p.style.lineHeight = lineSpacing;
    p.style.textAlign = currentPAlign;
  });

  closeModal('modal-paragraph-settings');
  updateRulerFromActiveParagraph();
  updateCounts();
  debouncedPagination();
  setTimeout(() => {
    restoreCurrentSelection();
    const editor = document.getElementById('editor-content');
    if (editor) editor.focus();
  }, 100);
}

// Gelişmiş Maddeleme ve Numaralandırma
function insertCustomList(type) {
  let listHtml = '';
  if (type === 'decimal') {
    format('insertOrderedList');
    return;
  } else if (type === 'disc') {
    format('insertUnorderedList');
    return;
  } else if (type === 'legal') {
    listHtml = `
      <p style="text-align: justify; margin-left: 20px; text-indent: 0; margin-top: 4pt; margin-bottom: 6pt;"><strong>1.1-)</strong> [Birinci alt madde açıklaması...]</p>
      <p style="text-align: justify; margin-left: 20px; text-indent: 0; margin-top: 4pt; margin-bottom: 6pt;"><strong>1.2-)</strong> [İkinci alt madde açıklaması...]</p>
      <p style="text-align: justify;"><br></p>
    `;
  } else if (type === 'roman') {
    listHtml = `
      <ol style="list-style-type: upper-roman; padding-left: 24px;">
        <li>[Birinci Hukuki Sebep / Delil]</li>
        <li>[İkinci Hukuki Sebep / Delil]</li>
      </ol>
      <p style="text-align: justify;"><br></p>
    `;
  } else if (type === 'alpha') {
    listHtml = `
      <ol style="list-style-type: lower-alpha; padding-left: 24px;">
        <li>[Talep bendi a)]</li>
        <li>[Talep bendi b)]</li>
      </ol>
      <p style="text-align: justify;"><br></p>
    `;
  } else if (type === 'square') {
    listHtml = `
      <ul style="list-style-type: square; padding-left: 24px;">
        <li>[Madde 1]</li>
        <li>[Madde 2]</li>
      </ul>
      <p style="text-align: justify;"><br></p>
    `;
  } else if (type === 'arrow') {
    listHtml = `
      <ul style="list-style-type: '➢ '; padding-left: 24px;">
        <li>[Önemli Açıklama 1]</li>
        <li>[Önemli Açıklama 2]</li>
      </ul>
      <p style="text-align: justify;"><br></p>
    `;
  }

  if (listHtml) {
    document.execCommand('insertHTML', false, listHtml);
  }
}

// Tablo Ekleme
function insertTable() {
  const tableHtml = `
    <table border="1">
      <thead>
        <tr>
          <th style="width: 15%;">S. No</th>
          <th style="width: 55%;">Talep Kalemi / Delil Açıklaması</th>
          <th style="width: 30%;">Tutar (TL)</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>1</td>
          <td>Kıdem Tazminatı</td>
          <td>... TL</td>
        </tr>
        <tr>
          <td>2</td>
          <td>İhbar Tazminatı</td>
          <td>... TL</td>
        </tr>
      </tbody>
    </table>
    <p style="text-align: justify;"><br></p>
  `;
  document.execCommand('insertHTML', false, tableHtml);
}

// Resim Seçiciyi Tetikleme
function triggerImagePicker() {
  if (window.AndroidBridge && window.AndroidBridge.pickImage) {
    window.AndroidBridge.pickImage();
  } else {
    alert("Resim seçici Android ortamında çalışır.");
  }
}

function insertImageBase64(base64Data) {
  const imgHtml = `<p style="text-align: center;"><img src="${base64Data}" alt="Dilekçe Eki / Belge Delili" style="max-width: 95%; max-height: 400px; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);"><br><em style="font-size: 10pt; color: #666;">(Ek / Delil Görseli)</em></p><p style="text-align: justify;"><br></p>`;
  document.execCommand('insertHTML', false, imgHtml);
  updateCounts();
}

// --- MODAL YÖNETİMİ & SEÇİM KORUMA ---
function saveCurrentSelection() {
  recordCurrentSelection();
}

function restoreCurrentSelection() {
  const editor = document.getElementById('editor-content');
  if (savedSelectionRange) {
    try {
      if (editor && document.activeElement !== editor) {
        editor.focus();
      }
      const sel = window.getSelection();
      if (sel) {
        sel.removeAllRanges();
        sel.addRange(savedSelectionRange);
        return true;
      }
    } catch (e) {
      console.warn('Selection range restore failed:', e);
    }
  }

  // Yedek geri yükleme: Eğer range kaybolduysa son seçili paragrafları seç
  if (lastSelectedParagraphs && lastSelectedParagraphs.length > 0 && editor) {
    try {
      const valid = lastSelectedParagraphs.filter(p => editor.contains(p));
      if (valid.length > 0) {
        if (document.activeElement !== editor) editor.focus();
        const sel = window.getSelection();
        if (sel) {
          const r = document.createRange();
          r.setStartBefore(valid[0]);
          r.setEndAfter(valid[valid.length - 1]);
          sel.removeAllRanges();
          sel.addRange(r);
          return true;
        }
      }
    } catch (err) {}
  }
  return false;
}

function openModal(id) {
  document.getElementById(id).classList.add('open');
}

function closeModal(id) {
  document.getElementById(id).classList.remove('open');
  if (id === 'modal-paragraph-settings') {
    setTimeout(restoreCurrentSelection, 50);
  }
  if (id === 'modal-smartcard-sign' && smartCardPollInterval) {
    clearInterval(smartCardPollInterval);
    smartCardPollInterval = null;
  }
}

function openMobileSignModal() {
  saveCurrentSelection();
  // Kaydedilmiş bilgileri yükle
  const savedOp = localStorage.getItem('udemobile_msign_op');
  const savedPhone = localStorage.getItem('udemobile_msign_phone');
  const savedTckn = localStorage.getItem('udemobile_msign_tckn');
  const savedSigner = localStorage.getItem('udemobile_signer_name');

  if (savedOp && document.getElementById('msign-operator')) document.getElementById('msign-operator').value = savedOp;
  if (savedPhone && document.getElementById('msign-phone')) document.getElementById('msign-phone').value = savedPhone;
  if (savedTckn && document.getElementById('msign-tckn')) document.getElementById('msign-tckn').value = savedTckn;
  if (savedSigner && document.getElementById('msign-signer-name')) document.getElementById('msign-signer-name').value = savedSigner;

  const statusEl = document.getElementById('msign-status');
  if (statusEl) {
    statusEl.innerHTML = '';
    statusEl.className = 'modal-status';
  }
  const btn = document.getElementById('btn-do-msign');
  if (btn) {
    btn.disabled = false;
    btn.textContent = '📱 Mobil İmzala & Mühürle';
  }

  openModal('modal-mobile-sign');
}

function onMobileSignInputChanged() {
  const op = document.getElementById('msign-operator').value;
  const phone = document.getElementById('msign-phone').value.trim();
  const tckn = document.getElementById('msign-tckn').value.trim();
  const signerName = document.getElementById('msign-signer-name').value.trim();

  if (op) localStorage.setItem('udemobile_msign_op', op);
  if (phone) localStorage.setItem('udemobile_msign_phone', phone);
  if (tckn) localStorage.setItem('udemobile_msign_tckn', tckn);
  if (signerName) localStorage.setItem('udemobile_signer_name', signerName);
}

function executeMobileSignInApp() {
  const opSelect = document.getElementById('msign-operator').value;
  const phone = document.getElementById('msign-phone').value.trim();
  const tckn = document.getElementById('msign-tckn').value.trim();
  const signerName = (document.getElementById('msign-signer-name') ? document.getElementById('msign-signer-name').value.trim() : 'Av. Can KIZILYAR') || 'Av. Can KIZILYAR';
  const statusEl = document.getElementById('msign-status');
  const btn = document.getElementById('btn-do-msign');

  if (phone.length < 10) {
    statusEl.style.color = '#C62828';
    statusEl.textContent = 'Lütfen geçerli bir telefon numarası giriniz (örn: 05xxxxxxxxx).';
    return;
  }
  if (tckn.length !== 11) {
    statusEl.style.color = '#C62828';
    statusEl.textContent = 'Lütfen 11 haneli T.C. Kimlik numaranızı giriniz.';
    return;
  }

  // Bilgileri kalıcı hafızaya yaz
  onMobileSignInputChanged();

  // UYAP MobilImzaSigner operatör kodları: 1 = Turkcell, 2 = Türk Telekom, 3 = Vodafone
  let opCode = 1;
  let opName = 'Turkcell';
  if (opSelect === 'TURK_TELEKOM') {
    opCode = 2;
    opName = 'Türk Telekom';
  } else if (opSelect === 'VODAFONE') {
    opCode = 3;
    opName = 'Vodafone';
  }

  btn.disabled = true;
  statusEl.style.color = '#1565C0';
  statusEl.innerHTML = `
    <div style="padding: 10px; background-color: #E3F2FD; border: 1px solid #90CAF9; border-radius: 6px;">
      <div style="font-weight: bold; margin-bottom: 4px;">📡 UYAP &amp; ${opName} Mobil İmza Gateway Bağlantısı Kuruluyor...</div>
      <div style="font-size: 11px; color: #1976D2;">Doküman özeti hesaplanıyor ve SIM karta istek gönderiliyor.</div>
    </div>
  `;

  if (window.AndroidBridge && window.AndroidBridge.performMobileSign) {
    const docData = getStructuredDocument();
    const structured = (typeof docData === 'string') ? docData : JSON.stringify(docData);
    try { window.AndroidBridge.setDocModified(isDocumentModified()); } catch (e) {}
    window.AndroidBridge.performMobileSign(phone, opCode, tckn, signerName, structured);
  } else {
    statusEl.style.color = '#C62828';
    statusEl.textContent = 'Mobil imza motoru Android uygulaması içinde çalışır.';
    btn.disabled = false;
  }
}

window.onMobileSignWaiting = function(fingerPrint, apTransId) {
  const statusEl = document.getElementById('msign-status');
  if (!statusEl) return;
  statusEl.innerHTML = `
    <div style="padding: 12px; background-color: #FFF8E1; border: 1px solid #FFE082; border-radius: 8px; margin-top: 4px;">
      <div style="font-weight: bold; color: #E65100; font-size: 13px; margin-bottom: 6px;">
        🔔 SIM KARTINIZA ONAY BİLDİRİMİ GÖNDERİLDİ!
      </div>
      <div style="margin: 8px 0; background-color: #FFF; border: 2px dashed #FFB300; border-radius: 6px; padding: 10px; text-align: center;">
        <span style="font-size: 11px; color: #555; display: block; margin-bottom: 2px;">Telefon Ekranındaki Parfüm / Doğrulama Kodu:</span>
        <strong style="font-size: 24px; color: #0D47A1; letter-spacing: 3px;">${fingerPrint || '----'}</strong>
      </div>
      <div style="font-size: 11.5px; color: #4E342E; line-height: 1.4;">
        Lütfen telefonunuza gelen operatör bildirim ekranındaki kodun yukarıdaki kodla <strong>birebir aynı</strong> olduğunu kontrol edip telefonunuzdan <strong>Mobil İmza PIN</strong> kodunuzu giriniz.
      </div>
      <div style="margin-top: 8px; font-size: 11px; color: #795548; display: flex; align-items: center; justify-content: center; gap: 6px;">
        <span class="spinner" style="display:inline-block; width:12px; height:12px; border:2px solid #FF9800; border-top-color:transparent; border-radius:50%; animation:spin 1s linear infinite;"></span>
        <span>Kullanıcı PIN onayı bekleniyor...</span>
      </div>
    </div>
  `;
};

window.onMobileSignFailed = function(errMsg) {
  const statusEl = document.getElementById('msign-status');
  const btn = document.getElementById('btn-do-msign');
  if (btn) btn.disabled = false;
  if (!statusEl) return;
  statusEl.innerHTML = `
    <div style="padding: 10px; background-color: #FFEBEE; border: 1px solid #FFCDD2; border-radius: 6px; color: #C62828;">
      <strong>❌ Mobil İmza Başarısız:</strong><br>
      <span style="font-size: 11.5px;">${errMsg || 'İşlem tamamlanamadı.'}</span>
    </div>
  `;
};

window.onMobileSignSuccess = function(hash, sigInfo, signerName, tckn, opName) {
  const statusEl = document.getElementById('msign-status');
  if (statusEl) {
    statusEl.innerHTML = `
      <div style="padding: 10px; background-color: #E8F5E9; border: 1px solid #C8E6C9; border-radius: 6px; color: #2E7D32;">
        <strong>✓ Mobil İmza Başarıyla Tamamlandı!</strong><br>
        <span style="font-size: 11.5px;">TÜBİTAK UEKAE MA3 &amp; UYAP standardında mühürlendi.</span>
      </div>
    `;
  }

  // Belgeye resmi mobil imza bloğunu mühürle
  const now = new Date().toLocaleString('tr-TR');
  const maskedTckn = (tckn && tckn.length === 11) ? (tckn.substring(0, 3) + '*****' + tckn.substring(8)) : (tckn || '***');
  const phone = document.getElementById('msign-phone') ? document.getElementById('msign-phone').value.trim() : '';
  const maskedPhone = phone.length >= 10 ? (phone.substring(0, 4) + '***' + phone.substring(phone.length - 2)) : phone;

  const sealHtml = `
    <div class="official-signature-seal" style="text-align: right; margin-top: 14px; margin-bottom: 8px;">
      <div style="border: 2px double #1565C0; background-color: #F8FAFC; padding: 12px 16px; border-radius: 6px; display: inline-block; text-align: left; max-width: 90%;">
        <div style="font-weight: bold; font-size: 11pt; color: #0D47A1; margin-bottom: 4px;">
          📱 GÜVENLİ ELEKTRONİK MOBİL İMZA İLE İMZALANMIŞTIR
        </div>
        <div style="font-size: 10pt; color: #1A237E; line-height: 1.35;">
          <strong>İmzacı:</strong> ${signerName}<br>
          <strong>Operatör &amp; Hat:</strong> ${opName} Mobil İmza (${maskedPhone})<br>
          <strong>T.C. Kimlik No:</strong> ${maskedTckn}<br>
          <strong>İmza Zamanı:</strong> ${now}<br>
          <strong>Doğrulama Özeti (SHA-256):</strong> <code>${hash}</code> (5070 S.K.)
        </div>
      </div>
    </div>
    <p style="text-align: justify;"><br></p>
  `;

  // NOT: İmza mührü belge gövdesine EKLENMEZ. Gövdeye eklemek imzalanan içeriği değiştirir ve
  // önceki/yeni imzaları geçersiz kılar. İmza bilgisi üstteki imza şeridinde gösterilir.
  void sealHtml;

  setTimeout(() => {
    closeModal('modal-mobile-sign');
    if (sigInfo) {
      currentDocSignature = sigInfo;
      updateSignatureBanner(sigInfo);
    }
  }, 900);
};

let smartCardPollInterval = null;
let currentSmartCardCerts = [];

function openSmartCardSignModal() {
  saveCurrentSelection();

  const pinEl = document.getElementById('sc-pin');
  if (pinEl) {
    pinEl.value = '';
    pinEl.disabled = true;
    pinEl.placeholder = 'Kart takıldığında PIN girilebilir';
  }
  const statusEl = document.getElementById('sc-status');
  if (statusEl) {
    statusEl.innerHTML = '';
    statusEl.className = 'modal-status';
  }
  const btn = document.getElementById('btn-do-eimza');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Kart Bekleniyor...';
    btn.style.backgroundColor = '#90A4AE';
  }

  // Varsayılan kart durumu: Takılı değil
  setCardBadgeState(false, 'E-İmza Kartı Algılanamadı', 'Lütfen akıllı kartınızı veya tokenınızı Type-C OTG adaptörüyle telefonunuza bağlayınız.', 'Takılı cihaz yok', '--');

  openModal('modal-smartcard-sign');

  // Hemen sorgula
  refreshSmartCardStatus();

  // Her 2 saniyede bir kart durumunu otomatik kontrol et
  if (smartCardPollInterval) clearInterval(smartCardPollInterval);
  smartCardPollInterval = setInterval(() => {
    refreshSmartCardStatus();
  }, 2000);
}

function refreshSmartCardStatus() {
  if (window.AndroidBridge && window.AndroidBridge.checkSmartCardStatus) {
    window.AndroidBridge.checkSmartCardStatus();
  } else {
    onSmartCardStatusUpdated({
      connected: false,
      message: "Android donanım köprüsü aktif değil veya servis yanıt vermiyor."
    });
  }
}

function setCardBadgeState(connected, title, desc, reader, validity) {
  const badge = document.getElementById('cert-status-badge');
  const cardBox = document.getElementById('cert-card-box');
  const titleEl = document.getElementById('cert-display-name');
  const issuerEl = document.getElementById('cert-display-issuer');
  const typeEl = document.getElementById('cert-display-type');
  const validityEl = document.getElementById('cert-display-validity');
  const noCardBox = document.getElementById('sc-no-card-box');
  const certContainer = document.getElementById('sc-cert-container');
  const pinEl = document.getElementById('sc-pin');
  const btn = document.getElementById('btn-do-eimza');

  if (connected) {
    if (badge) {
      badge.style.backgroundColor = '#2E7D32';
      badge.textContent = '🟢 KART AKTİF (OTG BAĞLI)';
    }
    if (cardBox) {
      cardBox.style.background = 'linear-gradient(135deg, #1B5E20, #2E7D32)';
    }
    if (noCardBox) noCardBox.style.display = 'none';
    if (certContainer) certContainer.style.display = 'block';
    if (pinEl) {
      pinEl.disabled = false;
      pinEl.placeholder = 'Akıllı kart PIN kodunu giriniz';
    }
    if (btn) {
      btn.disabled = false;
      btn.textContent = '✍️ 5070 S.K. İle İmzala';
      btn.style.backgroundColor = '#1565C0';
    }
  } else {
    if (badge) {
      badge.style.backgroundColor = '#D32F2F';
      badge.textContent = '🔴 KART TAKILI DEĞİL';
    }
    if (cardBox) {
      cardBox.style.background = 'linear-gradient(135deg, #37474F, #455A64)';
    }
    if (noCardBox) noCardBox.style.display = 'block';
    if (certContainer) certContainer.style.display = 'none';
    if (pinEl) {
      pinEl.value = '';
      pinEl.disabled = true;
      pinEl.placeholder = 'Kart takıldığında PIN girilebilir';
    }
    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Kart Bekleniyor...';
      btn.style.backgroundColor = '#90A4AE';
    }
  }

  if (titleEl) titleEl.textContent = title;
  if (issuerEl) issuerEl.textContent = desc;
  if (typeEl) typeEl.textContent = 'Okuyucu: ' + (reader || 'Cihaz Yok');
  if (validityEl) validityEl.textContent = 'Geçerlilik: ' + (validity || '--');
}

// AndroidBridge tarafından çağrılan callback
window.onSmartCardStatusUpdated = function(data) {
  if (typeof data === 'string') {
    try { data = JSON.parse(data); } catch(e) {}
  }

  if (!data || !data.connected || !data.certificates || data.certificates.length === 0) {
    currentSmartCardCerts = [];
    const msg = data && data.message ? data.message : 'Lütfen akıllı kartınızı veya tokenınızı Type-C OTG adaptörüyle telefonunuza bağlayınız.';
    setCardBadgeState(false, 'E-İmza Kartı Algılanamadı', msg, 'Takılı cihaz yok', '--');
    return;
  }

  currentSmartCardCerts = data.certificates;
  const certSelect = document.getElementById('sc-cert-select');
  if (certSelect) {
    certSelect.innerHTML = '';
    currentSmartCardCerts.forEach((c, idx) => {
      const opt = document.createElement('option');
      opt.value = c.id || idx;
      let label = c.subject || 'Nitelikli Elektronik Sertifika';
      const m = label.match(/CN=([^,]+)/i);
      if (m) label = m[1].trim();
      let iss = 'NES';
      if (c.issuer) {
        const oMatch = c.issuer.match(/O=([^,]+)/i);
        const cnMatch = c.issuer.match(/CN=([^,]+)/i);
        if (oMatch) {
          iss = oMatch[1].trim();
        } else if (cnMatch) {
          iss = cnMatch[1].trim();
        } else {
          iss = c.issuer.split(',')[0].trim();
        }
      }
      opt.textContent = `${label} (${iss})`;
      certSelect.appendChild(opt);
    });
  }

  onRealCertSelected();
};

function onRealCertSelected() {
  if (!currentSmartCardCerts || currentSmartCardCerts.length === 0) return;
  const certSelect = document.getElementById('sc-cert-select');
  let selectedCert = currentSmartCardCerts[0];
  if (certSelect && certSelect.value) {
    const found = currentSmartCardCerts.find(c => (c.id === certSelect.value));
    if (found) selectedCert = found;
  }

  // CN parse et
  let subjectName = selectedCert.subject || 'Nitelikli Elektronik İmza Sahibi';
  const cnMatch = subjectName.match(/CN=([^,]+)/i);
  if (cnMatch) {
    subjectName = cnMatch[1].trim();
  }

  // Issuer parse et
  let issuerText = selectedCert.issuer || 'Nitelikli Elektronik Sertifika Hizmet Sağlayıcısı';
  const oMatch = issuerText.match(/O=([^,]+)/i);
  const cnMatchIssuer = issuerText.match(/CN=([^,]+)/i);
  if (oMatch) {
    issuerText = oMatch[1].trim();
  } else if (cnMatchIssuer) {
    issuerText = cnMatchIssuer[1].trim();
  } else if (issuerText.includes(',')) {
    issuerText = issuerText.split(',')[0].trim();
  }

  let validity = selectedCert.validUntil || '--';
  if (validity.length > 10) {
    try {
      const d = new Date(validity);
      if (!isNaN(d.getTime())) {
        validity = d.toLocaleDateString('tr-TR');
      }
    } catch(e) {}
  }

  setCardBadgeState(
    true,
    subjectName,
    issuerText + (selectedCert.serial ? (' • Seri: ' + selectedCert.serial) : ''),
    selectedCert.terminal || 'CCID Akıllı Kart Okuyucu',
    validity
  );
}

function togglePinVisibility() {
  const pinInput = document.getElementById('sc-pin');
  if (!pinInput) return;
  pinInput.type = (pinInput.type === 'password') ? 'text' : 'password';
}

function executeSmartCardSignInApp() {
  const certSelect = document.getElementById('sc-cert-select');
  const pin = document.getElementById('sc-pin').value.trim();
  const statusEl = document.getElementById('sc-status');
  const btn = document.getElementById('btn-do-eimza');

  if (!currentSmartCardCerts || currentSmartCardCerts.length === 0) {
    statusEl.style.color = '#C62828';
    statusEl.textContent = 'İşlem için takılı bir akıllı kart bulunamadı. Lütfen kartınızı bağlayınız.';
    return;
  }

  if (!pin || pin.length < 4) {
    statusEl.style.color = '#C62828';
    statusEl.textContent = 'Lütfen akıllı kartınızın PIN kodunu giriniz (en az 4 hane).';
    return;
  }

  const certId = (certSelect && certSelect.value) ? certSelect.value : (currentSmartCardCerts[0].id || "");

  btn.disabled = true;
  statusEl.style.color = '#1565C0';
  statusEl.innerHTML = '⏳ <strong>Adım 1/3:</strong> Akıllı kart güvenli oturumu açılıyor ve PIN doğrulanıyor...';

  setTimeout(() => {
    statusEl.innerHTML = '🔐 <strong>Adım 2/3:</strong> CAdES-BES donanımsal imza üretiliyor (TÜBİTAK UEKAE MA3)...';

    const docData = getStructuredDocument();
    const structured = (typeof docData === 'string') ? docData : JSON.stringify(docData);
    if (window.AndroidBridge && window.AndroidBridge.signWithRealSmartCard) {
      try { window.AndroidBridge.setDocModified(isDocumentModified()); } catch (e) {}
      window.AndroidBridge.signWithRealSmartCard(certId, pin, structured);
    } else {
      setTimeout(() => {
        onRealSignFailed("Android donanım köprüsüne erişilemedi.");
      }, 500);
    }
  }, 400);
}

window.onRealSignFailed = function(errMsg) {
  const statusEl = document.getElementById('sc-status');
  const btn = document.getElementById('btn-do-eimza');
  if (statusEl) {
    statusEl.style.color = '#C62828';
    statusEl.innerHTML = '❌ <strong>İmza Başarısız:</strong> ' + (errMsg || 'Kart hatası veya hatalı PIN.');
  }
  if (btn) {
    btn.disabled = false;
    btn.textContent = '✍️ Tekrar Dene';
  }
};

window.onRealSignSuccess = function(realHash, sigInfo) {
  const statusEl = document.getElementById('sc-status');
  if (statusEl) {
    statusEl.style.color = '#2E7D32';
    statusEl.innerHTML = '✓ <strong>İmzalama Başarılı!</strong> CAdES-BES imzası UDF arşivine mühürlendi.';
  }

  const titleEl = document.getElementById('cert-display-name');
  const signerName = titleEl ? titleEl.textContent : 'Avukat';
  const issuerEl = document.getElementById('cert-display-issuer');
  const issuerName = issuerEl ? issuerEl.textContent : 'Kamu Sertifikasyon Merkezi';
  const now = new Date().toLocaleString('tr-TR');

  const sealHtml = `
    <div class="official-signature-seal" style="text-align: right; margin-top: 14px; margin-bottom: 8px;">
      <div style="border: 2px double #0D47A1; background-color: #F8FAFC; padding: 12px 16px; border-radius: 6px; display: inline-block; text-align: left; max-width: 90%;">
        <div style="font-weight: bold; font-size: 11pt; color: #0D47A1; margin-bottom: 4px;">
          ✍️ 5070 SAYILI KANUN UYARINCA E-İMZA İLE İMZALANMIŞTIR
        </div>
        <div style="font-size: 10pt; color: #1A237E; line-height: 1.35;">
          <strong>Sertifika Sahibi:</strong> ${signerName}<br>
          <strong>Sertifika Sağlayıcı (NES):</strong> ${issuerName}<br>
          <strong>İmza Standardı:</strong> CAdES-BES (5070 S.K. m. 4 ve m. 5)<br>
          <strong>İmza Zamanı:</strong> ${now}<br>
          <strong>Doğrulama Özeti (SHA-256):</strong> <code>${realHash}</code>
        </div>
      </div>
    </div>
    <p style="text-align: justify;"><br></p>
  `;

  if (sigInfo) {
    let parsedInfo = sigInfo;
    if (typeof sigInfo === 'string') {
      try { parsedInfo = JSON.parse(sigInfo); } catch(e) {}
    }
    if (window.onDocumentSignatureChecked) {
      window.onDocumentSignatureChecked(parsedInfo);
    }
  }

  // İmza mührü belge gövdesine eklenmez (imzalı içeriği değiştirir); bilgi imza şeridinde gösterilir.
  void sealHtml;
  setTimeout(() => {
    closeModal('modal-smartcard-sign');
  }, 600);
};

// Hem E-İmza Hem Mobil İmza Arka Plandan Döndüğünde Çağrılan Metot
function onBackgroundSignComplete(type, provider, signerName, hash) {
  const now = new Date().toLocaleString('tr-TR');
  const isMobil = (type === "MOBIL_IMZA");

  let sealHtml = '';
  if (isMobil) {
    const savedPhone = localStorage.getItem('udemobile_msign_phone') || '05*********';
    const savedTckn = localStorage.getItem('udemobile_msign_tckn') || '***********';
    const maskedTckn = savedTckn.length === 11 ? (savedTckn.substring(0, 3) + '*****' + savedTckn.substring(8)) : savedTckn;
    const maskedPhone = savedPhone.length >= 10 ? (savedPhone.substring(0, 4) + '***' + savedPhone.substring(savedPhone.length - 2)) : savedPhone;

    sealHtml = `
      <div class="official-signature-seal" style="text-align: right; margin-top: 14px; margin-bottom: 8px;">
        <div style="border: 2px double #1565C0; background-color: #F8FAFC; padding: 12px 16px; border-radius: 6px; display: inline-block; text-align: left; max-width: 90%;">
          <div style="font-weight: bold; font-size: 11pt; color: #0D47A1; margin-bottom: 4px;">
            📱 GÜVENLİ ELEKTRONİK MOBİL İMZA İLE İMZALANMIŞTIR
          </div>
          <div style="font-size: 10pt; color: #1A237E; line-height: 1.35;">
            <strong>Operatör:</strong> ${provider} Mobil İmza Servisi<br>
            <strong>İmzalayan:</strong> ${signerName} &nbsp;|&nbsp; TCKN: ${maskedTckn} &nbsp;|&nbsp; GSM: ${maskedPhone}<br>
            <strong>İmza Zamanı:</strong> ${now}<br>
            <strong>Doğrulama Özeti (SHA-256):</strong> <code>${hash}</code> (5070 S.K. Uyumlu)
          </div>
        </div>
      </div>
      <p style="text-align: justify;"><br></p>
    `;
    closeModal('modal-mobile-sign');
  } else {
    sealHtml = `
      <div class="official-signature-seal" style="text-align: right; margin-top: 14px; margin-bottom: 8px;">
        <div style="border: 2px double #0D47A1; background-color: #F8FAFC; padding: 12px 16px; border-radius: 6px; display: inline-block; text-align: left; max-width: 90%;">
          <div style="font-weight: bold; font-size: 11pt; color: #0D47A1; margin-bottom: 4px;">
            ✍️ 5070 SAYILI KANUN UYARINCA E-İMZA İLE İMZALANMIŞTIR
          </div>
          <div style="font-size: 10pt; color: #1A237E; line-height: 1.35;">
            <strong>Sertifika Sahibi:</strong> ${signerName}<br>
            <strong>Kart Sağlayıcı:</strong> ${provider} Nitelikli Elektronik Sertifika (NES)<br>
            <strong>İmza Standardı:</strong> CAdES-BES / XAdES (5070 S.K. m. 4 ve m. 5)<br>
            <strong>İmza Zamanı:</strong> ${now}<br>
            <strong>Doğrulama Özeti (SHA-256):</strong> <code>${hash}</code>
          </div>
        </div>
      </div>
      <p style="text-align: justify;"><br></p>
    `;
    closeModal('modal-smartcard-sign');
  }

  insertSignatureSeal(sealHtml);

  if (window.AndroidBridge && window.AndroidBridge.onDocumentSigned) {
    window.AndroidBridge.onDocumentSigned(type, provider, hash);
  }
}

// Şablon Ekleme
function insertTemplate(type) {
  let tpl = '';
  if (type === 'dava') {
    tpl = `
      <p style="text-align: center;"><strong>NÖBETÇİ ASLİYE HUKUK MAHKEMESİ HÂKİMLİĞİ'NE</strong></p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>DAVACI :</strong> [Davacı Ad Soyad / Ünvan - TCKN / VKN]</p>
      <p style="text-align: justify;"><strong>VEKİLİ :</strong> Av. [Adınız Soyadınız] - Adres / UETS</p>
      <p style="text-align: justify;"><strong>DAVALI :</strong> [Davalı Ad Soyad / Ünvan]</p>
      <p style="text-align: justify;"><strong>DAVA DEĞERİ :</strong> [Harca Esas Değer] TL</p>
      <p style="text-align: justify;"><strong>KONU :</strong> [Dava Konusu / Talebin Özeti]</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>AÇIKLAMALAR :</strong></p>
      <p style="text-align: justify; text-indent: 1.25cm; margin-top: 4pt; margin-bottom: 8pt;">1.1-) Müvekkil ile davalı taraf arasında akdedilen sözleşme uyarınca ...</p>
      <p style="text-align: justify; text-indent: 1.25cm; margin-top: 4pt; margin-bottom: 8pt;">1.2-) Davalı taraf edimlerini haksız ve hukuka aykırı olarak yerine getirmemiştir ...</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>HUKUKİ SEBEPLER :</strong> 6100 sayılı HMK, 6098 sayılı TBK, TTK ve ilgili tüm mevzuat.</p>
      <p style="text-align: justify;"><strong>DELİLLER :</strong> Fatura, banka kayıtları, tanık, bilirkişi, yemin ve her türlü yasal delil.</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>NETİCE-İ TALEP :</strong> Yukarıda arz ve izah edilen nedenlerle;</p>
      <p style="text-align: justify; text-indent: 1.25cm; margin-top: 4pt; margin-bottom: 6pt;">1-) Haklı davamızın KABULÜNE,</p>
      <p style="text-align: justify; text-indent: 1.25cm; margin-top: 4pt; margin-bottom: 6pt;">2-) Yargılama giderleri ile vekâlet ücretinin davalı yana tahmiline karar verilmesini saygıyla vekâleten arz ve talep ederiz.</p>
      <p style="text-align: right;"><br></p>
      <p style="text-align: right;"><strong>Davacı Vekili</strong><br>Av. [Ad Soyad]<br><em>(e-imzalıdır)</em></p>
    `;
  } else if (type === 'cevap') {
    tpl = `
      <p style="text-align: center;"><strong>... SULH HUKUK MAHKEMESİ HÂKİMLİĞİ'NE</strong></p>
      <p style="text-align: justify;"><strong>DOSYA NO :</strong> 2026/.... Esas</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>CEVAP VEREN DAVALI :</strong> [Davalı Ad Soyad]</p>
      <p style="text-align: justify;"><strong>VEKİLİ :</strong> Av. [Ad Soyad]</p>
      <p style="text-align: justify;"><strong>DAVACI :</strong> [Davacı Ad Soyad]</p>
      <p style="text-align: justify;"><strong>VEKİLİ :</strong> Av. [Davacı Vekili]</p>
      <p style="text-align: justify;"><strong>KONU :</strong> Dava dilekçesine karşı süresi içinde cevaplarımızın sunulmasından ibarettir.</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>AÇIKLAMALAR :</strong></p>
      <p style="text-align: justify; text-indent: 1.25cm; margin-top: 4pt; margin-bottom: 8pt;">1.1-) Davacı tarafın dava dilekçesindeki iddiaları mesnedsiz ve hukuki dayanaktan yoksun olup davanın reddi gerekmektedir. Şöyle ki;</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>NETİCE-İ TALEP :</strong> Haksız ve hukuki temelden yoksun davanın REDDİNE, yargılama gideri ve vekâlet ücretinin davacıya yükletilmesine karar verilmesini arz ve talep ederiz.</p>
      <p style="text-align: right;"><br></p>
      <p style="text-align: right;"><strong>Davalı Vekili</strong><br>Av. [Ad Soyad]<br><em>(e-imzalıdır)</em></p>
    `;
  } else if (type === 'sure') {
    tpl = `
      <p style="text-align: center;"><strong>... MAHKEMESİ HÂKİMLİĞİ'NE</strong></p>
      <p style="text-align: justify;"><strong>DOSYA NO :</strong> 2026/.... Esas</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>TALEPTE BULUNAN :</strong> Davalı [Ad Soyad]</p>
      <p style="text-align: justify;"><strong>VEKİLİ :</strong> Av. [Ad Soyad]</p>
      <p style="text-align: justify;"><strong>KONU :</strong> HMK m. 127 uyarınca cevap süresinin uzatılması talebimizdir.</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>AÇIKLAMALAR :</strong></p>
      <p style="text-align: justify; text-indent: 1.25cm; margin-top: 4pt; margin-bottom: 8pt;">Mahkemenizin yukarıda numarası yazılı dosyasında dava dilekçesi tarafımıza tebliğ edilmiştir. Dava konusu iddiaların kapsamlı olması, ilgili bilgi ve belgelerin temin edilebilmesi amacıyla tarafımıza HMK m. 127 gereğince 2 HAFTALIK EK CEVAP SÜRESİ verilmesini vekâleten talep ederiz.</p>
      <p style="text-align: right;"><br></p>
      <p style="text-align: right;"><strong>Davalı Vekili</strong><br>Av. [Ad Soyad]<br><em>(e-imzalıdır)</em></p>
    `;
  } else if (type === 'beyan') {
    tpl = `
      <p style="text-align: center;"><strong>... İŞ MAHKEMESİ HÂKİMLİĞİ'NE</strong></p>
      <p style="text-align: justify;"><strong>DOSYA NO :</strong> 2026/.... Esas</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>BEYANDA BULUNAN :</strong> [Davacı / Davalı]</p>
      <p style="text-align: justify;"><strong>VEKİLİ :</strong> Av. [Ad Soyad]</p>
      <p style="text-align: justify;"><strong>KONU :</strong> Bilirkişi raporuna karşı beyan ve itirazlarımızın sunulmasıdır.</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>BEYANLARIMIZ :</strong></p>
      <p style="text-align: justify; text-indent: 1.25cm; margin-top: 4pt; margin-bottom: 8pt;">Dosyaya sunulan bilirkişi raporu usul ve yasaya uygun olmayıp aleyhe hususları kabul etmiyoruz...</p>
      <p style="text-align: right;"><br></p>
      <p style="text-align: right;"><strong>Vekili</strong><br>Av. [Ad Soyad]<br><em>(e-imzalıdır)</em></p>
    `;
  } else if (type === 'istinaf') {
    tpl = `
      <p style="text-align: center;"><strong>İSTANBUL BÖLGE ADLİYE MAHKEMESİ İLGİLİ HUKUK DAİRESİ'NE<br>Gönderilmek Üzere<br>... MAHKEMESİ HÂKİMLİĞİ'NE</strong></p>
      <p style="text-align: justify;"><strong>DOSYA NO :</strong> 2026/.... Esas, 2026/.... Karar</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>İSTİNAF YOLUNA BAŞVURAN :</strong> [Ad Soyad]</p>
      <p style="text-align: justify;"><strong>VEKİLİ :</strong> Av. [Ad Soyad]</p>
      <p style="text-align: justify;"><strong>KONU :</strong> Yerel mahkemenin haksız ve hukuka aykırı kararına karşı istinaf başvuru dilekçemizdir.</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>İSTİNAF SEBEPLERİ :</strong></p>
      <p style="text-align: justify; text-indent: 1.25cm; margin-top: 4pt; margin-bottom: 8pt;">Yerel mahkemece eksik inceleme ve yanılgılı değerlendirme ile karar verilmiştir...</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>NETİCE-İ TALEP :</strong> Yerel mahkeme kararının KALDIRILMASINA ve davanın kabulüne karar verilmesini arz ve talep ederiz.</p>
      <p style="text-align: right;"><br></p>
      <p style="text-align: right;"><strong>İstinaf Eden Vekili</strong><br>Av. [Ad Soyad]<br><em>(e-imzalıdır)</em></p>
    `;
  } else if (type === 'ihtar') {
    tpl = `
      <p style="text-align: center;"><strong>İHTARNAME</strong></p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>İHTAR EDEN :</strong> [Ad Soyad / Şirket Ünvanı]</p>
      <p style="text-align: justify;"><strong>VEKİLİ :</strong> Av. [Ad Soyad]</p>
      <p style="text-align: justify;"><strong>MUHATAP :</strong> [Muhatap Ad Soyad / Şirket Ünvanı]</p>
      <p style="text-align: justify;"><strong>KONU :</strong> ... Sözleşmesinin feshi ile bakiye alacağın ödenmesi ihtarıdır.</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>SAYIN MUHATAP;</strong></p>
      <p style="text-align: justify; text-indent: 1.25cm; margin-top: 4pt; margin-bottom: 8pt;">Aramızda akdedilen sözleşme kapsamındaki borçlarınızı işbu ihtarnamenin tebliğinden itibaren 3 (üç) gün içinde ifa etmeniz, aksi halde yasal yollara müracaat olunacağı ihtar olunur.</p>
      <p style="text-align: right;"><br></p>
      <p style="text-align: right;"><strong>İhtar Eden Vekili</strong><br>Av. [Ad Soyad]<br><em>(e-imzalıdır)</em></p>
    `;
  } else if (type === 'delil') {
    tpl = `
      <p style="text-align: center;"><strong>... ASLİYE HUKUK MAHKEMESİ HÂKİMLİĞİ'NE</strong></p>
      <p style="text-align: justify;"><strong>DOSYA NO :</strong> 2026/.... Esas</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>DELİL BİLDİREN :</strong> [Davacı / Davalı]</p>
      <p style="text-align: justify;"><strong>VEKİLİ :</strong> Av. [Ad Soyad]</p>
      <p style="text-align: justify;"><strong>KONU :</strong> Mahkemenizin ara kararı uyarınca yasal delil listemizin sunulmasıdır.</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>DELİLLERİMİZ :</strong></p>
      <p style="text-align: justify; text-indent: 1.25cm; margin-top: 4pt; margin-bottom: 6pt;">1-) Taraflar arasındaki ... tarihli Sözleşme sureti (Ek-1),</p>
      <p style="text-align: justify; text-indent: 1.25cm; margin-top: 4pt; margin-bottom: 6pt;">2-) ... Bankası hesap hareketleri ve ödeme dekontları (Ek-2),</p>
      <p style="text-align: justify; text-indent: 1.25cm; margin-top: 4pt; margin-bottom: 6pt;">3-) Ticari defter ve kayıtlar, faturalar,</p>
      <p style="text-align: justify; text-indent: 1.25cm; margin-top: 4pt; margin-bottom: 6pt;">4-) Bilirkişi incelemesi, keşif,</p>
      <p style="text-align: justify; text-indent: 1.25cm; margin-top: 4pt; margin-bottom: 6pt;">5-) Tanık beyanları (İsim ve adresleri bilahare bildirilecektir),</p>
      <p style="text-align: justify; text-indent: 1.25cm; margin-top: 4pt; margin-bottom: 6pt;">6-) Yemin ve her türlü yasal delil.</p>
      <p style="text-align: right;"><br></p>
      <p style="text-align: right;"><strong>Vekil</strong><br>Av. [Ad Soyad]<br><em>(e-imzalıdır)</em></p>
    `;
  } else if (type === 'icra') {
    tpl = `
      <p style="text-align: center;"><strong>... İCRA DAİRESİ MÜDÜRLÜĞÜ'NE</strong></p>
      <p style="text-align: justify;"><strong>DOSYA NO :</strong> 2026/.... Esas</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>İTİRAZ EDEN BORÇLU :</strong> [Borçlu Ad Soyad / Ünvan - TCKN / VKN]</p>
      <p style="text-align: justify;"><strong>VEKİLİ :</strong> Av. [Ad Soyad]</p>
      <p style="text-align: justify;"><strong>ALACAKLI :</strong> [Alacaklı Ad Soyad / Ünvan]</p>
      <p style="text-align: justify;"><strong>KONU :</strong> Ödeme emrine, borca, fer'ilerine ve yetkiye itirazlarımızın sunulmasıdır.</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>İTİRAZLARIMIZ :</strong></p>
      <p style="text-align: justify; text-indent: 1.25cm; margin-top: 4pt; margin-bottom: 8pt;">Müdürlüğünüzce gönderilen ödeme emri müvekkile tebliğ edilmiştir. Müvekkilin alacaklı görünen tarafa herhangi bir borcu bulunmamaktadır. Borcun aslına, faizine, faiz oranına ve tüm fer'ilerine açıkça itiraz ediyoruz.</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>SONUÇ VE İSTEM :</strong> İtirazlarımızın kabulü ile takibin durdurulmasına karar verilmesini saygıyla vekâleten arz ve talep ederiz.</p>
      <p style="text-align: right;"><br></p>
      <p style="text-align: right;"><strong>Borçlu Vekili</strong><br>Av. [Ad Soyad]<br><em>(e-imzalıdır)</em></p>
    `;
  }

  if (tpl) {
    document.getElementById('editor-content').innerHTML = tpl;
    updateCounts();
    updateRulerFromActiveParagraph();
  }
}

// --- YENİ UYAP DİLEKÇE VE METİN ARAÇLARI ---

// Güncel Resmi Tarih Ekleme (GG.AA.YYYY)
function insertOfficialDate() {
  const d = new Date();
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  const dateStr = `${day}.${month}.${year}`;
  document.execCommand('insertText', false, dateStr);
  updateCounts();
}

// Türkçe Büyük/Küçük Harf Dönüştürücü (UYAP standartlarına tam uyumlu: İ/i, I/ı)
function convertTextCase(caseType) {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || sel.isCollapsed) {
    alert("Lütfen önce dönüştürmek istediğiniz metni seçiniz.");
    return;
  }

  const text = sel.toString();
  let converted = text;

  if (caseType === 'upper') {
    converted = text.toLocaleUpperCase('tr-TR');
  } else if (caseType === 'lower') {
    converted = text.toLocaleLowerCase('tr-TR');
  } else if (caseType === 'title') {
    converted = text.toLocaleLowerCase('tr-TR').replace(/(?:^|\s|\b)(\p{L})/gu, m => m.toLocaleUpperCase('tr-TR'));
  } else if (caseType === 'sentence') {
    converted = text.toLocaleLowerCase('tr-TR').replace(/(?:^|[.!?]\s+)(\p{L})/gu, m => m.toLocaleUpperCase('tr-TR'));
  }

  document.execCommand('insertText', false, converted);
  updateCounts();
}

// Biçimlendirmeyi Sıfırla (Pasted style temizleme)
function clearFormatting() {
  document.execCommand('removeFormat', false, null);
  document.execCommand('foreColor', false, '#000000');
  document.execCommand('hiliteColor', false, 'transparent');
  updateCounts();
}

// Sayfa Sonu (UYAP Page Break) Ekle
function insertPageBreak() {
  const pbHtml = '<div class="page-break" contenteditable="false"></div><p><br></p>';
  document.execCommand('insertHTML', false, pbHtml);
  updateCounts();
}

// Belge Bilgileri ve İstatistikleri Modal
function openDocStatsModal() {
  const editor = document.getElementById('editor-content');
  const text = editor ? (editor.innerText || '') : '';
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  const charsWithSpaces = text.length;
  const charsNoSpaces = text.replace(/\s/g, '').length;
  const paragraphs = editor ? editor.querySelectorAll('p, table, div.official-signature-seal').length : 0;
  const estimatedPages = Math.max(1, Math.ceil(words / 450));

  const statWords = document.getElementById('stat-words');
  const statCharsSpaces = document.getElementById('stat-chars-spaces');
  const statCharsNoSpaces = document.getElementById('stat-chars-nospaces');
  const statParagraphs = document.getElementById('stat-paragraphs');
  const statPages = document.getElementById('stat-pages');
  const statPageSize = document.getElementById('stat-pagesize');
  const statMargins = document.getElementById('stat-margins');

  if (statWords) statWords.textContent = words.toLocaleString('tr-TR');
  if (statCharsSpaces) statCharsSpaces.textContent = charsWithSpaces.toLocaleString('tr-TR');
  if (statCharsNoSpaces) statCharsNoSpaces.textContent = charsNoSpaces.toLocaleString('tr-TR');
  if (statParagraphs) statParagraphs.textContent = paragraphs.toLocaleString('tr-TR');
  if (statPages) statPages.textContent = estimatedPages + ' Sayfa';
  if (statPageSize) statPageSize.textContent = (currentMargins.orientation === 'landscape' ? 'A4 Yatay (297 × 210 mm)' : 'A4 Dikey (210 × 297 mm)');
  if (statMargins) statMargins.textContent = `Sol: ${currentMargins.left}cm, Sağ: ${currentMargins.right}cm, Üst: ${currentMargins.top}cm, Alt: ${currentMargins.bottom}cm`;

  openModal('modal-doc-stats');
}

// --- BUL VE DEĞİŞTİR (FIND & REPLACE) MOTORU ---
let findMatches = [];
let activeFindIndex = -1;

function openFindReplaceModal() {
  saveCurrentSelection();
  openModal('modal-find-replace');
  setTimeout(() => {
    const input = document.getElementById('find-query');
    if (input) {
      input.focus();
      input.select();
    }
  }, 150);
}

function closeFindReplaceModal() {
  clearFindHighlights();
  closeModal('modal-find-replace');
  restoreCurrentSelection();
}

function clearFindHighlights() {
  const editor = document.getElementById('editor-content');
  if (!editor) return;
  const highlights = editor.querySelectorAll('.find-highlight');
  highlights.forEach(h => {
    const parent = h.parentNode;
    if (parent) {
      parent.replaceChild(document.createTextNode(h.textContent), h);
      parent.normalize();
    }
  });
  findMatches = [];
  activeFindIndex = -1;
  const badge = document.getElementById('find-status-badge');
  if (badge) badge.textContent = '0 / 0 eşleşme';
}

function onFindQueryChanged() {
  clearFindHighlights();
  const query = (document.getElementById('find-query').value || '').trim();
  const matchCaseEl = document.getElementById('find-match-case');
  const matchCase = matchCaseEl ? matchCaseEl.checked : false;
  if (!query) return;

  const editor = document.getElementById('editor-content');
  highlightTextNodes(editor, query, matchCase);

  findMatches = Array.from(editor.querySelectorAll('.find-highlight'));
  const badge = document.getElementById('find-status-badge');
  if (badge) {
    badge.textContent = findMatches.length > 0 ? `1 / ${findMatches.length} eşleşme` : 'Eşleşme bulunamadı';
  }
  if (findMatches.length > 0) {
    activeFindIndex = 0;
    updateActiveFindHighlight();
  }
}

function highlightTextNodes(element, query, matchCase) {
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT, null, false);
  const textNodes = [];
  let n;
  while ((n = walker.nextNode())) {
    if (n.nodeValue.trim().length > 0) textNodes.push(n);
  }

  const flags = matchCase ? 'g' : 'gi';
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp(escaped, flags);

  for (let textNode of textNodes) {
    const val = textNode.nodeValue;
    if (regex.test(val)) {
      regex.lastIndex = 0;
      const frag = document.createDocumentFragment();
      let lastIdx = 0;
      let m;
      while ((m = regex.exec(val)) !== null) {
        if (m.index > lastIdx) {
          frag.appendChild(document.createTextNode(val.substring(lastIdx, m.index)));
        }
        const span = document.createElement('span');
        span.className = 'find-highlight';
        span.textContent = m[0];
        frag.appendChild(span);
        lastIdx = regex.lastIndex;
      }
      if (lastIdx < val.length) {
        frag.appendChild(document.createTextNode(val.substring(lastIdx)));
      }
      if (textNode.parentNode) {
        textNode.parentNode.replaceChild(frag, textNode);
      }
    }
  }
}

function updateActiveFindHighlight() {
  findMatches.forEach((m, idx) => {
    if (idx === activeFindIndex) {
      m.classList.add('active');
      m.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else {
      m.classList.remove('active');
    }
  });
  const badge = document.getElementById('find-status-badge');
  if (badge && findMatches.length > 0) {
    badge.textContent = `${activeFindIndex + 1} / ${findMatches.length} eşleşme`;
  }
}

function findNav(dir) {
  if (findMatches.length === 0) return;
  activeFindIndex = (activeFindIndex + dir + findMatches.length) % findMatches.length;
  updateActiveFindHighlight();
}

function doReplaceCurrent() {
  if (findMatches.length === 0 || activeFindIndex < 0) return;
  const replaceWith = document.getElementById('replace-query').value || '';
  const current = findMatches[activeFindIndex];
  if (current && current.parentNode) {
    const textNode = document.createTextNode(replaceWith);
    current.parentNode.replaceChild(textNode, current);
    onFindQueryChanged();
  }
}

function doReplaceAll() {
  if (findMatches.length === 0) return;
  const replaceWith = document.getElementById('replace-query').value || '';
  const count = findMatches.length;
  findMatches.forEach(m => {
    if (m && m.parentNode) {
      const textNode = document.createTextNode(replaceWith);
      m.parentNode.replaceChild(textNode, m);
    }
  });
  clearFindHighlights();
  alert(`Toplam ${count} adet eşleşme başarıyla değiştirildi.`);
}

// Buton Durumları
function updateActiveButtons() {
  setBtnState('btn-bold', document.queryCommandState('bold'));
  setBtnState('btn-italic', document.queryCommandState('italic'));
  setBtnState('btn-underline', document.queryCommandState('underline'));
  setBtnState('btn-strike', document.queryCommandState('strikeThrough'));
}

function setBtnState(id, isActive) {
  const btn = document.getElementById(id);
  if (btn) {
    if (isActive) btn.classList.add('active');
    else btn.classList.remove('active');
  }
}

// Kelime ve Karakter Sayımı
function updateCounts() {
  const text = document.getElementById('editor-content').innerText || '';
  const trimmed = text.trim();
  const wordCount = trimmed ? trimmed.split(/\s+/).length : 0;
  const charCount = text.length;

  if (window.AndroidBridge && window.AndroidBridge.onContentChanged) {
    window.AndroidBridge.onContentChanged(wordCount, charCount);
  }
}

// --- AI DİLEKÇE FORMATLAMA MOTORU (Canlı Gemini Flash + Çevrimdışı Standart Hukuk) ---

function openAiFormatModal() {
  saveCurrentSelection();
  const modal = document.getElementById('modal-ai-format');
  if (modal) {
    const key = localStorage.getItem('gemini_api_key') || '';
    const input = document.getElementById('gemini-api-key-input');
    if (input) input.value = key;
    const statusEl = document.getElementById('ai-format-status');
    if (statusEl) statusEl.innerHTML = '';
    modal.classList.add('open');
  }
}

function closeAiFormatModal() {
  closeModal('modal-ai-format');
  setTimeout(restoreCurrentSelection, 50);
}

function toggleApiKeyVisibility() {
  const input = document.getElementById('gemini-api-key-input');
  if (input) {
    input.type = input.type === 'password' ? 'text' : 'password';
  }
}

function saveGeminiApiKey() {
  const input = document.getElementById('gemini-api-key-input');
  if (input) {
    const key = (input.value || '').trim();
    localStorage.setItem('gemini_api_key', key);
    showEditorToast('Gemini API anahtarı kaydedildi!');
  }
}

function executeDeterministicFormat() {
  const editor = document.getElementById('editor-content');
  if (!editor) return;

  const paragraphs = Array.from(editor.querySelectorAll('p, blockquote, div'));
  if (paragraphs.length === 0) {
    showEditorToast('Biçimlendirilecek metin bulunamadı.');
    return;
  }

  // Mahkeme başlığı tespiti:
  const courtRegex = /(MAHKEMES[İI]'?NE|H[ÂA]K[İI]ML[İI][ĞG][İI]'?NE|BA[ŞS]SAVCILI[ĞG]I'?NA|DA[İI]RES[İI]'?NE|KOM[İI]SYONU'?NA|KURULU'?NA|BA[ŞS]KANLI[ĞG]I'?NA)$/i;
  const dispatchRegex = /^(GÖNDERİLMEK|SUNULMAK)\s+ÜZERE$/i;
  const metaRegex = /^(DOSYA\s+NO|ESAS\s+NO|KARAR\s+NO|SANIK|ŞÜPHELİ|MÜŞTEKİ|MAĞDUR|KATILAN|DAVACI|DAVALI|MÜDAFİ[İI]?|VEK[İI]L[İI]?|KONU|DAVA\s+KONUSU|SUÇ|TALEP\s+KONUSU|TEBLİĞ\s+TARİHİ)\b/i;
  const salutationRegex = /^(SAYIN\s+BAŞKAN|SAYIN\s+H[ÂA]K[İI]M|SAYIN\s+HEYET|H[ÂA]K[İI]ML[İI]ĞE|BAŞKANLIĞA|YÜKSEK\s+MAHKEME)/i;
  const sectionHeadingRegex = /^(AÇIKLAMALAR|HUKUK[İI]\s+NEDENLER|HUKUK[İI]\s+DEL[İI]LLER|DEL[İI]LLER|SONUÇ\s+VE\s+(TALEP|İSTEM)|NETİCE-İ\s+TALEP|TALEP|SAVUNMALARIMIZ|[I|V|X0-9]+\.\s+[A-ZÇĞİÖŞÜ\s]+)/i;
  const sigRegex = /^(SANIK|DAVACI|DAVALI|MÜŞTEKİ|ŞÜPHELİ|MÜDAFİ[İI]?|VEK[İI]L[İI]?|AV\.\s+[A-ZÇĞİÖŞÜ\s]+|\(E-İMZALIDIR\)|\(İMZA\))/i;

  const total = paragraphs.length;

  paragraphs.forEach((p, index) => {
    // Sayfa sonlarını ve boşlukları atla
    if (p.classList && (p.classList.contains('page-break') || p.classList.contains('auto-page-break'))) return;

    const rawText = (p.innerText || '').replace(/[\r\n\t\s]+/g, ' ').trim();
    if (!rawText) return;

    // 1. Dilekçe Sonu İmza Bloğu (Son 6 paragraf içindeki imza satırları)
    if (index >= total - 6 && sigRegex.test(rawText)) {
      p.style.textAlign = 'right';
      p.style.textIndent = '0';
      p.style.marginLeft = 'auto';
      p.style.marginRight = '0';
      p.style.marginTop = '1pt';
      p.style.marginBottom = '1pt';
      p.style.lineHeight = '1.2';
      return;
    }

    // 2. Mahkeme / Makam Başlığı
    if (courtRegex.test(rawText) || (index <= 4 && /(MAHKEMESİ|SAVCILIĞI|HÂKİMLİĞİ|DAİRESİ)/i.test(rawText))) {
      p.style.textAlign = 'center';
      p.style.textIndent = '0';
      p.style.marginTop = '4pt';
      p.style.marginBottom = '4pt';
      p.style.lineHeight = '1.25';
      p.innerHTML = '<strong>' + rawText.toLocaleUpperCase('tr-TR') + '</strong>';
      return;
    }

    // 3. Gönderilmek / Sunulmak Üzere
    if (dispatchRegex.test(rawText)) {
      p.style.textAlign = 'center';
      p.style.textIndent = '0';
      p.style.marginTop = '2pt';
      p.style.marginBottom = '2pt';
      p.innerHTML = '<em>' + rawText + '</em>';
      return;
    }

    // 4. Dosya / Taraf / Konu Satırları (5.0 cm sekme durağı ile UYAP hizalaması)
    if (metaRegex.test(rawText)) {
      p.style.textAlign = 'left';
      p.style.textIndent = '0';
      p.style.marginLeft = '0';
      p.style.marginRight = '0';
      p.style.marginTop = '2pt';
      p.style.marginBottom = '2pt';
      p.dataset.tabStops = '5';

      let parts = rawText.split(':');
      let label = parts[0].trim().toLocaleUpperCase('tr-TR');
      let val = parts.slice(1).join(':').trim();

      p.innerHTML = `<strong>${label}</strong><span class="udf-tab-space" contenteditable="false">&nbsp;</span>: ${val}`;
      return;
    }

    // 4b. Adres antettedir vb. taraf ek satırları
    if (index <= 10 && /(antettedir|adres|tckn|vkn|baro|uets)/i.test(rawText)) {
      p.style.textAlign = 'left';
      p.style.textIndent = '0';
      p.style.marginLeft = '5.0cm';
      p.style.marginTop = '1pt';
      p.style.marginBottom = '2pt';
      p.style.fontSize = '10pt';
      p.style.color = '#555555';
      return;
    }

    // 5. Hitap Satırı (Sayın Heyet, vb.)
    if (salutationRegex.test(rawText)) {
      p.style.textAlign = 'left';
      p.style.textIndent = '0';
      p.style.marginTop = '10pt';
      p.style.marginBottom = '6pt';
      p.innerHTML = '<strong>' + rawText + '</strong>';
      return;
    }

    // 6. Bölüm Başlıkları (AÇIKLAMALAR, vb.)
    if (sectionHeadingRegex.test(rawText)) {
      p.style.textAlign = 'left';
      p.style.textIndent = '0';
      p.style.marginTop = '10pt';
      p.style.marginBottom = '4pt';
      p.innerHTML = '<strong>' + rawText + '</strong>';
      return;
    }

    // 7. Standart Gövde Paragrafları
    p.style.textAlign = 'justify';
    p.style.textIndent = '1.0cm';
    p.style.marginTop = '4pt';
    p.style.marginBottom = '6pt';
    p.style.lineHeight = '1.25';
  });

  closeAiFormatModal();
  updatePagination();
  if (typeof markDirty === 'function') markDirty();
  showEditorToast('⚡ Dilekçe Türk yargı standartlarına göre formatlandı!');
}

async function executeGeminiFormat() {
  const statusEl = document.getElementById('ai-format-status');
  const keyInput = document.getElementById('gemini-api-key-input');
  const modelSelect = document.getElementById('gemini-model-select');
  const runBtn = document.getElementById('btn-run-gemini-ai');

  let apiKey = (keyInput ? keyInput.value : '').trim() || localStorage.getItem('gemini_api_key') || '';
  if (!apiKey) {
    if (statusEl) {
      statusEl.innerHTML = '<span style="color:#D32F2F; font-size:12px;">⚠️ Lütfen geçerli bir Gemini API anahtarı giriniz veya yukarıdaki çevrimdışı standardı kullanınız.</span>';
    }
    return;
  }
  localStorage.setItem('gemini_api_key', apiKey);

  const model = modelSelect ? modelSelect.value : 'gemini-3.5-flash-lite';
  const editor = document.getElementById('editor-content');
  if (!editor) return;

  const petitionText = editor.innerText.trim();
  if (!petitionText) {
    if (statusEl) statusEl.innerHTML = '<span style="color:#D32F2F;">Formatlanacak metin bulunamadı.</span>';
    return;
  }

  if (runBtn) {
    runBtn.disabled = true;
    runBtn.textContent = '⏳ Gemini ile analiz ediliyor...';
  }
  if (statusEl) {
    statusEl.innerHTML = '<span style="color:#6200EA; font-size:12px;">🤖 Dilekçeniz Gemini ' + model + ' ile analiz ediliyor, lütfen bekleyiniz...</span>';
  }

  const systemInstruction = `Sen Türkiye Cumhuriyeti Adalet Bakanlığı, Havelsan UYAP ve Türk mahkemeleri formatlarına tam hâkim kıdemli bir avukat ve hukuk katipliği yapay zekasısın.
Görevin: Verilen dilekçenin metin içeriğini, vakıalarını, taleplerini ve delillerini KESİNLİKLE değiştirmeden, UYAP kurallarına uygun HTML paragrafları olarak biçimlendirmek.

UYAP Biçimlendirme Kuralları:
1. Mahkeme/Savcılık Makam Başlığı: <p style="text-align: center;"><strong>...</strong></p>
2. Dosya No, Sanık, Müdafi, Davacı, Vekili, Konu satırları:
   <p style="text-align: left;" data-tab-stops="5"><strong>ETİKET</strong><span class="udf-tab-space" contenteditable="false">&nbsp;</span>: DEĞER</p>
3. Hitap ve Bölüm Başlıkları (AÇIKLAMALAR, HUKUKİ NEDENLER, DELİLLER, SONUÇ VE İSTEM vb.):
   <p style="text-align: left; margin-top: 10pt; margin-bottom: 4pt;"><strong>BAŞLIK</strong></p>
4. Gövde Paragrafları:
   <p style="text-align: justify; text-indent: 1.0cm; margin-top: 4pt; margin-bottom: 6pt; line-height: 1.25;">Metin...</p>
5. Dilekçe Sonu İmza Bloğu:
   <p style="text-align: right; text-indent: 0; margin: 1pt 0;"><strong>Vekil / Müdafi / Taraf</strong></p>
   <p style="text-align: right; text-indent: 0; margin: 1pt 0;">Av. ...</p>
   <p style="text-align: right; text-indent: 0; margin: 1pt 0;">(e-imzalıdır)</p>
6. SADECE saf HTML (p etiketleri) döndür. Asla markdown \`\`\`html kodu veya giriş/çıkış açıklaması yazma.`;

  try {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        contents: [
          {
            parts: [
              {
                text: `${systemInstruction}\n\nİşte biçimlendirilecek dilekçe:\n${petitionText}`
              }
            ]
          }
        ],
        generationConfig: {
          temperature: 0.1,
          topP: 0.95
        }
      })
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error((errData.error && errData.error.message) || `API Hatası: HTTP ${response.status}`);
    }

    const resJson = await response.json();
    const candidate = resJson.candidates && resJson.candidates[0];
    let outputText = candidate && candidate.content && candidate.content.parts && candidate.content.parts[0] && candidate.content.parts[0].text;

    if (!outputText) {
      throw new Error('Gemini API boş yanıt döndürdü.');
    }

    // Markdown temizliği
    outputText = outputText.replace(/^```html\s*/i, '').replace(/\s*```$/i, '').trim();

    if (outputText.includes('<p') || outputText.includes('<div')) {
      editor.innerHTML = outputText;
      closeAiFormatModal();
      updatePagination();
      if (typeof markDirty === 'function') markDirty();
      showEditorToast('✨ Dilekçe Gemini AI ile mükemmel şekilde formatlandı!');
    } else {
      throw new Error('Yapay zeka geçerli bir HTML yapısı oluşturamadı.');
    }
  } catch (err) {
    if (statusEl) {
      statusEl.innerHTML = `<span style="color:#D32F2F; font-size:11.5px;">❌ Hata: ${err.message}<br><a href="#" onclick="executeDeterministicFormat(); return false;" style="color:#1565C0; text-decoration:underline; font-weight:bold;">⚡ Yerel Standart Biçimlendirmeyi Kullan</a></span>`;
    }
  } finally {
    if (runBtn) {
      runBtn.disabled = false;
      runBtn.textContent = '✨ Gemini ile Canlı Formatla';
    }
  }
}

// Java Tarafından Çağrılan Metotlar:
function setDocumentData(header, footer, htmlContent) {
  const editor = document.getElementById('editor-content');
  const headerEl = document.getElementById('doc-header');
  const footerEl = document.getElementById('doc-footer');

  if (headerEl) headerEl.innerText = (header || '').trim();
  if (footerEl) footerEl.innerText = (footer || '').trim();
  if (editor) {
    editor.innerHTML = htmlContent || '<p><br></p>';
  }

  updateCounts();
  setTimeout(() => {
    applyAutoFitZoom();
    updateRulerFromActiveParagraph();
  }, 150);
  setTimeout(markDocumentPristine, 400);
  setTimeout(() => { if (window.CanHistory) CanHistory.reset(); }, 450);
}

// --- Değişiklik takibi (imzalı belgelerde imzaları korumak için) ---
window.__origDocSnapshot = null;
function snapshotDocument() {
  try {
    const d = getStructuredDocument();
    return JSON.stringify({ h: d.header, f: d.footer, p: d.paragraphs });
  } catch (e) {
    return null;
  }
}
function markDocumentPristine() {
  window.__origDocSnapshot = snapshotDocument();
  try { localStorage.removeItem(AUTOSAVE_STORAGE_KEY); } catch (x) {}
}
function isDocumentModified() {
  if (window.__origDocSnapshot === null) return true;
  return snapshotDocument() !== window.__origDocSnapshot;
}

// --- 30 Saniyede Bir Otomatik Taslak Kaydetme & Kurtarma ---
const AUTOSAVE_STORAGE_KEY = 'caneditor_autosave_draft';

function saveAutoDraft() {
  try {
    if (!isDocumentModified()) return;
    const ed = document.getElementById('editor-content');
    if (!ed) return;
    const rawText = (ed.innerText || '').trim();
    if (rawText.length < 15) return; // Boş veya anlamsız kısa belgeleri taslak yapma

    const headerEl = document.getElementById('doc-header');
    const footerEl = document.getElementById('doc-footer');
    const payload = {
      timestamp: Date.now(),
      dateStr: new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }),
      html: ed.innerHTML,
      header: headerEl ? (headerEl.innerText || '').trim() : '',
      footer: footerEl ? (footerEl.innerText || '').trim() : '',
      margins: currentMargins
    };
    localStorage.setItem(AUTOSAVE_STORAGE_KEY, JSON.stringify(payload));
  } catch (e) {
    console.warn('Otomatik taslak kaydetme hatası:', e);
  }
}

setInterval(saveAutoDraft, 30000);

function checkAutoDraftRecovery() {
  try {
    const raw = localStorage.getItem(AUTOSAVE_STORAGE_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    if (!data || !data.html) return;
    const ed = document.getElementById('editor-content');
    const curLen = (ed ? ed.innerText : '').trim().length;
    if (curLen > 30) return; // Halihazırda büyük bir dosya açıldıysa üzerine yazma

    showAutoDraftModal(data);
  } catch (e) {
    console.warn('Taslak kontrol hatası:', e);
  }
}

function showAutoDraftModal(draft) {
  const existing = document.getElementById('modal-autodraft-recovery');
  if (existing) existing.remove();

  const modal = document.createElement('div');
  modal.id = 'modal-autodraft-recovery';
  modal.style.cssText = `
    position: fixed; inset: 0; background: rgba(0,0,0,0.55); z-index: 999999;
    display: flex; align-items: center; justify-content: center; backdrop-filter: blur(3px);
  `;
  modal.innerHTML = `
    <div style="background:#fff; border-radius:12px; width:90%; max-width:440px; padding:22px; box-shadow:0 12px 36px rgba(0,0,0,0.3); font-family:system-ui,-apple-system,sans-serif; text-align:left;">
      <div style="display:flex; align-items:center; gap:10px; margin-bottom:12px;">
        <span style="font-size:24px;">💾</span>
        <h3 style="margin:0; font-size:17px; color:#1a237e; font-weight:700;">Kurtarılabilir Taslak Bulundu</h3>
      </div>
      <p style="font-size:13px; color:#444; line-height:1.5; margin-bottom:16px;">
        Önceki oturumunuzda kaydedilmemiş bir çalışma (Saat: <strong>\${draft.dateStr || ''}</strong>) tespit edildi. Belgenizi kaldığınız yerden devam ettirmek için kurtarmak ister misiniz?
      </p>
      <div style="display:flex; justify-content:flex-end; gap:8px;">
        <button id="btn-draft-discard" style="padding:9px 15px; border-radius:6px; border:1px solid #ccc; background:#f5f5f5; color:#555; font-size:13px; cursor:pointer; font-weight:600;">Yoksay</button>
        <button id="btn-draft-restore" style="padding:9px 18px; border-radius:6px; border:none; background:#1a237e; color:#fff; font-size:13px; cursor:pointer; font-weight:600;">Kurtar ve Aç</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  document.getElementById('btn-draft-discard').onclick = () => {
    localStorage.removeItem(AUTOSAVE_STORAGE_KEY);
    modal.remove();
  };

  document.getElementById('btn-draft-restore').onclick = () => {
    const ed = document.getElementById('editor-content');
    if (ed) {
      ed.innerHTML = draft.html;
      const headerEl = document.getElementById('doc-header');
      const footerEl = document.getElementById('doc-footer');
      if (headerEl && draft.header) { headerEl.innerText = draft.header; headerEl.style.display = 'block'; }
      if (footerEl && draft.footer) { footerEl.innerText = draft.footer; }
      if (draft.margins) {
        applyPageSetup(draft.margins.left, draft.margins.right, draft.margins.top, draft.margins.bottom, draft.margins.orientation);
      }
      realignAllTabs();
      updatePagination();
      updateCounts();
      if (window.CanHistory) CanHistory.reset();
      showEditorToast('✓ Taslak başarıyla kurtarıldı');
    }
    modal.remove();
  };
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => setTimeout(checkAutoDraftRecovery, 1200));
} else {
  setTimeout(checkAutoDraftRecovery, 1200);
}

function setHtmlContent(content) {
  if (!content) return;
  const editor = document.getElementById('editor-content');
  const headerEl = document.getElementById('doc-header');
  const footerEl = document.getElementById('doc-footer');

  // JSON Yapılandırılmış Belge veya Düz HTML Kontrolü
  const trimmed = content.trim();
  if (trimmed.startsWith('{')) {
    try {
      const data = JSON.parse(trimmed);
      if (data && typeof data === 'object') {
        if (data.headerHtml) {
          headerEl.innerHTML = data.headerHtml;
          headerEl.style.display = 'block';
        } else if (data.header !== undefined && headerEl) {
          headerEl.innerText = data.header;
          headerEl.style.display = (data.header && data.header.trim()) ? 'block' : 'none';
        }
        if (data.footerHtml) {
          currentDocFooterTemplate = data.footerHtml;
        } else if (data.footer !== undefined && footerEl) {
          footerEl.innerText = data.footer;
          currentDocFooterTemplate = '';
        }
        if (data.leftMarginCm !== undefined) {
          applyPageSetup(data.leftMarginCm, data.rightMarginCm, data.topMarginCm, data.bottomMarginCm, data.paperOrientation === '2' ? 'landscape' : 'portrait', data.headerMarginCm, data.footerMarginCm);
        }
        if (data.html) {
          editor.innerHTML = data.html;
          updateCounts();
          setTimeout(() => {
            applyAutoFitZoom();
            updateRulerFromActiveParagraph();
            updatePagination();
          }, 200);
          setTimeout(markDocumentPristine, 400);
  setTimeout(() => { if (window.CanHistory) CanHistory.reset(); }, 450);
          return;
        }
      }
    } catch (e) {
      // JSON değilse düz metin veya html olarak yüklemeye devam et
    }
  }

  editor.innerHTML = content;
  updateCounts();
  setTimeout(() => {
    updateRulerFromActiveParagraph();
    updatePagination();
  }, 200);
  setTimeout(() => { if (window.CanHistory) CanHistory.reset(); }, 450);
}

function getHtmlContent() {
  return document.getElementById('editor-content').innerHTML;
}

function getPlainText() {
  const parts = [];
  
  // 1. Üstbilgi
  const headerEl = document.getElementById('doc-header');
  if (headerEl) {
    const hText = (headerEl.innerText || '').trim();
    if (hText) parts.push(hText + '\n');
  }

  // 2. Ana İçerik
  const editor = document.getElementById('editor-content');
  if (editor) {
    const blocks = Array.from(editor.children);
    for (let b of blocks) {
      if (b.classList && (b.classList.contains('auto-page-break') || b.classList.contains('page-break') || b.classList.contains('page-break-desk-gap') || b.classList.contains('page-break-header-area') || b.classList.contains('page-break-footer-area'))) {
        continue;
      }
      if (b.tagName && b.tagName.toLowerCase() === 'table') {
        const rows = b.querySelectorAll('tr');
        for (let row of rows) {
          const cells = Array.from(row.querySelectorAll('th, td')).map(c => (c.innerText || '').trim());
          if (cells.length > 0) parts.push(cells.join('\t'));
        }
        continue;
      }

      // Paragraf veya satır
      const txt = (b.innerText || '').replace(/[\r\n]+/g, ' ').trim();
      if (txt) {
        parts.push(txt);
      }
    }
  }

  // 3. Altbilgi
  const footerEl = document.getElementById('doc-footer');
  if (footerEl) {
    const fText = (footerEl.innerText || '').trim();
    if (fText && !fText.toLowerCase().includes('sayfa')) {
      parts.push('\n' + fText);
    }
  }

  return parts.join('\n\n');
}

// Belgeyi Java UDF & DOCX Üreticileri için Üstbilgi, Altbilgi ve Paragraflar Olarak Çıkar
function getStructuredDocument() {
  const container = document.getElementById('editor-content');
  const paragraphs = [];
  
  const nodes = container.children;
  if (!nodes || nodes.length === 0) {
    paragraphs.push({
      text: container.innerText || '',
      align: 3,
      spaceAbove: 1.0,
      spaceBelow: 1.0,
      lineSpacing: 0.0,
      firstLineIndent: 0.0,
      leftIndent: 0.0,
      rightIndent: 0.0,
      runs: [{ text: container.innerText || '', bold: false, italic: false, underline: false }]
    });
  } else {
    for (let node of nodes) {
      if (node.classList && (node.classList.contains('auto-page-break') || node.classList.contains('page-break'))) {
        continue;
      }
      if (node.tagName && node.tagName.toLowerCase() === 'table') {
        const rows = node.querySelectorAll('tr');
        for (let row of rows) {
          const cells = row.querySelectorAll('th, td');
          let rowText = '';
          for (let cell of cells) {
            rowText += (cell.innerText || '').trim() + '\t';
          }
          paragraphs.push({
            text: rowText.trim(),
            align: 0,
            spaceAbove: 1.0,
            spaceBelow: 1.0,
            lineSpacing: 0.0,
            firstLineIndent: 0.0,
            leftIndent: 0.0,
            rightIndent: 0.0,
            runs: [{ text: rowText.trim(), bold: row.querySelector('th') !== null, italic: false, underline: false }]
          });
        }
        continue;
      }

      if (node.classList && (node.classList.contains('official-signature-seal') || node.classList.contains('seal-wrapper-block') || node.querySelector('.official-signature-seal'))) {
        const sealText = (node.innerText || '').trim();
        if (sealText) {
          paragraphs.push({
            text: sealText,
            align: 2, // Sağa yaslı resmi imza bloğu
            spaceAbove: 8.0,
            spaceBelow: 4.0,
            lineSpacing: 1.15,
            firstLineIndent: 0.0,
            leftIndent: 0.0,
            rightIndent: 0.0,
            runs: [{ text: sealText, bold: true, italic: false, underline: false }]
          });
        }
        continue;
      }

      let align = 3;
      const textAlign = node.style ? node.style.textAlign : '';
      if (textAlign === 'center') align = 1;
      else if (textAlign === 'right') align = 2;
      else if (textAlign === 'left') align = 0;
      else align = 3;

      const pText = node.innerText || '';
      const runs = [];
      parseInlineRuns(node, runs, false, false, false);

      const spaceAbove = node.style && node.style.marginTop ? (parseFloat(node.style.marginTop) || 1.0) : 1.0;
      const spaceBelow = node.style && node.style.marginBottom ? (parseFloat(node.style.marginBottom) || 1.0) : 1.0;
      const lineSpacing = node.style && node.style.lineHeight ? (parseFloat(node.style.lineHeight) || 0.0) : 0.0;
      const firstLineIndent = parseToCm(node.style ? node.style.textIndent : '');
      const leftIndent = parseToCm(node.style ? node.style.marginLeft : '');
      const rightIndent = parseToCm(node.style ? node.style.marginRight : '');

      paragraphs.push({
        text: pText,
        align: align,
        spaceAbove: spaceAbove,
        spaceBelow: spaceBelow,
        lineSpacing: lineSpacing,
        firstLineIndent: firstLineIndent,
        leftIndent: leftIndent,
        rightIndent: rightIndent,
        tabStops: (node.dataset && node.dataset.tabStops) ? node.dataset.tabStops : '',
        runs: runs.length > 0 ? runs : [{ text: pText, bold: false, italic: false, underline: false }]
      });
    }
  }

  const headerEl = document.getElementById('doc-header');
  const footerEl = document.getElementById('doc-footer');
  const hasSeal = container.querySelectorAll('.official-signature-seal').length > 0;

  const docPayload = {
    header: headerEl ? (headerEl.innerText || '').trim() : '',
    footer: footerEl ? (footerEl.innerText || '').trim() : '',
    isSigned: hasSeal,
    margins: currentMargins,
    leftMarginCm: currentMargins.left,
    rightMarginCm: currentMargins.right,
    topMarginCm: currentMargins.top,
    bottomMarginCm: currentMargins.bottom,
    paperOrientation: currentMargins.orientation === 'landscape' ? '2' : '1',
    paragraphs: paragraphs
  };

  return docPayload;
}

function parseInlineRuns(element, runs, bold, italic, underline, subscript, superscript, strikethrough) {
  for (let child of element.childNodes) {
    if (child.nodeType === Node.TEXT_NODE) {
      if (child.textContent) {
        runs.push({
          text: child.textContent,
          bold: !!bold,
          italic: !!italic,
          underline: !!underline,
          subscript: !!subscript,
          superscript: !!superscript,
          strikethrough: !!strikethrough
        });
      }
    } else if (child.nodeType === Node.ELEMENT_NODE) {
      if (child.classList && (child.classList.contains('auto-page-break') || child.classList.contains('page-break'))) {
        continue;
      }
      if (child.classList && child.classList.contains('udf-tab-label')) {
        const isBold = child.querySelector('strong, b') !== null || !!bold;
        const txt = (child.textContent || '').trim();
        runs.push({
          text: txt + '\t',
          bold: isBold,
          italic: !!italic,
          underline: !!underline,
          subscript: !!subscript,
          superscript: !!superscript,
          strikethrough: !!strikethrough
        });
        continue;
      }
      if (child.classList && child.classList.contains('udf-colon')) {
        runs.push({
          text: ':',
          bold: !!bold,
          italic: !!italic,
          underline: !!underline,
          subscript: !!subscript,
          superscript: !!superscript,
          strikethrough: !!strikethrough
        });
        continue;
      }
      if (child.classList && child.classList.contains('udf-tab-space')) {
        runs.push({
          text: '\t',
          bold: !!bold,
          italic: !!italic,
          underline: !!underline,
          subscript: !!subscript,
          superscript: !!superscript,
          strikethrough: !!strikethrough
        });
        continue;
      }
      const tag = child.tagName.toLowerCase();
      const isB = bold || tag === 'b' || tag === 'strong' || (child.style && child.style.fontWeight === 'bold');
      const isI = italic || tag === 'i' || tag === 'em' || (child.style && child.style.fontStyle === 'italic');
      const isU = underline || tag === 'u' || (child.style && child.style.textDecoration && child.style.textDecoration.includes('underline'));
      const isSub = subscript || tag === 'sub';
      const isSup = superscript || tag === 'sup';
      const isStrike = strikethrough || tag === 's' || tag === 'strike' || (child.style && child.style.textDecoration && child.style.textDecoration.includes('line-through'));
      parseInlineRuns(child, runs, isB, isI, isU, isSub, isSup, isStrike);
    }
  }
}

// ==========================================
// ELEKTRONİK İMZA DOĞRULAMA (Havelsan UYAP Uyumlu)
// ==========================================

let currentDocSignature = null;

// Java tarafından belge açıldığında veya imza doğrulandığında çağrılır
window.onDocumentSignatureChecked = function(data) {
  if (!data) return;
  if (typeof data === 'string') {
    try {
      data = JSON.parse(data);
    } catch(e) {
      return;
    }
  }

  currentDocSignature = data;
  updateSignatureBanner(data);

  // Eğer detay modalı açıksa, içeriğini de canlı güncelle
  const modal = document.getElementById('modal-signature-details');
  if (modal && modal.classList.contains('active')) {
    populateSignatureDetailsModal(data);
  }
};

function updateSignatureBanner(data) {
  const banner = document.getElementById('doc-signature-banner');
  const iconEl = document.getElementById('sig-banner-icon');
  const textEl = document.getElementById('sig-banner-text');
  const docSeal = document.getElementById('official-doc-seal');
  if (docSeal) {
    docSeal.style.display = (data && data.hasSignature && data.isValid) ? 'flex' : 'none';
  }
  if (!banner || !iconEl || !textEl) return;

  if (!data.hasSignature) {
    banner.style.display = 'none';
    banner.className = 'signature-status-banner unsigned';
    return;
  }

  banner.style.display = 'flex';
  if (data.isValid) {
    banner.className = 'signature-status-banner valid';
    iconEl.textContent = '🟢';
    if (data.signers && data.signers.length > 1) {
      const names = data.signers.map(s => s.signerName).join(', ');
      textEl.innerHTML = `<strong>${data.signers.length} Geçerli E-İmza:</strong> ${names}`;
    } else {
      const signer = data.signerName || 'Elektronik İmza Sahibi';
      const iss = data.issuer ? ` (${data.issuer})` : '';
      textEl.innerHTML = `<strong>Geçerli E-İmza:</strong> ${signer}${iss}`;
    }
  } else {
    banner.className = 'signature-status-banner invalid';
    iconEl.textContent = '🔴';
    textEl.innerHTML = `<strong>DİKKAT:</strong> Doküman üzerinde geçersiz imza tespit edildi!`;
  }
}

// Araç çubuğundaki "🔍 İmza Kontrolü" butonuna basıldığında
function checkDocumentSignature() {
  openSignatureDetailsModal();
  if (window.AndroidBridge && window.AndroidBridge.checkDocumentSignature) {
    window.AndroidBridge.checkDocumentSignature();
  }
}

function openSignatureDetailsModal() {
  openModal('modal-signature-details');
  if (currentDocSignature) {
    populateSignatureDetailsModal(currentDocSignature);
  } else {
    if (window.AndroidBridge && window.AndroidBridge.checkDocumentSignature) {
      window.AndroidBridge.checkDocumentSignature();
    }
  }
}
window.openSignatureModal = openSignatureDetailsModal;

function populateSignatureDetailsModal(data) {
  const mainBox = document.getElementById('sig-main-status-box');
  const largeIcon = document.getElementById('sig-status-large-icon');
  const heading = document.getElementById('sig-status-heading');
  const subtext = document.getElementById('sig-status-subtext');

  const valMath = document.getElementById('val-chk-math');
  const valCert = document.getElementById('val-chk-cert');
  const valVal = document.getElementById('val-chk-validity');
  const valDigest = document.getElementById('val-chk-digest');
  const iconDigest = document.getElementById('icon-chk-digest');

  const detSigner = document.getElementById('det-signer-name');
  const detIssuer = document.getElementById('det-issuer-name');
  const detSerial = document.getElementById('det-serial-no');
  const detValidity = document.getElementById('det-validity');
  const detAlgo = document.getElementById('det-algorithm');
  const detDigest = document.getElementById('det-digest-hex');
  const certBox = document.getElementById('sig-cert-info-box');

  if (!data || !data.hasSignature) {
    if (mainBox) {
      mainBox.style.backgroundColor = '#F5F5F5';
      mainBox.style.borderColor = '#E0E0E0';
    }
    if (largeIcon) largeIcon.textContent = '⚪';
    if (heading) {
      heading.textContent = 'Dokümanda Elektronik İmza Bulunmuyor';
      heading.style.color = '#616161';
    }
    if (subtext) {
      subtext.textContent = 'Belge henüz 5070 sayılı kanun kapsamında imzalanmamıştır.';
      subtext.style.color = '#757575';
    }

    if (valMath) { valMath.textContent = 'İmza yok'; valMath.style.color = '#757575'; }
    if (valCert) { valCert.textContent = 'Sertifika yok'; valCert.style.color = '#757575'; }
    if (valVal) { valVal.textContent = 'Geçerlilik bilgisi yok'; valVal.style.color = '#757575'; }
    if (valDigest) { valDigest.textContent = 'Hesaplama yapılmadı'; valDigest.style.color = '#757575'; }
    if (iconDigest) { iconDigest.textContent = '(•)'; iconDigest.style.color = '#757575'; }

    if (detSigner) detSigner.textContent = '-';
    if (detIssuer) detIssuer.textContent = '-';
    if (detSerial) detSerial.textContent = '-';
    if (detValidity) detValidity.textContent = '-';
    if (detAlgo) detAlgo.textContent = '-';
    if (detDigest) detDigest.textContent = (data && data.rawDigest) ? data.rawDigest : '-';
    return;
  }

  if (data.isValid) {
    if (mainBox) {
      mainBox.style.backgroundColor = '#E8F5E9';
      mainBox.style.borderColor = '#A5D6A7';
    }
    if (largeIcon) largeIcon.textContent = '🟢';
    if (heading) {
      if (data.signers && data.signers.length > 1) {
        heading.textContent = `Dokümanda ${data.signers.length} Geçerli Elektronik İmza Bulundu`;
      } else {
        heading.textContent = 'Doküman Üzerinde Geçerli Elektronik İmza Bulundu';
      }
      heading.style.color = '#1B5E20';
    }
    if (subtext) {
      subtext.textContent = 'TÜBİTAK UEKAE MA3 & 5070 Sayılı Kanun Standartlarına Tam Uyumlu';
      subtext.style.color = '#2E7D32';
    }

    if (valMath) { valMath.textContent = 'Başarılı (Matematiksel Şifre Doğrulandı)'; valMath.style.color = '#2E7D32'; }
    if (valCert) { valCert.textContent = 'Başarılı (Nitelikli Elektronik Sertifika - NES)'; valCert.style.color = '#2E7D32'; }
    if (valVal) { valVal.textContent = `Başarılı (${data.validUntil ? 'Son: ' + data.validUntil : 'Geçerli'})`; valVal.style.color = '#2E7D32'; }
    if (iconDigest) { iconDigest.textContent = '(+)'; iconDigest.style.color = '#2E7D32'; }
    if (valDigest) {
      valDigest.textContent = 'İçerik özeti özelliğindeki değer hesaplanan değerle aynı. Kontrolcü sonucu başarılı.';
      valDigest.style.color = '#2E7D32';
    }
  } else {
    if (mainBox) {
      mainBox.style.backgroundColor = '#FFEBEE';
      mainBox.style.borderColor = '#FFCDD2';
    }
    if (largeIcon) largeIcon.textContent = '🔴';
    if (heading) {
      heading.textContent = 'Doküman Üzerinde Geçersiz İmza Tespit Edildi!';
      heading.style.color = '#B71C1C';
    }
    if (subtext) {
      subtext.textContent = 'İçerik özeti uyuşmuyor! Belge imzalandıktan sonra değiştirilmiş veya geçersiz imzalanmış.';
      subtext.style.color = '#C62828';
    }

    if (valMath) { valMath.textContent = 'Başarılı'; valMath.style.color = '#2E7D32'; }
    if (valCert) { valCert.textContent = 'Başarılı'; valCert.style.color = '#2E7D32'; }
    if (valVal) { valVal.textContent = 'Başarılı'; valVal.style.color = '#2E7D32'; }
    if (iconDigest) { iconDigest.textContent = '(-)'; iconDigest.style.color = '#C62828'; }
    if (valDigest) {
      valDigest.textContent = 'İçerik özeti özelliğindeki değer hesaplanan değerle aynı değil. Kontrolcü sonucu başarısız.';
      valDigest.style.color = '#C62828';
    }
  }

  if (data.signers && data.signers.length > 1 && certBox) {
    let cardsHtml = `
      <div style="font-size: 11px; font-weight: bold; color: #475569; margin-bottom: 8px; text-transform: uppercase;">
        Dokümandaki İmzalar (Toplam ${data.signers.length} E-İmza):
      </div>
    `;
    data.signers.forEach((s, idx) => {
      cardsHtml += `
        <div style="border: 1px solid #90CAF9; background-color: #F8FAFC; border-radius: 6px; padding: 10px 12px; margin-bottom: 8px;">
          <div style="font-weight: bold; color: #0D47A1; margin-bottom: 4px; font-size: 12px;">✍️ İmza #${idx + 1}: ${s.signerName}</div>
          <div><strong>Sertifika Sağlayıcı (NES):</strong> ${s.issuer || '-'}</div>
          <div><strong>Seri No:</strong> <code style="font-size: 11px; word-break: break-all;">${s.serialNumber || '-'}</code></div>
          <div><strong>Geçerlilik Aralığı:</strong> ${(s.validFrom ? s.validFrom + ' - ' : '') + (s.validUntil || '-')}</div>
          <div><strong>Algoritma:</strong> ${s.signAlgorithm || 'SHA256withRSA'} / CAdES-BES</div>
        </div>
      `;
    });
    cardsHtml += `
      <div style="margin-top: 6px;"><strong>Belge Özet Değeri (SHA-256):</strong> <code style="font-size: 10.5px; word-break: break-all;">${data.rawDigest || '-'}</code></div>
    `;
    certBox.innerHTML = cardsHtml;
  } else {
    if (detSigner) detSigner.textContent = data.signerName || 'Bilinmeyen İmzacı';
    if (detIssuer) detIssuer.textContent = data.issuer || 'Nitelikli Elektronik Sertifika Sağlayıcı';
    if (detSerial) detSerial.textContent = data.serialNumber || '-';
    if (detValidity) detValidity.textContent = (data.validFrom ? data.validFrom + ' - ' : '') + (data.validUntil || '-');
    if (detAlgo) detAlgo.textContent = (data.signAlgorithm || 'SHA256withRSA') + ' / CAdES-BES (5070 S.K.)';
    if (detDigest) detDigest.textContent = data.rawDigest || '-';
  }
}

function recheckSignatureInModal() {
  const heading = document.getElementById('sig-status-heading');
  if (heading) heading.textContent = 'İmza yeniden doğrulanıyor...';
  if (window.AndroidBridge && window.AndroidBridge.checkDocumentSignature) {
    window.AndroidBridge.checkDocumentSignature();
  }
}

// --- BİÇİM BOYACISI (Format Painter) MOTORU ---
function toggleFormatPainter() {
  if (isFormatPainterActive) {
    deactivateFormatPainter();
    showEditorToast('Biçim boyacısı kapatıldı');
    return;
  }
  activateFormatPainter(false);
}

function activateFormatPainter(persistent = false) {
  const sel = window.getSelection();
  const editor = document.getElementById('editor-content');
  if (!editor) return;

  // Biçim alınacak kaynak öğeyi belirle
  let sourceEl = null;
  if (sel && sel.rangeCount > 0) {
    const range = sel.getRangeAt(0);
    if (!sel.isCollapsed) {
      sourceEl = range.commonAncestorContainer;
      if (sourceEl.nodeType === Node.TEXT_NODE) sourceEl = sourceEl.parentElement;
    } else {
      sourceEl = sel.anchorNode;
      if (sourceEl && sourceEl.nodeType === Node.TEXT_NODE) sourceEl = sourceEl.parentElement;
    }
  }
  if (!sourceEl || !editor.contains(sourceEl)) {
    sourceEl = lastActiveParagraph || editor.firstElementChild;
  }
  if (!sourceEl) {
    showEditorToast('Önce biçimi kopyalanacak metne dokunun');
    return;
  }

  // Hesaplanan stilleri al
  const cs = window.getComputedStyle(sourceEl);
  let pEl = sourceEl;
  while (pEl && pEl !== editor && pEl !== document.body) {
    if (pEl.tagName && (pEl.tagName === 'P' || pEl.tagName === 'LI' || pEl.tagName === 'DIV' || pEl.tagName === 'BLOCKQUOTE')) break;
    pEl = pEl.parentElement;
  }
  const pCs = (pEl && pEl !== editor) ? window.getComputedStyle(pEl) : cs;

  copiedFormat = {
    fontFamily: cs.fontFamily,
    fontSize: cs.fontSize,
    fontWeight: cs.fontWeight,
    fontStyle: cs.fontStyle,
    textDecoration: cs.textDecorationLine || cs.textDecoration,
    color: cs.color,
    backgroundColor: cs.backgroundColor !== 'rgba(0, 0, 0, 0)' && cs.backgroundColor !== 'transparent' ? cs.backgroundColor : '',
    textAlign: pCs.textAlign,
    lineHeight: pCs.lineHeight,
    marginTop: pCs.marginTop,
    marginBottom: pCs.marginBottom,
    textIndent: pCs.textIndent
  };

  isFormatPainterActive = true;
  isFormatPainterPersistent = persistent;
  document.body.classList.add('format-painter-active');
  const btn = document.getElementById('btn-format-painter');
  if (btn) btn.classList.add('active');

  showEditorToast('🖌️ Biçim kopyalandı! Hedef metni seçin veya tıklayın');
}

function deactivateFormatPainter() {
  isFormatPainterActive = false;
  isFormatPainterPersistent = false;
  document.body.classList.remove('format-painter-active');
  const btn = document.getElementById('btn-format-painter');
  if (btn) btn.classList.remove('active');
}

function applyCopiedFormatToTarget() {
  if (!isFormatPainterActive || !copiedFormat) return;

  const sel = window.getSelection();
  const editor = document.getElementById('editor-content');
  if (!sel || sel.rangeCount === 0 || !editor) return;

  const range = sel.getRangeAt(0);
  if (!editor.contains(range.commonAncestorContainer)) return;

  if (!sel.isCollapsed) {
    // 1. Seçili metin aralığına uygula
    if (copiedFormat.fontFamily) document.execCommand('fontName', false, copiedFormat.fontFamily);
    if (copiedFormat.color) document.execCommand('foreColor', false, copiedFormat.color);
    if (copiedFormat.backgroundColor) document.execCommand('hiliteColor', false, copiedFormat.backgroundColor);
    if (copiedFormat.fontWeight === 'bold' || parseInt(copiedFormat.fontWeight) >= 700) {
      if (!document.queryCommandState('bold')) document.execCommand('bold');
    }
    if (copiedFormat.fontStyle === 'italic') {
      if (!document.queryCommandState('italic')) document.execCommand('italic');
    }
    if (copiedFormat.textDecoration && copiedFormat.textDecoration.includes('underline')) {
      if (!document.queryCommandState('underline')) document.execCommand('underline');
    }

    // Paragraf hizalama & boşluk uygula
    const targetP = getActiveParagraph();
    if (targetP) {
      if (copiedFormat.textAlign) targetP.style.textAlign = copiedFormat.textAlign;
      if (copiedFormat.lineHeight) targetP.style.lineHeight = copiedFormat.lineHeight;
      if (copiedFormat.marginTop) targetP.style.marginTop = copiedFormat.marginTop;
      if (copiedFormat.marginBottom) targetP.style.marginBottom = copiedFormat.marginBottom;
      if (copiedFormat.textIndent) targetP.style.textIndent = copiedFormat.textIndent;
    }
  } else {
    // 2. Tıklanan paragrafa/kelimeye uygula
    const targetP = getActiveParagraph();
    if (targetP) {
      if (copiedFormat.textAlign) targetP.style.textAlign = copiedFormat.textAlign;
      if (copiedFormat.lineHeight) targetP.style.lineHeight = copiedFormat.lineHeight;
      if (copiedFormat.marginTop) targetP.style.marginTop = copiedFormat.marginTop;
      if (copiedFormat.marginBottom) targetP.style.marginBottom = copiedFormat.marginBottom;
      if (copiedFormat.textIndent) targetP.style.textIndent = copiedFormat.textIndent;
      if (copiedFormat.fontFamily) targetP.style.fontFamily = copiedFormat.fontFamily;
      if (copiedFormat.fontSize) targetP.style.fontSize = copiedFormat.fontSize;
      if (copiedFormat.color) targetP.style.color = copiedFormat.color;
    }
  }

  showEditorToast('✓ Biçim uygulandı');
  updateActiveButtons();
  updateRulerFromActiveParagraph();
  debouncedPagination();

  if (!isFormatPainterPersistent) {
    deactivateFormatPainter();
  }
}

// --- METİN SEÇİMİ YÜZEN EYLEM ÇUBUĞU (Floating Context Bubble) ---
function updateFloatingContextMenu() {
  const menu = document.getElementById('floating-context-menu');
  if (!menu) return;

  if (isFormatPainterActive) {
    menu.style.display = 'none';
    return;
  }

  const sel = window.getSelection();
  const editor = document.getElementById('editor-content');
  if (!sel || sel.isCollapsed || sel.rangeCount === 0 || !editor) {
    menu.style.display = 'none';
    return;
  }

  const range = sel.getRangeAt(0);
  const text = sel.toString().trim();
  if (text.length === 0 || !editor.contains(range.commonAncestorContainer)) {
    menu.style.display = 'none';
    return;
  }

  const rect = range.getBoundingClientRect();
  if (rect.width === 0 && rect.height === 0) {
    menu.style.display = 'none';
    return;
  }

  menu.style.display = 'flex';
  const menuWidth = menu.offsetWidth || 260;
  const menuHeight = menu.offsetHeight || 38;

  let left = rect.left + (rect.width / 2) - (menuWidth / 2);
  left = Math.max(12, Math.min(window.innerWidth - menuWidth - 12, left));

  let top = rect.top - menuHeight - 8;
  if (top < 60) {
    top = rect.bottom + 8;
  }

  menu.style.left = left + 'px';
  menu.style.top = top + 'px';
}

function hideFloatingContextMenu() {
  const menu = document.getElementById('floating-context-menu');
  if (menu) menu.style.display = 'none';
}

function execBubbleCmd(cmd) {
  recordCurrentSelection();
  if (cmd === 'copy') {
    document.execCommand('copy');
    showEditorToast('📋 Kopyalandı');
  } else if (cmd === 'cut') {
    document.execCommand('cut');
    showEditorToast('✂️ Kesildi');
  } else if (cmd === 'paste') {
    if (navigator.clipboard && navigator.clipboard.readText) {
      navigator.clipboard.readText().then(clipText => {
        if (clipText) {
          document.execCommand('insertText', false, clipText);
          showEditorToast('📄 Yapıştırıldı');
        }
      }).catch(() => {
        document.execCommand('paste');
      });
    } else {
      document.execCommand('paste');
    }
  }
  hideFloatingContextMenu();
}

// --- DİNAMİK KAYDIRMA BLUR BANTLARI (Progressive Dynamic Blur) ---
function initDynamicScrollBlur() {
  const scrollWrapper = document.getElementById('page-wrapper');
  const blurTop = document.getElementById('scroll-blur-top');
  const blurBottom = document.getElementById('scroll-blur-bottom');

  if (!scrollWrapper || !blurTop || !blurBottom) return;

  function updateBlurState() {
    const st = scrollWrapper.scrollTop;
    const maxScroll = scrollWrapper.scrollHeight - scrollWrapper.clientHeight;

    if (st > 12) {
      blurTop.classList.add('visible');
    } else {
      blurTop.classList.remove('visible');
    }

    if (maxScroll - st > 20) {
      blurBottom.classList.add('visible');
    } else {
      blurBottom.classList.remove('visible');
    }
  }

  scrollWrapper.addEventListener('scroll', () => {
    updateBlurState();
    hideFloatingContextMenu();
  }, { passive: true });

  setTimeout(updateBlurState, 300);
}
