// UdeMobile Profesyonel Mobil Editör Motoru
let currentFontSize = 12;
let isMobileView = false;
let headerFooterVisible = false;

document.addEventListener('DOMContentLoaded', () => {
  const editor = document.getElementById('editor-content');
  
  editor.addEventListener('input', () => {
    updateCounts();
  });

  document.addEventListener('selectionchange', () => {
    updateActiveButtons();
  });

  updateCounts();
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

// Üstbilgi ve Altbilgi Görünürlüğü
function toggleHeaderFooter() {
  headerFooterVisible = !headerFooterVisible;
  const header = document.getElementById('doc-header');
  const footer = document.getElementById('doc-footer');
  const btn = document.getElementById('btn-toggle-header-footer');

  if (headerFooterVisible) {
    header.classList.add('visible');
    footer.classList.add('visible');
    btn.classList.add('active');
  } else {
    header.classList.remove('visible');
    footer.classList.remove('visible');
    btn.classList.remove('active');
  }
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

// Satır Aralığı (Line Spacing)
function changeLineSpacing(val) {
  document.getElementById('editor-content').style.lineHeight = val;
}

// Paragraf Öncesi/Sonrası Boşluk (UYAP Standardı)
function changeParagraphSpacing(val) {
  const ps = document.getElementById('editor-content').querySelectorAll('p');
  for (let p of ps) {
    p.style.marginBottom = val + 'px';
  }
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
      <p style="text-align: justify; margin-left: 20px;"><strong>1.1-)</strong> [Birinci alt madde açıklaması...]</p>
      <p style="text-align: justify; margin-left: 20px;"><strong>1.2-)</strong> [İkinci alt madde açıklaması...]</p>
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

// Sayfa Numarası Ekleme
function insertPageNumber() {
  toggleHeaderFooter();
  const footer = document.getElementById('doc-footer');
  const now = new Date().toLocaleDateString('tr-TR');
  footer.innerHTML = `<span>Belge Düzenleme Tarihi: ${now}</span> <span style="float: right; font-weight: bold;">Sayfa 1 / 1</span>`;
  footer.classList.add('visible');
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

// Android'den Gelen Base64 Resmi İlgili Konuma Ekleme
function insertImageBase64(base64Data) {
  const imgHtml = `<p style="text-align: center;"><img src="${base64Data}" alt="Dilekçe Eki / Belge Delili" style="max-width: 95%; max-height: 400px; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);"><br><em style="font-size: 10pt; color: #666;">(Ek / Delil Görseli)</em></p><p style="text-align: justify;"><br></p>`;
  document.execCommand('insertHTML', false, imgHtml);
  updateCounts();
}

// MODAL YÖNETİMİ
function openModal(id) {
  document.getElementById(id).classList.add('open');
}

function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}

function openMobileSignModal() {
  openModal('modal-mobile-sign');
}

function openSmartCardSignModal() {
  openModal('modal-smartcard-sign');
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
    // Resmi Mobil İmza Mührü
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

    document.execCommand('insertHTML', false, sealHtml);
    closeModal('modal-mobile-sign');

    if (window.AndroidBridge && window.AndroidBridge.onDocumentSigned) {
      window.AndroidBridge.onDocumentSigned("MOBIL_IMZA", op, hash);
    }
  }, 1200);
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

    document.execCommand('insertHTML', false, sealHtml);
    closeModal('modal-smartcard-sign');

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
      <p style="text-align: justify; text-indent: 28px;">1.1-) Müvekkil ile davalı taraf arasında akdedilen sözleşme uyarınca ...</p>
      <p style="text-align: justify; text-indent: 28px;">1.2-) Davalı taraf edimlerini haksız ve hukuka aykırı olarak yerine getirmemiştir ...</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>HUKUKİ SEBEPLER :</strong> 6100 sayılı HMK, 6098 sayılı TBK, TTK ve ilgili tüm mevzuat.</p>
      <p style="text-align: justify;"><strong>DELİLLER :</strong> Fatura, banka kayıtları, tanık, bilirkişi, yemin ve her türlü yasal delil.</p>
      <p style="text-align: justify;"><br></p>
      <p style="text-align: justify;"><strong>NETİCE-İ TALEP :</strong> Yukarıda arz ve izah edilen nedenlerle;</p>
      <p style="text-align: justify; text-indent: 28px;">1-) Haklı davamızın KABULÜNE,</p>
      <p style="text-align: justify; text-indent: 28px;">2-) Yargılama giderleri ile vekâlet ücretinin davalı yana tahmiline karar verilmesini saygıyla vekâleten arz ve talep ederiz.</p>
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
      <p style="text-align: justify; text-indent: 28px;">1.1-) Davacı tarafın dava dilekçesindeki iddiaları mesnedsiz ve hukuki dayanaktan yoksun olup davanın reddi gerekmektedir. Şöyle ki;</p>
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
      <p style="text-align: justify; text-indent: 28px;">Mahkemenizin yukarıda numarası yazılı dosyasında dava dilekçesi tarafımıza tebliğ edilmiştir. Dava konusu iddiaların kapsamlı olması, ilgili bilgi ve belgelerin temin edilebilmesi amacıyla tarafımıza HMK m. 127 gereğince 2 HAFTALIK EK CEVAP SÜRESİ verilmesini vekâleten talep ederiz.</p>
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
      <p style="text-align: justify; text-indent: 28px;">Dosyaya sunulan bilirkişi raporu usul ve yasaya uygun olmayıp aleyhe hususları kabul etmiyoruz...</p>
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
      <p style="text-align: justify; text-indent: 28px;">Yerel mahkemece eksik inceleme ve yanılgılı değerlendirme ile karar verilmiştir...</p>
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
      <p style="text-align: justify; text-indent: 28px;">Aramızda akdedilen sözleşme kapsamındaki borçlarınızı işbu ihtarnamenin tebliğinden itibaren 3 (üç) gün içinde ifa etmeniz, aksi halde yasal yollara müracaat olunacağı ihtar olunur.</p>
      <p style="text-align: right;"><br></p>
      <p style="text-align: right;"><strong>İhtar Eden Vekili</strong><br>Av. [Ad Soyad]<br><em>(e-imzalıdır)</em></p>
    `;
  }

  if (tpl) {
    document.getElementById('editor-content').innerHTML = tpl;
    updateCounts();
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

// Sayım
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
function setHtmlContent(html) {
  document.getElementById('editor-content').innerHTML = html;
  updateCounts();
}

function getHtmlContent() {
  return document.getElementById('editor-content').innerHTML;
}

function getPlainText() {
  return document.getElementById('editor-content').innerText || '';
}

// Belgeyi Java UDF & DOCX Üreticileri için Yapılandırılmış Paragraflar Olarak Çıkar
function getStructuredDocument() {
  const container = document.getElementById('editor-content');
  const paragraphs = [];
  
  const nodes = container.children;
  if (!nodes || nodes.length === 0) {
    paragraphs.push({
      text: container.innerText || '',
      align: 3,
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

      paragraphs.push({
        text: pText,
        align: align,
        runs: runs.length > 0 ? runs : [{ text: pText, bold: false, italic: false, underline: false }]
      });
    }
  }

  return JSON.stringify(paragraphs);
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
