package com.agy.uyapacici;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.print.PrintAttributes;
import android.print.PrintDocumentAdapter;
import android.print.PrintManager;
import android.view.View;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import com.agy.telemetry.CrashReporter;

import org.json.JSONObject;

import java.io.File;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;

public class EditorActivity extends Activity {

    public static final String EXTRA_FILE_PATH = "extra_file_path";

    private WebView editorWebView;
    private EditText etDocTitle;
    private Button btnBack;
    private Button btnSave;
    private Button btnSaveDocx;
    private Button btnExportPdf;
    private Button btnShare;
    private Button btnDesktopUyap;

    private TextView tvWordCount;
    private TextView tvSaveStatus;

    private File currentFile = null;
    private boolean isPageLoaded = false;
    private String pendingHtmlToLoad = null;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        CrashReporter.install(this);
        setContentView(R.layout.activity_editor);

        initViews();
        setupWebView();
        setupListeners();

        loadIncomingFile();
    }

    private void initViews() {
        editorWebView = findViewById(R.id.editorWebView);
        etDocTitle = findViewById(R.id.etDocTitle);
        btnBack = findViewById(R.id.btnBack);
        btnSave = findViewById(R.id.btnSave);
        btnSaveDocx = findViewById(R.id.btnSaveDocx);
        btnExportPdf = findViewById(R.id.btnExportPdf);
        btnShare = findViewById(R.id.btnShare);
        btnDesktopUyap = findViewById(R.id.btnDesktopUyap);
        tvWordCount = findViewById(R.id.tvWordCount);
        tvSaveStatus = findViewById(R.id.tvSaveStatus);
    }

    private void setupWebView() {
        WebSettings settings = editorWebView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);

        editorWebView.addJavascriptInterface(new EditorBridge(), "AndroidBridge");
        editorWebView.setWebChromeClient(new WebChromeClient());
        editorWebView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                isPageLoaded = true;
                if (pendingHtmlToLoad != null) {
                    injectHtmlContent(pendingHtmlToLoad);
                    pendingHtmlToLoad = null;
                }
            }
        });

        editorWebView.loadUrl("file:///android_asset/editor/editor.html");
    }

    private void setupListeners() {
        btnBack.setOnClickListener(v -> finish());

        // UDF Olarak Kaydet
        btnSave.setOnClickListener(v -> saveDocument(false, false));

        // DOCX (Word) Olarak Kaydet
        btnSaveDocx.setOnClickListener(v -> saveDocument(true, false));

        // PDF Dışa Aktar
        btnExportPdf.setOnClickListener(v -> exportToPdf());

        // Dosya Paylaş
        btnShare.setOnClickListener(v -> shareCurrentDocument());

        // Masaüstü X11 UYAP
        btnDesktopUyap.setOnClickListener(v -> {
            saveDocument(false, true);
        });
    }

    private void loadIncomingFile() {
        String path = getIntent().getStringExtra(EXTRA_FILE_PATH);
        if (path != null && !path.trim().isEmpty()) {
            currentFile = new File(path);
            if (currentFile.exists()) {
                etDocTitle.setText(currentFile.getName());
                tvSaveStatus.setText("Belge okunuyor...");

                new Thread(() -> {
                    try {
                        String html;
                        String lower = currentFile.getName().toLowerCase();
                        if (lower.endsWith(".docx")) {
                            html = DocxEngine.readDocxToHtml(currentFile);
                        } else {
                            html = UdfEngine.readUdfToHtml(currentFile);
                        }

                        final String finalHtml = html;
                        runOnUiThread(() -> {
                            if (isPageLoaded) {
                                injectHtmlContent(finalHtml);
                            } else {
                                pendingHtmlToLoad = finalHtml;
                            }
                            tvSaveStatus.setText("✓ Yüklendi");
                        });
                    } catch (Exception e) {
                        runOnUiThread(() -> {
                            Toast.makeText(EditorActivity.this, "Belge okuma hatası: " + e.getMessage(), Toast.LENGTH_LONG).show();
                            tvSaveStatus.setText("Hata");
                        });
                    }
                }).start();
                return;
            }
        }

        // Yeni boş dilekçe
        SimpleDateFormat sdf = new SimpleDateFormat("yyyyMMdd_HHmm", Locale.getDefault());
        etDocTitle.setText("Dilekce_" + sdf.format(new Date()) + ".udf");
    }

    private void injectHtmlContent(String html) {
        String quoted = JSONObject.quote(html);
        editorWebView.evaluateJavascript("setHtmlContent(" + quoted + ");", null);
    }

    private void saveDocument(boolean isDocx, boolean andOpenInDesktop) {
        tvSaveStatus.setText("Kaydediliyor...");
        btnSave.setEnabled(false);
        btnSaveDocx.setEnabled(false);

        editorWebView.evaluateJavascript("getStructuredDocument();", rawResult -> {
            btnSave.setEnabled(true);
            btnSaveDocx.setEnabled(true);

            if (rawResult == null || rawResult.isEmpty() || "null".equals(rawResult)) {
                Toast.makeText(EditorActivity.this, "Kaydedilecek metin bulunamadı!", Toast.LENGTH_SHORT).show();
                tvSaveStatus.setText("Hata");
                return;
            }

            String cleanJson = rawResult;
            if (cleanJson.startsWith("\"") && cleanJson.endsWith("\"")) {
                try {
                    cleanJson = new org.json.JSONTokener(cleanJson).nextValue().toString();
                } catch (Exception ignored) {}
            }

            final String finalJson = cleanJson;

            new Thread(() -> {
                try {
                    String baseTitle = etDocTitle.getText().toString().trim();
                    if (baseTitle.isEmpty()) baseTitle = "Yeni_Dilekce";

                    // Uzantıyı ayarla
                    if (baseTitle.toLowerCase().endsWith(".udf") || baseTitle.toLowerCase().endsWith(".docx")) {
                        baseTitle = baseTitle.substring(0, baseTitle.lastIndexOf('.'));
                    }

                    String ext = isDocx ? ".docx" : ".udf";
                    String finalTitle = baseTitle + ext;

                    File targetDir;
                    if (currentFile != null && currentFile.getParentFile() != null) {
                        targetDir = currentFile.getParentFile();
                    } else {
                        targetDir = new File(Environment.getExternalStorageDirectory(), "Documents/UYAP_Belgelerim");
                        targetDir.mkdirs();
                    }

                    File targetFile = new File(targetDir, finalTitle);

                    if (isDocx) {
                        DocxEngine.saveStructuredToDocx(finalJson, targetFile);
                    } else {
                        UdfEngine.saveStructuredToUdf(finalJson, targetFile);
                    }

                    currentFile = targetFile;

                    runOnUiThread(() -> {
                        etDocTitle.setText(targetFile.getName());
                        String time = new SimpleDateFormat("HH:mm", Locale.getDefault()).format(new Date());
                        tvSaveStatus.setText("✓ " + (isDocx ? "DOCX" : "UDF") + " Kaydedildi (" + time + ")");
                        Toast.makeText(EditorActivity.this, "✓ " + targetFile.getName() + " kaydedildi!", Toast.LENGTH_SHORT).show();

                        if (andOpenInDesktop) {
                            openInDesktopUyap(targetFile.getAbsolutePath());
                        }
                    });

                } catch (Exception e) {
                    runOnUiThread(() -> {
                        tvSaveStatus.setText("Kayıt Hatası");
                        Toast.makeText(EditorActivity.this, "Kayıt hatası: " + e.getMessage(), Toast.LENGTH_LONG).show();
                    });
                }
            }).start();
        });
    }

    private void exportToPdf() {
        try {
            PrintManager printManager = (PrintManager) getSystemService(Context.PRINT_SERVICE);
            String jobName = etDocTitle.getText().toString().replace(".udf", "").replace(".docx", "") + "_PDF";
            PrintDocumentAdapter printAdapter = editorWebView.createPrintDocumentAdapter(jobName);
            printManager.print(jobName, printAdapter, new PrintAttributes.Builder()
                    .setMediaSize(PrintAttributes.MediaSize.ISO_A4)
                    .setColorMode(PrintAttributes.COLOR_MODE_COLOR)
                    .build());
        } catch (Exception e) {
            Toast.makeText(this, "PDF aktarım hatası: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }

    private void shareCurrentDocument() {
        if (currentFile == null || !currentFile.exists()) {
            // Önce kaydet sonra paylaş
            saveDocument(false, false);
            Toast.makeText(this, "Önce belge kaydedildi. Tekrar 'Paylaş'a dokunun.", Toast.LENGTH_SHORT).show();
            return;
        }

        try {
            Intent shareIntent = new Intent(Intent.ACTION_SEND);
            shareIntent.setType("*/*");
            Uri fileUri = Uri.fromFile(currentFile);
            shareIntent.putExtra(Intent.EXTRA_STREAM, fileUri);
            shareIntent.putExtra(Intent.EXTRA_SUBJECT, currentFile.getName());
            startActivity(Intent.createChooser(shareIntent, "Dilekçeyi Paylaş"));
        } catch (Exception e) {
            Toast.makeText(this, "Paylaşım hatası: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }

    private void openInDesktopUyap(String path) {
        Toast.makeText(this, "Masaüstü Termux:X11'e aktarılıyor...", Toast.LENGTH_SHORT).show();

        try {
            Intent intent = new Intent();
            intent.setClassName("com.termux", "com.termux.app.RunCommandService");
            intent.setAction("com.termux.RUN_COMMAND");
            intent.putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/usr/bin/bash");

            List<String> args = new ArrayList<>();
            args.add("/data/data/com.termux/files/home/uyap_baslat.sh");
            args.add(path);

            intent.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", args.toArray(new String[0]));
            intent.putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home");
            intent.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);
            intent.putExtra("com.termux.RUN_COMMAND_SESSION_ACTION", "0");
            startService(intent);
        } catch (Exception ignored) {}

        try {
            Intent x11Intent = new Intent();
            x11Intent.setComponent(new ComponentName("com.termux.x11", "com.termux.x11.MainActivity"));
            x11Intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(x11Intent);
        } catch (Exception ignored) {}
    }

    private class EditorBridge {
        @JavascriptInterface
        public void onContentChanged(int wordCount, int charCount) {
            runOnUiThread(() -> {
                tvWordCount.setText(wordCount + " kelime • " + charCount + " karakter");
                tvSaveStatus.setText("● Düzenleniyor");
            });
        }
    }
}
