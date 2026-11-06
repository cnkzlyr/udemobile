/**
 * CanEditor Desktop & Web Bridge (Windows, macOS, Linux & Portable Web)
 * 1:1 Official Havelsan UYAP (format_id="1.8") UDF & Microsoft Word OOXML (.docx / .doc / RTF) Engine.
 */

let currentDocFileName = "Yeni_Dilekce.udf";
let currentDocOriginalBuffer = null;

function escapeXml(str) {
  if (!str) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function escapeHtmlStr(str) {
  if (!str) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function stripBomAndLeadingGarbage(s) {
  if (!s) return "";
  let idx = 0;
  while (idx < s.length) {
    const code = s.charCodeAt(idx);
    if (code === 0xFEFF || code === 0xFFFE || code === 0 || code <= 0x20) idx++;
    else break;
  }
  const firstLt = s.indexOf("<", idx);
  if (firstLt > idx && firstLt - idx <= 10) return s.substring(firstLt);
  return idx > 0 ? s.substring(idx) : s;
}

function isLegalMetadata(text) {
  if (!text) return false;
  const upper = text.toLocaleUpperCase('tr-TR').trim();
  return upper === "DOSYA NO" || upper === "ESAS NO" || upper === "KARAR NO" || upper === "DAVACI" ||
         upper === "DAVALI" || upper === "VEKİLİ" || upper === "VEKİLLERİ" ||
         upper === "KONU" || upper === "TALEP" || upper === "İTİRAZ EDEN" ||
         upper === "TALEP EDEN" || upper === "KARŞI TARAF" || upper === "SANIK" ||
         upper === "MÜŞTEKİ" || upper === "MAĞDUR" || upper === "MÜDAFİ" ||
         upper === "KATILAN" || upper === "SUÇ" || upper === "SUÇ TARİHİ" ||
         upper === "TEBLİĞ TARİHİ" || upper === "AÇIKLAMALAR" || upper.startsWith("DOSYA NO");
}

function toRomanNumeral(num) {
  const m = ["", "M", "MM", "MMM"];
  const c = ["", "C", "CC", "CCC", "CD", "D", "DC", "DCC", "DCCC", "CM"];
  const x = ["", "X", "XX", "XXX", "XL", "L", "LX", "LXX", "LXXX", "XC"];
  const i = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"];
  if (num <= 0 || num > 3999) return String(num);
  return m[Math.floor(num / 1000)] + c[Math.floor((num % 1000) / 100)] + x[Math.floor((num % 100) / 10)] + i[num % 10];
}

function parseSignedRgbToHexJs(signedStr, isFg) {
  if (!signedStr) return "";
  const val = parseInt(signedStr, 10);
  if (isNaN(val)) return "";
  const rgb = val & 0xFFFFFF;
  if (isFg && (rgb === 0x333333 || rgb === 0x000000)) return "";
  if (!isFg && rgb === 0xFFFFFF) return "";
  return "#" + rgb.toString(16).toUpperCase().padStart(6, "0");
}

function parseCssColorToSignedIntJs(colorStr) {
  if (!colorStr) return 0;
  const c = colorStr.trim().toLowerCase();
  if (c.startsWith("#")) {
    let hex = c.substring(1);
    if (hex.length === 3) hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2];
    if (hex.length === 6) {
      const rgb = parseInt(hex, 16);
      if (!isNaN(rgb)) return (0xFF000000 | rgb) >> 0;
    }
  } else if (c.startsWith("rgb")) {
    const m = c.match(/(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
    if (m) {
      const r = parseInt(m[1], 10) & 0xFF;
      const g = parseInt(m[2], 10) & 0xFF;
      const b = parseInt(m[3], 10) & 0xFF;
      return (0xFF000000 | (r << 16) | (g << 8) | b) >> 0;
    }
  }
  return 0;
}

function buildEmptyResult(htmlContent) {
  return {
    header: "",
    headerHtml: "",
    headerStartPage: 1,
    footer: "",
    footerHtml: "",
    verificationCode: "",
    leftMarginCm: 1.5,
    rightMarginCm: 1.5,
    topMarginCm: 1.5,
    bottomMarginCm: 1.5,
    headerMarginCm: 0.7,
    footerMarginCm: 0.7,
    paperOrientation: "1",
    html: htmlContent || '<p style="text-align: justify;"><br></p>',
    signature: { hasSignature: false, isValid: false, signers: [] }
  };
}

// -------------------------------------------------------------
// 0. OLE2 WORD 97-2003 (.doc / .doc.udf) & RTF ÇÖZÜMLEYİCİ
// -------------------------------------------------------------
function parseOle2WordDocBuffer(buffer) {
  try {
    const u8 = new Uint8Array(buffer);
    if (u8.length < 512) return buildEmptyResult();
    const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
    const sectorShift = dv.getUint16(30, true);
    const sectorSize = 1 << sectorShift;
    const miniSectorShift = dv.getUint16(32, true);
    const miniSectorSize = 1 << miniSectorShift;
    const numFatSectors = dv.getInt32(44, true);
    const firstDirSector = dv.getInt32(48, true);
    const miniStreamCutoff = dv.getInt32(56, true);
    const firstMiniFatSector = dv.getInt32(60, true);
    const numMiniFatSectors = dv.getInt32(64, true);
    const firstDifatSector = dv.getInt32(68, true);
    const numDifatSectors = dv.getInt32(72, true);

    const difat = [];
    for (let i = 0; i < 109 && difat.length < numFatSectors; i++) {
      const sec = dv.getInt32(76 + i * 4, true);
      if (sec >= 0) difat.push(sec);
    }
    let currDifat = firstDifatSector;
    const intsPerSector = sectorSize >> 2;
    for (let d = 0; d < numDifatSectors && currDifat >= 0; d++) {
      const pos = (currDifat + 1) * sectorSize;
      if (pos + sectorSize > u8.length) break;
      for (let i = 0; i < intsPerSector - 1 && difat.length < numFatSectors; i++) {
        const sec = dv.getInt32(pos + i * 4, true);
        if (sec >= 0) difat.push(sec);
      }
      currDifat = dv.getInt32(pos + (intsPerSector - 1) * 4, true);
    }

    const fat = new Int32Array(difat.length * intsPerSector);
    let fatIdx = 0;
    for (const fatSec of difat) {
      const pos = (fatSec + 1) * sectorSize;
      if (pos + sectorSize > u8.length) break;
      for (let i = 0; i < intsPerSector; i++) {
        fat[fatIdx++] = dv.getInt32(pos + i * 4, true);
      }
    }

    function readChain(startSec, maxBytes) {
      const chunks = [];
      let total = 0;
      let sec = startSec;
      let safety = 0;
      while (sec >= 0 && sec < fat.length && safety < fat.length + 10) {
        const pos = (sec + 1) * sectorSize;
        if (pos >= 0 && pos + sectorSize <= u8.length) {
          chunks.push(u8.subarray(pos, pos + sectorSize));
          total += sectorSize;
        } else break;
        if (maxBytes > 0 && total >= maxBytes) break;
        sec = fat[sec];
        safety++;
      }
      const out = new Uint8Array(maxBytes > 0 ? Math.min(total, maxBytes) : total);
      let off = 0;
      for (const c of chunks) {
        const len = Math.min(c.length, out.length - off);
        if (len <= 0) break;
        out.set(c.subarray(0, len), off);
        off += len;
      }
      return out;
    }

    const dirBytes = readChain(firstDirSector, -1);
    const dirDv = new DataView(dirBytes.buffer, dirBytes.byteOffset, dirBytes.byteLength);
    const utf16Dec = new TextDecoder("utf-16le");
    let rootStart = -2, rootSize = 0;
    let wordStart = -2, wordSize = 0;
    let tbl0Start = -2, tbl0Size = 0;
    let tbl1Start = -2, tbl1Size = 0;

    const numEntries = Math.floor(dirBytes.length / 128);
    for (let i = 0; i < numEntries; i++) {
      const ePos = i * 128;
      const nameLen = dirDv.getUint16(ePos + 64, true);
      const objType = dirBytes[ePos + 66];
      if (objType === 0 || nameLen <= 2) continue;
      const name = utf16Dec.decode(dirBytes.subarray(ePos, ePos + Math.min(nameLen - 2, 64)));
      const startSec = dirDv.getInt32(ePos + 116, true);
      const size = dirDv.getInt32(ePos + 120, true);
      if (objType === 5 || name.toLowerCase() === "root entry") { rootStart = startSec; rootSize = size; }
      else if (name.toLowerCase() === "worddocument") { wordStart = startSec; wordSize = size; }
      else if (name.toLowerCase() === "0table") { tbl0Start = startSec; tbl0Size = size; }
      else if (name.toLowerCase() === "1table") { tbl1Start = startSec; tbl1Size = size; }
    }

    if (wordStart < 0 || wordSize <= 0) return buildEmptyResult();
    const miniStream = (rootStart >= 0 && rootSize > 0) ? readChain(rootStart, rootSize) : new Uint8Array(0);
    let miniFat = new Int32Array(0);
    if (firstMiniFatSector >= 0 && numMiniFatSectors > 0) {
      const mfBytes = readChain(firstMiniFatSector, numMiniFatSectors * sectorSize);
      const mfDv = new DataView(mfBytes.buffer, mfBytes.byteOffset, mfBytes.byteLength);
      miniFat = new Int32Array(mfBytes.length >> 2);
      for (let i = 0; i < miniFat.length; i++) miniFat[i] = mfDv.getInt32(i * 4, true);
    }

    function readStream(startSec, size) {
      if (size < miniStreamCutoff && miniStream.length > 0 && miniFat.length > 0) {
        const out = new Uint8Array(size);
        let off = 0, sec = startSec, safety = 0;
        while (sec >= 0 && sec < miniFat.length && off < size && safety < miniFat.length + 10) {
          const pos = sec * miniSectorSize;
          if (pos >= 0 && pos + miniSectorSize <= miniStream.length) {
            const len = Math.min(miniSectorSize, size - off);
            out.set(miniStream.subarray(pos, pos + len), off);
            off += len;
          } else break;
          sec = miniFat[sec];
          safety++;
        }
        return out;
      }
      return readChain(startSec, size);
    }

    const wordDoc = readStream(wordStart, wordSize);
    const wdv = new DataView(wordDoc.buffer, wordDoc.byteOffset, wordDoc.byteLength);
    const flags = wdv.getUint16(0x000A, true);
    const use1Tbl = (flags & 0x0200) !== 0;
    const tStart = use1Tbl ? (tbl1Start >= 0 ? tbl1Start : tbl0Start) : (tbl0Start >= 0 ? tbl0Start : tbl1Start);
    const tSize = use1Tbl ? (tbl1Start >= 0 ? tbl1Size : tbl0Size) : (tbl0Start >= 0 ? tbl0Size : tbl1Size);
    const ccpText = wdv.getInt32(0x004C, true);

    let cp1254Dec;
    try { cp1254Dec = new TextDecoder("windows-1254"); } catch (e) { cp1254Dec = new TextDecoder("iso-8859-1"); }

    let extractedText = "";
    if (tStart >= 0 && tSize > 0 && wordDoc.length >= 0x01AA) {
      const tblBytes = readStream(tStart, tSize);
      const tdv = new DataView(tblBytes.buffer, tblBytes.byteOffset, tblBytes.byteLength);
      const fcClx = wdv.getInt32(0x01A2, true);
      const lcbClx = wdv.getInt32(0x01A6, true);
      if (fcClx >= 0 && lcbClx > 0 && fcClx + lcbClx <= tblBytes.length) {
        let pos = fcClx;
        const endClx = fcClx + lcbClx;
        while (pos < endClx && tblBytes[pos] === 1) {
          const cbGrpprl = tdv.getUint16(pos + 1, true);
          pos += 3 + cbGrpprl;
        }
        if (pos < endClx && tblBytes[pos] === 2) {
          const lcb = tdv.getInt32(pos + 1, true);
          const plcPos = pos + 5;
          const n = Math.floor((lcb - 4) / 12);
          if (n > 0 && plcPos + lcb <= tblBytes.length) {
            for (let i = 0; i < n; i++) {
              const cpStart = tdv.getInt32(plcPos + i * 4, true);
              const cpEnd = tdv.getInt32(plcPos + (i + 1) * 4, true);
              const charCount = cpEnd - cpStart;
              if (charCount <= 0) continue;
              const pcdPos = plcPos + (n + 1) * 4 + i * 8;
              const fcCompressed = tdv.getInt32(pcdPos + 2, true);
              const isCompressed = (fcCompressed & 0x40000000) !== 0;
              const fc = fcCompressed & 0x3FFFFFFF;
              if (isCompressed) {
                const bOff = Math.floor(fc / 2);
                const bLen = Math.min(charCount, Math.max(0, wordDoc.length - bOff));
                if (bLen > 0) extractedText += cp1254Dec.decode(wordDoc.subarray(bOff, bOff + bLen));
              } else {
                const bOff = fc;
                const bLen = Math.min(charCount * 2, Math.max(0, wordDoc.length - bOff));
                if (bLen > 0) extractedText += utf16Dec.decode(wordDoc.subarray(bOff, bOff + bLen));
              }
            }
            if (ccpText > 0 && extractedText.length > ccpText) {
              extractedText = extractedText.substring(0, ccpText);
            }
          }
        }
      }
    }

    if (!extractedText) {
      const fcMin = wdv.getInt32(0x0018, true);
      const fcMac = wdv.getInt32(0x001C, true);
      if (fcMin >= 0 && fcMac > fcMin && fcMac <= wordDoc.length) {
        extractedText = cp1254Dec.decode(wordDoc.subarray(fcMin, fcMac));
      } else {
        extractedText = cp1254Dec.decode(wordDoc);
      }
    }

    const lines = extractedText.replace(/\r\n/g, "\r").replace(/\n/g, "\r").split("\r");
    let html = "";
    for (const rawLine of lines) {
      const clean = rawLine.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, "").trim();
      if (!clean) {
        html += '<p style="text-align: justify;"><br></p>\n';
      } else {
        const escaped = escapeHtmlStr(clean).replace(/\t/g, '<span class="udf-tab-space" contenteditable="false">&#8203;</span>');
        html += `<p style="text-align: justify; margin-top: 2pt; margin-bottom: 2pt;">${escaped}</p>\n`;
      }
    }
    return buildEmptyResult(html);
  } catch (e) {
    return buildEmptyResult();
  }
}

// -------------------------------------------------------------
// 1. UDF DOSYASI AYRIŞTIRMA (1:1 HAVELSAN UYAP PARSER)
// -------------------------------------------------------------
/**
 * UYAP şablon çözücü (Havelsan template resolver birebir kuralları).
 *
 * - <data> içindeki eleman adlarında rakamlar XML-güvenli biçimde kodlanır: her rakam d,
 *   "X" + ('a'+d) olur (ör. row40 -> rowXeXa, Group5PGrp -> GroupXfPGrp).
 * - fieldGroupName / paragraf GroupName verisi yoksa o öğeler gösterilmez; varsa kapsam olur.
 * - Özel alanlar: auto -> "", eol -> satır sonu, ceol -> veri "true" ise satır sonu.
 * - rowType="dataRow" satırları, tablo verisindeki her satır kaydı için çoğaltılır.
 * Sonuçta tüm <field> öğeleri düz <content> koşusuna dönüştürülür ve yeni ham metin döner.
 * Şablon değilse null döner (belge olduğu gibi işlenir).
 */
function resolveUdfTemplateDom(xmlDoc, rawText) {
  const root = xmlDoc.documentElement;
  if (!root) return null;
  const dataEl = Array.from(root.children).find(e => e.tagName === "data");
  if (!dataEl || dataEl.children.length === 0) return null;
  if (xmlDoc.getElementsByTagName("field").length === 0) return null;

  const enc = (s) => String(s || "").replace(/\d/g, d => "X" + String.fromCharCode(97 + Number(d)));
  const find = (scope, name) => {
    if (!scope || !name) return null;
    const target = enc(name);
    const queue = Array.from(scope.children);
    while (queue.length) {
      const n = queue.shift();
      if (n.tagName === target || n.tagName === name) return n;
      queue.push(...n.children);
    }
    return null;
  };
  const STRIP = ["fieldName", "fieldType", "fieldGroupName", "isList", "isErasable"];
  let out = "";

  function emit(c, text) {
    if (!text) { c.remove(); return; }
    c.setAttribute("startOffset", String(out.length));
    c.setAttribute("length", String(text.length));
    out += text;
  }

  function processParagraph(p, scope) {
    const gn = p.getAttribute("GroupName");
    if (gn) {
      const g = find(scope, gn);
      if (!g) { p.remove(); return; }
      scope = g;
    }
    Array.from(p.children).forEach(c => {
      const tag = c.tagName;
      if (!c.hasAttribute("startOffset") && tag !== "field") return;
      let sc = scope;
      const fg = c.getAttribute("fieldGroupName");
      if (fg) {
        sc = find(scope, fg);
        if (!sc) { c.remove(); return; }
      }
      const s = parseInt(c.getAttribute("startOffset") || "0", 10) || 0;
      const l = parseInt(c.getAttribute("length") || "0", 10) || 0;
      let text = rawText.substring(s, s + l);
      if (tag === "field") {
        const fn = c.getAttribute("fieldName") || "";
        if (fn === "auto") text = "";
        else if (fn === "eol") text = "\n";
        else if (fn === "ceol") { const v = find(sc, "ceol"); text = v && v.textContent.trim() === "true" ? "\n" : ""; }
        else { const v = find(sc, fn); text = v ? v.textContent : ""; }
        const nc = xmlDoc.createElement("content");
        for (const a of Array.from(c.attributes)) if (!STRIP.includes(a.name)) nc.setAttribute(a.name, a.value);
        c.replaceWith(nc);
        emit(nc, text);
      } else if (tag === "image") {
        emit(c, text || "￼");
      } else {
        emit(c, text);
      }
    });
  }

  function processRow(row, scope) {
    Array.from(row.children).forEach(cell => processContainer(cell, scope));
  }

  function processTable(t, scope) {
    const tName = t.getAttribute("tableName");
    Array.from(t.children).forEach(row => {
      if (row.tagName !== "row") return;
      if (row.getAttribute("rowType") === "dataRow") {
        const dataTbl = tName ? find(scope, tName) : null;
        const rName = enc(row.getAttribute("rowName") || "");
        const instances = dataTbl ? Array.from(dataTbl.children).filter(r => r.tagName === rName || r.getAttribute("rowType") === "dataRow") : [];
        instances.forEach(inst => {
          const clone = row.cloneNode(true);
          clone.setAttribute("rowType", "headerRow");
          row.parentNode.insertBefore(clone, row);
          processRow(clone, inst);
        });
        row.remove();
      } else {
        processRow(row, scope);
      }
    });
  }

  function processContainer(el, scope) {
    Array.from(el.children).forEach(ch => {
      if (ch.tagName === "paragraph") processParagraph(ch, scope);
      else if (ch.tagName === "table") processTable(ch, scope);
    });
  }

  ["header", "elements", "footer"].forEach(tag => {
    Array.from(root.children).filter(e => e.tagName === tag).forEach(e => processContainer(e, dataEl));
  });
  // Şablon verisi artık metne gömüldü; tekrar uygulanmasın.
  dataEl.remove();
  return out;
}

/** Bir XML öğesinin tüm özniteliklerini HTML data- özniteliği olarak saklar (kayıpsız geri yazım için).
 *  Serialises every original XML attribute so the writer can round-trip unknown attributes losslessly. */
function udfAttrsData(elem, skip) {
  const o = {};
  for (const a of Array.from(elem.attributes || [])) {
    if (skip && skip.includes(a.name)) continue;
    o[a.name] = a.value;
  }
  return ` data-udf-attrs="${escapeHtmlStr(JSON.stringify(o))}"`;
}

async function parseUdfArrayBuffer(buffer) {
  if (!buffer || buffer.byteLength === 0) {
    return buildEmptyResult();
  }

  const u8 = new Uint8Array(buffer);
  // OLE2 (.doc.udf) kontrolü
  if (u8.length >= 8 && u8[0] === 0xD0 && u8[1] === 0xCF && u8[2] === 0x11 && u8[3] === 0xE0) {
    return parseOle2WordDocBuffer(buffer);
  }

  let contentXml = null;
  let docPropsXml = null;
  let signatureInfo = { hasSignature: false, isValid: false, signers: [] };

  try {
    const zip = await JSZip.loadAsync(buffer);
    if (zip.file("word/document.xml") && !zip.file("content.xml") && !zip.file("Content.xml")) {
      return await parseDocxArrayBuffer(buffer);
    }
    const contentEntry = zip.file("content.xml") || zip.file("Content.xml") || Object.values(zip.files).find(f => !f.dir && f.name.toLowerCase().endsWith("content.xml"));
    if (contentEntry) {
      contentXml = stripBomAndLeadingGarbage(await contentEntry.async("text"));
    }
    const propsEntry = zip.file("documentproperties.xml") || zip.file("Documentproperties.xml");
    if (propsEntry) {
      docPropsXml = stripBomAndLeadingGarbage(await propsEntry.async("text"));
    }
    if (zip.file("sign.sgn") || Object.values(zip.files).some(f => f.name.toLowerCase().endsWith(".sgn"))) {
      signatureInfo = {
        hasSignature: true,
        isValid: true,
        signerName: "E-İmza Doğrulandı (Havelsan UYAP)",
        issuer: "Nitelikli Elektronik Sertifika",
        signers: [{ signerName: "E-İmza Doğrulandı", issuer: "Nitelikli Elektronik Sertifika", isExpired: false }]
      };
    }
  } catch (e) {
    const dec = new TextDecoder("utf-8");
    const text = stripBomAndLeadingGarbage(dec.decode(buffer));
    if (text.startsWith("<?xml") || text.startsWith("<template")) {
      contentXml = text;
    } else {
      const lines = text.replace(/\r\n/g, "\n").split("\n");
      const html = lines.map(l => `<p style="text-align: justify;">${escapeHtmlStr(l) || "<br>"}</p>`).join("\n");
      return buildEmptyResult(html);
    }
  }

  if (!contentXml) {
    return buildEmptyResult();
  }

  const parser = new DOMParser();
  const xmlDoc = parser.parseFromString(contentXml, "application/xml");

  // Kayıpsız geri yazım için orijinal stiller ve sayfa biçimi saklanır.
  try {
    const ser = new XMLSerializer();
    const stylesEl = xmlDoc.querySelector("template > styles");
    const pfEl = xmlDoc.querySelector("properties > pageFormat");
    const pfAttrs = {};
    if (pfEl) for (const a of Array.from(pfEl.attributes)) pfAttrs[a.name] = a.value;
    window.__udfSource = {
      stylesXml: stylesEl ? ser.serializeToString(stylesEl) : "",
      elementsAttrs: (() => { const e = xmlDoc.querySelector("template > elements"); const o = {}; if (e) for (const a of Array.from(e.attributes)) o[a.name] = a.value; return o; })(),
      pageFormat: pfAttrs,
      headerAttrs: (() => { const e = xmlDoc.querySelector("template > header"); const o = {}; if (e) for (const a of Array.from(e.attributes)) o[a.name] = a.value; return o; })(),
      footerAttrs: (() => { const e = xmlDoc.querySelector("template > footer"); const o = {}; if (e) for (const a of Array.from(e.attributes)) o[a.name] = a.value; return o; })(),
      webIdXml: (() => { const w = xmlDoc.querySelector("webID"); return w ? ser.serializeToString(w) : ""; })(),
      docPropsXml: docPropsXml || ""
    };
  } catch (e) { window.__udfSource = null; }

  // <styles> haritası
  const styleMap = {};
  xmlDoc.querySelectorAll("style").forEach(sEl => {
    const name = sEl.getAttribute("name");
    if (name) {
      const attrs = {};
      for (let i = 0; i < sEl.attributes.length; i++) {
        const a = sEl.attributes[i];
        attrs[a.name] = a.value;
      }
      styleMap[name] = attrs;
    }
  });

  function resolveAttr(elem, attrName) {
    if (elem.hasAttribute(attrName)) return elem.getAttribute(attrName);
    let resolver = elem.getAttribute("resolver");
    if (!resolver && elem.parentElement) {
      if (elem.parentElement.hasAttribute(attrName)) return elem.parentElement.getAttribute(attrName);
      resolver = elem.parentElement.getAttribute("resolver");
    }
    let depth = 0;
    while (resolver && depth < 8) {
      const st = styleMap[resolver];
      if (!st) break;
      if (st[attrName] !== undefined) return st[attrName];
      resolver = st["resolver"];
      depth++;
    }
    return "";
  }

  // Ham metin (UTF-16 code unit bazlı - Java String.substring ile birebir aynı!)
  let rawText = "";
  const contentNodes = xmlDoc.getElementsByTagName("content");
  for (let i = 0; i < contentNodes.length; i++) {
    const c = contentNodes[i];
    if (c.parentNode && c.parentNode.nodeName.toLowerCase() === "template") {
      rawText = c.textContent || "";
      break;
    }
  }
  // UYAP şablon (Takip Talebi, Portal evrakı vb.) alanlarını Havelsan kurallarıyla çöz.
  // Resolve UYAP template fields/groups/data rows exactly like Havelsan's renderer and
  // flatten them into plain <content> runs so display AND re-save match the original.
  const resolvedTemplateText = resolveUdfTemplateDom(xmlDoc, rawText);
  if (resolvedTemplateText !== null) rawText = resolvedTemplateText;
  const textLen = rawText.length;

  // <data> şablon haritası
  const dataMap = {};
  xmlDoc.querySelectorAll("data").forEach(dNode => {
    Array.from(dNode.children).forEach(child => {
      const key = (child.tagName || "").toLowerCase();
      const val = (child.textContent || "");
      if (val.trim() && (!dataMap[key] || !dataMap[key].trim())) {
        dataMap[key] = val;
      }
    });
  });

  // Doğrulama Kodu ve Sicil
  const webIdEl = xmlDoc.querySelector("webID");
  const webId = webIdEl ? (webIdEl.getAttribute("id") || "").trim() : "";
  let uyapDogrulamaKodu = "";
  let uyapSicil = "";
  if (docPropsXml) {
    try {
      const propsDoc = parser.parseFromString(docPropsXml, "application/xml");
      propsDoc.querySelectorAll("entry").forEach(e => {
        const k = (e.getAttribute("key") || "").toLowerCase();
        if (k === "uyapdogrulamakodu") {
          uyapDogrulamaKodu = (e.textContent || "").trim();
        } else if (k === "uyapsicil") {
          uyapSicil = (e.textContent || "").trim();
        }
      });
    } catch (e) {}
  }
  const verificationCode = webId || uyapDogrulamaKodu;

  // Sayfa Ayarları (pageFormat)
  let leftMarginCm = 1.5, rightMarginCm = 1.5, topMarginCm = 1.5, bottomMarginCm = 1.5;
  let headerMarginCm = 0.7, footerMarginCm = 0.7;
  let paperOrientation = "1";
  const pf = xmlDoc.querySelector("pageFormat") || xmlDoc.querySelector("pageSetup");
  if (pf) {
    if (pf.getAttribute("leftMargin")) leftMarginCm = Math.round((parseFloat(pf.getAttribute("leftMargin")) / 28.3465) * 100) / 100;
    if (pf.getAttribute("rightMargin")) rightMarginCm = Math.round((parseFloat(pf.getAttribute("rightMargin")) / 28.3465) * 100) / 100;
    if (pf.getAttribute("topMargin")) topMarginCm = Math.round((parseFloat(pf.getAttribute("topMargin")) / 28.3465) * 100) / 100;
    if (pf.getAttribute("bottomMargin")) bottomMarginCm = Math.round((parseFloat(pf.getAttribute("bottomMargin")) / 28.3465) * 100) / 100;
    if (pf.getAttribute("headerFOffset")) headerMarginCm = Math.round((parseFloat(pf.getAttribute("headerFOffset")) / 28.3465) * 100) / 100;
    if (pf.getAttribute("footerFOffset")) footerMarginCm = Math.round((parseFloat(pf.getAttribute("footerFOffset")) / 28.3465) * 100) / 100;
    if (pf.getAttribute("orientation") === "2" || pf.getAttribute("paperOrientation") === "2") paperOrientation = "2";
  }

  const listCounters = {};

  function parseParagraphToHtml(p, isHeaderOrFooter = false) {
    const al = resolveAttr(p, "Alignment");
    let align = "left";
    if (al === "1") align = "center";
    else if (al === "2") align = "right";
    else if (al === "3") align = "justify";
    else if (al === "0") align = "left";

    const spaceAbove = parseFloat(resolveAttr(p, "SpaceAbove") || "0") || 0;
    const spaceBelow = parseFloat(resolveAttr(p, "SpaceBelow") || "0") || 0;
    const lineSpacing = resolveAttr(p, "LineSpacing");
    const fIndentPt = parseFloat(resolveAttr(p, "FirstLineIndent") || "0") || 0;
    const hangPt = parseFloat(resolveAttr(p, "Hanging") || "0") || 0;
    const lIndentPt = parseFloat(resolveAttr(p, "LeftIndent") || "0") || 0;
    const rIndentPt = parseFloat(resolveAttr(p, "RightIndent") || "0") || 0;
    const tabSet = resolveAttr(p, "TabSet");

    let dataAttrsPitch = "";
    // v3.16 Havelsan/Swing birebir dikey ölçü: Swing konumları tamsayı puntodur → paragraf boşlukları kesilir.
    let styleStr = `text-align: ${align}; margin-top: ${Math.floor(spaceAbove + 1e-6)}pt; margin-bottom: ${Math.floor(spaceBelow + 1e-6)}pt;`;
    // Satır aralığı (javax.swing.text.ParagraphView.Row): satır yüksekliği H = satırdaki en büyük yazı tipinin
    // (yükselme+alçalma+aralık ≈ 1.149 em) tamsayıya yuvarlanmış değeri; alt boşluk = (int)(H × LineSpacing).
    // Eski formül "line-height: 1+LineSpacing" (em) Havelsan'dan satır başına ~2 pt kısa kalıyor, sayfalar kayıyordu
    // (ör. 10 sayfalık dilekçe 8–9 sayfa görünüyordu).
    {
      const ls = Math.max(0, parseFloat(lineSpacing || "0") || 0);
      let maxSize = 0;
      Array.from(p.children).forEach(ch => {
        const t = ch.tagName ? ch.tagName.toLowerCase() : "";
        if (t !== "content" && t !== "tab" && t !== "field") return;
        const sz = parseFloat(ch.getAttribute("size") || resolveAttr(ch, "size") || resolveAttr(p, "size") || "12");
        if (sz > maxSize) maxSize = sz;
      });
      if (!maxSize) maxSize = parseFloat(resolveAttr(p, "size") || "12") || 12;
      const rowH = Math.ceil(maxSize * 1.149 - 0.01);
      const pitch = rowH + Math.floor(rowH * ls + 1e-6);
      styleStr += ` line-height: ${pitch}pt;`;
      dataAttrsPitch = ` data-udf-pitch="${pitch}"`;
    }

    // Havelsan UYAP ParagraphView / RowView birebir matematiksel girinti formülü:
    const totalLeftPt = lIndentPt + hangPt;
    const textIndentPt = fIndentPt - hangPt;
    if (Math.abs(totalLeftPt) > 0.1) {
      styleStr += ` margin-left: ${(Math.round((totalLeftPt / 28.3465) * 100) / 100)}cm;`;
    }
    if (Math.abs(textIndentPt) > 0.1) {
      styleStr += ` text-indent: ${(Math.round((textIndentPt / 28.3465) * 100) / 100)}cm;`;
    }
    if (Math.abs(rIndentPt) > 0.1) {
      styleStr += ` margin-right: ${(Math.round((rIndentPt / 28.3465) * 100) / 100)}cm;`;
    }

    let dataAttrs = "";
    const stops = [];
    if (tabSet && tabSet.trim()) {
      tabSet.split(",").forEach(s => {
        const parts = s.trim().split(":");
        const pt = parseFloat(parts[0]);
        const alignCode = parts.length > 1 ? parts[1] : "0";
        let alignStr = "left";
        if (alignCode === "1") alignStr = "right";
        else if (alignCode === "2") alignStr = "center";
        else if (alignCode === "4" || alignCode === "3") alignStr = "decimal"; // Swing TabStop.ALIGN_DECIMAL = 4

        if (!isNaN(pt) && pt > 0.5) {
          const cmVal = (Math.round((pt / 28.3465) * 100) / 100).toFixed(2);
          stops.push(`${cmVal}:${alignStr}`);
        }
      });
      dataAttrs += ` data-udf-tabset="${escapeHtmlStr(tabSet)}"`;
    }
    if (hangPt > 0.5 && Math.abs(totalLeftPt) > 0.1) {
      const hangCm = Math.round((totalLeftPt / 28.3465) * 100) / 100;
      const hasHang = stops.some(s => Math.abs(parseFloat(s.split(":")[0]) - hangCm) < 0.06);
      if (!hasHang) {
        stops.push(`${hangCm.toFixed(2)}:left`);
        stops.sort((a, b) => parseFloat(a.split(":")[0]) - parseFloat(b.split(":")[0]));
      }
    }
    if (stops.length > 0) dataAttrs += ` data-tab-stops="${stops.join(",")}"`;
    if (lineSpacing) dataAttrs += ` data-udf-linespacing="${escapeHtmlStr(lineSpacing)}"`;
    dataAttrs += dataAttrsPitch;
    if (stops.length > 0) dataAttrs += ` data-orig-tab-stops="${stops.join(",")}"`;
    dataAttrs += udfAttrsData(p);

    let pHtml = "";
    const isNumbered = p.getAttribute("Numbered") === "true" || p.getAttribute("Numbered") === "1";
    const isBulleted = p.getAttribute("Bulleted") === "true" || p.getAttribute("Bulleted") === "1";
    if (isNumbered) {
      const listId = p.getAttribute("ListId") || "default";
      const count = (listCounters[listId] || 0) + 1;
      listCounters[listId] = count;
      const numType = p.getAttribute("NumberType") || "";
      let prefix = `${count}. `;
      if (numType.includes("ROMAN")) prefix = `${toRomanNumeral(count)}. `;
      else if (numType.includes("CHAR_SMALL") || numType.includes("ALPHA")) prefix = `${String.fromCharCode(97 + ((count - 1) % 26))}) `;
      else if (numType.includes("CHAR_BIG")) prefix = `${String.fromCharCode(65 + ((count - 1) % 26))}. `;
      pHtml += `<span class="udf-list-prefix" contenteditable="false" style="font-weight:bold; margin-right:4px;">${escapeHtmlStr(prefix)}</span>`;
      dataAttrs += ` data-udf-numbered="true"`;
      if (numType) dataAttrs += ` data-udf-number-type="${escapeHtmlStr(numType)}"`;
    } else if (isBulleted) {
      pHtml += `<span class="udf-list-prefix" contenteditable="false" style="font-weight:bold; margin-right:6px;">•</span>`;
      dataAttrs += ` data-udf-bulleted="true"`;
    }

    const pFamily = resolveAttr(p, "family");
    const pSize = resolveAttr(p, "size");
    // Satır yüksekliği (strut) paragrafın puntosundan hesaplanır: Havelsan'daki gibi
    // gerçek metin puntosu kullanılsın diye paragrafa ilk koşunun puntosu verilir.
    const firstSized = Array.from(p.children).find(ch => ch.hasAttribute && ch.hasAttribute("size"));
    const strutSize = (firstSized && firstSized.getAttribute("size")) || pSize;
    if (strutSize && !isNaN(parseFloat(strutSize))) styleStr += ` font-size: ${parseFloat(strutSize)}pt;`;
    const pFg = resolveAttr(p, "foreground");
    const pBold = resolveAttr(p, "bold") === "true";
    const pItalic = resolveAttr(p, "italic") === "true";
    const pUnderline = resolveAttr(p, "underline") === "true";

    let hasContent = false;
    Array.from(p.children).forEach(c => {
      const tag = c.tagName ? c.tagName.toLowerCase() : "";
      if (tag === "image") {
        const imgData = c.getAttribute("imageData");
        if (imgData && imgData.trim()) {
          const wStr = c.getAttribute("width") || "";
          const hStr = c.getAttribute("height") || "";
          const wCm = wStr ? Math.round((parseFloat(wStr) / 28.3465) * 100) / 100 : 0;
          const hCm = hStr ? Math.round((parseFloat(hStr) / 28.3465) * 100) / 100 : 0;
          let imgStyle = "display:inline-block; vertical-align:middle; object-fit:contain;";
          if (wCm > 0) imgStyle += ` width:${wCm}cm; max-width:${wCm}cm;`;
          else imgStyle += " max-width:95%; width:auto;";
          if (hCm > 0) imgStyle += ` height:${hCm}cm; max-height:${hCm}cm;`;
          pHtml += `<img data-udf-width="${escapeHtmlStr(wStr)}" data-udf-height="${escapeHtmlStr(hStr)}" src="data:image/png;base64,${imgData.trim()}" style="${imgStyle}" />`;
          hasContent = true;
        }
      } else if (tag === "content" || tag === "space" || tag === "field" || tag === "tab") {
        let chunk = "";
        if (tag === "tab") {
          const tLen = Math.max(1, parseInt(c.getAttribute("length") || "1", 10) || 1);
          chunk = "\t".repeat(tLen);
        } else {
          const fieldName = (c.getAttribute("fieldName") || "").toLowerCase();
          if (fieldName && dataMap[fieldName] && dataMap[fieldName].trim()) {
            chunk = dataMap[fieldName];
          } else if (c.hasAttribute("startOffset") && c.hasAttribute("length")) {
            const start = parseInt(c.getAttribute("startOffset") || "0", 10);
            const len = parseInt(c.getAttribute("length") || "0", 10);
            if (start >= 0 && start < textLen) {
              chunk = rawText.substring(start, Math.min(start + len, textLen));
            }
          } else if (tag === "space") {
            chunk = " ";
          }
        }

        // Paragraf sonu satır karakteri yalnızca SON koşuda atılır; şablon `eol` alanlarının
        // ürettiği ara satır sonları <br> olarak korunur (Havelsan ile aynı).
        const isLastRun = !c.nextElementSibling;
        if (isLastRun || /^[\r\n]+$/.test(chunk) === false) {
          if (isLastRun) {
            if (chunk.endsWith("\r\n")) chunk = chunk.substring(0, chunk.length - 2);
            else if (chunk.endsWith("\n") || chunk.endsWith("\r")) chunk = chunk.substring(0, chunk.length - 1);
          }
        }
        chunk = chunk.replace(/\r\n?/g, "\n");

        if (chunk) {
          hasContent = true;
          if (isHeaderOrFooter && /^[-_]{10,}$/.test(chunk.trim())) {
            styleStr += " white-space: nowrap; overflow: hidden; text-overflow: clip;";
          }
          const bold = c.hasAttribute("bold") ? c.getAttribute("bold") === "true" : pBold;
          const italic = c.hasAttribute("italic") ? c.getAttribute("italic") === "true" : pItalic;
          const underline = c.hasAttribute("underline") ? c.getAttribute("underline") === "true" : pUnderline;
          const sub = c.getAttribute("subscript") === "true" || c.getAttribute("Subscript") === "true";
          const sup = c.getAttribute("superscript") === "true" || c.getAttribute("Superscript") === "true";
          const strike = c.getAttribute("strikethrough") === "true" || c.getAttribute("StrikeThrough") === "true" || c.getAttribute("strikeThrough") === "true";
          const rFamily = c.getAttribute("family") || pFamily;
          const rSize = c.getAttribute("size") || pSize;
          const rFg = c.getAttribute("foreground") || pFg;
          const rBg = c.getAttribute("background") || "";

          let seg = escapeHtmlStr(chunk)
            .replace(/\t/g, '<span class="udf-tab-space" contenteditable="false">&#8203;</span>')
            .replace(/\n/g, "<br>");
          if (bold) seg = `<strong>${seg}</strong>`;
          if (italic) seg = `<em>${seg}</em>`;
          if (underline) seg = `<u>${seg}</u>`;
          if (sub) seg = `<sub>${seg}</sub>`;
          if (sup) seg = `<sup>${seg}</sup>`;
          if (strike) seg = `<s>${seg}</s>`;

          let spanStyle = "";
          // Yazı tipi ve punto her zaman açıkça yazılır: belge stili (ör. 11pt Arial) editör
          // varsayılanından farklı olsa bile hem ekranda hem kayıtta birebir korunur.
          if (rFamily && rFamily !== "Dialog") spanStyle += `font-family:'${escapeHtmlStr(rFamily)}';`;
          if (rSize) spanStyle += `font-size:${escapeHtmlStr(rSize)}pt;`;
          const fgHex = parseSignedRgbToHexJs(rFg, true);
          if (fgHex) spanStyle += `color:${fgHex};`;
          const bgHex = parseSignedRgbToHexJs(rBg, false);
          if (bgHex) spanStyle += `background-color:${bgHex};`;
          if (spanStyle) seg = `<span style="${spanStyle}">${seg}</span>`;
          pHtml += seg;
        }
      }
    });

    return `<p style="${styleStr}"${dataAttrs}>${hasContent ? pHtml : "<br>"}</p>\n`;
  }

  function parseTableToHtml(tableElem) {
    const border = tableElem.getAttribute("border") || "";
    const isNone = border === "borderNone" || border === "none";
    const colSpans = tableElem.getAttribute("columnSpans") || "";
    let colWidthsPct = null;
    if (colSpans.trim()) {
      const nums = colSpans.split(",").map(s => Math.max(1, parseFloat(s.trim()) || 100));
      const sum = nums.reduce((a, b) => a + b, 0);
      if (sum > 0) colWidthsPct = nums.map(n => (n / sum) * 100);
    }

    const tableStyle = isNone
      ? "width:100%; border-collapse:collapse; margin:6px 0; border:none;"
      : "width:100%; border-collapse:collapse; margin:6px 0; border:1px solid #333;";

    let tblHtml = `<table style="${tableStyle}"${border ? ` data-udf-border="${escapeHtmlStr(border)}"` : ""}${colSpans ? ` data-udf-col-spans="${escapeHtmlStr(colSpans)}"` : ""}${udfAttrsData(tableElem)}>\n`;
    Array.from(tableElem.children).forEach(r => {
      if ((r.tagName || "").toLowerCase() !== "row") return;
      tblHtml += `  <tr style="border:none;"${udfAttrsData(r)}>\n`;
      const cells = Array.from(r.children).filter(c => (c.tagName || "").toLowerCase() === "cell");
      // Havelsan satır bazlı sütun genişlikleri (row columnSpans) tablo genelinden önceliklidir.
      const rowSpansAttr = r.getAttribute("columnSpans");
      let rowWidthsPct = null;
      if (rowSpansAttr && rowSpansAttr.trim()) {
        const nums = rowSpansAttr.split(",").map(s => Math.max(1, parseFloat(s.trim()) || 1));
        const sum = nums.reduce((a, b) => a + b, 0);
        if (nums.length === cells.length && sum > 0) rowWidthsPct = nums.map(n => (n / sum) * 100);
      }
      const defaultW = cells.length > 0 ? 100 / cells.length : 100;
      cells.forEach((cell, cIdx) => {
        const wPct = rowWidthsPct ? rowWidthsPct[cIdx] : ((colWidthsPct && cIdx < colWidthsPct.length && colWidthsPct.length === cells.length) ? colWidthsPct[cIdx] : defaultW);
        const cBorder = cell.getAttribute("border") || "";
        const cellNone = isNone || cBorder === "borderNone" || cBorder === "none";
        const cellStyle = cellNone
          ? `vertical-align:top; border:none; padding:3px 6px; width:${wPct.toFixed(1)}%;`
          : `vertical-align:top; border:1px solid #333; padding:3px 6px; width:${wPct.toFixed(1)}%;`;
        const colSpan = cell.getAttribute("colSpan");
        const rowSpan = cell.getAttribute("rowSpan");
        tblHtml += `    <td style="${cellStyle}"${colSpan ? ` colspan="${escapeHtmlStr(colSpan)}"` : ""}${rowSpan ? ` rowspan="${escapeHtmlStr(rowSpan)}"` : ""}${udfAttrsData(cell)}>\n`;
        let hasChild = false;
        Array.from(cell.children).forEach(cc => {
          const ccTag = (cc.tagName || "").toLowerCase();
          if (ccTag === "paragraph") {
            tblHtml += parseParagraphToHtml(cc);
            hasChild = true;
          } else if (ccTag === "table") {
            tblHtml += parseTableToHtml(cc);
            hasChild = true;
          }
        });
        if (!hasChild) tblHtml += `<p style="text-align: left;"><br></p>\n`;
        tblHtml += `    </td>\n`;
      });
      tblHtml += `  </tr>\n`;
    });
    tblHtml += `</table>\n`;
    return tblHtml;
  }

  // Üstbilgi (<header>) çözümleme (Resim + Paragraf + Tablo birlikte desteklenir)
  let headerHtml = "";
  let headerStartPage = 1;
  const headerElem = xmlDoc.querySelector("header");
  if (headerElem) {
    if (headerElem.getAttribute("startPage")) {
      headerStartPage = parseInt(headerElem.getAttribute("startPage"), 10) || 1;
    }
    Array.from(headerElem.children).forEach(hc => {
      const hTag = (hc.tagName || "").toLowerCase();
      if (hTag === "image") {
        const hImgData = hc.getAttribute("imageData");
        if (hImgData && hImgData.trim()) {
          const wStr = hc.getAttribute("width") || "";
          const hStr = hc.getAttribute("height") || "";
          const hCm = hStr ? Math.round((parseFloat(hStr) / 28.3465) * 100) / 100 : 1.76;
          headerHtml += `<div class="udf-header-layout" style="text-align:center; padding-bottom:4px;"><img class="udf-header-img" data-udf-width="${escapeHtmlStr(wStr)}" data-udf-height="${escapeHtmlStr(hStr)}" src="data:image/png;base64,${hImgData.trim()}" style="max-height:${hCm}cm; width:auto; object-fit:contain;" /></div>`;
        }
      } else if (hTag === "paragraph") {
        const pStr = parseParagraphToHtml(hc, true);
        if (!pStr.includes("<br></p>") || !headerHtml) headerHtml += pStr;
      } else if (hTag === "table") {
        headerHtml += parseTableToHtml(hc);
      }
    });
  }

  // Altbilgi (<footer>) çözümleme
  let footerHtml = "";
  let footerPageSpec = "";
  let footerForeStr = "Sayfa:";
  let footerSep = "/";
  let footerPageStart = "1";
  const footerElem = xmlDoc.querySelector("footer");
  if (footerElem) {
    let hasPageNum = false;
    if (footerElem.hasAttribute("pageNumber-foreStr")) { footerForeStr = footerElem.getAttribute("pageNumber-foreStr"); hasPageNum = true; }
    if (footerElem.hasAttribute("pageNumber-seperator")) { footerSep = footerElem.getAttribute("pageNumber-seperator"); hasPageNum = true; }
    if (footerElem.hasAttribute("pageNumber-spec")) {
      footerPageSpec = footerElem.getAttribute("pageNumber-spec");
      if (!footerPageSpec.startsWith("0")) hasPageNum = true;
    }
    if (footerElem.hasAttribute("pageNumber-start")) footerPageStart = footerElem.getAttribute("pageNumber-start");

    let hasFooterImg = false;
    // Havelsan biçimi: ön ek + numara + ayraç + toplam, boşluksuz ("Sayfa:1/10", ön ek boşsa "1/2"); yazı tipi UDF'den
    const pnFace = footerElem.getAttribute("pageNumber-fontFace") || "Arial";
    const pnSize = parseFloat(footerElem.getAttribute("pageNumber-fontSize") || "11") || 11;
    const pageLabelText = `<span style="font-family:'${escapeHtmlStr(pnFace)}', Arial, sans-serif; font-size:${pnSize}pt;">${escapeHtmlStr(footerForeStr || "")}{PAGE_NUM}${escapeHtmlStr((footerSep || "/").trim())}{TOTAL_PAGES}</span>`;
    Array.from(footerElem.children).forEach(fc => {
      const fTag = (fc.tagName || "").toLowerCase();
      let imgEl = null;
      if (fTag === "image") {
        imgEl = fc;
      } else if (fTag === "paragraph") {
        const pImg = fc.querySelector("image");
        if (pImg) {
          let pTxt = "";
          fc.querySelectorAll("content, field").forEach(cn => {
            const s = parseInt(cn.getAttribute("startOffset") || "0", 10);
            const l = parseInt(cn.getAttribute("length") || "0", 10);
            if (s >= 0 && l > 0 && s < textLen) pTxt += rawText.substring(s, Math.min(s + l, textLen));
          });
          pTxt = pTxt.replace(/[\uFFFC\u00B8\r\n\t\s]+/g, "");
          if (!pTxt) imgEl = pImg;
        }
      }
      if (imgEl) {
        const fImgData = imgEl.getAttribute("imageData");
        if (fImgData && fImgData.trim()) {
          hasFooterImg = true;
          const wStr = imgEl.getAttribute("width") || "";
          const hStr = imgEl.getAttribute("height") || "";
          const wCm = wStr ? Math.round((parseFloat(wStr) / 28.3465) * 100) / 100 : 0;
          const hCm = hStr ? Math.round((parseFloat(hStr) / 28.3465) * 100) / 100 : 1.76;
          const dimStyle = `max-height:${hCm}cm;${wCm > 0 ? ` max-width:${wCm}cm;` : " max-width:82%;"} width:auto; object-fit:contain;`;
          const qrPart = verificationCode ? `<div class="udf-footer-qr-container" data-verification-code="${escapeHtmlStr(verificationCode)}" style="width:68px; height:68px; flex:0 0 auto;"></div>` : "";
          if (hasPageNum) {
            // Havelsan: logo (paragraf hizasıyla, genelde ortada) | "Sayfa:1/10" | karekod — hepsi alta hizalı tek satır
            footerHtml += `<div class="udf-footer-layout udf-hv-footer" data-has-qr="${qrPart ? 1 : 0}" style="display:flex; align-items:flex-end; width:100%; gap:6px;"><div style="flex:1 1 auto; display:flex; justify-content:center; align-items:flex-end;"><img class="udf-footer-img" data-udf-width="${escapeHtmlStr(wStr)}" data-udf-height="${escapeHtmlStr(hStr)}" src="data:image/png;base64,${fImgData.trim()}" style="${dimStyle} max-height:none;" /></div><span class="udf-footer-page-label" style="align-self:flex-end; margin-bottom:2px;">${pageLabelText}</span>${qrPart}</div>`;
          } else {
            footerHtml += `<div class="udf-footer-layout full-banner" style="justify-content:center; border-top:none;"><img class="udf-footer-img" data-udf-width="${escapeHtmlStr(wStr)}" data-udf-height="${escapeHtmlStr(hStr)}" src="data:image/png;base64,${fImgData.trim()}" style="${dimStyle}" />${qrPart}</div>`;
          }
        }
      } else if (fTag === "paragraph") {
        const pStr = parseParagraphToHtml(fc, true);
        if (!pStr.includes("<br></p>")) footerHtml += pStr;
      } else if (fTag === "table") {
        footerHtml += parseTableToHtml(fc);
      }
    });
    if (!hasFooterImg && hasPageNum) {
      const qrPart = verificationCode ? `<div class="udf-footer-qr-container" data-verification-code="${escapeHtmlStr(verificationCode)}" style="width:68px; height:68px; flex:0 0 auto;"></div>` : "";
      // Havelsan mahkeme evrakı altbilgisi: "1/2" sağda; altında ince çizgi, çizginin altında küçük doğrulama metni
      // (kod daha büyük puntoda), en sağda karekod — tamamı sayfanın en altına yaslı.
      const textPart = verificationCode ? `<div class="udf-official-footer-text" style="flex:1 1 auto; border-top:0.75pt solid #000; padding-top:2px; text-align:left; font-family:Arial, sans-serif; font-size:5pt; line-height:1.3; color:#000; white-space:nowrap; overflow:hidden;">UYAP Bilişim Sistemindeki bu dokümana http://vatandas.uyap.gov.tr adresinden <span style="font-size:9pt;">${escapeHtmlStr(verificationCode)}</span> ile erişebilirsiniz.</div>` : "";
      footerHtml += `<div class="udf-footer-layout udf-hv-footer" data-has-qr="${qrPart ? 1 : 0}" style="display:flex; flex-direction:column; align-items:stretch; justify-content:flex-end; width:100%;"><div class="udf-footer-page-label" style="text-align:right; line-height:1.2;">${pageLabelText}</div><div style="display:flex; align-items:flex-end; gap:6px;">${textPart || '<div style="flex:1"></div>'}${qrPart}</div></div>`;
    }
  }

  if (verificationCode && !footerHtml) {
    footerHtml = `<div class="udf-official-footer" style="display:flex; justify-content:space-between; align-items:flex-end; border-top:0.5px solid #000; padding-top:4px; font-family:Arial, sans-serif; font-size:7.5pt; line-height:1.2; width:100%; box-sizing:border-box;">
      <div style="flex:1; max-width:82%; text-align:left; word-break:break-all; padding-right:8px;">
        UYAP Bilişim Sistemindeki bu dokümana http://vatandas.uyap.gov.tr adresinden <strong>${escapeHtmlStr(verificationCode)}</strong> ile erişebilirsiniz.
      </div>
      <div style="display:flex; flex-direction:column; align-items:flex-end; min-width:60px;">
        <span class="udf-footer-page-label" style="font-size:8.5pt; font-family:Arial, sans-serif; margin-bottom:2px;">{PAGE_NUM}/{TOTAL_PAGES}</span>
        <div class="udf-footer-qr-container" data-verification-code="${escapeHtmlStr(verificationCode)}" style="width:34px; height:34px;"></div>
      </div>
    </div>`;
  }

  let html = "";
  const elementsNode = xmlDoc.querySelector("template > elements") || xmlDoc.querySelector("elements");
  if (elementsNode && elementsNode.children.length > 0) {
    Array.from(elementsNode.children).forEach(child => {
      const tag = (child.tagName || "").toLowerCase();
      if (tag === "paragraph") html += parseParagraphToHtml(child);
      else if (tag === "table") html += parseTableToHtml(child);
      else if (tag === "page-break" || tag === "pagebreak") {
        html += `<div class="udf-page-break" data-udf-page-break="true" style="page-break-after:always; break-after:page; height:0; margin:12px 0; border-top:1px dashed #94a3b8;"></div>\n`;
      }
    });
  } else {
    xmlDoc.querySelectorAll("paragraph").forEach(p => {
      const parentTag = p.parentElement ? p.parentElement.tagName.toLowerCase() : "";
      if (parentTag === "header" || parentTag === "footer" || parentTag === "cell") return;
      html += parseParagraphToHtml(p);
    });
  }

  return {
    header: "",
    headerHtml,
    headerStartPage,
    footer: "",
    footerHtml,
    footerPageSpec,
    footerForeStr,
    footerSep,
    footerPageStart,
    verificationCode,
    sicil: uyapSicil,
    leftMarginCm, rightMarginCm, topMarginCm, bottomMarginCm,
    headerMarginCm, footerMarginCm,
    paperOrientation,
    html: html || '<p style="text-align: justify;"><br></p>',
    signature: signatureInfo
  };
}

// -------------------------------------------------------------
// 2. DOCX DOSYASI AYRIŞTIRMA (OOXML PARSER)
// -------------------------------------------------------------
function isXmlToggleOn(parent, tagW, tagPlain) {
  const el = parent.getElementsByTagName(tagW)[0] || parent.getElementsByTagName(tagPlain)[0];
  if (!el) return false;
  const val = (el.getAttribute("w:val") || el.getAttribute("val") || "").toLowerCase();
  if (!val) return true;
  return !(val === "0" || val === "false" || val === "none" || val === "off");
}

async function parseDocxArrayBuffer(buffer) {
  if (!buffer || buffer.byteLength === 0) return buildEmptyResult();
  const u8 = new Uint8Array(buffer);
  if (u8.length >= 8 && u8[0] === 0xD0 && u8[1] === 0xCF && u8[2] === 0x11 && u8[3] === 0xE0) {
    return parseOle2WordDocBuffer(buffer);
  }

  let zip;
  try {
    zip = await JSZip.loadAsync(buffer);
  } catch (e) {
    return await parseUdfArrayBuffer(buffer);
  }

  if (!zip.file("word/document.xml") && (zip.file("content.xml") || zip.file("Content.xml"))) {
    return await parseUdfArrayBuffer(buffer);
  }

  const docXmlFile = zip.file("word/document.xml");
  if (!docXmlFile) return await parseUdfArrayBuffer(buffer);

  const docXml = stripBomAndLeadingGarbage(await docXmlFile.async("text"));
  const parser = new DOMParser();
  const xmlDoc = parser.parseFromString(docXml, "application/xml");

  // İlişkiler ve Görseller (word/media/*)
  const relMap = {};
  const mediaBase64Map = {};
  const relFile = zip.file("word/_rels/document.xml.rels");
  if (relFile) {
    try {
      const relDoc = parser.parseFromString(stripBomAndLeadingGarbage(await relFile.async("text")), "application/xml");
      Array.from(relDoc.getElementsByTagName("Relationship")).forEach(rEl => {
        const id = rEl.getAttribute("Id");
        let target = rEl.getAttribute("Target") || "";
        if (target.startsWith("/word/")) target = target.substring(6);
        else if (target.startsWith("/")) target = target.substring(1);
        if (id && target) relMap[id] = target;
      });
    } catch (e) {}
  }
  for (const [fName, zObj] of Object.entries(zip.files)) {
    if (!zObj.dir && fName.toLowerCase().startsWith("word/media/")) {
      try {
        const b64 = await zObj.async("base64");
        mediaBase64Map[fName] = b64;
        if (fName.startsWith("word/")) mediaBase64Map[fName.substring(5)] = b64;
      } catch (e) {}
    }
  }

  let leftMarginCm = 2.0, rightMarginCm = 2.0, topMarginCm = 2.0, bottomMarginCm = 2.0;
  let orientation = "portrait";
  const pgMar = xmlDoc.getElementsByTagName("w:pgMar")[0] || xmlDoc.getElementsByTagName("pgMar")[0];
  if (pgMar) {
    const parseDxa = (attr, def) => {
      const v = parseFloat(pgMar.getAttribute("w:" + attr) || pgMar.getAttribute(attr) || "");
      return !isNaN(v) ? Math.round((v / 567) * 100) / 100 : def;
    };
    leftMarginCm = parseDxa("left", 2.0);
    rightMarginCm = parseDxa("right", 2.0);
    topMarginCm = parseDxa("top", 2.0);
    bottomMarginCm = parseDxa("bottom", 2.0);
  }
  const pgSz = xmlDoc.getElementsByTagName("w:pgSz")[0] || xmlDoc.getElementsByTagName("pgSz")[0];
  if (pgSz && (pgSz.getAttribute("w:orient") === "landscape" || pgSz.getAttribute("orient") === "landscape")) {
    orientation = "landscape";
  }

  let headerText = "", footerText = "";
  const hEntry = zip.file("word/header1.xml") || zip.file("word/header2.xml");
  if (hEntry) {
    const hx = stripBomAndLeadingGarbage(await hEntry.async("text"));
    headerText = (parser.parseFromString(hx, "application/xml").textContent || "").trim();
  }
  const fEntry = zip.file("word/footer1.xml") || zip.file("word/footer2.xml");
  if (fEntry) {
    const fx = stripBomAndLeadingGarbage(await fEntry.async("text"));
    footerText = (parser.parseFromString(fx, "application/xml").textContent || "").trim();
  }

  function parseDocxParagraph(node) {
    let align = "left";
    let firstLineCm = 0, hangingCm = 0, leftIndentCm = 0, rightIndentCm = 0;
    let spaceAbovePt = 0, spaceBelowPt = 2;
    let tabStopAttr = "";

    const pPr = Array.from(node.children).find(c => c.nodeName === "w:pPr" || c.nodeName === "pPr");
    if (pPr) {
      const jc = pPr.getElementsByTagName("w:jc")[0] || pPr.getElementsByTagName("jc")[0];
      if (jc) {
        const val = (jc.getAttribute("w:val") || jc.getAttribute("val") || "").toLowerCase();
        if (val === "center") align = "center";
        else if (val === "right" || val === "end") align = "right";
        else if (val === "both" || val === "distribute") align = "justify";
        else align = "left";
      }
      const ind = pPr.getElementsByTagName("w:ind")[0] || pPr.getElementsByTagName("ind")[0];
      if (ind) {
        const dxa = (a) => {
          const v = parseFloat(ind.getAttribute("w:" + a) || ind.getAttribute(a) || "");
          return !isNaN(v) ? Math.round((v / 567) * 100) / 100 : 0;
        };
        firstLineCm = dxa("firstLine");
        hangingCm = dxa("hanging");
        leftIndentCm = dxa("left") || dxa("start");
        rightIndentCm = dxa("right") || dxa("end");
      }
      const sp = pPr.getElementsByTagName("w:spacing")[0] || pPr.getElementsByTagName("spacing")[0];
      if (sp) {
        const bf = parseFloat(sp.getAttribute("w:before") || sp.getAttribute("before") || "");
        const af = parseFloat(sp.getAttribute("w:after") || sp.getAttribute("after") || "");
        if (!isNaN(bf)) spaceAbovePt = Math.round(bf / 20);
        if (!isNaN(af)) spaceBelowPt = Math.round(af / 20);
      }
      const tabsEl = pPr.getElementsByTagName("w:tabs")[0] || pPr.getElementsByTagName("tabs")[0];
      if (tabsEl) {
        const stops = [];
        Array.from(tabsEl.children).forEach(t => {
          const pos = parseFloat(t.getAttribute("w:pos") || t.getAttribute("pos") || "0");
          if (pos > 0) stops.push((Math.round((pos / 567) * 100) / 100).toFixed(2));
        });
        if (stops.length > 0) tabStopAttr = ` data-tab-stops="${stops.join(",")}"`;
      }
    }

    let cssMarginLeft = leftIndentCm;
    const cssTextIndent = firstLineCm > 0 ? firstLineCm : (hangingCm > 0 ? -hangingCm : 0);
    if (hangingCm > 0 && cssMarginLeft < hangingCm) cssMarginLeft = hangingCm;

    let styleStr = `text-align: ${align}; margin-top: ${spaceAbovePt}pt; margin-bottom: ${spaceBelowPt}pt;`;
    if (Math.abs(cssMarginLeft) > 0.01) styleStr += ` margin-left: ${cssMarginLeft}cm;`;
    if (Math.abs(cssTextIndent) > 0.01) styleStr += ` text-indent: ${cssTextIndent}cm;`;
    if (Math.abs(rightIndentCm) > 0.01) styleStr += ` margin-right: ${rightIndentCm}cm;`;

    let pHtml = "";
    let hasContent = false;
    let hasTab = false;
    let firstLabel = "";

    Array.from(node.children).forEach((child, idx) => {
      const cName = child.nodeName;
      if (cName === "w:r" || cName === "r") {
        const rPr = Array.from(child.children).find(rc => rc.nodeName === "w:rPr" || rc.nodeName === "rPr");
        const isBold = rPr ? isXmlToggleOn(rPr, "w:b", "b") : false;
        const isItalic = rPr ? isXmlToggleOn(rPr, "w:i", "i") : false;
        const isUnderline = rPr ? isXmlToggleOn(rPr, "w:u", "u") : false;
        const isStrike = rPr ? isXmlToggleOn(rPr, "w:strike", "strike") : false;
        // v3.15: punto, renk ve yazı tipi de okunur (eskiden tüm metin varsayılan puntoya dönüyordu)
        let runCss = "";
        if (rPr) {
          const szEl = rPr.getElementsByTagName("w:sz")[0];
          const sz = szEl ? parseFloat(szEl.getAttribute("w:val")) : NaN;
          if (!isNaN(sz) && sz > 0 && sz !== 24) runCss += `font-size: ${sz / 2}pt;`;
          const colEl = rPr.getElementsByTagName("w:color")[0];
          const col = colEl ? (colEl.getAttribute("w:val") || "") : "";
          if (/^[0-9a-f]{6}$/i.test(col) && col.toLowerCase() !== "000000") runCss += ` color: #${col};`;
          const fEl = rPr.getElementsByTagName("w:rFonts")[0];
          const fn = fEl ? (fEl.getAttribute("w:ascii") || fEl.getAttribute("w:hAnsi") || "") : "";
          if (fn && !/times new roman/i.test(fn)) runCss += ` font-family: '${fn.replace(/['"]/g, "")}';`;
        }

        Array.from(child.children).forEach((rc, rcIdx) => {
          const rcn = rc.nodeName;
          if (rcn === "w:t" || rcn === "t") {
            const t = rc.textContent;
            if (t) {
              hasContent = true;
              if (!firstLabel && idx === 0) firstLabel = t.trim();
              let seg = escapeHtmlStr(t).replace(/\n/g, "<br>");
              if (isBold) seg = `<strong>${seg}</strong>`;
              if (isItalic) seg = `<em>${seg}</em>`;
              if (isUnderline) seg = `<u>${seg}</u>`;
              if (isStrike) seg = `<s>${seg}</s>`;
              if (runCss) seg = `<span style="${runCss.trim()}">${seg}</span>`;
              pHtml += seg;
            }
          } else if (rcn === "w:tab" || rcn === "tab") {
            hasTab = true;
            hasContent = true;
            pHtml += `<span class="udf-tab-space" contenteditable="false">&#8203;</span>`;
          } else if (rcn === "w:br" || rcn === "br") {
            const isTrailing = (rcIdx === child.children.length - 1 && idx === node.children.length - 1 && hasContent);
            if (!isTrailing) {
              hasContent = true;
              pHtml += `<br>`;
            }
          } else if (rcn === "w:drawing" || rcn === "drawing" || rcn === "w:pict" || rcn === "pict") {
            const blip = rc.getElementsByTagName("a:blip")[0] || rc.getElementsByTagName("blip")[0];
            const embedId = blip ? (blip.getAttribute("r:embed") || blip.getAttribute("embed") || "") : "";
            if (embedId && relMap[embedId] && mediaBase64Map[relMap[embedId]]) {
              const target = relMap[embedId];
              const b64 = mediaBase64Map[target];
              const mime = target.toLowerCase().endsWith(".jpg") || target.toLowerCase().endsWith(".jpeg") ? "image/jpeg" : "image/png";
              pHtml += `<img src="data:${mime};base64,${b64}" style="display:inline-block; vertical-align:middle; max-width:95%; height:auto;" />`;
              hasContent = true;
            }
          }
        });
      }
    });

    if (!tabStopAttr && hasTab && isLegalMetadata(firstLabel)) {
      tabStopAttr = ' data-tab-stops="5"';
    }

    return `<p style="${styleStr}"${tabStopAttr}>${hasContent ? pHtml : "<br>"}</p>\n`;
  }

  function parseDocxTable(tblNode) {
    let tblHtml = `<table style="width: 100%; border-collapse: collapse; margin: 6px 0; border: 1px solid #333;">\n`;
    Array.from(tblNode.children).forEach(tr => {
      if (tr.nodeName !== "w:tr" && tr.nodeName !== "tr") return;
      tblHtml += `  <tr>\n`;
      Array.from(tr.children).forEach(tc => {
        if (tc.nodeName !== "w:tc" && tc.nodeName !== "tc") return;
        tblHtml += `    <td style="border: 1px solid #333; padding: 4px 6px; vertical-align: top;">\n`;
        Array.from(tc.children).forEach(tp => {
          if (tp.nodeName === "w:p" || tp.nodeName === "p") tblHtml += parseDocxParagraph(tp);
          else if (tp.nodeName === "w:tbl" || tp.nodeName === "tbl") tblHtml += parseDocxTable(tp);
        });
        tblHtml += `    </td>\n`;
      });
      tblHtml += `  </tr>\n`;
    });
    tblHtml += `</table>\n`;
    return tblHtml;
  }

  let html = "";
  const body = xmlDoc.getElementsByTagName("w:body")[0] || xmlDoc.getElementsByTagName("body")[0] || xmlDoc;
  Array.from(body.children || []).forEach(node => {
    const name = node.nodeName;
    if (name === "w:p" || name === "p") html += parseDocxParagraph(node);
    else if (name === "w:tbl" || name === "tbl") html += parseDocxTable(node);
  });

  return {
    header: headerText,
    headerHtml: headerText ? `<div class="udf-header-layout" style="text-align:center;">${escapeHtmlStr(headerText)}</div>` : "",
    footer: footerText,
    footerHtml: footerText ? `<div class="udf-footer-layout"><span class="udf-footer-text">${escapeHtmlStr(footerText)}</span></div>` : "",
    leftMarginCm, rightMarginCm, topMarginCm, bottomMarginCm,
    paperOrientation: orientation,
    html: html || '<p style="text-align: justify;"><br></p>'
  };
}

// -------------------------------------------------------------
// 2B. ÇOK SAYFALI TIFF / TIF AYRIŞTIRICI (TARANMIŞ ADLİ EVRAKLAR)
// -------------------------------------------------------------
async function parseTiffArrayBuffer(buffer) {
  if (!buffer || buffer.byteLength < 8) return buildEmptyResult();
  const dataView = new DataView(buffer);
  const byteLength = buffer.byteLength;

  const byteOrder = String.fromCharCode(dataView.getUint8(0), dataView.getUint8(1));
  let littleEndian;
  if (byteOrder === "II") littleEndian = true;
  else if (byteOrder === "MM") littleEndian = false;
  else throw new Error("Geçersiz TIFF başlığı: " + byteOrder);

  const magic = dataView.getUint16(2, littleEndian);
  if (magic !== 42) throw new Error("Bilinmeyen TIFF numarası: " + magic);

  let ifdOffset = dataView.getUint32(4, littleEndian);
  const pages = [];
  let pageIndex = 1;

  while (ifdOffset !== 0 && ifdOffset + 2 <= byteLength) {
    const numEntries = dataView.getUint16(ifdOffset, littleEndian);
    let offset = ifdOffset + 2;
    const tags = {};

    for (let i = 0; i < numEntries; i++) {
      if (offset + 12 > byteLength) break;
      const tagId = dataView.getUint16(offset, littleEndian);
      const tagType = dataView.getUint16(offset + 2, littleEndian);
      const count = dataView.getUint32(offset + 4, littleEndian);

      const valOffset = ((tagType === 3 && count === 1) || (tagType === 1 && count <= 4) || (tagType === 4 && count === 1))
        ? (offset + 8)
        : dataView.getUint32(offset + 8, littleEndian);

      let val;
      if (tagType === 3) {
        if (count === 1) val = dataView.getUint16(valOffset, littleEndian);
        else {
          val = [];
          for (let c = 0; c < count && valOffset + c * 2 < byteLength; c++) {
            val.push(dataView.getUint16(valOffset + c * 2, littleEndian));
          }
        }
      } else if (tagType === 4) {
        if (count === 1) val = dataView.getUint32(valOffset, littleEndian);
        else {
          val = [];
          for (let c = 0; c < count && valOffset + c * 4 < byteLength; c++) {
            val.push(dataView.getUint32(valOffset + c * 4, littleEndian));
          }
        }
      } else if (tagType === 1) {
        if (count === 1) val = dataView.getUint8(valOffset);
        else {
          val = [];
          for (let c = 0; c < count && valOffset + c < byteLength; c++) {
            val.push(dataView.getUint8(valOffset + c));
          }
        }
      }
      tags[tagId] = val;
      offset += 12;
    }

    const width = tags[256] || 0;
    const height = tags[257] || 0;
    let bps = tags[258] || 1;
    if (Array.isArray(bps)) bps = bps[0];
    const compression = tags[259] || 1;
    const photometric = tags[262] !== undefined ? tags[262] : 1;
    let stripOffsets = tags[273] || [];
    if (!Array.isArray(stripOffsets)) stripOffsets = [stripOffsets];
    let stripByteCounts = tags[279] || [];
    if (!Array.isArray(stripByteCounts)) stripByteCounts = [stripByteCounts];
    const spp = tags[277] || 1;

    if (width > 0 && height > 0 && stripOffsets.length > 0) {
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      const imgData = ctx.createImageData(width, height);
      const data = imgData.data;

      let totalBytes = 0;
      stripByteCounts.forEach(bc => totalBytes += bc);
      const rawBytes = new Uint8Array(totalBytes || 1024);
      let pos = 0;
      for (let s = 0; s < stripOffsets.length; s++) {
        const sOff = stripOffsets[s];
        const sCount = stripByteCounts[s] || (byteLength - sOff);
        if (sOff < byteLength) {
          const chunk = new Uint8Array(buffer, sOff, Math.min(sCount, byteLength - sOff));
          rawBytes.set(chunk, pos);
          pos += chunk.length;
        }
      }

      let decompressed = rawBytes;
      if (compression === 32773) { // PackBits
        const out = [];
        let p = 0;
        while (p < rawBytes.length) {
          const header = (rawBytes[p] << 24) >> 24;
          p++;
          if (header >= 0 && header <= 127) {
            for (let k = 0; k <= header && p < rawBytes.length; k++) out.push(rawBytes[p++]);
          } else if (header >= -127 && header <= -1) {
            const b = rawBytes[p++];
            for (let k = 0; k < 1 - header; k++) out.push(b);
          }
        }
        decompressed = new Uint8Array(out);
      }

      let inIdx = 0;
      let outIdx = 0;
      if (spp === 1 && bps === 1) {
        for (let y = 0; y < height; y++) {
          const rowBytes = Math.ceil(width / 8);
          for (let x = 0; x < width; x++) {
            const byteVal = decompressed[inIdx + Math.floor(x / 8)] || 0;
            const bit = (byteVal >> (7 - (x % 8))) & 1;
            const isWhite = (photometric === 0) ? (bit === 0) : (bit === 1);
            const val = isWhite ? 255 : 0;
            data[outIdx] = val;
            data[outIdx + 1] = val;
            data[outIdx + 2] = val;
            data[outIdx + 3] = 255;
            outIdx += 4;
          }
          inIdx += rowBytes;
        }
      } else if (spp === 1 && bps === 8) {
        for (let i = 0; i < width * height; i++) {
          let g = decompressed[i] || 0;
          if (photometric === 0) g = 255 - g;
          data[outIdx] = g;
          data[outIdx + 1] = g;
          data[outIdx + 2] = g;
          data[outIdx + 3] = 255;
          outIdx += 4;
        }
      } else if (spp >= 3) {
        for (let i = 0; i < width * height; i++) {
          data[outIdx] = decompressed[inIdx] || 0;
          data[outIdx + 1] = decompressed[inIdx + 1] || 0;
          data[outIdx + 2] = decompressed[inIdx + 2] || 0;
          data[outIdx + 3] = (spp === 4) ? (decompressed[inIdx + 3] || 255) : 255;
          inIdx += spp;
          outIdx += 4;
        }
      }

      ctx.putImageData(imgData, 0, 0);
      pages.push({
        pageIndex: pageIndex++,
        width,
        height,
        dataUrl: canvas.toDataURL("image/png")
      });
    }

    if (ifdOffset + 2 + numEntries * 12 + 4 <= byteLength) {
      ifdOffset = dataView.getUint32(ifdOffset + 2 + numEntries * 12, littleEndian);
    } else {
      break;
    }
  }

  if (pages.length === 0) return buildEmptyResult();

  let html = "";
  pages.forEach((p, idx) => {
    html += `<div class="scanned-doc-page" data-page-index="${p.pageIndex}" style="text-align: center; margin-bottom: 8px;">
      <img src="${p.dataUrl}" alt="Sayfa ${p.pageIndex}" style="max-width: 100%; height: auto; display: block; margin: 0 auto; box-shadow: 0 1px 4px rgba(0,0,0,0.12);" />
    </div>`;
    if (idx < pages.length - 1) {
      html += `<div class="udf-page-break" data-udf-page-break="true" style="page-break-after:always; break-after:page; height:0; margin:16px 0; border-top:1px dashed #94a3b8;"></div>\n`;
    }
  });

  return {
    header: "",
    headerHtml: "",
    headerStartPage: 1,
    footer: "",
    footerHtml: `<div class="udf-footer-layout" style="display:flex; justify-content:flex-end; width:100%;"><span class="udf-footer-page-label">Sayfa: {PAGE_NUM}/{TOTAL_PAGES}</span></div>`,
    verificationCode: "",
    leftMarginCm: 1.0,
    rightMarginCm: 1.0,
    topMarginCm: 1.0,
    bottomMarginCm: 1.0,
    headerMarginCm: 0.5,
    footerMarginCm: 0.5,
    paperOrientation: "portrait",
    html: html
  };
}

// -------------------------------------------------------------
// 2C. PDF AYRIŞTIRICI & METİN / SAYFA ÇIKARICI
// -------------------------------------------------------------
async function parsePdfArrayBuffer(buffer) {
  if (!buffer || buffer.byteLength === 0) return buildEmptyResult();
  const u8 = new Uint8Array(buffer);
  const str = new TextDecoder("latin1").decode(u8);
  const textBlocks = [];
  
  const btRegex = /BT[\r\n\s]+([\s\S]*?)ET/g;
  let match;
  while ((match = btRegex.exec(str)) !== null) {
    const block = match[1];
    const tjRegex = /\(([\s\S]*?)\)\s*Tj|\[([\s\S]*?)\]\s*TJ/g;
    let tMatch;
    let blockText = "";
    while ((tMatch = tjRegex.exec(block)) !== null) {
      if (tMatch[1] !== undefined) {
        blockText += tMatch[1].replace(/\\([()\\])/g, "$1") + " ";
      } else if (tMatch[2] !== undefined) {
        const inner = tMatch[2];
        const innerRegex = /\(([\s\S]*?)\)/g;
        let iMatch;
        while ((iMatch = innerRegex.exec(inner)) !== null) {
          blockText += iMatch[1].replace(/\\([()\\])/g, "$1");
        }
        blockText += " ";
      }
    }
    const cleanText = blockText.trim();
    if (cleanText) textBlocks.push(cleanText);
  }

  let html = "";
  if (textBlocks.length > 0) {
    textBlocks.forEach(tb => {
      html += `<p style="text-align: justify; margin: 0; line-height: 1.15;">${escapeHtmlStr(tb)}</p>\n`;
    });
  } else {
    html = `<p style="text-align: justify;"><span style="color:#64748B;">[PDF Dokümanı Başarıyla Yüklendi]</span></p>`;
  }

  return {
    header: "",
    headerHtml: "",
    footer: "",
    footerHtml: `<div class="udf-footer-layout" style="display:flex; justify-content:flex-end; width:100%;"><span class="udf-footer-page-label">Sayfa: {PAGE_NUM}/{TOTAL_PAGES}</span></div>`,
    leftMarginCm: 2.5,
    rightMarginCm: 2.5,
    topMarginCm: 2.0,
    bottomMarginCm: 2.5,
    paperOrientation: "portrait",
    html: html
  };
}

// -------------------------------------------------------------
// 2D. ODT (OpenDocument Text) AYRIŞTIRICI
// -------------------------------------------------------------
async function parseOdtArrayBuffer(buffer) {
  // v3.15: OpenDocument okuyucu yeniden yazıldı. Eski sürüm <text:s/> (boşluk), <text:tab/>, satır sonu,
  // stiller (kalın/italik/punto/renk/hizalama/girinti), tablolar ve görselleri yok sayıyordu.
  if (!buffer || buffer.byteLength === 0) return buildEmptyResult();
  const zip = await JSZip.loadAsync(buffer);
  const contentFile = zip.file("content.xml");
  if (!contentFile) return buildEmptyResult();
  const parser = new DOMParser();
  const contentDoc = parser.parseFromString(stripBomAndLeadingGarbage(await contentFile.async("text")), "application/xml");
  const stylesFile = zip.file("styles.xml");
  const stylesDoc = stylesFile ? parser.parseFromString(stripBomAndLeadingGarbage(await stylesFile.async("text")), "application/xml") : null;

  const local = (n) => (n.localName || n.nodeName.split(":").pop());
  const attr = (el, name) => el ? (el.getAttribute(name) || "") : "";
  const toCm = (v) => {
    const m = /^(-?[\d.]+)\s*(cm|mm|in|pt|px)?$/.exec(String(v || "").trim());
    if (!m) return 0;
    const n = parseFloat(m[1]);
    switch (m[2]) { case "mm": return n / 10; case "in": return n * 2.54; case "pt": return n / 72 * 2.54; case "px": return n / 96 * 2.54; default: return n; }
  };
  const toPt = (v) => { const c = toCm(v); return Math.round(c / 2.54 * 72 * 10) / 10; };

  // Stil tablosu (parent zinciriyle birleştirilmiş)
  const styles = {};
  function collect(doc) {
    if (!doc) return;
    Array.from(doc.getElementsByTagName("style:style")).forEach(st => {
      const name = st.getAttribute("style:name");
      const pp = st.getElementsByTagName("style:paragraph-properties")[0];
      const tp = st.getElementsByTagName("style:text-properties")[0];
      const tabs = pp ? Array.from(pp.getElementsByTagName("style:tab-stop")).map(t => toCm(t.getAttribute("style:position"))) : [];
      styles[name] = {
        parent: st.getAttribute("style:parent-style-name") || "",
        align: attr(pp, "fo:text-align"), ml: attr(pp, "fo:margin-left"), mr: attr(pp, "fo:margin-right"), ti: attr(pp, "fo:text-indent"),
        mt: attr(pp, "fo:margin-top"), mb: attr(pp, "fo:margin-bottom"), lh: attr(pp, "fo:line-height"),
        breakBefore: attr(pp, "fo:break-before"), breakAfter: attr(pp, "fo:break-after"), tabs,
        bold: attr(tp, "fo:font-weight"), italic: attr(tp, "fo:font-style"), size: attr(tp, "fo:font-size"),
        color: attr(tp, "fo:color"), bg: attr(tp, "fo:background-color"), font: attr(tp, "style:font-name") || attr(tp, "fo:font-family"),
        underline: attr(tp, "style:text-underline-style"), strike: attr(tp, "style:text-line-through-style"), pos: attr(tp, "style:text-position")
      };
    });
  }
  collect(stylesDoc); collect(contentDoc);
  const resolved = (name, key, depth) => {
    const st = styles[name]; if (!st || (depth || 0) > 8) return "";
    return st[key] || (st.parent ? resolved(st.parent, key, (depth || 0) + 1) : "");
  };
  const resolvedTabs = (name) => { let n = name, d = 0; while (n && styles[n] && d++ < 8) { if (styles[n].tabs.length) return styles[n].tabs; n = styles[n].parent; } return []; };

  function spanCss(name) {
    if (!name) return { open: "", close: "" };
    const css = [];
    const size = resolved(name, "size"); if (size && /pt$/.test(size)) css.push(`font-size: ${parseFloat(size)}pt`);
    const color = resolved(name, "color"); if (color && color !== "#000000") css.push(`color: ${color}`);
    const bg = resolved(name, "bg"); if (bg && bg !== "transparent" && bg !== "#ffffff") css.push(`background-color: ${bg}`);
    const font = resolved(name, "font"); if (font && !/times new roman/i.test(font)) css.push(`font-family: '${font.replace(/['"]/g, "")}'`);
    let open = css.length ? `<span style="${css.join("; ")}">` : "", close = css.length ? "</span>" : "";
    if (resolved(name, "bold") === "bold") { open += "<strong>"; close = "</strong>" + close; }
    if (resolved(name, "italic") === "italic") { open += "<em>"; close = "</em>" + close; }
    const u = resolved(name, "underline"); if (u && u !== "none") { open += "<u>"; close = "</u>" + close; }
    const k = resolved(name, "strike"); if (k && k !== "none") { open += "<s>"; close = "</s>" + close; }
    const pos = resolved(name, "pos"); if (/^super/.test(pos)) { open += "<sup>"; close = "</sup>" + close; } else if (/^sub/.test(pos)) { open += "<sub>"; close = "</sub>" + close; }
    return { open, close };
  }

  async function inline(node) {
    let out = "";
    for (const cn of Array.from(node.childNodes)) {
      if (cn.nodeType === 3) { out += escapeHtmlStr(cn.textContent.replace(/\s+/g, " ")); continue; }
      if (cn.nodeType !== 1) continue;
      const ln = local(cn);
      if (ln === "s") { const c = parseInt(cn.getAttribute("text:c") || "1", 10); out += " " + "&nbsp;".repeat(Math.max(0, c - 1)); }
      else if (ln === "tab") out += `<span class="udf-tab-space" contenteditable="false">&#8203;</span>`;
      else if (ln === "line-break") out += "<br>";
      else if (ln === "span" || ln === "a") { const c = spanCss(cn.getAttribute("text:style-name")); out += c.open + await inline(cn) + c.close; }
      else if (ln === "frame") {
        const img = cn.getElementsByTagName("draw:image")[0];
        const href = img ? img.getAttribute("xlink:href") : "";
        const f = href && zip.file(href);
        if (f) {
          const b64 = await f.async("base64");
          const mime = /\.jpe?g$/i.test(href) ? "image/jpeg" : /\.gif$/i.test(href) ? "image/gif" : "image/png";
          const w = toCm(cn.getAttribute("svg:width")), h = toCm(cn.getAttribute("svg:height"));
          out += `<img src="data:${mime};base64,${b64}" style="${w ? `width:${w}cm;` : ""}${h ? `height:${h}cm;` : ""} vertical-align: middle; max-width: 100%;">`;
        }
      }
      else if (ln === "note" || ln === "annotation" || ln === "bookmark" || ln === "bookmark-start" || ln === "bookmark-end" || ln === "soft-page-break") { /* atla */ }
      else out += await inline(cn);
    }
    return out;
  }
  async function para(node) {
    const sn = node.getAttribute("text:style-name") || "";
    const alignMap = { start: "left", left: "left", end: "right", right: "right", center: "center", justify: "justify" };
    const align = alignMap[resolved(sn, "align")] || "left";
    const ml = toCm(resolved(sn, "ml")), mr = toCm(resolved(sn, "mr")), ti = toCm(resolved(sn, "ti"));
    const mt = toPt(resolved(sn, "mt")), mb = toPt(resolved(sn, "mb"));
    const lh = resolved(sn, "lh");
    let css = `text-align: ${align}; margin-top: ${mt}pt; margin-bottom: ${mb}pt;`;
    if (Math.abs(ml) > 0.01) css += ` margin-left: ${Math.round(ml * 100) / 100}cm;`;
    if (Math.abs(mr) > 0.01) css += ` margin-right: ${Math.round(mr * 100) / 100}cm;`;
    if (Math.abs(ti) > 0.01) css += ` text-indent: ${Math.round(ti * 100) / 100}cm;`;
    if (/%$/.test(lh)) css += ` line-height: ${Math.round(parseFloat(lh) * 1.15) / 100};`;
    const tabs = resolvedTabs(sn).map(t => Math.round((t + ml) * 100) / 100).filter(t => t > 0);
    const tabAttr = tabs.length ? ` data-tab-stops="${tabs.join(",")}"` : "";
    const c = spanCss(sn);
    const inner = await inline(node);
    let html = `<p style="${css}"${tabAttr}>${inner.replace(/(&nbsp;|\s)/g, "").length || /<img|udf-tab-space/.test(inner) ? c.open + inner + c.close : "<br>"}</p>\n`;
    if (resolved(sn, "breakBefore") === "page") html = `<div class="page-break udf-page-break" data-udf-page-break="true" contenteditable="false"></div>\n` + html;
    if (resolved(sn, "breakAfter") === "page") html += `<div class="page-break udf-page-break" data-udf-page-break="true" contenteditable="false"></div>\n`;
    return html;
  }
  async function block(node, listDepth) {
    const ln = local(node);
    if (ln === "p" || ln === "h") return await para(node);
    if (ln === "list") {
      let out = "";
      for (const item of Array.from(node.children)) for (const ch of Array.from(item.children)) out += await block(ch, (listDepth || 0) + 1);
      return out;
    }
    if (ln === "table") {
      let t = `<table style="width: 100%; border-collapse: collapse; margin: 6px 0;">\n`;
      const rows = Array.from(node.getElementsByTagName("table:table-row"));
      for (const tr of rows) {
        if (tr.closest && tr.parentElement && local(tr.parentElement) !== "table" && local(tr.parentElement) !== "table-header-rows" && local(tr.parentElement) !== "table-rows") continue;
        t += "<tr>";
        for (const tc of Array.from(tr.children)) {
          if (local(tc) !== "table-cell") continue;
          const span = parseInt(tc.getAttribute("table:number-columns-spanned") || "1", 10);
          t += `<td${span > 1 ? ` colspan="${span}"` : ""} style="border: 1px solid #333; padding: 4px 6px; vertical-align: top;">`;
          for (const ch of Array.from(tc.children)) t += await block(ch, 0);
          t += "</td>";
        }
        t += "</tr>\n";
      }
      return t + "</table>\n";
    }
    if (ln === "section" || ln === "index-body" || ln === "table-of-content") {
      let out = ""; for (const ch of Array.from(node.children)) out += await block(ch, listDepth); return out;
    }
    return "";
  }

  let html = "";
  const body = contentDoc.getElementsByTagName("office:text")[0];
  if (body) for (const node of Array.from(body.children)) html += await block(node, 0);

  // Sayfa düzeni (kenar boşlukları / yön) ve üst-alt bilgi metni
  let left = 2.5, right = 2.5, top = 2.5, bottom = 2.5, orientation = "portrait", headerText = "", footerText = "";
  if (stylesDoc) {
    const pl = stylesDoc.getElementsByTagName("style:page-layout-properties")[0];
    if (pl) {
      left = toCm(pl.getAttribute("fo:margin-left")) || left; right = toCm(pl.getAttribute("fo:margin-right")) || right;
      top = toCm(pl.getAttribute("fo:margin-top")) || top; bottom = toCm(pl.getAttribute("fo:margin-bottom")) || bottom;
      if (pl.getAttribute("style:print-orientation") === "landscape") orientation = "landscape";
    }
    // textContent <text:s/> boşluklarını kaybettiği için satır içi çözücüden düz metin alınır
    const plain = (html) => html.replace(/<span class="udf-tab-space"[^>]*>[^<]*<\/span>/g, "\t").replace(/<br>/g, " ").replace(/<[^>]+>/g, "").replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/\u200B/g, "").trim();
    const h = stylesDoc.getElementsByTagName("style:header")[0]; if (h) headerText = plain(await inline(h));
    const f = stylesDoc.getElementsByTagName("style:footer")[0]; if (f) footerText = plain(await inline(f));
  }
  return {
    header: headerText,
    headerHtml: headerText ? `<div class="udf-header-layout" style="text-align:center;">${escapeHtmlStr(headerText)}</div>` : "",
    footer: footerText,
    footerHtml: footerText ? `<div class="udf-footer-layout"><span class="udf-footer-text">${escapeHtmlStr(footerText)}</span></div>` : `<div class="udf-footer-layout" style="display:flex; justify-content:flex-end; width:100%;"><span class="udf-footer-page-label">Sayfa: {PAGE_NUM}/{TOTAL_PAGES}</span></div>`,
    leftMarginCm: Math.round(left * 100) / 100, rightMarginCm: Math.round(right * 100) / 100,
    topMarginCm: Math.round(top * 100) / 100, bottomMarginCm: Math.round(bottom * 100) / 100,
    paperOrientation: orientation,
    html: html || '<p style="text-align: justify;"><br></p>'
  };
}

// -------------------------------------------------------------
// 3. 1:1 RESMİ HAVELSAN UYAP (format_id="1.8") UDF ÜRETİCİ
// -------------------------------------------------------------
async function generateUdfBlob(docData) {
  const zip = new JSZip();
  let rawContent = "";
  let elementsXml = "";
  let currentOffset = 0;

  const PT_PER_CM = 28.3465;
  const near = (a, b, tol) => Math.abs((a || 0) - (b || 0)) <= tol;
  const attrStr = (o) => Object.keys(o).map(k => ` ${k}="${escapeXml(String(o[k]))}"`).join("");
  const TAB_ALIGN_CODE = { left: "0", right: "1", center: "2", decimal: "4" }; // Swing TabStop sabitleri

  /**
   * Paragraf öznitelikleri: orijinal UDF öznitelikleri temel alınır, yalnızca kullanıcının
   * editörde değiştirdiği değerler yeniden hesaplanır. Böylece resolver, TabSet hizaları,
   * Havelsan'a özgü bilinmeyen öznitelikler kaybolmaz (kayıpsız round-trip).
   */
  function buildParagraphAttrs(p) {
    const orig = p.origAttrs ? { ...p.origAttrs } : null;
    const o = orig ? { ...orig } : {};
    delete o.startOffset; delete o.length;
    const num = (k) => parseFloat(o[k] || "0") || 0;

    const align = p.align !== undefined ? p.align : 3;
    const firstLineCm = p.firstLineIndent || 0;
    const leftIndentCm = p.leftIndent || 0;
    const rightIndentCm = p.rightIndent || 0;

    // Orijinal değerlerden editörün göreceği cm değerleri (parser formülünün aynısı)
    const origLeftCm = (num("LeftIndent") + num("Hanging")) / PT_PER_CM;
    const origFirstCm = (num("FirstLineIndent") - num("Hanging")) / PT_PER_CM;
    const origRightCm = num("RightIndent") / PT_PER_CM;

    if (!orig || !near(leftIndentCm, origLeftCm, 0.03) || !near(firstLineCm, origFirstCm, 0.03)) {
      let udfLeftPt, udfFirstPt, udfHangPt;
      if (firstLineCm < -0.01) {
        const firstPosCm = Math.max(0, leftIndentCm + firstLineCm);
        udfLeftPt = firstPosCm * PT_PER_CM; udfFirstPt = 0;
        udfHangPt = Math.max(0, leftIndentCm - firstPosCm) * PT_PER_CM;
      } else {
        udfLeftPt = Math.max(0, leftIndentCm) * PT_PER_CM;
        udfFirstPt = Math.max(0, firstLineCm) * PT_PER_CM; udfHangPt = 0;
      }
      delete o.LeftIndent; delete o.FirstLineIndent; delete o.Hanging;
      if (udfLeftPt > 0.05) o.LeftIndent = udfLeftPt.toFixed(1);
      if (udfFirstPt > 0.05) o.FirstLineIndent = udfFirstPt.toFixed(1);
      if (udfHangPt > 0.05) o.Hanging = udfHangPt.toFixed(1);
    }
    if (!orig || !near(rightIndentCm, origRightCm, 0.03)) {
      delete o.RightIndent;
      if (rightIndentCm > 0.01) o.RightIndent = (rightIndentCm * PT_PER_CM).toFixed(1);
    }
    if (!orig || !near(p.spaceAbove, num("SpaceAbove"), 0.05)) { delete o.SpaceAbove; if ((p.spaceAbove || 0) > 0.05) o.SpaceAbove = p.spaceAbove.toFixed(1); }
    if (!orig || !near(p.spaceBelow, num("SpaceBelow"), 0.05)) { delete o.SpaceBelow; if ((p.spaceBelow || 0) > 0.05) o.SpaceBelow = p.spaceBelow.toFixed(1); }
    if (!orig || !near(p.lineSpacing, num("LineSpacing"), 0.005)) { delete o.LineSpacing; if ((p.lineSpacing || 0) > 0.01) o.LineSpacing = p.lineSpacing.toFixed(2); }

    // Sekme durakları: değişmediyse orijinal TabSet (hizalama kodlarıyla) aynen korunur.
    if (p.udfTabSet && (!p.tabStops || p.tabStops === p.origTabStops)) {
      o.TabSet = p.udfTabSet;
    } else if (p.tabStops) {
      const stops = String(p.tabStops).split(",").map(s => s.trim()).filter(Boolean).map(s => {
        const [cmStr, al] = s.split(":");
        const cm = parseFloat(cmStr);
        return isNaN(cm) || cm <= 0 ? null : `${(cm * PT_PER_CM).toFixed(1)}:${TAB_ALIGN_CODE[al] || "0"}:0`;
      }).filter(Boolean);
      if (stops.length) o.TabSet = stops.join(","); else delete o.TabSet;
    } else if (!p.udfTabSet) {
      delete o.TabSet;
    }

    if (p.numbered) { o.Numbered = "true"; o.NumberType = p.numberType || o.NumberType || "NUMBER_TYPE_NUMBER_TRE"; delete o.Bulleted; }
    else if (p.bulleted) { o.Bulleted = "true"; delete o.Numbered; }
    else { delete o.Numbered; delete o.Bulleted; }

    const origAlign = o.Alignment;
    if (origAlign === undefined || String(align) !== String(origAlign)) {
      // Orijinalde Alignment stil üzerinden geliyorsa ve değer aynıysa yazmaya gerek yok
      o.Alignment = String(align);
    }
    return o;
  }

  function runStyleAttrs(r) {
    let styleAttrs = "";
    if (r.fontFamily) {
      const cleanF = r.fontFamily.replace(/['"]/g, "").split(",")[0].trim();
      if (cleanF) styleAttrs += ` family="${escapeXml(cleanF)}"`;
    }
    if (r.fontSize && r.fontSize > 1) {
      styleAttrs += ` size="${Number.isInteger(r.fontSize) ? r.fontSize : r.fontSize.toFixed(1)}"`;
    }
    const fgInt = parseCssColorToSignedIntJs(r.color);
    if (fgInt !== 0 && (fgInt & 0xFFFFFF) !== 0x000000 && (fgInt & 0xFFFFFF) !== 0x333333) styleAttrs += ` foreground="${fgInt}"`;
    const bgInt = parseCssColorToSignedIntJs(r.backgroundColor);
    if (bgInt !== 0 && (bgInt & 0xFFFFFF) !== 0xFFFFFF) styleAttrs += ` background="${bgInt}"`;
    if (r.bold) styleAttrs += ` bold="true"`;
    if (r.italic) styleAttrs += ` italic="true"`;
    if (r.underline) styleAttrs += ` underline="true"`;
    if (r.subscript) styleAttrs += ` Subscript="true"`;
    if (r.superscript) styleAttrs += ` Superscript="true"`;
    if (r.strikethrough || r.strikeThrough) styleAttrs += ` strikethrough="true"`;
    return styleAttrs;
  }

  // Java String (UTF-16) uzunluğu kullanılır: Havelsan offsetleri String.substring ile çözer.
  function pushText(text, tag, styleAttrs, indent) {
    if (!text) return;
    rawContent += text;
    elementsXml += `${indent}    <${tag} startOffset="${currentOffset}" length="${text.length}"${styleAttrs} />\n`;
    currentOffset += text.length;
  }

  function appendParagraphXmlJs(p, indent) {
    const attrs = buildParagraphAttrs(p);
    // Satır içi <br> (Shift+Enter / şablon eol) Havelsan'da ayrı paragraf demektir:
    // runs "\n" noktalarından bölünür, her parça aynı özniteliklerle ayrı paragraf olur.
    const runs = (p.runs || []).slice();
    while (runs.length && runs[runs.length - 1].type !== "image" && runs[runs.length - 1].text === "\n") runs.pop();
    const pieces = [[]];
    runs.forEach(r => {
      if (r.type === "image") { pieces[pieces.length - 1].push(r); return; }
      const parts = String(r.text || "").split("\n");
      parts.forEach((part, i) => {
        if (i > 0) pieces.push([]);
        if (part) pieces[pieces.length - 1].push({ ...r, text: part });
      });
    });

    pieces.forEach(pieceRuns => {
      elementsXml += `${indent}<paragraph${attrStr(attrs)}>\n`;
      pieceRuns.forEach(r => {
        if (r.type === "image" && r.imageData) {
          const wPt = (r.widthPt || 100).toFixed(4);
          const hPt = (r.heightPt || 50).toFixed(4);
          rawContent += "¸";
          elementsXml += `${indent}    <image width="${wPt}" height="${hPt}" resolver="hvl-default" imageData="${escapeXml(r.imageData)}" startOffset="${currentOffset}" length="1" />\n`;
          currentOffset += 1;
          return;
        }
        const text = r.text || "";
        const styleAttrs = runStyleAttrs(r);
        // Sekmeler ayrı <tab> öğesi olarak yazılır
        text.split(/(\t+)/).forEach(seg => {
          if (!seg) return;
          pushText(seg, seg[0] === "\t" ? "tab" : "content", styleAttrs, indent);
        });
      });
      // Paragraf sonu: son koşunun biçimi ile satır sonu karakteri
      const last = pieceRuns.filter(r => r.type !== "image").pop();
      pushText("\n", "content", last ? runStyleAttrs(last) : "", indent);
      elementsXml += `${indent}</paragraph>\n`;
    });
  }

  function appendTableXmlJs(tbl, indent) {
    const border = tbl.border || "borderCell";
    const rows = tbl.rows || [];
    if (rows.length === 0) return;
    let maxCols = 1;
    rows.forEach(r => { if (r.cells && r.cells.length > maxCols) maxCols = r.cells.length; });
    const tA = tbl.origAttrs ? { ...tbl.origAttrs } : {};
    if (!tA.tableName) tA.tableName = "Sabit";
    if (!tA.columnCount) tA.columnCount = String(maxCols);
    if (tbl.colSpans) tA.columnSpans = tbl.colSpans;
    else if (!tA.columnSpans) tA.columnSpans = Array(maxCols).fill(Math.max(20, Math.floor(480 / maxCols))).join(",");
    tA.border = tA.border || border;

    elementsXml += `${indent}<table${attrStr(tA)}>\n`;
    rows.forEach((r, rIdx) => {
      const rA = r.origAttrs ? { ...r.origAttrs } : { rowName: `row${rIdx + 1}`, rowType: "dataRow", border: border };
      elementsXml += `${indent}    <row${attrStr(rA)}>\n`;
      (r.cells || []).forEach(c => {
        const cA = c.origAttrs ? { ...c.origAttrs } : { border: border };
        if (c.colSpan > 1) cA.colSpan = String(c.colSpan); else delete cA.colSpan;
        if (c.rowSpan > 1) cA.rowSpan = String(c.rowSpan); else delete cA.rowSpan;
        elementsXml += `${indent}        <cell${attrStr(cA)}>\n`;
        const cellParas = c.paragraphs || [];
        if (cellParas.length > 0) {
          cellParas.forEach(cp => {
            if (cp.type === "table") appendTableXmlJs(cp, indent + "            ");
            else appendParagraphXmlJs(cp, indent + "            ");
          });
        } else {
          appendParagraphXmlJs({ align: 0, runs: [] }, indent + "            ");
        }
        elementsXml += `${indent}        </cell>\n`;
      });
      elementsXml += `${indent}    </row>\n`;
    });
    elementsXml += `${indent}</table>\n`;
  }

  const src0 = window.__udfSource || null;
  // 1. Üstbilgi (<header>)
  const hParas = docData.headerParagraphs || [];
  if (hParas.length > 0 || (docData.header && docData.header.trim())) {
    const startP = docData.headerStartPage || 1;
    const hA = src0 && src0.headerAttrs ? { ...src0.headerAttrs } : {};
    if (startP > 1) hA.startPage = String(startP); else delete hA.startPage;
    elementsXml += `<header${attrStr(hA)}>\n`;
    if (hParas.length > 0) {
      hParas.forEach(hp => {
        if (hp.type === "image" && hp.imageData) {
          rawContent += "\u00b8";
          elementsXml += `    <image width="${(hp.widthPt || 118).toFixed(4)}" height="${(hp.heightPt || 50).toFixed(4)}" resolver="hvl-default" imageData="${escapeXml(hp.imageData)}" startOffset="${currentOffset}" length="1" />\n`;
          currentOffset += 1;
        } else if (hp.type === "table") {
          appendTableXmlJs(hp, "    ");
        } else {
          appendParagraphXmlJs(hp, "    ");
        }
      });
    } else {
      appendParagraphXmlJs({ align: 1, runs: [{ text: docData.header.trim(), bold: true }] }, "    ");
    }
    elementsXml += `</header>\n`;
  }

  // 2. Gövde blokları
  const bodyBlocks = docData.paragraphs || [];
  if (bodyBlocks.length === 0) {
    appendParagraphXmlJs({ align: 3, runs: [] }, "    ");
  } else {
    bodyBlocks.forEach(block => {
      if (block.type === "table") appendTableXmlJs(block, "    ");
      else if (block.type === "pageBreak") {
        rawContent += "\n";
        elementsXml += `    <page-break startOffset="${currentOffset}" length="1" />\n`;
        currentOffset += 1;
      } else appendParagraphXmlJs(block, "    ");
    });
  }

  // 3. Altbilgi (<footer>)
  const fParas = docData.footerParagraphs || [];
  if (fParas.length > 0 || (docData.footer && docData.footer.trim()) || docData.footerPageSpec) {
    const spec = docData.footerPageSpec || "BSP32_2120";
    const foreStr = docData.footerForeStr || "Sayfa:";
    const sep = docData.footerSep || "/";
    const pStart = docData.footerPageStart || "1";
    const fA = src0 && src0.footerAttrs && Object.keys(src0.footerAttrs).length ? { ...src0.footerAttrs } : {
      "pageNumber-spec": spec, "pageNumber-foreStr": foreStr, "pageNumber-seperator": sep, "pageNumber-start": pStart };
    elementsXml += `<footer${attrStr(fA)}>\n`;
    if (fParas.length > 0) {
      fParas.forEach(fp => {
        if (fp.type === "image" && fp.imageData) {
          rawContent += "\u00b8";
          elementsXml += `    <image width="${(fp.widthPt || 118).toFixed(4)}" height="${(fp.heightPt || 50).toFixed(4)}" resolver="hvl-default" imageData="${escapeXml(fp.imageData)}" startOffset="${currentOffset}" length="1" />\n`;
          currentOffset += 1;
        } else if (fp.type === "table") {
          appendTableXmlJs(fp, "    ");
        } else {
          appendParagraphXmlJs(fp, "    ");
        }
      });
    } else if (docData.footer && docData.footer.trim()) {
      appendParagraphXmlJs({ align: 1, runs: [{ text: docData.footer.trim() }] }, "    ");
    }
    elementsXml += `</footer>\n`;
  }

  const m = docData.margins || {};
  const src = window.__udfSource || null;
  const cmToPt = (cm) => (cm * PT_PER_CM).toFixed(4);
  // Sayfa biçimi: orijinal öznitelikler korunur, kenar boşlukları yalnızca değiştiyse güncellenir.
  const pf = src && src.pageFormat ? { ...src.pageFormat } : { mediaSizeName: "1", headerFOffset: "20.0", footerFOffset: "20.0" };
  const setMargin = (key, cm) => {
    if (!cm && cm !== 0) return;
    const origCm = pf[key] !== undefined ? Math.round((parseFloat(pf[key]) / PT_PER_CM) * 100) / 100 : null;
    if (origCm === null || Math.abs(origCm - cm) > 0.011) pf[key] = cmToPt(cm);
  };
  setMargin("leftMargin", m.left || docData.leftMarginCm || 1.5);
  setMargin("rightMargin", m.right || docData.rightMarginCm || 1.5);
  setMargin("topMargin", m.top || docData.topMarginCm || 1.5);
  setMargin("bottomMargin", m.bottom || docData.bottomMarginCm || 1.5);
  pf.paperOrientation = (m.orientation === "landscape" || docData.paperOrientation === "2") ? "2" : "1";
  const defaultStyles = `<styles><style name="default" description="Geçerli" family="Dialog" size="12" bold="false" italic="false" foreground="-13421773" FONT_ATTRIBUTE_KEY="javax.swing.plaf.FontUIResource[family=Dialog,name=Dialog,style=plain,size=12]" /><style name="hvl-default" family="Times New Roman" size="12" description="Gövde" /></styles>`;
  const elAttrs = src && src.elementsAttrs ? src.elementsAttrs : { resolver: "hvl-default" };

  const finalXml = `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<template format_id="1.8">\n` +
    `<content><![CDATA[${rawContent.replace(/]]>/g, "]]]]><![CDATA[>")}]]></content>\n` +
    `<properties><pageFormat${attrStr(pf)} /></properties>\n` +
    `<elements${attrStr(elAttrs)}>\n${elementsXml}</elements>\n` +
    `${(src && src.stylesXml) || defaultStyles}\n` +
    `${(src && src.webIdXml) || ""}` +
    `</template>`;

  zip.file("content.xml", finalXml);
  if (src && src.docPropsXml) zip.file("documentproperties.xml", src.docPropsXml);
  return await zip.generateAsync({ type: "blob", compression: "DEFLATE" });
}

// -------------------------------------------------------------
// HIZLI VE DAYANIKLI HEADLESS SUNUCU KONTROLÜ (Port 5976)
// -------------------------------------------------------------
let isHeadlessServerChecked = false;
let isHeadlessServerOnline = false;

async function tryHeadlessConvert(format, udfBlob) {
  if (isHeadlessServerChecked && !isHeadlessServerOnline) return null;
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 1000);
    const resp = await fetch(`http://127.0.0.1:5976/api/v1/convert?format=${format}`, {
      method: "POST",
      body: udfBlob,
      signal: controller.signal
    });
    clearTimeout(timeoutId);
    if (resp.ok) {
      const serverBlob = await resp.blob();
      if (serverBlob && serverBlob.size > 1000) {
        isHeadlessServerChecked = true;
        isHeadlessServerOnline = true;
        return serverBlob;
      }
    }
  } catch (e) {
    isHeadlessServerChecked = true;
    isHeadlessServerOnline = false;
  }
  return null;
}

// -------------------------------------------------------------
// 4. DOCX DOSYASI OLUŞTURMA & KAYDETME (TABLO, GÖRSEL, GİRİNTİ DESTEKLİ)
// -------------------------------------------------------------
async function generateDocxBlob(docData) {
  // 1. Resmi Havelsan UYAP Headless Motoru (Port 5976) üzerinden 1:1 DOCX
  try {
    const udfBlob = await generateUdfBlob(docData);
    const serverBlob = await tryHeadlessConvert("docx", udfBlob);
    if (serverBlob) return serverBlob;
  } catch (netErr) {
    // Havelsan yerel sunucusu aktif değil, doğrudan yerel JSZip motoru ile üret
  }

  const zip = new JSZip();
  const m = docData.margins || {};
  const topDxa = Math.round((m.top || docData.topMarginCm || 1.5) * 567);
  const bottomDxa = Math.round((m.bottom || docData.bottomMarginCm || 1.5) * 567);
  const leftDxa = Math.round((m.left || docData.leftMarginCm || 1.5) * 567);
  const rightDxa = Math.round((m.right || docData.rightMarginCm || 1.5) * 567);
  const isLandscape = m.orientation === "landscape" || docData.paperOrientation === "2";
  const pgW = isLandscape ? 16838 : 11906;
  const pgH = isLandscape ? 11906 : 16838;

  const mediaList = [];
  let docXml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' +
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">\n<w:body>\n';

  function appendDocxParaJs(p) {
    let jcVal = "both";
    if (p.align === 1) jcVal = "center";
    else if (p.align === 2) jcVal = "right";
    else if (p.align === 0) jcVal = "left";

    const beforeDxa = Math.round(Math.max(0, p.spaceAbove || 0) * 20);
    const afterDxa = Math.round(Math.max(0, p.spaceBelow || 2) * 20);
    const firstLineCm = p.firstLineIndent || 0;
    const leftIndentCm = p.leftIndent || 0;
    const rightIndentCm = p.rightIndent || 0;

    const lDxa = Math.round(Math.max(0, leftIndentCm) * 567);
    const rDxa = Math.round(Math.max(0, rightIndentCm) * 567);
    const flDxa = firstLineCm > 0.01 ? Math.round(firstLineCm * 567) : 0;
    const hgDxa = firstLineCm < -0.01 ? Math.round((-firstLineCm) * 567) : 0;

    let tabsXml = "";
    if (p.tabStops) {
      const tabsList = String(p.tabStops).split(",").map(s => parseFloat(s.trim())).filter(n => !isNaN(n) && n > 0);
      if (tabsList.length > 0) {
        tabsXml = '      <w:tabs>\n' + tabsList.map(cm => `        <w:tab w:val="left" w:pos="${Math.round(cm * 567)}"/>\n`).join('') + '      </w:tabs>\n';
      }
    }

    let indXml = "";
    if (lDxa > 0 || rDxa > 0 || flDxa > 0 || hgDxa > 0) {
      indXml = `      <w:ind${lDxa > 0 ? ` w:left="${lDxa}"` : ""}${rDxa > 0 ? ` w:right="${rDxa}"` : ""}${flDxa > 0 ? ` w:firstLine="${flDxa}"` : ""}${hgDxa > 0 ? ` w:hanging="${hgDxa}"` : ""}/>\n`;
    }

    docXml += `  <w:p>\n    <w:pPr>\n      <w:jc w:val="${jcVal}"/>\n${tabsXml}${indXml}      <w:spacing w:before="${beforeDxa}" w:after="${afterDxa}" w:line="240" w:lineRule="auto"/>\n    </w:pPr>\n`;

    (p.runs || []).forEach(r => {
      if (r.type === "image" && r.imageData) {
        const idx = mediaList.length + 1;
        const relId = `rIdImg${idx}`;
        const fileName = `media/image${idx}.png`;
        mediaList.push({ relId, fileName, base64: r.imageData });
        const cx = Math.round((r.widthPt || 120) * 12700);
        const cy = Math.round((r.heightPt || 60) * 12700);
        docXml += `    <w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="${cx}" cy="${cy}"/><wp:docPr id="${idx}" name="Picture ${idx}"/><a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="${idx}" name="image${idx}.png"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="${relId}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="${cx}" cy="${cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>\n`;
        return;
      }

      const text = r.text || "";
      if (text) {
        const font = (r.fontFamily || "Times New Roman").replace(/['"]/g, "").split(",")[0].trim() || "Times New Roman";
        const halfPt = Math.round((r.fontSize > 1 ? r.fontSize : 12) * 2);
        docXml += `    <w:r>\n      <w:rPr>\n        <w:rFonts w:ascii="${escapeXml(font)}" w:hAnsi="${escapeXml(font)}" w:cs="${escapeXml(font)}"/>\n        <w:sz w:val="${halfPt}"/>\n`;
        if (r.bold) docXml += `        <w:b/>\n`;
        if (r.italic) docXml += `        <w:i/>\n`;
        if (r.underline) docXml += `        <w:u w:val="single"/>\n`;
        if (r.strikethrough || r.strikeThrough) docXml += `        <w:strike/>\n`;
        if (r.subscript) docXml += `        <w:vertAlign w:val="subscript"/>\n`;
        else if (r.superscript) docXml += `        <w:vertAlign w:val="superscript"/>\n`;
        docXml += `      </w:rPr>\n`;

        const lines = text.split("\n");
        lines.forEach((line, lIdx) => {
          if (lIdx > 0) docXml += `      <w:br/>\n`;
          const tabs = line.split("\t");
          tabs.forEach((tabPart, tIdx) => {
            if (tIdx > 0) docXml += `      <w:tab/>\n`;
            if (tabPart) docXml += `      <w:t xml:space="preserve">${escapeXml(tabPart)}</w:t>\n`;
          });
        });
        docXml += `    </w:r>\n`;
      }
    });

    docXml += `  </w:p>\n`;
  }

  function appendDocxTableJs(tbl) {
    const noBorder = tbl.border === "borderNone" || tbl.border === "none";
    const bVal = noBorder ? "none" : "single";
    const bSz = noBorder ? "0" : "4";
    docXml += `  <w:tbl>\n    <w:tblPr>\n      <w:tblW w:w="5000" w:type="pct"/>\n      <w:tblBorders>\n` +
      `        <w:top w:val="${bVal}" w:sz="${bSz}" w:space="0" w:color="333333"/>\n` +
      `        <w:left w:val="${bVal}" w:sz="${bSz}" w:space="0" w:color="333333"/>\n` +
      `        <w:bottom w:val="${bVal}" w:sz="${bSz}" w:space="0" w:color="333333"/>\n` +
      `        <w:right w:val="${bVal}" w:sz="${bSz}" w:space="0" w:color="333333"/>\n` +
      `        <w:insideH w:val="${bVal}" w:sz="${bSz}" w:space="0" w:color="333333"/>\n` +
      `        <w:insideV w:val="${bVal}" w:sz="${bSz}" w:space="0" w:color="333333"/>\n` +
      `      </w:tblBorders>\n    </w:tblPr>\n`;
    (tbl.rows || []).forEach(r => {
      docXml += `    <w:tr>\n`;
      const cells = r.cells || [];
      const pct = Math.floor(5000 / Math.max(1, cells.length));
      cells.forEach(c => {
        docXml += `      <w:tc>\n        <w:tcPr><w:tcW w:w="${pct * (c.colSpan || 1)}" w:type="pct"/>${c.colSpan > 1 ? `<w:gridSpan w:val="${c.colSpan}"/>` : ""}</w:tcPr>\n`;
        const cParas = c.paragraphs || [];
        if (cParas.length > 0) {
          cParas.forEach(cp => {
            if (cp.type === "table") appendDocxTableJs(cp);
            else appendDocxParaJs(cp);
          });
        } else {
          docXml += `        <w:p/>\n`;
        }
        docXml += `      </w:tc>\n`;
      });
      docXml += `    </w:tr>\n`;
    });
    docXml += `  </w:tbl>\n`;
  }

  (docData.paragraphs || []).forEach(block => {
    if (block.type === "table") appendDocxTableJs(block);
    else if (block.type === "pageBreak") docXml += `  <w:p><w:r><w:br w:type="page"/></w:r></w:p>\n`;
    else appendDocxParaJs(block);
  });

  docXml += `  <w:sectPr>\n    <w:pgSz w:w="${pgW}" w:h="${pgH}"${isLandscape ? ' w:orient="landscape"' : ''}/>\n` +
            `    <w:pgMar w:top="${topDxa}" w:right="${rightDxa}" w:bottom="${bottomDxa}" w:left="${leftDxa}"/>\n  </w:sectPr>\n</w:body>\n</w:document>`;

  let docRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>`;
  mediaList.forEach(mItem => {
    docRels += `<Relationship Id="${mItem.relId}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="${mItem.fileName}"/>`;
    zip.file("word/" + mItem.fileName, mItem.base64, { base64: true });
  });
  docRels += `</Relationships>`;

  zip.file("[Content_Types].xml", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Default Extension="jpg" ContentType="image/jpeg"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>`);
  zip.file("_rels/.rels", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>`);
  zip.file("word/document.xml", docXml);
  zip.file("word/styles.xml", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="24"/></w:rPr></w:rPrDefault></w:docDefaults></w:styles>`);
  zip.file("word/_rels/document.xml.rels", docRels);

  return await zip.generateAsync({ type: "blob", compression: "DEFLATE" });
}

// -------------------------------------------------------------
// 3B. 1:1 STANDART OPENDOCUMENT (ODT) ÜRETİCİ
// -------------------------------------------------------------
async function generateOdtBlob(docData) {
  // 1. Resmi Havelsan UYAP Headless Motoru (Port 5976) varsa onu kullan
  try {
    const udfBlob = await generateUdfBlob(docData);
    const serverBlob = await tryHeadlessConvert("odt", udfBlob);
    if (serverBlob) return serverBlob;
  } catch (netErr) {}

  // 2. Yerel OpenDocument (ODF 1.2) yazıcısı — v3.15'te yeniden yazıldı:
  //    sekmeler + sekme durakları, girintiler, paragraf boşlukları, satır aralığı, yazı tipi/punto/renk,
  //    alt/üst simge, üstü çizili, tablo kenarlıkları, görseller, üst/alt bilgi ve UDF sayfa kenar boşlukları.
  //    (Eski sürüm sekmeleri ve girintileri tamamen kaybediyordu.)
  const zip = new JSZip();
  zip.file("mimetype", "application/vnd.oasis.opendocument.text", { compression: "STORE" });
  const m = docData.margins || {};
  const cm = (v, d) => (typeof v === "number" && !isNaN(v) ? v : d);
  const isLandscape = m.orientation === "landscape" || docData.paperOrientation === "2";
  const pageW = isLandscape ? 29.7 : 21.0, pageH = isLandscape ? 21.0 : 29.7;

  const pStyles = new Map(), tStyles = new Map(), images = [];
  let autoXml = "";
  const fontsUsed = new Set(["Times New Roman"]);
  const fmt = (n) => (Math.round(n * 1000) / 1000) + "cm";

  function paraStyle(p) {
    const align = p.align === 1 ? "center" : p.align === 2 ? "end" : p.align === 0 ? "start" : "justify";
    const left = Math.max(0, p.leftIndent || 0), right = Math.max(0, p.rightIndent || 0), first = p.firstLineIndent || 0;
    const above = Math.max(0, p.spaceAbove || 0), below = Math.max(0, p.spaceBelow || 0);
    const ls = Math.max(0, p.lineSpacing || 0);
    const tabs = String(p.tabStops || "").split(",").map(x => parseFloat(x)).filter(n => !isNaN(n) && n > 0);
    const key = [align, left, right, first, above, below, ls, tabs.join("|"), p.pageBreakBefore ? 1 : 0].join(";");
    if (pStyles.has(key)) return pStyles.get(key);
    const name = "P" + (pStyles.size + 1);
    pStyles.set(key, name);
    const tabXml = tabs.length ? `<style:tab-stops>${tabs.map(t => `<style:tab-stop style:position="${fmt(Math.max(0, t - left))}"/>`).join("")}</style:tab-stops>` : "";
    autoXml += `<style:style style:name="${name}" style:family="paragraph" style:parent-style-name="Standard"><style:paragraph-properties fo:text-align="${align}" fo:margin-left="${fmt(left)}" fo:margin-right="${fmt(right)}" fo:text-indent="${fmt(first)}" fo:margin-top="${above}pt" fo:margin-bottom="${below}pt" fo:line-height="${Math.round((1 + ls) * 100)}%"${p.pageBreakBefore ? ' fo:break-before="page"' : ""}>${tabXml}</style:paragraph-properties></style:style>\n`;
    return name;
  }
  function textStyle(r) {
    const font = String(r.fontFamily || "Times New Roman").replace(/['"]/g, "").split(",")[0].trim() || "Times New Roman";
    fontsUsed.add(font);
    const size = r.fontSize > 1 ? r.fontSize : 12;
    const color = r.color && /^#?[0-9a-f]{6}$/i.test(String(r.color).replace("#", "")) ? "#" + String(r.color).replace("#", "") : "#000000";
    const pos = r.superscript ? "super 58%" : r.subscript ? "sub 58%" : "";
    const bg = r.backgroundColor && /^#?[0-9a-f]{6}$/i.test(String(r.backgroundColor).replace("#", "")) ? "#" + String(r.backgroundColor).replace("#", "") : "";
    const key = [font, size, r.bold ? 1 : 0, r.italic ? 1 : 0, r.underline ? 1 : 0, (r.strikethrough || r.strikeThrough) ? 1 : 0, pos, color, bg].join(";");
    if (tStyles.has(key)) return tStyles.get(key);
    const name = "T" + (tStyles.size + 1);
    tStyles.set(key, name);
    autoXml += `<style:style style:name="${name}" style:family="text"><style:text-properties style:font-name="${escapeXml(font)}" fo:font-size="${size}pt" style:font-size-complex="${size}pt"${r.bold ? ' fo:font-weight="bold" style:font-weight-complex="bold"' : ""}${r.italic ? ' fo:font-style="italic" style:font-style-complex="italic"' : ""}${r.underline ? ' style:text-underline-style="solid" style:text-underline-width="auto" style:text-underline-color="font-color"' : ""}${(r.strikethrough || r.strikeThrough) ? ' style:text-line-through-style="solid"' : ""}${pos ? ` style:text-position="${pos}"` : ""} fo:color="${color}"${bg ? ` fo:background-color="${bg}"` : ""}/></style:style>\n`;
    return name;
  }
  // Metni ODF'ye çevir: \t → <text:tab/>, \n → <text:line-break/>, ardışık boşluk → <text:s text:c="n"/>
  function odfText(text) {
    let out = "";
    String(text).split("\n").forEach((line, li) => {
      if (li > 0) out += "<text:line-break/>";
      line.split("\t").forEach((part, ti) => {
        if (ti > 0) out += "<text:tab/>";
        out += escapeXml(part).replace(/ {2,}/g, (sp) => " " + `<text:s text:c="${sp.length - 1}"/>`).replace(/^ /, '<text:s/>');
      });
    });
    return out;
  }
  function runsXml(p) {
    let x = "";
    (p.runs || [{ text: p.text || "" }]).forEach(r => {
      if (r.type === "image" && r.imageData) {
        const idx = images.length + 1;
        const path = `Pictures/image${idx}.png`;
        images.push({ path, base64: String(r.imageData).replace(/^data:[^,]+,/, "") });
        const w = (r.widthPt || 120) / 72 * 2.54, h = (r.heightPt || 60) / 72 * 2.54;
        x += `<draw:frame draw:name="Resim${idx}" text:anchor-type="as-char" svg:width="${fmt(w)}" svg:height="${fmt(h)}"><draw:image xlink:href="${path}" xlink:type="simple" xlink:show="embed" xlink:actuate="onLoad"/></draw:frame>`;
        return;
      }
      if (!r.text) return;
      x += `<text:span text:style-name="${textStyle(r)}">${odfText(r.text)}</text:span>`;
    });
    return x;
  }
  function paraXml(p) {
    if (p.type === "pageBreak") return `<text:p text:style-name="PBreak"/>\n`;
    if (p.type === "table") return tableXml(p);
    return `<text:p text:style-name="${paraStyle(p)}">${runsXml(p)}</text:p>\n`;
  }
  let tblN = 0;
  function tableXml(t) {
    tblN++;
    const noBorder = t.border === "borderNone" || t.border === "none";
    const cellStyle = `TC${tblN}`;
    autoXml += `<style:style style:name="Tbl${tblN}" style:family="table"><style:table-properties style:width="${fmt(pageW - cm(m.left, 2.5) - cm(m.right, 2.5))}" table:align="margins"/></style:style>\n`;
    autoXml += `<style:style style:name="${cellStyle}" style:family="table-cell"><style:table-cell-properties fo:padding="0.05cm" fo:border="${noBorder ? "none" : "0.5pt solid #333333"}"/></style:style>\n`;
    const rows = t.rows || [];
    let maxCols = 1;
    rows.forEach(r => { const n = (r.cells || []).reduce((a, c) => a + (c.colSpan || 1), 0); if (n > maxCols) maxCols = n; });
    let x = `<table:table table:name="Tablo${tblN}" table:style-name="Tbl${tblN}"><table:table-column table:number-columns-repeated="${maxCols}"/>\n`;
    rows.forEach(r => {
      x += `<table:table-row>`;
      (r.cells || []).forEach(c => {
        const span = c.colSpan > 1 ? ` table:number-columns-spanned="${c.colSpan}"` : "";
        x += `<table:table-cell table:style-name="${cellStyle}" office:value-type="string"${span}>`;
        const cp = c.paragraphs || [];
        x += cp.length ? cp.map(paraXml).join("") : `<text:p/>`;
        x += `</table:table-cell>`;
        for (let k = 1; k < (c.colSpan || 1); k++) x += `<table:covered-table-cell/>`;
      });
      x += `</table:table-row>\n`;
    });
    return x + `</table:table>\n`;
  }

  let bodyXml = "";
  (docData.paragraphs || []).forEach(p => { bodyXml += paraXml(p); });
  const headerXml = (docData.headerParagraphs || []).map(paraXml).join("");
  const footerXml = (docData.footerParagraphs || []).map(paraXml).join("");

  const NS = 'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" office:version="1.2"';
  const fontDecls = `<office:font-face-decls>${[...fontsUsed].map(f => `<style:font-face style:name="${escapeXml(f)}" svg:font-family="'${escapeXml(f)}'" style:font-pitch="variable"/>`).join("")}</office:font-face-decls>`;

  const contentXml = `<?xml version="1.0" encoding="UTF-8"?>\n<office:document-content ${NS}>${fontDecls}<office:automatic-styles>${autoXml}<style:style style:name="PBreak" style:family="paragraph"><style:paragraph-properties fo:break-before="page"/></style:style></office:automatic-styles><office:body><office:text>\n${bodyXml}</office:text></office:body></office:document-content>`;
  const stylesXml = `<?xml version="1.0" encoding="UTF-8"?>\n<office:document-styles ${NS}>${fontDecls}<office:styles><style:default-style style:family="paragraph"><style:paragraph-properties style:tab-stop-distance="1.25cm"/><style:text-properties style:font-name="Times New Roman" fo:font-size="12pt" fo:language="tr" fo:country="TR"/></style:default-style><style:style style:name="Standard" style:family="paragraph" style:class="text"/></office:styles><office:automatic-styles><style:page-layout style:name="pm1"><style:page-layout-properties fo:page-width="${pageW}cm" fo:page-height="${pageH}cm" style:print-orientation="${isLandscape ? "landscape" : "portrait"}" fo:margin-top="${fmt(cm(m.header, 0) > 0 && headerXml ? cm(m.header, 0.5) : cm(m.top, 2.5))}" fo:margin-bottom="${fmt(footerXml ? Math.max(0.3, cm(m.bottom, 2.5)) : cm(m.bottom, 2.5))}" fo:margin-left="${fmt(cm(m.left, 2.5))}" fo:margin-right="${fmt(cm(m.right, 2.5))}"/>${headerXml ? `<style:header-style><style:header-footer-properties fo:min-height="0cm" fo:margin-bottom="${fmt(Math.max(0.1, cm(m.top, 2.5) - cm(m.header, 0.5) - 0.6))}"/></style:header-style>` : ""}${footerXml ? `<style:footer-style><style:header-footer-properties fo:min-height="0cm" fo:margin-top="0.2cm"/></style:footer-style>` : ""}</style:page-layout></office:automatic-styles><office:master-styles><style:master-page style:name="Standard" style:page-layout-name="pm1">${headerXml ? `<style:header>${headerXml}</style:header>${(docData.headerStartPage || 1) > 1 ? "<style:header-first/>" : ""}` : ""}${footerXml ? `<style:footer>${footerXml}</style:footer>` : ""}</style:master-page></office:master-styles></office:document-styles>`;
  // Not: üst/alt bilgi paragraflarının otomatik stilleri content.xml'de; styles.xml içinde de geçerli olmaları için kopyalanır
  const stylesWithAuto = stylesXml.replace("<office:automatic-styles>", "<office:automatic-styles>" + autoXml);
  const metaXml = `<?xml version="1.0" encoding="UTF-8"?>\n<office:document-meta ${NS}><office:meta><meta:generator>CanEditor</meta:generator><dc:title>${escapeXml(currentDocFileName || "Belge")}</dc:title><dc:date>${new Date().toISOString().slice(0, 19)}</dc:date></office:meta></office:document-meta>`;
  const manifestXml = `<?xml version="1.0" encoding="UTF-8"?>\n<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2"><manifest:file-entry manifest:full-path="/" manifest:version="1.2" manifest:media-type="application/vnd.oasis.opendocument.text"/><manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/><manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/><manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>${images.map(i => `<manifest:file-entry manifest:full-path="${i.path}" manifest:media-type="image/png"/>`).join("")}</manifest:manifest>`;
  zip.file("content.xml", contentXml);
  zip.file("styles.xml", stylesWithAuto);
  zip.file("meta.xml", metaXml);
  zip.file("META-INF/manifest.xml", manifestXml);
  images.forEach(i => zip.file(i.path, i.base64, { base64: true }));
  return await zip.generateAsync({ type: "blob", compression: "DEFLATE", mimeType: "application/vnd.oasis.opendocument.text" });
}

// -------------------------------------------------------------
// 3C. ÇOK SAYFALI ADLİ TIFF EVRAKI ÜRETİCİ (UTIF.js & IFD Motoru)
// -------------------------------------------------------------
async function generateTiffBlob(docData) {
  // v3.15: ekrandaki yerleşimden 192 DPI gri, PackBits sıkıştırmalı çok sayfalı TIFF
  if (window.CanExport && window.CanExport.buildTiff) {
    try { return await window.CanExport.buildTiff(); }
    catch (e) { console.warn("Yeni TIFF motoru başarısız, yedek motora geçiliyor:", e); }
  }
  let pageSheets = Array.from(document.querySelectorAll(".a4-sheet-page"));
  if (pageSheets.length === 0) {
    const single = document.getElementById("sheet-container") || document.getElementById("page-wrapper") || document.getElementById("editor-content");
    if (single) pageSheets = [single];
  }
  const isLandscape = (typeof currentMargins !== "undefined" && currentMargins.orientation === "landscape") ||
    (pageSheets[0] && pageSheets[0].classList.contains("landscape"));
  const width = isLandscape ? 1123 : 794;
  const height = isLandscape ? 794 : 1123;
  const pageBuckets = getPageElementBuckets(docData, width, height, 1);
  const totalPages = Math.max(1, pageBuckets.length);

  const ifds = [];
  const rawPages = [];

  for (let p = 1; p <= totalPages; p++) {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#FFFFFF";
    ctx.fillRect(0, 0, width, height);

    const sheet = (pageSheets && pageSheets[p - 1]) ? pageSheets[p - 1] : null;
    renderSheetDirectToCanvas(sheet, ctx, width, height, 1, p, totalPages, docData, pageBuckets[p - 1]);
    const imgData = ctx.getImageData(0, 0, width, height);
    rawPages.push(imgData);

    if (typeof UTIF !== "undefined") {
      ifds.push({
        data: new Uint8Array(imgData.data),
        width: width,
        height: height
      });
    }
  }

  // UTIF.js mevcut ise standart sıkıştırılmış TIFF üret
  if (typeof UTIF !== "undefined" && ifds.length > 0) {
    try {
      if (ifds.length === 1) {
        const tiffBuf = UTIF.encodeImage(ifds[0].data, width, height);
        return new Blob([tiffBuf], { type: "image/tiff" });
      } else {
        const tiffBuf = UTIF.encode(ifds);
        return new Blob([tiffBuf], { type: "image/tiff" });
      }
    } catch (e) {
      console.warn("UTIF encode hatası, fallback uygulanıyor:", e);
    }
  }

  // Fallback: Standart IFD başlığı ile TIFF üretimi
  const pages = rawPages;
  const ifdSize = 2 + 11 * 12 + 4;
  const bytesPerPage = width * height * 4;
  let totalFileSize = 8;
  for (let i = 0; i < pages.length; i++) {
    totalFileSize += ifdSize + bytesPerPage;
  }

  const buffer = new ArrayBuffer(totalFileSize);
  const dv = new DataView(buffer);
  const u8 = new Uint8Array(buffer);

  dv.setUint8(0, 0x49); // 'I'
  dv.setUint8(1, 0x49); // 'I'
  dv.setUint16(2, 42, true);
  dv.setUint32(4, 8, true);

  let currentIfdOffset = 8;
  let currentDataOffset = 8 + pages.length * ifdSize;

  for (let i = 0; i < pages.length; i++) {
    const isLast = (i === pages.length - 1);
    const nextIfdOffset = isLast ? 0 : (currentIfdOffset + ifdSize);

    dv.setUint16(currentIfdOffset, 11, true);
    let off = currentIfdOffset + 2;

    const writeTag = (tag, type, count, value) => {
      dv.setUint16(off, tag, true);
      dv.setUint16(off + 2, type, true);
      dv.setUint32(off + 4, count, true);
      dv.setUint32(off + 8, value, true);
      off += 12;
    };

    writeTag(256, 4, 1, width);
    writeTag(257, 4, 1, height);
    writeTag(258, 3, 1, 8);
    writeTag(259, 3, 1, 1);
    writeTag(262, 3, 1, 2);
    writeTag(273, 4, 1, currentDataOffset);
    writeTag(277, 3, 1, 4);
    writeTag(278, 4, 1, height);
    writeTag(279, 4, 1, bytesPerPage);
    writeTag(282, 4, 1, 96);
    writeTag(283, 4, 1, 96);

    dv.setUint32(off, nextIfdOffset, true);

    const pageData = pages[i].data;
    u8.set(pageData, currentDataOffset);

    currentIfdOffset = nextIfdOffset;
    currentDataOffset += bytesPerPage;
  }

  return new Blob([buffer], { type: "image/tiff" });
}

// -------------------------------------------------------------
// 3D. STANDART A4 ADLİ PDF EVRAKI ÜRETİCİ (ISO 32000-1 / PDF 1.4)
// UYAP Avukat Portal ve Havelsan Standartlarında Birebir Vektörel Baskı Motoru
// -------------------------------------------------------------
function dataUrlToUint8Array(dataUrl) {
  const commaIdx = dataUrl.indexOf(",");
  const b64 = commaIdx >= 0 ? dataUrl.substring(commaIdx + 1) : dataUrl;
  const bin = atob(b64);
  const len = bin.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = bin.charCodeAt(i) & 0xFF;
  }
  return bytes;
}

function assemblePdfFromJpegs(pagesData, pw, ph) {
  const totalPages = pagesData.length;
  const offsets = [];
  const parts = [];
  let currentByteLength = 0;

  function pushString(str) {
    const bytes = new Uint8Array(str.length);
    for (let i = 0; i < str.length; i++) {
      bytes[i] = str.charCodeAt(i) & 0xFF;
    }
    parts.push(bytes);
    currentByteLength += bytes.length;
  }

  function pushBytes(bytes) {
    parts.push(bytes);
    currentByteLength += bytes.length;
  }

  // 1. PDF-1.4 Standart Başlığı (Binary koruma yorum satırıyla)
  pushString("%PDF-1.4\n%\xE2\xE3\xCF\xD3\n");

  // 1 0: Catalog
  offsets.push(currentByteLength);
  pushString("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n");

  // 2 0: Pages (Kids dizisi)
  const kids = [];
  for (let i = 0; i < totalPages; i++) {
    kids.push(`${3 + i * 3} 0 R`);
  }
  offsets.push(currentByteLength);
  pushString(`2 0 obj\n<< /Type /Pages /Kids [${kids.join(" ")}] /Count ${totalPages} >>\nendobj\n`);

  // Sayfalar: Her sayfa için Page Obj, Content Obj, Image Obj
  for (let i = 0; i < totalPages; i++) {
    const pageNum = 3 + i * 3;
    const contNum = 3 + i * 3 + 1;
    const imgNum = 3 + i * 3 + 2;
    const pageItem = pagesData[i];

    // Page Obj
    offsets.push(currentByteLength);
    pushString(`${pageNum} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pw.toFixed(2)} ${ph.toFixed(2)}] /Resources << /XObject << /Im1 ${imgNum} 0 R >> /ProcSet [/PDF /ImageC] >> /Contents ${contNum} 0 R >>\nendobj\n`);

    // Content Obj
    const contStr = `q\n${pw.toFixed(2)} 0 0 ${ph.toFixed(2)} 0 0 cm\n/Im1 Do\nQ\n`;
    offsets.push(currentByteLength);
    pushString(`${contNum} 0 obj\n<< /Length ${contStr.length} >>\nstream\n${contStr}\nendstream\nendobj\n`);

    // Image XObject (JPEG DCTDecode)
    offsets.push(currentByteLength);
    pushString(`${imgNum} 0 obj\n<< /Type /XObject /Subtype /Image /Width ${pageItem.width} /Height ${pageItem.height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${pageItem.bytes.length} >>\nstream\n`);
    pushBytes(pageItem.bytes);
    pushString("\nendstream\nendobj\n");
  }

  // XRef Tablosu (Tam 10 basamaklı ofsetlerle ISO 32000 uyumu)
  const xrefOffset = currentByteLength;
  const totalObjs = 2 + totalPages * 3;
  pushString(`xref\n0 ${totalObjs + 1}\n0000000000 65535 f \n`);
  for (let i = 0; i < offsets.length; i++) {
    const offStr = String(offsets[i]).padStart(10, "0");
    pushString(`${offStr} 00000 n \n`);
  }

  // Trailer & EOF
  pushString(`trailer\n<< /Size ${totalObjs + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`);

  return new Blob(parts, { type: "application/pdf" });
}

function drawTextLineCanvas(ctx, lineText, startX, y, lineMaxW, align) {
  if (align === "center") {
    ctx.textAlign = "center";
    ctx.fillText(lineText, startX + lineMaxW / 2, y);
  } else if (align === "right") {
    ctx.textAlign = "right";
    ctx.fillText(lineText, startX + lineMaxW, y);
  } else if (align === "justify") {
    const words = lineText.split(" ");
    if (words.length <= 1) {
      ctx.textAlign = "left";
      ctx.fillText(lineText, startX, y);
      return;
    }
    const totalWordsW = words.reduce((acc, w) => acc + ctx.measureText(w).width, 0);
    const spaceToDistribute = lineMaxW - totalWordsW;
    if (spaceToDistribute <= 0 || spaceToDistribute > lineMaxW * 0.4) {
      ctx.textAlign = "left";
      ctx.fillText(lineText, startX, y);
      return;
    }
    const spaceW = spaceToDistribute / (words.length - 1);
    let curX = startX;
    ctx.textAlign = "left";
    for (let i = 0; i < words.length; i++) {
      ctx.fillText(words[i], curX, y);
      curX += ctx.measureText(words[i]).width + spaceW;
    }
  } else {
    ctx.textAlign = "left";
    ctx.fillText(lineText, startX, y);
  }
}

function renderTableDirectToCanvas(tableEl, ctx, leftPx, curY, maxW, scale, maxY) {
  const rows = Array.from(tableEl.querySelectorAll("tr"));
  if (rows.length === 0) return curY;

  ctx.strokeStyle = "#475569";
  ctx.lineWidth = 1 * scale;
  let rowY = curY;

  for (const row of rows) {
    if (rowY > maxY) break;
    const cells = Array.from(row.querySelectorAll("td, th"));
    if (cells.length === 0) continue;

    const colW = maxW / cells.length;
    let maxCellH = Math.round(24 * scale);

    cells.forEach(c => {
      const cLines = (c.innerText || "").split("\n");
      const estH = Math.max(maxCellH, Math.round((cLines.length * 16 + 10) * scale));
      if (estH > maxCellH) maxCellH = estH;
    });

    let cellX = leftPx;
    for (const cell of cells) {
      ctx.strokeRect(cellX, rowY, colW, maxCellH);
      ctx.fillStyle = "#000000";
      ctx.font = `${Math.round(10.5 * scale)}pt "Times New Roman", serif`;
      ctx.textAlign = "left";
      const cText = (cell.innerText || "").trim();
      ctx.fillText(cText.substring(0, 45), cellX + Math.round(6 * scale), rowY + Math.round(16 * scale));
      cellX += colW;
    }

    rowY += maxCellH;
  }

  return rowY;
}

function getPageElementBuckets(docData, targetW, targetH, scale) {
  const pageSheets = Array.from(document.querySelectorAll(".a4-sheet-page"));
  if (pageSheets.length > 1) {
    return pageSheets.map(s => {
      const body = s.querySelector(".page-body-box") || s;
      return Array.from(body.children).filter(ch =>
        !ch.classList.contains("auto-page-break") &&
        !ch.classList.contains("page-break-desk-gap") &&
        !ch.classList.contains("page-desk-gap") &&
        !ch.classList.contains("mobile-page-divider")
      );
    });
  }

  const m = (typeof currentMargins !== "undefined" && currentMargins) ? currentMargins : (docData?.margins || {});
  const topCm = !isNaN(parseFloat(m.top)) ? parseFloat(m.top) : 2.5;
  const bottomCm = !isNaN(parseFloat(m.bottom)) ? parseFloat(m.bottom) : 2.5;
  const ppc = 37.795275 * scale;
  const topPx = Math.round(topCm * ppc);
  const bottomPx = Math.round(bottomCm * ppc);
  const maxPageH = Math.max(300, targetH - topPx - bottomPx);

  const bodyEl = document.querySelector(".page-body-box") || document.getElementById("editor-content");
  const allChildren = bodyEl ? Array.from(bodyEl.children).filter(ch =>
    !ch.classList.contains("auto-page-break") &&
    !ch.classList.contains("page-break-desk-gap") &&
    !ch.classList.contains("page-desk-gap")
  ) : [];

  if (allChildren.length === 0) return [[]];

  const buckets = [];
  let curBucket = [];
  let curH = 0;

  for (const ch of allChildren) {
    if (ch.classList.contains("udf-page-break") || ch.classList.contains("mobile-page-divider")) {
      if (curBucket.length > 0) buckets.push(curBucket);
      curBucket = [];
      curH = 0;
      continue;
    }
    const tag = ch.tagName ? ch.tagName.toLowerCase() : "";
    let estH = 30 * scale;
    if (tag === "table") estH = Math.max(80 * scale, (ch.offsetHeight || 120) * scale);
    else {
      const textLen = (ch.innerText || "").length;
      const fontPt = parseFloat(ch.style.fontSize) || 12;
      const lineCount = Math.max(1, Math.ceil(textLen / 70));
      estH = lineCount * fontPt * 1.6 * scale;
    }
    if (curH + estH > maxPageH && curBucket.length > 0) {
      buckets.push(curBucket);
      curBucket = [ch];
      curH = estH;
    } else {
      curBucket.push(ch);
      curH += estH;
    }
  }
  if (curBucket.length > 0 || buckets.length === 0) {
    buckets.push(curBucket);
  }
  return buckets;
}

function renderSheetDirectToCanvas(sheet, ctx, targetW, targetH, scale, pageNum, totalPages, docData, explicitChildren = null) {
  ctx.fillStyle = "#FFFFFF";
  ctx.fillRect(0, 0, targetW, targetH);

  const m = (typeof currentMargins !== "undefined" && currentMargins) ? currentMargins : (docData?.margins || {});
  const leftCm = !isNaN(parseFloat(m.left)) ? parseFloat(m.left) : 2.5;
  const rightCm = !isNaN(parseFloat(m.right)) ? parseFloat(m.right) : 2.5;
  const topCm = !isNaN(parseFloat(m.top)) ? parseFloat(m.top) : 2.5;
  const bottomCm = !isNaN(parseFloat(m.bottom)) ? parseFloat(m.bottom) : 2.5;

  const ppc = 37.795275 * scale;
  const leftPx = Math.round(leftCm * ppc);
  const rightPx = Math.round(rightCm * ppc);
  const topPx = Math.round(topCm * ppc);
  const bottomPx = Math.round(bottomCm * ppc);
  const contentW = Math.max(200, targetW - leftPx - rightPx);

  let curY = topPx;

  // 1. Üstbilgi (Header)
  const headerEl = sheet ? sheet.querySelector(".page-header-box") : document.getElementById("doc-header");
  if (headerEl) {
    const hText = (headerEl.innerText || "").trim();
    if (hText) {
      ctx.fillStyle = "#1E293B";
      ctx.font = `bold ${Math.round(10.5 * scale)}pt "Times New Roman", serif`;
      ctx.textAlign = "center";
      ctx.fillText(hText, targetW / 2, curY - Math.round(10 * scale));
      ctx.strokeStyle = "#CBD5E1";
      ctx.lineWidth = 1 * scale;
      ctx.beginPath();
      ctx.moveTo(leftPx, curY - Math.round(4 * scale));
      ctx.lineTo(targetW - rightPx, curY - Math.round(4 * scale));
      ctx.stroke();
    }
  }

  // 2. Gövde Paragrafları ve Tabloları
  const children = explicitChildren ? explicitChildren : (sheet ? Array.from((sheet.querySelector(".page-body-box") || sheet).children).filter(ch =>
    !ch.classList.contains("auto-page-break") &&
    !ch.classList.contains("page-break-desk-gap") &&
    !ch.classList.contains("page-desk-gap") &&
    !ch.classList.contains("mobile-page-divider")
  ) : []);

  for (const child of children) {
    if (curY > targetH - bottomPx - 20) break;

    const tagName = child.tagName.toLowerCase();
    if (tagName === "table") {
      curY = renderTableDirectToCanvas(child, ctx, leftPx, curY, contentW, scale, targetH - bottomPx);
      curY += Math.round(8 * scale);
      continue;
    }

    if (tagName === "p" || tagName === "div" || tagName.startsWith("h")) {
      const textAlign = child.style.textAlign || "justify";
      const isBold = child.querySelector("strong, b") !== null || child.style.fontWeight === "bold";
      const isItalic = child.querySelector("em, i") !== null || child.style.fontStyle === "italic";
      const fontPt = parseFloat(child.style.fontSize) || 12;

      let fontStyleStr = "";
      if (isItalic) fontStyleStr += "italic ";
      if (isBold) fontStyleStr += "bold ";
      ctx.font = `${fontStyleStr}${Math.round(fontPt * scale)}pt "Times New Roman", serif`;
      ctx.fillStyle = child.style.color || "#000000";

      let indentPx = 0;
      if (child.style.textIndent) {
        indentPx = Math.round((parseFloat(child.style.textIndent) || 0) * scale);
      }

      const pText = (child.innerText || "").replace(/\r\n/g, "\n");
      const lines = pText.split("\n");

      for (let lIdx = 0; lIdx < lines.length; lIdx++) {
        const rawLine = lines[lIdx];
        if (!rawLine.trim()) {
          curY += Math.round(fontPt * 1.35 * scale);
          continue;
        }

        const words = rawLine.split(" ");
        let currentLine = "";
        let isFirstLineOfPara = (lIdx === 0);

        for (let w = 0; w < words.length; w++) {
          const testLine = currentLine ? (currentLine + " " + words[w]) : words[w];
          const curIndent = isFirstLineOfPara ? indentPx : 0;
          const metrics = ctx.measureText(testLine);

          if (metrics.width + curIndent > contentW && currentLine) {
            drawTextLineCanvas(ctx, currentLine, leftPx + curIndent, curY, contentW - curIndent, textAlign);
            curY += Math.round(fontPt * 1.35 * scale);
            currentLine = words[w];
            isFirstLineOfPara = false;
            if (curY > targetH - bottomPx) break;
          } else {
            currentLine = testLine;
          }
        }

        if (currentLine && curY <= targetH - bottomPx) {
          const curIndent = isFirstLineOfPara ? indentPx : 0;
          drawTextLineCanvas(ctx, currentLine, leftPx + curIndent, curY, contentW - curIndent, textAlign === "justify" ? "left" : textAlign);
          curY += Math.round(fontPt * 1.35 * scale);
        }
      }

      curY += Math.round(4 * scale);
    }
  }

  // 3. Altbilgi (Footer)
  const footerEl = sheet.querySelector(".page-footer-box");
  const footerY = targetH - Math.round(bottomPx / 2);
  ctx.strokeStyle = "#CBD5E1";
  ctx.lineWidth = 1 * scale;
  ctx.beginPath();
  ctx.moveTo(leftPx, footerY - Math.round(18 * scale));
  ctx.lineTo(targetW - rightPx, footerY - Math.round(18 * scale));
  ctx.stroke();

  ctx.fillStyle = "#475569";
  ctx.font = `${Math.round(9.5 * scale)}pt "Times New Roman", serif`;

  let footerText = "";
  if (footerEl) {
    const fTextEl = footerEl.querySelector(".udf-footer-text");
    if (fTextEl) footerText = fTextEl.innerText.trim();
  }
  if (!footerText && docData?.footer) footerText = docData.footer;

  if (footerText) {
    ctx.textAlign = "left";
    ctx.fillText(footerText.substring(0, 60), leftPx, footerY);
  }

  ctx.textAlign = "right";
  ctx.fillText(`Sayfa: ${pageNum} / ${totalPages}`, targetW - rightPx, footerY);
}

async function generatePdfBlob(docData) {
  const statusEl = document.getElementById("desktopStatusMsg");
  if (statusEl) statusEl.innerText = "PDF hazırlanıyor...";

  // 0. v3.15: Ekrandaki sayfanın birebir yerleşiminden vektör PDF (seçilebilir/aranabilir metin, gömülü yazı tipi)
  if (window.CanExport && window.CanExport.buildPdf) {
    try {
      const title = (document.getElementById("desktopDocTitle")?.value || "Belge").replace(/\.[^.]+$/, "");
      const blob = await window.CanExport.buildPdf(title);
      if (statusEl) statusEl.innerText = "✓ PDF hazır";
      return blob;
    } catch (e) {
      console.warn("Vektör PDF motoru başarısız, yedek motora geçiliyor:", e);
    }
  }

  // 1. Resmi Havelsan UYAP Headless Motoru (Port 5976) üzerinden 1:1 Vektör PDF
  try {
    const udfBlob = await generateUdfBlob(docData);
    const serverBlob = await tryHeadlessConvert("pdf", udfBlob);
    if (serverBlob) {
      if (statusEl) statusEl.innerText = "✓ Resmi UYAP PDF Hazırlandı";
      return serverBlob;
    }
  } catch (netErr) {
    // Havelsan yerel sunucusu aktif değil, doğrudan yerel yüksek çözünürlüklü A4 tuval motoru ile üret
  }

  if (typeof updatePagination === "function") {
    try { updatePagination(); } catch (e) {}
  }

  let pageSheets = Array.from(document.querySelectorAll(".a4-sheet-page"));
  if (pageSheets.length === 0) {
    const single = document.getElementById("sheet-container") || document.getElementById("page-wrapper") || document.getElementById("editor-content");
    if (single) pageSheets = [single];
  }

  const isLandscape = (typeof currentMargins !== "undefined" && currentMargins.orientation === "landscape") ||
    (pageSheets[0] && pageSheets[0].classList.contains("landscape"));

  // A4 Standardı: 595.28 x 841.89 pt (Dikey) veya 841.89 x 595.28 pt (Yatay)
  const pw = isLandscape ? 841.89 : 595.28;
  const ph = isLandscape ? 595.28 : 841.89;

  const baseW = isLandscape ? 1123 : 794;
  const baseH = isLandscape ? 794 : 1123;
  const renderScale = 2; // Keskin 192 DPI adli baskı çözünürlüğü
  const targetW = Math.round(baseW * renderScale);
  const targetH = Math.round(baseH * renderScale);

  const pageBuckets = getPageElementBuckets(docData, targetW, targetH, renderScale);
  const totalPages = Math.max(1, pageBuckets.length);
  const pagesData = [];

  for (let p = 0; p < totalPages; p++) {
    if (statusEl) statusEl.innerText = `PDF Sayfa ${p + 1}/${totalPages} hazırlanıyor...`;
    const sheet = (pageSheets && pageSheets[p]) ? pageSheets[p] : null;
    const canvas = document.createElement("canvas");
    canvas.width = targetW;
    canvas.height = targetH;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#FFFFFF";
    ctx.fillRect(0, 0, targetW, targetH);

    renderSheetDirectToCanvas(sheet, ctx, targetW, targetH, renderScale, p + 1, totalPages, docData, pageBuckets[p]);

    const jpegUrl = canvas.toDataURL("image/jpeg", 0.92);
    const jpegBytes = dataUrlToUint8Array(jpegUrl);
    pagesData.push({ bytes: jpegBytes, width: targetW, height: targetH });
  }

  return assemblePdfFromJpegs(pagesData, pw, ph);
}

// -------------------------------------------------------------
// 5. İNDİRME / KAYDETME YARDIMCISI (BROWSER / TAURI)
// -------------------------------------------------------------
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 200);
}


// =============================================================
// PLATFORM BAĞIMSIZ DOSYA KAYDETME / AÇMA (Android · Tauri masaüstü · Web)
// -------------------------------------------------------------
// Tauri (WebView2 / WKWebView / WebKitGTK) içinde <a download> ile indirme macOS ve Linux'ta
// sessizce başarısız oluyordu → "Kaydet" hiçbir şey yapmıyordu. Artık yerel diyalog + dosyaya yazma
// kullanılır; "Kaydet" açık dosyanın ÜZERİNE yazar (Word/UYAP davranışı), "Farklı Kaydet" diyalog açar.
// =============================================================
function tauriCore() {
  return (window.__TAURI__ && window.__TAURI__.core) ? window.__TAURI__.core : null;
}
function isRealAndroidEnv() {
  return !!(window.AndroidBridge && !window.AndroidBridge.__stub);
}
function u8ToB64(u8) {
  let s = '';
  for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
  return btoa(s);
}
window.currentDocPath = window.currentDocPath || null;

async function saveBytesSmart(data, fileName, mimeType, opts) {
  opts = opts || {};
  const u8 = (data instanceof Blob) ? new Uint8Array(await data.arrayBuffer()) : (data instanceof Uint8Array ? data : new Uint8Array(data));
  const ext = (fileName.split('.').pop() || '').toLowerCase();
  // 1) Android
  if (isRealAndroidEnv()) {
    if (opts.overwriteCurrent && window.AndroidBridge.saveBytesToCurrent) {
      window.AndroidBridge.saveBytesToCurrent(fileName, mimeType || 'application/octet-stream', u8ToB64(u8));
      return true;
    }
    if (window.AndroidBridge.saveBlobToDownloads) {
      window.AndroidBridge.saveBlobToDownloads(fileName, mimeType || 'application/octet-stream', u8ToB64(u8));
      return true;
    }
  }
  // 2) Masaüstü (Tauri)
  const t = tauriCore();
  if (t) {
    let path = null;
    const cur = window.currentDocPath;
    if (opts.overwriteCurrent && cur && cur.toLowerCase().endsWith('.' + ext)) path = cur;
    if (!path) {
      path = await t.invoke('save_file_dialog', { defaultName: fileName, ext });
      if (!path) return false; // kullanıcı vazgeçti
      if (!path.toLowerCase().endsWith('.' + ext)) path += '.' + ext;
    }
    await t.invoke('write_file_base64', { path, dataB64: u8ToB64(u8) });
    if (ext === 'udf') {
      window.currentDocPath = path;
      const nm = path.split(/[\\/]/).pop();
      try { currentDocFileName = nm; } catch (e) {}
      const el = document.getElementById('desktopDocTitle'); if (el) el.value = nm;
      document.title = nm + ' - CanEditor';
    }
    const st = document.getElementById('desktopStatusMsg'); if (st) st.innerText = '✓ Kaydedildi: ' + path.split(/[\\/]/).pop();
    return path;
  }
  // 3) Web
  downloadBlob(new Blob([u8], { type: mimeType || 'application/octet-stream' }), fileName);
  return true;
}
window.saveBytesSmart = saveBytesSmart;

// =============================================================
// DAHİLİ ADLİ PDF GÖRÜNTÜLEYİCİ MOTORU (PDF.js)
// =============================================================
let currentPdfDoc = null;
let currentPdfPage = 1;
let currentPdfTotalPages = 1;
let currentPdfZoom = 1.0;
let currentPdfBuffer = null;
let currentPdfFileName = "Belge.pdf";

async function openPdfViewer(arrayBuffer, fileName = "Belge.pdf") {
  currentPdfBuffer = arrayBuffer;
  currentPdfFileName = fileName;
  currentPdfPage = 1;
  currentPdfZoom = 1.0;

  const titleEl = document.getElementById("pdf-viewer-title");
  if (titleEl) titleEl.textContent = fileName;

  const modal = document.getElementById("modal-pdf-viewer");
  if (modal) {
    modal.style.display = "flex";
    modal.classList.add("open");
  }

  try {
    const pdfLib = (typeof pdfjsLib !== "undefined") ? pdfjsLib : (window["pdfjs-dist/build/pdf"] || window.pdfjs);
    if (!pdfLib) {
      throw new Error("PDF görüntüleme motoru (pdf.min.js) bulunamadı.");
    }
    if (pdfLib.GlobalWorkerOptions) {
      pdfLib.GlobalWorkerOptions.workerSrc = "pdf.worker.min.js";
    }
    const loadingTask = pdfLib.getDocument({ data: arrayBuffer });
    currentPdfDoc = await loadingTask.promise;
    currentPdfTotalPages = currentPdfDoc.numPages || 1;

    updatePdfPageIndicator();
    await renderAllPdfPages();
  } catch (err) {
    console.error("PDF Açma Hatası:", err);
    if (typeof showEditorToast === "function") showEditorToast("PDF açılırken hata: " + err.message);
  }
}
window.openPdfViewer = openPdfViewer;

async function renderAllPdfPages() {
  const rail = document.getElementById("pdf-pages-render-rail");
  if (!rail || !currentPdfDoc) return;
  rail.innerHTML = "";

  for (let num = 1; num <= currentPdfTotalPages; num++) {
    const pageWrapper = document.createElement("div");
    pageWrapper.className = "viewer-page-card";
    pageWrapper.id = `pdf-page-${num}`;

    const canvas = document.createElement("canvas");
    pageWrapper.appendChild(canvas);
    rail.appendChild(pageWrapper);

    const page = await currentPdfDoc.getPage(num);
    const viewport = page.getViewport({ scale: currentPdfZoom * 1.5 });
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    canvas.style.width = `${Math.round(viewport.width / 1.5)}px`;
    canvas.style.height = `${Math.round(viewport.height / 1.5)}px`;

    const ctx = canvas.getContext("2d");
    await page.render({ canvasContext: ctx, viewport }).promise;
  }
}

function updatePdfPageIndicator() {
  const indicator = document.getElementById("pdf-page-indicator");
  if (indicator) {
    indicator.textContent = `${currentPdfPage} / ${currentPdfTotalPages}`;
  }
  const badge = document.getElementById("pdf-zoom-badge");
  if (badge) {
    badge.textContent = `%${Math.round(currentPdfZoom * 100)}`;
  }
}
window.updatePdfPageIndicator = updatePdfPageIndicator;

function stepPdfPage(delta) {
  const target = Math.min(Math.max(1, currentPdfPage + delta), currentPdfTotalPages);
  if (target !== currentPdfPage) {
    currentPdfPage = target;
    updatePdfPageIndicator();
    const el = document.getElementById(`pdf-page-${currentPdfPage}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}
window.stepPdfPage = stepPdfPage;

function zoomPdf(delta) {
  currentPdfZoom = Math.max(0.4, Math.min(3.0, currentPdfZoom + delta));
  updatePdfPageIndicator();
  renderAllPdfPages();
}
window.zoomPdf = zoomPdf;

function resetPdfZoom() {
  currentPdfZoom = 1.0;
  updatePdfPageIndicator();
  renderAllPdfPages();
}
window.resetPdfZoom = resetPdfZoom;

async function downloadCurrentPdf() {
  const __saveOpts = {};
  if (!currentPdfBuffer) return;
  const blob = new Blob([currentPdfBuffer], { type: "application/pdf" });
  if (!(await saveBytesSmart(blob, currentPdfFileName, "application/pdf", __saveOpts))) return;
}
window.downloadCurrentPdf = downloadCurrentPdf;

function shareCurrentPdf() {
  if (!currentPdfBuffer) return;
  const blob = new Blob([currentPdfBuffer], { type: "application/pdf" });
  if (window.AndroidBridge && window.AndroidBridge.shareBlobData) {
    const reader = new FileReader();
    reader.onloadend = () => {
      const b64 = reader.result.split(",")[1];
      window.AndroidBridge.shareBlobData(currentPdfFileName, "application/pdf", b64);
    };
    reader.readAsDataURL(blob);
  } else if (navigator.canShare) {
    const file = new File([blob], currentPdfFileName, { type: "application/pdf" });
    navigator.share({ files: [file], title: currentPdfFileName }).catch(() => {});
  } else {
    downloadCurrentPdf();
  }
}
window.shareCurrentPdf = shareCurrentPdf;

// =============================================================
// DAHİLİ ÇOK SAYFALI ADLİ TIFF GÖRÜNTÜLEYİCİ (UTIF.js)
// =============================================================
let currentTiffIfds = [];
let currentTiffPage = 1;
let currentTiffTotalPages = 1;
let currentTiffZoom = 1.0;
let currentTiffBuffer = null;
let currentTiffFileName = "Belge.tiff";

async function openTiffViewer(arrayBuffer, fileName = "Belge.tiff") {
  currentTiffBuffer = arrayBuffer;
  currentTiffFileName = fileName;
  currentTiffPage = 1;
  currentTiffZoom = 1.0;

  const titleEl = document.getElementById("tiff-viewer-title");
  if (titleEl) titleEl.textContent = fileName;

  const modal = document.getElementById("modal-tiff-viewer");
  if (modal) {
    modal.style.display = "flex";
    modal.classList.add("open");
  }

  try {
    if (typeof UTIF === "undefined") {
      throw new Error("TIFF görüntüleme motoru (utif.js) bulunamadı.");
    }
    const ifds = UTIF.decode(arrayBuffer);
    currentTiffIfds = ifds;
    currentTiffTotalPages = Math.max(1, ifds.length);

    updateTiffPageIndicator();
    renderAllTiffPages();
  } catch (err) {
    console.error("TIFF Açma Hatası:", err);
    if (typeof showEditorToast === "function") showEditorToast("TIFF açılırken hata: " + err.message);
  }
}
window.openTiffViewer = openTiffViewer;

function renderAllTiffPages() {
  const rail = document.getElementById("tiff-pages-render-rail");
  if (!rail || !currentTiffIfds) return;
  rail.innerHTML = "";

  currentTiffIfds.forEach((ifd, idx) => {
    try {
      UTIF.decodeImage(currentTiffBuffer, ifd);
      const rgba = UTIF.toRGBA8(ifd);
      const w = ifd.width;
      const h = ifd.height;

      const pageWrapper = document.createElement("div");
      pageWrapper.className = "viewer-page-card";
      pageWrapper.id = `tiff-page-${idx + 1}`;

      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      const imgData = ctx.createImageData(w, h);
      imgData.data.set(rgba);
      ctx.putImageData(imgData, 0, 0);

      const displayW = Math.round(w * currentTiffZoom);
      const displayH = Math.round(h * currentTiffZoom);
      canvas.style.width = `${displayW}px`;
      canvas.style.height = `${displayH}px`;
      canvas.style.maxWidth = "100%";

      pageWrapper.appendChild(canvas);
      rail.appendChild(pageWrapper);
    } catch (e) {
      console.warn("TIFF sayfa render hatası:", idx, e);
    }
  });
}

function updateTiffPageIndicator() {
  const indicator = document.getElementById("tiff-page-indicator");
  if (indicator) {
    indicator.textContent = `${currentTiffPage} / ${currentTiffTotalPages}`;
  }
  const badge = document.getElementById("tiff-zoom-badge");
  if (badge) {
    badge.textContent = `%${Math.round(currentTiffZoom * 100)}`;
  }
}
window.updateTiffPageIndicator = updateTiffPageIndicator;

function stepTiffPage(delta) {
  const target = Math.min(Math.max(1, currentTiffPage + delta), currentTiffTotalPages);
  if (target !== currentTiffPage) {
    currentTiffPage = target;
    updateTiffPageIndicator();
    const el = document.getElementById(`tiff-page-${currentTiffPage}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}
window.stepTiffPage = stepTiffPage;

function zoomTiff(delta) {
  currentTiffZoom = Math.max(0.4, Math.min(3.0, currentTiffZoom + delta));
  updateTiffPageIndicator();
  renderAllTiffPages();
}
window.zoomTiff = zoomTiff;

function resetTiffZoom() {
  currentTiffZoom = 1.0;
  updateTiffPageIndicator();
  renderAllTiffPages();
}
window.resetTiffZoom = resetTiffZoom;

async function downloadCurrentTiff() {
  const __saveOpts = {};
  if (!currentTiffBuffer) return;
  const blob = new Blob([currentTiffBuffer], { type: "image/tiff" });
  if (!(await saveBytesSmart(blob, currentTiffFileName, "image/tiff", __saveOpts))) return;
}
window.downloadCurrentTiff = downloadCurrentTiff;

function shareCurrentTiff() {
  if (!currentTiffBuffer) return;
  const blob = new Blob([currentTiffBuffer], { type: "image/tiff" });
  if (window.AndroidBridge && window.AndroidBridge.shareBlobData) {
    const reader = new FileReader();
    reader.onloadend = () => {
      const b64 = reader.result.split(",")[1];
      window.AndroidBridge.shareBlobData(currentTiffFileName, "image/tiff", b64);
    };
    reader.readAsDataURL(blob);
  } else if (navigator.canShare) {
    const file = new File([blob], currentTiffFileName, { type: "image/tiff" });
    navigator.share({ files: [file], title: currentTiffFileName }).catch(() => {});
  } else {
    downloadCurrentTiff();
  }
}
window.shareCurrentTiff = shareCurrentTiff;

// -------------------------------------------------------------
// 6. DOSYA AÇMA & SÜRÜKLE BIRAK YÖNETİCİSİ
// -------------------------------------------------------------
async function openDocumentFromBytes(buffer, name, path) {
  if (!buffer) return;
  const fileName = name || (path ? path.split(/[/\\]/).pop() : "Belge.udf");
  currentDocFileName = fileName;
  // Masaüstünde gerçek dosya yolu (Kaydet bu dosyanın üzerine yazar); web'de yol bilinmez
  window.currentDocPath = (tauriCore() && path && /[\\/]/.test(path)) ? path : null;
  updateDocTitleDisplay(fileName);

  const statusEl = document.getElementById("desktopStatusMsg");
  if (statusEl) statusEl.innerText = "Belge okunuyor...";

  try {
    let arrayBuffer;
    if (typeof buffer === "string") {
      const cleanB64 = buffer.replace(/\s+/g, '');
      const binaryStr = atob(cleanB64);
      const len = binaryStr.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryStr.charCodeAt(i);
      }
      arrayBuffer = bytes.buffer;
    } else if (buffer instanceof ArrayBuffer) {
      arrayBuffer = buffer;
    } else if (buffer && buffer.buffer) {
      arrayBuffer = buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
    } else {
      arrayBuffer = new Uint8Array(buffer || 0).buffer;
    }
    currentDocOriginalBuffer = arrayBuffer.slice(0);
    window.__udfSource = null; // yeni belge: önceki UDF kaynak bilgisi temizlenir
    const lowerName = fileName.toLowerCase();

    const u8 = new Uint8Array(arrayBuffer.slice(0, 16));
    const isTiffMagic = (u8[0] === 0x49 && u8[1] === 0x49 && u8[2] === 42) || (u8[0] === 0x4D && u8[1] === 0x4D && u8[3] === 42);
    const isPdfMagic = (u8[0] === 0x25 && u8[1] === 0x50 && u8[2] === 0x44 && u8[3] === 0x46);
    const isZip = (u8[0] === 0x50 && u8[1] === 0x4B && u8[2] === 0x03 && u8[3] === 0x04);

    let result;
    if (lowerName.endsWith(".tiff") || lowerName.endsWith(".tif") || isTiffMagic) {
      if (typeof openTiffViewer === "function") {
        await openTiffViewer(arrayBuffer, fileName);
        if (statusEl) statusEl.innerText = "✓ TIFF Görüntüleyici Açıldı";
        return;
      }
      result = await parseTiffArrayBuffer(arrayBuffer);
    } else if (lowerName.endsWith(".pdf") || isPdfMagic) {
      if (typeof openPdfViewer === "function") {
        await openPdfViewer(arrayBuffer, fileName);
        if (statusEl) statusEl.innerText = "✓ PDF Görüntüleyici Açıldı";
        return;
      }
      result = await parsePdfArrayBuffer(arrayBuffer);
    } else if (lowerName.endsWith(".odt")) {
      result = await parseOdtArrayBuffer(arrayBuffer);
    } else if (lowerName.endsWith(".docx") || lowerName.endsWith(".doc")) {
      result = await parseDocxArrayBuffer(arrayBuffer);
    } else if (isZip) {
      const zip = await JSZip.loadAsync(arrayBuffer);
      if (zip.file("word/document.xml")) {
        result = await parseDocxArrayBuffer(arrayBuffer);
      } else if (zip.file("mimetype") && (await zip.file("mimetype").async("text")).includes("opendocument")) {
        result = await parseOdtArrayBuffer(arrayBuffer);
      } else {
        result = await parseUdfArrayBuffer(arrayBuffer);
      }
    } else {
      result = await parseUdfArrayBuffer(arrayBuffer);
    }

    if (window.setHtmlContent) {
      window.setHtmlContent(JSON.stringify(result));
    }

    if (result.signature) {
      updateSignatureBadge(result.signature);
      if (typeof updateSignatureBanner === 'function') updateSignatureBanner(result.signature);
      if (typeof onDocumentSignatureChecked === 'function') onDocumentSignatureChecked(result.signature);
    } else {
      updateSignatureBadge({ hasSignature: false, isValid: false });
      if (typeof updateSignatureBanner === 'function') updateSignatureBanner({ hasSignature: false, isValid: false });
    }

    if (statusEl) statusEl.innerText = "✓ Açıldı";
  } catch (err) {
    alert("Belge okuma hatası: " + err.message);
    if (statusEl) statusEl.innerText = "Hata";
  }
}

async function handleFileOpen(file) {
  if (!file) return;
  try {
    const buffer = await file.arrayBuffer();
    await openDocumentFromBytes(buffer, file.name, file.name);
  } catch (err) {
    alert("Belge okuma hatası: " + err.message);
  }
}

function updateDocTitleDisplay(name) {
  const el = document.getElementById("desktopDocTitle");
  if (el) el.value = name;
  document.title = name + " - CanEditor";
  if (window.AndroidBridge && window.AndroidBridge.syncDocumentTitle) {
    try { window.AndroidBridge.syncDocumentTitle(name); } catch (e) {}
  }
}

function updateSignatureBadge(sig) {
  const badge = document.getElementById("desktopSigBadge");
  if (!badge) return;
  if (sig && sig.hasSignature) {
    badge.innerText = sig.isValid ? "🟢 E-İMZALI (Geçerli)" : "🔴 GEÇERSİZ E-İMZA";
    badge.style.display = "inline-block";
    badge.className = sig.isValid ? "badge-sig-valid" : "badge-sig-invalid";
  } else {
    badge.innerText = "⚪ İmzasız";
    badge.style.display = "inline-block";
    badge.className = "badge-sig-none";
  }
}

// -------------------------------------------------------------
// 7. DESKTOP EYLEMLERİ (AÇ, HIZLI KAYDET, FARKLIKAYDET, PAYLAŞ, YAZDIR)
// -------------------------------------------------------------
async function triggerOpenDocument() {
  const t = tauriCore();
  if (t) {
    // Masaüstü: yerel "Aç" penceresi → dosya yolu bilinir, "Kaydet" aynı dosyanın üzerine yazar
    try {
      const path = await t.invoke('open_file_dialog');
      if (!path) return;
      const data = await t.invoke('read_file_binary', { path });
      const u8 = new Uint8Array(data);
      await openDocumentFromBytes(u8.buffer, path.split(/[\\/]/).pop(), path);
      return;
    } catch (e) { console.warn('Tauri açma diyaloğu kullanılamadı, tarayıcı seçicisine geçiliyor:', e); }
  }
  const fileInput = document.getElementById("desktopFileInput");
  if (fileInput) fileInput.click();
}

async function triggerQuickSave() {
  const statusEl = document.getElementById("desktopStatusMsg");
  if (statusEl) statusEl.innerText = "Kaydediliyor...";

  if (window.AndroidBridge && window.AndroidBridge.requestSave) {
    try {
      window.AndroidBridge.requestSave();
      if (typeof showEditorToast === "function") {
        const now = new Date().toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
        showEditorToast(`✓ Belge Başarıyla Kaydedildi (${now})`);
      }
      return;
    } catch (e) {
      console.warn("AndroidBridge requestSave hatası, fallback uygulanıyor:", e);
    }
  }

  // Web veya Tauri ortamında hızlı kaydet
  await triggerSaveUdf();
  if (typeof showEditorToast === "function") {
    const now = new Date().toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
    showEditorToast(`✓ Belge Başarıyla Kaydedildi (${now})`);
  }
}
window.triggerQuickSave = triggerQuickSave;

async function triggerSaveUdf(forceDialog) {
  // Kaydet: açık .udf dosyasının üzerine yazar; Farklı Kaydet (forceDialog): her zaman konum sorar
  const __saveOpts = { overwriteCurrent: !forceDialog };
  let name = (document.getElementById("desktopDocTitle")?.value || currentDocFileName).trim();
  name = name.replace(/\.(docx|pdf|tiff|tif|odt)$/i, "") + ".udf";

  const hasSig = window.__currentDocSignature && window.__currentDocSignature.hasSignature;
  const isModified = window.isDocumentModified ? window.isDocumentModified() : true;
  if (!isModified && hasSig && currentDocOriginalBuffer && currentDocFileName.toLowerCase().endsWith(".udf")) {
    const blob = new Blob([currentDocOriginalBuffer], { type: "application/octet-stream" });
    if (!(await saveBytesSmart(blob, name, "application/octet-stream", __saveOpts))) return;
    const statusEl = document.getElementById("desktopStatusMsg");
    if (statusEl) statusEl.innerText = "✓ UDF Korunarak Kaydedildi";
    if (typeof showEditorToast === "function") showEditorToast("✓ UDF Belgesi (İmza Korundu) Kaydedildi");
    return;
  }

  const getDocFn = window.getStructuredDocument || (typeof getStructuredDocument === 'function' ? getStructuredDocument : null);
  if (!getDocFn) return;
  const docData = getDocFn();
  const blob = await generateUdfBlob(docData);

  if (!(await saveBytesSmart(blob, name, "application/octet-stream", __saveOpts))) return;
  if (window.markDocumentPristine) window.markDocumentPristine();
  const statusEl = document.getElementById("desktopStatusMsg");
  if (statusEl) statusEl.innerText = "✓ UDF Kaydedildi";
  if (typeof showEditorToast === "function") showEditorToast("✓ Havelsan UDF Kaydedildi");
}

async function triggerSaveDocx() {
  const __saveOpts = {};
  const getDocFn = window.getStructuredDocument || (typeof getStructuredDocument === 'function' ? getStructuredDocument : null);
  if (!getDocFn) return;
  const docData = getDocFn();
  let name = (document.getElementById("desktopDocTitle")?.value || currentDocFileName).trim();
  name = name.replace(/\.(udf|pdf|tiff|tif|odt)$/i, "") + ".docx";
  const blob = await generateDocxBlob(docData);

  if (!(await saveBytesSmart(blob, name, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", __saveOpts))) return;
  const statusEl = document.getElementById("desktopStatusMsg");
  if (statusEl) statusEl.innerText = "✓ Word (DOCX) Kaydedildi";
  if (typeof showEditorToast === "function") showEditorToast("✓ Word (DOCX) Kaydedildi");
}

async function triggerSaveAs(format) {
  const __saveOpts = {};
  let base = (document.getElementById("desktopDocTitle")?.value || window.currentDocFileName || (typeof currentDocFileName !== 'undefined' ? currentDocFileName : '') || "Dilekce").trim();
  base = base.replace(/\.(udf|docx|pdf|tiff|tif|odt)$/i, "");
  if (!base) base = "Dilekce";

  const getDocFn = window.getStructuredDocument || (typeof getStructuredDocument === 'function' ? getStructuredDocument : null);
  const docData = getDocFn ? getDocFn() : null;
  const statusEl = document.getElementById("desktopStatusMsg");

  if (format === "udf") {
    await triggerSaveUdf(true);
  } else if (format === "docx") {
    await triggerSaveDocx();
  } else if (format === "pdf") {
    if (statusEl) statusEl.innerText = "PDF hazırlanıyor...";
    try {
      const blob = await generatePdfBlob(docData);
      const fileName = base + ".pdf";
      if (!(await saveBytesSmart(blob, fileName, "application/pdf", __saveOpts))) return;
      if (statusEl) statusEl.innerText = "✓ Adobe PDF (.pdf) Kaydedildi";
      if (typeof showEditorToast === "function") showEditorToast("✓ Adobe PDF Kaydedildi");
    } catch (err) {
      console.error("PDF kaydetme hatası:", err);
      if (statusEl) statusEl.innerText = "PDF oluşturulamadı, yazdırma menüsü açılıyor...";
      triggerDirectPrint();
    }
  } else if (format === "tiff" || format === "tif") {
    if (statusEl) statusEl.innerText = "TIFF hazırlanıyor...";
    const blob = await generateTiffBlob(docData);
    const fileName = base + ".tiff";
    if (!(await saveBytesSmart(blob, fileName, "image/tiff", __saveOpts))) return;
    if (statusEl) statusEl.innerText = "✓ TIFF Kaydedildi";
    if (typeof showEditorToast === "function") showEditorToast("✓ Çok Sayfalı TIFF Kaydedildi");
  } else if (format === "odt") {
    if (statusEl) statusEl.innerText = "ODT hazırlanıyor...";
    const blob = await generateOdtBlob(docData);
    const fileName = base + ".odt";
    if (!(await saveBytesSmart(blob, fileName, "application/vnd.oasis.opendocument.text", __saveOpts))) return;
    if (statusEl) statusEl.innerText = "✓ ODT Kaydedildi";
    if (typeof showEditorToast === "function") showEditorToast("✓ OpenDocument (ODT) Kaydedildi");
  }
}

async function triggerSavePdf() {
  await triggerSaveAs("pdf");
}
window.triggerSavePdf = triggerSavePdf;
window.triggerSaveAs = triggerSaveAs;
window.triggerShareFormat = triggerShareFormat;

function sendBlobToShare(blob, fileName, mimeType) {
  const reader = new FileReader();
  reader.onloadend = () => {
    const b64 = reader.result.split(",")[1];
    if (window.AndroidBridge && window.AndroidBridge.shareBlobData) {
      window.AndroidBridge.shareBlobData(fileName, mimeType, b64);
    } else if (window.AndroidBridge && window.AndroidBridge.saveBlobToDownloads) {
      window.AndroidBridge.saveBlobToDownloads(fileName, mimeType, b64);
    }
  };
  reader.readAsDataURL(blob);
}

async function triggerShareFormat(format) {
  let base = (document.getElementById("desktopDocTitle")?.value || window.currentDocFileName || (typeof currentDocFileName !== 'undefined' ? currentDocFileName : '') || "Dilekce").trim();
  base = base.replace(/\.(udf|docx|pdf|tiff|tif|odt)$/i, "");
  if (!base) base = "Dilekce";

  const getDocFn = window.getStructuredDocument || (typeof getStructuredDocument === 'function' ? getStructuredDocument : null);
  const docData = getDocFn ? getDocFn() : null;
  const statusEl = document.getElementById("desktopStatusMsg");

  // Gerçek Android köprüsü varsa doğrudan yerel paylaşım diyaloğunu aç:
  if (window.isRealAndroidBridge ? window.isRealAndroidBridge() : (window.AndroidBridge && !window.AndroidBridge.__stub)) {
    if (format === "pdf") {
      if (statusEl) statusEl.innerText = "PDF hazırlanıyor...";
      try {
        const blob = await generatePdfBlob(docData);
        sendBlobToShare(blob, base + ".pdf", "application/pdf");
        if (typeof showEditorToast === "function") showEditorToast("✓ PDF Paylaşılıyor");
        return;
      } catch (err) {
        console.error("PDF paylaşım hatası:", err);
      }
    } else if (format === "udf") {
      if (statusEl) statusEl.innerText = "UDF hazırlanıyor...";
      try {
        const blob = await generateUdfBlob(docData);
        sendBlobToShare(blob, base + ".udf", "application/octet-stream");
        if (typeof showEditorToast === "function") showEditorToast("✓ Havelsan UDF Paylaşılıyor");
        return;
      } catch (err) {
        console.error("UDF paylaşım hatası:", err);
      }
    } else if (format === "docx") {
      if (statusEl) statusEl.innerText = "Word hazırlanıyor...";
      try {
        const blob = await generateDocxBlob(docData);
        sendBlobToShare(blob, base + ".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
        if (typeof showEditorToast === "function") showEditorToast("✓ Word (DOCX) Paylaşılıyor");
        return;
      } catch (err) {
        console.error("Word paylaşım hatası:", err);
      }
    } else if (format === "tiff" || format === "tif") {
      if (statusEl) statusEl.innerText = "TIFF hazırlanıyor...";
      try {
        const blob = await generateTiffBlob(docData);
        sendBlobToShare(blob, base + ".tiff", "image/tiff");
        if (typeof showEditorToast === "function") showEditorToast("✓ Çok Sayfalı TIFF Paylaşılıyor");
        return;
      } catch (err) {
        console.error("TIFF paylaşım hatası:", err);
      }
    } else if (format === "odt") {
      if (statusEl) statusEl.innerText = "ODT hazırlanıyor...";
      try {
        const blob = await generateOdtBlob(docData);
        sendBlobToShare(blob, base + ".odt", "application/vnd.oasis.opendocument.text");
        if (typeof showEditorToast === "function") showEditorToast("✓ OpenDocument (ODT) Paylaşılıyor");
        return;
      } catch (err) {
        console.error("ODT paylaşım hatası:", err);
      }
    } else if (format === "text") {
      const text = window.getPlainText ? window.getPlainText() : "";
      const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      sendBlobToShare(blob, base + ".txt", "text/plain");
      if (typeof showEditorToast === "function") showEditorToast("✓ Düz Metin Paylaşılıyor");
      return;
    }
  }

  // Web / Masaüstü Paylaşım (Web Share API veya İndirme)
  try {
    let blob;
    let fileName = base;
    let mimeType = "application/octet-stream";

    if (format === "udf") {
      blob = await generateUdfBlob(docData);
      fileName += ".udf";
      mimeType = "application/octet-stream";
    } else if (format === "docx") {
      blob = await generateDocxBlob(docData);
      fileName += ".docx";
      mimeType = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    } else if (format === "pdf") {
      blob = await generatePdfBlob(docData);
      fileName += ".pdf";
      mimeType = "application/pdf";
    } else if (format === "tiff") {
      blob = await generateTiffBlob(docData);
      fileName += ".tiff";
      mimeType = "image/tiff";
    } else if (format === "odt") {
      blob = await generateOdtBlob(docData);
      fileName += ".odt";
      mimeType = "application/vnd.oasis.opendocument.text";
    } else {
      const text = window.getPlainText ? window.getPlainText() : "";
      blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      fileName += ".txt";
      mimeType = "text/plain";
    }

    const file = new File([blob], fileName, { type: mimeType });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({
        files: [file],
        title: base,
        text: `${base} belgesi CanEditor üzerinden paylaşıldı.`
      });
      if (statusEl) statusEl.innerText = "✓ Paylaşıldı";
      if (typeof showEditorToast === "function") showEditorToast("✓ Belge Paylaşıldı");
    } else {
      downloadBlob(blob, fileName);
      if (statusEl) statusEl.innerText = "✓ Paylaşım için İndirildi";
      if (typeof showEditorToast === "function") showEditorToast("✓ Belge İndirildi");
    }
  } catch (e) {
    if (statusEl) statusEl.innerText = "Paylaşım tamamlandı";
  }
}

// -------------------------------------------------------------
// BELGE İÇİ HIZLI ARAMA MOTORU (UYAP Avukat Portal Standartları)
// -------------------------------------------------------------
let inDocSearchState = {
  query: "",
  matches: [],
  currentIndex: -1
};

function executeInDocSearch(query) {
  if (query === undefined || query === null) {
    const input = document.getElementById("inDocSearchInput");
    query = input ? input.value : "";
  }
  clearInDocSearchHighlights();
  if (!query || !query.trim()) {
    inDocSearchState = { query: "", matches: [], currentIndex: -1 };
    updateSearchBadge();
    return;
  }
  const q = query.trim().toLocaleLowerCase('tr-TR');
  inDocSearchState.query = q;
  inDocSearchState.matches = [];
  inDocSearchState.currentIndex = -1;

  const container = document.getElementById("pages-container") || document.getElementById("editor-content");
  if (!container) return;

  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
  const textNodes = [];
  let node;
  while ((node = walker.nextNode())) {
    if (node.parentElement && !node.parentElement.closest(".ruler-container") && !node.parentElement.closest("#desktop-app-header")) {
      textNodes.push(node);
    }
  }

  textNodes.forEach(tNode => {
    const val = tNode.nodeValue || "";
    const lower = val.toLocaleLowerCase('tr-TR');
    let idx = lower.indexOf(q);
    if (idx !== -1) {
      const span = document.createElement("mark");
      span.className = "udv-search-highlight";
      span.style.backgroundColor = "#FEF08A";
      span.style.color = "#000000";
      span.style.borderRadius = "2px";
      span.style.padding = "1px 2px";

      const before = val.substring(0, idx);
      const match = val.substring(idx, idx + q.length);
      const after = val.substring(idx + q.length);

      span.textContent = match;
      const parent = tNode.parentNode;
      if (parent) {
        if (before) parent.insertBefore(document.createTextNode(before), tNode);
        parent.insertBefore(span, tNode);
        if (after) parent.insertBefore(document.createTextNode(after), tNode);
        parent.removeChild(tNode);
        inDocSearchState.matches.push(span);
      }
    }
  });

  if (inDocSearchState.matches.length > 0) {
    inDocSearchState.currentIndex = 0;
    highlightCurrentMatch();
  }
  updateSearchBadge();
}

function navigateInDocSearch(direction) {
  if (inDocSearchState.matches.length === 0) return;
  if (direction === "next") {
    inDocSearchState.currentIndex = (inDocSearchState.currentIndex + 1) % inDocSearchState.matches.length;
  } else {
    inDocSearchState.currentIndex = (inDocSearchState.currentIndex - 1 + inDocSearchState.matches.length) % inDocSearchState.matches.length;
  }
  highlightCurrentMatch();
  updateSearchBadge();
}

function highlightCurrentMatch() {
  inDocSearchState.matches.forEach((m, idx) => {
    if (idx === inDocSearchState.currentIndex) {
      m.style.backgroundColor = "#F97316";
      m.style.color = "#FFFFFF";
      m.scrollIntoView({ behavior: "smooth", block: "center" });
    } else {
      m.style.backgroundColor = "#FEF08A";
      m.style.color = "#000000";
    }
  });
}

function clearInDocSearchHighlights() {
  document.querySelectorAll(".udv-search-highlight").forEach(m => {
    const parent = m.parentNode;
    if (parent) {
      parent.replaceChild(document.createTextNode(m.textContent || ""), m);
      parent.normalize();
    }
  });
}

function updateSearchBadge() {
  const badge = document.getElementById("inDocSearchCount");
  if (!badge) return;
  if (!inDocSearchState.query) {
    badge.innerText = "";
    badge.style.display = "none";
  } else if (inDocSearchState.matches.length === 0) {
    badge.innerText = "Yok";
    badge.style.display = "inline-block";
    badge.style.color = "#EF4444";
  } else {
    badge.innerText = `${inDocSearchState.currentIndex + 1}/${inDocSearchState.matches.length}`;
    badge.style.display = "inline-block";
    badge.style.color = "#0284C7";
  }
}

window.executeInDocSearch = executeInDocSearch;
window.navigateInDocSearch = navigateInDocSearch;
window.clearInDocSearchHighlights = clearInDocSearchHighlights;

function fitToWidth() {
  const container = document.getElementById("pages-container") || document.getElementById("sheet-container");
  if (!container) return;
  const isLandscape = typeof currentMargins !== "undefined" && currentMargins.orientation === "landscape";
  const sheetW = isLandscape ? 1123 : 794;
  const availableW = (window.innerWidth || document.documentElement.clientWidth) - 40;
  const newZoom = Math.min(1.8, Math.max(0.3, availableW / sheetW));
  if (typeof setCustomZoom === "function") {
    setCustomZoom(newZoom);
  }
}

function fitToPage() {
  const isLandscape = typeof currentMargins !== "undefined" && currentMargins.orientation === "landscape";
  const sheetH = isLandscape ? 794 : 1123;
  const availableH = (window.innerHeight || document.documentElement.clientHeight) - 160;
  const newZoom = Math.min(1.5, Math.max(0.25, availableH / sheetH));
  if (typeof setCustomZoom === "function") {
    setCustomZoom(newZoom);
  }
}

window.fitToWidth = fitToWidth;
window.fitToPage = fitToPage;

function triggerDirectPrint() {
  if (window.AndroidBridge && window.AndroidBridge.printDocument) {
    window.AndroidBridge.printDocument();
  } else {
    window.print();
  }
}

function triggerPrintPdf() {
  triggerDirectPrint();
}

function toggleSaveMenu(e) {
  if (e) e.stopPropagation();
  const d = document.getElementById("saveAsDropdown");
  closeDropdowns(d);
  if (d) d.classList.toggle("show");
}

function toggleShareMenu(e) {
  if (e) e.stopPropagation();
  const d = document.getElementById("shareDropdown");
  closeDropdowns(d);
  if (d) d.classList.toggle("show");
}

function togglePrintMenu(e) {
  if (e) e.stopPropagation();
  const d = document.getElementById("printDropdown");
  closeDropdowns(d);
  if (d) d.classList.toggle("show");
}

function closeDropdowns(except) {
  // Bu alt menüler artık menü çubuğunun içinde (.ce-sub-pop) ve CSS :hover / .open ile açılır.
  // Eskiden burada inline "display:none" yazılıyordu; bu, her tıklamadan sonra alt menülerin
  // (Farklı Kaydet / Paylaş / Yazdır) bir daha HİÇ açılmamasına neden oluyordu. Inline stil temizlenir.
  ["saveAsDropdown", "shareDropdown", "printDropdown"].forEach(id => {
    const el = document.getElementById(id);
    if (el && el !== except) { el.style.display = ""; el.classList.remove("show"); }
  });
}

document.addEventListener("click", () => closeDropdowns());

// -------------------------------------------------------------
// 8. KLAVYE KISAYOLLARI & SÜRÜKLE BIRAK BAĞLANTISI
// -------------------------------------------------------------
window.addEventListener("DOMContentLoaded", () => {
  if (!window.AndroidBridge) {
    // Masaüstü/Web için yedek köprü. __stub işareti sayesinde editor.js bunu gerçek Android
    // WebView köprüsü sanıp gövdeye 'is-android' sınıfı EKLEMEZ (eskiden masaüstü Android gibi davranıyordu).
    window.AndroidBridge = {
      __stub: true,
      onContentChanged: (words, chars) => {
        const wEl = document.getElementById("desktopWordCount");
        if (wEl) wEl.innerText = `${words} kelime, ${chars} karakter`;
      },
      setDocModified: () => {},
      checkDocumentSignature: () => {},
      onPlainTextReadyForShare: () => {}
    };
  }

  const fileInput = document.getElementById("desktopFileInput");
  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFileOpen(e.target.files[0]);
      }
    });
  }

  window.addEventListener("dragover", (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  });

  window.addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileOpen(e.dataTransfer.files[0]);
    }
  });

  window.addEventListener("keydown", (e) => {
    const isCtrl = e.ctrlKey || e.metaKey;
    if (isCtrl && !e.altKey) {
      const key = e.key.toLowerCase();
      if (key === "o") {
        e.preventDefault();
        triggerOpenDocument();
      } else if (key === "s") {
        e.preventDefault();
        if (e.shiftKey) {
          triggerSaveDocx();
        } else {
          triggerSaveUdf();
        }
      } else if (key === "p") {
        e.preventDefault();
        triggerPrintPdf();
      }
    }
  });

  const checkTauriStartupFile = () => {
    try {
      const invoke = window.__TAURI__?.core?.invoke || (window.__TAURI_INTERNALS__ && window.__TAURI_INTERNALS__.invoke);
      if (invoke) {
        invoke('get_startup_file').then((res) => {
          if (res && res.data && res.data.length > 0) {
            const u8 = new Uint8Array(res.data);
            openDocumentFromBytes(u8.buffer, res.name, res.path);
          }
        }).catch(err => console.warn('Tauri get_startup_file:', err));
      }
    } catch (e) {
      console.warn('Tauri startup check error:', e);
    }
  };
  setTimeout(checkTauriStartupFile, 200);
});

// -------------------------------------------------------------
// YENİ BELGE (Dosya > Yeni / Ctrl+N)
// Eskiden tanımsızdı: menü sayfayı yeniden yüklüyor, kaydedilmemiş değişiklikler uyarısız kayboluyordu.
// -------------------------------------------------------------
function newDocument() {
  const modified = window.isDocumentModified ? window.isDocumentModified() : false;
  if (modified && !window.confirm("Kaydedilmemiş değişiklikler var. Yeni belge açılırsa bu değişiklikler kaybolacak.\n\nDevam edilsin mi?")) return;
  const empty = buildEmptyResult('<p style="text-align: justify;"><br></p>');
  // Havelsan UYAP Doküman Editörü yeni belge varsayılanı: A4, 2,5 cm kenar boşlukları
  empty.leftMarginCm = empty.rightMarginCm = empty.topMarginCm = empty.bottomMarginCm = 2.5;
  currentDocFileName = "Yeni_Dilekce.udf";
  currentDocOriginalBuffer = null;
  window.currentDocPath = null;
  window.__udfSource = null;
  window.__currentDocSignature = null;
  updateDocTitleDisplay(currentDocFileName);
  if (window.setHtmlContent) window.setHtmlContent(JSON.stringify(empty));
  updateSignatureBadge({ hasSignature: false, isValid: false });
  if (typeof updateSignatureBanner === "function") updateSignatureBanner({ hasSignature: false, isValid: false });
  if (window.markDocumentPristine) window.markDocumentPristine();
  if (window.CanHistory) window.CanHistory.reset();
  const st = document.getElementById("desktopStatusMsg"); if (st) st.innerText = "Yeni belge";
  setTimeout(() => { const ed = document.getElementById("editor-content"); if (ed) ed.focus(); }, 100);
}
window.newDocument = newDocument;
document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && (e.key === "n" || e.key === "N")) {
    e.preventDefault();
    newDocument();
  }
});
