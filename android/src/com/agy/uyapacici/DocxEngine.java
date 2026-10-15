package com.agy.uyapacici;

import org.json.JSONArray;
import org.json.JSONObject;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Enumeration;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;

public class DocxEngine {

    /**
     * Dosyanın geçerli bir Microsoft Word (.docx) belgesi olup olmadığını tespit eder.
     */
    public static boolean isDocxFile(File file) {
        if (file == null || !file.exists() || file.length() < 10) return false;
        String name = file.getName().toLowerCase(Locale.ROOT);
        if (name.endsWith(".docx") || name.endsWith(".docx.udf")) return true;
        try (ZipFile zip = new ZipFile(file)) {
            return zip.getEntry("word/document.xml") != null;
        } catch (Exception ignored) {
            return false;
        }
    }

    /**
     * .docx dosyasını okuyup mobil editör için yapılandırılmış JSON/HTML formatına dönüştürür.
     */
    public static String readDocxToHtml(File file) throws Exception {
        String docXml = null;
        String headerXml = null;
        String footerXml = null;

        try (ZipFile zip = new ZipFile(file)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                String name = entry.getName();
                if ("word/document.xml".equals(name)) {
                    docXml = readZipEntryString(zip, entry);
                } else if (headerXml == null && (name.startsWith("word/header") && name.endsWith(".xml"))) {
                    headerXml = readZipEntryString(zip, entry);
                } else if (footerXml == null && (name.startsWith("word/footer") && name.endsWith(".xml"))) {
                    footerXml = readZipEntryString(zip, entry);
                }
            }
        }

        if (docXml == null) {
            throw new IllegalStateException("DOCX içinde word/document.xml bulunamadı.");
        }

        return parseDocxToStructuredJson(docXml, headerXml, footerXml);
    }

    private static String readZipEntryString(ZipFile zip, ZipEntry entry) throws Exception {
        try (InputStream is = zip.getInputStream(entry);
             ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = is.read(buf)) != -1) {
                baos.write(buf, 0, n);
            }
            return new String(baos.toByteArray(), StandardCharsets.UTF_8);
        }
    }

    private static String parseDocxToStructuredJson(String docXml, String headerXml, String footerXml) {
        try {
            DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
            dbf.setNamespaceAware(false);
            DocumentBuilder db = dbf.newDocumentBuilder();
            Document doc = db.parse(new ByteArrayInputStream(docXml.getBytes(StandardCharsets.UTF_8)));

            double leftMarginCm = 2.5;
            double rightMarginCm = 2.5;
            double topMarginCm = 2.5;
            double bottomMarginCm = 2.5;
            double headerMarginCm = 1.25;
            double footerMarginCm = 1.25;
            String orientation = "portrait";

            // Sayfa Ayarları (<w:sectPr>)
            NodeList sectPrList = doc.getElementsByTagName("w:sectPr");
            if (sectPrList.getLength() > 0) {
                Element sectPr = (Element) sectPrList.item(sectPrList.getLength() - 1);
                NodeList pgMarList = sectPr.getElementsByTagName("w:pgMar");
                if (pgMarList.getLength() > 0) {
                    Element pgMar = (Element) pgMarList.item(0);
                    if (pgMar.hasAttribute("w:left")) leftMarginCm = parseDxaToCm(pgMar.getAttribute("w:left"), 2.5);
                    if (pgMar.hasAttribute("w:right")) rightMarginCm = parseDxaToCm(pgMar.getAttribute("w:right"), 2.5);
                    if (pgMar.hasAttribute("w:top")) topMarginCm = parseDxaToCm(pgMar.getAttribute("w:top"), 2.5);
                    if (pgMar.hasAttribute("w:bottom")) bottomMarginCm = parseDxaToCm(pgMar.getAttribute("w:bottom"), 2.5);
                    if (pgMar.hasAttribute("w:header")) headerMarginCm = parseDxaToCm(pgMar.getAttribute("w:header"), 1.25);
                    if (pgMar.hasAttribute("w:footer")) footerMarginCm = parseDxaToCm(pgMar.getAttribute("w:footer"), 1.25);
                }
                NodeList pgSzList = sectPr.getElementsByTagName("w:pgSz");
                if (pgSzList.getLength() > 0) {
                    Element pgSz = (Element) pgSzList.item(0);
                    if ("landscape".equalsIgnoreCase(pgSz.getAttribute("w:orient"))) {
                        orientation = "landscape";
                    }
                }
            }

            // Üstbilgi & Altbilgi
            String headerText = "";
            String headerHtml = "";
            if (headerXml != null) {
                headerText = extractSimpleTextFromXml(headerXml, db);
                headerHtml = headerText;
            }

            String footerText = "";
            String footerHtml = "";
            if (footerXml != null) {
                footerText = extractSimpleTextFromXml(footerXml, db);
                footerHtml = footerText;
            }

            // Gövde Elementlerini Oku (Paragraflar ve Tablolar)
            NodeList bodyList = doc.getElementsByTagName("w:body");
            StringBuilder html = new StringBuilder();

            if (bodyList.getLength() > 0) {
                Element body = (Element) bodyList.item(0);
                Node child = body.getFirstChild();
                while (child != null) {
                    if (child.getNodeType() == Node.ELEMENT_NODE) {
                        String nodeName = child.getNodeName();
                        if ("w:p".equals(nodeName) || "p".equals(nodeName)) {
                            parseParagraphElement((Element) child, html);
                        } else if ("w:tbl".equals(nodeName) || "tbl".equals(nodeName)) {
                            parseTableElement((Element) child, html);
                        }
                    }
                    child = child.getNextSibling();
                }
            }

            // Eğer w:body doğrudan bulunamadıysa fallback: tüm w:p'leri tara
            if (html.length() == 0) {
                NodeList pList = doc.getElementsByTagName("w:p");
                if (pList.getLength() == 0) pList = doc.getElementsByTagName("p");
                for (int i = 0; i < pList.getLength(); i++) {
                    parseParagraphElement((Element) pList.item(i), html);
                }
            }

            // Son çare: regex ile metin ayıklama
            if (html.length() == 0) {
                Matcher m = Pattern.compile("<w:t[^>]*>(.*?)</w:t>").matcher(docXml);
                StringBuilder fb = new StringBuilder();
                while (m.find()) {
                    String t = m.group(1).trim();
                    if (!t.isEmpty()) {
                        fb.append("<p style=\"text-align: justify;\">").append(escapeHtml(t)).append("</p>\n");
                    }
                }
                if (fb.length() > 0) {
                    html.append(fb);
                }
            }

            JSONObject res = new JSONObject();
            res.put("header", headerText);
            res.put("headerHtml", headerHtml);
            res.put("footer", footerText);
            res.put("footerHtml", footerHtml);
            res.put("leftMarginCm", leftMarginCm);
            res.put("rightMarginCm", rightMarginCm);
            res.put("topMarginCm", topMarginCm);
            res.put("bottomMarginCm", bottomMarginCm);
            res.put("headerMarginCm", headerMarginCm);
            res.put("footerMarginCm", footerMarginCm);
            res.put("paperOrientation", orientation);
            res.put("html", html.toString());

            return res.toString();

        } catch (Exception e) {
            try {
                JSONObject err = new JSONObject();
                err.put("html", "<p style=\"text-align: justify;\">DOCX okuma hatası: " + escapeHtml(e.getMessage()) + "</p>");
                return err.toString();
            } catch (Exception ignored) {
                return "<p style=\"text-align: justify;\">DOCX okuma hatası: " + escapeHtml(e.getMessage()) + "</p>";
            }
        }
    }

    private static double parseDxaToCm(String dxaStr, double defaultCm) {
        try {
            double dxa = Double.parseDouble(dxaStr);
            return Math.round((dxa / 567.0) * 10.0) / 10.0;
        } catch (Exception e) {
            return defaultCm;
        }
    }

    private static String extractSimpleTextFromXml(String xml, DocumentBuilder db) {
        try {
            Document d = db.parse(new ByteArrayInputStream(xml.getBytes(StandardCharsets.UTF_8)));
            NodeList tList = d.getElementsByTagName("w:t");
            if (tList.getLength() == 0) tList = d.getElementsByTagName("t");
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < tList.getLength(); i++) {
                sb.append(tList.item(i).getTextContent()).append(" ");
            }
            return sb.toString().trim();
        } catch (Exception e) {
            return "";
        }
    }

    private static void parseParagraphElement(Element p, StringBuilder html) {
        String align = "justify";
        double firstLineCm = 0.0;
        double leftIndentCm = 0.0;
        double spaceAbovePt = 0.0;
        double spaceBelowPt = 0.0;

        NodeList pPrList = p.getElementsByTagName("w:pPr");
        if (pPrList.getLength() > 0) {
            Element pPr = (Element) pPrList.item(0);

            // Hizalama
            NodeList jcList = pPr.getElementsByTagName("w:jc");
            if (jcList.getLength() > 0) {
                String val = ((Element) jcList.item(0)).getAttribute("w:val");
                if ("center".equalsIgnoreCase(val)) align = "center";
                else if ("right".equalsIgnoreCase(val)) align = "right";
                else if ("left".equalsIgnoreCase(val)) align = "left";
                else if ("both".equalsIgnoreCase(val)) align = "justify";
            }

            // Girintiler
            NodeList indList = pPr.getElementsByTagName("w:ind");
            if (indList.getLength() > 0) {
                Element ind = (Element) indList.item(0);
                if (ind.hasAttribute("w:firstLine")) {
                    firstLineCm = parseDxaToCm(ind.getAttribute("w:firstLine"), 0.0);
                }
                if (ind.hasAttribute("w:left")) {
                    leftIndentCm = parseDxaToCm(ind.getAttribute("w:left"), 0.0);
                }
            }

            // Boşluklar
            NodeList spList = pPr.getElementsByTagName("w:spacing");
            if (spList.getLength() > 0) {
                Element sp = (Element) spList.item(0);
                if (sp.hasAttribute("w:before")) {
                    try { spaceAbovePt = Double.parseDouble(sp.getAttribute("w:before")) / 20.0; } catch (Exception ignored) {}
                }
                if (sp.hasAttribute("w:after")) {
                    try { spaceBelowPt = Double.parseDouble(sp.getAttribute("w:after")) / 20.0; } catch (Exception ignored) {}
                }
            }
        }

        StringBuilder styleAttr = new StringBuilder();
        styleAttr.append("text-align: ").append(align).append(";");
        if (firstLineCm > 0) {
            styleAttr.append(" text-indent: ").append(firstLineCm).append("cm;");
        }
        if (leftIndentCm > 0) {
            styleAttr.append(" margin-left: ").append(leftIndentCm).append("cm;");
        }
        if (spaceAbovePt > 0) {
            styleAttr.append(" margin-top: ").append(Math.round(spaceAbovePt)).append("pt;");
        }
        if (spaceBelowPt > 0) {
            styleAttr.append(" margin-bottom: ").append(Math.round(spaceBelowPt)).append("pt;");
        }

        StringBuilder pContent = new StringBuilder();
        Node child = p.getFirstChild();
        boolean hasContent = false;
        boolean hasTab = false;
        String firstRunText = "";

        while (child != null) {
            if (child.getNodeType() == Node.ELEMENT_NODE) {
                String nodeName = child.getNodeName();
                if ("w:r".equals(nodeName) || "r".equals(nodeName)) {
                    Element r = (Element) child;
                    boolean isBold = r.getElementsByTagName("w:b").getLength() > 0 || r.getElementsByTagName("b").getLength() > 0;
                    boolean isItalic = r.getElementsByTagName("w:i").getLength() > 0 || r.getElementsByTagName("i").getLength() > 0;
                    boolean isUnderline = r.getElementsByTagName("w:u").getLength() > 0 || r.getElementsByTagName("u").getLength() > 0;

                    Node rChild = r.getFirstChild();
                    while (rChild != null) {
                        if (rChild.getNodeType() == Node.ELEMENT_NODE) {
                            String rName = rChild.getNodeName();
                            if ("w:t".equals(rName) || "t".equals(rName)) {
                                String text = rChild.getTextContent();
                                if (text != null && !text.isEmpty()) {
                                    hasContent = true;
                                    if (firstRunText.isEmpty()) firstRunText = text.trim();
                                    String escaped = escapeHtml(text).replace("\n", "<br>");
                                    if (isBold) escaped = "<strong>" + escaped + "</strong>";
                                    if (isItalic) escaped = "<em>" + escaped + "</em>";
                                    if (isUnderline) escaped = "<u>" + escaped + "</u>";
                                    pContent.append(escaped);
                                }
                            } else if ("w:tab".equals(rName) || "tab".equals(rName)) {
                                hasTab = true;
                                hasContent = true;
                                pContent.append("<span class=\"udf-tab-space\">&nbsp;&nbsp;&nbsp;&nbsp;</span>");
                            } else if ("w:br".equals(rName) || "br".equals(rName)) {
                                hasContent = true;
                                pContent.append("<br>");
                            }
                        }
                        rChild = rChild.getNextSibling();
                    }
                }
            }
            child = child.getNextSibling();
        }

        // Dilekçe Başlığı / Metadatasını (DOSYA NO, DAVACI, VEKİLİ, KONU vb.) Zeki Çözümleme
        String rawParagraphHtml = pContent.toString();
        if (hasTab && isMetadataLabel(firstRunText)) {
            rawParagraphHtml = wrapMetadataRow(rawParagraphHtml);
            html.append("<p style=\"").append(styleAttr).append("\" data-tab-stops=\"5\">")
                .append(rawParagraphHtml)
                .append("</p>\n");
            return;
        }

        html.append("<p style=\"").append(styleAttr).append("\">");
        if (hasContent) {
            html.append(rawParagraphHtml);
        } else {
            html.append("<br>");
        }
        html.append("</p>\n");
    }

    private static boolean isMetadataLabel(String text) {
        if (text == null) return false;
        String upper = text.toUpperCase(new Locale("tr", "TR")).trim();
        return upper.equals("DOSYA NO") || upper.equals("ESAS NO") || upper.equals("DAVACI")
                || upper.equals("DAVALI") || upper.equals("VEKİLİ") || upper.equals("VEKİLLERİ")
                || upper.equals("KONU") || upper.equals("TALEP") || upper.equals("İTİRAZ EDEN")
                || upper.equals("TALEP EDEN") || upper.equals("KARŞI TARAF") || upper.equals("SANIK")
                || upper.equals("MÜŞTEKİ") || upper.equals("MAĞDUR") || upper.equals("MÜDAFİ")
                || upper.equals("KATILAN") || upper.equals("SUÇ") || upper.equals("SUÇ TARİHİ")
                || upper.equals("TEBLİĞ TARİHİ") || upper.equals("AÇIKLAMALAR") || upper.startsWith("DOSYA NO");
    }

    private static String wrapMetadataRow(String pHtml) {
        if (pHtml.contains("udf-tab-space") && pHtml.contains(":")) {
            int colonIdx = pHtml.indexOf(':');
            int tabIdx = pHtml.indexOf("<span class=\"udf-tab-space\">");
            if (tabIdx >= 0 && tabIdx < colonIdx) {
                String beforeTab = pHtml.substring(0, tabIdx).trim();
                String afterColon = pHtml.substring(colonIdx + 1).trim();
                return "<span class=\"udf-tab-label\">" + beforeTab + "</span><span class=\"udf-colon\">:</span> " + afterColon;
            }
        }
        return pHtml;
    }

    private static void parseTableElement(Element tbl, StringBuilder html) {
        html.append("<table style=\"width: 100%; border-collapse: collapse; margin: 12px 0; border: 1px solid #777;\">\n");
        Node trNode = tbl.getFirstChild();
        while (trNode != null) {
            if (trNode.getNodeType() == Node.ELEMENT_NODE) {
                String trName = trNode.getNodeName();
                if ("w:tr".equals(trName) || "tr".equals(trName)) {
                    html.append("  <tr>\n");
                    Node tcNode = trNode.getFirstChild();
                    while (tcNode != null) {
                        if (tcNode.getNodeType() == Node.ELEMENT_NODE) {
                            String tcName = tcNode.getNodeName();
                            if ("w:tc".equals(tcName) || "tc".equals(tcName)) {
                                html.append("    <td style=\"border: 1px solid #aaa; padding: 6px 10px; vertical-align: top;\">\n");
                                StringBuilder cellHtml = new StringBuilder();
                                Node pNode = tcNode.getFirstChild();
                                while (pNode != null) {
                                    if (pNode.getNodeType() == Node.ELEMENT_NODE) {
                                        String pName = pNode.getNodeName();
                                        if ("w:p".equals(pName) || "p".equals(pName)) {
                                            parseParagraphElement((Element) pNode, cellHtml);
                                        }
                                    }
                                    pNode = pNode.getNextSibling();
                                }
                                html.append(cellHtml);
                                html.append("    </td>\n");
                            }
                        }
                        tcNode = tcNode.getNextSibling();
                    }
                    html.append("  </tr>\n");
                }
            }
            trNode = trNode.getNextSibling();
        }
        html.append("</table>\n");
    }

    /**
     * Editördeki yapılandırılmış paragrafları Microsoft Word (.docx) dosyasına dönüştürür.
     */
    public static void saveStructuredToDocx(String jsonString, File targetFile) throws Exception {
        String trimmed = (jsonString != null) ? jsonString.trim() : "";
        while (trimmed.startsWith("\"") && trimmed.endsWith("\"") && trimmed.length() > 1) {
            try {
                Object unquoted = new org.json.JSONTokener(trimmed).nextValue();
                if (unquoted != null) {
                    trimmed = unquoted.toString().trim();
                } else {
                    break;
                }
            } catch (Exception ignored) {
                break;
            }
        }

        JSONArray paragraphs;
        String headerText = "";
        String footerText = "";
        double leftMarginCm = 2.5;
        double rightMarginCm = 2.5;
        double topMarginCm = 2.5;
        double bottomMarginCm = 2.5;
        String orientation = "portrait";

        if (trimmed.startsWith("{")) {
            JSONObject obj = new JSONObject(trimmed);
            headerText = obj.optString("header", "");
            footerText = obj.optString("footer", "");
            paragraphs = obj.optJSONArray("paragraphs");
            if (paragraphs == null) paragraphs = new JSONArray();

            if (obj.has("margins")) {
                JSONObject m = obj.getJSONObject("margins");
                leftMarginCm = m.optDouble("left", 2.5);
                rightMarginCm = m.optDouble("right", 2.5);
                topMarginCm = m.optDouble("top", 2.5);
                bottomMarginCm = m.optDouble("bottom", 2.5);
                orientation = m.optString("orientation", "portrait");
            } else {
                leftMarginCm = obj.optDouble("leftMarginCm", 2.5);
                rightMarginCm = obj.optDouble("rightMarginCm", 2.5);
                topMarginCm = obj.optDouble("topMarginCm", 2.5);
                bottomMarginCm = obj.optDouble("bottomMarginCm", 2.5);
            }
        } else if (trimmed.startsWith("[")) {
            paragraphs = new JSONArray(trimmed);
        } else {
            paragraphs = new JSONArray();
        }

        StringBuilder docXml = new StringBuilder();

        docXml.append("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n")
              .append("<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">\n")
              .append("<w:body>\n");

        for (int i = 0; i < paragraphs.length(); i++) {
            JSONObject pObj = paragraphs.getJSONObject(i);
            int align = pObj.optInt("align", 3);
            String jcVal = "both";
            if (align == 1) jcVal = "center";
            else if (align == 2) jcVal = "right";
            else if (align == 0) jcVal = "left";

            double spaceAbove = pObj.optDouble("spaceAbove", 0.0);
            double spaceBelow = pObj.optDouble("spaceBelow", 6.0);
            double firstLine = pObj.optDouble("firstLineIndent", 0.0);
            double leftIndent = pObj.optDouble("leftIndent", 0.0);
            double rightIndent = pObj.optDouble("rightIndent", 0.0);

            int beforeDxa = (int) Math.round(spaceAbove * 20.0);
            int afterDxa = (int) Math.round(spaceBelow * 20.0);
            int firstLineDxa = (int) Math.round(firstLine * 567.0);
            int leftDxa = (int) Math.round(leftIndent * 567.0);
            int rightDxa = (int) Math.round(rightIndent * 567.0);

            docXml.append("  <w:p>\n")
                  .append("    <w:pPr>\n")
                  .append("      <w:jc w:val=\"").append(jcVal).append("\"/>\n")
                  .append("      <w:spacing w:before=\"").append(beforeDxa).append("\" w:after=\"").append(afterDxa).append("\" w:line=\"276\" w:lineRule=\"auto\"/>\n");

            if (firstLineDxa > 0 || leftDxa > 0 || rightDxa > 0) {
                docXml.append("      <w:ind");
                if (firstLineDxa > 0) docXml.append(" w:firstLine=\"").append(firstLineDxa).append("\"");
                if (leftDxa > 0) docXml.append(" w:left=\"").append(leftDxa).append("\"");
                if (rightDxa > 0) docXml.append(" w:right=\"").append(rightDxa).append("\"");
                docXml.append("/>\n");
            }

            docXml.append("      <w:rPr><w:rFonts w:ascii=\"Times New Roman\" w:hAnsi=\"Times New Roman\"/><w:sz w:val=\"24\"/></w:rPr>\n")
                  .append("    </w:pPr>\n");

            JSONArray runs = pObj.optJSONArray("runs");
            if (runs != null && runs.length() > 0) {
                for (int j = 0; j < runs.length(); j++) {
                    JSONObject r = runs.getJSONObject(j);
                    String text = r.optString("text", "");
                    boolean bold = r.optBoolean("bold", false);
                    boolean italic = r.optBoolean("italic", false);
                    boolean underline = r.optBoolean("underline", false);

                    if (!text.isEmpty()) {
                        docXml.append("    <w:r>\n")
                              .append("      <w:rPr>\n")
                              .append("        <w:rFonts w:ascii=\"Times New Roman\" w:hAnsi=\"Times New Roman\"/>\n")
                              .append("        <w:sz w:val=\"24\"/>\n");
                        if (bold) docXml.append("        <w:b/>\n");
                        if (italic) docXml.append("        <w:i/>\n");
                        if (underline) docXml.append("        <w:u w:val=\"single\"/>\n");
                        docXml.append("      </w:rPr>\n");

                        // OpenXML Standardı: \t karakteri <w:t> içinde YASAKTIR, <w:tab/> olmalıdır. \n ise <w:br/> olmalıdır.
                        String[] lines = text.split("\n", -1);
                        for (int lIdx = 0; lIdx < lines.length; lIdx++) {
                            if (lIdx > 0) {
                                docXml.append("      <w:br/>\n");
                            }
                            String line = lines[lIdx];
                            String[] tabParts = line.split("\t", -1);
                            for (int tIdx = 0; tIdx < tabParts.length; tIdx++) {
                                if (tIdx > 0) {
                                    docXml.append("      <w:tab/>\n");
                                }
                                if (!tabParts[tIdx].isEmpty()) {
                                    docXml.append("      <w:t xml:space=\"preserve\">").append(escapeXml(tabParts[tIdx])).append("</w:t>\n");
                                }
                            }
                        }
                        docXml.append("    </w:r>\n");
                    }
                }
            }

            docXml.append("  </w:p>\n");
        }

        // A4 sayfa ve kenar boşluğu ayarı
        long topDxa = Math.round(topMarginCm * 567.0);
        long bottomDxa = Math.round(bottomMarginCm * 567.0);
        long leftDxa = Math.round(leftMarginCm * 567.0);
        long rightDxa = Math.round(rightMarginCm * 567.0);
        boolean isLandscape = "landscape".equalsIgnoreCase(orientation);
        long pgW = isLandscape ? 16838 : 11906;
        long pgH = isLandscape ? 11906 : 16838;

        docXml.append("  <w:sectPr>\n")
              .append("    <w:pgSz w:w=\"").append(pgW).append("\" w:h=\"").append(pgH).append("\"")
              .append(isLandscape ? " w:orient=\"landscape\"" : "").append("/>\n")
              .append("    <w:pgMar w:top=\"").append(topDxa).append("\" w:right=\"").append(rightDxa)
              .append("\" w:bottom=\"").append(bottomDxa).append("\" w:left=\"").append(leftDxa).append("\"/>\n")
              .append("  </w:sectPr>\n")
              .append("</w:body>\n")
              .append("</w:document>");

        // Gerekli standart OPC XML dosyaları
        String contentTypesXml = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
                + "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">\n"
                + "  <Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>\n"
                + "  <Default Extension=\"xml\" ContentType=\"application/xml\"/>\n"
                + "  <Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>\n"
                + "  <Override PartName=\"/word/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml\"/>\n"
                + "</Types>";

        String rootRelsXml = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
                + "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">\n"
                + "  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>\n"
                + "</Relationships>";

        String docRelsXml = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
                + "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">\n"
                + "  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" Target=\"styles.xml\"/>\n"
                + "</Relationships>";

        String stylesXml = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
                + "<w:styles xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">\n"
                + "  <w:docDefaults>\n"
                + "    <w:rPrDefault>\n"
                + "      <w:rPr>\n"
                + "        <w:rFonts w:ascii=\"Times New Roman\" w:hAnsi=\"Times New Roman\" w:cs=\"Times New Roman\"/>\n"
                + "        <w:sz w:val=\"24\"/>\n"
                + "        <w:lang w:val=\"tr-TR\"/>\n"
                + "      </w:rPr>\n"
                + "    </w:rPrDefault>\n"
                + "    <w:pPrDefault>\n"
                + "      <w:pPr>\n"
                + "        <w:spacing w:line=\"276\" w:lineRule=\"auto\"/>\n"
                + "      </w:pPr>\n"
                + "    </w:pPrDefault>\n"
                + "  </w:docDefaults>\n"
                + "  <w:style w:type=\"paragraph\" w:default=\"1\" w:styleId=\"Normal\">\n"
                + "    <w:name w:val=\"Normal\"/>\n"
                + "    <w:qFormat/>\n"
                + "  </w:style>\n"
                + "</w:styles>";

        if (targetFile.getParentFile() != null) {
            targetFile.getParentFile().mkdirs();
        }

        try (FileOutputStream fos = new FileOutputStream(targetFile);
             ZipOutputStream zos = new ZipOutputStream(fos)) {

            writeZipEntry(zos, "[Content_Types].xml", contentTypesXml);
            writeZipEntry(zos, "_rels/.rels", rootRelsXml);
            writeZipEntry(zos, "word/document.xml", docXml.toString());
            writeZipEntry(zos, "word/styles.xml", stylesXml);
            writeZipEntry(zos, "word/_rels/document.xml.rels", docRelsXml);
        }
    }

    private static void writeZipEntry(ZipOutputStream zos, String name, String content) throws Exception {
        ZipEntry entry = new ZipEntry(name);
        zos.putNextEntry(entry);
        byte[] bytes = content.getBytes(StandardCharsets.UTF_8);
        zos.write(bytes, 0, bytes.length);
        zos.closeEntry();
    }

    private static String escapeHtml(String text) {
        if (text == null) return "";
        return text.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;")
                   .replace("\"", "&quot;");
    }

    private static String escapeXml(String text) {
        if (text == null) return "";
        return text.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;");
    }
}
