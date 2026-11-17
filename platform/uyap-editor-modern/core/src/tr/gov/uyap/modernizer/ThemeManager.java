package tr.gov.uyap.modernizer;

import javax.swing.*;
import java.awt.*;
import java.lang.reflect.Method;

public class ThemeManager {
    public static void applyTheme(String themeName) {
        try {
            if ("flat-light".equalsIgnoreCase(themeName)) {
                tryLoadLaf("com.formdev.flatlaf.FlatLightLaf");
            } else if ("flat-dark".equalsIgnoreCase(themeName)) {
                tryLoadLaf("com.formdev.flatlaf.FlatDarkLaf");
            } else {
                UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName());
            }
            updateComponentTrees();
        } catch (Throwable t) {
            System.err.println("[Modernizer] Tema uygulanamadı: " + t.getMessage());
        }
    }

    private static void tryLoadLaf(String className) throws Exception {
        Class<?> lafClass = Class.forName(className);
        Method setupMethod = lafClass.getMethod("setup");
        setupMethod.invoke(null);
    }

    public static void updateComponentTrees() {
        for (Window window : Window.getWindows()) {
            SwingUtilities.updateComponentTreeUI(window);
        }
    }

    public static void initDisplayEnhancements() {
        System.setProperty("awt.useSystemAAFontSettings", "lcd");
        System.setProperty("swing.aatext", "true");
        System.setProperty("sun.java2d.renderer", "sun.java2d.marlin.MarlinRenderingEngine");
    }
}
