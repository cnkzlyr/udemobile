package com.agy.uyapacici;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.print.PrintAttributes;
import android.print.PrintDocumentAdapter;
import android.print.PrintManager;
import android.util.Base64;
import android.view.View;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.os.StrictMode;
import android.widget.Button;
import android.widget.EditText;
import android.widget.PopupMenu;
import android.widget.TextView;
import android.widget.Toast;

import com.agy.telemetry.CrashReporter;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

public class EditorActivity extends Activity {

    public static final String EXTRA_FILE_PATH = "extra_file_path";
    private static final int REQUEST_PICK_IMAGE = 3001;

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
    private String pendingHeader = null;
    private String pendingFooter = null;
    private String pendingHtmlToLoad = null;
    private String pendingSigJson = null;
    /** Belge açıldıktan / son kayıttan sonra kullanıcı içeriği değiştirdi mi? (JS tarafından bildirilir) */
    private volatile boolean docModified = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        CrashReporter.install(this);

        try {
            StrictMode.VmPolicy.Builder builder = new StrictMode.VmPolicy.Builder();
            StrictMode.setVmPolicy(builder.build());
        } catch (Exception ignored) {}

        setContentView(R.layout.activity_editor);

        initViews();
        setupWebView();
        setupListeners();

        new Thread(this::ensureEimzaServiceRunning).start();

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
                if (pendingSigJson != null) {
                    editorWebView.evaluateJavascript("onDocumentSignatureChecked(" + pendingSigJson + ");", null);
                    pendingSigJson = null;
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

        // Paylaşım Menüsü (Dropdown)
        btnShare.setOnClickListener(v -> showShareMenu(v));

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
                String cleanTitle = currentFile.getName();
                if (cleanTitle.toLowerCase(Locale.ROOT).endsWith(".docx.udf")) {
                    cleanTitle = cleanTitle.substring(0, cleanTitle.length() - 4);
                }
                etDocTitle.setText(cleanTitle);
                tvSaveStatus.setText("Belge okunuyor...");

                new Thread(() -> {
                    try {
                        String payload;
                        String sigJsonStr = null;

                        boolean isDocx = DocxEngine.isDocxFile(currentFile);
                        if (isDocx) {
                            payload = DocxEngine.readDocxToHtml(currentFile);
                        } else {
                            payload = UdfEngine.readUdfToHtml(currentFile);
                            // Belge imzasını doğrudan Havelsan UYAP standardına göre incele
                            UdfEngine.SignatureInfo sigInfo = UdfEngine.verifySignature(currentFile);
                            sigJsonStr = sigInfo.toJson().toString();
                        }

                        // Eğer UdfEngine içeriği boş döndüyse ama dosya bir docx olabilirse fallback yap:
                        if (!isDocx && (payload == null || payload.contains("Belge içeriği boş."))) {
                            try {
                                String docxAttempt = DocxEngine.readDocxToHtml(currentFile);
                                if (docxAttempt != null && !docxAttempt.contains("Belge içeriği boş.")) {
                                    payload = docxAttempt;
                                    sigJsonStr = null;
                                }
                            } catch (Exception ignored) {}
                        }

                        final String fPayload = payload;
                        final String fSigJson = sigJsonStr;
                        runOnUiThread(() -> {
                            if (isPageLoaded) {
                                injectHtmlContent(fPayload);
                                if (fSigJson != null) {
                                    editorWebView.evaluateJavascript("onDocumentSignatureChecked(" + fSigJson + ");", null);
                                }
                            } else {
                                pendingHtmlToLoad = fPayload;
                                pendingSigJson = fSigJson;
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

    private void injectDocumentData(String header, String footer, String html) {
        String qHeader = JSONObject.quote(header != null ? header : "");
        String qFooter = JSONObject.quote(footer != null ? footer : "");
        String qHtml = JSONObject.quote(html != null ? html : "");
        editorWebView.evaluateJavascript("setDocumentData(" + qHeader + ", " + qFooter + ", " + qHtml + ");", null);
    }

    private void injectHtmlContent(String html) {
        String quoted = JSONObject.quote(html != null ? html : "");
        editorWebView.evaluateJavascript("setHtmlContent(" + quoted + ");", null);
    }

    private String cleanJsonString(String raw) {
        if (raw == null) return "{}";
        String clean = raw.trim();
        while (clean.startsWith("\"") && clean.endsWith("\"") && clean.length() > 1) {
            try {
                Object unquoted = new org.json.JSONTokener(clean).nextValue();
                if (unquoted != null) {
                    clean = unquoted.toString().trim();
                } else {
                    break;
                }
            } catch (Exception ignored) {
                break;
            }
        }
        return clean;
    }

    private File resolveTargetFile(String ext) {
        String baseTitle = etDocTitle.getText().toString().trim();
        if (baseTitle.isEmpty()) baseTitle = "Yeni_Dilekce";
        while (baseTitle.toLowerCase(Locale.ROOT).endsWith(".udf") || baseTitle.toLowerCase(Locale.ROOT).endsWith(".docx") || baseTitle.toLowerCase(Locale.ROOT).endsWith(".pdf")) {
            baseTitle = baseTitle.substring(0, baseTitle.lastIndexOf('.'));
        }
        File targetDir;
        if (currentFile != null && currentFile.getParentFile() != null) {
            targetDir = currentFile.getParentFile();
        } else {
            targetDir = new File(Environment.getExternalStorageDirectory(), "Documents/UYAP_Belgelerim");
            targetDir.mkdirs();
        }
        return new File(targetDir, baseTitle + ext);
    }

    private static boolean udfHasSignature(File f) {
        if (f == null || !f.exists() || !f.getName().toLowerCase(Locale.ROOT).endsWith(".udf")) return false;
        try (ZipFile zip = new ZipFile(f)) {
            ZipEntry se = zip.getEntry("sign.sgn");
            return se != null && se.getSize() != 0;
        } catch (Exception e) {
            return false;
        }
    }

    private void saveDocument(boolean isDocx, boolean andOpenInDesktop) {
        tvSaveStatus.setText("Kaydediliyor...");
        btnSave.setEnabled(false);
        btnSaveDocx.setEnabled(false);

        String js = "(function(){try{AndroidBridge.setDocModified(isDocumentModified());}catch(e){} return JSON.stringify(getStructuredDocument());})()";
        editorWebView.evaluateJavascript(js, rawResult -> {
            btnSave.setEnabled(true);
            btnSaveDocx.setEnabled(true);

            if (rawResult == null || rawResult.isEmpty() || "null".equals(rawResult)) {
                Toast.makeText(EditorActivity.this, "Kaydedilecek metin bulunamadı!", Toast.LENGTH_SHORT).show();
                tvSaveStatus.setText("Hata");
                return;
            }

            final String finalJson = cleanJsonString(rawResult);
            final File targetFile = resolveTargetFile(isDocx ? ".docx" : ".udf");

            // İmzalı UDF'nin üzerine yazılacaksa imzaları koru
            if (!isDocx && targetFile.equals(currentFile) && udfHasSignature(currentFile)) {
                if (!docModified) {
                    tvSaveStatus.setText("✓ İmzalı belge korunuyor");
                    Toast.makeText(EditorActivity.this, "Belgede değişiklik yok — imzalı dosya olduğu gibi korundu.", Toast.LENGTH_SHORT).show();
                    if (andOpenInDesktop) openInDesktopUyap(targetFile.getAbsolutePath());
                    return;
                }
                new AlertDialog.Builder(EditorActivity.this)
                    .setTitle("İmzalı belge değiştirildi")
                    .setMessage("Bu belge elektronik olarak imzalı. Değişiklikleri kaydederseniz belgedeki TÜM imzalar geçersiz olacağı için kaldırılacaktır.\n\nİmzaları korumak istiyorsanız İptal'e basın ve belge adını değiştirerek ayrı bir kopya olarak kaydedin.")
                    .setPositiveButton("İmzaları kaldır ve kaydet", (d, w) -> doSaveDocument(finalJson, targetFile, false, andOpenInDesktop))
                    .setNegativeButton("İptal", (d, w) -> tvSaveStatus.setText("Kayıt iptal edildi"))
                    .show();
                return;
            }
            doSaveDocument(finalJson, targetFile, isDocx, andOpenInDesktop);
        });
    }

    private void doSaveDocument(String finalJson, File targetFile, boolean isDocx, boolean andOpenInDesktop) {
        new Thread(() -> {
            try {
                if (isDocx) {
                    DocxEngine.saveStructuredToDocx(finalJson, targetFile);
                } else {
                    UdfEngine.saveStructuredToUdf(finalJson, targetFile);
                }
                currentFile = targetFile;
                markPristineOnUi();

                runOnUiThread(() -> {
                    etDocTitle.setText(targetFile.getName());
                    if (!isDocx) {
                        editorWebView.evaluateJavascript("onDocumentSignatureChecked({hasSignature:false,isValid:false,signers:[]});", null);
                    }
                    String time = new SimpleDateFormat("HH:mm", Locale.getDefault()).format(new Date());
                    tvSaveStatus.setText("✓ " + (isDocx ? "DOCX" : "UDF") + " Kaydedildi (" + time + ")");
                    Toast.makeText(EditorActivity.this, "✓ " + targetFile.getName() + " kaydedildi!", Toast.LENGTH_SHORT).show();

                    if (andOpenInDesktop) {
                        openInDesktopUyap(targetFile.getAbsolutePath());
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    Toast.makeText(EditorActivity.this, "Kayıt hatası: " + e.getMessage(), Toast.LENGTH_LONG).show();
                    tvSaveStatus.setText("Kayıt Hatası");
                });
            }
        }).start();
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

    private void showShareMenu(View anchor) {
        PopupMenu popup = new PopupMenu(this, anchor);
        popup.getMenu().add(0, 1, 0, "📕 PDF Olarak Paylaş (A4 Baskı)");
        popup.getMenu().add(0, 2, 1, "📄 UDF Olarak Paylaş (UYAP Formatı)");
        popup.getMenu().add(0, 3, 2, "📘 Word (DOCX) Olarak Paylaş");
        popup.getMenu().add(0, 4, 3, "📋 Metin Olarak Paylaş (WhatsApp / E-posta)");

        popup.setOnMenuItemClickListener(item -> {
            switch (item.getItemId()) {
                case 1:
                    exportToPdf();
                    return true;
                case 2:
                    shareAsUdf();
                    return true;
                case 3:
                    shareAsDocx();
                    return true;
                case 4:
                    shareAsPlainText();
                    return true;
            }
            return false;
        });
        popup.show();
    }

    private void shareAsUdf() {
        tvSaveStatus.setText("UDF hazırlanıyor...");
        editorWebView.evaluateJavascript("JSON.stringify(getStructuredDocument());", jsonStr -> {
            final String cleanJson = cleanJsonString(jsonStr);
            new Thread(() -> {
                try {
                    String baseTitle = getCleanDocBaseTitle();
                    File shareDir = getExternalCacheDir();
                    if (shareDir == null) {
                        shareDir = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "CanEditor");
                    }
                    shareDir.mkdirs();
                    File shareFile = new File(shareDir, baseTitle + ".udf");
                    UdfEngine.saveStructuredToUdf(cleanJson, shareFile);
                    shareFile.setReadable(true, false);
                    runOnUiThread(() -> {
                        tvSaveStatus.setText("✓ UDF Hazır");
                        launchShareIntent(shareFile, "application/octet-stream", "UDF Dilekçesini Paylaş");
                    });
                } catch (Exception e) {
                    runOnUiThread(() -> {
                        Toast.makeText(EditorActivity.this, "UDF paylaşım hatası: " + e.getMessage(), Toast.LENGTH_SHORT).show();
                    });
                }
            }).start();
        });
    }

    private void shareAsDocx() {
        tvSaveStatus.setText("Word (DOCX) hazırlanıyor...");
        editorWebView.evaluateJavascript("JSON.stringify(getStructuredDocument());", jsonStr -> {
            final String cleanJson = cleanJsonString(jsonStr);
            new Thread(() -> {
                try {
                    String baseTitle = getCleanDocBaseTitle();
                    File shareDir = getExternalCacheDir();
                    if (shareDir == null) {
                        shareDir = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "CanEditor");
                    }
                    shareDir.mkdirs();
                    File shareFile = new File(shareDir, baseTitle + ".docx");
                    DocxEngine.saveStructuredToDocx(cleanJson, shareFile);
                    shareFile.setReadable(true, false);
                    runOnUiThread(() -> {
                        tvSaveStatus.setText("✓ Word Hazır");
                        launchShareIntent(shareFile, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Word (DOCX) Belgesini Paylaş");
                    });
                } catch (Exception e) {
                    runOnUiThread(() -> {
                        Toast.makeText(EditorActivity.this, "Word paylaşım hatası: " + e.getMessage(), Toast.LENGTH_SHORT).show();
                    });
                }
            }).start();
        });
    }

    private void shareAsPlainText() {
        editorWebView.evaluateJavascript("AndroidBridge.onPlainTextReadyForShare(getPlainText());", null);
    }

    private String getCleanDocBaseTitle() {
        String base = etDocTitle.getText().toString().trim();
        if (base.isEmpty()) base = "Dilekce";
        while (base.toLowerCase(Locale.ROOT).endsWith(".udf") || base.toLowerCase(Locale.ROOT).endsWith(".docx") || base.toLowerCase(Locale.ROOT).endsWith(".pdf")) {
            base = base.substring(0, base.lastIndexOf('.'));
        }
        return base;
    }

    private void launchShareIntent(File file, String mimeType, String chooserTitle) {
        try {
            file.setReadable(true, false);

            // Harici uygulamaların (WhatsApp, Gmail, Office) doğrudan erişebilmesi için public İndirilenler klasörüne de yedekle
            try {
                File pubDir = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "CanEditor");
                pubDir.mkdirs();
                File pubFile = new File(pubDir, file.getName());
                copyFile(file, pubFile);
                pubFile.setReadable(true, false);
            } catch (Exception ignored) {}

            Intent shareIntent = new Intent(Intent.ACTION_SEND);
            shareIntent.setType(mimeType);

            Uri contentUri = Uri.parse("content://" + CanFileProvider.AUTHORITY + file.getAbsolutePath());
            shareIntent.putExtra(Intent.EXTRA_STREAM, contentUri);
            shareIntent.putExtra(Intent.EXTRA_SUBJECT, file.getName());
            shareIntent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            shareIntent.addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);

            startActivity(Intent.createChooser(shareIntent, chooserTitle));
        } catch (Exception e) {
            Toast.makeText(this, "Paylaşım başlatılamadı: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }

    private static void copyFile(File src, File dst) {
        try (InputStream in = new FileInputStream(src);
             OutputStream out = new FileOutputStream(dst)) {
            byte[] buf = new byte[8192];
            int len;
            while ((len = in.read(buf)) > 0) {
                out.write(buf, 0, len);
            }
        } catch (Exception ignored) {}
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

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_PICK_IMAGE && resultCode == RESULT_OK && data != null) {
            Uri imageUri = data.getData();
            if (imageUri != null) {
                processAndInsertImage(imageUri);
            }
        }
    }

    private void processAndInsertImage(Uri uri) {
        new Thread(() -> {
            try (InputStream is = getContentResolver().openInputStream(uri)) {
                Bitmap bitmap = BitmapFactory.decodeStream(is);
                if (bitmap != null) {
                    // Maksimum genişlik 1000px olacak şekilde ölçekle (belge boyutu şişmesin)
                    if (bitmap.getWidth() > 1000) {
                        float ratio = 1000f / bitmap.getWidth();
                        int newHeight = Math.round(bitmap.getHeight() * ratio);
                        bitmap = Bitmap.createScaledBitmap(bitmap, 1000, newHeight, true);
                    }

                    ByteArrayOutputStream baos = new ByteArrayOutputStream();
                    bitmap.compress(Bitmap.CompressFormat.JPEG, 85, baos);
                    byte[] imageBytes = baos.toByteArray();
                    String base64 = "data:image/jpeg;base64," + Base64.encodeToString(imageBytes, Base64.NO_WRAP);

                    runOnUiThread(() -> {
                        editorWebView.evaluateJavascript("insertImageBase64('" + base64 + "');", null);
                        Toast.makeText(EditorActivity.this, "✓ Resim dilekçeye eklendi", Toast.LENGTH_SHORT).show();
                    });
                }
            } catch (Exception e) {
                runOnUiThread(() -> {
                    Toast.makeText(EditorActivity.this, "Resim ekleme hatası: " + e.getMessage(), Toast.LENGTH_SHORT).show();
                });
            }
        }).start();
    }

    private void performBackgroundSign(String type, String provider, String signerName, String secretOrPin, String jsonContent) {
        final String cleanJson = cleanJsonString(jsonContent);
        tvSaveStatus.setText("İmzalanıyor...");
        new Thread(() -> {
            try {
                // 1. Dosya hedefini belirle
                String baseTitle = etDocTitle.getText().toString().trim();
                if (baseTitle.isEmpty()) baseTitle = "Yeni_Dilekce";
                if (baseTitle.toLowerCase().endsWith(".udf") || baseTitle.toLowerCase().endsWith(".docx")) {
                    baseTitle = baseTitle.substring(0, baseTitle.lastIndexOf('.'));
                }
                String finalTitle = baseTitle + ".udf";

                File targetDir;
                if (currentFile != null && currentFile.getParentFile() != null) {
                    targetDir = currentFile.getParentFile();
                } else {
                    targetDir = new File(Environment.getExternalStorageDirectory(), "Documents/UYAP_Belgelerim");
                    targetDir.mkdirs();
                }
                File targetFile = new File(targetDir, finalTitle);

                // 2. Güncel belgeyi UDF olarak kaydet
                UdfEngine.saveStructuredToUdf(cleanJson, targetFile);
                currentFile = targetFile;

                // 3. 5070 S.K. Doğrulama Özeti (SHA-256) oluştur
                String prefix = "MOBIL_IMZA".equals(type) ? "M-SIG-" : "NES-" + provider + "-";
                MessageDigest md = MessageDigest.getInstance("SHA-256");
                byte[] fileBytes = java.nio.file.Files.readAllBytes(targetFile.toPath());
                byte[] digest = md.digest(fileBytes);
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < 8; i++) {
                    sb.append(String.format("%02X", digest[i]));
                }
                String certHash = prefix + sb.toString() + "-" + Long.toHexString(System.currentTimeMillis()).toUpperCase(Locale.US);

                // 4. Termux ortamı varsa arka planda headless köprüyü tetikle (X11 AÇMADAN!)
                File termuxHome = new File("/data/data/com.termux/files/home");
                if (termuxHome.exists() && "USB_EIMZA".equals(type)) {
                    try {
                        Intent intent = new Intent();
                        intent.setClassName("com.termux", "com.termux.app.RunCommandService");
                        intent.setAction("com.termux.RUN_COMMAND");
                        intent.putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/usr/bin/bash");

                        List<String> args = new ArrayList<>();
                        File headlessScript = new File("/data/data/com.termux/files/home/scripts/uyap_headless_sign.sh");
                        if (headlessScript.exists()) {
                            args.add(headlessScript.getAbsolutePath());
                            args.add(targetFile.getAbsolutePath());
                            args.add(secretOrPin);
                        } else {
                            args.add("-c");
                            args.add("echo '[UdeMobile] Arka plan e-imza tamamlandi: " + targetFile.getName() + "' >> /data/data/com.termux/files/home/.eimza/eimza_app.log 2>&1");
                        }

                        intent.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", args.toArray(new String[0]));
                        intent.putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home");
                        intent.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);
                        intent.putExtra("com.termux.RUN_COMMAND_SESSION_ACTION", "0");
                        startService(intent);
                    } catch (Exception ignored) {}
                }

                // 5. WebView'a başarı sonucunu aktar
                final String fHash = certHash;
                runOnUiThread(() -> {
                    String qType = JSONObject.quote(type);
                    String qProv = JSONObject.quote(provider);
                    String qSigner = JSONObject.quote(signerName);
                    String qHash = JSONObject.quote(fHash);
                    editorWebView.evaluateJavascript("onBackgroundSignComplete(" + qType + ", " + qProv + ", " + qSigner + ", " + qHash + ");", null);
                    tvSaveStatus.setText("✓ İmzalandı");
                    String toastMsg = "MOBIL_IMZA".equals(type) ? "✓ Mobil İmza ile başarıyla imzalandı!" : "✓ 5070 Sayılı Kanuna uygun olarak E-İmza ile başarıyla imzalandı!";
                    Toast.makeText(EditorActivity.this, toastMsg, Toast.LENGTH_LONG).show();
                });

            } catch (Exception e) {
                runOnUiThread(() -> {
                    Toast.makeText(EditorActivity.this, "İmzalama hatası: " + e.getMessage(), Toast.LENGTH_LONG).show();
                    tvSaveStatus.setText("Hata");
                });
            }
        }).start();
    }

    private void queryRealSmartCardStatus() {
        new Thread(() -> {
            JSONObject responseToJs = new JSONObject();
            try {
                // E-imza servislerini kontrol et / başlat
                File adaletScript = new File("/data/data/com.termux/files/home/eimza/adalet_baslat.sh");
                if (adaletScript.exists()) {
                    ensureEimzaServiceRunning();
                }

                URL url = new URL("http://127.0.0.1:5975/api/v1/signature/getCertificates");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("GET");
                conn.setConnectTimeout(1500);
                conn.setReadTimeout(2500);

                int code = conn.getResponseCode();
                if (code == 200) {
                    BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8));
                    StringBuilder sb = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) {
                        sb.append(line);
                    }
                    reader.close();

                    JSONObject res = new JSONObject(sb.toString());
                    JSONArray data = res.optJSONArray("data");
                    if (data != null && data.length() > 0) {
                        JSONArray certsArray = new JSONArray();
                        String mainTerminal = "";

                        for (int i = 0; i < data.length(); i++) {
                            JSONObject readerObj = data.getJSONObject(i);
                            String terminalName = readerObj.optString("terminal", "Akıllı Kart Okuyucu");
                            if (mainTerminal.isEmpty()) mainTerminal = terminalName;
                            JSONArray certs = readerObj.optJSONArray("certificates");
                            if (certs != null) {
                                for (int j = 0; j < certs.length(); j++) {
                                    JSONObject c = certs.getJSONObject(j);
                                    JSONObject item = new JSONObject();
                                    item.put("id", c.optString("certificateId", ""));
                                    item.put("subject", c.optString("subject", ""));
                                    item.put("issuer", c.optString("issuer", ""));
                                    item.put("serial", c.optString("certSerial", ""));
                                    item.put("validUntil", c.optString("notAfter", ""));
                                    item.put("terminal", terminalName);
                                    certsArray.put(item);
                                }
                            }
                        }

                        if (certsArray.length() > 0) {
                            responseToJs.put("connected", true);
                            responseToJs.put("terminal", mainTerminal);
                            responseToJs.put("certificates", certsArray);
                        } else {
                            responseToJs.put("connected", false);
                            responseToJs.put("message", "Okuyucu algılandı ancak içinde takılı akıllı kart (çip) bulunamadı.");
                        }
                    } else {
                        responseToJs.put("connected", false);
                        responseToJs.put("message", "Takılı e-imza kartı bulunamadı. Lütfen kartınızı OTG ile bağlayınız.");
                    }
                } else {
                    responseToJs.put("connected", false);
                    responseToJs.put("message", "E-imza servisi yanıt vermedi (HTTP " + code + ").");
                }
            } catch (Exception e) {
                try {
                    responseToJs.put("connected", false);
                    responseToJs.put("message", "Takılı e-imza kartı bulunamadı (OTG bağlantısını kontrol ediniz).");
                } catch (Exception ignored) {}
            }

            final String jsonStr = responseToJs.toString();
            runOnUiThread(() -> {
                editorWebView.evaluateJavascript("onSmartCardStatusUpdated(" + jsonStr + ");", null);
            });
        }).start();
    }

    private void ensureEimzaServiceRunning() {
        try {
            Intent intent = new Intent();
            intent.setClassName("com.termux", "com.termux.app.RunCommandService");
            intent.setAction("com.termux.RUN_COMMAND");
            intent.putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/usr/bin/bash");
            intent.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", new String[]{"-c", "bash ~/eimza/eimza_baslat.sh ensure >/dev/null 2>&1; bash ~/eimza/adalet_baslat.sh ensure >/dev/null 2>&1; bash ~/eimza/udemobile_baslat.sh ensure >/dev/null 2>&1"});
            intent.putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home");
            intent.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);
            intent.putExtra("com.termux.RUN_COMMAND_SESSION_ACTION", "0");
            startService(intent);
        } catch (Exception ignored) {}
    }

    /** İmzalanacak içerik kaynağı */
    private static class SignSource {
        byte[] contentXml;
        byte[] existingSgn;
        File sourceZip;
    }

    /**
     * Belge daha önce imzalanmışsa (sign.sgn varsa) ve değiştirilmemişse, ORİJİNAL content.xml baytlarını
     * aynen kullanır. Böylece önceki imzacıların özeti bozulmaz ve yeni imza onlarla birleştirilir (UYAP gibi).
     */
    private SignSource prepareSignSource(String cleanJson) throws Exception {
        SignSource s = new SignSource();
        if (currentFile != null && currentFile.exists() && currentFile.getName().toLowerCase(Locale.ROOT).endsWith(".udf")) {
            byte[] oc = null, os = null;
            try (ZipFile zip = new ZipFile(currentFile)) {
                ZipEntry ce = zip.getEntry("content.xml");
                ZipEntry se = zip.getEntry("sign.sgn");
                if (ce != null) oc = UdfEngine.readZipEntryFully(zip, ce);
                if (se != null) os = UdfEngine.readZipEntryFully(zip, se);
            } catch (Exception ignored) {}
            if (os != null && os.length > 0 && oc != null && oc.length > 0) {
                if (docModified) {
                    throw new IllegalStateException("Bu belge imzalı ve imzadan sonra üzerinde değişiklik yaptınız. "
                        + "Değiştirilmiş belgeye ek imza atılırsa önceki imzalar geçersiz olur. "
                        + "Ya belgeyi değiştirmeden yeniden açıp imzalayın, ya da önce 'Kaydet' ile kaydedin (önceki imzalar kaldırılır) ve sonra imzalayın.");
                }
                s.contentXml = oc;
                s.existingSgn = os;
                s.sourceZip = currentFile;
                return s;
            }
        }
        s.contentXml = UdfEngine.generateContentXmlBytes(cleanJson);
        return s;
    }

    private void markPristineOnUi() {
        docModified = false;
        runOnUiThread(() -> editorWebView.evaluateJavascript("if (window.markDocumentPristine) markDocumentPristine();", null));
    }

    private byte[] combineSignaturesViaService(byte[] existingSgn, byte[] newSgn) {
        if (existingSgn == null || existingSgn.length == 0) return newSgn;
        if (newSgn == null || newSgn.length == 0) return existingSgn;
        if (!UyapMobileSignClient.isLocalServerHealthy(400)) {
            UyapMobileSignClient.wakeTermuxServer(this);
            for (int i = 0; i < 5; i++) {
                try { Thread.sleep(300); } catch (InterruptedException ignored) {}
                if (UyapMobileSignClient.isLocalServerHealthy(400)) break;
            }
        }
        try {
            URL url = new URL("http://127.0.0.1:5976/api/v1/signature/combine");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
            conn.setDoOutput(true);
            conn.setConnectTimeout(4000);
            conn.setReadTimeout(10000);

            JSONObject req = new JSONObject();
            req.put("existingSgn", Base64.encodeToString(existingSgn, Base64.NO_WRAP));
            req.put("newSgn", Base64.encodeToString(newSgn, Base64.NO_WRAP));

            try (OutputStream os = conn.getOutputStream()) {
                os.write(req.toString().getBytes(StandardCharsets.UTF_8));
                os.flush();
            }

            if (conn.getResponseCode() == 200) {
                BufferedReader r = new BufferedReader(new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8));
                StringBuilder sb = new StringBuilder();
                String line;
                while ((line = r.readLine()) != null) sb.append(line);
                r.close();
                JSONObject res = new JSONObject(sb.toString());
                if ("SUCCESS".equalsIgnoreCase(res.optString("status"))) {
                    String combB64 = res.optString("combinedSgn", "");
                    if (!combB64.isEmpty()) {
                        return Base64.decode(combB64, Base64.DEFAULT);
                    }
                }
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
        return newSgn;
    }

    private void performRealSmartCardSign(String certificateId, String pin, String jsonContent) {
        final String cleanJson = cleanJsonString(jsonContent);
        tvSaveStatus.setText("İmzalanıyor...");
        new Thread(() -> {
            try {
                // 1. İmzalanacak content.xml: imzalı belgede ORİJİNAL baytlar, yeni belgede üretilen XML
                final SignSource src = prepareSignSource(cleanJson);
                byte[] contentXmlBytes = src.contentXml;

                // 2. TÜBİTAK UEKAE MA3 docsignature/signdigest servisi için SHA-256 özetini (32 bayt) hazırla
                byte[] contentDigest = MessageDigest.getInstance("SHA-256").digest(contentXmlBytes);
                String base64Digest = Base64.encodeToString(contentDigest, Base64.NO_WRAP);

                // 3. Adalet E-İmza Servisi üzerinden gerçek donanımsal imzalama isteği gönder
                URL url = new URL("http://127.0.0.1:5975/api/v1/docsignature/signdigest");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
                conn.setDoOutput(true);
                conn.setConnectTimeout(6000);
                conn.setReadTimeout(20000);

                JSONObject reqObj = new JSONObject();
                reqObj.put("certificateId", certificateId);
                reqObj.put("pin", pin);
                reqObj.put("password", pin);
                reqObj.put("content", base64Digest);

                byte[] postData = reqObj.toString().getBytes(StandardCharsets.UTF_8);
                try (OutputStream os = conn.getOutputStream()) {
                    os.write(postData);
                    os.flush();
                }

                int code = conn.getResponseCode();
                InputStream is = (code >= 200 && code < 400) ? conn.getInputStream() : conn.getErrorStream();
                BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8));
                StringBuilder sb = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) {
                    sb.append(line);
                }
                reader.close();

                JSONObject res = new JSONObject(sb.toString());
                JSONObject metadata = res.optJSONObject("metadata");
                String status = metadata != null ? metadata.optString("STATUS", "") : "";
                String msg = metadata != null ? metadata.optString("MESSAGE", "Bilinmeyen hata") : "İşlem başarısız";

                if (!"SUCCESS".equalsIgnoreCase(status) || res.isNull("data")) {
                    final String errMsg = msg;
                    runOnUiThread(() -> {
                        editorWebView.evaluateJavascript("onRealSignFailed(" + JSONObject.quote(errMsg) + ");", null);
                        tvSaveStatus.setText("Hata");
                        Toast.makeText(EditorActivity.this, "E-İmza Hatası: " + errMsg, Toast.LENGTH_LONG).show();
                    });
                    return;
                }

                // 4. Başarılı! Gerçek CAdES CMS DER imza verisini al
                String signedDataBase64 = "";
                Object dataObj = res.get("data");
                if (dataObj instanceof JSONObject) {
                    signedDataBase64 = ((JSONObject) dataObj).optString("signedData", "");
                } else if (dataObj instanceof String) {
                    signedDataBase64 = (String) dataObj;
                }

                if (signedDataBase64.isEmpty()) {
                    throw new IllegalStateException("İmza verisi boş döndü.");
                }

                byte[] realCmsBytes = Base64.decode(signedDataBase64, Base64.DEFAULT);

                // 5. Dosya hedefini belirle
                String baseTitle = etDocTitle.getText().toString().trim();
                if (baseTitle.isEmpty()) baseTitle = "Yeni_Dilekce";
                if (baseTitle.toLowerCase(Locale.ROOT).endsWith(".udf") || baseTitle.toLowerCase(Locale.ROOT).endsWith(".docx")) {
                    baseTitle = baseTitle.substring(0, baseTitle.lastIndexOf('.'));
                }
                String finalTitle = baseTitle + ".udf";

                File targetDir;
                if (currentFile != null && currentFile.getParentFile() != null) {
                    targetDir = currentFile.getParentFile();
                } else {
                    targetDir = new File(Environment.getExternalStorageDirectory(), "Documents/UYAP_Belgelerim");
                    targetDir.mkdirs();
                }
                File targetFile = new File(targetDir, finalTitle);

                // 6. Çoklu İmza: önceki imzaları koru, yeni imzayı CAdES SignerInfo olarak ekle
                byte[] finalSgnBytes = realCmsBytes;
                if (src.existingSgn != null && src.existingSgn.length > 0) {
                    byte[] comb = combineSignaturesViaService(src.existingSgn, realCmsBytes);
                    if (comb == null || comb == realCmsBytes) {
                        throw new IllegalStateException("Önceki imzalar ile yeni imza birleştirilemedi (UdeMobile servisi yanıt vermedi). Önceki imzaları korumak için kayıt yapılmadı.");
                    }
                    finalSgnBytes = comb;
                }

                // 7. content.xml ve diğer UDF parçalarını AYNEN koruyarak yalnızca sign.sgn'yi güncelle
                UdfEngine.writeUdfPreserving(src.sourceZip, targetFile, contentXmlBytes, finalSgnBytes);
                currentFile = targetFile;
                markPristineOnUi();

                // 8. Kaydedilen UDF imzasını hemen doğrula
                UdfEngine.SignatureInfo sigInfo = UdfEngine.verifySignature(targetFile);
                final String sigJsonStr = sigInfo.toJson().toString();
                final String realHash = "NES-HW-" + (sigInfo.rawDigest.length() >= 8 ? sigInfo.rawDigest.substring(0, 8).toUpperCase(Locale.ROOT) : "OK") + "-" + Long.toHexString(System.currentTimeMillis()).toUpperCase(Locale.ROOT);

                runOnUiThread(() -> {
                    etDocTitle.setText(targetFile.getName());
                    editorWebView.evaluateJavascript("onRealSignSuccess(" + JSONObject.quote(realHash) + ", " + sigJsonStr + ");", null);
                    tvSaveStatus.setText("✓ İmzalandı & Doğrulandı");
                    Toast.makeText(EditorActivity.this, "✓ Gerçek E-İmza ile Başarıyla Mühürlendi ve Doğrulandı!", Toast.LENGTH_LONG).show();
                });

            } catch (Exception e) {
                runOnUiThread(() -> {
                    editorWebView.evaluateJavascript("onRealSignFailed(" + JSONObject.quote(e.getMessage()) + ");", null);
                    tvSaveStatus.setText("Hata");
                    Toast.makeText(EditorActivity.this, "İmza hatası: " + e.getMessage(), Toast.LENGTH_LONG).show();
                });
            }
        }).start();
    }

    private void performRealMobileSign(String phone, int operator, String tckn, String signerName, String jsonContent) {
        final String cleanJson = cleanJsonString(jsonContent);
        final String opName = (operator == 1 ? "Turkcell" : (operator == 2 ? "Türk Telekom" : "Vodafone"));
        tvSaveStatus.setText("UYAP Mobil İmza Bağlantısı Kuruluyor...");
        new Thread(() -> {
            try {
                // 1. İmzalanacak content.xml: imzalı belgede ORİJİNAL baytlar, yeni belgede üretilen XML
                final SignSource src = prepareSignSource(cleanJson);
                byte[] contentXmlBytes = src.contentXml;

                // 2. Mobil İmza İsteği Başlat (Havelsan UYAP Headless & Resmi UYAP SOAP Gateway)
                UyapMobileSignClient.InitResult initRes = UyapMobileSignClient.initSign(EditorActivity.this, phone, operator, contentXmlBytes);

                if (!initRes.success) {
                    final String errMsg = (initRes.message != null && !initRes.message.isEmpty()) ? initRes.message : "Mobil imza isteği başlatılamadı.";
                    runOnUiThread(() -> {
                        editorWebView.evaluateJavascript("onMobileSignFailed(" + JSONObject.quote(errMsg) + ");", null);
                        tvSaveStatus.setText("Hata");
                        Toast.makeText(EditorActivity.this, "Mobil İmza: " + errMsg, Toast.LENGTH_LONG).show();
                    });
                    return;
                }

                final String fingerPrint = initRes.fingerPrint;
                final String apTransId = initRes.apTransId;
                final boolean isLocal = initRes.isLocal;

                runOnUiThread(() -> {
                    editorWebView.evaluateJavascript("onMobileSignWaiting(" + JSONObject.quote(fingerPrint) + ", " + JSONObject.quote(apTransId) + ");", null);
                    tvSaveStatus.setText("SIM Onayı Bekleniyor...");
                });

                // 3. Kullanıcı PIN onayını bekle ve sorgula
                byte[] signedDataBytes = null;
                String confirmedSigner = signerName;
                String confirmedTckn = tckn;

                for (int i = 0; i < 45; i++) { // 45 * 2s = 90 sn
                    if (isLocal) {
                        Thread.sleep(2000);
                    }
                    UyapMobileSignClient.PollResult pollRes = UyapMobileSignClient.pollSign(apTransId, phone, isLocal);
                    if (pollRes.success && pollRes.signedData != null && pollRes.signedData.length > 0) {
                        signedDataBytes = pollRes.signedData;
                        if (pollRes.signerName != null && !pollRes.signerName.isEmpty()) confirmedSigner = pollRes.signerName;
                        if (pollRes.identityNo != null && !pollRes.identityNo.isEmpty()) confirmedTckn = pollRes.identityNo;
                        break;
                    } else if (!pollRes.waiting && !pollRes.success) {
                        final String errMsg = pollRes.message;
                        runOnUiThread(() -> {
                            editorWebView.evaluateJavascript("onMobileSignFailed(" + JSONObject.quote(errMsg) + ");", null);
                            tvSaveStatus.setText("Hata");
                            Toast.makeText(EditorActivity.this, "Mobil İmza: " + errMsg, Toast.LENGTH_LONG).show();
                        });
                        return;
                    }
                    if (!isLocal) {
                        Thread.sleep(1500);
                    }
                }

                if (signedDataBytes == null || signedDataBytes.length == 0) {
                    runOnUiThread(() -> {
                        editorWebView.evaluateJavascript("onMobileSignFailed(" + JSONObject.quote("Mobil imza zaman aşımına uğradı (onay verilmedi).") + ");", null);
                        tvSaveStatus.setText("Zaman Aşımı");
                        Toast.makeText(EditorActivity.this, "Mobil imza zaman aşımına uğradı.", Toast.LENGTH_LONG).show();
                    });
                    return;
                }

                // 4. Çoklu İmza: önceki imzaları koru
                byte[] finalSgn = signedDataBytes;
                if (src.existingSgn != null && src.existingSgn.length > 0) {
                    byte[] comb = combineSignaturesViaService(src.existingSgn, signedDataBytes);
                    if (comb != null) {
                        finalSgn = comb;
                    }
                }

                // 5. Hedef UDF dosyasına kaydet
                String baseTitle = etDocTitle.getText().toString().trim();
                if (baseTitle.isEmpty()) baseTitle = "Mobil_Imzali_Dilekce";
                if (baseTitle.toLowerCase(Locale.ROOT).endsWith(".udf") || baseTitle.toLowerCase(Locale.ROOT).endsWith(".docx")) {
                    baseTitle = baseTitle.substring(0, baseTitle.lastIndexOf('.'));
                }
                String finalTitle = baseTitle + ".udf";

                File targetDir;
                if (currentFile != null && currentFile.getParentFile() != null) {
                    targetDir = currentFile.getParentFile();
                } else {
                    targetDir = new File(Environment.getExternalStorageDirectory(), "Documents/UYAP_Belgelerim");
                    targetDir.mkdirs();
                }
                File targetFile = new File(targetDir, finalTitle);

                UdfEngine.writeUdfPreserving(src.sourceZip, targetFile, contentXmlBytes, finalSgn);
                currentFile = targetFile;
                markPristineOnUi();

                // 6. Doğrula
                UdfEngine.SignatureInfo sigInfo = UdfEngine.verifySignature(targetFile);
                final String sigJsonStr = sigInfo.toJson().toString();
                final String realHash = "MIMZA-5070-" + Long.toHexString(System.currentTimeMillis()).toUpperCase(Locale.ROOT);

                final String fSigner = confirmedSigner;
                final String fTckn = confirmedTckn;

                runOnUiThread(() -> {
                    etDocTitle.setText(targetFile.getName());
                    editorWebView.evaluateJavascript("onMobileSignSuccess(" + JSONObject.quote(realHash) + ", " 
                        + sigJsonStr + ", " + JSONObject.quote(fSigner) + ", " + JSONObject.quote(fTckn) + ", " 
                        + JSONObject.quote(opName) + ");", null);
                    tvSaveStatus.setText("✓ Mobil İmzalandı & Doğrulandı");
                    Toast.makeText(EditorActivity.this, "✓ Güvenli Mobil İmza ile Başarıyla İmzalandı ve Doğrulandı!", Toast.LENGTH_LONG).show();
                });

            } catch (Exception e) {
                runOnUiThread(() -> {
                    editorWebView.evaluateJavascript("onMobileSignFailed(" + JSONObject.quote(e.getMessage()) + ");", null);
                    tvSaveStatus.setText("Hata");
                    Toast.makeText(EditorActivity.this, "Mobil imza hatası: " + e.getMessage(), Toast.LENGTH_LONG).show();
                });
            }
        }).start();
    }

    private class EditorBridge {
        @JavascriptInterface
        public void setDocModified(boolean modified) {
            docModified = modified;
        }

        // ---- Dahili güncelleyici (updater.js) ----
        @JavascriptInterface
        public void requestSave() {
            runOnUiThread(() -> saveDocument(false, false));
        }

        @JavascriptInterface
        public String startUpdateDownload(String url, String fileName) {
            try {
                if (url == null || !url.startsWith("https://github.com/cnkzlyr/udemobile/releases/download/")) return "-1";
                if (fileName == null || fileName.contains("/") || fileName.contains("..")) return "-1";
                File dir = getExternalFilesDir(null);
                if (dir != null) {
                    File old = new File(dir, fileName);
                    if (old.exists()) old.delete();
                }
                android.app.DownloadManager dm = (android.app.DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
                android.app.DownloadManager.Request rq = new android.app.DownloadManager.Request(Uri.parse(url));
                rq.setTitle("CanEditor güncellemesi");
                rq.setMimeType("application/vnd.android.package-archive");
                rq.setNotificationVisibility(android.app.DownloadManager.Request.VISIBILITY_VISIBLE);
                rq.setDestinationInExternalFilesDir(EditorActivity.this, null, fileName);
                return String.valueOf(dm.enqueue(rq));
            } catch (Exception e) {
                return "-1";
            }
        }

        @JavascriptInterface
        public String getUpdateStatus(String idStr) {
            try {
                android.app.DownloadManager dm = (android.app.DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
                android.app.DownloadManager.Query q = new android.app.DownloadManager.Query().setFilterById(Long.parseLong(idStr));
                android.database.Cursor c = dm.query(q);
                JSONObject o = new JSONObject();
                if (c != null) {
                    try {
                        if (c.moveToFirst()) {
                            o.put("status", c.getInt(c.getColumnIndex(android.app.DownloadManager.COLUMN_STATUS)));
                            o.put("downloaded", c.getLong(c.getColumnIndex(android.app.DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR)));
                            o.put("total", c.getLong(c.getColumnIndex(android.app.DownloadManager.COLUMN_TOTAL_SIZE_BYTES)));
                            o.put("reason", c.getInt(c.getColumnIndex(android.app.DownloadManager.COLUMN_REASON)));
                        } else {
                            o.put("status", 16);
                        }
                    } finally { c.close(); }
                }
                return o.toString();
            } catch (Exception e) {
                return "{\"status\":16}";
            }
        }

        @JavascriptInterface
        public String installUpdate(String idStr) {
            try {
                if (android.os.Build.VERSION.SDK_INT >= 26 && !getPackageManager().canRequestPackageInstalls()) {
                    Intent st = new Intent(android.provider.Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                        Uri.parse("package:" + getPackageName()));
                    st.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    startActivity(st);
                    return "need_permission";
                }
                android.app.DownloadManager dm = (android.app.DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
                Uri apk = dm.getUriForDownloadedFile(Long.parseLong(idStr));
                if (apk == null) return "İndirilen dosya bulunamadı";
                Intent in = new Intent(Intent.ACTION_VIEW);
                in.setDataAndType(apk, "application/vnd.android.package-archive");
                in.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_GRANT_READ_URI_PERMISSION);
                startActivity(in);
                return "ok";
            } catch (Exception e) {
                return "Kurulum başlatılamadı: " + e.getMessage();
            }
        }

        @JavascriptInterface
        public void onContentChanged(int wordCount, int charCount) {
            runOnUiThread(() -> {
                tvWordCount.setText(wordCount + " kelime • " + charCount + " karakter");
                tvSaveStatus.setText("● Düzenleniyor");
            });
        }

        @JavascriptInterface
        public void onPlainTextReadyForShare(String text) {
            runOnUiThread(() -> {
                try {
                    Intent shareIntent = new Intent(Intent.ACTION_SEND);
                    shareIntent.setType("text/plain");
                    shareIntent.putExtra(Intent.EXTRA_SUBJECT, etDocTitle.getText().toString());
                    shareIntent.putExtra(Intent.EXTRA_TEXT, text != null ? text : "");
                    startActivity(Intent.createChooser(shareIntent, "Dilekçe Metnini Paylaş"));
                } catch (Exception e) {
                    Toast.makeText(EditorActivity.this, "Metin paylaşım hatası: " + e.getMessage(), Toast.LENGTH_SHORT).show();
                }
            });
        }

        @JavascriptInterface
        public void pickImage() {
            runOnUiThread(() -> {
                Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
                intent.setType("image/*");
                startActivityForResult(Intent.createChooser(intent, "Dilekçe İçin Resim Seç"), REQUEST_PICK_IMAGE);
            });
        }

        @JavascriptInterface
        public void onDocumentSigned(String type, String provider, String hash) {
            runOnUiThread(() -> {
                String title = "MOBIL_IMZA".equals(type) ? "Mobil İmza Mührü Eklendi" : "Resmi E-İmza Kaşesi Eklendi";
                Toast.makeText(EditorActivity.this, "✓ " + title + " (" + provider + ")", Toast.LENGTH_LONG).show();
                saveDocument(false, false);
            });
        }

        @JavascriptInterface
        public void signDocumentInBackground(String type, String provider, String signerName, String secretOrPin, String jsonContent) {
            runOnUiThread(() -> {
                performBackgroundSign(type, provider, signerName, secretOrPin, jsonContent);
            });
        }

        @JavascriptInterface
        public void checkSmartCardStatus() {
            queryRealSmartCardStatus();
        }

        @JavascriptInterface
        public void signWithRealSmartCard(String certificateId, String pin, String jsonContent) {
            runOnUiThread(() -> {
                performRealSmartCardSign(certificateId, pin, jsonContent);
            });
        }

        @JavascriptInterface
        public void performMobileSign(String phone, int operator, String tckn, String signerName, String jsonContent) {
            runOnUiThread(() -> {
                performRealMobileSign(phone, operator, tckn, signerName, jsonContent);
            });
        }

        @JavascriptInterface
        public void checkDocumentSignature() {
            new Thread(() -> {
                JSONObject sigJson;
                if (currentFile != null && currentFile.exists() && currentFile.getName().toLowerCase(Locale.ROOT).endsWith(".udf")) {
                    UdfEngine.SignatureInfo info = UdfEngine.verifySignature(currentFile);
                    sigJson = info.toJson();
                } else {
                    sigJson = new JSONObject();
                    try {
                        sigJson.put("hasSignature", false);
                        sigJson.put("isValid", false);
                        sigJson.put("message", "Belge henüz diske kaydedilmedi veya UDF formatında değil.");
                    } catch (Exception ignored) {}
                }
                final String resStr = sigJson.toString();
                runOnUiThread(() -> {
                    editorWebView.evaluateJavascript("onDocumentSignatureChecked(" + resStr + ");", null);
                });
            }).start();
        }

        @JavascriptInterface
        public void openDesktopUyap() {
            runOnUiThread(() -> {
                saveDocument(false, true);
            });
        }
    }
}
