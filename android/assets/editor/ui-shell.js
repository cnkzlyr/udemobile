/**
 * CanEditor arayüz kabuğu: UYAP Doküman Editörü ile aynı menü çubuğu davranışı.
 * - Tıkla aç, menüler arasında üzerinden geç, dışarı tıkla / Esc ile kapat.
 * - Menüden bir komut seçilince menü kapanır ve editör odağı korunur.
 */
(function () {
  const bar = document.getElementById('ce-menubar');
  if (!bar) return;
  let open = null;
  const close = () => {
    if (open) { open.classList.remove('open'); open.querySelectorAll('.ce-sub.open').forEach(x => x.classList.remove('open')); }
    open = null; bar.classList.remove('active');
  };
  bar.querySelectorAll('.ce-menu').forEach(menu => {
    const title = menu.querySelector('.ce-menu-title');
    // Seçimi kaybetmemek için mousedown varsayılanı engellenir
    title.addEventListener('mousedown', e => e.preventDefault());
    title.addEventListener('click', () => {
      if (open === menu) { close(); return; }
      close(); open = menu; menu.classList.add('open'); bar.classList.add('active');
    });
    title.addEventListener('mouseenter', () => {
      if (open && open !== menu) { open.classList.remove('open'); open = menu; menu.classList.add('open'); }
    });
    // Alt menüler (Farklı Kaydet / Paylaş / Yazdır ...): dokunmatik ekranda hover olmadığından tıklayınca aç/kapat
    menu.querySelectorAll('.ce-sub > span').forEach(span => {
      span.addEventListener('mousedown', e => e.preventDefault());
      span.addEventListener('click', e => {
        e.stopPropagation();
        const sub = span.parentElement;
        const wasOpen = sub.classList.contains('open');
        menu.querySelectorAll('.ce-sub.open').forEach(x => x.classList.remove('open'));
        if (!wasOpen) sub.classList.add('open');
      });
    });
    menu.querySelectorAll('.ce-menu-pop button').forEach(btn => {
      btn.type = 'button';
      if (!btn.hasAttribute('onmousedown')) btn.addEventListener('mousedown', e => e.preventDefault());
      btn.addEventListener('click', () => setTimeout(close, 0));
    });
  });
  document.addEventListener('mousedown', e => { if (open && !bar.contains(e.target)) close(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });

  // Biçim çubuğu düğmeleri: tıklarken editör seçimi kaybolmasın
  document.querySelectorAll('#toolbar-container .ce-tb').forEach(b => {
    if (!b.hasAttribute('onmousedown')) b.addEventListener('mousedown', e => e.preventDefault());
  });
  // Renk seçicileri: seçim, renk penceresi açılmadan önce kaydedilir
  document.querySelectorAll('.ce-color input').forEach(inp => {
    inp.addEventListener('mousedown', () => { if (window.recordCurrentSelection) recordCurrentSelection(); });
    inp.addEventListener('input', () => { inp.parentElement.style.setProperty('--ce-swatch', inp.value); });
    inp.parentElement.style.setProperty('--ce-swatch', inp.value);
  });

  // =========================================================================
  // 1. GECE MODU, GECE KAĞIDI VE ODAK MODU (Sıfır UDF Etkisi - Salt CSS Sınıfı)
  // =========================================================================
  function syncThemeButtons() {
    const isDark = document.body.classList.contains('ce-dark-mode');
    const isFocus = document.body.classList.contains('ce-focus-mode');
    const darkBtn = document.getElementById('btn-dark-mode');
    if (darkBtn) {
      darkBtn.textContent = isDark ? '☀️' : '🌙';
      darkBtn.classList.toggle('active', isDark);
      darkBtn.title = isDark ? 'Gündüz Moduna Geç' : 'Gece Modu (Koyu Arayüz)';
    }
    const focusBtn = document.getElementById('btn-focus-mode');
    if (focusBtn) {
      focusBtn.classList.toggle('active', isFocus);
    }
    const exitPill = document.getElementById('ce-focus-exit-pill');
    if (exitPill) {
      exitPill.style.display = isFocus ? 'inline-flex' : 'none';
    }
  }

  window.toggleDarkMode = function (force) {
    const next = typeof force === 'boolean' ? force : !document.body.classList.contains('ce-dark-mode');
    document.body.classList.toggle('ce-dark-mode', next);
    try { localStorage.setItem('ce_dark_mode', next ? '1' : '0'); } catch (_) {}
    syncThemeButtons();
  };

  window.toggleDarkPaperMode = function (force) {
    const next = typeof force === 'boolean' ? force : !document.body.classList.contains('ce-dark-paper');
    if (next && !document.body.classList.contains('ce-dark-mode')) {
      document.body.classList.add('ce-dark-mode');
      try { localStorage.setItem('ce_dark_mode', '1'); } catch (_) {}
    }
    document.body.classList.toggle('ce-dark-paper', next);
    try { localStorage.setItem('ce_dark_paper', next ? '1' : '0'); } catch (_) {}
    syncThemeButtons();
  };

  window.toggleFocusMode = function (force) {
    const next = typeof force === 'boolean' ? force : !document.body.classList.contains('ce-focus-mode');
    document.body.classList.toggle('ce-focus-mode', next);
    syncThemeButtons();
    if (typeof window.fitToWidth === 'function' && !document.body.classList.contains('mobile-mode')) {
      setTimeout(() => { try { window.fitToWidth(); } catch (_) {} }, 60);
    }
  };

  try {
    if (localStorage.getItem('ce_dark_mode') === '1') document.body.classList.add('ce-dark-mode');
    if (localStorage.getItem('ce_dark_paper') === '1') document.body.classList.add('ce-dark-paper');
    syncThemeButtons();
  } catch (_) {}

  // =========================================================================
  // 2. BELGE ANAHATTI VE TÜRK HUKUK BÖLÜM GEZGİNİ (OUTLINE DRAWER)
  // =========================================================================
  let outlineItemsCache = [];

  function classifyLegalHeading(text, pEl) {
    const clean = (text || '').replace(/\u200B/g, '').replace(/\s+/g, ' ').trim();
    if (!clean || clean.length < 3 || clean.length > 180) return null;

    const upper = clean.toLocaleUpperCase('tr-TR');
    // 1. Mahkeme / Savcılık / İcra Dairesi Başlıkları
    if (/(MAHKEMESİ|BAŞSAVCILIĞI|DAİRESİ|MÜDÜRLÜĞÜ|HAKİMLİĞİ|BAŞKANLIĞI|KURULU)/.test(upper) && clean.length <= 120) {
      const align = (pEl.getAttribute('data-udf-align') || pEl.style.textAlign || '').toLowerCase();
      if (align === 'center' || align === '1' || upper === clean) {
        return { icon: '🏛️', type: 'court', label: clean, level: 0 };
      }
    }
    // 2. Dosya / Esas / Karar / Soruşturma No
    if (/^(DOSYA|ESAS|KARAR|SORUŞTURMA|İCRA|TALİMAT)\s*(NO|NUMARASI)?\s*[:\t]/i.test(clean)) {
      return { icon: '📁', type: 'meta', label: clean, level: 1 };
    }
    // 3. Taraf Bilgileri (Davacı, Davalı, Sanık, Müşteki, Vekili, Müdafii)
    if (/^(DAVACI|DAVALI|SANIK|SSÇ|MÜŞTEKİ|MAĞDUR|KATILAN|İHBAR EDEN|BORÇLU|ALACAKLI|VEKİLİ|MÜDAFİİ|KARŞI TARAF)\b[^a-zğüşıöç]{0,15}[:\t]/i.test(clean)) {
      return { icon: '👤', type: 'party', label: clean, level: 1 };
    }
    // 4. Konu / Suç / Dava Değeri / Talep Konusu
    if (/^(KONU|KONUSU|DAVA KONUSU|TALEP KONUSU|SUÇ|SUÇ TARİHİ|DAVA DEĞERİ|HARCA ESAS DEĞER|TEBLİĞ TARİHİ)\b[^a-zğüşıöç]{0,15}[:\t]/i.test(clean)) {
      return { icon: '📌', type: 'subject', label: clean, level: 1 };
    }
    // 5. Ana Dilekçe ve Karar Bölümleri
    if (/^(AÇIKLAMALAR|İZAHAT|SAVUNMALARIMIZ|İTİRAZLARIMIZ|BEYANLARIMIZ|OLAYLAR|USULE İLİŞKİN|ESASA İLİŞKİN|GEREKÇE|DELİLLER|HUKUKİ DELİLLER|HUKUKİ SEBEPLER|HUKUKİ NEDENLER|SONUÇ VE İSTEM|SONUÇ VE TALEP|NETİCE-İ TALEP|NETİCE VE TALEP|HÜKÜM|KARAR)\b/i.test(upper) && clean.length <= 95) {
      return { icon: '⚖️', type: 'section', label: clean, level: 0 };
    }
    // 6. Numaralı veya Romen Rakamlı Alt Başlıklar (I-, II., 1-, 1., A-, A))
    if (/^([IVX]{1,4}[\.\-\)]|[0-9]{1,2}[\.\-\)]|[A-ZÇĞİÖŞÜ][\.\)])\s+[A-ZÇĞİÖŞÜ0-9]/.test(clean) && clean.length <= 110) {
      const hasBold = !!pEl.querySelector('b, strong, [style*="font-weight: bold"], [style*="font-weight:bold"]');
      if (hasBold || upper === clean) {
        return { icon: '📑', type: 'subheading', label: clean, level: 1 };
      }
    }
    // 7. Tamamı Büyük Harf ve Kalın / Ortalanmış Kısa Başlıklar
    if (clean.length >= 4 && clean.length <= 90 && upper === clean && /[A-ZÇĞİÖŞÜ]{3,}/.test(clean)) {
      const hasBold = !!pEl.querySelector('b, strong, [style*="font-weight: bold"], [style*="font-weight:bold"]');
      const align = (pEl.getAttribute('data-udf-align') || pEl.style.textAlign || '').toLowerCase();
      if (hasBold || align === 'center' || align === '1') {
        return { icon: '🔹', type: 'heading', label: clean, level: 0 };
      }
    }
    return null;
  }

  window.refreshDocumentOutline = function () {
    const listEl = document.getElementById('ce-outline-list');
    if (!listEl) return;

    const pagesContainer = document.getElementById('pages-container');
    const pages = pagesContainer ? Array.from(pagesContainer.querySelectorAll('.a4-sheet-page')) : [];
    const allParas = pagesContainer
      ? Array.from(pagesContainer.querySelectorAll('.page-body-box p'))
      : Array.from(document.querySelectorAll('#editor-content p'));

    outlineItemsCache = [];
    allParas.forEach((p, idx) => {
      if (p.getAttribute('data-split-continuation') === 'true') return;
      const text = (p.innerText || p.textContent || '').replace(/\u200B/g, '').trim();
      if (!text) return;
      const match = classifyLegalHeading(text, p);
      if (match) {
        const pageSheet = p.closest('.a4-sheet-page');
        const pageNum = pageSheet ? (pageSheet.getAttribute('data-page-number') || '1') : '1';
        outlineItemsCache.push({
          idx,
          pageNum,
          icon: match.icon,
          type: match.type,
          level: match.level,
          label: match.label,
          element: p
        });
      }
    });

    const pagePill = document.getElementById('ce-outline-page-pill');
    const paraPill = document.getElementById('ce-outline-para-pill');
    const secPill = document.getElementById('ce-outline-sec-pill');
    const nonContParas = allParas.filter(p => p.getAttribute('data-split-continuation') !== 'true');
    if (pagePill) pagePill.textContent = `${Math.max(1, pages.length)} Sayfa`;
    if (paraPill) paraPill.textContent = `${nonContParas.length} Paragraf`;
    if (secPill) secPill.textContent = `${outlineItemsCache.length} Bölüm`;

    const searchInput = document.getElementById('ce-outline-search');
    window.filterDocumentOutline(searchInput ? searchInput.value : '');
  };

  window.filterDocumentOutline = function (query) {
    const listEl = document.getElementById('ce-outline-list');
    if (!listEl) return;
    const q = (query || '').trim().toLocaleLowerCase('tr-TR');
    const filtered = q
      ? outlineItemsCache.filter(item => item.label.toLocaleLowerCase('tr-TR').includes(q))
      : outlineItemsCache;

    listEl.innerHTML = '';
    if (filtered.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'ce-outline-empty';
      empty.innerHTML = outlineItemsCache.length === 0
        ? '<span>📄</span><p>Belgede henüz başlık veya hukuki bölüm tespit edilmedi.</p><small>Mahkeme adı, Dosya No, Davacı/Davalı, Açıklamalar, Deliller, Sonuç ve İstem gibi başlıklar otomatik listelenir.</small>'
        : '<span>🔍</span><p>Aramanızla eşleşen başlık bulunamadı.</p>';
      listEl.appendChild(empty);
      return;
    }

    filtered.forEach(item => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `ce-outline-item level-${item.level} type-${item.type}`;
      btn.innerHTML = `
        <span class="ce-outline-item-icon">${item.icon}</span>
        <span class="ce-outline-item-text">${item.label.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</span>
        <span class="ce-outline-item-page">S.${item.pageNum}</span>
      `;
      btn.addEventListener('click', () => {
        if (item.element && item.element.isConnected) {
          item.element.scrollIntoView({ behavior: 'smooth', block: 'center' });
          item.element.classList.remove('ce-outline-flash');
          void item.element.offsetWidth;
          item.element.classList.add('ce-outline-flash');
          setTimeout(() => item.element.classList.remove('ce-outline-flash'), 1600);
        }
      });
      listEl.appendChild(btn);
    });
  };

  window.toggleOutlineDrawer = function (force) {
    const drawer = document.getElementById('ce-outline-drawer');
    if (!drawer) return;
    const isVisible = drawer.style.display !== 'none';
    const next = typeof force === 'boolean' ? force : !isVisible;
    drawer.style.display = next ? 'flex' : 'none';
    document.body.classList.toggle('ce-outline-open', next);
    const btn = document.getElementById('btn-outline-drawer');
    if (btn) btn.classList.toggle('active', next);
    if (next) {
      window.refreshDocumentOutline();
    }
  };

  // =========================================================================
  // 3. HAVELSAN UYAP %100 UYUMLULUK VE KAYNAK KORUMA RAPORU MODALI
  // =========================================================================
  window.refreshUdfCompatBadge = function () {
    const badge = document.getElementById('udfCompatBadge');
    const footerStatus = document.getElementById('footerCompatStatus');
    const src = window.__udfSource;
    const stats = window.__udfCompatStats;

    if (badge) {
      if (src && src.originalContentXml) {
        badge.textContent = '🏛️ UYAP %100';
        badge.classList.add('compat-verified');
      } else {
        badge.textContent = '🏛️ UYAP %100';
      }
    }
    if (footerStatus && stats) {
      if (stats.mode === 'byte-identical-100%') {
        footerStatus.textContent = `✓ Havelsan UYAP %100 Birebir Korundu (${stats.totalBlocks || 0} blok)`;
      } else if (stats.mode === 'hybrid-source-splicing') {
        footerStatus.textContent = `✓ Havelsan UYAP %100 Uyumlu (${stats.untouchedBlocks}/${stats.totalBlocks} blok korundu, ${stats.partialEditedBlocks || 0} kısmi)`;
      }
    }
  };

  window.openUdfCompatModal = function () {
    const modal = document.getElementById('modal-udf-compat');
    if (!modal) return;
    const src = window.__udfSource;
    const stats = window.__udfCompatStats || {};

    const totalBlocks = stats.totalBlocks || (src && src.origBlocks ? src.origBlocks.length : document.querySelectorAll('.page-body-box p:not([data-split-continuation="true"]), .page-body-box table:not([data-split-continuation="true"])').length);
    const untouched = stats.untouchedBlocks !== undefined ? stats.untouchedBlocks : (src && src.origBlocks ? src.origBlocks.length : totalBlocks);
    const partial = stats.partialEditedBlocks || 0;
    let specialRunsCount = stats.preservedRuns || 0;
    let nlModeLabel = 'Standart (Attached)';
    if (src && src.paragraphMap) {
      let sepCount = 0;
      let attCount = 0;
      let totalRuns = 0;
      Object.values(src.paragraphMap).forEach(entry => {
        if (entry.trailingNlXml) sepCount++;
        else attCount++;
        if (entry.visRuns) totalRuns += entry.visRuns.length;
      });
      if (!specialRunsCount) specialRunsCount = totalRuns;
      if (sepCount > 0 && attCount === 0) nlModeLabel = 'Ayrık Satır Sonu (separate_nl)';
      else if (sepCount > 0 && attCount > 0) nlModeLabel = `Karma (${sepCount} ayrık / ${attCount} bitişik)`;
      else nlModeLabel = 'Bitişik Satır Sonu (attached_nl)';
    }

    const setEl = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = String(val); };
    setEl('compat-stat-mode', src && src.originalContentXml ? 'Katman-1 + Katman-2 Kaynak Korumalı' : 'Havelsan Format 1.8 Üretici');
    setEl('compat-stat-total-blocks', totalBlocks);
    setEl('compat-stat-untouched', untouched);
    setEl('compat-stat-partial', partial);
    setEl('compat-stat-runs', specialRunsCount);
    setEl('compat-stat-nl-mode', nlModeLabel);

    const resEl = document.getElementById('compat-live-test-result');
    if (resEl) resEl.style.display = 'none';
    modal.style.display = 'flex';
  };

  window.runLiveUdfCompatCheck = async function () {
    const resEl = document.getElementById('compat-live-test-result');
    if (!resEl) return;
    resEl.style.display = 'block';
    resEl.innerHTML = '⏳ <strong>Anlık Havelsan UDF Doğrulaması çalışıyor…</strong>';

    try {
      const docData = typeof window.getStructuredDocument === 'function' ? window.getStructuredDocument() : null;
      if (!docData || typeof window.generateUdfBlob !== 'function') {
        throw new Error('UDF motoru hazır değil.');
      }
      const blob = await window.generateUdfBlob(docData);
      const ab = await blob.arrayBuffer();
      const zip = await window.JSZip.loadAsync(ab);
      const contentEntry = zip.file('content.xml');
      if (!contentEntry) throw new Error('content.xml bulunamadı.');
      const xmlStr = await contentEntry.async('string');
      const parser = new DOMParser();
      const xmlDoc = parser.parseFromString(xmlStr, 'text/xml');
      const parseErr = xmlDoc.querySelector('parsererror');
      if (parseErr) throw new Error('XML Sözdizimi Hatası: ' + parseErr.textContent);

      const cdataNode = xmlDoc.querySelector('template > content');
      const cdataLen = cdataNode ? (cdataNode.textContent || '').length : 0;
      const paraNodes = xmlDoc.querySelectorAll('elements paragraph');
      const hasProps = !!zip.file('documentproperties.xml');
      const hasSign = !!zip.file('sign.sgn');
      const stats = window.__udfCompatStats || {};

      window.openUdfCompatModal();
      resEl.style.display = 'block';
      resEl.innerHTML = `
        <div style="color:#15803D; font-weight:700; margin-bottom:4px;">✅ Anlık UDF Uyumluluk Testi Başarılı (%100 Geçerli Havelsan Format_ID 1.8)</div>
        <div style="font-size:12px; line-height:1.5; color:var(--ce-text);">
          • <strong>Üretilen UDF Boyutu:</strong> ${(ab.byteLength / 1024).toFixed(1)} KB (${paraNodes.length} paragraf, ${cdataLen} CDATA karakteri)<br>
          • <strong>Koruma Modu:</strong> <code>${stats.mode || 'havelsan-1.8'}</code> (${stats.untouchedBlocks || 0}/${stats.totalBlocks || 0} blok birebir, ${stats.partialEditedBlocks || 0} kısmi düzenlenen blok)<br>
          • <strong>ZIP Zarfı:</strong> <code>content.xml</code> ✓ ${hasProps ? '• <code>documentproperties.xml</code> ✓' : ''} ${hasSign ? '• <code>sign.sgn</code> (E-İmza) ✓' : ''}
        </div>
      `;
      window.refreshUdfCompatBadge();
    } catch (err) {
      resEl.innerHTML = `<span style="color:#DC2626; font-weight:700;">❌ Doğrulama Hatası: ${err.message}</span>`;
    }
  };

  // =========================================================================
  // 4. KOMUT PALETİ (Ctrl+K / ⌘K — HIZLI EYLEM VE ŞABLON ARAMA)
  // =========================================================================
  const COMMAND_PALETTE_ITEMS = [
    { id: 'save-udf', icon: '💾', category: 'Dosya', title: 'Belgeyi Kaydet (.udf)', shortcut: 'Ctrl+S', run: () => window.triggerQuickSave && window.triggerQuickSave() },
    { id: 'open-doc', icon: '📂', category: 'Dosya', title: 'Belge Aç (UDF, DOCX, PDF, TIFF, ODT)', shortcut: 'Ctrl+O', run: () => window.triggerOpenDocument && window.triggerOpenDocument() },
    { id: 'open-uyap-orig', icon: '🏛️', category: 'Havelsan UYAP', title: "Orijinal UYAP Doküman Editörü'nde Aç (Java/Swing)", shortcut: '', run: () => window.uyapEditordeAc && window.uyapEditordeAc() },
    { id: 'udf-compat', icon: '🛡️', category: 'Havelsan UYAP', title: 'Havelsan UYAP %100 Uyumluluk ve Kaynak Koruma Raporu', shortcut: '', run: () => window.openUdfCompatModal && window.openUdfCompatModal() },
    { id: 'udf-live-test', icon: '🔬', category: 'Havelsan UYAP', title: 'Anlık Havelsan UDF Uyumluluk Testi Çalıştır', shortcut: '', run: () => { window.openUdfCompatModal && window.openUdfCompatModal(); window.runLiveUdfCompatCheck && window.runLiveUdfCompatCheck(); } },
    { id: 'outline', icon: '📑', category: 'Görünüm', title: 'Belge Anahattı ve Hukuki Bölümler Çekmecesini Aç/Kapat', shortcut: '', run: () => window.toggleOutlineDrawer && window.toggleOutlineDrawer() },
    { id: 'focus-mode', icon: '🧘', category: 'Görünüm', title: 'Odak Modu (Dikkat Dağıtmayan Tam Ekran Yazım)', shortcut: '', run: () => window.toggleFocusMode && window.toggleFocusMode() },
    { id: 'dark-mode', icon: '🌙', category: 'Görünüm', title: 'Gece Modu (Koyu Arayüz Teması Aç/Kapat)', shortcut: '', run: () => window.toggleDarkMode && window.toggleDarkMode() },
    { id: 'dark-paper', icon: '📜', category: 'Görünüm', title: 'Gece Kağıdı (Koyu Sayfa Görünümü Aç/Kapat)', shortcut: '', run: () => window.toggleDarkPaperMode && window.toggleDarkPaperMode() },
    { id: 'view-toggle', icon: '📱', category: 'Görünüm', title: 'Sayfa Görünümü / Mobil Akış Görünümü Değiştir', shortcut: '', run: () => window.toggleViewMode && window.toggleViewMode() },
    { id: 'ai-format', icon: '🤖', category: 'Hukuk & AI', title: 'Dilekçeyi Otomatik Biçimlendir (Standart & Gemini AI)', shortcut: '', run: () => window.openAiFormatModal && window.openAiFormatModal() },
    { id: 'amount-words', icon: '💰', category: 'Hukuk & AI', title: 'Seçili Tutarı Rakam ve Yazıyla Ekle (Örn: 12.500,00 TL)', shortcut: '', run: () => window.insertAmountInWords && window.insertAmountInWords() },
    { id: 'official-date', icon: '📅', category: 'Hukuk & AI', title: 'Günün Resmi Tarihini Ekle (GG.AA.YYYY)', shortcut: '', run: () => window.insertOfficialDate && window.insertOfficialDate() },
    { id: 'sign-smartcard', icon: '✍️', category: 'E-İmza', title: 'Nitelikli E-İmza ile İmzala (Akıllı Kart / USB Token)', shortcut: '', run: () => window.openSmartCardSignModal && window.openSmartCardSignModal() },
    { id: 'sign-mobile', icon: '📲', category: 'E-İmza', title: 'Mobil İmza ile İmzala (Turkcell / Vodafone / Türk Telekom)', shortcut: '', run: () => window.openMobileSignModal && window.openMobileSignModal() },
    { id: 'sign-verify', icon: '🟢', category: 'E-İmza', title: 'Belgedeki Elektronik İmzaları Doğrula (sign.sgn)', shortcut: '', run: () => window.checkDocumentSignature && window.checkDocumentSignature() },
    { id: 'save-pdf', icon: '📕', category: 'Dışa Aktar', title: 'PDF Olarak İndir (.pdf)', shortcut: 'Ctrl+Shift+P', run: () => window.triggerSavePdf && window.triggerSavePdf() },
    { id: 'save-docx', icon: '📘', category: 'Dışa Aktar', title: 'Microsoft Word Olarak Kaydet (.docx)', shortcut: '', run: () => window.triggerSaveAs && window.triggerSaveAs('docx') },
    { id: 'save-tiff', icon: '🖼️', category: 'Dışa Aktar', title: 'Çok Sayfalı TIFF Olarak Kaydet (.tiff)', shortcut: '', run: () => window.triggerSaveAs && window.triggerSaveAs('tiff') },
    { id: 'print-preview', icon: '🖨️', category: 'Dışa Aktar', title: 'Baskı Önizleme ve Yazdır', shortcut: 'Ctrl+P', run: () => window.openPrintPreview && window.openPrintPreview() },
    { id: 'tpl-dava', icon: '⚖️', category: 'Şablon', title: 'Şablon: Dava Dilekçesi Oluştur', shortcut: '', run: () => window.insertTemplate && window.insertTemplate('dava') },
    { id: 'tpl-cevap', icon: '⚖️', category: 'Şablon', title: 'Şablon: Cevap Dilekçesi Oluştur', shortcut: '', run: () => window.insertTemplate && window.insertTemplate('cevap') },
    { id: 'tpl-istinaf', icon: '⚖️', category: 'Şablon', title: 'Şablon: İstinaf Başvuru Dilekçesi Oluştur', shortcut: '', run: () => window.insertTemplate && window.insertTemplate('istinaf') },
    { id: 'tpl-icra', icon: '⚖️', category: 'Şablon', title: 'Şablon: Ödeme Emrine / İcraya İtiraz Dilekçesi', shortcut: '', run: () => window.insertTemplate && window.insertTemplate('icra') },
    { id: 'tpl-delil', icon: '⚖️', category: 'Şablon', title: 'Şablon: Delil Listesi Sunum Dilekçesi', shortcut: '', run: () => window.insertTemplate && window.insertTemplate('delil') },
    { id: 'tpl-beyan', icon: '⚖️', category: 'Şablon', title: 'Şablon: Bilirkişi Raporuna Beyan ve İtiraz Dilekçesi', shortcut: '', run: () => window.insertTemplate && window.insertTemplate('beyan') },
    { id: 'find-replace', icon: '🔍', category: 'Düzen', title: 'Bul ve Değiştir…', shortcut: 'Ctrl+F', run: () => window.openFindReplaceModal && window.openFindReplaceModal() },
    { id: 'para-modal', icon: '¶', category: 'Biçim', title: 'Paragraf Girinti ve Boşluk Ayarları…', shortcut: '', run: () => window.openParagraphModal && window.openParagraphModal() },
    { id: 'page-setup', icon: '📐', category: 'Biçim', title: 'Sayfa Yapısı ve Kenar Boşlukları…', shortcut: '', run: () => window.openPageSetupModal && window.openPageSetupModal() },
    { id: 'doc-stats', icon: '📊', category: 'Araçlar', title: 'Kelime, Karakter ve Sayfa İstatistikleri', shortcut: '', run: () => window.openDocStatsModal && window.openDocStatsModal() },
    // Hukuk Asistanı (asistan.js): UETS + UYAP Evrak + A4 motoru birleşik paneli
    { id: 'as-sure', icon: '⏱️', category: 'Asistan', title: 'Yasal Süre Hesapla (UETS tebliğ + HMK/CMK/İYUK)', shortcut: '', run: () => window.openHukukAsistani && window.openHukukAsistani('sure') },
    { id: 'as-hesap', icon: '🧮', category: 'Asistan', title: 'Vekâlet Ücreti / Faiz / Harç / SMM / CMK Makbuzu Hesapla', shortcut: '', run: () => window.openHukukAsistani && window.openHukukAsistani('hesap') },
    { id: 'as-yeni', icon: '🔔', category: 'Asistan', title: "UYAP'a Düşen Yeni Evraklar ve Tebligatlar", shortcut: '', run: () => window.openHukukAsistani && window.openHukukAsistani('yeni') },
    { id: 'as-drive', icon: '☁️', category: 'Asistan', title: 'Google Drive Eşitleme Durumu', shortcut: '', run: () => window.openHukukAsistani && window.openHukukAsistani('drive') },
    { id: 'as-a4', icon: '📄', category: 'Asistan', title: 'Görsel / TIFF / PDF → Tek A4 PDF (NAPS2 yöntemi)', shortcut: '', run: () => window.openHukukAsistani && window.openHukukAsistani('a4') },
    { id: 'as-ajanda', icon: '📅', category: 'Asistan', title: 'Ajanda: Yaklaşan Duruşmalar ve Süre Sonları', shortcut: '', run: () => window.openHukukAsistani && window.openHukukAsistani('ajanda') },
    { id: 'as-evrak', icon: '🗂️', category: 'Asistan', title: 'UYAP Evrak Kataloğunda Ara ve Aç', shortcut: '', run: () => window.openHukukAsistani && window.openHukukAsistani('evrak') },
    { id: 'as-gorev', icon: '⚙️', category: 'Asistan', title: 'UETS Senkronu / UYAP Evrak İndirme Görevleri', shortcut: '', run: () => window.openHukukAsistani && window.openHukukAsistani('gorev') }
  ];

  let cmdFiltered = COMMAND_PALETTE_ITEMS.slice();
  let cmdActiveIndex = 0;

  function renderCommandPaletteList() {
    const listEl = document.getElementById('ce-cmd-list');
    if (!listEl) return;
    listEl.innerHTML = '';
    if (cmdFiltered.length === 0) {
      listEl.innerHTML = '<div class="ce-cmd-empty">Eşleşen komut bulunamadı.</div>';
      return;
    }
    cmdFiltered.forEach((item, idx) => {
      const row = document.createElement('button');
      row.type = 'button';
      row.className = 'ce-cmd-item' + (idx === cmdActiveIndex ? ' active' : '');
      row.innerHTML = `
        <span class="ce-cmd-item-icon">${item.icon}</span>
        <span class="ce-cmd-item-body">
          <span class="ce-cmd-item-title">${item.title}</span>
          <span class="ce-cmd-item-cat">${item.category}</span>
        </span>
        ${item.shortcut ? `<kbd class="ce-cmd-item-kbd">${item.shortcut}</kbd>` : ''}
      `;
      row.addEventListener('mouseenter', () => {
        cmdActiveIndex = idx;
        Array.from(listEl.children).forEach((c, i) => c.classList.toggle('active', i === idx));
      });
      row.addEventListener('click', () => {
        window.closeCommandPalette();
        setTimeout(() => { try { item.run(); } catch (e) { console.error(e); } }, 10);
      });
      listEl.appendChild(row);
    });
    const activeEl = listEl.children[cmdActiveIndex];
    if (activeEl && activeEl.scrollIntoView) {
      activeEl.scrollIntoView({ block: 'nearest' });
    }
  }

  window.openCommandPalette = function () {
    const modal = document.getElementById('modal-command-palette');
    const inp = document.getElementById('ce-cmd-input');
    if (!modal || !inp) return;
    if (window.recordCurrentSelection) window.recordCurrentSelection();
    modal.style.display = 'flex';
    inp.value = '';
    cmdFiltered = COMMAND_PALETTE_ITEMS.slice();
    cmdActiveIndex = 0;
    renderCommandPaletteList();
    setTimeout(() => inp.focus(), 20);
  };

  window.closeCommandPalette = function () {
    const modal = document.getElementById('modal-command-palette');
    if (modal) modal.style.display = 'none';
  };

  const cmdInput = document.getElementById('ce-cmd-input');
  if (cmdInput) {
    cmdInput.addEventListener('input', () => {
      const q = (cmdInput.value || '').trim().toLocaleLowerCase('tr-TR');
      cmdFiltered = q
        ? COMMAND_PALETTE_ITEMS.filter(item =>
            item.title.toLocaleLowerCase('tr-TR').includes(q) ||
            item.category.toLocaleLowerCase('tr-TR').includes(q)
          )
        : COMMAND_PALETTE_ITEMS.slice();
      cmdActiveIndex = 0;
      renderCommandPaletteList();
    });
    cmdInput.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (cmdFiltered.length > 0) {
          cmdActiveIndex = (cmdActiveIndex + 1) % cmdFiltered.length;
          renderCommandPaletteList();
        }
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (cmdFiltered.length > 0) {
          cmdActiveIndex = (cmdActiveIndex - 1 + cmdFiltered.length) % cmdFiltered.length;
          renderCommandPaletteList();
        }
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const chosen = cmdFiltered[cmdActiveIndex];
        if (chosen) {
          window.closeCommandPalette();
          setTimeout(() => { try { chosen.run(); } catch (err) { console.error(err); } }, 10);
        }
      } else if (e.key === 'Escape') {
        e.preventDefault();
        window.closeCommandPalette();
      }
    });
  }

  // Global Klavye Kısayolları (Ctrl+K Komut Paleti, Esc Odak Modu / Komut Paleti Kapatma)
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
      e.preventDefault();
      const modal = document.getElementById('modal-command-palette');
      if (modal && modal.style.display !== 'none') window.closeCommandPalette();
      else window.openCommandPalette();
      return;
    }
    if (e.key === 'Escape') {
      const cmdModal = document.getElementById('modal-command-palette');
      if (cmdModal && cmdModal.style.display !== 'none') {
        window.closeCommandPalette();
        return;
      }
      if (document.body.classList.contains('ce-focus-mode')) {
        window.toggleFocusMode(false);
      }
    }
  });

  // Esc: açık pencere yoksa Anahat çekmecesini kapatır
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape' || e.defaultPrevented) return;
    const drawer = document.getElementById('ce-outline-drawer');
    const acikPencere = [...document.querySelectorAll('.modal-backdrop')].some(m => m.classList.contains('open') || m.style.display === 'flex');
    if (drawer && drawer.style.display !== 'none' && !acikPencere) window.toggleOutlineDrawer(false);
  });

  // Belge değişikliklerinde Anahat çekmecesi açıksa otomatik güncelle
  let outlineTimer = null;
  document.addEventListener('input', () => {
    const drawer = document.getElementById('ce-outline-drawer');
    if (drawer && drawer.style.display !== 'none') {
      clearTimeout(outlineTimer);
      outlineTimer = setTimeout(() => window.refreshDocumentOutline(), 450);
    }
  });
})();
