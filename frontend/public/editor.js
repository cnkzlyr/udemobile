// UdeMobile Profesyonel Mobil Editör Motoru
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

let currentFontSize = 12;
let isMobileView = false;
let isRulerVisible = true;
let activeDragMarker = null;
let savedSelectionRange = null;

// Paragraf Ayarları Değişkenleri
let paragraphScope = 'selected';
var currentPAlign = 'justify';

var currentMargins = {
  top: 2.5,
  right: 2.5,
  bottom: 2.5,
  left: 2.5,
  header: 1.25,
  footer: 1.25,
  orientation: 'portrait' // 'portrait' or 'landscape'
};
window.currentMargins = currentMargins;

// --- Sayfa Numarası ve Biçim Boyacısı Durum Değişkenleri ---
var currentDocPageNumberPos = 'bottom-right';
var isFormatPainterActive = false;
var isFormatPainterPersistent = false;
var copiedFormat = null;
window.isFormatPainterActive = isFormatPainterActive;

// Android Native WebView ortam tespiti
if (typeof window !== 'undefined' && window.AndroidBridge) {
  try { document.body.classList.add('is-android'); } catch (e) {}
}
if (typeof window !== 'undefined') {
  window.addEventListener('DOMContentLoaded', () => {
    if (window.AndroidBridge && document.body) {
      document.body.classList.add('is-android');
    }
  });
}

// Aktif yazım ve klavye odak koruma durumu
let lastUserTypingTimestamp = 0;
function noteUserActivity() {
  lastUserTypingTimestamp = Date.now();
  window.__userHasEditedDocument = true;
  if (window.AndroidBridge && window.AndroidBridge.setDocModified) {
    try { window.AndroidBridge.setDocModified(true); } catch (e) {}
  }
}
if (typeof document !== 'undefined') {
  ['beforeinput', 'input', 'keydown', 'compositionstart', 'compositionupdate', 'compositionend'].forEach(evt => {
    document.addEventListener(evt, noteUserActivity, { passive: true, capture: true });
  });
}

function isUserTypingActive() {
  return (Date.now() - lastUserTypingTimestamp) < 3000;
}
window.isUserTypingActive = isUserTypingActive;

let countDebounceTimer = null;
function debouncedUpdateCounts(delay = 800) {
  clearTimeout(countDebounceTimer);
  countDebounceTimer = setTimeout(() => {
    updateCounts();
  }, delay);
}

// --- Google Dokümanlar Yazdırma Düzeni & Zoom Motoru ---
let currentDocFooterTemplate = '';
let currentDocHeaderTemplate = '';
let currentDocHeaderStartPage = 1;
let currentDocVerificationCode = '';
let currentZoom = 0.48;
let isFitMode = true; // true = Google Dokümanlar stili uzaktan genel görünüm (A4 sığdır)
let lastSelectedParagraphs = [];
let lastActiveParagraph = null;

function recordCurrentSelection() {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return;

  const anchor = sel.anchorNode;
  const container = document.getElementById('pages-container') || document.getElementById('sheet-container') || document.getElementById('editor-content') || document.body;
  if (!container || !container.contains(anchor)) {
    // Odak editör dışında ise seçimi koru
    return;
  }

  try {
    savedSelectionRange = sel.getRangeAt(0).cloneRange();
  } catch (e) {}

  // Aktif paragrafı bul
  let node = anchor;
  let activeP = null;
  while (node && node !== container && node !== document.body) {
    if (node.nodeType === Node.ELEMENT_NODE) {
      const tag = node.tagName.toLowerCase();
      if (tag === 'p' || tag === 'li' || tag === 'blockquote' || (tag === 'div' && (node.parentElement?.classList?.contains('page-body-box') || node.parentNode === container))) {
        activeP = node;
        break;
      }
    }
    node = node.parentNode;
  }
  if (activeP) lastActiveParagraph = activeP;

  // Seçili paragrafları bul: Hızlı O(1) imleç koruması
  if (sel.isCollapsed) {
    if (activeP) lastSelectedParagraphs = [activeP];
    return;
  }

  // Sadece kullanıcı açıkça birden çok satırı sürükleyerek seçmişse (drag selection) filtrele:
  try {
    const range = sel.getRangeAt(0);
    const parentBox = (activeP && activeP.parentElement) ? activeP.parentElement : container;
    const blocks = Array.from(parentBox.querySelectorAll('p, li, blockquote'));
    lastSelectedParagraphs = blocks.filter(b => range.intersectsNode(b));
    if (lastSelectedParagraphs.length === 0 && activeP) {
      lastSelectedParagraphs = [activeP];
    }
  } catch (e) {
    if (activeP) lastSelectedParagraphs = [activeP];
  }
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
  // Araç çubuğu butonlarının editördeki metin seçimini ve imleç odağını çalmasını engelle
  ['toolbar-container', 'floating-zoom-bar', 'ruler-container'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('mousedown', (e) => {
        if (!e.target.closest('select, input, textarea')) {
          e.preventDefault();
        }
      });
      el.addEventListener('touchstart', (e) => {
        if (!e.target.closest('select, input, textarea, .ruler-marker')) {
          // İlgisiz dokunmalarda seçimi koru
        }
      }, { passive: true });
    }
  });

  const editor = document.getElementById('editor-content');
  if (editor) {
    editor.addEventListener('input', () => {
      noteUserActivity();
      debouncedUpdateCounts(1500);
    });
  }

  document.addEventListener('selectionchange', () => {
    recordCurrentSelection();
    updateActiveButtons();
    // Yazma esnasında (IME etkinken) veya kullanıcı odağı içerideyken cetvel DOM ağacını ve yüzen menüyü ASLA kurcalama
    // Bu sayede klavyenin aniden kapanması %100 engellenir
    if (!isUserTypingActive() && !isEditorFocused()) {
      updateRulerFromActiveParagraph();
      if (!isFormatPainterActive) {
        setTimeout(updateFloatingContextMenu, 150);
      }
    }
  });

  document.addEventListener('mouseup', (e) => {
    recordCurrentSelection();
    if (isFormatPainterActive) {
      const t = e.target;
      if (t && t.closest && (t.closest('.page-body-box') || t.closest('#editor-content'))) {
        setTimeout(applyCopiedFormatToTarget, 20);
      }
    } else {
      setTimeout(updateFloatingContextMenu, 60);
    }
  });

  document.addEventListener('touchend', (e) => {
    recordCurrentSelection();
    if (isFormatPainterActive) {
      const t = e.target;
      if (t && t.closest && (t.closest('.page-body-box') || t.closest('#editor-content'))) {
        setTimeout(applyCopiedFormatToTarget, 20);
      }
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
      markDocumentUserEdited();
      handleTabAction();
    } else if (!e.ctrlKey && !e.metaKey && !e.altKey && e.key.length === 1) {
      markDocumentUserEdited();
    } else if (e.key === 'Backspace' || e.key === 'Delete' || e.key === 'Enter') {
      markDocumentUserEdited();
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
  const toolbar = document.getElementById('toolbar-container') || document.querySelector('.toolbar');
  if (toolbar) {
    toolbar.addEventListener('mousedown', (e) => {
      recordCurrentSelection();
      // <select> ve <input> dışındaki tüm buton/ikon tıklamalarında seçimi koru
      if (!e.target.closest('select, input, textarea')) {
        e.preventDefault();
      }
    });
    toolbar.addEventListener('touchstart', (e) => {
      recordCurrentSelection();
    }, { passive: true });
  }

  // Başlangıçta kenar boşlukları ve kağıt ölçeğini uygula
  applyPageSetup(currentMargins.left, currentMargins.right, currentMargins.top, currentMargins.bottom, currentMargins.orientation, currentMargins.header, currentMargins.footer);
  initRuler();
  updateRulerBodyWidth();
  initPinchToZoom();
  initDynamicScrollBlur();
  updateCounts();
  
  setTimeout(() => {
    applyAutoFitZoom();
    updatePagination();
    initRuler();
    updateRulerFromActiveParagraph();
  }, 200);
});

// Yardımcı: Kullanıcı editör alanına odaklı mı veya imleç içeride mi?
function isEditorFocused() {
  const active = document.activeElement;
  if (active && (
    active.classList?.contains('page-body-box') ||
    active.id === 'editor-content' ||
    active.isContentEditable ||
    (active.closest && active.closest('.page-body-box')) ||
    (active.closest && active.closest('#editor-content'))
  )) {
    return true;
  }
  const sel = window.getSelection();
  if (sel && sel.rangeCount > 0 && sel.anchorNode) {
    const el = sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement;
    if (el && (el.closest?.('.page-body-box') || el.closest?.('#editor-content') || el.isContentEditable)) {
      return true;
    }
  }
  return false;
}
window.isEditorFocused = isEditorFocused;

// Kağıt Görünümü (Yazdırma Düzeni) / Mobil Görünüm Geçişi
function toggleViewMode() {
  const wrapper = document.getElementById('page-wrapper');
  const btn = document.getElementById('btn-toggle-view');
  const headerBtn = document.querySelector('.mobile-header-btn');
  const pillBtn = document.getElementById('pill-toggle-view');
  const sheetContainer = document.getElementById('sheet-container');
  
  isMobileView = !isMobileView;
  if (isMobileView) {
    if (wrapper) {
      wrapper.classList.remove('paper-view');
      wrapper.classList.add('mobile-view');
    }
    document.body.classList.add('mobile-view');
    if (btn) btn.innerHTML = '🖥️ <span>Kağıt</span>';
    if (headerBtn) headerBtn.innerHTML = '🖥️ <span class="hide-on-mobile">Kağıt</span>';
    if (pillBtn) pillBtn.textContent = '🖥️';

    // Android yerel başlığındaki butonu güncelle (🖥️)
    if (window.AndroidBridge && window.AndroidBridge.onViewModeChanged) {
      try { window.AndroidBridge.onViewModeChanged(true); } catch (e) {}
    }

    if (sheetContainer) sheetContainer.style.zoom = '1';
    switchToMobileViewFlow();
    updateRulerBodyWidth();
    showEditorToast('📱 Mobil Akış Görünümü (Kesintisiz Akış)');
  } else {
    if (wrapper) {
      wrapper.classList.remove('mobile-view');
      wrapper.classList.add('paper-view');
    }
    document.body.classList.remove('mobile-view');
    if (btn) btn.innerHTML = '📱 <span>Mobil</span>';
    if (headerBtn) headerBtn.innerHTML = '📱 <span class="hide-on-mobile">Mobil</span>';
    if (pillBtn) pillBtn.textContent = '📱';

    // Android yerel başlığındaki butonu güncelle (📱)
    if (window.AndroidBridge && window.AndroidBridge.onViewModeChanged) {
      try { window.AndroidBridge.onViewModeChanged(false); } catch (e) {}
    }

    switchToPaperViewFlow();
    applyAutoFitZoom();
    updateRulerBodyWidth();
    showEditorToast('📄 Kağıt Baskı Düzeni (1:1 A4 Havelsan)');
  }
}

function switchToMobileViewFlow() {
  const container = document.getElementById('pages-container') || document.getElementById('sheet-container');
  if (!container) return;

  const existingBoxes = Array.from(container.querySelectorAll('.page-body-box'));
  let allNodes = [];
  if (existingBoxes.length > 0) {
    existingBoxes.forEach((bb, idx) => {
      if (idx > 0) {
        const divider = document.createElement('div');
        divider.className = 'mobile-page-divider';
        divider.contentEditable = 'false';
        divider.innerHTML = `<span>── Sayfa ${idx + 1} ──</span>`;
        allNodes.push(divider);
      }
      Array.from(bb.children).forEach(c => {
        if (!c.classList.contains('auto-page-break') &&
            !c.classList.contains('page-break-desk-gap') &&
            !c.classList.contains('page-desk-gap') &&
            !c.classList.contains('mobile-page-divider')) {
          allNodes.push(c);
        }
      });
    });
  } else {
    const ed = document.getElementById('editor-content');
    if (ed) allNodes = Array.from(ed.children).filter(c => !c.classList.contains('mobile-page-divider'));
  }

  container.innerHTML = `
    <div class="mobile-flow-sheet" id="mobile-sheet">
      <div id="editor-content" class="page-body-box mobile-flow-body" contenteditable="true" spellcheck="true" autocomplete="off" autocapitalize="sentences"></div>
    </div>
  `;
  const mobileEd = document.getElementById('editor-content');
  allNodes.forEach(n => mobileEd.appendChild(n));
  if (mobileEd.children.length === 0) {
    mobileEd.innerHTML = '<p style="text-align: justify;"><br></p>';
  }
  mobileEd.addEventListener('input', function() {
    markDocumentUserEdited();
    debouncedUpdateCounts(1500);
  });
}

function switchToPaperViewFlow() {
  const container = document.getElementById('pages-container') || document.getElementById('sheet-container');
  if (!container) return;
  container.querySelectorAll('.mobile-page-divider').forEach(d => d.remove());
  updatePagination();
}

// Minimal standard QR Code generator (Byte Mode, Mask 0, ECC Level L, Version 1 to 4)
function createQrSvg(text, size = 34) {
  if (!text) return "";
  const exp = new Uint8Array(512), log = new Uint8Array(256);
  let x = 1;
  for (let i = 0; i < 255; i++) {
    exp[i] = exp[i + 255] = x;
    log[x] = i;
    x = (x << 1) ^ (x >= 128 ? 0x11d : 0);
  }
  function gmul(a, b) { return (a === 0 || b === 0) ? 0 : exp[log[a] + log[b]]; }

  const bytes = new TextEncoder().encode(text);
  let ver = 2, totalCodewords = 44, dataCapacity = 34, ecCount = 10;
  if (bytes.length > 32) { ver = 3; totalCodewords = 70; dataCapacity = 44; ecCount = 15; }
  if (bytes.length > 42) { ver = 4; totalCodewords = 100; dataCapacity = 64; ecCount = 20; }
  const dim = 17 + 4 * ver;

  const bits = [];
  function pushBits(val, len) {
    for (let i = len - 1; i >= 0; i--) bits.push((val >> i) & 1);
  }
  pushBits(0b0100, 4);
  pushBits(bytes.length, 8);
  for (const b of bytes) pushBits(b, 8);
  pushBits(0, Math.min(4, dataCapacity * 8 - bits.length));
  while (bits.length % 8 !== 0) bits.push(0);
  const pads = [0xec, 0x11];
  let pIdx = 0;
  while (bits.length < dataCapacity * 8) {
    pushBits(pads[pIdx % 2], 8);
    pIdx++;
  }

  const dataCodewords = new Uint8Array(dataCapacity);
  for (let i = 0; i < dataCapacity; i++) {
    let b = 0;
    for (let j = 0; j < 8; j++) b = (b << 1) | bits[i * 8 + j];
    dataCodewords[i] = b;
  }

  let gen = [1];
  for (let i = 0; i < ecCount; i++) {
    const next = new Uint8Array(gen.length + 1);
    for (let j = 0; j < gen.length; j++) {
      next[j] ^= gmul(gen[j], exp[i]);
      next[j + 1] ^= gen[j];
    }
    gen = next;
  }

  const ec = new Uint8Array(ecCount);
  for (let i = 0; i < dataCapacity; i++) {
    const factor = dataCodewords[i] ^ ec[0];
    for (let j = 0; j < ecCount - 1; j++) {
      ec[j] = ec[j + 1] ^ gmul(gen[j], factor);
    }
    ec[ecCount - 1] = gmul(gen[ecCount - 1], factor);
  }

  const allCodewords = new Uint8Array(totalCodewords);
  allCodewords.set(dataCodewords, 0);
  allCodewords.set(ec, dataCapacity);

  const grid = Array.from({ length: dim }, () => new Int8Array(dim).fill(-1));
  function setFunc(r, c, val) { grid[r][c] = val; }

  function drawFinder(r0, c0) {
    for (let r = -1; r <= 7; r++) {
      for (let c = -1; c <= 7; c++) {
        const nr = r0 + r, nc = c0 + c;
        if (nr < 0 || nr >= dim || nc < 0 || nc >= dim) continue;
        if (r >= 0 && r <= 6 && c >= 0 && c <= 6) {
          setFunc(nr, nc, (r === 0 || r === 6 || c === 0 || c === 6 || (r >= 2 && r <= 4 && c >= 2 && c <= 4)) ? 1 : 0);
        } else {
          setFunc(nr, nc, 0);
        }
      }
    }
  }
  drawFinder(0, 0);
  drawFinder(0, dim - 7);
  drawFinder(dim - 7, 0);

  if (ver >= 2) {
    const pos = dim - 7;
    for (let r = -2; r <= 2; r++) {
      for (let c = -2; c <= 2; c++) {
        if (grid[pos + r][pos + c] === -1) {
          setFunc(pos + r, pos + c, (Math.abs(r) === 2 || Math.abs(c) === 2 || (r === 0 && c === 0)) ? 1 : 0);
        }
      }
    }
  }

  for (let i = 8; i < dim - 8; i++) {
    if (grid[6][i] === -1) setFunc(6, i, i % 2 === 0 ? 1 : 0);
    if (grid[i][6] === -1) setFunc(i, 6, i % 2 === 0 ? 1 : 0);
  }
  setFunc(4 * ver + 9, 8, 1);

  const formatBits = 0b111011111000100;
  for (let i = 0; i < 15; i++) {
    const bit = (formatBits >> i) & 1;
    if (i < 6) { setFunc(8, i, bit); setFunc(dim - 1 - i, 8, bit); }
    else if (i === 6) { setFunc(8, 7, bit); setFunc(dim - 7, 8, bit); }
    else if (i === 7) { setFunc(8, 8, bit); setFunc(dim - 8, 8, bit); }
    else if (i === 8) { setFunc(7, 8, bit); setFunc(8, dim - 7, bit); }
    else { setFunc(14 - i, 8, bit); setFunc(8, dim - 15 + i, bit); }
  }

  let bitIdx = 0;
  const totalBits = totalCodewords * 8;
  for (let right = dim - 1; right > 0; right -= 2) {
    if (right === 6) right--;
    const upward = ((dim - 1 - right) / 2) % 2 === 0;
    for (let v = 0; v < dim; v++) {
      const r = upward ? dim - 1 - v : v;
      for (let d = 0; d < 2; d++) {
        const c = right - d;
        if (grid[r][c] === -1) {
          let b = 0;
          if (bitIdx < totalBits) {
            b = (allCodewords[bitIdx >> 3] >> (7 - (bitIdx & 7))) & 1;
            bitIdx++;
          }
          if ((r + c) % 2 === 0) b ^= 1;
          grid[r][c] = b;
        }
      }
    }
  }

  let pathD = "";
  for (let r = 0; r < dim; r++) {
    for (let c = 0; c < dim; c++) {
      if (grid[r][c] === 1) {
        pathD += `M${c + 1},${r + 1}h1v1h-1z `;
      }
    }
  }
  const viewBoxSize = dim + 2;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${viewBoxSize} ${viewBoxSize}" width="${size}" height="${size}" shape-rendering="crispEdges"><path d="${pathD}" fill="#000"/></svg>`;
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

    if (tpl.includes('udf-footer-qr-container')) {
      const match = tpl.match(/data-verification-code="([^"]+)"/);
      const code = match ? match[1] : (currentDocVerificationCode || '');
      if (code) {
        const qrSvg = createQrSvg("https://vatandas.uyap.gov.tr/?k=" + encodeURIComponent(code), 34);
        tpl = tpl.replace(/(<div class="udf-footer-qr-container"[^>]*>)(<\/div>)/, `$1${qrSvg}$2`);
      }
    }

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

function isEmptyFillerParagraph(el) {
  if (!el || !el.tagName) return false;
  const tag = el.tagName.toLowerCase();
  if (tag !== 'p' && tag !== 'div') return false;
  if (el.classList && (el.classList.contains('auto-page-break') || el.classList.contains('page-break') || el.classList.contains('official-signature-seal'))) return false;
  if (el.querySelector && el.querySelector('img, table, svg, hr, input')) return false;
  const txt = (el.innerText || el.textContent || '').replace(/[\u200B\u00A0\r\n\t\s]+/g, '');
  return txt.length === 0;
}

function getOffsetTopInSheet(el, sheet) {
  let y = 0;
  let cur = el;
  while (cur && cur !== sheet && cur !== document.body) {
    y += cur.offsetTop || 0;
    cur = cur.offsetParent;
  }
  return y;
}

// --- HAVELSAN UYAP 1:1 FİZİKSEL A4 ÇOKLU SAYFA VE KART YÖNETİMİ ---
let isPaginating = false;

function saveSelectionState() {
  const sel = window.getSelection ? window.getSelection() : null;
  if (!sel || sel.rangeCount === 0) return null;
  const range = sel.getRangeAt(0);
  const container = range.startContainer;
  let p = container.nodeType === Node.ELEMENT_NODE ? container : container.parentElement;
  while (p && !p.classList.contains('page-body-box') && p.parentElement && !p.parentElement.classList.contains('page-body-box')) {
    p = p.parentElement;
  }
  if (!p || p.classList.contains('page-body-box')) return null;

  p.setAttribute('data-cursor-target', '1');
  return {
    offset: range.startOffset,
    isText: container.nodeType === Node.TEXT_NODE
  };
}

function restoreSelectionState(saved) {
  if (!saved) return;
  const target = document.querySelector('[data-cursor-target="1"]');
  if (!target) return;
  target.removeAttribute('data-cursor-target');

  try {
    const sel = window.getSelection();
    if (!sel) return;
    sel.removeAllRanges();
    const range = document.createRange();

    if (saved.isText && target.firstChild) {
      let node = target.firstChild;
      let curOff = 0;
      while (node) {
        if (node.nodeType === Node.TEXT_NODE) {
          const len = node.textContent.length;
          if (curOff + len >= saved.offset) {
            range.setStart(node, Math.min(len, Math.max(0, saved.offset - curOff)));
            range.collapse(true);
            sel.addRange(range);
            return;
          }
          curOff += len;
        }
        node = node.nextSibling;
      }
    }
    range.selectNodeContents(target);
    range.collapse(false);
    sel.addRange(range);
  } catch (e) {}
}

function findParagraphSplitIndex(pNode, maxH) {
  const measurer = document.getElementById('pagination-measurer');
  if (!measurer) return null;
  const mTop = measurer.getBoundingClientRect().top;
  const cutoffY = mTop + maxH;

  const walker = document.createTreeWalker(pNode, NodeFilter.SHOW_TEXT, null, false);
  const textNodes = [];
  let tn;
  while ((tn = walker.nextNode())) {
    textNodes.push(tn);
  }

  if (textNodes.length === 0) return null;

  const range = document.createRange();

  for (let i = 0; i < textNodes.length; i++) {
    const tNode = textNodes[i];
    const text = tNode.nodeValue;
    if (!text) continue;

    range.setStart(tNode, 0);
    range.setEnd(tNode, text.length);
    const rect = range.getBoundingClientRect();

    if (rect.bottom <= cutoffY) {
      continue;
    }

    if (rect.top > cutoffY) {
      if (i === 0) return null;
      return { splitTextNode: tNode, splitOffset: 0 };
    }

    let low = 0, high = text.length;
    let best = 0;
    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      range.setStart(tNode, 0);
      range.setEnd(tNode, mid);
      const midRect = range.getBoundingClientRect();
      if (midRect.bottom <= cutoffY) {
        best = mid;
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }

    let splitPos = best;
    while (splitPos > 0 && !/\s/.test(text[splitPos])) {
      splitPos--;
    }
    if (splitPos === 0) {
      splitPos = best > 0 ? best : 0;
    } else {
      splitPos++;
    }

    if (i === 0 && splitPos === 0) return null;
    return { splitTextNode: tNode, splitOffset: splitPos };
  }

  return null;
}

function updatePagination() {
  if (isMobileView || isPaginating) return;

  // KESİN KLAVYE VE ODAK KORUMASI:
  // Sanal klavyenin açık olduğu veya kullanıcının aktif yazı yazdığı / imlecin içeride olduğu
  // anlarda DOM ağacı (container.innerHTML = '') ASLA yıkılmaz.
  // Bu sayede Android IME odak kaybı ve klavye kapanması %100 engellenir.
  if (isEditorFocused() || isUserTypingActive()) {
    const container = document.getElementById('pages-container') || document.getElementById('sheet-container');
    if (container) {
      const currentBoxes = Array.from(container.querySelectorAll('.page-body-box'));
      const statusEl = document.getElementById('stat-page-count');
      if (statusEl && currentBoxes.length > 0) {
        statusEl.textContent = `Sayfa 1 / ${currentBoxes.length}`;
      }
    }
    return;
  }

  const container = document.getElementById('pages-container') || document.getElementById('sheet-container');
  if (!container) return;

  const currentBoxes = Array.from(container.querySelectorAll('.page-body-box'));

  isPaginating = true;
  try {
    try { realignAllTabs(); } catch (e) {}

    // 1. Gather all body content nodes across all pages in order
    const existingBodyBoxes = Array.from(container.querySelectorAll('.page-body-box'));
    let allNodes = [];
    if (existingBodyBoxes.length > 0) {
      existingBodyBoxes.forEach(bb => {
        Array.from(bb.children).forEach(child => {
          if (!child.classList.contains('auto-page-break') &&
              !child.classList.contains('page-break-desk-gap') &&
              !child.classList.contains('page-desk-gap') &&
              !child.classList.contains('page-break-footer-area') &&
              !child.classList.contains('page-break-header-area')) {
            allNodes.push(child);
          }
        });
      });
    } else {
      const editor = document.getElementById('editor-content');
      if (editor) {
        allNodes = Array.from(editor.children).filter(child =>
          !child.classList.contains('auto-page-break') &&
          !child.classList.contains('page-break-desk-gap') &&
          !child.classList.contains('page-desk-gap')
        );
      }
    }

    if (allNodes.length === 0) {
      const p = document.createElement('p');
      p.style.textAlign = 'justify';
      p.innerHTML = '<br>';
      allNodes.push(p);
    }

    // Daha önce bölünmüş paragrafları birleştirerek temiz durumdan başla
    const cleanNodes = [];
    for (let i = 0; i < allNodes.length; i++) {
      const n = allNodes[i];
      if (n.getAttribute && n.getAttribute('data-split-continuation') === 'true' && cleanNodes.length > 0) {
        const prev = cleanNodes[cleanNodes.length - 1];
        while (n.firstChild) {
          prev.appendChild(n.firstChild);
        }
      } else {
        cleanNodes.push(n);
      }
    }
    allNodes = cleanNodes;

    // 2. Havelsan UYAP (tr.com.havelsan.uyap.system.swing.wp.b.ar) birebir A4 geometri hesapları:
    const PPC = 37.795275; // 1 cm = 37.795275 px (96 DPI)
    const isLandscape = currentMargins.orientation === 'landscape';
    const pageW = isLandscape ? 1123 : 794;
    const pageH = isLandscape ? 794 : 1123;
    const leftMarginPx = (!isNaN(parseFloat(currentMargins.left)) ? parseFloat(currentMargins.left) : 2.5) * PPC;
    const rightMarginPx = (!isNaN(parseFloat(currentMargins.right)) ? parseFloat(currentMargins.right) : 2.5) * PPC;
    const topMarginPx = (!isNaN(parseFloat(currentMargins.top)) ? parseFloat(currentMargins.top) : 2.5) * PPC;
    const bottomMarginPx = (!isNaN(parseFloat(currentMargins.bottom)) ? parseFloat(currentMargins.bottom) : 2.5) * PPC;
    const headerOffsetPx = (!isNaN(parseFloat(currentMargins.header)) ? parseFloat(currentMargins.header) : 0.501) * PPC;
    const footerOffsetPx = (!isNaN(parseFloat(currentMargins.footer)) ? parseFloat(currentMargins.footer) : 0.501) * PPC;

    const printableW = Math.max(300, Math.round(pageW - leftMarginPx - rightMarginPx));

    // Üstbilgi ve Altbilgi yükseklikleri
    let headerHeightPx = 0;
    const hasHeaderTemplate = !!(currentDocHeaderTemplate && currentDocHeaderTemplate.trim());
    if (hasHeaderTemplate) {
      if (currentDocHeaderTemplate.includes('udf-header-img') || currentDocHeaderTemplate.includes('<img')) {
        headerHeightPx = 76; // Havelsan logo 50pt-54pt + padding
      } else {
        headerHeightPx = 28;
      }
    }

    let footerHeightPx = 28;
    if (currentDocFooterTemplate) {
      if (currentDocFooterTemplate.includes('udf-footer-img') || currentDocFooterTemplate.includes('<img')) {
        footerHeightPx = 76; // Havelsan altbilgi görseli (54pt = 72px) + padding
      } else if (currentDocFooterTemplate.includes('udf-official-footer') || currentDocVerificationCode) {
        footerHeightPx = 32; // UYAP doğrulama kodlu resmi altbilgi
      } else {
        footerHeightPx = 28;
      }
    }

    // Havelsan UYAP ar.s() ve ar.u() formülü:
    const topInsetPx = Math.round(hasHeaderTemplate ? Math.max(topMarginPx, headerOffsetPx + headerHeightPx) : topMarginPx);
    // UYAP standardı: Gövde metni alt marj sınırına (bottomMargin) kadar iner. Altbilgi bu marj alanı içine çizilir.
    const bottomInsetPx = Math.round(Math.max(bottomMarginPx, footerHeightPx > Math.round(bottomMarginPx) ? (footerHeightPx + 4) : bottomMarginPx));
    const printableH = Math.max(350, pageH - topInsetPx - bottomInsetPx);

    // Konteyner CSS değişkenlerini ayarla
    container.style.setProperty('--sheet-width', pageW + 'px');
    container.style.setProperty('--sheet-height', pageH + 'px');
    container.style.setProperty('--page-margin-left', Math.round(leftMarginPx) + 'px');
    container.style.setProperty('--page-margin-right', Math.round(rightMarginPx) + 'px');
    container.style.setProperty('--printable-width', printableW + 'px');
    container.style.setProperty('--top-inset', topInsetPx + 'px');
    container.style.setProperty('--bottom-inset', bottomInsetPx + 'px');
    container.style.setProperty('--printable-height', printableH + 'px');
    container.style.setProperty('--header-offset', Math.round(headerOffsetPx) + 'px');
    container.style.setProperty('--footer-offset', Math.round(footerOffsetPx) + 'px');
    container.style.setProperty('--header-height', headerHeightPx + 'px');
    container.style.setProperty('--footer-height', footerHeightPx + 'px');

    // 3. Görünmez ölçüm konteyneri ile her paragrafın A4 printableW genişliğindeki gerçek yüksekliğini ölç:
    let measurer = document.getElementById('pagination-measurer');
    if (!measurer) {
      measurer = document.createElement('div');
      measurer.id = 'pagination-measurer';
      measurer.style.cssText = `position: absolute; visibility: hidden; pointer-events: none; left: -9999px; top: 0; width: ${printableW}px; box-sizing: border-box; font-family: "Times New Roman", Times, serif; font-size: 12pt; line-height: 1.15;`;
      document.body.appendChild(measurer);
    } else {
      measurer.style.width = printableW + 'px';
    }

    const pagesData = [];
    let currentPageNodes = [];
    let currentAccumHeight = 0;
    let prevMb = 0;

    const getCapacityForPage = (pNum) => {
      const showH = hasHeaderTemplate && (pNum >= (currentDocHeaderStartPage || 1));
      const tInset = Math.round(showH ? Math.max(topMarginPx, headerOffsetPx + headerHeightPx) : topMarginPx);
      return Math.max(350, pageH - tInset - bottomInsetPx);
    };

    let targetCap = getCapacityForPage(1);

    const nodeQueue = [...allNodes];
    while (nodeQueue.length > 0) {
      const node = nodeQueue.shift();
      if (!node) continue;

      // Kullanıcının veya UDF'in eklediği sayfa sonu
      if (node.classList && (node.classList.contains('page-break') || node.classList.contains('udf-page-break') || node.getAttribute('data-udf-page-break') === 'true')) {
        if (currentPageNodes.length > 0) {
          pagesData.push(currentPageNodes);
          currentPageNodes = [];
          currentAccumHeight = 0;
          prevMb = 0;
          targetCap = getCapacityForPage(pagesData.length + 1);
        }
        continue;
      }

      const clone = node.cloneNode(true);
      measurer.appendChild(clone);
      const cs = window.getComputedStyle(clone);
      const mt = parseFloat(cs.marginTop) || 0;
      const mb = parseFloat(cs.marginBottom) || 0;
      const rawH = clone.offsetHeight || 18.4;
      measurer.removeChild(clone);
      const gap = (currentAccumHeight === 0) ? mt : Math.max(prevMb, mt);
      const h = rawH + gap;

      if ((currentAccumHeight + h > targetCap) && currentPageNodes.length > 0) {
        // Sığmıyor! Havelsan UYAP standardı: Paragrafı satır satır bölmeyi dene
        const availH = targetCap - currentAccumHeight - gap;
        const isSplittable = (node.tagName && node.tagName.toLowerCase() === 'p') &&
                             !node.classList.contains('page-break') &&
                             !node.classList.contains('udf-page-break') &&
                             availH >= 24;

        if (isSplittable) {
          const splitRes = findParagraphSplitIndex(node, availH);
          if (splitRes && splitRes.splitTextNode) {
            const range = document.createRange();
            range.setStart(splitRes.splitTextNode, splitRes.splitOffset);
            range.setEndAfter(node.lastChild);
            const fragment = range.extractContents();

            const contP = node.cloneNode(false);
            contP.appendChild(fragment);
            contP.setAttribute('data-split-continuation', 'true');
            contP.style.textIndent = '0cm';
            contP.style.marginTop = '0px';
            contP.style.paddingTop = '0px';
            node.style.marginBottom = '0px';

            currentPageNodes.push(node);
            pagesData.push(currentPageNodes);

            currentPageNodes = [];
            currentAccumHeight = 0;
            prevMb = 0;
            targetCap = getCapacityForPage(pagesData.length + 1);
            nodeQueue.unshift(contP);
            continue;
          }
        }

        pagesData.push(currentPageNodes);
        currentPageNodes = [node];
        currentAccumHeight = rawH + mt;
        prevMb = mb;
        targetCap = getCapacityForPage(pagesData.length + 1);
      } else {
        currentPageNodes.push(node);
        currentAccumHeight += h;
        prevMb = mb;
      }
    }

    if (currentPageNodes.length > 0 || pagesData.length === 0) {
      pagesData.push(currentPageNodes);
    }

    const totalPages = pagesData.length;

    // Sayfalama optimizasyonu: Eğer sayfa sayısı ve sayfaların içerdiği paragraflar
    // değişmediyse DOM'u asla yıkıp yeniden inşa etme (container.innerHTML = '').
    // Bu sayede tarayıcının yerel Undo/Redo (Geri Al / Yinele) geçmişi, imleç konumu
    // ve seçimi %100 kesintisiz korunur, yazım anında sıfır gecikme sağlanır.
    let isDomIdentical = (pagesData.length === existingBodyBoxes.length);
    if (isDomIdentical && existingBodyBoxes.length > 0) {
      for (let p = 0; p < totalPages; p++) {
        const curChildren = Array.from(existingBodyBoxes[p].children).filter(c =>
          !c.classList.contains('auto-page-break') &&
          !c.classList.contains('page-break-desk-gap') &&
          !c.classList.contains('page-desk-gap')
        );
        const nextNodes = pagesData[p];
        if (curChildren.length !== nextNodes.length) {
          isDomIdentical = false;
          break;
        }
        for (let j = 0; j < curChildren.length; j++) {
          if (curChildren[j] !== nextNodes[j]) {
            isDomIdentical = false;
            break;
          }
        }
        if (!isDomIdentical) break;
      }
    }

    if (isDomIdentical && existingBodyBoxes.length > 0) {
      const statusEl = document.getElementById('stat-page-count');
      if (statusEl) {
        statusEl.textContent = `Sayfa 1 / ${totalPages}`;
      }
      return;
    }

    // 4. Fiziksel A4 Kart Sayfalarını İnşa Et
    const savedSel = saveSelectionState();
    container.innerHTML = '';

    const sicilVal = (window.currentDocSicil || '').trim();
    const watermarkHtml = sicilVal
      ? `<div class="sheet-watermark-overlay" aria-hidden="true">${Array(36).fill(`<span>${escapeHtml(sicilVal)}</span>`).join('')}</div>`
      : '';

    for (let pIdx = 0; pIdx < totalPages; pIdx++) {
      const pageNum = pIdx + 1;
      const showH = hasHeaderTemplate && (pageNum >= (currentDocHeaderStartPage || 1));
      const tInset = Math.round(showH ? Math.max(topMarginPx, headerOffsetPx + headerHeightPx) : topMarginPx);
      const pPrintableH = Math.max(350, pageH - tInset - bottomInsetPx);

      // Sayfalar arası masaüstü gri boşluğu
      if (pIdx > 0) {
        const gap = document.createElement('div');
        gap.className = 'page-desk-gap';
        gap.setAttribute('data-page-label', `Sayfa ${pIdx} / ${totalPages}`);
        gap.innerHTML = `<span class="page-desk-chip">Sayfa ${pIdx} / ${totalPages}</span>`;
        container.appendChild(gap);
      }

      // Fiziksel A4 Kağıt Kartı (Tam 1123px x 794px, Asla Uzamaz!)
      const pageSheet = document.createElement('div');
      pageSheet.className = 'a4-sheet-page' + (isLandscape ? ' landscape' : '');
      pageSheet.setAttribute('data-page-number', pageNum);
      pageSheet.id = `page-${pageNum}`;

      // Filigran
      if (watermarkHtml) {
        pageSheet.insertAdjacentHTML('afterbegin', watermarkHtml);
      }

      // Sayfa 1'de Resmi E-İmza Rozeti
      if (pageNum === 1) {
        const sealDiv = document.createElement('div');
        sealDiv.id = 'official-doc-seal';
        sealDiv.className = 'official-doc-seal';
        sealDiv.onclick = openSignatureModal;
        sealDiv.title = 'Elektronik İmza Doğrulama ve Detayları';
        sealDiv.style.display = window.currentDocHasSignature ? 'flex' : 'none';
        sealDiv.innerHTML = '<div class="seal-medal">⚖️</div><div class="seal-ribbon"></div>';
        pageSheet.appendChild(sealDiv);
      }

      // 1. Rezerve Üstbilgi Alanı (Üst Yazı)
      const headerBox = document.createElement('div');
      headerBox.className = 'page-header-box';
      if (pageNum === 1) headerBox.id = 'doc-header';
      headerBox.setAttribute('contenteditable', 'true');
      headerBox.setAttribute('spellcheck', 'false');
      headerBox.style.top = Math.round(headerOffsetPx) + 'px';
      headerBox.style.left = Math.round(leftMarginPx) + 'px';
      headerBox.style.width = printableW + 'px';
      headerBox.style.height = headerHeightPx + 'px';

      if (showH) {
        headerBox.innerHTML = currentDocHeaderTemplate;
        headerBox.style.display = 'flex';
      } else {
        headerBox.innerHTML = '';
        headerBox.style.display = 'none';
      }
      headerBox.addEventListener('input', () => {
        currentDocHeaderTemplate = headerBox.innerHTML;
        debouncedPagination(400);
      });
      pageSheet.appendChild(headerBox);

      // 2. Rezerve Gövde Metin Alanı (Printable Body)
      const bodyBox = document.createElement('div');
      bodyBox.className = 'page-body-box';
      if (pageNum === 1) bodyBox.id = 'editor-content';
      bodyBox.setAttribute('contenteditable', 'true');
      bodyBox.setAttribute('spellcheck', 'true');
      bodyBox.setAttribute('autocomplete', 'off');
      bodyBox.setAttribute('autocapitalize', 'sentences');
      bodyBox.style.top = tInset + 'px';
      bodyBox.style.left = Math.round(leftMarginPx) + 'px';
      bodyBox.style.width = printableW + 'px';
      bodyBox.style.height = pPrintableH + 'px';

      const pNodes = pagesData[pIdx] || [];
      pNodes.forEach(n => bodyBox.appendChild(n));
      if (pNodes.length === 0) {
        bodyBox.innerHTML = '<p style="text-align: justify;"><br></p>';
      }

      bodyBox.addEventListener('input', function() {
        markDocumentUserEdited();
        debouncedUpdateCounts(800);
      });

      pageSheet.appendChild(bodyBox);

      // 3. Rezerve Altbilgi Alanı (Alt Yazı ve Sayfa Numarası)
      const footerBox = document.createElement('div');
      footerBox.className = 'page-footer-box';
      if (pageNum === 1) footerBox.id = 'doc-footer';
      footerBox.setAttribute('contenteditable', 'false');
      footerBox.style.bottom = Math.round(footerOffsetPx) + 'px';
      footerBox.style.left = Math.round(leftMarginPx) + 'px';
      footerBox.style.width = printableW + 'px';
      footerBox.style.height = footerHeightPx + 'px';
      footerBox.innerHTML = getDocFooterHtml(pageNum, totalPages);
      pageSheet.appendChild(footerBox);

      container.appendChild(pageSheet);
    }

    restoreSelectionState(savedSel);

    // Durum çubuğunda sayfa sayısını göster
    const statusEl = document.getElementById('stat-page-count');
    if (statusEl) {
      statusEl.textContent = `Sayfa 1 / ${totalPages}`;
    }
  } finally {
    isPaginating = false;
  }
}

function debouncedPagination(delay = 500) {
  clearTimeout(paginationTimer);
  paginationTimer = setTimeout(updatePagination, delay);
}

// Üstbilgi ve Altbilgiye Odaklanma (Asla kaybolmaz, doğrudan düzenlenir)
function focusHeaderFooter() {
  const header = document.getElementById('doc-header');
  const footer = document.getElementById('doc-footer');
  if (header && header.style.display === 'none') {
    header.style.display = 'flex';
    if (!header.innerHTML.trim()) header.innerHTML = '<p style="text-align:center;"><br></p>';
    currentDocHeaderTemplate = header.innerHTML;
    currentDocHeaderStartPage = 1;
    debouncedPagination(100);
    header.focus();
    header.scrollIntoView({ behavior: 'smooth', block: 'center' });
    return;
  }
  if (header && document.activeElement === header && footer) {
    footer.focus();
    footer.scrollIntoView({ behavior: 'smooth', block: 'center' });
  } else if (header) {
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
  // Geri al: Tarayıcının yerel UndoManager motorunu doğrudan çalıştırır.
  // Bu sayede her harf, kelime, boşluk, silme ve biçimlendirme adım adım, tam imleç konumunda geri alınır.
  if (cmd === 'undo') {
    let targetBox = document.activeElement && document.activeElement.classList && document.activeElement.classList.contains('page-body-box')
      ? document.activeElement
      : (document.getElementById('editor-content') || document.querySelector('.page-body-box'));
    if (targetBox && document.activeElement !== targetBox && !targetBox.contains(document.activeElement)) {
      const sel = window.getSelection();
      const curRange = (sel && sel.rangeCount > 0) ? sel.getRangeAt(0) : null;
      targetBox.focus();
      if (curRange && sel) {
        try {
          sel.removeAllRanges();
          sel.addRange(curRange);
        } catch (x) {}
      }
    }

    let ok = false;
    try {
      ok = document.execCommand('undo', false, null);
    } catch (e) {
      ok = false;
    }

    if (!ok && window.CanHistory && typeof window.CanHistory.undo === 'function' && window.CanHistory.canUndo()) {
      ok = window.CanHistory.undo();
    }

    updateActiveButtons();
    updateCounts();
    return;
  }

  // Yinele: Tarayıcının yerel RedoManager motorunu adım adım çalıştırır.
  if (cmd === 'redo') {
    let targetBox = document.activeElement && document.activeElement.classList && document.activeElement.classList.contains('page-body-box')
      ? document.activeElement
      : (document.getElementById('editor-content') || document.querySelector('.page-body-box'));
    if (targetBox && document.activeElement !== targetBox && !targetBox.contains(document.activeElement)) {
      const sel = window.getSelection();
      const curRange = (sel && sel.rangeCount > 0) ? sel.getRangeAt(0) : null;
      targetBox.focus();
      if (curRange && sel) {
        try {
          sel.removeAllRanges();
          sel.addRange(curRange);
        } catch (x) {}
      }
    }

    let ok = false;
    try {
      ok = document.execCommand('redo', false, null);
    } catch (e) {
      ok = false;
    }

    if (!ok && window.CanHistory && typeof window.CanHistory.redo === 'function' && window.CanHistory.canRedo()) {
      ok = window.CanHistory.redo();
    }

    updateActiveButtons();
    updateCounts();
    return;
  }

  document.execCommand(cmd, false, val);

  // Paragraf hizalaması: Hem CSS style hem align niteliğini eşzamanlı güncelle
  if (cmd === 'justifyLeft' || cmd === 'justifyCenter' || cmd === 'justifyRight' || cmd === 'justifyFull') {
    const alignVal = cmd === 'justifyLeft' ? 'left' : (cmd === 'justifyCenter' ? 'center' : (cmd === 'justifyRight' ? 'right' : 'justify'));
    const ap = getActiveParagraph();
    if (ap) {
      ap.style.textAlign = alignVal;
      ap.setAttribute('align', alignVal);
    }
  }

  // Düzenlenebilir alan odaklı değilse son aktif sayfaya odak ver
  const isEditable = document.activeElement && (document.activeElement.isContentEditable || (document.activeElement.closest && document.activeElement.closest('.page-body-box')));
  if (!isEditable) {
    const curBox = document.querySelector('.page-body-box') || document.getElementById('editor-content');
    if (curBox) curBox.focus();
  }

  updateActiveButtons();
  updateCounts();
}

// Yazı Tipi Ailesi (Tüm Sayfalar ve Seçim Uyumlu)
function changeFontFamily(font) {
  const selection = window.getSelection();
  if (selection.rangeCount > 0 && !selection.isCollapsed) {
    document.execCommand('fontName', false, font);
  } else {
    document.querySelectorAll('.page-body-box').forEach(box => {
      box.style.fontFamily = font;
    });
    const ed = document.getElementById('editor-content');
    if (ed) ed.style.fontFamily = font;
  }
  updateCounts();
  debouncedPagination();
  if (window.CanHistory) CanHistory.commit();
}

// Yazı Boyutu (Punto Seçici Dropdown & A- / A+)
function changeFontSize(val) {
  const size = parseInt(val, 10);
  if (isNaN(size) || size < 6 || size > 72) return;
  currentFontSize = size;
  window.currentFontSize = currentFontSize;
  const label = document.getElementById('font-size-label');
  if (label) label.textContent = currentFontSize + 'pt';
  const selEl = document.getElementById('select-font-size');
  if (selEl) selEl.value = currentFontSize;

  const selection = window.getSelection();
  if (selection && selection.rangeCount > 0 && !selection.isCollapsed) {
    document.execCommand('fontSize', false, '7');
    const fontElements = document.getElementsByTagName('font');
    for (let el of fontElements) {
      if (el.size === '7' || el.getAttribute('size') === '7') {
        el.removeAttribute('size');
        el.style.fontSize = currentFontSize + 'pt';
      }
    }
  } else {
    document.querySelectorAll('.page-body-box').forEach(box => {
      box.style.fontSize = currentFontSize + 'pt';
    });
    const ed = document.getElementById('editor-content');
    if (ed) ed.style.fontSize = currentFontSize + 'pt';
  }
  updateCounts();
  if (window.CanHistory) CanHistory.commit();
}
window.changeFontSize = changeFontSize;

function adjustFontSize(delta) {
  changeFontSize(currentFontSize + delta);
}

// --- PARAGRAF BULMA VE HEDEFLİ SEÇİM (Tüm Sayfalar Uyumlu) ---
function getActiveParagraph() {
  const selection = window.getSelection ? window.getSelection() : null;
  if (selection && selection.rangeCount > 0) {
    let node = selection.anchorNode;
    if (!node) return lastActiveParagraph;
    let el = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
    const bodyBox = el ? (el.closest ? el.closest('.page-body-box') : null) : null;
    if (bodyBox) {
      while (el && el !== bodyBox && el !== document.body) {
        const tag = el.tagName ? el.tagName.toLowerCase() : '';
        if (tag === 'p' || tag === 'li' || tag === 'blockquote' || (tag === 'div' && el.parentNode === bodyBox)) {
          lastActiveParagraph = el;
          return el;
        }
        el = el.parentElement;
      }
    }
  }
  if (lastActiveParagraph && document.body.contains(lastActiveParagraph)) {
    return lastActiveParagraph;
  }
  const ps = document.querySelectorAll('.page-body-box p, .page-body-box li, #editor-content p');
  return ps.length > 0 ? ps[0] : null;
}

function getSelectedParagraphs() {
  const selection = window.getSelection ? window.getSelection() : null;
  const cp = getActiveParagraph();
  if (selection && selection.rangeCount > 0 && selection.isCollapsed && cp) {
    return [cp];
  }
  if (selection && selection.rangeCount > 0 && !selection.isCollapsed) {
    try {
      const range = selection.getRangeAt(0);
      const allBlocks = Array.from(document.querySelectorAll('.page-body-box p, .page-body-box li, .page-body-box blockquote, #editor-content p'));
      const intersected = allBlocks.filter(b => range.intersectsNode(b));
      if (intersected.length > 0) {
        lastSelectedParagraphs = intersected;
        return intersected;
      }
    } catch(e) {}
  }

  // Seçim araç çubuğuna tıklanması nedeniyle odak kaybında önceden kaydedilen seçimi kullan:
  if (lastSelectedParagraphs && lastSelectedParagraphs.length > 0) {
    const valid = lastSelectedParagraphs.filter(p => document.body.contains(p));
    if (valid.length > 0) return valid;
  }

  return cp ? [cp] : [];
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
  if (window.CanHistory) CanHistory.commit();
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
  if (window.CanHistory) CanHistory.commit();
}

// --- SAYFA YAPISI VE KENAR BOŞLUKLARI MOTORU ---
function applyPageSetup(left, right, top, bottom, orientation, header, footer) {
  if (left !== undefined && left !== null && !isNaN(parseFloat(left))) currentMargins.left = parseFloat(left);
  if (right !== undefined && right !== null && !isNaN(parseFloat(right))) currentMargins.right = parseFloat(right);
  if (top !== undefined && top !== null && !isNaN(parseFloat(top))) currentMargins.top = parseFloat(top);
  if (bottom !== undefined && bottom !== null && !isNaN(parseFloat(bottom))) currentMargins.bottom = parseFloat(bottom);
  if (header !== undefined && header !== null && !isNaN(parseFloat(header))) currentMargins.header = parseFloat(header);
  if (footer !== undefined && footer !== null && !isNaN(parseFloat(footer))) currentMargins.footer = parseFloat(footer);
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
  const isMobileDevice = window.innerWidth < 650;
  if (!isMobileView) {
    const scale = availableWidth / sheetWidth;
    if (isMobileDevice) {
      // Telefonda A4 kağıt görünümünü ekran genişliğine sığdır
      return Math.round(Math.min(1.0, Math.max(0.38, scale)) * 100) / 100;
    }
    // Masaüstünde pencere daralsa dahi UYAP standardında net okunabilirlik için min %75
    return Math.round(Math.max(0.75, Math.min(1.2, scale)) * 100) / 100;
  }
  const fit = Math.min(1.0, Math.max(0.35, availableWidth / sheetWidth));
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
  updateRulerBodyWidth();

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

  let lastRecordedWidth = window.innerWidth;
  window.addEventListener('resize', () => {
    // Sanal klavye açıldığında/kapandığında innerHeight değişir, innerWidth DEĞİŞMEZ.
    // Klavye tetiklemeli odak kaybını ve klavye kapanmasını %100 engelle:
    if (Math.abs(window.innerWidth - lastRecordedWidth) < 25) {
      return;
    }
    lastRecordedWidth = window.innerWidth;
    if (isEditorFocused() || isUserTypingActive()) {
      return;
    }
    if (isFitMode && !isMobileView) {
      applyAutoFitZoom();
    }
    updateRulerBodyWidth();
  });
}

// Cetvel genişliğini kağıt sayfasına veya ekrana tam oturacak şekilde ayarla (e-UDF standardı)
function updateRulerBodyWidth() {
  const rulerBody = document.getElementById('ruler-body');
  if (!rulerBody) return;
  const sheet = document.querySelector('.a4-sheet-page') || document.querySelector('.mobile-flow-sheet') || document.getElementById('editor-content');
  if (sheet && !isMobileView) {
    const rect = sheet.getBoundingClientRect();
    if (rect.width > 200) {
      rulerBody.style.width = Math.round(rect.width) + 'px';
      rulerBody.style.maxWidth = Math.round(rect.width) + 'px';
      rulerBody.style.margin = '0 auto';
      return;
    }
  }
  rulerBody.style.width = '100%';
  rulerBody.style.maxWidth = '100%';
  rulerBody.style.margin = '0 auto';
}
window.updateRulerBodyWidth = updateRulerBodyWidth;

// --- DİNAMİK CETVEL MOTORU ---
function initRuler() {
  const ticksContainer = document.getElementById('ruler-ticks');
  if (!ticksContainer) return;
  ticksContainer.innerHTML = '';

  const isLandscape = currentMargins.orientation === 'landscape';
  const totalPageCm = isLandscape ? 29.7 : 21.0;
  const leftCm = (currentMargins.left !== undefined) ? currentMargins.left : 2.5;
  const rightCm = (currentMargins.right !== undefined) ? currentMargins.right : 2.5;
  const activeCm = Math.max(5, totalPageCm - leftCm - rightCm);
  const totalMm = Math.round(activeCm * 10);

  const leftPct = (leftCm / totalPageCm) * 100;
  const rightPct = (rightCm / totalPageCm) * 100;

  // Sol kenar boşluğunda negatif ölçek (-2cm .. 0)
  const leftMarginBox = document.querySelector('.ruler-margin-left');
  if (leftMarginBox) {
    leftMarginBox.style.width = leftPct.toFixed(2) + '%';
    leftMarginBox.innerHTML = '';
    const negMm = Math.round(leftCm * 10);
    for (let m = 0; m <= negMm; m++) {
      const tick = document.createElement('div');
      tick.style.left = ((m / negMm) * 100) + '%';
      if (m === 0) {
        tick.className = 'ruler-tick cm';
        const num = document.createElement('div');
        num.className = 'ruler-number';
        num.style.left = ((m / negMm) * 100) + '%';
        num.textContent = -Math.round(leftCm);
        leftMarginBox.appendChild(num);
      } else if (m === Math.round(negMm / 2)) {
        tick.className = 'ruler-tick cm';
        const num = document.createElement('div');
        num.className = 'ruler-number';
        num.style.left = ((m / negMm) * 100) + '%';
        num.textContent = -1;
        leftMarginBox.appendChild(num);
      } else if (m % 5 === 0) {
        tick.className = 'ruler-tick half-cm';
      } else {
        tick.className = 'ruler-tick mm';
      }
      leftMarginBox.appendChild(tick);
    }
  }

  // Sağ kenar boşluğunda pozitif uzantı ölçeği (16cm .. 18cm)
  const rightMarginBox = document.querySelector('.ruler-margin-right');
  if (rightMarginBox) {
    rightMarginBox.style.width = rightPct.toFixed(2) + '%';
    rightMarginBox.innerHTML = '';
    const posMm = Math.round(rightCm * 10);
    for (let m = 0; m <= posMm; m++) {
      const tick = document.createElement('div');
      tick.style.left = ((m / posMm) * 100) + '%';
      if (m === Math.round(posMm / 2)) {
        tick.className = 'ruler-tick cm';
        const num = document.createElement('div');
        num.className = 'ruler-number';
        num.style.left = ((m / posMm) * 100) + '%';
        num.textContent = Math.round(activeCm + 1);
        rightMarginBox.appendChild(num);
      } else if (m === posMm) {
        tick.className = 'ruler-tick cm';
        const num = document.createElement('div');
        num.className = 'ruler-number';
        num.style.left = ((m / posMm) * 100) + '%';
        num.textContent = Math.round(activeCm + rightCm);
        rightMarginBox.appendChild(num);
      } else if (m % 5 === 0) {
        tick.className = 'ruler-tick half-cm';
      } else {
        tick.className = 'ruler-tick mm';
      }
      rightMarginBox.appendChild(tick);
    }
  }

  // Aktif yazı alanı ölçeği (0 .. 16cm)
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
  setupMarkerDragging('marker-hanging-indent', 'hangingIndent', activeCm);
  setupMarkerDragging('marker-left-indent', 'leftIndent', activeCm);
  setupMarkerDragging('marker-right-indent', 'rightIndent', activeCm);
  updateRulerBodyWidth();

  const rulerScale = document.getElementById('ruler-scale');
  rulerScale.addEventListener('mousedown', (e) => {
    // Editördeki metin seçiminin cetvele tıklanınca kaybolmaması için mousedown'u engelle
    e.preventDefault();
  });

  const handleRulerScaleTap = (clientX, target) => {
    if (activeDragMarker) return;
    if (target && (target.closest('.ruler-tab-stop') || target.closest('.ruler-marker'))) {
      return;
    }
    const rect = rulerScale.getBoundingClientRect();
    const x = clientX - rect.left;
    const pct = Math.max(0, Math.min(1, x / rect.width));
    const cm = Math.round((pct * activeCm) * 10) / 10;
    toggleTabStop(cm);
  };

  rulerScale.onclick = (e) => {
    handleRulerScaleTap(e.clientX, e.target);
  };

  let touchStartPos = null;
  rulerScale.addEventListener('touchstart', (e) => {
    if (e.touches && e.touches.length === 1) {
      touchStartPos = { x: e.touches[0].clientX, y: e.touches[0].clientY, target: e.target };
    }
  }, { passive: true });

  rulerScale.addEventListener('touchend', (e) => {
    if (touchStartPos && e.changedTouches && e.changedTouches.length === 1) {
      const dx = Math.abs(e.changedTouches[0].clientX - touchStartPos.x);
      const dy = Math.abs(e.changedTouches[0].clientY - touchStartPos.y);
      if (dx < 10 && dy < 10) {
        handleRulerScaleTap(e.changedTouches[0].clientX, touchStartPos.target);
      }
    }
    touchStartPos = null;
  }, { passive: true });
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
  return p.dataset.tabStops.split(',').map(s => {
    const parts = s.trim().split(':');
    const pos = parseFloat(parts[0]);
    const align = parts[1] || 'left';
    return isNaN(pos) ? null : { pos, align };
  }).filter(Boolean).sort((a, b) => a.pos - b.pos);
}

// Word mantığı: özel durak varsa önce ona gider; özel duraklardan sonra varsayılan 1.25 cm ızgarası
function computeNextTabStop(stops, curCm) {
  const EPS = 0.05;
  const custom = stops.find(s => (typeof s === 'object' ? s.pos : s) > curCm + EPS);
  if (custom !== undefined) return (typeof custom === 'object' ? custom.pos : custom);
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
      const first = Math.max(1, typeof stops[0] === 'object' ? stops[0].pos : stops[0]);
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

  // Ölçüm öncesi tüm sekmelerin genişliğini sıfırla (önceki hesaplamalardan bağımsız kesin ölçüm)
  tabSpaces.forEach(ts => {
    ts.style.width = '0px';
    if (!ts.hasAttribute('contenteditable')) ts.setAttribute('contenteditable', 'false');
    if (!ts.textContent) ts.textContent = '\u200B';
    ts.style.display = 'inline-block';
  });

  // Sırayla her sekme boşluğunun genişliğini hedef durağa göre belirle
  tabSpaces.forEach((ts, tabIdx) => {
    const tsRect = ts.getBoundingClientRect();
    const curCm = Math.max(0, (tsRect.left - m.left) / m.ppc);

    const stopObj = (tabIdx < stops.length) ? stops[tabIdx] : null;
    const target = stopObj ? (typeof stopObj === 'object' ? stopObj.pos : stopObj) : computeNextTabStop(stops, curCm);
    const align = stopObj && typeof stopObj === 'object' ? stopObj.align : 'left';
    let gap = target - curCm;

    // UYAP / Havelsan standardı: Son sekmeden sonra metin geliyorsa ve tanımlı durak kalmadıysa
    // (örneğin T.C. ... BERAAT başlığı), kalan metni sağ marja yasla
    const hasTrailingContent = ts.nextSibling && (ts.nextSibling.textContent || '').trim().length > 0;
    if (tabIdx >= stops.length && hasTrailingContent) {
      let trailingW = 0;
      let nextNode = ts.nextSibling;
      while (nextNode) {
        if (nextNode.nodeType === Node.TEXT_NODE) {
          const r = document.createRange();
          r.selectNodeContents(nextNode);
          trailingW += r.getBoundingClientRect().width;
        } else if (nextNode.getBoundingClientRect) {
          trailingW += nextNode.getBoundingClientRect().width;
        }
        nextNode = nextNode.nextSibling;
      }
      const trailingCm = trailingW / m.ppc;
      const targetGap = m.widthCm - curCm - trailingCm - 0.08;
      if (targetGap > 0.3) {
        gap = targetGap;
      }
    } else if (align === 'center' && ts.nextSibling) {
      // Merkezli sekme durağı: sekmeden sonra gelen kelimenin / parçanın merkezini durağa ortala
      let chunkW = 0;
      let nextNode = ts.nextSibling;
      while (nextNode && !(nextNode.classList && nextNode.classList.contains('udf-tab-space'))) {
        if (nextNode.nodeType === Node.TEXT_NODE) {
          const r = document.createRange();
          r.selectNodeContents(nextNode);
          chunkW += r.getBoundingClientRect().width;
        } else if (nextNode.getBoundingClientRect) {
          chunkW += nextNode.getBoundingClientRect().width;
        }
        nextNode = nextNode.nextSibling;
      }
      const halfW = (chunkW / 2) / m.ppc;
      gap = Math.max(0.1, target - curCm - halfW);
    }

    // Satır sonuna taşmasın (asla alt satıra düşürme)
    const room = m.widthCm - curCm;
    if (room > 0.1 && gap > room) gap = room;
    gap = Math.max(0.05, gap);
    const targetWidth = (Math.round(gap * 1000) / 1000) + 'cm';
    ts.style.width = targetWidth;
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
  if (isUserTypingActive()) return;
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
  if (marker._dragBound) return;
  marker._dragBound = true;

  function onStart(e) {
    e.preventDefault();
    e.stopPropagation();
    activeDragMarker = markerId;

    const isLandscape = currentMargins.orientation === 'landscape';
    const totalPageCm = isLandscape ? 29.7 : 21.0;
    const currentActiveCm = Math.max(5, totalPageCm - (currentMargins.left || 2.5) - (currentMargins.right || 2.5));

    const p = getActiveParagraph();
    let initLeftCm = 0;
    let initTextIndentCm = 0;
    if (p) {
      const marginL = parseToCm(p.style.marginLeft);
      const paddingL = parseToCm(p.style.paddingLeft);
      const compL = parseToCm(window.getComputedStyle(p).marginLeft);
      initLeftCm = (marginL || paddingL) ? (marginL + paddingL) : compL;
      initTextIndentCm = parseToCm(p.style.textIndent || window.getComputedStyle(p).textIndent);
    }
    const initFirstLineRulerCm = Math.max(0, initLeftCm + initTextIndentCm);

    const firstMarker = document.getElementById('marker-first-line');
    const hangingMarker = document.getElementById('marker-hanging-indent');
    const leftMarker = document.getElementById('marker-left-indent');
    const rightMarker = document.getElementById('marker-right-indent');
    const guideLine = document.getElementById('ruler-guide-line');
    const tooltip = document.getElementById('ruler-tooltip');

    const startClientX = e.touches ? e.touches[0].clientX : e.clientX;
    const initialRect = scale.getBoundingClientRect();
    const startPct = Math.max(0, Math.min(1, (startClientX - initialRect.left) / initialRect.width));
    const startTouchCm = Math.round((startPct * currentActiveCm) * 4) / 4;

    if (guideLine) {
      guideLine.style.display = 'block';
      guideLine.style.left = startClientX + 'px';
    }

    const moveHandler = (moveEvent) => {
      if (moveEvent.cancelable) moveEvent.preventDefault();
      const clientX = moveEvent.touches ? moveEvent.touches[0].clientX : moveEvent.clientX;
      const rect = scale.getBoundingClientRect();
      const x = clientX - rect.left;
      const pct = Math.max(0, Math.min(1, x / rect.width));
      const currentCm = Math.round((pct * currentActiveCm) * 4) / 4;
      const delta = currentCm - startTouchCm;

      if (guideLine) {
        guideLine.style.left = clientX + 'px';
      }

      let tipText = '';
      let markerPosPct = 0;

      if (type === 'firstLine') {
        // 1. Üstteki Aşağı Bakan Üçgen (İlk Satır Girintisi):
        // Yalnızca ilk satırı taşır. Asılı girinti ve sol girinti kutusu SABİT kalır.
        const targetFirst = Math.max(0, Math.min(currentActiveCm - 0.5, initFirstLineRulerCm + delta));
        markerPosPct = (targetFirst / currentActiveCm * 100);
        if (firstMarker) firstMarker.style.left = markerPosPct + '%';
        if (hangingMarker) hangingMarker.style.left = (initLeftCm / currentActiveCm * 100) + '%';
        if (leftMarker) leftMarker.style.left = (initLeftCm / currentActiveCm * 100) + '%';
        setFirstLineIndent(targetFirst, initLeftCm);
        tipText = `İlk Satır: ${targetFirst.toFixed(2)} cm`;
      } else if (type === 'hangingIndent') {
        // 2. Ortadaki Yukarı Bakan Üçgen (Asılı Girinti):
        // 2. ve sonraki satırların girintisini ayarlar. Altındaki kutu onunla birlikte hareket eder.
        // İLK SATIRIN CETVELDEKİ POZİSYONU SABİT KALIR.
        const targetHanging = Math.max(0, Math.min(currentActiveCm - 0.5, initLeftCm + delta));
        markerPosPct = (targetHanging / currentActiveCm * 100);
        if (hangingMarker) hangingMarker.style.left = markerPosPct + '%';
        if (leftMarker) leftMarker.style.left = markerPosPct + '%';
        if (firstMarker) firstMarker.style.left = (initFirstLineRulerCm / currentActiveCm * 100) + '%';
        setHangingIndent(targetHanging, initFirstLineRulerCm);
        tipText = `Asılı Girinti: ${targetHanging.toFixed(2)} cm`;
      } else if (type === 'leftIndent') {
        // 3. En Alttaki Dikdörtgen Kutu (Sol Girinti - Tüm Paragraf):
        // TÜM PARAGRAFI BLOK HALİNDE TAŞIR. İlk satır ve asılı satırlar arasındaki fark korunur.
        let safeDelta = delta;
        if (initLeftCm + safeDelta < 0) safeDelta = -initLeftCm;
        if (initFirstLineRulerCm + safeDelta < 0) safeDelta = -initFirstLineRulerCm;
        const targetLeft = Math.max(0, Math.min(currentActiveCm - 0.5, initLeftCm + safeDelta));
        const targetFirst = Math.max(0, Math.min(currentActiveCm - 0.5, initFirstLineRulerCm + safeDelta));
        markerPosPct = (targetLeft / currentActiveCm * 100);
        if (leftMarker) leftMarker.style.left = markerPosPct + '%';
        if (hangingMarker) hangingMarker.style.left = markerPosPct + '%';
        if (firstMarker) firstMarker.style.left = (targetFirst / currentActiveCm * 100) + '%';
        setFullParagraphIndent(targetLeft, initTextIndentCm);
        tipText = `Tüm Paragraf: ${targetLeft.toFixed(2)} cm`;
      } else if (type === 'rightIndent') {
        const rightPct = 1 - pct;
        const rightCm = Math.round((rightPct * currentActiveCm) * 4) / 4;
        const targetRight = Math.max(0, Math.min(currentActiveCm - 1, rightCm));
        if (rightMarker) {
          rightMarker.style.right = (targetRight / currentActiveCm * 100) + '%';
          rightMarker.style.left = 'auto';
        }
        setRightIndent(targetRight);
        tipText = `Sağ Kenar Girintisi: ${targetRight.toFixed(2)} cm`;
        markerPosPct = (1 - (targetRight / currentActiveCm)) * 100;
      }

      if (tooltip && tipText) {
        tooltip.style.display = 'block';
        tooltip.textContent = tipText;
        tooltip.style.left = Math.min(rect.width - 45, Math.max(45, (markerPosPct / 100) * rect.width)) + 'px';
      }
    };

    const upHandler = () => {
      window.removeEventListener('mousemove', moveHandler);
      window.removeEventListener('mouseup', upHandler);
      window.removeEventListener('touchmove', moveHandler);
      window.removeEventListener('touchend', upHandler);
      if (guideLine) guideLine.style.display = 'none';
      if (tooltip) tooltip.style.display = 'none';
      setTimeout(() => { activeDragMarker = null; }, 120);
      updateCounts();
      debouncedPagination();
      if (typeof markDirty === 'function') markDirty();
      if (window.CanHistory) CanHistory.commit();
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
  if (activeDragMarker) return;
  const p = getActiveParagraph();
  if (!p) return;

  const firstMarker = document.getElementById('marker-first-line');
  const hangingMarker = document.getElementById('marker-hanging-indent');
  const leftMarker = document.getElementById('marker-left-indent');
  const rightMarker = document.getElementById('marker-right-indent');
  if (!firstMarker || !leftMarker || !rightMarker) return;

  const isLandscape = currentMargins.orientation === 'landscape';
  const totalPageCm = isLandscape ? 29.7 : 21.0;
  const activeCm = Math.max(5, totalPageCm - (currentMargins.left || 2.5) - (currentMargins.right || 2.5));

  const marginL = parseToCm(p.style.marginLeft);
  const paddingL = parseToCm(p.style.paddingLeft);
  const compL = parseToCm(window.getComputedStyle(p).marginLeft);
  const leftCm = (marginL || paddingL) ? (marginL + paddingL) : compL;
  const textIndentCm = parseToCm(p.style.textIndent || window.getComputedStyle(p).textIndent);
  const rightCm = parseToCm(p.style.marginRight || window.getComputedStyle(p).marginRight);

  // İlk satırın cetvel üzerindeki mutlak konumu = sol/asılı girinti + ilk satır girintisi
  const firstLineRulerCm = Math.max(0, leftCm + textIndentCm);

  firstMarker.style.left = Math.min(100, Math.max(0, (firstLineRulerCm / activeCm) * 100)) + '%';
  if (hangingMarker) {
    hangingMarker.style.left = Math.min(100, Math.max(0, (leftCm / activeCm) * 100)) + '%';
  }
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

function setFirstLineIndent(targetFirstRulerCm, bodyLeftCm) {
  const targets = getSelectedParagraphs();
  targets.forEach(p => {
    const curLeft = (bodyLeftCm !== undefined) ? bodyLeftCm : parseToCm(p.style.marginLeft || window.getComputedStyle(p).marginLeft);
    p.style.textIndent = Math.round((targetFirstRulerCm - curLeft) * 100) / 100 + 'cm';
  });
  updateCounts();
}

function setHangingIndent(targetHangingCm, fixedFirstLineRulerCm) {
  const targets = getSelectedParagraphs();
  targets.forEach(p => {
    let firstLineRuler = fixedFirstLineRulerCm;
    if (firstLineRuler === undefined) {
      const curLeft = parseToCm(p.style.marginLeft || window.getComputedStyle(p).marginLeft);
      const curIndent = parseToCm(p.style.textIndent || window.getComputedStyle(p).textIndent);
      firstLineRuler = curLeft + curIndent;
    }
    p.style.marginLeft = targetHangingCm + 'cm';
    p.style.textIndent = Math.round((firstLineRuler - targetHangingCm) * 100) / 100 + 'cm';
    if (p.style.paddingLeft) p.style.removeProperty('padding-left');
  });
  updateCounts();
}

function setFullParagraphIndent(targetLeftCm, preservedTextIndentCm) {
  const targets = getSelectedParagraphs();
  targets.forEach(p => {
    p.style.marginLeft = targetLeftCm + 'cm';
    if (preservedTextIndentCm !== undefined) {
      p.style.textIndent = preservedTextIndentCm + 'cm';
    }
    if (p.style.paddingLeft) p.style.removeProperty('padding-left');
  });
  updateCounts();
}

function setLeftIndent(cm) {
  setFullParagraphIndent(cm);
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
    targets = Array.from(document.querySelectorAll('.page-body-box p, .page-body-box li, .page-body-box blockquote'));
    if (targets.length === 0 && document.getElementById('editor-content')) {
      targets = Array.from(document.getElementById('editor-content').querySelectorAll('p, li, blockquote'));
    }
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
  if (window.CanHistory) CanHistory.commit();
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

// Tablo Ekleme (Seçim Olmasa da Güvenle Ekler)
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
  const sel = window.getSelection();
  const cp = getActiveParagraph();
  let inserted = false;
  if (sel && sel.rangeCount > 0 && cp && cp.closest && cp.closest('.page-body-box')) {
    inserted = document.execCommand('insertHTML', false, tableHtml);
  }
  if (!inserted) {
    if (cp && cp.parentNode) {
      cp.insertAdjacentHTML('afterend', tableHtml);
    } else {
      const box = document.querySelector('.page-body-box') || document.getElementById('editor-content');
      if (box) box.insertAdjacentHTML('beforeend', tableHtml);
    }
  }
  updateCounts();
  debouncedPagination();
  if (window.CanHistory) CanHistory.commit();
}

// Resim Seçiciyi Tetikleme (Android + Masaüstü + Web Uyumlu)
function triggerImagePicker() {
  if (window.AndroidBridge && window.AndroidBridge.pickImage) {
    window.AndroidBridge.pickImage();
  } else {
    // Masaüstü ve Web: standart dosya seçici ile doğrudan resim yükleme
    let picker = document.getElementById('desktopImagePickerInput');
    if (!picker) {
      picker = document.createElement('input');
      picker.id = 'desktopImagePickerInput';
      picker.type = 'file';
      picker.accept = 'image/png,image/jpeg,image/jpg,image/webp,image/bmp';
      picker.style.display = 'none';
      document.body.appendChild(picker);
      picker.addEventListener('change', function(e) {
        const file = e.target.files && e.target.files[0];
        if (file) {
          const reader = new FileReader();
          reader.onload = function(evt) {
            insertImageBase64(evt.target.result);
          };
          reader.readAsDataURL(file);
        }
        picker.value = '';
      });
    }
    picker.click();
  }
}

function insertImageBase64(base64Data) {
  const imgHtml = `<p style="text-align: center;"><img src="${base64Data}" alt="Dilekçe Eki / Belge Delili" style="max-width: 95%; max-height: 400px; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);"><br><em style="font-size: 10pt; color: #666;">(Ek / Delil Görseli)</em></p><p style="text-align: justify;"><br></p>`;
  const sel = window.getSelection();
  const cp = getActiveParagraph();
  let inserted = false;
  if (sel && sel.rangeCount > 0 && cp && cp.closest && cp.closest('.page-body-box')) {
    inserted = document.execCommand('insertHTML', false, imgHtml);
  }
  if (!inserted) {
    if (cp && cp.parentNode) {
      cp.insertAdjacentHTML('afterend', imgHtml);
    } else {
      const box = document.querySelector('.page-body-box') || document.getElementById('editor-content');
      if (box) box.insertAdjacentHTML('beforeend', imgHtml);
    }
  }
  updateCounts();
  debouncedPagination();
  if (window.CanHistory) CanHistory.commit();
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
  const el = document.getElementById(id);
  if (el) {
    el.classList.add('open');
    el.style.display = 'flex';
  }
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) {
    el.classList.remove('open');
    el.style.display = 'none';
  }
  if (id === 'modal-paragraph-settings') {
    setTimeout(restoreCurrentSelection, 50);
  }
  if (id === 'modal-smartcard-sign' && smartCardPollInterval) {
    clearInterval(smartCardPollInterval);
    smartCardPollInterval = null;
  }
}

function toggleToolbarExpand() {
  const tb = document.getElementById('toolbar-container');
  const icon = document.getElementById('chevron-icon');
  if (!tb) return;
  tb.classList.toggle('toolbar-expanded');
  const isExp = tb.classList.contains('toolbar-expanded');
  if (icon) {
    icon.textContent = isExp ? '▴' : '▾';
  }
}
window.toggleToolbarExpand = toggleToolbarExpand;

function openMobileMenuModal() {
  openModal('modal-mobile-menu');
}
window.openMobileMenuModal = openMobileMenuModal;

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
    if (window.CanHistory) CanHistory.commit();
    const container = document.getElementById('pages-container') || document.getElementById('sheet-container');
    if (container) {
      container.innerHTML = `
        <div class="a4-sheet-page" data-page-number="1" id="page-1">
          <div id="official-doc-seal" class="official-doc-seal" onclick="openSignatureModal()" title="Elektronik İmza Doğrulama ve Detayları" style="display: none;">
            <div class="seal-medal">⚖️</div>
            <div class="seal-ribbon"></div>
          </div>
          <div id="doc-header" class="page-header-box" contenteditable="true" spellcheck="false" data-placeholder="Üstbilgi...">T.C. İSTANBUL ANADOLU 1. ASLİYE HUKUK MAHKEMESİ — Dosya No: 2026/.... Esas</div>
          <div id="editor-content" class="page-body-box" contenteditable="true" spellcheck="true" autocomplete="off" autocapitalize="sentences">${tpl}</div>
          <div id="doc-footer" class="page-footer-box" contenteditable="false">${getDocFooterHtml(1, 1)}</div>
        </div>
      `;
    } else {
      const ed = document.getElementById('editor-content');
      if (ed) ed.innerHTML = tpl;
    }
    updateCounts();
    updateRulerFromActiveParagraph();
    updatePagination();
    if (window.CanHistory) CanHistory.commit();
    if (typeof markDirty === 'function') markDirty();
    showEditorToast('⚖️ Dilekçe şablonu yüklendi');
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

// Belge Bilgileri ve İstatistikleri Modal (Tüm Sayfalar Uyumlu)
function openDocStatsModal() {
  const text = (typeof getPlainText === 'function') ? getPlainText() : ((document.querySelector('.page-body-box') || {}).innerText || '');
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  const charsWithSpaces = text.length;
  const charsNoSpaces = text.replace(/\s/g, '').length;
  const paragraphs = document.querySelectorAll('.page-body-box p, .page-body-box table, .page-body-box li').length || 1;
  const pagesCount = document.querySelectorAll('.a4-sheet-page').length || 1;

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
  if (statPages) statPages.textContent = pagesCount + ' Sayfa';
  if (statPageSize) statPageSize.textContent = (currentMargins.orientation === 'landscape' ? 'A4 Yatay (297 × 210 mm)' : 'A4 Dikey (210 × 297 mm)');
  if (statMargins) statMargins.textContent = `Sol: ${currentMargins.left}cm, Sağ: ${currentMargins.right}cm, Üst: ${currentMargins.top}cm, Alt: ${currentMargins.bottom}cm`;

  openModal('modal-doc-stats');
}

// --- BUL VE DEĞİŞTİR (FIND & REPLACE) MOTORU ---
var findMatches = [];
var activeFindIndex = -1;
window.findMatches = findMatches;

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
  const bodyBoxes = Array.from(document.querySelectorAll('.page-body-box'));
  if (bodyBoxes.length === 0) {
    const editor = document.getElementById('editor-content');
    if (editor) bodyBoxes.push(editor);
  }
  bodyBoxes.forEach(box => {
    const highlights = box.querySelectorAll('.find-highlight');
    highlights.forEach(h => {
      const parent = h.parentNode;
      if (parent) {
        parent.replaceChild(document.createTextNode(h.textContent), h);
        parent.normalize();
      }
    });
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

  const bodyBoxes = Array.from(document.querySelectorAll('.page-body-box'));
  if (bodyBoxes.length === 0) {
    const editor = document.getElementById('editor-content');
    if (editor) bodyBoxes.push(editor);
  }
  bodyBoxes.forEach(box => {
    highlightTextNodes(box, query, matchCase);
  });

  findMatches = Array.from(document.querySelectorAll('.page-body-box .find-highlight, #editor-content .find-highlight'));
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
    updateCounts();
    debouncedPagination();
    if (window.CanHistory) CanHistory.commit();
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
  updateCounts();
  debouncedPagination();
  if (window.CanHistory) CanHistory.commit();
  showEditorToast(`✓ Toplam ${count} adet eşleşme başarıyla değiştirildi.`);
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

// Kelime ve Karakter Sayımı (Tüm Sayfalar)
function updateCounts() {
  const bodyBoxes = Array.from(document.querySelectorAll('.page-body-box'));
  let text = '';
  if (bodyBoxes.length > 0) {
    text = bodyBoxes.map(b => b.innerText || '').join('\n');
  } else {
    text = (document.getElementById('editor-content') || {}).innerText || '';
  }
  const trimmed = text.trim();
  const wordCount = trimmed ? trimmed.split(/\s+/).length : 0;
  const charCount = text.length;

  const wEl = document.getElementById("desktopWordCount");
  if (wEl) {
    wEl.innerText = `${wordCount} kelime, ${charCount} karakter`;
  }

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
  const bodyBoxes = Array.from(document.querySelectorAll('.page-body-box'));
  if (bodyBoxes.length === 0) {
    const editor = document.getElementById('editor-content');
    if (editor) bodyBoxes.push(editor);
  }
  const paragraphs = [];
  bodyBoxes.forEach(box => {
    paragraphs.push(...Array.from(box.querySelectorAll('p, blockquote, div:not(.page-break):not(.auto-page-break):not(.udf-footer-layout)')));
  });
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
  if (window.CanHistory) CanHistory.commit();
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
window.__userHasEditedDocument = false;
window.__origDocSnapshot = null;

function markDocumentUserEdited() {
  window.__userHasEditedDocument = true;
  lastUserTypingTimestamp = Date.now();
  if (window.AndroidBridge && window.AndroidBridge.setDocModified) {
    try { window.AndroidBridge.setDocModified(true); } catch (e) {}
  }
}

function snapshotDocument() {
  try {
    const d = getStructuredDocument();
    return JSON.stringify({ h: d.header, f: d.footer, p: d.paragraphs });
  } catch (e) {
    return null;
  }
}

function markDocumentPristine() {
  window.__userHasEditedDocument = false;
  window.__origDocSnapshot = snapshotDocument();
  if (window.AndroidBridge && window.AndroidBridge.setDocModified) {
    try { window.AndroidBridge.setDocModified(false); } catch (e) {}
  }
  try { localStorage.removeItem(AUTOSAVE_STORAGE_KEY); } catch (x) {}
}

function isDocumentModified() {
  if (!window.__userHasEditedDocument) return false;
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

  const container = document.getElementById('pages-container') || document.getElementById('sheet-container');
  let targetHtml = '';
  let headerHtmlToSet = '';
  let footerHtmlToSet = '';
  let headerStartPageToSet = 1;

  // JSON Yapılandırılmış Belge veya Düz HTML Kontrolü
  const trimmed = content.trim();
  if (trimmed.startsWith('{')) {
    try {
      const data = JSON.parse(trimmed);
      if (data && typeof data === 'object') {
        if (data.headerHtml) {
          currentDocHeaderTemplate = data.headerHtml;
          headerHtmlToSet = data.headerHtml;
          currentDocHeaderStartPage = parseInt(data.headerStartPage || '1', 10);
          headerStartPageToSet = currentDocHeaderStartPage;
        } else if (data.header !== undefined) {
          currentDocHeaderTemplate = (data.header && data.header.trim()) ? `<div class="udf-header-bar" style="text-align:center;">${escapeHtml(data.header)}</div>` : '';
          currentDocHeaderStartPage = 1;
          headerHtmlToSet = currentDocHeaderTemplate;
          headerStartPageToSet = 1;
        } else {
          currentDocHeaderTemplate = '';
        }

        if (data.footerHtml) {
          currentDocFooterTemplate = data.footerHtml;
          footerHtmlToSet = data.footerHtml;
        } else if (data.footer !== undefined) {
          currentDocFooterTemplate = (data.footer && data.footer.trim()) ? `<div class="udf-footer-layout"><span class="udf-footer-text">${escapeHtml(data.footer)}</span></div>` : '';
          footerHtmlToSet = currentDocFooterTemplate;
        } else {
          currentDocFooterTemplate = '';
        }

        window.currentDocFooterPageSpec = data.footerPageSpec || '';
        window.currentDocFooterForeStr = data.footerForeStr || 'Sayfa:';
        window.currentDocFooterSep = data.footerSep || '/';
        window.currentDocFooterPageStart = data.footerPageStart || '1';
        currentDocVerificationCode = data.verificationCode || '';
        window.currentDocSicil = data.sicil || '';

        if (data.leftMarginCm !== undefined) {
          applyPageSetup(data.leftMarginCm, data.rightMarginCm, data.topMarginCm, data.bottomMarginCm,
            data.paperOrientation === '2' || data.paperOrientation === 'landscape' ? 'landscape' : 'portrait',
            data.headerMarginCm, data.footerMarginCm);
        }

        targetHtml = data.html || '';
      }
    } catch (e) {
      targetHtml = content;
    }
  } else {
    targetHtml = content;
  }

  // Konteyneri tek ve tertemiz bir başlangıç sayfasına sıfırla (eski sayfa kalıntılarını temizle)
  if (container) {
    const showHdr = !!(headerHtmlToSet && headerStartPageToSet <= 1);
    container.innerHTML = `
      <div class="a4-sheet-page" data-page-number="1" id="page-1">
        <div id="official-doc-seal" class="official-doc-seal" onclick="openSignatureModal()" title="Elektronik İmza Doğrulama ve Detayları" style="display: none;">
          <div class="seal-medal">⚖️</div>
          <div class="seal-ribbon"></div>
        </div>
        <div id="doc-header" class="page-header-box" contenteditable="true" spellcheck="false" style="display:${showHdr ? 'flex' : 'none'};">${showHdr ? headerHtmlToSet : ''}</div>
        <div id="editor-content" class="page-body-box" contenteditable="true" spellcheck="true" autocomplete="off" autocapitalize="sentences">${targetHtml}</div>
        <div id="doc-footer" class="page-footer-box" contenteditable="false">${footerHtmlToSet ? getDocFooterHtml(1, 1) : ''}</div>
      </div>
    `;
  }

  updateCounts();
  setTimeout(() => {
    if (isMobileView) {
      applyAutoFitZoom();
    } else {
      const fit = calculateFitScale();
      setZoom(fit >= 0.9 ? 1.0 : fit, true);
    }
    if (typeof realignAllTabs === 'function') realignAllTabs();
    updateRulerFromActiveParagraph();
    updatePagination();
  }, 100);
  setTimeout(markDocumentPristine, 350);
}

function getHtmlContent() {
  const bodyBoxes = Array.from(document.querySelectorAll('.page-body-box'));
  if (bodyBoxes.length > 0) {
    return bodyBoxes.map(b => b.innerHTML).join('');
  }
  const ed = document.getElementById('editor-content');
  return ed ? ed.innerHTML : '';
}

function getPlainText() {
  const parts = [];
  
  // 1. Üstbilgi
  const headerEl = document.getElementById('doc-header');
  if (headerEl) {
    const hText = (headerEl.innerText || '').trim();
    if (hText) parts.push(hText + '\n');
  }

  // 2. Ana İçerik (Tüm Sayfalar)
  const bodyBoxes = Array.from(document.querySelectorAll('.page-body-box'));
  const blocks = [];
  if (bodyBoxes.length > 0) {
    bodyBoxes.forEach(box => {
      blocks.push(...Array.from(box.children));
    });
  } else {
    const editor = document.getElementById('editor-content');
    if (editor) blocks.push(...Array.from(editor.children));
  }
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

// Belgeyi Java/Web UDF & DOCX Üreticileri için Üstbilgi, Altbilgi, Tablo, Görsel ve Paragraflar Olarak Çıkar
function extractParagraphNode(node) {
  let align = 3;
  const textAlign = node.style ? node.style.textAlign : '';
  if (textAlign === 'center') align = 1;
  else if (textAlign === 'right') align = 2;
  else if (textAlign === 'left') align = 0;
  else align = 3;

  const runs = [];
  const skipListPrefix = !!(node.dataset && (node.dataset.udfNumbered === 'true' || node.dataset.udfBulleted === 'true'));
  parseInlineRuns(node, runs, {
    bold: false,
    italic: false,
    underline: false,
    subscript: false,
    superscript: false,
    strikethrough: false,
    fontFamily: '',
    fontSize: 0,
    color: '',
    backgroundColor: '',
    skipListPrefix: skipListPrefix
  });

  // Paragrafın en sonundaki tekil boş <br> kaynaklı '\n' karakterini temizle
  if (runs.length === 1 && runs[0].type !== 'image' && runs[0].text === '\n') {
    runs.length = 0;
  }

  const pText = runs.map(r => r.type === 'image' ? '\u00b8' : (r.text || '')).join('');
  const rawMt = (node.getAttribute && node.getAttribute('data-orig-mt')) || (node.style && node.style.marginTop) || '';
  const rawMb = (node.getAttribute && node.getAttribute('data-orig-mb')) || (node.style && node.style.marginBottom) || '';
  const spaceAbove = rawMt ? (parseFloat(rawMt) || 0.0) : 0.0;
  const spaceBelow = rawMb ? (parseFloat(rawMb) || 0.0) : 0.0;
  let lineSpacing = 0.0;
  if (node.dataset && node.dataset.udfLinespacing !== undefined && node.dataset.udfLinespacing !== '') {
    lineSpacing = parseFloat(node.dataset.udfLinespacing) || 0.0;
  } else if (node.style && node.style.lineHeight) {
    const lh = parseFloat(node.style.lineHeight) || 0.0;
    if (lh > 1.2) lineSpacing = Math.max(0, Math.round((lh - 1.15) * 100) / 100);
  }
  const firstLineIndent = parseToCm(node.style ? node.style.textIndent : '');
  const leftIndent = parseToCm(node.style ? (node.style.marginLeft || node.style.paddingLeft) : '');
  const rightIndent = parseToCm(node.style ? node.style.marginRight : '');

  const pObj = {
    type: 'paragraph',
    text: pText,
    align: align,
    spaceAbove: spaceAbove,
    spaceBelow: spaceBelow,
    lineSpacing: lineSpacing,
    firstLineIndent: firstLineIndent,
    leftIndent: leftIndent,
    rightIndent: rightIndent,
    tabStops: (node.dataset && node.dataset.tabStops) ? node.dataset.tabStops : '',
    udfTabSet: (node.dataset && node.dataset.udfTabset) ? node.dataset.udfTabset : '',
    runs: runs
  };
  if (node.dataset && node.dataset.udfNumbered === 'true') {
    pObj.numbered = true;
    if (node.dataset.udfNumberType) pObj.numberType = node.dataset.udfNumberType;
    if (node.dataset.udfListId) pObj.listId = node.dataset.udfListId;
    if (node.dataset.udfListLevel) pObj.listLevel = node.dataset.udfListLevel;
  } else if (node.dataset && node.dataset.udfBulleted === 'true') {
    pObj.bulleted = true;
  }
  return pObj;
}

function extractTableNode(tableNode) {
  let border = (tableNode.dataset && tableNode.dataset.udfBorder) ? tableNode.dataset.udfBorder : '';
  if (!border) {
    const bStyle = tableNode.style ? tableNode.style.border : '';
    border = (bStyle && bStyle.includes('none')) ? 'borderNone' : 'borderCell';
  }
  const colSpans = (tableNode.dataset && tableNode.dataset.udfColSpans) ? tableNode.dataset.udfColSpans : '';
  const rows = [];

  const trElements = [];
  for (let child of tableNode.children) {
    const t = child.tagName ? child.tagName.toLowerCase() : '';
    if (t === 'tr') {
      trElements.push(child);
    } else if (t === 'tbody' || t === 'thead' || t === 'tfoot') {
      for (let sub of child.children) {
        if (sub.tagName && sub.tagName.toLowerCase() === 'tr') trElements.push(sub);
      }
    }
  }

  for (let tr of trElements) {
    const cells = [];
    for (let td of tr.children) {
      const cTag = td.tagName ? td.tagName.toLowerCase() : '';
      if (cTag !== 'td' && cTag !== 'th') continue;
      const cellParagraphs = [];
      let hasBlockChildren = false;
      for (let cc of td.children) {
        const ccTag = cc.tagName ? cc.tagName.toLowerCase() : '';
        if (ccTag === 'p' || ccTag === 'div') {
          cellParagraphs.push(extractParagraphNode(cc));
          hasBlockChildren = true;
        } else if (ccTag === 'table') {
          cellParagraphs.push(extractTableNode(cc));
          hasBlockChildren = true;
        }
      }
      if (!hasBlockChildren) {
        cellParagraphs.push(extractParagraphNode(td));
      }
      cells.push({
        colSpan: parseInt(td.getAttribute('colspan') || '1', 10) || 1,
        rowSpan: parseInt(td.getAttribute('rowspan') || '1', 10) || 1,
        paragraphs: cellParagraphs
      });
    }
    if (cells.length > 0) {
      rows.push({ cells: cells });
    }
  }

  return {
    type: 'table',
    border: border,
    colSpans: colSpans,
    rows: rows
  };
}

function extractHeaderFooterBlocks(htmlStr) {
  if (!htmlStr || !htmlStr.trim()) return [];
  const temp = document.createElement('div');
  temp.innerHTML = htmlStr;
  if (temp.querySelector('.udf-official-footer')) return [];
  const blocks = [];
  for (let child of temp.children) {
    const tag = child.tagName ? child.tagName.toLowerCase() : '';
    if (child.classList && (child.classList.contains('udf-header-layout') || child.classList.contains('udf-footer-layout'))) {
      const img = child.querySelector('img');
      if (img && img.src && img.src.includes('base64,')) {
        const b64 = img.src.split('base64,')[1].trim();
        const wPt = parseFloat(img.dataset.udfWidth) || 118.0;
        const hPt = parseFloat(img.dataset.udfHeight) || 50.0;
        blocks.push({ type: 'image', imageData: b64, widthPt: wPt, heightPt: hPt });
      }
    } else if (tag === 'p') {
      blocks.push(extractParagraphNode(child));
    } else if (tag === 'table') {
      blocks.push(extractTableNode(child));
    } else if (child.classList && child.classList.contains('udf-header-bar')) {
      const txt = (child.innerText || '').trim();
      if (txt) {
        blocks.push({
          type: 'paragraph',
          text: txt,
          align: 1,
          spaceAbove: 0,
          spaceBelow: 0,
          lineSpacing: 0,
          firstLineIndent: 0,
          leftIndent: 0,
          rightIndent: 0,
          runs: [{ text: txt, bold: true, italic: false, underline: false }]
        });
      }
    }
  }
  return blocks;
}

function getStructuredDocument() {
  const container = document.getElementById('pages-container') || document.getElementById('sheet-container') || document.getElementById('editor-content') || document.body;
  const paragraphs = [];
  const bodyBoxes = Array.from(document.querySelectorAll('.page-body-box'));
  let nodes = [];
  if (bodyBoxes.length > 0) {
    bodyBoxes.forEach(bb => {
      Array.from(bb.children).forEach(c => nodes.push(c));
    });
  } else {
    if (container) nodes = Array.from(container.children);
  }

  if (!nodes || nodes.length === 0) {
    const p1 = document.querySelector('.page-body-box') || document.getElementById('editor-content');
    const rawTxt = (p1 ? p1.innerText : '').replace(/\u200B/g, '');
    paragraphs.push({
      type: 'paragraph',
      text: rawTxt,
      align: 3,
      spaceAbove: 0.0,
      spaceBelow: 0.0,
      lineSpacing: 0.0,
      firstLineIndent: 0.0,
      leftIndent: 0.0,
      rightIndent: 0.0,
      runs: rawTxt ? [{ text: rawTxt, bold: false, italic: false, underline: false }] : []
    });
  } else {
    for (let node of nodes) {
      if (node.classList && (node.classList.contains('auto-page-break') || node.classList.contains('page-break-desk-gap') || node.classList.contains('page-desk-gap') || node.classList.contains('page-break-header-area') || node.classList.contains('page-break-footer-area'))) {
        continue;
      }
      if (node.classList && node.classList.contains('udf-page-break')) {
        paragraphs.push({ type: 'pageBreak' });
        continue;
      }
      const tag = node.tagName ? node.tagName.toLowerCase() : '';
      if (tag === 'table') {
        paragraphs.push(extractTableNode(node));
        continue;
      }
      if (tag === 'ol' || tag === 'ul') {
        const isOrdered = tag === 'ol';
        const items = node.querySelectorAll('li');
        items.forEach(li => {
          const pObj = extractParagraphNode(li);
          if (isOrdered) pObj.numbered = true;
          else pObj.bulleted = true;
          paragraphs.push(pObj);
        });
        continue;
      }

      if (node.classList && (node.classList.contains('official-signature-seal') || node.classList.contains('seal-wrapper-block') || node.querySelector('.official-signature-seal'))) {
        const sealText = (node.innerText || '').replace(/\u200B/g, '').trim();
        if (sealText) {
          paragraphs.push({
            type: 'paragraph',
            text: sealText,
            align: 2,
            spaceAbove: 8.0,
            spaceBelow: 4.0,
            lineSpacing: 0.0,
            firstLineIndent: 0.0,
            leftIndent: 0.0,
            rightIndent: 0.0,
            runs: [{ text: sealText, bold: true, italic: false, underline: false }]
          });
        }
        continue;
      }

      paragraphs.push(extractParagraphNode(node));
    }
  }

  const headerEl = document.getElementById('doc-header');
  const footerEl = document.getElementById('doc-footer');
  const hasSeal = container.querySelectorAll('.official-signature-seal').length > 0;
  const headerSourceHtml = currentDocHeaderTemplate || (headerEl ? headerEl.innerHTML : '');
  const footerSourceHtml = currentDocFooterTemplate || (footerEl ? footerEl.innerHTML : '');
  const headerParagraphs = extractHeaderFooterBlocks(headerSourceHtml);
  const footerParagraphs = extractHeaderFooterBlocks(footerSourceHtml);

  let footerCleanText = '';
  if (footerEl && !footerEl.querySelector('.udf-official-footer') && !footerEl.querySelector('.udf-footer-page-label')) {
    footerCleanText = (footerEl.innerText || '').replace(/\u200B/g, '').trim();
  }

  const docPayload = {
    header: headerEl ? (headerEl.innerText || '').replace(/\u200B/g, '').trim() : '',
    headerStartPage: currentDocHeaderStartPage || 1,
    headerParagraphs: headerParagraphs,
    footer: footerCleanText,
    footerPageSpec: window.currentDocFooterPageSpec || '',
    footerForeStr: window.currentDocFooterForeStr || 'Sayfa:',
    footerSep: window.currentDocFooterSep || '/',
    footerPageStart: window.currentDocFooterPageStart || '1',
    footerParagraphs: footerParagraphs,
    isSigned: hasSeal,
    margins: currentMargins,
    leftMarginCm: currentMargins.left,
    rightMarginCm: currentMargins.right,
    topMarginCm: currentMargins.top,
    bottomMarginCm: currentMargins.bottom,
    headerMarginCm: currentMargins.header || 0.7,
    footerMarginCm: currentMargins.footer || 0.7,
    paperOrientation: currentMargins.orientation === 'landscape' ? '2' : '1',
    paragraphs: paragraphs
  };

  return docPayload;
}

function parseInlineRuns(element, runs, state) {
  const st = state || {};
  for (let child of element.childNodes) {
    if (child.nodeType === Node.TEXT_NODE) {
      const cleanText = (child.textContent || '').replace(/\u200B/g, '');
      if (cleanText) {
        const runObj = {
          text: cleanText,
          bold: !!st.bold,
          italic: !!st.italic,
          underline: !!st.underline,
          subscript: !!st.subscript,
          superscript: !!st.superscript,
          strikethrough: !!st.strikethrough
        };
        if (st.fontFamily) runObj.fontFamily = st.fontFamily;
        if (st.fontSize > 0) runObj.fontSize = st.fontSize;
        if (st.color) runObj.color = st.color;
        if (st.backgroundColor) runObj.backgroundColor = st.backgroundColor;
        runs.push(runObj);
      }
    } else if (child.nodeType === Node.ELEMENT_NODE) {
      if (child.classList && (child.classList.contains('auto-page-break') || child.classList.contains('page-break'))) {
        continue;
      }
      if (st.skipListPrefix && child.classList && child.classList.contains('udf-list-prefix')) {
        continue;
      }
      if (child.classList && child.classList.contains('udf-tab-label')) {
        const isBold = child.querySelector('strong, b') !== null || !!st.bold;
        const txt = (child.textContent || '').replace(/\u200B/g, '').trim();
        runs.push({
          text: txt + '\t',
          bold: isBold,
          italic: !!st.italic,
          underline: !!st.underline,
          subscript: !!st.subscript,
          superscript: !!st.superscript,
          strikethrough: !!st.strikethrough
        });
        continue;
      }
      if (child.classList && child.classList.contains('udf-colon')) {
        runs.push({
          text: ':',
          bold: !!st.bold,
          italic: !!st.italic,
          underline: !!st.underline,
          subscript: !!st.subscript,
          superscript: !!st.superscript,
          strikethrough: !!st.strikethrough
        });
        continue;
      }
      if (child.classList && child.classList.contains('udf-tab-space')) {
        runs.push({
          text: '\t',
          bold: !!st.bold,
          italic: !!st.italic,
          underline: !!st.underline,
          subscript: !!st.subscript,
          superscript: !!st.superscript,
          strikethrough: !!st.strikethrough
        });
        continue;
      }
      const tag = child.tagName ? child.tagName.toLowerCase() : '';
      if (tag === 'br') {
        runs.push({
          text: '\n',
          bold: !!st.bold,
          italic: !!st.italic,
          underline: !!st.underline,
          subscript: !!st.subscript,
          superscript: !!st.superscript,
          strikethrough: !!st.strikethrough
        });
        continue;
      }
      if (tag === 'img') {
        const src = child.getAttribute('src') || '';
        if (src.includes('base64,')) {
          const b64 = src.split('base64,')[1].trim();
          let wPt = parseFloat(child.dataset ? child.dataset.udfWidth : '') || 0;
          let hPt = parseFloat(child.dataset ? child.dataset.udfHeight : '') || 0;
          if (!wPt && child.style && child.style.width) {
            wPt = parseToCm(child.style.width) * 28.3465;
          }
          if (!hPt && child.style && child.style.height) {
            hPt = parseToCm(child.style.height) * 28.3465;
          }
          if (!wPt) wPt = (child.width || 120) * 0.75;
          if (!hPt) hPt = (child.height || 60) * 0.75;
          runs.push({
            type: 'image',
            imageData: b64,
            widthPt: wPt,
            heightPt: hPt
          });
        }
        continue;
      }

      const fw = child.style ? child.style.fontWeight : '';
      const isB = st.bold || tag === 'b' || tag === 'strong' || fw === 'bold' || parseInt(fw, 10) >= 600;
      const isI = st.italic || tag === 'i' || tag === 'em' || (child.style && child.style.fontStyle === 'italic');
      const td = child.style ? (child.style.textDecoration || child.style.textDecorationLine || '') : '';
      const isU = st.underline || tag === 'u' || td.includes('underline');
      const isSub = st.subscript || tag === 'sub';
      const isSup = st.superscript || tag === 'sup';
      const isStrike = st.strikethrough || tag === 's' || tag === 'strike' || tag === 'del' || td.includes('line-through');

      let fontFamily = st.fontFamily || '';
      if (child.style && child.style.fontFamily) fontFamily = child.style.fontFamily;
      else if (tag === 'font' && child.getAttribute('face')) fontFamily = child.getAttribute('face');

      let fontSize = st.fontSize || 0;
      if (child.style && child.style.fontSize) {
        const fsStr = child.style.fontSize.trim();
        if (fsStr.endsWith('pt')) fontSize = parseFloat(fsStr) || 0;
        else if (fsStr.endsWith('px')) fontSize = Math.round(((parseFloat(fsStr) || 16) * 0.75) * 10) / 10;
      }

      let color = st.color || '';
      if (child.style && child.style.color) color = child.style.color;
      else if (tag === 'font' && child.getAttribute('color')) color = child.getAttribute('color');

      let bgColor = st.backgroundColor || '';
      if (child.style && child.style.backgroundColor) bgColor = child.style.backgroundColor;

      parseInlineRuns(child, runs, {
        bold: isB,
        italic: isI,
        underline: isU,
        subscript: isSub,
        superscript: isSup,
        strikethrough: isStrike,
        fontFamily: fontFamily,
        fontSize: fontSize,
        color: color,
        backgroundColor: bgColor,
        skipListPrefix: st.skipListPrefix
      });
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
  const container = document.getElementById('pages-container') || document.getElementById('sheet-container') || document.body;
  if (!container) return;

  // Biçim alınacak kaynak öğeyi ve metin düğümünü belirle
  let sourceEl = null;
  let isBold = false;
  let isItalic = false;
  let isUnderline = false;
  let isStrike = false;

  if (sel && sel.rangeCount > 0) {
    const range = sel.getRangeAt(0);
    let n = range.startContainer;
    sourceEl = (n.nodeType === Node.TEXT_NODE) ? n.parentElement : n;
  }
  if (!sourceEl || !container.contains(sourceEl)) {
    sourceEl = lastActiveParagraph || document.querySelector('.page-body-box p') || document.querySelector('.page-body-box');
  }
  if (!sourceEl) {
    showEditorToast('Önce biçimi kopyalanacak metne dokunun');
    return;
  }

  // Tarayıcının queryCommandState API'si ile inline biçimleri sorgula
  try {
    isBold = document.queryCommandState('bold');
    isItalic = document.queryCommandState('italic');
    isUnderline = document.queryCommandState('underline');
    isStrike = document.queryCommandState('strikeThrough');
  } catch (e) {}

  const cs = window.getComputedStyle(sourceEl);
  if (!isBold && (cs.fontWeight === 'bold' || parseInt(cs.fontWeight, 10) >= 600 || sourceEl.closest('strong, b'))) {
    isBold = true;
  }
  if (!isItalic && (cs.fontStyle === 'italic' || sourceEl.closest('em, i'))) {
    isItalic = true;
  }
  if (!isUnderline && ((cs.textDecorationLine || cs.textDecoration || '').includes('underline') || sourceEl.closest('u'))) {
    isUnderline = true;
  }
  if (!isStrike && ((cs.textDecorationLine || cs.textDecoration || '').includes('line-through') || sourceEl.closest('s, strike'))) {
    isStrike = true;
  }

  let ptSize = 12;
  const fsRaw = cs.fontSize || '16px';
  if (fsRaw.endsWith('pt')) {
    ptSize = parseFloat(fsRaw) || 12;
  } else if (fsRaw.endsWith('px')) {
    ptSize = Math.round(parseFloat(fsRaw) * 0.75) || 12;
  }

  let pEl = sourceEl;
  while (pEl && pEl !== container && pEl !== document.body) {
    if (pEl.tagName && (pEl.tagName === 'P' || pEl.tagName === 'LI' || pEl.tagName === 'DIV' || pEl.tagName === 'BLOCKQUOTE')) break;
    pEl = pEl.parentElement;
  }
  const pCs = (pEl && pEl !== container && pEl !== document.body) ? window.getComputedStyle(pEl) : cs;

  copiedFormat = {
    fontFamily: cs.fontFamily,
    fontSizePt: ptSize,
    fontSize: ptSize + 'pt',
    isBold: isBold,
    isItalic: isItalic,
    isUnderline: isUnderline,
    isStrike: isStrike,
    color: cs.color,
    backgroundColor: (cs.backgroundColor !== 'rgba(0, 0, 0, 0)' && cs.backgroundColor !== 'transparent') ? cs.backgroundColor : '',
    textAlign: pCs.textAlign,
    lineHeight: pCs.lineHeight,
    marginTop: pCs.marginTop,
    marginBottom: pCs.marginBottom,
    textIndent: pCs.textIndent
  };

  window.isFormatPainterActive = isFormatPainterActive = true;
  isFormatPainterPersistent = persistent;
  document.body.classList.add('format-painter-active');
  const btn = document.getElementById('btn-format-painter');
  if (btn) btn.classList.add('active');

  showEditorToast('🖌️ Biçim kopyalandı! Hedef metni seçin veya tıklayın');
}

function deactivateFormatPainter() {
  window.isFormatPainterActive = isFormatPainterActive = false;
  isFormatPainterPersistent = false;
  document.body.classList.remove('format-painter-active');
  const btn = document.getElementById('btn-format-painter');
  if (btn) btn.classList.remove('active');
}

function applyCopiedFormatToTarget() {
  if (!isFormatPainterActive || !copiedFormat) return;

  const sel = window.getSelection();
  const container = document.getElementById('pages-container') || document.getElementById('sheet-container') || document.body;
  if (!sel || sel.rangeCount === 0 || !container) return;

  const range = sel.getRangeAt(0);
  if (!container.contains(range.commonAncestorContainer)) return;

  const targetNode = (range.startContainer.nodeType === Node.TEXT_NODE) ? range.startContainer.parentElement : range.startContainer;
  const bodyBox = (targetNode && targetNode.closest) ? (targetNode.closest('.page-body-box') || document.getElementById('editor-content')) : document.getElementById('editor-content');
  if (bodyBox && document.activeElement !== bodyBox) {
    bodyBox.focus();
    try {
      sel.removeAllRanges();
      sel.addRange(range);
    } catch (e) {}
  }

  if (sel.isCollapsed && sel.modify) {
    sel.modify('move', 'backward', 'word');
    sel.modify('extend', 'forward', 'word');
  }

  const targetCs = window.getComputedStyle(targetNode);

  let targetPt = 12;
  const targetFsRaw = targetCs.fontSize || '16px';
  if (targetFsRaw.endsWith('pt')) targetPt = parseFloat(targetFsRaw) || 12;
  else if (targetFsRaw.endsWith('px')) targetPt = Math.round(parseFloat(targetFsRaw) * 0.75) || 12;

  // 1. Yazı Tipi (Font Family) - Sadece farklıysa uygula
  if (copiedFormat.fontFamily && targetCs.fontFamily !== copiedFormat.fontFamily) {
    document.execCommand('fontName', false, copiedFormat.fontFamily);
  }

  // 2. Yazı Boyutu (Font Size pt) - Sadece farklıysa uygula
  if (copiedFormat.fontSizePt && Math.abs(targetPt - copiedFormat.fontSizePt) >= 0.5) {
    document.execCommand('fontSize', false, '7');
    const fontElements = document.getElementsByTagName('font');
    for (let el of fontElements) {
      if (el.size === '7') {
        el.removeAttribute('size');
        el.style.fontSize = copiedFormat.fontSizePt + 'pt';
      }
    }
  }

  // 3. Yazı Rengi ve Vurgu - Sadece farklıysa uygula
  if (copiedFormat.color && targetCs.color !== copiedFormat.color) {
    document.execCommand('foreColor', false, copiedFormat.color);
  }
  if (copiedFormat.backgroundColor && targetCs.backgroundColor !== copiedFormat.backgroundColor) {
    document.execCommand('hiliteColor', false, copiedFormat.backgroundColor);
  }

  // 4. Kalınlık (Bold): Hedef ile kopyalanan durumu birebir eşitle
  const targetIsBold = document.queryCommandState('bold') || (targetCs.fontWeight === 'bold' || parseInt(targetCs.fontWeight, 10) >= 600 || (targetNode.closest && targetNode.closest('strong, b') !== null));
  if (copiedFormat.isBold && !targetIsBold) {
    document.execCommand('bold', false, null);
  } else if (!copiedFormat.isBold && targetIsBold) {
    document.execCommand('bold', false, null);
  }

  // 5. İtalik: Hedef ile kopyalanan durumu birebir eşitle
  const targetIsItalic = document.queryCommandState('italic') || (targetCs.fontStyle === 'italic' || (targetNode.closest && targetNode.closest('em, i') !== null));
  if (copiedFormat.isItalic && !targetIsItalic) {
    document.execCommand('italic', false, null);
  } else if (!copiedFormat.isItalic && targetIsItalic) {
    document.execCommand('italic', false, null);
  }

  // 6. Altı Çizili: Hedef ile kopyalanan durumu birebir eşitle
  const targetIsUnderline = document.queryCommandState('underline') || ((targetCs.textDecorationLine || targetCs.textDecoration || '').includes('underline') || (targetNode.closest && targetNode.closest('u') !== null));
  if (copiedFormat.isUnderline && !targetIsUnderline) {
    document.execCommand('underline', false, null);
  } else if (!copiedFormat.isUnderline && targetIsUnderline) {
    document.execCommand('underline', false, null);
  }

  // 7. Üstü Çizili: Hedef ile kopyalanan durumu birebir eşitle
  const targetIsStrike = document.queryCommandState('strikeThrough') || ((targetCs.textDecorationLine || targetCs.textDecoration || '').includes('line-through') || (targetNode.closest && targetNode.closest('s, strike') !== null));
  if (copiedFormat.isStrike && !targetIsStrike) {
    document.execCommand('strikeThrough', false, null);
  } else if (!copiedFormat.isStrike && targetIsStrike) {
    document.execCommand('strikeThrough', false, null);
  }

  // 8. Paragraf Biçimlendirmesi (Sadece tüm paragraf seçiliyse veya boşluğa tıklandıysa uygula)
  const targetP = getActiveParagraph();
  if (targetP && (sel.isCollapsed || range.toString().trim().length >= targetP.innerText.trim().length)) {
    const pCs = window.getComputedStyle(targetP);
    if (copiedFormat.textAlign && pCs.textAlign !== copiedFormat.textAlign) targetP.style.textAlign = copiedFormat.textAlign;
    if (copiedFormat.lineHeight && pCs.lineHeight !== copiedFormat.lineHeight) targetP.style.lineHeight = copiedFormat.lineHeight;
    if (copiedFormat.marginTop && pCs.marginTop !== copiedFormat.marginTop) targetP.style.marginTop = copiedFormat.marginTop;
    if (copiedFormat.marginBottom && pCs.marginBottom !== copiedFormat.marginBottom) targetP.style.marginBottom = copiedFormat.marginBottom;
    if (copiedFormat.textIndent && pCs.textIndent !== copiedFormat.textIndent) targetP.style.textIndent = copiedFormat.textIndent;
  }

  showEditorToast('✓ Biçim uygulandı');
  updateActiveButtons();
  updateRulerFromActiveParagraph();

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

// --- DİNAMİK KAYDIRMA BLUR BANTLARI (Performans ve klavye akıcılığı için devre dışı) ---
function initDynamicScrollBlur() {
  const blurTop = document.getElementById('scroll-blur-top');
  const blurBottom = document.getElementById('scroll-blur-bottom');
  if (blurTop) blurTop.style.display = 'none';
  if (blurBottom) blurBottom.style.display = 'none';
}

// --- YAZDIRMA ÖNİZLEME (PRINT PREVIEW) ---
let printPreviewScale = 0.8;

function openPrintPreview() {
  if (typeof updatePagination === 'function') updatePagination();
  const modal = document.getElementById('modal-print-preview');
  const container = document.getElementById('print-preview-body');
  if (!modal || !container) {
    if (typeof triggerDirectPrint === 'function') triggerDirectPrint();
    return;
  }

  container.innerHTML = '';
  const pagesContainer = document.getElementById('pages-container') || document.getElementById('sheet-container') || document.getElementById('a4-sheet');
  if (!pagesContainer) return;

  const isLandscape = currentMargins.orientation === 'landscape';
  const clone = pagesContainer.cloneNode(true);
  clone.id = 'print-preview-pages-clone';
  clone.style.transform = `scale(${printPreviewScale})`;
  clone.style.transformOrigin = 'top center';
  clone.style.margin = '0 auto';
  clone.style.pointerEvents = 'none';

  clone.querySelectorAll('.page-body-box, .page-header-box, #editor-content, #doc-header').forEach(el => {
    el.removeAttribute('contenteditable');
  });

  const wrapper = document.createElement('div');
  wrapper.className = 'print-preview-sheet-wrapper';
  wrapper.style.display = 'flex';
  wrapper.style.justifyContent = 'center';
  wrapper.style.width = '100%';
  wrapper.style.height = Math.round(pagesContainer.offsetHeight * printPreviewScale + 60) + 'px';
  wrapper.appendChild(clone);

  container.appendChild(wrapper);

  const totalPages = document.querySelectorAll('.a4-sheet-page').length || 1;
  const indicator = document.getElementById('preview-page-indicator');
  if (indicator) {
    indicator.innerText = `Toplam ${totalPages} Sayfa (A4 ${isLandscape ? 'Yatay' : 'Dikey'})`;
  }
  const zoomLabel = document.getElementById('preview-zoom-label');
  if (zoomLabel) {
    zoomLabel.innerText = Math.round(printPreviewScale * 100) + '%';
  }

  modal.style.display = 'flex';
}

function closePrintPreview() {
  const modal = document.getElementById('modal-print-preview');
  if (modal) modal.style.display = 'none';
}

function printPreviewZoom(delta) {
  printPreviewScale = Math.max(0.3, Math.min(2.0, printPreviewScale + delta));
  const clone = document.getElementById('print-preview-pages-clone');
  const pagesContainer = document.getElementById('pages-container') || document.getElementById('sheet-container') || document.getElementById('a4-sheet');
  if (clone && pagesContainer) {
    clone.style.transform = `scale(${printPreviewScale})`;
    const wrapper = clone.parentElement;
    if (wrapper) {
      wrapper.style.height = Math.round(pagesContainer.offsetHeight * printPreviewScale + 60) + 'px';
    }
  }
  const zoomLabel = document.getElementById('preview-zoom-label');
  if (zoomLabel) {
    zoomLabel.innerText = Math.round(printPreviewScale * 100) + '%';
  }
}

function printPreviewFit() {
  const container = document.getElementById('print-preview-body');
  const pagesContainer = document.getElementById('pages-container') || document.getElementById('sheet-container') || document.getElementById('a4-sheet');
  if (!container || !pagesContainer) return;
  const availW = container.clientWidth - 60;
  const isLandscape = currentMargins.orientation === 'landscape';
  const sheetW = isLandscape ? 1123 : 794;
  if (availW > 100 && sheetW > 0) {
    printPreviewScale = Math.max(0.3, Math.min(1.5, Math.round((availW / sheetW) * 100) / 100));
    printPreviewZoom(0);
  }
}

window.openPrintPreview = openPrintPreview;
window.closePrintPreview = closePrintPreview;
window.printPreviewZoom = printPreviewZoom;
window.printPreviewFit = printPreviewFit;
