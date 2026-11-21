/**
 * CanEditor v4.1 — HAYFA Hukuk Tasarım Sistemi ve Birleşik Hukuk Platformu Sekmeleri
 * -----------------------------------------------------------------------------------
 * asistan.js ile birlikte çalışır ve şu modülleri masaüstü + Android + web'e getirir:
 *   • 📁 UYAP Dosya Yönetim Merkezi (tüm davalar, evraklar, notlar, Drive eşleşmesi, tek tıkla Notion/TT)
 *   • ☁️ Google Drive Eşitleme + Drive → SQLite Veritabanı İndeks & Arama + Doğrudan Açma
 *   • 📋 Notion & TickTick Canlı Yönetim + Güvenli Yerel API Yapılandırması + Otomatik Aktarım
 *   • 🔄 Resmî Havelsan JAR Dönüştürücü (UDF → PDF / ODT / DOCX + Paylaş)
 *   • 📰 HAYFA Hukuk Portalı (İçtihat Karar Arama + Dilekçeye Ekle, Haberler, Resmî Gazete, Mevzuat, Çevrimdışı Adliye & IBAN)
 */
(function () {
  'use strict';

  const GOOGLE_APPS_SCRIPT_KODU = `// ===========================================================================
// UYAP Google Drive Webhook Betiği (script.google.com)
// Bu kodu Google Drive'ınızda "Yeni > Diğer > Google Apps Script" açıp yapıştırın.
// Ardından "Dağıt (Deploy) > Yeni Dağıtım > Web Uygulaması" seçip URL'yi alın.
// ===========================================================================
// Sürüm 2 (CanEditor 4.3.1+): "list" ile Drive'ın tamamı sayfa sayfa indekslenir, "get" ile dosya açılır.
// GÜNCELLEME: Bu kodu yapıştırdıktan sonra "Dağıt > Dağıtımları yönet > ✏️ > Sürüm: Yeni sürüm > Dağıt"
// yapın; böylece Web Uygulaması adresi (URL) DEĞİŞMEZ.
var BETIK_SURUM = 2;

function _json(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

// Drive'ı klasör klasör gezer; ~25 sn veya 2000 dosyada durup "state" döner (Apps Script 6 dk sınırı).
// Walks the Drive tree breadth-first and returns a resumable state token.
function _listele(data) {
  var basla = Date.now();
  var st = data.state ? JSON.parse(data.state) : null;
  if (!st) {
    var kok;
    if (data.kok) {
      var it0 = DriveApp.getFoldersByName(data.kok);
      if (!it0.hasNext()) return { status: "error", message: "Klasör bulunamadı: " + data.kok };
      kok = it0.next();
    } else {
      kok = DriveApp.getRootFolder();
    }
    st = { q: [[kok.getId(), ""]], cur: null, ft: null };
  }
  var dosyalar = [];
  while (Date.now() - basla < 25000 && dosyalar.length < 2000) {
    if (!st.cur) {
      if (!st.q.length) { st = null; break; }
      st.cur = st.q.shift();
      st.ft = null;
      var alt = DriveApp.getFolderById(st.cur[0]).getFolders();
      while (alt.hasNext()) {
        var f = alt.next();
        st.q.push([f.getId(), (st.cur[1] ? st.cur[1] + "/" : "") + f.getName()]);
      }
    }
    var it = st.ft ? DriveApp.continueFileIterator(st.ft) : DriveApp.getFolderById(st.cur[0]).getFiles();
    var bitti = true;
    while (it.hasNext()) {
      if (Date.now() - basla > 25000 || dosyalar.length >= 2000) { bitti = false; break; }
      var d = it.next();
      dosyalar.push({ id: d.getId(), ad: d.getName(), klasor: st.cur[1], boyut: d.getSize(),
        mtime: Math.floor(d.getLastUpdated().getTime() / 1000), url: d.getUrl(), mime: d.getMimeType() });
    }
    if (bitti) { st.cur = null; st.ft = null; } else { st.ft = it.getContinuationToken(); }
  }
  return { status: "ok", surum: BETIK_SURUM, dosyalar: dosyalar, state: st ? JSON.stringify(st) : null };
}

// UYAP_Arsiv altında aynı klasörde aynı ad + aynı boyuttaki kopyaları ÇÖP KUTUSUNA taşır (30 gün geri alınabilir);
// en eski dosya kalır. Eski sürümlerin "Eksikleri Drive'a Eşitle" düğmesi her basışta yeniden yüklüyordu.
function _kopyaTemizle(data) {
  var basla = Date.now();
  var st = data.state ? JSON.parse(data.state) : null;
  if (!st) {
    var it0 = DriveApp.getFoldersByName("UYAP_Arsiv");
    if (!it0.hasNext()) return { status: "ok", tasinan: 0, state: null };
    st = { q: [it0.next().getId()] };
  }
  var tasinan = 0;
  while (st.q.length && Date.now() - basla < 25000) {
    var f = DriveApp.getFolderById(st.q.shift());
    var alt = f.getFolders();
    while (alt.hasNext()) st.q.push(alt.next().getId());
    var gruplar = {};
    var it = f.getFiles();
    while (it.hasNext()) {
      var d = it.next();
      var k = d.getName() + "|" + d.getSize();
      (gruplar[k] = gruplar[k] || []).push(d);
    }
    for (var k in gruplar) {
      var l = gruplar[k];
      if (l.length < 2) continue;
      l.sort(function (a, b) { return a.getDateCreated().getTime() - b.getDateCreated().getTime(); });
      for (var i = 1; i < l.length; i++) { l[i].setTrashed(true); tasinan++; }
    }
  }
  return { status: "ok", tasinan: tasinan, state: st.q.length ? JSON.stringify(st) : null };
}

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    if (data.action === "ping" || data.test) {
      return _json({ status: "ok", surum: BETIK_SURUM, message: "Bağlantı başarılı!" });
    }
    if (data.action === "list") return _json(_listele(data));
    if (data.action === "kopya_temizle") return _json(_kopyaTemizle(data));
    if (data.action === "get") {
      var gf = DriveApp.getFileById(data.id);
      var b = gf.getBlob();
      return _json({ status: "ok", ad: gf.getName(), mime: b.getContentType(), content: Utilities.base64Encode(b.getBytes()) });
    }
    var rootFolderName = "UYAP_Arsiv";
    var rootFolders = DriveApp.getFoldersByName(rootFolderName);
    var root = rootFolders.hasNext() ? rootFolders.next() : DriveApp.createFolder(rootFolderName);
    
    // Klasör hiyerarşisini bul veya oluştur
    var folder = root;
    if (data.folder_path) {
      var parts = data.folder_path.replace(/\\\\/g, "/").split("/");
      for (var i = 0; i < parts.length; i++) {
        var part = parts[i].trim();
        if (!part) continue;
        var sub = folder.getFoldersByName(part);
        folder = sub.hasNext() ? sub.next() : folder.createFolder(part);
      }
    }
    
    // Dosyayı oluştur — aynı klasörde aynı ad ve boyutta dosya varsa YENİDEN OLUŞTURMA (kopya birikmesin)
    var decoded = Utilities.base64Decode(data.content);
    var ad = data.filename || "evrak.pdf";
    var mevcut = folder.getFilesByName(ad);
    while (mevcut.hasNext()) {
      var mf = mevcut.next();
      if (mf.getSize() === decoded.length) {
        return _json({ status: "success", mevcut: true, filename: ad, fileId: mf.getId(), url: mf.getUrl() });
      }
    }
    var blob = Utilities.newBlob(decoded, "application/pdf", ad);
    var file = folder.createFile(blob);
    
    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      filename: data.filename,
      fileId: file.getId(),
      url: file.getUrl()
    })).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}
function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({ status: "ok", message: "CanEditor Google Drive Webhook Aktif" }))
    .setMimeType(ContentService.MimeType.JSON);
}
`;

  const HAYFA_CSS = `
  /* HAYFA Hukuk & Danışmanlık Kurumsal Renk Paleti + Mobil Uyumlu Tasarım */
  :root {
    --hf-navy: #0f2341; --hf-navy-2: #16315a; --hf-navy-3: #1f4173;
    --hf-gold: #c8a45a; --hf-gold-2: #8c6214; --hf-gold-soft: #f5ecd9;
  }
  #ca-panel .ca-kutu {
    width: min(1040px, calc(100vw - 20px));
    max-height: calc(100vh - 24px);
    border-radius: 16px;
    border: 1px solid rgba(200,164,90,.28);
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
  }
  #ca-panel header {
    background: linear-gradient(135deg, var(--hf-navy) 0%, var(--hf-navy-2) 65%, var(--hf-navy-3) 100%);
    color: #fff;
    padding: 12px 16px;
    border-bottom: 2px solid var(--hf-gold);
    flex-shrink: 0 !important;
    min-height: 50px !important;
    height: 50px !important;
    box-sizing: border-box !important;
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
  }
  #ca-panel header h2 {
    font-family: Georgia, 'Playfair Display', serif;
    letter-spacing: .3px;
    color: #fff;
    display: flex; align-items: center; gap: 10px;
    font-size: 15px !important;
    margin: 0 !important;
  }
  #ca-panel header .hf-badge {
    font: 600 11px/1 system-ui, sans-serif;
    background: rgba(200,164,90,.22); color: #f6dfad;
    border: 1px solid rgba(200,164,90,.45);
    padding: 4px 9px; border-radius: 999px;
  }
  #ca-panel nav {
    background: var(--ce-surface, #f8fafc) !important;
    padding: 0 8px !important;
    gap: 4px !important;
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    flex-shrink: 0 !important;
    min-height: 48px !important;
    height: 48px !important;
    align-items: center !important;
    overflow-x: auto !important;
    overflow-y: hidden !important;
    white-space: nowrap !important;
    border-bottom: 2px solid var(--hf-gold, #c8a45a) !important;
    scrollbar-width: none !important;
    -webkit-overflow-scrolling: touch !important;
    position: sticky !important;
    top: 0 !important;
    z-index: 25 !important;
    box-sizing: border-box !important;
  }
  #ca-panel nav::-webkit-scrollbar { display: none !important; }
  body.ce-dark-mode #ca-panel nav { background: #0f172a !important; }
  #ca-panel nav button {
    padding: 0 14px !important;
    height: 34px !important;
    line-height: 34px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    border: 1px solid transparent !important;
    flex-shrink: 0 !important;
    white-space: nowrap !important;
    color: var(--ce-muted, #64748b) !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    cursor: pointer !important;
    transition: background .15s, color .15s !important;
    box-sizing: border-box !important;
  }
  #ca-panel nav button.secili {
    color: var(--hf-navy, #0f2341) !important;
    background: var(--hf-gold-soft, #f5ecd9) !important;
    border: 1px solid var(--hf-gold, #c8a45a) !important;
    font-weight: 700 !important;
  }
  body.ce-dark-mode #ca-panel nav button.secili {
    color: #f5d896 !important;
    background: rgba(200,164,90,.22) !important;
    border-color: var(--hf-gold, #c8a45a) !important;
  }
  #ca-panel .ca-icerik {
    flex: 1 1 0% !important;
    min-height: 0 !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    -webkit-overflow-scrolling: touch !important;
    box-sizing: border-box !important;
  }
  #ca-panel .ca-btn.ana {
    background: var(--hf-navy);
    border-color: var(--hf-navy);
    color: #fff;
  }
  #ca-panel .ca-btn.ana:hover:not(:disabled) { background: var(--hf-navy-3); }
  #ca-panel .ca-btn.altin {
    background: var(--hf-gold); border-color: var(--hf-gold); color: #1a1405; font-weight: 600;
  }
  #ca-panel .ca-btn.altin:hover:not(:disabled) { background: var(--hf-gold-2); border-color: var(--hf-gold-2); color: #fff; }
  #ca-panel .ca-btn.kucuk { padding: 5px 10px; font-size: 12px; margin: 2px 4px 2px 0; }
  #ca-panel .ca-hedef { color: var(--hf-navy); }
  body.ce-dark-mode #ca-panel .ca-hedef { color: #f5d896; }
  #ca-panel .hf-alt-nav { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
  #ca-panel .hf-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; margin-top: 12px; }
  #ca-panel .hf-kart {
    border: 1px solid var(--ce-border, #e2e6ec);
    border-radius: 12px; padding: 13px;
    background: var(--ce-surface, #fff);
    display: flex; flex-direction: column; gap: 6px;
    transition: border-color .15s, box-shadow .15s;
  }
  #ca-panel .hf-kart:hover { border-color: var(--hf-gold); box-shadow: 0 6px 20px rgba(15,35,65,.08); }
  #ca-panel .hf-etiket {
    display: inline-block; font-size: 11px; font-weight: 600;
    padding: 2px 8px; border-radius: 999px;
    background: var(--hf-gold-soft); color: var(--hf-gold-2); margin: 0 4px 4px 0;
  }
  body.ce-dark-mode #ca-panel .hf-etiket { background: rgba(200,164,90,.18); color: #f5d896; }
  #ca-panel .hf-etiket.acik { background: #dcfce7; color: #166534; }
  #ca-panel .hf-etiket.kapali { background: #f1f5f9; color: #475569; }
  #ca-panel .hf-iban {
    font-family: ui-monospace, Consolas, monospace; font-size: 12.5px;
    padding: 5px 8px; border-radius: 6px; background: var(--ce-bg, #f6f7fa);
    display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-top: 4px;
  }
  #ca-yuzen {
    background: linear-gradient(135deg, var(--hf-navy), var(--hf-navy-3)) !important;
    color: #fff !important;
    border: 1px solid var(--hf-gold) !important;
    box-shadow: 0 8px 22px rgba(15,35,65,.3) !important;
  }
  #ca-yuzen .ca-sayi { color: #fde047 !important; }
  @media (max-width: 720px) {
    #ca-panel .ca-kutu {
      width: 100vw !important;
      max-height: 100dvh !important;
      height: 100dvh !important;
      border-radius: 0 !important;
      border: 0 !important;
      display: flex !important;
      flex-direction: column !important;
      overflow: hidden !important;
    }
    #ca-panel header {
      flex-shrink: 0 !important;
      min-height: 48px !important;
      height: 48px !important;
      padding: 10px 14px !important;
    }
    #ca-panel nav {
      flex-shrink: 0 !important;
      min-height: 46px !important;
      height: 46px !important;
      padding: 0 6px !important;
      position: sticky !important;
      top: 0 !important;
      z-index: 25 !important;
      display: flex !important;
      flex-direction: row !important;
      flex-wrap: nowrap !important;
      overflow-x: auto !important;
      overflow-y: hidden !important;
      white-space: nowrap !important;
      -webkit-overflow-scrolling: touch !important;
    }
    #ca-panel nav button {
      padding: 0 12px !important;
      height: 32px !important;
      line-height: 32px !important;
      font-size: 12.5px !important;
      flex-shrink: 0 !important;
      white-space: nowrap !important;
      display: inline-flex !important;
      align-items: center !important;
      justify-content: center !important;
    }
    #ca-panel .ca-icerik {
      flex: 1 1 0% !important;
      min-height: 0 !important;
      overflow-y: auto !important;
      overflow-x: hidden !important;
      padding: 12px !important;
      -webkit-overflow-scrolling: touch !important;
    }
    #ca-panel table, #ca-panel tbody, #ca-panel tr, #ca-panel td { display: block; width: 100%; }
    #ca-panel thead { display: none; }
    #ca-panel tr { border: 1px solid var(--ce-border, #e5e8ee); border-radius: 10px; padding: 8px; margin-bottom: 8px; }
    #ca-panel td { border: 0; padding: 3px 0; }
    #ca-yuzen { right: 14px !important; bottom: 16px !important; padding: 10px 14px !important; }
  }
  .hf-tree { list-style: none; padding-left: 0; margin: 8px 0; }
  .hf-tree details { margin-bottom: 6px; border: 1px solid var(--ce-border, #e2e6ec); border-radius: 8px; padding: 6px 10px; background: var(--ce-surface, #fff); transition: all 0.2s ease; }
  .hf-tree details[open] { border-color: var(--hf-gold, #c8a45a); }
  .hf-tree summary { cursor: pointer; font-weight: 600; outline: none; user-select: none; display: flex; align-items: center; justify-content: space-between; }
  .hf-tree-sub { list-style: none; padding-left: 14px; margin: 6px 0 0; border-left: 2px solid var(--hf-gold-soft, #f5ecd9); }
  .hf-tree-item { padding: 5px 8px; border-radius: 6px; margin: 3px 0; cursor: pointer; display: flex; align-items: center; justify-content: space-between; font-size: 13px; }
  .hf-tree-item:hover { background: var(--ce-bg, #f1f5f9); }
  .hf-finans-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-top: 10px; }
  .hf-finans-kart { border: 1px solid var(--ce-border, #e2e6ec); border-radius: 10px; padding: 12px; background: var(--ce-surface, #fff); display: flex; flex-direction: column; gap: 4px; }
  .hf-finans-deger { font-size: 18px; font-weight: 700; color: var(--hf-navy, #0f2341); }
  body.ce-dark-mode .hf-finans-deger { color: #f5d896; }
  .hf-finans-etiket { font-size: 11.5px; color: var(--ce-muted, #64748b); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
  .hf-toplu-bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding: 10px 14px; border-radius: 10px; background: var(--hf-navy, #0f2341); color: #fff; margin: 10px 0; box-shadow: 0 4px 14px rgba(15,35,65,.18); }
  `;

  function stilYukle() {
    if (document.getElementById('ca-hayfa-css') || !document.head) return;
    const s = document.createElement('style');
    s.id = 'ca-hayfa-css';
    s.textContent = HAYFA_CSS;
    document.head.appendChild(s);
  }

  function metinEkleBelgeye(metin, kapatFn) {
    try {
      document.execCommand('insertText', false, metin);
      if (window.showToast) window.showToast('📝 Belgeye eklendi');
    } catch (e) {
      if (navigator.clipboard) navigator.clipboard.writeText(metin);
      if (window.showToast) window.showToast('📋 Panoya kopyalandı');
    }
    if (kapatFn) kapatFn();
  }

  function kopyala(metin) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(metin).then(() => window.showToast && window.showToast('📋 Kopyalandı: ' + metin));
    } else {
      const ta = document.createElement('textarea');
      ta.value = metin; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove();
      if (window.showToast) window.showToast('📋 Kopyalandı');
    }
  }

  function b64ToBytes(b64) {
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }

  function bytesToB64(bytes) {
    let bin = '';
    const u8 = new Uint8Array(bytes);
    const parca = 0x8000;
    for (let i = 0; i < u8.length; i += parca) bin += String.fromCharCode.apply(null, u8.subarray(i, i + parca));
    return btoa(bin);
  }

  async function jarDonusturVeKaydet(ctx, payload, format, paylas) {
    const r = await ctx.api('/api/donustur', { method: 'POST', govde: Object.assign({}, payload, { format, json: true }) });
    const bayt = b64ToBytes(r.icerik_b64);
    if (paylas && navigator.share && window.File) {
      const f = new File([bayt], r.dosya_adi, { type: r.mime });
      if (!navigator.canShare || navigator.canShare({ files: [f] })) {
        await navigator.share({ title: r.dosya_adi, files: [f] });
        return r;
      }
    }
    if (window.saveBytesSmart) {
      await window.saveBytesSmart(bayt, r.dosya_adi, r.mime);
    } else {
      const url = URL.createObjectURL(new Blob([bayt], { type: r.mime }));
      const a = document.createElement('a'); a.href = url; a.download = r.dosya_adi; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    }
    return r;
  }

  // =========================================================================
  // 1. 📁 UYAP DOSYA YÖNETİM MERKEZİ & HESAPLAR & AĞAÇ GÖRÜNÜMÜ
  // =========================================================================
  let dosyaGorunumModu = 'kart'; // 'kart' | 'tablo' | 'agac' | 'hesaplar'

  async function dosyalarSekmesi(ic, ctx) {
    const { api, esc, sunucuHatasi, evrakAc, kapat } = ctx;
    ic.innerHTML = `
      <div class="hf-alt-nav" style="margin-bottom:8px">
        <button class="ca-btn kucuk${dosyaGorunumModu === 'kart' ? ' ana' : ''}" type="button" data-gorunum="kart">🗂️ Kart Görünümü</button>
        <button class="ca-btn kucuk${dosyaGorunumModu === 'tablo' ? ' ana' : ''}" type="button" data-gorunum="tablo">📋 Tablo Görünümü</button>
        <button class="ca-btn kucuk${dosyaGorunumModu === 'agac' ? ' ana' : ''}" type="button" data-gorunum="agac">🌳 Ağaç Görünümü</button>
        <button class="ca-btn kucuk altin${dosyaGorunumModu === 'hesaplar' ? ' ana' : ''}" type="button" data-gorunum="hesaplar">💰 Dosya Hesapları &amp; Masraflar</button>
      </div>

      <div class="ca-satir" style="grid-template-columns:2fr 1fr 1fr 1fr">
        <div><label>Dosya Ara (esas no, mahkeme, müvekkil, taraf)</label><input id="hf-dosya-q" placeholder="ör. 2025/142, Asliye Hukuk, Ahmet..."></div>
        <div><label>Durum</label><select id="hf-dosya-durum"><option value="">Tümü</option><option value="Açık" selected>Açık (Derdest)</option><option value="Kapalı">Kapalı</option></select></div>
        <div><label>Yargı / Mahkeme Türü</label><select id="hf-dosya-tur">
          <option value="">Tümü</option>
          <option value="İcra">İcra Daireleri</option>
          <option value="Ceza">Ceza Mahkemeleri</option>
          <option value="Hukuk">Hukuk Mahkemeleri</option>
          <option value="İdare">İdare / Vergi</option>
          <option value="Yargıtay">BAM / Yargıtay</option>
        </select></div>
        <div><label>Sıralama</label><select id="hf-dosya-sira">
          <option value="yeni">En Yeni Açılan</option>
          <option value="evrak">Evrak Sayısı (Çoktan Aza)</option>
          <option value="esas">Esas Numarası</option>
          <option value="birim">Mahkeme / Birim Adı</option>
        </select></div>
      </div>
      <div id="hf-dosya-govde" style="margin-top:12px"><p class="ca-soluk">Yükleniyor…</p></div>`;

    const qIn = ic.querySelector('#hf-dosya-q');
    const dSel = ic.querySelector('#hf-dosya-durum');
    const turSel = ic.querySelector('#hf-dosya-tur');
    const siraSel = ic.querySelector('#hf-dosya-sira');
    const govde = ic.querySelector('#hf-dosya-govde');
    let zam = null;

    ic.querySelectorAll('[data-gorunum]').forEach(b => {
      b.onclick = () => {
        dosyaGorunumModu = b.dataset.gorunum;
        dosyalarSekmesi(ic, ctx);
      };
    });

    function hesapKarti(h) {
      const yenile = `<button class="ca-btn kucuk" type="button" id="hf-d-hesap-yenile" style="float:right">🔄 UYAP'tan yenile</button>`;
      if (!h || !h.cekildi) {
        return `${yenile}<b>💰 Hesap</b><div class="ca-soluk" style="margin-top:6px">Bu dosyanın hesabı henüz UYAP'tan çekilmedi${h && h.hata ? ' (' + esc(h.hata) + ')' : ''}.</div>`;
      }
      const satir = (ad, deger, renk) => `<tr><td>${ad}</td><td style="text-align:right;white-space:nowrap;${renk ? 'color:' + renk + ';font-weight:700' : ''}">${tl(deger)}</td></tr>`;
      const govdeH = h.is_icra
        ? satir('Asıl alacak (takipte kesinleşen)', h.asil_alacak) + satir('İşlemiş faiz', h.islemis_faiz) + satir('Vekâlet ücreti', h.vekalet_ucreti)
          + satir('Masraf + tahsil harcı', h.masraf_harc) + satir('Toplam alacak', h.toplam_borc, 'var(--hf-navy,#1e3a5f)')
          + satir('Tahsil edilen', h.tahsilat, '#16a34a') + satir('Reddiyat (ödenen)', h.reddiyat) + satir('Kasada bekleyen', h.kasada_bekleyen, '#0284c7')
          + satir('Kalan bakiye', h.kalan_borc, '#dc2626')
        : satir('Yatırılan (tahsilat)', h.tahsilat) + satir('Kullanılan (reddiyat)', h.reddiyat) + satir('Ödenen harçlar', h.masraf_harc)
          + satir('Artan avans (kasada)', h.artan_avans, '#0284c7');
      const kalem = (h.harc_kalemleri || []).length ? `<details style="margin-top:6px"><summary class="ca-soluk">Harç kalemleri (${h.harc_kalemleri.length})</summary><table>${h.harc_kalemleri.map(k => satir(esc(k.ad), k.tutar)).join('')}</table></details>` : '';
      return `${yenile}<b>💰 ${h.is_icra ? 'İcra kapak hesabı' : 'Dosya hesabı'}</b>
        ${h.is_icra && h.kesinlesme ? `<span class="hf-etiket">${esc(h.kesinlesme)}</span>` : ''}
        <table style="margin-top:6px">${govdeH}</table>${kalem}
        ${h.is_icra && (h.borclular || []).length ? `<div class="ca-soluk" style="margin-top:4px">Borçlu: ${esc(h.borclular.join(', '))}</div>` : ''}
        <div class="ca-soluk" style="font-size:11.5px;margin-top:4px">UYAP'tan: ${esc((h.son_guncelleme || '').slice(0, 16))}</div>`;
    }

    async function detayAc(dkey) {
      govde.innerHTML = '<p class="ca-soluk">Dosya ayrıntıları yükleniyor…</p>';
      try {
        const v = await api('/api/dosya/detay?dkey=' + encodeURIComponent(dkey));
        const d = v.dosya || {};
        govde.innerHTML = `
          <button class="ca-btn kucuk" type="button" id="hf-dosya-geri">← Dosya Listesine Dön</button>
          <div class="ca-kart">
            <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;align-items:center">
              <div>
                <span class="hf-etiket ${d.durum === 'Açık' ? 'acik' : 'kapali'}">${esc(d.durum || 'Bilinmiyor')}</span>
                <span class="hf-etiket">${esc(d.yargi || d.dosya_tur || 'UYAP')}</span>
                <h3 style="margin:6px 0 2px">${esc(d.birim || '')} — ${esc(d.dosya_no || '')}</h3>
                <div class="ca-soluk">Müvekkil: <b>${esc(d.muvekkil || '—')}</b> · Açılış: ${esc(d.acilis || '—')} · ${v.evraklar.length} evrak</div>
              </div>
              <div>
                <button class="ca-btn altin kucuk" type="button" id="hf-d-aktar">📋 Notion + TickTick'e Aktar</button>
              </div>
            </div>
            ${v.konu && v.konu.metin ? `<div style="margin-top:8px;padding:8px 10px;border-left:3px solid var(--hf-navy,#1e3a5f);background:rgba(30,58,95,.05)"><b>📌 Dosya konusu</b> <span class="ca-soluk">(${esc(v.konu.kaynak || '')})</span><div style="margin-top:4px;line-height:1.45">${esc(v.konu.metin)}</div></div>` : ''}
            <div id="hf-d-aktar-sonuc" class="ca-soluk"></div>
          </div>

          <div class="hf-detay-iki" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:10px">
            <div class="ca-kart" style="margin:0">
              <b>👥 Taraflar (${(v.taraf_listesi || []).length})</b>
              ${(v.taraf_listesi || []).length ? `<table style="margin-top:6px">${v.taraf_listesi.map(t => `<tr>
                <td>${t.muvekkil ? '<span class="hf-etiket acik">Müvekkil</span> ' : ''}<b>${esc(t.ad)}</b></td>
                <td class="ca-soluk">${esc(t.rol || '')}</td><td class="ca-soluk" style="font-size:12px">${esc(t.vekil || '')}</td></tr>`).join('')}</table>`
                : `<div class="ca-soluk">${esc(d.taraflar || 'Taraf bilgisi henüz çekilmedi.')}</div>`}
            </div>
            <div class="ca-kart" style="margin:0" id="hf-d-hesap">${hesapKarti(v.hesap)}</div>
          </div>

          <div class="ca-kart">
            <b>📝 Dosya Notu Ekle (Yerel + İsteğe Bağlı Notion/TickTick)</b>
            <div class="ca-satir" style="grid-template-columns:1fr 2fr">
              <div><label>Başlık</label><input id="hf-not-baslik" placeholder="ör. Bilirkişi İncelemesi"></div>
              <div><label>Not</label><input id="hf-not-metin" placeholder="Dosya hakkında notunuzu yazın..."></div>
            </div>
            <label style="display:flex;align-items:center;gap:8px;color:inherit;font-size:13px"><input type="checkbox" id="hf-not-sync" style="width:auto" checked> Notion & TickTick'e de otomatik aktar</label>
            <button class="ca-btn ana kucuk" type="button" id="hf-not-kaydet">💾 Notu Kaydet</button>
            <div id="hf-not-liste" style="margin-top:8px">${(v.notlar || []).map(n => `<div style="border-top:1px solid var(--ce-border,#eee);padding:6px 0"><b>${esc(n.baslik)}</b> <span class="ca-soluk">${esc((n.zaman || '').replace('T', ' '))}</span><div>${esc(n.metin)}</div></div>`).join('') || '<span class="ca-soluk">Henüz yerel not yok.</span>'}</div>
          </div>

          ${(v.durusmalar || []).length ? `<div class="ca-kart"><b>🏛️ Duruşmalar</b><table>${v.durusmalar.map(x => `<tr><td>${esc(x.tarih)} ${esc(x.saat || '')}</td><td>${esc(x.aciklama || 'Duruşma')}</td><td class="ca-soluk">${esc(x.yer || '')}</td></tr>`).join('')}</table></div>` : ''}

          <div class="ca-kart">
            <b>🗂️ Dosya Evrakları (${v.evraklar.length})</b>
            <table><thead><tr><th>Tarih</th><th>Evrak</th><th>İşlem</th></tr></thead><tbody>
            ${v.evraklar.map(r => `<tr>
              <td style="white-space:nowrap">${esc((r.tarih || '').slice(0, 10))}</td>
              <td><b>${esc(r.tur || '')}</b>${r.is_ek ? ' <span class="hf-etiket">EK</span>' : ''}<div class="ca-soluk">${esc(r.aciklama || '')}</div></td>
              <td style="white-space:nowrap">
                ${r.yerel ? `<button class="ca-btn kucuk ana" type="button" data-ac="${esc(r.skey)}">Aç</button>
                  <button class="ca-btn kucuk" type="button" data-jar-pdf="${esc(r.skey)}" title="Resmî Havelsan JAR ile PDF">PDF</button>
                  <button class="ca-btn kucuk" type="button" data-jar-docx="${esc(r.skey)}" title="Resmî Havelsan JAR ile Word">DOCX</button>` : '<span class="ca-soluk">indirilmedi</span>'}
                <button class="ca-btn kucuk" type="button" data-aktar-tur="${esc(r.tur || '')}" data-aktar-acik="${esc(r.aciklama || '')}" data-aktar-tar="${esc(r.tarih || '')}">📋</button>
              </td></tr>`).join('')}
            </tbody></table>
          </div>

          ${(v.drive_dosyalar || []).length ? `<div class="ca-kart"><b>☁️ Google Drive'daki Eşleşen Dosyalar (${v.drive_dosyalar.length})</b><table>${v.drive_dosyalar.map(f => `<tr><td>${esc(f.ad)}<div class="ca-soluk">${esc(f.klasor)}</div></td><td><button class="ca-btn kucuk" type="button" data-drive-ac="${esc(f.rel_yol)}">Aç</button></td></tr>`).join('')}</table></div>` : ''}
        `;

        govde.querySelector('#hf-dosya-geri').onclick = listele;
        const hesapBagla = () => {
          const b = govde.querySelector('#hf-d-hesap-yenile');
          if (!b) return;
          b.onclick = async () => {
            b.disabled = true; b.textContent = 'UYAP\'tan çekiliyor…';
            try {
              const r = await api('/api/dosya/hesap_yenile', { method: 'POST', govde: { dkey } });
              govde.querySelector('#hf-d-hesap').innerHTML = hesapKarti(r.hesap);
            } catch (e) { govde.querySelector('#hf-d-hesap').insertAdjacentHTML('beforeend', `<div class="ca-hata">${esc(e.message)}</div>`); }
            hesapBagla();
          };
        };
        hesapBagla();
        govde.querySelector('#hf-d-aktar').onclick = async () => {
          const s = govde.querySelector('#hf-d-aktar-sonuc');
          s.textContent = 'Notion ve TickTick güncelleniyor…';
          try {
            const res = await api('/api/entegrasyon/uyap-aktar', { method: 'POST', govde: { birim: d.birim, dosya_no: d.dosya_no, tur: 'Dosya Takip Güncellemesi', aciklama: d.taraflar || '', muvekkil: d.muvekkil || '' } });
            s.textContent = `✓ Aktarıldı (Notion: ${res.notion ? '✓' : '—'}, TickTick: ${res.ticktick ? '✓' : '—'})${res.hatalar.length ? ' · ' + res.hatalar.join('; ') : ''}`;
          } catch (e) { s.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
        };
        govde.querySelector('#hf-not-kaydet').onclick = async () => {
          const baslik = govde.querySelector('#hf-not-baslik').value.trim() || 'Dosya Notu';
          const metin = govde.querySelector('#hf-not-metin').value.trim();
          if (!metin) return alert('Lütfen not metni girin.');
          try {
            await api('/api/dosya/not', { method: 'POST', govde: { dkey, esas_no: d.dosya_no, birim: d.birim, baslik, metin, senkron_et: govde.querySelector('#hf-not-sync').checked } });
            detayAc(dkey);
          } catch (e) { alert(e.message); }
        };
        govde.querySelectorAll('[data-ac]').forEach(b => { b.onclick = () => evrakAc(b.dataset.ac); });
        govde.querySelectorAll('[data-jar-pdf]').forEach(b => { b.onclick = () => jarDonusturVeKaydet(ctx, { skey: b.dataset.jarPdf }, 'pdf').catch(e => alert(e.message)); });
        govde.querySelectorAll('[data-jar-docx]').forEach(b => { b.onclick = () => jarDonusturVeKaydet(ctx, { skey: b.dataset.jarDocx }, 'docx').catch(e => alert(e.message)); });
        govde.querySelectorAll('[data-aktar-tur]').forEach(b => {
          b.onclick = async () => {
            try {
              const res = await api('/api/entegrasyon/uyap-aktar', { method: 'POST', govde: { birim: d.birim, dosya_no: d.dosya_no, tur: b.dataset.aktarTur, aciklama: b.dataset.aktarAcik, tarih: b.dataset.aktarTar, muvekkil: d.muvekkil || '' } });
              alert(`Aktarıldı!\nNotion: ${res.notion ? '✓' : '—'}\nTickTick: ${res.ticktick ? '✓' : '—'}${res.hatalar.length ? '\nNot: ' + res.hatalar.join('\n') : ''}`);
            } catch (e) { alert(e.message); }
          };
        });
        govde.querySelectorAll('[data-drive-ac]').forEach(b => {
          b.onclick = () => driveDosyaAc(b.dataset.driveAc, ctx);
        });
      } catch (e) { sunucuHatasi(ic, e); }
    }

    window.CanHayfa.detayAc = detayAc;

    async function listele() {
      if (dosyaGorunumModu === 'hesaplar') {
        await listeleHesaplar();
        return;
      }
      govde.innerHTML = '<p class="ca-soluk">Dosyalar yükleniyor…</p>';
      try {
        const v = await api(`/api/dosyalar?limit=250&q=${encodeURIComponent(qIn.value.trim())}&durum=${encodeURIComponent(dSel.value)}`);
        if (!v.hazir) { govde.innerHTML = `<div class="ca-kart">${esc(v.mesaj)}</div>`; return; }

        let dosyalar = (v.dosyalar || []).filter(d => {
          if (!turSel.value) return true;
          return (d.birim || '').toLowerCase().includes(turSel.value.toLowerCase()) ||
                 (d.dosya_tur || '').toLowerCase().includes(turSel.value.toLowerCase());
        });

        const sVal = siraSel.value;
        if (sVal === 'evrak') {
          dosyalar.sort((a, b) => (b.evrak_sayisi || 0) - (a.evrak_sayisi || 0));
        } else if (sVal === 'esas') {
          dosyalar.sort((a, b) => String(a.dosya_no || '').localeCompare(String(b.dosya_no || '')));
        } else if (sVal === 'birim') {
          dosyalar.sort((a, b) => String(a.birim || '').localeCompare(String(b.birim || '')));
        } else {
          dosyalar.sort((a, b) => String(b.acilis || '').localeCompare(String(a.acilis || '')));
        }

        const ozetMetin = `<div class="ca-soluk" style="margin-bottom:8px">Toplam <b>${v.toplam}</b> dosya (<b>${v.acik}</b> açık) · Filtrelenen: <b>${dosyalar.length}</b> dosya</div>`;

        if (dosyaGorunumModu === 'agac') {
          // Ağaç Görünümü: Yargı türü -> Mahkeme/Birim -> Dosyalar
          const gruplar = {};
          for (const d of dosyalar) {
            const b = d.birim || 'Belirtilmemiş';
            let cat = '🏛️ Hukuk Mahkemeleri';
            if (b.includes('Ceza')) cat = '⚖️ Ceza Mahkemeleri';
            else if (b.includes('İcra')) cat = '📜 İcra Daireleri';
            else if (b.includes('İdare') || b.includes('Vergi')) cat = '🏢 İdari Yargı';
            else if (b.includes('Bölge Adliye') || b.includes('Yargıtay')) cat = '⚖️ Üst Yargı / BAM';
            if (!gruplar[cat]) gruplar[cat] = {};
            if (!gruplar[cat][b]) gruplar[cat][b] = [];
            gruplar[cat][b].push(d);
          }

          let treeHtml = ozetMetin + '<div class="hf-tree">';
          for (const [catName, birimler] of Object.entries(gruplar)) {
            const catTotal = Object.values(birimler).reduce((acc, arr) => acc + arr.length, 0);
            treeHtml += `<details open style="margin-bottom:10px">
              <summary style="font-size:14.5px;color:var(--hf-navy)"><span>${esc(catName)}</span> <span class="hf-etiket">${catTotal} dosya</span></summary>
              <div class="hf-tree-sub">`;
            for (const [birimAd, dList] of Object.entries(birimler)) {
              treeHtml += `<details open style="margin:5px 0">
                <summary style="font-size:13.5px"><span>🏛️ ${esc(birimAd)}</span> <span class="ca-soluk">${dList.length} dosya</span></summary>
                <div class="hf-tree-sub">`;
              for (const d of dList) {
                treeHtml += `<div class="hf-tree-item" data-dkey="${esc(d.dkey)}">
                  <div>
                    <span class="hf-etiket ${d.durum === 'Açık' ? 'acik' : 'kapali'}">${esc(d.durum || '—')}</span>
                    <b>${esc(d.dosya_no || '—')}</b>
                    <span class="ca-soluk" style="margin-left:6px">${esc(d.muvekkil || d.taraflar || '').slice(0, 45)}</span>
                  </div>
                  <span class="hf-etiket">${d.evrak_sayisi || 0} evrak</span>
                </div>`;
              }
              treeHtml += `</div></details>`;
            }
            treeHtml += `</div></details>`;
          }
          treeHtml += '</div>';
          govde.innerHTML = treeHtml;
        } else if (dosyaGorunumModu === 'tablo') {
          // Tablo Görünümü
          govde.innerHTML = ozetMetin + `
            <div class="ca-kart" style="overflow-x:auto">
              <table>
                <thead>
                  <tr>
                    <th>Durum</th>
                    <th>Mahkeme / Birim</th>
                    <th>Esas No</th>
                    <th>Müvekkil / Karşı Taraf</th>
                    <th>Açılış</th>
                    <th>Evrak</th>
                    <th>İşlem</th>
                  </tr>
                </thead>
                <tbody>
                  ${dosyalar.map(d => `
                    <tr>
                      <td><span class="hf-etiket ${d.durum === 'Açık' ? 'acik' : 'kapali'}">${esc(d.durum || '—')}</span></td>
                      <td><b>${esc(d.birim || '—')}</b></td>
                      <td style="font-weight:700;color:var(--hf-navy)">${esc(d.dosya_no || '—')}</td>
                      <td>${esc(d.muvekkil || d.taraflar || '—')}</td>
                      <td style="white-space:nowrap">${esc(d.acilis || '—')}</td>
                      <td><span class="hf-etiket">${d.evrak_sayisi || 0}</span></td>
                      <td><button class="ca-btn kucuk ana" type="button" data-dkey="${esc(d.dkey)}">Detay</button></td>
                    </tr>
                  `).join('') || '<tr><td colspan="7" class="ca-soluk">Eşleşen dosya bulunamadı.</td></tr>'}
                </tbody>
              </table>
            </div>`;
        } else {
          // Kart Görünümü (varsayılan)
          govde.innerHTML = ozetMetin + `<div class="hf-grid">${dosyalar.map(d => `
            <div class="hf-kart" style="cursor:pointer" data-dkey="${esc(d.dkey)}">
              <div><span class="hf-etiket ${d.durum === 'Açık' ? 'acik' : 'kapali'}">${esc(d.durum || '—')}</span><span class="hf-etiket">${d.evrak_sayisi || 0} evrak</span></div>
              <b>${esc(d.birim || 'Birim belirtilmedi')}</b>
              <div style="font-size:15px;font-weight:700;color:var(--hf-navy)">${esc(d.dosya_no || '—')}</div>
              <div class="ca-soluk">${esc(d.muvekkil || d.taraflar || '').slice(0, 90)}</div>
            </div>`).join('') || '<p class="ca-soluk">Eşleşen dosya bulunamadı.</p>'}</div>`;
        }

        govde.querySelectorAll('[data-dkey]').forEach(k => { k.onclick = () => (window.CanPencere ? window.CanPencere.dosya(k.dataset.dkey) : detayAc(k.dataset.dkey)); });
      } catch (e) { sunucuHatasi(ic, e); }
    }

    const tl = n => (n === null || n === undefined) ? '—' : '₺' + Number(n || 0).toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    // Kesinleşme (ödeme/icra emri tebliği + itiraz süresi, tensip/karar kayıtları) ve takipsizlik (son talep/işlem
    // tarihi) analizi: icra_analiz.py. Kesinleştirilebilir dosyalar ve 1 yılı yaklaşan/aşan dosyalar en üstte.
    async function icraAnalizCiz(kap) {
      if (!kap) return;
      try {
        const a = await api('/api/icra/analiz');
        const o = a.ozet || {};
        const KC = { kesin: ['#dcfce7', '#166534', 'Kesinleşmiş'], kesinlestirilebilir: ['#ffedd5', '#9a3412', 'Kesinleştirilebilir'], sure_isliyor: ['#dbeafe', '#1e40af', 'Süre işliyor'],
          itiraz: ['#fee2e2', '#991b1b', 'İtiraz'], teblig_bekleniyor: ['#fef9c3', '#854d0e', 'Tebliğ bekleniyor'], bilinmiyor: ['#f1f5f9', '#475569', 'Bilinmiyor'] };
        const TC = { kirmizi: ['#fee2e2', '#991b1b'], turuncu: ['#ffedd5', '#9a3412'], sari: ['#fef9c3', '#854d0e'], yesil: ['#dcfce7', '#166534'], kapali: ['#f1f5f9', '#475569'], bilinmiyor: ['#f1f5f9', '#475569'] };
        const cip = (r, y) => `<span style="background:${r[0]};color:${r[1]};padding:1px 8px;border-radius:999px;font-size:11.5px;font-weight:600;white-space:nowrap">${y}</span>`;
        const l = a.dosyalar || [];
        kap.innerHTML = `<b>⚖️ İcra takip uyarıları</b>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin:8px 0">
            ${cip(KC.kesinlestirilebilir, `${o.kesinlestirilebilir || 0} kesinleştirilebilir`)} ${cip(TC.kirmizi, `${o.kirmizi || 0} dosya 1 yılı aştı`)}
            ${cip(TC.turuncu, `${o.turuncu || 0} dosya 9-12 ay işlemsiz`)} ${cip(TC.sari, `${o.sari || 0} dosya 6-9 ay işlemsiz`)}
            ${cip(KC.itiraz, `${o.itiraz || 0} itirazlı`)} ${cip(KC.kesin, `${o.kesin || 0} kesinleşmiş`)} <span class="ca-soluk">${o.toplam || 0} açık icra dosyası</span></div>
          ${l.length ? `<div style="max-height:420px;overflow:auto"><table>${l.filter(x => x.kesinlesme.durum !== 'kesin' || ['kirmizi', 'turuncu', 'sari'].includes(x.takipsizlik.seviye)).slice(0, 200).map(x => `
            <tr data-dkey="${esc(x.dkey)}" style="cursor:pointer"><td><b>${esc(x.birim)}</b><div style="font-weight:700">${esc(x.dosya_no)}</div><div class="ca-soluk">${esc((x.borclular || []).join(', '))}</div></td>
            <td>${cip(KC[x.kesinlesme.durum] || KC.bilinmiyor, KC[x.kesinlesme.durum] ? KC[x.kesinlesme.durum][2] : x.kesinlesme.durum)}<div style="font-size:12.5px;margin-top:3px">${esc(x.kesinlesme.aciklama || x.kesinlesme.baslik)}</div></td>
            <td>${cip(TC[x.takipsizlik.seviye] || TC.bilinmiyor, x.takipsizlik.gun != null ? x.takipsizlik.gun + ' gün' : '—')}<div class="ca-soluk" style="font-size:12px;margin-top:3px">${esc(x.takipsizlik.aciklama)}</div></td></tr>`).join('')}</table></div>`
          : '<p class="ca-soluk">Açık icra dosyası bulunamadı (katalog taranınca görünür).</p>'}
          <p class="ca-soluk" style="font-size:11.5px">Kaynak: UYAP safahatı, evraklar (tensip/karar/talep), tebligat mazbataları ve UYAP borçlu kesinleşme bilgisi. İtiraz süreleri: ilamsız 7 gün (İİK 62), kambiyo 5 gün (İİK 168/5), icra emri 7 gün. Somut dosyada mutlaka kontrol edin.</p>`;
        kap.querySelectorAll('[data-dkey]').forEach(k => { k.onclick = () => window.CanPencere && window.CanPencere.dosya(k.dataset.dkey); });
      } catch (e) { kap.innerHTML = `<b>⚖️ İcra takip uyarıları</b><div class="ca-hata">${esc(e.message)}</div>`; }
    }

    async function listeleHesaplar() {
      govde.innerHTML = '<p class="ca-soluk">Dosya hesapları yükleniyor…</p>';
      try {
        const v = await api(`/api/dosya/hesaplar?q=${encodeURIComponent(qIn.value.trim())}&dosya_tur=${encodeURIComponent(turSel.value)}&durum=${encodeURIComponent(dSel.value)}`);
        if (!v.hazir) { govde.innerHTML = `<div class="ca-kart">${esc(v.mesaj || 'Katalog hazır değil.')}</div>`; return; }
        const st = v.istatistik || {};
        const hs = v.hesaplar || [];
        const icra = hs.filter(h => h.is_icra);
        const dava = hs.filter(h => !h.is_icra);
        const satirIcra = h => `<tr data-dkey="${esc(h.dkey)}" style="cursor:pointer">
            <td><b>${esc(h.birim || '')}</b><div style="font-weight:700;color:var(--hf-navy)">${esc(h.dosya_no || '')}</div>
              <div class="ca-soluk">${esc((h.borclular || []).join(', ') || h.muvekkil || '')}</div></td>
            ${h.cekildi ? `<td>${tl(h.asil_alacak)}</td><td>${tl(h.islemis_faiz)}</td><td>${tl(h.vekalet_ucreti)}</td><td>${tl(h.masraf_harc)}</td>
            <td style="font-weight:700">${tl(h.toplam_borc)}</td><td style="color:#16a34a">${tl(h.tahsilat)}</td>
            <td style="font-weight:700;color:#dc2626">${tl(h.kalan_borc)}</td><td class="ca-soluk">${esc(h.kesinlesme || '')}</td>`
            : `<td colspan="8" class="ca-soluk">Hesap henüz UYAP'tan çekilmedi${h.hata ? ' · ' + esc(h.hata) : ''}</td>`}
          </tr>`;
        const satirDava = h => `<tr data-dkey="${esc(h.dkey)}" style="cursor:pointer">
            <td><span class="hf-etiket ${h.durum === 'Açık' ? 'acik' : 'kapali'}">${esc(h.durum || '—')}</span> <b>${esc(h.birim || '')}</b>
              <div style="font-weight:700;color:var(--hf-navy)">${esc(h.dosya_no || '')}</div><div class="ca-soluk">${esc(h.muvekkil || '')}</div></td>
            ${h.cekildi ? `<td>${tl(h.tahsilat)}</td><td>${tl(h.reddiyat)}</td><td>${tl(h.masraf_harc)}
              ${(h.harc_kalemleri || []).length ? `<div class="ca-soluk" style="font-size:11.5px">${h.harc_kalemleri.slice(0, 4).map(k => esc(k.ad) + ': ' + tl(k.tutar)).join('<br>')}</div>` : ''}</td>
              <td style="font-weight:700;color:#0284c7">${tl(h.artan_avans)}</td>`
            : `<td colspan="4" class="ca-soluk">Hesap henüz UYAP'tan çekilmedi${h.hata ? ' · ' + esc(h.hata) : ''}</td>`}
          </tr>`;
        govde.innerHTML = `
          <div class="hf-finans-grid">
            <div class="hf-finans-kart"><span class="hf-finans-etiket">📜 İcra: toplam alacak</span>
              <span class="hf-finans-deger">${tl(st.toplam_alacak)}</span><span class="ca-soluk">${st.icra_dosya || 0} icra dosyası</span></div>
            <div class="hf-finans-kart"><span class="hf-finans-etiket">💰 İcra: tahsil edilen</span>
              <span class="hf-finans-deger" style="color:#16a34a">${tl(st.toplam_tahsilat)}</span><span class="ca-soluk">Oran: <b>%${st.tahsilat_yuzdesi || 0}</b> · Kalan ${tl(st.kalan_alacak)}</span></div>
            <div class="hf-finans-kart"><span class="hf-finans-etiket">🏦 Davalarda artan avans</span>
              <span class="hf-finans-deger" style="color:#0284c7">${tl(st.toplam_avans)}</span><span class="ca-soluk">${st.avansli_dosya || 0} dosyada kasada para var</span></div>
            <div class="hf-finans-kart"><span class="hf-finans-etiket">🧾 Ödenen harçlar</span>
              <span class="hf-finans-deger">${tl(st.toplam_harc)}</span><span class="ca-soluk">Hesabı çekilen: ${st.hesabi_cekilen || 0}/${st.toplam_dosya || 0}</span></div>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 6px;align-items:center">
            <button class="ca-btn kucuk altin" type="button" id="hf-fin-cek">🔄 Hesapları UYAP'tan çek</button>
            <button class="ca-btn kucuk" type="button" id="hf-fin-csv">📊 CSV indir</button>
            <span class="ca-soluk" id="hf-fin-durum">${st.hesabi_bekleyen ? `${st.hesabi_bekleyen} dosyanın hesabı henüz çekilmedi; Senkron açıkken boşta otomatik çekilir.` : 'Tüm dosyaların hesabı çekildi.'}</span>
          </div>
          <div class="ca-kart" id="hf-icra-analiz"><b>⚖️ İcra takip uyarıları</b> <span class="ca-soluk">yükleniyor…</span></div>
          ${icra.length ? `<div class="ca-kart" style="overflow-x:auto"><b>📜 İcra dosyaları (${icra.length})</b><table>
            <thead><tr><th>Dosya / Borçlu</th><th>Asıl alacak</th><th>Faiz</th><th>Vekâlet</th><th>Masraf+harç</th><th>Toplam</th><th>Tahsilat</th><th>Bakiye</th><th>Durum</th></tr></thead>
            <tbody>${icra.map(satirIcra).join('')}</tbody></table></div>` : `<div class="ca-kart ca-soluk">Listede icra dosyası yok. Katalog icra dairelerini de tarar; Senkron'u bir tur çalıştırın.</div>`}
          ${dava.length ? `<div class="ca-kart" style="overflow-x:auto"><b>⚖️ Dava dosyaları (${dava.length})</b><table>
            <thead><tr><th>Dosya</th><th>Yatırılan (tahsilat)</th><th>Kullanılan (reddiyat)</th><th>Harçlar</th><th>Artan avans</th></tr></thead>
            <tbody>${dava.map(satirDava).join('')}</tbody></table></div>` : ''}`;

        icraAnalizCiz(govde.querySelector('#hf-icra-analiz'));
        govde.querySelectorAll('[data-dkey]').forEach(k => { k.onclick = () => (window.CanPencere ? window.CanPencere.dosya(k.dataset.dkey) : detayAc(k.dataset.dkey)); });
        govde.querySelector('#hf-fin-cek').onclick = async () => {
          const d = govde.querySelector('#hf-fin-durum');
          try { await api('/api/gorev/hesap-tara', { method: 'POST', govde: {} }); d.textContent = 'Hesaplar arka planda çekiliyor (gizli UYAP oturumuyla). Birkaç dakika sonra yenileyin.'; }
          catch (e) { d.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
        };
        govde.querySelector('#hf-fin-csv').onclick = () => {
          const q = x => `"${String(x ?? '').replace(/"/g, '""')}"`;
          const n = x => (x === null || x === undefined) ? '' : String(x).replace('.', ',');
          const bas = ['Tür', 'Birim', 'Dosya No', 'Müvekkil', 'Durum', 'Asıl Alacak', 'Faiz', 'Vekalet', 'Masraf+Harç', 'Toplam', 'Tahsilat', 'Reddiyat', 'Bakiye', 'Artan Avans', 'Son Güncelleme'];
          const sat = hs.map(h => [h.is_icra ? 'İcra' : 'Dava', q(h.birim), q(h.dosya_no), q(h.muvekkil), q(h.durum), n(h.asil_alacak), n(h.islemis_faiz), n(h.vekalet_ucreti), n(h.masraf_harc), n(h.toplam_borc), n(h.tahsilat), n(h.reddiyat), n(h.kalan_borc), n(h.artan_avans), q(h.son_guncelleme)].join(';'));
          const blob = new Blob(['﻿' + [bas.join(';'), ...sat].join('\r\n')], { type: 'text/csv;charset=utf-8;' });
          const link = document.createElement('a');
          link.href = URL.createObjectURL(blob);
          link.download = `Dosya_Hesaplari_${new Date().toISOString().slice(0, 10)}.csv`;
          link.click();
        };
      } catch (e) { sunucuHatasi(ic, e); }
    }

    qIn.addEventListener('input', () => { clearTimeout(zam); zam = setTimeout(listele, 320); });
    dSel.onchange = listele;
    turSel.onchange = listele;
    siraSel.onchange = listele;
    listele();
  }

  // =========================================================================
  // 2. ☁️ GOOGLE DRIVE EŞİTLEME & VERİTABANI İNDEKSİ
  // =========================================================================
  async function driveDosyaAc(rel, ctx) {
    try {
      // "gdrive:<id>" kayıtları Google Drive'dan (Apps Script "get") indirilir; diğerleri yerel klasörden
      const bulut = String(rel).startsWith('gdrive:');
      const r = await ctx.api(bulut ? '/api/drive/dosya?id=' + encodeURIComponent(rel.slice(7)) : '/api/drive/dosya?rel=' + encodeURIComponent(rel), { ham: true });
      const buf = await r.arrayBuffer();
      const cd = r.headers && r.headers.get ? (r.headers.get('Content-Disposition') || '') : '';
      const m = /filename\*?=(?:UTF-8'')?"?([^";]+)/i.exec(cd);
      const ad = (m ? decodeURIComponent(m[1]) : '') || rel.split('/').pop() || 'DriveDosyasi';
      ctx.kapat();
      if (window.openDocumentFromBytes) await window.openDocumentFromBytes(buf, ad);
      else if (window.openPdfViewer) await window.openPdfViewer(buf, ad);
    } catch (e) { alert('Drive dosyası açılamadı: ' + e.message); }
  }

  async function driveProSekmesi(ic, ctx) {
    const { api, esc, sunucuHatasi } = ctx;
    ic.innerHTML = '<p class="ca-soluk">Google Drive durumu yükleniyor…</p>';
    try {
      const v = await api('/api/drive');
      const a = v.ayar || {}, idx = v.indeks || {}, k = v.katalog || {}, n = v.nobetci, kl = v.klasor;
      const tarih = t => t ? esc(String(t).replace('T', ' ').slice(0, 16)) : '—';
      const durum = !v.yapilandirildi ? '⚪ Yapılandırılmadı' : (v.mod === 'webhook' ? '🟢 Bulut Webhook' : (v.dizin_var ? (v.yazilabilir ? '🟢 Bağlı ve Yazılabilir' : '🟠 Salt Okunur') : '🔴 Klasör Erişilemiyor'));

      ic.innerHTML = `
        <div class="ca-kart">
          <div class="ca-hedef" style="font-size:18px">${durum}</div>
          <table>
            <tr><th>Klasör / Mod</th><td><code>${esc(v.dizin || a.google_drive_webhook || '—')}</code></td></tr>
            ${kl ? `<tr><th>Disk Özeti</th><td>${kl.dosya.toLocaleString('tr-TR')}${kl.tam_sayim ? '' : '+'} dosya · ${kl.boyut_mb.toLocaleString('tr-TR')} MB · son: ${tarih(kl.son_degisiklik)}</td></tr>` : ''}
            <tr><th>Drive Veritabanı İndeksi</th><td>${idx.hazir ? `<b>${idx.toplam.toLocaleString('tr-TR')}</b> dosya (${idx.boyut_mb.toLocaleString('tr-TR')} MB) · son indeks: ${tarih(idx.son_indeks)}` : 'Henüz indekslenmedi'}</td></tr>
            <tr><th>Katalog Yedeği</th><td>${v.yedek ? tarih(v.yedek.zaman) + ' · ' + v.yedek.boyut_mb + ' MB' : '—'}</td></tr>
            ${k.indirilen !== undefined ? `<tr><th>UYAP Kataloğu</th><td>${k.indirilen.toLocaleString('tr-TR')} indirildi · ${k.indirilmeyi_bekleyen.toLocaleString('tr-TR')} bekliyor${k.driveda_olmayan != null ? ` · <b>${k.driveda_olmayan.toLocaleString('tr-TR')}</b> Drive'a aktarılacak` : ''}</td></tr>` : ''}
            ${v.mod === 'webhook' && v.yukleme ? `<tr><th>Drive'a Yüklenen</th><td><b>${v.yukleme.drivede.toLocaleString('tr-TR')}</b> / ${v.yukleme.indirilen.toLocaleString('tr-TR')} evrak${v.yukleme.indirilen > v.yukleme.drivede ? ` · <b>${(v.yukleme.indirilen - v.yukleme.drivede).toLocaleString('tr-TR')}</b> yüklenecek` : ' ✓ tamamı Drive\'da'}${v.yukleme.son_yukleme ? ' · son: ' + tarih(v.yukleme.son_yukleme) : ''}</td></tr>` : ''}
            <tr><th>Nöbetçi Son Tur</th><td>${n ? `${tarih(n.son_tur)} (${n.dakika_once} dk önce) ${n.gecikti ? '🔴' : '🟢'}` : '—'}</td></tr>
          </table>
          ${(v.uyarilar || []).map(u => `<div class="ca-uyari">⚠️ ${esc(u)}</div>`).join('')}
          <div style="margin-top:8px">
            <button class="ca-btn ana" type="button" id="hf-drv-esitle">☁️ Eksikleri Drive'a Eşitle</button>
            <button class="ca-btn altin" type="button" id="hf-drv-indeks">🗄️ Drive'ı Veritabanına İndeksle</button>
            <button class="ca-btn" type="button" id="hf-drv-yenile">↻ Yenile</button>
            ${v.mod === 'webhook' ? '<button class="ca-btn" type="button" id="hf-drv-kopya" title="UYAP_Arsiv içinde aynı ad ve boyuttaki kopyaları çöp kutusuna taşır (30 gün geri alınabilir)">🧹 Drive\'daki kopyaları temizle</button>' : ''}
          </div>
          <div id="hf-drv-ilerleme" style="display:none;margin-top:10px">
            <div style="height:10px;border-radius:6px;background:rgba(100,116,139,.18);overflow:hidden"><div id="hf-drv-bar" style="height:100%;width:0;background:var(--hf-gold,#c8a45a);transition:width .4s"></div></div>
          </div>
          <div id="hf-drv-islem" class="ca-soluk" style="margin-top:6px"></div>
        </div>

        <div class="ca-kart">
          <b>🔍 Google Drive Veritabanında Ara</b>
          <div class="ca-satir" style="grid-template-columns:2fr 1fr">
            <div><input id="hf-drv-q" placeholder="Dosya adı, mahkeme, esas no (ör. 2025/104, bilirkişi)..."></div>
            <div><select id="hf-drv-uz"><option value="">Tüm uzantılar</option><option value="pdf">PDF</option><option value="udf">UDF</option><option value="docx">DOCX</option><option value="tif">TIF</option></select></div>
          </div>
          <div id="hf-drv-sonuc" class="ca-soluk" style="margin-top:8px">Aramak için yazın veya önce Drive'ı veritabanına indeksleyin.</div>
        </div>

        <details class="ca-kart" id="hf-cfg-detay">
          <summary style="cursor:pointer;font-weight:600">⚙️ Google Drive &amp; Telegram Ayarları</summary>
          <div class="ca-satir" style="margin-top:8px">
            <div>
              <label>Yerel Google Drive Klasörü</label>
              <input id="hf-cfg-dir" value="${esc(a.google_drive_dir || '')}" placeholder="Bilgisayarda G:\\Drive'ım\\UYAP_Arsiv (Telefonda boş bırakın)">
              <small class="ca-soluk" style="display:block;margin-top:3px;font-size:11px">
                📱 <b>Telefonda boş bırakın</b> ve aşağıya Apps Script Webhook (/exec) adresini girin: Drive'a yükleme ve Drive'ın tamamını indeksleme bu adres üzerinden yapılır.
              </small>
            </div>
            <div>
              <label>Bulut Webhook URL (Android / Uzak)</label>
              <input id="hf-cfg-wh" value="${esc(a.google_drive_webhook || '')}" placeholder="https://script.google.com/macros/s/.../exec">
              <small class="ca-soluk" style="display:block;margin-top:3px;font-size:11px">
                ☁️ Google Apps Script Web Uygulaması bağlantısı (sonu <code>/exec</code> ile biter).
              </small>
            </div>
            <div><label>Telegram Bot Token</label><input id="hf-cfg-tg" type="password" placeholder="${a.telegram_token_var ? '•••• (kayıtlı)' : 'isteğe bağlı'}"></div>
            <div><label>Telegram Chat ID</label><input id="hf-cfg-chat" value="${esc(a.telegram_chat_id || '')}" placeholder="ör. 123456789"></div>
          </div>

          <div id="hf-cfg-wh-uyari" style="display:none;margin-top:8px;padding:9px 12px;border-radius:8px;background:#fef2f2;border:1px solid #f87171;color:#991b1b;font-size:12.5px;line-height:1.4"></div>
          <div id="hf-cfg-dir-uyari" style="display:none;margin-top:8px;padding:9px 12px;border-radius:8px;background:#fffbeb;border:1px solid #f59e0b;color:#92400e;font-size:12.5px;line-height:1.4"></div>

          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">
            <button class="ca-btn ana" type="button" id="hf-cfg-kaydet">💾 Ayarları Kaydet</button>
            <button class="ca-btn" type="button" id="hf-cfg-test-wh">🧪 Webhook Bağlantısını Test Et</button>
            <button class="ca-btn altin" type="button" id="hf-cfg-kopyala-gs">📋 Google Apps Script Kodunu Kopyala</button>
          </div>
          <div id="hf-cfg-bildirim" class="ca-soluk" style="margin-top:6px"></div>
          <label style="display:flex;gap:8px;align-items:center;color:inherit;font-size:13px;margin-top:10px"><input type="checkbox" id="hf-cfg-auto" style="width:auto"${a.drive_auto_index !== false ? ' checked' : ''}> Her nöbetçi turunda Drive veritabanını otomatik güncelle</label>
        </details>

        <details class="ca-kart" style="background:var(--hf-gold-soft,#f5ecd9);border:1px solid var(--hf-gold,#c8a45a)">
          <summary style="cursor:pointer;font-weight:700;color:var(--hf-navy,#0f2341)">📖 Telefonda Google Drive Kurulum Kılavuzu (Adım Adım — 1 Dakika)</summary>
          <div style="margin-top:8px;font-size:13px;line-height:1.6;color:#1e293b">
            <p style="margin:4px 0"><b>1. Adım:</b> Yukarıdaki <b>"📋 Google Apps Script Kodunu Kopyala"</b> düğmesine basın.</p>
            <p style="margin:4px 0"><b>2. Adım:</b> Telefon tarayıcınızda (Chrome vb.) <b><a href="https://script.google.com" target="_blank" style="color:#2563eb;font-weight:600;text-decoration:underline">script.google.com</a></b> açıp sol üstteki <b>"+ Yeni proje"</b> butonuna dokunun.</p>
            <p style="margin:4px 0"><b>3. Adım:</b> Ekrandaki örnek kodları silin, kopyaladığınız kodu yapıştırın ve üstteki disket (💾 Kaydet) simgesine dokunun.</p>
            <p style="margin:4px 0;padding:8px;background:rgba(255,255,255,.8);border-radius:6px;border-left:4px solid #ef4444">
              <b>⚠️ EN ÖNEMLİ NOKTA ("Paylaş" DEĞİL, "Dağıt"):</b><br>
              ❌ Sağ üstteki <i>"Paylaş"</i> (veya <i>"Share"</i>) butonu sadece projeyi düzenleme davetidir (<code>/edit?usp=sharing</code> ile biter) ve UYAP evraklarını <b>kabul etmez!</b><br>
              ✅ Sağ üstteki mavi <b>"Dağıt (Deploy)"</b> butonuna dokunun → <b>"Yeni dağıtım"</b> seçin.<br>
              • Sol üstteki dişli ⚙️ simgesinden <b>"Web uygulaması"</b> seçin.<br>
              • <i>Uygulamayı şu kullanıcı olarak çalıştır:</i> <b>Ben</b><br>
              • <i>Erişimi olanlar (Who has access):</i> <b>Mutlaka "Herkes" (Anyone)</b> seçin.<br>
              • Mavi <b>"Dağıt"</b> butonuna basın ve Google hesabınızın erişim izinlerini onaylayın.<br>
              • Ekrana gelen <b>"Web uygulaması URL'si"</b>ni kopyalayın (<code>https://script.google.com/macros/s/.../exec</code> ile biter).
            </p>
            <p style="margin:4px 0"><b>4. Adım:</b> Kopyaladığınız <code>.../exec</code> URL'sini yukarıdaki <b>"Bulut Webhook URL"</b> kutusuna yapıştırıp <b>"💾 Ayarları Kaydet"</b> deyin.</p>
            <p style="margin:4px 0"><b>📁 Klasör Kutusu:</b> <i>"Yerel Google Drive Klasörü"</i> kutusunu telefonunuzda <b>boş bırakın</b>. İndirilen evraklar otomatik olarak telefonunuzun <code>/sdcard/Download/UYAP_Arsiv</code> klasöründe tutulur ve oradan Google Drive'ınıza yüklenir.</p>
          </div>
        </details>`;

      const islem = ic.querySelector('#hf-drv-islem');
      const whInput = ic.querySelector('#hf-cfg-wh');
      const whUyari = ic.querySelector('#hf-cfg-wh-uyari');
      const dirInput = ic.querySelector('#hf-cfg-dir');
      const dirUyari = ic.querySelector('#hf-cfg-dir-uyari');
      const bildirim = ic.querySelector('#hf-cfg-bildirim');

      function linkKontrol() {
        if (!whInput) return;
        const v = whInput.value.trim();
        if (v && (v.includes('/edit') || v.includes('usp=sharing') || (v.includes('/d/') && !v.endsWith('/exec')))) {
          whUyari.style.display = 'block';
          whUyari.innerHTML = '⚠️ <b>Dikkat:</b> Girdiğiniz link bir düzenleme/paylaşım linkidir (<code>.../edit</code>). Google Drive webhook için Google Apps Script ekranında sağ üstteki mavi <b>"Dağıt (Deploy)" &gt; "Yeni dağıtım" &gt; "Web uygulaması" &gt; "Herkes"</b> adımlarını uygulayıp aldığınız <code>.../exec</code> ile biten linki yapıştırmalısınız.';
        } else {
          whUyari.style.display = 'none';
        }

        const d = dirInput ? dirInput.value.trim() : '';
        if (d && (d.startsWith('http://') || d.startsWith('https://'))) {
          dirUyari.style.display = 'block';
          dirUyari.innerHTML = 'ℹ️ <b>Bilgi:</b> "Yerel Google Drive Klasörü" kutusuna internet linki girilemez. Bilgisayarda klasör yolu (ör. G:\\Drive\'ım\\UYAP_Arsiv) içindir. Telefonda bu kutuyu <b>boş bırakabilirsiniz</b> (evraklar otomatik olarak <code>/sdcard/Download/UYAP_Arsiv</code> konumuna kaydedilir). İnternet linkini yandaki <b>Bulut Webhook URL</b> kutusuna yapıştırınız.';
        } else {
          dirUyari.style.display = 'none';
        }
      }
      if (whInput) whInput.addEventListener('input', linkKontrol);
      if (dirInput) dirInput.addEventListener('input', linkKontrol);
      linkKontrol();

      const kopyalaGsBtn = ic.querySelector('#hf-cfg-kopyala-gs');
      if (kopyalaGsBtn) {
        kopyalaGsBtn.onclick = async () => {
          try {
            await navigator.clipboard.writeText(GOOGLE_APPS_SCRIPT_KODU);
            if (bildirim) bildirim.innerHTML = '<span style="color:#16a34a;font-weight:600">✓ Google Apps Script kodu panoya kopyalandı! script.google.com adresine yapıştırabilirsiniz.</span>';
          } catch (e) {
            prompt('Aşağıdaki kodu kopyalayıp script.google.com adresine yapıştırın:', GOOGLE_APPS_SCRIPT_KODU);
          }
        };
      }

      const testWhBtn = ic.querySelector('#hf-cfg-test-wh');
      if (testWhBtn) {
        testWhBtn.onclick = async () => {
          const wh = whInput ? whInput.value.trim() : '';
          if (!wh) {
            if (bildirim) bildirim.innerHTML = '<span class="ca-hata">Lütfen önce bir Webhook URL girin.</span>';
            return;
          }
          if (wh.includes('/edit') || wh.includes('usp=sharing')) {
            if (bildirim) bildirim.innerHTML = '<span class="ca-hata">Girdiğiniz link paylaşım linkidir (/edit). Lütfen "Dağıt &gt; Web Uygulaması" linkini (/exec) kullanın.</span>';
            return;
          }
          if (bildirim) bildirim.textContent = '⏳ Webhook bağlantısı test ediliyor…';
          try {
            const r = await api('/api/drive/test_webhook', { method: 'POST', govde: { url: wh } });
            if (bildirim) bildirim.innerHTML = `<span style="color:#16a34a;font-weight:600">${esc(r.mesaj || '✓ Webhook başarılı!')}</span>`;
          } catch (e) {
            if (bildirim) bildirim.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`;
          }
        };
      }

      ic.querySelector('#hf-drv-yenile').onclick = () => driveProSekmesi(ic, ctx);
      // Drive indeksleme: bilgisayarda yerel klasör hemen taranır; telefonda Drive'ın tamamı Apps Script ile
      // arka planda sayfa sayfa okunur (on binlerce dosya birkaç dakika sürebilir) ve ilerleme gösterilir.
      const indeksSonucuYaz = r => {
        islem.textContent = `✓ İndekslendi${r.kaynak ? ' (' + r.kaynak + ')' : ''}: ${r.toplam.toLocaleString('tr-TR')} dosya (${r.boyut_mb.toLocaleString('tr-TR')} MB) · +${r.yeni} yeni, ${r.guncellenen} güncellendi, ${r.silinen} silindi (${Math.round(r.sure_ms / 1000)} sn)`;
      };
      const indeksIzle = async () => {
        for (;;) {
          const d = await api('/api/drive/indeks_durum');
          if (d.calisiyor) {
            islem.textContent = `⏳ Google Drive okunuyor… ${d.okunan.toLocaleString('tr-TR')} dosya (${d.sayfa} sayfa, ${d.gecen_sn} sn). Paneli kapatabilirsiniz, arka planda sürer.`;
            await new Promise(r => setTimeout(r, 2500));
            if (!document.body.contains(islem)) return;
            continue;
          }
          if (d.hata) { islem.innerHTML = `<span class="ca-hata">${esc(d.hata)}</span>`; return; }
          if (d.sonuc) { indeksSonucuYaz(d.sonuc); driveAra(); }
          return;
        }
      };
      ic.querySelector('#hf-drv-indeks').onclick = async () => {
        islem.textContent = '⏳ Google Drive taranıyor…';
        try {
          const wh = whInput ? whInput.value.trim() : '';
          const r = await api('/api/drive/indeksle', { method: 'POST', govde: wh ? { webhook: wh } : {} });
          if (r.arkaplan) { await indeksIzle(); } else { indeksSonucuYaz(r); driveAra(); }
        } catch (e) { islem.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
      };
      // Sekme açıldığında süren bir indeksleme varsa ilerlemesini göster
      api('/api/drive/indeks_durum').then(d => { if (d && d.calisiyor) indeksIzle(); }).catch(() => {});
      // Drive eşitleme: arka planda, canlı ilerleme çubuğu ve dosya adıyla; panel kapansa da sürer.
      const bar = ic.querySelector('#hf-drv-bar'), barKutu = ic.querySelector('#hf-drv-ilerleme');
      const esitleIzle = async () => {
        barKutu.style.display = 'block';
        for (;;) {
          let d;
          try { d = await api('/api/drive/esitle_durum'); } catch (e) { islem.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; return; }
          const yuzde = d.toplam ? Math.round(100 * d.islenen / d.toplam) : (d.calisiyor ? 2 : 100);
          bar.style.width = yuzde + '%';
          const hataSatiri = (d.hatalar || []).length ? `<div class="ca-hata" style="margin-top:4px">${d.hatalar.map(esc).join('<br>')}</div>` : '';
          if (d.calisiyor) {
            islem.innerHTML = `⏳ Drive'a yükleniyor: <b>${d.islenen}</b> / ${d.toplam} (%${yuzde}) · ✓ ${d.aktarilan} yüklendi · ${d.atlanan} zaten vardı · ${d.hata} hata<br><span class="ca-soluk">${esc(d.son_dosya || '')} · ${d.gecen_sn} sn</span>${hataSatiri}`;
            await new Promise(r => setTimeout(r, 2000));
            if (!document.body.contains(islem)) return;
            continue;
          }
          if (d.mesaj) { islem.innerHTML = `<span class="ca-hata">${esc(d.mesaj)}</span>`; return; }
          const o = d.ozet || {};
          islem.innerHTML = `✓ Eşitleme bitti (${d.gecen_sn} sn): <b>${d.aktarilan}</b> yeni yüklendi, ${d.atlanan} zaten Drive'daydı, ${d.hata} hata.`
            + (o.indirilen ? ` Drive'da şu an <b>${(o.drivede || 0).toLocaleString('tr-TR')}</b> / ${o.indirilen.toLocaleString('tr-TR')} evrak.` : '') + hataSatiri;
          return;
        }
      };
      ic.querySelector('#hf-drv-esitle').onclick = async () => {
        islem.textContent = '⏳ Eşitleme başlatılıyor…';
        try {
          await api('/api/drive/esitle', { method: 'POST', govde: {} });
          await esitleIzle();
        } catch (e) { islem.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
      };
      api('/api/drive/esitle_durum').then(d => { if (d && d.calisiyor) esitleIzle(); }).catch(() => {});
      const kopyaBtn = ic.querySelector('#hf-drv-kopya');
      if (kopyaBtn) kopyaBtn.onclick = async () => {
        if (!confirm("UYAP_Arsiv içindeki, aynı klasörde aynı ad ve boyuttaki kopya dosyalar Google Drive çöp kutusuna taşınacak (en eskisi kalır, 30 gün içinde geri alınabilir). Devam edilsin mi?")) return;
        islem.textContent = '⏳ Drive\'daki kopyalar taranıyor… (büyük arşivlerde birkaç dakika sürebilir)';
        try {
          const r = await api('/api/drive/kopya_temizle', { method: 'POST', govde: {} });
          islem.textContent = `✓ ${r.tasinan.toLocaleString('tr-TR')} kopya dosya çöp kutusuna taşındı.`;
        } catch (e) { islem.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
      };
      ic.querySelector('#hf-cfg-kaydet').onclick = async () => {
        let dirVal = ic.querySelector('#hf-cfg-dir').value.trim();
        let whVal = ic.querySelector('#hf-cfg-wh').value.trim();
        if (dirVal && (dirVal.startsWith('http://') || dirVal.startsWith('https://'))) {
          if (!whVal) whVal = dirVal;
          dirVal = '';
        }
        const g = {
          google_drive_dir: dirVal,
          google_drive_webhook: whVal,
          telegram_chat_id: ic.querySelector('#hf-cfg-chat').value.trim(),
          drive_auto_index: ic.querySelector('#hf-cfg-auto').checked
        };
        const tg = ic.querySelector('#hf-cfg-tg').value.trim();
        if (tg) g.telegram_token = tg;
        try {
          await api('/api/drive/ayar', { method: 'POST', govde: g });
          if (window.showToast) window.showToast('✓ Drive & Telegram ayarları kaydedildi');
          driveProSekmesi(ic, ctx);
        } catch (e) {
          alert(e.message);
        }
      };

      const dq = ic.querySelector('#hf-drv-q'), du = ic.querySelector('#hf-drv-uz'), dson = ic.querySelector('#hf-drv-sonuc');
      let dzam = null;
      const driveAra = async () => {
        try {
          const r = await api(`/api/drive/ara?limit=80&q=${encodeURIComponent(dq.value.trim())}&uzanti=${encodeURIComponent(du.value)}`);
          if (!r.hazir) { dson.textContent = r.mesaj; return; }
          dson.innerHTML = `<div class="ca-soluk">${r.sonuclar.length} sonuç (indekste ${r.toplam.toLocaleString('tr-TR')} dosya)</div>
            <table>${r.sonuclar.map(f => `<tr>
              <td><b>${esc(f.ad)}</b><div class="ca-soluk">${esc(f.klasor)}${f.esas_no ? ' · Esas: ' + esc(f.esas_no) : ''}</div></td>
              <td style="white-space:nowrap">${(f.boyut / 1024).toFixed(0)} KB</td>
              <td style="white-space:nowrap">
                <button class="ca-btn kucuk ana" type="button" data-dac="${esc(f.rel_yol)}">Aç</button>
                ${f.url ? `<a class="ca-btn kucuk" href="${esc(f.url)}" target="_blank" rel="noopener">Drive'da</a>` : ''}
                ${f.uzanti === 'udf' ? `<button class="ca-btn kucuk" type="button" data-dpdf="${esc(f.rel_yol)}">JAR PDF</button>` : ''}
              </td></tr>`).join('')}</table>`;
          dson.querySelectorAll('[data-dac]').forEach(b => { b.onclick = () => driveDosyaAc(b.dataset.dac, ctx); });
          dson.querySelectorAll('[data-dpdf]').forEach(b => { b.onclick = () => jarDonusturVeKaydet(ctx, { drive_rel: b.dataset.dpdf }, 'pdf').catch(e => alert(e.message)); });
        } catch (e) { dson.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
      };
      dq.addEventListener('input', () => { clearTimeout(dzam); dzam = setTimeout(driveAra, 300); });
      du.onchange = driveAra;
      if (idx.hazir) driveAra();
    } catch (e) { sunucuHatasi(ic, e); }
  }

  // =========================================================================
  // 3. 📋 NOTION & TICKTICK CANLI ENTEGRASYON
  // =========================================================================
  let entAlt = null;
  // AYAR YEDEĞİ: anahtarları bir kez girin. Yedek şifresi belirlendiyse her değişiklikten sonra şifreli yedek
  // Drive'ınıza (Apps Script webhook) ve masaüstünde ~/CanEditor/ altına yazılır; yeni kurulumda tek adımda geri gelir.
  async function ayarYedekKarti(kap, ctx) {
    const api = ctx.api, esc = ctx.esc;
    let v;
    try { v = await api('/api/ayar/yedek'); } catch (e) { kap.innerHTML = `<div class="ca-kart ca-hata">${esc(e.message)}</div>`; return; }
    const son = v.son || {};
    const geriH = `<div class="ca-kart" style="border:2px solid #c8a45a">
        <b>♻️ Ayarlarınızı geri yükleyin</b>
        <p class="ca-soluk" style="margin:4px 0">Daha önce yedek aldıysanız tüm anahtarlar (Notion, TickTick, Telegram, Gmail, UETS, Drive, UYAP) tek adımda gelir.</p>
        <div class="ca-satir">
          <div><label>Yedek şifresi</label><input id="ay-g-sifre" type="password" placeholder="yedeği alırken belirlediğiniz şifre"></div>
          <div><label>Drive webhook (Apps Script /exec) — buluttan alırken</label><input id="ay-g-webhook" placeholder="https://script.google.com/macros/s/…/exec"></div>
        </div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">
          ${v.yerel_yedek ? `<button class="ca-btn ana" type="button" data-g="yerel">💻 Bu cihazdaki yedekten (${esc(v.yerel_zaman)})</button>` : ''}
          <button class="ca-btn${v.yerel_yedek ? '' : ' ana'}" type="button" data-g="bulut">☁️ Google Drive'dan</button>
          <label class="ca-btn" style="cursor:pointer;margin:0">📁 Dosyadan (.cnayar)<input id="ay-g-dosya" type="file" hidden></label>
        </div><div id="ay-g-sonuc" style="margin-top:6px"></div></div>`;
    const yedekH = `<div class="ca-kart">
        <b>🔐 Ayar yedeği</b> ${v.sifre_kayitli ? '<span class="hf-etiket acik">Otomatik yedek açık</span>' : '<span class="hf-etiket kapali">Kapalı</span>'}
        <p class="ca-soluk" style="margin:4px 0">${v.sifre_kayitli
          ? `Her ayar değişikliğinden sonra şifreli yedek ${v.webhook_var ? 'Google Drive\'ınıza (UYAP_Arsiv/_CanEditor_Ayar)' : ''}${v.webhook_var && v.yerel_yedek !== null ? ' ve ' : ''}${v.yerel_yedek ? 'bu bilgisayarda ' + esc(v.yerel_yedek) : ''} yenilenir.${v.webhook_var ? '' : ' Drive webhook girilirse buluta da yedeklenir.'}`
          : 'Bir yedek şifresi belirleyin: anahtarlar şifrelenip Drive\'ınıza ve bu bilgisayara yedeklenir; yeni kurulumda yalnızca bu şifreyle geri gelir.'}
          ${son.zaman ? `<br>Son yedek: ${esc(son.zaman)}${son.bulut ? ' · ☁️ Drive' : ''}${son.yerel ? ' · 💻 yerel' : ''}${(son.hata || []).length ? ` · <span class="ca-hata">${esc(son.hata.join('; '))}</span>` : ''}` : ''}</p>
        <div class="ca-satir"><div><label>${v.sifre_kayitli ? 'Yedek şifresini değiştir' : 'Yedek şifresi (en az 6 karakter)'}</label><input id="ay-sifre" type="password" placeholder="unutmayacağınız bir şifre"></div></div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">
          <button class="ca-btn ana" type="button" id="ay-kaydet">${v.sifre_kayitli ? '🔁 Şifreyi değiştir ve yedekle' : '✅ Otomatik yedeği aç'}</button>
          ${v.sifre_kayitli ? '<button class="ca-btn" type="button" id="ay-simdi">☁️ Şimdi yedekle</button>' : ''}
          <button class="ca-btn" type="button" id="ay-disa">💾 Yedeği dosyaya kaydet</button>
          <label style="font-size:12.5px;display:flex;align-items:center;gap:4px"><input type="checkbox" id="ay-pin"> e-İmza PIN'i de dahil et</label>
        </div><div id="ay-sonuc" style="margin-top:6px"></div></div>`;
    kap.innerHTML = (v.bos_kurulum ? geriH + yedekH : yedekH + `<details><summary class="ca-soluk" style="cursor:pointer">♻️ Başka bir yedekten geri yükle</summary>${geriH}</details>`);
    const yaz = (id, h) => { const el = kap.querySelector(id); if (el) el.innerHTML = h; };
    const geri = async (kaynak, icerik) => {
      const sifre = kap.querySelector('#ay-g-sifre').value;
      if (!sifre) return yaz('#ay-g-sonuc', '<span class="ca-hata">Yedek şifresini girin.</span>');
      yaz('#ay-g-sonuc', 'Geri yükleniyor…');
      try {
        const r = await api('/api/ayar/yedek/geri', { method: 'POST', govde: { kaynak, sifre, icerik, webhook: kap.querySelector('#ay-g-webhook').value.trim(), hatirla: true } });
        yaz('#ay-g-sonuc', `<span style="color:#166534;font-weight:600">✓ Geri yüklendi: ${r.sayi.anahtar} anahtar, ${r.sayi.drive} Drive ayarı, ${r.sayi.uyap} UYAP ayarı${r.sayi.pin ? ', e-İmza PIN' : ''}. Otomatik yedek açık.</span>`);
        setTimeout(() => ctx.yenile && ctx.yenile(), 1500);
      } catch (e) { yaz('#ay-g-sonuc', `<span class="ca-hata">${esc(e.message)}</span>`); }
    };
    kap.querySelectorAll('[data-g]').forEach(b => { b.onclick = () => geri(b.dataset.g); });
    const df = kap.querySelector('#ay-g-dosya');
    if (df) df.onchange = async () => {
      const f = df.files[0]; if (!f) return;
      const u8 = new Uint8Array(await f.arrayBuffer());
      let b = ''; for (let i = 0; i < u8.length; i += 0x8000) b += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
      df.value = ''; // yanlış şifreden sonra aynı dosya yeniden seçilebilsin
      geri('dosya', btoa(b));
    };
    kap.querySelector('#ay-kaydet').onclick = async () => {
      const sifre = kap.querySelector('#ay-sifre').value;
      yaz('#ay-sonuc', 'Kaydediliyor ve yedekleniyor…');
      try { const r = await api('/api/ayar/yedek/sifre', { method: 'POST', govde: { sifre } });
        yaz('#ay-sonuc', `<span style="color:#166534;font-weight:600">✓ Otomatik yedek açık.${r.yedek.bulut ? ' Drive\'a yüklendi.' : ''}${r.yedek.yerel ? ' Yerel: ' + esc(r.yedek.yerel) : ''}</span>${(r.yedek.hata || []).length ? `<div class="ca-hata">${esc(r.yedek.hata.join('; '))}</div>` : ''}`);
        setTimeout(() => ayarYedekKarti(kap, ctx), 2500);
      } catch (e) { yaz('#ay-sonuc', `<span class="ca-hata">${esc(e.message)}</span>`); }
    };
    const sm = kap.querySelector('#ay-simdi');
    if (sm) sm.onclick = async () => {
      yaz('#ay-sonuc', 'Yedekleniyor…');
      try { const r = await api('/api/ayar/yedek/simdi', { method: 'POST', govde: {} }); yaz('#ay-sonuc', `✓ ${esc(r.zaman)}${r.bulut ? ' · ☁️ Drive' : ''}${r.yerel ? ' · 💻 yerel' : ''}${(r.hata || []).length ? ` <span class="ca-hata">${esc(r.hata.join('; '))}</span>` : ''}`); }
      catch (e) { yaz('#ay-sonuc', `<span class="ca-hata">${esc(e.message)}</span>`); }
    };
    kap.querySelector('#ay-disa').onclick = async () => {
      try {
        const r = await api('/api/ayar/yedek/disa', { method: 'POST', govde: { sifre: kap.querySelector('#ay-sifre').value, pin: kap.querySelector('#ay-pin').checked }, ham: true });
        const buf = new Uint8Array(await r.arrayBuffer());
        const ad = `CanEditor-ayar-yedegi-${new Date().toISOString().slice(0, 10)}.cnayar`;
        if (window.saveBytesSmart) await window.saveBytesSmart(buf, ad, 'application/json');
        else { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([buf])); a.download = ad; a.click(); }
        yaz('#ay-sonuc', '✓ Yedek dosyası kaydedildi. Telefona/USB\'ye koyabilirsiniz; şifresiz açılamaz.');
      } catch (e) { yaz('#ay-sonuc', `<span class="ca-hata">${esc(e.message === 'HTTP 400' ? 'Önce yedek şifresi belirleyin ya da kutuya yazın.' : e.message)}</span>`); }
    };
  }
  window.CanAyarYedek = ayarYedekKarti;

  async function entegrasyonSekmesi(ic, ctx) {
    const { api, esc, sunucuHatasi } = ctx;
    ic.innerHTML = '<p class="ca-soluk">Entegrasyon durumu yükleniyor…</p>';
    let ayar;
    try { ayar = await api('/api/entegrasyon/ayar'); } catch (e) { sunucuHatasi(ic, e); return; }
    // Hiçbir servis bağlı değilse doğrudan anahtar girme ekranı açılır (boş "anahtar girilmemiş" sayfası yerine)
    if (!entAlt) entAlt = (ayar.ticktick_bagli || ayar.notion_bagli) ? 'duzen' : 'ayar';

    ic.innerHTML = `
      <div class="hf-alt-nav">
        <button class="ca-btn${entAlt === 'duzen' ? ' ana' : ''}" type="button" data-ea="duzen">🧹 Düzen & Durum</button>
        <button class="ca-btn${entAlt === 'ticktick' ? ' ana' : ''}" type="button" data-ea="ticktick">✅ TickTick Görevleri ${ayar.ticktick_bagli ? '🟢' : '⚪'}</button>
        <button class="ca-btn${entAlt === 'notion' ? ' ana' : ''}" type="button" data-ea="notion">📓 Notion Dosyaları ${ayar.notion_bagli ? '🟢' : '⚪'}</button>
        <button class="ca-btn${entAlt === 'ayar' ? ' ana' : ''}" type="button" data-ea="ayar">🔑 API Anahtarları & Otomatik Senkron</button>
      </div>
      <div id="hf-ent-ic"></div>`;
    ic.querySelectorAll('[data-ea]').forEach(b => { b.onclick = () => { entAlt = b.dataset.ea; entegrasyonSekmesi(ic, ctx); }; });
    const alan = ic.querySelector('#hf-ent-ic');

    if (entAlt === 'duzen') {
      // Tek ekran: TickTick temizliği (mükerrer: aktif + tamamlanan + yapılmayacak; eksik tebligat; dosya kartları)
      // ve UYAP → Notion eşitleme. Canlı günlük, son sonuç sayıları; ikisi de 6 saatte bir kendiliğinden çalışır.
      const kartH = (k, baslik, aciklama) => `<div class="ca-kart" data-gk="${k}"><div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap">
          <b>${baslik}</b><span><span class="hf-d-r"></span> <button class="ca-btn ana kucuk" type="button" data-calistir="${k}">▶ Şimdi çalıştır</button></span></div>
        <p class="ca-soluk" style="margin:4px 0">${aciklama}</p><div class="hf-d-sonuc"></div>
        <pre class="hf-d-log" style="max-height:220px;overflow:auto;background:#0f172a;color:#e2e8f0;padding:8px;border-radius:6px;font-size:11px;white-space:pre-wrap;margin-top:6px"></pre></div>`;
      alan.innerHTML = kartH('ticktick-duzen', '🧹 TickTick temizliği ve düzeni', 'Mükerrerleri aktif, tamamlanan ve <b>yapılmayacak</b> görevlerin tamamına bakarak kapatır (silmez; notlar ve alt görevler asıl göreve taşınır), eksik tebligatları işaretler, Notion\'daki her açık dosyaya kart açar ve dosya konusunu yazar.')
        + kartH('notion-esitle', '📒 UYAP → Notion eşitleme', 'Eksik dosyaları açar; açılış tarihi, durum, müvekkil ve karşı taraf bağlarını, ikonları ve 5-10 cümlelik dosya konusunu yazar. Elle yazdığınız konu ezilmez.');
      const sonucMetin = (k, r) => !r ? '' : k === 'ticktick-duzen'
        ? `Son tur: <b>${r.kapatilan ?? 0}</b> kopya kapatıldı · <b>${r.yeni_kart ?? 0}</b> dosya kartı açıldı · <b>${r.eksik ?? 0}</b> eksik görev · ${r.kapali_sayisi ?? '?'} kapalı görev (${r.yapilmayacak_sayisi ?? '?'} yapılmayacak) denetlendi`
        : `Son tur: <b>${r.yeni_dosya ?? 0}</b> yeni dosya · <b>${r.konu ?? 0}</b> konu · <b>${(r.muvekkil_bag ?? 0) + (r.karsi_bag ?? 0)}</b> taraf bağı · ${r.ikon ?? 0} ikon${r.engel ? ` · <span class="ca-hata">${esc(r.engel)}</span>` : ''}`;
      const tazele = async () => {
        if (!document.body.contains(alan)) return clearInterval(zz);
        try {
          const v = await api('/api/gorevler?satir=120');
          for (const g of v.gorevler.filter(x => x.kimlik === 'ticktick-duzen' || x.kimlik === 'notion-esitle')) {
            const el = alan.querySelector(`[data-gk="${g.kimlik}"]`); if (!el) continue;
            el.querySelector('.hf-d-r').innerHTML = g.calisiyor ? '<span class="hf-etiket acik">● Çalışıyor</span>' : g.kod === 0 ? '<span class="hf-etiket">✓ Tamam</span>' : g.kod ? `<span class="hf-etiket kapali">Hata (${g.kod})</span>` : '';
            const b = el.querySelector('[data-calistir]'); b.disabled = !!g.calisiyor;
            const satirlar = (g.gunluk || []).filter(x => !x.includes('@@SONUC@@'));
            const pre = el.querySelector('pre'); const altta = pre.scrollHeight - pre.scrollTop - pre.clientHeight < 24; const ust = pre.scrollTop;
            const m = satirlar.join('\n'); if (pre.textContent !== m) { pre.textContent = m || 'Henüz çalışmadı.'; pre.scrollTop = altta ? pre.scrollHeight : ust; }
            const sx = (g.gunluk || []).filter(x => x.includes('@@SONUC@@')).slice(-1)[0];
            if (sx) { try { el.querySelector('.hf-d-sonuc').innerHTML = sonucMetin(g.kimlik, JSON.parse(sx.split('@@SONUC@@')[1])); } catch (e) { /* */ } }
          }
        } catch (e) { /* bağlantı anlık kopabilir */ }
      };
      alan.onclick = async e => {
        const b = e.target.closest('[data-calistir]'); if (!b) return;
        b.disabled = true;
        try { await api('/api/gorev/' + b.dataset.calistir, { method: 'POST', govde: {} }); } catch (er) { alert(er.message); }
        tazele();
      };
      const zz = setInterval(tazele, 3000); tazele();
      return;
    }

    if (entAlt === 'ayar') {
      alan.innerHTML = `<div id="ay-yedek"></div><div class="ca-kart">
        <b>🔐 Yerel API Yapılandırması (yalnızca bu cihazdaki .env dosyasına 0600 izniyle yazılır)</b>
        <div class="ca-satir">
          <div><label>Notion API Token</label><input id="hf-e-nt" type="password" placeholder="${ayar.notion_bagli ? esc(ayar.notion_token) + ' (kayıtlı)' : 'ntn_...'}"></div>
          <div><label>Notion Dosyalar Veritabanı ID</label><input id="hf-e-ndb" value="${esc(ayar.notion_db || '')}"></div>
          <div><label>TickTick API Token</label><input id="hf-e-tt" type="password" placeholder="${ayar.ticktick_bagli ? esc(ayar.ticktick_token) + ' (kayıtlı)' : 'tp_...'}"></div>
          <div><label>Telegram Bot Token</label><input id="hf-e-tg" type="password" placeholder="${ayar.telegram_bagli ? '•••• (kayıtlı)' : 'isteğe bağlı'}"></div>
          <div><label>Telegram Chat ID</label><input id="hf-e-chat" value="${esc(ayar.telegram_chat_id || '')}"></div>
          <div><label>UETS T.C. Kimlik No</label><input id="hf-e-uets-tc" placeholder="${ayar.uets_bagli ? esc(ayar.uets_tckn) + ' (kayıtlı)' : 'isteğe bağlı'}"></div>
          <div><label>UETS Şifre</label><input id="hf-e-uets-pw" type="password" placeholder="${ayar.uets_bagli ? '•••• (kayıtlı)' : 'isteğe bağlı'}"></div>
          <div><label>Gmail adresi (UETS giriş kodu buraya gelir)</label><input id="hf-e-gm-u" placeholder="${ayar.gmail_bagli ? esc(ayar.gmail_user) + ' (kayıtlı)' : 'ornek@gmail.com'}"></div>
          <div><label>Gmail Uygulama Şifresi</label><input id="hf-e-gm-p" type="password" placeholder="${ayar.gmail_bagli ? '•••• (kayıtlı)' : '16 haneli uygulama şifresi'}">
            <small class="ca-soluk" style="display:block;font-size:11px">Google Hesabı → Güvenlik → 2 Adımlı Doğrulama → Uygulama şifreleri. Girilmezse giriş kodunu Tebligatlar sekmesinden elle yazarsınız.</small></div>
          <div><label>Dosya özeti için yapay zekâ anahtarı (isteğe bağlı)</label><input id="hf-e-oz-k" type="password" placeholder="${ayar.ozet_bagli ? esc(ayar.ozet_api_key) + ' (kayıtlı)' : 'boş bırakılırsa özet evraklardan çıkarılır'}">
            <small class="ca-soluk" style="display:block;font-size:11px">Her dosyanın 5-10 cümlelik konusu Notion "DOSYA KONUSU" sütununa ve TickTick dosya kartına yazılır. Elle yazdığınız konu asla ezilmez.</small></div>
          <div><label>Yapay zekâ sağlayıcısı / model</label><div style="display:flex;gap:6px"><select id="hf-e-oz-s" style="flex:1">
            <option value="anthropic"${ayar.ozet_saglayici !== 'openai' ? ' selected' : ''}>Claude (Anthropic)</option>
            <option value="openai"${ayar.ozet_saglayici === 'openai' ? ' selected' : ''}>OpenAI</option></select>
            <input id="hf-e-oz-m" style="flex:1" placeholder="model (varsayılan)" value="${esc(ayar.ozet_model || '')}"></div></div>
        </div>
        <label style="display:flex;gap:8px;align-items:center;color:inherit;font-size:14px"><input type="checkbox" id="hf-e-oto" style="width:auto"${ayar.otomatik_senkron ? ' checked' : ''}> UYAP'a yeni evrak/tebligat düşünce Notion & TickTick'e otomatik aktar</label>
        <button class="ca-btn ana" type="button" id="hf-e-kaydet">💾 Kaydet</button>
        <button class="ca-btn" type="button" id="hf-e-test">🧪 Bağlantıları test et</button>
        <span id="hf-e-msg" class="ca-soluk"></span>
        <div id="hf-e-test-sonuc" style="margin-top:10px"></div></div>`;
      ayarYedekKarti(alan.querySelector('#ay-yedek'), Object.assign({}, ctx, { yenile: () => entegrasyonSekmesi(ic, ctx) }));
      alan.querySelector('#hf-e-kaydet').onclick = async () => {
        const g = {
          notion_token: alan.querySelector('#hf-e-nt').value.trim(),
          notion_db: alan.querySelector('#hf-e-ndb').value.trim(),
          ticktick_token: alan.querySelector('#hf-e-tt').value.trim(),
          telegram_bot_token: alan.querySelector('#hf-e-tg').value.trim(),
          telegram_chat_id: alan.querySelector('#hf-e-chat').value.trim(),
          uets_tckn: alan.querySelector('#hf-e-uets-tc').value.trim(),
          uets_password: alan.querySelector('#hf-e-uets-pw').value.trim(),
          gmail_user: alan.querySelector('#hf-e-gm-u').value.trim(),
          gmail_app_pass: alan.querySelector('#hf-e-gm-p').value.replace(/\s+/g, ''),
          ozet_api_key: alan.querySelector('#hf-e-oz-k').value.trim(),
          ozet_saglayici: alan.querySelector('#hf-e-oz-s').value,
          ozet_model: alan.querySelector('#hf-e-oz-m').value.trim(),
          otomatik_senkron: alan.querySelector('#hf-e-oto').checked
        };
        const msg = alan.querySelector('#hf-e-msg');
        msg.textContent = 'Kaydediliyor…';
        try {
          await api('/api/entegrasyon/ayar', { method: 'POST', govde: g });
          if (window.showToast) window.showToast('✓ API anahtarları kaydedildi');
          entegrasyonSekmesi(ic, ctx);
        } catch (e) { msg.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
      };
      alan.querySelector('#hf-e-test').onclick = async () => {
        const kutu = alan.querySelector('#hf-e-test-sonuc');
        kutu.innerHTML = '<span class="ca-soluk">⏳ Notion, TickTick ve Telegram deneniyor…</span>';
        try {
          const r = await api('/api/entegrasyon/test', { method: 'POST', govde: {} });
          const ad = { notion: 'Notion', ticktick: 'TickTick', telegram: 'Telegram' };
          const simge = { ok: '🟢', hata: '🔴', yok: '⚪' };
          kutu.innerHTML = '<table>' + Object.keys(ad).map(k => {
            const v = r[k] || { durum: 'yok', mesaj: '' };
            return `<tr><th>${simge[v.durum] || '⚪'} ${ad[k]}</th><td>${esc(v.mesaj)}</td></tr>`;
          }).join('') + '</table>';
        } catch (e) { kutu.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
      };
      return;
    }

    if (entAlt === 'notion') {
      if (!ayar.notion_bagli) { alan.innerHTML = '<div class="ca-kart">Notion API anahtarı henüz girilmemiş. <b>API Anahtarları</b> sekmesinden ekleyin.</div>'; return; }
      alan.innerHTML = `<div class="ca-satir" style="grid-template-columns:2fr auto">
        <input id="hf-n-q" placeholder="Notion dosyalarında ara (mahkeme, esas, müvekkil, durum)...">
        <button class="ca-btn" type="button" id="hf-n-yenile">↻ Yenile</button>
      </div><div id="hf-n-sonuc" style="margin-top:10px" class="ca-soluk">Notion dosyaları yükleniyor…</div>`;
      const nq = alan.querySelector('#hf-n-q'), nson = alan.querySelector('#hf-n-sonuc');
      const yukle = async (yenile) => {
        nson.innerHTML = '<span class="ca-soluk">Notion sorgulanıyor…</span>';
        try {
          const v = await api(`/api/notion/dosyalar?limit=100&q=${encodeURIComponent(nq.value.trim())}${yenile ? '&yenile=1' : ''}`);
          nson.innerHTML = `<div class="ca-soluk">Toplam ${v.toplam} dava · Gösterilen: ${v.dosyalar.length}</div>
            <table><thead><tr><th>Dosya</th><th>Müvekkil / Durum</th><th>Duruşma / Tebligat</th><th>İşlem</th></tr></thead><tbody>
            ${v.dosyalar.map(d => `<tr>
              <td><b>${esc(d.baslik)}</b><div class="ca-soluk">${esc(d.konu || '')}</div></td>
              <td>${esc(d.muvekkil || '—')}<div class="ca-soluk">${esc(d.durum || '')}</div></td>
              <td class="ca-soluk">${d.durusma ? '📅 ' + esc(d.durusma) + '<br>' : ''}${d.son_tebligat ? '📨 ' + esc(d.son_tebligat) : '—'}</td>
              <td style="white-space:nowrap">
                <button class="ca-btn kucuk ana" type="button" data-nnot="${esc(d.page_id)}" data-nbas="${esc(d.baslik)}">📝 Not Ekle</button>
                ${d.url ? `<a class="ca-btn kucuk" href="${esc(d.url)}" target="_blank" rel="noopener">↗</a>` : ''}
              </td></tr>`).join('')}</tbody></table>`;
          nson.querySelectorAll('[data-nnot]').forEach(b => {
            b.onclick = async () => {
              const metin = prompt(b.dataset.nbas + ' — Notion sayfasına eklenecek not:');
              if (!metin) return;
              try { await api('/api/notion/not', { method: 'POST', govde: { page_id: b.dataset.nnot, baslik: 'CanEditor Notu', metin } }); alert('✓ Notion sayfasına eklendi!'); }
              catch (e) { alert(e.message); }
            };
          });
        } catch (e) { nson.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
      };
      let nzam = null;
      nq.addEventListener('input', () => { clearTimeout(nzam); nzam = setTimeout(() => yukle(false), 320); });
      alan.querySelector('#hf-n-yenile').onclick = () => yukle(true);
      yukle(false);
      return;
    }

    // TickTick
    if (!ayar.ticktick_bagli) { alan.innerHTML = '<div class="ca-kart">TickTick API anahtarı henüz girilmemiş. <b>API Anahtarları</b> sekmesinden ekleyin.</div>'; return; }
    alan.innerHTML = '<p class="ca-soluk">TickTick görevleri yükleniyor…</p>';
    try {
      const v = await api('/api/ticktick/gorevler?limit=80');
      alan.innerHTML = `
        <div class="ca-kart">
          <b>➕ Yeni TickTick Görevi Ekle</b>
          <div class="ca-satir" style="grid-template-columns:2fr 1fr 1fr">
            <div><label>Başlık</label><input id="hf-tt-bas" placeholder="ör. 2025/142 Bilirkişi itiraz dilekçesi"></div>
            <div><label>Liste</label><select id="hf-tt-pid">${(v.projeler || []).map(p => `<option value="${esc(p.id)}">${esc(p.ad)}</option>`).join('')}</select></div>
            <div><label>Son Gün</label><input id="hf-tt-tar" type="date"></div>
          </div>
          <button class="ca-btn ana kucuk" type="button" id="hf-tt-ekle">➕ Görev Oluştur</button>
        </div>
        <div class="ca-kart">
          <b>Aktif Görevler (${v.gorevler.length})</b>
          <table><thead><tr><th>Görev</th><th>Liste</th><th>Son Tarih</th><th></th></tr></thead><tbody>
          ${v.gorevler.map(t => `<tr>
            <td><b>${esc(t.baslik)}</b>${t.icerik ? `<div class="ca-soluk">${esc(t.icerik.slice(0, 140))}</div>` : ''}</td>
            <td><span class="hf-etiket">${esc(t.proje)}</span></td>
            <td style="white-space:nowrap">${esc((t.son_tarih || '—').slice(0, 10))}</td>
            <td><button class="ca-btn kucuk" type="button" data-tt-done="${esc(t.id)}" data-tt-pid="${esc(t.project_id)}">✓ Bitir</button></td>
          </tr>`).join('') || '<tr><td colspan="4" class="ca-soluk">Aktif görev bulunamadı.</td></tr>'}</tbody></table>
        </div>`;
      alan.querySelector('#hf-tt-ekle').onclick = async () => {
        const baslik = alan.querySelector('#hf-tt-bas').value.trim();
        if (!baslik) return alert('Başlık girin.');
        try {
          await api('/api/ticktick/ekle', { method: 'POST', govde: { baslik, project_id: alan.querySelector('#hf-tt-pid').value, son_tarih: alan.querySelector('#hf-tt-tar').value } });
          entegrasyonSekmesi(ic, ctx);
        } catch (e) { alert(e.message); }
      };
      alan.querySelectorAll('[data-tt-done]').forEach(b => {
        b.onclick = async () => {
          if (!confirm('Bu TickTick görevini tamamlandı olarak işaretleyelim mi?')) return;
          try { await api('/api/ticktick/tamamla', { method: 'POST', govde: { project_id: b.dataset.ttPid, task_id: b.dataset.ttDone } }); entegrasyonSekmesi(ic, ctx); }
          catch (e) { alert(e.message); }
        };
      });
    } catch (e) { alan.innerHTML = `<div class="ca-kart ca-hata">${esc(e.message)}</div>`; }
  }

  // =========================================================================
  // 4. 🔄 RESMÎ HAVELSAN JAR DÖNÜŞTÜRÜCÜ & PAYLAŞIM
  // =========================================================================
  async function jarSekmesi(ic, ctx) {
    const { api, esc, sunucuHatasi } = ctx;
    ic.innerHTML = '<p class="ca-soluk">JAR dönüştürme motoru denetleniyor…</p>';
    let d;
    try { d = await api('/api/donustur/durum'); } catch (e) { sunucuHatasi(ic, e); return; }
    ic.innerHTML = `
      <div class="ca-kart">
        <div class="ca-hedef" style="font-size:18px">${d.hazir ? '🟢 Resmî Havelsan JAR Motoru Hazır' : '🟠 JAR Kütüphaneleri Eksik'}</div>
        <table>
          <tr><th>Java</th><td><code>${esc(d.java || 'bulunamadı')}</code></td></tr>
          <tr><th>Havelsan JAR Dizini</th><td><code>${esc(d.jars_dizini || 'bulunamadı')}</code> (${d.jar_sayisi || 0} JAR)</td></tr>
          <tr><th>Desteklenen Çıktılar</th><td>${(d.desteklenen || []).map(x => `<span class="hf-etiket">${x.toUpperCase()}</span>`).join('') || '—'}</td></tr>
        </table>
        ${d.uyari ? `<div class="ca-uyari">⚠️ ${esc(d.uyari)}</div>` : ''}
      </div>

      <div class="ca-kart">
        <b>📄 Açık CanEditor Belgesini Resmî JAR ile Dönüştür / Paylaş</b>
        <p class="ca-soluk">Mevcut açık belgeyi doğrudan Havelsan'ın orijinal <code>editor_lib.jar</code> vektörel PDF / ODFDOM motoruyla %100 birebir çıktıya dönüştürür.</p>
        <div>
          <button class="ca-btn ana" type="button" data-mevcut="pdf"${d.hazir ? '' : ' disabled'}>📕 JAR ile PDF Kaydet</button>
          <button class="ca-btn" type="button" data-mevcut="odt"${d.hazir ? '' : ' disabled'}>📘 JAR ile ODT Kaydet</button>
          <button class="ca-btn" type="button" data-mevcut="docx"${d.hazir ? '' : ' disabled'}>📝 JAR ile DOCX Kaydet</button>
          <button class="ca-btn altin" type="button" data-mevcut="pdf" data-paylas="1"${d.hazir ? '' : ' disabled'}>📤 PDF Paylaş</button>
        </div>
        <div id="hf-jar-durum" class="ca-soluk" style="margin-top:8px"></div>
      </div>

      <div class="ca-kart">
        <b>📂 Bilgisayardan / Telefondan UDF Dosyası Seçip Dönüştür</b>
        <div class="ca-satir" style="grid-template-columns:2fr 1fr">
          <div><input id="hf-jar-file" type="file" accept=".udf,.tif,.tiff,.jpg,.jpeg,.png"></div>
          <div><select id="hf-jar-fmt"><option value="pdf">PDF (Havelsan Vektörel)</option><option value="docx">Word (.docx)</option><option value="odt">OpenDocument (.odt)</option></select></div>
        </div>
        <button class="ca-btn ana" type="button" id="hf-jar-cevir" disabled>⚡ Dönüştür ve İndir</button>
        <button class="ca-btn altin" type="button" id="hf-jar-paylas" disabled>📤 Dönüştür ve Paylaş</button>
      </div>`;

    const durum = ic.querySelector('#hf-jar-durum');
    ic.querySelectorAll('[data-mevcut]').forEach(b => {
      b.onclick = async () => {
        durum.textContent = '⏳ Havelsan JAR motoru çalıştırılıyor…';
        try {
          if (typeof window.buildUdfZipBytes !== 'function') throw new Error('Açık belge UDF motoru bulunamadı.');
          const udfBytes = await window.buildUdfZipBytes();
          const ad = ((document.getElementById('desktopDocTitle') || {}).value || 'Dilekce.udf').replace(/\.[^.]+$/, '') + '.udf';
          const r = await jarDonusturVeKaydet(ctx, { dosya_adi: ad, icerik_b64: bytesToB64(udfBytes) }, b.dataset.mevcut, !!b.dataset.paylas);
          durum.textContent = `✓ Hazır: ${r.dosya_adi} (${(r.boyut / 1024).toFixed(1)} KB)`;
        } catch (e) { durum.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
      };
    });

    const fIn = ic.querySelector('#hf-jar-file'), bCev = ic.querySelector('#hf-jar-cevir'), bPay = ic.querySelector('#hf-jar-paylas');
    fIn.onchange = () => { bCev.disabled = bPay.disabled = !fIn.files.length || !d.hazir; };
    const dosyaIsle = async (paylas) => {
      const f = fIn.files[0]; if (!f) return;
      durum.textContent = `⏳ ${f.name} dönüştürülüyor…`;
      try {
        const buf = await f.arrayBuffer();
        const r = await jarDonusturVeKaydet(ctx, { dosya_adi: f.name, icerik_b64: bytesToB64(buf) }, ic.querySelector('#hf-jar-fmt').value, paylas);
        durum.textContent = `✓ Tamamlandı: ${r.dosya_adi} (${(r.boyut / 1024).toFixed(1)} KB)`;
      } catch (e) { durum.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
    };
    bCev.onclick = () => dosyaIsle(false);
    bPay.onclick = () => dosyaIsle(true);
  }

  // =========================================================================
  // 5. 📰 HAYFA HUKUK PORTALI (İçtihat, Haberler, Resmî Gazete, Mevzuat, Çevrimdışı Adliye/IBAN)
  // =========================================================================
  let hayfaAlt = 'ictihat';
  async function hayfaSekmesi(ic, ctx) {
    const { api, esc, sunucuHatasi, kapat } = ctx;
    ic.innerHTML = `
      <div class="hf-alt-nav">
        <button class="ca-btn${hayfaAlt === 'ictihat' ? ' ana' : ''}" type="button" data-ha="ictihat">⚖️ İçtihat / Karar Ara</button>
        <button class="ca-btn${hayfaAlt === 'haber' ? ' ana' : ''}" type="button" data-ha="haber">📰 Hukuk Haberleri</button>
        <button class="ca-btn${hayfaAlt === 'rg' ? ' ana' : ''}" type="button" data-ha="rg">📜 Resmî Gazete</button>
        <button class="ca-btn${hayfaAlt === 'mevzuat' ? ' ana' : ''}" type="button" data-ha="mevzuat">📚 Mevzuat</button>
        <button class="ca-btn${hayfaAlt === 'adliye' ? ' ana' : ''}" type="button" data-ha="adliye">🏛️ Adliye & IBAN (Çevrimdışı)</button>
      </div>
      <div id="hf-portal-ic"></div>`;
    ic.querySelectorAll('[data-ha]').forEach(b => { b.onclick = () => { hayfaAlt = b.dataset.ha; hayfaSekmesi(ic, ctx); }; });
    const alan = ic.querySelector('#hf-portal-ic');

    if (hayfaAlt === 'ictihat') {
      alan.innerHTML = `
        <div class="ca-satir" style="grid-template-columns:2fr 1fr auto">
          <div>
            <label>Arama Terimleri (kavram, kanun maddesi, konu)</label>
            <input id="hf-k-q" placeholder="ör. manevi tazminat, kıdem, tahliye, HMK 119, TCK 158...">
          </div>
          <div>
            <label>Yargı Yeri / Daire</label>
            <select id="hf-k-daire">
              <option value="">Tüm Yargı Yerleri</option>
              <optgroup label="Yargıtay Kurulları">
                <option value="HGK">Hukuk Genel Kurulu</option>
                <option value="CGK">Ceza Genel Kurulu</option>
                <option value="BGK">Büyük Genel Kurul</option>
                <option value="IBK">İçtihadı Birleştirme Kararları</option>
              </optgroup>
              <optgroup label="Yargıtay Hukuk Daireleri">
                <option value="1HD">1. Hukuk Dairesi (Tapu/Mülkiyet)</option>
                <option value="2HD">2. Hukuk Dairesi (Aile/Boşanma)</option>
                <option value="3HD">3. Hukuk Dairesi (Kira/Borçlar)</option>
                <option value="4HD">4. Hukuk Dairesi (Tazminat/Haksız Fiil)</option>
                <option value="5HD">5. Hukuk Dairesi</option>
                <option value="6HD">6. Hukuk Dairesi</option>
                <option value="7HD">7. Hukuk Dairesi</option>
                <option value="8HD">8. Hukuk Dairesi</option>
                <option value="9HD">9. Hukuk Dairesi (İş/Kıdem/İhbar)</option>
                <option value="10HD">10. Hukuk Dairesi (Sosyal Güvenlik)</option>
                <option value="11HD">11. Hukuk Dairesi (Ticaret/Şirketler)</option>
                <option value="12HD">12. Hukuk Dairesi (İcra/İflas)</option>
                <option value="13HD">13. Hukuk Dairesi</option>
                <option value="14HD">14. Hukuk Dairesi</option>
                <option value="15HD">15. Hukuk Dairesi</option>
                <option value="16HD">16. Hukuk Dairesi</option>
                <option value="17HD">17. Hukuk Dairesi</option>
                <option value="18HD">18. Hukuk Dairesi</option>
                <option value="19HD">19. Hukuk Dairesi</option>
                <option value="20HD">20. Hukuk Dairesi</option>
                <option value="21HD">21. Hukuk Dairesi</option>
                <option value="22HD">22. Hukuk Dairesi</option>
                <option value="23HD">23. Hukuk Dairesi</option>
              </optgroup>
              <optgroup label="Yargıtay Ceza Daireleri">
                <option value="1CD">1. Ceza Dairesi</option>
                <option value="2CD">2. Ceza Dairesi</option>
                <option value="3CD">3. Ceza Dairesi</option>
                <option value="4CD">4. Ceza Dairesi</option>
                <option value="5CD">5. Ceza Dairesi</option>
                <option value="6CD">6. Ceza Dairesi</option>
                <option value="7CD">7. Ceza Dairesi</option>
                <option value="8CD">8. Ceza Dairesi</option>
                <option value="9CD">9. Ceza Dairesi</option>
                <option value="10CD">10. Ceza Dairesi</option>
                <option value="11CD">11. Ceza Dairesi</option>
                <option value="12CD">12. Ceza Dairesi</option>
                <option value="13CD">13. Ceza Dairesi</option>
                <option value="14CD">14. Ceza Dairesi</option>
                <option value="15CD">15. Ceza Dairesi</option>
                <option value="16CD">16. Ceza Dairesi</option>
                <option value="17CD">17. Ceza Dairesi</option>
                <option value="18CD">18. Ceza Dairesi</option>
                <option value="19CD">19. Ceza Dairesi</option>
                <option value="20CD">20. Ceza Dairesi</option>
                <option value="21CD">21. Ceza Dairesi</option>
                <option value="22CD">22. Ceza Dairesi</option>
                <option value="23CD">23. Ceza Dairesi</option>
              </optgroup>
              <optgroup label="Danıştay">
                <option value="Danistay">Danıştay (tümü)</option>
                <option value="IDDK">İdari Dava Daireleri Kurulu</option>
                <option value="VDDK">Vergi Dava Daireleri Kurulu</option>
                <option value="Danistay1">Danıştay 1. Daire</option>
                <option value="Danistay2">Danıştay 2. Daire</option>
                <option value="Danistay3">Danıştay 3. Daire</option>
                <option value="Danistay4">Danıştay 4. Daire</option>
                <option value="Danistay5">Danıştay 5. Daire</option>
                <option value="Danistay6">Danıştay 6. Daire</option>
                <option value="Danistay7">Danıştay 7. Daire</option>
                <option value="Danistay8">Danıştay 8. Daire</option>
                <option value="Danistay9">Danıştay 9. Daire</option>
                <option value="Danistay10">Danıştay 10. Daire</option>
                <option value="Danistay11">Danıştay 11. Daire</option>
                <option value="Danistay12">Danıştay 12. Daire</option>
                <option value="Danistay13">Danıştay 13. Daire</option>
                <option value="Danistay14">Danıştay 14. Daire</option>
                <option value="Danistay15">Danıştay 15. Daire</option>
                <option value="Danistay16">Danıştay 16. Daire</option>
                <option value="Danistay17">Danıştay 17. Daire</option>
              </optgroup>
              <optgroup label="Diğer">
                <option value="AYM">Anayasa Mahkemesi</option>
                <option value="BAM">Bölge Adliye Mahkemesi</option>
                <option value="BIM">Bölge İdare Mahkemesi</option>
                <option value="UYM">Uyuşmazlık Mahkemesi</option>
                <option value="SAYISTAY">Sayıştay</option>
              </optgroup>
            </select>
          </div>
          <div style="display:flex;align-items:flex-end">
            <button class="ca-btn ana" type="button" id="hf-k-ara">🔍 Ara</button>
          </div>
        </div>

        <div style="display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 4px">
          <span class="ca-soluk" style="line-height:28px">Hızlı Konular:</span>
          <button class="ca-btn kucuk" type="button" data-k-hizli="manevi tazminat">Manevi Tazminat</button>
          <button class="ca-btn kucuk" type="button" data-k-hizli="kıdem tazminatı">Kıdem Tazminatı</button>
          <button class="ca-btn kucuk" type="button" data-k-hizli="itirazın iptali">İtirazın İptali</button>
          <button class="ca-btn kucuk" type="button" data-k-hizli="tahliye">Tahliye</button>
          <button class="ca-btn kucuk" type="button" data-k-hizli="nafaka artırımı">Nafaka</button>
          <button class="ca-btn kucuk" type="button" data-k-hizli="işe iade">İşe İade</button>
          <button class="ca-btn kucuk" type="button" data-k-hizli="dolandırıcılık">Dolandırıcılık</button>
          <button class="ca-btn kucuk" type="button" data-k-hizli="menfi tespit">Menfi Tespit</button>
        </div>

        <div id="hf-k-sonuc" style="margin-top:10px" class="ca-soluk">hayfahukuk.com Yargıtay karar veritabanında aramak için anahtar kelime girin. Kararlar tam metin korunur, asla anonimleştirilmez.</div>`;

      const kq = alan.querySelector('#hf-k-q'), kdaire = alan.querySelector('#hf-k-daire'), kson = alan.querySelector('#hf-k-sonuc');
      // Sonuçlar sayfa sayfa birikir ("Daha fazla karar"); eskiden yalnız ilk sayfa geliyordu
      let kSayfa = 1, kBirikmis = [];
      const ara = async (devam) => {
        const sorgu = kq.value.trim();
        if (sorgu.length < 2) { kson.textContent = 'En az 2 karakter girin.'; return; }
        if (devam !== true) { kSayfa = 1; kBirikmis = []; kson.innerHTML = '<span class="ca-soluk">İçtihat veritabanı taranıyor…</span>'; }
        try {
          const v = await api(`/api/hayfa/kararlar?q=${encodeURIComponent(sorgu)}&alan=${encodeURIComponent(kdaire.value)}&sayfa=${kSayfa}`);
          if (v.hata) { kson.innerHTML = `<span class="ca-hata">${esc(v.hata)}</span>`; return; }
          const gorulen = new Set(kBirikmis.map(k => k.id));
          const yeniler = (v.kararlar || []).filter(k => !gorulen.has(k.id));
          kBirikmis = kBirikmis.concat(yeniler);
          const dahaVar = yeniler.length > 0;
          v.kararlar = kBirikmis;
          kson.innerHTML = `<div class="ca-soluk"><b>${esc(v.toplam)}</b> karar bulundu${v.suzuldu ? ' (daire adına göre süzüldü)' : ''} · ${kBirikmis.length} gösteriliyor (Anonimleştirilmemiş tam metin)</div>
            ${(v.kararlar || []).map(k => `<div class="ca-kart">
              <b>${esc(k.baslik)}</b>
              <div style="margin:4px 0">${(k.etiketler || []).map(t => `<span class="hf-etiket">${esc(t)}</span>`).join('')}</div>
              <p class="ca-soluk" style="margin:4px 0;line-height:1.5">${esc(k.ozet)}</p>
              <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">
                <button class="ca-btn kucuk ana" type="button" data-koku="${esc(k.id)}">📖 Tam Metni Oku</button>
                <button class="ca-btn kucuk altin" type="button" data-kekle="${esc(k.id)}">📝 Dilekçeye İçtihat Ekle</button>
                <a class="ca-btn kucuk" href="${esc(k.url)}" target="_blank" rel="noopener">↗ hayfahukuk.com</a>
              </div>
            </div>`).join('') || '<p class="ca-soluk">Karar bulunamadı.</p>'}
            ${dahaVar ? '<div style="text-align:center;margin:12px 0"><button class="ca-btn" type="button" id="hf-k-daha">⬇️ Daha fazla karar yükle</button></div>' : ''}`;
          const dahaBtn = kson.querySelector('#hf-k-daha');
          if (dahaBtn) dahaBtn.onclick = () => { dahaBtn.disabled = true; dahaBtn.textContent = 'Yükleniyor…'; kSayfa += 1; ara(true); };

          kson.querySelectorAll('[data-koku]').forEach(b => {
            b.onclick = async () => {
              kson.innerHTML = '<p class="ca-soluk">Karar tam metni yükleniyor…</p>';
              try {
                const d = await api('/api/hayfa/karar?id=' + encodeURIComponent(b.dataset.koku));
                kson.innerHTML = `
                  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
                    <button class="ca-btn kucuk" type="button" id="hf-k-geri">← Sonuçlara Dön</button>
                    <button class="ca-btn kucuk altin" type="button" id="hf-k-yap">📝 Dilekçeye Ekle</button>
                    <button class="ca-btn kucuk" type="button" id="hf-k-kopyala">📋 Metni Kopyala</button>
                    <a class="ca-btn kucuk" href="${esc(d.url)}" target="_blank" rel="noopener">↗ Orijinal Sayfa</a>
                  </div>
                  <div class="ca-kart">
                    <h3 style="margin-top:0">${esc(d.baslik)}</h3>
                    <pre style="max-height:550px;font-family:inherit;line-height:1.6;white-space:pre-wrap;overflow:auto">${esc(d.metin)}</pre>
                  </div>`;
                kson.querySelector('#hf-k-geri').onclick = () => ara();
                kson.querySelector('#hf-k-yap').onclick = () => metinEkleBelgeye(`\n${d.baslik}\n${d.metin}\n`, kapat);
                kson.querySelector('#hf-k-kopyala').onclick = () => kopyala(d.metin);
              } catch (e) { kson.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
            };
          });

          kson.querySelectorAll('[data-kekle]').forEach(b => {
            b.onclick = async () => {
              try {
                const d = await api('/api/hayfa/karar?id=' + encodeURIComponent(b.dataset.kekle));
                metinEkleBelgeye(`\n${d.baslik}\n"${d.metin.slice(0, 1800)}"\n`, kapat);
              } catch (e) { alert(e.message); }
            };
          });
        } catch (e) { sunucuHatasi(ic, e); }
      };

      alan.querySelector('#hf-k-ara').onclick = () => ara();
      kq.addEventListener('keydown', e => { if (e.key === 'Enter') ara(); });
      kdaire.onchange = () => { if (kq.value.trim().length >= 2) ara(); };
      alan.querySelectorAll('[data-k-hizli]').forEach(b => {
        b.onclick = () => {
          kq.value = b.dataset.kHizli;
          ara();
        };
      });
      return;
    }

    if (hayfaAlt === 'haber') {
      alan.innerHTML = '<p class="ca-soluk">HAYFA Hukuk haberleri yükleniyor…</p>';
      try {
        const v = await api('/api/hayfa/haberler?limit=24');
        alan.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center">
            <span class="ca-soluk">Kaynak: hayfahukuk.com/haberler ${v.cevrimdisi ? '(çevrimdışı önbellek)' : ''}</span>
            <button class="ca-btn kucuk" type="button" id="hf-h-yen">↻ Yenile</button>
          </div>
          <div class="hf-grid">${(v.haberler || []).map(h => `<div class="hf-kart">
            <span class="hf-etiket">${esc(h.kaynak || 'Hukuk')}</span>
            <b>${esc(h.baslik)}</b>
            <div class="ca-soluk">${esc(h.ozet || '')}</div>
            <div style="margin-top:auto"><button class="ca-btn kucuk ana" type="button" data-hoku="${esc(h.id)}">Oku</button>
            <a class="ca-btn kucuk" href="${esc(h.url)}" target="_blank" rel="noopener">↗</a></div>
          </div>`).join('') || '<p class="ca-soluk">Haber bulunamadı.</p>'}</div>`;
        alan.querySelector('#hf-h-yen').onclick = async () => { await api('/api/hayfa/haberler?yenile=1'); hayfaSekmesi(ic, ctx); };
        alan.querySelectorAll('[data-hoku]').forEach(b => {
          b.onclick = async () => {
            alan.innerHTML = '<p class="ca-soluk">Haber yükleniyor…</p>';
            try {
              const d = await api('/api/hayfa/haber?id=' + encodeURIComponent(b.dataset.hoku));
              alan.innerHTML = `<button class="ca-btn kucuk" type="button" id="hf-h-geri">← Haberlere Dön</button>
                <div class="ca-kart"><h3>${esc(d.baslik)}</h3><pre style="max-height:420px;font-family:inherit;line-height:1.6">${esc(d.metin)}</pre></div>`;
              alan.querySelector('#hf-h-geri').onclick = () => hayfaSekmesi(ic, ctx);
            } catch (e) { alan.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
          };
        });
      } catch (e) { sunucuHatasi(ic, e); }
      return;
    }

    if (hayfaAlt === 'rg') {
      alan.innerHTML = '<p class="ca-soluk">Resmî Gazete bülteni yükleniyor…</p>';
      try {
        const v = await api('/api/hayfa/resmi-gazete');
        alan.innerHTML = `<div class="ca-kart">
          <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;align-items:center">
            <div><div class="ca-hedef" style="font-size:18px">📜 ${esc(v.tarih_etiket || 'Resmî Gazete')}</div><div class="ca-soluk">${esc(v.sayi || '')}</div></div>
            <div>${v.pdf_url ? `<a class="ca-btn altin kucuk" href="${esc(v.pdf_url)}" target="_blank" rel="noopener">📕 Sayının Tamamı (PDF)</a>` : ''}
            <button class="ca-btn kucuk" type="button" id="hf-rg-yen">↻ Yenile</button></div>
          </div>
          <table style="margin-top:10px">${(v.maddeler || []).map(m => `<tr><td><a href="${esc(m.url)}" target="_blank" rel="noopener">${esc(m.baslik)}</a></td></tr>`).join('') || '<tr><td class="ca-soluk">Kayıt bulunamadı.</td></tr>'}</table>
        </div>`;
        alan.querySelector('#hf-rg-yen').onclick = async () => { await api('/api/hayfa/resmi-gazete?yenile=1'); hayfaSekmesi(ic, ctx); };
      } catch (e) { sunucuHatasi(ic, e); }
      return;
    }

    if (hayfaAlt === 'mevzuat') {
      alan.innerHTML = `<div class="ca-satir" style="grid-template-columns:2fr auto">
        <input id="hf-m-q" placeholder="Kanun veya yönetmelik ara (ör. Borçlar, HMK, TCK, İİK)...">
        <button class="ca-btn ana" type="button" id="hf-m-ara">🔍 Ara</button>
      </div><div id="hf-m-sonuc" style="margin-top:10px" class="ca-soluk">Yükleniyor…</div>`;
      const mq = alan.querySelector('#hf-m-q'), mson = alan.querySelector('#hf-m-sonuc');
      const ara = async () => {
        mson.innerHTML = '<span class="ca-soluk">Mevzuat taranıyor…</span>';
        try {
          const v = await api('/api/hayfa/mevzuat?q=' + encodeURIComponent(mq.value.trim()));
          mson.innerHTML = `<table>${(v.mevzuat || []).map(x => `<tr>
            <td><b>${esc(x.baslik)}</b></td>
            <td style="white-space:nowrap;text-align:right">
              <button class="ca-btn kucuk ana" type="button" data-m-oku="${esc(x.url)}" data-m-bas="${esc(x.baslik)}">📖 Uygulamada Oku</button>
              <a class="ca-btn kucuk" href="${esc(x.url)}" target="_blank" rel="noopener">↗</a>
            </td>
          </tr>`).join('') || '<tr><td colspan="2" class="ca-soluk">Sonuç bulunamadı.</td></tr>'}</table>`;

          mson.querySelectorAll('[data-m-oku]').forEach(b => {
            b.onclick = async () => {
              mson.innerHTML = '<p class="ca-soluk">Mevzuat metni yükleniyor…</p>';
              try {
                const d = await api('/api/hayfa/mevzuat/detay?url=' + encodeURIComponent(b.dataset.mOku));
                mson.innerHTML = `
                  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
                    <button class="ca-btn kucuk" type="button" id="hf-m-geri">← Mevzuat Listesine Dön</button>
                    <button class="ca-btn kucuk altin" type="button" id="hf-m-ekle">📝 Belgeye Ekle</button>
                    <button class="ca-btn kucuk" type="button" id="hf-m-kopyala">📋 Metni Kopyala</button>
                    <a class="ca-btn kucuk" href="${esc(d.url || b.dataset.mOku)}" target="_blank" rel="noopener">↗ Orijinal</a>
                  </div>
                  <div class="ca-kart">
                    <h3 style="margin-top:0">${esc(d.baslik || b.dataset.mBas)}</h3>
                    <pre style="max-height:550px;font-family:inherit;line-height:1.6;white-space:pre-wrap;overflow:auto">${esc(d.metin || 'Metin yüklenemedi.')}</pre>
                  </div>`;
                mson.querySelector('#hf-m-geri').onclick = ara;
                mson.querySelector('#hf-m-ekle').onclick = () => metinEkleBelgeye(`\n${d.baslik}\n${d.metin}\n`, kapat);
                mson.querySelector('#hf-m-kopyala').onclick = () => kopyala(d.metin);
              } catch (e) { mson.innerHTML = `<span class="ca-hata">Mevzuat yüklenemedi: ${esc(e.message)}</span>`; }
            };
          });
        } catch (e) { sunucuHatasi(ic, e); }
      };
      alan.querySelector('#hf-m-ara').onclick = ara;
      mq.addEventListener('keydown', e => { if (e.key === 'Enter') ara(); });
      ara();
      return;
    }

    // Adliye & İcra Rehberi (100% ÇEVRİMDIŞI!)
    alan.innerHTML = `<div class="ca-satir" style="grid-template-columns:2fr 1fr">
      <div><label>Adliye / İcra Dairesi / IBAN Ara (çevrimdışı çalışır)</label><input id="hf-ad-q" placeholder="ör. Ankara 1. İcra, Çağlayan, Kartal, emanet..."></div>
      <div><label>İl</label><select id="hf-ad-il"><option value="">Tüm İller</option></select></div>
    </div><div id="hf-ad-sonuc" style="margin-top:10px" class="ca-soluk">Yükleniyor…</div>`;
    const aq = alan.querySelector('#hf-ad-q'), ail = alan.querySelector('#hf-ad-il'), ason = alan.querySelector('#hf-ad-sonuc');
    let illerDolu = false, azam = null;
    const ara = async () => {
      try {
        const v = await api(`/api/hayfa/adliyeler?q=${encodeURIComponent(aq.value.trim())}&il=${encodeURIComponent(ail.value)}`);
        if (!illerDolu) {
          illerDolu = true;
          (v.iller || []).forEach(il => { const o = document.createElement('option'); o.value = il; o.textContent = il; ail.appendChild(o); });
        }
        ason.innerHTML = `<div class="ca-soluk">Çevrimdışı rehber: ${v.bina_sayisi} adliye binası, ${v.birim_sayisi} birim (Doğrulama: ${esc(v.olusturma || '—')})</div>
          ${(v.birimler || []).slice(0, 30).map(b => `<div class="ca-kart">
            <div><span class="hf-etiket">${esc(b.il || '')}</span><span class="hf-etiket">${esc(b.tur || '')}</span></div>
            <b>${esc(b.ad)}</b>
            <div class="ca-soluk">${esc(b.adliye)} · ${esc(b.adres || '')}${b.bina_telefon ? ' · ☎️ ' + esc(b.bina_telefon) : ''}</div>
            ${(b.ibanlar || []).map(ib => `<div class="hf-iban"><span><b>${esc(ib.tur)}:</b> ${esc(ib.iban)} <span class="ca-soluk">(${esc(ib.banka || '')})</span></span><button class="ca-btn kucuk" type="button" data-kopya="${esc(ib.iban)}">📋</button></div>`).join('')}
          </div>`).join('') || '<p class="ca-soluk">Eşleşen birim bulunamadı.</p>'}`;
        ason.querySelectorAll('[data-kopya]').forEach(b => { b.onclick = () => kopyala(b.dataset.kopya); });
      } catch (e) { sunucuHatasi(ic, e); }
    };
    aq.addEventListener('input', () => { clearTimeout(azam); azam = setTimeout(ara, 250); });
    ail.onchange = ara;
    ara();
  }

  window.CanHayfa = {
    stilYukle,
    dosyalarSekmesi,
    driveProSekmesi,
    entegrasyonSekmesi,
    jarSekmesi,
    hayfaSekmesi,
    jarDonusturVeKaydet,
    metinEkleBelgeye
  };
})();
