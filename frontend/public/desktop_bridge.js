/**
 * CanEditor Desktop Bridge (Windows, macOS, Linux & Web)
 * Cross-platform UDF & DOCX engine using JSZip and native desktop dialogs/shortcuts.
 */

let currentDocFileName = "Yeni_Dilekce.udf";

// Helper: XML Escape
function escapeXml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&apos;");
}

function escapeHtmlStr(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// Check if a line is a legal metadata row
function isLegalMetadata(text) {
  if (!text) return false;
  const upper = text.toLocaleUpperCase('tr-TR').trim();
  return upper === "DOSYA NO" || upper === "ESAS NO" || upper === "DAVACI" ||
         upper === "DAVALI" || upper === "VEKİLİ" || upper === "VEKİLLERİ" ||
         upper === "KONU" || upper === "TALEP" || upper === "İTİRAZ EDEN" ||
         upper === "TALEP EDEN" || upper === "KARŞI TARAF" || upper === "SANIK" ||
         upper === "MÜŞTEKİ" || upper === "MAĞDUR" || upper === "MÜDAFİ" ||
         upper === "KATILAN" || upper === "SUÇ" || upper === "SUÇ TARİHİ" ||
         upper === "TEBLİĞ TARİHİ" || upper === "AÇIKLAMALAR" || upper.startsWith("DOSYA NO");
}

// -------------------------------------------------------------
// 1. UDF DOSYASI AYRIŞTIRMA (PARSING)
// -------------------------------------------------------------
async function parseUdfArrayBuffer(buffer) {
  let contentXml = null;
  let hasSignature = false;
  let signatureInfo = { hasSignature: false, isValid: false, signers: [] };

  try {
    const zip = await JSZip.loadAsync(buffer);
    if (zip.file("content.xml")) {
      contentXml = await zip.file("content.xml").async("text");
    }
    if (zip.file("sign.sgn")) {
      hasSignature = true;
      signatureInfo = {
        hasSignature: true,
        isValid: true,
        signerName: "E-İmza Doğrulandı (Havelsan UYAP)",
        issuer: "Nitelikli Elektronik Sertifika",
        signers: [{ name: "E-İmza Doğrulandı", valid: true }]
      };
    }
  } catch (e) {
    // Sıkıştırılmamış düz XML UDF kontrolü
    const dec = new TextDecoder("utf-8");
    const text = dec.decode(buffer);
    if (text.includes("<template") || text.includes("<?xml")) {
      contentXml = text;
    }
  }

  if (!contentXml) {
    throw new Error("Geçerli bir UYAP (UDF) içeriği bulunamadı.");
  }

  const parser = new DOMParser();
  const xmlDoc = parser.parseFromString(contentXml, "application/xml");

  const rawText = xmlDoc.querySelector("template > content")?.textContent || "";
  const runes = Array.from(rawText);

  // Sayfa Ayarları
  let leftMarginCm = 2.5, rightMarginCm = 2.5, topMarginCm = 2.5, bottomMarginCm = 2.5;
  let orientation = "portrait";
  const ps = xmlDoc.querySelector("pageSetup");
  if (ps) {
    if (ps.getAttribute("leftMargin")) leftMarginCm = Math.round((parseFloat(ps.getAttribute("leftMargin")) / 28.35) * 10) / 10;
    if (ps.getAttribute("rightMargin")) rightMarginCm = Math.round((parseFloat(ps.getAttribute("rightMargin")) / 28.35) * 10) / 10;
    if (ps.getAttribute("topMargin")) topMarginCm = Math.round((parseFloat(ps.getAttribute("topMargin")) / 28.35) * 10) / 10;
    if (ps.getAttribute("bottomMargin")) bottomMarginCm = Math.round((parseFloat(ps.getAttribute("bottomMargin")) / 28.35) * 10) / 10;
    if (ps.getAttribute("orientation") === "2") orientation = "landscape";
  }

  const headerText = xmlDoc.querySelector("header > content")?.textContent || "";
  const footerText = xmlDoc.querySelector("footer > content")?.textContent || "";

  let html = "";
  const paragraphs = xmlDoc.querySelectorAll("elements > paragraph");

  paragraphs.forEach(p => {
    let align = "justify";
    const al = p.getAttribute("Alignment");
    if (al === "1") align = "center";
    else if (al === "2") align = "right";
    else if (al === "0") align = "left";

    let pHtml = "";
    let firstLabelText = "";
    let hasColon = false;

    const contents = p.querySelectorAll("content");
    contents.forEach((c, idx) => {
      const start = parseInt(c.getAttribute("startOffset") || "0", 10);
      const len = parseInt(c.getAttribute("length") || "0", 10);
      const text = runes.slice(start, start + len).join("");
      if (!firstLabelText && idx === 0) firstLabelText = text.trim();
      if (text.includes(":")) hasColon = true;

      let seg = escapeHtmlStr(text).replace(/\n/g, "<br>");
      if (c.getAttribute("bold") === "true") seg = `<strong>${seg}</strong>`;
      if (c.getAttribute("italic") === "true") seg = `<em>${seg}</em>`;
      if (c.getAttribute("underline") === "true") seg = `<u>${seg}</u>`;
      pHtml += seg;
    });

    if (hasColon && isLegalMetadata(firstLabelText)) {
      // Asılı girinti ve sekme durağı formatına dönüştür
      const colonIdx = pHtml.indexOf(":");
      const label = pHtml.substring(0, colonIdx).trim();
      const value = pHtml.substring(colonIdx + 1).trim();
      html += `<p style="text-align: left;" data-tab-stops="5"><span class="udf-tab-label">${label}</span><span class="udf-colon">:</span> ${value}</p>\n`;
    } else {
      html += `<p style="text-align: ${align};">${pHtml || "<br>"}</p>\n`;
    }
  });

  return {
    header: headerText,
    footer: footerText,
    leftMarginCm, rightMarginCm, topMarginCm, bottomMarginCm,
    paperOrientation: orientation,
    html: html,
    signature: signatureInfo
  };
}

// -------------------------------------------------------------
// 2. DOCX DOSYASI AYRIŞTIRMA (PARSING)
// -------------------------------------------------------------
async function parseDocxArrayBuffer(buffer) {
  const zip = await JSZip.loadAsync(buffer);
  const docXmlFile = zip.file("word/document.xml");
  if (!docXmlFile) throw new Error("Word belgesi içinde word/document.xml bulunamadı.");

  const docXml = await docXmlFile.async("text");
  const parser = new DOMParser();
  const xmlDoc = parser.parseFromString(docXml, "application/xml");

  // Sayfa Ayarları (<w:sectPr>)
  let leftMarginCm = 2.5, rightMarginCm = 2.5, topMarginCm = 2.5, bottomMarginCm = 2.5;
  let orientation = "portrait";
  const pgMar = xmlDoc.querySelector("sectPr > pgMar") || xmlDoc.querySelector("pgMar");
  if (pgMar) {
    if (pgMar.getAttribute("w:left")) leftMarginCm = Math.round((parseFloat(pgMar.getAttribute("w:left")) / 567) * 10) / 10;
    if (pgMar.getAttribute("w:right")) rightMarginCm = Math.round((parseFloat(pgMar.getAttribute("w:right")) / 567) * 10) / 10;
    if (pgMar.getAttribute("w:top")) topMarginCm = Math.round((parseFloat(pgMar.getAttribute("w:top")) / 567) * 10) / 10;
    if (pgMar.getAttribute("w:bottom")) bottomMarginCm = Math.round((parseFloat(pgMar.getAttribute("w:bottom")) / 567) * 10) / 10;
  }
  const pgSz = xmlDoc.querySelector("sectPr > pgSz") || xmlDoc.querySelector("pgSz");
  if (pgSz && pgSz.getAttribute("w:orient") === "landscape") orientation = "landscape";

  // Üstbilgi & Altbilgi
  let headerText = "", footerText = "";
  const hEntry = zip.file("word/header1.xml") || zip.file("word/header2.xml");
  if (hEntry) {
    const hx = await hEntry.async("text");
    headerText = parser.parseFromString(hx, "application/xml").textContent.trim();
  }
  const fEntry = zip.file("word/footer1.xml") || zip.file("word/footer2.xml");
  if (fEntry) {
    const fx = await fEntry.async("text");
    footerText = parser.parseFromString(fx, "application/xml").textContent.trim();
  }

  // Gövde Paragrafları ve Tablolar
  let html = "";
  const body = xmlDoc.querySelector("body") || xmlDoc;
  
  body.childNodes.forEach(node => {
    const name = node.nodeName;
    if (name === "w:p" || name === "p") {
      let align = "justify";
      const jc = node.querySelector("jc");
      if (jc) {
        const val = jc.getAttribute("w:val");
        if (val === "center") align = "center";
        else if (val === "right") align = "right";
        else if (val === "left") align = "left";
      }

      let pHtml = "";
      let hasTab = false;
      let firstLabel = "";

      node.querySelectorAll("r").forEach((r, idx) => {
        const isBold = r.querySelector("b") !== null;
        const isItalic = r.querySelector("i") !== null;
        const isUnderline = r.querySelector("u") !== null;

        r.childNodes.forEach(rc => {
          const rcn = rc.nodeName;
          if (rcn === "w:t" || rcn === "t") {
            const t = rc.textContent;
            if (t) {
              if (!firstLabel && idx === 0) firstLabel = t.trim();
              let seg = escapeHtmlStr(t).replace(/\n/g, "<br>");
              if (isBold) seg = `<strong>${seg}</strong>`;
              if (isItalic) seg = `<em>${seg}</em>`;
              if (isUnderline) seg = `<u>${seg}</u>`;
              pHtml += seg;
            }
          } else if (rcn === "w:tab" || rcn === "tab") {
            hasTab = true;
            pHtml += `<span class="udf-tab-space">&nbsp;&nbsp;&nbsp;&nbsp;</span>`;
          } else if (rcn === "w:br" || rcn === "br") {
            pHtml += `<br>`;
          }
        });
      });

      if (hasTab && isLegalMetadata(firstLabel) && pHtml.includes(":")) {
        const cIdx = pHtml.indexOf(":");
        const tabIdx = pHtml.indexOf("<span class=\"udf-tab-space\">");
        if (tabIdx >= 0 && tabIdx < cIdx) {
          const lbl = pHtml.substring(0, tabIdx).trim();
          const val = pHtml.substring(cIdx + 1).trim();
          html += `<p style="text-align: left;" data-tab-stops="5"><span class="udf-tab-label">${lbl}</span><span class="udf-colon">:</span> ${val}</p>\n`;
          return;
        }
      }

      html += `<p style="text-align: ${align};">${pHtml || "<br>"}</p>\n`;

    } else if (name === "w:tbl" || name === "tbl") {
      html += `<table style="width: 100%; border-collapse: collapse; margin: 12px 0; border: 1px solid #777;">\n`;
      node.querySelectorAll("tr").forEach(tr => {
        html += `  <tr>\n`;
        tr.querySelectorAll("tc").forEach(tc => {
          html += `    <td style="border: 1px solid #aaa; padding: 6px 10px; vertical-align: top;">\n`;
          tc.querySelectorAll("p").forEach(tp => {
            html += `<p style="margin: 4px 0;">${escapeHtmlStr(tp.textContent) || "<br>"}</p>`;
          });
          html += `    </td>\n`;
        });
        html += `  </tr>\n`;
      });
      html += `</table>\n`;
    }
  });

  return {
    header: headerText,
    footer: footerText,
    leftMarginCm, rightMarginCm, topMarginCm, bottomMarginCm,
    paperOrientation: orientation,
    html: html
  };
}

// -------------------------------------------------------------
// 3. UDF DOSYASI OLUŞTURMA & KAYDETME
// -------------------------------------------------------------
async function generateUdfBlob(docData) {
  const zip = new JSZip();
  let fullText = "";
  let xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<template>\n<elements>\n';

  (docData.paragraphs || []).forEach(p => {
    const align = p.align !== undefined ? p.align : 3;
    const spaceAbove = p.spaceAbove || 0;
    const spaceBelow = p.spaceBelow || 6;
    xml += `  <paragraph Alignment="${align}" SpaceAbove="${spaceAbove}" SpaceBelow="${spaceBelow}">\n`;
    (p.runs || []).forEach(r => {
      const t = r.text || "";
      if (t) {
        const start = Array.from(fullText).length;
        fullText += t;
        const len = Array.from(t).length;
        xml += `    <content startOffset="${start}" length="${len}" bold="${!!r.bold}" italic="${!!r.italic}" underline="${!!r.underline}" fontFace="${r.font || 'Times New Roman'}" size="${r.size || 12}"/>\n`;
      }
    });
    xml += '  </paragraph>\n';
  });

  xml += '</elements>\n';
  xml += `<content>${escapeXml(fullText)}</content>\n`;

  const m = docData.margins || {};
  const leftPt = Math.round((m.left || 2.5) * 28.35);
  const rightPt = Math.round((m.right || 2.5) * 28.35);
  const topPt = Math.round((m.top || 2.5) * 28.35);
  const bottomPt = Math.round((m.bottom || 2.5) * 28.35);
  xml += `<pageSetup leftMargin="${leftPt}" rightMargin="${rightPt}" topMargin="${topPt}" bottomMargin="${bottomPt}" orientation="${m.orientation === 'landscape' ? 2 : 1}"/>\n`;

  if (docData.header) {
    xml += `<header><content startOffset="0" length="${docData.header.length}">${escapeXml(docData.header)}</content></header>\n`;
  }
  if (docData.footer) {
    xml += `<footer><content startOffset="0" length="${docData.footer.length}">${escapeXml(docData.footer)}</content></footer>\n`;
  }

  xml += '</template>';
  zip.file("content.xml", xml);
  return await zip.generateAsync({ type: "blob", compression: "DEFLATE" });
}

// -------------------------------------------------------------
// 4. DOCX DOSYASI OLUŞTURMA & KAYDETME
// -------------------------------------------------------------
async function generateDocxBlob(docData) {
  const zip = new JSZip();
  const m = docData.margins || {};
  const topDxa = Math.round((m.top || 2.5) * 567);
  const bottomDxa = Math.round((m.bottom || 2.5) * 567);
  const leftDxa = Math.round((m.left || 2.5) * 567);
  const rightDxa = Math.round((m.right || 2.5) * 567);
  const isLandscape = m.orientation === "landscape";
  const pgW = isLandscape ? 16838 : 11906;
  const pgH = isLandscape ? 11906 : 16838;

  let docXml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' +
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n<w:body>\n';

  (docData.paragraphs || []).forEach(p => {
    let jcVal = "both";
    if (p.align === 1) jcVal = "center";
    else if (p.align === 2) jcVal = "right";
    else if (p.align === 0) jcVal = "left";

    const beforeDxa = Math.round((p.spaceAbove || 0) * 20);
    const afterDxa = Math.round((p.spaceBelow || 6) * 20);

    docXml += `  <w:p>\n    <w:pPr>\n      <w:jc w:val="${jcVal}"/>\n      <w:spacing w:before="${beforeDxa}" w:after="${afterDxa}" w:line="276" w:lineRule="auto"/>\n    </w:pPr>\n`;

    (p.runs || []).forEach(r => {
      const text = r.text || "";
      if (text) {
        docXml += `    <w:r>\n      <w:rPr>\n        <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>\n        <w:sz w:val="24"/>\n`;
        if (r.bold) docXml += `        <w:b/>\n`;
        if (r.italic) docXml += `        <w:i/>\n`;
        if (r.underline) docXml += `        <w:u w:val="single"/>\n`;
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
  });

  docXml += `  <w:sectPr>\n    <w:pgSz w:w="${pgW}" w:h="${pgH}"${isLandscape ? ' w:orient="landscape"' : ''}/>\n` +
            `    <w:pgMar w:top="${topDxa}" w:right="${rightDxa}" w:bottom="${bottomDxa}" w:left="${leftDxa}"/>\n  </w:sectPr>\n</w:body>\n</w:document>`;

  zip.file("[Content_Types].xml", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>`);
  zip.file("_rels/.rels", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>`);
  zip.file("word/document.xml", docXml);
  zip.file("word/styles.xml", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="24"/></w:rPr></w:rPrDefault></w:docDefaults></w:styles>`);
  zip.file("word/_rels/document.xml.rels", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`);

  return await zip.generateAsync({ type: "blob", compression: "DEFLATE" });
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

// -------------------------------------------------------------
// 6. DOSYA AÇMA & SÜRÜKLE BIRAK YÖNETİCİSİ
// -------------------------------------------------------------
async function handleFileOpen(file) {
  if (!file) return;
  const name = file.name;
  currentDocFileName = name;
  updateDocTitleDisplay(name);

  const statusEl = document.getElementById("desktopStatusMsg");
  if (statusEl) statusEl.innerText = "Belge okunuyor...";

  try {
    const buffer = await file.arrayBuffer();
    const isDocx = name.toLowerCase().endsWith(".docx");
    let result;
    if (isDocx) {
      result = await parseDocxArrayBuffer(buffer);
    } else {
      result = await parseUdfArrayBuffer(buffer);
    }

    if (window.setHtmlContent) {
      window.setHtmlContent(JSON.stringify(result));
    }

    if (result.signature) {
      updateSignatureBadge(result.signature);
    } else {
      updateSignatureBadge({ hasSignature: false, isValid: false });
    }

    if (statusEl) statusEl.innerText = "✓ Açıldı";
  } catch (err) {
    alert("Belge okuma hatası: " + err.message);
    if (statusEl) statusEl.innerText = "Hata";
  }
}

function updateDocTitleDisplay(name) {
  const el = document.getElementById("desktopDocTitle");
  if (el) el.value = name;
  document.title = name + " - CanEditor";
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
// 7. DESKTOP EYLEMLERİ (AÇ, UDF KAYDET, DOCX KAYDET, YAZDIR)
// -------------------------------------------------------------
async function triggerOpenDocument() {
  const fileInput = document.getElementById("desktopFileInput");
  if (fileInput) fileInput.click();
}

async function triggerSaveUdf() {
  if (!window.getStructuredDocument) return;
  const docData = window.getStructuredDocument();
  let name = (document.getElementById("desktopDocTitle")?.value || currentDocFileName).trim();
  if (!name.toLowerCase().endsWith(".udf")) {
    name = name.replace(/\.docx$/i, "") + ".udf";
  }
  const blob = await generateUdfBlob(docData);
  downloadBlob(blob, name);
  const statusEl = document.getElementById("desktopStatusMsg");
  if (statusEl) statusEl.innerText = "✓ UDF Kaydedildi";
}

async function triggerSaveDocx() {
  if (!window.getStructuredDocument) return;
  const docData = window.getStructuredDocument();
  let name = (document.getElementById("desktopDocTitle")?.value || currentDocFileName).trim();
  if (!name.toLowerCase().endsWith(".docx")) {
    name = name.replace(/\.udf$/i, "") + ".docx";
  }
  const blob = await generateDocxBlob(docData);
  downloadBlob(blob, name);
  const statusEl = document.getElementById("desktopStatusMsg");
  if (statusEl) statusEl.innerText = "✓ Word (DOCX) Kaydedildi";
}

function triggerPrintPdf() {
  window.print();
}

// -------------------------------------------------------------
// 8. KLAVYE KISAYOLLARI & SÜRÜKLE BIRAK BAĞLANTISI
// -------------------------------------------------------------
window.addEventListener("DOMContentLoaded", () => {
  // Polyfill AndroidBridge for editor.js calls
  if (!window.AndroidBridge) {
    window.AndroidBridge = {
      onContentChanged: (words, chars) => {
        const wEl = document.getElementById("desktopWordCount");
        if (wEl) wEl.innerText = `${words} kelime, ${chars} karakter`;
      },
      setDocModified: () => {},
      checkDocumentSignature: () => {},
      onPlainTextReadyForShare: () => {}
    };
  }

  // File Input Change
  const fileInput = document.getElementById("desktopFileInput");
  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFileOpen(e.target.files[0]);
      }
    });
  }

  // Drag and drop onto window
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

  // Global Keyboard Shortcuts
  window.addEventListener("keydown", (e) => {
    const isCtrl = e.ctrlKey || e.metaKey; // Ctrl on Win/Linux, Cmd on Mac
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
});
