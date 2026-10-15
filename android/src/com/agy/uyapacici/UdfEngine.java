package com.agy.uyapacici;

import org.json.JSONArray;
import org.json.JSONObject;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
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

public class UdfEngine {

    /**
     * .udf dosyasını okuyup mobil editör için HTML'e dönüştürür.
     */
    public static String readUdfToHtml(File file) throws Exception {
        if (!file.exists()) {
            throw new IllegalArgumentException("Dosya bulunamadı: " + file.getAbsolutePath());
        }

        String contentXml = null;
        try (ZipFile zip = new ZipFile(file)) {
            Enumeration<? extends ZipEntry> entries = zip.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                if (entry.getName().contains("content.xml") || entry.getName().endsWith(".xml")) {
                    try (InputStream is = zip.getInputStream(entry)) {
                        byte[] bytes = new byte[(int) entry.getSize()];
                        int offset = 0;
                        while (offset < bytes.length) {
                            int read = is.read(bytes, offset, bytes.length - offset);
                            if (read == -1) break;
                            offset += read;
                        }
                        contentXml = new String(bytes, StandardCharsets.UTF_8);
                        break;
                    }
                }
            }
        }

        if (contentXml == null) {
            throw new IllegalStateException("UDF arşivi içinde content.xml bulunamadı.");
        }

        return parseContentXmlToHtml(contentXml);
    }

    private static String parseContentXmlToHtml(String xml) {
        try {
            DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
            dbf.setNamespaceAware(false);
            DocumentBuilder db = dbf.newDocumentBuilder();
            Document doc = db.parse(new ByteArrayInputStream(xml.getBytes(StandardCharsets.UTF_8)));

            // 1. Ham metni al
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
                return "<p style=\"text-align: justify;\">Belge içeriği boş.</p>";
            }

            // 2. Paragrafları ve stilleri çözümle
            NodeList paragraphs = doc.getElementsByTagName("paragraph");
            if (paragraphs.getLength() == 0) {
                // Paragraf etiketi yoksa satır başlarına göre p üret
                StringBuilder fallback = new StringBuilder();
                String[] lines = rawText.split("\n");
                for (String line : lines) {
                    fallback.append("<p style=\"text-align: justify;\">")
                            .append(escapeHtml(line))
                            .append("</p>");
                }
                return fallback.toString();
            }

            StringBuilder html = new StringBuilder();
            int textLen = rawText.length();

            for (int i = 0; i < paragraphs.getLength(); i++) {
                Element p = (Element) paragraphs.item(i);
                String alignAttr = p.getAttribute("Alignment");
                String alignStyle = "justify";
                if ("1".equals(alignAttr)) alignStyle = "center";
                else if ("2".equals(alignAttr)) alignStyle = "right";
                else if ("0".equals(alignAttr)) alignStyle = "left";

                html.append("<p style=\"text-align: ").append(alignStyle).append(";\">");

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

                        if (!startStr.isEmpty() && !lenStr.isEmpty()) {
                            int start = Integer.parseInt(startStr);
                            int len = Integer.parseInt(lenStr);
                            if (start < textLen && start >= 0) {
                                int end = Math.min(start + len, textLen);
                                String chunk = rawText.substring(start, end);
                                if (!chunk.isEmpty()) {
                                    hasText = true;
                                    String escaped = escapeHtml(chunk).replace("\n", "<br>");
                                    if (bold) escaped = "<strong>" + escaped + "</strong>";
                                    if (italic) escaped = "<em>" + escaped + "</em>";
                                    if (underline) escaped = "<u>" + escaped + "</u>";
                                    html.append(escaped);
                                }
                            }
                        }
                    }
                    if (!hasText) {
                        html.append("<br>");
                    }
                }
                html.append("</p>\n");
            }

            return html.toString();

        } catch (Exception e) {
            // Hata olursa ham metni güvenli şekilde göster
            return "<p style=\"text-align: justify;\">" + escapeHtml(xml) + "</p>";
        }
    }

    /**
     * Editörden gelen yapılandırılmış JSON verisini geçerli bir Havelsan UYAP 1.8 UDF (.udf) dosyasına dönüştürür.
     */
    public static void saveStructuredToUdf(String jsonArrayString, File targetFile) throws Exception {
        JSONArray paragraphs = new JSONArray(jsonArrayString);

        StringBuilder rawContent = new StringBuilder();
        StringBuilder elementsXml = new StringBuilder();

        int currentOffset = 0;

        for (int i = 0; i < paragraphs.length(); i++) {
            JSONObject pObj = paragraphs.getJSONObject(i);
            int align = pObj.optInt("align", 3);
            JSONArray runs = pObj.optJSONArray("runs");

            elementsXml.append("    <paragraph TabSet=\"54.0:2:0\" LeftIndent=\"0.0\" SpaceAbove=\"1.0\" SpaceBelow=\"1.0\" LineSpacing=\"0.0\" Hanging=\"0.0\" RightIndent=\"0.0\" Alignment=\"")
                       .append(align).append("\">\n");

            if (runs != null && runs.length() > 0) {
                for (int j = 0; j < runs.length(); j++) {
                    JSONObject r = runs.getJSONObject(j);
                    String text = r.optString("text", "");
                    boolean bold = r.optBoolean("bold", false);
                    boolean italic = r.optBoolean("italic", false);
                    boolean underline = r.optBoolean("underline", false);

                    int len = text.length();
                    if (len > 0) {
                        rawContent.append(text);

                        elementsXml.append("        <content startOffset=\"").append(currentOffset)
                                   .append("\" length=\"").append(len).append("\"");
                        if (bold) elementsXml.append(" bold=\"true\"");
                        if (italic) elementsXml.append(" italic=\"true\"");
                        if (underline) elementsXml.append(" underline=\"true\"");
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
                + "    <pageFormat mediaSizeName=\"1\" leftMargin=\"42.525000000000006\" rightMargin=\"42.525000000000006\" topMargin=\"42.525000000000006\" bottomMargin=\"42.52500000000006\" paperOrientation=\"1\" headerFOffset=\"20.0\" footerFOffset=\"20.0\"/>\n"
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

        // Zip olarak .udf oluştur
        if (targetFile.getParentFile() != null) {
            targetFile.getParentFile().mkdirs();
        }

        try (FileOutputStream fos = new FileOutputStream(targetFile);
             ZipOutputStream zos = new ZipOutputStream(fos)) {
            ZipEntry entry = new ZipEntry("content.xml");
            zos.putNextEntry(entry);
            byte[] bytes = finalXml.getBytes(StandardCharsets.UTF_8);
            zos.write(bytes, 0, bytes.length);
            zos.closeEntry();
        }
    }

    private static String escapeHtml(String text) {
        if (text == null) return "";
        return text.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;")
                   .replace("\"", "&quot;");
    }
}
