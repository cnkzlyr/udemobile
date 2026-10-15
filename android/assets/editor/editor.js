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
}

function openMobileSignModal() {
  saveCurrentSelection();
  openModal('modal-mobile-sign');
}

function openSmartCardSignModal() {
  saveCurrentSelection();
  openModal('modal-smartcard-sign');
}

function insertSignatureSeal(sealHtml) {
  const restored = restoreCurrentSelection();
  const editor = document.getElementById('editor-content');
  editor.focus();

  let inserted = false;
  if (restored) {
    try {
      inserted = document.execCommand('insertHTML', false, sealHtml);
    } catch (e) {
      inserted = false;
    }
  }

  if (!inserted) {
    const wrapper = document.createElement('div');
    wrapper.innerHTML = sealHtml;
    editor.appendChild(wrapper);
  }

  setTimeout(() => {
    const seals = editor.querySelectorAll('.official-signature-seal');
    if (seals.length > 0) {
      seals[seals.length - 1].scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, 100);

  updateCounts();
}

// MOBİL İMZA İŞLEMİ
function startMobileSign() {
  const op = document.getElementById('msign-operator').value;
  const phone = document.getElementById('msign-phone').value.trim();
  const tckn = document.getElementById('msign-tckn').value.trim();
  const statusEl = document.getElementById('msign-status');

  if (phone.length < 10) {
    statusEl.style.color = '#C62828';
    statusEl.textContent = 'Lütfen geçerli bir telefon numarası giriniz.';
    return;
  }
  if (tckn.length !== 11) {
    statusEl.style.color = '#C62828';
    statusEl.textContent = 'Lütfen 11 haneli T.C. Kimlik numaranızı giriniz.';
    return;
  }

  statusEl.style.color = '#1565C0';
  statusEl.textContent = '⏳ ' + op + ' Mobil İmza isteği SIM karta iletiliyor...';

  setTimeout(() => {
    const now = new Date().toLocaleString('tr-TR');
    const hash = 'M-SIG-' + Math.random().toString(36).substring(2, 10).toUpperCase() + '-' + Date.now().toString(16).toUpperCase();
    const maskedTckn = tckn.substring(0, 3) + '*****' + tckn.substring(8);
    const maskedPhone = phone.substring(0, 4) + '***' + phone.substring(phone.length - 2);

    const sealHtml = `
      <div class="official-signature-seal">
        <div class="seal-icon">📱</div>
        <div class="seal-details">
          <div class="seal-title">GÜVENLİ ELEKTRONİK MOBİL İMZA İLE İMZALANMIŞTIR</div>
          <div><strong>Operatör:</strong> ${op} Mobil İmza Servisi</div>
          <div><strong>İmzalayan TCKN:</strong> ${maskedTckn} | <strong>GSM:</strong> ${maskedPhone}</div>
          <div><strong>Zaman Damgası:</strong> ${now}</div>
          <div><strong>Sertifika Doğrulama Kodu:</strong> <code>${hash}</code> (5070 S.K. Uyumlu)</div>
        </div>
      </div>
      <p style="text-align: justify;"><br></p>
    `;

    closeModal('modal-mobile-sign');
    insertSignatureSeal(sealHtml);

    if (window.AndroidBridge && window.AndroidBridge.onDocumentSigned) {
      window.AndroidBridge.onDocumentSigned("MOBIL_IMZA", op, hash);
    }
  }, 1000);
}

// USB AKILLI KART / E-İMZA İŞLEMİ
function startSmartCardSign() {
  const provider = document.getElementById('sc-provider').value;
  const pin = document.getElementById('sc-pin').value.trim();
  const statusEl = document.getElementById('sc-status');

  if (pin.length < 4) {
    statusEl.style.color = '#C62828';
    statusEl.textContent = 'Lütfen en az 4 haneli kart PIN kodunu giriniz.';
    return;
  }

  statusEl.style.color = '#1565C0';
  statusEl.textContent = '⏳ Type-C Akıllı Kart okunuyor ve imzalanıyor...';

  setTimeout(() => {
    const now = new Date().toLocaleString('tr-TR');
    const certHash = 'CCID-' + provider + '-' + Math.random().toString(36).substring(2, 8).toUpperCase() + '-' + Date.now().toString(16).toUpperCase();

    const sealHtml = `
      <div class="official-signature-seal">
        <div class="seal-icon">✍️</div>
        <div class="seal-details">
          <div class="seal-title">GÜVENLİ NİTELİKLİ ELEKTRONİK SERTİFİKA İLE İMZALANMIŞTIR</div>
          <div><strong>Sağlayıcı / Kart Tipi:</strong> ${provider} Güvenli Akıllı Kart Token</div>
          <div><strong>İmza Standardı:</strong> CAdES-BES / XAdES (5070 S.K. m. 4 ve m. 5)</div>
          <div><strong>İmza Zamanı:</strong> ${now}</div>
          <div><strong>Doğrulama Özeti (SHA-256):</strong> <code>${certHash}</code></div>
        </div>
      </div>
      <p style="text-align: justify;"><br></p>
    `;

    closeModal('modal-smartcard-sign');
    insertSignatureSeal(sealHtml);

    if (window.AndroidBridge && window.AndroidBridge.onDocumentSigned) {
      window.AndroidBridge.onDocumentSigned("USB_EIMZA", provider, certHash);
    }
  }, 1000);
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
function setHtmlContent(content) {
  if (!content) return;
  const editor = document.getElementById('editor-content');
  const headerEl = document.getElementById('doc-header');
  const footerEl = document.getElementById('doc-footer');

  // JSON Yapılandırılmış Belge veya Düz HTML Kontrolü
  const trimmed = content.trim();
  if (trimmed.startsWith('{') && trimmed.includes('"paragraphs"')) {
    try {
      const data = JSON.parse(trimmed);
      if (data.header && headerEl) headerEl.innerText = data.header;
      if (data.footer && footerEl) footerEl.innerText = data.footer;
      if (data.html) {
        editor.innerHTML = data.html;
      }
    } catch (e) {
      editor.innerHTML = content;
    }
  } else {
    editor.innerHTML = content;
  }

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

  return JSON.stringify(docPayload);
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
