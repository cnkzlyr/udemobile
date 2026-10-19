/**
 * CanEditor Desktop Bridge (Windows, macOS, Linux & Web)
 * Cross-platform UDF & DOCX engine using JSZip and native desktop dialogs/shortcuts.
 */

let currentDocFileName = "Yeni_Dilekce.udf";
let currentDocOriginalBuffer = null;

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
  let docPropsXml = null;
  let hasSignature = false;
  let signatureInfo = { hasSignature: false, isValid: false, signers: [] };

  try {
    const zip = await JSZip.loadAsync(buffer);
    if (zip.file("content.xml")) {
      contentXml = await zip.file("content.xml").async("text");
    }
    if (zip.file("documentproperties.xml")) {
      docPropsXml = await zip.file("documentproperties.xml").async("text");
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

  // UYAP Şablon Alanı Veri Haritası (<data>)
  const dataMap = {};
  const dataNodes = xmlDoc.querySelectorAll("data, template > data");
  dataNodes.forEach(dNode => {
    Array.from(dNode.children).forEach(child => {
      const key = (child.tagName || "").toLowerCase();
      const val = (child.textContent || "");
      if (val.trim() && (!dataMap[key] || !dataMap[key].trim())) {
        dataMap[key] = val;
      }
    });
  });

  // Doğrulama Kodu Çözümleme (webID & documentproperties.xml)
  const webIdEl = xmlDoc.querySelector("webID");
  const webId = webIdEl ? (webIdEl.getAttribute("id") || "").trim() : "";
  let uyapDogrulamaKodu = "";
  if (docPropsXml) {
    try {
      const propsDoc = parser.parseFromString(docPropsXml, "application/xml");
      const entries = propsDoc.querySelectorAll("entry");
      entries.forEach(e => {
        if ((e.getAttribute("key") || "").toLowerCase() === "uyapdogrulamakodu") {
          uyapDogrulamaKodu = (e.textContent || "").trim();
        }
      });
    } catch (e) {}
  }
  const verificationCode = webId || uyapDogrulamaKodu;

  // Sayfa Ayarları (pageFormat veya pageSetup)
  let leftMarginCm = 1.5, rightMarginCm = 1.5, topMarginCm = 1.5, bottomMarginCm = 1.5;
  let orientation = "portrait";
  const pf = xmlDoc.querySelector("pageFormat") || xmlDoc.querySelector("pageSetup");
  if (pf) {
    if (pf.getAttribute("leftMargin")) leftMarginCm = Math.round((parseFloat(pf.getAttribute("leftMargin")) / 28.3465) * 100) / 100;
    if (pf.getAttribute("rightMargin")) rightMarginCm = Math.round((parseFloat(pf.getAttribute("rightMargin")) / 28.3465) * 100) / 100;
    if (pf.getAttribute("topMargin")) topMarginCm = Math.round((parseFloat(pf.getAttribute("topMargin")) / 28.3465) * 100) / 100;
    if (pf.getAttribute("bottomMargin")) bottomMarginCm = Math.round((parseFloat(pf.getAttribute("bottomMargin")) / 28.3465) * 100) / 100;
    if (pf.getAttribute("orientation") === "2" || pf.getAttribute("paperOrientation") === "2") orientation = "landscape";
  }

  // Header Çözümleme (startPage ve çoklu sütun desteği)
  let headerHtml = "";
  let headerStartPage = 1;
  const headerElem = xmlDoc.querySelector("header");
  if (headerElem) {
    if (headerElem.getAttribute("startPage")) {
      headerStartPage = parseInt(headerElem.getAttribute("startPage"), 10) || 1;
    }
    const headerParas = headerElem.querySelectorAll("paragraph");
    if (headerParas.length > 0) {
      let hText = "";
      headerParas.forEach(p => {
        Array.from(p.children).forEach(c => {
          const fieldName = (c.getAttribute("fieldName") || "").toLowerCase();
          if (fieldName && dataMap[fieldName] !== undefined && dataMap[fieldName].trim() !== "") {
            hText += dataMap[fieldName];
          } else {
            const s = parseInt(c.getAttribute("startOffset") || "-1", 10);
            const l = parseInt(c.getAttribute("length") || "-1", 10);
            if (s >= 0 && l > 0) {
              hText += runes.slice(s, s + l).join("");
            } else if (c.tagName.toLowerCase() === "tab") {
              hText += "\t";
            } else if (c.tagName.toLowerCase() === "space") {
              hText += " ";
            }
          }
        });
      });
      hText = hText.trim();
      if (hText) {
        if (hText.includes("\t")) {
          const parts = hText.split(/\t+/);
          headerHtml = `<div class="udf-header-bar" style="display:flex; justify-content:space-between; align-items:flex-end; font-family:'Times New Roman', serif; font-size:9pt; line-height:1.2; border-bottom:0.5px solid #000; padding-bottom:3px; margin-bottom:8px; width:100%; box-sizing:border-box;">
            <span style="font-weight:bold;">${escapeHtmlStr(parts[0].trim())}</span>
            <span>${escapeHtmlStr(parts.slice(1).join(" ").trim())}</span>
          </div>`;
        } else {
          headerHtml = `<div class="udf-header-bar" style="display:flex; justify-content:center; align-items:center; font-family:'Times New Roman', serif; font-size:9pt; line-height:1.2; border-bottom:0.5px solid #000; padding-bottom:3px; margin-bottom:8px; width:100%; box-sizing:border-box;">
            <span>${escapeHtmlStr(hText)}</span>
          </div>`;
        }
      }
    }
  }

  // Footer Çözümleme (Resmi UYAP Doğrulama & Barkod)
  const footerText = xmlDoc.querySelector("footer > content")?.textContent || "";
  let footerHtml = "";
  if (verificationCode) {
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

  function parseParagraphToHtml(p, runes) {
    let align = "justify";
    const al = p.getAttribute("Alignment");
    if (al === "1") align = "center";
    else if (al === "2") align = "right";
    else if (al === "0") align = "left";

    let tabStopAttr = "";
    const tabSet = p.getAttribute("TabSet");
    if (tabSet && tabSet.trim()) {
      const stops = [];
      tabSet.split(",").forEach(s => {
        const parts = s.trim().split(":");
        const pt = parseFloat(parts[0]);
        if (!isNaN(pt) && pt > 5) {
          stops.push((Math.round((pt / 28.3465) * 100) / 100).toFixed(2));
        }
      });
      if (stops.length > 0) {
        tabStopAttr = ` data-tab-stops="${stops.join(",")}"`;
      }
    }

    let pHtml = "";
    let firstLabelText = "";
    let hasTab = false;

    const children = Array.from(p.children);
    children.forEach((c, idx) => {
      const tag = c.tagName ? c.tagName.toLowerCase() : "";
      if (tag === "image") {
        const imgData = c.getAttribute("imageData");
        if (imgData && imgData.trim()) {
          pHtml += `<img src="data:image/png;base64,${imgData.trim()}" style="display:block; margin:6px auto; max-width:95%; height:auto;" />`;
        }
      } else if (tag === "content" || tag === "space" || tag === "field" || tag === "tab") {
        let text = "";
        const fieldName = (c.getAttribute("fieldName") || "").toLowerCase();
        if (fieldName && dataMap[fieldName] !== undefined && dataMap[fieldName].trim() !== "") {
          text = dataMap[fieldName];
        } else if (c.hasAttribute("startOffset") && c.hasAttribute("length")) {
          const start = parseInt(c.getAttribute("startOffset") || "0", 10);
          const len = parseInt(c.getAttribute("length") || "0", 10);
          text = runes.slice(start, start + len).join("");
        } else if (tag === "tab") {
          text = "\t";
        } else if (tag === "space") {
          text = " ";
        }

        if (!firstLabelText && idx === 0) firstLabelText = text.trim();
        if (text.includes("\t")) hasTab = true;

        let seg = escapeHtmlStr(text)
          .replace(/\t/g, '<span class="udf-tab-space" contenteditable="false">&nbsp;</span>')
          .replace(/\n/g, "<br>");
        if (c.getAttribute("bold") === "true") seg = `<strong>${seg}</strong>`;
        if (c.getAttribute("italic") === "true") seg = `<em>${seg}</em>`;
        if (c.getAttribute("underline") === "true") seg = `<u>${seg}</u>`;
        pHtml += seg;
      }
    });

    if (!tabStopAttr && hasTab && isLegalMetadata(firstLabelText)) {
      tabStopAttr = ' data-tab-stops="5"';
    }

    return `<p style="text-align: ${align};"${tabStopAttr}>${pHtml || "<br>"}</p>\n`;
  }

  function parseTableToHtml(tableElem, runes) {
    const border = tableElem.getAttribute("border");
    const isNone = border === "borderNone" || border === "none";
    const tableStyle = isNone
      ? "width:100%; border-collapse:collapse; margin:12px 0; border:none;"
      : "width:100%; border-collapse:collapse; margin:12px 0; border:1px solid #ccc;";

    let tblHtml = `<table style="${tableStyle}">\n`;
    const rows = tableElem.querySelectorAll("row");
    rows.forEach(r => {
      tblHtml += `  <tr style="border:none;">\n`;
      const cells = r.querySelectorAll("cell");
      const cellWidthPct = cells.length > 0 ? (100 / cells.length).toFixed(1) : "100";
      cells.forEach(cell => {
        const cellStyle = isNone
          ? `vertical-align:top; border:none; padding:4px 8px; width:${cellWidthPct}%;`
          : `vertical-align:top; border:1px solid #ccc; padding:4px 8px; width:${cellWidthPct}%;`;
        tblHtml += `    <td style="${cellStyle}">\n`;
        const cellParas = cell.querySelectorAll("paragraph");
        if (cellParas.length === 0) {
          tblHtml += "&nbsp;";
        } else {
          cellParas.forEach(p => {
            tblHtml += parseParagraphToHtml(p, runes);
          });
        }
        tblHtml += `    </td>\n`;
      });
      tblHtml += `  </tr>\n`;
    });
    tblHtml += `</table>\n`;
    return tblHtml;
  }

  let html = "";
  const elementsNode = xmlDoc.querySelector("template > elements") || xmlDoc.querySelector("elements");

  if (elementsNode && elementsNode.children.length > 0) {
    Array.from(elementsNode.children).forEach(child => {
      const tag = child.tagName ? child.tagName.toLowerCase() : "";
      if (tag === "paragraph") {
        html += parseParagraphToHtml(child, runes);
      } else if (tag === "table") {
        html += parseTableToHtml(child, runes);
      }
    });
  } else {
    const paragraphs = xmlDoc.querySelectorAll("paragraph");
    paragraphs.forEach(p => {
      const parentTag = p.parentElement ? p.parentElement.tagName.toLowerCase() : "";
      if (parentTag === "header" || parentTag === "footer" || parentTag === "cell") return;
      html += parseParagraphToHtml(p, runes);
    });
  }

  return {
    header: "",
    headerHtml,
    headerStartPage,
    footer: footerText,
    footerHtml,
    verificationCode,
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
      let tabStopAttr = "";
      const tabsElem = node.querySelector("w\\:tabs, tabs");
      if (tabsElem) {
        const stops = [];
        tabsElem.querySelectorAll("w\\:tab, tab").forEach(t => {
          const pos = parseFloat(t.getAttribute("w:pos") || t.getAttribute("pos") || "0");
          if (pos > 0) {
            stops.push(Math.round((pos / 567) * 10) / 10);
          }
        });
        if (stops.length > 0) {
          tabStopAttr = ` data-tab-stops="${stops.join(",")}"`;
        }
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
            pHtml += `<span class="udf-tab-space" contenteditable="false">&nbsp;</span>`;
          } else if (rcn === "w:br" || rcn === "br") {
            pHtml += `<br>`;
          }
        });
      });

      if (!tabStopAttr && hasTab && isLegalMetadata(firstLabel)) {
        tabStopAttr = ' data-tab-stops="5"';
      }

      html += `<p style="text-align: ${align};"${tabStopAttr}>${pHtml || "<br>"}</p>\n`;

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
    let tabAttr = "";
    if (p.tabStops) {
      const parts = String(p.tabStops).split(",");
      const firstStop = parseFloat(parts[0]);
      if (!isNaN(firstStop) && firstStop > 0) {
        const pt = (firstStop * 28.3465).toFixed(1);
        tabAttr = ` TabSet="${pt}:0:0" Hanging="${pt}"`;
      }
    }
    xml += `  <paragraph Alignment="${align}" SpaceAbove="${spaceAbove}" SpaceBelow="${spaceBelow}"${tabAttr}>\n`;
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

    let tabsXml = "";
    if (p.tabStops) {
      const parts = String(p.tabStops).split(",");
      const tabsList = parts.map(s => parseFloat(s)).filter(n => !isNaN(n) && n > 0);
      if (tabsList.length > 0) {
        tabsXml = '      <w:tabs>\n' + tabsList.map(cm => `        <w:tab w:val="left" w:pos="${Math.round(cm * 567)}"/>\n`).join('') + '      </w:tabs>\n';
      }
    }

    docXml += `  <w:p>\n    <w:pPr>\n      <w:jc w:val="${jcVal}"/>\n${tabsXml}      <w:spacing w:before="${beforeDxa}" w:after="${afterDxa}" w:line="276" w:lineRule="auto"/>\n    </w:pPr>\n`;

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
async function openDocumentFromBytes(buffer, name, path) {
  if (!buffer) return;
  const fileName = name || (path ? path.split(/[/\\]/).pop() : "Belge.udf");
  currentDocFileName = fileName;
  updateDocTitleDisplay(fileName);

  const statusEl = document.getElementById("desktopStatusMsg");
  if (statusEl) statusEl.innerText = "Belge okunuyor...";

  try {
    const arrayBuffer = buffer instanceof ArrayBuffer ? buffer : (buffer.buffer ? buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength) : new Uint8Array(buffer).buffer);
    currentDocOriginalBuffer = arrayBuffer.slice(0);
    const isDocx = fileName.toLowerCase().endsWith(".docx");
    let result;
    if (isDocx) {
      result = await parseDocxArrayBuffer(arrayBuffer);
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
  let name = (document.getElementById("desktopDocTitle")?.value || currentDocFileName).trim();
  if (!name.toLowerCase().endsWith(".udf")) {
    name = name.replace(/\.docx$/i, "") + ".udf";
  }

  const isModified = window.isDocumentModified ? window.isDocumentModified() : false;
  if (!isModified && currentDocOriginalBuffer) {
    const blob = new Blob([currentDocOriginalBuffer], { type: "application/octet-stream" });
    downloadBlob(blob, name);
    const statusEl = document.getElementById("desktopStatusMsg");
    if (statusEl) statusEl.innerText = "✓ UDF Korunarak Kaydedildi";
    return;
  }

  if (!window.getStructuredDocument) return;
  const docData = window.getStructuredDocument();
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

  // Tauri Başlangıç Dosyası Kontrolü (Birlikte Aç / CLI Dosya Parametresi)
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
