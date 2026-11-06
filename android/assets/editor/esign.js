/**
 * CanEditor — Platformlar Arası E-İmza / Mobil İmza Motoru (esign.js)
 *
 * Tüm platformlarda (Android, Windows, macOS, Linux, Web) AYNI imza mantığı çalışır.
 * Platformlar yalnızca "ham" işlemleri sağlar:
 *   - http(url, body, headers)         : UYAP mobil imza SOAP çağrısı (tarayıcı CORS'u aşmak için yerel köprü)
 *   - scList() / scSign(...)           : Akıllı karttan sertifika okuma ve ham imza (PKCS#11 / USB CCID)
 *
 * UYAP (Havelsan Doküman Editörü 5.x) ile birebir uyum — tersine mühendislikle doğrulandı:
 *   - İmzalanan veri: UDF içindeki content.xml baytlarının KENDİSİ (detached CMS).
 *   - sign.sgn = CMS ContentInfo(signedData), eContentType=data, eContent YOK (ayrık imza).
 *   - SignerInfo imzalı öznitelikleri (CAdES-BES): contentType, signingTime, messageDigest(SHA-256),
 *     signingCertificateV2 (ESSCertIDv2: SHA-256 sertifika özeti + IssuerSerial).
 *   - İmza algoritması: sha256WithRSAEncryption (NULL parametreli) / ecdsa-with-SHA256.
 *   - Çoklu imza: aynı SignedData içine paralel SignerInfo + sertifika eklenir (Havelsan combineSignatures).
 *   - Mobil imza: http://vatandas.uyap.gov.tr/mimzaclient/services/MImzaSigner
 *       getHash(dataToBeSigned=content.xml, telNo="05XXXXXXXXX" (11 hane), gsmOperator=1 Turkcell|2 Türk Telekom|3 Vodafone)
 *       getSignature(dataToBeDisplayed="Evrak Mobil Imza Talebi", apTransId) → SignatureResult.data = CMS
 */
(function () {
  'use strict';

  const MIMZA_URL = 'http://vatandas.uyap.gov.tr/mimzaclient/services/MImzaSigner';
  const OID = {
    data: '1.2.840.113549.1.7.1',
    signedData: '1.2.840.113549.1.7.2',
    contentType: '1.2.840.113549.1.9.3',
    messageDigest: '1.2.840.113549.1.9.4',
    signingTime: '1.2.840.113549.1.9.5',
    signingCertificateV2: '1.2.840.113549.1.9.16.2.47',
    sha256: '2.16.840.1.101.3.4.2.1',
    sha384: '2.16.840.1.101.3.4.2.2',
    sha512: '2.16.840.1.101.3.4.2.3',
    rsaEncryption: '1.2.840.113549.1.1.1',
    sha256WithRSA: '1.2.840.113549.1.1.11',
    ecPublicKey: '1.2.840.10045.2.1',
    ecdsaSha256: '1.2.840.10045.4.3.2',
    cn: '2.5.4.3',
    serialNumber: '2.5.4.5',
    title: '2.5.4.12'
  };

  // ------------------------------------------------------------------ bayt yardımcıları
  const enc = new TextEncoder();
  function concat(parts) {
    let n = 0; parts.forEach(p => { n += p.length; });
    const out = new Uint8Array(n); let o = 0;
    parts.forEach(p => { out.set(p, o); o += p.length; });
    return out;
  }
  function eq(a, b) { if (a.length !== b.length) return false; for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false; return true; }
  function cmp(a, b) { const n = Math.min(a.length, b.length); for (let i = 0; i < n; i++) if (a[i] !== b[i]) return a[i] - b[i]; return a.length - b.length; }
  function b64e(u8) { let s = ''; for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000)); return btoa(s); }
  function b64d(s) { const bin = atob(String(s || '').replace(/\s+/g, '')); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; }
  async function sha256(u8) { return new Uint8Array(await crypto.subtle.digest('SHA-256', u8)); }
  const hex = (u8) => Array.from(u8).map(b => b.toString(16).padStart(2, '0')).join('');

  // ------------------------------------------------------------------ DER kodlayıcı
  function derLen(n) {
    if (n < 0x80) return Uint8Array.of(n);
    const b = []; while (n > 0) { b.unshift(n & 0xff); n = Math.floor(n / 256); }
    return Uint8Array.from([0x80 | b.length, ...b]);
  }
  function tlv(tag, ...parts) { const body = concat(parts); return concat([Uint8Array.of(tag), derLen(body.length), body]); }
  const SEQ = (...p) => tlv(0x30, ...p);
  const SET = (...p) => tlv(0x31, ...p);
  const SETOF = (items) => tlv(0x31, ...items.slice().sort(cmp)); // DER: SET OF elemanları sıralı
  const NULL = () => Uint8Array.of(0x05, 0x00);
  const OCTET = (u8) => tlv(0x04, u8);
  const INT = (n) => tlv(0x02, Uint8Array.of(n));
  function OIDv(s) {
    const a = s.split('.').map(Number); const out = [a[0] * 40 + a[1]];
    for (let i = 2; i < a.length; i++) {
      let v = a[i]; const tmp = [v & 0x7f]; v = Math.floor(v / 128);
      while (v > 0) { tmp.unshift((v & 0x7f) | 0x80); v = Math.floor(v / 128); }
      out.push(...tmp);
    }
    return tlv(0x06, Uint8Array.from(out));
  }
  function UTCTIME(d) {
    const p = (n) => String(n).padStart(2, '0');
    const s = p(d.getUTCFullYear() % 100) + p(d.getUTCMonth() + 1) + p(d.getUTCDate()) + p(d.getUTCHours()) + p(d.getUTCMinutes()) + p(d.getUTCSeconds()) + 'Z';
    return tlv(0x17, enc.encode(s));
  }

  // ------------------------------------------------------------------ DER çözücü
  function read(b, o) {
    const tag = b[o]; let l = b[o + 1]; let h = 2;
    if (l & 0x80) { const n = l & 0x7f; l = 0; for (let i = 0; i < n; i++) l = l * 256 + b[o + 2 + i]; h += n; }
    return { tag, start: o, hl: h, len: l, cs: o + h, end: o + h + l, raw: () => b.subarray(o, o + h + l), body: () => b.subarray(o + h, o + h + l) };
  }
  function kids(b, node) { const out = []; let o = node.cs; while (o < node.end) { const k = read(b, o); out.push(k); o = k.end; } return out; }
  function oidStr(u8) {
    const v = [Math.floor(u8[0] / 40), u8[0] % 40]; let n = 0;
    for (let i = 1; i < u8.length; i++) { n = n * 128 + (u8[i] & 0x7f); if (!(u8[i] & 0x80)) { v.push(n); n = 0; } }
    return v.join('.');
  }
  function decodeStr(node) {
    const body = node.body();
    if (node.tag === 0x1e) { let s = ''; for (let i = 0; i + 1 < body.length; i += 2) s += String.fromCharCode((body[i] << 8) | body[i + 1]); return s; }
    try { return new TextDecoder('utf-8').decode(body); } catch (e) { return ''; }
  }

  // X.509 sertifikasından imza için gerekli alanlar
  function parseCert(der) {
    const cert = read(der, 0);
    const tbs = kids(der, cert)[0];
    const t = kids(der, tbs);
    let i = 0;
    if (t[0].tag === 0xa0) i = 1; // version
    const serial = t[i], issuer = t[i + 2], validity = t[i + 3], subject = t[i + 4], spki = t[i + 5];
    const nameAttrs = (nameNode) => {
      const out = {};
      kids(der, nameNode).forEach(rdn => kids(der, rdn).forEach(atv => {
        const [o, v] = kids(der, atv);
        out[oidStr(o.body())] = decodeStr(v);
      }));
      return out;
    };
    const subj = nameAttrs(subject), iss = nameAttrs(issuer);
    const val = kids(der, validity).map(v => decodeStr(v));
    const algNode = kids(der, kids(der, spki)[0])[0];
    const keyAlg = oidStr(algNode.body());
    return {
      der,
      serialTLV: serial.raw(),
      issuerTLV: issuer.raw(),
      subjectCN: subj[OID.cn] || '',
      subjectSerial: (subj[OID.serialNumber] || '').replace(/^TCKTR-|^PNOTR-/i, ''),
      subjectTitle: subj[OID.title] || '',
      issuerCN: iss[OID.cn] || '',
      notBefore: val[0] || '',
      notAfter: val[1] || '',
      keyType: keyAlg === OID.ecPublicKey ? 'EC' : 'RSA'
    };
  }

  // ------------------------------------------------------------------ CAdES-BES oluşturma
  async function buildSignedAttrs(contentBytes, certDer, when) {
    const c = parseCert(certDer);
    const md = await sha256(contentBytes);
    const certHash = await sha256(certDer);
    const essCertIdV2 = SEQ(OCTET(certHash), SEQ(SEQ(tlv(0xa4, c.issuerTLV)), c.serialTLV)); // hashAlgorithm varsayılan SHA-256 → yazılmaz
    const attrs = [
      SEQ(OIDv(OID.contentType), SET(OIDv(OID.data))),
      SEQ(OIDv(OID.signingTime), SET(UTCTIME(when || new Date()))),
      SEQ(OIDv(OID.messageDigest), SET(OCTET(md))),
      SEQ(OIDv(OID.signingCertificateV2), SET(SEQ(SEQ(essCertIdV2))))
    ];
    const setDer = SETOF(attrs);         // imzalanacak bayt dizisi (SET etiketiyle)
    return { setDer, digestOfAttrs: await sha256(setDer), cert: c };
  }
  // DER INTEGER (r,s) — PKCS#11 CKM_ECDSA ham r||s döndürür, CMS DER ister
  function ecdsaRawToDer(raw) {
    const half = raw.length / 2;
    const fix = (x) => { let i = 0; while (i < x.length - 1 && x[i] === 0) i++; x = x.subarray(i); return (x[0] & 0x80) ? concat([Uint8Array.of(0), x]) : x; };
    return SEQ(tlv(0x02, fix(raw.subarray(0, half))), tlv(0x02, fix(raw.subarray(half))));
  }
  function assembleCms(signed, signature, keyType) {
    const c = signed.cert;
    const signedAttrsImplicit = concat([Uint8Array.of(0xa0), signed.setDer.subarray(1)]);
    let sigAlg = SEQ(OIDv(OID.sha256WithRSA), NULL());
    let sig = signature;
    if ((keyType || c.keyType) === 'EC') {
      sigAlg = SEQ(OIDv(OID.ecdsaSha256));
      if (sig[0] !== 0x30) sig = ecdsaRawToDer(sig);
    }
    const signerInfo = SEQ(
      INT(1),
      SEQ(c.issuerTLV, c.serialTLV),
      SEQ(OIDv(OID.sha256)),
      signedAttrsImplicit,
      sigAlg,
      OCTET(sig)
    );
    const signedData = SEQ(
      INT(1),
      SET(SEQ(OIDv(OID.sha256))),
      SEQ(OIDv(OID.data)),
      tlv(0xa0, c.der),
      SET(signerInfo)
    );
    return SEQ(OIDv(OID.signedData), tlv(0xa0, signedData));
  }

  // ------------------------------------------------------------------ CMS çözümleme / birleştirme / doğrulama
  function parseSignedData(cms) {
    const ci = read(cms, 0);
    const [oidN, wrap] = kids(cms, ci);
    if (oidStr(oidN.body()) !== OID.signedData) throw new Error('sign.sgn bir CMS SignedData değil');
    const sd = kids(cms, wrap)[0];
    const parts = kids(cms, sd);
    const out = { version: parts[0].body()[0], digestAlgs: [], encap: null, certs: [], crls: null, signers: [] };
    let k = 1;
    out.digestAlgs = kids(cms, parts[k++]).map(n => n.raw());
    out.encap = parts[k++].raw();
    while (k < parts.length && (parts[k].tag === 0xa0 || parts[k].tag === 0xa1)) {
      if (parts[k].tag === 0xa0) out.certs = kids(cms, parts[k]).map(n => n.raw());
      else out.crls = parts[k].raw();
      k++;
    }
    out.signerNodes = kids(cms, parts[k]);
    out.signers = out.signerNodes.map(n => n.raw());
    out._buf = cms;
    return out;
  }
  function buildSignedDataFrom(p) {
    const sd = SEQ(
      tlv(0x02, Uint8Array.of(p.version || 1)),
      SETOF(p.digestAlgs),
      p.encap,
      ...(p.certs.length ? [tlv(0xa0, ...p.certs)] : []),
      ...(p.crls ? [p.crls] : []),
      tlv(0x31, ...p.signers) // SignerInfo sırası korunur (imza sırası anlamlıdır)
    );
    return SEQ(OIDv(OID.signedData), tlv(0xa0, sd));
  }
  /** Havelsan combineSignatures ile aynı: önceki imzalar korunur, yeni imzacı paralel eklenir. */
  function combine(existing, added) {
    if (!existing || !existing.length) return added;
    if (!added || !added.length) return existing;
    const a = parseSignedData(existing), b = parseSignedData(added);
    const algOid = (raw) => oidStr(kids(raw, read(raw, 0))[0].body());
    b.digestAlgs.forEach(d => { if (!a.digestAlgs.some(x => algOid(x) === algOid(d))) a.digestAlgs.push(d); });
    b.certs.forEach(c => { if (!a.certs.some(x => eq(x, c))) a.certs.push(c); });
    b.signers.forEach(s => { if (!a.signers.some(x => eq(x, s))) a.signers.push(s); });
    a.version = Math.max(a.version, b.version);
    return buildSignedDataFrom(a);
  }

  function findCertFor(p, sidRaw) {
    for (const c of p.certs) {
      try {
        const pc = parseCert(c);
        if (eq(concat([pc.issuerTLV, pc.serialTLV]), sidRaw)) return pc; // sid = IssuerAndSerialNumber gövdesi
      } catch (e) {}
    }
    return null;
  }
  // WebCrypto ile imza doğrulaması (RSA PKCS#1 v1.5 / ECDSA, SHA-256/384/512)
  async function verifySignerCrypto(pc, attrsSet, sigBytes, sigAlgOid, digestOid) {
    const hashName = digestOid === OID.sha512 ? 'SHA-512' : digestOid === OID.sha384 ? 'SHA-384' : 'SHA-256';
    const cert = read(pc.der, 0);
    const tbs = kids(pc.der, cert)[0];
    const t = kids(pc.der, tbs); const i = t[0].tag === 0xa0 ? 1 : 0;
    const spki = t[i + 5].raw();
    try {
      if (pc.keyType === 'EC') {
        const algParams = kids(pc.der, kids(pc.der, t[i + 5])[0]);
        const curveOid = algParams[1] ? oidStr(algParams[1].body()) : '';
        const namedCurve = curveOid === '1.3.132.0.34' ? 'P-384' : curveOid === '1.3.132.0.35' ? 'P-521' : 'P-256';
        const key = await crypto.subtle.importKey('spki', spki, { name: 'ECDSA', namedCurve }, false, ['verify']);
        // DER (r,s) → ham r||s
        const seq = read(sigBytes, 0); const [r, s] = kids(sigBytes, seq);
        const size = namedCurve === 'P-384' ? 48 : namedCurve === 'P-521' ? 66 : 32;
        const pad = (x) => { let y = x.body(); while (y.length > size && y[0] === 0) y = y.subarray(1); const o = new Uint8Array(size); o.set(y, size - y.length); return o; };
        const sigOid = sigAlgOid;
        const h = sigOid === '1.2.840.10045.4.3.3' ? 'SHA-384' : sigOid === '1.2.840.10045.4.3.4' ? 'SHA-512' : hashName;
        return await crypto.subtle.verify({ name: 'ECDSA', hash: h }, key, concat([pad(r), pad(s)]), attrsSet);
      }
      const h = sigAlgOid === '1.2.840.113549.1.1.12' ? 'SHA-384' : sigAlgOid === '1.2.840.113549.1.1.13' ? 'SHA-512' : sigAlgOid === OID.sha256WithRSA ? 'SHA-256' : hashName;
      const key = await crypto.subtle.importKey('spki', spki, { name: 'RSASSA-PKCS1-v1_5', hash: h }, false, ['verify']);
      return await crypto.subtle.verify('RSASSA-PKCS1-v1_5', key, sigBytes, attrsSet);
    } catch (e) {
      return null; // doğrulanamadı (desteklenmeyen algoritma)
    }
  }
  /**
   * sign.sgn'yi content.xml'e karşı doğrular. Her imzacı için: mesaj özeti eşleşmesi + kriptografik imza.
   * Not: Sertifika zinciri / iptal (OCSP) kontrolü yapılmaz — UYAP bunu sunucu tarafında yapar.
   */
  async function verify(contentBytes, sgn) {
    const p = parseSignedData(sgn);
    const result = { hasSignature: true, isValid: true, signers: [] };
    for (const node of p.signerNodes) {
      const f = kids(sgn, node);
      let k = 1;
      const sid = f[k++].body();
      const digestOid = oidStr(kids(sgn, f[k++])[0].body());
      let attrsNode = null;
      if (f[k].tag === 0xa0) attrsNode = f[k++];
      const sigAlgOid = oidStr(kids(sgn, f[k++])[0].body());
      const sigBytes = f[k++].body();
      const info = { name: '', tckn: '', title: '', issuer: '', time: '', digestOk: false, signatureOk: null };
      const pc = findCertFor(p, sid);
      if (pc) { info.name = pc.subjectCN; info.tckn = pc.subjectSerial; info.title = pc.subjectTitle; info.issuer = pc.issuerCN; info.notAfter = pc.notAfter; }
      if (attrsNode) {
        const hashName = digestOid === OID.sha512 ? 'SHA-512' : digestOid === OID.sha384 ? 'SHA-384' : 'SHA-256';
        const md = new Uint8Array(await crypto.subtle.digest(hashName, contentBytes));
        kids(sgn, attrsNode).forEach(a => {
          const [o, vals] = kids(sgn, a);
          const id = oidStr(o.body());
          const v = kids(sgn, vals)[0];
          if (id === OID.messageDigest) info.digestOk = eq(v.body(), md);
          if (id === OID.signingTime) info.time = decodeStr(v);
        });
        const attrsSet = concat([Uint8Array.of(0x31), sgn.subarray(attrsNode.start + 1, attrsNode.end)]);
        if (pc) info.signatureOk = await verifySignerCrypto(pc, attrsSet, sigBytes, sigAlgOid, digestOid);
      }
      if (!info.digestOk || info.signatureOk === false) result.isValid = false;
      result.signers.push(info);
    }
    if (!result.signers.length) result.isValid = false;
    const s0 = result.signers[0] || {};
    result.signerName = result.signers.map(s => s.name).filter(Boolean).join(', ');
    result.tckn = s0.tckn || '';
    result.issuer = s0.issuer || '';
    result.signingTime = s0.time || '';
    result.signerCount = result.signers.length;
    return result;
  }

  // ------------------------------------------------------------------ platform köprüleri
  const tauri = () => (window.__TAURI__ && window.__TAURI__.core) ? window.__TAURI__.core : null;
  const realAndroid = () => !!(window.AndroidBridge && !window.AndroidBridge.__stub);
  let cbSeq = 0; const cbs = {};
  // Android köprüsü asenkron sonuçları bu fonksiyonla iletir
  window.__esignCallback = function (id, ok, payload) {
    const c = cbs[id]; if (!c) return; delete cbs[id];
    ok ? c.resolve(payload) : c.reject(new Error(payload || 'İşlem başarısız'));
  };
  function androidCall(method, ...args) {
    return new Promise((resolve, reject) => {
      const id = 'e' + (++cbSeq) + '_' + Date.now();
      cbs[id] = { resolve, reject };
      try { window.AndroidBridge[method](id, ...args); } catch (e) { delete cbs[id]; reject(e); }
    });
  }

  async function httpPost(url, body, headers) {
    const t = tauri();
    if (t) return await t.invoke('http_post', { url, body, contentType: headers['Content-Type'] || 'text/xml; charset=utf-8', soapAction: headers.SOAPAction || '' });
    if (realAndroid() && window.AndroidBridge.httpPostAsync) return await androidCall('httpPostAsync', url, headers['Content-Type'] || 'text/xml; charset=utf-8', headers.SOAPAction || '', body);
    // Web: yerel yardımcı servis (UdeMobileServer 127.0.0.1:5976 /api/v1/proxy) veya doğrudan (CORS izin verirse)
    try {
      const r = await fetch('http://127.0.0.1:5976/api/v1/proxy', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url, body, headers }) });
      if (r.ok) return await r.text();
    } catch (e) {}
    const r = await fetch(url, { method: 'POST', headers, body });
    return await r.text();
  }
  function canMobileSign() {
    return !!(tauri() || (realAndroid() && window.AndroidBridge.httpPostAsync));
  }

  // ------------------------------------------------------------------ UYAP mobil imza (SOAP)
  function xmlEsc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function soapEnv(op, inner) {
    return '<?xml version="1.0" encoding="UTF-8"?><soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:cli="http://client.mimza.uyap.gov.tr"><soapenv:Body><cli:' + op + '>' + inner + '</cli:' + op + '></soapenv:Body></soapenv:Envelope>';
  }
  function tag(xml, name) {
    const m = new RegExp('<(?:[\\w-]+:)?' + name + '(?:\\s[^>]*)?>([\\s\\S]*?)</(?:[\\w-]+:)?' + name + '>').exec(xml);
    if (m) return m[1].trim();
    return '';
  }
  function soapFault(xml) { const f = tag(xml, 'faultstring'); return f ? 'UYAP servis hatası: ' + f : ''; }
  function normalizePhone(p) {
    let d = String(p || '').replace(/\D/g, '');
    if (d.startsWith('90') && d.length === 12) d = d.slice(2);
    if (d.length === 10 && d.startsWith('5')) d = '0' + d;
    return d; // Havelsan: tam 11 hane, "05XXXXXXXXX"
  }
  function mimzaMessage(msg, phone) {
    if (/UNKNOWN_CLIENT/i.test(msg)) return phone + ' numaralı hatta seçilen operatörde aktif bir mobil imza bulunamadı. Operatör seçimini ve numarayı kontrol edin.';
    if (/USER_CANCEL|IPTAL|CANCEL/i.test(msg)) return 'Mobil imza işlemi telefondan iptal edildi.';
    if (/EXPIRED|TIMEOUT|ZAMAN/i.test(msg)) return 'Mobil imza onayı zaman aşımına uğradı.';
    return msg || 'Mobil imza tamamlanamadı.';
  }
  async function mimzaGetHash(contentBytes, phone, operator) {
    const xml = await httpPost(MIMZA_URL, soapEnv('getHash', '<dataToBeSigned>' + b64e(contentBytes) + '</dataToBeSigned><telNo>' + xmlEsc(phone) + '</telNo><gsmOperator>' + (operator | 0) + '</gsmOperator>'), { 'Content-Type': 'text/xml; charset=utf-8', SOAPAction: '""' });
    const fault = soapFault(xml); if (fault) throw new Error(fault);
    const code = parseInt(tag(xml, 'resultCode'), 10);
    const res = { apTransId: tag(xml, 'apTransId'), fingerPrint: tag(xml, 'fingerPrint'), message: tag(xml, 'message'), resultCode: code };
    if (code !== 0 || !res.apTransId) throw new Error(mimzaMessage(res.message, phone));
    return res;
  }
  async function mimzaGetSignature(apTransId) {
    const xml = await httpPost(MIMZA_URL, soapEnv('getSignature', '<dataToBeDisplayed>Evrak Mobil Imza Talebi</dataToBeDisplayed><apTransId>' + xmlEsc(apTransId) + '</apTransId>'), { 'Content-Type': 'text/xml; charset=utf-8', SOAPAction: '""' });
    const fault = soapFault(xml); if (fault) throw new Error(fault);
    const code = parseInt(tag(xml, 'resultCode'), 10);
    const data = tag(xml, 'data');
    if (code !== 0 || !data) throw new Error(mimzaMessage(tag(xml, 'message')));
    return { cms: b64d(data), signerName: tag(xml, 'signerName'), identityNo: tag(xml, 'identityNo'), signatureDate: tag(xml, 'signatureDate') };
  }

  // ------------------------------------------------------------------ akıllı kart
  async function scList(libPath) {
    const t = tauri();
    // Özel sürücü yolu: localStorage 'caneditor_pkcs11_lib' (veya ortam değişkeni CANEDITOR_PKCS11)
    if (!libPath) { try { libPath = localStorage.getItem('caneditor_pkcs11_lib') || null; } catch (e) {} }
    if (t) return await t.invoke('pkcs11_list', { libPath: libPath || null });
    if (realAndroid() && window.AndroidBridge.scardCertAsync) {
      const r = await androidCall('scardCertAsync');
      return JSON.parse(r);
    }
    throw new Error('Akıllı kart erişimi bu platformda yok (tarayıcı sürümü). Masaüstü veya Android uygulamasını kullanın.');
  }
  async function scSign(card, pin, signedAttrs) {
    const t = tauri();
    if (t) {
      const sig = await t.invoke('pkcs11_sign', { libPath: card.lib, slot: card.slot, keyId: card.keyId, pin, dataB64: b64e(signedAttrs.setDer), digestB64: b64e(signedAttrs.digestOfAttrs), keyType: card.keyType || 'RSA' });
      return b64d(sig);
    }
    if (realAndroid() && window.AndroidBridge.scardSignAsync) {
      // Android CCID sürücüsü SHA-256 özetini DigestInfo ile PSO:CDS'e verir
      return b64d(await androidCall('scardSignAsync', pin, b64e(signedAttrs.digestOfAttrs)));
    }
    throw new Error('Akıllı kart ile imza bu platformda desteklenmiyor.');
  }

  // ------------------------------------------------------------------ belge (UDF) kaynağı
  /**
   * İmzalanacak content.xml ve mevcut sign.sgn'yi hazırlar.
   * Belge imzalı ve değiştirilmemişse ORİJİNAL content.xml baytları kullanılır (önceki imzalar geçerli kalır).
   */
  async function prepareSource() {
    const modified = window.isDocumentModified ? window.isDocumentModified() : true;
    const orig = window.currentDocOriginalBuffer || (typeof currentDocOriginalBuffer !== 'undefined' ? currentDocOriginalBuffer : null);
    const name = String(window.currentDocFileName || (typeof currentDocFileName !== 'undefined' ? currentDocFileName : '') || '');
    if (orig && /\.udf$/i.test(name)) {
      try {
        const zip = await JSZip.loadAsync(orig);
        const sgnF = zip.file('sign.sgn');
        const cF = zip.file('content.xml');
        if (sgnF && cF) {
          if (modified) throw new Error('Bu belge imzalı ve imzadan sonra değiştirildi. Değiştirilmiş belgeye ek imza atılırsa önceki imzalar geçersiz olur. Önce belgeyi "Kaydet" ile kaydedin (önceki imzalar kaldırılır) veya değişiklik yapmadan yeniden açıp imzalayın.');
          return { zip, content: await cF.async('uint8array'), existingSgn: await sgnF.async('uint8array') };
        }
        if (!modified && cF) return { zip, content: await cF.async('uint8array'), existingSgn: null };
      } catch (e) { if (/imzalı/.test(e.message)) throw e; }
    }
    const getDoc = window.getStructuredDocument || (typeof getStructuredDocument === 'function' ? getStructuredDocument : null);
    const blob = await generateUdfBlob(getDoc ? getDoc() : null);
    const zip = await JSZip.loadAsync(await blob.arrayBuffer());
    return { zip, content: await zip.file('content.xml').async('uint8array'), existingSgn: null };
  }
  async function writeSigned(src, sgn) {
    src.zip.file('content.xml', src.content, { compression: 'DEFLATE' }); // baytlar AYNEN korunur
    src.zip.file('sign.sgn', sgn, { compression: 'DEFLATE' });
    const out = await src.zip.generateAsync({ type: 'uint8array', compression: 'DEFLATE' });
    return out;
  }
  async function finish(udfBytes) {
    let name = String(window.currentDocFileName || (typeof currentDocFileName !== 'undefined' ? currentDocFileName : '') || 'Belge.udf');
    if (!/\.udf$/i.test(name)) name = name.replace(/\.[^.]+$/, '') + '.udf';
    // Kaydet: masaüstünde açık dosyanın üzerine, Android'de belgenin kaynağına / İndirilenler'e, web'de indir
    if (typeof window.saveBytesSmart === 'function') {
      await window.saveBytesSmart(udfBytes, name, 'application/octet-stream', { overwriteCurrent: true, signed: true });
    } else {
      downloadBlob(new Blob([udfBytes]), name);
    }
    // İmzalı belgeyi yeniden yükle → imza şeridi ve doğrulama güncellenir, belge "değiştirilmemiş" olur
    const buf = udfBytes.buffer.slice(udfBytes.byteOffset, udfBytes.byteOffset + udfBytes.byteLength);
    const keepPath = window.currentDocPath || null;
    if (typeof openDocumentFromBytes === 'function') await openDocumentFromBytes(buf, name, keepPath);
    if (keepPath) window.currentDocPath = keepPath;
  }

  // ------------------------------------------------------------------ üst düzey akışlar
  async function mobileSign(opts, ui) {
    ui = ui || {};
    const phone = normalizePhone(opts.phone);
    if (phone.length !== 11 || !phone.startsWith('05')) throw new Error('GSM numarasını 05XXXXXXXXX biçiminde (11 hane) giriniz.');
    const src = await prepareSource();
    ui.status && ui.status('UYAP mobil imza servisine bağlanılıyor…');
    const h = await mimzaGetHash(src.content, phone, opts.operator);
    ui.waiting && ui.waiting(h.fingerPrint, h.apTransId);
    // getSignature, kullanıcı telefonda PIN girene kadar sunucuda bekler (Havelsan da tek çağrı yapar)
    let res = null, lastErr = null;
    const deadline = Date.now() + 150000;
    while (Date.now() < deadline) {
      try { res = await mimzaGetSignature(h.apTransId); break; }
      catch (e) {
        lastErr = e;
        if (/bekleniyor|PENDING|OUTSTANDING|WAIT/i.test(e.message)) { await new Promise(r => setTimeout(r, 2500)); continue; }
        throw e;
      }
    }
    if (!res) throw lastErr || new Error('Mobil imza onayı zaman aşımına uğradı.');
    const sgn = src.existingSgn ? combine(src.existingSgn, res.cms) : res.cms;
    const check = await verify(src.content, sgn);
    const bytes = await writeSigned(src, sgn);
    await finish(bytes);
    return { signerName: res.signerName, identityNo: res.identityNo, verification: check };
  }

  async function smartCardSign(card, pin, ui) {
    ui = ui || {};
    if (!pin || pin.length < 4) throw new Error('E-imza PIN en az 4 karakter olmalıdır.');
    const src = await prepareSource();
    ui.status && ui.status('İmza öznitelikleri hazırlanıyor…');
    const certDer = b64d(card.certB64);
    const signed = await buildSignedAttrs(src.content, certDer, new Date());
    ui.status && ui.status('Kart ile imzalanıyor (PIN doğrulanıyor)…');
    const sig = await scSign(card, pin, signed);
    const cms = assembleCms(signed, sig, card.keyType);
    const sgn = src.existingSgn ? combine(src.existingSgn, cms) : cms;
    const check = await verify(src.content, sgn);
    if (!check.isValid) throw new Error('Oluşturulan imza doğrulanamadı (kart yanlış imza üretti). Belge kaydedilmedi.');
    const bytes = await writeSigned(src, sgn);
    await finish(bytes);
    return { verification: check, cert: signed.cert };
  }

  async function verifyUdf(arrayBuffer) {
    const zip = await JSZip.loadAsync(arrayBuffer);
    const s = zip.file('sign.sgn'), c = zip.file('content.xml');
    if (!s || !c) return { hasSignature: false, isValid: false };
    return await verify(await c.async('uint8array'), await s.async('uint8array'));
  }


  // ==================================================================== ARAYÜZ BAĞLANTISI
  // index.html'deki "Mobil İmza" ve "E-İmza (Akıllı Kart)" pencereleri bu motoru kullanır.
  // Eski sürüm Android APK'larında (yeni köprü metotları yoksa) eski yerel akışa düşülür.
  const OPS = { TURKCELL: [1, 'Turkcell'], TURK_TELEKOM: [2, 'Türk Telekom'], VODAFONE: [3, 'Vodafone'] };
  const legacyMobile = window.executeMobileSignInApp;
  const legacyCardSign = window.executeSmartCardSignInApp;
  const legacyRefresh = window.refreshSmartCardStatus;

  window.executeMobileSignInApp = async function () {
    if (!canMobileSign()) {
      if (realAndroid() && window.AndroidBridge.performMobileSign && legacyMobile) return legacyMobile();
      const st = document.getElementById('msign-status');
      if (st) { st.style.color = '#C62828'; st.innerHTML = 'Mobil imza, tarayıcı güvenlik kısıtları (CORS) nedeniyle web sürümünde yapılamaz.<br>Lütfen CanEditor <b>masaüstü (Windows/macOS/Linux)</b> veya <b>Android</b> uygulamasını kullanın.'; }
      return;
    }
    const st = document.getElementById('msign-status');
    const btn = document.getElementById('btn-do-msign');
    const opSel = (document.getElementById('msign-operator') || {}).value || 'TURKCELL';
    const phone = ((document.getElementById('msign-phone') || {}).value || '').trim();
    const [opCode, opName] = OPS[opSel] || OPS.TURKCELL;
    try { if (typeof onMobileSignInputChanged === 'function') onMobileSignInputChanged(); } catch (e) {}
    if (btn) btn.disabled = true;
    try {
      const r = await mobileSign({ phone, operator: opCode }, {
        status: (m) => { if (st) { st.style.color = '#1565C0'; st.textContent = m; } },
        waiting: (fp, id) => { if (window.onMobileSignWaiting) window.onMobileSignWaiting(fp, id); }
      });
      const v = r.verification || {};
      if (window.onMobileSignSuccess) window.onMobileSignSuccess('MIMZA-' + Date.now().toString(16).toUpperCase(), v, r.signerName || v.signerName || '', r.identityNo || v.tckn || '', opName);
      if (typeof showEditorToast === 'function') showEditorToast('✓ Mobil imza eklendi: ' + (r.signerName || v.signerName || ''));
    } catch (e) {
      if (window.onMobileSignFailed) window.onMobileSignFailed(e.message || String(e));
    } finally { if (btn) btn.disabled = false; }
  };

  // --- Akıllı kart: sertifika listesi (masaüstü PKCS#11 / Android USB CCID)
  let scCards = [];
  let scBusy = false;
  const usesNewCardPath = () => !!(tauri() || (realAndroid() && window.AndroidBridge.scardCertAsync));
  window.refreshSmartCardStatus = async function () {
    if (!usesNewCardPath()) return legacyRefresh ? legacyRefresh() : undefined;
    if (scBusy) return;
    scBusy = true;
    try {
      const list = await scList();
      scCards = (list && list.cards) || list || [];
      const certs = scCards.map((c, i) => {
        let pc = null; try { pc = parseCert(b64d(c.certB64)); } catch (e) {}
        c.keyType = c.keyType || (pc && pc.keyType) || 'RSA';
        return { id: String(i), subject: 'CN=' + ((pc && pc.subjectCN) || c.label || 'Sertifika'), issuer: 'CN=' + ((pc && pc.issuerCN) || ''), validUntil: pc ? pc.notAfter : '', terminal: c.reader || c.tokenLabel || 'Akıllı kart okuyucu', serial: pc ? pc.subjectSerial : '' };
      });
      if (window.onSmartCardStatusUpdated) window.onSmartCardStatusUpdated({ connected: certs.length > 0, certificates: certs, message: certs.length ? '' : ((list && list.message) || 'Takılı e-imza kartı bulunamadı. Kartı/token\'ı takın ve sürücüsünün kurulu olduğundan emin olun.') });
    } catch (e) {
      scCards = [];
      if (window.onSmartCardStatusUpdated) window.onSmartCardStatusUpdated({ connected: false, certificates: [], message: e.message || String(e) });
    } finally { scBusy = false; }
  };
  window.executeSmartCardSignInApp = async function () {
    if (!usesNewCardPath()) return legacyCardSign ? legacyCardSign() : undefined;
    const st = document.getElementById('sc-status');
    const btn = document.getElementById('btn-do-eimza');
    const pin = ((document.getElementById('sc-pin') || {}).value || '').trim();
    const sel = document.getElementById('sc-cert-select');
    const card = scCards[parseInt((sel && sel.value) || '0', 10)] || scCards[0];
    if (!card) { if (window.onRealSignFailed) window.onRealSignFailed('Takılı akıllı kart bulunamadı.'); return; }
    if (btn) btn.disabled = true;
    // Kart okunurken sorgu döngüsü PIN oturumunu bozmasın
    try { if (typeof smartCardPollInterval !== 'undefined' && smartCardPollInterval) { clearInterval(smartCardPollInterval); } } catch (e) {}
    try {
      const r = await smartCardSign(card, pin, { status: (m) => { if (st) { st.style.color = '#1565C0'; st.textContent = m; } } });
      if (window.onRealSignSuccess) window.onRealSignSuccess('NES-' + Date.now().toString(16).toUpperCase(), r.verification);
      if (typeof showEditorToast === 'function') showEditorToast('✓ E-imza eklendi: ' + ((r.cert && r.cert.subjectCN) || ''));
    } catch (e) {
      if (window.onRealSignFailed) window.onRealSignFailed(e.message || String(e));
    } finally { if (btn) btn.disabled = false; }
  };

  // --- "İmzayı Doğrula": yerel kriptografik doğrulama (tüm platformlar)
  const legacyCheck = window.checkDocumentSignature;
  window.checkDocumentSignature = async function () {
    try {
      const orig = window.currentDocOriginalBuffer || (typeof currentDocOriginalBuffer !== 'undefined' ? currentDocOriginalBuffer : null);
      const name = String(window.currentDocFileName || (typeof currentDocFileName !== 'undefined' ? currentDocFileName : '') || '');
      if (orig && /\.udf$/i.test(name)) {
        const v = await verifyUdf(orig);
        if (window.isDocumentModified && window.isDocumentModified() && v.hasSignature) {
          v.isValid = false; v.modifiedAfterSign = true;
        }
        if (typeof updateSignatureBadge === 'function') updateSignatureBadge(v);
        if (typeof onDocumentSignatureChecked === 'function') onDocumentSignatureChecked(v);
        if (typeof updateSignatureBanner === 'function') updateSignatureBanner(v);
        if (typeof showEditorToast === 'function') {
          showEditorToast(!v.hasSignature ? 'Belgede e-imza yok' : v.isValid ? ('✓ İmza geçerli: ' + v.signerName) : (v.modifiedAfterSign ? '⚠ Belge imzadan sonra değiştirildi' : '✗ İmza doğrulanamadı'));
        }
        return v;
      }
    } catch (e) { console.warn('İmza doğrulama hatası', e); }
    return legacyCheck ? legacyCheck() : undefined;
  };

  window.ESign = {
    // çekirdek
    parseCert, buildSignedAttrs, assembleCms, combine, verify, verifyUdf, ecdsaRawToDer,
    // akışlar
    mobileSign, smartCardSign, scList, canMobileSign, normalizePhone,
    // test yardımcıları
    _b64e: b64e, _b64d: b64d, _hex: hex, _mimzaGetHash: mimzaGetHash, _mimzaGetSignature: mimzaGetSignature, _parseSignedData: parseSignedData,
    platform: () => tauri() ? 'desktop' : (realAndroid() ? 'android' : 'web')
  };
})();
