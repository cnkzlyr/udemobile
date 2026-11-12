package com.agy.uyapacici;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.zip.Inflater;

/**
 * Windows yazı tipleri (3.26.0) — Microsoft Core Fonts for the Web: Times New Roman, Arial, Arial Black, Courier New,
 * Georgia, Verdana, Trebuchet MS, Comic Sans MS, Impact, Andale Mono, Webdings.
 *
 * Lisans bu yazı tiplerinin yalnızca Microsoft'un ORİJİNAL, değiştirilmemiş kurulum dosyalarıyla dağıtılmasına izin
 * verir; uygulama onları içermez. Telefon ilk açılışta resmi aynadan (sourceforge corefonts) indirir, SHA-256 ile
 * doğrular ve kurulum dosyasının içindeki Microsoft CAB arşivini (LZX; gömülü cabextract ile) açarak .ttf dosyalarını yalnızca bu cihaza,
 * editörün yazı tipi klasörüne (~/.fonts) koyar. Böylece belgeler Windows'taki UYAP Editör ile aynı yazı tipiyle,
 * aynı satır kırılımıyla görünür; yazı tipi listesinde de gerçek adlarıyla çıkar.
 */
final class YaziTipleri {
    private YaziTipleri() { }

    static final String[][] PAKETLER = {
            {"andale32.exe", "0524fe42951adc3a7eb870e32f0920313c71f170c859b5f770d82b4ee111e970"},
            {"arial32.exe", "85297a4d146e9c87ac6f74822734bdee5f4b2a722d7eaa584b7f2cbf76f478f6"},
            {"arialb32.exe", "a425f0ffb6a1a5ede5b979ed6177f4f4f4fdef6ae7c302a7b7720ef332fec0a8"},
            {"comic32.exe", "9c6df3feefde26d4e41d4a4fe5db2a89f9123a772594d7f59afd062625cd204e"},
            {"courie32.exe", "bb511d861655dde879ae552eb86b134d6fae67cb58502e6ff73ec5d9151f3384"},
            {"georgi32.exe", "2c2c7dcda6606ea5cf08918fb7cd3f3359e9e84338dc690013f20cd42e930301"},
            {"impact32.exe", "6061ef3b7401d9642f5dfdb5f2b376aa14663f6275e60a51207ad4facf2fccfb"},
            {"times32.exe", "db56595ec6ef5d3de5c24994f001f03b2a13e37cee27bc25c58f6f43e8f807ab"},
            {"trebuc32.exe", "5a690d9bb8510be1b8b4fe49f1f2319651fe51bbe54775ddddd8ef0bd07fdac9"},
            {"verdan32.exe", "c1cb61255e363166794e47664e2f21af8e3a26cb6346eb8d2ae2fa85dd5aad96"},
            {"webdin32.exe", "64595b5abc1080fba8610c5c34fab5863408e806aafe84653ca8575bed17d75a"},
    };
    static final String KAYNAK = "https://downloads.sourceforge.net/corefonts/";

    interface Ilerleme { void yaz(String m); }

    /** Kurulu mu (Times New Roman ve Arial yeterli göstergedir). */
    static boolean kurulu(File dizin) {
        return new File(dizin, "times.ttf").isFile() && new File(dizin, "arial.ttf").isFile();
    }

    /** İndir, doğrula, aç. Döndürür: kurulan yazı tipi dosyası sayısı. */
    static int kur(android.content.Context c, File dizin, Ilerleme il) throws IOException {
        File rt = UyapMobil.rt(c), gecici = new File(c.getCacheDir(), "corefonts");
        gecici.mkdirs();
        dizin.mkdirs();
        int toplam = 0, n = 0;
        IOException son = null;
        for (String[] p : PAKETLER) {
            n++;
            if (il != null) il.yaz("Windows yazı tipleri indiriliyor (" + n + "/" + PAKETLER.length + ")…");
            try {
                byte[] exe = indir(KAYNAK + p[0]);
                if (!sha256(exe).equalsIgnoreCase(p[1])) throw new IOException(p[0] + ": SHA-256 uyuşmuyor");
                File f = new File(gecici, p[0]);
                try (OutputStream o = new FileOutputStream(f)) { o.write(exe); }
                // corefonts kurulumları LZX sıkıştırmalı CAB içerir: gömülü cabextract (glibc) ile açılır
                ProcessBuilder pb = new ProcessBuilder(new File(rt, "glibc/ld-linux-aarch64.so.1").getAbsolutePath(),
                        "--library-path", new File(rt, "glibc").getAbsolutePath(),
                        new File(rt, "bin/cabextract").getAbsolutePath(), "-q", "-L", "-F", "*.ttf", "-d", dizin.getAbsolutePath(), f.getAbsolutePath());
                pb.redirectErrorStream(true);
                pb.environment().remove("LD_PRELOAD");
                Process pr = pb.start();
                String cikti = new String(AdaletServisi.okuHepsi(pr.getInputStream()), StandardCharsets.UTF_8);
                int kod;
                try { kod = pr.waitFor(); } catch (InterruptedException e) { throw new IOException("kesildi"); }
                f.delete();
                if (kod != 0) throw new IOException(p[0] + ": cabextract " + kod + " " + cikti.trim());
                toplam++;
            } catch (IOException e) {
                son = e;
                Tani.hata("uyapmobil", "yazı tipi " + p[0], e);
            }
        }
        if (toplam == 0 && son != null) throw son;
        return toplam;
    }

    /** (Yedek, yalnızca MSZIP CAB'lar için; corefonts LZX kullanır.) */
    static int kurMszip(File dizin, Ilerleme il) throws IOException {
        dizin.mkdirs();
        int toplam = 0, n = 0;
        IOException son = null;
        for (String[] p : PAKETLER) {
            n++;
            if (il != null) il.yaz("Windows yazı tipleri indiriliyor (" + n + "/" + PAKETLER.length + ")…");
            try {
                byte[] exe = indir(KAYNAK + p[0]);
                if (!sha256(exe).equalsIgnoreCase(p[1])) throw new IOException(p[0] + ": SHA-256 uyuşmuyor");
                for (Dosya d : cabAc(exe)) {
                    String ad = d.ad.toLowerCase(Locale.ROOT);
                    if (!ad.endsWith(".ttf")) continue;
                    try (OutputStream o = new FileOutputStream(new File(dizin, ad))) { o.write(d.veri); }
                    toplam++;
                }
            } catch (IOException e) {
                son = e;
                Tani.hata("uyapmobil", "yazı tipi " + p[0], e);
            }
        }
        if (toplam == 0 && son != null) throw son;
        return toplam;
    }

    private static byte[] indir(String adres) throws IOException {
        for (int y = 0; y < 6; y++) {
            HttpURLConnection c = (HttpURLConnection) new URL(adres).openConnection();
            c.setConnectTimeout(20000);
            c.setReadTimeout(60000);
            c.setInstanceFollowRedirects(false);
            c.setRequestProperty("User-Agent", "Mozilla/5.0");
            int k = c.getResponseCode();
            if (k >= 300 && k < 400) {
                String yer = c.getHeaderField("Location");
                c.disconnect();
                if (yer == null) throw new IOException("yönlendirme adresi yok");
                adres = new URL(new URL(adres), yer).toString();
                continue;
            }
            if (k != 200) throw new IOException("HTTP " + k + " (" + adres + ")");
            try (InputStream in = c.getInputStream()) { return AdaletServisi.okuHepsi(in); }
        }
        throw new IOException("çok fazla yönlendirme");
    }

    static String sha256(byte[] b) {
        try {
            byte[] h = MessageDigest.getInstance("SHA-256").digest(b);
            StringBuilder sb = new StringBuilder();
            for (byte x : h) sb.append(String.format("%02x", x & 255));
            return sb.toString();
        } catch (Exception e) { return ""; }
    }

    // ------------------------------------------------------------------------------------ Microsoft CAB (MSZIP)
    static final class Dosya { String ad; byte[] veri; }

    private static int u16(byte[] b, int i) { return (b[i] & 255) | (b[i + 1] & 255) << 8; }
    private static long u32(byte[] b, int i) { return (u16(b, i) | (long) u16(b, i + 2) << 16) & 0xffffffffL; }

    /**
     * Kurulum dosyasının (PE) içindeki CAB'ı bul ve aç. Biçim: CFHEADER ("MSCF"), CFFOLDER (sıkıştırma: 1 = MSZIP),
     * CFFILE, CFDATA blokları. MSZIP: her blok "CK" + ham deflate; önceki 32 KB çıktı sözlük olarak sürer.
     */
    static List<Dosya> cabAc(byte[] b) throws IOException {
        int bas = -1;
        for (int i = 0; i + 4 < b.length; i++)
            if (b[i] == 'M' && b[i + 1] == 'S' && b[i + 2] == 'C' && b[i + 3] == 'F' && b[i + 4] == 0) {
                long uzun = u32(b, i + 8);
                if (uzun > 0 && i + uzun <= b.length + 16) { bas = i; break; }
            }
        if (bas < 0) throw new IOException("CAB bulunamadı");
        int h = bas;
        long dosyaOfs = u32(b, h + 16);
        int klasorSay = u16(b, h + 26), dosyaSay = u16(b, h + 28), bayrak = u16(b, h + 30);
        int p = h + 36, basRez = 0, klasorRez = 0, veriRez = 0;
        if ((bayrak & 4) != 0) { basRez = u16(b, p); klasorRez = b[p + 2] & 255; veriRez = b[p + 3] & 255; p += 4 + basRez; }
        if ((bayrak & 1) != 0) { while (b[p] != 0) p++; p++; while (b[p] != 0) p++; p++; }
        if ((bayrak & 2) != 0) { while (b[p] != 0) p++; p++; while (b[p] != 0) p++; p++; }
        List<byte[]> klasorler = new ArrayList<>();
        for (int f = 0; f < klasorSay; f++) {
            long veriBas = u32(b, p);
            int blokSay = u16(b, p + 4), tur = u16(b, p + 6) & 0x0f;
            p += 8 + klasorRez;
            klasorler.add(klasorAc(b, h + (int) veriBas, blokSay, tur, veriRez));
        }
        List<Dosya> sonuc = new ArrayList<>();
        int q = h + (int) dosyaOfs;
        for (int f = 0; f < dosyaSay; f++) {
            long boy = u32(b, q), ofs = u32(b, q + 4);
            int klasor = u16(b, q + 8);
            int ad0 = q + 16, ad1 = ad0;
            while (b[ad1] != 0) ad1++;
            Dosya d = new Dosya();
            d.ad = new String(b, ad0, ad1 - ad0, StandardCharsets.ISO_8859_1);
            q = ad1 + 1;
            if (klasor >= klasorler.size()) continue;
            byte[] k = klasorler.get(klasor);
            if (ofs + boy > k.length) throw new IOException("CAB bozuk: " + d.ad);
            d.veri = new byte[(int) boy];
            System.arraycopy(k, (int) ofs, d.veri, 0, (int) boy);
            sonuc.add(d);
        }
        return sonuc;
    }

    private static byte[] klasorAc(byte[] b, int p, int blokSay, int tur, int veriRez) throws IOException {
        ByteArrayOutputStream cikti = new ByteArrayOutputStream();
        byte[] pencere = new byte[0];
        for (int i = 0; i < blokSay; i++) {
            int sikisik = u16(b, p + 4), acik = u16(b, p + 6);
            int v = p + 8 + veriRez;
            if (tur == 0) {
                cikti.write(b, v, sikisik);
            } else if (tur == 1) {
                if (b[v] != 'C' || b[v + 1] != 'K') throw new IOException("MSZIP imzası yok");
                Inflater inf = new Inflater(true);
                if (pencere.length > 0) inf.setDictionary(pencere);
                inf.setInput(b, v + 2, sikisik - 2);
                byte[] blok = new byte[acik];
                int n = 0;
                try {
                    while (n < acik) {
                        int r = inf.inflate(blok, n, acik - n);
                        if (r == 0) {
                            if (inf.needsDictionary() && pencere.length > 0) { inf.setDictionary(pencere); continue; }
                            if (inf.finished() || inf.needsInput()) break;
                        }
                        n += r;
                    }
                } catch (java.util.zip.DataFormatException e) {
                    throw new IOException("MSZIP açılamadı: " + e.getMessage());
                } finally { inf.end(); }
                cikti.write(blok, 0, n);
                byte[] tum = cikti.toByteArray();
                int w = Math.min(32768, tum.length);
                pencere = new byte[w];
                System.arraycopy(tum, tum.length - w, pencere, 0, w);
            } else throw new IOException("desteklenmeyen CAB sıkıştırması: " + tur);
            p = v + sikisik;
        }
        return cikti.toByteArray();
    }
}
