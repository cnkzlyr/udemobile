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
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Enumeration;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
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
        if (file == null || !file.exists() || file.length() == 0) return false;
        String name = file.getName().toLowerCase(Locale.ROOT);
        try (ZipFile zip = new ZipFile(file)) {
            if (zip.getEntry("word/document.xml") != null) return true;
            if (zip.getEntry("content.xml") != null || zip.getEntry("Content.xml") != null) return false;
        } catch (Exception ignored) {}
        return name.endsWith(".docx") || name.endsWith(".docx.udf");
    }

    /**
     * .docx dosyasını (veya .docx uzantılı UDF, OLE2 .doc, RTF, düz metin dosyalarını)
     * hatasız okuyup editör için yapılandırılmış JSON/HTML formatına dönüştürür.
     */
    public static String readDocxToHtml(File file) throws Exception {
        if (file == null || !file.exists()) {
            throw new IllegalArgumentException("Dosya bulunamadı: " + (file != null ? file.getAbsolutePath() : "null"));
        }
        if (file.length() == 0) {
            JSONObject empty = new JSONObject();
            empty.put("header", "");
            empty.put("headerHtml", "");
            empty.put("footer", "");
            empty.put("footerHtml", "");
            empty.put("leftMarginCm", 2.5);
            empty.put("rightMarginCm", 2.5);
            empty.put("topMarginCm", 2.5);
            empty.put("bottomMarginCm", 2.5);
            empty.put("paperOrientation", "portrait");
            empty.put("html", "<p style=\"text-align: justify;\"><br></p>");
            return empty.toString();
        }

        byte[] headerBytes = new byte[(int) Math.min(file.length(), 64)];
        try (FileInputStream fis = new FileInputStream(file)) {
            fis.read(headerBytes);
        }

        // OLE2 Word 97-2003 (.doc) kontrolü
        if (headerBytes.length >= 8
                && (headerBytes[0] & 0xFF) == 0xD0 && (headerBytes[1] & 0xFF) == 0xCF
                && (headerBytes[2] & 0xFF) == 0x11 && (headerBytes[3] & 0xFF) == 0xE0) {
            return UdfEngine.readUdfToHtml(file);
        }

        String headStr = UdfEngine.stripBomAndLeadingGarbage(new String(headerBytes, StandardCharsets.UTF_8));
        if (headStr.startsWith("<?xml") || headStr.startsWith("<template") || headStr.startsWith("{\\rtf")) {
            return UdfEngine.readUdfToHtml(file);
        }

        String docXml = null;
        String stylesXml = null;
        String numberingXml = null;
        String relsXml = null;
        String headerXml = null;
        String footerXml = null;
        boolean hasUdfContentXml = false;
        Map<String, String> mediaBase64Map = new HashMap<>();

        try (ZipFile zip = new ZipFile(file)) {
            if (zip.getEntry("word/document.xml") == null && (zip.getEntry("content.xml") != null || zip.getEntry("Content.xml") != null)) {
                hasUdfContentXml = true;
            } else {
                Enumeration<? extends ZipEntry> entries = zip.entries();
                while (entries.hasMoreElements()) {
                    ZipEntry entry = entries.nextElement();
                    String name = entry.getName();
                    if ("word/document.xml".equalsIgnoreCase(name)) {
                        docXml = readZipEntryString(zip, entry);
                    } else if ("word/styles.xml".equalsIgnoreCase(name)) {
                        stylesXml = readZipEntryString(zip, entry);
                    } else if ("word/numbering.xml".equalsIgnoreCase(name)) {
                        numberingXml = readZipEntryString(zip, entry);
                    } else if ("word/_rels/document.xml.rels".equalsIgnoreCase(name)) {
                        relsXml = readZipEntryString(zip, entry);
                    } else if (headerXml == null && name.toLowerCase(Locale.ROOT).startsWith("word/header") && name.toLowerCase(Locale.ROOT).endsWith(".xml")) {
                        headerXml = readZipEntryString(zip, entry);
                    } else if (footerXml == null && name.toLowerCase(Locale.ROOT).startsWith("word/footer") && name.toLowerCase(Locale.ROOT).endsWith(".xml")) {
                        footerXml = readZipEntryString(zip, entry);
                    } else if (name.toLowerCase(Locale.ROOT).startsWith("word/media/") && !entry.isDirectory()) {
                        try {
                            byte[] imgBytes = UdfEngine.readZipEntryFully(zip, entry);
                            if (imgBytes != null && imgBytes.length > 0) {
                                String b64 = Base64.getEncoder().encodeToString(imgBytes);
                                mediaBase64Map.put(name, b64);
                                if (name.startsWith("word/")) {
                                    mediaBase64Map.put(name.substring(5), b64);
                                }
                            }
                        } catch (Exception ignored) {}
                    }
                }
            }
        } catch (Exception zipEx) {
            return UdfEngine.readUdfToHtml(file);
        }

        if (hasUdfContentXml) {
            return UdfEngine.readUdfToHtml(file);
        }

        if (docXml == null) {
            return UdfEngine.readUdfToHtml(file);
        }

        return parseDocxToStructuredJson(docXml, stylesXml, numberingXml, relsXml, headerXml, footerXml, mediaBase64Map);
    }

    private static String readZipEntryString(ZipFile zip, ZipEntry entry) throws Exception {
        try (InputStream is = zip.getInputStream(entry);
             ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = is.read(buf)) != -1) {
                baos.write(buf, 0, n);
            }
            return UdfEngine.stripBomAndLeadingGarbage(new String(baos.toByteArray(), StandardCharsets.UTF_8));
        }
    }

    private static boolean isXmlToggleTrue(Element parent, String tagW, String tagPlain) {
        NodeList list = parent.getElementsByTagName(tagW);
        if (list.getLength() == 0) list = parent.getElementsByTagName(tagPlain);
        if (list.getLength() == 0) return false;
        Element el = (Element) list.item(0);
        String val = el.getAttribute("w:val");
        if (val == null || val.isEmpty()) val = el.getAttribute("val");
        if (val == null || val.isEmpty()) return true;
        return !("0".equalsIgnoreCase(val) || "false".equalsIgnoreCase(val) || "none".equalsIgnoreCase(val) || "off".equalsIgnoreCase(val));
    }

    private static Element getDirectChild(Element parent, String tagW, String tagPlain) {
        if (parent == null) return null;
        Node c = parent.getFirstChild();
        while (c != null) {
            if (c.getNodeType() == Node.ELEMENT_NODE) {
                String n = c.getNodeName();
                if (tagW.equalsIgnoreCase(n) || tagPlain.equalsIgnoreCase(n)) {
                    return (Element) c;
                }
            }
            c = c.getNextSibling();
        }
        return null;
    }

    private static String getAttr(Element el, String wAttr, String plainAttr) {
        if (el == null) return "";
        if (el.hasAttribute(wAttr)) return el.getAttribute(wAttr);
        if (el.hasAttribute(plainAttr)) return el.getAttribute(plainAttr);
        return "";
    }

    private static String parseDocxToStructuredJson(
            String docXml,
            String stylesXml,
            String numberingXml,
            String relsXml,
            String headerXml,
            String footerXml,
            Map<String, String> mediaBase64Map
    ) {
        try {
            DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
            dbf.setNamespaceAware(false);
            DocumentBuilder db = dbf.newDocumentBuilder();
            Document doc = db.parse(new ByteArrayInputStream(docXml.getBytes(StandardCharsets.UTF_8)));

            // İlişkileri (rId -> media/imageX) oku
            Map<String, String> relMap = new HashMap<>();
            if (relsXml != null && !relsXml.isEmpty()) {
                try {
                    Document relDoc = db.parse(new ByteArrayInputStream(relsXml.getBytes(StandardCharsets.UTF_8)));
                    NodeList rels = relDoc.getElementsByTagName("Relationship");
                    for (int i = 0; i < rels.getLength(); i++) {
                        Element rEl = (Element) rels.item(i);
                        String id = rEl.getAttribute("Id");
                        String target = rEl.getAttribute("Target");
                        if (id != null && target != null) {
                            if (target.startsWith("/word/")) target = target.substring(6);
                            else if (target.startsWith("/")) target = target.substring(1);
                            relMap.put(id, target);
                        }
                    }
                } catch (Exception ignored) {}
            }

            // Numaralandırma (numId -> format) oku
            Map<String, String> abstractNumFmt = new HashMap<>();
            Map<String, String> numIdToFmt = new HashMap<>();
            if (numberingXml != null && !numberingXml.isEmpty()) {
                try {
                    Document numDoc = db.parse(new ByteArrayInputStream(numberingXml.getBytes(StandardCharsets.UTF_8)));
                    NodeList absList = numDoc.getElementsByTagName("w:abstractNum");
                    if (absList.getLength() == 0) absList = numDoc.getElementsByTagName("abstractNum");
                    for (int i = 0; i < absList.getLength(); i++) {
                        Element absEl = (Element) absList.item(i);
                        String absId = getAttr(absEl, "w:abstractNumId", "abstractNumId");
                        NodeList fmtList = absEl.getElementsByTagName("w:numFmt");
                        if (fmtList.getLength() == 0) fmtList = absEl.getElementsByTagName("numFmt");
                        if (fmtList.getLength() > 0) {
                            String fmtVal = getAttr((Element) fmtList.item(0), "w:val", "val");
                            abstractNumFmt.put(absId, fmtVal);
                        }
                    }
                    NodeList numList = numDoc.getElementsByTagName("w:num");
                    if (numList.getLength() == 0) numList = numDoc.getElementsByTagName("num");
                    for (int i = 0; i < numList.getLength(); i++) {
                        Element numEl = (Element) numList.item(i);
                        String numId = getAttr(numEl, "w:numId", "numId");
                        NodeList absIdList = numEl.getElementsByTagName("w:abstractNumId");
                        if (absIdList.getLength() == 0) absIdList = numEl.getElementsByTagName("abstractNumId");
                        if (absIdList.getLength() > 0) {
                            String absId = getAttr((Element) absIdList.item(0), "w:val", "val");
                            if (abstractNumFmt.containsKey(absId)) {
                                numIdToFmt.put(numId, abstractNumFmt.get(absId));
                            }
                        }
                    }
                } catch (Exception ignored) {}
            }

            // Stilleri (styleId -> pPr/rPr) oku
            Map<String, Element> styleMap = new HashMap<>();
            if (stylesXml != null && !stylesXml.isEmpty()) {
                try {
                    Document stDoc = db.parse(new ByteArrayInputStream(stylesXml.getBytes(StandardCharsets.UTF_8)));
                    NodeList stList = stDoc.getElementsByTagName("w:style");
                    if (stList.getLength() == 0) stList = stDoc.getElementsByTagName("style");
                    for (int i = 0; i < stList.getLength(); i++) {
                        Element stEl = (Element) stList.item(i);
                        String stId = getAttr(stEl, "w:styleId", "styleId");
                        if (!stId.isEmpty()) {
                            styleMap.put(stId, stEl);
                        }
                    }
                } catch (Exception ignored) {}
            }

            double leftMarginCm = 2.0;
            double rightMarginCm = 2.0;
            double topMarginCm = 2.0;
            double bottomMarginCm = 2.0;
            double headerMarginCm = 1.25;
            double footerMarginCm = 1.25;
            String orientation = "portrait";

            NodeList sectPrList = doc.getElementsByTagName("w:sectPr");
            if (sectPrList.getLength() == 0) sectPrList = doc.getElementsByTagName("sectPr");
            if (sectPrList.getLength() > 0) {
                Element sectPr = (Element) sectPrList.item(sectPrList.getLength() - 1);
                NodeList pgMarList = sectPr.getElementsByTagName("w:pgMar");
                if (pgMarList.getLength() == 0) pgMarList = sectPr.getElementsByTagName("pgMar");
                if (pgMarList.getLength() > 0) {
                    Element pgMar = (Element) pgMarList.item(0);
                    String lAttr = getAttr(pgMar, "w:left", "left");
                    String rAttr = getAttr(pgMar, "w:right", "right");
                    String tAttr = getAttr(pgMar, "w:top", "top");
                    String bAttr = getAttr(pgMar, "w:bottom", "bottom");
                    String hAttr = getAttr(pgMar, "w:header", "header");
                    String fAttr = getAttr(pgMar, "w:footer", "footer");
                    if (!lAttr.isEmpty()) leftMarginCm = parseDxaToCm(lAttr, 2.0);
                    if (!rAttr.isEmpty()) rightMarginCm = parseDxaToCm(rAttr, 2.0);
                    if (!tAttr.isEmpty()) topMarginCm = parseDxaToCm(tAttr, 2.0);
                    if (!bAttr.isEmpty()) bottomMarginCm = parseDxaToCm(bAttr, 2.0);
                    if (!hAttr.isEmpty()) headerMarginCm = parseDxaToCm(hAttr, 1.25);
                    if (!fAttr.isEmpty()) footerMarginCm = parseDxaToCm(fAttr, 1.25);
                }
                NodeList pgSzList = sectPr.getElementsByTagName("w:pgSz");
                if (pgSzList.getLength() == 0) pgSzList = sectPr.getElementsByTagName("pgSz");
                if (pgSzList.getLength() > 0) {
                    Element pgSz = (Element) pgSzList.item(0);
                    String orient = getAttr(pgSz, "w:orient", "orient");
                    if ("landscape".equalsIgnoreCase(orient)) {
                        orientation = "landscape";
                    }
                }
            }

            String headerText = "";
            String headerHtml = "";
            if (headerXml != null) {
                headerText = extractSimpleTextFromXml(headerXml, db);
                if (!headerText.isEmpty()) {
                    headerHtml = "<div class=\"udf-header-layout\" style=\"text-align:center;\">" + escapeHtml(headerText) + "</div>";
                }
            }

            String footerText = "";
            String footerHtml = "";
            if (footerXml != null) {
                footerText = extractSimpleTextFromXml(footerXml, db);
                if (!footerText.isEmpty()) {
                    footerHtml = "<div class=\"udf-footer-layout\"><span class=\"udf-footer-text\">" + escapeHtml(footerText) + "</span></div>";
                }
            }

            NodeList bodyList = doc.getElementsByTagName("w:body");
            if (bodyList.getLength() == 0) bodyList = doc.getElementsByTagName("body");
            StringBuilder html = new StringBuilder();
            Map<String, Integer> listCounters = new HashMap<>();

            if (bodyList.getLength() > 0) {
                Element body = (Element) bodyList.item(0);
                Node child = body.getFirstChild();
                while (child != null) {
                    if (child.getNodeType() == Node.ELEMENT_NODE) {
                        String nodeName = child.getNodeName();
                        if ("w:p".equalsIgnoreCase(nodeName) || "p".equalsIgnoreCase(nodeName)) {
                            parseParagraphElement((Element) child, styleMap, numIdToFmt, listCounters, relMap, mediaBase64Map, html);
                        } else if ("w:tbl".equalsIgnoreCase(nodeName) || "tbl".equalsIgnoreCase(nodeName)) {
                            parseTableElement((Element) child, styleMap, numIdToFmt, listCounters, relMap, mediaBase64Map, html);
                        } else if ("w:sdt".equalsIgnoreCase(nodeName) || "sdt".equalsIgnoreCase(nodeName)) {
                            Element sdtContent = getDirectChild((Element) child, "w:sdtContent", "sdtContent");
                            if (sdtContent != null) {
                                Node sc = sdtContent.getFirstChild();
                                while (sc != null) {
                                    if (sc.getNodeType() == Node.ELEMENT_NODE) {
                                        String sn = sc.getNodeName();
                                        if ("w:p".equalsIgnoreCase(sn) || "p".equalsIgnoreCase(sn)) {
                                            parseParagraphElement((Element) sc, styleMap, numIdToFmt, listCounters, relMap, mediaBase64Map, html);
                                        } else if ("w:tbl".equalsIgnoreCase(sn) || "tbl".equalsIgnoreCase(sn)) {
                                            parseTableElement((Element) sc, styleMap, numIdToFmt, listCounters, relMap, mediaBase64Map, html);
                                        }
                                    }
                                    sc = sc.getNextSibling();
                                }
                            }
                        }
                    }
                    child = child.getNextSibling();
                }
            }

            if (html.length() == 0) {
                NodeList pList = doc.getElementsByTagName("w:p");
                if (pList.getLength() == 0) pList = doc.getElementsByTagName("p");
                for (int i = 0; i < pList.getLength(); i++) {
                    parseParagraphElement((Element) pList.item(i), styleMap, numIdToFmt, listCounters, relMap, mediaBase64Map, html);
                }
            }

            if (html.length() == 0) {
                Matcher m = Pattern.compile("<(?:w:)?t[^>]*>(.*?)</(?:w:)?t>").matcher(docXml);
                StringBuilder fb = new StringBuilder();
                while (m.find()) {
                    String t = m.group(1).trim();
                    if (!t.isEmpty()) {
                        fb.append("<p style=\"text-align: justify;\">").append(escapeHtml(t)).append("</p>\n");
                    }
                }
                if (fb.length() > 0) {
                    html.append(fb);
                } else {
                    html.append("<p style=\"text-align: justify;\"><br></p>\n");
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
            return UdfEngine.parsePlainTextToPayload(docXml);
        }
    }

    private static double parseDxaToCm(String dxaStr, double defaultCm) {
        try {
            if (dxaStr == null || dxaStr.trim().isEmpty()) return defaultCm;
            String clean = dxaStr.trim().replace("pt", "").replace("dxa", "");
            double dxa = Double.parseDouble(clean);
            return Math.round((dxa / 567.0) * 100.0) / 100.0;
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
                sb.append(tList.item(i).getTextContent());
            }
            return sb.toString().trim();
        } catch (Exception e) {
            return "";
        }
    }

    private static void parseParagraphElement(
            Element p,
            Map<String, Element> styleMap,
            Map<String, String> numIdToFmt,
            Map<String, Integer> listCounters,
            Map<String, String> relMap,
            Map<String, String> mediaBase64Map,
            StringBuilder html
    ) {
        String align = "left";
        double firstLineCm = 0.0;
        double hangingCm = 0.0;
        double leftIndentCm = 0.0;
        double rightIndentCm = 0.0;
        double spaceAbovePt = 0.0;
        double spaceBelowPt = 2.0;
        double lineHeightRatio = 0.0;
        String docxTabStops = "";
        boolean isNumbered = false;
        boolean isBulleted = false;
        String numId = "";

        Element pPr = getDirectChild(p, "w:pPr", "pPr");
        Element stylePPr = null;
        Element styleRPr = null;

        if (pPr != null) {
            Element pStyleEl = getDirectChild(pPr, "w:pStyle", "pStyle");
            if (pStyleEl != null && styleMap != null) {
                String stId = getAttr(pStyleEl, "w:val", "val");
                Element stDef = styleMap.get(stId);
                if (stDef != null) {
                    stylePPr = getDirectChild(stDef, "w:pPr", "pPr");
                    styleRPr = getDirectChild(stDef, "w:rPr", "rPr");
                }
            }
        }

        // Hizalama (önce stil, sonra doğrudan pPr)
        Element[] pPrChain = new Element[]{stylePPr, pPr};
        for (Element pr : pPrChain) {
            if (pr == null) continue;
            Element jcEl = getDirectChild(pr, "w:jc", "jc");
            if (jcEl != null) {
                String val = getAttr(jcEl, "w:val", "val");
                if ("center".equalsIgnoreCase(val)) align = "center";
                else if ("right".equalsIgnoreCase(val) || "end".equalsIgnoreCase(val)) align = "right";
                else if ("left".equalsIgnoreCase(val) || "start".equalsIgnoreCase(val)) align = "left";
                else if ("both".equalsIgnoreCase(val) || "distribute".equalsIgnoreCase(val)) align = "justify";
            }

            Element ind = getDirectChild(pr, "w:ind", "ind");
            if (ind != null) {
                String fl = getAttr(ind, "w:firstLine", "firstLine");
                String hg = getAttr(ind, "w:hanging", "hanging");
                String lf = getAttr(ind, "w:left", "left");
                if (lf.isEmpty()) lf = getAttr(ind, "w:start", "start");
                String rg = getAttr(ind, "w:right", "right");
                if (rg.isEmpty()) rg = getAttr(ind, "w:end", "end");
                if (!fl.isEmpty()) firstLineCm = parseDxaToCm(fl, 0.0);
                if (!hg.isEmpty()) hangingCm = parseDxaToCm(hg, 0.0);
                if (!lf.isEmpty()) leftIndentCm = parseDxaToCm(lf, 0.0);
                if (!rg.isEmpty()) rightIndentCm = parseDxaToCm(rg, 0.0);
            }

            Element sp = getDirectChild(pr, "w:spacing", "spacing");
            if (sp != null) {
                String bf = getAttr(sp, "w:before", "before");
                String af = getAttr(sp, "w:after", "after");
                String ln = getAttr(sp, "w:line", "line");
                String lr = getAttr(sp, "w:lineRule", "lineRule");
                if (!bf.isEmpty()) {
                    try { spaceAbovePt = Double.parseDouble(bf) / 20.0; } catch (Exception ignored) {}
                }
                if (!af.isEmpty()) {
                    try { spaceBelowPt = Double.parseDouble(af) / 20.0; } catch (Exception ignored) {}
                }
                if (!ln.isEmpty() && (lr.isEmpty() || "auto".equalsIgnoreCase(lr))) {
                    try {
                        double lVal = Double.parseDouble(ln);
                        if (lVal > 200) lineHeightRatio = Math.round((lVal / 240.0) * 100.0) / 100.0;
                    } catch (Exception ignored) {}
                }
            }

            Element tabsElem = getDirectChild(pr, "w:tabs", "tabs");
            if (tabsElem != null) {
                NodeList tabItems = tabsElem.getElementsByTagName("w:tab");
                if (tabItems.getLength() == 0) tabItems = tabsElem.getElementsByTagName("tab");
                StringBuilder sb = new StringBuilder();
                for (int t = 0; t < tabItems.getLength(); t++) {
                    Element tElem = (Element) tabItems.item(t);
                    String posStr = getAttr(tElem, "w:pos", "pos");
                    if (!posStr.isEmpty()) {
                        double cm = parseDxaToCm(posStr, 0.0);
                        if (cm > 0) {
                            if (sb.length() > 0) sb.append(",");
                            sb.append(String.format(Locale.US, "%.2f", cm));
                        }
                    }
                }
                if (sb.length() > 0) docxTabStops = sb.toString();
            }

            Element numPr = getDirectChild(pr, "w:numPr", "numPr");
            if (numPr != null) {
                Element numIdEl = getDirectChild(numPr, "w:numId", "numId");
                if (numIdEl != null) {
                    numId = getAttr(numIdEl, "w:val", "val");
                    if (!numId.isEmpty() && !"0".equals(numId)) {
                        String fmt = numIdToFmt != null ? numIdToFmt.getOrDefault(numId, "decimal") : "decimal";
                        if ("bullet".equalsIgnoreCase(fmt)) {
                            isBulleted = true;
                        } else {
                            isNumbered = true;
                        }
                    }
                }
            }
        }

        // Word w:ind -> CSS dönüşümü:
        // Word'de w:left paragrafın sol girintisi (asılı girinti dahil), w:hanging ise ilk satırın sola geri çekilme miktarıdır.
        double cssMarginLeftCm = leftIndentCm;
        double cssTextIndentCm = firstLineCm > 0 ? firstLineCm : (hangingCm > 0 ? -hangingCm : 0.0);
        if (hangingCm > 0 && cssMarginLeftCm < hangingCm) {
            cssMarginLeftCm = hangingCm;
        }

        StringBuilder styleAttr = new StringBuilder();
        styleAttr.append("text-align: ").append(align).append(";");
        if (Math.abs(cssMarginLeftCm) > 0.01) {
            styleAttr.append(" margin-left: ").append(cssMarginLeftCm).append("cm;");
        }
        if (Math.abs(cssTextIndentCm) > 0.01) {
            styleAttr.append(" text-indent: ").append(cssTextIndentCm).append("cm;");
        }
        if (Math.abs(rightIndentCm) > 0.01) {
            styleAttr.append(" margin-right: ").append(rightIndentCm).append("cm;");
        }
        styleAttr.append(" margin-top: ").append(Math.round(spaceAbovePt)).append("pt;");
        styleAttr.append(" margin-bottom: ").append(Math.round(spaceBelowPt)).append("pt;");
        if (lineHeightRatio > 1.0) {
            styleAttr.append(" line-height: ").append(lineHeightRatio).append(";");
        }

        StringBuilder pContent = new StringBuilder();
        boolean hasContent = false;
        boolean hasTab = false;
        String firstRunText = "";

        if (isNumbered) {
            String key = numId.isEmpty() ? "default" : numId;
            int count = listCounters.getOrDefault(key, 0) + 1;
            listCounters.put(key, count);
            pContent.append("<span class=\"udf-list-prefix\" contenteditable=\"false\" style=\"font-weight:bold; margin-right:4px;\">")
                    .append(count).append(". </span>");
        } else if (isBulleted) {
            pContent.append("<span class=\"udf-list-prefix\" contenteditable=\"false\" style=\"font-weight:bold; margin-right:6px;\">•</span>");
        }

        boolean defaultBold = styleRPr != null && isXmlToggleTrue(styleRPr, "w:b", "b");
        boolean defaultItalic = styleRPr != null && isXmlToggleTrue(styleRPr, "w:i", "i");
        boolean defaultUnderline = styleRPr != null && isXmlToggleTrue(styleRPr, "w:u", "u");

        Node child = p.getFirstChild();
        while (child != null) {
            if (child.getNodeType() == Node.ELEMENT_NODE) {
                String nodeName = child.getNodeName();
                if ("w:r".equalsIgnoreCase(nodeName) || "r".equalsIgnoreCase(nodeName)
                        || "w:hyperlink".equalsIgnoreCase(nodeName) || "hyperlink".equalsIgnoreCase(nodeName)) {
                    List<Element> runsToProcess = new ArrayList<>();
                    if ("w:hyperlink".equalsIgnoreCase(nodeName) || "hyperlink".equalsIgnoreCase(nodeName)) {
                        Node hc = child.getFirstChild();
                        while (hc != null) {
                            if (hc.getNodeType() == Node.ELEMENT_NODE && ("w:r".equalsIgnoreCase(hc.getNodeName()) || "r".equalsIgnoreCase(hc.getNodeName()))) {
                                runsToProcess.add((Element) hc);
                            }
                            hc = hc.getNextSibling();
                        }
                    } else {
                        runsToProcess.add((Element) child);
                    }

                    for (Element r : runsToProcess) {
                        Element rPr = getDirectChild(r, "w:rPr", "rPr");
                        boolean isBold = rPr != null ? (rPr.getElementsByTagName("w:b").getLength() > 0 || rPr.getElementsByTagName("b").getLength() > 0 ? isXmlToggleTrue(rPr, "w:b", "b") : defaultBold) : defaultBold;
                        boolean isItalic = rPr != null ? (rPr.getElementsByTagName("w:i").getLength() > 0 || rPr.getElementsByTagName("i").getLength() > 0 ? isXmlToggleTrue(rPr, "w:i", "i") : defaultItalic) : defaultItalic;
                        boolean isUnderline = rPr != null ? (rPr.getElementsByTagName("w:u").getLength() > 0 || rPr.getElementsByTagName("u").getLength() > 0 ? isXmlToggleTrue(rPr, "w:u", "u") : defaultUnderline) : defaultUnderline;
                        boolean isStrike = rPr != null && (isXmlToggleTrue(rPr, "w:strike", "strike") || isXmlToggleTrue(rPr, "w:dstrike", "dstrike"));
                        boolean isSub = false;
                        boolean isSup = false;
                        String fontFamily = "";
                        double fontSizePt = 0.0;
                        String colorHex = "";
                        String bgHex = "";

                        if (rPr != null) {
                            Element va = getDirectChild(rPr, "w:vertAlign", "vertAlign");
                            if (va != null) {
                                String vVal = getAttr(va, "w:val", "val");
                                if ("subscript".equalsIgnoreCase(vVal)) isSub = true;
                                else if ("superscript".equalsIgnoreCase(vVal)) isSup = true;
                            }
                            Element rFonts = getDirectChild(rPr, "w:rFonts", "rFonts");
                            if (rFonts != null) {
                                fontFamily = getAttr(rFonts, "w:ascii", "ascii");
                                if (fontFamily.isEmpty()) fontFamily = getAttr(rFonts, "w:hAnsi", "hAnsi");
                            }
                            Element sz = getDirectChild(rPr, "w:sz", "sz");
                            if (sz != null) {
                                String szVal = getAttr(sz, "w:val", "val");
                                try { fontSizePt = Double.parseDouble(szVal) / 2.0; } catch (Exception ignored) {}
                            }
                            Element col = getDirectChild(rPr, "w:color", "color");
                            if (col != null) {
                                String cVal = getAttr(col, "w:val", "val");
                                if (!cVal.isEmpty() && !"auto".equalsIgnoreCase(cVal) && !"000000".equalsIgnoreCase(cVal) && !"333333".equalsIgnoreCase(cVal)) {
                                    colorHex = "#" + cVal;
                                }
                            }
                            Element hl = getDirectChild(rPr, "w:highlight", "highlight");
                            if (hl != null) {
                                String hVal = getAttr(hl, "w:val", "val");
                                if ("yellow".equalsIgnoreCase(hVal)) bgHex = "#FFFF00";
                                else if ("green".equalsIgnoreCase(hVal)) bgHex = "#00FF00";
                                else if ("cyan".equalsIgnoreCase(hVal)) bgHex = "#00FFFF";
                            }
                        }

                        Node rChild = r.getFirstChild();
                        while (rChild != null) {
                            if (rChild.getNodeType() == Node.ELEMENT_NODE) {
                                String rName = rChild.getNodeName();
                                if ("w:t".equalsIgnoreCase(rName) || "t".equalsIgnoreCase(rName)) {
                                    String text = rChild.getTextContent();
                                    if (text != null && !text.isEmpty()) {
                                        hasContent = true;
                                        if (firstRunText.isEmpty()) firstRunText = text.trim();
                                        String escaped = escapeHtml(text).replace("\n", "<br>");
                                        if (isBold) escaped = "<strong>" + escaped + "</strong>";
                                        if (isItalic) escaped = "<em>" + escaped + "</em>";
                                        if (isUnderline) escaped = "<u>" + escaped + "</u>";
                                        if (isStrike) escaped = "<s>" + escaped + "</s>";
                                        if (isSub) escaped = "<sub>" + escaped + "</sub>";
                                        if (isSup) escaped = "<sup>" + escaped + "</sup>";

                                        StringBuilder spanStyle = new StringBuilder();
                                        if (!fontFamily.isEmpty() && !"Times New Roman".equalsIgnoreCase(fontFamily)) {
                                            spanStyle.append("font-family:'").append(escapeHtml(fontFamily)).append("';");
                                        }
                                        if (fontSizePt > 1.0 && Math.abs(fontSizePt - 12.0) > 0.1) {
                                            spanStyle.append("font-size:").append(fontSizePt == Math.floor(fontSizePt) ? String.valueOf((int) fontSizePt) : String.valueOf(fontSizePt)).append("pt;");
                                        }
                                        if (!colorHex.isEmpty()) {
                                            spanStyle.append("color:").append(escapeHtml(colorHex)).append(";");
                                        }
                                        if (!bgHex.isEmpty()) {
                                            spanStyle.append("background-color:").append(escapeHtml(bgHex)).append(";");
                                        }
                                        if (spanStyle.length() > 0) {
                                            escaped = "<span style=\"" + spanStyle + "\">" + escaped + "</span>";
                                        }
                                        pContent.append(escaped);
                                    }
                                } else if ("w:tab".equalsIgnoreCase(rName) || "tab".equalsIgnoreCase(rName)) {
                                    hasTab = true;
                                    hasContent = true;
                                    pContent.append("<span class=\"udf-tab-space\" contenteditable=\"false\">&#8203;</span>");
                                } else if ("w:br".equalsIgnoreCase(rName) || "br".equalsIgnoreCase(rName)) {
                                    Element brEl = (Element) rChild;
                                    String brType = getAttr(brEl, "w:type", "type");
                                    if ("page".equalsIgnoreCase(brType)) {
                                        pContent.append("<div class=\"udf-page-break\" data-udf-page-break=\"true\" style=\"page-break-after:always; break-after:page; height:0; margin:12px 0; border-top:1px dashed #94a3b8;\"></div>");
                                    } else {
                                        // Yalnızca paragrafın en sonundaki gereksiz <w:br/> değilse ekle
                                        boolean isTrailingBr = (rChild.getNextSibling() == null && r.getNextSibling() == null && hasContent);
                                        if (!isTrailingBr) {
                                            hasContent = true;
                                            pContent.append("<br>");
                                        }
                                    }
                                } else if ("w:drawing".equalsIgnoreCase(rName) || "drawing".equalsIgnoreCase(rName)
                                        || "w:pict".equalsIgnoreCase(rName) || "pict".equalsIgnoreCase(rName)) {
                                    Element drawEl = (Element) rChild;
                                    String embedId = "";
                                    NodeList blips = drawEl.getElementsByTagName("a:blip");
                                    if (blips.getLength() == 0) blips = drawEl.getElementsByTagName("blip");
                                    if (blips.getLength() > 0) {
                                        embedId = getAttr((Element) blips.item(0), "r:embed", "embed");
                                    }
                                    if (embedId.isEmpty()) {
                                        NodeList imgDataList = drawEl.getElementsByTagName("v:imagedata");
                                        if (imgDataList.getLength() == 0) imgDataList = drawEl.getElementsByTagName("imagedata");
                                        if (imgDataList.getLength() > 0) {
                                            embedId = getAttr((Element) imgDataList.item(0), "r:id", "id");
                                        }
                                    }
                                    if (!embedId.isEmpty() && relMap != null && mediaBase64Map != null) {
                                        String target = relMap.get(embedId);
                                        if (target != null && mediaBase64Map.containsKey(target)) {
                                            String b64 = mediaBase64Map.get(target);
                                            double wCm = 0, hCm = 0;
                                            NodeList extents = drawEl.getElementsByTagName("wp:extent");
                                            if (extents.getLength() == 0) extents = drawEl.getElementsByTagName("extent");
                                            if (extents.getLength() > 0) {
                                                Element ext = (Element) extents.item(0);
                                                try {
                                                    wCm = Math.round((Double.parseDouble(ext.getAttribute("cx")) / 360000.0) * 100.0) / 100.0;
                                                    hCm = Math.round((Double.parseDouble(ext.getAttribute("cy")) / 360000.0) * 100.0) / 100.0;
                                                } catch (Exception ignored) {}
                                            }
                                            String mime = target.toLowerCase(Locale.ROOT).endsWith(".jpg") || target.toLowerCase(Locale.ROOT).endsWith(".jpeg") ? "image/jpeg" : "image/png";
                                            StringBuilder imgStyle = new StringBuilder("display:inline-block; vertical-align:middle; object-fit:contain;");
                                            if (wCm > 0) imgStyle.append(" width:").append(wCm).append("cm; max-width:100%;");
                                            if (hCm > 0) imgStyle.append(" height:").append(hCm).append("cm;");
                                            pContent.append("<img src=\"data:").append(mime).append(";base64,").append(b64).append("\" style=\"").append(imgStyle).append("\" />");
                                            hasContent = true;
                                        }
                                    }
                                }
                            }
                            rChild = rChild.getNextSibling();
                        }
                    }
                }
            }
            child = child.getNextSibling();
        }

        html.append("<p style=\"").append(styleAttr).append("\"");
        if (!docxTabStops.isEmpty()) {
            html.append(" data-tab-stops=\"").append(docxTabStops).append("\"");
        } else if (hasTab && isMetadataLabel(firstRunText)) {
            html.append(" data-tab-stops=\"5\"");
        }
        if (isNumbered) html.append(" data-udf-numbered=\"true\"");
        if (isBulleted) html.append(" data-udf-bulleted=\"true\"");
        html.append(">");
        if (hasContent) {
            html.append(pContent);
        } else {
            html.append("<br>");
        }
        html.append("</p>\n");
    }

    private static boolean isMetadataLabel(String text) {
        if (text == null) return false;
        String upper = text.toUpperCase(new Locale("tr", "TR")).trim();
        return upper.equals("DOSYA NO") || upper.equals("ESAS NO") || upper.equals("KARAR NO")
                || upper.equals("DAVACI") || upper.equals("DAVALI") || upper.equals("VEKİLİ")
                || upper.equals("VEKİLLERİ") || upper.equals("KONU") || upper.equals("TALEP")
                || upper.equals("İTİRAZ EDEN") || upper.equals("TALEP EDEN") || upper.equals("KARŞI TARAF")
                || upper.equals("SANIK") || upper.equals("MÜŞTEKİ") || upper.equals("MAĞDUR")
                || upper.equals("MÜDAFİ") || upper.equals("KATILAN") || upper.equals("SUÇ")
                || upper.equals("SUÇ TARİHİ") || upper.equals("TEBLİĞ TARİHİ") || upper.equals("AÇIKLAMALAR")
                || upper.startsWith("DOSYA NO");
    }

    private static void parseTableElement(
            Element tbl,
            Map<String, Element> styleMap,
            Map<String, String> numIdToFmt,
            Map<String, Integer> listCounters,
            Map<String, String> relMap,
            Map<String, String> mediaBase64Map,
            StringBuilder html
    ) {
        boolean isBorderNone = false;
        Element tblPr = getDirectChild(tbl, "w:tblPr", "tblPr");
        if (tblPr != null) {
            Element tblBorders = getDirectChild(tblPr, "w:tblBorders", "tblBorders");
            if (tblBorders != null) {
                Element topB = getDirectChild(tblBorders, "w:top", "top");
                if (topB != null && ("none".equalsIgnoreCase(getAttr(topB, "w:val", "val")) || "nil".equalsIgnoreCase(getAttr(topB, "w:val", "val")))) {
                    isBorderNone = true;
                }
            }
        }

        String tableBorderStyle = isBorderNone ? "border: none;" : "border: 1px solid #333;";
        html.append("<table style=\"width: 100%; border-collapse: collapse; margin: 6px 0; ").append(tableBorderStyle).append("\"")
            .append(isBorderNone ? " data-udf-border=\"borderNone\"" : " data-udf-border=\"borderCell\"").append(">\n");

        Node trNode = tbl.getFirstChild();
        while (trNode != null) {
            if (trNode.getNodeType() == Node.ELEMENT_NODE) {
                String trName = trNode.getNodeName();
                if ("w:tr".equalsIgnoreCase(trName) || "tr".equalsIgnoreCase(trName)) {
                    html.append("  <tr>\n");
                    Node tcNode = trNode.getFirstChild();
                    while (tcNode != null) {
                        if (tcNode.getNodeType() == Node.ELEMENT_NODE) {
                            String tcName = tcNode.getNodeName();
                            if ("w:tc".equalsIgnoreCase(tcName) || "tc".equalsIgnoreCase(tcName)) {
                                Element tcEl = (Element) tcNode;
                                Element tcPr = getDirectChild(tcEl, "w:tcPr", "tcPr");
                                String colSpanAttr = "";
                                StringBuilder tdStyle = new StringBuilder(isBorderNone ? "border: none; " : "border: 1px solid #333; ");
                                tdStyle.append("padding: 4px 6px; vertical-align: top;");
                                if (tcPr != null) {
                                    Element gs = getDirectChild(tcPr, "w:gridSpan", "gridSpan");
                                    if (gs != null) {
                                        String gsVal = getAttr(gs, "w:val", "val");
                                        if (!gsVal.isEmpty()) colSpanAttr = " colspan=\"" + escapeHtml(gsVal) + "\"";
                                    }
                                    Element shd = getDirectChild(tcPr, "w:shd", "shd");
                                    if (shd != null) {
                                        String fill = getAttr(shd, "w:fill", "fill");
                                        if (!fill.isEmpty() && !"auto".equalsIgnoreCase(fill) && !"FFFFFF".equalsIgnoreCase(fill)) {
                                            tdStyle.append(" background-color:#").append(escapeHtml(fill)).append(";");
                                        }
                                    }
                                }
                                html.append("    <td style=\"").append(tdStyle).append("\"").append(colSpanAttr).append(">\n");
                                StringBuilder cellHtml = new StringBuilder();
                                Node pNode = tcEl.getFirstChild();
                                while (pNode != null) {
                                    if (pNode.getNodeType() == Node.ELEMENT_NODE) {
                                        String pName = pNode.getNodeName();
                                        if ("w:p".equalsIgnoreCase(pName) || "p".equalsIgnoreCase(pName)) {
                                            parseParagraphElement((Element) pNode, styleMap, numIdToFmt, listCounters, relMap, mediaBase64Map, cellHtml);
                                        } else if ("w:tbl".equalsIgnoreCase(pName) || "tbl".equalsIgnoreCase(pName)) {
                                            parseTableElement((Element) pNode, styleMap, numIdToFmt, listCounters, relMap, mediaBase64Map, cellHtml);
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

    private static class DocxMediaItem {
        String relId;
        String fileName;
        byte[] bytes;
    }

    private static void appendDocxParagraphXml(JSONObject pObj, StringBuilder docXml, List<DocxMediaItem> mediaList) throws Exception {
        int align = pObj.optInt("align", 3);
        String jcVal = "both";
        if (align == 1) jcVal = "center";
        else if (align == 2) jcVal = "right";
        else if (align == 0) jcVal = "left";

        double spaceAbove = pObj.optDouble("spaceAbove", 0.0);
        double spaceBelow = pObj.optDouble("spaceBelow", 2.0);
        double lineSpacing = pObj.optDouble("lineSpacing", 0.0);
        double firstLineCm = pObj.optDouble("firstLineIndent", 0.0);
        double leftIndentCm = pObj.optDouble("leftIndent", 0.0);
        double rightIndentCm = pObj.optDouble("rightIndent", 0.0);
        String tabStopsStr = pObj.optString("tabStops", "");

        int beforeDxa = (int) Math.round(Math.max(0, spaceAbove) * 20.0);
        int afterDxa = (int) Math.round(Math.max(0, spaceBelow) * 20.0);
        int lineDxa = lineSpacing > 0.05 ? (int) Math.round((1.0 + lineSpacing) * 240.0) : 240;

        int leftDxa = (int) Math.round(Math.max(0, leftIndentCm) * 567.0);
        int rightDxa = (int) Math.round(Math.max(0, rightIndentCm) * 567.0);
        int firstLineDxa = firstLineCm > 0.01 ? (int) Math.round(firstLineCm * 567.0) : 0;
        int hangingDxa = firstLineCm < -0.01 ? (int) Math.round((-firstLineCm) * 567.0) : 0;

        docXml.append("  <w:p>\n")
              .append("    <w:pPr>\n")
              .append("      <w:jc w:val=\"").append(jcVal).append("\"/>\n")
              .append("      <w:spacing w:before=\"").append(beforeDxa).append("\" w:after=\"").append(afterDxa).append("\" w:line=\"").append(lineDxa).append("\" w:lineRule=\"auto\"/>\n");

        if (!tabStopsStr.isEmpty()) {
            String[] stops = tabStopsStr.split(",");
            StringBuilder tabsXml = new StringBuilder();
            for (String s : stops) {
                try {
                    double cm = Double.parseDouble(s.trim());
                    if (cm > 0) {
                        int posDxa = (int) Math.round(cm * 567.0);
                        tabsXml.append("        <w:tab w:val=\"left\" w:pos=\"").append(posDxa).append("\"/>\n");
                    }
                } catch (Exception ignored) {}
            }
            if (tabsXml.length() > 0) {
                docXml.append("      <w:tabs>\n").append(tabsXml).append("      </w:tabs>\n");
            }
        }

        if (firstLineDxa > 0 || hangingDxa > 0 || leftDxa > 0 || rightDxa > 0) {
            docXml.append("      <w:ind");
            if (leftDxa > 0) docXml.append(" w:left=\"").append(leftDxa).append("\"");
            if (rightDxa > 0) docXml.append(" w:right=\"").append(rightDxa).append("\"");
            if (firstLineDxa > 0) docXml.append(" w:firstLine=\"").append(firstLineDxa).append("\"");
            if (hangingDxa > 0) docXml.append(" w:hanging=\"").append(hangingDxa).append("\"");
            docXml.append("/>\n");
        }

        docXml.append("      <w:rPr><w:rFonts w:ascii=\"Times New Roman\" w:hAnsi=\"Times New Roman\"/><w:sz w:val=\"24\"/></w:rPr>\n")
              .append("    </w:pPr>\n");

        JSONArray runs = pObj.optJSONArray("runs");
        if (runs != null && runs.length() > 0) {
            for (int j = 0; j < runs.length(); j++) {
                JSONObject r = runs.getJSONObject(j);
                String rType = r.optString("type", "text");
                if ("image".equalsIgnoreCase(rType)) {
                    String imgData = r.optString("imageData", "");
                    if (!imgData.isEmpty() && mediaList != null) {
                        try {
                            byte[] imgBytes = Base64.getDecoder().decode(imgData.trim());
                            int idx = mediaList.size() + 1;
                            DocxMediaItem item = new DocxMediaItem();
                            item.relId = "rIdImg" + idx;
                            item.fileName = "media/image" + idx + ".png";
                            item.bytes = imgBytes;
                            mediaList.add(item);

                            long cx = Math.round(r.optDouble("widthPt", 120.0) * 12700.0);
                            long cy = Math.round(r.optDouble("heightPt", 60.0) * 12700.0);
                            docXml.append("    <w:r>\n")
                                  .append("      <w:drawing>\n")
                                  .append("        <wp:inline distT=\"0\" distB=\"0\" distL=\"0\" distR=\"0\">\n")
                                  .append("          <wp:extent cx=\"").append(cx).append("\" cy=\"").append(cy).append("\"/>\n")
                                  .append("          <wp:docPr id=\"").append(idx).append("\" name=\"Picture ").append(idx).append("\"/>\n")
                                  .append("          <a:graphic xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\">\n")
                                  .append("            <a:graphicData uri=\"http://schemas.openxmlformats.org/drawingml/2006/picture\">\n")
                                  .append("              <pic:pic xmlns:pic=\"http://schemas.openxmlformats.org/drawingml/2006/picture\">\n")
                                  .append("                <pic:nvPicPr><pic:cNvPr id=\"").append(idx).append("\" name=\"image").append(idx).append(".png\"/><pic:cNvPicPr/></pic:nvPicPr>\n")
                                  .append("                <pic:blipFill><a:blip r:embed=\"").append(item.relId).append("\"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>\n")
                                  .append("                <pic:spPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"").append(cx).append("\" cy=\"").append(cy).append("\"/></a:xfrm><a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom></pic:spPr>\n")
                                  .append("              </pic:pic>\n")
                                  .append("            </a:graphicData>\n")
                                  .append("          </a:graphic>\n")
                                  .append("        </wp:inline>\n")
                                  .append("      </w:drawing>\n")
                                  .append("    </w:r>\n");
                        } catch (Exception ignored) {}
                    }
                    continue;
                }

                String text = r.optString("text", "");
                boolean bold = r.optBoolean("bold", false);
                boolean italic = r.optBoolean("italic", false);
                boolean underline = r.optBoolean("underline", false);
                boolean strike = r.optBoolean("strikethrough", false) || r.optBoolean("strikeThrough", false);
                boolean sub = r.optBoolean("subscript", false);
                boolean sup = r.optBoolean("superscript", false);
                String fontFamily = r.optString("fontFamily", "Times New Roman").replace("'", "").replace("\"", "").split(",")[0].trim();
                if (fontFamily.isEmpty()) fontFamily = "Times New Roman";
                double fontSize = r.optDouble("fontSize", 12.0);
                if (fontSize <= 1.0) fontSize = 12.0;
                int halfPt = (int) Math.round(fontSize * 2.0);
                String colorStr = r.optString("color", "");

                if (!text.isEmpty()) {
                    docXml.append("    <w:r>\n")
                          .append("      <w:rPr>\n")
                          .append("        <w:rFonts w:ascii=\"").append(escapeXml(fontFamily)).append("\" w:hAnsi=\"").append(escapeXml(fontFamily)).append("\" w:cs=\"").append(escapeXml(fontFamily)).append("\"/>\n")
                          .append("        <w:sz w:val=\"").append(halfPt).append("\"/>\n")
                          .append("        <w:szCs w:val=\"").append(halfPt).append("\"/>\n");
                    if (bold) docXml.append("        <w:b/>\n");
                    if (italic) docXml.append("        <w:i/>\n");
                    if (underline) docXml.append("        <w:u w:val=\"single\"/>\n");
                    if (strike) docXml.append("        <w:strike/>\n");
                    if (sub) docXml.append("        <w:vertAlign w:val=\"subscript\"/>\n");
                    else if (sup) docXml.append("        <w:vertAlign w:val=\"superscript\"/>\n");
                    if (colorStr != null && colorStr.startsWith("#") && colorStr.length() == 7) {
                        docXml.append("        <w:color w:val=\"").append(escapeXml(colorStr.substring(1).toUpperCase(Locale.ROOT))).append("\"/>\n");
                    }
                    docXml.append("      </w:rPr>\n");

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

    private static void appendDocxTableXml(JSONObject tblObj, StringBuilder docXml, List<DocxMediaItem> mediaList) throws Exception {
        String border = tblObj.optString("border", "borderCell");
        boolean noBorder = "borderNone".equalsIgnoreCase(border) || "none".equalsIgnoreCase(border);
        JSONArray rows = tblObj.optJSONArray("rows");
        if (rows == null || rows.length() == 0) return;

        docXml.append("  <w:tbl>\n")
              .append("    <w:tblPr>\n")
              .append("      <w:tblW w:w=\"5000\" w:type=\"pct\"/>\n");
        if (noBorder) {
            docXml.append("      <w:tblBorders>\n")
                  .append("        <w:top w:val=\"none\" w:sz=\"0\" w:space=\"0\" w:color=\"auto\"/>\n")
                  .append("        <w:left w:val=\"none\" w:sz=\"0\" w:space=\"0\" w:color=\"auto\"/>\n")
                  .append("        <w:bottom w:val=\"none\" w:sz=\"0\" w:space=\"0\" w:color=\"auto\"/>\n")
                  .append("        <w:right w:val=\"none\" w:sz=\"0\" w:space=\"0\" w:color=\"auto\"/>\n")
                  .append("        <w:insideH w:val=\"none\" w:sz=\"0\" w:space=\"0\" w:color=\"auto\"/>\n")
                  .append("        <w:insideV w:val=\"none\" w:sz=\"0\" w:space=\"0\" w:color=\"auto\"/>\n")
                  .append("      </w:tblBorders>\n");
        } else {
            docXml.append("      <w:tblBorders>\n")
                  .append("        <w:top w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"333333\"/>\n")
                  .append("        <w:left w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"333333\"/>\n")
                  .append("        <w:bottom w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"333333\"/>\n")
                  .append("        <w:right w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"333333\"/>\n")
                  .append("        <w:insideH w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"333333\"/>\n")
                  .append("        <w:insideV w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"333333\"/>\n")
                  .append("      </w:tblBorders>\n");
        }
        docXml.append("    </w:tblPr>\n");

        for (int r = 0; r < rows.length(); r++) {
            JSONObject rObj = rows.getJSONObject(r);
            docXml.append("    <w:tr>\n");
            JSONArray cells = rObj.optJSONArray("cells");
            if (cells != null) {
                int cellCount = Math.max(1, cells.length());
                int pctPerCell = 5000 / cellCount;
                for (int c = 0; c < cells.length(); c++) {
                    JSONObject cellObj = cells.getJSONObject(c);
                    int colSpan = cellObj.optInt("colSpan", 1);
                    docXml.append("      <w:tc>\n")
                          .append("        <w:tcPr>\n")
                          .append("          <w:tcW w:w=\"").append(pctPerCell * colSpan).append("\" w:type=\"pct\"/>\n");
                    if (colSpan > 1) {
                        docXml.append("          <w:gridSpan w:val=\"").append(colSpan).append("\"/>\n");
                    }
                    docXml.append("        </w:tcPr>\n");

                    JSONArray cellParas = cellObj.optJSONArray("paragraphs");
                    if (cellParas != null && cellParas.length() > 0) {
                        for (int p = 0; p < cellParas.length(); p++) {
                            JSONObject pItem = cellParas.getJSONObject(p);
                            if ("table".equalsIgnoreCase(pItem.optString("type", "paragraph"))) {
                                appendDocxTableXml(pItem, docXml, mediaList);
                            } else {
                                appendDocxParagraphXml(pItem, docXml, mediaList);
                            }
                        }
                    } else {
                        docXml.append("        <w:p/>\n");
                    }
                    docXml.append("      </w:tc>\n");
                }
            }
            docXml.append("    </w:tr>\n");
        }
        docXml.append("  </w:tbl>\n");
    }

    /**
     * Editördeki yapılandırılmış paragraf, tablo ve görselleri Microsoft Word (.docx) dosyasına dönüştürür.
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
        double leftMarginCm = 1.5;
        double rightMarginCm = 1.5;
        double topMarginCm = 1.5;
        double bottomMarginCm = 1.5;
        String orientation = "portrait";

        if (trimmed.startsWith("{")) {
            JSONObject obj = new JSONObject(trimmed);
            headerText = obj.optString("header", "");
            footerText = obj.optString("footer", "");
            paragraphs = obj.optJSONArray("paragraphs");
            if (paragraphs == null) paragraphs = new JSONArray();

            if (obj.has("margins")) {
                JSONObject m = obj.getJSONObject("margins");
                leftMarginCm = m.optDouble("left", 1.5);
                rightMarginCm = m.optDouble("right", 1.5);
                topMarginCm = m.optDouble("top", 1.5);
                bottomMarginCm = m.optDouble("bottom", 1.5);
                orientation = m.optString("orientation", "portrait");
            } else {
                leftMarginCm = obj.optDouble("leftMarginCm", 1.5);
                rightMarginCm = obj.optDouble("rightMarginCm", 1.5);
                topMarginCm = obj.optDouble("topMarginCm", 1.5);
                bottomMarginCm = obj.optDouble("bottomMarginCm", 1.5);
                String po = obj.optString("paperOrientation", "1");
                if ("2".equals(po) || "landscape".equalsIgnoreCase(po)) orientation = "landscape";
            }
        } else if (trimmed.startsWith("[")) {
            paragraphs = new JSONArray(trimmed);
        } else {
            paragraphs = new JSONArray();
        }

        List<DocxMediaItem> mediaList = new ArrayList<>();
        StringBuilder docXml = new StringBuilder();

        docXml.append("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n")
              .append("<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" ")
              .append("xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" ")
              .append("xmlns:wp=\"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing\">\n")
              .append("<w:body>\n");

        for (int i = 0; i < paragraphs.length(); i++) {
            JSONObject block = paragraphs.getJSONObject(i);
            String blockType = block.optString("type", "paragraph");
            if ("table".equalsIgnoreCase(blockType)) {
                appendDocxTableXml(block, docXml, mediaList);
            } else if ("pageBreak".equalsIgnoreCase(blockType) || "page-break".equalsIgnoreCase(blockType)) {
                docXml.append("  <w:p><w:r><w:br w:type=\"page\"/></w:r></w:p>\n");
            } else {
                appendDocxParagraphXml(block, docXml, mediaList);
            }
        }

        long topDxa = Math.round(topMarginCm * 567.0);
        long bottomDxa = Math.round(bottomMarginCm * 567.0);
        long leftDxa = Math.round(leftMarginCm * 567.0);
        long rightDxa = Math.round(rightMarginCm * 567.0);
        boolean isLandscape = "landscape".equalsIgnoreCase(orientation);
        long pgW = isLandscape ? 16838 : 11906;
        long pgH = isLandscape ? 11906 : 16838;

        boolean hasHeader = headerText != null && !headerText.trim().isEmpty();
        boolean hasFooter = footerText != null && !footerText.trim().isEmpty();

        docXml.append("  <w:sectPr>\n");
        if (hasHeader) {
            docXml.append("    <w:headerReference w:type=\"default\" r:id=\"rIdHeader1\"/>\n");
        }
        if (hasFooter) {
            docXml.append("    <w:footerReference w:type=\"default\" r:id=\"rIdFooter1\"/>\n");
        }
        docXml.append("    <w:pgSz w:w=\"").append(pgW).append("\" w:h=\"").append(pgH).append("\"")
              .append(isLandscape ? " w:orient=\"landscape\"" : "").append("/>\n")
              .append("    <w:pgMar w:top=\"").append(topDxa).append("\" w:right=\"").append(rightDxa)
              .append("\" w:bottom=\"").append(bottomDxa).append("\" w:left=\"").append(leftDxa)
              .append("\" w:header=\"708\" w:footer=\"708\"/>\n")
              .append("  </w:sectPr>\n")
              .append("</w:body>\n")
              .append("</w:document>");

        StringBuilder contentTypesXml = new StringBuilder();
        contentTypesXml.append("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n")
                .append("<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">\n")
                .append("  <Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>\n")
                .append("  <Default Extension=\"xml\" ContentType=\"application/xml\"/>\n")
                .append("  <Default Extension=\"png\" ContentType=\"image/png\"/>\n")
                .append("  <Default Extension=\"jpg\" ContentType=\"image/jpeg\"/>\n")
                .append("  <Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>\n")
                .append("  <Override PartName=\"/word/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml\"/>\n");
        if (hasHeader) {
            contentTypesXml.append("  <Override PartName=\"/word/header1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml\"/>\n");
        }
        if (hasFooter) {
            contentTypesXml.append("  <Override PartName=\"/word/footer1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml\"/>\n");
        }
        contentTypesXml.append("</Types>");

        String rootRelsXml = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
                + "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">\n"
                + "  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>\n"
                + "</Relationships>";

        StringBuilder docRelsXml = new StringBuilder();
        docRelsXml.append("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n")
                .append("<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">\n")
                .append("  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" Target=\"styles.xml\"/>\n");
        if (hasHeader) {
            docRelsXml.append("  <Relationship Id=\"rIdHeader1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/header\" Target=\"header1.xml\"/>\n");
        }
        if (hasFooter) {
            docRelsXml.append("  <Relationship Id=\"rIdFooter1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer\" Target=\"footer1.xml\"/>\n");
        }
        for (DocxMediaItem item : mediaList) {
            docRelsXml.append("  <Relationship Id=\"").append(item.relId)
                    .append("\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/image\" Target=\"")
                    .append(item.fileName).append("\"/>\n");
        }
        docRelsXml.append("</Relationships>");

        String stylesXml = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
                + "<w:styles xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">\n"
                + "  <w:docDefaults>\n"
                + "    <w:rPrDefault>\n"
                + "      <w:rPr>\n"
                + "        <w:rFonts w:ascii=\"Times New Roman\" w:hAnsi=\"Times New Roman\" w:cs=\"Times New Roman\"/>\n"
                + "        <w:sz w:val=\"24\"/>\n"
                + "        <w:szCs w:val=\"24\"/>\n"
                + "        <w:lang w:val=\"tr-TR\"/>\n"
                + "      </w:rPr>\n"
                + "    </w:rPrDefault>\n"
                + "    <w:pPrDefault>\n"
                + "      <w:pPr>\n"
                + "        <w:spacing w:line=\"240\" w:lineRule=\"auto\"/>\n"
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

            writeZipEntry(zos, "[Content_Types].xml", contentTypesXml.toString());
            writeZipEntry(zos, "_rels/.rels", rootRelsXml);
            writeZipEntry(zos, "word/document.xml", docXml.toString());
            writeZipEntry(zos, "word/styles.xml", stylesXml);
            writeZipEntry(zos, "word/_rels/document.xml.rels", docRelsXml.toString());

            if (hasHeader) {
                String hXml = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
                        + "<w:hdr xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">\n"
                        + "  <w:p><w:pPr><w:jc w:val=\"center\"/></w:pPr><w:r><w:t>" + escapeXml(headerText.trim()) + "</w:t></w:r></w:p>\n"
                        + "</w:hdr>";
                writeZipEntry(zos, "word/header1.xml", hXml);
            }
            if (hasFooter) {
                String fXml = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
                        + "<w:ftr xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">\n"
                        + "  <w:p><w:pPr><w:jc w:val=\"center\"/></w:pPr><w:r><w:t>" + escapeXml(footerText.trim()) + "</w:t></w:r></w:p>\n"
                        + "</w:ftr>";
                writeZipEntry(zos, "word/footer1.xml", fXml);
            }
            for (DocxMediaItem item : mediaList) {
                ZipEntry imgEntry = new ZipEntry("word/" + item.fileName);
                zos.putNextEntry(imgEntry);
                zos.write(item.bytes, 0, item.bytes.length);
                zos.closeEntry();
            }
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
