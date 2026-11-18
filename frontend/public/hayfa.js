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
  }
  #ca-panel header {
    background: linear-gradient(135deg, var(--hf-navy) 0%, var(--hf-navy-2) 65%, var(--hf-navy-3) 100%);
    color: #fff;
    padding: 13px 18px;
    border-bottom: 2px solid var(--hf-gold);
  }
  #ca-panel header h2 {
    font-family: Georgia, 'Playfair Display', serif;
    letter-spacing: .3px;
    color: #fff;
    display: flex; align-items: center; gap: 10px;
  }
  #ca-panel header .hf-badge {
    font: 600 11px/1 system-ui, sans-serif;
    background: rgba(200,164,90,.22); color: #f6dfad;
    border: 1px solid rgba(200,164,90,.45);
    padding: 4px 9px; border-radius: 999px;
  }
  #ca-panel nav {
    background: var(--ce-surface, #f8fafc);
    padding: 6px 10px 0;
    gap: 2px;
    scrollbar-width: thin;
    -webkit-overflow-scrolling: touch;
  }
  body.ce-dark-mode #ca-panel nav { background: #0f172a; }
  #ca-panel nav button {
    padding: 9px 11px;
    font-size: 13px;
    border-radius: 8px 8px 0 0;
    transition: background .15s, color .15s;
  }
  #ca-panel nav button.secili {
    color: var(--hf-navy);
    background: var(--hf-gold-soft);
    border-bottom-color: var(--hf-gold);
    font-weight: 700;
  }
  body.ce-dark-mode #ca-panel nav button.secili {
    color: #f5d896;
    background: rgba(200,164,90,.15);
    border-bottom-color: var(--hf-gold);
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
    #ca-panel .ca-kutu { width: 100vw; max-height: 100dvh; height: 100dvh; border-radius: 0; border: 0; }
    #ca-panel .ca-icerik { padding: 12px; }
    #ca-panel nav button { padding: 10px 10px; font-size: 12.5px; }
    #ca-panel table, #ca-panel tbody, #ca-panel tr, #ca-panel td { display: block; width: 100%; }
    #ca-panel thead { display: none; }
    #ca-panel tr { border: 1px solid var(--ce-border, #e5e8ee); border-radius: 10px; padding: 8px; margin-bottom: 8px; }
    #ca-panel td { border: 0; padding: 3px 0; }
    #ca-yuzen { right: 14px !important; bottom: 16px !important; padding: 10px 14px !important; }
  }
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
  // 1. 📁 UYAP DOSYA YÖNETİM MERKEZİ
  // =========================================================================
  async function dosyalarSekmesi(ic, ctx) {
    const { api, esc, sunucuHatasi, evrakAc, kapat } = ctx;
    ic.innerHTML = `
      <div class="ca-satir" style="grid-template-columns:2fr 1fr auto">
        <div><label>Dosya Ara (esas no, mahkeme, müvekkil, taraf)</label><input id="hf-dosya-q" placeholder="ör. 2025/142, Asliye Hukuk, Ahmet..."></div>
        <div><label>Durum</label><select id="hf-dosya-durum"><option value="">Tümü</option><option value="Açık" selected>Açık (Derdest)</option><option value="Kapalı">Kapalı</option></select></div>
        <div style="display:flex;align-items:flex-end"><button class="ca-btn ana" type="button" id="hf-dosya-ara-btn">🔍 Listele</button></div>
      </div>
      <div id="hf-dosya-govde" style="margin-top:12px"><p class="ca-soluk">Yükleniyor…</p></div>`;

    const qIn = ic.querySelector('#hf-dosya-q');
    const dSel = ic.querySelector('#hf-dosya-durum');
    const govde = ic.querySelector('#hf-dosya-govde');
    let zam = null;

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
            ${d.taraflar ? `<p class="ca-soluk" style="margin-top:8px"><b>Taraflar:</b> ${esc(d.taraflar)}</p>` : ''}
            <div id="hf-d-aktar-sonuc" class="ca-soluk"></div>
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

    async function listele() {
      govde.innerHTML = '<p class="ca-soluk">Dosyalar yükleniyor…</p>';
      try {
        const v = await api(`/api/dosyalar?limit=150&q=${encodeURIComponent(qIn.value.trim())}&durum=${encodeURIComponent(dSel.value)}`);
        if (!v.hazir) { govde.innerHTML = `<div class="ca-kart">${esc(v.mesaj)}</div>`; return; }
        govde.innerHTML = `<div class="ca-soluk">Toplam <b>${v.toplam}</b> dosya (<b>${v.acik}</b> açık) · Gösterilen: ${v.dosyalar.length}</div>
          <div class="hf-grid">${v.dosyalar.map(d => `
            <div class="hf-kart" style="cursor:pointer" data-dkey="${esc(d.dkey)}">
              <div><span class="hf-etiket ${d.durum === 'Açık' ? 'acik' : 'kapali'}">${esc(d.durum || '—')}</span><span class="hf-etiket">${d.evrak_sayisi || 0} evrak</span></div>
              <b>${esc(d.birim || 'Birim belirtilmedi')}</b>
              <div style="font-size:15px;font-weight:700;color:var(--hf-navy)">${esc(d.dosya_no || '—')}</div>
              <div class="ca-soluk">${esc(d.muvekkil || d.taraflar || '').slice(0, 90)}</div>
            </div>`).join('') || '<p class="ca-soluk">Eşleşen dosya bulunamadı.</p>'}</div>`;
        govde.querySelectorAll('[data-dkey]').forEach(k => { k.onclick = () => detayAc(k.dataset.dkey); });
      } catch (e) { sunucuHatasi(ic, e); }
    }

    ic.querySelector('#hf-dosya-ara-btn').onclick = listele;
    qIn.addEventListener('input', () => { clearTimeout(zam); zam = setTimeout(listele, 320); });
    dSel.onchange = listele;
    listele();
  }

  // =========================================================================
  // 2. ☁️ GOOGLE DRIVE EŞİTLEME & VERİTABANI İNDEKSİ
  // =========================================================================
  async function driveDosyaAc(rel, ctx) {
    try {
      const r = await ctx.api('/api/drive/dosya?rel=' + encodeURIComponent(rel), { ham: true });
      const buf = await r.arrayBuffer();
      const ad = rel.split('/').pop() || 'DriveDosyasi';
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
            <tr><th>Nöbetçi Son Tur</th><td>${n ? `${tarih(n.son_tur)} (${n.dakika_once} dk önce) ${n.gecikti ? '🔴' : '🟢'}` : '—'}</td></tr>
          </table>
          ${(v.uyarilar || []).map(u => `<div class="ca-uyari">⚠️ ${esc(u)}</div>`).join('')}
          <div style="margin-top:8px">
            <button class="ca-btn ana" type="button" id="hf-drv-esitle">☁️ Eksikleri Drive'a Eşitle</button>
            <button class="ca-btn altin" type="button" id="hf-drv-indeks">🗄️ Drive'ı Veritabanına İndeksle</button>
            <button class="ca-btn" type="button" id="hf-drv-yenile">↻ Yenile</button>
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

        <details class="ca-kart">
          <summary style="cursor:pointer;font-weight:600">⚙️ Google Drive & Telegram Ayarları</summary>
          <div class="ca-satir" style="margin-top:8px">
            <div><label>Yerel Google Drive Klasörü</label><input id="hf-cfg-dir" value="${esc(a.google_drive_dir || '')}" placeholder="ör. G:\\Drive'ım\\UYAP_Arsiv"></div>
            <div><label>Bulut Webhook URL (Android / Uzak)</label><input id="hf-cfg-wh" value="${esc(a.google_drive_webhook || '')}" placeholder="https://script.google.com/macros/s/.../exec"></div>
            <div><label>Telegram Bot Token</label><input id="hf-cfg-tg" type="password" placeholder="${a.telegram_token_var ? '•••• (kayıtlı)' : 'isteğe bağlı'}"></div>
            <div><label>Telegram Chat ID</label><input id="hf-cfg-chat" value="${esc(a.telegram_chat_id || '')}" placeholder="ör. 123456789"></div>
          </div>
          <label style="display:flex;gap:8px;align-items:center;color:inherit;font-size:13px"><input type="checkbox" id="hf-cfg-auto" style="width:auto"${a.drive_auto_index !== false ? ' checked' : ''}> Her nöbetçi turunda Drive veritabanını otomatik güncelle</label>
          <button class="ca-btn ana" type="button" id="hf-cfg-kaydet">💾 Ayarları Kaydet</button>
        </details>`;

      const islem = ic.querySelector('#hf-drv-islem');
      ic.querySelector('#hf-drv-yenile').onclick = () => driveProSekmesi(ic, ctx);
      ic.querySelector('#hf-drv-indeks').onclick = async () => {
        islem.textContent = '⏳ Google Drive klasörü taranıp SQLite veritabanına alınıyor…';
        try {
          const r = await api('/api/drive/indeksle', { method: 'POST', govde: {} });
          islem.textContent = `✓ İndekslendi: ${r.toplam.toLocaleString('tr-TR')} dosya (${r.boyut_mb} MB) · +${r.yeni} yeni, ${r.guncellenen} güncellendi, ${r.silinen} silindi (${r.sure_ms} ms)`;
          driveAra();
        } catch (e) { islem.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
      };
      ic.querySelector('#hf-drv-esitle').onclick = async () => {
        islem.textContent = '⏳ Yerel UYAP evrakları Google Drive ile eşitleniyor…';
        try {
          const r = await api('/api/drive/esitle', { method: 'POST', govde: { limit: 150 } });
          islem.textContent = `✓ Eşitleme tamamlandı: ${r.aktarilan} aktarıldı, ${r.atlanan} zaten güncel, ${r.hata} hata.`;
        } catch (e) { islem.innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
      };
      ic.querySelector('#hf-cfg-kaydet').onclick = async () => {
        const g = {
          google_drive_dir: ic.querySelector('#hf-cfg-dir').value.trim(),
          google_drive_webhook: ic.querySelector('#hf-cfg-wh').value.trim(),
          telegram_chat_id: ic.querySelector('#hf-cfg-chat').value.trim(),
          drive_auto_index: ic.querySelector('#hf-cfg-auto').checked
        };
        const tg = ic.querySelector('#hf-cfg-tg').value.trim();
        if (tg) g.telegram_token = tg;
        try { await api('/api/drive/ayar', { method: 'POST', govde: g }); driveProSekmesi(ic, ctx); }
        catch (e) { alert(e.message); }
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
  let entAlt = 'ticktick';
  async function entegrasyonSekmesi(ic, ctx) {
    const { api, esc, sunucuHatasi } = ctx;
    ic.innerHTML = '<p class="ca-soluk">Entegrasyon durumu yükleniyor…</p>';
    let ayar;
    try { ayar = await api('/api/entegrasyon/ayar'); } catch (e) { sunucuHatasi(ic, e); return; }

    ic.innerHTML = `
      <div class="hf-alt-nav">
        <button class="ca-btn${entAlt === 'ticktick' ? ' ana' : ''}" type="button" data-ea="ticktick">✅ TickTick Görevleri ${ayar.ticktick_bagli ? '🟢' : '⚪'}</button>
        <button class="ca-btn${entAlt === 'notion' ? ' ana' : ''}" type="button" data-ea="notion">📓 Notion Dosyaları ${ayar.notion_bagli ? '🟢' : '⚪'}</button>
        <button class="ca-btn${entAlt === 'ayar' ? ' ana' : ''}" type="button" data-ea="ayar">🔑 API Anahtarları & Otomatik Senkron</button>
      </div>
      <div id="hf-ent-ic"></div>`;
    ic.querySelectorAll('[data-ea]').forEach(b => { b.onclick = () => { entAlt = b.dataset.ea; entegrasyonSekmesi(ic, ctx); }; });
    const alan = ic.querySelector('#hf-ent-ic');

    if (entAlt === 'ayar') {
      alan.innerHTML = `<div class="ca-kart">
        <b>🔐 Yerel API Yapılandırması (yalnızca bu cihazdaki .env dosyasına 0600 izniyle yazılır)</b>
        <div class="ca-satir">
          <div><label>Notion API Token</label><input id="hf-e-nt" type="password" placeholder="${ayar.notion_bagli ? esc(ayar.notion_token) + ' (kayıtlı)' : 'ntn_...'}"></div>
          <div><label>Notion Dosyalar Veritabanı ID</label><input id="hf-e-ndb" value="${esc(ayar.notion_db || '')}"></div>
          <div><label>TickTick API Token</label><input id="hf-e-tt" type="password" placeholder="${ayar.ticktick_bagli ? esc(ayar.ticktick_token) + ' (kayıtlı)' : 'tp_...'}"></div>
          <div><label>Telegram Bot Token</label><input id="hf-e-tg" type="password" placeholder="${ayar.telegram_bagli ? '•••• (kayıtlı)' : 'isteğe bağlı'}"></div>
          <div><label>Telegram Chat ID</label><input id="hf-e-chat" value="${esc(ayar.telegram_chat_id || '')}"></div>
          <div><label>UETS T.C. Kimlik No</label><input id="hf-e-uets-tc" placeholder="${ayar.uets_bagli ? esc(ayar.uets_tckn) + ' (kayıtlı)' : 'isteğe bağlı'}"></div>
          <div><label>UETS Şifre</label><input id="hf-e-uets-pw" type="password" placeholder="${ayar.uets_bagli ? '•••• (kayıtlı)' : 'isteğe bağlı'}"></div>
        </div>
        <label style="display:flex;gap:8px;align-items:center;color:inherit;font-size:14px"><input type="checkbox" id="hf-e-oto" style="width:auto"${ayar.otomatik_senkron ? ' checked' : ''}> UYAP'a yeni evrak/tebligat düşünce Notion & TickTick'e otomatik aktar</label>
        <button class="ca-btn ana" type="button" id="hf-e-kaydet">💾 Kaydet</button>
        <span id="hf-e-msg" class="ca-soluk"></span></div>`;
      alan.querySelector('#hf-e-kaydet').onclick = async () => {
        const g = {
          notion_token: alan.querySelector('#hf-e-nt').value.trim(),
          notion_db: alan.querySelector('#hf-e-ndb').value.trim(),
          ticktick_token: alan.querySelector('#hf-e-tt').value.trim(),
          telegram_bot_token: alan.querySelector('#hf-e-tg').value.trim(),
          telegram_chat_id: alan.querySelector('#hf-e-chat').value.trim(),
          uets_tckn: alan.querySelector('#hf-e-uets-tc').value.trim(),
          uets_password: alan.querySelector('#hf-e-uets-pw').value.trim(),
          otomatik_senkron: alan.querySelector('#hf-e-oto').checked
        };
        try { await api('/api/entegrasyon/ayar', { method: 'POST', govde: g }); entegrasyonSekmesi(ic, ctx); }
        catch (e) { alan.querySelector('#hf-e-msg').innerHTML = `<span class="ca-hata">${esc(e.message)}</span>`; }
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
      alan.innerHTML = `<div class="ca-satir" style="grid-template-columns:2fr auto">
          <input id="hf-k-q" placeholder="Yargıtay içtihatlarında ara (ör. manevi tazminat, kıdem, tahliye, HMK 119)...">
          <button class="ca-btn ana" type="button" id="hf-k-ara">🔍 Ara</button>
        </div><div id="hf-k-sonuc" style="margin-top:10px" class="ca-soluk">hayfahukuk.com Yargıtay karar veritabanında aramak için anahtar kelime girin.</div>`;
      const kq = alan.querySelector('#hf-k-q'), kson = alan.querySelector('#hf-k-sonuc');
      const ara = async () => {
        if (kq.value.trim().length < 2) { kson.textContent = 'En az 2 karakter girin.'; return; }
        kson.innerHTML = '<span class="ca-soluk">İçtihat veritabanı taranıyor…</span>';
        try {
          const v = await api('/api/hayfa/kararlar?q=' + encodeURIComponent(kq.value.trim()));
          if (v.hata) { kson.innerHTML = `<span class="ca-hata">${esc(v.hata)}</span>`; return; }
          kson.innerHTML = `<div class="ca-soluk"><b>${esc(v.toplam)}</b> karar bulundu</div>
            ${(v.kararlar || []).map(k => `<div class="ca-kart">
              <b>${esc(k.baslik)}</b>
              <div style="margin:4px 0">${(k.etiketler || []).map(t => `<span class="hf-etiket">${esc(t)}</span>`).join('')}</div>
              <p class="ca-soluk" style="margin:4px 0">${esc(k.ozet)}</p>
              <button class="ca-btn kucuk ana" type="button" data-koku="${esc(k.id)}">📖 Tam Metni Oku</button>
              <button class="ca-btn kucuk altin" type="button" data-kekle="${esc(k.id)}">📝 Dilekçeye İçtihat Ekle</button>
              <a class="ca-btn kucuk" href="${esc(k.url)}" target="_blank" rel="noopener">↗ hayfahukuk.com</a>
            </div>`).join('') || '<p class="ca-soluk">Karar bulunamadı.</p>'}`;
          kson.querySelectorAll('[data-koku]').forEach(b => {
            b.onclick = async () => {
              kson.innerHTML = '<p class="ca-soluk">Karar metni yükleniyor…</p>';
              try {
                const d = await api('/api/hayfa/karar?id=' + encodeURIComponent(b.dataset.koku));
                kson.innerHTML = `<button class="ca-btn kucuk" type="button" id="hf-k-geri">← Sonuçlara Dön</button>
                  <button class="ca-btn kucuk altin" type="button" id="hf-k-yap">📝 Dilekçeye Ekle</button>
                  <div class="ca-kart"><h3>${esc(d.baslik)}</h3><pre style="max-height:420px;font-family:inherit;line-height:1.6">${esc(d.metin)}</pre></div>`;
                kson.querySelector('#hf-k-geri').onclick = ara;
                kson.querySelector('#hf-k-yap').onclick = () => metinEkleBelgeye(`\n${d.baslik}\n${d.metin}\n`, kapat);
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
      alan.querySelector('#hf-k-ara').onclick = ara;
      kq.addEventListener('keydown', e => { if (e.key === 'Enter') ara(); });
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
          mson.innerHTML = `<table>${(v.mevzuat || []).map(x => `<tr><td><a href="${esc(x.url)}" target="_blank" rel="noopener"><b>${esc(x.baslik)}</b></a></td></tr>`).join('') || '<tr><td class="ca-soluk">Sonuç yok.</td></tr>'}</table>`;
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
