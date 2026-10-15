package com.agy.uyapacici;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.provider.OpenableColumns;
import android.provider.Settings;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import com.agy.telemetry.CrashReporter;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Date;
import java.util.List;
import java.util.Locale;

public class MainActivity extends Activity {

    private static final int REQUEST_PICK_UDF = 1001;
    private static final int REQUEST_PERM_CODE = 2001;
    private static final String PREFS_NAME = "uyap_bridge_prefs";
    private static final String KEY_DIRECT_OPEN = "direct_open";

    // UI Bileşenleri
    private LinearLayout cardActiveDoc;
    private TextView tvDocName;
    private TextView tvDocDetails;
    private Button btnCloseActiveDoc;
    private Button btnOpenInEditor;
    private Button btnQuickPreview;
    private Button btnDesktopUyapDoc;

    private LinearLayout cardPreview;
    private TextView tvPreviewContent;
    private Button btnCopyText;

    private Button btnNewDoc;
    private Button btnPickFile;
    private Button btnLaunchBlank;
    private Button btnForceCloseUyap;
    private Switch switchDirectOpen;

    private LinearLayout containerRecentDocs;
    private TextView tvEmptyRecent;

    private TextView tvStatusTermux;
    private TextView tvStatusX11;
    private TextView tvStatusScript;

    private File currentDocFile = null;
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        CrashReporter.install(this);
        setContentView(R.layout.activity_main);

        prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);

        initViews();
        setupListeners();
        checkSystemStatus();
        loadRecentDocuments();

        requestTermuxPermissionIfNeeded();

        handleIntent(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleIntent(intent);
    }

    @Override
    protected void onResume() {
        super.onResume();
        loadRecentDocuments();
        checkSystemStatus();
    }

    private void initViews() {
        cardActiveDoc = findViewById(R.id.cardActiveDoc);
        tvDocName = findViewById(R.id.tvDocName);
        tvDocDetails = findViewById(R.id.tvDocDetails);
        btnCloseActiveDoc = findViewById(R.id.btnCloseActiveDoc);
        btnOpenInEditor = findViewById(R.id.btnOpenInEditor);
        btnQuickPreview = findViewById(R.id.btnQuickPreview);
        btnDesktopUyapDoc = findViewById(R.id.btnDesktopUyapDoc);

        cardPreview = findViewById(R.id.cardPreview);
        tvPreviewContent = findViewById(R.id.tvPreviewContent);
        btnCopyText = findViewById(R.id.btnCopyText);

        btnNewDoc = findViewById(R.id.btnNewDoc);
        btnPickFile = findViewById(R.id.btnPickFile);
        btnLaunchBlank = findViewById(R.id.btnLaunchBlank);
        btnForceCloseUyap = findViewById(R.id.btnForceCloseUyap);
        switchDirectOpen = findViewById(R.id.switchDirectOpen);

        containerRecentDocs = findViewById(R.id.containerRecentDocs);
        tvEmptyRecent = findViewById(R.id.tvEmptyRecent);

        tvStatusTermux = findViewById(R.id.tvStatusTermux);
        tvStatusX11 = findViewById(R.id.tvStatusX11);
        tvStatusScript = findViewById(R.id.tvStatusScript);

        boolean directOpen = prefs.getBoolean(KEY_DIRECT_OPEN, true);
        switchDirectOpen.setChecked(directOpen);
    }

    private void setupListeners() {
        switchDirectOpen.setOnCheckedChangeListener((buttonView, isChecked) -> {
            prefs.edit().putBoolean(KEY_DIRECT_OPEN, isChecked).apply();
            Toast.makeText(this, isChecked ? "Doğrudan Mobil Editör açılacak" : "Önizleme/seçim modu etkin", Toast.LENGTH_SHORT).show();
        });

        btnNewDoc.setOnClickListener(v -> {
            Intent intent = new Intent(this, EditorActivity.class);
            startActivity(intent);
        });

        btnCloseActiveDoc.setOnClickListener(v -> {
            currentDocFile = null;
            cardActiveDoc.setVisibility(View.GONE);
            cardPreview.setVisibility(View.GONE);
            Toast.makeText(this, "Seçili belge temizlendi.", Toast.LENGTH_SHORT).show();
        });

        btnOpenInEditor.setOnClickListener(v -> {
            if (currentDocFile != null) {
                openInMobileEditor(currentDocFile.getAbsolutePath());
            } else {
                Toast.makeText(this, "Açılacak belge bulunamadı!", Toast.LENGTH_SHORT).show();
            }
        });

        btnDesktopUyapDoc.setOnClickListener(v -> {
            if (currentDocFile != null) {
                launchInTermux(currentDocFile.getAbsolutePath());
                launchX11();
            }
        });

        btnQuickPreview.setOnClickListener(v -> {
            if (currentDocFile != null) {
                extractAndShowPreview(currentDocFile);
            }
        });

        btnCopyText.setOnClickListener(v -> {
            CharSequence text = tvPreviewContent.getText();
            if (text != null && text.length() > 0) {
                ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
                ClipData clip = ClipData.newPlainText("UDF Metni", text);
                clipboard.setPrimaryClip(clip);
                Toast.makeText(this, "Belge metni panoya kopyalandı!", Toast.LENGTH_SHORT).show();
            }
        });

        btnPickFile.setOnClickListener(v -> {
            Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType("*/*");
            startActivityForResult(intent, REQUEST_PICK_UDF);
        });

        btnLaunchBlank.setOnClickListener(v -> {
            launchInTermux("");
            launchX11();
        });

        btnForceCloseUyap.setOnClickListener(v -> {
            forceCloseUyap();
        });

        tvStatusTermux.setOnClickListener(v -> {
            openAppSettings();
        });
    }

    private void openInMobileEditor(String filePath) {
        Intent intent = new Intent(this, EditorActivity.class);
        intent.putExtra(EditorActivity.EXTRA_FILE_PATH, filePath);
        startActivity(intent);
    }

    private void forceCloseUyap() {
        try {
            Intent intent = new Intent();
            intent.setClassName("com.termux", "com.termux.app.RunCommandService");
            intent.setAction("com.termux.RUN_COMMAND");
            intent.putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/usr/bin/pkill");
            intent.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", new String[]{"-f", "java|fluxbox"});
            intent.putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home");
            intent.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);
            intent.putExtra("com.termux.RUN_COMMAND_SESSION_ACTION", "0");
            startService(intent);
            Toast.makeText(this, "Masaüstü UYAP pencereleri kapatıldı.", Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Toast.makeText(this, "Kapatma hatası: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }

    private void requestTermuxPermissionIfNeeded() {
        if (checkSelfPermission("com.termux.permission.RUN_COMMAND") != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{"com.termux.permission.RUN_COMMAND"}, REQUEST_PERM_CODE);
        }
    }

    private void openAppSettings() {
        try {
            Intent intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
            intent.setData(Uri.parse("package:" + getPackageName()));
            startActivity(intent);
            Toast.makeText(this, "İzinler > Ek İzinler > 'Termux ortamında komut çalıştırma' iznini kontrol edin.", Toast.LENGTH_LONG).show();
        } catch (Exception ignored) {}
    }

    private void handleIntent(Intent intent) {
        if (intent == null) return;
        String action = intent.getAction();

        Uri targetUri = null;
        if (Intent.ACTION_VIEW.equals(action)) {
            targetUri = intent.getData();
        } else if (Intent.ACTION_SEND.equals(action)) {
            targetUri = intent.getParcelableExtra(Intent.EXTRA_STREAM);
        }

        if (targetUri != null) {
            // Intent bir kez işlendikten sonra hemen temizlenir
            intent.setData(null);
            intent.removeExtra(Intent.EXTRA_STREAM);
            intent.setAction(Intent.ACTION_MAIN);
            setIntent(new Intent(Intent.ACTION_MAIN));

            processIncomingUri(targetUri);
        }
    }

    private void processIncomingUri(Uri uri) {
        new Thread(() -> {
            try {
                String displayName = getDisplayName(uri);
                if (displayName == null || displayName.trim().isEmpty()) {
                    displayName = "belge_" + System.currentTimeMillis() + ".udf";
                }
                if (!displayName.toLowerCase().endsWith(".udf")) {
                    displayName += ".udf";
                }

                File destDir = new File(Environment.getExternalStorageDirectory(), "Documents/UYAP_Belgelerim");
                if (!destDir.exists()) {
                    destDir.mkdirs();
                }

                File destFile = new File(destDir, displayName);
                if (!destDir.canWrite()) {
                    File fallbackDir = getExternalFilesDir(null);
                    if (fallbackDir != null) {
                        destFile = new File(fallbackDir, displayName);
                    }
                }

                try (InputStream in = getContentResolver().openInputStream(uri);
                     FileOutputStream out = new FileOutputStream(destFile)) {
                    byte[] buffer = new byte[32768];
                    int len;
                    while ((len = in.read(buffer)) != -1) {
                        out.write(buffer, 0, len);
                    }
                    out.flush();
                }

                final File savedFile = destFile;
                runOnUiThread(() -> {
                    currentDocFile = savedFile;
                    boolean direct = prefs.getBoolean(KEY_DIRECT_OPEN, true);
                    if (direct) {
                        openInMobileEditor(savedFile.getAbsolutePath());
                    } else {
                        showActiveDocCard(savedFile);
                    }
                });

            } catch (Exception e) {
                runOnUiThread(() -> {
                    Toast.makeText(MainActivity.this, "Belge hazırlanamadı: " + e.getMessage(), Toast.LENGTH_LONG).show();
                });
            }
        }).start();
    }

    private void showActiveDocCard(File file) {
        cardActiveDoc.setVisibility(View.VISIBLE);
        tvDocName.setText(file.getName());
        long sizeKb = Math.max(1, file.length() / 1024);
        UdfEngine.SignatureInfo sig = UdfEngine.verifySignature(file);
        String sigBadge = "⚪ İmzasız";
        if (sig.hasSignature) {
            sigBadge = sig.isValid ? "🟢 GEÇERLİ E-İMZA (" + sig.signerName + ")" : "🔴 GEÇERSİZ İMZA (İçerik Uyuşmuyor)";
        }
        tvDocDetails.setText("Boyut: " + sizeKb + " KB • " + sigBadge + "\nKonum: " + file.getAbsolutePath());
        loadRecentDocuments();
    }

    private void extractAndShowPreview(File file) {
        cardPreview.setVisibility(View.VISIBLE);
        tvPreviewContent.setText("Belge okunuyor, lütfen bekleyin...");

        new Thread(() -> {
            String text = "Belge metni bulunamadı.";
            try {
                String html = UdfEngine.readUdfToHtml(file);
                // HTML etiketlerini ayıkla
                text = html.replaceAll("<[^>]*>", " ").replaceAll("\\s+", " ").trim();
            } catch (Exception e) {
                text = "Hızlı önizleme hatası: " + e.getMessage();
            }

            final String finalText = text;
            runOnUiThread(() -> {
                tvPreviewContent.setText(finalText);
            });
        }).start();
    }

    private void launchInTermux(String filePath) {
        try {
            Intent intent = new Intent();
            intent.setClassName("com.termux", "com.termux.app.RunCommandService");
            intent.setAction("com.termux.RUN_COMMAND");
            intent.putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/usr/bin/bash");

            List<String> args = new ArrayList<>();
            args.add("/data/data/com.termux/files/home/uyap_baslat.sh");
            if (filePath != null && !filePath.trim().isEmpty()) {
                args.add(filePath);
            }

            intent.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", args.toArray(new String[0]));
            intent.putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home");
            intent.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);
            intent.putExtra("com.termux.RUN_COMMAND_SESSION_ACTION", "0");

            startService(intent);
        } catch (Exception e) {
            try {
                Intent intent = new Intent();
                intent.setClassName("com.termux", "com.termux.app.RunCommandService");
                intent.setAction("com.termux.RUN_COMMAND");
                intent.putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/usr/bin/bash");

                List<String> args = new ArrayList<>();
                args.add("/data/data/com.termux/files/home/uyap_baslat.sh");
                if (filePath != null && !filePath.trim().isEmpty()) {
                    args.add(filePath);
                }

                intent.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", args.toArray(new String[0]));
                intent.putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home");
                intent.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);
                startForegroundService(intent);
            } catch (Exception ex) {
                Toast.makeText(this, "Termux başlatma hatası: " + ex.getMessage(), Toast.LENGTH_SHORT).show();
            }
        }
    }

    private void launchX11() {
        try {
            Intent x11Intent = new Intent();
            x11Intent.setComponent(new ComponentName("com.termux.x11", "com.termux.x11.MainActivity"));
            x11Intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(x11Intent);
            return;
        } catch (Exception ignored) {}

        try {
            Intent fallback = getPackageManager().getLaunchIntentForPackage("com.termux.x11");
            if (fallback != null) {
                fallback.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(fallback);
            } else {
                Toast.makeText(this, "Termux:X11 ekranı bulunamadı!", Toast.LENGTH_SHORT).show();
            }
        } catch (Exception e) {
            Toast.makeText(this, "X11 geçiş hatası: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }

    private void checkSystemStatus() {
        boolean termuxInstalled = isPackageInstalled("com.termux");
        boolean x11Installed = isPackageInstalled("com.termux.x11");

        if (termuxInstalled) {
            int perm = checkSelfPermission("com.termux.permission.RUN_COMMAND");
            if (perm == PackageManager.PERMISSION_GRANTED) {
                tvStatusTermux.setText("✓ Mobil UYAP Motoru: Aktif (A4 & XML Hazır)");
                tvStatusTermux.setTextColor(0xFF2E7D32);
            } else {
                tvStatusTermux.setText("✓ Mobil UYAP Motoru: Aktif (Masaüstü için yetki alınız)");
                tvStatusTermux.setTextColor(0xFF2E7D32);
            }
        }

        if (x11Installed) {
            tvStatusX11.setText("✓ Termux / X11 Köprüsü: Hazır");
            tvStatusX11.setTextColor(0xFF2E7D32);
        } else {
            tvStatusX11.setText("• Masaüstü Modu: Opsiyonel");
            tvStatusX11.setTextColor(0xFF757575);
        }
    }

    private void loadRecentDocuments() {
        List<File> list = new ArrayList<>();
        File docDir = new File(Environment.getExternalStorageDirectory(), "Documents/UYAP_Belgelerim");
        File downDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);

        scanUdfFiles(docDir, list);
        scanUdfFiles(downDir, list);

        Collections.sort(list, (f1, f2) -> Long.compare(f2.lastModified(), f1.lastModified()));

        containerRecentDocs.removeAllViews();
        if (list.isEmpty()) {
            tvEmptyRecent.setVisibility(View.VISIBLE);
            containerRecentDocs.addView(tvEmptyRecent);
            return;
        }

        tvEmptyRecent.setVisibility(View.GONE);
        SimpleDateFormat sdf = new SimpleDateFormat("dd.MM.yyyy HH:mm", Locale.getDefault());

        int count = Math.min(list.size(), 6);
        for (int i = 0; i < count; i++) {
            final File f = list.get(i);
            LinearLayout itemLayout = new LinearLayout(this);
            itemLayout.setOrientation(LinearLayout.VERTICAL);
            itemLayout.setPadding(14, 16, 14, 16);
            itemLayout.setBackgroundResource(R.drawable.badge_bg);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
            lp.bottomMargin = 10;
            itemLayout.setLayoutParams(lp);

            TextView title = new TextView(this);
            title.setText("📄 " + f.getName());
            title.setTextSize(14);
            title.setTextColor(0xFF212121);
            title.setTypeface(null, android.graphics.Typeface.BOLD);

            TextView sub = new TextView(this);
            sub.setText(sdf.format(new Date(f.lastModified())) + " • " + Math.max(1, f.length() / 1024) + " KB");
            sub.setTextSize(11.5f);
            sub.setTextColor(0xFF555555);

            // Havelsan UYAP elektronik imza kontrolü
            UdfEngine.SignatureInfo sig = UdfEngine.verifySignature(f);
            TextView tvSig = new TextView(this);
            tvSig.setTextSize(12);
            tvSig.setPadding(0, 4, 0, 0);

            if (sig.hasSignature) {
                if (sig.isValid) {
                    String signer = sig.signerName.isEmpty() ? "Bilinmeyen İmzacı" : sig.signerName;
                    String issuer = sig.issuer.isEmpty() ? "" : " (" + sig.issuer + ")";
                    if (sig.signers.size() > 1) {
                        tvSig.setText("🟢 " + sig.signers.size() + " GEÇERLİ İMZA: " + signer);
                    } else {
                        tvSig.setText("🟢 GEÇERLİ E-İMZA: " + signer + issuer);
                    }
                    tvSig.setTextColor(0xFF2E7D32); // Koyu yeşil
                    tvSig.setTypeface(null, android.graphics.Typeface.BOLD);
                } else {
                    tvSig.setText("🔴 GEÇERSİZ İMZA (İçerik Özeti Uyuşmuyor veya Hatalı)");
                    tvSig.setTextColor(0xFFC62828); // Koyu kırmızı
                    tvSig.setTypeface(null, android.graphics.Typeface.BOLD);
                }
            } else {
                tvSig.setText("⚪ İmzasız Belge");
                tvSig.setTextColor(0xFF757575); // Gri
            }

            itemLayout.addView(title);
            itemLayout.addView(sub);
            itemLayout.addView(tvSig);

            itemLayout.setOnClickListener(v -> {
                openInMobileEditor(f.getAbsolutePath());
            });

            containerRecentDocs.addView(itemLayout);
        }
    }

    private void scanUdfFiles(File dir, List<File> list) {
        if (dir != null && dir.exists() && dir.isDirectory()) {
            File[] files = dir.listFiles();
            if (files != null) {
                for (File f : files) {
                    if (f.isFile() && f.getName().toLowerCase().endsWith(".udf")) {
                        list.add(f);
                    }
                }
            }
        }
    }

    private boolean isPackageInstalled(String pkg) {
        try {
            getPackageManager().getPackageInfo(pkg, 0);
            return true;
        } catch (PackageManager.NameNotFoundException e) {
            return false;
        }
    }

    private String getDisplayName(Uri uri) {
        String name = null;
        if ("content".equalsIgnoreCase(uri.getScheme())) {
            try (Cursor cursor = getContentResolver().query(uri, null, null, null, null)) {
                if (cursor != null && cursor.moveToFirst()) {
                    int index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                    if (index >= 0) {
                        name = cursor.getString(index);
                    }
                }
            } catch (Exception ignored) {}
        }
        if (name == null) {
            name = uri.getLastPathSegment();
        }
        return name;
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_PICK_UDF && resultCode == RESULT_OK && data != null) {
            Uri uri = data.getData();
            if (uri != null) {
                processIncomingUri(uri);
            }
        }
    }
}
