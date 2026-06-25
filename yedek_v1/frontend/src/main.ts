let globalXmlDoc: Document | null = null;
let currentFileName: string = "duzenlenmis_dilekce.udf";

// Renk Dönüşüm Motorları
function argbToHex(argbStr: string | null): string {
  if (!argbStr) return "inherit";
  const argb = parseInt(argbStr, 10);
  if (isNaN(argb)) return "inherit";
  return "#" + (argb & 0x00FFFFFF).toString(16).padStart(6, '0');
}

function hexToArgb(hex: string): string {
  let r=0, g=0, b=0;
  if (hex.startsWith('#')) {
    r = parseInt(hex.substring(1,3), 16) || 0;
    g = parseInt(hex.substring(3,5), 16) || 0;
    b = parseInt(hex.substring(5,7), 16) || 0;
  } else if (hex.startsWith('rgb')) {
    const matches = hex.match(/\d+/g);
    if (matches) { r = parseInt(matches[0]); g = parseInt(matches[1]); b = parseInt(matches[2]); }
  } else {
    return "-16777216"; // Varsayılan siyah
  }
  const argb = (0xFF000000 | (r << 16) | (g << 8) | b) >> 0;
  return argb.toString();
}

function mapHtmlSizeToPt(size: string): string {
  const mapping: Record<string, string> = { '1':'8', '2':'10', '3':'12', '4':'14', '5':'18', '6':'24', '7':'36' };
  return mapping[size] || size.replace('pt','').replace('px','');
}

// Araç Çubuğu Butonları
document.getElementById('menuOpen')?.addEventListener('click', () => document.getElementById('fileInput')?.click());

document.querySelectorAll('.tool-btn[data-command]').forEach(btn => {
  btn.addEventListener('click', (e) => {
    e.preventDefault();
    const command = btn.getAttribute('data-command');
    if (command) { document.execCommand(command, false, undefined); document.getElementById('body-zone')?.focus(); }
  });
});

document.getElementById('fontFamily')?.addEventListener('change', (e) => {
  document.execCommand('fontName', false, (e.target as HTMLSelectElement).value);
});
document.getElementById('fontSize')?.addEventListener('change', (e) => {
  document.execCommand('fontSize', false, (e.target as HTMLSelectElement).value);
});
document.getElementById('textColor')?.addEventListener('input', (e) => {
  document.execCommand('foreColor', false, (e.target as HTMLInputElement).value);
});

// === UDF YÜKLEME VE EKRANA ÇİZME ===
document.getElementById('fileInput')?.addEventListener('change', async (e) => {
  const fileInput = e.target as HTMLInputElement;
  const bodyZone = document.getElementById('body-zone');
  if (!fileInput.files || fileInput.files.length === 0 || !bodyZone) return;
  
  const file = fileInput.files[0];
  currentFileName = file.name;
  bodyZone.innerText = "UYAP UDF Ayrıştırılıyor...";
  
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch('http://127.0.0.1:3000/api/upload_udf', { method: 'POST', body: formData });
    const data = await response.json();

    if (data.success) {
      const parser = new DOMParser();
      globalXmlDoc = parser.parseFromString(data.content, "application/xml");
      const rawText = globalXmlDoc.querySelector("template > content")?.textContent || "";
      const runes = Array.from(rawText);

      // XML Yedekleme
      globalXmlDoc.querySelectorAll("content, image, tab, space, field").forEach(item => {
        const start = parseInt(item.getAttribute("startOffset") || "0");
        const len = parseInt(item.getAttribute("length") || "0");
        if (item.tagName === "content") item.setAttribute("data-text", runes.slice(start, start + len).join(""));
      });

      document.getElementById('body-zone')!.innerHTML = "";
      document.getElementById('header-zone')!.innerHTML = "";
      document.getElementById('footer-zone')!.innerHTML = "";

      const elements = globalXmlDoc.querySelector("elements");
      const renderNodes = (nodes: NodeListOf<Element>, targetId: string) => {
        const target = document.getElementById(targetId);
        nodes.forEach(child => {
          if (child.tagName === "paragraph") {
            const p = document.createElement("div");
            p.style.minHeight = "1.15em"; 
            
            const align = child.getAttribute("Alignment");
            if (align === "1") p.style.textAlign = "center";
            else if (align === "2") p.style.textAlign = "right";
            else if (align === "3") p.style.textAlign = "justify";

            if (child.getAttribute("LeftIndent")) p.style.marginLeft = `${child.getAttribute("LeftIndent")}pt`;
            if (child.getAttribute("SpaceAbove")) p.style.marginTop = `${child.getAttribute("SpaceAbove")}pt`;

            child.querySelectorAll("content").forEach(ct => {
              const textSegment = ct.getAttribute("data-text") || "";
              if (textSegment.length > 0) {
                if (textSegment === "\n") { p.appendChild(document.createElement("br")); return; }
                const span = document.createElement("span");
                span.textContent = textSegment.replace(/\n/g, ''); 
                
                if (ct.getAttribute("bold") === "true") span.style.fontWeight = "bold";
                if (ct.getAttribute("italic") === "true") span.style.fontStyle = "italic";
                if (ct.getAttribute("underline") === "true") span.style.textDecoration = "underline";
                if (ct.getAttribute("size")) span.style.fontSize = `${ct.getAttribute("size")}pt`;
                if (ct.getAttribute("foreground")) span.style.color = argbToHex(ct.getAttribute("foreground"));
                if (ct.getAttribute("family")) span.style.fontFamily = ct.getAttribute("family")!;

                p.appendChild(span);
              }
            });
            target?.appendChild(p);
          }
        });
      };

      if (elements) {
        renderNodes(elements.querySelectorAll(":scope > header > paragraph"), 'header-zone');
        renderNodes(elements.querySelectorAll(":scope > paragraph"), 'body-zone');
        renderNodes(elements.querySelectorAll(":scope > footer > paragraph"), 'footer-zone');
      }
    } else {
      bodyZone.innerText = "Hata:\n" + data.error;
    }
  } catch (err) {
    bodyZone.innerText = "Bağlantı hatası: " + err;
  }
});

// === YENİ XML/HTML DÜĞÜM TARAYICISI (Klavyeyi bozmayan asıl motor) ===
function extractTextAndStyles(node: ChildNode, currentStyles: any): any[] {
  let results: any[] = [];
  if (node.nodeType === Node.TEXT_NODE) {
    if (node.textContent && (node.textContent.trim().length > 0 || node.textContent.includes(" "))) {
      results.push({ text: node.textContent, styles: { ...currentStyles } });
    }
  } else if (node.nodeType === Node.ELEMENT_NODE) {
    const el = node as HTMLElement;
    let newStyles = { ...currentStyles };
    const tag = el.tagName.toLowerCase();
    
    if (tag === 'b' || tag === 'strong' || el.style.fontWeight === 'bold') newStyles.bold = true;
    if (tag === 'i' || tag === 'em' || el.style.fontStyle === 'italic') newStyles.italic = true;
    if (tag === 'u' || el.style.textDecoration === 'underline') newStyles.underline = true;
    if (tag === 'font') {
      if (el.getAttribute('color')) newStyles.color = hexToArgb(el.getAttribute('color')!);
      if (el.getAttribute('size')) newStyles.size = mapHtmlSizeToPt(el.getAttribute('size')!);
    }
    if (el.style.color) newStyles.color = hexToArgb(el.style.color);
    if (el.style.fontSize) newStyles.size = mapHtmlSizeToPt(el.style.fontSize);

    if (tag === 'br') results.push({ text: '\n', styles: newStyles });

    el.childNodes.forEach(child => {
      results = results.concat(extractTextAndStyles(child, newStyles));
    });
  }
  return results;
}

// === UDF KAYDETME ===
document.getElementById('menuSaveUdf')?.addEventListener('click', async () => {
  if (!globalXmlDoc) { alert("Açık bir dosya yok."); return; }
  const bodyZone = document.getElementById('body-zone');
  const elementsRoot = globalXmlDoc.querySelector("elements");
  if (!bodyZone || !elementsRoot) return;

  // Sadece GÖVDE paragraflarını temizle
  Array.from(elementsRoot.children).forEach(child => {
    if (child.tagName === "paragraph") elementsRoot.removeChild(child);
  });

  Array.from(bodyZone.childNodes).forEach(htmlNode => {
    if (htmlNode.nodeName === "DIV" || htmlNode.nodeName === "P") {
      const p = globalXmlDoc!.createElement("paragraph");
      p.setAttribute("Alignment", (htmlNode as HTMLElement).style.textAlign === "center" ? "1" : ((htmlNode as HTMLElement).style.textAlign === "right" ? "2" : "0"));
      p.setAttribute("SpaceBelow", "0.0");
      p.setAttribute("LeftIndent", "0.0");

      const fragments = extractTextAndStyles(htmlNode, {});
      fragments.forEach(frag => {
        if (frag.text === "\n") {
           const nl = globalXmlDoc!.createElement("content");
           nl.setAttribute("data-text", "\n");
           p.appendChild(nl);
        } else {
           const ct = globalXmlDoc!.createElement("content");
           ct.setAttribute("family", "Times New Roman");
           ct.setAttribute("size", frag.styles.size || "12");
           ct.setAttribute("data-text", frag.text);
           if (frag.styles.bold) ct.setAttribute("bold", "true");
           if (frag.styles.italic) ct.setAttribute("italic", "true");
           if (frag.styles.underline) ct.setAttribute("underline", "true");
           if (frag.styles.color) ct.setAttribute("foreground", frag.styles.color);
           p.appendChild(ct);
        }
      });

      // UYAP zorunlu paragraf sonu
      if (fragments.length === 0 || fragments[fragments.length-1].text !== "\n") {
         const nl = globalXmlDoc!.createElement("content");
         nl.setAttribute("data-text", "\n");
         p.appendChild(nl);
      }

      const footer = globalXmlDoc!.querySelector("footer");
      if (footer) elementsRoot.insertBefore(p, footer);
      else elementsRoot.appendChild(p);
    }
  });

  // Ofset Matematik Motoru
  let globalOffset = 0;
  let newCdataText = "";
  globalXmlDoc.querySelectorAll("content, image, tab, space, field").forEach(item => {
    const text = item.getAttribute("data-text") || "";
    const len = Array.from(text).length; 
    item.setAttribute("startOffset", globalOffset.toString());
    item.setAttribute("length", len.toString());
    newCdataText += text;
    globalOffset += len;
    item.removeAttribute("data-text"); 
  });

  const cdataNode = globalXmlDoc.createCDATASection(newCdataText);
  const templateContent = globalXmlDoc.querySelector("template > content");
  if (templateContent) {
    templateContent.innerHTML = "";
    templateContent.appendChild(cdataNode);
  }

  try {
    const serializer = new XMLSerializer();
    const finalXml = serializer.serializeToString(globalXmlDoc);
    const response = await fetch('http://127.0.0.1:3000/api/download_udf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ xml_content: finalXml })
    });

    if (response.ok) {
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = currentFileName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    }
  } catch (err) {
    alert("Bağlantı hatası: " + err);
  }
});

// === PDF OLARAK KAYDET (Tarayıcının yazıcı motoruyla 1:1 çıktı) ===
document.getElementById('menuSavePdf')?.addEventListener('click', () => {
  window.print();
});
