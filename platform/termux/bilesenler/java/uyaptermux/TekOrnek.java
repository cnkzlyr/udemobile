package uyaptermux;

import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.security.SecureRandom;

/**
 * Tek ornek servisi: editor zaten aciksa cift tiklanan belge yeni JVM acilmadan bu ornekte acilir.
 * 127.0.0.1 uzerinde rastgele portta dinler; istemci her satirda "JETON\tKOMUT[\tYOL]" gonderir:
 *   OPEN <yol>  belgeyi acar      NEW  bos belge acar      PING  canli mi
 * Port/jeton/pid {@code <uyap.instance.dir>/instance.properties} dosyasina yalnizca sahibinin okuyabilecegi
 * izinle yazilir (ue.py okur). Jeton olmadan gelen istekler reddedilir.
 */
final class TekOrnek {
    private TekOrnek() { }

    static void baslat() {
        final String dir = System.getProperty("uyap.instance.dir");
        if (dir == null || dir.isEmpty()) return;
        try {
            final ServerSocket ss = new ServerSocket(0, 8, InetAddress.getByName("127.0.0.1"));
            byte[] b = new byte[16];
            new SecureRandom().nextBytes(b);
            StringBuilder sb = new StringBuilder();
            for (byte x : b) sb.append(String.format("%02x", x));
            final String jeton = sb.toString();

            File d = new File(dir);
            d.mkdirs();
            final File f = new File(d, "instance.properties");
            File tmp = new File(d, "instance.properties.tmp");
            String body = "port=" + ss.getLocalPort() + "\ntoken=" + jeton + "\npid=" + ProcessHandle.current().pid() + "\n";
            Files.write(tmp.toPath(), new byte[0]);
            tmp.setReadable(false, false); tmp.setReadable(true, true);
            tmp.setWritable(false, false); tmp.setWritable(true, true);
            Files.write(tmp.toPath(), body.getBytes(StandardCharsets.UTF_8));
            Files.move(tmp.toPath(), f.toPath(), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
            Runtime.getRuntime().addShutdownHook(new Thread(f::delete));

            Thread t = new Thread(() -> {
                while (!ss.isClosed()) {
                    try (Socket s = ss.accept()) {
                        s.setSoTimeout(5000);
                        BufferedReader br = new BufferedReader(new InputStreamReader(s.getInputStream(), StandardCharsets.UTF_8));
                        String cevap = isle(br.readLine(), jeton);
                        OutputStream os = s.getOutputStream();
                        os.write((cevap + "\n").getBytes(StandardCharsets.UTF_8));
                        os.flush();
                    } catch (Throwable e) {
                        if (ss.isClosed()) return;
                    }
                }
            }, "uyap-tek-ornek");
            t.setDaemon(true);
            t.start();
            System.out.println("[UYAP] tek-ornek servisi hazir (port " + ss.getLocalPort() + ")");
        } catch (Throwable t) {
            System.out.println("[UYAP] tek-ornek servisi baslatilamadi: " + t);
        }
    }

    static String isle(String satir, String jeton) {
        if (satir == null) return "ERR";
        String[] p = satir.split("\t", 3);
        if (p.length < 2 || !sabitZamanEsit(p[0], jeton)) return "ERR";
        switch (p[1]) {
            case "PING": return "OK";
            case "NEW": Baslatici.belgeAc(null); return "OK";
            case "OPEN":
                if (p.length == 3 && !p[2].isEmpty()) { Baslatici.belgeAc(p[2]); return "OK"; }
                return "ERR";
            default: return "ERR";
        }
    }

    private static boolean sabitZamanEsit(String a, String b) {
        return java.security.MessageDigest.isEqual(a.getBytes(StandardCharsets.UTF_8), b.getBytes(StandardCharsets.UTF_8));
    }
}
