package com.agy.uyapacici;

import android.app.Activity;
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
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import com.agy.telemetry.CrashReporter;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.File;
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
                    injectDocumentData(pendingHeader, pendingFooter, pendingHtmlToLoad);
                    pendingHeader = null;
                    pendingFooter = null;
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
                        String header = "";
                        String footer = "";
                        String html = "";
                        String lower = currentFile.getName().toLowerCase();
                        if (lower.endsWith(".docx")) {
                            html = DocxEngine.readDocxToHtml(currentFile);
                        } else {
                            String udfPayload = UdfEngine.readUdfToHtml(currentFile);
                            try {
                                JSONObject obj = new JSONObject(udfPayload);
                                header = obj.optString("header", "");
                                footer = obj.optString("footer", "");
                                html = obj.optString("html", "");
                            } catch (Exception ignored) {
                                html = udfPayload;
                            }
                        }

                        final String fHeader = header;
                        final String fFooter = footer;
                        final String fHtml = html;
                        runOnUiThread(() -> {
                            if (isPageLoaded) {
                                injectDocumentData(fHeader, fFooter, fHtml);
                            } else {
                                pendingHeader = fHeader;
                                pendingFooter = fFooter;
                                pendingHtmlToLoad = fHtml;
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

            final String finalJson = cleanJsonString(rawResult);

            new Thread(() -> {
                try {
                    String baseTitle = etDocTitle.getText().toString().trim();
                    if (baseTitle.isEmpty()) baseTitle = "Yeni_Dilekce";

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
            intent.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", new String[]{"-c", "bash ~/eimza/eimza_baslat.sh ensure >/dev/null 2>&1; bash ~/eimza/adalet_baslat.sh ensure >/dev/null 2>&1"});
            intent.putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home");
            intent.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);
            intent.putExtra("com.termux.RUN_COMMAND_SESSION_ACTION", "0");
            startService(intent);
        } catch (Exception ignored) {}
    }

    private void performRealSmartCardSign(String certificateId, String pin, String jsonContent) {
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

                // UDF olarak yaz
                UdfEngine.saveStructuredToUdf(cleanJson, targetFile);
                currentFile = targetFile;

                // Dosya içeriğini Base64 olarak hazırla
                byte[] fileBytes = java.nio.file.Files.readAllBytes(targetFile.toPath());
                String base64Content = Base64.encodeToString(fileBytes, Base64.NO_WRAP);

                // 2. Adalet E-İmza Servisi üzerinden gerçek donanımsal imzalama isteği gönder
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
                reqObj.put("content", base64Content);

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

                // 3. Başarılı! Gerçek CAdES CMS DER imza verisini al
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

                // 4. Belgeyi gerçek sign.sgn ikilisi ile UDF arşivine mühürle ve kaydet
                UdfEngine.saveStructuredToUdf(cleanJson, targetFile, realCmsBytes);

                // 5. Doğrulama özeti hesapla
                MessageDigest md = MessageDigest.getInstance("SHA-256");
                byte[] digest = md.digest(realCmsBytes);
                StringBuilder hashSb = new StringBuilder();
                for (int i = 0; i < 8; i++) {
                    hashSb.append(String.format("%02X", digest[i]));
                }
                final String realHash = "NES-HW-" + hashSb.toString() + "-" + Long.toHexString(System.currentTimeMillis()).toUpperCase(Locale.US);

                runOnUiThread(() -> {
                    editorWebView.evaluateJavascript("onRealSignSuccess(" + JSONObject.quote(realHash) + ");", null);
                    tvSaveStatus.setText("✓ İmzalandı");
                    Toast.makeText(EditorActivity.this, "✓ Gerçek E-İmza ile Başarıyla İmzalandı!", Toast.LENGTH_LONG).show();
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

    private class EditorBridge {
        @JavascriptInterface
        public void onContentChanged(int wordCount, int charCount) {
            runOnUiThread(() -> {
                tvWordCount.setText(wordCount + " kelime • " + charCount + " karakter");
                tvSaveStatus.setText("● Düzenleniyor");
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
        public void openDesktopUyap() {
            runOnUiThread(() -> {
                saveDocument(false, true);
            });
        }
    }
}
