package tr.gov.uyap.modernizer;

import java.io.File;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * UYAP Editörü PDF Dışa Aktarım Yazı Tipi İyileştiricisi (PDF Font Fixer).
 *
 * UYAP'ın dahili iText PDF motoru (tr.com.havelsan.uyap.system.editor.b.b),
 * Linux ve modern sistemlerde standart yazı tipi dizinlerini (/usr/share/fonts,
 * /usr/local/share/fonts, ~/.local/share/fonts vb.) taramaz ve haritası boş kalır.
 * Bu durumda Times New Roman gibi belgelerdeki fontlar bulunamadığı için
 * UYAP'ın hatalı fallback mantığı sebebiyle PDF'e Helvetica olarak aktarılır.
 *
 * PdfFontFixer, arka planda asenkron çalışarak işletim sistemindeki tüm
 * standart font dizinlerini UYAP'ın FontMapper nesnesine kaydeder ve
 * font takma adlarını (aliases) eksiksiz yapılandırır.
 */
public class PdfFontFixer {

    private static volatile boolean initialized = false;

    public static void init() {
        if (initialized) {
            return;
        }
        initialized = true;

        Thread fixerThread = new Thread(() -> {
            try {
                // Kısa bir bekleme ile uygulamanın ilk pencere açılışını geciktirmemek
                Thread.sleep(300);
                fixFonts();
            } catch (Throwable t) {
                // Hata oluşursa sessizce devam et
            }
        }, "Modernizer-PdfFontFixer");

        fixerThread.setDaemon(true);
        fixerThread.setPriority(Thread.NORM_PRIORITY - 1);
        fixerThread.start();
    }

    @SuppressWarnings("unchecked")
    private static void fixFonts() {
        try {
            ClassLoader cl = Thread.currentThread().getContextClassLoader();
            if (cl == null) {
                cl = ClassLoader.getSystemClassLoader();
            }

            Class<?> bClass;
            try {
                bClass = Class.forName("tr.com.havelsan.uyap.system.editor.b.b", true, cl);
            } catch (ClassNotFoundException e) {
                return;
            }

            Object mapper = null;
            for (Method m : bClass.getDeclaredMethods()) {
                if (Modifier.isStatic(m.getModifiers()) && m.getParameterCount() == 0) {
                    String retName = m.getReturnType().getName();
                    if (retName.contains("editor.b") || retName.contains("FontMapper")) {
                        m.setAccessible(true);
                        mapper = m.invoke(null);
                        break;
                    }
                }
            }

            if (mapper == null) {
                return;
            }

            Class<?> cClass = mapper.getClass();
            Method scanDir = null;
            for (Method m : cClass.getMethods()) {
                if (m.getParameterCount() == 1 && m.getParameterTypes()[0] == String.class && m.getReturnType() == int.class) {
                    scanDir = m;
                    break;
                }
            }

            if (scanDir == null) {
                return;
            }

            // Taranacak sistem ve kullanıcı font dizinleri
            List<String> fontDirs = getFontDirectories();
            for (String dirPath : fontDirs) {
                try {
                    File dir = new File(dirPath);
                    if (dir.exists() && dir.isDirectory()) {
                        scanDir.invoke(mapper, dir.getAbsolutePath());
                    }
                } catch (Throwable ignored) {
                }
            }

            // Takma ad (alias) haritasını ve font haritasını al
            Map<String, String> aliasMap = null;
            Map<String, Object> fontMap = null;

            for (Field f : cClass.getDeclaredFields()) {
                if (Map.class.isAssignableFrom(f.getType())) {
                    f.setAccessible(true);
                    Map<?, ?> map = (Map<?, ?>) f.get(mapper);
                    if (map != null && !map.isEmpty()) {
                        Object val = map.values().iterator().next();
                        if (val instanceof String) {
                            aliasMap = (Map<String, String>) map;
                        } else {
                            fontMap = (Map<String, Object>) map;
                        }
                    }
                }
            }

            // Times New Roman için garanti takma adlar ve serbest serif yedekleri
            ensureTimesNewRomanAliases(aliasMap, fontMap);

        } catch (Throwable ignored) {
        }
    }

    private static List<String> getFontDirectories() {
        List<String> dirs = new ArrayList<>();
        String os = System.getProperty("os.name", "").toLowerCase();
        String userHome = System.getProperty("user.home", "");

        if (os.contains("win")) {
            String winDir = System.getenv("windir");
            if (winDir != null && !winDir.isEmpty()) {
                dirs.add(winDir + "\\Fonts");
            }
            String localAppData = System.getenv("LOCALAPPDATA");
            if (localAppData != null && !localAppData.isEmpty()) {
                dirs.add(localAppData + "\\Microsoft\\Windows\\Fonts");
            }
            dirs.add(userHome + "\\AppData\\Local\\Microsoft\\Windows\\Fonts");
        } else if (os.contains("mac")) {
            dirs.add("/Library/Fonts");
            dirs.add("/System/Library/Fonts");
            dirs.add(userHome + "/Library/Fonts");
        } else {
            // Linux, Unix, BSD, Android
            dirs.add("/usr/share/fonts");
            dirs.add("/usr/local/share/fonts");
            dirs.add(userHome + "/.local/share/fonts");
            dirs.add(userHome + "/.fonts");
            dirs.add("/opt/fonts");
            dirs.add("/system/fonts"); // Android
            dirs.add("/data/data/com.termux/files/usr/share/fonts"); // Termux
        }

        return dirs;
    }

    private static void ensureTimesNewRomanAliases(Map<String, String> aliasMap, Map<String, Object> fontMap) {
        if (aliasMap == null || fontMap == null) {
            return;
        }

        // Times New Roman font haritasında var mı?
        String timesTarget = null;
        if (fontMap.containsKey("Times New Roman")) {
            timesTarget = "Times New Roman";
        } else if (fontMap.containsKey("TimesNewRomanPSMT")) {
            timesTarget = "TimesNewRomanPSMT";
        } else {
            // Eğer Times New Roman dosyası yoksa, sistemdeki Serif fontları bağla (Liberation Serif vb.)
            for (String key : fontMap.keySet()) {
                if (key.equalsIgnoreCase("Liberation Serif") || key.equalsIgnoreCase("Nimbus Roman")
                        || key.equalsIgnoreCase("FreeSerif") || key.equalsIgnoreCase("Tinos")) {
                    timesTarget = key;
                    break;
                }
            }
        }

        if (timesTarget != null) {
            aliasMap.putIfAbsent("Times New Roman", timesTarget);
            aliasMap.putIfAbsent("TimesRoman", timesTarget);
            aliasMap.putIfAbsent("Times-Roman", timesTarget);
            aliasMap.putIfAbsent("Times", timesTarget);
        }
    }
}
