package com.agy.telemetry;

import android.content.Context;
import android.os.Build;
import android.util.Log;
import java.io.File;
import java.io.FileWriter;
import java.io.OutputStream;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class CrashReporter {
    private static final String TAG = "AgyCrashReporter";
    private static final String SERVER_URL = "http://127.0.0.1:8765/api/crash";

    public static void install(final Context context) {
        final Thread.UncaughtExceptionHandler defaultHandler = Thread.getDefaultUncaughtExceptionHandler();

        Thread.setDefaultUncaughtExceptionHandler(new Thread.UncaughtExceptionHandler() {
            @Override
            public void uncaughtException(Thread thread, Throwable throwable) {
                try {
                    StringWriter sw = new StringWriter();
                    throwable.printStackTrace(new PrintWriter(sw));
                    String stackTrace = sw.toString();
                    String errorType = throwable.getClass().getName();
                    String errorMessage = throwable.getMessage() != null ? throwable.getMessage() : "Unknown error";
                    String packageName = context.getPackageName();

                    Log.e(TAG, "CRASH DETECTED: " + errorType + " - " + errorMessage);
                    Log.e(TAG, stackTrace);

                    // 1. Write to /sdcard/Download for local access
                    try {
                        File crashFile = new File("/sdcard/Download/" + packageName + "_crash.log");
                        FileWriter writer = new FileWriter(crashFile, false);
                        writer.write("Package: " + packageName + "\n");
                        writer.write("Error: " + errorType + ": " + errorMessage + "\n");
                        writer.write("Device: " + Build.MANUFACTURER + " " + Build.MODEL + " (Android " + Build.VERSION.RELEASE + ")\n");
                        writer.write("Timestamp: " + System.currentTimeMillis() + "\n");
                        writer.write("StackTrace:\n" + stackTrace + "\n");
                        writer.close();
                    } catch (Throwable ignored) {}

                    // 2. Transmit to Termux telemetry listener
                    sendReport(packageName, errorType, errorMessage, stackTrace);

                } catch (Throwable t) {
                    Log.e(TAG, "Exception inside CrashReporter", t);
                }

                if (defaultHandler != null) {
                    defaultHandler.uncaughtException(thread, throwable);
                }
            }
        });
    }

    public static void reportCustom(final String packageName, final String errorType, final String message, final String stackTrace) {
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    File crashFile = new File("/sdcard/Download/" + packageName + "_crash.log");
                    FileWriter writer = new FileWriter(crashFile, false);
                    writer.write("Package: " + packageName + "\n");
                    writer.write("Type: " + errorType + "\n");
                    writer.write("Message: " + message + "\n");
                    writer.write("StackTrace:\n" + stackTrace + "\n");
                    writer.close();
                } catch (Throwable ignored) {}

                sendReport(packageName, errorType, message, stackTrace);
            }
        }).start();
    }

    private static void sendReport(String packageName, String errorType, String message, String stackTrace) {
        try {
            String json = "{"
                + "\"package\":\"" + escapeJson(packageName) + "\","
                + "\"error_type\":\"" + escapeJson(errorType) + "\","
                + "\"message\":\"" + escapeJson(message) + "\","
                + "\"stack_trace\":\"" + escapeJson(stackTrace) + "\","
                + "\"device\":\"" + escapeJson(Build.MANUFACTURER + " " + Build.MODEL) + "\","
                + "\"android_version\":\"" + escapeJson(Build.VERSION.RELEASE) + "\","
                + "\"timestamp\":" + System.currentTimeMillis()
                + "}";

            URL url = new URL(SERVER_URL);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
            conn.setConnectTimeout(2000);
            conn.setReadTimeout(2000);
            conn.setDoOutput(true);
            byte[] bytes = json.getBytes(StandardCharsets.UTF_8);
            OutputStream os = conn.getOutputStream();
            os.write(bytes);
            os.flush();
            os.close();
            conn.getResponseCode();
            conn.disconnect();
        } catch (Throwable ignored) {}
    }

    private static String escapeJson(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\b", "\\b")
                .replace("\f", "\\f")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
