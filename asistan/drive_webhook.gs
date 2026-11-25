// ===========================================================================
// CanEditor — UYAP Google Drive Webhook Betiği (script.google.com)          SÜRÜM 3
// Bu kodu Google Drive'ınızda "Yeni > Diğer > Google Apps Script" açıp yapıştırın.
// Ardından "Dağıt (Deploy) > Yeni Dağıtım > Web Uygulaması" (Erişim: Herkes) seçip URL'yi alın.
// GÜNCELLEME: Kodu yapıştırdıktan sonra "Dağıt > Dağıtımları yönet > ✏️ > Sürüm: Yeni sürüm > Dağıt"
// yapın; Web Uygulaması adresi (URL) DEĞİŞMEZ, CanEditor'da bir şey değiştirmeniz gerekmez.
//
// Sürüm 3 (CanEditor 4.10.2) düzeltmeleri:
//  * KÖK SABİT: Eskiden DriveApp.getFoldersByName("UYAP_Arsiv") Drive'daki HERHANGİ bir "UYAP_Arsiv"
//    klasörünü kök alıyordu. İstemci yolun başına "UYAP_Arsiv/" ekleyince iç içe UYAP_Arsiv/UYAP_Arsiv/...
//    klasörleri oluşuyor, kök rastgele seçildiği için aynı evrak iki ayrı yere ikişer kopya düşüyordu.
//    Artık kök, Drive'ım'ın DOĞRUDAN altındaki UYAP_Arsiv'dir; kimliği betik ayarlarında saklanır.
//  * Yolun başındaki "UYAP_Arsiv" parçaları atılır (iç içe klasör bir daha oluşmaz).
//  * uzerine_yaz: true → aynı klasörde aynı adlı dosyalar çöp kutusuna (30 gün geri alınabilir) taşınıp yenisi
//    yazılır. Onarılan PDF artık bozuk olanın YANINA değil YERİNE geçer.
//  * Dosya türü uzantıdan belirlenir (EYP, CSV, JSON, UDF, TIFF de doğru türle saklanır).
//  * "ic_ice_duzelt": UYAP_Arsiv altındaki iç içe UYAP_Arsiv klasörlerini köke birleştirir (aynı ad+boyut kopyalar
//    çöpe, diğerleri taşınır; boşalan klasör çöpe). Uzun sürerse "state" ile kaldığı yerden devam eder.
//  * "bul": klasör yolu + dosya adıyla dosyayı bulur (onarım öncesi kontrol için).
// ===========================================================================
var BETIK_SURUM = 3;
var KOK_ADI = "UYAP_Arsiv";

function _json(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

// Drive'ım'ın doğrudan altındaki UYAP_Arsiv (yoksa oluşturulur); kimliği betik ayarlarında tutulur.
function _kok() {
  var p = PropertiesService.getScriptProperties();
  var id = p.getProperty("KOK_ID");
  if (id) {
    try { var f = DriveApp.getFolderById(id); if (!f.isTrashed()) return f; } catch (e) {}
  }
  var it = DriveApp.getRootFolder().getFoldersByName(KOK_ADI);
  var kok = it.hasNext() ? it.next() : DriveApp.getRootFolder().createFolder(KOK_ADI);
  p.setProperty("KOK_ID", kok.getId());
  return kok;
}

function _parcalar(yol) {
  var l = String(yol || "").replace(/\\/g, "/").split("/").map(function (x) { return x.trim(); })
    .filter(function (x) { return x; });
  while (l.length && l[0] === KOK_ADI) l.shift();   // "UYAP_Arsiv/..." ile gelen yollar iç içe klasör açmasın
  return l;
}

function _klasor(yol, olustur) {
  var f = _kok(), l = _parcalar(yol);
  for (var i = 0; i < l.length; i++) {
    var s = f.getFoldersByName(l[i]);
    if (s.hasNext()) f = s.next();
    else if (olustur) f = f.createFolder(l[i]);
    else return null;
  }
  return f;
}

var MIME = { pdf: "application/pdf", udf: "application/zip", eyp: "application/zip", zip: "application/zip",
  csv: "text/csv", json: "application/json", md: "text/markdown", txt: "text/plain", xml: "application/xml",
  tif: "image/tiff", tiff: "image/tiff", jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", odt: "application/vnd.oasis.opendocument.text" };

function _mime(ad) {
  var m = /\.([a-z0-9]+)$/i.exec(ad || "");
  return (m && MIME[m[1].toLowerCase()]) || "application/octet-stream";
}

// Drive'ı klasör klasör gezer; ~25 sn veya 2000 dosyada durup "state" döner (Apps Script 6 dk sınırı).
function _listele(data) {
  var basla = Date.now();
  var st = data.state ? JSON.parse(data.state) : null;
  if (!st) {
    var kok = data.kok ? (data.kok === KOK_ADI ? _kok() : _klasor(data.kok, false)) : DriveApp.getRootFolder();
    if (!kok) return { status: "error", message: "Klasör bulunamadı: " + data.kok };
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

// Aynı klasörde aynı ad + aynı boyuttaki kopyaları çöp kutusuna taşır (en eski kalır).
function _kopyaTemizle(data) {
  var basla = Date.now();
  var st = data.state ? JSON.parse(data.state) : { q: [_kok().getId()] };
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

// src klasörünün içeriğini dst'ye birleştirir: aynı ad+boyut dosya çöpe, farklı dosya taşınır, aynı adlı alt
// klasörler özyinelemeli birleşir. Süre dolarsa false döner (bir sonraki çağrı kaldığı yerden sürer).
function _birlestir(src, dst, basla, sayac) {
  var alt = src.getFolders();
  while (alt.hasNext()) {
    if (Date.now() - basla > 24000) return false;
    var a = alt.next();
    var hedef = a.getName() === KOK_ADI ? dst : null;
    if (!hedef) { var es = dst.getFoldersByName(a.getName()); hedef = es.hasNext() ? es.next() : null; }
    if (hedef) { if (!_birlestir(a, hedef, basla, sayac)) return false; a.setTrashed(true); sayac.klasor++; }
    else { a.moveTo(dst); sayac.tasinan++; }
  }
  var it = src.getFiles();
  while (it.hasNext()) {
    if (Date.now() - basla > 24000) return false;
    var d = it.next(), ayni = false, es2 = dst.getFilesByName(d.getName());
    while (es2.hasNext()) { if (es2.next().getSize() === d.getSize()) { ayni = true; break; } }
    if (ayni) { d.setTrashed(true); sayac.kopya++; } else { d.moveTo(dst); sayac.tasinan++; }
  }
  return true;
}

// UYAP_Arsiv altındaki TÜM iç içe "UYAP_Arsiv" klasörlerini bir üstüne birleştirir.
function _icIceDuzelt(data) {
  var basla = Date.now(), sayac = { tasinan: 0, kopya: 0, klasor: 0 };
  var kok = _kok(), q = [kok], bitti = true;
  while (q.length) {
    var f = q.shift(), alt = f.getFolders();
    while (alt.hasNext()) {
      var a = alt.next();
      if (a.getName() === KOK_ADI) {
        if (!_birlestir(a, f, basla, sayac)) { bitti = false; break; }
        a.setTrashed(true); sayac.klasor++;
      } else { q.push(a); }
    }
    if (!bitti || Date.now() - basla > 24000) { bitti = false; break; }
  }
  return { status: "ok", surum: BETIK_SURUM, bitti: bitti, tasinan: sayac.tasinan, kopya_cope: sayac.kopya,
    birlesen_klasor: sayac.klasor };
}

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    if (data.action === "ping" || data.test) {
      return _json({ status: "ok", surum: BETIK_SURUM, kok: _kok().getId(), message: "Bağlantı başarılı!" });
    }
    if (data.action === "list") return _json(_listele(data));
    if (data.action === "kopya_temizle") return _json(_kopyaTemizle(data));
    if (data.action === "ic_ice_duzelt") return _json(_icIceDuzelt(data));
    if (data.action === "get") {
      var gf = DriveApp.getFileById(data.id);
      var b = gf.getBlob();
      return _json({ status: "ok", ad: gf.getName(), mime: b.getContentType(), content: Utilities.base64Encode(b.getBytes()) });
    }
    if (data.action === "bul") {
      var bk = _klasor(data.folder_path, false);
      if (!bk) return _json({ status: "ok", bulunan: [] });
      var bl = [], bi = bk.getFilesByName(data.filename || "");
      while (bi.hasNext()) { var x = bi.next(); bl.push({ id: x.getId(), boyut: x.getSize(), url: x.getUrl() }); }
      return _json({ status: "ok", bulunan: bl });
    }

    // Yükleme
    var folder = _klasor(data.folder_path, true);
    var decoded = Utilities.base64Decode(data.content);
    var ad = data.filename || "evrak.pdf";
    var mevcut = folder.getFilesByName(ad), cope = 0;
    while (mevcut.hasNext()) {
      var mf = mevcut.next();
      if (mf.getSize() === decoded.length && !data.uzerine_yaz) {
        return _json({ status: "success", mevcut: true, filename: ad, fileId: mf.getId(), url: mf.getUrl() });
      }
      if (data.uzerine_yaz) { mf.setTrashed(true); cope++; }
    }
    var file = folder.createFile(Utilities.newBlob(decoded, data.mime || _mime(ad), ad));
    return _json({ status: "success", filename: ad, fileId: file.getId(), url: file.getUrl(), degisti: cope > 0, surum: BETIK_SURUM });
  } catch (err) {
    return _json({ status: "error", message: err.toString() });
  }
}

function doGet(e) {
  return _json({ status: "ok", surum: BETIK_SURUM, message: "CanEditor Google Drive Webhook Aktif" });
}
