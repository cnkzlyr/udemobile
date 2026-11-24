package app.eimza.mobile;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/** Read-only PKCS#15 CDF/PrKDF association. No key-index or PIN guessing. */
final class AkisPkcs15 {
    private AkisPkcs15() { }
    static byte keyReference(byte[] cdf, byte[] prkdf, byte[] certificateFile) throws IOException {
        byte[] certificateId = null;
        for (Node record : records(cdf)) {
            if (record.children.size() < 3) continue;
            Node attributes = record.children.get(1);
            byte[] id = firstOctets(attributes);
            boolean matches = false;
            for (int i = 2; i < record.children.size(); i++)
                matches |= containsPath(record.children.get(i), certificateFile);
            if (matches) {
                if (certificateId != null) throw new IOException("PKCS15 sertifika yolu birden çok nesneyle eşleşiyor");
                certificateId = id;
            }
        }
        if (certificateId == null) throw new IOException("PKCS15 CDF içinde seçilen sertifika bulunamadı");
        Integer reference = null;
        for (Node record : records(prkdf)) {
            if (record.children.size() < 2) continue;
            Node attributes = record.children.get(1);
            if (!Arrays.equals(certificateId, firstOctets(attributes))) continue;
            // CommonKeyAttributes: id, usage, native?, accessFlags?, keyReference?, ...
            for (Node field : attributes.children) if (field.tag == 2) {
                if (field.value.length == 0 || field.value.length > 2) throw new IOException("PKCS15 anahtar referansı geçersiz");
                int value = 0; for (byte b : field.value) value = (value << 8) | (b & 255);
                if (value > 255) throw new IOException("PKCS15 anahtar referansı byte sınırını aşıyor");
                if (reference != null) throw new IOException("PKCS15 anahtar referansı belirsiz");
                reference = value;
            }
        }
        if (reference == null) throw new IOException("PKCS15 özel anahtar referansı bulunamadı");
        return (byte) (int) reference;
    }
    private static byte[] firstOctets(Node node) {
        for (Node field : node.children) if (field.tag == 4) return field.value;
        return null;
    }
    private static boolean containsPath(Node node, byte[] file) {
        if (file == null || file.length < 2) return false;
        if (node.tag == 4 && node.value.length >= file.length && node.value.length % 2 == 0) {
            int start = node.value.length - file.length;
            if (Arrays.equals(Arrays.copyOfRange(node.value, start, node.value.length), file)) return true;
        }
        for (Node child : node.children) if (containsPath(child, file)) return true;
        return false;
    }
    private static List<Node> records(byte[] raw) throws IOException {
        if (raw == null || raw.length == 0 || raw.length > 65536) throw new IOException("PKCS15 dizin dosyası boş/geçersiz");
        int[] cursor = {0}; List<Node> result = new ArrayList<>();
        while (cursor[0] < raw.length) {
            int b = raw[cursor[0]] & 255;
            if (b == 0 || b == 255) {
                for (int i = cursor[0]; i < raw.length; i++) if (raw[i] != 0 && (raw[i] & 255) != 255)
                    throw new IOException("PKCS15 dolgu sonrasında veri var");
                break;
            }
            Node node = parse(raw, cursor, raw.length, 0);
            // Some card files wrap the concatenated objects in a SEQUENCE OF.
            if (node.tag == 48 && !node.children.isEmpty() && !node.children.get(0).children.isEmpty()
                    && node.children.get(0).children.get(0).tag == 48) result.addAll(node.children);
            else result.add(node);
        }
        return result;
    }
    private static Node parse(byte[] data, int[] cursor, int end, int depth) throws IOException {
        if (depth > 16 || cursor[0] + 2 > end) throw new IOException("PKCS15 ASN1 sınırı geçersiz");
        int tag = data[cursor[0]++] & 255, length = data[cursor[0]++] & 255;
        if ((tag & 31) == 31) throw new IOException("PKCS15 yüksek ASN1 etiketi desteklenmiyor");
        if ((length & 128) != 0) {
            int count = length & 127; length = 0;
            if (count == 0 || count > 3 || cursor[0] + count > end) throw new IOException("PKCS15 ASN1 uzunluğu geçersiz");
            for (int i = 0; i < count; i++) length = (length << 8) | (data[cursor[0]++] & 255);
        }
        if (length > end - cursor[0]) throw new IOException("PKCS15 ASN1 dosyası kesik");
        int stop = cursor[0] + length;
        Node node = new Node(tag, Arrays.copyOfRange(data, cursor[0], stop));
        if ((tag & 32) != 0) while (cursor[0] < stop) node.children.add(parse(data, cursor, stop, depth + 1));
        else cursor[0] = stop;
        return node;
    }
    private static final class Node {
        final int tag; final byte[] value; final List<Node> children = new ArrayList<>();
        Node(int tag, byte[] value) { this.tag = tag; this.value = value; }
    }
}
