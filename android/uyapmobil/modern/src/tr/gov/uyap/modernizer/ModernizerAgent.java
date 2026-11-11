package tr.gov.uyap.modernizer;

import javax.swing.*;
import java.awt.*;
import java.awt.event.AWTEventListener;
import java.awt.event.HierarchyEvent;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Field;

public class ModernizerAgent {
    private static String appName = "uyap-dokuman";

    public static void premain(String agentArgs, Instrumentation inst) {
        if ("sablon".equalsIgnoreCase(agentArgs)) {
            appName = "uyap-sablon";
        } else if ("dokuman".equalsIgnoreCase(agentArgs)) {
            appName = "uyap-dokuman";
        } else {
            String cmd = System.getProperty("sun.java.command", "");
            if (cmd.contains("EDITOR_TYPE_TEMPLATE")) {
                appName = "uyap-sablon";
            } else {
                appName = "uyap-dokuman";
            }
        }

        // GNOME / X11 dock eşleşmesi için WM_CLASS'ı en başta ayarla
        fixAwtAppClassName(appName);

        ThemeManager.initDisplayEnhancements();
        ScrollBench.start();

        // PDF dışa aktarımında Times New Roman ve sistem fontlarının eksiksiz eşleşmesi için font iyileştiriciyi başlat
        PdfFontFixer.init();

        SwingUtilities.invokeLater(() -> {
            String cmd = System.getProperty("sun.java.command", "");
            if (cmd.contains("EDITOR_TYPE_TEMPLATE")) {
                appName = "uyap-sablon";
            }
            fixAwtAppClassName(appName);

            String theme = ModernizerConfig.getTheme();
            if (!"system".equalsIgnoreCase(theme)) {
                ThemeManager.applyTheme(theme);
            }

            PdfFontFixer.init();

            Toolkit.getDefaultToolkit().addAWTEventListener(new AWTEventListener() {
                @Override
                public void eventDispatched(AWTEvent event) {
                    if (event instanceof HierarchyEvent) {
                        HierarchyEvent he = (HierarchyEvent) event;
                        if ((he.getChangeFlags() & HierarchyEvent.SHOWING_CHANGED) != 0 && he.getComponent().isShowing()) {
                            scanComponent(he.getComponent());
                        }
                    }
                }
            }, AWTEvent.HIERARCHY_EVENT_MASK);
        });
    }

    public static String getAppName() {
        return appName;
    }

    public static void fixAwtAppClassName(String name) {
        try {
            Toolkit.getDefaultToolkit();
            Class<?> xtk = Class.forName("sun.awt.X11.XToolkit");
            Field f = xtk.getDeclaredField("awtAppClassName");
            f.setAccessible(true);
            f.set(null, name);
        } catch (Throwable ignored) {
        }
    }

    private static void scanComponent(Component comp) {
        if (comp instanceof JFrame) {
            JFrame frame = (JFrame) comp;
            ModernizerUI.injectMenu(frame);
            ModernizerUI.applyWindowMetadata(frame, appName);
        }
        if (comp instanceof JScrollPane) {
            SmoothScroller.hook((JScrollPane) comp);
        }
        if (comp instanceof Container) {
            Container cont = (Container) comp;
            for (Component child : cont.getComponents()) {
                scanComponent(child);
            }
        }
    }
}
