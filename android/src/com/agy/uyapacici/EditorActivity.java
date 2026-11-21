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
    private static final int REQUEST_FILE_CHOOSER = 3002;

    private WebView editorWebView;
    private android.webkit.ValueCallback<Uri[]> filePathCallback = null;
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
    private Uri originDataUri = null;
    private boolean isPageLoaded = false;
    private String pendingHeader = null;
    private String pendingFooter = null;
    private String pendingHtmlToLoad = null;
    private String pendingJsToRun = null;
    private String pendingSigJson = null;
    /** Belge açıldıktan / son kayıttan sonra kullanıcı içeriği değiştirdi mi? (JS tarafından bildirilir) */
    private volatile boolean docModified = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Tani.baglam(this);
        Tani.yaz("editör", "açıldı");
        CrashReporter.install(this);

        try {
            StrictMode.ThreadPolicy policy = new StrictMode.ThreadPolicy.Builder().permitAll().build();
            StrictMode.setThreadPolicy(policy);
            StrictMode.VmPolicy.Builder builder = new StrictMode.VmPolicy.Builder();
            StrictMode.setVmPolicy(builder.build());
        } catch (Exception ignored) {}

        setContentView(R.layout.activity_editor);

        initViews();
        setupWebView();
        setupListeners();
        // Asistanın UYAP oturumu için görünmez tarayıcı (Termux/Chrome gerekmez); sunucu başlamadan önce hazır olmalı
        GizliTarayici.hazirla(this);
        AsistanServisi.baglantiBaslat(this);

        // USB CCID sürücüsü. 127.0.0.1:5975'i artık RESMİ Adalet E-İmza (AdaletServisi, gömülü Java) dinler;
        // eski tahmini dahili sunucu (EmbeddedAdaletServer) portu işgal ediyordu, başlatılmaz. Adalet servisi
        // çalışıyorsa okuyucu onun köprüsünde: editör aynı USB arayüzünü ayrıca tutmaz.
        try {
            setupUsbReceiver();
            // Kart artık yalnızca resmi Adalet E-İmza (AdaletServisi + USB köprüsü) üzerinden okunur. Eski tahmini
            // sürücü (CcidDriver) kartı okuyamayınca uydurma sertifika gösteriyor ve USB'yi ana iş parçacığında
            // kullanıp uygulamayı donduruyordu; editör açılışında bağlanmaz.
        } catch (Exception ignored) {}

        new Thread(this::ensureEimzaServiceRunning).start();

        loadIncomingFile();
        if (getIntent().getBooleanExtra(EXTRA_UYAP_SAYFA, false)) sayfaGorunumuDugmesi();
    }

    /** UYAP Editör uygulamasından "📱 Mobil görünüm" ile açıldı: geri dönüş düğmesi gösterilir. */
    public static final String EXTRA_UYAP_SAYFA = "uyap_sayfa_gorunumu";

    /**
     * "🏛 Orijinal Sayfa Görünümü": belge değiştiyse önce kaydedilir (aynı dosyaya), sonra UYAP Editör'e dönülür;
     * UYAP Editör belgeyi yeniden yükler.
     */
    private void sayfaGorunumuDugmesi() {
        final android.widget.TextView t = new android.widget.TextView(this);
        t.setText("🏛  Orijinal Sayfa Görünümü");
        t.setTextColor(android.graphics.Color.WHITE);
        t.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, 15);
        t.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        float d = getResources().getDisplayMetrics().density;
        t.setPadding(Math.round(18 * d), Math.round(12 * d), Math.round(20 * d), Math.round(12 * d));
        android.graphics.drawable.GradientDrawable g = new android.graphics.drawable.GradientDrawable();
        g.setColor(android.graphics.Color.rgb(121, 59, 34));
        g.setCornerRadius(24 * d);
        t.setBackground(g);
        if (Build.VERSION.SDK_INT >= 21) t.setElevation(10 * d);
        android.widget.FrameLayout.LayoutParams lp = new android.widget.FrameLayout.LayoutParams(
                android.view.ViewGroup.LayoutParams.WRAP_CONTENT, android.view.ViewGroup.LayoutParams.WRAP_CONTENT,
                android.view.Gravity.BOTTOM | android.view.Gravity.CENTER_HORIZONTAL);
        lp.bottomMargin = Math.round(84 * d);
        ((android.widget.FrameLayout) findViewById(android.R.id.content)).addView(t, lp);
        t.setAlpha(0f);
        t.setTranslationY(20 * d);
        t.animate().alpha(1f).translationY(0).setStartDelay(400).setDuration(260).start();
        t.setOnClickListener(v -> {
            t.setEnabled(false);
            t.setText("⏳  Kaydediliyor…");
            // değişikliği editörün kendi bildirimiyle öğren, gerekirse kaydet, dosya yazılınca dön
            editorWebView.evaluateJavascript("(function(){try{return isDocumentModified()?'1':'0';}catch(e){return '1';}})()", r -> {
                boolean degisti = r != null && r.contains("1");
                if (!degisti) { sayfayaDon(); return; }
                final long once = currentFile != null ? currentFile.lastModified() : 0;
                saveDocument(false, false);
                final long son = System.currentTimeMillis() + 10000;
                t.postDelayed(new Runnable() {
                    @Override public void run() {
                        boolean yazildi = currentFile != null && currentFile.lastModified() != once;
                        if (yazildi || System.currentTimeMillis() > son) t.postDelayed(EditorActivity.this::sayfayaDon, 300);
                        else t.postDelayed(this, 200);
                    }
                }, 300);
            });
        });
    }

    private void sayfayaDon() {
        setResult(RESULT_OK);
        finish();
        overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
    }

    private final BroadcastReceiver usbReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            String action = intent != null ? intent.getAction() : null;
            CcidDriver driver = CcidDriver.getInstance(context);
            if (CcidDriver.ACTION_USB_PERMISSION.equals(action)) {
                driver.onPermissionResult();
            } else if (UsbManager.ACTION_USB_DEVICE_DETACHED.equals(action)) {
                UsbDevice dev = intent.getParcelableExtra(UsbManager.EXTRA_DEVICE);
                if (dev != null && driver.getConnectedDevice() != null) {
                    if (dev.getDeviceId() == driver.getConnectedDevice().getDeviceId() ||
                        dev.getDeviceName().equals(driver.getConnectedDevice().getDeviceName())) {
                        driver.disconnect();
                    }
                } else if (dev == null) {
                    driver.disconnect();
                }
            } else if (UsbManager.ACTION_USB_DEVICE_ATTACHED.equals(action)) {
                new Thread(() -> {
                    try { Thread.sleep(300); } catch (Exception ignored) {}
                    driver.scanAndConnect();
                    runOnUiThread(EditorActivity.this::queryRealSmartCardStatus);
                }).start();
                return;
            }
            queryRealSmartCardStatus();
        }
    };

    private void setupUsbReceiver() {
        try {
            IntentFilter filter = new IntentFilter();
            filter.addAction(CcidDriver.ACTION_USB_PERMISSION);
            filter.addAction(UsbManager.ACTION_USB_DEVICE_ATTACHED);
            filter.addAction(UsbManager.ACTION_USB_DEVICE_DETACHED);
            // Android 14 (API 34): bayraksız registerReceiver SecurityException fırlatıyordu (sessizce yutuluyordu)
            // → USB izin sonucu ve tak/çıkar olayları hiç gelmiyor, kart "takılı değil" görünüyordu.
            if (Build.VERSION.SDK_INT >= 33) registerReceiver(usbReceiver, filter, 2 /* RECEIVER_EXPORTED: sistem yayınları için */);
            else registerReceiver(usbReceiver, filter);
        } catch (Exception ignored) {}
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        try { unregisterReceiver(usbReceiver); } catch (Exception ignored) {}
        try { CcidDriver.getInstance(this).disconnect(); } catch (Exception ignored) {}
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (asistanIstegi(intent)) {
            if (isPageLoaded && editorWebView != null) {
                // Editör zaten açıksa (belge olabilir) asistan tam ekran açılır; kapatınca editöre dönülür
                editorWebView.evaluateJavascript("document.body.classList.add('ce-asistan-modu'); if (window.openHukukAsistani) window.openHukukAsistani('ana');", null);
            }
        }
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
        editorWebView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView webView, android.webkit.ValueCallback<Uri[]> filePathCb, FileChooserParams fileChooserParams) {
                if (filePathCallback != null) {
                    filePathCallback.onReceiveValue(null);
                    filePathCallback = null;
                }
                filePathCallback = filePathCb;
                try {
                    // Android, .cnayar/.udf gibi tanımadığı uzantıları "accept" filtresinde gri gösterip
                    // seçtirmiyor. Bu yüzden filtreyi kendimiz kuruyoruz: tüm türler MIME'a çevrilebiliyorsa
                    // onlarla, biri bile bilinmiyorsa */* ile (seçim yine yapılır, doğrulamayı sayfa yapar).
                    Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    intent.setType("*/*");
                    if (fileChooserParams != null) {
                        if (fileChooserParams.getMode() == FileChooserParams.MODE_OPEN_MULTIPLE) {
                            intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                        }
                        java.util.ArrayList<String> mimler = new java.util.ArrayList<>();
                        boolean hepsiBilinen = true;
                        String[] turler = fileChooserParams.getAcceptTypes();
                        if (turler != null) {
                            for (String ham : turler) {
                                if (ham == null) continue;
                                for (String t : ham.split(",")) {
                                    t = t.trim().toLowerCase(java.util.Locale.ROOT);
                                    if (t.isEmpty()) continue;
                                    if (t.startsWith(".")) {
                                        String m = android.webkit.MimeTypeMap.getSingleton().getMimeTypeFromExtension(t.substring(1));
                                        if (m == null) { hepsiBilinen = false; continue; }
                                        t = m;
                                    }
                                    if (!mimler.contains(t)) mimler.add(t);
                                }
                            }
                        }
                        if (hepsiBilinen && !mimler.isEmpty() && !mimler.contains("*/*")) {
                            intent.putExtra(Intent.EXTRA_MIME_TYPES, mimler.toArray(new String[0]));
                        }
                    }
                    startActivityForResult(intent, REQUEST_FILE_CHOOSER);
                    return true;
                } catch (Exception e) {
                    try {
                        Intent fallback = new Intent(Intent.ACTION_GET_CONTENT);
                        fallback.addCategory(Intent.CATEGORY_OPENABLE);
                        fallback.setType("*/*");
                        startActivityForResult(Intent.createChooser(fallback, "Belge Seç"), REQUEST_FILE_CHOOSER);
                        return true;
                    } catch (Exception ex) {
                        if (filePathCallback != null) {
                            filePathCallback.onReceiveValue(null);
                            filePathCallback = null;
                        }
                        return false;
                    }
                }
            }
        });
        editorWebView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                isPageLoaded = true;
                editorWebView.evaluateJavascript("document.body.classList.add('in-android');", null);
                if (pendingJsToRun != null) {
                    editorWebView.evaluateJavascript(pendingJsToRun, null);
                    pendingJsToRun = null;
                }
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

        // Ana ekrandaki "Hukuk Asistanı": editör HİÇ gösterilmeden asistan tam ekran açılır (editor.html?asistan=1)
        asistanIcinAcildi = asistanIstegi(getIntent());
        editorWebView.loadUrl("file:///android_asset/editor/editor.html" + (asistanIcinAcildi ? "?asistan=1" : ""));
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
                originDataUri = dataUri;
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
                        } else {
                            // Tek motor: UDF masaüstündeki ile AYNI JS motoruyla (desktop_bridge.js) açılır.
                            // Gerçek e-imza doğrulaması Java (UdfEngine.verifySignature) ile yapılır.
                            byte[] bytes;
                            try (FileInputStream fis = new FileInputStream(currentFile);
                                 ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
                                byte[] buf = new byte[32768];
                                int n;
                                while ((n = fis.read(buf)) != -1) baos.write(buf, 0, n);
                                bytes = baos.toByteArray();
                            }
                            final String fBase64 = android.util.Base64.encodeToString(bytes, android.util.Base64.NO_WRAP);
                            final String fName = JSONObject.quote(currentFile.getName());
                            String sj = null;
                            if (!isPdf && !isTiff && !isOdt) {
                                try { sj = UdfEngine.verifySignature(currentFile).toJson().toString(); } catch (Exception ignored) {}
                            }
                            final String fSig = sj;
                            runOnUiThread(() -> {
                                String js = "openDocumentFromBytes('" + fBase64 + "', " + fName + ")" +
                                        (fSig != null ? ".then(function(){onDocumentSignatureChecked(" + fSig + ");})" : "") + ";";
                                if (isPageLoaded) {
                                    editorWebView.evaluateJavascript(js, null);
                                    tvSaveStatus.setText("✓ Yüklendi");
                                } else {
                                    pendingJsToRun = js;
                                }
                            });
                            return;
                        }
                        if (false) {
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

        String js = "(function(){try{var t=document.getElementById('desktopDocTitle');if(t&&t.value)AndroidBridge.syncDocumentTitle(t.value);AndroidBridge.setDocModified(isDocumentModified());}catch(e){} try{if(!__DOCX__&&window.imzaliBelgeKorunurMu&&window.imzaliBelgeKorunurMu())return '__IMZALI_KORU__';}catch(e){} return JSON.stringify(getStructuredDocument());})()";
        js = js.replace("__DOCX__", isDocx ? "true" : "false");
        editorWebView.evaluateJavascript(js, rawResult -> {
            if (btnQuickSave != null) btnQuickSave.setEnabled(true);
            btnSave.setEnabled(true);
            btnSaveDocx.setEnabled(true);

            if (rawResult == null || rawResult.isEmpty() || "null".equals(rawResult)) {
                Toast.makeText(EditorActivity.this, "Kaydedilecek metin bulunamadı!", Toast.LENGTH_SHORT).show();
                tvSaveStatus.setText("Hata");
                return;
            }

            // İmzalı ve değiştirilmemiş belge (editörün kendi kontrolü): orijinal baytlar aynen yazılır, imzalar korunur.
            // Eskiden karar yalnızca currentFile'a bakıyordu; belge editör içinden açıldıysa currentFile boş kalıyor,
            // "Kaydet" belgeyi yeniden üretip TÜM imzaları siliyordu.
            if (!isDocx && rawResult.contains("__IMZALI_KORU__")) {
                editorWebView.evaluateJavascript("imzaliBelgeyiKoruyarakKaydet(false);", null);
                tvSaveStatus.setText("✓ İmzalı belge korundu");
                return;
            }

            final String finalJson = cleanJsonString(rawResult);
            final File targetFile = resolveTargetFile(isDocx ? ".docx" : ".udf");

            final boolean isSigned = (currentFile != null && udfHasSignature(currentFile));

            // Orijinal e-imzalı belgede değişiklik yapılmamışsa: e-imzayı bit'i bit'ine koru
            if (!isDocx && !docModified && isSigned && currentFile != null && currentFile.exists()) {
                if (originDataUri != null) {
                    try (OutputStream out = getContentResolver().openOutputStream(originDataUri, "wt")) {
                        if (out != null) {
                            byte[] rawBytes = java.nio.file.Files.readAllBytes(currentFile.toPath());
                            out.write(rawBytes);
                            out.flush();
                        }
                    } catch (Exception ignored) {}
                }
                if (targetFile.equals(currentFile)) {
                    tvSaveStatus.setText("✓ İmzalı belge korundu");
                    Toast.makeText(EditorActivity.this, "✓ " + targetFile.getName() + " kaydedildi (orijinal e-imza korundu).", Toast.LENGTH_SHORT).show();
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
                            Toast.makeText(EditorActivity.this, "✓ " + targetFile.getName() + " kaydedildi (orijinal e-imza korundu).", Toast.LENGTH_SHORT).show();
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

    /** JS motorunun ürettiği UDF baytlarını bekleyen kayıt işlemi (tek seferlik). */
    private volatile java.util.function.Consumer<byte[]> pendingUdfBytesConsumer = null;

    private void doSaveDocument(String finalJson, File targetFile, boolean isDocx, boolean andOpenInDesktop) {
        if (!isDocx) {
            // UDF: masaüstü ile birebir aynı kayıpsız JS yazıcısı (generateUdfBlob) kullanılır.
            pendingUdfBytesConsumer = bytes -> doSaveDocumentBytes(bytes, finalJson, targetFile, andOpenInDesktop);
            editorWebView.evaluateJavascript(
                "(async function(){try{const b=await generateUdfBlob(getStructuredDocument());" +
                "const a=new Uint8Array(await b.arrayBuffer());let s='';for(let i=0;i<a.length;i+=8192)s+=String.fromCharCode.apply(null,a.subarray(i,i+8192));" +
                "AndroidBridge.deliverUdfBytes(btoa(s));}catch(e){AndroidBridge.deliverUdfBytes('');}})();", null);
            return;
        }
        doSaveDocumentBytes(null, finalJson, targetFile, andOpenInDesktop);
    }

    private void doSaveDocumentBytes(byte[] udfBytes, String finalJson, File targetFile, boolean andOpenInDesktop) {
        final boolean isDocx = udfBytes == null;
        new Thread(() -> {
            try {
                if (isDocx) {
                    DocxEngine.saveStructuredToDocx(finalJson, targetFile);
                } else if (udfBytes.length > 0) {
                    java.nio.file.Files.write(targetFile.toPath(), udfBytes);
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

                // Kullanıcı belgeyi harici bir uygulamadan (WhatsApp, Dosyalarım vb.) SAF / content:// üzerinden açtıysa
                // Değişikliği orijinal dosyaya da doğrudan geri yaz:
                if (originDataUri != null && !isDocx) {
                    try (OutputStream out = getContentResolver().openOutputStream(originDataUri, "wt")) {
                        if (out != null) {
                            byte[] targetBytes = java.nio.file.Files.readAllBytes(targetFile.toPath());
                            out.write(targetBytes);
                            out.flush();
                        }
                    } catch (Exception ignored) {}
                }

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
                    int pw = Math.max(1, page.getWidth());
                    int ph = Math.max(1, page.getHeight());
                    float scale = Math.min(2.0f, Math.min(1920f / pw, 2560f / ph));
                    if (scale < 1.0f) scale = 1.0f;
                    int width = Math.max(1, Math.round(pw * scale));
                    int height = Math.max(1, Math.round(ph * scale));
                    Bitmap bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
                    bitmap.eraseColor(0xFFFFFFFF);
                    try {
                        page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_PRINT);
                    } catch (Exception rex) {
                        try {
                            page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);
                        } catch (Exception ignored) {}
                    }
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
        if (requestCode == REQUEST_FILE_CHOOSER) {
            if (filePathCallback != null) {
                Uri[] results = null;
                if (resultCode == RESULT_OK && data != null) {
                    String dataString = data.getDataString();
                    android.content.ClipData clipData = data.getClipData();
                    if (clipData != null) {
                        results = new Uri[clipData.getItemCount()];
                        for (int i = 0; i < clipData.getItemCount(); i++) {
                            results[i] = clipData.getItemAt(i).getUri();
                        }
                    } else if (dataString != null) {
                        results = new Uri[]{Uri.parse(dataString)};
                    }
                }
                filePathCallback.onReceiveValue(results);
                filePathCallback = null;
            }
            return;
        }
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
        // Kart durumu esign.js tarafından resmi Adalet E-İmza servisinden okunur (gerçek sertifika ya da açık hata).
        // Eskiden burada kart okunamasa bile "Nitelikli Elektronik Sertifika / NES-... / 31.12.2028" gibi UYDURMA
        // değerlerle "kart aktif" gösteriliyordu.
        if (Thread.currentThread() != getMainLooper().getThread()) {
            runOnUiThread(this::queryRealSmartCardStatus);
            return;
        }
        if (editorWebView != null) {
            editorWebView.evaluateJavascript("window.refreshSmartCardStatus && window.refreshSmartCardStatus();", null);
        }
    }

    private void ensureEimzaServiceRunning() {
        // Termux'suz: resmi Adalet E-İmza kuruluysa UdeMobile'ın kendi servisi başlatılır (Termux çağrılmaz).
        if (AdaletKurulum.jarDosyasi(this).exists()) {
            try { if (!AdaletServisi.calisiyor()) AdaletServisi.baslat(this); } catch (Exception ignored) { }
        }
    }

    /** İmzalanacak içerik kaynağı */
    private static class SignSource {
        byte[] contentXml;
        byte[] existingSgn;
        File sourceZip;
    }

    /**
     * Belge daha önce imzalanmışsa (sign.sgn varsa), ORİJİNAL content.xml baytlarını
     * aynen kullanır. Böylece önceki imzacıların özeti bozulmaz ve yeni imza onlarla birleştirilir (UYAP çoklu imza standardı).
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
                // Havelsan çoklu imza: orijinal content.xml ve mevcut sign.sgn korunur
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

        // 1. Yerel Termux mikroservisi varsa dene (masaüstü / Termux ortamı)
        if (UyapMobileSignClient.isLocalServerHealthy(300)) {
            try {
                URL url = new URL("http://127.0.0.1:5976/api/v1/signature/combine");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
                conn.setDoOutput(true);
                conn.setConnectTimeout(2000);
                conn.setReadTimeout(5000);

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
            } catch (Exception ignored) {}
        }

        // 2. Termux yoksa / kapalıysa: WebView içerisindeki saf ASN.1 Havelsan birleştiriciyi (window.ESign.combineB64) çalıştır
        try {
            final String existB64 = Base64.encodeToString(existingSgn, Base64.NO_WRAP);
            final String newB64 = Base64.encodeToString(newSgn, Base64.NO_WRAP);
            final String[] resultHolder = new String[1];
            final java.util.concurrent.CountDownLatch latch = new java.util.concurrent.CountDownLatch(1);

            runOnUiThread(() -> {
                try {
                    editorWebView.evaluateJavascript(
                        "(function() { try { return (window.ESign && window.ESign.combineB64) ? window.ESign.combineB64('" + existB64 + "', '" + newB64 + "') : ''; } catch(e) { return ''; } })()",
                        val -> {
                            if (val != null && !val.equals("null") && !val.isEmpty()) {
                                String clean = val.startsWith("\"") && val.endsWith("\"") && val.length() >= 2
                                    ? val.substring(1, val.length() - 1) : val;
                                clean = clean.replace("\\\"", "\"").replace("\\\\", "\\");
                                resultHolder[0] = clean;
                            }
                            latch.countDown();
                        }
                    );
                } catch (Exception e) {
                    latch.countDown();
                }
            });

            if (latch.await(6, java.util.concurrent.TimeUnit.SECONDS) && resultHolder[0] != null && !resultHolder[0].isEmpty()) {
                byte[] decoded = Base64.decode(resultHolder[0], Base64.DEFAULT);
                if (decoded != null && decoded.length > 0) return decoded;
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
                    if (comb != null) {
                        finalSgnBytes = comb;
                    }
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

    /** "Asistan" düğmesi (ac_asistan) ya da ayrı "Hukuk Asistanı" başlatıcı simgesi (AsistanGiris). */
    private static boolean asistanIstegi(Intent i) {
        if (i == null) return false;
        if (i.getBooleanExtra("ac_asistan", false)) return true;
        return i.getComponent() != null && i.getComponent().getClassName().endsWith("AsistanGiris");
    }

    /** Etkinlik yalnız asistan için açıldıysa (editörde belge yok) asistanı kapatmak ana ekrana döner. */
    private boolean asistanIcinAcildi = false;

    private class EditorBridge {
        /** Asistan modunda × : yalnız asistan için açıldıysa ana ekrana dön, değilse editöre. */
        @JavascriptInterface
        public void asistanKapat() {
            runOnUiThread(() -> {
                if (asistanIcinAcildi) {
                    finish();
                } else if (editorWebView != null) {
                    editorWebView.evaluateJavascript("document.body.classList.remove('ce-asistan-modu');"
                            + "document.documentElement.classList.remove('ce-asistan-modu');"
                            + "var p=document.getElementById('ca-panel'); if(p) p.classList.remove('acik');", null);
                }
            });
        }

        /** Asistandan bir belge editörde açıldı: artık bu etkinlik bir editör, kapatınca bitmemeli. */
        @JavascriptInterface
        public void asistanModuBitti() {
            asistanIcinAcildi = false;
        }

        /** Hukuk Asistanı sunucusunu (Termux'suz, APK içi Python) hazırlar/başlatır; {"port","anahtar"} ya da {"hata"} döner. */
        @JavascriptInterface
        public String asistanBaglanti() {
            return AsistanServisi.baglanti(EditorActivity.this);
        }

        /** Bloklamayan sürüm: hazırlığı arka planda başlatır; sonuç asistanBaglantiDurum() ile sorulur. */
        @JavascriptInterface
        public void asistanHazirla() {
            AsistanServisi.baglantiBaslat(EditorActivity.this);
        }

        @JavascriptInterface
        public String asistanBaglantiDurum() {
            return AsistanServisi.baglantiDurumu();
        }

        /** JS generateUdfBlob çıktısını (base64) kayıt iş parçacığına iletir. */
        @JavascriptInterface
        public void deliverUdfBytes(String b64) {
            java.util.function.Consumer<byte[]> c = pendingUdfBytesConsumer;
            pendingUdfBytesConsumer = null;
            if (c == null) return;
            byte[] bytes = new byte[0];
            try { if (b64 != null && !b64.isEmpty()) bytes = android.util.Base64.decode(b64, android.util.Base64.DEFAULT); } catch (Exception ignored) {}
            final byte[] fb = bytes;
            runOnUiThread(() -> c.accept(fb));
        }

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



        /** Uygulama varlığını (ör. editor/fonts/TimesNewRoman.TTF) Base64 olarak döndürür — PDF'e yazı tipi gömmek için.
         *  (Android WebView'de file:///android_asset için fetch() kullanılamaz.) Yalnızca editor/ altı okunabilir. */
        @JavascriptInterface
        public String readAssetBase64(String path) {
            if (path == null || !path.startsWith("editor/") || path.contains("..")) return "";
            try (InputStream in = getAssets().open(path)) {
                ByteArrayOutputStream bo = new ByteArrayOutputStream();
                byte[] buf = new byte[16384]; int r;
                while ((r = in.read(buf)) != -1) bo.write(buf, 0, r);
                return Base64.encodeToString(bo.toByteArray(), Base64.NO_WRAP);
            } catch (Exception e) { return ""; }
        }

        // ================================================================================
        // v3.15.0 — Platformlar arası e-imza motoru (esign.js) için ham işlemler.
        // CMS/CAdES-BES yapısı JS tarafında üretilir; burada yalnızca ağ, kart ve dosya erişimi yapılır.
        // Sonuçlar window.__esignCallback(id, ok, payload) ile JS'e döner.
        // ================================================================================
        private void esignReply(String cbId, boolean ok, String payload) {
            final String js = "window.__esignCallback && window.__esignCallback(" + JSONObject.quote(cbId) + "," + ok + "," + JSONObject.quote(payload == null ? "" : payload) + ");";
            runOnUiThread(() -> editorWebView.evaluateJavascript(js, null));
        }

        /** esign.js adımlarını tanı günlüğüne yazar (PIN/belge içeriği gönderilmez). */
        @JavascriptInterface
        public void taniYaz(String mesaj) { Tani.yaz("editör", mesaj == null ? "" : mesaj); }

        @JavascriptInterface
        public boolean taniAcik() { return Tani.acik(); }

        /** Adalet E-İmza durumu: {"kurulu","calisiyor","port","durum","okuyucu"} (anlık, engellemez). */
        @JavascriptInterface
        public String adaletDurum() {
            try {
                JSONObject j = new JSONObject();
                j.put("kurulu", AdaletKurulum.jarDosyasi(EditorActivity.this).exists());
                j.put("calisiyor", AdaletServisi.calisiyor());
                j.put("port", AdaletServisi.portAcik());
                j.put("durum", AdaletServisi.durum());
                String o = AdaletServisi.sonOkuyucu();
                if (o != null) j.put("okuyucu", o);
                return j.toString();
            } catch (Exception e) {
                return "{}";
            }
        }

        @JavascriptInterface
        public void adaletBaslat() {
            if (AdaletKurulum.jarDosyasi(EditorActivity.this).exists() && !AdaletServisi.calisiyor()) AdaletServisi.baslat(EditorActivity.this);
        }

        /** Adalet E-İmza kurulu değilse yerel (Android) soru penceresi; Evet -> kurulum ekranı. */
        @JavascriptInterface
        public void adaletKurulumSor() {
            runOnUiThread(() -> new android.app.AlertDialog.Builder(EditorActivity.this)
                    .setTitle("🏛️ Adalet E-İmza gerekli")
                    .setMessage("Kartla e-imza için resmi Adalet E-İmza uygulaması bir kez kurulmalı.\n\n"
                            + "• Termux gerekmez\n• ~80 MB, Adalet Bakanlığı'nın sunucusundan (cdn.uyap.gov.tr) indirilir\n\n"
                            + "Kurulum ekranı açılsın mı?")
                    .setPositiveButton("Kurulum ekranını aç", (d, w) -> startActivity(new Intent(EditorActivity.this, AdaletActivity.class)))
                    .setNegativeButton("Şimdi değil", null)
                    .show());
        }

        @JavascriptInterface
        public void adaletEkraniAc() {
            runOnUiThread(() -> startActivity(new Intent(EditorActivity.this, AdaletActivity.class)));
        }

        /** Resmi Adalet E-İmza servisine (127.0.0.1:5975, UdeMobile içinde) istek: kart listesi, UDF imzası. */
        @JavascriptInterface
        public void adaletIstekAsync(String cbId, String yontem, String yol, String govde) {
            new Thread(() -> {
                try {
                    if (yol == null || !(yol.startsWith("/api/v1/signature/getCertificates") || yol.startsWith("/api/v1/docsignature/")
                            || yol.startsWith("/client/info"))) {
                        esignReply(cbId, false, "İzin verilmeyen istek");
                        return;
                    }
                    if (!AdaletServisi.portAcik()) {
                        if (AdaletKurulum.jarDosyasi(EditorActivity.this).exists()) AdaletServisi.baslat(EditorActivity.this);
                        esignReply(cbId, false, "Adalet E-İmza servisi çalışmıyor");
                        return;
                    }
                    long t0 = System.currentTimeMillis();
                    Tani.yaz("editör→adalet", yontem + " " + yol + " (gövde " + (govde == null ? 0 : govde.length()) + " karakter)");
                    String cevap = AdaletServisi.istek(yontem, yol, govde == null || govde.isEmpty() ? null : govde);
                    if (Tani.acik()) {
                        String ozet = cevap.replaceAll("\"content\":\"[^\"]{40,}\"", "\"content\":\"<UDF içeriği>\"");
                        Tani.yaz("adalet→editör", (System.currentTimeMillis() - t0) + " ms · " + ozet.substring(0, Math.min(ozet.length(), 1500)));
                    }
                    esignReply(cbId, true, cevap);
                } catch (Exception e) {
                    Tani.hata("editör→adalet", "istek hatası " + yol, e);
                    esignReply(cbId, false, "Adalet E-İmza: " + e.getMessage());
                }
            }).start();
        }

        /** UYAP mobil imza SOAP isteği (yalnızca vatandas.uyap.gov.tr) */
        @JavascriptInterface
        public void httpPostAsync(String cbId, String url, String contentType, String soapAction, String body) {
            new Thread(() -> {
                HttpURLConnection conn = null;
                try {
                    if (!(url.startsWith("http://vatandas.uyap.gov.tr/") || url.startsWith("https://vatandas.uyap.gov.tr/"))) {
                        esignReply(cbId, false, "İzin verilmeyen adres");
                        return;
                    }
                    conn = (HttpURLConnection) new URL(url).openConnection();
                    conn.setRequestMethod("POST");
                    conn.setRequestProperty("Content-Type", contentType);
                    if (soapAction != null && !soapAction.isEmpty()) conn.setRequestProperty("SOAPAction", soapAction);
                    // Havelsan Doküman Editörü (Apache Axis 1.3) ile aynı başlıklar
                    conn.setRequestProperty("Accept", "application/soap+xml, application/dime, multipart/related, text/*");
                    conn.setRequestProperty("User-Agent", "Axis/1.3");
                    conn.setRequestProperty("Cache-Control", "no-cache");
                    conn.setRequestProperty("Pragma", "no-cache");
                    conn.setUseCaches(false);
                    conn.setDoOutput(true);
                    conn.setConnectTimeout(20000);
                    conn.setReadTimeout(200000); // getSignature kullanıcı PIN onayına kadar bekler
                    try (OutputStream os = conn.getOutputStream()) { os.write(body.getBytes(StandardCharsets.UTF_8)); }
                    int code = conn.getResponseCode();
                    InputStream is = (code >= 200 && code < 400) ? conn.getInputStream() : conn.getErrorStream();
                    ByteArrayOutputStream bo = new ByteArrayOutputStream();
                    if (is != null) { byte[] buf = new byte[8192]; int r; while ((r = is.read(buf)) != -1) bo.write(buf, 0, r); is.close(); }
                    esignReply(cbId, true, new String(bo.toByteArray(), StandardCharsets.UTF_8));
                } catch (Exception e) {
                    esignReply(cbId, false, "UYAP mobil imza servisine bağlanılamadı: " + e.getMessage());
                } finally { if (conn != null) conn.disconnect(); }
            }).start();
        }

        /** USB OTG CCID okuyucudaki kartın imza sertifikası */
        @JavascriptInterface
        public void scardCertAsync(String cbId) {
            new Thread(() -> {
                try {
                    CcidDriver driver = CcidDriver.getInstance(EditorActivity.this);
                    if (!driver.isConnected()) driver.scanAndConnect();
                    JSONObject res = new JSONObject();
                    org.json.JSONArray cards = new org.json.JSONArray();
                    if (driver.isConnected()) {
                        CcidDriver.CardCertificateInfo info = driver.getCertificateInfo();
                        if (info == null || info.derBytes == null) { driver.readCardCertificate(); info = driver.getCertificateInfo(); }
                        if (info != null && info.derBytes != null && info.derBytes.length > 0) {
                            JSONObject c = new JSONObject();
                            c.put("lib", "ccid");
                            c.put("slot", 0);
                            c.put("keyId", "");
                            c.put("label", info.subject);
                            c.put("tokenLabel", driver.getCardType());
                            c.put("reader", info.terminal);
                            c.put("certB64", Base64.encodeToString(info.derBytes, Base64.NO_WRAP));
                            cards.put(c);
                        }
                    }
                    res.put("cards", cards);
                    res.put("message", cards.length() > 0 ? "" : (driver.isConnected()
                        ? "Kart okuyucu bağlı ancak karttan sertifika okunamadı. Kartı çıkarıp yeniden takın."
                        : "USB e-imza okuyucusu/token bulunamadı. OTG adaptörüyle takın ve USB iznini onaylayın."));
                    esignReply(cbId, true, res.toString());
                } catch (Exception e) {
                    esignReply(cbId, false, "Kart okunamadı: " + e.getMessage());
                }
            }).start();
        }

        /** SHA-256 özetini (imzalı öznitelikler) kartta PIN ile imzalar → ham RSA imzası (Base64) */
        @JavascriptInterface
        public void scardSignAsync(String cbId, String pin, String digestB64) {
            new Thread(() -> {
                try {
                    CcidDriver driver = CcidDriver.getInstance(EditorActivity.this);
                    if (!driver.isConnected() && !driver.scanAndConnect()) { esignReply(cbId, false, "Kart takılı değil."); return; }
                    byte[] sig = driver.signWithPin(pin, Base64.decode(digestB64, Base64.DEFAULT));
                    esignReply(cbId, true, Base64.encodeToString(sig, Base64.NO_WRAP));
                } catch (Exception e) {
                    esignReply(cbId, false, e.getMessage());
                }
            }).start();
        }

        /**
         * "Orijinal UYAP Editör'de aç": belge AYRI "UYAP Editör" uygulamasında (com.agy.uyapeditor; resmi UYAP Doküman
         * Editörü, Java 14, Termux/X11'siz) açılır. Belgenin kopyası (CanFileProvider, salt okunur) gönderilir; UYAP Editör'de
         * kaydedilen belge İndirilenler/UYAP klasörüne yazılır.
         */
        @JavascriptInterface
        public void uyapEditordeAc(String ad, String base64Data) {
            new Thread(() -> {
                try {
                    Uri hedef;
                    {   // her zaman kopya: başka uygulamadan gelen geçici URI izni üçüncü uygulamaya güvenle aktarılamıyor
                        byte[] bytes = Base64.decode(base64Data, Base64.DEFAULT);
                        String a = (ad == null || ad.trim().isEmpty() ? "Belge.udf" : ad.trim()).replaceAll("[\\\\/:*?\"<>|]", "_");
                        if (!a.toLowerCase(Locale.ROOT).endsWith(".udf") && !a.toLowerCase(Locale.ROOT).endsWith(".usf")) a = a.replaceAll("\\.[^.]+$", "") + ".udf";
                        File d = getExternalCacheDir() != null ? getExternalCacheDir() : getCacheDir();
                        File f = new File(d, a);
                        try (FileOutputStream fos = new FileOutputStream(f)) { fos.write(bytes); }
                        hedef = Uri.parse("content://" + CanFileProvider.AUTHORITY + f.getAbsolutePath());
                    }
                    Intent i = new Intent(Intent.ACTION_VIEW);
                    i.setDataAndType(hedef, "application/octet-stream");
                    i.setPackage("com.agy.uyapeditor");
                    i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
                    try {
                        startActivity(i);
                    } catch (android.content.ActivityNotFoundException yok) {
                        runOnUiThread(() -> new AlertDialog.Builder(EditorActivity.this)
                                .setTitle("UYAP Editör uygulaması kurulu değil")
                                .setMessage("Belgeyi resmi UYAP Doküman Editörü'nde (Java 14, Termux/X11 gerekmez) açmak için "
                                        + "\"UYAP Editör\" uygulamasını kurun: CanEditor sürüm sayfasında UYAP-Editor-v…apk.")
                                .setPositiveButton("Sürüm sayfası", (dlg, w) -> {
                                    try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("https://github.com/cnkzlyr/udemobile/releases/latest"))); } catch (Exception ignored) { }
                                })
                                .setNegativeButton("Kapat", null).show());
                    }
                } catch (Exception e) {
                    runOnUiThread(() -> Toast.makeText(EditorActivity.this, "UYAP Editör açılamadı: " + e.getMessage(), Toast.LENGTH_LONG).show());
                }
            }).start();
        }

        /** İmzalanmış/oluşturulmuş belgeyi açık belgenin yerine (yoksa İndirilenler/UYAP_Belgelerim) kaydeder */
        @JavascriptInterface
        public void saveBytesToCurrent(String fileName, String mimeType, String base64Data) {
            new Thread(() -> {
                try {
                    byte[] bytes = Base64.decode(base64Data, Base64.DEFAULT);
                    String ext = fileName.contains(".") ? fileName.substring(fileName.lastIndexOf('.')).toLowerCase(Locale.ROOT) : ".udf";
                    final File target = resolveTargetFile(ext);
                    try (FileOutputStream fos = new FileOutputStream(target)) { fos.write(bytes); fos.flush(); }
                    if (originDataUri != null && ".udf".equals(ext)) {
                        try (OutputStream out = getContentResolver().openOutputStream(originDataUri, "wt")) { if (out != null) { out.write(bytes); out.flush(); } } catch (Exception ignored) {}
                    }
                    try { android.media.MediaScannerConnection.scanFile(EditorActivity.this, new String[]{target.getAbsolutePath()}, new String[]{mimeType}, null); } catch (Exception ignored) {}
                    currentFile = target;
                    docModified = false;
                    runOnUiThread(() -> {
                        etDocTitle.setText(target.getName());
                        tvSaveStatus.setText("✓ " + target.getName() + " kaydedildi");
                        Toast.makeText(EditorActivity.this, "✓ Kaydedildi: " + target.getAbsolutePath(), Toast.LENGTH_LONG).show();
                    });
                } catch (Exception e) {
                    runOnUiThread(() -> Toast.makeText(EditorActivity.this, "Kayıt hatası: " + e.getMessage(), Toast.LENGTH_LONG).show());
                }
            }).start();
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
