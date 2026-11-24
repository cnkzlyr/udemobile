package app.eimza.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.Dialog;
import android.content.ClipData;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Message;
import android.text.InputType;
import android.text.TextUtils;
import android.view.View;
import android.view.DragEvent;
import android.view.Gravity;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceError;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebSettings;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.FrameLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;
import android.widget.PopupMenu;
import android.widget.Spinner;
import android.widget.ArrayAdapter;
import android.widget.AutoCompleteTextView;
import java.security.Security;
import java.net.URI;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.text.SimpleDateFormat;
import java.util.Date;

import javax.security.auth.x500.X500Principal;
import org.bouncycastle.asn1.x500.X500Name;
import org.bouncycastle.asn1.x500.style.BCStyle;
import org.bouncycastle.asn1.x500.style.IETFUtils;
import org.bouncycastle.asn1.x500.RDN;

import org.bouncycastle.asn1.*;
import org.bouncycastle.asn1.x509.Certificate;
import org.bouncycastle.cert.X509CertificateHolder;
import org.bouncycastle.cms.CMSSignedData;
import org.bouncycastle.cms.SignerInformation;
import java.io.ByteArrayInputStream;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;
import javax.xml.parsers.DocumentBuilderFactory;

public final class MainActivity extends Activity {
    private TextView readerStatus;
    private TextView signerStatus;
    private TextView portalStatus;
    private WebView webView;
    private WebView activeWebView;
    private View menuPanel;
    private View browserPanel;
    private View helpPanel;
    private View debuggerPanel;
    private View udfPanel;
    private View settingsPanel;
    private View aboutPanel;
    private volatile String activePageUrl = "";
    private volatile String lastObsCallbackUrl = "";
    private volatile long lastObsCallbackAt;
    private volatile String activeEdevletCode = "";
    private volatile long activeEdevletCodeAt;
    private volatile String completedEdevletCode = "";
    private volatile long completedEdevletCodeAt;
    private String adaletPageHook;
    private String arkPageHook;
    private String edevletPageHook;
    private String obsSsoDiagnosticsHook;
    private TextView arkDiagnostics;
    private final StringBuilder arkTrace = new StringBuilder();
    private final java.util.concurrent.ConcurrentHashMap<String, String> arkJobs = new java.util.concurrent.ConcurrentHashMap<>();
    private String mobileUserAgent;
    private boolean showingPortalError;
    private final java.util.concurrent.atomic.AtomicBoolean autoCertificateScan = new java.util.concurrent.atomic.AtomicBoolean();
    private int automaticScanRetries;
    private boolean desktopMode;
    private boolean addressAutocompleteEnabled;
    private AutoCompleteTextView addressBar;
    private Switch desktopSwitch;
    private FrameLayout webHost;
    private TextView debugOutput;
    private TextView udfStatus;
    private TextView udfPreview;
    private WebView udfPreviewWeb;
    private Switch udfTimestampSwitch;
    private EditText tsaUrlInput;
    private EditText tsaUsernameInput;
    private EditText tsaPasswordInput;
    private Spinner tsaProviderInput;
    private static final String[] TSA_PROVIDERS = {
            "KamuSM üretim", "UYAP / Adalet (KamuSM)", "Arkİmza / ArkSigner", "Özel RFC 3161"
    };
    private byte[] selectedUdfBytes;
    private byte[] selectedUdfContent;
    private byte[] pendingSignedUdf;
    private String selectedUdfName = "";
    private Uri pendingUdfOutput;
    private int titleTaps;
    private boolean adminDebug;
    private boolean darkMode;
    private FrameLayout rootScreen;
    private FrameLayout tutorialOverlay;
    private View menuOverflowAnchor;
    private TextView tabCountView;
    private final java.util.ArrayList<WebView> browserTabs = new java.util.ArrayList<>();
    private final java.util.IdentityHashMap<WebView, String> browserTabGroups = new java.util.IdentityHashMap<>();
    private final java.util.IdentityHashMap<WebView, Bitmap> browserTabPreviews = new java.util.IdentityHashMap<>();
    private final java.util.ArrayList<String> browserHistory = new java.util.ArrayList<>();
    private WebView draggedBrowserTab;
    private final StringBuilder debugTrace = new StringBuilder();
    private static final int REQUEST_UDF_OPEN = 7401;
    private static final int REQUEST_UDF_SAVE = 7402;
    private UsbCcidProbe usbProbe;
    private AkisSignerBackend akisBackend;
    private ArkLoopbackServer loopbackServer;
    private final ExecutorService signerWorker = Executors.newSingleThreadExecutor();

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        initializeEsyaLicense();
        if (Security.getProvider("AndroidCCID") == null) Security.addProvider(new AndroidCcidProvider());
        usbProbe = new UsbCcidProbe(this, this::showReaderStatus);
        akisBackend = new AkisSignerBackend();
        loopbackServer = new ArkLoopbackServer(this::handleLoopbackRequest);
        loopbackServer.start();
        adminDebug = getPreferences(MODE_PRIVATE).getBoolean("admin_debug", false);
        darkMode = getPreferences(MODE_PRIVATE).getBoolean("dark_mode", false);
        addressAutocompleteEnabled = getPreferences(MODE_PRIVATE)
                .getBoolean("address_autocomplete", true);
        loadBrowserHistory();
        Telemetry.configure(this, getPreferences(MODE_PRIVATE).getBoolean("telemetry_enabled", false));
        enforceOfflinePolicy();
        arkPageHook = readAsset("arksigner-bridge.js");
        adaletPageHook = readAsset("adalet-bridge.js");
        edevletPageHook = readAsset("edevlet-bridge.js");
        obsSsoDiagnosticsHook = readAsset("obs-sso-diagnostics.js");
        setContentView(buildView());
        // Start navigation after the WebView has been attached to its window.
        webView.post(() -> {
            maybeShowTutorial();
            webView.loadUrl("about:blank");
            debugLog("Başlangıç: ana menü");
            Telemetry.event("app_open");
        });
        usbProbe.scan();
    }

    private void initializeEsyaLicense() {
        try (java.io.InputStream encrypted = getAssets().open("tubitak/lisans.xml.enc");
             java.io.InputStream input = AdaletEsyaConfig.decrypt(encrypted)) {
            // The supplied Adalet client intentionally ignores this boolean;
            // encrypted licence material is installed even when it returns false.
            tr.gov.tubitak.uekae.esya.api.common.util.LicenseUtil.setLicenseXml(input);
        } catch (Exception error) {
            throw new IllegalStateException("Adalet ESYA imza motoru başlatılamadı", error);
        }
    }

    private View buildView() {
        FrameLayout screen = new FrameLayout(this);
        rootScreen = screen;
        menuPanel = buildMenuPanel();
        browserPanel = buildBrowserPanel();
        helpPanel = buildHelpPanel();
        debuggerPanel = buildDebuggerPanel();
        udfPanel = buildUdfPanel();
        settingsPanel = buildSettingsPanel();
        aboutPanel = buildAboutPanel();
        for (View panel : new View[]{menuPanel, browserPanel, helpPanel, debuggerPanel, udfPanel, settingsPanel, aboutPanel})
            screen.addView(panel, new FrameLayout.LayoutParams(-1, -1));
        showPanel(menuPanel);
        applyTheme(screen);
        return screen;
    }

    private View buildMenuPanel() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = panelRoot("E-İmza One");
        root.removeViewAt(0);
        TextView subtitle = statusText("Kartını bağla, portalı adres çubuğundan aç, imzanı tek yerden yönet.");
        subtitle.setTextColor(Color.rgb(82, 101, 130));
        root.addView(subtitle);
        LinearLayout brand = new LinearLayout(this);
        brand.setGravity(Gravity.CENTER_VERTICAL);
        ImageView logo = new ImageView(this);
        logo.setImageResource(app.eimza.mobile.R.drawable.eimza_one_brand);
        brand.addView(logo, new LinearLayout.LayoutParams(dp(42), dp(42)));
        TextView heading = new TextView(this);
        heading.setText("E-İmza One · 0.3.1");
        heading.setTextSize(29);
        heading.setTextColor(Color.rgb(16, 24, 40));
        heading.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        heading.setPadding(dp(10), 0, 0, 0);
        brand.addView(heading, new LinearLayout.LayoutParams(0, -2, 1f));
        TextView overflow = new TextView(this);
        overflow.setText("⋮");
        overflow.setTextSize(28);
        overflow.setGravity(Gravity.CENTER);
        overflow.setOnClickListener(v -> showMenuOverflow());
        menuOverflowAnchor = overflow;
        brand.addView(overflow, new LinearLayout.LayoutParams(dp(42), dp(48)));
        root.addView(brand, 0);
        heading.setOnClickListener(v -> adminTap());
        /* The brand row owns the title; keep the old heading reference behavior. */

        LinearLayout statusCard = card();
        readerStatus = statusText("USB okuyucu aranıyor…");
        signerStatus = statusText("ArkSigner Arkİmza · TÜRKTRUST TBB Kırmızı Token · Kamu SM ATR19 gömülü sürücüler hazır.");
        statusCard.addView(readerStatus);
        statusCard.addView(signerStatus);
        root.addView(statusCard, marginParams(0, 14, 0, 10));
        root.addView(sectionTitle("Hızlı erişim"));
        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.VERTICAL);
        actions.addView(actionRow(action("Tarayıcı", v -> showPanel(browserPanel)), action("Kartı tara", v -> usbProbe.scan())));
        actions.addView(actionRow(action("e-Devlet E-İmza", v -> open("https://giris.turkiye.gov.tr/Giris/Elektronik-Imza")),
                action("İşlem kodu", v -> promptEdevletTransactionCode())));
        actions.addView(actionRow(action("Kart & Sertifika Bilgisi", v -> readCertificates()), action("UYAP UDF", v -> showPanel(udfPanel))));
        actions.addView(actionRow(action("Tanı & Debugger", v -> showPanel(debuggerPanel)), action("Tanı Günlüğü (.txt)", v -> exportDiagnosticTxt())));
        actions.addView(actionRow(action("Ayarlar", v -> showPanel(settingsPanel)), action("Hakkında", v -> showPanel(aboutPanel))));
        root.addView(actions);
        root.addView(sectionTitle("Destek durumu"));
        root.addView(infoCard("Gömülü Token Sürücüleri", "1) ArkSigner Arkİmza Kriptografik Token\n2) TÜRKTRUST / TBB Kırmızı Token (Baro Kart)\n3) Kamu SM / TÜBİTAK (ATR19 Mini Okuyucu)"));
        root.addView(infoCard("Donanım & Protokol", "USB CCID (Doğrudan APDU & T=1/T=0 TPDU) · ISO 7816-4 / PKCS#15 · AKİS CIF · RSA & ECDSA"));
        arkDiagnostics = statusText("Portal tanısı: henüz imza isteği gelmedi");
        arkDiagnostics.setTextIsSelectable(true);
        root.addView(sectionTitle("Son tanı"));
        root.addView(cardWith(arkDiagnostics));
        scroll.addView(root);
        return scroll;
    }

    private void showMenuOverflow() {
        PopupMenu popup = new PopupMenu(this, menuOverflowAnchor == null ? menuPanel : menuOverflowAnchor);
        popup.getMenu().add("Tarayıcı").setOnMenuItemClickListener(i -> { showPanel(browserPanel); return true; });
        popup.getMenu().add("Tanı Raporunu İndir (.txt)").setOnMenuItemClickListener(i -> { exportDiagnosticTxt(); return true; });
        popup.getMenu().add("Tanı & Debugger").setOnMenuItemClickListener(i -> { showPanel(debuggerPanel); return true; });
        popup.getMenu().add("Ayarlar").setOnMenuItemClickListener(i -> { showPanel(settingsPanel); return true; });
        popup.getMenu().add("Hakkında").setOnMenuItemClickListener(i -> { showPanel(aboutPanel); return true; });
        popup.getMenu().add("Yardım").setOnMenuItemClickListener(i -> { showPanel(helpPanel); return true; });
        popup.show();
    }

    private View buildBrowserPanel() {
        LinearLayout browser = new LinearLayout(this);
        browser.setTag("browser_chrome");
        browser.setOrientation(LinearLayout.VERTICAL);
        browser.setBackgroundColor(Color.rgb(18, 22, 33));
        LinearLayout bar = new LinearLayout(this);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(10), dp(9), dp(10), dp(7));
        bar.setBackgroundColor(Color.rgb(26, 31, 45));
        TextView shield = browserIcon("◆", v -> showBrowserPrivacyInfo());
        shield.setTextColor(Color.rgb(255, 105, 75));
        bar.addView(shield, new LinearLayout.LayoutParams(dp(38), dp(44)));
        addressBar = new AutoCompleteTextView(this);
        addressBar.setSingleLine(true);
        addressBar.setThreshold(1);
        addressBar.setTextSize(14);
        addressBar.setHint("Ara veya adres yaz");
        addressBar.setTextColor(Color.WHITE);
        addressBar.setHintTextColor(Color.rgb(160, 170, 190));
        addressBar.setPadding(dp(12), 0, dp(12), 0);
        addressBar.setBackground(roundBackground(Color.rgb(40, 46, 63), Color.rgb(62, 70, 91), 22));
        addressBar.setOnEditorActionListener((v, id, event) -> { navigateAddress(); return true; });
        refreshAddressSuggestions();
        bar.addView(addressBar, new LinearLayout.LayoutParams(0, dp(44), 1f));
        bar.addView(browserIcon("×", v -> {
            addressBar.setText("");
            addressBar.requestFocus();
        }), new LinearLayout.LayoutParams(dp(38), dp(44)));
        bar.addView(browserIcon("✎", v -> showAddressEditor()), new LinearLayout.LayoutParams(dp(38), dp(44)));
        bar.addView(browserIcon("↻", v -> reloadPage()), new LinearLayout.LayoutParams(dp(42), dp(44)));
        browser.addView(bar);
        desktopSwitch = new Switch(this);
        desktopSwitch.setChecked(desktopMode);
        desktopSwitch.setOnCheckedChangeListener((b, checked) -> {
            desktopMode = checked;
            applyUserAgent();
            WebView target = activeWebView == null ? webView : activeWebView;
            if (target != null && !activePageUrl.isEmpty()) target.reload();
            debugLog("Masaüstü modu: " + checked);
        });
        portalStatus = statusText("Adres girin veya dış tarayıcıdan bir portal açın.");
        portalStatus.setTextColor(Color.rgb(174, 184, 204));
        portalStatus.setBackgroundColor(Color.rgb(26, 31, 45));
        portalStatus.setPadding(dp(14), dp(2), dp(14), dp(5));
        portalStatus.setSingleLine(true);
        portalStatus.setEllipsize(TextUtils.TruncateAt.MIDDLE);
        browser.addView(portalStatus);

        webView = new WebView(this);
        activeWebView = webView;
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setSafeBrowsingEnabled(true);
        hardenWebSettings(settings);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);
        settings.setSupportMultipleWindows(true);
        settings.setJavaScriptCanOpenWindowsAutomatically(true);
        settings.setSupportZoom(true);
        settings.setBuiltInZoomControls(true);
        settings.setDisplayZoomControls(false);
        mobileUserAgent = settings.getUserAgentString();
        webView.addJavascriptInterface(new ArkPageBridge(), "EimzaNative");
        if (WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
            WebViewCompat.addDocumentStartJavaScript(webView, arkPageHook + adaletPageHook,
                    new HashSet<>(Arrays.asList("https://uyap.gov.tr", "https://*.uyap.gov.tr",
                            "https://adalet.gov.tr", "https://*.adalet.gov.tr", "https://yargitay.gov.tr",
                            "https://*.yargitay.gov.tr", "https://danistay.gov.tr", "https://*.danistay.gov.tr",
                            "https://enabiz.gov.tr", "https://*.enabiz.gov.tr", "https://saglik.gov.tr",
                            "https://*.saglik.gov.tr", "https://recetem.saglik.gov.tr", "https://test.arksigner.com")));
            WebViewCompat.addDocumentStartJavaScript(webView, edevletPageHook,
                    new HashSet<>(Arrays.asList("https://turkiye.gov.tr", "https://*.turkiye.gov.tr")));
            WebViewCompat.addDocumentStartJavaScript(webView, obsSsoDiagnosticsHook,
                    new HashSet<>(Arrays.asList("https://obs.saglik.gov.tr")));
        }
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true);
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onCreateWindow(WebView view, boolean isDialog,
                                                    boolean isUserGesture, Message resultMsg) {
                WebView popup = new WebView(MainActivity.this);
                popup.getSettings().setJavaScriptEnabled(true);
                popup.getSettings().setDomStorageEnabled(true);
                hardenWebSettings(popup.getSettings());
                popup.getSettings().setSupportMultipleWindows(true);
                popup.getSettings().setJavaScriptCanOpenWindowsAutomatically(true);
                popup.getSettings().setSupportZoom(true);
                popup.getSettings().setBuiltInZoomControls(true);
                popup.getSettings().setDisplayZoomControls(false);
                popup.getSettings().setUseWideViewPort(true);
                popup.getSettings().setLoadWithOverviewMode(desktopMode);
                popup.getSettings().setUserAgentString(webView.getSettings().getUserAgentString());
                popup.addJavascriptInterface(new ArkPageBridge(), "EimzaNative");
                CookieManager.getInstance().setAcceptThirdPartyCookies(popup, true);
                popup.setWebChromeClient(new WebChromeClient());
                popup.setWebViewClient(new WebViewClient() {
                    @Override public boolean shouldOverrideUrlLoading(WebView child, WebResourceRequest request) {
                        if (handleArkSignerLaunch(child, request.getUrl())) return true;
                        if (isEdevletJnlp(request.getUrl())) {
                            debugLog("e-Devlet JNLP indiriliyor; işlem kodu sayfadan alınacak");
                            return false;
                        }
                        if (rejectDuplicateObsCallback(request.getUrl())) return true;
                        // OBS q is an opaque server token. Never rewrite or
                        // decode it in the client; WebView must follow it byte-for-byte.
                        return false;
                    }
                    @Override public void onPageStarted(WebView child, String url,
                                                        android.graphics.Bitmap icon) {
                        if (handleArkSignerLaunch(child, Uri.parse(url))) return;
                        activePageUrl = url == null ? "" : url;
                        showAddress(url);
                        debugLog("Popup açıldı: " + url);
                    }
                    @Override public void onPageFinished(WebView child, String url) {
                        activePageUrl = url == null ? "" : url;
                        applyViewport(child);
                        recordHistory(child.getTitle(), url);
                        captureTabPreview(child);
                        if (edevletOrigin(url)) {
                            child.evaluateJavascript(edevletPageHook, null);
                        } else if (shouldInjectArk(url)) {
                            child.evaluateJavascript(arkPageHook, null);
                            if (adaletOrigin(url)) child.evaluateJavascript(adaletPageHook, null);
                        }
                    }
                    @Override public void onReceivedError(WebView child, WebResourceRequest request,
                                                          WebResourceError error) {
                        if (isArkSignerLaunch(request.getUrl())) return;
                        if (request.isForMainFrame()) showPortalError("Sayfa yüklenemedi ("
                                + error.getErrorCode() + "): " + error.getDescription(),
                                request.getUrl().toString());
                    }
                });
                if (webHost != null) {
                    webHost.removeAllViews();
                    webHost.addView(popup, new FrameLayout.LayoutParams(-1, -1));
                }
                activeWebView = popup;
                if (!browserTabs.contains(popup)) {
                    browserTabs.add(popup);
                    browserTabGroups.put(popup, "Açılır pencereler");
                    updateTabCount();
                }
                applyUserAgent(activePageUrl);
                WebView.WebViewTransport transport = (WebView.WebViewTransport) resultMsg.obj;
                transport.setWebView(popup);
                resultMsg.sendToTarget();
                return true;
            }
        });
        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (handleArkSignerLaunch(view, request.getUrl())) return true;
                if (isEdevletJnlp(request.getUrl())) {
                    debugLog("e-Devlet JNLP indiriliyor; işlem kodu sayfadan alınacak");
                    return false;
                }
                if (rejectDuplicateObsCallback(request.getUrl())) return true;
                // OBS q is an opaque server token; preserve the original URL.
                String scheme = request.getUrl().getScheme();
                if ("https".equalsIgnoreCase(scheme)) return false;
                if ("http".equalsIgnoreCase(scheme)) {
                    if (isLoopbackHost(request.getUrl().getHost())) return false;
                    debugLog("Güvenlik: şifrelenmemiş uzak HTTP engellendi: " + request.getUrl().getHost());
                    setPortalStatus("Güvenlik nedeniyle HTTP bağlantısı engellendi");
                    return true;
                }
                if (!("mailto".equalsIgnoreCase(scheme) || "tel".equalsIgnoreCase(scheme))) {
                    debugLog("Güvenlik: desteklenmeyen bağlantı şeması engellendi: " + scheme);
                    return true;
                }
                try { startActivity(new Intent(Intent.ACTION_VIEW, request.getUrl())); }
                catch (Exception e) { debugLog("Dış bağlantı açılamadı: " + scheme); }
                return true;
            }
            @Override public void onReceivedSslError(WebView view, SslErrorHandler handler, android.net.http.SslError error) {
                handler.cancel();
                debugLog("TLS hatası: " + error.getUrl());
                showPortalError("Güvenli bağlantı kurulamadı (TLS)", error.getUrl());
            }
            @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap icon) {
                if (handleArkSignerLaunch(view, Uri.parse(url))) return;
                if (url != null && url.startsWith("https://obs.saglik.gov.tr/Account/SsoLogin?code="))
                    CookieManager.getInstance().flush();
                activePageUrl = url == null ? "" : url;
                showAddress(url);
                if (!showingPortalError) setPortalStatus("Yükleniyor: " + url);
            }
            @Override public void onPageFinished(WebView view, String url) {
                if (showingPortalError) return;
                activePageUrl = url == null ? "" : url;
                showAddress(url);
                setPortalStatus("Açık: " + url);
                debugLog("Sayfa açıldı: " + url);
                recordHistory(view.getTitle(), url);
                captureTabPreview(view);
                applyViewport(view);
                diagnoseHealthSso(view, url);
                if (edevletOrigin(url)) {
                    view.evaluateJavascript(edevletPageHook, null);
                } else if (shouldInjectArk(url)) {
                    view.evaluateJavascript(arkPageHook, null);
                    if (adaletOrigin(url)) view.evaluateJavascript(adaletPageHook, null);
                }
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (isArkSignerLaunch(request.getUrl())) return;
                if (request.isForMainFrame()) showPortalError("Sayfa yüklenemedi (" + error.getErrorCode() + "): "
                        + error.getDescription(), request.getUrl().toString());
            }
            @Override public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse response) {
                if (request.isForMainFrame()) showPortalError("Portal HTTP " + response.getStatusCode(), request.getUrl().toString());
            }
        });
        webView.setDownloadListener((url, userAgent, contentDisposition, mimeType, contentLength) -> {
            if (isEdevletJnlp(Uri.parse(url))) debugLog("e-Devlet JNLP indiriliyor; işlem kodu sayfadan alınacak");
            else try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); }
            catch (Exception error) { debugLog("İndirme bağlantısı açılamadı"); }
        });
        webHost = new FrameLayout(this);
        webHost.addView(webView, new FrameLayout.LayoutParams(-1, -1));
        browserTabs.add(webView);
        browserTabGroups.put(webView, "Genel");
        browser.addView(webHost, new LinearLayout.LayoutParams(-1, 0, 1f));

        LinearLayout bottom = new LinearLayout(this);
        bottom.setGravity(Gravity.CENTER);
        bottom.setPadding(dp(8), dp(5), dp(8), dp(7));
        bottom.setBackgroundColor(Color.rgb(26, 31, 45));
        bottom.addView(browserIcon("‹", v -> goBack()), new LinearLayout.LayoutParams(0, dp(46), 1f));
        bottom.addView(browserIcon("›", v -> goForward()), new LinearLayout.LayoutParams(0, dp(46), 1f));
        bottom.addView(browserIcon("⌂", v -> showPanel(menuPanel)), new LinearLayout.LayoutParams(0, dp(46), 1f));
        TextView tabs = browserIcon("1", v -> showTabManager());
        tabCountView = tabs;
        tabs.setBackground(roundBackground(Color.TRANSPARENT, Color.rgb(151, 160, 181), 7));
        LinearLayout.LayoutParams tabParams = new LinearLayout.LayoutParams(dp(32), dp(32));
        tabParams.setMargins(dp(20), dp(7), dp(20), dp(7));
        bottom.addView(tabs, tabParams);
        TextView overflow = browserIcon("⋮", v -> showBrowserMenu());
        menuOverflowAnchor = overflow;
        bottom.addView(overflow, new LinearLayout.LayoutParams(0, dp(46), 1f));
        browser.addView(bottom);
        return browser;
    }

    private TextView browserIcon(String label, View.OnClickListener listener) {
        TextView icon = new TextView(this);
        icon.setText(label);
        icon.setTextSize(22);
        icon.setTextColor(Color.rgb(232, 236, 245));
        icon.setGravity(Gravity.CENTER);
        icon.setOnClickListener(listener);
        icon.setBackground(roundBackground(Color.TRANSPARENT, Color.TRANSPARENT, 18));
        return icon;
    }

    private void updateTabCount() {
        if (tabCountView != null) tabCountView.setText(String.valueOf(browserTabs.size()));
    }

    private WebView createBrowserTab(String url, String group) {
        WebView tab = new WebView(this);
        WebSettings settings = tab.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setSafeBrowsingEnabled(true);
        hardenWebSettings(settings);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(desktopMode);
        settings.setSupportMultipleWindows(true);
        settings.setJavaScriptCanOpenWindowsAutomatically(true);
        settings.setSupportZoom(true);
        settings.setBuiltInZoomControls(true);
        settings.setDisplayZoomControls(false);
        settings.setUserAgentString(webView.getSettings().getUserAgentString());
        tab.addJavascriptInterface(new ArkPageBridge(), "EimzaNative");
        CookieManager.getInstance().setAcceptThirdPartyCookies(tab, true);
        if (WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
            WebViewCompat.addDocumentStartJavaScript(tab, arkPageHook + adaletPageHook,
                    new HashSet<>(Arrays.asList("https://uyap.gov.tr", "https://*.uyap.gov.tr",
                            "https://adalet.gov.tr", "https://*.adalet.gov.tr", "https://enabiz.gov.tr",
                            "https://*.enabiz.gov.tr", "https://saglik.gov.tr", "https://*.saglik.gov.tr",
                            "https://test.arksigner.com")));
            WebViewCompat.addDocumentStartJavaScript(tab, edevletPageHook,
                    new HashSet<>(Arrays.asList("https://turkiye.gov.tr", "https://*.turkiye.gov.tr")));
        }
        tab.setWebViewClient(webView.getWebViewClient());
        tab.setWebChromeClient(webView.getWebChromeClient());
        tab.setDownloadListener((downloadUrl, userAgent, contentDisposition, mimeType, contentLength) -> {
            if (isEdevletJnlp(Uri.parse(downloadUrl))) debugLog("e-Devlet JNLP indiriliyor; işlem kodu sayfadan alınacak");
            else try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(downloadUrl))); }
            catch (Exception error) { debugLog("İndirme bağlantısı açılamadı"); }
        });
        browserTabs.add(tab);
        browserTabGroups.put(tab, group == null || group.isEmpty() ? "Genel" : group);
        switchBrowserTab(tab);
        tab.loadUrl(url == null || url.isEmpty() ? "about:blank" : url);
        updateTabCount();
        return tab;
    }

    private void switchBrowserTab(WebView tab) {
        if (tab == null || webHost == null) return;
        webHost.removeAllViews();
        webHost.addView(tab, new FrameLayout.LayoutParams(-1, -1));
        activeWebView = tab;
        activePageUrl = tab.getUrl() == null ? "about:blank" : tab.getUrl();
        showAddress(activePageUrl);
        tab.onResume();
        tab.requestFocus();
    }

    private void showTabManager() {
        if (browserTabs.isEmpty()) createBrowserTab("about:blank", "Genel");
        Dialog dialog = new Dialog(this);
        LinearLayout shell = new LinearLayout(this);
        shell.setOrientation(LinearLayout.VERTICAL);
        shell.setPadding(dp(16), dp(14), dp(16), dp(14));
        shell.setBackgroundColor(darkMode ? Color.rgb(25, 30, 42) : Color.rgb(244, 247, 252));
        TextView title = sectionTitle("Sekmeler · " + browserTabs.size());
        title.setTextSize(20);
        shell.addView(title);

        LinearLayout groups = new LinearLayout(this);
        groups.setOrientation(LinearLayout.HORIZONTAL);
        java.util.LinkedHashSet<String> names = new java.util.LinkedHashSet<>(browserTabGroups.values());
        names.add("Genel");
        for (String name : names) groups.addView(tabGroupDropTarget(name, dialog));
        groups.addView(tabGroupDropTarget("＋ Yeni grup", dialog));
        android.widget.HorizontalScrollView groupScroll = new android.widget.HorizontalScrollView(this);
        groupScroll.addView(groups);
        shell.addView(groupScroll, new LinearLayout.LayoutParams(-1, dp(54)));

        LinearLayout cards = new LinearLayout(this);
        cards.setOrientation(LinearLayout.VERTICAL);
        for (WebView tab : new java.util.ArrayList<>(browserTabs)) cards.addView(tabCard(tab, dialog));
        ScrollView scroller = new ScrollView(this);
        scroller.addView(cards);
        shell.addView(scroller, new LinearLayout.LayoutParams(-1, 0, 1f));

        shell.addView(actionRow(action("＋ Yeni sekme", v -> {
            dialog.dismiss(); createBrowserTab("about:blank", "Genel");
        }), action("Kapat", v -> dialog.dismiss())));
        dialog.setContentView(shell);
        android.view.Window window = dialog.getWindow();
        if (window != null) window.setLayout(-1, -1);
        dialog.setOnShowListener(ignored -> {
            android.view.Window w = dialog.getWindow();
            if (w != null) w.setLayout(-1, -1);
        });
        dialog.show();
    }

    private View tabCard(WebView tab, Dialog dialog) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.HORIZONTAL);
        card.setGravity(Gravity.CENTER_VERTICAL);
        card.setPadding(dp(8), dp(8), dp(8), dp(8));
        card.setBackground(roundBackground(tab == activeWebView ? Color.rgb(225, 235, 255) : Color.WHITE,
                tab == activeWebView ? Color.rgb(55, 105, 220) : Color.rgb(210, 219, 233), 15));
        LinearLayout.LayoutParams outer = new LinearLayout.LayoutParams(-1, dp(112));
        outer.setMargins(0, dp(5), 0, dp(5));
        card.setLayoutParams(outer);
        ImageView preview = new ImageView(this);
        preview.setScaleType(ImageView.ScaleType.CENTER_CROP);
        Bitmap bitmap = browserTabPreviews.get(tab);
        if (bitmap != null && !bitmap.isRecycled()) preview.setImageBitmap(bitmap);
        else preview.setImageResource(R.drawable.ic_eimza_logo);
        card.addView(preview, new LinearLayout.LayoutParams(dp(116), dp(88)));
        LinearLayout words = new LinearLayout(this);
        words.setOrientation(LinearLayout.VERTICAL);
        words.setPadding(dp(10), 0, dp(5), 0);
        TextView tabTitle = new TextView(this);
        String label = tab.getTitle();
        if (label == null || label.trim().isEmpty()) label = "Yeni sekme";
        tabTitle.setText(label);
        tabTitle.setTextSize(15);
        tabTitle.setTextColor(Color.rgb(21, 31, 49));
        tabTitle.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        tabTitle.setMaxLines(2);
        TextView detail = statusText((browserTabGroups.get(tab) == null ? "Genel" : browserTabGroups.get(tab))
                + "\n" + ((tab.getUrl() == null || "about:blank".equals(tab.getUrl())) ? "Boş sayfa" : tab.getUrl()));
        detail.setPadding(0, dp(4), 0, 0);
        detail.setMaxLines(2);
        words.addView(tabTitle);
        words.addView(detail);
        card.addView(words, new LinearLayout.LayoutParams(0, -2, 1f));
        TextView close = browserIcon("×", v -> {
            closeBrowserTab(tab);
            dialog.dismiss();
            showTabManager();
        });
        close.setTextColor(Color.rgb(35, 45, 64));
        card.addView(close, new LinearLayout.LayoutParams(dp(42), dp(50)));
        card.setOnClickListener(v -> { switchBrowserTab(tab); dialog.dismiss(); });
        card.setOnLongClickListener(v -> {
            draggedBrowserTab = tab;
            return v.startDragAndDrop(ClipData.newPlainText("tab", "tab"),
                    new View.DragShadowBuilder(v), tab, 0);
        });
        card.setOnDragListener((view, event) -> {
            if (event.getAction() == DragEvent.ACTION_DROP && draggedBrowserTab != null
                    && draggedBrowserTab != tab) {
                browserTabs.remove(draggedBrowserTab);
                int target = browserTabs.indexOf(tab);
                browserTabs.add(Math.max(0, target), draggedBrowserTab);
                dialog.dismiss(); showTabManager();
                return true;
            }
            if (event.getAction() == DragEvent.ACTION_DRAG_ENDED) draggedBrowserTab = null;
            return true;
        });
        return card;
    }

    private View tabGroupDropTarget(String name, Dialog dialog) {
        TextView chip = new TextView(this);
        chip.setText(name);
        chip.setTextColor(darkMode ? Color.WHITE : Color.rgb(28, 43, 67));
        chip.setGravity(Gravity.CENTER);
        chip.setPadding(dp(14), 0, dp(14), 0);
        chip.setBackground(roundBackground(darkMode ? Color.rgb(48, 56, 75) : Color.WHITE,
                Color.rgb(120, 140, 175), 18));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-2, dp(40));
        params.setMargins(dp(3), dp(5), dp(3), dp(5));
        chip.setLayoutParams(params);
        chip.setOnDragListener((view, event) -> {
            if (event.getAction() != DragEvent.ACTION_DROP || draggedBrowserTab == null) return true;
            final WebView droppedTab = draggedBrowserTab;
            if (name.startsWith("＋")) {
                EditText input = new EditText(this);
                input.setHint("Grup adı");
                new AlertDialog.Builder(this).setTitle("Yeni sekme grubu").setView(input)
                        .setPositiveButton("Oluştur", (d, w) -> {
                            String value = input.getText().toString().trim();
                            browserTabGroups.put(droppedTab, value.isEmpty() ? "Genel" : value);
                            draggedBrowserTab = null; dialog.dismiss(); showTabManager();
                        }).setNegativeButton("İptal", null).show();
            } else {
                browserTabGroups.put(droppedTab, name);
                draggedBrowserTab = null; dialog.dismiss(); showTabManager();
            }
            return true;
        });
        if (!name.startsWith("＋")) chip.setOnLongClickListener(v -> {
            EditText input = new EditText(this);
            input.setText(name);
            input.selectAll();
            new AlertDialog.Builder(this).setTitle("Grubu yeniden adlandır").setView(input)
                    .setPositiveButton("Kaydet", (d, w) -> {
                        String renamed = input.getText().toString().trim();
                        if (renamed.isEmpty()) renamed = "Genel";
                        for (WebView tab : browserTabs)
                            if (name.equals(browserTabGroups.get(tab))) browserTabGroups.put(tab, renamed);
                        dialog.dismiss(); showTabManager();
                    }).setNegativeButton("İptal", null).show();
            return true;
        });
        return chip;
    }

    private void captureTabPreview(WebView tab) {
        if (tab == null) return;
        tab.post(() -> {
            try {
                int width = Math.max(1, tab.getWidth()), height = Math.max(1, tab.getHeight());
                Bitmap bitmap = Bitmap.createBitmap(360, 220, Bitmap.Config.RGB_565);
                Canvas canvas = new Canvas(bitmap);
                canvas.drawColor(Color.WHITE);
                canvas.scale(360f / width, 220f / height);
                tab.draw(canvas);
                Bitmap old = browserTabPreviews.put(tab, bitmap);
                if (old != null && old != bitmap && !old.isRecycled()) old.recycle();
            } catch (Throwable ignored) { }
        });
    }

    private void closeCurrentTab() {
        closeBrowserTab(activeWebView);
    }

    private void closeBrowserTab(WebView closing) {
        if (closing == null) return;
        int index = browserTabs.indexOf(closing);
        browserTabs.remove(closing);
        browserTabGroups.remove(closing);
        Bitmap preview = browserTabPreviews.remove(closing);
        if (preview != null && !preview.isRecycled()) preview.recycle();
        if (closing != webView) closing.destroy();
        if (browserTabs.isEmpty()) createBrowserTab("about:blank", "Genel");
        else switchBrowserTab(browserTabs.get(Math.max(0, Math.min(index, browserTabs.size() - 1))));
        updateTabCount();
    }

    private void groupCurrentTab() {
        if (activeWebView == null) return;
        EditText name = new EditText(this);
        name.setSingleLine(true);
        name.setHint("Örn. Sağlık, UYAP, İş");
        name.setText(browserTabGroups.get(activeWebView));
        new AlertDialog.Builder(this).setTitle("Sekme grubu").setView(name)
                .setPositiveButton("Kaydet", (d, w) -> {
                    String group = name.getText().toString().trim();
                    browserTabGroups.put(activeWebView, group.isEmpty() ? "Genel" : group);
                }).setNegativeButton("İptal", null).show();
    }

    private void showBrowserPrivacyInfo() {
        new AlertDialog.Builder(this).setTitle("Bağlantı ve imza koruması")
                .setMessage("TLS hataları engellenir. E-imza köprüsü yalnız izin verilen kamu alan adlarında çalışır; PIN sayfaya aktarılmaz.")
                .setPositiveButton("Tamam", null).show();
    }

    private View buildHelpPanel() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = panelRoot("Desteklenen E-İmza Tokenları ve Yardım");
        root.addView(infoCard("1. ArkSigner Arkİmza Token",
                "ArkSigner'ın resmi kriptografik tokenları (Feitian ePass2003, Atos CardOS 5.x, SafeNet/Gemalto IDPrime vb.) için tam gömülü yerel sürücü entegre edilmiştir. Doğrudan APDU ve PKCS#15 üzerinden çalışır."));
        root.addView(infoCard("2. TÜRKTRUST / TBB Kırmızı Token",
                "Türkiye Barolar Birliği (TBB) avukatlarına verilen kırmızı USB token (TÜRKTRUST lisanslı AKİS yongası) otomatik algılanır. CommandsV20/V25 ve Gezgin protokolleriyle yerel olarak desteklenir."));
        root.addView(infoCard("3. Kamu SM / TÜBİTAK (ATR19)",
                "TÜBİTAK UEKAE tarafından üretilen Kamu SM AKİS kartları ve ATR19 USB CCID okuyucu; T=1 blok protokolü ve otomatik IFSD müzakeresi ile desteklenir."));
        root.addView(infoCard("Hata ve Tanı Günlüğü (TXT)",
                "Herhangi bir sorun veya imza reddinde, 'Tanı Günlüğü (.txt)' butonuna basarak detaylı tanı dosyasını kaydedebilir veya paylaşarak teknik inceleme talep edebilirsiniz."));
        root.addView(infoCard("Portal ve UDF Desteği",
                "e-Devlet, Sağlık Bakanlığı OBS/Reçetem, UYAP Avukat/Vatandaş ve UDF dosya imzalama (CAdES-BES) tek bir uygulama üzerinden yürütülür."));
        root.addView(action("Ana menü", v -> showPanel(menuPanel)));
        scroll.addView(root);
        return scroll;
    }

    private View buildDebuggerPanel() {
        LinearLayout root = panelRoot("Tanı & Debugger");
        root.addView(actionRow(
                action("Tanı Raporunu Paylaş (.txt)", v -> exportDiagnosticTxt()),
                action("Panoya Kopyala", v -> copyDiagnosticReport())));
        root.addView(actionRow(
                action("Günlüğü Yenile", v -> refreshDebug()),
                action("Temizle", v -> {
                    DiagnosticLogger.clear();
                    synchronized (debugTrace) { debugTrace.setLength(0); }
                    refreshDebug();
                })));
        root.addView(actionRow(
                action("Kart Bilgisi & ATR", v -> showPanel(helpPanel)),
                action("Menüye Dön", v -> showPanel(menuPanel))));
        debugOutput = statusText("Debug logları hazırlanıyor…");
        debugOutput.setTextIsSelectable(true);
        debugOutput.setTypeface(android.graphics.Typeface.MONOSPACE);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(debugOutput);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1f));
        return root;
    }

    private void exportDiagnosticTxt() {
        try {
            String report = DiagnosticLogger.buildDiagnosticReport(this, akisBackend, usbProbe);
            java.io.File file = DiagnosticLogger.saveReportToFile(this, report);
            if (file != null) {
                Toast.makeText(this, "Tanı raporu kaydedildi:\n" + file.getName(), Toast.LENGTH_LONG).show();
            }
            DiagnosticLogger.shareReport(this, report);
        } catch (Exception e) {
            Toast.makeText(this, "Rapor oluşturulamadı: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private void copyDiagnosticReport() {
        try {
            String report = DiagnosticLogger.buildDiagnosticReport(this, akisBackend, usbProbe);
            DiagnosticLogger.copyReportToClipboard(this, report);
        } catch (Exception e) {
            Toast.makeText(this, "Kopyalanamadı: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }

    private View buildUdfPanel() {
        LinearLayout root = panelRoot("UYAP UDF imzalama");
        root.addView(infoCard("UDF dosyası", "Dosyayı açın, content.xml önizlemesini kontrol edin ve kart sertifikasıyla sign.sgn içeren imzalı UDF üretin."));
        root.addView(actionRow(action("UDF aç", v -> chooseUdf()), action("Menü", v -> showPanel(menuPanel))));
        udfStatus = statusText("Henüz UDF seçilmedi.");
        udfPreview = statusText("");
        udfPreview.setTextIsSelectable(true);
        root.addView(cardWith(udfStatus));
        udfPreviewWeb = new WebView(this);
        udfPreviewWeb.getSettings().setJavaScriptEnabled(false);
        udfPreviewWeb.setBackgroundColor(Color.WHITE);
        root.addView(udfPreviewWeb, new LinearLayout.LayoutParams(-1, 0, 1f));
        root.addView(cardWith(udfPreview));
        udfTimestampSwitch = new Switch(this);
        udfTimestampSwitch.setText("CAdES-T zaman damgası ekle");
        udfTimestampSwitch.setChecked(getPreferences(MODE_PRIVATE).getBoolean("udf_timestamp", false));
        udfTimestampSwitch.setOnCheckedChangeListener((button, checked) ->
                getPreferences(MODE_PRIVATE).edit().putBoolean("udf_timestamp", checked).apply());
        root.addView(cardWith(udfTimestampSwitch));
        root.addView(actionRow(action("Karttan imzala", v -> signSelectedUdf()), action("Tarayıcı", v -> showPanel(browserPanel))));
        return root;
    }

    private View buildSettingsPanel() {
        LinearLayout root = panelRoot("Ayarlar");
        root.addView(infoCard("Tema", "Açık veya koyu görünümü seçin."));
        root.addView(actionRow(action("Açık tema", v -> setDarkMode(false)),
                action("Koyu tema", v -> setDarkMode(true))));
        root.addView(infoCard("Masaüstü görünümü", "Tarayıcı araç çubuğundaki anahtar User-Agent, viewport ve yakınlaştırma ayarlarını birlikte değiştirir."));
        Switch autocomplete = new Switch(this);
        autocomplete.setText("Adres otomatik tamamlama");
        autocomplete.setChecked(addressAutocompleteEnabled);
        autocomplete.setOnCheckedChangeListener((button, checked) -> {
            addressAutocompleteEnabled = checked;
            getPreferences(MODE_PRIVATE).edit()
                    .putBoolean("address_autocomplete", checked).apply();
            refreshAddressSuggestions();
            debugLog("Adres otomatik tamamlama: " + checked);
        });
        root.addView(cardWith(autocomplete));
        root.addView(infoCard("Bağlantı güvenliği", "Uzak sunucularda yalnızca HTTPS kabul edilir. Şifresiz HTTP yalnızca cihaz içindeki 127.0.0.1/localhost ArkSigner köprüsüne izinlidir."));
        root.addView(infoCard("Dış tarayıcı", "Firefox/Chrome yalnızca kendi ArkSigner bağlayıcısı 127.0.0.1 veya HTTPS yerel servisini destekliyorsa uygulamayı görür. Android WebView içindeki köprü bundan bağımsızdır."));
        root.addView(infoCard("CAdES-T zaman damgası", "KamuSM üretim servisi resmî olarak HTTP/80 kullanır ve satın alma sonrası verilen müşteri numarası/parolayı ister. UYAP/Adalet için yayımlanmış ayrı bir TSA yoktur; bu profil KamuSM'yi kullanır. Arkİmza profilinde sözleşmenizde verilen RFC 3161 adresini girin."));
        tsaProviderInput = new Spinner(this);
        ArrayAdapter<String> tsaAdapter = new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_item, TSA_PROVIDERS);
        tsaAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        tsaProviderInput.setAdapter(tsaAdapter);
        int savedProvider = Math.max(0, Math.min(TSA_PROVIDERS.length - 1,
                getPreferences(MODE_PRIVATE).getInt("tsa_provider", 0)));
        tsaProviderInput.setSelection(savedProvider);
        root.addView(cardWith(tsaProviderInput));
        tsaUrlInput = new EditText(this);
        tsaUrlInput.setSingleLine(true);
        tsaUrlInput.setHint("https://tsa.example/... ");
        tsaUrlInput.setText(getPreferences(MODE_PRIVATE).getString("tsa_url", ""));
        root.addView(cardWith(tsaUrlInput));
        tsaUsernameInput = new EditText(this);
        tsaUsernameInput.setSingleLine(true);
        tsaUsernameInput.setHint("TSA kullanıcı adı (opsiyonel)");
        tsaUsernameInput.setText(getPreferences(MODE_PRIVATE).getString("tsa_username", ""));
        root.addView(cardWith(tsaUsernameInput));
        tsaPasswordInput = new EditText(this);
        tsaPasswordInput.setSingleLine(true);
        tsaPasswordInput.setHint("TSA parolası (oturum boyunca; kaydedilmez)");
        tsaPasswordInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        root.addView(cardWith(tsaPasswordInput));
        tsaProviderInput.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(android.widget.AdapterView<?> parent, View view, int position, long id) {
                if (position == 0 || position == 1) {
                    tsaUrlInput.setText("http://zd.kamusm.gov.tr");
                    tsaUsernameInput.setHint("KamuSM müşteri numarası");
                } else {
                    tsaUsernameInput.setHint("TSA kullanıcı adı (sağlayıcı verirse)");
                    String current = tsaUrlInput.getText().toString().trim();
                    if ("http://zd.kamusm.gov.tr".equalsIgnoreCase(current)) tsaUrlInput.setText("");
                }
            }
            @Override public void onNothingSelected(android.widget.AdapterView<?> parent) { }
        });
        root.addView(action("TSA adresini kaydet", v -> {
            String value = tsaUrlInput.getText().toString().trim();
            int provider = tsaProviderInput == null ? 3 : tsaProviderInput.getSelectedItemPosition();
            boolean officialKamuSm = (provider == 0 || provider == 1)
                    && "http://zd.kamusm.gov.tr".equalsIgnoreCase(value);
            if (!value.isEmpty() && !value.toLowerCase(Locale.ROOT).startsWith("https://") && !officialKamuSm) {
                Toast.makeText(this, "Özel TSA adresi HTTPS olmalı", Toast.LENGTH_SHORT).show();
                return;
            }
            String user = tsaUsernameInput == null ? "" : tsaUsernameInput.getText().toString().trim();
            if (officialKamuSm && !user.matches("[0-9]+")) {
                Toast.makeText(this, "KamuSM müşteri numarası sayısal olmalı", Toast.LENGTH_SHORT).show();
                return;
            }
            getPreferences(MODE_PRIVATE).edit().putInt("tsa_provider", provider)
                    .putString("tsa_url", value).putString("tsa_username", user).apply();
            Toast.makeText(this, "TSA ayarı kaydedildi", Toast.LENGTH_SHORT).show();
        }));
        if (adminDebug) {
            root.addView(infoCard("Anonim tanımsal telemetri", "PIN, TCKN, URL, sertifika ve imza içeriği gönderilmez. Firebase yapılandırması yoksa bu özellik etkisizdir."));
            root.addView(actionRow(action("İstatistikleri aç", v -> setTelemetry(true)),
                    action("İstatistikleri kapat", v -> setTelemetry(false))));
            root.addView(action("3 günlük çevrimdışı kilidi aç/kapat", v -> toggleOfflineLock()));
        }
        root.addView(action("İlk kullanım turunu yeniden göster", v -> {
            getPreferences(MODE_PRIVATE).edit().putBoolean("tutorial_seen", false).apply();
            maybeShowTutorial();
        }));
        root.addView(action("Ana menü", v -> showPanel(menuPanel)));
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.addView(root);
        return scroll;
    }

    private View buildAboutPanel() {
        LinearLayout root = panelRoot("Hakkında");
        root.addView(infoCard("E-İmza One · v0.3.1", "Türkiye'deki standart e-imza donanımlarını (ArkSigner Arkİmza, TÜRKTRUST TBB Kırmızı Token, Kamu SM ATR19) ek ara yazılım gerektirmeden yerel sürücülerle doğrudan destekleyen hepsi-bir-arada mobil imzalama platformu."));
        root.addView(infoCard("Gömülü Sürücüler", "1) ArkSigner Arkİmza (Feitian, CardOS, IDPrime PKCS#15)\n2) TÜRKTRUST / TBB Kırmızı Token (Baro Kart)\n3) Kamu SM / TÜBİTAK (ATR19 Mini Okuyucu)\nUSB CCID doğrudan APDU ve TPDU (T=1/T=0), RSA ve ECDSA algoritmaları."));
        root.addView(infoCard("Tanı & Debug Raporlama (.txt)", "Herhangi bir teknik aksaklık veya imza reddinde, 'Tanı Günlüğü (.txt)' butonundan sistem ve kart tanı verilerini içeren sansürlü TXT raporunu tek tıkla kaydedip paylaşabilirsiniz."));
        root.addView(infoCard("İmza profili", "UDF çıktısı varsayılan olarak CAdES-BES'tir. Ayarlardan RFC 3161 TSA adresi verilip UDF ekranındaki seçenek açılırsa imza CAdES-T'ye yükseltilir."));
        root.addView(action("Ana menü", v -> showPanel(menuPanel)));
        return root;
    }

    private LinearLayout panelRoot(String title) {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(16), dp(14), dp(16), dp(16));
        root.setBackgroundColor(Color.rgb(246, 248, 252));
        TextView heading = new TextView(this);
        heading.setText(title);
        heading.setTextSize(27);
        heading.setTextColor(Color.rgb(16, 24, 40));
        heading.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        heading.setPadding(0, 0, 0, dp(8));
        root.addView(heading);
        return root;
    }

    private LinearLayout card() {
        LinearLayout view = new LinearLayout(this);
        view.setOrientation(LinearLayout.VERTICAL);
        view.setPadding(dp(8), dp(7), dp(8), dp(7));
        view.setBackground(roundBackground(Color.WHITE, Color.rgb(222, 229, 239), 16));
        return view;
    }

    private View cardWith(View child) {
        LinearLayout box = card();
        box.addView(child);
        return box;
    }

    private View infoCard(String title, String body) {
        LinearLayout box = card();
        TextView heading = new TextView(this);
        heading.setText(title);
        heading.setTextSize(15);
        heading.setTextColor(Color.rgb(16, 24, 40));
        heading.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        TextView text = statusText(body);
        text.setPadding(0, dp(4), 0, dp(2));
        box.addView(heading);
        box.addView(text);
        box.setLayoutParams(marginParams(0, 0, 0, 9));
        return box;
    }

    private TextView sectionTitle(String text) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(13);
        view.setTextColor(Color.rgb(71, 91, 119));
        view.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        view.setPadding(dp(3), dp(10), dp(3), dp(5));
        return view;
    }

    private GradientDrawable roundBackground(int fill, int stroke, int radiusDp) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(fill);
        drawable.setCornerRadius(dp(radiusDp));
        drawable.setStroke(dp(1), stroke);
        return drawable;
    }

    private LinearLayout.LayoutParams marginParams(int left, int top, int right, int bottom) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.setMargins(dp(left), dp(top), dp(right), dp(bottom));
        return params;
    }

    private LinearLayout.LayoutParams weightParams(int widthDp) {
        return new LinearLayout.LayoutParams(dp(widthDp), dp(42));
    }

    private Button toolbarButton(String label, View.OnClickListener listener) {
        Button button = action(label, listener);
        button.setTextSize(12);
        button.setPadding(dp(2), 0, dp(2), 0);
        return button;
    }

    private void showPanel(View target) {
        View[] panels = {menuPanel, browserPanel, helpPanel, debuggerPanel, udfPanel, settingsPanel, aboutPanel};
        for (View panel : panels) if (panel != null) panel.setVisibility(panel == target ? View.VISIBLE : View.GONE);
        if (target == browserPanel && webView != null) webView.requestFocus();
        if (target == debuggerPanel) refreshDebug();
    }

    private void adminTap() {
        titleTaps++;
        if (titleTaps < 7) return;
        titleTaps = 0;
        adminDebug = !adminDebug;
        getPreferences(MODE_PRIVATE).edit().putBoolean("admin_debug", adminDebug).apply();
        Toast.makeText(this, adminDebug ? "Admin debugger açıldı" : "Admin debugger kapatıldı", Toast.LENGTH_SHORT).show();
        debugLog("Admin debugger: " + adminDebug);
    }

    private void appendDebug(String text) {
        DiagnosticLogger.d(DiagnosticLogger.Tag.APP, text);
        String line = new SimpleDateFormat("HH:mm:ss.SSS", Locale.ROOT).format(new Date()) + " " + text;
        synchronized (debugTrace) {
            if (debugTrace.length() > 24000) debugTrace.delete(0, Math.min(6000, debugTrace.length()));
            debugTrace.append(line).append('\n');
        }
        android.util.Log.d("EIMZA_DEBUG", text);
    }

    private void debugLog(String text) {
        appendDebug(text);
        runOnUiThread(this::refreshDebug);
    }

    private void refreshDebug() {
        if (debugOutput == null) return;
        try {
            String report = DiagnosticLogger.buildDiagnosticReport(this, akisBackend, usbProbe);
            debugOutput.setText(report);
        } catch (Exception ignored) {
            synchronized (debugTrace) { debugOutput.setText(debugTrace.toString()); }
        }
    }

    private void maybeShowTutorial() {
        if (getPreferences(MODE_PRIVATE).getBoolean("tutorial_seen", false)) return;
        if (tutorialOverlay == null) {
            tutorialOverlay = new FrameLayout(this);
            tutorialOverlay.setBackgroundColor(Color.argb(190, 0, 0, 0));
            rootScreen.addView(tutorialOverlay, new FrameLayout.LayoutParams(-1, -1));
        }
        showTutorialPage(0);
    }

    private void showTutorialPage(int page) {
        final String[] titles = {"1 / 5 · Kartı bağla", "2 / 5 · Tarayıcı", "3 / 5 · E-imza", "4 / 5 · UDF", "5 / 5 · Tanı ve ayarlar"};
        final String[] messages = {
                "ArkSigner Arkİmza, TÜRKTRUST TBB Kırmızı Token veya Kamu SM ATR19 USB tokenınızı OTG ile bağlayın. 'Kartı tara' ile okuyucu ve token otomatik algılanır; 'Kart & Sertifika Bilgisi' ile test edebilirsiniz.",
                "Adres çubuğuna portal yazın. Masaüstü anahtarı User-Agent ve viewport'u değiştirir; araç çubuğunda geri, ileri, yenile, ana sayfa ve üç nokta menüsü vardır. Sayfayı iki parmakla yakınlaştırabilirsiniz.",
                "ArkSigner veya e-Devlet kullanan destekli portalda imza isteği uygulama içindeki köprüye gelir. PIN yalnızca kart imzası için kullanılır; portalın kendi PIN penceresi ayrıca açılabilir.",
                "UYAP UDF ekranından ZIP tabanlı UDF açılır. content.xml görsel önizlenir; imzalama sonunda content.xml ve sign.sgn içeren yeni .udf kaydedilir.",
                "Tanı & Debugger menüsünden veya 'Tanı Günlüğü (.txt)' butonundan istediğiniz an detaylı sansürlü hata ve işlem raporunu TXT olarak dışa aktarabilir, teknik destek için paylaşabilirsiniz."
        };
        if (tutorialOverlay == null) return;
        tutorialOverlay.removeAllViews();
        LinearLayout card = card();
        card.setPadding(dp(20), dp(18), dp(20), dp(14));
        TextView title = new TextView(this);
        title.setText("E-İmza One  ·  " + titles[page]);
        title.setTextSize(20);
        title.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        title.setTextColor(Color.rgb(20, 35, 55));
        card.addView(title);
        TextView message = new TextView(this);
        message.setText(messages[page]);
        message.setTextSize(15);
        message.setTextColor(Color.rgb(65, 80, 100));
        message.setPadding(0, dp(10), 0, dp(12));
        card.addView(message);
        LinearLayout buttons = new LinearLayout(this);
        buttons.setGravity(Gravity.END | Gravity.CENTER_VERTICAL);
        Button skip = action("Atla", v -> finishTutorial());
        Button example = action("Örnek ekran", v -> tutorialExample(page));
        Button next = action(page == titles.length - 1 ? "Başla" : "İleri", v -> {
            if (page == titles.length - 1) finishTutorial(); else showTutorialPage(page + 1);
        });
        buttons.addView(skip, new LinearLayout.LayoutParams(0, -2, 1f));
        buttons.addView(example, new LinearLayout.LayoutParams(0, -2, 1f));
        buttons.addView(next, new LinearLayout.LayoutParams(0, -2, 1f));
        card.addView(buttons);
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(-1, -2, Gravity.BOTTOM);
        params.setMargins(dp(14), 0, dp(14), dp(22));
        tutorialOverlay.addView(card, params);
    }

    private void tutorialExample(int page) {
        if (page == 0) showPanel(menuPanel);
        else if (page == 1) showPanel(browserPanel);
        else if (page == 2) showPanel(helpPanel);
        else if (page == 3) showPanel(udfPanel);
        else showPanel(adminDebug ? debuggerPanel : settingsPanel);
        Toast.makeText(this, "Bu ekranı inceleyebilirsiniz; tur devam ediyor.", Toast.LENGTH_SHORT).show();
    }

    private void finishTutorial() {
        getPreferences(MODE_PRIVATE).edit().putBoolean("tutorial_seen", true).apply();
        if (tutorialOverlay != null) {
            rootScreen.removeView(tutorialOverlay);
            tutorialOverlay = null;
        }
        showPanel(menuPanel);
    }

    private void setDarkMode(boolean enabled) {
        darkMode = enabled;
        getPreferences(MODE_PRIVATE).edit().putBoolean("dark_mode", enabled).apply();
        applyTheme(findViewById(android.R.id.content));
        debugLog("Tema: " + (enabled ? "koyu" : "açık"));
    }

    private void setTelemetry(boolean enabled) {
        getPreferences(MODE_PRIVATE).edit().putBoolean("telemetry_enabled", enabled).apply();
        Telemetry.configure(this, enabled);
        Telemetry.event("telemetry_setting", enabled ? "enabled" : "disabled");
        Toast.makeText(this, enabled ? "Anonim tanı etkin" : "Anonim tanı kapalı", Toast.LENGTH_SHORT).show();
    }

    private void toggleOfflineLock() {
        boolean next = !getPreferences(MODE_PRIVATE).getBoolean("offline_lock_enabled", false);
        getPreferences(MODE_PRIVATE).edit().putBoolean("offline_lock_enabled", next).apply();
        Toast.makeText(this, next ? "3 günlük çevrimdışı kilit açık" : "Çevrimdışı kilit kapalı", Toast.LENGTH_SHORT).show();
    }

    private void enforceOfflinePolicy() {
        if (!getPreferences(MODE_PRIVATE).getBoolean("offline_lock_enabled", false)) return;
        long now = System.currentTimeMillis();
        if (isNetworkAvailable()) {
            getPreferences(MODE_PRIVATE).edit().putLong("last_online_ms", now).apply();
            return;
        }
        long last = getPreferences(MODE_PRIVATE).getLong("last_online_ms", now);
        if (now - last <= 3L * 24L * 60L * 60L * 1000L) return;
        new AlertDialog.Builder(this).setTitle("İnternet bağlantısı gerekli")
                .setMessage("Admin test politikasında uygulama üç günden uzun çevrimdışı kullanılamaz. İnternete bağlanıp tekrar açın.")
                .setPositiveButton("Kapat", (d, w) -> finish()).setOnCancelListener(d -> finish()).show();
    }

    private boolean isNetworkAvailable() {
        try {
            android.net.ConnectivityManager manager = (android.net.ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
            android.net.Network network = manager == null ? null : manager.getActiveNetwork();
            android.net.NetworkCapabilities capabilities = network == null ? null : manager.getNetworkCapabilities(network);
            return capabilities != null && capabilities.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET)
                    && capabilities.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_VALIDATED);
        } catch (Exception ignored) { return false; }
    }

    private void applyTheme(View view) {
        if (view == null) return;
        if ("browser_chrome".equals(view.getTag())) return;
        int background = darkMode ? Color.rgb(22, 28, 36) : Color.rgb(246, 248, 252);
        int foreground = darkMode ? Color.rgb(232, 238, 247) : Color.rgb(24, 34, 48);
        if (view instanceof WebView) return;
        if (view instanceof LinearLayout || view instanceof ScrollView || view instanceof FrameLayout) view.setBackgroundColor(background);
        if (view instanceof TextView) ((TextView) view).setTextColor(foreground);
        if (view instanceof Button) {
            Button button = (Button) view;
            button.setTextColor(darkMode ? Color.rgb(240, 245, 252) : Color.rgb(24, 50, 80));
            button.setBackground(roundBackground(darkMode ? Color.rgb(38, 50, 66) : Color.WHITE,
                    darkMode ? Color.rgb(78, 101, 132) : Color.rgb(205, 216, 231), 14));
        }
        if (view instanceof EditText) {
            EditText edit = (EditText) view;
            edit.setTextColor(foreground);
            edit.setHintTextColor(darkMode ? Color.rgb(165, 179, 198) : Color.rgb(110, 125, 145));
        }
        if (view instanceof android.view.ViewGroup) {
            android.view.ViewGroup group = (android.view.ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) applyTheme(group.getChildAt(i));
        }
    }

    private void applyUserAgent() {
        applyUserAgent(activePageUrl);
    }

    private void applyUserAgent(String targetUrl) {
        WebView target = activeWebView == null ? webView : activeWebView;
        if (target == null) return;
        String ua = mobileUserAgent == null ? target.getSettings().getUserAgentString() : mobileUserAgent;
        if (desktopMode && healthPortal(targetUrl)) {
            // WebView is Chromium. Spoofing Firefox makes OGN/OBS select a
            // browser-specific SSO path that does not match the actual engine.
            ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    + "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";
        } else if (desktopMode) {
            ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    + "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";
        } else if (healthPortal(targetUrl)) {
            // Keep the genuine Android WebView UA in mobile mode.
            ua = mobileUserAgent == null ? ua : mobileUserAgent;
        }
        target.getSettings().setUserAgentString(ua);
        target.getSettings().setUseWideViewPort(true);
        target.getSettings().setLoadWithOverviewMode(desktopMode);
        target.getSettings().setTextZoom(100);
        target.getSettings().setSupportZoom(true);
        target.getSettings().setBuiltInZoomControls(true);
        target.getSettings().setDisplayZoomControls(false);
        target.setInitialScale(desktopMode ? 100 : 0);
        debugLog("User-Agent modu: " + (desktopMode ? "desktop" : "mobil")
                + "; geniş görünüm=" + target.getSettings().getUseWideViewPort());
    }

    private void showBrowserMenu() {
        if (browserPanel == null) return;
        PopupMenu popup = new PopupMenu(this, menuOverflowAnchor == null ? addressBar : menuOverflowAnchor);
        popup.getMenu().add("Yeni sekme / boş sayfa").setOnMenuItemClickListener(item -> {
            createBrowserTab("about:blank", "Genel"); return true;
        });
        popup.getMenu().add("Sekmeler ve gruplar").setOnMenuItemClickListener(item -> {
            showTabManager(); return true;
        });
        popup.getMenu().add("Favorilere ekle").setOnMenuItemClickListener(item -> {
            addCurrentFavorite(); return true;
        });
        popup.getMenu().add("Favoriler").setOnMenuItemClickListener(item -> {
            showFavorites(); return true;
        });
        popup.getMenu().add("Geçmiş").setOnMenuItemClickListener(item -> {
            showHistory(); return true;
        });
        popup.getMenu().add(desktopMode ? "Mobil görünüme geç" : "Masaüstü görünümünü zorla")
                .setOnMenuItemClickListener(item -> {
                    desktopMode = !desktopMode;
                    if (desktopSwitch != null) desktopSwitch.setChecked(desktopMode);
                    applyUserAgent();
                    WebView target = activeWebView == null ? webView : activeWebView;
                    if (target != null && !activePageUrl.isEmpty()) target.reload();
                    return true;
                });
        popup.getMenu().add("UYAP UDF imzalama").setOnMenuItemClickListener(item -> {
            showPanel(udfPanel); return true;
        });
        popup.getMenu().add("e-Devlet işlem kodu gir").setOnMenuItemClickListener(item -> {
            promptEdevletTransactionCode(); return true;
        });
        popup.getMenu().add("Kart bilgisi / yardım").setOnMenuItemClickListener(item -> {
            showPanel(helpPanel); return true;
        });
        if (adminDebug) popup.getMenu().add("Debugger").setOnMenuItemClickListener(item -> {
            showPanel(debuggerPanel); return true;
        });
        popup.getMenu().add("Dış tarayıcıda aç").setOnMenuItemClickListener(item -> {
            openInExternalBrowser(); return true;
        });
        popup.getMenu().add("Eklentiler").setOnMenuItemClickListener(item -> {
            showExtensionCompatibility(); return true;
        });
        popup.getMenu().add("Çerezleri temizle").setOnMenuItemClickListener(item -> {
            CookieManager.getInstance().removeAllCookies(value -> debugLog("Çerezler temizlendi"));
            CookieManager.getInstance().flush();
            return true;
        });
        popup.getMenu().add("OBS oturumunu sıfırla").setOnMenuItemClickListener(item -> {
            resetObsSession(); return true;
        });
        popup.show();
    }

    private void addCurrentFavorite() {
        String url = activeWebView == null ? "" : activeWebView.getUrl();
        if (url == null || !(url.startsWith("http://") || url.startsWith("https://"))) {
            Toast.makeText(this, "Bu sayfa favorilere eklenemez", Toast.LENGTH_SHORT).show();
            return;
        }
        java.util.Set<String> stored = new java.util.HashSet<>(getPreferences(MODE_PRIVATE)
                .getStringSet("browser_favorites", java.util.Collections.emptySet()));
        stored.add(url);
        getPreferences(MODE_PRIVATE).edit().putStringSet("browser_favorites", stored).apply();
        Toast.makeText(this, "Favorilere eklendi", Toast.LENGTH_SHORT).show();
    }

    private void showFavorites() {
        java.util.ArrayList<String> favorites = new java.util.ArrayList<>(getPreferences(MODE_PRIVATE)
                .getStringSet("browser_favorites", java.util.Collections.emptySet()));
        java.util.Collections.sort(favorites);
        if (favorites.isEmpty()) {
            Toast.makeText(this, "Henüz favori yok", Toast.LENGTH_SHORT).show();
            return;
        }
        String[] labels = new String[favorites.size()];
        for (int i = 0; i < favorites.size(); i++) {
            Uri uri = Uri.parse(favorites.get(i));
            labels[i] = (uri.getHost() == null ? favorites.get(i) : uri.getHost()) + "\n" + favorites.get(i);
        }
        new AlertDialog.Builder(this).setTitle("Favoriler")
                .setItems(labels, (d, which) -> open(favorites.get(which)))
                .setNeutralButton("Tümünü temizle", (d, w) -> getPreferences(MODE_PRIVATE)
                        .edit().remove("browser_favorites").apply())
                .setNegativeButton("Kapat", null).show();
    }

    private void showExtensionCompatibility() {
        new AlertDialog.Builder(this).setTitle("Tarayıcı eklentileri")
                .setMessage("Android System WebView, Chrome/Chromium uzantı API'lerini yükleyemez. "
                        + "Bu nedenle .crx veya Manifest V2/V3 eklentilerini çalıştırmak güvenilir biçimde mümkün değildir. "
                        + "ArkSigner entegrasyonu uygulamanın izinli yerel köprüsüyle çalışır. Tam Chromium eklenti desteği "
                        + "için WebView yerine Chromium tabanlı ayrı bir tarayıcı motoru/forku gerekir.")
                .setPositiveButton("Tamam", null).show();
    }

    private void navigateAddress() {
        String value = addressBar == null ? "" : addressBar.getText().toString().trim();
        if (value.isEmpty()) return;
        if (!value.matches("(?i)^[a-z][a-z0-9+.-]*://.*$")) value = "https://" + value;
        open(value);
    }

    private void showAddress(String url) {
        if (addressBar == null) return;
        String value = url == null ? "" : url;
        if ("about:blank".equalsIgnoreCase(value) || value.startsWith("data:text/html")) value = "";
        addressBar.setText(value);
        addressBar.setSelection(addressBar.length());
    }

    private void showAddressEditor() {
        EditText editor = new EditText(this);
        editor.setSingleLine(true);
        String current = activeWebView == null ? "" : activeWebView.getUrl();
        if ("about:blank".equalsIgnoreCase(current)) current = "";
        editor.setText(current == null ? "" : current);
        editor.selectAll();
        new AlertDialog.Builder(this).setTitle("Adresi düzenle").setView(editor)
                .setNegativeButton("İptal", null)
                .setPositiveButton("Git", (dialog, which) -> {
                    addressBar.setText(editor.getText());
                    navigateAddress();
                }).show();
    }

    private void loadBrowserHistory() {
        browserHistory.clear();
        String raw = getPreferences(MODE_PRIVATE).getString("browser_history", "[]");
        try {
            org.json.JSONArray rows = new org.json.JSONArray(raw);
            for (int i = 0; i < rows.length(); i++) {
                String value = rows.optString(i, "");
                if (!value.isEmpty()) browserHistory.add(value);
            }
        } catch (Exception ignored) { }
    }

    private void recordHistory(String title, String url) {
        if (url == null || !(url.startsWith("https://") || url.startsWith("http://"))) return;
        browserHistory.remove(url);
        browserHistory.add(0, url);
        while (browserHistory.size() > 200) browserHistory.remove(browserHistory.size() - 1);
        getPreferences(MODE_PRIVATE).edit().putString("browser_history",
                new org.json.JSONArray(browserHistory).toString()).apply();
        refreshAddressSuggestions();
    }

    private void refreshAddressSuggestions() {
        if (addressBar == null) return;
        if (!addressAutocompleteEnabled) {
            addressBar.dismissDropDown();
            addressBar.setAdapter(null);
            return;
        }
        addressBar.setThreshold(1);
        addressBar.setAdapter(new ArrayAdapter<>(this,
                android.R.layout.simple_dropdown_item_1line, browserHistory));
    }

    private void hardenWebSettings(WebSettings settings) {
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setSaveFormData(false);
        settings.setGeolocationEnabled(false);
        settings.setMediaPlaybackRequiresUserGesture(true);
    }

    private static boolean isLoopbackHost(String host) {
        if (host == null) return false;
        return "localhost".equalsIgnoreCase(host) || "127.0.0.1".equals(host)
                || "::1".equals(host) || "[::1]".equals(host);
    }

    private static boolean isArkSignerLaunch(Uri uri) {
        return uri != null && "arksigner".equalsIgnoreCase(uri.getScheme());
    }

    /**
     * ArkSigner pages probe their desktop helper with arksigner:open.  The
     * Android bridge is already installed, so attempting to navigate a WebView
     * to that custom scheme only destroys the working portal page.
     */
    private boolean handleArkSignerLaunch(WebView target, Uri uri) {
        if (!isArkSignerLaunch(uri)) return false;
        if (target != null) target.stopLoading();
        setPortalStatus("ArkSigner uygulama içi köprüyle bağlı");
        debugLog("arksigner:open harici uygulama navigasyonu engellendi; yerel köprü korunuyor");
        return true;
    }

    private void showHistory() {
        if (browserHistory.isEmpty()) {
            Toast.makeText(this, "Geçmiş boş", Toast.LENGTH_SHORT).show();
            return;
        }
        String[] rows = browserHistory.toArray(new String[0]);
        new AlertDialog.Builder(this).setTitle("Geçmiş")
                .setItems(rows, (dialog, which) -> open(rows[which]))
                .setNeutralButton("Temizle", (dialog, which) -> {
                    browserHistory.clear();
                    getPreferences(MODE_PRIVATE).edit().remove("browser_history").apply();
                    refreshAddressSuggestions();
                }).setNegativeButton("Kapat", null).show();
    }

    private void applyViewport(WebView target) {
        if (target == null) return;
        String script = desktopMode
                ? "(function(){var m=document.querySelector('meta[name=viewport]');if(!m){m=document.createElement('meta');m.name='viewport';document.head&&document.head.appendChild(m);}if(m)m.content='width=1280, initial-scale=1';document.documentElement.style.minWidth='1280px';})()"
                : "(function(){var m=document.querySelector('meta[name=viewport]');if(m)m.content='width=device-width, initial-scale=1';document.documentElement.style.minWidth='';})()";
        target.evaluateJavascript(script, null);
    }

    private void diagnoseHealthSso(WebView target, String url) {
        if (target == null || url == null || !url.contains("/Account/SsoLogin")) return;
        diagnoseCookieNames(url);
        String script = "(function(){"
                + "function path(u){try{var x=new URL(u,location.href);return x.origin+x.pathname;}catch(e){return '';}}"
                + "var b=((document.body&&document.body.innerText)||'').replace(/\\s+/g,' ').slice(0,600)"
                + ".replace(/[A-Za-z0-9+\\/=_%-]{80,}/g,'[gizli]');"
                + "var f=[].slice.call(document.forms).map(function(x){return {method:x.method||'',action:path(x.action||location.href),inputs:[].slice.call(x.elements||[]).map(function(i){return {name:(i.name||'').slice(0,60),type:(i.type||'').slice(0,30)};}).slice(0,20)};});"
                + "var m=document.querySelector('meta[http-equiv=refresh]');"
                + "var n=Number(window.__eimzaObsErrorLine||0),c='';"
                + "if(n){var l=(document.documentElement.outerHTML||'').split(/\\n/);c=l.slice(Math.max(0,n-3),Math.min(l.length,n+2)).join('\\n');}"
                + "c=c.replace(/([?&]q=)[^\\\"'&<>\\s]+/gi,'$1[gizli]')"
                + ".replace(/value=(['\\\"])[\\s\\S]*?\\1/gi,'value=\\\"[gizli]\\\"')"
                + ".replace(/\\b\\d{11}\\b/g,'[tckn]').replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}/gi,'[eposta]')"
                + ".replace(/[A-Za-z0-9+\\/=_%-]{40,}/g,'[uzun-deger]').slice(0,1400);"
                + "var sm='',ss=[].slice.call(document.scripts).map(function(s){return s.text||'';}).join('\\n');"
                + "var pi=ss.search(/248\\s*51\\s*51/);if(pi>=0){var ps=ss.lastIndexOf(\"'\",pi),pe=ss.indexOf(\"'\",pi);if(ps>=0&&pe>pi)sm=ss.slice(ps+1,pe);else sm=ss.slice(Math.max(0,pi-900),Math.min(ss.length,pi+120));}"
                + "sm=sm.replace(/\\s+/g,' ').replace(/\\b\\d{11}\\b/g,'[tckn]').replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}/gi,'[eposta]').replace(/[A-Za-z0-9+\\/=_%-]{40,}/g,'[uzun-deger]').slice(0,1200);"
                + "return JSON.stringify({title:document.title,ready:document.readyState,body:b,forms:f,refresh:m?(m.content||''):'',errorLine:n,errorColumn:Number(window.__eimzaObsErrorColumn||0),serverMessage:sm,errorContext:c});})()";
        target.evaluateJavascript(script, value -> {
            if (value == null) return;
            String safe = value.replaceAll("[A-Za-z0-9+/=_%-]{100,}", "[gizli]")
                    .replaceAll("[\\r\\n\\t]", " ");
            debugLog("SSO sayfa tanısı: " + safe.substring(0, Math.min(1800, safe.length())));
        });
    }

    /** Log cookie names only; values may contain authentication secrets. */
    private void diagnoseCookieNames(String url) {
        if (!adminDebug || url == null) return;
        String raw = CookieManager.getInstance().getCookie(url);
        if (raw == null || raw.trim().isEmpty()) {
            debugLog("SSO çerez tanısı: çerez yok");
            return;
        }
        java.util.LinkedHashSet<String> names = new java.util.LinkedHashSet<>();
        for (String item : raw.split(";")) {
            int equals = item.indexOf('=');
            String name = (equals < 0 ? item : item.substring(0, equals)).trim();
            if (!name.isEmpty() && name.length() < 80) names.add(name);
        }
        debugLog("SSO çerez adları: " + TextUtils.join(",", names));
    }

    private boolean rejectDuplicateObsCallback(Uri uri) {
        if (uri == null || !"obs.saglik.gov.tr".equalsIgnoreCase(uri.getHost())
                || !"/Account/SsoLogin".equalsIgnoreCase(uri.getPath())
                || uri.getQueryParameter("code") == null) return false;
        String current = uri.toString();
        long now = System.currentTimeMillis();
        if (current.equals(lastObsCallbackUrl) && now - lastObsCallbackAt < 30000L) {
            debugLog("OBS tek kullanımlık callback tekrar yüklenmesi engellendi");
            return true;
        }
        lastObsCallbackUrl = current;
        lastObsCallbackAt = now;
        CookieManager.getInstance().flush();
        return false;
    }

    private void resetObsSession() {
        CookieManager.getInstance().removeSessionCookies(value -> {
            CookieManager.getInstance().flush();
            lastObsCallbackUrl = "";
            lastObsCallbackAt = 0L;
            runOnUiThread(() -> {
                if (activeWebView != null) activeWebView.clearCache(false);
                open("https://obs.saglik.gov.tr/Account/Login");
                Toast.makeText(this, "OBS oturumu sıfırlandı", Toast.LENGTH_SHORT).show();
            });
        });
    }

    private void goBack() { if (activeWebView != null && activeWebView.canGoBack()) activeWebView.goBack(); }
    private void goForward() { if (activeWebView != null && activeWebView.canGoForward()) activeWebView.goForward(); }
    private void reloadPage() { if (activeWebView != null) { showingPortalError = false; activeWebView.reload(); } }

    private void openInExternalBrowser() {
        String url = activePageUrl;
        if (url == null || !(url.startsWith("http://") || url.startsWith("https://"))) return;
        try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); }
        catch (Exception e) { debugLog("Dış tarayıcı açılamadı: " + e.getClass().getSimpleName()); }
    }

    private void chooseUdf() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        startActivityForResult(intent, REQUEST_UDF_OPEN);
    }

    private void signSelectedUdf() {
        if (selectedUdfContent == null || selectedUdfContent.length == 0) {
            Toast.makeText(this, "Önce bir UDF dosyası açın.", Toast.LENGTH_SHORT).show();
            return;
        }
        signerWorker.execute(() -> {
            Telemetry.event("udf_sign_start");
            try {
                List<AkisSignerBackend.ArkCertificate> certs = akisBackend.arkCertificates();
                runOnUiThread(() -> chooseUdfCertificate(certs));
            } catch (SignerBackend.SignerException e) {
                runOnUiThread(() -> udfStatus.setText("Kart sertifikası okunamadı: " + e.getMessage()));
            }
        });
    }

    private void chooseUdfCertificate(List<AkisSignerBackend.ArkCertificate> certs) {
        if (certs.isEmpty()) { udfStatus.setText("Kartta kullanılabilir sertifika yok."); return; }
        String[] labels = new String[certs.size()];
        for (int i = 0; i < certs.size(); i++) labels[i] = certs.get(i).subjectCN + " · " + certs.get(i).certificate.getPublicKey().getAlgorithm();
        new AlertDialog.Builder(this).setTitle("UDF sertifikası").setItems(labels, (d, which) -> askUdfPin(certs.get(which)))
                .setNegativeButton("İptal", null).show();
    }

    private void askUdfPin(AkisSignerBackend.ArkCertificate cert) {
        EditText pin = new EditText(this);
        pin.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        boolean timestampRequested = udfTimestampSwitch != null && udfTimestampSwitch.isChecked();
        String tsaUrl = getPreferences(MODE_PRIVATE).getString("tsa_url", "").trim();
        String tsaUsername = getPreferences(MODE_PRIVATE).getString("tsa_username", "").trim();
        char[] tsaPassword = tsaPasswordInput == null ? new char[0]
                : tsaPasswordInput.getText().toString().toCharArray();
        if (timestampRequested && tsaUrl.isEmpty()) {
            udfStatus.setText("CAdES-T seçili fakat Ayarlar bölümünde TSA adresi yok.");
            return;
        }
        new AlertDialog.Builder(this).setTitle("Kart PIN'i").setMessage("UDF içindeki content.xml, sign.sgn olarak "
                + (timestampRequested ? "CAdES-T" : "CAdES-BES") + " detached imzalanacak.")
                .setView(pin).setNegativeButton("İptal", (d, w) -> Arrays.fill(tsaPassword, '\0'))
                .setOnCancelListener(d -> Arrays.fill(tsaPassword, '\0'))
                .setPositiveButton("İmzala", (d, w) -> {
                    char[] secret = pin.getText().toString().toCharArray();
                    udfStatus.setText("UDF imzalanıyor…");
                    signerWorker.execute(() -> {
                        try {
                            byte[] signed = CadesSupport.sign(selectedUdfContent, cert.id, cert.certificate, secret, akisBackend, false);
                            if (timestampRequested) signed = CadesSupport.addTimestamp(
                                    signed, tsaUrl, tsaUsername, tsaPassword);
                            pendingSignedUdf = buildSignedUdf(selectedUdfBytes, selectedUdfContent, signed);
                            runOnUiThread(() -> {
                                udfStatus.setText("İmzalı UDF hazır: " + pendingSignedUdf.length + " bayt. Kaydedilecek yeri seçin.");
                                Intent out = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                                out.addCategory(Intent.CATEGORY_OPENABLE);
                                out.setType("application/octet-stream");
                                String cleanName = documentDisplayName(selectedUdfName);
                                String title = cleanName.toLowerCase(Locale.ROOT).endsWith(".udf")
                                        ? cleanName : cleanName + ".udf";
                                out.putExtra(Intent.EXTRA_TITLE, title);
                                startActivityForResult(out, REQUEST_UDF_SAVE);
                            });
                        } catch (Exception e) {
                            Arrays.fill(secret, '\0');
                            runOnUiThread(() -> udfStatus.setText("UDF imzası başarısız: " + e.getMessage()));
                        } finally {
                            Arrays.fill(tsaPassword, '\0');
                            runOnUiThread(() -> { if (tsaPasswordInput != null) tsaPasswordInput.setText(""); });
                        }
                    });
                }).show();
    }

    private void loadUdf(Uri uri) {
        try (java.io.InputStream in = getContentResolver().openInputStream(uri);
             java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192]; int n;
            while (in != null && (n = in.read(buffer)) >= 0) out.write(buffer, 0, n);
            selectedUdfBytes = out.toByteArray();
            selectedUdfName = documentDisplayName(uri.getLastPathSegment());
            selectedUdfContent = extractUdfContent(selectedUdfBytes);
            udfStatus.setText("Açıldı: " + selectedUdfName + " · " + selectedUdfBytes.length + " bayt");
            udfPreview.setText("content.xml · " + selectedUdfContent.length + " bayt · görsel önizleme hazır");
            renderUdfVisual(selectedUdfContent);
            String signatureInfo = inspectUdfSignature(selectedUdfBytes);
            if (!signatureInfo.isEmpty()) udfPreview.append("\n\n" + signatureInfo);
            showPanel(udfPanel);
            debugLog("UDF açıldı: " + selectedUdfName + " (" + selectedUdfBytes.length + " bayt)");
            Telemetry.event("udf_open");
        } catch (Exception e) { udfStatus.setText("UDF açılamadı: " + e.getMessage()); }
    }

    private String documentDisplayName(String raw) {
        if (raw == null || raw.trim().isEmpty()) return "uyap.udf";
        String name = raw.replace('\\', '/');
        int slash = name.lastIndexOf('/');
        if (slash >= 0) name = name.substring(slash + 1);
        // Android DocumentsProvider often returns primary:Download/file.udf.
        int colon = name.lastIndexOf(':');
        if (colon >= 0) name = name.substring(colon + 1);
        name = name.replaceAll("[\\r\\n\\t]", "_").trim();
        return name.isEmpty() ? "uyap.udf" : name;
    }

    private byte[] extractUdfContent(byte[] bytes) throws java.io.IOException {
        try (java.util.zip.ZipInputStream zip = new java.util.zip.ZipInputStream(new ByteArrayInputStream(bytes))) {
            java.util.zip.ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                if (!entry.isDirectory() && "content.xml".equalsIgnoreCase(entry.getName())) {
                    java.io.ByteArrayOutputStream xml = new java.io.ByteArrayOutputStream();
                    byte[] buffer = new byte[4096]; int n;
                    while ((n = zip.read(buffer)) >= 0) xml.write(buffer, 0, n);
                    return xml.toByteArray();
                }
            }
        } catch (java.util.zip.ZipException notZip) {
            return bytes;
        }
        return bytes;
    }

    private byte[] extractUdfEntry(byte[] bytes, String wanted) throws java.io.IOException {
        try (java.util.zip.ZipInputStream zip = new java.util.zip.ZipInputStream(new ByteArrayInputStream(bytes))) {
            java.util.zip.ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                if (entry.isDirectory() || !wanted.equalsIgnoreCase(entry.getName())) continue;
                java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
                byte[] buffer = new byte[4096]; int n;
                while ((n = zip.read(buffer)) >= 0) out.write(buffer, 0, n);
                return out.toByteArray();
            }
        } catch (java.util.zip.ZipException ignored) { }
        return null;
    }

    private String inspectUdfSignature(byte[] bytes) {
        try {
            byte[] sign = extractUdfEntry(bytes, "sign.sgn");
            if (sign == null || sign.length == 0) return "İmza: yok (imzasız UDF)";
            CMSSignedData cms = new CMSSignedData(new org.bouncycastle.cms.CMSProcessableByteArray(selectedUdfContent), sign);
            java.util.Collection<?> signers = cms.getSignerInfos().getSigners();
            StringBuilder info = new StringBuilder("İmza: CAdES/CMS · ").append(signers.size()).append(" imzacı");
            boolean timestamp = false;
            String timestampTime = "";
            for (Object value : signers) {
                SignerInformation signer = (SignerInformation) value;
                org.bouncycastle.asn1.cms.AttributeTable unsigned = signer.getUnsignedAttributes();
                org.bouncycastle.asn1.cms.Attribute stampAttribute = unsigned == null ? null
                        : unsigned.get(org.bouncycastle.asn1.pkcs.PKCSObjectIdentifiers.id_aa_signatureTimeStampToken);
                if (stampAttribute != null) {
                    timestamp = true;
                    try {
                        org.bouncycastle.cms.CMSSignedData stampCms = new org.bouncycastle.cms.CMSSignedData(
                                stampAttribute.getAttrValues().getObjectAt(0).toASN1Primitive().getEncoded());
                        org.bouncycastle.tsp.TimeStampToken token = new org.bouncycastle.tsp.TimeStampToken(stampCms);
                        timestampTime = token.getTimeStampInfo().getGenTime().toInstant().toString();
                    } catch (Exception ignored) { }
                }
                info.append("\nİmza algoritması: ").append(signer.getEncryptionAlgOID());
                info.append(" / özet: ").append(signer.getDigestAlgOID());
            }
            info.append("\nİmza profili: ").append(timestamp ? "CAdES-T" : "CAdES-BES");
            info.append("\nZaman damgası: ").append(timestamp
                    ? (timestampTime.isEmpty() ? "var" : timestampTime)
                    : "yok");
            info.append("\nİmza dosyası: ").append(sign.length).append(" bayt");
            return info.toString();
        } catch (Exception e) {
            return "İmza: sign.sgn bulundu fakat CMS olarak ayrıştırılamadı (" + e.getClass().getSimpleName() + ")";
        }
    }

    private String previewUdf(byte[] bytes, String name) throws java.io.IOException {
        byte[] previewBytes = extractUdfContent(bytes);
        int previewLength = Math.min(previewBytes.length, 16000);
        return new String(previewBytes, 0, previewLength, StandardCharsets.UTF_8).replace('\0', ' ');
    }

    private void renderUdfVisual(byte[] content) {
        if (udfPreviewWeb == null || content == null) return;
        final String source = new String(content, StandardCharsets.UTF_8);
        String html;
        try {
            javax.xml.parsers.DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setNamespaceAware(false);
            try { factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true); } catch (Exception ignored) { }
            org.w3c.dom.Document document = factory.newDocumentBuilder().parse(new ByteArrayInputStream(content));
            StringBuilder body = new StringBuilder();
            appendUdfNodes(document.getDocumentElement(), body);
            if (body.length() == 0) body.append("<pre>").append(escapeHtml(source)).append("</pre>");
            html = "<html><head><meta name='viewport' content='width=device-width,initial-scale=1'><style>"
                    + "body{font-family:sans-serif;padding:18px;color:#182230;background:#fff;line-height:1.55}"
                    + "p{margin:0 0 10px;white-space:pre-wrap}pre{white-space:pre-wrap;word-break:break-word}"
                    + "</style></head><body>" + body + "</body></html>";
        } catch (Exception invalidXml) {
            html = "<html><head><meta name='viewport' content='width=device-width,initial-scale=1'></head><body><pre>"
                    + escapeHtml(source) + "</pre></body></html>";
            udfPreview.setText("content.xml XML olarak ayrıştırılamadı; ham içerik gösteriliyor.");
        }
        udfPreviewWeb.loadDataWithBaseURL(null, html, "text/html", "UTF-8", null);
    }

    private void appendUdfNodes(Node node, StringBuilder out) {
        if (node == null) return;
        String name = node.getNodeName() == null ? "" : node.getNodeName().toLowerCase(Locale.ROOT);
        if (node.getNodeType() == Node.TEXT_NODE) {
            String text = node.getNodeValue() == null ? "" : node.getNodeValue().trim();
            if (!text.isEmpty()) out.append(escapeHtml(text));
            return;
        }
        boolean paragraph = name.contains("paragraph") || name.equals("p") || name.contains("line");
        if (paragraph) out.append("<p>");
        NodeList children = node.getChildNodes();
        for (int i = 0; i < children.getLength(); i++) appendUdfNodes(children.item(i), out);
        if (paragraph) out.append("</p>");
    }

    private static String escapeHtml(String text) {
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace("\"", "&quot;").replace("'", "&#39;");
    }

    private byte[] buildSignedUdf(byte[] original, byte[] content, byte[] signature) throws java.io.IOException {
        java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
        java.util.zip.ZipOutputStream zip = new java.util.zip.ZipOutputStream(out, StandardCharsets.UTF_8);
        boolean copiedContent = false;
        try {
            try (java.util.zip.ZipInputStream in = new java.util.zip.ZipInputStream(new ByteArrayInputStream(original))) {
                java.util.zip.ZipEntry entry;
                byte[] buffer = new byte[8192];
                while ((entry = in.getNextEntry()) != null) {
                    String name = entry.getName();
                    if (entry.isDirectory() || "sign.sgn".equalsIgnoreCase(name)) continue;
                    if (name.contains("..") || name.startsWith("/")) continue;
                    zip.putNextEntry(new java.util.zip.ZipEntry(name));
                    int n;
                    while ((n = in.read(buffer)) >= 0) zip.write(buffer, 0, n);
                    zip.closeEntry();
                    if ("content.xml".equalsIgnoreCase(name)) copiedContent = true;
                }
            } catch (java.util.zip.ZipException notZip) {
                // A plain XML/document is also accepted as input and becomes content.xml.
            }
            if (!copiedContent) {
                zip.putNextEntry(new java.util.zip.ZipEntry("content.xml"));
                zip.write(content);
                zip.closeEntry();
            }
            zip.putNextEntry(new java.util.zip.ZipEntry("sign.sgn"));
            zip.write(signature);
            zip.closeEntry();
        } finally {
            zip.close();
        }
        return out.toByteArray();
    }

    private View buildLegacyView() {
        FrameLayout screen = new FrameLayout(this);
        LinearLayout root = new LinearLayout(this);
        ScrollView menu = new ScrollView(this);
        menu.addView(root);
        menuPanel = menu;
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(246, 248, 252));

        TextView title = new TextView(this);
        title.setText("E-İmza One · 0.2.8");
        title.setTextSize(22);
        title.setTextColor(Color.rgb(16, 24, 40));
        title.setPadding(dp(18), dp(14), dp(18), dp(4));
        root.addView(title);

        readerStatus = statusText("USB okuyucu aranıyor…");
        root.addView(readerStatus);

        signerStatus = statusText("Tek uygulama içi kart imzalayıcı hazır; portal çağrıları için kartı bağlayın");
        root.addView(signerStatus);

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.VERTICAL);
        actions.setPadding(dp(10), 0, dp(10), dp(4));
        actions.addView(actionRow(action("Okuyucuyu tara", v -> usbProbe.scan()),
                action("Sertifikaları oku", v -> readCertificates())));
        actions.addView(actionRow(action("e-Nabız", v -> open("https://enabiz.gov.tr/")),
                action("Reçetem", v -> openDesktop("https://recetem.enabiz.gov.tr/"))));
        actions.addView(actionRow(action("UYAP Avukat", v -> open("https://avukat.uyap.gov.tr/")), new View(this)));
        root.addView(actions);
        arkDiagnostics = statusText("Portal tanısı: henüz imza isteği gelmedi");
        arkDiagnostics.setTextIsSelectable(true);
        root.addView(arkDiagnostics);

        LinearLayout browser = new LinearLayout(this);
        browser.setOrientation(LinearLayout.VERTICAL);
        browser.setBackgroundColor(Color.WHITE);
        browserPanel = browser;
        browser.addView(actionRow(action("Kart / Menü", v -> {
            browserPanel.setVisibility(View.GONE);
            menuPanel.setVisibility(View.VISIBLE);
        }), action("Yenile", v -> {
            showingPortalError = false;
            webView.reload();
        })));
        portalStatus = statusText("Portal açılıyor…");
        portalStatus.setPadding(dp(18), dp(3), dp(18), dp(3));
        portalStatus.setSingleLine(true);
        portalStatus.setEllipsize(TextUtils.TruncateAt.MIDDLE);
        browser.addView(portalStatus);

        webView = new WebView(this);
        webView.setBackgroundColor(Color.WHITE);
        WebSettings webSettings = webView.getSettings();
        webSettings.setJavaScriptEnabled(true);
        webSettings.setDomStorageEnabled(true);
        webSettings.setSafeBrowsingEnabled(true);
        hardenWebSettings(webSettings);
        webSettings.setUseWideViewPort(true);
        webSettings.setLoadWithOverviewMode(true);
        webSettings.setSupportMultipleWindows(true);
        webSettings.setJavaScriptCanOpenWindowsAutomatically(true);
        mobileUserAgent = webSettings.getUserAgentString();
        webView.addJavascriptInterface(new ArkPageBridge(), "EimzaNative");
        // Document-start injection is a newer WebView feature. Older Android System
        // WebView builds do not implement it; never let this optional hook prevent the
        // browser itself from being constructed. onPageFinished installs the hooks too.
        if (WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
            WebViewCompat.addDocumentStartJavaScript(webView, arkPageHook + adaletPageHook,
                    new HashSet<>(Arrays.asList("https://uyap.gov.tr", "https://*.uyap.gov.tr",
                            "https://adalet.gov.tr", "https://*.adalet.gov.tr",
                            "https://yargitay.gov.tr", "https://*.yargitay.gov.tr",
                            "https://danistay.gov.tr", "https://*.danistay.gov.tr",
                            "https://enabiz.gov.tr", "https://*.enabiz.gov.tr",
                            "https://saglik.gov.tr", "https://*.saglik.gov.tr",
                            "https://test.arksigner.com")));
        }
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true);
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onCreateWindow(WebView view, boolean isDialog,
                                                    boolean isUserGesture, Message resultMsg) {
                WebView popup = new WebView(MainActivity.this);
                popup.getSettings().setJavaScriptEnabled(true);
                popup.getSettings().setDomStorageEnabled(true);
                popup.getSettings().setUserAgentString(webView.getSettings().getUserAgentString());
                popup.setWebViewClient(new WebViewClient() {
                    @Override public void onPageStarted(WebView child, String url,
                                                        android.graphics.Bitmap icon) {
                        super.onPageStarted(child, url, icon);
                        child.stopLoading();
                        setPortalStatus("Açılıyor: " + url);
                        webView.loadUrl(url);
                    }
                });
                WebView.WebViewTransport transport = (WebView.WebViewTransport) resultMsg.obj;
                transport.setWebView(popup);
                resultMsg.sendToTarget();
                return true;
            }
        });
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String scheme = request.getUrl().getScheme();
                if ("https".equalsIgnoreCase(scheme)) return false;
                if ("http".equalsIgnoreCase(scheme)) {
                    String host = request.getUrl().getHost();
                    if (host != null && (host.equalsIgnoreCase("gov.tr")
                            || host.toLowerCase(Locale.ROOT).endsWith(".gov.tr"))) {
                        android.net.Uri secure = request.getUrl().buildUpon().scheme("https").build();
                        setPortalStatus("HTTPS adresine yönlendiriliyor: " + secure);
                        view.loadUrl(secure.toString());
                    } else {
                        setPortalStatus("Güvenlik nedeniyle HTTP bağlantısı engellendi: " + request.getUrl());
                    }
                    return true;
                }
                setPortalStatus("Desteklenmeyen bağlantı türü: " + scheme);
                return true;
            }

            @Override
            public void onReceivedSslError(WebView view, SslErrorHandler handler,
                                           android.net.http.SslError error) {
                handler.cancel();
                showPortalError("Güvenli bağlantı kurulamadı (TLS)", error.getUrl());
            }

            @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap icon) {
                super.onPageStarted(view, url, icon);
                activePageUrl = url == null ? "" : url;
                if (!showingPortalError) setPortalStatus("Yükleniyor: " + url);
            }

            @Override public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                if (showingPortalError) return;
                setPortalStatus("Açık: " + url);
                if (allowedOrigin(url)) {
                    view.evaluateJavascript(arkPageHook, null);
                    if (adaletOrigin(url)) view.evaluateJavascript(adaletPageHook, null);
                }
            }

            @Override public void onReceivedError(WebView view, WebResourceRequest request,
                                                  WebResourceError error) {
                super.onReceivedError(view, request, error);
                if (request.isForMainFrame()) {
                    showPortalError("Sayfa yüklenemedi (" + error.getErrorCode() + "): "
                            + error.getDescription(), request.getUrl().toString());
                }
            }

            @Override public void onReceivedHttpError(WebView view, WebResourceRequest request,
                                                      WebResourceResponse response) {
                super.onReceivedHttpError(view, request, response);
                if (request.isForMainFrame()) {
                    showPortalError("Portal HTTP " + response.getStatusCode(),
                            request.getUrl().toString());
                }
            }
        });
        browser.addView(webView, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));
        screen.addView(menu, new FrameLayout.LayoutParams(-1, -1));
        screen.addView(browser, new FrameLayout.LayoutParams(-1, -1));
        return screen;
    }

    private TextView statusText(String text) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(13);
        view.setTextColor(Color.rgb(52, 64, 84));
        view.setPadding(dp(18), dp(8), dp(18), dp(8));
        return view;
    }

    private Button action(String label, View.OnClickListener listener) {
        Button button = new Button(this);
        button.setText(label);
        button.setAllCaps(false);
        button.setTextColor(Color.rgb(24, 50, 80));
        button.setMinWidth(0);
        button.setMinHeight(dp(44));
        button.setBackground(roundBackground(Color.WHITE, Color.rgb(205, 216, 231), 14));
        button.setPadding(dp(8), dp(4), dp(8), dp(4));
        button.setOnClickListener(listener);
        return button;
    }

    private LinearLayout actionRow(View first, View second) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        LinearLayout.LayoutParams firstParams = new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        firstParams.setMargins(dp(3), 0, dp(3), dp(2));
        LinearLayout.LayoutParams secondParams = new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        secondParams.setMargins(dp(3), 0, dp(3), dp(2));
        row.addView(first, firstParams);
        row.addView(second, secondParams);
        return row;
    }

    private static boolean healthPortal(String url) {
        try {
            String host = URI.create(url).getHost();
            return host != null && (host.equals("enabiz.gov.tr") || host.endsWith(".enabiz.gov.tr")
                    || host.equals("saglik.gov.tr") || host.endsWith(".saglik.gov.tr"));
        } catch (Exception e) { return false; }
    }

    private void open(String url) {
        showPanel(browserPanel);
        showingPortalError = false;
        if (url == null || url.trim().isEmpty()) url = "about:blank";
        applyUserAgent(url);
        showAddress(url);
        setPortalStatus("Yükleniyor: " + url);
        debugLog("Navigasyon: " + url);
        Telemetry.event("navigation", desktopMode ? "desktop" : "mobile");
        if (activeWebView == null) activeWebView = webView;
        if (isFreshObsEntry(url)) {
            clearPortalCookies("https://obs.saglik.gov.tr");
            clearPortalCookies("https://ogn.saglik.gov.tr");
            CookieManager.getInstance().flush();
            debugLog("OBS/OGN yeni giriş oturumu başlatıldı");
        }
        activeWebView.loadUrl(url);
    }

    private static boolean isFreshObsEntry(String rawUrl) {
        try {
            URI uri = URI.create(rawUrl);
            String path = uri.getPath();
            return "obs.saglik.gov.tr".equalsIgnoreCase(uri.getHost())
                    && (path == null || path.isEmpty() || "/".equals(path)
                    || "/Account/Login".equalsIgnoreCase(path))
                    && uri.getQuery() == null;
        } catch (Exception ignored) { return false; }
    }

    /** Expire only cookies visible to one portal; never log their values. */
    private void clearPortalCookies(String origin) {
        String raw = CookieManager.getInstance().getCookie(origin);
        if (raw == null) return;
        for (String item : raw.split(";")) {
            int equals = item.indexOf('=');
            String name = (equals < 0 ? item : item.substring(0, equals)).trim();
            if (!name.isEmpty() && name.matches("[A-Za-z0-9_.-]{1,80}"))
                CookieManager.getInstance().setCookie(origin,
                        name + "=; Max-Age=0; Path=/; Secure; SameSite=Lax");
        }
    }

    private void openDesktop(String url) {
        desktopMode = true;
        if (desktopSwitch != null) desktopSwitch.setChecked(true);
        open(url);
    }

    private void showBrowser() {
        showPanel(browserPanel);
    }

    private String readAsset(String name) {
        try (java.io.InputStream in = getAssets().open(name);
             java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int n;
            while ((n = in.read(buffer)) != -1) out.write(buffer, 0, n);
            return new String(out.toByteArray(), StandardCharsets.UTF_8);
        } catch (java.io.IOException e) {
            throw new IllegalStateException("Portal köprüsü yüklenemedi: " + name, e);
        }
    }

    private void setPortalStatus(String text) {
        runOnUiThread(() -> {
            if (portalStatus != null) portalStatus.setText(text);
        });
    }

    private void showPortalError(String message, String url) {
        showingPortalError = true;
        setPortalStatus(message + ": " + url);
        String html = "<!doctype html><meta name='viewport' content='width=device-width,initial-scale=1'>"
                + "<style>body{font:16px sans-serif;margin:24px;color:#182230}</style>"
                + "<h2>Portal açılamadı</h2><p>" + android.text.Html.escapeHtml(message)
                + "</p><p>" + android.text.Html.escapeHtml(url == null ? "" : url)
                + "</p><p>Kart / Menü düğmesinden portalı yeniden seçin.</p>";
        WebView target = activeWebView == null ? webView : activeWebView;
        if (target != null) target.loadDataWithBaseURL(null, html, "text/html", "UTF-8", null);
    }

    private void showReaderStatus(String text) {
        debugLog("Okuyucu: " + text);
        DiagnosticLogger.i(DiagnosticLogger.Tag.USB, "Okuyucu durumu: " + text);
        if (text != null && (text.contains("kart oturumu hazır") || text.contains("APDU kart oturumu hazır") || text.contains("T=1 kart oturumu hazır"))
                && autoCertificateScan.compareAndSet(false, true)) {
            runOnUiThread(this::readCertificates);
        }
        if (text != null && text.contains("okuyucu bulunamadı")) autoCertificateScan.set(false);
        runOnUiThread(() -> {
            if (readerStatus != null) readerStatus.setText(text);
            if (signerStatus != null && akisBackend != null
                    && akisBackend.state() == SignerBackend.State.WAITING_FOR_READER) {
                signerStatus.setText(akisBackend.displayName() + ": okuyucu bekleniyor");
            }
        });
    }

    private void readCertificates() {
        String tokenTitle = akisBackend != null ? akisBackend.displayName() : "E-imza tokenı";
        signerStatus.setText(tokenTitle + " ve imza sertifikaları okunuyor…");
        signerWorker.execute(() -> {
            try {
                List<SignerBackend.CertificateSummary> certs = akisBackend.certificates();
                automaticScanRetries = 0;
                runOnUiThread(() -> showCertificates(certs));
            } catch (Exception e) {
                DiagnosticLogger.e(DiagnosticLogger.Tag.CARD, "Sertifika okuma hatası", e);
                runOnUiThread(() -> {
                    autoCertificateScan.set(false);
                    if (signerStatus != null) signerStatus.setText("Kart okunamadı (" + e.getMessage() + "); yeniden deneniyor…");
                    if (automaticScanRetries++ < 2 && usbProbe != null) {
                        usbProbe.scan();
                    } else if (signerStatus != null) {
                        signerStatus.setText("Kart / sertifika okunamadı. Detay için Tanı & Debugger panelini inceleyin.");
                    }
                });
            }
        });
    }

    private void showCertificates(List<SignerBackend.CertificateSummary> certs) {
        String tokenTitle = akisBackend != null ? akisBackend.displayName() : "E-imza motoru";
        if (certs.isEmpty()) {
            signerStatus.setText(tokenTitle + " görüldü; kartta uygun imza sertifikası bulunamadı.");
            return;
        }
        String[] labels = new String[certs.size()];
        for (int i = 0; i < certs.size(); i++) {
            SignerBackend.CertificateSummary c = certs.get(i);
            labels[i] = c.label + "\nGeçerlilik sonu: " + c.validUntil;
        }
        signerStatus.setText(tokenTitle + " hazır; " + certs.size() + " imza sertifikası bulundu.");
        new AlertDialog.Builder(this).setTitle(tokenTitle + " Sertifikaları")
                .setItems(labels, (dialog, which) -> askPinForSelfTest(certs.get(which)))
                .setNeutralButton("Tanı Raporu (.txt)", (dialog, which) -> exportDiagnosticTxt())
                .setNegativeButton("Kapat", null).show();
    }

    private void askPinForSelfTest(SignerBackend.CertificateSummary cert) {
        String tokenTitle = akisBackend != null ? akisBackend.displayName() : "E-imza";
        EditText pin = new EditText(this);
        pin.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        new AlertDialog.Builder(this).setTitle(tokenTitle + " PIN Girişi")
                .setMessage("Seçilen sertifika için yerel imza testi. PIN yalnızca kartta doğrulanır, hiçbir yere kaydedilmez.")
                .setView(pin).setNegativeButton("İptal", null)
                .setPositiveButton("İmzala", (dialog, which) -> {
                    char[] secret = pin.getText().toString().toCharArray();
                    byte[] challenge = "E-Imza One yerel kart testi".getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    signerStatus.setText("PIN doğrulanıyor ve kart imzası denetleniyor…");
                    signerWorker.execute(() -> {
                        try {
                            byte[] signed = akisBackend.sign(challenge, cert.id, secret);
                            runOnUiThread(() -> signerStatus.setText(tokenTitle + " imzası üretildi ve sertifikayla doğrulandı ("
                                    + signed.length + " bayt). Test başarılı!"));
                        } catch (SignerBackend.SignerException e) {
                            java.util.Arrays.fill(secret, '\0');
                            DiagnosticLogger.e(DiagnosticLogger.Tag.PIN, "İmza testi hatası", e);
                            runOnUiThread(() -> {
                                signerStatus.setText("İmza testi başarısız: " + e.getMessage());
                                new AlertDialog.Builder(this)
                                        .setTitle("İmza Test Hatası")
                                        .setMessage(e.getMessage() + "\n\nTanı ve hata kaydını TXT olarak almak ister misiniz?")
                                        .setPositiveButton("Tanı Çıktısı Al (.txt)", (d, w) -> exportDiagnosticTxt())
                                        .setNegativeButton("Tamam", null)
                                        .show();
                            });
                        }
                    });
                }).show();
    }

    private void traceArk(String text) {
        appendDebug(text);
        runOnUiThread(() -> {
            if (arkTrace.length() > 3000) arkTrace.delete(0, arkTrace.indexOf("\n") + 1);
            arkTrace.append(text).append('\n');
            if (arkDiagnostics != null) arkDiagnostics.setText(arkTrace.toString());
            if (portalStatus != null) portalStatus.setText(text);
        });
    }

    private boolean isEdevletJnlp(Uri uri) {
        if (uri == null || !"https".equalsIgnoreCase(uri.getScheme())) return false;
        String host = uri.getHost();
        String path = uri.getPath();
        return host != null && (host.equalsIgnoreCase("turkiye.gov.tr")
                || host.toLowerCase(Locale.ROOT).endsWith(".turkiye.gov.tr"))
                && path != null && path.toLowerCase(Locale.ROOT).endsWith(".jnlp");
    }

    private void promptEdevletTransactionCode() {
        promptEdevletTransactionCode("");
    }

    private String edevletBrowserCookies() {
        StringBuilder cookies = new StringBuilder();
        for (String origin : new String[]{"https://giris.turkiye.gov.tr/", "https://www.turkiye.gov.tr/"}) {
            String value = CookieManager.getInstance().getCookie(origin);
            if (value != null && !value.trim().isEmpty()) {
                if (cookies.length() > 0) cookies.append(';').append(' ');
                cookies.append(value);
            }
        }
        return cookies.toString();
    }

    private void promptEdevletTransactionCode(String detectedCode) {
        runOnUiThread(() -> {
            EditText code = new EditText(this);
            code.setSingleLine(true);
            code.setHint("6–10 karakterlik işlem kodu");
            code.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
            String safeCode = detectedCode != null && detectedCode.matches("[A-Za-z0-9]{6,10}") ? detectedCode : "";
            code.setText(safeCode);
            code.setSelection(code.length());
            new AlertDialog.Builder(this).setTitle("e-Devlet e-imza")
                    .setMessage("Sayfada gösterilen işlem kodunu büyük/küçük harfleri değiştirmeden doğrulayın.")
                    .setView(code).setNegativeButton("İptal", null)
                    .setPositiveButton("Devam", (dialog, which) ->
                            beginEdevletFlow(code.getText().toString().trim(), false))
                    .show();
        });
    }

    private void beginEdevletFlow(String transactionCode, boolean automatic) {
        try { EdevletClient.validateTransactionId(transactionCode); }
        catch (IllegalArgumentException error) {
            runOnUiThread(() -> Toast.makeText(this, error.getMessage(), Toast.LENGTH_LONG).show());
            return;
        }
        long now = System.currentTimeMillis();
        if (transactionCode.equals(completedEdevletCode)
                && now - completedEdevletCodeAt < 5 * 60 * 1000L) {
            traceArk("e-Devlet: daha önce kabul edilen işlem kodu yeniden gönderilmedi");
            return;
        }
        if (automatic && transactionCode.equals(activeEdevletCode) && now - activeEdevletCodeAt < 120000) return;
        activeEdevletCode = transactionCode;
        activeEdevletCodeAt = now;
        traceArk("e-Devlet işlem kodu alındı; sertifika seçimi bekleniyor");
        signerWorker.execute(() -> {
            try {
                List<AkisSignerBackend.ArkCertificate> certificates = akisBackend.arkCertificates();
                if (certificates.isEmpty()) throw new IllegalStateException("Kartta imza sertifikası bulunamadı");
                runOnUiThread(() -> chooseEdevletCertificate(transactionCode, certificates));
            } catch (Exception error) {
                activeEdevletCode = "";
                traceArk("e-Devlet sertifika okuma hatası: " + error.getMessage());
            }
        });
    }

    private void chooseEdevletCertificate(String transactionCode,
                                           List<AkisSignerBackend.ArkCertificate> certificates) {
        // The normal card path has one qualified signing certificate.  Do not
        // put an otherwise automatic e-Devlet flow behind an unnecessary
        // selector; retain a choice only for genuinely multi-certificate cards.
        if (certificates.size() == 1) {
            fetchEdevletSigningRequest(transactionCode, certificates.get(0));
            return;
        }
        String[] labels = new String[certificates.size()];
        for (int i = 0; i < certificates.size(); i++) {
            java.security.cert.X509Certificate certificate = certificates.get(i).certificate;
            labels[i] = extractCN(certificate) + "\nTCKN: " + extractTCKN(certificate)
                    + " · " + certificate.getPublicKey().getAlgorithm();
        }
        new AlertDialog.Builder(this).setTitle("e-Devlet sertifikası")
                .setItems(labels, (dialog, which) ->
                        fetchEdevletSigningRequest(transactionCode, certificates.get(which)))
                .setOnCancelListener(dialog -> activeEdevletCode = "")
                .setNegativeButton("İptal", (dialog, which) -> activeEdevletCode = "").show();
    }

    private void fetchEdevletSigningRequest(String transactionCode,
                                             AkisSignerBackend.ArkCertificate certificate) {
        traceArk("e-Devlet imzalanacak veri alınıyor…");
        signerWorker.execute(() -> {
            try {
                String identity = extractTCKN(certificate.certificate);
                EdevletClient.SigningRequest request = new EdevletClient()
                        .fetchSigningRequest(identity, transactionCode);
                traceArk("e-Devlet işlem verisi alındı: tür="
                        + request.operationType.replaceAll("[^A-Za-z0-9_.-]", "")
                        + "; mime=" + request.mimeType.replaceAll("[^A-Za-z0-9_./+-]", "")
                        + "; fileInputBase64Uzunluk=" + request.contentBase64.length());
                if (!request.operationType.isEmpty() && !"Giris".equalsIgnoreCase(request.operationType))
                    throw new IllegalStateException("Bu işlem giriş işlemi değil: " + request.operationType);
                if ("xml".equalsIgnoreCase(request.mimeType) || "imz".equalsIgnoreCase(request.mimeType))
                    throw new IllegalStateException("Bu e-Devlet belge imza türü henüz desteklenmiyor: " + request.mimeType);
                byte[] content = android.util.Base64.decode(request.contentBase64, android.util.Base64.DEFAULT);
                if (content.length == 0) throw new IllegalStateException("İmzalanacak e-Devlet verisi boş");
                runOnUiThread(() -> confirmEdevletSignature(transactionCode, certificate, content));
            } catch (Exception error) {
                activeEdevletCode = "";
                traceArk("e-Devlet işlem kodu doğrulanamadı: " + error.getMessage());
            }
        });
    }

    private void confirmEdevletSignature(String transactionCode,
                                         AkisSignerBackend.ArkCertificate certificate, byte[] content) {
        EditText pin = new EditText(this);
        pin.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        new AlertDialog.Builder(this).setTitle("e-Devlet girişini imzala")
                .setMessage("Sertifika: " + extractCN(certificate.certificate)
                        + "\nİşlem kodu: " + transactionCode
                        + "\nPIN yalnızca kartta doğrulanır; e-Devlet'e gönderilmez.")
                .setView(pin).setOnCancelListener(dialog -> activeEdevletCode = "")
                .setNegativeButton("İptal", (dialog, which) -> activeEdevletCode = "")
                .setPositiveButton("İmzala", (dialog, which) -> {
                    char[] secret = pin.getText().toString().toCharArray();
                    pin.setText("");
                    signerWorker.execute(() -> {
                        try {
                            // Match the official JNLP SmartCard.signContent CMS profile,
                            // including SigningCertificateV2, signingTime and embedded data.
                            byte[] cms = EdevletCmsSupport.sign(content, certificate.id,
                                    certificate.certificate, secret, akisBackend);
                            traceArk("e-Devlet CMS hazır: profil=resmi-CMS; içerik="
                                    + content.length + "; zarf=" + cms.length);
                            new EdevletClient().submitLogin(cms, transactionCode);
                            completedEdevletCode = transactionCode;
                            completedEdevletCodeAt = System.currentTimeMillis();
                            // The open e-Devlet page owns the browser session and
                            // polls for this transaction.  Do not submit the JNLP
                            // response's `sonuc` value into a guessed DOM form, and
                            // do not reload or navigate away from that waiting page.
                            traceArk("e-Devlet imzası kabul edildi; açık sayfanın oturum yoklaması bekleniyor");
                            runOnUiThread(() -> {
                                Toast.makeText(this,
                                        "İmza kabul edildi. e-Devlet sayfasını yenilemeden bekleyin.",
                                        Toast.LENGTH_LONG).show();
                            });
                        } catch (Exception error) {
                            showSigningFailure("e-Devlet", error);
                            traceArk("e-Devlet imzası başarısız: " + error.getMessage());
                        } finally {
                            java.util.Arrays.fill(secret, '\0');
                            activeEdevletCode = "";
                        }
                    });
                }).show();
    }

    public final class ArkPageBridge {
        @JavascriptInterface public void edevletTransactionCode(String pageOrigin, String code) {
            if (PortalOrigins.isEdevlet(pageOrigin) && sameAllowedOrigin(pageOrigin) && code != null) {
                String value = code.trim();
                if (value.matches("[A-Za-z0-9]{6,10}")) {
                    traceArk("e-Devlet işlem kodu sayfadaki kopyalama alanından otomatik alındı");
                    beginEdevletFlow(value, true);
                }
            }
        }

        @JavascriptInterface public void edevletJnlpRequested(String pageOrigin) {
            if (PortalOrigins.isEdevlet(pageOrigin) && sameAllowedOrigin(pageOrigin))
                traceArk("e-Devlet: işlem kodu henüz görünür değil; T.C./captcha adımı bekleniyor");
        }

        @JavascriptInterface public void arkTransportStatus(String text) {
            if (sameAllowedOrigin(activePageUrl) && text != null && text.length() < 180)
                traceArk(text);
        }
        @JavascriptInterface public void adaletRequest(String id, String method, String url, String body) {
            if (id == null || !adaletOrigin(activePageUrl) || !adaletLocalUrl(url)) {
                completeAdalet(id, adaletEnvelope(null, "ADALET_ERROR", "Geçersiz imza isteği"));
                return;
            }
            signerWorker.execute(() -> handleAdaletRequest(id, method, url, body));
        }

        @JavascriptInterface public void accept(String pageOrigin, String taskBase64) {
            if (!sameAllowedOrigin(pageOrigin) || adaletOrigin(pageOrigin) || taskBase64 == null || taskBase64.length() > 2_100_000) {
                traceArk("ArkSigner isteği reddedildi: portal kökeni eşleşmedi");
                sendPageResponse("[{\"responseCode\":\"1001\"}]");
                return;
            }
            final org.json.JSONObject task;
            try {
                byte[] raw = android.util.Base64.decode(taskBase64, android.util.Base64.DEFAULT);
                task = new org.json.JSONObject(new String(raw, StandardCharsets.UTF_8));
            } catch (Exception e) {
                sendPageResponse("[{\"responseCode\":\"1001\"}]");
                return;
            }
            final String action = task.optString("action", "");
            final String tx = task.optString("transactionUUID", "");
            if (arkJobs.size() > 100) arkJobs.clear();
            arkJobs.put(tx, task.optString("jobUUID", ""));
            traceArk("İstek: " + action.replaceAll("[^A-Za-z0-9_.]", "").substring(0, Math.min(80, action.replaceAll("[^A-Za-z0-9_.]", "").length())));
            if ("initialize".equals(action) || "listCardTypeAndSlots".equals(action)
                    || "listSignerCertificatesAsJSON".equals(action)
                    || "monitorSmartCardActivity".equals(action)) {
                signerWorker.execute(() -> handleArkReadAction(action, tx));
            } else if ("signPKCS1Padding1.5".equals(action) || "signCAdES_BES".equals(action)
                    || "signPKCS1AsJSON".equals(action) || "signCadesBesAsJSON".equals(action)) {
                signerWorker.execute(() -> handleArkSignAction(action, tx, task, pageOrigin));
            } else {
                traceArk("Desteklenmeyen ArkSigner işlemi");
                sendPageResponse(arkError(tx, "1001"));
            }
        }
    }

    /** ArkSigner HTTP transport for Firefox/Chrome on this same Android device. */
    private String handleLoopbackRequest(String encodedTask) {
        try {
            byte[] raw = android.util.Base64.decode(encodedTask, android.util.Base64.DEFAULT);
            org.json.JSONObject task = new org.json.JSONObject(new String(raw, StandardCharsets.UTF_8));
            String action = task.optString("action", "");
            String tx = task.optString("transactionUUID", "");
            traceArk("Loopback ArkSigner: " + action.replaceAll("[^A-Za-z0-9_.]", ""));
            if ("initialize".equals(action)) {
                org.json.JSONObject response = loopbackSuccess(tx, task);
                response.put("clientVersion", "34");
                response.put("nonce2", ArkBootstrap.cypher(readAsset("arksigner-sdk.js"), response.getString("nonce")));
                return new org.json.JSONArray().put(response).toString();
            }
            if ("monitorSmartCardActivity".equals(action))
                return new org.json.JSONArray().put(loopbackSuccess(tx, task)
                        .put("monitoringResult", portalBase64("0"))).toString();
            if ("listCardTypeAndSlots".equals(action))
                return new org.json.JSONArray().put(loopbackSuccess(tx, task)
                        .put("terminal", portalBase64(AndroidCardSession.readerName())).put("slotId", "0")
                        .put("library", portalBase64("akisp11")).put("smartCardType", portalBase64("token"))
                        .put("cardType", portalBase64("AKIS"))
                        .put("providesPINReader", portalBase64("false"))
                        .put("isCardInserted", portalBase64(AndroidCardSession.readerName() == null ? "false" : "true")))
                        .toString();
            if ("listSignerCertificatesAsJSON".equals(action)) {
                org.json.JSONArray rows = new org.json.JSONArray();
                for (AkisSignerBackend.ArkCertificate c : akisBackend.arkCertificates()) {
                    java.security.cert.X509Certificate cert = c.certificate;
                    String cn = extractCN(cert), tckn = extractTCKN(cert);
                    rows.put(loopbackSuccess(tx, task).put("certificateHex", hex(c.der))
                            .put("serialNumber", portalBase64(c.serial)).put("certSerialNumber", portalBase64(c.serial))
                            .put("commonName", portalBase64(cn)).put("subjectCommonName", portalBase64(cn))
                            .put("subjectSerialNumber", portalBase64(tckn))
                            .put("subject", portalBase64(cert.getSubjectX500Principal().getName(X500Principal.RFC2253)))
                            .put("issuer", portalBase64(rebuildDn(cert.getIssuerX500Principal())))
                            .put("issuerCommonName", portalBase64(extractIssuerCN(cert)))
                            .put("subjectNameSurname", portalBase64(subjectNameSurnameFromCN(cn)))
                            .put("isExpired", portalBase64(cert.getNotAfter().before(new java.util.Date()) ? "true" : "false"))
                            .put("notAfter", portalBase64(cert.getNotAfter().toInstant().toString()))
                            .put("notBefore", portalBase64(cert.getNotBefore().toInstant().toString())));
                }
                return rows.length() == 0 ? arkError(tx, "7") : rows.toString();
            }
            if ("signCAdES_BES".equals(action) || "signCadesBesAsJSON".equals(action)
                    || "signPKCS1Padding1.5".equals(action) || "signPKCS1AsJSON".equals(action)) {
                String serial = task.optString("certSerialNumber", task.optString("serialNumber", ""));
                String id = akisBackend.idForSerial(serial);
                if (id == null) return arkError(tx, "1001");
                AkisSignerBackend.ArkCertificate selected = null;
                for (AkisSignerBackend.ArkCertificate c : akisBackend.arkCertificates()) if (c.id.equals(id)) selected = c;
                String pin = task.optString("pincode", task.optString("pinCode", task.optString("password", "")));
                if (selected == null || pin.isEmpty()) return arkError(tx, "1001");
                byte[] data = arkPayload(task);
                char[] secret = pin.toCharArray();
                try {
                    boolean attached = portalAttachedContent(task, task.optString("origin", ""));
                    byte[] signed = action.toLowerCase(Locale.ROOT).contains("cades")
                            ? CadesSupport.sign(data, selected.id, selected.certificate, secret, akisBackend, attached)
                            : akisBackend.signRawPkcs1(data, selected.id, secret);
                    if (action.toLowerCase(Locale.ROOT).contains("cades"))
                        traceCmsShape("ArkSigner loopback", data, signed);
                    String b64 = android.util.Base64.encodeToString(signed, android.util.Base64.NO_WRAP);
                    org.json.JSONObject result = loopbackSuccess(tx, task).put("signedMime", b64)
                            .put("signature", b64).put("signedData", b64).put("dataBase64", b64);
                    return new org.json.JSONArray().put(result).toString();
                } finally { java.util.Arrays.fill(secret, '\0'); }
            }
            return arkError(tx, "1001");
        } catch (Exception e) {
            traceArk("Loopback ArkSigner hatası: " + e.getClass().getSimpleName());
            return "[{\"responseCode\":\"1001\"}]";
        }
    }

    private static org.json.JSONObject loopbackSuccess(String tx, org.json.JSONObject task)
            throws org.json.JSONException {
        org.json.JSONObject response = arkSuccess(tx);
        String job = task == null ? "" : task.optString("jobUUID", "");
        if (!job.isEmpty()) response.put("jobUUID", job);
        return response;
    }

    private static String portalBase64(String value) {
        return android.util.Base64.encodeToString(
                value == null ? new byte[0] : value.getBytes(StandardCharsets.UTF_8),
                android.util.Base64.NO_WRAP
        );
    }

    private void handleArkReadAction(String action, String tx) {
        try {
            org.json.JSONArray rows = new org.json.JSONArray();
            if ("initialize".equals(action)) {
                org.json.JSONObject response = arkSuccess(tx);
                String nonce = response.getString("nonce");
                response.put("clientVersion", "34");
                installArkSdkAndRespond(response, nonce);
                return;
            } else if ("monitorSmartCardActivity".equals(action)) {
                rows.put(arkSuccess(tx).put("monitoringResult", "0"));
            } else if ("listCardTypeAndSlots".equals(action)) {
                String readerName = AndroidCardSession.readerName();
                rows.put(arkSuccess(tx)
                        .put("terminal", portalBase64(readerName))
                        .put("slotId", "0")
                        .put("library", portalBase64("akisp11"))
                        .put("smartCardType", portalBase64("token"))
                        .put("cardType", portalBase64("AKIS"))
                        .put("providesPINReader", portalBase64("false"))
                        .put("isCardInserted",
                                portalBase64(readerName == null ? "false" : "true")));
            } else {
                for (AkisSignerBackend.ArkCertificate item : akisBackend.arkCertificates()) {
                    java.security.cert.X509Certificate cert = item.certificate;

                    // Sertifikadan TÜM değerleri BouncyCastle ile al (encoding sorunu yok)
                    String cn = extractCN(cert);
                    String tckn = extractTCKN(cert);
                    String issuerCn = extractIssuerCN(cert);

                    // Issuer'ı da BouncyCastle ile düzgün formatta üret
                    String issuerClean = rebuildDn(cert.getIssuerX500Principal());

                    // Sertifika seri numarasını hex olarak al (portal eşleştirme için)
                    String serialHex = cert.getSerialNumber().toString(16).toUpperCase(Locale.ROOT);


					String serialDigits = extractTCKN(cert);
					byte[] der = item.der;

                    java.security.cert.CertificateFactory factory =
                            java.security.cert.CertificateFactory.getInstance("X.509");

                    java.security.cert.X509Certificate check =
                            (java.security.cert.X509Certificate) factory.generateCertificate(
                                    new java.io.ByteArrayInputStream(der));

                    android.util.Log.d(
                            "CERT_VERIFY",
                            "TCKN=" + extractTCKN(check)
                            + " DER=" + der.length
                            + " HEX=" + hex(der).length()
                    );

					String subjectDn = cert.getSubjectX500Principal().getName(X500Principal.RFC2253);

                    org.json.JSONObject row = arkSuccess(tx)
                            // Bu alan hex olarak kalmalı; ArkSignerJS hexToBase64() yapıyor
                            .put("certificateHex", hex(item.der))
                            // ArkSignerJS bunları Base64.decode() ediyor
                            .put("serialNumber", portalBase64(serialHex))
                            .put("certSerialNumber", portalBase64(serialHex))
                            .put("commonName", portalBase64(cn))
                            .put("subjectCommonName", portalBase64(cn))
                            .put("issuer", portalBase64(issuerClean))
                            .put("notAfter", portalBase64(cert.getNotAfter().toInstant().toString()))
                            .put("notBefore", portalBase64(cert.getNotBefore().toInstant().toString()))
                            .put("subjectSerialNumber", portalBase64(tckn))
                            .put("subjectNameSurname", portalBase64(subjectNameSurnameFromCN(cn)))
                            .put("subject", portalBase64(subjectDn));

                    android.util.Log.d("ARK_CERT_JSON", row.toString());
                    rows.put(row);
                }
            }
            if (rows.length() == 0) { sendPageResponse(arkError(tx, "7")); return; }
            sendPageResponse(rows.toString());
        } catch (Exception e) {
            runOnUiThread(() -> portalStatus.setText("ArkSigner: " + e.getClass().getSimpleName() + ": " + e.getMessage()));
            sendPageResponse(arkError(tx, "1001"));
        }
    }

    private void handleArkSignAction(String action, String tx, org.json.JSONObject task, String origin) {
        try {
            String serial = task.optString("certSerialNumber", task.optString("serialNumber", ""));
            String certId = akisBackend.idForSerial(serial);
            if (certId == null) {
                String certHex = task.optString("certificateHex", "");
                for (AkisSignerBackend.ArkCertificate candidate : akisBackend.arkCertificates()) {
                    if (!certHex.isEmpty() && certHex.equalsIgnoreCase(hex(candidate.der))) certId = candidate.id;
                }
            }
            if (certId == null) { sendPageResponse(arkError(tx, "1001")); return; }
            AkisSignerBackend.ArkCertificate cert = null;
            for (AkisSignerBackend.ArkCertificate c : akisBackend.arkCertificates()) if (c.id.equals(certId)) cert = c;
            if (cert == null) { sendPageResponse(arkError(tx, "1001")); return; }
            byte[] data = arkPayload(task);
            if (data.length == 0) { sendPageResponse(arkError(tx, "1001")); return; }
            AkisSignerBackend.ArkCertificate selected = cert;
            runOnUiThread(() -> confirmPortalSignature(action, tx, origin, task, selected, data));
        } catch (Exception e) {
            sendPageResponse(arkError(tx, "1001"));
        }
    }

    private boolean portalAttachedContent(org.json.JSONObject task, String origin) {
        // OGN's signed SSO assertion is consumed as an attached CMS even when
        // the page omits isAttached or incorrectly sends false.
        if (PortalOrigins.requiresAttachedCades(origin)
                || PortalOrigins.requiresAttachedCades(activePageUrl)) {
            traceArk("Sağlık SSO CAdES: gömülü içerik modu zorlandı");
            return true;
        }
        if (task == null) return false;
        return task.has("isAttached") && task.optBoolean("isAttached", false);
    }

    private void signPortalData(
            String action,
            String tx,
            org.json.JSONObject task,
            String origin,
            AkisSignerBackend.ArkCertificate cert,
            byte[] data,
            char[] secret) {

        signerWorker.execute(() -> {
            try {
                byte[] signed;

                if (action.toLowerCase(Locale.ROOT).contains("cades")) {
                    signed = CadesSupport.sign(
                            data,
                            cert.id,
                            cert.certificate,
                            secret,
                            akisBackend,
                            portalAttachedContent(task, origin)
                    );
                    traceCmsShape("ArkSigner", data, signed);
                } else {
                    signed = akisBackend.signRawPkcs1(
                            data,
                            cert.id,
                            secret
                    );
                }

                org.json.JSONObject result = arkSuccess(tx);

                String b64 = android.util.Base64.encodeToString(
                        signed,
                        android.util.Base64.NO_WRAP
                );

                result.put("signedMime", b64)
                        .put("signature", b64)
                        .put("signedData", b64)
                        .put("dataBase64", b64);

                sendPageResponse(
                        new org.json.JSONArray()
                                .put(result)
                                .toString()
                );

            } catch (Exception e) {
                showSigningFailure("ArkSigner", e);
                sendPageResponse(arkError(tx, "1001"));
            } finally {
                java.util.Arrays.fill(secret, '\0');
            }
        });
    }

    private void traceCmsShape(String provider, byte[] input, byte[] cmsBytes) {
        if (!adminDebug) return;
        try {
            org.bouncycastle.cms.CMSSignedData cms =
                    new org.bouncycastle.cms.CMSSignedData(cmsBytes);
            traceArk(provider + " CMS: içerik=" + input.length + " bayt; zarf="
                    + cmsBytes.length + " bayt; gömülü=" + (cms.getSignedContent() != null));
        } catch (Exception error) {
            traceArk(provider + " CMS tanısı başarısız: " + error.getClass().getSimpleName());
        }
    }

    private void confirmPortalSignature(
            String action,
            String tx,
            String origin,
            org.json.JSONObject task,
            AkisSignerBackend.ArkCertificate cert,
            byte[] data) {

        String suppliedPin = task.optString("pincode", "");

        if (suppliedPin.isEmpty()) {
            suppliedPin = task.optString("pinCode", "");
        }

        if (suppliedPin.isEmpty()) {
            suppliedPin = task.optString("password", "");
        }

        final String pinFromSite = suppliedPin;

        android.util.Log.d(
                "ARK_PIN",
                "Site PIN gönderdi mi: " + (!pinFromSite.isEmpty())
        );

        if (!pinFromSite.isEmpty()) {
            signPortalData(
                    action,
                    tx,
                    task,
                    origin,
                    cert,
                    data,
                    pinFromSite.toCharArray()
            );
            return;
        }

        // Site PIN göndermiyorsa yerel PIN ekranı açılır
        EditText pin = new EditText(this);
        pin.setInputType(
                InputType.TYPE_CLASS_NUMBER
                        | InputType.TYPE_NUMBER_VARIATION_PASSWORD
        );

        String cn = commonName(
                cert.certificate
                        .getSubjectX500Principal()
                        .getName(X500Principal.RFC2253)
        );

        new AlertDialog.Builder(this)
                .setTitle("E-imza isteğini onayla")
                .setMessage(
                        "Site: " + origin
                                + "\nSertifika: " + cn
                                + "\nVeri: " + data.length
                                + " bayt\nPIN kartta doğrulanacak."
                )
                .setView(pin)
                .setNegativeButton(
                        "İptal",
                        (d, w) -> sendPageResponse(arkError(tx, "1001"))
                )
                .setPositiveButton("İmzala", (dialog, which) -> {
                    char[] secret =
                            pin.getText().toString().toCharArray();

                    pin.setText("");

                    signPortalData(
                            action,
                            tx,
                            task,
                            origin,
                            cert,
                            data,
                            secret
                    );
                })
                .setOnCancelListener(
                        d -> sendPageResponse(arkError(tx, "1001"))
                )
                .show();
    }

    private void sendPageResponse(String json) {
        String output = json;
        try {
            org.json.JSONArray rows = new org.json.JSONArray(json);
            if (rows.length() > 0) {
                String tx = rows.getJSONObject(0).optString("transactionUUID", "");
                String job = arkJobs.remove(tx);
                if (job != null) for (int i = 0; i < rows.length(); i++) rows.getJSONObject(i).put("jobUUID", job);
                org.json.JSONObject first = rows.getJSONObject(0);
                java.util.Iterator<String> names = first.keys();
                StringBuilder keys = new StringBuilder();
                while (names.hasNext()) {
                    if (keys.length() > 0) keys.append(',');
                    keys.append(names.next());
                }
                if (first.has("signedMime")) {
                    keys.append("; signedMimeLen=").append(first.optString("signedMime").length())
                            .append(",signatureLen=").append(first.optString("signature").length())
                            .append(",signedDataLen=").append(first.optString("signedData").length())
                            .append(",dataBase64Len=").append(first.optString("dataBase64").length());
                }
                traceArk("Yanıt: kod=" + first.optString("responseCode") + "; kayıt=" + rows.length()
                        + "; alanlar=" + keys);
            } else traceArk("Yanıt: sertifika listesi boş");
            output = rows.toString();
        } catch (org.json.JSONException error) {
            traceArk("ArkSigner yanıtı ayrıştırılamadı: " + error.getMessage());
        }
        final String data = org.json.JSONObject.quote(output);
        runOnUiThread(() -> {
            WebView target = activeWebView == null ? webView : activeWebView;
            if (target == null) return;
            target.evaluateJavascript("window.__eimzaArkResolve && window.__eimzaArkResolve(" + data + ");", null);
        });
    }

    private void installArkSdkAndRespond(org.json.JSONObject response, String nonce) {
        final String sdk = readAsset("arksigner-sdk.js");
        try {
            // Do not evaluate the client before ArkSignerJS has processed this
            // initialize response. Doing so overwrites the portal's 3.x
            // processResponseObject with the bundled client's implementation
            // while the 3.x SocketV13 onload handler is still on the stack.
            // The native service contract delivers the client in nonce2; the
            // portal validates/decrypts/evaluates it from its own callback.
            response.put("nonce2", ArkBootstrap.cypher(sdk, nonce));
            traceArk("ArkSigner SDK şifreli bootstrap ile teslim edildi");
            sendPageResponse(new org.json.JSONArray().put(response).toString());
        } catch (org.json.JSONException error) {
            sendPageResponse(arkError(response.optString("transactionUUID"), "1001"));
        }
    }

    private static org.json.JSONObject arkSuccess(String tx) throws org.json.JSONException {
        return new org.json.JSONObject().put("responseCode", "0").put("transactionUUID", tx).put("nonce", ArkBootstrap.nonce());
    }
    private static String arkError(String tx, String code) {
        try { return new org.json.JSONArray().put(new org.json.JSONObject().put("responseCode", code).put("transactionUUID", tx)).toString(); }
        catch (org.json.JSONException e) { return "[{\"responseCode\":\"1001\"}]"; }
    }
    private boolean allowedOrigin(String url) { return sameAllowedOrigin(url); }
    private boolean shouldInjectArk(String url) {
        if (!allowedOrigin(url)) return false;
        try {
            Uri uri = Uri.parse(url);
            // OBS renders its signed SSO response inside this page.  It is a
            // terminal callback, never an ArkSigner transport endpoint.
            return !("obs.saglik.gov.tr".equalsIgnoreCase(uri.getHost())
                    && "/Account/SsoLogin".equalsIgnoreCase(uri.getPath()));
        } catch (Exception ignored) { return false; }
    }
    private boolean adaletOrigin(String url) { return PortalOrigins.isAdalet(url); }
    private boolean edevletOrigin(String url) { return PortalOrigins.isEdevlet(url); }
    private boolean sameAllowedOrigin(String origin) {
        return PortalOrigins.mayBridge(origin, activePageUrl);
    }

    private static String commonName(String dn) {
        for (String part : dn.split("(?<!\\\\),")) {
            String p = part.trim(); if (p.regionMatches(true, 0, "CN=", 0, 3)) return p.substring(3).replace("\\,", ",");
        }
        return dn;
    }

    private static String commonNameARK(java.security.cert.X509Certificate cert) {
        try {
            X500Name x500Name = new X500Name(
                cert.getSubjectX500Principal().getName(X500Principal.RFC2253));
            RDN[] rdns = x500Name.getRDNs(BCStyle.CN);
            if (rdns.length == 0) return "";
            return IETFUtils.valueToString(rdns[0].getFirst().getValue());
        } catch (Exception e) {
            return "";
        }
    }

    /** Sertifikadan CN'yi BouncyCastle ile çeker (Türkçe karakterler düzgün). */
    private static String extractCN(java.security.cert.X509Certificate cert) {
        try {
            X500Name name = new X500Name(
                    cert.getSubjectX500Principal().getName(X500Principal.RFC2253));
            RDN[] rdns = name.getRDNs(BCStyle.CN);
            if (rdns.length == 0) return "";
            return IETFUtils.valueToString(rdns[0].getFirst().getValue());
        } catch (Exception e) {
            return "";
        }
    }

    /** Sertifikadan SERIALNUMBER (TCKN) değerini BouncyCastle ile çeker. */
    private static String extractTCKN(java.security.cert.X509Certificate cert) {
        try {
            X500Name name = new X500Name(
                    cert.getSubjectX500Principal().getName(X500Principal.RFC2253));
            RDN[] rdns = name.getRDNs(BCStyle.SERIALNUMBER);
            if (rdns.length == 0) return "";
            String value = IETFUtils.valueToString(rdns[0].getFirst().getValue());
            String digits = value.replaceAll("[^0-9]", "");
            return digits;  // 11 hane olmasa da döndür (portal kendi kontrol eder)
        } catch (Exception e) {
            return "";
        }
    }

    /** Sertifikanın issuer CN'sini BouncyCastle ile çeker. */
    private static String extractIssuerCN(java.security.cert.X509Certificate cert) {
        try {
            X500Name name = new X500Name(
                    cert.getIssuerX500Principal().getName(X500Principal.RFC2253));
            RDN[] rdns = name.getRDNs(BCStyle.CN);
            if (rdns.length == 0) return "";
            return IETFUtils.valueToString(rdns[0].getFirst().getValue());
        } catch (Exception e) {
            return "";
        }
    }

    /** Issuer DN'sini BouncyCastle ile temizleyin, 2.5.4.5'i SERIALNUMBER olarak yeniden yazın */
    private static String rebuildDn(javax.security.auth.x500.X500Principal principal) {
        try {
            X500Name name = new X500Name(principal.getName(X500Principal.RFC2253));
            RDN[] rdns = name.getRDNs();
            StringBuilder sb = new StringBuilder();
            for (RDN rdn : rdns) {
                if (sb.length() > 0) sb.append(',');
                String type = rdn.getFirst().getType().getId();
                // OID 2.5.4.5 → SERIALNUMBER
                if ("2.5.4.5".equals(type)) {
                    type = "SERIALNUMBER";
                }
                String value = IETFUtils.valueToString(rdn.getFirst().getValue());
                sb.append(type).append('=').append(value);
            }
            return sb.toString();
        } catch (Exception e) {
            return principal.getName(X500Principal.RFC2253);
        }
    }

    /**
     * Sertifikayı parse eder, SERIALNUMBER'ı UTF8String olarak yeniden kodlar.
     * UYARI: Bu, sertifikanın imzasını GEÇERSİZ kılar.
     * Sadece portalın certificateHex'i parse ederken TCKN'yi doğru okuması için kullanılır.
     */
    private static byte[] reencodeCertificateForPortal(byte[] originalDer) {
        try {
            // 1. Ham DER'i ASN.1 yapısına çöz
            ASN1Sequence certSeq = ASN1Sequence.getInstance(
                    ASN1Primitive.fromByteArray(originalDer));
            
            // Certificate ::= SEQUENCE { tbsCertificate TBSCertificate, ... }
            ASN1Sequence tbsSeq = ASN1Sequence.getInstance(certSeq.getObjectAt(0));
            
            // 2. TBSCertificate içindeki subject'i bul (index 5)
            // TBSCertificate ::= SEQUENCE {
            //   version [0] EXPLICIT Version DEFAULT v1,  -- index 0 (opsiyonel)
            //   serialNumber CertificateSerialNumber,     -- index 0 veya 1
            //   signature AlgorithmIdentifier,            -- index 1 veya 2
            //   issuer Name,                              -- index 2 veya 3
            //   validity Validity,                        -- index 3 veya 4
            //   subject Name,                             -- index 4 veya 5
            //   subjectPublicKeyInfo SubjectPublicKeyInfo,-- index 5 veya 6
            //   ...
            // }
            
            // Version varsa index'ler 1 kayar
            int subjectIndex = 5;
            ASN1Encodable first = tbsSeq.getObjectAt(0);
            if (first instanceof ASN1TaggedObject) {
                // version [0] EXPLICIT var, subject index 5
                subjectIndex = 5;
            } else {
                // version yok (v1), subject index 4
                subjectIndex = 4;
            }
            
            ASN1Sequence subjectSeq = ASN1Sequence.getInstance(tbsSeq.getObjectAt(subjectIndex));
            
            // 3. Subject içindeki her RDN'i gez, SERIALNUMBER'ı UTF8String'e çevir
            ASN1EncodableVector newRdns = new ASN1EncodableVector();
            for (int i = 0; i < subjectSeq.size(); i++) {
                ASN1Set rdnSet = ASN1Set.getInstance(subjectSeq.getObjectAt(i));
                ASN1EncodableVector newAtvs = new ASN1EncodableVector();
                for (int j = 0; j < rdnSet.size(); j++) {
                    ASN1Sequence atv = ASN1Sequence.getInstance(rdnSet.getObjectAt(j));
                    ASN1ObjectIdentifier oid = ASN1ObjectIdentifier.getInstance(atv.getObjectAt(0));
                    ASN1Encodable value = atv.getObjectAt(1);
                    
                    // SERIALNUMBER (2.5.4.5) ve PrintableString ise UTF8String'e çevir
                    if ("2.5.4.5".equals(oid.getId()) && value instanceof ASN1PrintableString) {
                        String str = ((ASN1PrintableString) value).getString();
                        newAtvs.add(new DERSequence(new ASN1Encodable[]{
                                oid, new DERUTF8String(str)
                        }));
                    } else {
                        newAtvs.add(atv);
                    }
                }
                newRdns.add(new DERSet(newAtvs));
            }
            
            ASN1Sequence newSubject = new DERSequence(newRdns);
            
            // 4. TBSCertificate'ı yeniden oluştur (subject değişti)
            ASN1EncodableVector newTbs = new ASN1EncodableVector();
            for (int i = 0; i < tbsSeq.size(); i++) {
                if (i == subjectIndex) {
                    newTbs.add(newSubject);
                } else {
                    newTbs.add(tbsSeq.getObjectAt(i));
                }
            }
            
            // 5. Certificate'ı yeniden oluştur
            ASN1EncodableVector newCert = new ASN1EncodableVector();
            newCert.add(new DERSequence(newTbs));
            for (int i = 1; i < certSeq.size(); i++) {
                newCert.add(certSeq.getObjectAt(i));
            }
            
            return new DERSequence(newCert).getEncoded("DER");
        } catch (Exception e) {
            android.util.Log.e("REENC", "Sertifika yeniden kodlanamadı", e);
            return originalDer;
        }
    }

    /*private static String subjectSerialArk(java.security.cert.X509Certificate cert) {
        try {
            // String DN yerine doğrudan X500Principal kullan
            X500Principal principal = cert.getSubjectX500Principal();
            X500Name x500Name = new X500Name(principal.getName(X500Principal.RFC2253));
            
            // SERIALNUMBER için BCStyle kullan (OID 2.5.4.5)
            RDN[] rdns = x500Name.getRDNs(BCStyle.SERIALNUMBER);
            if (rdns.length == 0) return "";
            
            String value = IETFUtils.valueToString(rdns[0].getFirst().getValue());
            
            // Sadece rakamları al (TCKN 11 haneli)
            String digits = value.replaceAll("[^0-9]", "");
            return digits.length() == 11 ? digits : "";
        } catch (Exception e) {
            return "";
        }
    }*/

    private static String subjectSerial(String dn) {
        try {
            org.bouncycastle.asn1.x500.RDN[] r = new org.bouncycastle.asn1.x500.X500Name(dn)
                    .getRDNs(org.bouncycastle.asn1.x500.style.BCStyle.SERIALNUMBER);
            return r.length == 0 ? "" : org.bouncycastle.asn1.x500.style.IETFUtils.valueToString(r[0].getFirst().getValue());
        } catch (RuntimeException e) { return ""; }
    }

    private static String subjectNameSurname(String dn) {
        String cn = commonName(dn);
        String[] words = cn.trim().split("\\s+");
        if (words.length < 2) return cn;
        return words[words.length - 1] + " " + words[0];
    }

    /** CN'yi "Ad Soyad" formatından "Soyad Ad" formatına çevirir. */
    private static String subjectNameSurnameFromCN(String cn) {
        if (cn == null || cn.trim().isEmpty()) return "";
        String[] words = cn.trim().split("\\s+");
        if (words.length < 2) return cn;
        return words[words.length - 1] + " " + words[0];
    }

/*
    private static String subjectNameSurnameARK(String dn) {
        String cn = commonNameARK(dn);
        String[] words = cn.trim().split("\\s+");
        if (words.length < 2) return cn;
        return words[words.length - 1] + " " + words[0];
    }
*/

    private static byte[] arkPayload(org.json.JSONObject task) throws Exception {
        Object value = task.has("dataToSignBA") ? task.get("dataToSignBA") : task.opt("dataBase64");
        if (value instanceof org.json.JSONArray) {
            org.json.JSONArray array = (org.json.JSONArray) value;
            byte[] bytes = new byte[array.length()];
            for (int i = 0; i < array.length(); i++) bytes[i] = (byte) array.getInt(i);
            return bytes;
        }
        String encoded = value == null ? "" : String.valueOf(value);
        if (encoded.isEmpty()) encoded = task.optString("data", "");
        if (encoded.isEmpty()) return new byte[0];
        try { return android.util.Base64.decode(encoded, android.util.Base64.DEFAULT); }
        catch (IllegalArgumentException e) { return encoded.getBytes(StandardCharsets.UTF_8); }
    }

    private boolean adaletLocalUrl(String raw) {
        try {
            URI u = URI.create(raw);
            String h = u.getHost() == null ? "" : u.getHost().toLowerCase(Locale.ROOT);
            return (h.equals("localhost") || h.equals("127.0.0.1"))
                    && (u.getPort() == -1 || u.getPort() == 5975)
                    && u.getPath() != null && (u.getPath().startsWith("/api/v1/")
                    || u.getPath().equals("/client/info"));
        } catch (Exception e) { return false; }
    }

    private void handleAdaletRequest(String id, String method, String rawUrl, String body) {
        try {
            URI u = URI.create(rawUrl);
            String path = u.getPath();
            traceArk("Adalet istek: " + method.toUpperCase(Locale.ROOT) + " "
                    + (path.contains("/getCertificate/") ? "/signature/getCertificate" : path));
            if ("GET".equalsIgnoreCase(method) && path.equals("/client/info")) {
                org.json.JSONObject info = new org.json.JSONObject()
                        .put("hostName", "EImzaOne").put("osVersion", "Android " + android.os.Build.VERSION.RELEASE)
                        .put("systemManufacturer", android.os.Build.MANUFACTURER).put("systemModel", android.os.Build.MODEL)
                        .put("productId", "app.eimza.mobile").put("registeredOwner", "")
                        .put("biosVersion", "").put("user", "Android")
                        .put("networkCards", new org.json.JSONArray());
                completeAdalet(id, adaletEnvelope(AdaletDeviceInfo.encrypt(info.toString()), "ADALET_SUCCESS", "İstemci hazır"));
                return;
            }
            if ("GET".equalsIgnoreCase(method) && path.matches(".*/signature/getCertificate/[^/]+/?$")) {
                String pathId = path.replaceAll(".*/signature/getCertificate/", "").replaceAll("/$", "");
                completeAdalet(id, adaletCertificate(pathId));
                return;
            }
            if ("GET".equalsIgnoreCase(method) && path.endsWith("/signature/getCertificates")) {
                completeAdalet(id, adaletCertificates());
            } else if ("GET".equalsIgnoreCase(method) && path.endsWith("/signature/getCertificate")) {
                org.json.JSONObject q = body != null && !body.trim().isEmpty()
                        ? new org.json.JSONObject(body) : queryJson(u.getRawQuery());
                completeAdalet(id, adaletCertificate(q.optString("certificateId", "")));
            } else if ("POST".equalsIgnoreCase(method) && path.endsWith("/signature/sign")) {
                org.json.JSONObject request = new org.json.JSONObject(body == null ? "{}" : body);
                signAdaletContent(id, request);
            } else {
                completeAdalet(id, adaletEnvelope(null, "ADALET_ERROR", "Desteklenmeyen Adalet imza işlemi"));
            }
        } catch (Exception e) {
            traceArk("Adalet istek hatası: " + e.getClass().getSimpleName());
            completeAdalet(id, adaletEnvelope(null, "ADALET_ERROR", "Adalet isteği işlenemedi"));
        }
    }

    private String adaletCertificates() throws Exception {
        org.json.JSONArray list = new org.json.JSONArray();
        for (AkisSignerBackend.ArkCertificate c : akisBackend.arkCertificates()) {
            java.security.cert.X509Certificate x = c.certificate;
            org.json.JSONObject dto = new org.json.JSONObject().put("certificateId", c.id)
                    .put("subject", x.getSubjectX500Principal().getName())
                    .put("issuer", x.getIssuerX500Principal().getName())
                    .put("notBefore", x.getNotBefore().toInstant().toString())
                    .put("notAfter", x.getNotAfter().toInstant().toString())
                    .put("certSerial", c.serial).put("subjectSerial", subjectSerial(x.getSubjectX500Principal().getName()))
                    .put("valid", !x.getNotBefore().after(new java.util.Date()) && !x.getNotAfter().before(new java.util.Date()))
                    .put("default", list.length() == 0).put("cardReaderName", AndroidCardSession.readerName())
                    .put("sigAlgorithm", x.getSigAlgName()).put("pubKeyAlgorithm", x.getPublicKey().getAlgorithm())
                    .put("digestAlgorithm", "SHA-256");
            list.put(dto);
        }
        org.json.JSONArray readers = new org.json.JSONArray().put(new org.json.JSONObject()
                .put("terminal", AndroidCardSession.readerName()).put("ready", true)
                .put("serialNumber", "").put("certificates", list));
        return adaletEnvelope(readers, "ADALET_SUCCESS", "İşlem başarıyla tamamlandı");
    }

    private String adaletCertificate(String id) throws Exception {
        for (AkisSignerBackend.ArkCertificate c : akisBackend.arkCertificates()) if (c.id.equals(id)) {
            return adaletEnvelope(android.util.Base64.encodeToString(c.der, android.util.Base64.NO_WRAP),
                    "ADALET_SUCCESS", "İşlem başarıyla tamamlandı");
        }
        return adaletEnvelope(null, "ADALET_CERTIFICATE_NOT_FOUND", "Sertifika bulunamadı");
    }

    private void showSigningFailure(String provider, Throwable error) {
        StringBuilder codes = new StringBuilder(provider + " imza hatası");
        Throwable cause = error;
        for (int depth = 0; cause != null && depth < 8; depth++, cause = cause.getCause()) {
            codes.append(" → ").append(cause.getClass().getSimpleName());
            for (StackTraceElement frame : cause.getStackTrace()) {
                if (frame.getClassName().startsWith("tubitak.akis.") || frame.getClassName().startsWith("app.eimza.mobile.Akis")) {
                    codes.append(" (").append(frame.getMethodName()).append(")"); break;
                }
            }
            if (cause instanceof tubitak.akis.cif.akisExceptions.AkisSWException)
                codes.append(" SW=").append(Long.toHexString(((tubitak.akis.cif.akisExceptions.AkisSWException) cause).getErrorCode()).toUpperCase(Locale.ROOT));
            if (cause.getCause() == cause) break;
        }
        // Exception types and card status only. Do not expose request/PIN contents.
        String cardStep = akisBackend.cardFailureDetail();
        if (!cardStep.isEmpty()) codes.append("; adım: ").append(cardStep);
        traceArk(codes.toString());
        DiagnosticLogger.e(DiagnosticLogger.Tag.SIGN, codes.toString(), error);
    }

    private void signAdaletContent(String id, org.json.JSONObject request) throws Exception {
        String certId = request.optString("certificateId", "");
        AkisSignerBackend.ArkCertificate cert = null;
        for (AkisSignerBackend.ArkCertificate c : akisBackend.arkCertificates()) if (c.id.equals(certId)) cert = c;
        if (cert == null) { completeAdalet(id, adaletEnvelope(null, "ADALET_CERTIFICATE_NOT_FOUND", "Sertifika bulunamadı")); return; }
        // The supplied Adalet tray calls this field pubKey, but sends the whole
        // DER certificate (SignatureFlowManagerImpl.getCertificate), not SPKI.
        String pubKey = android.util.Base64.encodeToString(cert.der, android.util.Base64.NO_WRAP);
        org.json.JSONObject fetched = adaletFetchContent(pubKey);
        org.json.JSONObject data = fetched.optJSONObject("data");
        traceArk("Adalet içerik yanıtı: data=" + jsonType(fetched.opt("data")) + "; durum="
                + (fetched.optJSONObject("metadata") == null ? "bilinmiyor"
                : fetched.optJSONObject("metadata").optString("STATUS", "SUCCESS")));
        if (data == null || !data.has("content") || !data.has("txId")) {
            completeAdalet(id, adaletEnvelope(null, "ADALET_ERROR", "UYAP imzalanacak içeriği döndürmedi"));
            return;
        }
        String signedContent = data.optString("content", "");
        String responseTx = data.optString("txId", "");
        // The original tray signs content.getBytes(), so even Base64-looking text
        // is literal UTF-8 content here. Decoding it changes the signed bytes.
        byte[] bytes = signedContent.getBytes(StandardCharsets.UTF_8);
        final AkisSignerBackend.ArkCertificate selected = cert;
        final byte[] payload = bytes;
        final String finalTx = responseTx;
        final char[] suppliedPin = request.optString("password", "").toCharArray();
        request.remove("password");
        runOnUiThread(() -> {
            EditText pin = new EditText(this);
            pin.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_VARIATION_PASSWORD);
            new AlertDialog.Builder(this).setTitle("UYAP e-imza isteği")
                    .setMessage("Adalet portalı, sertifika " + commonName(selected.certificate.getSubjectX500Principal().getName())
                            + " ile " + payload.length + " bayt imzalamak istiyor. "
                            + (suppliedPin.length > 0 ? "Portalda girdiğiniz PIN bu işlem için kartta doğrulanacak." : "Kart PIN'ini girin."))
                    .setView(suppliedPin.length == 0 ? pin : null)
                    .setOnCancelListener(d -> {
                        java.util.Arrays.fill(suppliedPin, '\0');
                        completeAdalet(id, adaletEnvelope(null, "ADALET_ERROR", "İmza iptal edildi"));
                    })
                    .setNegativeButton("İptal", (d, w) -> {
                        java.util.Arrays.fill(suppliedPin, '\0');
                        completeAdalet(id, adaletEnvelope(null, "ADALET_ERROR", "İmza iptal edildi"));
                    })
                    .setPositiveButton("İmzala", (d, w) -> {
                        char[] secret = suppliedPin.length > 0 ? suppliedPin : pin.getText().toString().toCharArray();
                        pin.setText("");
                        signerWorker.execute(() -> {
                            try {
                                byte[] cms = CadesSupport.sign(payload, selected.id, selected.certificate, secret, akisBackend, false);
                                org.json.JSONObject result = new org.json.JSONObject().put("signedData", android.util.Base64.encodeToString(cms, android.util.Base64.NO_WRAP))
                                        .put("txId", finalTx);
                                completeAdalet(id, adaletEnvelope(result, "ADALET_SUCCESS", "İşlem başarıyla tamamlandı"));
                            } catch (Exception e) {
                                java.util.Arrays.fill(secret, '\0');
                                showSigningFailure("UYAP", e);
                                completeAdalet(id, adaletEnvelope(null, "ADALET_ERROR", "Kartla imzalama başarısız; Kart / Menü tanısına bakın"));
                            } finally {
                                java.util.Arrays.fill(secret, '\0');
                                java.util.Arrays.fill(suppliedPin, '\0');
                            }
                        });
                    }).show();
        });
    }

    private org.json.JSONObject adaletFetchContent(String pubKey) throws Exception {
        URL url = new URL("https://bedesten.adalet.gov.tr/imza/api/v1/signature/getContentToBeSigned");
        HttpURLConnection c = (HttpURLConnection) url.openConnection();
        c.setRequestMethod("POST"); c.setConnectTimeout(15000); c.setReadTimeout(30000); c.setDoOutput(true);
        c.setRequestProperty("Content-Type", "application/json");
        byte[] body = new org.json.JSONObject().put("pubKey", pubKey).toString().getBytes(StandardCharsets.UTF_8);
        c.getOutputStream().write(body);
        int code = c.getResponseCode();
        java.io.InputStream in = code < 400 ? c.getInputStream() : c.getErrorStream();
        java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
        byte[] buf = new byte[8192]; int n; while ((n = in.read(buf)) >= 0) out.write(buf, 0, n);
        c.disconnect();
        if (code >= 400) throw new java.io.IOException("Adalet content HTTP " + code);
        return new org.json.JSONObject(new String(out.toByteArray(), StandardCharsets.UTF_8));
    }

    private static org.json.JSONObject queryJson(String raw) throws Exception {
        org.json.JSONObject out = new org.json.JSONObject();
        if (raw == null) return out;
        for (String pair : raw.split("&")) { String[] p = pair.split("=", 2); if (p.length == 2) out.put(java.net.URLDecoder.decode(p[0], "UTF-8"), java.net.URLDecoder.decode(p[1], "UTF-8")); }
        return out;
    }

    private static String adaletEnvelope(Object data, String code, String message) {
        try {
            org.json.JSONObject metadata = new org.json.JSONObject();
            if (!"ADALET_SUCCESS".equals(code)) metadata.put("STATUS", "ERROR").put("MESSAGE", message);
            return new org.json.JSONObject().put("data", data == null ? org.json.JSONObject.NULL : data)
                    .put("metadata", metadata).toString();
        } catch (Exception e) { return "{}"; }
    }

    private void completeAdalet(String id, String json) {
        if (id == null) return;
        try {
            org.json.JSONObject reply = new org.json.JSONObject(json);
            org.json.JSONObject metadata = reply.optJSONObject("metadata");
            traceArk("Adalet yanıt: data=" + jsonType(reply.opt("data")) + "; durum="
                    + (metadata == null ? "bilinmiyor" : metadata.optString("STATUS", "SUCCESS")));
        } catch (Exception ignored) { traceArk("Adalet yanıtı ayrıştırılamadı"); }
        runOnUiThread(() -> {
            WebView target = activeWebView == null ? webView : activeWebView;
            if (target == null) return;
            String quotedId = org.json.JSONObject.quote(id), quotedJson = org.json.JSONObject.quote(json);
            target.evaluateJavascript("window.__eimzaAdaletResolve && window.__eimzaAdaletResolve(" + quotedId + "," + quotedJson + ")", null);
        });
    }
    private static String jsonType(Object value) {
        if (value == null || value == org.json.JSONObject.NULL) return "null";
        if (value instanceof org.json.JSONObject) return "object";
        if (value instanceof org.json.JSONArray) return "array";
        if (value instanceof String) return "string";
        return "scalar";
    }
    private static String hex(byte[] bytes) {
        StringBuilder out = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) out.append(String.format(Locale.ROOT, "%02X", b & 0xff));
        return out.toString();
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (resultCode != RESULT_OK || data == null || data.getData() == null) return;
        Uri uri = data.getData();
        if (requestCode == REQUEST_UDF_OPEN) {
            loadUdf(uri);
        } else if (requestCode == REQUEST_UDF_SAVE && pendingSignedUdf != null) {
            try (java.io.OutputStream out = getContentResolver().openOutputStream(uri)) {
                if (out == null) throw new java.io.IOException("Çıktı açılamadı");
                out.write(pendingSignedUdf);
                udfStatus.setText("İmzalı UDF çıktısı kaydedildi.");
                debugLog("İmzalı UDF kaydedildi: " + uri);
            } catch (Exception e) {
                udfStatus.setText("İmzalı UDF kaydedilemedi: " + e.getMessage());
            } finally {
                pendingSignedUdf = null;
            }
        }
    }

    @Override
    public void onBackPressed() {
        if (browserPanel != null && browserPanel.getVisibility() == View.VISIBLE
                && activeWebView != null && activeWebView.canGoBack()) activeWebView.goBack();
        else if (browserPanel != null && browserPanel.getVisibility() == View.VISIBLE) {
            browserPanel.setVisibility(View.GONE);
            menuPanel.setVisibility(View.VISIBLE);
        }
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        signerWorker.shutdownNow();
        if (loopbackServer != null) loopbackServer.close();
        if (akisBackend != null) akisBackend.close();
        if (usbProbe != null) usbProbe.close();
        for (WebView tab : new java.util.ArrayList<>(browserTabs)) {
            try { tab.stopLoading(); tab.destroy(); } catch (Exception ignored) { }
        }
        browserTabs.clear();
        super.onDestroy();
    }
}
