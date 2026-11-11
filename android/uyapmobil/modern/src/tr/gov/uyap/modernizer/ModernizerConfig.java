package tr.gov.uyap.modernizer;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Properties;

public class ModernizerConfig {
    private static final String CONFIG_FILENAME = "modernizer.properties";
    private static final Properties props = new Properties();
    private static final List<Listener> listeners = new ArrayList<>();

    private static boolean smoothScroll = true;
    private static int targetHz = 120;
    private static double scrollStep = 70.0;
    private static double scrollDecay = 14.0;
    private static String theme = "system"; // system, flat-light, flat-dark

    public interface Listener {
        void onConfigChanged();
    }

    static {
        load();
    }

    private static File getConfigFile() {
        String home = System.getProperty("user.home");
        File dir = new File(home, ".uki");
        if (!dir.exists()) {
            dir.mkdirs();
        }
        return new File(dir, CONFIG_FILENAME);
    }

    public static synchronized void load() {
        File file = getConfigFile();
        if (file.exists()) {
            try (FileInputStream in = new FileInputStream(file)) {
                props.load(in);
                smoothScroll = Boolean.parseBoolean(props.getProperty("smoothScroll", "true"));
                targetHz = Integer.parseInt(props.getProperty("targetHz", "120"));
                scrollStep = Double.parseDouble(props.getProperty("scrollStep", "70.0"));
                scrollDecay = Double.parseDouble(props.getProperty("scrollDecay", "14.0"));
                theme = props.getProperty("theme", "system");
            } catch (Exception e) {
                System.err.println("[Modernizer] Ayarlar yüklenirken hata: " + e.getMessage());
            }
        }
    }

    public static synchronized void save() {
        File file = getConfigFile();
        props.setProperty("smoothScroll", String.valueOf(smoothScroll));
        props.setProperty("targetHz", String.valueOf(targetHz));
        props.setProperty("scrollStep", String.valueOf(scrollStep));
        props.setProperty("scrollDecay", String.valueOf(scrollDecay));
        props.setProperty("theme", theme);
        try (FileOutputStream out = new FileOutputStream(file)) {
            props.store(out, "UYAP Modernizer Configuration");
        } catch (IOException e) {
            System.err.println("[Modernizer] Ayarlar kaydedilemedi: " + e.getMessage());
        }
        notifyListeners();
    }

    public static synchronized void addListener(Listener l) {
        listeners.add(l);
    }

    private static synchronized void notifyListeners() {
        for (Listener l : listeners) {
            try {
                l.onConfigChanged();
            } catch (Throwable t) {
                t.printStackTrace();
            }
        }
    }

    public static boolean isSmoothScrollEnabled() { return smoothScroll; }
    public static void setSmoothScrollEnabled(boolean enabled) { smoothScroll = enabled; save(); }

    public static int getTargetHz() { return targetHz; }
    public static void setTargetHz(int hz) { targetHz = hz; save(); }

    public static double getScrollStep() { return scrollStep; }
    public static void setScrollStep(double step) { scrollStep = step; save(); }

    public static double getScrollDecay() { return scrollDecay; }
    public static void setScrollDecay(double decay) { scrollDecay = decay; save(); }

    public static String getTheme() { return theme; }
    public static void setTheme(String newTheme) { theme = newTheme; save(); }
}
