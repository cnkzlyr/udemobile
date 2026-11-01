package com.agy.uyapacici;

import org.json.JSONArray;
import org.json.JSONObject;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NamedNodeMap;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Date;
import java.util.Enumeration;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;

public class UdfEngine {

    private static String toRoman(int num) {
        String[] m = {"", "M", "MM", "MMM"};
        String[] c = {"", "C", "CC", "CCC", "CD", "D", "DC", "DCC", "DCCC", "CM"};
        String[] x = {"", "X", "XX", "XXX", "XL", "L", "LX", "LXX", "LXXX", "XC"};
        String[] i = {"", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"};
        if (num <= 0 || num > 3999) return String.valueOf(num);
        return m[num / 1000] + c[(num % 1000) / 100] + x[(num % 100) / 10] + i[num % 10];
    }

    private static String buildEmptyPayload(String htmlContent) {
        try {
            JSONObject res = new JSONObject();
            res.put("header", "");
            res.put("headerHtml", "");
            res.put("headerStartPage", 1);
            res.put("footer", "");
            res.put("footerHtml", "");
            res.put("verificationCode", "");
            res.put("leftMarginCm", 1.5);
            res.put("rightMarginCm", 1.5);
            res.put("topMarginCm", 1.5);
            res.put("bottomMarginCm", 1.5);
            res.put("headerMarginCm", 1.25);
            res.put("footerMarginCm", 1.25);
            res.put("paperOrientation", "1");
            res.put("html", htmlContent != null && !htmlContent.isEmpty() ? htmlContent : "<p style=\"text-align: justify;\"><br></p>");
            return res.toString();
        } catch (Exception e) {
            return "{\"html\":\"<p style=\\\"text-align: justify;\\\"><br></p>\"}";
        }
    }

    private static byte[] readFileBytes(File file) throws IOException {
        try (FileInputStream fis = new FileInputStream(file);
             ByteArrayOutputStream baos = new ByteArrayOutputStream((int) Math.min(file.length(), 65536))) {
            byte[] buf = new byte[8192];
            int r;
            while ((r = fis.read(buf)) != -1) {
                baos.write(buf, 0, r);
            }
            return baos.toByteArray();
        }
    }

    /**
     * .udf dosyasını (veya .udf uzantılı XML, DOCX, OLE2 Word 97-2003 .doc, RTF veya düz metin dosyalarını)
     * hatasız okuyup editör için yapılandırılmış JSON/HTML içeriğine dönüştürür.
     */
    public static String readUdfToHtml(File file) throws Exception {
        if (file == null || !file.exists()) {
            throw new IllegalArgumentException("Dosya bulunamadı: " + (file != null ? file.getAbsolutePath() : "null"));
        }

        if (file.length() == 0) {
            return buildEmptyPayload("<p style=\"text-align: justify;\"><br></p>");
        }

        byte[] headerBytes = new byte[(int) Math.min(file.length(), 64)];
        try (FileInputStream fis = new FileInputStream(file)) {
            int read = fis.read(headerBytes);
            if (read <= 0) {
                return buildEmptyPayload("<p style=\"text-align: justify;\"><br></p>");
            }
        }

        // 1. OLE2 Compound Document kontrolü (Word 97-2003 .doc dosyaları, örn: .doc.udf)
        if (headerBytes.length >= 8
                && (headerBytes[0] & 0xFF) == 0xD0 && (headerBytes[1] & 0xFF) == 0xCF
                && (headerBytes[2] & 0xFF) == 0x11 && (headerBytes[3] & 0xFF) == 0xE0
                && (headerBytes[4] & 0xFF) == 0xA1 && (headerBytes[5] & 0xFF) == 0xB1
                && (headerBytes[6] & 0xFF) == 0x1A && (headerBytes[7] & 0xFF) == 0xE1) {
            byte[] allBytes = readFileBytes(file);
            return parseOle2WordDocToPayload(allBytes);
        }

        // 2. Doğrudan sıkıştırılmamış XML kontrolü (<?xml veya <template, UTF-8 BOM dahil)
        String headStr = stripBomAndLeadingGarbage(new String(headerBytes, StandardCharsets.UTF_8));
        if (headStr.startsWith("<?xml") || headStr.startsWith("<template")) {
            byte[] allBytes = readFileBytes(file);
            String xml = stripBomAndLeadingGarbage(new String(allBytes, StandardCharsets.UTF_8));
            return parseContentXmlToPayload(xml, null);
        }

        // 3. RTF kontrolü ({\rtf)
        if (headStr.startsWith("{\\rtf")) {
            byte[] allBytes = readFileBytes(file);
            return parseRtfToPayload(allBytes);
        }

        // 4. ZIP arşivi kontrolü (UDF veya DOCX)
        String contentXml = null;
        String docPropsXml = null;
        boolean hasWordDocXml = false;
        try (ZipFile zip = new ZipFile(file)) {
            if (zip.getEntry("word/document.xml") != null && zip.getEntry("content.xml") == null && zip.getEntry("Content.xml") == null) {
                hasWordDocXml = true;
            } else {
                ZipEntry contentEntry = zip.getEntry("content.xml");
                if (contentEntry == null) {
                    contentEntry = zip.getEntry("Content.xml");
                }
                if (contentEntry == null) {
                    Enumeration<? extends ZipEntry> entries = zip.entries();
                    while (entries.hasMoreElements()) {
                        ZipEntry entry = entries.nextElement();
                        String name = entry.getName().toLowerCase(Locale.ROOT);
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
                        String name = entry.getName().toLowerCase(Locale.ROOT);
                        if (name.endsWith(".xml") && !name.contains("documentproperties") && !name.contains("meta") && !name.contains("rels") && !name.contains("[content_types]")) {
                            contentEntry = entry;
                            break;
                        }
                    }
                }

                if (contentEntry != null) {
                    byte[] cBytes = readZipEntryFully(zip, contentEntry);
                    contentXml = stripBomAndLeadingGarbage(new String(cBytes, StandardCharsets.UTF_8));
                }

                ZipEntry propsEntry = zip.getEntry("documentproperties.xml");
                if (propsEntry == null) propsEntry = zip.getEntry("Documentproperties.xml");
                if (propsEntry != null) {
                    try {
                        byte[] pBytes = readZipEntryFully(zip, propsEntry);
                        docPropsXml = stripBomAndLeadingGarbage(new String(pBytes, StandardCharsets.UTF_8));
                    } catch (Exception ignored) {}
                }
            }
        } catch (Exception zipEx) {
            // ZIP olarak açılamadıysa düz XML veya metin olarak kurtarmayı dene
            byte[] allBytes = readFileBytes(file);
            String rawStr = stripBomAndLeadingGarbage(new String(allBytes, StandardCharsets.UTF_8));
            if (rawStr.startsWith("<")) {
                return parseContentXmlToPayload(rawStr, null);
            }
            return parsePlainTextToPayload(rawStr);
        }

        if (hasWordDocXml) {
            return DocxEngine.readDocxToHtml(file);
        }

        if (contentXml == null) {
            return buildEmptyPayload("<p style=\"text-align: justify;\"><br></p>");
        }

        return parseContentXmlToPayload(contentXml, docPropsXml);
    }

    public static String stripBomAndLeadingGarbage(String s) {
        if (s == null || s.isEmpty()) return "";
        int len = s.length();
        int idx = 0;
        while (idx < len) {
            char ch = s.charAt(idx);
            if (ch == '\uFEFF' || ch == '\uFFFE' || ch == '\u0000' || Character.isWhitespace(ch)) {
                idx++;
            } else {
                break;
            }
        }
        // Eğer ilk birkaç bayt içinde '<' varsa (örn. bozuk BOM sonrası XML), '<' karakterinden başlat
        int firstLt = s.indexOf('<', idx);
        if (firstLt > idx && firstLt - idx <= 10) {
            return s.substring(firstLt);
        }
        return idx > 0 ? s.substring(idx) : s;
    }

    /**
     * Microsoft Word 97-2003 (.doc / OLE2 Compound Binary) dosyasını FIB + Clx Piece Table
     * üzerinden çözümleyerek tüm Türkçe metin ve paragrafları HTML'e dönüştürür.
     */
    public static String parseOle2WordDocToPayload(byte[] data) {
        try {
            if (data == null || data.length < 512) {
                return buildEmptyPayload("<p style=\"text-align: justify;\"><br></p>");
            }
            ByteBuffer bb = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN);
            int sectorShift = bb.getShort(30) & 0xFFFF;
            int sectorSize = 1 << sectorShift;
            int miniSectorShift = bb.getShort(32) & 0xFFFF;
            int miniSectorSize = 1 << miniSectorShift;
            int numFatSectors = bb.getInt(44);
            int firstDirSector = bb.getInt(48);
            int miniStreamCutoff = bb.getInt(56);
            int firstMiniFatSector = bb.getInt(60);
            int numMiniFatSectors = bb.getInt(64);
            int firstDifatSector = bb.getInt(68);
            int numDifatSectors = bb.getInt(72);

            List<Integer> difat = new ArrayList<>();
            for (int i = 0; i < 109 && difat.size() < numFatSectors; i++) {
                int sec = bb.getInt(76 + i * 4);
                if (sec >= 0) difat.add(sec);
            }
            int currDifat = firstDifatSector;
            int intsPerSector = sectorSize / 4;
            for (int d = 0; d < numDifatSectors && currDifat >= 0; d++) {
                int pos = (currDifat + 1) * sectorSize;
                if (pos + sectorSize > data.length) break;
                for (int i = 0; i < intsPerSector - 1 && difat.size() < numFatSectors; i++) {
                    int sec = bb.getInt(pos + i * 4);
                    if (sec >= 0) difat.add(sec);
                }
                currDifat = bb.getInt(pos + (intsPerSector - 1) * 4);
            }

            int[] fat = new int[difat.size() * intsPerSector];
            int fatIdx = 0;
            for (int fatSec : difat) {
                int pos = (fatSec + 1) * sectorSize;
                if (pos + sectorSize > data.length) break;
                for (int i = 0; i < intsPerSector; i++) {
                    fat[fatIdx++] = bb.getInt(pos + i * 4);
                }
            }

            byte[] dirBytes = readOleChain(data, fat, firstDirSector, sectorSize, -1);

            int rootStartSec = -2, rootSize = 0;
            int wordDocStartSec = -2, wordDocSize = 0;
            int table0StartSec = -2, table0Size = 0;
            int table1StartSec = -2, table1Size = 0;

            ByteBuffer dirBb = ByteBuffer.wrap(dirBytes).order(ByteOrder.LITTLE_ENDIAN);
            int numEntries = dirBytes.length / 128;
            for (int i = 0; i < numEntries; i++) {
                int ePos = i * 128;
                int nameLen = dirBb.getShort(ePos + 64) & 0xFFFF;
                byte objType = dirBb.get(ePos + 66);
                if (objType == 0 || nameLen <= 2) continue;
                String name = new String(dirBytes, ePos, Math.min(nameLen - 2, 64), StandardCharsets.UTF_16LE);
                int startSec = dirBb.getInt(ePos + 116);
                int size = dirBb.getInt(ePos + 120);
                if (objType == 5 || "Root Entry".equalsIgnoreCase(name)) {
                    rootStartSec = startSec;
                    rootSize = size;
                } else if ("WordDocument".equalsIgnoreCase(name)) {
                    wordDocStartSec = startSec;
                    wordDocSize = size;
                } else if ("0Table".equalsIgnoreCase(name)) {
                    table0StartSec = startSec;
                    table0Size = size;
                } else if ("1Table".equalsIgnoreCase(name)) {
                    table1StartSec = startSec;
                    table1Size = size;
                }
            }

            if (wordDocStartSec < 0 || wordDocSize <= 0) {
                return parsePlainTextToPayload(new String(data, StandardCharsets.UTF_8));
            }

            byte[] miniStream = (rootStartSec >= 0 && rootSize > 0)
                    ? readOleChain(data, fat, rootStartSec, sectorSize, rootSize)
                    : new byte[0];
            int[] miniFat = new int[0];
            if (firstMiniFatSector >= 0 && numMiniFatSectors > 0) {
                byte[] mfBytes = readOleChain(data, fat, firstMiniFatSector, sectorSize, numMiniFatSectors * sectorSize);
                ByteBuffer mfBb = ByteBuffer.wrap(mfBytes).order(ByteOrder.LITTLE_ENDIAN);
                miniFat = new int[mfBytes.length / 4];
                for (int i = 0; i < miniFat.length; i++) miniFat[i] = mfBb.getInt(i * 4);
            }

            byte[] wordDoc = readOleStream(data, fat, sectorSize, miniStream, miniFat, miniSectorSize, miniStreamCutoff, wordDocStartSec, wordDocSize);
            ByteBuffer wbb = ByteBuffer.wrap(wordDoc).order(ByteOrder.LITTLE_ENDIAN);

            int flags = wbb.getShort(0x000A) & 0xFFFF;
            boolean use1Table = (flags & 0x0200) != 0;
            int tableStart = use1Table ? table1StartSec : table0StartSec;
            int tableSize = use1Table ? table1Size : table0Size;
            if (tableStart < 0) {
                tableStart = table1StartSec >= 0 ? table1StartSec : table0StartSec;
                tableSize = table1StartSec >= 0 ? table1Size : table0Size;
            }

            String extractedText = null;
            Charset cp1254;
            try {
                cp1254 = Charset.forName("windows-1254");
            } catch (Exception e) {
                cp1254 = StandardCharsets.ISO_8859_1;
            }

            int ccpText = wbb.getInt(0x004C);
            if (tableStart >= 0 && tableSize > 0 && wordDoc.length >= 0x01AA) {
                byte[] tableBytes = readOleStream(data, fat, sectorSize, miniStream, miniFat, miniSectorSize, miniStreamCutoff, tableStart, tableSize);
                int fcClx = wbb.getInt(0x01A2);
                int lcbClx = wbb.getInt(0x01A6);
                if (fcClx >= 0 && lcbClx > 0 && fcClx + lcbClx <= tableBytes.length) {
                    ByteBuffer tbb = ByteBuffer.wrap(tableBytes).order(ByteOrder.LITTLE_ENDIAN);
                    int pos = fcClx;
                    int endClx = fcClx + lcbClx;
                    while (pos < endClx && tableBytes[pos] == 1) {
                        int cbGrpprl = tbb.getShort(pos + 1) & 0xFFFF;
                        pos += 3 + cbGrpprl;
                    }
                    if (pos < endClx && tableBytes[pos] == 2) {
                        int lcb = tbb.getInt(pos + 1);
                        int plcPos = pos + 5;
                        int n = (lcb - 4) / 12;
                        if (n > 0 && plcPos + lcb <= tableBytes.length) {
                            StringBuilder sb = new StringBuilder();
                            for (int i = 0; i < n; i++) {
                                int cpStart = tbb.getInt(plcPos + i * 4);
                                int cpEnd = tbb.getInt(plcPos + (i + 1) * 4);
                                int charCount = cpEnd - cpStart;
                                if (charCount <= 0) continue;
                                int pcdPos = plcPos + (n + 1) * 4 + i * 8;
                                int fcCompressed = tbb.getInt(pcdPos + 2);
                                boolean isCompressed = (fcCompressed & 0x40000000) != 0;
                                int fc = fcCompressed & 0x3FFFFFFF;
                                if (isCompressed) {
                                    int byteOffset = fc / 2;
                                    int byteLen = Math.min(charCount, Math.max(0, wordDoc.length - byteOffset));
                                    if (byteLen > 0) {
                                        sb.append(decodeWordCp1254(wordDoc, byteOffset, byteLen, cp1254));
                                    }
                                } else {
                                    int byteOffset = fc;
                                    int byteLen = Math.min(charCount * 2, Math.max(0, wordDoc.length - byteOffset));
                                    if (byteLen > 0) {
                                        sb.append(new String(wordDoc, byteOffset, byteLen, StandardCharsets.UTF_16LE));
                                    }
                                }
                            }
                            if (ccpText > 0 && sb.length() > ccpText) {
                                extractedText = sb.substring(0, ccpText);
                            } else {
                                extractedText = sb.toString();
                            }
                        }
                    }
                }
            }

            if (extractedText == null || extractedText.isEmpty()) {
                int fcMin = wbb.getInt(0x0018);
                int fcMac = wbb.getInt(0x001C);
                if (fcMin >= 0 && fcMac > fcMin && fcMac <= wordDoc.length) {
                    extractedText = decodeWordCp1254(wordDoc, fcMin, fcMac - fcMin, cp1254);
                } else {
                    extractedText = decodeWordCp1254(wordDoc, 0, wordDoc.length, cp1254);
                }
            }

            return convertWordDocTextToPayload(extractedText);
        } catch (Exception e) {
            return buildEmptyPayload("<p style=\"text-align: justify;\"><br></p>");
        }
    }

    private static String decodeWordCp1254(byte[] bytes, int offset, int length, Charset cp1254) {
        String s = new String(bytes, offset, length, cp1254);
        StringBuilder sb = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '\r' || c == '\n' || c == '\t' || c == '\u0007' || c == '\f' || c == '\u000B' || c >= 0x20) {
                sb.append(c == '\u000B' ? '\n' : c);
            }
        }
        return sb.toString();
    }

    private static String convertWordDocTextToPayload(String text) {
        if (text == null || text.isEmpty()) {
            return buildEmptyPayload("<p style=\"text-align: justify;\"><br></p>");
        }
        StringBuilder html = new StringBuilder();
        String normalized = text.replace("\r\n", "\r").replace('\n', '\r');
        String[] rawParas = normalized.split("\r", -1);
        List<List<String>> pendingTableRows = new ArrayList<>();
        List<String> currentRowCells = new ArrayList<>();

        for (String p : rawParas) {
            if (p.indexOf('\u0007') >= 0) {
                // Word tablo hücresi veya satır sonu işareti
                String cleaned = p.replace("\u0007", "").trim();
                if (p.equals("\u0007") || (p.endsWith("\u0007") && cleaned.isEmpty() && !currentRowCells.isEmpty())) {
                    if (!currentRowCells.isEmpty()) {
                        pendingTableRows.add(new ArrayList<>(currentRowCells));
                        currentRowCells.clear();
                    }
                } else {
                    currentRowCells.add(cleaned);
                }
                continue;
            }

            if (!currentRowCells.isEmpty()) {
                pendingTableRows.add(new ArrayList<>(currentRowCells));
                currentRowCells.clear();
            }
            if (!pendingTableRows.isEmpty()) {
                appendSimpleTableHtml(pendingTableRows, html);
                pendingTableRows.clear();
            }

            String line = p.replace("\f", "").trim();
            if (line.isEmpty()) {
                html.append("<p style=\"text-align: justify;\"><br></p>\n");
            } else {
                String escaped = formatParagraphTabs(escapeHtml(line));
                html.append("<p style=\"text-align: justify; margin-top: 2pt; margin-bottom: 2pt;\">")
                    .append(escaped)
                    .append("</p>\n");
            }
        }

        if (!currentRowCells.isEmpty()) {
            pendingTableRows.add(new ArrayList<>(currentRowCells));
        }
        if (!pendingTableRows.isEmpty()) {
            appendSimpleTableHtml(pendingTableRows, html);
        }

        return buildEmptyPayload(html.toString());
    }

    private static void appendSimpleTableHtml(List<List<String>> rows, StringBuilder html) {
        html.append("<table style=\"width:100%; border-collapse:collapse; margin:8px 0; border:1px solid #ccc;\">\n");
        for (List<String> row : rows) {
            html.append("  <tr>\n");
            int cols = Math.max(1, row.size());
            double pct = 100.0 / cols;
            for (String cell : row) {
                html.append("    <td style=\"border:1px solid #ccc; padding:4px 8px; vertical-align:top; width:")
                    .append(String.format(Locale.US, "%.1f", pct)).append("%;\">")
                    .append("<p style=\"text-align: left;\">")
                    .append(cell.isEmpty() ? "<br>" : escapeHtml(cell))
                    .append("</p></td>\n");
            }
            html.append("  </tr>\n");
        }
        html.append("</table>\n");
    }

    private static byte[] readOleChain(byte[] data, int[] fat, int startSec, int sectorSize, int maxBytes) {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        int sec = startSec;
        int safety = 0;
        while (sec >= 0 && sec < fat.length && safety < fat.length + 10) {
            int pos = (sec + 1) * sectorSize;
            if (pos >= 0 && pos + sectorSize <= data.length) {
                baos.write(data, pos, sectorSize);
            } else {
                break;
            }
            if (maxBytes > 0 && baos.size() >= maxBytes) break;
            sec = fat[sec];
            safety++;
        }
        byte[] res = baos.toByteArray();
        if (maxBytes > 0 && res.length > maxBytes) {
            byte[] trimmed = new byte[maxBytes];
            System.arraycopy(res, 0, trimmed, 0, maxBytes);
            return trimmed;
        }
        return res;
    }

    private static byte[] readOleStream(byte[] data, int[] fat, int sectorSize, byte[] miniStream, int[] miniFat, int miniSectorSize, int cutoff, int startSec, int size) {
        if (size < cutoff && miniStream.length > 0 && miniFat.length > 0) {
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            int sec = startSec;
            int safety = 0;
            while (sec >= 0 && sec < miniFat.length && safety < miniFat.length + 10) {
                int pos = sec * miniSectorSize;
                if (pos >= 0 && pos + miniSectorSize <= miniStream.length) {
                    baos.write(miniStream, pos, miniSectorSize);
                } else {
                    break;
                }
                if (baos.size() >= size) break;
                sec = miniFat[sec];
                safety++;
            }
            byte[] res = baos.toByteArray();
            if (res.length > size) {
                byte[] trimmed = new byte[size];
                System.arraycopy(res, 0, trimmed, 0, size);
                return trimmed;
            }
            return res;
        }
        return readOleChain(data, fat, startSec, sectorSize, size);
    }

    public static String parseRtfToPayload(byte[] data) {
        if (data == null || data.length == 0) {
            return buildEmptyPayload("<p style=\"text-align: justify;\"><br></p>");
        }
        Charset cp1254;
        try {
            cp1254 = Charset.forName("windows-1254");
        } catch (Exception e) {
            cp1254 = StandardCharsets.ISO_8859_1;
        }
        String rtf = new String(data, StandardCharsets.ISO_8859_1);
        StringBuilder out = new StringBuilder();
        int len = rtf.length();
        int i = 0;
        int braceDepth = 0;
        int skipDepth = -1;
        while (i < len) {
            char ch = rtf.charAt(i);
            if (ch == '{') {
                braceDepth++;
                if (skipDepth < 0 && i + 1 < len) {
                    String lookahead = rtf.substring(i + 1, Math.min(len, i + 25));
                    if (lookahead.startsWith("\\*") || lookahead.startsWith("\\fonttbl") || lookahead.startsWith("\\colortbl")
                            || lookahead.startsWith("\\stylesheet") || lookahead.startsWith("\\info") || lookahead.startsWith("\\pict")) {
                        skipDepth = braceDepth;
                    }
                }
                i++;
            } else if (ch == '}') {
                if (braceDepth == skipDepth) skipDepth = -1;
                braceDepth--;
                i++;
            } else if (skipDepth >= 0) {
                i++;
            } else if (ch == '\\') {
                i++;
                if (i >= len) break;
                char next = rtf.charAt(i);
                if (next == '\\' || next == '{' || next == '}') {
                    out.append(next);
                    i++;
                } else if (next == '\'') {
                    if (i + 2 < len) {
                        String hex = rtf.substring(i + 1, i + 3);
                        try {
                            byte[] b = new byte[]{(byte) Integer.parseInt(hex, 16)};
                            out.append(new String(b, cp1254));
                        } catch (Exception ignored) {}
                        i += 3;
                    } else {
                        i++;
                    }
                } else if (Character.isLetter(next)) {
                    int startWord = i;
                    while (i < len && Character.isLetter(rtf.charAt(i))) i++;
                    String word = rtf.substring(startWord, i);
                    int numStart = i;
                    if (i < len && (rtf.charAt(i) == '-' || Character.isDigit(rtf.charAt(i)))) {
                        i++;
                        while (i < len && Character.isDigit(rtf.charAt(i))) i++;
                    }
                    String numStr = rtf.substring(numStart, i);
                    if (i < len && rtf.charAt(i) == ' ') i++;
                    if ("par".equals(word) || "line".equals(word)) {
                        out.append('\n');
                    } else if ("tab".equals(word)) {
                        out.append('\t');
                    } else if ("u".equals(word) && !numStr.isEmpty()) {
                        try {
                            int code = Integer.parseInt(numStr);
                            if (code < 0) code += 65536;
                            out.append((char) code);
                            if (i < len && rtf.charAt(i) == '?') i++;
                        } catch (Exception ignored) {}
                    }
                } else {
                    i++;
                }
            } else if (ch == '\r' || ch == '\n') {
                i++;
            } else {
                out.append(ch);
                i++;
            }
        }
        return parsePlainTextToPayload(out.toString());
    }

    public static String parsePlainTextToPayload(String text) {
        if (text == null || text.trim().isEmpty()) {
            return buildEmptyPayload("<p style=\"text-align: justify;\"><br></p>");
        }
        StringBuilder html = new StringBuilder();
        String[] lines = text.replace("\r\n", "\n").replace('\r', '\n').split("\n", -1);
        for (String line : lines) {
            if (line.trim().isEmpty()) {
                html.append("<p style=\"text-align: justify;\"><br></p>\n");
            } else {
                html.append("<p style=\"text-align: justify;\">")
                    .append(formatParagraphTabs(escapeHtml(line)))
                    .append("</p>\n");
            }
        }
        return buildEmptyPayload(html.toString());
    }

    private static String parseContentXmlToPayload(String xml) {
        return parseContentXmlToPayload(xml, null);
    }

    public static String parseContentXmlToPayload(String xml, String docPropsXml) {
        try {
            String cleanXml = stripBomAndLeadingGarbage(xml);
            DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
            dbf.setNamespaceAware(false);
            DocumentBuilder db = dbf.newDocumentBuilder();
            Document doc = db.parse(new ByteArrayInputStream(cleanXml.getBytes(StandardCharsets.UTF_8)));

            // 0. <styles> haritasını oku (resolver kalıtımı için)
            Map<String, Map<String, String>> styleMap = new HashMap<>();
            NodeList styleNodes = doc.getElementsByTagName("style");
            for (int i = 0; i < styleNodes.getLength(); i++) {
                Element sElem = (Element) styleNodes.item(i);
                String name = sElem.getAttribute("name");
                if (name != null && !name.isEmpty()) {
                    Map<String, String> attrs = new HashMap<>();
                    NamedNodeMap nnm = sElem.getAttributes();
                    for (int a = 0; a < nnm.getLength(); a++) {
                        Node attr = nnm.item(a);
                        attrs.put(attr.getNodeName(), attr.getNodeValue());
                    }
                    styleMap.put(name, attrs);
                }
            }

            // 1. Üstbilgi, Altbilgi ve Kenar Boşlukları (pageFormat)
            String headerText = "";
            String footerText = "";
            double leftMarginCm = 1.5;
            double rightMarginCm = 1.5;
            double topMarginCm = 1.5;
            double bottomMarginCm = 1.5;
            double headerMarginCm = 0.7;
            double footerMarginCm = 0.7;
            String paperOrientation = "1";
            String mediaSizeName = "1";
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
                if (pf.hasAttribute("headerFOffset")) {
                    headerMarginCm = parsePtToCm(pf.getAttribute("headerFOffset"), 0.7);
                }
                if (pf.hasAttribute("footerFOffset")) {
                    footerMarginCm = parsePtToCm(pf.getAttribute("footerFOffset"), 0.7);
                }
                if (pf.hasAttribute("paperOrientation")) {
                    paperOrientation = pf.getAttribute("paperOrientation");
                }
                if (pf.hasAttribute("mediaSizeName")) {
                    mediaSizeName = pf.getAttribute("mediaSizeName");
                }
            }

            // Ham metni al (<template> altındaki <content>)
            NodeList contentList = doc.getElementsByTagName("content");
            String rawText = "";
            for (int i = 0; i < contentList.getLength(); i++) {
                Element c = (Element) contentList.item(i);
                if (c.getParentNode() != null && "template".equalsIgnoreCase(c.getParentNode().getNodeName())) {
                    rawText = c.getTextContent();
                    break;
                }
            }
            int textLen = rawText != null ? rawText.length() : 0;

            // 2. Doğrulama Kodu Çözümleme (webID & documentproperties.xml)
            String webId = "";
            NodeList webIdList = doc.getElementsByTagName("webID");
            if (webIdList.getLength() > 0) {
                Element webIdEl = (Element) webIdList.item(0);
                String idAttr = webIdEl.getAttribute("id");
                if (idAttr != null) webId = idAttr.trim();
            }

            String uyapDogrulamaKodu = "";
            String uyapSicil = "";
            if (docPropsXml != null && !docPropsXml.trim().isEmpty()) {
                try {
                    DocumentBuilder dbProps = DocumentBuilderFactory.newInstance().newDocumentBuilder();
                    Document propsDoc = dbProps.parse(new ByteArrayInputStream(docPropsXml.getBytes(StandardCharsets.UTF_8)));
                    NodeList entries = propsDoc.getElementsByTagName("entry");
                    for (int i = 0; i < entries.getLength(); i++) {
                        Element entry = (Element) entries.item(i);
                        String key = entry.getAttribute("key");
                        String val = entry.getTextContent();
                        if ("uyapdogrulamakodu".equalsIgnoreCase(key) && val != null) {
                            uyapDogrulamaKodu = val.trim();
                        } else if ("uyapsicil".equalsIgnoreCase(key) && val != null) {
                            uyapSicil = val.trim();
                        }
                    }
                } catch (Exception ignored) {}
            }

            String verificationCode = !webId.isEmpty() ? webId : uyapDogrulamaKodu;

            // 2.5. UYAP Şablon Alanı Veri Haritası (<data>)
            Map<String, String> dataMap = new HashMap<>();
            NodeList dataNodes = doc.getElementsByTagName("data");
            for (int d = 0; d < dataNodes.getLength(); d++) {
                Element dElem = (Element) dataNodes.item(d);
                Node dChild = dElem.getFirstChild();
                while (dChild != null) {
                    if (dChild.getNodeType() == Node.ELEMENT_NODE) {
                        Element cElem = (Element) dChild;
                        String k = cElem.getTagName().toLowerCase(Locale.ROOT);
                        String v = cElem.getTextContent();
                        if (v != null && !v.trim().isEmpty() && (!dataMap.containsKey(k) || dataMap.get(k).trim().isEmpty())) {
                            dataMap.put(k, v);
                        }
                    }
                    dChild = dChild.getNextSibling();
                }
            }

            // 3. Header (Üstbilgi) Çözümleme - Hem Resim Hem Paragraf/Tablo Eksiksiz Destekli
            NodeList headers = doc.getElementsByTagName("header");
            String headerHtml = "";
            int headerStartPage = 1;
            if (headers.getLength() > 0) {
                Element headerElem = (Element) headers.item(0);
                if (headerElem.hasAttribute("startPage")) {
                    try {
                        headerStartPage = Integer.parseInt(headerElem.getAttribute("startPage").trim());
                    } catch (Exception ignored) {}
                }

                StringBuilder hBuilder = new StringBuilder();
                Map<String, Integer> hCounters = new HashMap<>();
                Node hChild = headerElem.getFirstChild();
                boolean hasHeaderChildren = false;
                while (hChild != null) {
                    if (hChild.getNodeType() == Node.ELEMENT_NODE) {
                        Element hce = (Element) hChild;
                        String hTag = hce.getTagName();
                        if ("image".equalsIgnoreCase(hTag)) {
                            String hImgData = hce.getAttribute("imageData");
                            if (hImgData != null && !hImgData.trim().isEmpty()) {
                                String wStr = hce.getAttribute("width");
                                String hStr = hce.getAttribute("height");
                                double wCm = parsePtToCm(wStr, 0);
                                double hCm = parsePtToCm(hStr, 1.76);
                                hBuilder.append("<div class=\"udf-header-layout\" style=\"text-align:center; padding-bottom:4px;\">")
                                        .append("<img class=\"udf-header-img\" data-udf-width=\"").append(escapeHtml(wStr)).append("\" data-udf-height=\"").append(escapeHtml(hStr)).append("\" src=\"data:image/png;base64,").append(hImgData.trim()).append("\" style=\"max-height:").append(hCm > 0 ? hCm + "cm" : "50px").append(";").append(wCm > 0 ? " max-width:" + wCm + "cm;" : "").append(" width:auto; object-fit:contain;\" />")
                                        .append("</div>");
                                hasHeaderChildren = true;
                            }
                        } else if ("paragraph".equalsIgnoreCase(hTag)) {
                            StringBuilder pOut = new StringBuilder();
                            appendParagraphToHtml(hce, rawText, textLen, hCounters, dataMap, styleMap, pOut, true);
                            String pStr = pOut.toString();
                            // Eğer üstbilgi paragrafı tamamen boşsa ve başka içerik varsa gereksiz boşluk yapma
                            if (!pStr.contains("<br></p>") || !hasHeaderChildren) {
                                hBuilder.append(pStr);
                                hasHeaderChildren = true;
                            }
                        } else if ("table".equalsIgnoreCase(hTag)) {
                            appendTableToHtml(hce, rawText, textLen, hCounters, dataMap, styleMap, hBuilder);
                            hasHeaderChildren = true;
                        }
                    }
                    hChild = hChild.getNextSibling();
                }
                headerHtml = hBuilder.toString();
                if ((headerText == null || headerText.isEmpty()) && !headerHtml.isEmpty()) {
                    headerText = extractPlainTextFromContainer(headerElem, rawText, textLen, dataMap);
                }
            }
            if (headerHtml.isEmpty() && headerText != null && !headerText.isEmpty()) {
                headerHtml = "<div class=\"udf-header-layout\" style=\"text-align:center;\">" + escapeHtml(headerText) + "</div>";
            }

            // 4. Footer (Altbilgi) Çözümleme - Resim, Paragraf, Sayfa Numarası ve UYAP Doğrulama Kodu Dahil
            NodeList footers = doc.getElementsByTagName("footer");
            String footerHtml = "";
            String footerForeStr = "Sayfa:";
            String footerSep = "/";
            String footerPageSpec = "";
            String footerPageStart = "1";
            boolean hasPageNumber = false;
            if (footers.getLength() > 0) {
                Element footerElem = (Element) footers.item(0);
                if (footerElem.hasAttribute("pageNumber-foreStr")) {
                    footerForeStr = footerElem.getAttribute("pageNumber-foreStr");
                    hasPageNumber = true;
                }
                if (footerElem.hasAttribute("pageNumber-seperator")) {
                    footerSep = footerElem.getAttribute("pageNumber-seperator");
                    hasPageNumber = true;
                }
                if (footerElem.hasAttribute("pageNumber-spec")) {
                    footerPageSpec = footerElem.getAttribute("pageNumber-spec");
                    if (!footerPageSpec.startsWith("0")) {
                        hasPageNumber = true;
                    }
                }
                if (footerElem.hasAttribute("pageNumber-start")) {
                    footerPageStart = footerElem.getAttribute("pageNumber-start");
                }

                StringBuilder fBuilder = new StringBuilder();
                Map<String, Integer> fCounters = new HashMap<>();
                Node fChild = footerElem.getFirstChild();
                boolean hasFooterImg = false;
                String pageLabelText = escapeHtml(footerForeStr != null ? footerForeStr.trim() : "Sayfa:") + " {PAGE_NUM}" + escapeHtml(footerSep != null ? footerSep.trim() : "/") + "{TOTAL_PAGES}";
                while (fChild != null) {
                    if (fChild.getNodeType() == Node.ELEMENT_NODE) {
                        Element fce = (Element) fChild;
                        String fTag = fce.getTagName();
                        Element imgElem = null;
                        if ("image".equalsIgnoreCase(fTag)) {
                            imgElem = fce;
                        } else if ("paragraph".equalsIgnoreCase(fTag)) {
                            NodeList pImgs = fce.getElementsByTagName("image");
                            String pPlain = extractPlainTextFromContainer(fce, rawText, textLen, dataMap);
                            if (pImgs.getLength() > 0 && (pPlain == null || pPlain.trim().isEmpty())) {
                                imgElem = (Element) pImgs.item(0);
                            }
                        }
                        if (imgElem != null) {
                            String fImgData = imgElem.getAttribute("imageData");
                            if (fImgData != null && !fImgData.trim().isEmpty()) {
                                String wStr = imgElem.getAttribute("width");
                                String hStr = imgElem.getAttribute("height");
                                double wCm = parsePtToCm(wStr, 0);
                                double hCm = parsePtToCm(hStr, 1.76);
                                hasFooterImg = true;
                                String dimStyle = "max-height:" + (hCm > 0 ? hCm + "cm" : "50px") + ";" + (wCm > 0 ? " max-width:" + wCm + "cm;" : " max-width:82%;") + " width:auto; object-fit:contain;";
                                if (hasPageNumber) {
                                    fBuilder.append("<div class=\"udf-footer-layout\">")
                                            .append("<img class=\"udf-footer-img\" data-udf-width=\"").append(escapeHtml(wStr)).append("\" data-udf-height=\"").append(escapeHtml(hStr)).append("\" src=\"data:image/png;base64,").append(fImgData.trim()).append("\" style=\"").append(dimStyle).append("\" />")
                                            .append("<span class=\"udf-footer-page-label\">").append(pageLabelText).append("</span>")
                                            .append("</div>");
                                } else {
                                    fBuilder.append("<div class=\"udf-footer-layout full-banner\" style=\"justify-content:center; border-top:none;\">")
                                            .append("<img class=\"udf-footer-img\" data-udf-width=\"").append(escapeHtml(wStr)).append("\" data-udf-height=\"").append(escapeHtml(hStr)).append("\" src=\"data:image/png;base64,").append(fImgData.trim()).append("\" style=\"").append(dimStyle).append("\" />")
                                            .append("</div>");
                                }
                            }
                        } else if ("paragraph".equalsIgnoreCase(fTag)) {
                            StringBuilder pOut = new StringBuilder();
                            appendParagraphToHtml(fce, rawText, textLen, fCounters, dataMap, styleMap, pOut, true);
                            String pStr = pOut.toString();
                            if (!pStr.contains("<br></p>")) {
                                fBuilder.append(pStr);
                            }
                        } else if ("table".equalsIgnoreCase(fTag)) {
                            appendTableToHtml(fce, rawText, textLen, fCounters, dataMap, styleMap, fBuilder);
                        }
                    }
                    fChild = fChild.getNextSibling();
                }
                if (!hasFooterImg && hasPageNumber) {
                    fBuilder.append("<div class=\"udf-footer-layout\" style=\"display:flex; justify-content:flex-end; width:100%;\">")
                            .append("<span class=\"udf-footer-page-label\">").append(pageLabelText).append("</span>")
                            .append("</div>");
                }
                footerHtml = fBuilder.toString();
                if ((footerText == null || footerText.isEmpty()) && !footerHtml.isEmpty()) {
                    footerText = extractPlainTextFromContainer(footerElem, rawText, textLen, dataMap);
                }
            }

            // Eğer UYAP doğrulama kodu varsa resmi UYAP altbilgisi oluştur:
            if (!verificationCode.isEmpty()) {
                footerHtml = "<div class=\"udf-official-footer\" style=\"display:flex; justify-content:space-between; align-items:flex-end; border-top:0.5px solid #000; padding-top:4px; font-family:Arial, sans-serif; font-size:7.5pt; line-height:1.2; width:100%; box-sizing:border-box;\">" +
                             "<div style=\"flex:1; max-width:82%; text-align:left; word-break:break-all; padding-right:8px;\">" +
                             "UYAP Bilişim Sistemindeki bu dokümana http://vatandas.uyap.gov.tr adresinden <strong>" + escapeHtml(verificationCode) + "</strong> ile erişebilirsiniz." +
                             "</div>" +
                             "<div style=\"display:flex; flex-direction:column; align-items:flex-end; min-width:60px;\">" +
                             "<span class=\"udf-footer-page-label\" style=\"font-size:8.5pt; font-family:Arial, sans-serif; margin-bottom:2px;\">{PAGE_NUM}/{TOTAL_PAGES}</span>" +
                             "<div class=\"udf-footer-qr-container\" data-verification-code=\"" + escapeHtml(verificationCode) + "\" style=\"width:34px; height:34px;\"></div>" +
                             "</div>" +
                             "</div>";
            } else if (footerHtml.isEmpty() && footerText != null && !footerText.isEmpty()) {
                footerHtml = "<div class=\"udf-footer-layout\">" +
                             "<span class=\"udf-footer-text\">" + escapeHtml(footerText) + "</span>" +
                             "<span class=\"udf-footer-page-label\">Sayfa: {PAGE_NUM} / {TOTAL_PAGES}</span>" +
                             "</div>";
            }

            if (rawText == null || rawText.isEmpty()) {
                JSONObject res = new JSONObject();
                res.put("header", headerText);
                res.put("headerHtml", headerHtml);
                res.put("headerStartPage", headerStartPage);
                res.put("footer", footerText);
                res.put("footerHtml", footerHtml);
                res.put("footerPageSpec", footerPageSpec);
                res.put("footerForeStr", footerForeStr);
                res.put("footerSep", footerSep);
                res.put("footerPageStart", footerPageStart);
                res.put("verificationCode", verificationCode);
                res.put("leftMarginCm", leftMarginCm);
                res.put("rightMarginCm", rightMarginCm);
                res.put("topMarginCm", topMarginCm);
                res.put("bottomMarginCm", bottomMarginCm);
                res.put("headerMarginCm", headerMarginCm);
                res.put("footerMarginCm", footerMarginCm);
                res.put("paperOrientation", paperOrientation);
                res.put("mediaSizeName", mediaSizeName);
                res.put("html", "<p style=\"text-align: justify;\"><br></p>");
                return res.toString();
            }

            // 5. Gövde paragraflarını ve tablolarını çözümle
            NodeList paragraphs = doc.getElementsByTagName("paragraph");
            if (paragraphs.getLength() == 0) {
                StringBuilder fallback = new StringBuilder();
                String[] lines = rawText.split("\n", -1);
                for (String line : lines) {
                    fallback.append("<p style=\"text-align: justify;\">")
                            .append(line.isEmpty() ? "<br>" : escapeHtml(line))
                            .append("</p>");
                }
                JSONObject res = new JSONObject();
                res.put("header", headerText);
                res.put("headerHtml", headerHtml);
                res.put("headerStartPage", headerStartPage);
                res.put("footer", footerText);
                res.put("footerHtml", footerHtml);
                res.put("verificationCode", verificationCode);
                res.put("leftMarginCm", leftMarginCm);
                res.put("rightMarginCm", rightMarginCm);
                res.put("topMarginCm", topMarginCm);
                res.put("bottomMarginCm", bottomMarginCm);
                res.put("headerMarginCm", headerMarginCm);
                res.put("footerMarginCm", footerMarginCm);
                res.put("paperOrientation", paperOrientation);
                res.put("html", fallback.toString());
                return res.toString();
            }

            StringBuilder html = new StringBuilder();
            Map<String, Integer> listCounters = new HashMap<>();

            Element elementsNode = null;
            NodeList elemList = doc.getElementsByTagName("elements");
            if (elemList.getLength() > 0) {
                elementsNode = (Element) elemList.item(0);
            }

            boolean renderedAny = false;
            if (elementsNode != null) {
                Node child = elementsNode.getFirstChild();
                while (child != null) {
                    if (child.getNodeType() == Node.ELEMENT_NODE) {
                        Element childElem = (Element) child;
                        String tagName = childElem.getTagName();
                        if ("paragraph".equalsIgnoreCase(tagName)) {
                            appendParagraphToHtml(childElem, rawText, textLen, listCounters, dataMap, styleMap, html, false);
                            renderedAny = true;
                        } else if ("table".equalsIgnoreCase(tagName)) {
                            appendTableToHtml(childElem, rawText, textLen, listCounters, dataMap, styleMap, html);
                            renderedAny = true;
                        } else if ("page-break".equalsIgnoreCase(tagName) || "pageBreak".equalsIgnoreCase(tagName)) {
                            html.append("<div class=\"udf-page-break\" data-udf-page-break=\"true\" style=\"page-break-after:always; break-after:page; height:0; margin:12px 0; border-top:1px dashed #94a3b8;\"></div>\n");
                            renderedAny = true;
                        }
                    }
                    child = child.getNextSibling();
                }
            }

            if (!renderedAny) {
                for (int i = 0; i < paragraphs.getLength(); i++) {
                    Element p = (Element) paragraphs.item(i);
                    Node parent = p.getParentNode();
                    if (parent != null) {
                        String pName = parent.getNodeName();
                        if ("header".equalsIgnoreCase(pName) || "footer".equalsIgnoreCase(pName) || "cell".equalsIgnoreCase(pName)) {
                            continue;
                        }
                    }
                    appendParagraphToHtml(p, rawText, textLen, listCounters, dataMap, styleMap, html, false);
                }
            }

            JSONObject res = new JSONObject();
            res.put("header", headerText);
            res.put("headerHtml", headerHtml);
            res.put("headerStartPage", headerStartPage);
            res.put("footer", footerText);
            res.put("footerHtml", footerHtml);
            res.put("footerPageSpec", footerPageSpec);
            res.put("footerForeStr", footerForeStr);
            res.put("footerSep", footerSep);
            res.put("footerPageStart", footerPageStart);
            res.put("verificationCode", verificationCode);
            res.put("leftMarginCm", leftMarginCm);
            res.put("rightMarginCm", rightMarginCm);
            res.put("topMarginCm", topMarginCm);
            res.put("bottomMarginCm", bottomMarginCm);
            res.put("headerMarginCm", headerMarginCm);
            res.put("footerMarginCm", footerMarginCm);
            res.put("paperOrientation", paperOrientation);
            res.put("mediaSizeName", mediaSizeName);
            res.put("html", html.toString());
            return res.toString();

        } catch (Exception e) {
            return parsePlainTextToPayload(xml);
        }
    }

    private static String extractPlainTextFromContainer(Element container, String rawText, int textLen, Map<String, String> dataMap) {
        if (container == null || rawText == null) return "";
        StringBuilder sb = new StringBuilder();
        NodeList paras = container.getElementsByTagName("paragraph");
        for (int i = 0; i < paras.getLength(); i++) {
            Element p = (Element) paras.item(i);
            Node child = p.getFirstChild();
            StringBuilder line = new StringBuilder();
            while (child != null) {
                if (child.getNodeType() == Node.ELEMENT_NODE) {
                    Element ce = (Element) child;
                    String tag = ce.getTagName();
                    if ("tab".equalsIgnoreCase(tag)) {
                        line.append("\t");
                    } else if ("space".equalsIgnoreCase(tag)) {
                        line.append(" ");
                    } else if ("content".equalsIgnoreCase(tag) || "field".equalsIgnoreCase(tag)) {
                        String fn = ce.getAttribute("fieldName");
                        if (fn != null && !fn.trim().isEmpty() && dataMap != null && dataMap.containsKey(fn.trim().toLowerCase(Locale.ROOT))) {
                            line.append(dataMap.get(fn.trim().toLowerCase(Locale.ROOT)));
                        } else {
                            String sStr = ce.getAttribute("startOffset");
                            String lStr = ce.getAttribute("length");
                            if (!sStr.isEmpty() && !lStr.isEmpty()) {
                                try {
                                    int s = Integer.parseInt(sStr);
                                    int l = Integer.parseInt(lStr);
                                    if (s >= 0 && s < textLen) {
                                        line.append(rawText.substring(s, Math.min(s + l, textLen)));
                                    }
                                } catch (Exception ignored) {}
                            }
                        }
                    }
                }
                child = child.getNextSibling();
            }
            String trimmed = line.toString().replace("\uFFFC", "").replace("\u00B8", "").trim();
            if (!trimmed.isEmpty()) {
                if (sb.length() > 0) sb.append(" ");
                sb.append(trimmed);
            }
        }
        return sb.toString();
    }

    private static String resolveAttribute(Element elem, String attrName, Map<String, Map<String, String>> styleMap) {
        if (elem.hasAttribute(attrName)) {
            return elem.getAttribute(attrName);
        }
        if (styleMap == null || styleMap.isEmpty()) return "";
        String resolver = elem.getAttribute("resolver");
        if (resolver == null || resolver.isEmpty()) {
            Node parent = elem.getParentNode();
            if (parent instanceof Element) {
                Element pElem = (Element) parent;
                if (pElem.hasAttribute(attrName)) return pElem.getAttribute(attrName);
                resolver = pElem.getAttribute("resolver");
            }
        }
        int depth = 0;
        while (resolver != null && !resolver.isEmpty() && depth < 8) {
            Map<String, String> st = styleMap.get(resolver);
            if (st == null) break;
            if (st.containsKey(attrName)) {
                return st.get(attrName);
            }
            resolver = st.get("resolver");
            depth++;
        }
        return "";
    }

    private static String parseSignedRgbToHex(String signedIntStr, boolean isForeground) {
        if (signedIntStr == null || signedIntStr.trim().isEmpty()) return "";
        try {
            int val = Integer.parseInt(signedIntStr.trim());
            int rgb = val & 0xFFFFFF;
            // Varsayılan UYAP metin renklerini (#333333 = -13421773 veya #000000 = -16777216) gereksiz span üretmemek için atla
            if (isForeground && (rgb == 0x333333 || rgb == 0x000000)) return "";
            if (!isForeground && rgb == 0xFFFFFF) return "";
            return String.format(Locale.US, "#%06X", rgb);
        } catch (Exception e) {
            return "";
        }
    }

    private static void appendParagraphToHtml(
            Element p,
            String rawText,
            int textLen,
            Map<String, Integer> listCounters,
            Map<String, String> dataMap,
            Map<String, Map<String, String>> styleMap,
            StringBuilder outHtml,
            boolean isHeaderOrFooter
    ) {
        String alignAttr = resolveAttribute(p, "Alignment", styleMap);
        String alignStyle = "left";
        if ("1".equals(alignAttr)) alignStyle = "center";
        else if ("2".equals(alignAttr)) alignStyle = "right";
        else if ("3".equals(alignAttr)) alignStyle = "justify";
        else if ("0".equals(alignAttr)) alignStyle = "left";
        else {
            // Alignment belirtilmemişse: TabSet veya Hanging varsa sola, yoksa UYAP varsayılanı sola (veya üstbilgi/altbilgi dışında iki yana)
            alignStyle = (p.hasAttribute("TabSet") || p.hasAttribute("Hanging") || isHeaderOrFooter) ? "left" : "left";
        }

        String spaceAbove = resolveAttribute(p, "SpaceAbove", styleMap);
        String spaceBelow = resolveAttribute(p, "SpaceBelow", styleMap);
        String lineSpacing = resolveAttribute(p, "LineSpacing", styleMap);
        String hanging = resolveAttribute(p, "Hanging", styleMap);
        String leftIndent = resolveAttribute(p, "LeftIndent", styleMap);
        String rightIndent = resolveAttribute(p, "RightIndent", styleMap);
        String firstLineIndent = resolveAttribute(p, "FirstLineIndent", styleMap);
        String tabSet = resolveAttribute(p, "TabSet", styleMap);

        List<String> stopsList = new ArrayList<>();
        if (tabSet != null && !tabSet.trim().isEmpty()) {
            String[] stops = tabSet.split(",");
            for (String s : stops) {
                String[] parts = s.trim().split(":");
                if (parts.length > 0) {
                    try {
                        double pt = Double.parseDouble(parts[0].trim());
                        if (pt > 0.5) {
                            double cm = Math.round((pt / 28.3465) * 100.0) / 100.0;
                            stopsList.add(String.format(Locale.US, "%.2f", cm));
                        }
                    } catch (Exception ignored) {}
                }
            }
        }

        StringBuilder styleAttr = new StringBuilder("text-align: ").append(alignStyle).append(";");
        double ptAbove = 0;
        double ptBelow = 0;
        if (!spaceAbove.isEmpty()) {
            try { ptAbove = Double.parseDouble(spaceAbove); } catch (Exception ignored) {}
        }
        if (!spaceBelow.isEmpty()) {
            try { ptBelow = Double.parseDouble(spaceBelow); } catch (Exception ignored) {}
        }
        styleAttr.append(" margin-top: ").append(ptAbove).append("pt;");
        styleAttr.append(" margin-bottom: ").append(ptBelow).append("pt;");

        if (!lineSpacing.isEmpty()) {
            try {
                double ls = Double.parseDouble(lineSpacing);
                if (ls > 0.05) {
                    double cssLh = Math.round((1.15 + ls) * 100.0) / 100.0;
                    styleAttr.append(" line-height: ").append(String.format(Locale.US, "%.2f", cssLh)).append(";");
                }
            } catch (Exception ignored) {}
        }

        double fIndentPt = 0;
        double hangPt = 0;
        double lIndentPt = 0;
        double rIndentPt = 0;
        if (!firstLineIndent.isEmpty()) {
            try { fIndentPt = Double.parseDouble(firstLineIndent); } catch (Exception ignored) {}
        }
        if (!hanging.isEmpty()) {
            try { hangPt = Double.parseDouble(hanging); } catch (Exception ignored) {}
        }
        if (!leftIndent.isEmpty()) {
            try { lIndentPt = Double.parseDouble(leftIndent); } catch (Exception ignored) {}
        }
        if (!rightIndent.isEmpty()) {
            try { rIndentPt = Double.parseDouble(rightIndent); } catch (Exception ignored) {}
        }

        // Havelsan UYAP ParagraphView / RowView (prof.d.J) birebir matematiksel girinti formülü:
        // Satır 0 sol boşluk = LeftIndent + FirstLineIndent
        // Satır 1..N sol boşluk = LeftIndent + Hanging
        // Dolayısıyla CSS karşılığı:
        // margin-left = LeftIndent + Hanging
        // text-indent = FirstLineIndent - Hanging
        double totalLeftPt = lIndentPt + hangPt;
        double textIndentPt = fIndentPt - hangPt;
        if (Math.abs(totalLeftPt) > 0.1) {
            double cm = Math.round((totalLeftPt / 28.3465) * 100.0) / 100.0;
            styleAttr.append(" margin-left: ").append(cm).append("cm;");
            if (hangPt > 0.5) {
                boolean hasHangStop = false;
                for (String existing : stopsList) {
                    try {
                        if (Math.abs(Double.parseDouble(existing) - cm) < 0.06) {
                            hasHangStop = true;
                            break;
                        }
                    } catch (Exception ignored) {}
                }
                if (!hasHangStop) {
                    stopsList.add(String.format(Locale.US, "%.2f", cm));
                    stopsList.sort((a, b) -> {
                        try {
                            return Double.compare(Double.parseDouble(a), Double.parseDouble(b));
                        } catch (Exception e) {
                            return 0;
                        }
                    });
                }
            }
        }
        if (Math.abs(textIndentPt) > 0.1) {
            double cm = Math.round((textIndentPt / 28.3465) * 100.0) / 100.0;
            styleAttr.append(" text-indent: ").append(cm).append("cm;");
        }
        if (Math.abs(rIndentPt) > 0.1) {
            double cm = Math.round((rIndentPt / 28.3465) * 100.0) / 100.0;
            styleAttr.append(" margin-right: ").append(cm).append("cm;");
        }

        StringBuilder pContent = new StringBuilder();

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
            pContent.append("<span class=\"udf-list-prefix\" contenteditable=\"false\" style=\"font-weight:bold; margin-right:4px;\">").append(escapeHtml(listPrefix)).append("</span>");
        } else if (isBulleted) {
            pContent.append("<span class=\"udf-list-prefix\" contenteditable=\"false\" style=\"font-weight:bold; margin-right:6px;\">•</span>");
        }

        String pFamily = resolveAttribute(p, "family", styleMap);
        String pSize = resolveAttribute(p, "size", styleMap);
        String pFg = resolveAttribute(p, "foreground", styleMap);
        boolean pBold = "true".equalsIgnoreCase(resolveAttribute(p, "bold", styleMap));
        boolean pItalic = "true".equalsIgnoreCase(resolveAttribute(p, "italic", styleMap));
        boolean pUnderline = "true".equalsIgnoreCase(resolveAttribute(p, "underline", styleMap));

        // Paragraf altındaki tüm elemanları (content, space, field, tab, image) sırayla tara:
        boolean hasContent = false;
        Node childNode = p.getFirstChild();
        while (childNode != null) {
            if (childNode.getNodeType() == Node.ELEMENT_NODE) {
                Element childElem = (Element) childNode;
                String tagName = childElem.getTagName();

                if ("image".equalsIgnoreCase(tagName)) {
                    String imgData = childElem.getAttribute("imageData");
                    if (imgData != null && !imgData.trim().isEmpty()) {
                        String wStr = childElem.getAttribute("width");
                        String hStr = childElem.getAttribute("height");
                        double wCm = parsePtToCm(wStr, 0);
                        double hCm = parsePtToCm(hStr, 0);
                        StringBuilder imgStyle = new StringBuilder("display:inline-block; vertical-align:middle; object-fit:contain;");
                        if (wCm > 0) imgStyle.append(" max-width:").append(wCm).append("cm; width:").append(wCm).append("cm;");
                        else imgStyle.append(" max-width:95%; width:auto;");
                        if (hCm > 0) imgStyle.append(" max-height:").append(hCm).append("cm; height:").append(hCm).append("cm;");
                        else imgStyle.append(" height:auto;");

                        pContent.append("<img data-udf-width=\"").append(escapeHtml(wStr))
                                .append("\" data-udf-height=\"").append(escapeHtml(hStr))
                                .append("\" src=\"data:image/png;base64,")
                                .append(imgData.trim())
                                .append("\" style=\"").append(imgStyle.toString()).append("\" />");
                        hasContent = true;
                    }
                } else if ("content".equalsIgnoreCase(tagName) || "space".equalsIgnoreCase(tagName)
                        || "field".equalsIgnoreCase(tagName) || "tab".equalsIgnoreCase(tagName)) {
                    String startStr = childElem.getAttribute("startOffset");
                    String lenStr = childElem.getAttribute("length");
                    String fieldName = childElem.getAttribute("fieldName");
                    boolean bold = childElem.hasAttribute("bold") ? "true".equalsIgnoreCase(childElem.getAttribute("bold")) : pBold;
                    boolean italic = childElem.hasAttribute("italic") ? "true".equalsIgnoreCase(childElem.getAttribute("italic")) : pItalic;
                    boolean underline = childElem.hasAttribute("underline") ? "true".equalsIgnoreCase(childElem.getAttribute("underline")) : pUnderline;
                    boolean subscript = "true".equalsIgnoreCase(childElem.getAttribute("subscript")) || "true".equalsIgnoreCase(childElem.getAttribute("Subscript"));
                    boolean superscript = "true".equalsIgnoreCase(childElem.getAttribute("superscript")) || "true".equalsIgnoreCase(childElem.getAttribute("Superscript"));
                    boolean strike = "true".equalsIgnoreCase(childElem.getAttribute("strikeThrough")) || "true".equalsIgnoreCase(childElem.getAttribute("strikethrough")) || "true".equalsIgnoreCase(childElem.getAttribute("StrikeThrough"));

                    String runFamily = childElem.hasAttribute("family") ? childElem.getAttribute("family") : pFamily;
                    String runSize = childElem.hasAttribute("size") ? childElem.getAttribute("size") : pSize;
                    String runFg = childElem.hasAttribute("foreground") ? childElem.getAttribute("foreground") : pFg;
                    String runBg = childElem.getAttribute("background");

                    String chunk = "";
                    if ("tab".equalsIgnoreCase(tagName)) {
                        int tabCount = 1;
                        if (!lenStr.isEmpty()) {
                            try { tabCount = Math.max(1, Integer.parseInt(lenStr)); } catch (Exception ignored) {}
                        }
                        StringBuilder tb = new StringBuilder();
                        for (int tc = 0; tc < tabCount; tc++) tb.append('\t');
                        chunk = tb.toString();
                    } else if (fieldName != null && !fieldName.trim().isEmpty() && dataMap != null && dataMap.containsKey(fieldName.trim().toLowerCase(Locale.ROOT)) && !dataMap.get(fieldName.trim().toLowerCase(Locale.ROOT)).trim().isEmpty()) {
                        chunk = dataMap.get(fieldName.trim().toLowerCase(Locale.ROOT));
                    } else if (!startStr.isEmpty() && !lenStr.isEmpty()) {
                        try {
                            int start = Integer.parseInt(startStr);
                            int len = Integer.parseInt(lenStr);
                            if (start < textLen && start >= 0) {
                                int end = Math.min(start + len, textLen);
                                chunk = rawText.substring(start, end);
                            }
                        } catch (Exception ignored) {}
                    } else if ("space".equalsIgnoreCase(tagName)) {
                        chunk = " ";
                    }

                    if (!chunk.isEmpty()) {
                        if (chunk.endsWith("\r\n")) {
                            chunk = chunk.substring(0, chunk.length() - 2);
                        } else if (chunk.endsWith("\n") || chunk.endsWith("\r")) {
                            chunk = chunk.substring(0, chunk.length() - 1);
                        }

                        if (!chunk.isEmpty()) {
                            hasContent = true;
                            if (isHeaderOrFooter && chunk.trim().matches("^[-_]{10,}$")) {
                                styleAttr.append(" white-space: nowrap; overflow: hidden; text-overflow: clip;");
                            }
                            String escaped = escapeHtml(chunk).replace("\n", "<br>");
                            if (bold) escaped = "<strong>" + escaped + "</strong>";
                            if (italic) escaped = "<em>" + escaped + "</em>";
                            if (underline) escaped = "<u>" + escaped + "</u>";
                            if (subscript) escaped = "<sub>" + escaped + "</sub>";
                            if (superscript) escaped = "<sup>" + escaped + "</sup>";
                            if (strike) escaped = "<s>" + escaped + "</s>";

                            StringBuilder spanStyle = new StringBuilder();
                            if (runFamily != null && !runFamily.isEmpty() && !"Dialog".equalsIgnoreCase(runFamily) && !"Times New Roman".equalsIgnoreCase(runFamily)) {
                                spanStyle.append("font-family:'").append(escapeHtml(runFamily)).append("';");
                            }
                            if (runSize != null && !runSize.isEmpty() && !"12".equals(runSize.trim()) && !"12.0".equals(runSize.trim())) {
                                spanStyle.append("font-size:").append(escapeHtml(runSize.trim())).append("pt;");
                            }
                            String fgHex = parseSignedRgbToHex(runFg, true);
                            if (!fgHex.isEmpty()) {
                                spanStyle.append("color:").append(fgHex).append(";");
                            }
                            String bgHex = parseSignedRgbToHex(runBg, false);
                            if (!bgHex.isEmpty()) {
                                spanStyle.append("background-color:").append(bgHex).append(";");
                            }
                            if (spanStyle.length() > 0) {
                                escaped = "<span style=\"" + spanStyle.toString() + "\">" + escaped + "</span>";
                            }
                            pContent.append(escaped);
                        }
                    }
                }
            }
            childNode = childNode.getNextSibling();
        }

        if (!hasContent) {
            pContent.append("<br>");
        }

        String formattedParagraphHtml = formatParagraphTabs(pContent.toString());
        outHtml.append("<p style=\"").append(styleAttr.toString()).append("\"");
        if (!stopsList.isEmpty()) {
            outHtml.append(" data-tab-stops=\"").append(String.join(",", stopsList)).append("\"");
        }
        if (tabSet != null && !tabSet.isEmpty()) {
            outHtml.append(" data-udf-tabset=\"").append(escapeHtml(tabSet)).append("\"");
        }
        if (!lineSpacing.isEmpty()) {
            outHtml.append(" data-udf-linespacing=\"").append(escapeHtml(lineSpacing)).append("\"");
        }
        if (isNumbered) {
            outHtml.append(" data-udf-numbered=\"true\"");
            if (p.hasAttribute("NumberType")) outHtml.append(" data-udf-number-type=\"").append(escapeHtml(p.getAttribute("NumberType"))).append("\"");
            if (p.hasAttribute("ListId")) outHtml.append(" data-udf-list-id=\"").append(escapeHtml(p.getAttribute("ListId"))).append("\"");
            if (p.hasAttribute("ListLevel")) outHtml.append(" data-udf-list-level=\"").append(escapeHtml(p.getAttribute("ListLevel"))).append("\"");
        }
        if (isBulleted) {
            outHtml.append(" data-udf-bulleted=\"true\"");
        }
        outHtml.append(">")
               .append(formattedParagraphHtml)
               .append("</p>\n");
    }

    private static void appendTableToHtml(
            Element tableElem,
            String rawText,
            int textLen,
            Map<String, Integer> listCounters,
            Map<String, String> dataMap,
            Map<String, Map<String, String>> styleMap,
            StringBuilder outHtml
    ) {
        String borderAttr = tableElem.getAttribute("border");
        boolean isBorderNone = "borderNone".equalsIgnoreCase(borderAttr) || "none".equalsIgnoreCase(borderAttr);
        String colSpansAttr = tableElem.getAttribute("columnSpans");
        double[] colWidthsPct = null;
        if (colSpansAttr != null && !colSpansAttr.trim().isEmpty()) {
            String[] parts = colSpansAttr.split(",");
            double[] rawWidths = new double[parts.length];
            double total = 0;
            for (int i = 0; i < parts.length; i++) {
                try {
                    rawWidths[i] = Math.max(1.0, Double.parseDouble(parts[i].trim()));
                    total += rawWidths[i];
                } catch (Exception ignored) {
                    rawWidths[i] = 100.0;
                    total += 100.0;
                }
            }
            if (total > 0) {
                colWidthsPct = new double[parts.length];
                for (int i = 0; i < parts.length; i++) {
                    colWidthsPct[i] = (rawWidths[i] / total) * 100.0;
                }
            }
        }

        String tableStyle = isBorderNone
            ? "width:100%; border-collapse:collapse; margin:6px 0; border:none;"
            : "width:100%; border-collapse:collapse; margin:6px 0; border:1px solid #333;";

        outHtml.append("<table style=\"").append(tableStyle).append("\"");
        if (borderAttr != null && !borderAttr.isEmpty()) {
            outHtml.append(" data-udf-border=\"").append(escapeHtml(borderAttr)).append("\"");
        }
        if (colSpansAttr != null && !colSpansAttr.isEmpty()) {
            outHtml.append(" data-udf-col-spans=\"").append(escapeHtml(colSpansAttr)).append("\"");
        }
        outHtml.append(">\n");

        // Yalnızca doğrudan <row> çocuklarını dön (iç içe tabloların karışmaması için)
        Node rNode = tableElem.getFirstChild();
        while (rNode != null) {
            if (rNode.getNodeType() == Node.ELEMENT_NODE && "row".equalsIgnoreCase(rNode.getNodeName())) {
                Element rowElem = (Element) rNode;
                outHtml.append("  <tr style=\"border:none;\">\n");

                List<Element> directCells = new ArrayList<>();
                Node cNode = rowElem.getFirstChild();
                while (cNode != null) {
                    if (cNode.getNodeType() == Node.ELEMENT_NODE && "cell".equalsIgnoreCase(cNode.getNodeName())) {
                        directCells.add((Element) cNode);
                    }
                    cNode = cNode.getNextSibling();
                }

                int cellCount = directCells.size();
                double defaultCellWidthPct = cellCount > 0 ? (100.0 / cellCount) : 100.0;

                for (int c = 0; c < cellCount; c++) {
                    Element cellElem = directCells.get(c);
                    double cellWidthPct = (colWidthsPct != null && c < colWidthsPct.length) ? colWidthsPct[c] : defaultCellWidthPct;
                    String cellBorderAttr = cellElem.getAttribute("border");
                    boolean cellNoBorder = isBorderNone || "borderNone".equalsIgnoreCase(cellBorderAttr) || "none".equalsIgnoreCase(cellBorderAttr);

                    StringBuilder cellStyle = new StringBuilder("vertical-align:top; padding:3px 6px; width:")
                            .append(String.format(Locale.US, "%.1f", cellWidthPct)).append("%;");
                    if (cellNoBorder) {
                        cellStyle.append(" border:none;");
                    } else {
                        cellStyle.append(" border:1px solid #333;");
                    }
                    String cellBg = parseSignedRgbToHex(cellElem.getAttribute("bgColor"), false);
                    if (cellBg.isEmpty()) cellBg = parseSignedRgbToHex(cellElem.getAttribute("background"), false);
                    if (!cellBg.isEmpty()) {
                        cellStyle.append(" background-color:").append(cellBg).append(";");
                    }

                    outHtml.append("    <td style=\"").append(cellStyle).append("\"");
                    if (cellElem.hasAttribute("colSpan")) {
                        outHtml.append(" colspan=\"").append(escapeHtml(cellElem.getAttribute("colSpan"))).append("\"");
                    }
                    if (cellElem.hasAttribute("rowSpan")) {
                        outHtml.append(" rowspan=\"").append(escapeHtml(cellElem.getAttribute("rowSpan"))).append("\"");
                    }
                    outHtml.append(">\n");

                    boolean hasCellChild = false;
                    Node cc = cellElem.getFirstChild();
                    while (cc != null) {
                        if (cc.getNodeType() == Node.ELEMENT_NODE) {
                            Element cce = (Element) cc;
                            if ("paragraph".equalsIgnoreCase(cce.getTagName())) {
                                appendParagraphToHtml(cce, rawText, textLen, listCounters, dataMap, styleMap, outHtml, false);
                                hasCellChild = true;
                            } else if ("table".equalsIgnoreCase(cce.getTagName())) {
                                appendTableToHtml(cce, rawText, textLen, listCounters, dataMap, styleMap, outHtml);
                                hasCellChild = true;
                            }
                        }
                        cc = cc.getNextSibling();
                    }
                    if (!hasCellChild) {
                        outHtml.append("<p style=\"text-align: left;\"><br></p>\n");
                    }

                    outHtml.append("    </td>\n");
                }
                outHtml.append("  </tr>\n");
            }
            rNode = rNode.getNextSibling();
        }
        outHtml.append("</table>\n");
    }

    private static String formatParagraphTabs(String pHtml) {
        if (!pHtml.contains("\t")) return pHtml;
        return pHtml.replace("\t", "<span class=\"udf-tab-space\" contenteditable=\"false\">&#8203;</span>");
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

    private static int parseHexOrCssColorToSignedInt(String colorStr) {
        if (colorStr == null || colorStr.trim().isEmpty()) return 0;
        String c = colorStr.trim().toLowerCase(Locale.ROOT);
        try {
            if (c.startsWith("#")) {
                String hex = c.substring(1);
                if (hex.length() == 3) {
                    hex = "" + hex.charAt(0) + hex.charAt(0) + hex.charAt(1) + hex.charAt(1) + hex.charAt(2) + hex.charAt(2);
                }
                if (hex.length() == 6) {
                    int rgb = Integer.parseInt(hex, 16);
                    return 0xFF000000 | rgb;
                }
            } else if (c.startsWith("rgb")) {
                int open = c.indexOf('(');
                int close = c.indexOf(')');
                if (open >= 0 && close > open) {
                    String[] parts = c.substring(open + 1, close).split(",");
                    if (parts.length >= 3) {
                        int r = Integer.parseInt(parts[0].trim()) & 0xFF;
                        int g = Integer.parseInt(parts[1].trim()) & 0xFF;
                        int b = Integer.parseInt(parts[2].trim()) & 0xFF;
                        return 0xFF000000 | (r << 16) | (g << 8) | b;
                    }
                }
            }
        } catch (Exception ignored) {}
        return 0;
    }

    private static int appendParagraphXml(JSONObject pObj, StringBuilder rawContent, StringBuilder outXml, int currentOffset, String indentPrefix) throws Exception {
        int align = pObj.optInt("align", 3);
        double spaceAbove = pObj.optDouble("spaceAbove", 0.0);
        double spaceBelow = pObj.optDouble("spaceBelow", 0.0);
        double lineSpacing = pObj.optDouble("lineSpacing", 0.0);
        double firstLineCm = pObj.optDouble("firstLineIndent", 0.0);
        double leftIndentCm = pObj.optDouble("leftIndent", 0.0);
        double rightIndentCm = pObj.optDouble("rightIndent", 0.0);

        // Havelsan UYAP birebir ters girinti dönüşümü:
        // CSS'te: marginLeftCm = LeftIndent + Hanging, textIndentCm = FirstLineIndent - Hanging
        double udfLeftPt = 0.0;
        double udfFirstPt = 0.0;
        double udfHangPt = 0.0;
        if (firstLineCm < -0.01) {
            double firstLinePosCm = Math.max(0.0, leftIndentCm + firstLineCm);
            udfLeftPt = firstLinePosCm * 28.3465;
            udfFirstPt = 0.0;
            udfHangPt = Math.max(0.0, leftIndentCm - firstLinePosCm) * 28.3465;
        } else {
            udfLeftPt = Math.max(0.0, leftIndentCm) * 28.3465;
            udfFirstPt = Math.max(0.0, firstLineCm) * 28.3465;
            udfHangPt = 0.0;
        }
        double udfRightPt = Math.max(0.0, rightIndentCm) * 28.3465;

        String rawTabSet = pObj.optString("udfTabSet", "");
        String tabStopsStr = pObj.optString("tabStops", "");
        StringBuilder tabSetBuilder = new StringBuilder();
        if (!tabStopsStr.isEmpty()) {
            String[] parts = tabStopsStr.split(",");
            for (String part : parts) {
                try {
                    double cm = Double.parseDouble(part.trim());
                    if (cm > 0) {
                        double pt = cm * 28.3465;
                        if (tabSetBuilder.length() > 0) tabSetBuilder.append(",");
                        tabSetBuilder.append(String.format(Locale.US, "%.1f:0:0", pt));
                    }
                } catch (Exception ignored) {}
            }
        } else if (!rawTabSet.isEmpty()) {
            tabSetBuilder.append(rawTabSet);
        }

        outXml.append(indentPrefix).append("<paragraph");
        if (tabSetBuilder.length() > 0) {
            outXml.append(" TabSet=\"").append(escapeXml(tabSetBuilder.toString())).append("\"");
        }
        if (udfLeftPt > 0.05) {
            outXml.append(" LeftIndent=\"").append(String.format(Locale.US, "%.1f", udfLeftPt)).append("\"");
        }
        if (udfFirstPt > 0.05) {
            outXml.append(" FirstLineIndent=\"").append(String.format(Locale.US, "%.1f", udfFirstPt)).append("\"");
        }
        if (udfHangPt > 0.05) {
            outXml.append(" Hanging=\"").append(String.format(Locale.US, "%.1f", udfHangPt)).append("\"");
        }
        if (udfRightPt > 0.05) {
            outXml.append(" RightIndent=\"").append(String.format(Locale.US, "%.1f", udfRightPt)).append("\"");
        }
        if (spaceAbove > 0.05) {
            outXml.append(" SpaceAbove=\"").append(String.format(Locale.US, "%.1f", spaceAbove)).append("\"");
        }
        if (spaceBelow > 0.05) {
            outXml.append(" SpaceBelow=\"").append(String.format(Locale.US, "%.1f", spaceBelow)).append("\"");
        }
        if (lineSpacing > 0.01) {
            outXml.append(" LineSpacing=\"").append(String.format(Locale.US, "%.2f", lineSpacing)).append("\"");
        }
        if (pObj.optBoolean("numbered", false)) {
            outXml.append(" Numbered=\"true\"");
            String numType = pObj.optString("numberType", "NUMBER_TYPE_NUMBER_TRE");
            outXml.append(" NumberType=\"").append(escapeXml(numType)).append("\"");
            if (pObj.has("listId")) outXml.append(" ListId=\"").append(escapeXml(pObj.optString("listId"))).append("\"");
            if (pObj.has("listLevel")) outXml.append(" ListLevel=\"").append(escapeXml(pObj.optString("listLevel"))).append("\"");
        } else if (pObj.optBoolean("bulleted", false)) {
            outXml.append(" Bulleted=\"true\"");
        }
        outXml.append(" Alignment=\"").append(align).append("\">\n");

        JSONArray runs = pObj.optJSONArray("runs");
        if (runs != null && runs.length() > 0) {
            for (int j = 0; j < runs.length(); j++) {
                JSONObject r = runs.getJSONObject(j);
                String rType = r.optString("type", "text");
                if ("image".equalsIgnoreCase(rType)) {
                    String imgData = r.optString("imageData", "");
                    if (!imgData.isEmpty()) {
                        double wPt = r.optDouble("widthPt", 100.0);
                        double hPt = r.optDouble("heightPt", 50.0);
                        // Resmi Havelsan UYAP standardı: Her <image> elemanı <content> içinde 1 karakter ('¸' = \u00b8) yer kaplar
                        rawContent.append('\u00b8');
                        outXml.append(indentPrefix).append("    <image width=\"").append(String.format(Locale.US, "%.4f", wPt))
                              .append("\" height=\"").append(String.format(Locale.US, "%.4f", hPt))
                              .append("\" resolver=\"hvl-default\" imageData=\"").append(escapeXml(imgData))
                              .append("\" startOffset=\"").append(currentOffset)
                              .append("\" length=\"1\" />\n");
                        currentOffset += 1;
                    }
                    continue;
                }

                String text = r.optString("text", "");
                boolean bold = r.optBoolean("bold", false);
                boolean italic = r.optBoolean("italic", false);
                boolean underline = r.optBoolean("underline", false);
                boolean subscript = r.optBoolean("subscript", false);
                boolean superscript = r.optBoolean("superscript", false);
                boolean strike = r.optBoolean("strikeThrough", false) || r.optBoolean("strikethrough", false);
                String fontFamily = r.optString("fontFamily", "");
                double fontSize = r.optDouble("fontSize", 0.0);
                String colorStr = r.optString("color", "");
                String bgColorStr = r.optString("backgroundColor", "");

                StringBuilder styleAttrs = new StringBuilder();
                if (!fontFamily.isEmpty()) {
                    String cleanFamily = fontFamily.replace("'", "").replace("\"", "").split(",")[0].trim();
                    if (!cleanFamily.isEmpty() && !"Times New Roman".equalsIgnoreCase(cleanFamily)) {
                        styleAttrs.append(" family=\"").append(escapeXml(cleanFamily)).append("\"");
                    }
                }
                if (fontSize > 1.0 && Math.abs(fontSize - 12.0) > 0.1) {
                    if (fontSize == Math.floor(fontSize)) {
                        styleAttrs.append(" size=\"").append((int) fontSize).append("\"");
                    } else {
                        styleAttrs.append(" size=\"").append(String.format(Locale.US, "%.1f", fontSize)).append("\"");
                    }
                }
                int fgInt = parseHexOrCssColorToSignedInt(colorStr);
                if (fgInt != 0 && (fgInt & 0xFFFFFF) != 0x000000 && (fgInt & 0xFFFFFF) != 0x333333) {
                    styleAttrs.append(" foreground=\"").append(fgInt).append("\"");
                }
                int bgInt = parseHexOrCssColorToSignedInt(bgColorStr);
                if (bgInt != 0 && (bgInt & 0xFFFFFF) != 0xFFFFFF) {
                    styleAttrs.append(" background=\"").append(bgInt).append("\"");
                }
                if (bold) styleAttrs.append(" bold=\"true\"");
                if (italic) styleAttrs.append(" italic=\"true\"");
                if (underline) styleAttrs.append(" underline=\"true\"");
                if (subscript) styleAttrs.append(" Subscript=\"true\"");
                if (superscript) styleAttrs.append(" Superscript=\"true\"");
                if (strike) styleAttrs.append(" strikethrough=\"true\"");

                // Metin içindeki \t karakterlerini resmi Havelsan <tab> elemanlarına ayır
                int idx = 0;
                int tLen = text.length();
                while (idx < tLen) {
                    int tabPos = text.indexOf('\t', idx);
                    if (tabPos == -1) {
                        String sub = text.substring(idx);
                        int subLen = sub.length();
                        if (subLen > 0) {
                            rawContent.append(sub);
                            outXml.append(indentPrefix).append("    <content startOffset=\"").append(currentOffset)
                                  .append("\" length=\"").append(subLen).append("\"")
                                  .append(styleAttrs)
                                  .append(" />\n");
                            currentOffset += subLen;
                        }
                        break;
                    } else {
                        if (tabPos > idx) {
                            String sub = text.substring(idx, tabPos);
                            int subLen = sub.length();
                            rawContent.append(sub);
                            outXml.append(indentPrefix).append("    <content startOffset=\"").append(currentOffset)
                                  .append("\" length=\"").append(subLen).append("\"")
                                  .append(styleAttrs)
                                  .append(" />\n");
                            currentOffset += subLen;
                        }
                        int tabEnd = tabPos + 1;
                        while (tabEnd < tLen && text.charAt(tabEnd) == '\t') tabEnd++;
                        int tabCount = tabEnd - tabPos;
                        for (int tc = 0; tc < tabCount; tc++) rawContent.append('\t');
                        outXml.append(indentPrefix).append("    <tab startOffset=\"").append(currentOffset)
                              .append("\" length=\"").append(tabCount).append("\"")
                              .append(styleAttrs)
                              .append(" />\n");
                        currentOffset += tabCount;
                        idx = tabEnd;
                    }
                }
            }
        }

        // Havelsan UYAP standardı: Her paragraf sonunda 1 karakter '\n' bulunur
        rawContent.append('\n');
        outXml.append(indentPrefix).append("    <content startOffset=\"").append(currentOffset)
              .append("\" length=\"1\" />\n");
        currentOffset += 1;

        outXml.append(indentPrefix).append("</paragraph>\n");
        return currentOffset;
    }

    private static int appendTableXml(JSONObject tblObj, StringBuilder rawContent, StringBuilder outXml, int currentOffset, String indentPrefix) throws Exception {
        String border = tblObj.optString("border", "borderCell");
        if (border.isEmpty()) border = "borderCell";
        String colSpans = tblObj.optString("colSpans", "");
        JSONArray rows = tblObj.optJSONArray("rows");
        if (rows == null || rows.length() == 0) return currentOffset;

        int maxCols = 1;
        for (int r = 0; r < rows.length(); r++) {
            JSONObject rObj = rows.getJSONObject(r);
            JSONArray cells = rObj.optJSONArray("cells");
            if (cells != null && cells.length() > maxCols) maxCols = cells.length();
        }
        if (colSpans.isEmpty()) {
            StringBuilder csb = new StringBuilder();
            int spanPerCol = Math.max(20, 480 / maxCols);
            for (int c = 0; c < maxCols; c++) {
                if (c > 0) csb.append(",");
                csb.append(spanPerCol);
            }
            colSpans = csb.toString();
        }

        outXml.append(indentPrefix).append("<table tableName=\"Sabit\" columnCount=\"").append(maxCols)
              .append("\" columnSpans=\"").append(escapeXml(colSpans))
              .append("\" border=\"").append(escapeXml(border)).append("\">\n");

        for (int r = 0; r < rows.length(); r++) {
            JSONObject rObj = rows.getJSONObject(r);
            outXml.append(indentPrefix).append("    <row rowName=\"row").append(r + 1).append("\" rowType=\"dataRow\" border=\"").append(escapeXml(border)).append("\">\n");
            JSONArray cells = rObj.optJSONArray("cells");
            if (cells != null) {
                for (int c = 0; c < cells.length(); c++) {
                    JSONObject cellObj = cells.getJSONObject(c);
                    outXml.append(indentPrefix).append("        <cell");
                    int colSpan = cellObj.optInt("colSpan", 1);
                    int rowSpan = cellObj.optInt("rowSpan", 1);
                    if (colSpan > 1) outXml.append(" colSpan=\"").append(colSpan).append("\"");
                    if (rowSpan > 1) outXml.append(" rowSpan=\"").append(rowSpan).append("\"");
                    outXml.append(" border=\"").append(escapeXml(border)).append("\">\n");

                    JSONArray cellParas = cellObj.optJSONArray("paragraphs");
                    if (cellParas != null && cellParas.length() > 0) {
                        for (int p = 0; p < cellParas.length(); p++) {
                            JSONObject pItem = cellParas.getJSONObject(p);
                            if ("table".equalsIgnoreCase(pItem.optString("type", "paragraph"))) {
                                currentOffset = appendTableXml(pItem, rawContent, outXml, currentOffset, indentPrefix + "            ");
                            } else {
                                currentOffset = appendParagraphXml(pItem, rawContent, outXml, currentOffset, indentPrefix + "            ");
                            }
                        }
                    } else {
                        JSONObject emptyP = new JSONObject();
                        emptyP.put("align", 0);
                        emptyP.put("runs", new JSONArray());
                        currentOffset = appendParagraphXml(emptyP, rawContent, outXml, currentOffset, indentPrefix + "            ");
                    }
                    outXml.append(indentPrefix).append("        </cell>\n");
                }
            }
            outXml.append(indentPrefix).append("    </row>\n");
        }

        outXml.append(indentPrefix).append("</table>\n");
        return currentOffset;
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
        JSONArray headerParagraphs = null;
        JSONArray footerParagraphs = null;
        String headerText = "";
        String footerText = "";
        int headerStartPage = 1;
        String footerPageSpec = "";
        String footerForeStr = "Sayfa:";
        String footerSep = "/";
        String footerPageStart = "1";
        double leftMarginCm = 1.5;
        double rightMarginCm = 1.5;
        double topMarginCm = 1.5;
        double bottomMarginCm = 1.5;
        double headerMarginCm = 0.7;
        double footerMarginCm = 0.7;
        String paperOrientation = "1";
        String mediaSizeName = "1";

        if (trimmed.startsWith("{")) {
            JSONObject obj = new JSONObject(trimmed);
            headerText = obj.optString("header", "");
            footerText = obj.optString("footer", "");
            headerStartPage = obj.optInt("headerStartPage", 1);
            footerPageSpec = obj.optString("footerPageSpec", "");
            footerForeStr = obj.optString("footerForeStr", "Sayfa:");
            footerSep = obj.optString("footerSep", "/");
            footerPageStart = obj.optString("footerPageStart", "1");
            headerParagraphs = obj.optJSONArray("headerParagraphs");
            footerParagraphs = obj.optJSONArray("footerParagraphs");
            paragraphs = obj.optJSONArray("paragraphs");
            if (paragraphs == null) paragraphs = new JSONArray();

            if (obj.has("margins")) {
                JSONObject m = obj.getJSONObject("margins");
                leftMarginCm = m.optDouble("left", 1.5);
                rightMarginCm = m.optDouble("right", 1.5);
                topMarginCm = m.optDouble("top", 1.5);
                bottomMarginCm = m.optDouble("bottom", 1.5);
                headerMarginCm = m.optDouble("header", 0.7);
                footerMarginCm = m.optDouble("footer", 0.7);
                if (m.has("orientation")) {
                    paperOrientation = "landscape".equalsIgnoreCase(m.optString("orientation")) ? "2" : "1";
                }
            } else {
                leftMarginCm = obj.optDouble("leftMarginCm", 1.5);
                rightMarginCm = obj.optDouble("rightMarginCm", 1.5);
                topMarginCm = obj.optDouble("topMarginCm", 1.5);
                bottomMarginCm = obj.optDouble("bottomMarginCm", 1.5);
                headerMarginCm = obj.optDouble("headerMarginCm", 0.7);
                footerMarginCm = obj.optDouble("footerMarginCm", 0.7);
                paperOrientation = obj.optString("paperOrientation", "1");
                if ("landscape".equalsIgnoreCase(paperOrientation)) paperOrientation = "2";
                else if ("portrait".equalsIgnoreCase(paperOrientation)) paperOrientation = "1";
            }
            mediaSizeName = obj.optString("mediaSizeName", "1");
        } else if (trimmed.startsWith("[")) {
            paragraphs = new JSONArray(trimmed);
        } else {
            paragraphs = new JSONArray();
        }

        double leftMarginPt = leftMarginCm * 28.3465;
        double rightMarginPt = rightMarginCm * 28.3465;
        double topMarginPt = topMarginCm * 28.3465;
        double bottomMarginPt = bottomMarginCm * 28.3465;
        double headerOffsetPt = headerMarginCm * 28.3465;
        double footerOffsetPt = footerMarginCm * 28.3465;

        StringBuilder rawContent = new StringBuilder();
        StringBuilder elementsXml = new StringBuilder();
        int currentOffset = 0;

        // 1. Üstbilgi (<header>) - Resmi Havelsan UYAP standardına göre <elements> içindeki İLK elemandır
        if ((headerParagraphs != null && headerParagraphs.length() > 0) || !headerText.trim().isEmpty()) {
            elementsXml.append("<header");
            if (headerStartPage > 1) {
                elementsXml.append(" startPage=\"").append(headerStartPage).append("\"");
            }
            elementsXml.append(">\n");
            if (headerParagraphs != null && headerParagraphs.length() > 0) {
                for (int i = 0; i < headerParagraphs.length(); i++) {
                    JSONObject hp = headerParagraphs.getJSONObject(i);
                    String bType = hp.optString("type", "paragraph");
                    if ("image".equalsIgnoreCase(bType)) {
                        String imgData = hp.optString("imageData", "");
                        if (!imgData.isEmpty()) {
                            double wPt = hp.optDouble("widthPt", 118.0);
                            double hPt = hp.optDouble("heightPt", 50.0);
                            rawContent.append('\u00b8');
                            elementsXml.append("    <image width=\"").append(String.format(Locale.US, "%.4f", wPt))
                                       .append("\" height=\"").append(String.format(Locale.US, "%.4f", hPt))
                                       .append("\" resolver=\"hvl-default\" imageData=\"").append(escapeXml(imgData))
                                       .append("\" startOffset=\"").append(currentOffset)
                                       .append("\" length=\"1\" />\n");
                            currentOffset += 1;
                        }
                    } else if ("table".equalsIgnoreCase(bType)) {
                        currentOffset = appendTableXml(hp, rawContent, elementsXml, currentOffset, "    ");
                    } else {
                        currentOffset = appendParagraphXml(hp, rawContent, elementsXml, currentOffset, "    ");
                    }
                }
            } else {
                JSONObject hp = new JSONObject();
                hp.put("align", 1);
                JSONArray runs = new JSONArray();
                JSONObject r = new JSONObject();
                r.put("text", headerText.trim());
                r.put("bold", true);
                runs.put(r);
                hp.put("runs", runs);
                currentOffset = appendParagraphXml(hp, rawContent, elementsXml, currentOffset, "    ");
            }
            elementsXml.append("</header>\n");
        }

        // 2. Gövde blokları (<paragraph>, <table>, <page-break>)
        if (paragraphs.length() == 0) {
            JSONObject emptyP = new JSONObject();
            emptyP.put("align", 3);
            emptyP.put("runs", new JSONArray());
            currentOffset = appendParagraphXml(emptyP, rawContent, elementsXml, currentOffset, "    ");
        } else {
            for (int i = 0; i < paragraphs.length(); i++) {
                JSONObject block = paragraphs.getJSONObject(i);
                String blockType = block.optString("type", "paragraph");
                if ("table".equalsIgnoreCase(blockType)) {
                    currentOffset = appendTableXml(block, rawContent, elementsXml, currentOffset, "    ");
                } else if ("pageBreak".equalsIgnoreCase(blockType) || "page-break".equalsIgnoreCase(blockType)) {
                    rawContent.append('\n');
                    elementsXml.append("    <page-break startOffset=\"").append(currentOffset).append("\" length=\"1\" />\n");
                    currentOffset += 1;
                } else {
                    currentOffset = appendParagraphXml(block, rawContent, elementsXml, currentOffset, "    ");
                }
            }
        }

        // 3. Altbilgi (<footer>) - Resmi Havelsan UYAP standardına göre <elements> içindeki SON elemandır
        if ((footerParagraphs != null && footerParagraphs.length() > 0) || !footerText.trim().isEmpty() || !footerPageSpec.isEmpty()) {
            String spec = !footerPageSpec.isEmpty() ? footerPageSpec : "BSP32_2120";
            elementsXml.append("<footer pageNumber-spec=\"").append(escapeXml(spec))
                       .append("\" pageNumber-foreStr=\"").append(escapeXml(footerForeStr))
                       .append("\" pageNumber-seperator=\"").append(escapeXml(footerSep))
                       .append("\" pageNumber-start=\"").append(escapeXml(footerPageStart)).append("\">\n");
            if (footerParagraphs != null && footerParagraphs.length() > 0) {
                for (int i = 0; i < footerParagraphs.length(); i++) {
                    JSONObject fp = footerParagraphs.getJSONObject(i);
                    String bType = fp.optString("type", "paragraph");
                    if ("image".equalsIgnoreCase(bType)) {
                        String imgData = fp.optString("imageData", "");
                        if (!imgData.isEmpty()) {
                            double wPt = fp.optDouble("widthPt", 118.0);
                            double hPt = fp.optDouble("heightPt", 50.0);
                            rawContent.append('\u00b8');
                            elementsXml.append("    <image width=\"").append(String.format(Locale.US, "%.4f", wPt))
                                       .append("\" height=\"").append(String.format(Locale.US, "%.4f", hPt))
                                       .append("\" resolver=\"hvl-default\" imageData=\"").append(escapeXml(imgData))
                                       .append("\" startOffset=\"").append(currentOffset)
                                       .append("\" length=\"1\" />\n");
                            currentOffset += 1;
                        }
                    } else if ("table".equalsIgnoreCase(bType)) {
                        currentOffset = appendTableXml(fp, rawContent, elementsXml, currentOffset, "    ");
                    } else {
                        currentOffset = appendParagraphXml(fp, rawContent, elementsXml, currentOffset, "    ");
                    }
                }
            } else if (!footerText.trim().isEmpty()) {
                JSONObject fp = new JSONObject();
                fp.put("align", 1);
                JSONArray runs = new JSONArray();
                JSONObject r = new JSONObject();
                r.put("text", footerText.trim());
                runs.put(r);
                fp.put("runs", runs);
                currentOffset = appendParagraphXml(fp, rawContent, elementsXml, currentOffset, "    ");
            }
            elementsXml.append("</footer>\n");
        }

        // Havelsan UYAP 1.8 standardı XML şablonu (pageFormat üzerinde standart dışı headerText/footerText YOKTUR)
        String finalXml = "<?xml version=\"1.0\" encoding=\"UTF-8\" ?>\n"
                + "<template format_id=\"1.8\">\n"
                + "<content><![CDATA[" + rawContent.toString() + "]]></content>\n"
                + "<properties><pageFormat mediaSizeName=\"" + escapeXml(mediaSizeName) + "\" leftMargin=\"" + String.format(Locale.US, "%.4f", leftMarginPt) + "\" rightMargin=\"" + String.format(Locale.US, "%.4f", rightMarginPt) + "\" topMargin=\"" + String.format(Locale.US, "%.4f", topMarginPt) + "\" bottomMargin=\"" + String.format(Locale.US, "%.4f", bottomMarginPt) + "\" paperOrientation=\"" + escapeXml(paperOrientation) + "\" headerFOffset=\"" + String.format(Locale.US, "%.1f", headerOffsetPt) + "\" footerFOffset=\"" + String.format(Locale.US, "%.1f", footerOffsetPt) + "\" /></properties>\n"
                + "<elements resolver=\"hvl-default\">\n"
                + elementsXml.toString()
                + "</elements>\n"
                + "<styles><style name=\"default\" description=\"Geçerli\" family=\"Dialog\" size=\"12\" bold=\"false\" italic=\"false\" foreground=\"-13421773\" FONT_ATTRIBUTE_KEY=\"javax.swing.plaf.FontUIResource[family=Dialog,name=Dialog,style=plain,size=12]\" /><style name=\"hvl-default\" family=\"Times New Roman\" size=\"12\" description=\"Gövde\" /></styles>\n"
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
                            if (xc.getBasicConstraints() == -1) {
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
