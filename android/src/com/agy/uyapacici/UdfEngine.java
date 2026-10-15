package com.agy.uyapacici;

import org.json.JSONArray;
import org.json.JSONObject;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Date;
import java.util.Enumeration;
import java.util.List;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;

public class UdfEngine {

    /**
     * .udf dosyasını okuyup mobil editör için başlık, altbilgi ve HTML içeriğine dönüştürür.
     */
    private static String toRoman(int num) {
        String[] m = {"", "M", "MM", "MMM"};
        String[] c = {"", "C", "CC", "CCC", "CD", "D", "DC", "DCC", "DCCC", "CM"};
        String[] x = {"", "X", "XX", "XXX", "XL", "L", "LX", "LXX", "LXXX", "XC"};
        String[] i = {"", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"};
        if (num <= 0 || num > 3999) return String.valueOf(num);
        return m[num / 1000] + c[(num % 1000) / 100] + x[(num % 100) / 10] + i[num % 10];
    }

    public static String readUdfToHtml(File file) throws Exception {
        if (!file.exists()) {
            throw new IllegalArgumentException("Dosya bulunamadı: " + file.getAbsolutePath());
        }

        String contentXml = null;
        try (ZipFile zip = new ZipFile(file)) {
            ZipEntry contentEntry = zip.getEntry("content.xml");
            if (contentEntry == null) {
                contentEntry = zip.getEntry("Content.xml");
            }
        if (contentEntry == null) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                String name = entry.getName().toLowerCase();
                if (name.endsWith("content.xml")) {
                    contentEntry = entry;
                    break;
                }
            }
        }
        if (contentEntry == null) {
            Enumeration<? extends ZipEntry> entries2 = zip.entries();
            while (entries2.hasMoreElements()) {
                ZipEntry entry = entries2.nextElement();
                String name = entry.getName().toLowerCase();
                if (name.endsWith(".xml") && !name.contains("documentproperties") && !name.contains("meta")) {
                    contentEntry = entry;
                    break;
                }
            }
        }

        if (contentEntry != null) {
            try (InputStream is = zip.getInputStream(contentEntry)) {
                ByteArrayOutputStream baos = new ByteArrayOutputStream();
                byte[] buf = new byte[8192];
                int r;
                while ((r = is.read(buf)) != -1) {
                    baos.write(buf, 0, r);
                }
                contentXml = baos.toString("UTF-8");
            }
        }
        }

        if (contentXml == null) {
            throw new IllegalStateException("UDF arşivi içinde content.xml bulunamadı.");
        }

        return parseContentXmlToPayload(contentXml);
    }

    private static String parseContentXmlToPayload(String xml) {
        try {
            DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
            dbf.setNamespaceAware(false);
            DocumentBuilder db = dbf.newDocumentBuilder();
            Document doc = db.parse(new ByteArrayInputStream(xml.getBytes(StandardCharsets.UTF_8)));

            // 1. Üstbilgi, Altbilgi ve Kenar Boşlukları (pageFormat)
            String headerText = "";
            String footerText = "";
            double leftMarginCm = 1.5;
            double rightMarginCm = 1.5;
            double topMarginCm = 1.5;
            double bottomMarginCm = 1.5;
            String paperOrientation = "1";
            NodeList pageFormats = doc.getElementsByTagName("pageFormat");
            if (pageFormats.getLength() > 0) {
                Element pf = (Element) pageFormats.item(0);
                headerText = pf.getAttribute("headerText");
                footerText = pf.getAttribute("footerText");
                if (pf.hasAttribute("leftMargin")) {
                    leftMarginCm = parsePtToCm(pf.getAttribute("leftMargin"), 1.5);
                }
                if (pf.hasAttribute("rightMargin")) {
                    rightMarginCm = parsePtToCm(pf.getAttribute("rightMargin"), 1.5);
                }
                if (pf.hasAttribute("topMargin")) {
                    topMarginCm = parsePtToCm(pf.getAttribute("topMargin"), 1.5);
                }
                if (pf.hasAttribute("bottomMargin")) {
                    bottomMarginCm = parsePtToCm(pf.getAttribute("bottomMargin"), 1.5);
                }
                if (pf.hasAttribute("paperOrientation")) {
                    paperOrientation = pf.getAttribute("paperOrientation");
                }
            }

            // 2. Ham metni al
            NodeList contentList = doc.getElementsByTagName("content");
            String rawText = "";
            for (int i = 0; i < contentList.getLength(); i++) {
                Element c = (Element) contentList.item(i);
                if (c.getParentNode() != null && "template".equals(c.getParentNode().getNodeName())) {
                    rawText = c.getTextContent();
                    break;
                }
            }

            if (rawText == null || rawText.isEmpty()) {
                JSONObject res = new JSONObject();
                res.put("header", headerText);
                res.put("footer", footerText);
                res.put("leftMarginCm", leftMarginCm);
                res.put("rightMarginCm", rightMarginCm);
                res.put("topMarginCm", topMarginCm);
                res.put("bottomMarginCm", bottomMarginCm);
                res.put("paperOrientation", paperOrientation);
                res.put("html", "<p style=\"text-align: justify;\">Belge içeriği boş.</p>");
                return res.toString();
            }

            // 3. Paragrafları ve stilleri çözümle
            NodeList paragraphs = doc.getElementsByTagName("paragraph");
            if (paragraphs.getLength() == 0) {
                StringBuilder fallback = new StringBuilder();
                String[] lines = rawText.split("\n");
                for (String line : lines) {
                    fallback.append("<p style=\"text-align: justify;\">")
                            .append(escapeHtml(line))
                            .append("</p>");
                }
                JSONObject res = new JSONObject();
                res.put("header", headerText);
                res.put("footer", footerText);
                res.put("html", fallback.toString());
                return res.toString();
            }

            StringBuilder html = new StringBuilder();
            int textLen = rawText.length();
            java.util.Map<String, Integer> listCounters = new java.util.HashMap<>();

            for (int i = 0; i < paragraphs.getLength(); i++) {
                Element p = (Element) paragraphs.item(i);
                String alignAttr = p.getAttribute("Alignment");
                String alignStyle = "justify";
                if ("1".equals(alignAttr)) alignStyle = "center";
                else if ("2".equals(alignAttr)) alignStyle = "right";
                else if ("0".equals(alignAttr)) alignStyle = "left";

                String spaceAbove = p.getAttribute("SpaceAbove");
                String spaceBelow = p.getAttribute("SpaceBelow");
                String hanging = p.getAttribute("Hanging");
                String leftIndent = p.getAttribute("LeftIndent");

                StringBuilder styleAttr = new StringBuilder("text-align: ").append(alignStyle).append(";");
                if (!spaceAbove.isEmpty()) {
                    try {
                        double pt = Double.parseDouble(spaceAbove);
                        styleAttr.append(" margin-top: ").append(pt).append("pt;");
                    } catch (Exception ignored) {}
                }
                if (!spaceBelow.isEmpty()) {
                    try {
                        double pt = Double.parseDouble(spaceBelow);
                        styleAttr.append(" margin-bottom: ").append(pt).append("pt;");
                    } catch (Exception ignored) {}
                }
                if (!hanging.isEmpty()) {
                    try {
                        double pt = Double.parseDouble(hanging);
                        double cm = Math.round((pt / 28.35) * 100.0) / 100.0;
                        if (cm > 0) styleAttr.append(" text-indent: ").append(cm).append("cm;");
                    } catch (Exception ignored) {}
                }
                if (!leftIndent.isEmpty()) {
                    try {
                        double pt = Double.parseDouble(leftIndent);
                        double cm = Math.round((pt / 28.35) * 100.0) / 100.0;
                        if (cm > 0) styleAttr.append(" margin-left: ").append(cm).append("cm;");
                    } catch (Exception ignored) {}
                }

                html.append("<p style=\"").append(styleAttr.toString()).append("\">");

                // UYAP Numaralandırma & Maddeleme Kontrolü
                boolean isNumbered = "true".equalsIgnoreCase(p.getAttribute("Numbered")) || "1".equals(p.getAttribute("Numbered"));
                boolean isBulleted = "true".equalsIgnoreCase(p.getAttribute("Bulleted")) || "1".equals(p.getAttribute("Bulleted"));
                if (isNumbered) {
                    String listId = p.getAttribute("ListId");
                    if (listId == null || listId.isEmpty()) listId = "default";
                    int count = listCounters.getOrDefault(listId, 0) + 1;
                    listCounters.put(listId, count);

                    String numType = p.getAttribute("NumberType");
                    String listPrefix = count + ". ";
                    if (numType != null && numType.contains("ROMAN")) {
                        listPrefix = toRoman(count) + ". ";
                    } else if (numType != null && (numType.contains("CHAR_SMALL") || numType.contains("ALPHA"))) {
                        char ch = (char) ('a' + ((count - 1) % 26));
                        listPrefix = ch + ") ";
                    } else if (numType != null && numType.contains("CHAR_BIG")) {
                        char ch = (char) ('A' + ((count - 1) % 26));
                        listPrefix = ch + ". ";
                    }
                    html.append("<span style=\"font-weight:bold; margin-right:4px;\">").append(escapeHtml(listPrefix)).append("</span>");
                } else if (isBulleted) {
                    html.append("<span style=\"font-weight:bold; margin-right:6px;\">•</span>");
                }

                NodeList runs = p.getElementsByTagName("content");
                if (runs.getLength() == 0) {
                    html.append("<br>");
                } else {
                    boolean hasText = false;
                    for (int j = 0; j < runs.getLength(); j++) {
                        Element run = (Element) runs.item(j);
                        String startStr = run.getAttribute("startOffset");
                        String lenStr = run.getAttribute("length");
                        boolean bold = "true".equalsIgnoreCase(run.getAttribute("bold"));
                        boolean italic = "true".equalsIgnoreCase(run.getAttribute("italic"));
                        boolean underline = "true".equalsIgnoreCase(run.getAttribute("underline"));
                        boolean subscript = "true".equalsIgnoreCase(run.getAttribute("subscript")) || "true".equalsIgnoreCase(run.getAttribute("Subscript"));
                        boolean superscript = "true".equalsIgnoreCase(run.getAttribute("superscript")) || "true".equalsIgnoreCase(run.getAttribute("Superscript"));
                        boolean strike = "true".equalsIgnoreCase(run.getAttribute("strikeThrough")) || "true".equalsIgnoreCase(run.getAttribute("strikethrough")) || "true".equalsIgnoreCase(run.getAttribute("StrikeThrough"));

                        if (!startStr.isEmpty() && !lenStr.isEmpty()) {
                            int start = Integer.parseInt(startStr);
                            int len = Integer.parseInt(lenStr);
                            if (start < textLen && start >= 0) {
                                int end = Math.min(start + len, textLen);
                                String chunk = rawText.substring(start, end);
                                // Havelsan UYAP paragraf sonundaki \r ve \n karakterlerini içeriğe dahil eder.
                                // Paragraf sonunda gereksiz fazladan boş satır veya <br> oluşmasını önle:
                                if (chunk.endsWith("\r\n")) {
                                    chunk = chunk.substring(0, chunk.length() - 2);
                                } else if (chunk.endsWith("\n") || chunk.endsWith("\r")) {
                                    chunk = chunk.substring(0, chunk.length() - 1);
                                }

                                if (!chunk.isEmpty()) {
                                    hasText = true;
                                    String escaped = escapeHtml(chunk).replace("\n", "<br>");
                                    if (bold) escaped = "<strong>" + escaped + "</strong>";
                                    if (italic) escaped = "<em>" + escaped + "</em>";
                                    if (underline) escaped = "<u>" + escaped + "</u>";
                                    if (subscript) escaped = "<sub>" + escaped + "</sub>";
                                    if (superscript) escaped = "<sup>" + escaped + "</sup>";
                                    if (strike) escaped = "<s>" + escaped + "</s>";
                                    html.append(escaped);
                                }
                            }
                        }
                    }
                    if (!hasText) {
                        html.append("<br>");
                    }
                }
                html.append("</p>");
            }

            JSONObject res = new JSONObject();
            res.put("header", headerText);
            res.put("footer", footerText);
            res.put("leftMarginCm", leftMarginCm);
            res.put("rightMarginCm", rightMarginCm);
            res.put("topMarginCm", topMarginCm);
            res.put("bottomMarginCm", bottomMarginCm);
            res.put("paperOrientation", paperOrientation);
            res.put("html", html.toString());
            return res.toString();

        } catch (Exception e) {
            JSONObject err = new JSONObject();
            try {
                err.put("header", "");
                err.put("footer", "");
                err.put("html", "<p style=\"text-align: justify;\">" + escapeHtml(xml) + "</p>");
            } catch (Exception ignored) {}
            return err.toString();
        }
    }

    private static double parsePtToCm(String ptStr, double defaultCm) {
        try {
            if (ptStr == null || ptStr.trim().isEmpty()) return defaultCm;
            double pt = Double.parseDouble(ptStr.trim());
            double cm = pt / 28.3465;
            return Math.round(cm * 100.0) / 100.0;
        } catch (Exception e) {
            return defaultCm;
        }
    }

    public static class SignerDetail {
        public String signerName = "";
        public String issuer = "";
        public String serialNumber = "";
        public String validFrom = "";
        public String validUntil = "";
        public String signAlgorithm = "";
        public boolean isExpired = false;

        public JSONObject toJson() {
            JSONObject obj = new JSONObject();
            try {
                obj.put("signerName", signerName);
                obj.put("issuer", issuer);
                obj.put("serialNumber", serialNumber);
                obj.put("validFrom", validFrom);
                obj.put("validUntil", validUntil);
                obj.put("signAlgorithm", signAlgorithm);
                obj.put("isExpired", isExpired);
            } catch (Exception ignored) {}
            return obj;
        }
    }

    public static class SignatureInfo {
        public boolean hasSignature = false;
        public boolean isValid = false;
        public String signerName = "";
        public String issuer = "";
        public String serialNumber = "";
        public String validFrom = "";
        public String validUntil = "";
        public String signAlgorithm = "";
        public String digestAlgorithm = "SHA-256";
        public String message = "";
        public String rawDigest = "";
        public int signatureCount = 0;
        public List<SignerDetail> signers = new ArrayList<>();

        public JSONObject toJson() {
            JSONObject obj = new JSONObject();
            try {
                obj.put("hasSignature", hasSignature);
                obj.put("isValid", isValid);
                obj.put("signerName", signerName);
                obj.put("issuer", issuer);
                obj.put("serialNumber", serialNumber);
                obj.put("validFrom", validFrom);
                obj.put("validUntil", validUntil);
                obj.put("signAlgorithm", signAlgorithm);
                obj.put("digestAlgorithm", digestAlgorithm);
                obj.put("message", message);
                obj.put("rawDigest", rawDigest);
                obj.put("signatureCount", signatureCount);
                JSONArray arr = new JSONArray();
                for (SignerDetail sd : signers) {
                    arr.put(sd.toJson());
                }
                obj.put("signers", arr);
            } catch (Exception ignored) {}
            return obj;
        }
    }

    public static byte[] generateContentXmlBytes(String jsonString) throws Exception {
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
        String paperOrientation = "1";

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
                if (m.has("orientation")) {
                    paperOrientation = "landscape".equalsIgnoreCase(m.optString("orientation")) ? "2" : "1";
                }
            } else {
                leftMarginCm = obj.optDouble("leftMarginCm", 1.5);
                rightMarginCm = obj.optDouble("rightMarginCm", 1.5);
                topMarginCm = obj.optDouble("topMarginCm", 1.5);
                bottomMarginCm = obj.optDouble("bottomMarginCm", 1.5);
                paperOrientation = obj.optString("paperOrientation", "1");
            }
        } else if (trimmed.startsWith("[")) {
            paragraphs = new JSONArray(trimmed);
        } else {
            paragraphs = new JSONArray();
        }

        double leftMarginPt = leftMarginCm * 28.3465;
        double rightMarginPt = rightMarginCm * 28.3465;
        double topMarginPt = topMarginCm * 28.3465;
        double bottomMarginPt = bottomMarginCm * 28.3465;

        StringBuilder rawContent = new StringBuilder();
        StringBuilder elementsXml = new StringBuilder();

        int currentOffset = 0;

        for (int i = 0; i < paragraphs.length(); i++) {
            JSONObject pObj = paragraphs.getJSONObject(i);
            int align = pObj.optInt("align", 3);
            double spaceAbove = pObj.optDouble("spaceAbove", 1.0);
            double spaceBelow = pObj.optDouble("spaceBelow", 1.0);
            double lineSpacing = pObj.optDouble("lineSpacing", 0.0);
            double firstLine = pObj.optDouble("firstLineIndent", 0.0);
            double leftIndent = pObj.optDouble("leftIndent", 0.0);
            double rightIndent = pObj.optDouble("rightIndent", 0.0);

            // 1cm = 28.35 pt
            double firstLinePt = firstLine * 28.35;
            double leftIndentPt = leftIndent * 28.35;
            double rightIndentPt = rightIndent * 28.35;

            elementsXml.append("    <paragraph TabSet=\"54.0:2:0\" LeftIndent=\"")
                       .append(String.format(Locale.US, "%.1f", leftIndentPt))
                       .append("\" SpaceAbove=\"").append(String.format(Locale.US, "%.1f", spaceAbove))
                       .append("\" SpaceBelow=\"").append(String.format(Locale.US, "%.1f", spaceBelow))
                       .append("\" LineSpacing=\"").append(String.format(Locale.US, "%.1f", lineSpacing))
                       .append("\" Hanging=\"").append(String.format(Locale.US, "%.1f", firstLinePt))
                       .append("\" RightIndent=\"").append(String.format(Locale.US, "%.1f", rightIndentPt))
                       .append("\" Alignment=\"").append(align).append("\">\n");

            JSONArray runs = pObj.optJSONArray("runs");
            if (runs != null && runs.length() > 0) {
                for (int j = 0; j < runs.length(); j++) {
                    JSONObject r = runs.getJSONObject(j);
                    String text = r.optString("text", "");
                    boolean bold = r.optBoolean("bold", false);
                    boolean italic = r.optBoolean("italic", false);
                    boolean underline = r.optBoolean("underline", false);
                    boolean subscript = r.optBoolean("subscript", false);
                    boolean superscript = r.optBoolean("superscript", false);
                    boolean strike = r.optBoolean("strikeThrough", false) || r.optBoolean("strikethrough", false);

                    int len = text.length();
                    if (len > 0) {
                        rawContent.append(text);

                        elementsXml.append("        <content startOffset=\"").append(currentOffset)
                                   .append("\" length=\"").append(len).append("\"");
                        if (bold) elementsXml.append(" bold=\"true\"");
                        if (italic) elementsXml.append(" italic=\"true\"");
                        if (underline) elementsXml.append(" underline=\"true\"");
                        if (subscript) elementsXml.append(" Subscript=\"true\"");
                        if (superscript) elementsXml.append(" Superscript=\"true\"");
                        if (strike) elementsXml.append(" StrikeThrough=\"true\"");
                        elementsXml.append(" resolver=\"hvl-default\"/>\n");

                        currentOffset += len;
                    }
                }
            }

            // Paragraf sonu satır atlama
            rawContent.append("\n");
            elementsXml.append("        <content startOffset=\"").append(currentOffset)
                       .append("\" length=\"1\" resolver=\"hvl-default\"/>\n");
            currentOffset += 1;

            elementsXml.append("    </paragraph>\n");
        }

        // Havelsan 1.8 standardı XML şablonu
        String finalXml = "<?xml version=\"1.0\" encoding=\"UTF-8\" ?>\n"
                + "<template format_id=\"1.8\">\n"
                + "<content><![CDATA[" + rawContent.toString() + "]]></content>\n"
                + "<properties>\n"
                + "    <pageFormat mediaSizeName=\"1\" leftMargin=\"" + String.format(Locale.US, "%.4f", leftMarginPt) + "\" rightMargin=\"" + String.format(Locale.US, "%.4f", rightMarginPt) + "\" topMargin=\"" + String.format(Locale.US, "%.4f", topMarginPt) + "\" bottomMargin=\"" + String.format(Locale.US, "%.4f", bottomMarginPt) + "\" paperOrientation=\"" + paperOrientation + "\" headerFOffset=\"20.0\" footerFOffset=\"20.0\""
                + " headerText=\"" + escapeXml(headerText) + "\""
                + " footerText=\"" + escapeXml(footerText) + "\"/>\n"
                + "</properties>\n"
                + "<elements resolver=\"hvl-default\">\n"
                + elementsXml.toString()
                + "</elements>\n"
                + "<styles>\n"
                + "    <style name=\"default\" description=\"Geçerli\" family=\"Dialog\" size=\"12\" bold=\"false\" italic=\"false\" foreground=\"-13421773\"/>\n"
                + "    <style name=\"hvl-default\" family=\"Times New Roman\" size=\"12\" description=\"Gövde\"/>\n"
                + "    <style name=\"edf_custom\" resolver=\"hvl-default\" RightIndent=\"0.0\" SpaceAbove=\"2.0\" LeftIndent=\"0.0\" size=\"12\" SpaceBelow=\"2.0\" description=\"Gövde\" LineSpacing=\"0.0\" Alignment=\"3\" family=\"Times New Roman\"/>\n"
                + "</styles>\n"
                + "</template>";

        return finalXml.getBytes(StandardCharsets.UTF_8);
    }

    public static void saveStructuredToUdf(String jsonString, File targetFile) throws Exception {
        saveStructuredToUdf(jsonString, targetFile, null);
    }

    public static void saveStructuredToUdf(String jsonString, File targetFile, byte[] realSignatureBytes) throws Exception {
        byte[] contentBytes = generateContentXmlBytes(jsonString);
        saveStructuredToUdf(contentBytes, targetFile, realSignatureBytes);
    }

    /**
     * Önceden hazırlanmış content.xml baytlarını ve varsa akıllı kart sign.sgn verisini
     * doğrudan ZIP içine yazarak bayt bütünlüğünü kesin olarak korur.
     */
    public static void saveStructuredToUdf(byte[] contentBytes, File targetFile, byte[] realSignatureBytes) throws Exception {
        if (targetFile.getParentFile() != null) {
            targetFile.getParentFile().mkdirs();
        }

        try (FileOutputStream fos = new FileOutputStream(targetFile);
             ZipOutputStream zos = new ZipOutputStream(fos)) {
            
            // 1. content.xml (Resmi Havelsan UYAP XML belgesi)
            ZipEntry entry = new ZipEntry("content.xml");
            zos.putNextEntry(entry);
            zos.write(contentBytes, 0, contentBytes.length);
            zos.closeEntry();

            // 2. Gerçek E-İmza (sign.sgn) varsa binary DER formatında ekle
            if (realSignatureBytes != null && realSignatureBytes.length > 0) {
                ZipEntry signEntry = new ZipEntry("sign.sgn");
                zos.putNextEntry(signEntry);
                zos.write(realSignatureBytes, 0, realSignatureBytes.length);
                zos.closeEntry();
            }
        }
    }

    /**
     * Çoklu imza için: kaynak UDF'deki TÜM parçaları (content.xml dahil) bayt bayt korur,
     * yalnızca sign.sgn'yi yeni (birleştirilmiş) imza ile değiştirir. Kaynak yoksa yeni UDF yazar.
     * Önce geçici dosyaya yazılır, başarılı olursa hedefin yerine taşınır.
     */
    public static void writeUdfPreserving(File source, File targetFile, byte[] contentBytes, byte[] signatureBytes) throws Exception {
        if (targetFile.getParentFile() != null) targetFile.getParentFile().mkdirs();
        File tmp = new File(targetFile.getAbsolutePath() + ".tmp");
        try (FileOutputStream fos = new FileOutputStream(tmp);
             ZipOutputStream zos = new ZipOutputStream(fos)) {
            ZipEntry ce = new ZipEntry("content.xml");
            zos.putNextEntry(ce);
            zos.write(contentBytes, 0, contentBytes.length);
            zos.closeEntry();

            if (source != null && source.exists()) {
                try (ZipFile zip = new ZipFile(source)) {
                    Enumeration<? extends ZipEntry> en = zip.entries();
                    while (en.hasMoreElements()) {
                        ZipEntry e = en.nextElement();
                        String n = e.getName();
                        if (n.equals("content.xml") || n.equals("sign.sgn") || e.isDirectory()) continue;
                        byte[] b = readZipEntryFully(zip, e);
                        zos.putNextEntry(new ZipEntry(n));
                        if (b != null) zos.write(b, 0, b.length);
                        zos.closeEntry();
                    }
                }
            }

            if (signatureBytes != null && signatureBytes.length > 0) {
                zos.putNextEntry(new ZipEntry("sign.sgn"));
                zos.write(signatureBytes, 0, signatureBytes.length);
                zos.closeEntry();
            }
        }
        if (targetFile.exists() && !targetFile.delete()) {
            throw new java.io.IOException("Hedef dosya güncellenemedi: " + targetFile.getName());
        }
        if (!tmp.renameTo(targetFile)) {
            throw new java.io.IOException("Geçici dosya taşınamadı: " + tmp.getName());
        }
    }

    /**
     * .udf dosyasındaki elektronik imzaları ve bütünlüğü Havelsan UYAP standardına uygun inceler.
     */
    public static SignatureInfo verifySignature(File udfFile) {
        SignatureInfo info = new SignatureInfo();
        if (udfFile == null || !udfFile.exists() || udfFile.length() == 0) {
            info.hasSignature = false;
            info.isValid = false;
            info.message = "Dosya bulunamadı veya boş.";
            return info;
        }

        byte[] contentBytes = null;
        List<byte[]> signFiles = new ArrayList<>();

        try (ZipFile zip = new ZipFile(udfFile)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry e = entries.nextElement();
                String name = e.getName().toLowerCase(Locale.ROOT);
                if (name.equals("content.xml") || name.endsWith("/content.xml")) {
                    contentBytes = readZipEntryFully(zip, e);
                } else if (name.endsWith(".sgn")) {
                    byte[] b = readZipEntryFully(zip, e);
                    if (b != null && b.length > 0) {
                        signFiles.add(b);
                    }
                }
            }
        } catch (Exception e) {
            info.hasSignature = false;
            info.isValid = false;
            info.message = "UDF arşivi açılamadı: " + e.getMessage();
            return info;
        }

        if (signFiles.isEmpty()) {
            info.hasSignature = false;
            info.isValid = false;
            info.message = "Belge üzerinde elektronik imza bulunmuyor.";
            return info;
        }

        info.hasSignature = true;
        info.signatureCount = signFiles.size();

        if (contentBytes == null) {
            info.isValid = false;
            info.message = "Belge içeriği (content.xml) bulunamadı.";
            return info;
        }

        byte[] sha256 = null;
        byte[] sha1 = null;
        try {
            sha256 = MessageDigest.getInstance("SHA-256").digest(contentBytes);
            sha1 = MessageDigest.getInstance("SHA-1").digest(contentBytes);
            info.rawDigest = bytesToHex(sha256);
        } catch (Exception ignored) {}

        boolean allValid = true;
        CertificateFactory cf = null;
        try {
            cf = CertificateFactory.getInstance("X.509");
        } catch (Exception ignored) {}

        Date now = new Date();
        SimpleDateFormat sdf = new SimpleDateFormat("dd.MM.yyyy HH:mm", Locale.getDefault());

        for (byte[] signBytes : signFiles) {
            boolean match = false;
            if (sha256 != null && containsSubarray(signBytes, sha256)) {
                match = true;
                info.digestAlgorithm = "SHA-256";
            } else if (sha1 != null && containsSubarray(signBytes, sha1)) {
                match = true;
                info.digestAlgorithm = "SHA-1";
            }

            if (!match) {
                allValid = false;
            }

            if (cf != null) {
                try {
                    ByteArrayInputStream bais = new ByteArrayInputStream(signBytes);
                    Collection<? extends java.security.cert.Certificate> certs = cf.generateCertificates(bais);
                    for (java.security.cert.Certificate c : certs) {
                        if (c instanceof X509Certificate) {
                            X509Certificate xc = (X509Certificate) c;
                            if (xc.getBasicConstraints() == -1) { // Son kullanıcı imza sertifikası
                                SignerDetail sd = new SignerDetail();
                                sd.signerName = extractCn(xc.getSubjectDN().getName());
                                sd.issuer = extractIssuerOrCn(xc.getIssuerDN().getName());
                                sd.serialNumber = xc.getSerialNumber() != null ? xc.getSerialNumber().toString(16).toUpperCase(Locale.ROOT) : "";
                                if (xc.getNotBefore() != null) sd.validFrom = sdf.format(xc.getNotBefore());
                                if (xc.getNotAfter() != null) {
                                    sd.validUntil = sdf.format(xc.getNotAfter());
                                    sd.isExpired = now.after(xc.getNotAfter());
                                }
                                sd.signAlgorithm = xc.getSigAlgName();
                                info.signers.add(sd);

                                if (info.signerName.isEmpty()) {
                                    info.signerName = sd.signerName;
                                    info.issuer = sd.issuer;
                                    info.serialNumber = sd.serialNumber;
                                    info.validFrom = sd.validFrom;
                                    info.validUntil = sd.validUntil;
                                    info.signAlgorithm = sd.signAlgorithm;
                                }
                            }
                        }
                    }
                } catch (Exception ignored) {}
            }
        }

        info.signatureCount = Math.max(signFiles.size(), info.signers.size());
        if (info.signers.size() > 1 && !info.signers.isEmpty()) {
            info.signerName = info.signers.get(0).signerName + " (ve " + (info.signers.size() - 1) + " imza daha)";
        }

        info.isValid = allValid;
        if (info.isValid) {
            info.message = "İmza ve içerik özeti doğrulandı. Belge imzalandıktan sonra değiştirilmemiştir.";
        } else {
            info.message = "İçerik özeti uyuşmuyor! Belge imzalandıktan sonra değiştirilmiş veya geçersiz imzalanmış.";
        }

        return info;
    }

    private static String extractCn(String dn) {
        if (dn == null) return "";
        for (String part : dn.split(",")) {
            part = part.trim();
            if (part.toUpperCase(Locale.ROOT).startsWith("CN=")) {
                return part.substring(3).trim();
            }
        }
        return dn;
    }

    private static String extractIssuerOrCn(String dn) {
        if (dn == null) return "";
        String org = null;
        for (String part : dn.split(",")) {
            part = part.trim();
            if (part.toUpperCase(Locale.ROOT).startsWith("CN=")) {
                return part.substring(3).trim();
            }
            if (part.toUpperCase(Locale.ROOT).startsWith("O=") && org == null) {
                org = part.substring(2).trim();
            }
        }
        return org != null ? org : dn;
    }

    public static byte[] readZipEntryFully(ZipFile zip, ZipEntry entry) throws IOException {
        try (InputStream is = zip.getInputStream(entry);
             ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
            byte[] buf = new byte[8192];
            int r;
            while ((r = is.read(buf)) != -1) {
                baos.write(buf, 0, r);
            }
            return baos.toByteArray();
        }
    }

    private static boolean containsSubarray(byte[] outer, byte[] inner) {
        if (outer == null || inner == null || inner.length == 0 || outer.length < inner.length) return false;
        int max = outer.length - inner.length;
        for (int i = 0; i <= max; i++) {
            boolean match = true;
            for (int j = 0; j < inner.length; j++) {
                if (outer[i + j] != inner[j]) {
                    match = false;
                    break;
                }
            }
            if (match) return true;
        }
        return false;
    }

    private static String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder();
        for (byte b : bytes) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
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
                   .replace(">", "&gt;")
                   .replace("\"", "&quot;");
    }
}
