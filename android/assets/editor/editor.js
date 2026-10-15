// UdeMobile Profesyonel Mobil Editör Motoru
let currentFontSize = 12;
let isMobileView = false;
let isRulerVisible = true;
let activeDragMarker = null;
let savedSelectionRange = null;

// Paragraf Ayarları Değişkenleri
let paragraphScope = 'selected';
let currentPAlign = 'justify';

document.addEventListener('DOMContentLoaded', () => {
  const editor = document.getElementById('editor-content');
  
  editor.addEventListener('input', () => {
    updateCounts();
  });

  document.addEventListener('selectionchange', () => {
    updateActiveButtons();
    updateRulerFromActiveParagraph();
  });

  // Tıklama ile aktif paragrafı algılama
  editor.addEventListener('click', () => {
    updateRulerFromActiveParagraph();
  });

  initRuler();
  updateCounts();
  setTimeout(() => {
    updateRulerFromActiveParagraph();
  }, 250);
});

// Kağıt Görünümü (A4) / Mobil Görünüm Geçişi
function toggleViewMode() {
  const wrapper = document.getElementById('page-wrapper');
  const btn = document.getElementById('btn-toggle-view');
  
  isMobileView = !isMobileView;
  if (isMobileView) {
    wrapper.classList.remove('paper-view');
    wrapper.classList.add('mobile-view');
    btn.textContent = '📄 Kağıt Modu';
  } else {
    wrapper.classList.remove('mobile-view');
    wrapper.classList.add('paper-view');
    btn.textContent = '📱 Mobil Mod';
  }
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
  if (!selection || selection.rangeCount === 0) {
    const ps = editor.querySelectorAll('p, li, blockquote');
    return ps.length > 0 ? ps[0] : null;
  }
  let node = selection.anchorNode;
  while (node && node !== editor && node !== document.body) {
    if (node.nodeType === Node.ELEMENT_NODE) {
      const tag = node.tagName.toLowerCase();
      if (tag === 'p' || tag === 'li' || tag === 'blockquote' || (tag === 'div' && node.parentNode === editor)) {
        return node;
      }
    }
    node = node.parentNode;
  }
  const ps = editor.querySelectorAll('p, li, blockquote');
  return ps.length > 0 ? ps[0] : null;
}

function getSelectedParagraphs() {
  const selection = window.getSelection();
  const editor = document.getElementById('editor-content');
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
    const p = getActiveParagraph();
    return p ? [p] : [];
  }
  const range = selection.getRangeAt(0);
  const allBlocks = Array.from(editor.querySelectorAll('p, li, blockquote'));
  const intersected = allBlocks.filter(b => range.intersectsNode(b));
  return intersected.length > 0 ? intersected : (getActiveParagraph() ? [getActiveParagraph()] : []);
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
}

// Satır Aralığı (Yalnızca Seçili Paragraflara Uygulanır)
function changeLineSpacing(val) {
  const targets = getSelectedParagraphs();
  targets.forEach(p => {
    p.style.lineHeight = val;
  });
  updateCounts();
}

// --- ETKİLEŞİMLİ CETVEL MOTORU ---
function initRuler() {
  const ticksContainer = document.getElementById('ruler-ticks');
  if (!ticksContainer) return;
  ticksContainer.innerHTML = '';

  const totalMm = 160; // 0 - 16 cm (160 mm)
  for (let mm = 0; mm <= totalMm; mm++) {
    const pct = (mm / totalMm) * 100;
    const tick = document.createElement('div');
    tick.style.left = pct + '%';

    if (mm % 10 === 0) {
      tick.className = 'ruler-tick cm';
      const cmNum = mm / 10;
      if (cmNum >= 0 && cmNum <= 16) {
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

  setupMarkerDragging('marker-first-line', 'firstLine');
  setupMarkerDragging('marker-left-indent', 'leftIndent');
  setupMarkerDragging('marker-right-indent', 'rightIndent');

  const rulerScale = document.getElementById('ruler-scale');
  rulerScale.addEventListener('click', (e) => {
    if (activeDragMarker) return;
    const rect = rulerScale.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = Math.max(0, Math.min(1, x / rect.width));
    const cm = Math.round((pct * 16) * 4) / 4;
    setFirstLineIndent(cm);
    updateRulerFromActiveParagraph();
  });
}

function setupMarkerDragging(markerId, type) {
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
      const cm = Math.round((pct * 16) * 4) / 4;

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
        const rightCm = Math.round((rightPct * 16) * 4) / 4;
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

  let firstCm = parseToCm(p.style.textIndent || window.getComputedStyle(p).textIndent);
  let leftCm = parseToCm(p.style.marginLeft || window.getComputedStyle(p).marginLeft);
  let rightCm = parseToCm(p.style.marginRight || window.getComputedStyle(p).marginRight);

  firstMarker.style.left = Math.min(100, Math.max(0, (firstCm / 16) * 100)) + '%';
  leftMarker.style.left = Math.min(100, Math.max(0, (leftCm / 16) * 100)) + '%';
  rightMarker.style.right = Math.min(100, Math.max(0, (rightCm / 16) * 100)) + '%';
  rightMarker.style.left = 'auto';
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
  const sel = window.getSelection();
  if (sel && sel.rangeCount > 0) {
    savedSelectionRange = sel.getRangeAt(0).cloneRange();
  } else {
    savedSelectionRange = null;
  }
}

function restoreCurrentSelection() {
  if (savedSelectionRange) {
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(savedSelectionRange);
    return true;
  }
  return false;
}

function openModal(id) {
  document.getElementById(id).classList.add('open');
}

function closeModal(id) {
  document.getElementById(id).classList.remove('open');
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
  }

  if (tpl) {
    document.getElementById('editor-content').innerHTML = tpl;
    updateCounts();
    updateRulerFromActiveParagraph();
  }
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
    updateRulerFromActiveParagraph();
  }, 150);
  setTimeout(markDocumentPristine, 400);
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
}
function isDocumentModified() {
  if (window.__origDocSnapshot === null) return true;
  return snapshotDocument() !== window.__origDocSnapshot;
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
        if (data.header !== undefined && headerEl) headerEl.innerText = data.header;
        if (data.footer !== undefined && footerEl) footerEl.innerText = data.footer;
        if (data.html) {
          editor.innerHTML = data.html;
          updateCounts();
          setTimeout(() => {
            updateRulerFromActiveParagraph();
          }, 150);
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
  }, 150);
}

function getHtmlContent() {
  return document.getElementById('editor-content').innerHTML;
}

function getPlainText() {
  return document.getElementById('editor-content').innerText || '';
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
    paragraphs: paragraphs
  };

  return docPayload;
}

function parseInlineRuns(element, runs, bold, italic, underline) {
  for (let child of element.childNodes) {
    if (child.nodeType === Node.TEXT_NODE) {
      if (child.textContent) {
        runs.push({
          text: child.textContent,
          bold: bold,
          italic: italic,
          underline: underline
        });
      }
    } else if (child.nodeType === Node.ELEMENT_NODE) {
      const tag = child.tagName.toLowerCase();
      const isB = bold || tag === 'b' || tag === 'strong' || (child.style && child.style.fontWeight === 'bold');
      const isI = italic || tag === 'i' || tag === 'em' || (child.style && child.style.fontStyle === 'italic');
      const isU = underline || tag === 'u' || (child.style && child.style.textDecoration && child.style.textDecoration.includes('underline'));
      parseInlineRuns(child, runs, isB, isI, isU);
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
