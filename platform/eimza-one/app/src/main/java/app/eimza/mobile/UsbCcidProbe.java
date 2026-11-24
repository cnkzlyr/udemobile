package app.eimza.mobile;

import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.hardware.usb.UsbConstants;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbDeviceConnection;
import android.hardware.usb.UsbEndpoint;
import android.hardware.usb.UsbInterface;
import android.hardware.usb.UsbManager;
import android.os.Build;
import java.io.IOException;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Android USB Host CCID session manager.
 * Detects and connects USB smart card tokens (ArkSigner, TürkTrust TBB, Kamu SM ATR19).
 * Automatically negotiates CCID exchange level (APDU direct or T=1/T=0 TPDU).
 */
final class UsbCcidProbe implements AutoCloseable {
    interface Listener { void onStatus(String message); }

    private static final int CCID_CLASS = 0x0B;

    private final Context context;
    private final UsbManager manager;
    private final Listener listener;
    private final String permissionAction;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private boolean receiverRegistered;
    private final Object cardLock = new Object();
    private UsbDevice activeDevice;
    private UsbInterface activeInterface;
    private UsbDeviceConnection activeConnection;
    private UsbCcidTransport activeTransport;
    private String activeReaderName;
    private byte[] activeAtr;
    private boolean activeIsApduLevel;

    private final BroadcastReceiver receiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            String action = intent.getAction();
            if (permissionAction.equals(action)) {
                UsbDevice device = getDevice(intent);
                if (device == null) return;
                if (intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false)) {
                    DiagnosticLogger.i(DiagnosticLogger.Tag.USB, "USB izni verildi: " + device.getProductName());
                    worker.execute(() -> inspect(device));
                } else {
                    DiagnosticLogger.w(DiagnosticLogger.Tag.USB, "USB izni reddedildi: " + device.getProductName());
                    listener.onStatus("USB izni verilmedi; okuyucuyu tara düğmesine basın.");
                }
            } else if (UsbManager.ACTION_USB_DEVICE_ATTACHED.equals(action)) {
                UsbDevice device = getDevice(intent);
                DiagnosticLogger.i(DiagnosticLogger.Tag.USB, "USB aygıt takıldı: " + (device != null ? device.getProductName() : "Bilinmiyor"));
                scan();
            } else if (UsbManager.ACTION_USB_DEVICE_DETACHED.equals(action)) {
                UsbDevice device = getDevice(intent);
                DiagnosticLogger.i(DiagnosticLogger.Tag.USB, "USB aygıt çıkarıldı: " + (device != null ? device.getProductName() : "Bilinmiyor"));
                synchronized (cardLock) {
                    if (activeDevice != null && device != null && activeDevice.getDeviceId() == device.getDeviceId()) {
                        closeActiveLocked();
                        listener.onStatus("E-imza tokenı çıkarıldı.");
                    }
                }
            }
        }
    };

    UsbCcidProbe(Context context, Listener listener) {
        this.context = context.getApplicationContext();
        this.manager = (UsbManager) context.getSystemService(Context.USB_SERVICE);
        this.listener = listener;
        AndroidCardSession.attach(this);
        this.permissionAction = context.getPackageName() + ".USB_PERMISSION";

        IntentFilter filter = new IntentFilter();
        filter.addAction(permissionAction);
        filter.addAction(UsbManager.ACTION_USB_DEVICE_ATTACHED);
        filter.addAction(UsbManager.ACTION_USB_DEVICE_DETACHED);

        if (Build.VERSION.SDK_INT >= 33) {
            this.context.registerReceiver(receiver, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            this.context.registerReceiver(receiver, filter);
        }
        receiverRegistered = true;
        DiagnosticLogger.i(DiagnosticLogger.Tag.USB, "UsbCcidProbe başlatıldı");
    }

    void scan() {
        if (manager == null) {
            listener.onStatus("Android USB Host servisi bulunamadı.");
            return;
        }
        boolean retainedDeviceFound = false;
        for (UsbDevice device : manager.getDeviceList().values()) {
            UsbInterface iface = findCcid(device);
            if (iface == null) continue;

            synchronized (cardLock) {
                if (activeDevice != null && activeDevice.getDeviceId() == device.getDeviceId()
                        && activeTransport != null) {
                    retainedDeviceFound = true;
                    listener.onStatus(activeReaderName + " bağlı; kart oturumu uygulama içinde açık.");
                    return;
                }
            }
            synchronized (cardLock) {
                if (activeDevice != null) closeActiveLocked();
            }
            if (!manager.hasPermission(device)) {
                String devName = device.getProductName() != null ? device.getProductName() : String.format(Locale.ROOT, "%04X:%04X", device.getVendorId(), device.getProductId());
                DiagnosticLogger.i(DiagnosticLogger.Tag.USB, "CCID aygıt için izin isteniyor: " + devName);
                listener.onStatus("CCID okuyucu (" + devName + ") bulundu; Android USB izni bekleniyor.");
                Intent intent = new Intent(permissionAction).setPackage(context.getPackageName());
                int flags = PendingIntent.FLAG_UPDATE_CURRENT;
                if (Build.VERSION.SDK_INT >= 31) flags |= PendingIntent.FLAG_MUTABLE;
                PendingIntent pending = PendingIntent.getBroadcast(context, device.getDeviceId(), intent, flags);
                manager.requestPermission(device, pending);
                return;
            }
            worker.execute(() -> inspect(device));
            return;
        }
        if (!retainedDeviceFound) {
            synchronized (cardLock) { if (activeDevice != null) closeActiveLocked(); }
        }
        listener.onStatus("CCID okuyucu bulunamadı. OTG bağlantısını ve okuyucuyu kontrol edin.");
    }

    private void inspect(UsbDevice device) {
        UsbInterface iface = findCcid(device);
        if (iface == null) {
            listener.onStatus("Seçilen USB aygıtında CCID arayüzü yok.");
            return;
        }
        UsbEndpoint input = null;
        UsbEndpoint output = null;
        for (int i = 0; i < iface.getEndpointCount(); i++) {
            UsbEndpoint ep = iface.getEndpoint(i);
            if (ep.getType() != UsbConstants.USB_ENDPOINT_XFER_BULK) continue;
            if (ep.getDirection() == UsbConstants.USB_DIR_IN) input = ep;
            else if (ep.getDirection() == UsbConstants.USB_DIR_OUT) output = ep;
        }
        if (input == null || output == null) {
            listener.onStatus("CCID okuyucu uç noktaları bulunamadı.");
            return;
        }

        UsbDeviceConnection connection = manager.openDevice(device);
        if (connection == null) {
            listener.onStatus("USB bağlantısı açılamadı; izni yenileyip tekrar deneyin.");
            return;
        }
        try {
            if (!connection.claimInterface(iface, false)) {
                listener.onStatus("CCID arayüzü alınamadı; başka bir uygulama okuyucuyu kullanıyor olabilir.");
                return;
            }

            // Check CCID descriptor for exchange level (APDU level vs TPDU level)
            boolean isApduLevel = checkApduLevelFromDescriptors(connection.getRawDescriptors());

            UsbCcidTransport transport = new UsbCcidTransport(connection, input, output);
            transport.setApduLevel(isApduLevel);

            int icc = transport.slotStatus();
            String label = device.getProductName();
            if (label == null || label.trim().isEmpty()) {
                label = String.format(Locale.ROOT, "USB %04X:%04X", device.getVendorId(), device.getProductId());
            }

            DiagnosticLogger.i(DiagnosticLogger.Tag.USB, String.format(Locale.ROOT,
                    "USB CCID Aygıt açıldı: %s (VID:%04X PID:%04X, SlotStatus=%d, APDUMode=%b)",
                    label, device.getVendorId(), device.getProductId(), icc, isApduLevel));

            if (icc == 2) {
                listener.onStatus(label + " bağlı; kart takılı değil.");
            } else {
                byte[] atr = transport.powerOn();
                if (atr == null || atr.length < 2) {
                    throw new IOException("Karttan geçerli bir ATR alınamadı");
                }

                // If reader didn't report APDU level from descriptor, check ATR protocol support
                boolean t1 = supportsT1(atr);
                boolean t0 = supportsT0(atr);
                DiagnosticLogger.i(DiagnosticLogger.Tag.CARD, String.format(Locale.ROOT,
                        "Kart ATR okundu (%d bayt). Desteklenen protokoller: T=0:%b, T=1:%b",
                        atr.length, t0, t1));

                // If T=1 is not supported by card and reader is not APDU level, adapt to APDU direct
                if (!t1 && !isApduLevel) {
                    DiagnosticLogger.w(DiagnosticLogger.Tag.CARD, "Kart T=1 bildirmiyor; doğrudan APDU moduna geçiliyor");
                    transport.setApduLevel(true);
                    isApduLevel = true;
                }

                synchronized (cardLock) {
                    closeActiveLocked();
                    activeDevice = device;
                    activeInterface = iface;
                    activeConnection = connection;
                    activeTransport = transport;
                    activeReaderName = label;
                    activeAtr = atr.clone();
                    activeIsApduLevel = isApduLevel;
                    connection = null; // retained by the active card session
                }
                listener.onStatus(label + " bağlı; " + (isApduLevel ? "APDU" : "T=1") + " kart oturumu hazır.");
            }
        } catch (Exception e) {
            String message = e.getMessage();
            DiagnosticLogger.e(DiagnosticLogger.Tag.USB, "CCID kart aktarımı başarısız", e);
            listener.onStatus("CCID kart aktarımı başarısız: " + (message == null ? e.getClass().getSimpleName() : message));
        } finally {
            if (connection != null) {
                try { connection.releaseInterface(iface); } catch (RuntimeException ignored) { }
                connection.close();
            }
        }
    }

    /**
     * Inspects raw USB configuration descriptors to find CCID descriptor (bDescriptorType=0x21)
     * and examines dwFeatures:
     * Bit 18 (0x00040000) = Short APDU level exchange
     * Bit 19 (0x00080000) = Short and Extended APDU level exchange
     */
    private static boolean checkApduLevelFromDescriptors(byte[] raw) {
        if (raw == null || raw.length < 54) return false;
        for (int i = 0; i <= raw.length - 54; i++) {
            int len = raw[i] & 0xFF;
            int type = raw[i + 1] & 0xFF;
            if (len >= 54 && type == 0x21) {
                // CCID class descriptor found
                int dwFeatures = (raw[i + 40] & 0xFF) | ((raw[i + 41] & 0xFF) << 8)
                        | ((raw[i + 42] & 0xFF) << 16) | ((raw[i + 43] & 0xFF) << 24);
                boolean apduLevel = (dwFeatures & 0x00040000) != 0 || (dwFeatures & 0x00080000) != 0;
                DiagnosticLogger.d(DiagnosticLogger.Tag.USB, String.format(Locale.ROOT,
                        "CCID dwFeatures: 0x%08X (APDU-level: %b)", dwFeatures, apduLevel));
                return apduLevel;
            }
        }
        return false;
    }

    /** Exchanges one ISO 7816 APDU over the retained USB session. Must be called off the UI thread. */
    byte[] transmit(byte[] apdu) throws IOException {
        synchronized (cardLock) {
            if (activeTransport == null) throw new IOException("Aktif USB kart oturumu yok.");
            try {
                return activeTransport.transmit(apdu);
            } catch (IOException e) {
                String message = e.getMessage();
                if (message != null && (message.contains("USB") || message.contains("zaman aşımı"))) {
                    closeActiveLocked();
                    listener.onStatus("USB kart oturumu koptu; okuyucuyu yeniden tarayın.");
                }
                throw e;
            }
        }
    }

    String activeReaderName() {
        synchronized (cardLock) { return activeReaderName; }
    }

    byte[] activeAtr() {
        synchronized (cardLock) { return activeAtr == null ? null : activeAtr.clone(); }
    }

    UsbDevice activeDevice() {
        synchronized (cardLock) { return activeDevice; }
    }

    boolean isApduLevel() {
        synchronized (cardLock) { return activeIsApduLevel; }
    }

    boolean isCardPresent() throws IOException {
        synchronized (cardLock) {
            if (activeTransport == null) return false;
            return activeTransport.slotStatus() != 2;
        }
    }

    private void closeActiveLocked() {
        if (activeTransport != null) activeTransport.powerOff();
        if (activeConnection != null) {
            try { if (activeInterface != null) activeConnection.releaseInterface(activeInterface); }
            catch (RuntimeException ignored) { }
            activeConnection.close();
        }
        activeDevice = null;
        activeInterface = null;
        activeConnection = null;
        activeTransport = null;
        activeReaderName = null;
        activeAtr = null;
        activeIsApduLevel = false;
    }

    private static UsbInterface findCcid(UsbDevice device) {
        for (int i = 0; i < device.getInterfaceCount(); i++) {
            UsbInterface candidate = device.getInterface(i);
            if (candidate.getInterfaceClass() == CCID_CLASS) return candidate;
        }
        return null;
    }

    private static boolean supportsT1(byte[] atr) {
        if (atr == null || atr.length < 2) return false;
        int y = (atr[1] >>> 4) & 15;
        int i = 2;
        boolean sawTd = false;
        boolean t1 = false;
        while (y != 0) {
            if ((y & 1) != 0) i++;
            if ((y & 2) != 0) i++;
            if ((y & 4) != 0) i++;
            if ((y & 8) != 0) {
                if (i >= atr.length) return false;
                int td = atr[i++] & 255;
                sawTd = true;
                if ((td & 15) == 1) t1 = true;
                y = (td >>> 4) & 15;
            } else y = 0;
            if (i > atr.length) return false;
        }
        return sawTd && t1;
    }

    private static boolean supportsT0(byte[] atr) {
        if (atr == null || atr.length < 2) return false;
        int y = (atr[1] >>> 4) & 15;
        int i = 2;
        if ((y & 8) == 0) return true; // Default is T=0 when no TD1 is specified
        while (y != 0) {
            if ((y & 1) != 0) i++;
            if ((y & 2) != 0) i++;
            if ((y & 4) != 0) i++;
            if ((y & 8) != 0) {
                if (i >= atr.length) return true;
                int td = atr[i++] & 255;
                if ((td & 15) == 0) return true;
                y = (td >>> 4) & 15;
            } else y = 0;
            if (i > atr.length) return true;
        }
        return false;
    }

    private static UsbDevice getDevice(Intent intent) {
        if (Build.VERSION.SDK_INT >= 33) return intent.getParcelableExtra(UsbManager.EXTRA_DEVICE, UsbDevice.class);
        //noinspection deprecation
        return (UsbDevice) intent.getParcelableExtra(UsbManager.EXTRA_DEVICE);
    }

    @Override public void close() {
        synchronized (cardLock) { closeActiveLocked(); }
        AndroidCardSession.detach(this);
        if (receiverRegistered) {
            try { context.unregisterReceiver(receiver); } catch (IllegalArgumentException ignored) { }
            receiverRegistered = false;
        }
        worker.shutdownNow();
    }
}
