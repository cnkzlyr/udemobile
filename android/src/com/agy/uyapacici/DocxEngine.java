package com.agy.uyapacici;

import org.json.JSONArray;
import org.json.JSONObject;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Enumeration;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;

public class DocxEngine {

    /**
     * .docx dosyasını okuyup mobil editör için HTML'e dönüştürür.
     */
    public static String readDocxToHtml(File file) throws Exception {
        String docXml = null;
        try (ZipFile zip = new ZipFile(file)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                if ("word/document.xml".equals(entry.getName())) {
                    try (InputStream is = zip.getInputStream(entry)) {
                        byte[] bytes = new byte[(int) entry.getSize()];
                        int offset = 0;
                        while (offset < bytes.length) {
                            int read = is.read(bytes, offset, bytes.length - offset);
                            if (read == -1) break;
                            offset += read;
                        }
                        docXml = new String(bytes, StandardCharsets.UTF_8);
                        break;
                    }
                }
            }
        }

        if (docXml == null) {
            throw new IllegalStateException("DOCX içinde word/document.xml bulunamadı.");
        }

        return parseDocxXmlToHtml(docXml);
    }

    private static String parseDocxXmlToHtml(String xml) {
        try {
            DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
            dbf.setNamespaceAware(false);
            DocumentBuilder db = dbf.newDocumentBuilder();
            Document doc = db.parse(new ByteArrayInputStream(xml.getBytes(StandardCharsets.UTF_8)));

            StringBuilder html = new StringBuilder();
            NodeList pList = doc.getElementsByTagName("w:p");

            for (int i = 0; i < pList.getLength(); i++) {
                Element p = (Element) pList.item(i);
                String align = "justify";

                // Hizalama kontrolü
                NodeList jcList = p.getElementsByTagName("w:jc");
                if (jcList.getLength() > 0) {
                    Element jc = (Element) jcList.item(0);
                    String val = jc.getAttribute("w:val");
                    if ("center".equalsIgnoreCase(val)) align = "center";
                    else if ("right".equalsIgnoreCase(val)) align = "right";
                    else if ("left".equalsIgnoreCase(val)) align = "left";
                    else if ("both".equalsIgnoreCase(val)) align = "justify";
                }

                html.append("<p style=\"text-align: ").append(align).append(";\">");

                // Paragraf içi metin parçaları (w:r)
                NodeList rList = p.getElementsByTagName("w:r");
                boolean hasContent = false;

                for (int j = 0; j < rList.getLength(); j++) {
                    Element r = (Element) rList.item(j);
                    boolean isBold = r.getElementsByTagName("w:b").getLength() > 0;
                    boolean isItalic = r.getElementsByTagName("w:i").getLength() > 0;
                    boolean isUnderline = r.getElementsByTagName("w:u").getLength() > 0;

                    NodeList tList = r.getElementsByTagName("w:t");
                    for (int k = 0; k < tList.getLength(); k++) {
                        String text = tList.item(k).getTextContent();
                        if (text != null && !text.isEmpty()) {
                            hasContent = true;
                            String escaped = escapeHtml(text).replace("\n", "<br>");
                            if (isBold) escaped = "<strong>" + escaped + "</strong>";
                            if (isItalic) escaped = "<em>" + escaped + "</em>";
                            if (isUnderline) escaped = "<u>" + escaped + "</u>";
                            html.append(escaped);
                        }
                    }
                }

                if (!hasContent) {
                    html.append("<br>");
                }
                html.append("</p>\n");
            }

            return html.toString();

        } catch (Exception e) {
            return "<p style=\"text-align: justify;\">DOCX okuma hatası: " + escapeHtml(e.getMessage()) + "</p>";
        }
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
                        docXml.append("      </w:rPr>\n")
                              .append("      <w:t xml:space=\"preserve\">").append(escapeXml(text)).append("</w:t>\n")
                              .append("    </w:r>\n");
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
                + "</Types>";

        String rootRelsXml = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
                + "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">\n"
                + "  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>\n"
                + "</Relationships>";

        if (targetFile.getParentFile() != null) {
            targetFile.getParentFile().mkdirs();
        }

        try (FileOutputStream fos = new FileOutputStream(targetFile);
             ZipOutputStream zos = new ZipOutputStream(fos)) {

            writeZipEntry(zos, "[Content_Types].xml", contentTypesXml);
            writeZipEntry(zos, "_rels/.rels", rootRelsXml);
            writeZipEntry(zos, "word/document.xml", docXml.toString());
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
