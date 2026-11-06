/**
 * CanEditor arayüz kabuğu: UYAP Doküman Editörü ile aynı menü çubuğu davranışı.
 * - Tıkla aç, menüler arasında üzerinden geç, dışarı tıkla / Esc ile kapat.
 * - Menüden bir komut seçilince menü kapanır ve editör odağı korunur.
 */
(function () {
  const bar = document.getElementById('ce-menubar');
  if (!bar) return;
  let open = null;
  const close = () => { if (open) open.classList.remove('open'); open = null; bar.classList.remove('active'); };
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
})();
