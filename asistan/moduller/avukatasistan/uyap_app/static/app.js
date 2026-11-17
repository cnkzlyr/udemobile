const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const BASE = location.protocol === 'file:' ? 'http://127.0.0.1:8080' : '';
let S = {cases: [], bridge: {}};

async function api(p) {
  const r = await fetch(BASE + p);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(j.error || r.status), {needLogin: j.needLogin});
  return j;
}
function view(v) {
  document.querySelectorAll('section').forEach(s => s.classList.toggle('hid', s.id !== 'v-' + v));
  document.querySelectorAll('nav button').forEach(b => b.classList.toggle('on', b.dataset.v === v));
  ({conn: loadConn, cases: loadCases, hear: () => loadHear(0, 30), intel: loadIntel, map: loadMap})[v]();
}
document.querySelectorAll('nav button').forEach(b => b.onclick = () => view(b.dataset.v));
const fail = (el, e) => { $(el).innerHTML = `<div class="card"><b class="er">Veri alınamadı</b><div class="mu">${esc(e.message)}</div>${e.needLogin ? '<p>🔌 Bağlantı sekmesinden tarayıcıyı açıp UYAP\'a giriş yapın.</p>' : ''}</div>`; };

// ---------- Bağlantı ----------
async function loadConn() {
  let st;
  try { st = await api('/api/bridge/status'); } catch (e) { return fail('#v-conn', e); }
  S.bridge = st;
  $('#conn').className = 'tag ' + (st.loggedIn ? 'ok' : st.browserAlive ? 'wr' : 'er');
  $('#conn').textContent = st.loggedIn ? 'UYAP bağlı' : st.browserAlive ? 'Giriş bekleniyor' : 'Tarayıcı kapalı';
  $('#v-conn').innerHTML = `
   <div class="card"><div class="row"><b>Tarayıcı (hata ayıklama portu ${st.port})</b><span class="tag ${st.browserAlive ? 'ok' : 'er'}">${st.browserAlive ? 'açık' : 'kapalı'}</span></div>
     <div class="row" style="margin-top:6px"><b>Köprü</b><span class="tag ${st.attached ? 'ok' : 'wr'}">${st.attached ? 'bağlandı' : 'bağlı değil'}</span></div>
     <div class="row" style="margin-top:6px"><b>UYAP oturumu</b><span class="tag ${st.loggedIn ? 'ok' : 'er'}">${st.loggedIn ? 'açık' : 'kapalı'}</span></div>
     <div class="mono mu" style="margin-top:8px">${esc(st.url || '-')}</div>
     <div class="mu" style="margin-top:6px">İstek sayısı: ${st.calls}</div></div>
   <div class="card"><p class="mu" style="margin-top:0">1) Tarayıcıyı açın ve UYAP'a e-imza / mobil imza ile kendiniz giriş yapın.<br>2) Giriş sonrası “Bağlan”a basın. Zaten bağlantı modunda açık bir tarayıcınız varsa doğrudan “Bağlan”.</p>
     <button onclick="act('/api/bridge/launch')">Tarayıcıyı aç</button> <button onclick="act('/api/bridge/attach')">Bağlan</button> <button class="sec" onclick="loadConn()">Yenile</button></div>
   <div class="card mu">Güvenlik: yalnızca salt-okunur uç noktalar çağrılır; kaydet/sil/gönder/imzala engellidir. İstekler sayfanın kendi oturumuyla ve hız sınırıyla gider.</div>`;
  if (st.loggedIn) api('/api/user').then(u => $('#who').textContent = `${u.adi || ''} ${u.soyadi || ''}`).catch(() => {});
}
async function act(p) { try { await api(p); } catch (e) { alert(e.message); } setTimeout(loadConn, 800); }

// ---------- Dosyalar ----------
async function loadCases() {
  $('#cases').innerHTML = '<div class="card mu">UYAP\'tan dosyalar alınıyor…</div>';
  try { const r = await api('/api/cases'); S.cases = r.items; S.cached = r.cached; renderCases(); } catch (e) { fail('#cases', e); }
}
function renderCases() {
  const q = ($('#q').value || '').toLowerCase();
  const l = S.cases.filter(c => `${c.dosyaNo} ${c.birimAdi} ${c.dosyaTur}`.toLowerCase().includes(q));
  $('#cases').innerHTML = (S.cached ? '<div class="card"><span class="tag wr">Önbellek: son gerçek veri</span></div>' : '') +
    (l.map(c => `<div class="card" onclick='openCase(${JSON.stringify(c.dosyaId)})'><div class="row"><b>${esc(c.dosyaNo)}</b><span class="tag ${c.dosyaDurum === 'Açık' ? 'ok' : ''}">${esc(c.dosyaDurum)}</span></div>
     <div>${esc(c.birimAdi)}</div><div class="mu">${esc(c.dosyaTur)} · ${esc(c.acilisTarihi)}</div></div>`).join('') || '<div class="card mu">Dosya bulunamadı.</div>');
}
async function openCase(id) {
  $('#cases').innerHTML = '<div class="card mu">Dosya ayrıntıları alınıyor…</div>';
  try {
    const d = await api('/api/cases/' + encodeURIComponent(id));
    const taraf = Array.isArray(d.taraflar) ? d.taraflar : [];
    $('#cases').innerHTML = `<button class="sec" onclick="renderCases()">← Geri</button>
     <h3>Taraflar</h3>${taraf.map(t => `<div class="card"><b>${esc(t.adi)}</b> <span class="tag">${esc(t.rol)}</span><div class="mu">${esc(t.vekil || '')}</div></div>`).join('') || '<div class="mu">-</div>'}
     <h3>Evraklar (${d.evraklar.length})</h3>${d.evraklar.map(e => `<div class="card"><div class="row"><div><b>${esc(e.tur || 'Evrak')}</b><div class="mu">${esc(e.aciklama)} ${esc(e.tarih)}</div></div>
      <a class="btn" target="_blank" href="${BASE}/api/document/${encodeURIComponent(e.evrakId)}?dosyaId=${encodeURIComponent(id)}">Aç</a></div></div>`).join('')}
     <h3>Safahat</h3>${d.safahat.map(s => `<div class="todo"><span class="mu">${esc(s.tarih)}</span> ${esc(s.islem)}</div>`).join('') || '<div class="mu">-</div>'}
     <h3>Hesap</h3>${(Array.isArray(d.hesap) ? d.hesap : []).map(h => `<div class="row todo"><span>${esc(h.textAlan)}</span><b>${esc(h.degerAlan ?? '')}</b></div>`).join('')}`;
  } catch (e) { fail('#cases', e); }
}

// ---------- Duruşmalar ----------
async function loadHear(back, fwd) {
  $('#hear').innerHTML = '<div class="card mu">Yükleniyor…</div>';
  try {
    const r = await api(`/api/hearings?back=${back}&fwd=${fwd}`);
    $('#hear').innerHTML = r.items.map(h => `<div class="card"><div class="row"><b>${esc(h.dosyaNo)}</b><span class="tag">${esc(h.tarih)} ${esc(h.saat)}</span></div>
      <div>${esc(h.birimAdi)}</div><div class="mu">${esc(h.tur)} ${h.sonuc ? '· <b>' + esc(h.sonuc) + '</b>' : ''}</div><div class="mu">${h.taraflar.map(t => esc(t.sifat + ': ' + t.isim)).join(' · ')}</div></div>`).join('') || '<div class="card mu">Kayıt yok.</div>';
  } catch (e) { fail('#hear', e); }
}

// ---------- Analiz ----------
async function loadIntel() {
  try {
    const r = await api('/api/intel');
    const items = Object.entries(r.items);
    $('#v-intel').innerHTML = `<div class="card"><b>Son 30 gün duruşma tutanakları</b><p class="mu">Duruşmaların evraklarından tutanak/zabıtları bulur, indirir, UDF/PDF metnini okur ve yapılacakları ayıklar.</p>
      <button onclick="startIntel()" ${r.running ? 'disabled' : ''}>${r.running ? 'Çalışıyor…' : 'Analizi başlat'}</button> <button class="sec" onclick="loadIntel()">Yenile</button>
      <div class="mu" style="margin-top:6px">${esc(r.progress)}</div></div>` +
      items.map(([id, it]) => `<div class="card"><b>${esc(it.dosyaNo)}</b> <span class="mu">${esc(it.birim)}</span>
        ${Object.values(it.belgeler).map(b => `<div style="margin-top:8px"><span class="tag">${esc(b.ad || 'Belge')}</span> ${b.hata ? `<span class="er">${esc(b.hata)}</span>` : ''}
          <div class="mu">${esc(b.ozet || '')}</div>${(b.tarihler || []).length ? `<div class="tag wr">Tarihler: ${esc(b.tarihler.join(', '))}</div>` : ''}
          ${(b.yapilacaklar || []).map(t => `<div class="todo ${it.yapildi.includes(t) ? 'done' : ''}" onclick='tg(${JSON.stringify(id)},${JSON.stringify(t)})'>${it.yapildi.includes(t) ? '☑' : '☐'} ${esc(t)}</div>`).join('')}</div>`).join('')}
        ${(it.digerEvraklar || []).length ? `<details class="mu"><summary>Diğer evraklar (${it.digerEvraklar.length})</summary>${it.digerEvraklar.map(esc).join('<br>')}</details>` : ''}</div>`).join('') +
      `<a class="btn" target="_blank" href="${BASE}/api/intel/proposals">TickTick/Notion önerileri (JSON)</a>`;
    if (r.running) setTimeout(loadIntel, 4000);
  } catch (e) { fail('#v-intel', e); }
}
async function startIntel() { try { await api('/api/intel/start?days=30'); } catch (e) { alert(e.message); } loadIntel(); }
async function tg(id, t) { await api(`/api/intel/toggle?dosyaId=${encodeURIComponent(id)}&todo=${encodeURIComponent(t)}`); loadIntel(); }

// ---------- Harita ----------
async function loadMap() {
  try {
    const r = await api('/api/discovery');
    $('#v-map').innerHTML = `<div class="card"><div class="row"><b>UYAP Haritası</b><span class="tag ${r.explore ? 'ok' : ''}">${r.explore ? 'keşif açık' : 'keşif kapalı'}</span></div>
      <div class="mu">${r.endpointCount} uç nokta · ${r.newEndpoints.length} yeni · ${r.staticRefs} JS referansı · ${r.menuItems} menü öğesi</div>
      <div style="margin-top:8px"><button onclick="explore(${r.explore ? 0 : 1})">${r.explore ? 'Keşfi durdur' : 'Güvenli menü keşfini başlat'}</button>
      <a class="btn sec" style="background:#1c2540" target="_blank" href="${BASE}/api/discovery/export">Markdown</a> <button class="sec" onclick="loadMap()">Yenile</button></div>
      <div class="mono mu" style="margin-top:8px">${r.log.slice(-8).map(esc).join('<br>')}</div></div>
      <h3>Haritada olup henüz çağrılmamış (${r.unexplored.length})</h3><div class="card mono">${r.unexplored.slice(0, 80).map(esc).join('<br>') || '-'}</div>
      <h3>Uç noktalar</h3>${r.endpoints.map(e => `<div class="card"><div class="row"><span class="mono">${esc(e.method)} ${esc(e.path)}</span><span class="tag ${e.isNew ? 'wr' : ''}">${e.hits}${e.isNew ? ' 🆕' : ''}</span></div></div>`).join('')}`;
  } catch (e) { fail('#v-map', e); }
}
async function explore(on) { await api('/api/discovery/explore?on=' + on).catch(e => alert(e.message)); loadMap(); }

loadConn();
setInterval(() => { if (!$('#v-conn').classList.contains('hid')) loadConn(); }, 8000);
