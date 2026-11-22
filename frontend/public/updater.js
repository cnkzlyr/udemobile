/* CanEditor — Dahili Güncelleyici
 * GitHub Releases üzerinden son sürümü denetler, kullanıcıyı uyarır, veri kaybını önlemek için
 * önce kaydetmeye izin verir (+ otomatik yerel taslak yedeği alır), sonra platforma uygun
 * paketi indirip kurar:
 *   Android : DownloadManager + sistem paket yükleyici (AndroidBridge)
 *   Windows : setup.exe indirilir ve çalıştırılır
 *   macOS   : .dmg indirilir ve açılır
 *   Linux   : AppImage ise yerinde değiştirilip yeniden başlatılır, değilse .deb açılır
 */
(function () {
  'use strict';

  const VERSION = '4.9.2';
  const REPO = 'cnkzlyr/udemobile';
  const API = 'https://api.github.com/repos/' + REPO + '/releases/latest';
  const LS_LAST = 'caneditor_update_last_check';
  const LS_SKIP = 'caneditor_update_skip';
  const LS_DRAFT = 'caneditor_update_draft';
  const CHECK_EVERY_MS = 12 * 3600 * 1000;

  window.CANEDITOR_VERSION = VERSION;
  // Alt bilgi çubuğundaki sürüm etiketi tek kaynaktan (bu dosyadan) yazılır; HTML'e elle yazılan sürüm eskiyordu
  const yazSurum = () => { const e = document.getElementById('footerVersion'); if (e) e.textContent = 'CanEditor v' + VERSION + ' (Birleşik Hukuk Platformu)'; };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', yazSurum); else yazSurum();

  const ls = {
    get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} },
    del: k => { try { localStorage.removeItem(k); } catch (e) {} }
  };

  const isAndroid = () => !!(window.AndroidBridge && window.AndroidBridge.startUpdateDownload);
  const tauri = () => (window.__TAURI__ && window.__TAURI__.core) ? window.__TAURI__.core : null;
  const toast = m => { try { if (typeof showEditorToast === 'function') showEditorToast(m); } catch (e) {} };

  function cmpVersion(a, b) {
    const pa = String(a).replace(/^v/i, '').split('.').map(n => parseInt(n, 10) || 0);
    const pb = String(b).replace(/^v/i, '').split('.').map(n => parseInt(n, 10) || 0);
    for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
      const d = (pa[i] || 0) - (pb[i] || 0);
      if (d) return d > 0 ? 1 : -1;
    }
    return 0;
  }

  async function fetchLatest() {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), 10000);
    try {
      const r = await fetch(API, { headers: { Accept: 'application/vnd.github+json' }, signal: ctl.signal, cache: 'no-store' });
      if (!r.ok) throw new Error('GitHub yanıtı: HTTP ' + r.status);
      return await r.json();
    } finally { clearTimeout(t); }
  }

  async function platformInfo() {
    if (isAndroid()) return { os: 'android', appimage: false };
    const c = tauri();
    if (c) { try { return await c.invoke('platform_info'); } catch (e) {} }
    return { os: 'web', appimage: false };
  }

  function pickAsset(rel, info) {
    const as = rel.assets || [];
    const f = fn => as.find(a => fn(a.name || ''));
    switch (info.os) {
      case 'android': return f(n => /^CanEditor-v[\d.]+\.apk$/i.test(n));
      case 'windows': return f(n => /x64-setup\.exe$/i.test(n));
      case 'macos': return f(n => /universal\.dmg$/i.test(n));
      case 'linux': return info.appimage ? f(n => /\.AppImage$/i.test(n)) : f(n => /amd64\.deb$/i.test(n));
      default: return null;
    }
  }

  const docEmpty = () => { const e = document.getElementById('editor-content'); return !e || !(e.innerText || '').trim(); };
  const docModified = () => {
    if (docEmpty()) return false;
    try { return typeof isDocumentModified === 'function' ? !!isDocumentModified() : true; } catch (e) { return true; }
  };

  function saveCurrentDocument() {
    try {
      if (isAndroid() && window.AndroidBridge.requestSave) window.AndroidBridge.requestSave();
      else if (typeof triggerSaveUdf === 'function') triggerSaveUdf();
    } catch (e) { toast('Kaydetme başlatılamadı: ' + e.message); }
  }

  // ---- Yerel taslak yedeği (güncelleme sırasında veri kaybına karşı ek güvence) ----
  function cleanEditorHtml() {
    const e = document.getElementById('editor-content');
    const c = e.cloneNode(true);
    c.querySelectorAll('.auto-page-break').forEach(n => n.remove());
    return c.innerHTML;
  }
  function saveDraft() {
    if (!docModified()) { ls.del(LS_DRAFT); return false; }
    const h = document.getElementById('doc-header'), f = document.getElementById('doc-footer');
    ls.set(LS_DRAFT, JSON.stringify({
      ts: Date.now(), ver: VERSION, html: cleanEditorHtml(),
      header: h ? h.innerHTML : '', footer: f ? f.innerHTML : ''
    }));
    return true;
  }
  function checkDraftOnStart() {
    if (typeof isEditorFocused === 'function' && isEditorFocused()) return;
    if (typeof isUserTypingActive === 'function' && isUserTypingActive()) return;
    if (window.__userHasEditedDocument) return;
    const raw = ls.get(LS_DRAFT);
    if (!raw) return;
    let d; try { d = JSON.parse(raw); } catch (e) { ls.del(LS_DRAFT); return; }
    if (!d || !d.html || Date.now() - d.ts > 14 * 86400000) { ls.del(LS_DRAFT); return; }
    const when = new Date(d.ts).toLocaleString('tr-TR');
    openModal(`
      <h3>💾 Kurtarılan taslak</h3>
      <p>Güncelleme öncesinde otomatik yedeklenen kaydedilmemiş bir belge bulundu (<b>${when}</b>).</p>
      <div class="cu-row">
        <button class="cu-btn cu-primary" id="cu-restore">Geri yükle</button>
        <button class="cu-btn" id="cu-discard">Sil</button>
        <button class="cu-btn" id="cu-keep">Daha sonra</button>
      </div>`);
    document.getElementById('cu-restore').onclick = () => {
      const e = document.getElementById('editor-content');
      e.innerHTML = d.html;
      const h = document.getElementById('doc-header'), f = document.getElementById('doc-footer');
      if (h && d.header) h.innerHTML = d.header;
      if (f && d.footer) f.innerHTML = d.footer;
      ls.del(LS_DRAFT);
      try { updatePagination(); updateCounts(); } catch (x) {}
      if (window.CanHistory) CanHistory.commit();
      closeModal();
      toast('✓ Taslak geri yüklendi. Lütfen kaydedin.');
    };
    document.getElementById('cu-discard').onclick = () => { ls.del(LS_DRAFT); closeModal(); };
    document.getElementById('cu-keep').onclick = closeModal;
  }

  // ---- Arayüz ----
  function injectCss() {
    if (document.getElementById('cu-style')) return;
    const st = document.createElement('style');
    st.id = 'cu-style';
    st.textContent = `
#cu-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:100000;display:flex;align-items:center;justify-content:center;padding:16px}
#cu-box{background:#fff;color:#202124;border-radius:12px;max-width:460px;width:100%;padding:20px 22px;box-shadow:0 12px 40px rgba(0,0,0,.35);font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-height:90vh;overflow:auto}
#cu-box h3{margin:0 0 10px;font-size:18px}
#cu-box p{margin:6px 0;font-size:14px;line-height:1.45}
#cu-box .cu-notes{background:#f1f3f4;border-radius:8px;padding:8px 10px;font-size:12.5px;max-height:130px;overflow:auto;white-space:pre-wrap;margin:8px 0}
#cu-box .cu-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
#cu-box .cu-btn{border:1px solid #dadce0;background:#f8f9fa;border-radius:8px;padding:9px 14px;font-size:14px;cursor:pointer}
#cu-box .cu-primary{background:#1a73e8;color:#fff;border-color:#1a73e8;font-weight:600}
#cu-box .cu-save{background:#188038;color:#fff;border-color:#188038}
#cu-box .cu-warn{background:#fef7e0;border:1px solid #f9ab00;border-radius:8px;padding:8px 10px;font-size:13px}
#cu-box .cu-ok{background:#e6f4ea;border:1px solid #34a853;border-radius:8px;padding:8px 10px;font-size:13px}
#cu-bar{height:10px;background:#e8eaed;border-radius:6px;overflow:hidden;margin:12px 0 4px}
#cu-bar>i{display:block;height:100%;width:0;background:#1a73e8;transition:width .3s}`;
    document.head.appendChild(st);
  }
  function openModal(html) {
    injectCss();
    closeModal();
    const bd = document.createElement('div');
    bd.id = 'cu-backdrop';
    bd.innerHTML = '<div id="cu-box">' + html + '</div>';
    document.body.appendChild(bd);
  }
  function closeModal() {
    const bd = document.getElementById('cu-backdrop');
    if (bd) bd.remove();
    if (window.__cuTimer) { clearInterval(window.__cuTimer); window.__cuTimer = null; }
  }
  const esc = s => String(s).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
  const mb = n => (n / 1048576).toFixed(1) + ' MB';

  function showUpdateDialog(rel, asset, info) {
    const newVer = String(rel.tag_name).replace(/^v/i, '');
    const notes = (rel.body || '').replace(/\r/g, '').split('\n').filter(l => l.trim() && !/^\s*\|/.test(l)).slice(0, 14).join('\n');
    openModal(`
      <h3>🔄 Yeni sürüm mevcut: ${esc(newVer)}</h3>
      <p>Kurulu sürüm: <b>${VERSION}</b>${asset ? ' • İndirme: ' + mb(asset.size) : ''}</p>
      <div class="cu-notes">${esc(notes || 'Sürüm notu yok.')}</div>
      <div id="cu-state"></div>
      <div class="cu-row">
        <button class="cu-btn cu-save" id="cu-save">💾 Önce belgeyi kaydet</button>
        <button class="cu-btn cu-primary" id="cu-go">${asset ? '⬇️ İndir ve güncelle' : '🌐 İndirme sayfasını aç'}</button>
        <button class="cu-btn" id="cu-later">Sonra</button>
        <button class="cu-btn" id="cu-skip">Bu sürümü atla</button>
      </div>`);

    const state = document.getElementById('cu-state');
    const refresh = () => {
      if (!document.getElementById('cu-state')) return;
      state.innerHTML = docModified()
        ? '<div class="cu-warn">⚠️ Belgede <b>kaydedilmemiş değişiklikler</b> var. Güncelleme uygulamayı yeniden başlatır. Önce kaydetmeniz önerilir (ayrıca otomatik taslak yedeği alınır).</div>'
        : '<div class="cu-ok">✓ Kaydedilmemiş değişiklik yok.</div>';
    };
    refresh();
    window.__cuTimer = setInterval(refresh, 800);

    document.getElementById('cu-save').onclick = () => { saveCurrentDocument(); setTimeout(refresh, 1500); };
    document.getElementById('cu-later').onclick = closeModal;
    document.getElementById('cu-skip').onclick = () => { ls.set(LS_SKIP, newVer); closeModal(); };
    document.getElementById('cu-go').onclick = () => {
      if (!asset) { window.open(rel.html_url, '_blank'); return; }
      if (docModified() && !confirm('Kaydedilmemiş değişiklikler var ve uygulama yeniden başlatılacak.\n\nDeğişiklikler otomatik taslak olarak yedeklenecek ve bir sonraki açılışta geri yüklenebilecek.\n\nDevam edilsin mi?')) return;
      saveDraft();
      startInstall(asset, info);
    };
  }

  async function startInstall(asset, info) {
    const box = document.getElementById('cu-box');
    box.innerHTML = `<h3>⬇️ Güncelleme indiriliyor…</h3>
      <div id="cu-bar"><i></i></div><p id="cu-msg">Başlatılıyor…</p>`;
    const bar = box.querySelector('#cu-bar>i'), msg = box.querySelector('#cu-msg');
    const setP = (got, total) => {
      const pct = total ? Math.min(100, Math.round(got * 100 / total)) : 0;
      bar.style.width = pct + '%';
      msg.textContent = mb(got) + ' / ' + mb(total) + ' (' + pct + '%)';
    };
    const fail = m => { box.innerHTML = `<h3>❌ Güncelleme başarısız</h3><p>${esc(m)}</p><div class="cu-row"><button class="cu-btn" id="cu-x">Kapat</button></div>`; document.getElementById('cu-x').onclick = closeModal; };
    try {
      if (info.os === 'android') {
        const id = String(window.AndroidBridge.startUpdateDownload(asset.browser_download_url, asset.name));
        if (!id || id === '-1') throw new Error('İndirme başlatılamadı.');
        window.__cuTimer = setInterval(() => {
          let s; try { s = JSON.parse(window.AndroidBridge.getUpdateStatus(id)); } catch (e) { return; }
          setP(s.downloaded || 0, s.total > 0 ? s.total : asset.size);
          if (s.status === 8) {
            clearInterval(window.__cuTimer); window.__cuTimer = null;
            msg.textContent = 'İndirildi. Yükleme ekranı açılıyor…';
            const r = String(window.AndroidBridge.installUpdate(id));
            if (r === 'need_permission') msg.textContent = 'Lütfen açılan ayarlarda "Bu kaynaktan yüklemeye izin ver"i açıp geri dönün, sonra tekrar deneyin.';
            else if (r !== 'ok') fail(r);
            else setTimeout(closeModal, 1500);
          } else if (s.status === 16) {
            clearInterval(window.__cuTimer); window.__cuTimer = null;
            fail('İndirme hatası (kod ' + (s.reason || '?') + '). İnternet bağlantınızı kontrol edin.');
          }
        }, 700);
      } else {
        const c = tauri();
        const path = await c.invoke('start_update_download', { url: asset.browser_download_url, fileName: asset.name });
        window.__cuTimer = setInterval(async () => {
          let s; try { s = await c.invoke('update_download_progress', { path }); } catch (e) { return; }
          setP(s.bytes || 0, asset.size);
          if (s.finished) {
            clearInterval(window.__cuTimer); window.__cuTimer = null;
            if (!s.ok || s.bytes !== asset.size) { fail('İndirme tamamlanamadı veya dosya eksik (' + s.bytes + '/' + asset.size + ' bayt). Tekrar deneyin.'); return; }
            msg.textContent = 'Kurulum başlatılıyor…';
            try { await c.invoke('install_update', { path }); } catch (e) { fail(String(e)); }
          }
        }, 700);
      }
    } catch (e) {
      fail(e && e.message ? e.message : String(e));
    }
  }

  async function checkForUpdates(manual) {
    try {
      if (manual) toast('Güncellemeler denetleniyor…');
      const rel = await fetchLatest();
      ls.set(LS_LAST, String(Date.now()));
      const newVer = String(rel.tag_name || '').replace(/^v/i, '');
      if (!newVer || cmpVersion(newVer, VERSION) <= 0) {
        if (manual) toast('✓ CanEditor güncel (v' + VERSION + ')');
        return false;
      }
      if (!manual && ls.get(LS_SKIP) === newVer) return false;
      if (!manual && ((typeof isEditorFocused === 'function' && isEditorFocused()) || (typeof isUserTypingActive === 'function' && isUserTypingActive()))) {
        return false;
      }
      const info = await platformInfo();
      showUpdateDialog(rel, pickAsset(rel, info), info);
      return true;
    } catch (e) {
      if (manual) toast('Güncelleme denetlenemedi: ' + (e && e.message ? e.message : e));
      return false;
    }
  }

  window.checkForUpdates = checkForUpdates;

  function boot() {
    setTimeout(checkDraftOnStart, 2500);
    const last = parseInt(ls.get(LS_LAST) || '0', 10);
    if (Date.now() - last > CHECK_EVERY_MS) setTimeout(() => checkForUpdates(false), 7000);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
