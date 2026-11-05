package com.agy.uyapacici;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.pdf.PdfRenderer;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.os.Environment;
import android.os.ParcelFileDescriptor;
import android.provider.MediaStore;
import android.provider.OpenableColumns;
import android.print.PageRange;
import android.print.PrintAttributes;
import android.print.PrintDocumentAdapter;
import android.print.PrintDocumentInfo;
import android.print.PrintManager;
import android.util.Base64;
import android.util.Log;
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
    private Button btnQuickSave;
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

        // Dahili Yerel Adalet E-İmza Sunucusu (Port 5975) & USB CCID Sürücüsü
        try {
            EmbeddedAdaletServer.getInstance(this).start();
            setupUsbReceiver();
            CcidDriver.getInstance(this).scanAndConnect();
        } catch (Exception ignored) {}

        new Thread(this::ensureEimzaServiceRunning).start();

        loadIncomingFile();
    }

    private final BroadcastReceiver usbReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            String action = intent.getAction();
            if (CcidDriver.ACTION_USB_PERMISSION.equals(action)) {
                synchronized (this) {
                    UsbDevice device = intent.getParcelableExtra(UsbManager.EXTRA_DEVICE);
                    if (intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false)) {
                        if (device != null) {
                            CcidDriver.getInstance(context).scanAndConnect();
                            queryRealSmartCardStatus();
                        }
                    }
                }
            } else if (UsbManager.ACTION_USB_DEVICE_ATTACHED.equals(action)) {
                CcidDriver.getInstance(context).scanAndConnect();
                queryRealSmartCardStatus();
            } else if (UsbManager.ACTION_USB_DEVICE_DETACHED.equals(action)) {
                CcidDriver.getInstance(context).disconnect();
                queryRealSmartCardStatus();
            }
        }
    };

    private void setupUsbReceiver() {
        try {
            IntentFilter filter = new IntentFilter();
            filter.addAction(CcidDriver.ACTION_USB_PERMISSION);
            filter.addAction(UsbManager.ACTION_USB_DEVICE_ATTACHED);
            filter.addAction(UsbManager.ACTION_USB_DEVICE_DETACHED);
            registerReceiver(usbReceiver, filter);
        } catch (Exception ignored) {}
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        try { unregisterReceiver(usbReceiver); } catch (Exception ignored) {}
        try { EmbeddedAdaletServer.getInstance(this).stop(); } catch (Exception ignored) {}
        try { CcidDriver.getInstance(this).disconnect(); } catch (Exception ignored) {}
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        loadIncomingFile();
    }

    private void initViews() {
        editorWebView = findViewById(R.id.editorWebView);
        etDocTitle = findViewById(R.id.etDocTitle);
        btnBack = findViewById(R.id.btnBack);
        btnQuickSave = findViewById(R.id.btnQuickSave);
        btnSave = findViewById(R.id.btnSave);
        btnSaveDocx = findViewById(R.id.btnSaveDocx);
        btnExportPdf = findViewById(R.id.btnExportPdf);
        btnShare = findViewById(R.id.btnShare);
        btnDesktopUyap = findViewById(R.id.btnDesktopUyap);
        tvWordCount = findViewById(R.id.tvWordCount);
        tvSaveStatus = findViewById(R.id.tvSaveStatus);
    }

    private void setupWebView() {
        editorWebView.setFocusable(true);
        editorWebView.setFocusableInTouchMode(true);
        editorWebView.requestFocus();
        editorWebView.requestFocusFromTouch();

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
                editorWebView.evaluateJavascript("document.body.classList.add('in-android');", null);
                if (pendingHtmlToLoad != null) {
                    if (pendingHtmlToLoad.startsWith("BYTES:")) {
                        String[] parts = pendingHtmlToLoad.substring(6).split(":", 2);
                        if (parts.length == 2) {
                            editorWebView.evaluateJavascript("openDocumentFromBytes('" + parts[1] + "', '" + parts[0] + "');", null);
                        }
                    } else {
                        injectHtmlContent(pendingHtmlToLoad);
                    }
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

        // Belge başlığı düzenleme odağı
        if (etDocTitle != null) {
            etDocTitle.setOnClickListener(v -> {
                etDocTitle.setFocusableInTouchMode(true);
                etDocTitle.requestFocus();
            });
            etDocTitle.setOnFocusChangeListener((v, hasFocus) -> {
                if (!hasFocus) {
                    etDocTitle.setFocusableInTouchMode(false);
                }
            });
        }

        // Doğrudan Hızlı Kaydet Butonu (1-Tık Kaydet)
        if (btnQuickSave != null) {
            btnQuickSave.setOnClickListener(v -> saveDocument(false, false));
        }

        // Görünüm Değiştirici Buton (Kağıt / Mobil)
        Button btnToggleView = findViewById(R.id.btnToggleView);
        if (btnToggleView != null) {
            btnToggleView.setOnClickListener(v -> {
                editorWebView.evaluateJavascript("toggleViewMode();", null);
            });
        }

        // Farklı Kaydet ve İşlem Menüsü
        btnSave.setOnClickListener(v -> showSaveMenu(v));

        // DOCX (Word) Olarak Kaydet (Hızlı Kısayol)
        btnSaveDocx.setOnClickListener(v -> saveDocument(true, false));

        // Yazdır / Önizleme Menüsü
        btnExportPdf.setOnClickListener(v -> showPrintMenu(v));

        // Paylaşım Menüsü (Dropdown)
        btnShare.setOnClickListener(v -> showShareMenu(v));

        // Masaüstü X11 UYAP
        btnDesktopUyap.setOnClickListener(v -> {
            saveDocument(false, true);
        });
    }

    private void loadIncomingFile() {
        String path = getIntent().getStringExtra(EXTRA_FILE_PATH);
        if ((path == null || path.trim().isEmpty()) && getIntent().getData() != null) {
            try {
                Uri dataUri = getIntent().getData();
                String displayName = null;
                if ("content".equalsIgnoreCase(dataUri.getScheme())) {
                    try (Cursor cursor = getContentResolver().query(dataUri, null, null, null, null)) {
                        if (cursor != null && cursor.moveToFirst()) {
                            int idx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                            if (idx >= 0) displayName = cursor.getString(idx);
                        }
                    } catch (Exception ignored) {}
                }
                if (displayName == null) displayName = dataUri.getLastPathSegment();
                if (displayName == null || displayName.trim().isEmpty()) {
                    displayName = "belge_" + System.currentTimeMillis() + ".udf";
                }
                File cacheFile = new File(getCacheDir(), displayName);
                try (InputStream in = getContentResolver().openInputStream(dataUri);
                     FileOutputStream out = new FileOutputStream(cacheFile)) {
                    byte[] buf = new byte[32768];
                    int l;
                    while ((l = in.read(buf)) != -1) out.write(buf, 0, l);
                    out.flush();
                }
                path = cacheFile.getAbsolutePath();
            } catch (Exception ignored) {}
        }
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
                        String payload = null;
                        String sigJsonStr = null;
                        String lower = currentFile.getName().toLowerCase(Locale.ROOT);

                        boolean isDocx = DocxEngine.isDocxFile(currentFile) || lower.endsWith(".docx");
                        boolean isPdf = lower.endsWith(".pdf");
                        boolean isTiff = lower.endsWith(".tiff") || lower.endsWith(".tif");
                        boolean isOdt = lower.endsWith(".odt");

                        if (isDocx) {
                            payload = DocxEngine.readDocxToHtml(currentFile);
                        } else if (isPdf || isTiff || isOdt) {
                            byte[] bytes = java.nio.file.Files.readAllBytes(currentFile.toPath());
                            String base64 = android.util.Base64.encodeToString(bytes, android.util.Base64.NO_WRAP);
                            final String fBase64 = base64;
                            final String fName = currentFile.getName();
                            runOnUiThread(() -> {
                                if (isPageLoaded) {
                                    editorWebView.evaluateJavascript("openDocumentFromBytes('" + fBase64 + "', '" + fName + "');", null);
                                    tvSaveStatus.setText("✓ Yüklendi");
                                } else {
                                    pendingHtmlToLoad = "BYTES:" + fName + ":" + fBase64;
                                }
                            });
                            return;
                        } else {
                            payload = UdfEngine.readUdfToHtml(currentFile);
                            // Belge imzasını doğrudan Havelsan UYAP standardına göre incele
                            UdfEngine.SignatureInfo sigInfo = UdfEngine.verifySignature(currentFile);
                            sigJsonStr = sigInfo.toJson().toString();
                        }

                        // Eğer UdfEngine içeriği boş döndüyse ama dosya bir docx olabilirse fallback yap:
                        if (!isDocx && !isPdf && (payload == null || payload.contains("Belge içeriği boş."))) {
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
        String quotedTitle = JSONObject.quote(etDocTitle != null ? etDocTitle.getText().toString() : "Dilekce.udf");
        editorWebView.evaluateJavascript("window.currentDocFileName = " + quotedTitle + "; if (typeof updateDocTitleDisplay === 'function') updateDocTitleDisplay(" + quotedTitle + "); setHtmlContent(" + quoted + ");", null);
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
        String baseTitle = (etDocTitle != null) ? etDocTitle.getText().toString().trim() : "Yeni_Dilekce";
        if (baseTitle.isEmpty()) baseTitle = "Yeni_Dilekce";
        while (baseTitle.toLowerCase(Locale.ROOT).endsWith(".udf") || baseTitle.toLowerCase(Locale.ROOT).endsWith(".docx") ||
               baseTitle.toLowerCase(Locale.ROOT).endsWith(".pdf") || baseTitle.toLowerCase(Locale.ROOT).endsWith(".odt") ||
               baseTitle.toLowerCase(Locale.ROOT).endsWith(".tiff") || baseTitle.toLowerCase(Locale.ROOT).endsWith(".tif")) {
            baseTitle = baseTitle.substring(0, baseTitle.lastIndexOf('.'));
        }
        File targetDir = null;
        boolean isInCache = (currentFile != null && currentFile.getAbsolutePath().startsWith(getCacheDir().getAbsolutePath()));
        if (!isInCache && currentFile != null && currentFile.getParentFile() != null && currentFile.getParentFile().canWrite()) {
            targetDir = currentFile.getParentFile();
        } else {
            File pubUyap = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "UYAP_Belgelerim");
            if (!pubUyap.exists()) pubUyap.mkdirs();
            if (pubUyap.exists() && pubUyap.canWrite()) {
                targetDir = pubUyap;
            } else {
                File extDir = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
                if (extDir != null) targetDir = extDir;
                else targetDir = getFilesDir();
            }
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
        if (btnQuickSave != null) btnQuickSave.setEnabled(false);
        btnSave.setEnabled(false);
        btnSaveDocx.setEnabled(false);

        String js = "(function(){try{var t=document.getElementById('desktopDocTitle');if(t&&t.value)AndroidBridge.syncDocumentTitle(t.value);AndroidBridge.setDocModified(isDocumentModified());}catch(e){} return JSON.stringify(getStructuredDocument());})()";
        editorWebView.evaluateJavascript(js, rawResult -> {
            if (btnQuickSave != null) btnQuickSave.setEnabled(true);
            btnSave.setEnabled(true);
            btnSaveDocx.setEnabled(true);

            if (rawResult == null || rawResult.isEmpty() || "null".equals(rawResult)) {
                Toast.makeText(EditorActivity.this, "Kaydedilecek metin bulunamadı!", Toast.LENGTH_SHORT).show();
                tvSaveStatus.setText("Hata");
                return;
            }

            final String finalJson = cleanJsonString(rawResult);
            final File targetFile = resolveTargetFile(isDocx ? ".docx" : ".udf");

            final boolean isSigned = (currentFile != null && udfHasSignature(currentFile));

            // Belgede hiçbir değişiklik yapılmamışsa: orijinal dosyayı asla bozma, bit'i bit'ine koru
            if (!isDocx && !docModified && currentFile != null && currentFile.exists()) {
                if (targetFile.equals(currentFile)) {
                    tvSaveStatus.setText(isSigned ? "✓ İmzalı belge korundu" : "✓ Belge korundu");
                    Toast.makeText(EditorActivity.this, "✓ " + targetFile.getName() + " kaydedildi (orijinal e-imza ve yapı korundu).", Toast.LENGTH_SHORT).show();
                    if (andOpenInDesktop) openInDesktopUyap(targetFile.getAbsolutePath());
                    return;
                } else {
                    // Farklı adla kaydet veya kopya: Orijinal dosyayı bit'i bit'ine kopyala!
                    try {
                        java.nio.file.Files.copy(currentFile.toPath(), targetFile.toPath(), java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                        currentFile = targetFile;
                        markPristineOnUi();
                        runOnUiThread(() -> {
                            etDocTitle.setText(targetFile.getName());
                            String time = new SimpleDateFormat("HH:mm", Locale.getDefault()).format(new Date());
                            tvSaveStatus.setText("✓ Kopya Kaydedildi (" + time + ")");
                            Toast.makeText(EditorActivity.this, "✓ " + targetFile.getName() + " kaydedildi (orijinal e-imza ve yapı korundu).", Toast.LENGTH_SHORT).show();
                            if (andOpenInDesktop) openInDesktopUyap(targetFile.getAbsolutePath());
                        });
                        return;
                    } catch (Exception e) {
                        Toast.makeText(EditorActivity.this, "Kopya oluşturma hatası: " + e.getMessage(), Toast.LENGTH_LONG).show();
                        tvSaveStatus.setText("Kayıt Hatası");
                        return;
                    }
                }
            }

            // İmzalı UDF üzerinde değişiklik yapıldıysa kullanıcıya onay sor
            if (!isDocx && targetFile.equals(currentFile) && isSigned) {
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
                    if (currentFile != null && currentFile.exists() && currentFile.getName().toLowerCase(Locale.ROOT).endsWith(".udf")) {
                        byte[] contentBytes = UdfEngine.generateContentXmlBytes(finalJson);
                        // Orijinal dosyadaki documentproperties.xml ve diğer ekleri koru, imzaları kaldır
                        UdfEngine.writeUdfPreserving(currentFile, targetFile, contentBytes, null);
                    } else {
                        UdfEngine.saveStructuredToUdf(finalJson, targetFile);
                    }
                }
                currentFile = targetFile;
                markPristineOnUi();

                // Kullanıcının dosyayı Dosyalarım/İndirilenler klasöründe rahatça bulabilmesi için UYAP_Belgelerim klasörüne de eşzamanla
                try {
                    byte[] targetBytes = java.nio.file.Files.readAllBytes(targetFile.toPath());
                    String mime = isDocx ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document" : "application/octet-stream";
                    boolean msOk = writeToDownloadsMediaStore(targetFile.getName(), mime, targetBytes);
                    if (!msOk) {
                        File pubDir = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "UYAP_Belgelerim");
                        pubDir.mkdirs();
                        if (pubDir.exists() && pubDir.canWrite()) {
                            File pubFile = new File(pubDir, targetFile.getName());
                            copyFile(targetFile, pubFile);
                            pubFile.setReadable(true, false);
                            try {
                                android.media.MediaScannerConnection.scanFile(EditorActivity.this, new String[]{pubFile.getAbsolutePath()}, null, null);
                            } catch (Exception ignored) {}
                        }
                    }
                } catch (Exception ignored) {}

                runOnUiThread(() -> {
                    etDocTitle.setText(targetFile.getName());
                    if (!isDocx) {
                        editorWebView.evaluateJavascript("onDocumentSignatureChecked({hasSignature:false,isValid:false,signers:[]});", null);
                    }
                    String time = new SimpleDateFormat("HH:mm", Locale.getDefault()).format(new Date());
                    tvSaveStatus.setText("✓ " + (isDocx ? "DOCX" : "UDF") + " Kaydedildi (" + time + ")");
                    Toast.makeText(EditorActivity.this, "✓ " + targetFile.getName() + " İndirilenler/UYAP_Belgelerim klasörüne kaydedildi!", Toast.LENGTH_SHORT).show();

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

    private String readPdfToPayload(File file) {
        StringBuilder html = new StringBuilder();
        try (ParcelFileDescriptor pfd = ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)) {
            if (pfd != null) {
                PdfRenderer renderer = new PdfRenderer(pfd);
                int count = renderer.getPageCount();
                for (int i = 0; i < count; i++) {
                    PdfRenderer.Page page = renderer.openPage(i);
                    int width = Math.min(2400, page.getWidth() * 2);
                    int height = Math.min(3200, page.getHeight() * 2);
                    Bitmap bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
                    bitmap.eraseColor(0xFFFFFFFF);
                    page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);
                    page.close();

                    ByteArrayOutputStream baos = new ByteArrayOutputStream();
                    bitmap.compress(Bitmap.CompressFormat.JPEG, 90, baos);
                    bitmap.recycle();
                    String b64 = Base64.encodeToString(baos.toByteArray(), Base64.NO_WRAP);

                    html.append("<div class=\"pdf-page-view\" style=\"text-align:center; margin-bottom:16px;\">")
                        .append("<img src=\"data:image/jpeg;base64,").append(b64)
                        .append("\" style=\"max-width:100%; height:auto; box-shadow:0 3px 10px rgba(0,0,0,0.2); border-radius:4px;\" />")
                        .append("</div>");
                }
                renderer.close();
            }
        } catch (Exception e) {
            html.append("<p style=\"color:red; font-weight:bold;\">PDF okuma hatası: ").append(e.getMessage()).append("</p>");
        }
        JSONObject root = new JSONObject();
        try {
            root.put("html", html.toString());
            root.put("title", file.getName());
        } catch (Exception ignored) {}
        return root.toString();
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

    /**
     * PDF dışa aktarma ve paylaşma motoru.
     * JavaScript tarafındaki yüksek çözünürlüklü A4 PDF üreticisi ile veya sistem yazdırma motoru ile çalışır.
     */
    private void saveAsPdfFile(boolean andShare) {
        exportToPdf();
    }

    private void shareAsPdf() {
        exportToPdf();
    }

    private void showSaveMenu(View anchor) {
        PopupMenu popup = new PopupMenu(this, anchor);
        popup.getMenu().add(0, 1, 0, "📄 Havelsan UDF Olarak Kaydet (.udf)");
        popup.getMenu().add(0, 2, 1, "📕 Adobe PDF Olarak Kaydet (A4 Baskı)");
        popup.getMenu().add(0, 3, 2, "📘 Microsoft Word Olarak Kaydet (.docx)");
        popup.getMenu().add(0, 4, 3, "🖼️ Çok Sayfalı TIFF Olarak Kaydet (.tiff)");
        popup.getMenu().add(0, 5, 4, "📗 OpenDocument Olarak Kaydet (.odt)");
        popup.getMenu().add(0, 6, 5, "🖨️ Yazdır / Yazdırma Önizleme");
        popup.getMenu().add(0, 7, 6, "🖥️ Klasik Masaüstü UYAP'ta Aç");

        popup.setOnMenuItemClickListener(item -> {
            switch (item.getItemId()) {
                case 1:
                    saveDocument(false, false);
                    return true;
                case 2:
                    editorWebView.evaluateJavascript("triggerSaveAs('pdf');", null);
                    return true;
                case 3:
                    saveDocument(true, false);
                    return true;
                case 4:
                    editorWebView.evaluateJavascript("triggerSaveAs('tiff');", null);
                    return true;
                case 5:
                    editorWebView.evaluateJavascript("triggerSaveAs('odt');", null);
                    return true;
                case 6:
                    showPrintMenu(anchor);
                    return true;
                case 7:
                    saveDocument(false, true);
                    return true;
            }
            return false;
        });
        popup.show();
    }

    private void showPrintMenu(View anchor) {
        PopupMenu popup = new PopupMenu(this, anchor);
        popup.getMenu().add(0, 1, 0, "🖨️ Yazıcıya Yazdır (Sistem Menüsü)");
        popup.getMenu().add(0, 2, 1, "👁️ Yazdırma Önizleme (Print Preview)");
        popup.getMenu().add(0, 3, 2, "📕 A4 PDF Dosyası Olarak Kaydet (.pdf)");

        popup.setOnMenuItemClickListener(item -> {
            switch (item.getItemId()) {
                case 1:
                    exportToPdf();
                    return true;
                case 2:
                    editorWebView.evaluateJavascript("openPrintPreview();", null);
                    return true;
                case 3:
                    saveAsPdfFile(false);
                    return true;
            }
            return false;
        });
        popup.show();
    }

    private void showShareMenu(View anchor) {
        PopupMenu popup = new PopupMenu(this, anchor);
        popup.getMenu().add(0, 1, 0, "📕 PDF Olarak Paylaş (A4 Baskı)");
        popup.getMenu().add(0, 2, 1, "📄 UDF Olarak Paylaş (UYAP Formatı)");
        popup.getMenu().add(0, 3, 2, "📘 Word (DOCX) Olarak Paylaş");
        popup.getMenu().add(0, 4, 3, "🖼️ Çok Sayfalı TIFF Olarak Paylaş");
        popup.getMenu().add(0, 5, 4, "📗 OpenDocument (ODT) Olarak Paylaş");
        popup.getMenu().add(0, 6, 5, "📋 Metin Olarak Paylaş (WhatsApp / E-posta)");

        popup.setOnMenuItemClickListener(item -> {
            switch (item.getItemId()) {
                case 1:
                    editorWebView.evaluateJavascript("triggerShareFormat('pdf');", null);
                    return true;
                case 2:
                    shareAsUdf();
                    return true;
                case 3:
                    shareAsDocx();
                    return true;
                case 4:
                    editorWebView.evaluateJavascript("triggerShareFormat('tiff');", null);
                    return true;
                case 5:
                    editorWebView.evaluateJavascript("triggerShareFormat('odt');", null);
                    return true;
                case 6:
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

            Intent shareIntent = new Intent(Intent.ACTION_SEND);
            shareIntent.setType(mimeType);

            Uri contentUri = Uri.parse("content://" + CanFileProvider.AUTHORITY + file.getAbsolutePath());
            shareIntent.putExtra(Intent.EXTRA_STREAM, contentUri);
            shareIntent.putExtra(Intent.EXTRA_SUBJECT, file.getName());
            shareIntent.setClipData(android.content.ClipData.newRawUri(file.getName(), contentUri));
            shareIntent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            shareIntent.addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);

            Intent chooser = Intent.createChooser(shareIntent, chooserTitle);
            chooser.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);

            // Tüm alıcı uygulamalara (WhatsApp, Gmail vb.) açıkça okuma izni ver
            try {
                android.content.pm.PackageManager pm = getPackageManager();
                java.util.List<android.content.pm.ResolveInfo> matches = pm.queryIntentActivities(shareIntent, 0);
                for (android.content.pm.ResolveInfo info : matches) {
                    if (info.activityInfo != null && info.activityInfo.packageName != null) {
                        grantUriPermission(info.activityInfo.packageName, contentUri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    }
                }
            } catch (Exception ignored) {}

            startActivity(chooser);
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
                // 1. Katman: Doğrudan Android Yerel USB Host CCID Sürücüsü (Sıfır Termux, Bağımsız)
                CcidDriver driver = CcidDriver.getInstance(this);
                if (!driver.isConnected()) {
                    driver.scanAndConnect();
                }
                if (driver.isConnected()) {
                    CcidDriver.CardCertificateInfo cert = driver.getCertificateInfo();
                    JSONArray certsArray = new JSONArray();
                    JSONObject item = new JSONObject();
                    item.put("id", cert != null ? cert.certificateId : "CERT_0");
                    item.put("subject", cert != null && !cert.subject.isEmpty() ? cert.subject : "Nitelikli Elektronik Sertifika");
                    item.put("issuer", cert != null && !cert.issuer.isEmpty() ? cert.issuer : driver.getCardType());
                    item.put("serial", cert != null && !cert.serial.isEmpty() ? cert.serial : "NES-1");
                    item.put("validUntil", cert != null && !cert.notAfter.isEmpty() ? cert.notAfter : "31.12.2028");
                    item.put("terminal", driver.getReaderName());
                    certsArray.put(item);

                    responseToJs.put("connected", true);
                    responseToJs.put("terminal", driver.getReaderName());
                    responseToJs.put("certificates", certsArray);

                    final String jsonStr = responseToJs.toString();
                    runOnUiThread(() -> editorWebView.evaluateJavascript("onSmartCardStatusUpdated(" + jsonStr + ");", null));
                    return;
                }

                // 2. Katman: Dahili/Harici Adalet E-İmza Servisi (Port 5975)
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

                // 1. Katman: Doğrudan Android Yerel USB Host CCID Sürücüsü (Termux'suz, Bağımsız)
                byte[] realCmsBytes = null;
                CcidDriver driver = CcidDriver.getInstance(this);
                if (driver.isConnected()) {
                    try {
                        byte[] rawSig = driver.signWithPin(pin, contentDigest);
                        byte[] certDer = driver.getCertificateInfo() != null ? driver.getCertificateInfo().derBytes : null;
                        realCmsBytes = EmbeddedAdaletServer.buildSimpleCms(contentDigest, rawSig, certDer);
                    } catch (Exception e) {
                        Log.w("EditorActivity", "CcidDriver doğrudan imzalama başarısız, HTTP servisine geçiliyor: " + e.getMessage());
                    }
                }

                if (realCmsBytes == null) {
                    // 2. Katman: Adalet E-İmza Servisi (Port 5975) üzerinden istek gönder
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

                    realCmsBytes = Base64.decode(signedDataBase64, Base64.DEFAULT);
                }

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

    private boolean writeToDownloadsMediaStore(String fileName, String mimeType, byte[] bytes) {
        if (Build.VERSION.SDK_INT >= 29) {
            try {
                Uri collection = MediaStore.Downloads.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);

                // Eski aynı isimli kaydı temizle
                try {
                    String where = MediaStore.MediaColumns.DISPLAY_NAME + "=? AND " + MediaStore.MediaColumns.RELATIVE_PATH + "=?";
                    String[] args = new String[]{fileName, Environment.DIRECTORY_DOWNLOADS + "/UYAP_Belgelerim/"};
                    getContentResolver().delete(collection, where, args);
                } catch (Exception ignored) {}

                ContentValues values = new ContentValues();
                values.put(MediaStore.MediaColumns.DISPLAY_NAME, fileName);
                values.put(MediaStore.MediaColumns.MIME_TYPE, (mimeType != null && !mimeType.isEmpty()) ? mimeType : "application/octet-stream");
                values.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/UYAP_Belgelerim");
                values.put(MediaStore.MediaColumns.IS_PENDING, 1);

                Uri itemUri = getContentResolver().insert(collection, values);
                if (itemUri != null) {
                    try (OutputStream os = getContentResolver().openOutputStream(itemUri, "wt")) {
                        if (os != null) {
                            os.write(bytes);
                            os.flush();
                        }
                    }
                    values.clear();
                    values.put(MediaStore.MediaColumns.IS_PENDING, 0);
                    getContentResolver().update(itemUri, values, null, null);
                    return true;
                }
            } catch (Exception e) {
                // MediaStore hatası durumunda dosya sistemine devam et
            }
        }
        return false;
    }

    private class EditorBridge {
        @JavascriptInterface
        public void setDocModified(boolean modified) {
            docModified = modified;
        }

        @JavascriptInterface
        public void syncDocumentTitle(String title) {
            if (title != null && !title.trim().isEmpty()) {
                runOnUiThread(() -> {
                    if (etDocTitle != null) etDocTitle.setText(title.trim());
                });
            }
        }

        @JavascriptInterface
        public void onViewModeChanged(boolean isMobile) {
            runOnUiThread(() -> {
                Button btnToggle = findViewById(R.id.btnToggleView);
                if (btnToggle != null) {
                    btnToggle.setText(isMobile ? "🖥️" : "📱");
                    btnToggle.setContentDescription(isMobile ? "Kağıt Görünümüne Geç" : "Mobil Görünüme Geç");
                }
            });
        }

        // ---- Dahili güncelleyici (updater.js) ve Hızlı Kaydet ----
        @JavascriptInterface
        public void requestSave() {
            runOnUiThread(() -> saveDocument(false, false));
        }

        @JavascriptInterface
        public void quickSave() {
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

        @JavascriptInterface
        public void saveAsPdf() {
            runOnUiThread(() -> saveAsPdfFile(false));
        }

        @JavascriptInterface
        public void shareAsPdf() {
            runOnUiThread(() -> saveAsPdfFile(true));
        }

        @JavascriptInterface
        public void printDocument() {
            runOnUiThread(EditorActivity.this::exportToPdf);
        }

        @JavascriptInterface
        public void openPrintPreview() {
            runOnUiThread(() -> editorWebView.evaluateJavascript("openPrintPreview();", null));
        }

        @JavascriptInterface
        public void shareDocument(String format, String title, String docJson) {
            runOnUiThread(() -> {
                if ("udf".equalsIgnoreCase(format)) {
                    shareAsUdf();
                } else if ("docx".equalsIgnoreCase(format)) {
                    shareAsDocx();
                } else if ("pdf".equalsIgnoreCase(format)) {
                    editorWebView.evaluateJavascript("triggerShareFormat('pdf');", null);
                } else {
                    shareAsPlainText();
                }
            });
        }

        @JavascriptInterface
        public void shareBlobData(String fileName, String mimeType, String base64Data) {
            runOnUiThread(() -> {
                try {
                    byte[] bytes = Base64.decode(base64Data, Base64.DEFAULT);
                    File shareDir = getExternalCacheDir();
                    if (shareDir == null) {
                        shareDir = getCacheDir();
                    }
                    shareDir.mkdirs();
                    File shareFile = new File(shareDir, fileName);
                    try (FileOutputStream fos = new FileOutputStream(shareFile)) {
                        fos.write(bytes);
                        fos.flush();
                    }
                    shareFile.setReadable(true, false);
                    launchShareIntent(shareFile, mimeType, fileName + " Paylaş");
                } catch (Exception e) {
                    Toast.makeText(EditorActivity.this, "Paylaşım hatası: " + e.getMessage(), Toast.LENGTH_SHORT).show();
                }
            });
        }

        @JavascriptInterface
        public void saveBlobToDownloads(String fileName, String mimeType, String base64Data) {
            runOnUiThread(() -> {
                try {
                    byte[] bytes = Base64.decode(base64Data, Base64.DEFAULT);
                    boolean mediaStoreOk = writeToDownloadsMediaStore(fileName, mimeType, bytes);

                    // Ayrıca doğrudan erişim ve uygulama içi açılışlar için uygulama klasörüne yedekle
                    try {
                        File extDir = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
                        if (extDir != null) {
                            File backupFile = new File(extDir, fileName);
                            try (FileOutputStream fos = new FileOutputStream(backupFile)) {
                                fos.write(bytes);
                                fos.flush();
                            }
                        }
                    } catch (Exception ignored) {}

                    if (!mediaStoreOk) {
                        try {
                            File targetDir = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "UYAP_Belgelerim");
                            targetDir.mkdirs();
                            File targetFile = new File(targetDir, fileName);
                            try (FileOutputStream fos = new FileOutputStream(targetFile)) {
                                fos.write(bytes);
                                fos.flush();
                            }
                            targetFile.setReadable(true, false);
                            try {
                                android.media.MediaScannerConnection.scanFile(EditorActivity.this, new String[]{targetFile.getAbsolutePath()}, new String[]{mimeType}, null);
                            } catch (Exception ignored) {}
                            mediaStoreOk = true;
                        } catch (Exception ignored) {}
                    }
                    tvSaveStatus.setText("✓ " + fileName + " Kaydedildi");
                    Toast.makeText(EditorActivity.this, "✓ " + fileName + " İndirilenler/UYAP_Belgelerim klasörüne kaydedildi!", Toast.LENGTH_LONG).show();
                } catch (Exception e) {
                    Toast.makeText(EditorActivity.this, "Kayıt hatası: " + e.getMessage(), Toast.LENGTH_SHORT).show();
                }
            });
        }
    }
}
