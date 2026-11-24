/*
 * CanEditor — ipucu.js (v4.10.0)
 * ─────────────────────────────────────────────────────────────────────────────
 * TR: Arayüzün TAMAMINA ayrıntılı ipuçları ve pratik süzgeçler ekler. Hiçbir modülün koduna dokunmaz;
 *     DOM'u izler (MutationObserver) ve sonradan çizilen (Asistan, HAYFA, diyaloglar) her öğeyi de kapsar.
 *
 *   1. İPUCU: düğme, menü öğesi, sekme, açılır liste, giriş alanı ve onay kutusunun üzerine gelince (dokunmatikte
 *      uzun basınca) "ne yapar · kısayol · terminal karşılığı" kartı çıkar. Kaynak sırası:
 *        data-ipucu → SÖZLÜK[id] → SÖZLÜK[metin] → title → aria-label → placeholder/etiket.
 *      title öznitelikleri tarayıcının sade ipucu yerine bu karta taşınır (erişilebilirlik için aria-label kalır).
 *   2. TABLO SÜZGECİ: Asistan/HAYFA panellerindeki her <table> (3+ satır) üstüne "bu tabloda süz" kutusu eklenir
 *      (Türkçe karakter duyarsız, "-kelime" hariç tutar) ve başlığa tıklayınca sütuna göre sıralanır.
 *   3. HIZLI TARİH ÇİPLERİ: yan yana iki tarih alanı (başlangıç/bitiş) gördüğü her yere "Bugün · 7 gün · 30 gün ·
 *      Bu ay · Geçen ay · Bu yıl · Temizle" çipleri ekler; ayrıntılı süzgeç alanları aynen kalır.
 *   Ayarlar: localStorage 'ce-ipucu' = '0' ipuçlarını kapatır (Araçlar → Komut paletinde "İpuçları").
 *
 * EN: rich tooltips (incl. keyboard shortcut and CLI equivalent), per-table quick filter + sortable headers and
 *     quick date-range chips — applied to every current and future element via MutationObserver.
 */
(function () {
  'use strict';
  if (window.CanIpucu) return;

  const katla = t => String(t || '').toLocaleLowerCase('tr').normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/ı/g, 'i').replace(/[^\p{L}\p{N}%/.,() +\-−✕]/gu, ' ').replace(/\s+/g, ' ').trim();

  // ── Sözlük: anahtar = öğe id'si ya da GÖRÜNEN METNİN katlanmış hâli (emoji/işaretler atılır) ──────────────
  // [açıklama, kısayol, terminal karşılığı]
  const S = {
    // Dosya
    'yeni': ['Boş bir A4 UYAP belgesi açar (Times New Roman 12, UYAP kenar boşlukları 2,5/1,5 cm).', 'Ctrl+N'],
    'ac…': ['UDF, PDF, DOCX, ODT, TIFF ya da görüntü dosyası açar. UDF birebir (paragraf, tablo, imza) yüklenir; PDF/TIFF görüntü olarak gösterilir.', 'Ctrl+O'],
    'kaydet': ['Belgeyi açıldığı biçimde ve aynı yere kaydeder. İmzalı UDF değiştirildiyse imzanın bozulacağını önceden söyler.', 'Ctrl+S'],
    'uyap belgesi (.udf)': ['UYAP Havelsan UDF (format_id 1.8) olarak kaydeder: UTF-16 ofset tablosu, paragraf/sekme/girinti değerleri UYAP Editör ile birebir.', '', 'caneditor donustur'],
    'pdf (.pdf)': ['A4, metni seçilebilir (vektörel) PDF. Masaüstünde resmî Havelsan motoru + gömülü Times New Roman kullanılır.', '', 'caneditor donustur belge.udf --bicim pdf'],
    'word (.docx)': ['Microsoft Word belgesi olarak kaydeder (paragraf, kalın/italik, hizalama ve tablolar korunur).', '', 'caneditor donustur belge.udf --bicim docx'],
    'opendocument (.odt)': ['LibreOffice/OpenDocument biçimi; resmî Havelsan ODFDOM dışa aktarımıyla üretilir.', '', 'caneditor donustur belge.udf --bicim odt'],
    'cok sayfali tiff (.tiff)': ['Her sayfayı 200 dpi görüntü olarak tek TIFF dosyasında birleştirir (faks/tarayıcı uyumlu).'],
    'pdf olarak': ['Belgeyi PDF olarak paylaşır/indirir.'], 'udf olarak': ['Belgeyi UYAP UDF olarak paylaşır/indirir.'],
    'word olarak': ['Belgeyi Word (DOCX) olarak paylaşır/indirir.'], 'odt olarak': ['Belgeyi ODT olarak paylaşır/indirir.'],
    'tiff olarak': ['Belgeyi çok sayfalı TIFF olarak paylaşır/indirir.'], 'duz metin olarak': ['Biçimsiz düz metin (.txt) olarak paylaşır.'],
    'sayfa yapisi…': ['Kağıt yönü ve kenar boşlukları (sol/sağ/üst/alt, üst-alt bilgi uzaklığı). UYAP varsayılanı: sol 2,5 · sağ 1,5 · üst/alt 1,5 cm.'],
    'yazdir': ['Yazıcıya gönderir; sayfa düzeni ekrandakiyle aynıdır.', 'Ctrl+P'],
    'baski onizleme': ['Yazdırılacak sayfaları tam boyutta gösterir.'],
    'pdf indir': ['Belgenin PDF kopyasını indirir.'],
    'guncellemeleri denetle': ['GitHub Releases\'ta yeni CanEditor sürümü var mı bakar; varsa platformunuza uygun paketi önerir.'],
    // Düzen
    'geri al': ['Son değişikliği geri alır (sınırsız geçmiş).', 'Ctrl+Z'], 'yinele': ['Geri alınanı yeniden uygular.', 'Ctrl+Y'],
    'kes': ['Seçimi panoya taşır.', 'Ctrl+X'], 'kopyala': ['Seçimi panoya kopyalar.', 'Ctrl+C'],
    'tumunu sec': ['Tüm belgeyi seçer; hizalama ve biçim seçimin tamamına uygulanır.', 'Ctrl+A'],
    'bul / degistir…': ['Belgede arar, tek tek ya da toptan değiştirir. Büyük/küçük harf duyarlılığı seçilebilir.', 'Ctrl+F / Ctrl+H'],
    // Görünüm
    'sayfa gorunumu': ['A4 sayfalarıyla, UYAP Editör\'deki gibi sayfa sonlarını göstererek düzenler.'],
    'mobil akis gorunumu': ['Telefonda rahat yazım için sayfa sınırı olmadan akan görünüm; kaydedilen belge yine A4 olur.'],
    'belge anahatti (bolumler)': ['AÇIKLAMALAR, DELİLLER, SONUÇ VE İSTEM gibi başlıklardan içindekiler listesi; tıklayınca o bölüme gider.'],
    'odak modu (zen yazim)': ['Menüleri gizler, yalnız sayfa kalır.', 'Esc ile çık'],
    'gece modu (koyu arayuz)': ['Arayüzü koyu renge çevirir (sayfa beyaz kalır).'],
    'gece kagidi (koyu sayfa)': ['Sayfayı da koyulaştırır; çıktı ve kayıt etkilenmez.'],
    'cetvel': ['Yatay cetveli gösterir/gizler: girinti ve sekme duraklarını sürükleyerek ayarlayın.'],
    'genislige sigdir': ['Sayfayı pencere genişliğine yakınlaştırır.'], 'sayfaya sigdir': ['Tüm sayfayı ekrana sığdırır.'],
    // Ekle
    'tablo…': ['Satır/sütun sayısıyla kenarlıklı tablo ekler (UYAP tablo biçimi).'], 'resim…': ['Görüntü ekler (UDF içine gömülür).'],
    'sayfa sonu': ['İmlecin olduğu yerden yeni sayfaya geçer.', 'Ctrl+Enter'], 'tarih': ['Bugünün tarihini GG.AA.YYYY olarak ekler.'],
    'sag alt (uyap)': ['Sayfa numarasını sağ alta koyar (UYAP varsayılanı).'], 'orta alt': ['Sayfa numarasını ortaya koyar.'],
    'sol alt': ['Sayfa numarasını sol alta koyar.'], 'sag ust': ['Sayfa numarasını sağ üste koyar.'], 'kaldir': ['Sayfa numarasını kaldırır.'],
    'dava dilekcesi': ['HMK 119\'a uygun dava dilekçesi şablonu: mahkeme, taraflar, konu, açıklamalar, deliller, hukuki sebepler, sonuç ve istem.'],
    'cevap dilekcesi': ['HMK 129\'a uygun cevap dilekçesi şablonu.'], 'sure uzatim (hmk 127)': ['Cevap süresinin uzatılması talebi (HMK 127) şablonu.'],
    'delil listesi': ['Delil listesi şablonu (tanık, bilirkişi, belge, keşif).'], 'bilirkisi beyani': ['Bilirkişi raporuna beyan/itiraz şablonu.'],
    'istinaf basvurusu': ['İstinaf başvuru dilekçesi şablonu (HMK 342).'], 'icraya itiraz': ['İcra takibine itiraz (İİK 62) şablonu.'],
    'ihtarname': ['Noter ihtarnamesi şablonu.'],
    // Biçim (UYAP Editör paragraf seçenekleri)
    'paragraf secenekleri…': ['UYAP Editör\'ün "Paragraf" penceresinin karşılığı: önce/sonra boşluk (nk), ilk satır girintisi, sol/sağ girinti, satır aralığı ve hizalama. Seçili paragrafa ya da tüm belgeye uygulanır.'],
    '4 nk (uyap)': ['Paragraf ÖNCESİ 4 nokta boşluk — UYAP Editör varsayılanı.'], '8 nk (uyap)': ['Paragraf SONRASI 8 nokta boşluk — UYAP Editör varsayılanı.'],
    '1,16 (uyap hassas)': ['UYAP Editör\'ün ekranda kullandığı hassas satır aralığı (Java metrikleri).'],
    '1,35 (uyap standart)': ['UYAP\'ta en sık kullanılan satır aralığı.'], '1,25 cm (uyap)': ['UYAP dilekçelerinde standart ilk satır girintisi.'],
    'ozel bosluk gir…': ['Nokta (nk) cinsinden istediğiniz değeri girin (1 nk = 1/72 inç ≈ 0,35 mm).'],
    'ozel satir araligi…': ['Satır aralığını çarpan olarak girin (ör. 1,25).'],
    'tumu buyuk': ['Seçimi TÜRKÇE kurallarla büyük harfe çevirir (i→İ, ı→I).'], 'tumu kucuk': ['Seçimi Türkçe kurallarla küçük harfe çevirir.'],
    'ilk harfler buyuk': ['Her kelimenin ilk harfini büyütür.'], 'cumle duzeni': ['Yalnız cümle başlarını büyük yapar.'],
    'ustu cizili': ['Seçimin üstünü çizer.'], 'ust simge': ['Üst simge (x²).'], 'alt simge': ['Alt simge (H₂O).'],
    'bicimi temizle': ['Seçimdeki kalın/italik/renk/boyutu kaldırır, UYAP gövde biçimine döndürür.'],
    // Araçlar
    'komut paleti…': ['Tüm komutları adla arayıp çalıştırın.', 'Ctrl+K'],
    'havelsan uyap uyumluluk raporu…': ['Belgeyi UYAP Editör\'ün okuyacağı biçimle karşılaştırır: yazı tipi, ofsetler, girinti/sekme, desteklenmeyen öğeler.'],
    'dilekceyi otomatik bicimlendir…': ['Başlıkları ortalar/kalın yapar, paragraf girintilerini ve boşlukları UYAP standardına getirir.'],
    'kelime sayisi…': ['Kelime, karakter (boşluklu/boşluksuz), paragraf ve sayfa sayısı.'],
    // Asistan menüsü
    'uyap giris (e-imza / mobil imza)…': ['UYAP Avukat Portal oturumu ARKA PLANDA açılır: e-imza kartı takılıysa sessiz e-imza, değilse Mobil İmza isteği gönderilir ve oturum açılana kadar 1→2→5→10 dk aralıklarla tekrarlanır.', '', 'caneditor uyap giris'],
    'uyap dosyalarim (dava yonetimi)…': ['Tüm dava/icra dosyalarınız: taraflar, safahat, evraklar, hesaplar; müvekkil, durum ve metinle süzülür.', '', 'caneditor dosya liste'],
    'yeni evrak & tebligatlar…': ['Son taramadan beri UYAP\'a düşen yeni evrak ve UETS tebligatları.', '', 'caneditor evrak yeni'],
    'google drive & veritabani…': ['İndirilen evrakların Google Drive\'a eşitlenmesi, Drive arşivinde arama ve kopya temizliği.', '', 'caneditor drive durum'],
    'notion & ticktick…': ['Notion dava sayfaları ve TickTick görevleri. Görevler başlıktan bağımsız KİMLİK ve barkodla eşleşir; tamamlanan ve "yapılmayacak" görevler mükerrer/eksik denetiminde dikkate alınır.', '', 'caneditor ticktick denetle'],
    'resmi jar donustur & paylas…': ['UDF\'i resmî Havelsan UYAP Editör kütüphaneleriyle (pakete gömülü) PDF/ODT/DOCX\'e birebir çevirir.', '', 'caneditor donustur'],
    'yasal sure hesapla…': ['Tebliğ tarihinden 7/14/30 günlük süreleri ve tatil uyarılarını hesaplar.', '', 'caneditor sure 20.11.2026'],
    'gorsel/pdf → a4 pdf birlestir…': ['Fotoğraf, TIFF ve PDF\'leri UYAP\'ın kabul ettiği tek A4 PDF\'te birleştirir (NAPS2 yöntemi).', '', 'caneditor a4 a.jpg b.pdf -o ek.pdf'],
    'ajanda (durusma ve sure sonlari)…': ['Duruşmalar ve tebligat son günleri takvimi; tarih aralığı ve müvekkille süzülür.', '', 'caneditor ajanda --gun 30'],
    'uyap evrak katalogunda ara…': ['Tüm UYAP arşivinde Türkçe-duyarsız arama: tür, kategori, tarih aralığı, müvekkil, dosya durumu süzgeçleri.', '', 'caneditor evrak ara "tensip"'],
    'uets / uyap gorevleri…': ['Arka plan görevleri (UETS indirme, UYAP nöbetçi, Drive akışı, TickTick düzeni) ve canlı günlükleri.', '', 'caneditor gorevler'],
    'asistan sunucusu baglantisi…': ['Yerel Hukuk Asistanı sunucusuyla eşleştirme (masaüstünde otomatik).', '', 'caneditor durum'],
    // İmza
    'e-imza (akilli kart)…': ['Takılı akıllı kart/USB token ile nitelikli elektronik imza (sürücü kurmadan, PC/SC ile).', '', 'caneditor imzala belge.udf --yontem eimza'],
    'mobil imza…': ['GSM operatörünüz üzerinden Mobil İmza; telefonunuza onay bildirimi gelir.', '', 'caneditor imzala belge.udf --yontem mobil'],
    'imzayi dogrula': ['Belgedeki imzaları, imzacıyı ve belge bütünlüğünü doğrular.', '', 'caneditor dogrula belge.udf'],
    // id'ye göre
    '#btn-do-msign': ['Mobil İmza isteğini gönderir; telefonunuzdaki onaydan sonra imza UDF\'e gömülür. Arka planda çalışır.'],
    '#btn-refresh-sc': ['Takılı kart okuyucularını yeniden tarar (sürücü gerekmez).'],
    '#btn-do-eimza': ['Seçili sertifika ve PIN ile imzalar. Yanlış PIN kartın kalan deneme hakkını düşürür; uygulama PIN\'i asla kendiliğinden yeniden denemez.'],
    '#sc-pin': ['Kart PIN\'i. Kaydedilmez; günlüklerde maskelenir.'],
    '#msign-phone': ['Mobil İmza hattının numarası (05XX...).'], '#msign-tckn': ['T.C. kimlik numarası (11 hane).'],
    '#msign-operator': ['Hattın operatörü: Turkcell, Türk Telekom ya da Vodafone.'],
    '#btn-scope-selected': ['Ayarlar yalnız seçili paragraf(lar)a uygulanır.'], '#btn-scope-all': ['Ayarlar tüm belgeye uygulanır.'],
    '#p-space-before': ['Paragraf ÖNCESİ boşluk (nk). UYAP: 4'], '#p-space-after': ['Paragraf SONRASI boşluk (nk). UYAP: 8'],
    '#p-first-line': ['İlk satır girintisi (cm). UYAP dilekçelerinde 1,25 cm.'], '#p-left-indent': ['Sol girinti (cm): paragrafın tamamı sağa kayar.'],
    '#p-right-indent': ['Sağ girinti (cm).'], '#p-line-spacing': ['Satır aralığı çarpanı. UYAP standart 1,35.'],
    '#p-align-left': ['Sola hizala (UYAP Alignment=0).', 'Ctrl+L'], '#p-align-center': ['Ortala (Alignment=1).', 'Ctrl+E'],
    '#p-align-right': ['Sağa hizala (Alignment=2).', 'Ctrl+R'], '#p-align-justify': ['İki yana yasla (Alignment=3) — dilekçe gövdesi için UYAP standardı.', 'Ctrl+J'],
    '#btn-orient-portrait': ['Dikey A4 (210×297 mm).'], '#btn-orient-landscape': ['Yatay A4 — geniş tablolar için.'],
    '#m-left': ['Sol kenar boşluğu (cm). UYAP: 2,5'], '#m-right': ['Sağ kenar boşluğu (cm). UYAP: 1,5'],
    '#m-top': ['Üst kenar boşluğu (cm). UYAP: 1,5'], '#m-bottom': ['Alt kenar boşluğu (cm). UYAP: 1,5'],
    '#m-header': ['Üst bilginin sayfa kenarına uzaklığı (cm).'], '#m-footer': ['Alt bilginin sayfa kenarına uzaklığı (cm).'],
    '#find-query': ['Aranacak metin.'], '#replace-query': ['Yerine yazılacak metin.'], '#find-match-case': ['İşaretliyse "Ankara" ile "ankara" farklı sayılır.'],
    '#inDocSearchInput': ['Açık belgede ara; Enter sonraki eşleşmeye gider.'], '#btn-toggle-ruler': ['Cetveli göster/gizle.'],
    '#ce-cmd-input': ['Komut adını yazın: ok tuşlarıyla seçip Enter ile çalıştırın.'], '#ce-outline-search': ['Belge bölümlerinde ara.'],
    '#gemini-api-key-input': ['Google Gemini API anahtarı (yalnız bu cihazda saklanır).'],
    // Ortak diyalog düğmeleri
    'iptal': ['Değişiklikleri uygulamadan pencereyi kapatır.', 'Esc'], 'kapat': ['Pencereyi kapatır.', 'Esc'], '✕': ['Kapat', 'Esc'],
    'tamam': ['Onayla ve kapat.', 'Enter'], 'uygula & kaydet': ['Ayarları uygular ve bu belge için kaydeder.'],
    '−': ['Değeri bir adım azaltır.'], '+': ['Değeri bir adım artırır.'],
    'onceki': ['Önceki eşleşmeye gider.', 'Shift+Enter'], 'sonraki': ['Sonraki eşleşmeye gider.', 'Enter'],
    'degistir': ['Seçili eşleşmeyi değiştirir.'], 'tumunu degistir': ['Tüm eşleşmeleri tek adımda değiştirir (geri alınabilir).'],
    // Asistan içi sık düğmeler
    'calistir': ['Bu görevi arka planda başlatır; günlüğü canlı izleyebilirsiniz.', '', 'caneditor gorev <ad> --izle'],
    'durdur': ['Çalışan görevi durdurur (yarım kalan iş bir sonraki turda kaldığı yerden sürer).', '', 'caneditor gorev <ad> --durdur'],
    'filtrele': ['Seçili süzgeçlerle listeyi yeniler.'], 'tumu': ['Süzgeci kaldırır, tüm kayıtları gösterir.'],
    'tebligatlar': ['Yalnız tebligatlar (UETS + UYAP tebligat evrakları).'], 'kararlar': ['Yalnız kararlar (ara karar, gerekçeli karar, hüküm).'],
    'durusma zapti': ['Yalnız duruşma zabıtları.'], 'bilirkisi': ['Yalnız bilirkişi rapor ve yazıları.'], 'dilekceler': ['Yalnız dilekçeler.'],
  };
  // Anahtarlar görünen metinle AYNI biçimde katlanır (…, &, →, emoji atılır) — eşleşme bundan bağımsızdır.
  const SK = {};
  Object.keys(S).forEach(k => { SK[k.startsWith('#') ? k : katla(k)] = S[k]; });
  // Görev kimliklerinin açıklamaları (Görevler sekmesindeki ▶ düğmelerinde data-baslat="<kimlik>")
  const GOREV_CLI = id => `caneditor gorev ${id} --izle`;

  function ipucuBul(el) {
    if (el.dataset.ipucu) return [el.dataset.ipucu, el.dataset.ipucuKisayol || '', el.dataset.ipucuCli || ''];
    if (el.id && SK['#' + el.id]) return SK['#' + el.id];
    const baslat = el.dataset.baslat || el.dataset.durdur;
    const metinHam = (el.innerText || el.value || '').split('\n')[0];
    const anahtar = katla(metinHam).replace(/^[^\p{L}\p{N}−+✕]+/u, '').trim();
    if (anahtar && SK[anahtar]) {
      const v = SK[anahtar].slice();
      if (baslat && !v[2]) v[2] = GOREV_CLI(baslat);
      return v;
    }
    const t = el.getAttribute('data-ce-baslik') || el.getAttribute('aria-label') || el.getAttribute('placeholder');
    if (t) return [t, '', baslat ? GOREV_CLI(baslat) : ''];
    if (el.tagName === 'SELECT') {
      const lab = el.labels && el.labels[0] ? el.labels[0].innerText : '';
      return [`${lab ? lab + ': ' : ''}listeden seçin. Seçenekler: ${[...el.options].slice(0, 8).map(o => o.text).join(' · ')}${el.options.length > 8 ? ' …' : ''}`];
    }
    if (el.tagName === 'INPUT' && el.labels && el.labels[0]) return [el.labels[0].innerText];
    if (baslat) return [`Görev: ${baslat}`, '', GOREV_CLI(baslat)];
    if (metinHam && metinHam.trim().length > 2 && el.matches('button, [role=menuitem], .menu-item, a')) {
      return [metinHam.trim().replace(/…$/, '') + (metinHam.includes('…') ? ' — ayrıntılı pencere açar.' : '')];
    }
    return null;
  }

  // ── İpucu kartı ─────────────────────────────────────────────────────────────────────────────────────
  const stil = document.createElement('style');
  stil.textContent = `
    #ce-ipucu{position:fixed;z-index:2147483000;max-width:min(380px,92vw);background:#0f2341;color:#f1f5f9;border-radius:10px;
      padding:9px 12px;font:13px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;box-shadow:0 10px 28px rgba(0,0,0,.28);
      pointer-events:none;opacity:0;transform:translateY(4px);transition:opacity .12s,transform .12s}
    #ce-ipucu.acik{opacity:1;transform:none}
    #ce-ipucu .k{display:inline-block;margin-top:6px;margin-right:6px;padding:1px 7px;border-radius:6px;background:rgba(255,255,255,.14);font-size:12px}
    #ce-ipucu code{display:block;margin-top:6px;padding:4px 7px;border-radius:6px;background:rgba(0,0,0,.35);font:12px ui-monospace,Menlo,Consolas,monospace;color:#a5f3fc;white-space:pre-wrap}
    .ce-tablo-suz{display:flex;gap:6px;align-items:center;margin:6px 0}
    .ce-tablo-suz input{flex:1;min-width:140px;padding:5px 9px;border:1px solid var(--ce-border,#d0d5dd);border-radius:8px;background:var(--ce-surface,#fff);color:inherit}
    .ce-tablo-suz span{font-size:12px;opacity:.7;white-space:nowrap}
    th.ce-sirali{cursor:pointer;user-select:none} th.ce-sirali::after{content:" ↕";opacity:.35} th.ce-sirali[data-yon="1"]::after{content:" ↑";opacity:.9} th.ce-sirali[data-yon="-1"]::after{content:" ↓";opacity:.9}
    .ce-tarih-cip{display:flex;flex-wrap:wrap;gap:5px;margin:4px 0 6px}
    .ce-tarih-cip button{border:1px solid var(--ce-border,#d0d5dd);background:var(--ce-surface,#fff);color:inherit;border-radius:999px;padding:2px 9px;font-size:12px;cursor:pointer}
    .ce-tarih-cip button:hover{background:#0f2341;color:#fff}
  `;
  document.head.appendChild(stil);
  const kart = document.createElement('div');
  kart.id = 'ce-ipucu';
  kart.setAttribute('role', 'tooltip');
  const etkin = () => { try { return localStorage.getItem('ce-ipucu') !== '0'; } catch (e) { return true; } };
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  let zamanlayici = null, hedef = null;

  function goster(el, x, y) {
    const v = ipucuBul(el);
    if (!v || !v[0]) return;
    if (!kart.isConnected) document.body.appendChild(kart);
    kart.innerHTML = esc(v[0]) + (v[1] ? `<br><span class="k">⌨ ${esc(v[1])}</span>` : '') + (v[2] ? `<code>$ ${esc(v[2])}</code>` : '');
    const r = el.getBoundingClientRect();
    kart.style.left = '0px'; kart.style.top = '0px';
    kart.classList.add('acik');
    const w = kart.offsetWidth, h = kart.offsetHeight;
    let sol = Math.min(Math.max(8, (x != null ? x : r.left + r.width / 2) - w / 2), innerWidth - w - 8);
    let ust = r.bottom + 8;
    if (ust + h > innerHeight - 8) ust = Math.max(8, r.top - h - 8);
    kart.style.left = sol + 'px'; kart.style.top = ust + 'px';
  }
  function gizle() { clearTimeout(zamanlayici); hedef = null; kart.classList.remove('acik'); }

  const SECICI = 'button, [role=button], [role=menuitem], [role=tab], select, input:not([type=hidden]), textarea, .menu-item, .dropdown-item, nav button, [data-ipucu], [data-baslat], [data-durdur], label.ce-switch';
  function titleTasi(el) {
    // Tarayıcının sade title ipucu bizimkinin üstüne binmesin: title → data-ce-baslik (+ aria-label korunur)
    if (el.hasAttribute('title')) {
      const t = el.getAttribute('title');
      el.setAttribute('data-ce-baslik', t);
      if (!el.hasAttribute('aria-label')) el.setAttribute('aria-label', t);
      el.removeAttribute('title');
    }
  }
  document.addEventListener('mouseover', e => {
    if (!etkin()) return;
    const el = e.target.closest && e.target.closest(SECICI);
    if (!el || el === hedef) return;
    titleTasi(el);
    gizle();
    hedef = el;
    zamanlayici = setTimeout(() => { if (hedef === el) goster(el); }, 380);
  }, true);
  document.addEventListener('mouseout', e => { if (hedef && !hedef.contains(e.relatedTarget)) gizle(); }, true);
  document.addEventListener('focusin', e => { const el = e.target.closest && e.target.closest(SECICI); if (el && etkin() && e.target.matches(':focus-visible')) { titleTasi(el); hedef = el; goster(el); } }, true);
  document.addEventListener('focusout', gizle, true);
  ['scroll', 'mousedown', 'keydown', 'wheel'].forEach(t => document.addEventListener(t, gizle, true));
  // Dokunmatik: 550 ms uzun bas → ipucu (tıklama iptal edilmez; parmak kalkınca 2,5 sn sonra kapanır)
  let dokunma = null;
  document.addEventListener('touchstart', e => {
    if (!etkin()) return;
    const el = e.target.closest && e.target.closest(SECICI);
    if (!el) return;
    const t = e.touches[0];
    dokunma = setTimeout(() => { titleTasi(el); goster(el, t.clientX); setTimeout(gizle, 2500); }, 550);
  }, { passive: true, capture: true });
  ['touchend', 'touchmove', 'touchcancel'].forEach(t => document.addEventListener(t, () => clearTimeout(dokunma), { passive: true, capture: true }));

  // ── Tablo süzgeci + sıralama ────────────────────────────────────────────────────────────────────────
  function tabloGelistir(tbl) {
    if (tbl.dataset.ceSuz || tbl.closest('.ProseMirror, [contenteditable=true], .ce-page, .page')) return;
    const satirlar = () => [...tbl.querySelectorAll('tr')].filter(r => !r.querySelector('th'));
    if (satirlar().length < 3) return;
    tbl.dataset.ceSuz = '1';
    const kutu = document.createElement('div');
    kutu.className = 'ce-tablo-suz';
    kutu.innerHTML = '<input type="search" placeholder="Bu tabloda süz… (-kelime hariç tutar)" data-ipucu="Yalnız bu tablodaki satırları süzer: tüm kelimeleri içeren satırlar kalır, -kelime yazılanlar çıkarılır. Türkçe karakter duyarsızdır (ı=i, ş=s)."><span></span>';
    tbl.parentNode.insertBefore(kutu, tbl);
    const giris = kutu.querySelector('input'), sayac = kutu.querySelector('span');
    const suz = () => {
      const k = katla(giris.value).split(' ').filter(Boolean);
      const art = k.filter(x => !x.startsWith('-')), eks = k.filter(x => x.length > 1 && x.startsWith('-')).map(x => x.slice(1));
      let n = 0; const l = satirlar();
      l.forEach(r => { const m = katla(r.innerText); const ok = art.every(x => m.includes(x)) && !eks.some(x => m.includes(x)); r.style.display = ok ? '' : 'none'; n += ok; });
      sayac.textContent = giris.value ? `${n} / ${l.length}` : `${l.length} satır`;
    };
    giris.addEventListener('input', suz);
    suz();
    const basliklar = tbl.querySelectorAll('tr:first-child th');
    basliklar.forEach((th, i) => {
      th.classList.add('ce-sirali');
      th.dataset.ipucu = th.dataset.ipucu || `“${th.innerText.trim()}” sütununa göre sırala (tekrar tıklayınca ters).`;
      th.addEventListener('click', () => {
        const yon = th.dataset.yon === '1' ? -1 : 1;
        basliklar.forEach(x => delete x.dataset.yon);
        th.dataset.yon = String(yon);
        const l = satirlar(), ebeveyn = l[0] && l[0].parentNode;
        const deger = r => { const t = (r.children[i] && r.children[i].innerText || '').trim();
          const tr = t.match(/^(\d{2})\.(\d{2})\.(\d{4})/); if (tr) return `${tr[3]}${tr[2]}${tr[1]}`;
          const n = t.replace(/\./g, '').replace(',', '.').match(/^-?\d+(\.\d+)?/); return n && /^[\d.,\s₺%-]+$/.test(t) ? parseFloat(n[0]) : katla(t); };
        l.sort((a, b) => { const x = deger(a), y = deger(b); return (x > y ? 1 : x < y ? -1 : 0) * yon; }).forEach(r => ebeveyn.appendChild(r));
      });
    });
  }

  // ── Hızlı tarih çipleri ─────────────────────────────────────────────────────────────────────────────
  const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  function tarihCipleri(a) {
    if (a.dataset.ceCip) return;
    const kap = a.parentElement && a.parentElement.parentElement;
    if (!kap) return;
    const tarihler = [...kap.querySelectorAll('input[type=date]')];
    const i = tarihler.indexOf(a);
    if (i !== 0 || tarihler.length < 2) return;
    const b = tarihler[1];
    a.dataset.ceCip = b.dataset.ceCip = '1';
    const cip = document.createElement('div');
    cip.className = 'ce-tarih-cip';
    const bugun = new Date(), g = n => { const d = new Date(); d.setDate(d.getDate() + n); return d; };
    const secenek = [
      ['Bugün', iso(bugun), iso(bugun)], ['Son 7 gün', iso(g(-7)), iso(bugun)], ['Son 30 gün', iso(g(-30)), iso(bugun)],
      ['Önümüzdeki 7 gün', iso(bugun), iso(g(7))], ['Önümüzdeki 30 gün', iso(bugun), iso(g(30))],
      ['Bu ay', iso(new Date(bugun.getFullYear(), bugun.getMonth(), 1)), iso(new Date(bugun.getFullYear(), bugun.getMonth() + 1, 0))],
      ['Geçen ay', iso(new Date(bugun.getFullYear(), bugun.getMonth() - 1, 1)), iso(new Date(bugun.getFullYear(), bugun.getMonth(), 0))],
      ['Bu yıl', `${bugun.getFullYear()}-01-01`, `${bugun.getFullYear()}-12-31`], ['Temizle', '', '']];
    cip.innerHTML = secenek.map(([ad, x, y]) => `<button type="button" data-a="${x}" data-b="${y}" data-ipucu="Tarih aralığını “${ad}” olarak doldurur${x ? ` (${x} – ${y})` : ''}; ayrıntılı tarih alanları aynen kullanılabilir.">${ad}</button>`).join('');
    cip.addEventListener('click', e => {
      const d = e.target.closest('button'); if (!d) return;
      a.value = d.dataset.a; b.value = d.dataset.b;
      [a, b].forEach(x => { x.dispatchEvent(new Event('input', { bubbles: true })); x.dispatchEvent(new Event('change', { bubbles: true })); });
    });
    kap.insertBefore(cip, a.parentElement);
  }

  function tara(kok) {
    if (!kok || !kok.querySelectorAll) return;
    kok.querySelectorAll('[title]').forEach(el => { if (el.matches(SECICI)) titleTasi(el); });
    kok.querySelectorAll('#ca-panel table, .cw-tablo, .ca-tablo, .hf-tablo, [data-filtrelenebilir] table, .ce-modal table').forEach(tabloGelistir);
    kok.querySelectorAll('input[type=date]').forEach(tarihCipleri);
  }
  let bekleyen = false;
  const gozcu = new MutationObserver(() => {
    if (bekleyen) return;
    bekleyen = true;
    requestAnimationFrame(() => { bekleyen = false; tara(document.body); });
  });
  const basla = () => { tara(document.body); gozcu.observe(document.body, { childList: true, subtree: true }); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', basla); else basla();

  window.CanIpucu = {
    sozluk: S, bul: ipucuBul, tara,
    ac() { try { localStorage.setItem('ce-ipucu', '1'); } catch (e) {} },
    kapat() { try { localStorage.setItem('ce-ipucu', '0'); } catch (e) {} gizle(); },
  };
})();
