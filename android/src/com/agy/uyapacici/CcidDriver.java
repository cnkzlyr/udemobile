package com.agy.uyapacici;

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
import android.util.Base64;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;

/**
 * 🏛️ CanEditor Android Yerel USB Host CCID Akıllı Kart & E-İmza Sürücüsü
 * 
 * Rootsuz, Termux gerektirmeyen, doğrudan Android UsbManager üzerinden çalışan
 * yerel USB CCID (Chip/Smart Card Interface Devices) haberleşme ve imzalama motoru.
 * 
 * Desteklenen Türk Hukuk E-İmza Donanımları:
 * - SafeNet eToken 5110 / 5100 (Kırmızı Token / Barokart / TNB / TürkTrust)
 * - ACS ACR38 / ACR39 (Türkiye Barolar Birliği Standart USB Okuyucu)
 * - ArkSigner USB Kriptografik Token
 * - TÜBİTAK UEKAE AKİS (Milli Akıllı Kart İşletim Sistemi)
 * - Gemalto / Thales IDPrime / e-Tuğra / E-Güven akıllı kartları
 */
public class CcidDriver {
    private static final String TAG = "CanEditor_CcidDriver";
    public static final String ACTION_USB_PERMISSION = "com.agy.uyapacici.USB_PERMISSION";

    private static CcidDriver instance;
    private final Context context;
    private final UsbManager usbManager;

    private UsbDevice connectedDevice;
    private UsbDeviceConnection activeConnection;
    private UsbInterface activeInterface;
    private UsbEndpoint endpointIn;
    private UsbEndpoint endpointOut;

    private byte sequenceNumber = 0;
    private byte[] lastAtr = null;
    private String detectedCardType = "5070 Sayılı Kanuna Uyumlu Nitelikli E-İmza Kartı";
    private CardCertificateInfo currentCertificateInfo = null;

    public static synchronized CcidDriver getInstance(Context ctx) {
        if (instance == null) {
            instance = new CcidDriver(ctx.getApplicationContext());
        }
        return instance;
    }

    private CcidDriver(Context context) {
        this.context = context;
        this.usbManager = (UsbManager) context.getSystemService(Context.USB_SERVICE);
    }

    /** Akıllı kart sertifika meta verisi */
    public static class CardCertificateInfo {
        public String certificateId = "CERT_0";
        public String subject = "";
        public String issuer = "";
        public String serial = "";
        public String notAfter = "";
        public String terminal = "CanEditor USB CCID";
        public byte[] derBytes = null;

        public JSONObject toJson() {
            JSONObject obj = new JSONObject();
            try {
                obj.put("id", certificateId);
                obj.put("subject", subject);
                obj.put("issuer", issuer);
                obj.put("serial", serial);
                obj.put("validUntil", notAfter);
                obj.put("terminal", terminal);
            } catch (Exception ignored) {}
            return obj;
        }
    }

    /** USB Cihazını Bul ve Bağlan */
    public synchronized boolean scanAndConnect() {
        if (usbManager == null) return false;
        HashMap<String, UsbDevice> deviceList = usbManager.getDeviceList();
        if (deviceList == null || deviceList.isEmpty()) {
            disconnect();
            return false;
        }

        for (UsbDevice device : deviceList.values()) {
            if (isCcidDevice(device)) {
                if (!usbManager.hasPermission(device)) {
                    requestPermission(device);
                    return false;
                }
                return connectDevice(device);
            }
        }
        return false;
    }

    /** Bir USB cihazının CCID Akıllı Kart Okuyucusu olup olmadığını tespit et */
    public static boolean isCcidDevice(UsbDevice device) {
        if (device == null) return false;

        // 1. Cihaz seviyesinde Class 0x0B (CCID)
        if (device.getDeviceClass() == 11) return true;

        // 2. Arayüzler içinde Class 11 (0x0B) var mı?
        for (int i = 0; i < device.getInterfaceCount(); i++) {
            UsbInterface iface = device.getInterface(i);
            if (iface.getInterfaceClass() == 11) return true;
        }

        // 3. Bilinen Vendor ID Eşleşmeleri
        int vid = device.getVendorId();
        if (vid == 0x072F || // ACS ACR38/39 (TBB Standart)
            vid == 0x0529 || // SafeNet eToken (Kırmızı Token)
            vid == 0x2CE3 || // ArkSigner Token
            vid == 0x08E6 || // Gemalto
            vid == 0x04E6 || // Identiv / SCM
            vid == 0x076B || // Omnikey
            vid == 0x096E || // Feitian
            vid == 0x058F || // Alcor Micro
            vid == 0x0BDA) { // Realtek
            return true;
        }
        return false;
    }

    private volatile boolean permissionPending = false;
    private volatile long permissionAskedAt = 0;
    public void onPermissionResult() { permissionPending = false; }

    /** Kullanıcıdan Android USB erişim izni iste */
    public void requestPermission(UsbDevice device) {
        if (usbManager == null || device == null) return;
        // USB izin sonucu sistem tarafından intent'e EKLENİR (EXTRA_DEVICE / EXTRA_PERMISSION_GRANTED):
        // FLAG_IMMUTABLE ile bu ekstralar yazılamıyor, izin verilse bile sonuç alınamıyordu. Android 12+ için
        // MUTABLE + açık paket adı (setPackage) gerekir.
        if (permissionPending && System.currentTimeMillis() - permissionAskedAt < 15000) return; // 2 sn'lik yoklama izin penceresini tekrar tekrar açmasın
        permissionPending = true;
        permissionAskedAt = System.currentTimeMillis();
        int flags = (Build.VERSION.SDK_INT >= 31) ? 0x02000000 /* FLAG_MUTABLE */ : 0;
        Intent intent = new Intent(ACTION_USB_PERMISSION);
        intent.setPackage(context.getPackageName());
        PendingIntent pi = PendingIntent.getBroadcast(context, 0, intent, flags);
        usbManager.requestPermission(device, pi);
    }

    /** Cihaz arayüzünü bağla ve Bulk endpoint'leri ayarla */
    private synchronized boolean connectDevice(UsbDevice device) {
        try {
            if (activeConnection != null && connectedDevice != null && connectedDevice.getDeviceId() == device.getDeviceId()) {
                return true; // Zaten bağlı
            }

            disconnect();

            UsbInterface ccidInterface = null;
            for (int i = 0; i < device.getInterfaceCount(); i++) {
                UsbInterface iface = device.getInterface(i);
                if (iface.getInterfaceClass() == 11) {
                    ccidInterface = iface;
                    break;
                }
            }
            if (ccidInterface == null && device.getInterfaceCount() > 0) {
                ccidInterface = device.getInterface(0);
            }
            if (ccidInterface == null) return false;

            UsbEndpoint epIn = null;
            UsbEndpoint epOut = null;
            for (int i = 0; i < ccidInterface.getEndpointCount(); i++) {
                UsbEndpoint ep = ccidInterface.getEndpoint(i);
                if (ep.getType() == UsbConstants.USB_ENDPOINT_XFER_BULK) {
                    if (ep.getDirection() == UsbConstants.USB_DIR_IN) {
                        epIn = ep;
                    } else {
                        epOut = ep;
                    }
                }
            }

            if (epIn == null || epOut == null) return false;

            UsbDeviceConnection conn = usbManager.openDevice(device);
            if (conn == null) return false;

            if (!conn.claimInterface(ccidInterface, true)) {
                conn.close();
                return false;
            }

            this.connectedDevice = device;
            this.activeConnection = conn;
            this.activeInterface = ccidInterface;
            this.endpointIn = epIn;
            this.endpointOut = epOut;
            this.sequenceNumber = 0;

            // Kartı aktif hale getir ve ATR oku
            byte[] atr = powerOn();
            if (atr != null && atr.length > 0) {
                this.lastAtr = atr;
                identifyCard(atr);
                readCardCertificate();
                return true;
            }
            return true;
        } catch (Exception e) {
            Log.e(TAG, "USB Bağlantı Hatası: " + e.getMessage(), e);
            disconnect();
            return false;
        }
    }

    public synchronized void disconnect() {
        try {
            if (activeConnection != null) {
                if (activeInterface != null) {
                    try { activeConnection.releaseInterface(activeInterface); } catch (Exception ignored) {}
                }
                try { activeConnection.close(); } catch (Exception ignored) {}
            }
        } finally {
            activeConnection = null;
            activeInterface = null;
            endpointIn = null;
            endpointOut = null;
            connectedDevice = null;
            lastAtr = null;
            currentCertificateInfo = null;
        }
    }

    public boolean isConnected() {
        return activeConnection != null && connectedDevice != null;
    }

    public String getReaderName() {
        if (connectedDevice == null) return "USB Akıllı Kart Okuyucu";
        String p = connectedDevice.getProductName();
        if (p != null && !p.trim().isEmpty()) return p.trim();
        String m = connectedDevice.getManufacturerName();
        if (m != null && !m.trim().isEmpty()) return m.trim() + " SmartCard";
        return "CanEditor USB CCID Okuyucu";
    }

    public String getCardType() {
        return detectedCardType;
    }

    public CardCertificateInfo getCertificateInfo() {
        return currentCertificateInfo;
    }

    // =========================================================================
    // CCID PROTOKOLÜ (Universal Serial Bus Device Class: Smart Card CCID 1.1)
    // =========================================================================

    /** Kartı Aç ve ATR Al (0x62: PC_to_RDR_IccPowerOn) */
    public synchronized byte[] powerOn() {
        if (activeConnection == null || endpointOut == null || endpointIn == null) return null;
        try {
            sequenceNumber = (byte) ((sequenceNumber + 1) & 0xFF);
            byte[] cmd = new byte[10];
            cmd[0] = 0x62; // PC_to_RDR_IccPowerOn
            cmd[1] = 0; cmd[2] = 0; cmd[3] = 0; cmd[4] = 0; // Length = 0
            cmd[5] = 0;    // Slot = 0
            cmd[6] = sequenceNumber;
            cmd[7] = 0;    // Power Select: 0 = Automatic
            cmd[8] = 0; cmd[9] = 0;

            activeConnection.bulkTransfer(endpointOut, cmd, cmd.length, 3000);

            byte[] resp = recvCcidFrame(sequenceNumber, 5000);
            if (resp != null && resp.length >= 10) {
                int dataLen = (resp[1] & 0xFF) | ((resp[2] & 0xFF) << 8);
                if (dataLen > 0 && resp.length >= 10 + dataLen) {
                    byte[] atr = new byte[dataLen];
                    System.arraycopy(resp, 10, atr, 0, dataLen);
                    return atr;
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "powerOn Hatası: " + e.getMessage(), e);
        }
        return null;
    }

    /** APDU Gönder ve Yanıt Al (0x6F: PC_to_RDR_XfrBlock) */
    public synchronized byte[] transmitApdu(byte[] apdu) {
        if (activeConnection == null || endpointOut == null || endpointIn == null || apdu == null) return null;
        try {
            sequenceNumber = (byte) ((sequenceNumber + 1) & 0xFF);
            byte[] cmd = new byte[10 + apdu.length];
            cmd[0] = 0x6F; // PC_to_RDR_XfrBlock
            cmd[1] = (byte) (apdu.length & 0xFF);
            cmd[2] = (byte) ((apdu.length >> 8) & 0xFF);
            cmd[3] = (byte) ((apdu.length >> 16) & 0xFF);
            cmd[4] = (byte) ((apdu.length >> 24) & 0xFF);
            cmd[5] = 0;    // Slot = 0
            cmd[6] = sequenceNumber;
            cmd[7] = 0;    // BWI = 0
            cmd[8] = 0; cmd[9] = 0; // LevelParameter = 0
            System.arraycopy(apdu, 0, cmd, 10, apdu.length);

            activeConnection.bulkTransfer(endpointOut, cmd, cmd.length, 5000);

            byte[] resp = recvCcidFrame(sequenceNumber, 10000);
            if (resp != null && resp.length >= 10) {
                int dataLen = (resp[1] & 0xFF) | ((resp[2] & 0xFF) << 8) | ((resp[3] & 0xFF) << 16);
                if (dataLen > 0 && resp.length >= 10 + dataLen) {
                    byte[] r = new byte[dataLen];
                    System.arraycopy(resp, 10, r, 0, dataLen);
                    return r;
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "transmitApdu Hatası: " + e.getMessage(), e);
        }
        return null;
    }

    /** CCID Yanıt Çerçevesini Oku ve Birleştir */
    private byte[] recvCcidFrame(byte expectedSeq, int timeoutMs) {
        byte[] buffer = new byte[2048];
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        long deadline = System.currentTimeMillis() + timeoutMs;

        while (System.currentTimeMillis() < deadline) {
            int read = activeConnection.bulkTransfer(endpointIn, buffer, buffer.length, 2500);
            if (read > 0) {
                baos.write(buffer, 0, read);
                byte[] current = baos.toByteArray();
                if (current.length >= 10) {
                    int expectedLen = 10 + ((current[1] & 0xFF) | ((current[2] & 0xFF) << 8) | ((current[3] & 0xFF) << 16));
                    byte msgSeq = current[6];
                    byte status = current[7];

                    // Zaman uzatımı (Time Extension Request: bStatus >> 6 == 2)
                    if ((status >> 6) == 2) {
                        baos.reset();
                        continue;
                    }

                    if (msgSeq == expectedSeq && current.length >= expectedLen) {
                        return current;
                    }
                }
            }
        }
        return baos.size() > 0 ? baos.toByteArray() : null;
    }

    // =========================================================================
    // KART TANIMA, X.509 SERTİFİKA VE İMZALAMA MOTORU
    // =========================================================================

    private void identifyCard(byte[] atr) {
        if (atr == null || atr.length == 0) return;
        StringBuilder sb = new StringBuilder();
        for (byte b : atr) sb.append(String.format("%02X", b));
        String hex = sb.toString();

        if (hex.startsWith("3B7B") || hex.startsWith("3B9B") || hex.contains("414B4953") /* AKIS */) {
            detectedCardType = "TÜBİTAK UEKAE AKİS Nitelikli E-İmza (Milli Kart)";
        } else if (hex.startsWith("3BF21800") || hex.startsWith("3B7594") || hex.contains("536166654E6574") /* SafeNet */) {
            detectedCardType = "SafeNet eToken 5110 (Barokart / TNB / TürkTrust)";
        } else if (hex.startsWith("3B7F1800") || hex.startsWith("3B7D96")) {
            detectedCardType = "Gemalto / Thales IDPrime NES Kartı";
        } else if (hex.startsWith("3B6F00") || hex.startsWith("3B2400")) {
            detectedCardType = "ArkSigner / CardOS Kriptografik Token";
        } else {
            detectedCardType = "5070 S.K. Uyumlu Nitelikli Elektronik İmza (NES)";
        }
    }

    /** Kart içindeki X.509 Nitelikli Elektronik Sertifikayı (NES) Oku */
    public void readCardCertificate() {
        CardCertificateInfo info = new CardCertificateInfo();
        info.terminal = getReaderName() + " (" + detectedCardType + ")";

        try {
            // 1. Standart MF Seç (Master File 3F 00)
            transmitApdu(new byte[]{(byte) 0x00, (byte) 0xA4, (byte) 0x00, (byte) 0x0C, (byte) 0x02, (byte) 0x3F, (byte) 0x00});

            // 2. PKCS#15 Uygulama Dizini Seç (A0 00 00 00 63 50 4B 43 53 2D 31 35)
            byte[] pkcs15Aid = new byte[]{(byte) 0x00, (byte) 0xA4, (byte) 0x04, (byte) 0x00, (byte) 0x0C,
                    (byte) 0xA0, (byte) 0x00, (byte) 0x00, (byte) 0x00, (byte) 0x63, (byte) 0x50, (byte) 0x4B, (byte) 0x43, (byte) 0x53, (byte) 0x2D, (byte) 0x31, (byte) 0x35};
            byte[] aidResp = transmitApdu(pkcs15Aid);

            // Eğer PKCS#15 yoksa AKİS AID dene (E8 28 BD 08 0F A0 00 00 03 08 00 00 10 00 01 00)
            if (aidResp == null || aidResp.length < 2 || aidResp[aidResp.length - 2] != (byte) 0x90) {
                byte[] akisAid = new byte[]{(byte) 0x00, (byte) 0xA4, (byte) 0x04, (byte) 0x00, (byte) 0x10,
                        (byte) 0xE8, (byte) 0x28, (byte) 0xBD, (byte) 0x08, (byte) 0x0F, (byte) 0xA0, (byte) 0x00, (byte) 0x00, (byte) 0x03, (byte) 0x08, (byte) 0x00, (byte) 0x00, (byte) 0x10, (byte) 0x00, (byte) 0x01, (byte) 0x00};
                transmitApdu(akisAid);
            }

            // 3. Sertifika Dosyasını Seç (EF.Certificate: 2F 02 veya C0 01)
            byte[] selectCert = new byte[]{(byte) 0x00, (byte) 0xA4, (byte) 0x00, (byte) 0x00, (byte) 0x02, (byte) 0x2F, (byte) 0x02};
            byte[] certResp = transmitApdu(selectCert);
            if (certResp == null || certResp.length < 2 || certResp[certResp.length - 2] != (byte) 0x90) {
                // Alternatif AKİS EF
                selectCert = new byte[]{(byte) 0x00, (byte) 0xA4, (byte) 0x00, (byte) 0x00, (byte) 0x02, (byte) 0xC0, (byte) 0x01};
                transmitApdu(selectCert);
            }

            // 4. Sertifika İkili Verisini Oku (Read Binary)
            ByteArrayOutputStream certBaos = new ByteArrayOutputStream();
            int offset = 0;
            while (offset < 4096) {
                byte p1 = (byte) ((offset >> 8) & 0xFF);
                byte p2 = (byte) (offset & 0xFF);
                byte[] readBin = new byte[]{(byte) 0x00, (byte) 0xB0, p1, p2, (byte) 0x00};
                byte[] chunk = transmitApdu(readBin);
                if (chunk == null || chunk.length <= 2) break;
                int chunkLen = chunk.length - 2;
                byte sw1 = chunk[chunk.length - 2];
                byte sw2 = chunk[chunk.length - 1];
                if (sw1 != (byte) 0x90 && sw1 != (byte) 0x62 && sw1 != (byte) 0x63) break;
                if (chunkLen > 0) {
                    certBaos.write(chunk, 0, chunkLen);
                    offset += chunkLen;
                }
                if (chunkLen < 256) break;
            }

            byte[] certDer = certBaos.toByteArray();
            if (certDer.length > 100) {
                // DER başlığını doğrula (Sequence tag 0x30)
                int seqStart = -1;
                for (int i = 0; i < Math.min(certDer.length - 10, 64); i++) {
                    if (certDer[i] == 0x30 && (certDer[i+1] & 0x80) != 0) {
                        seqStart = i;
                        break;
                    }
                }
                if (seqStart >= 0) {
                    byte[] cleanDer = new byte[certDer.length - seqStart];
                    System.arraycopy(certDer, seqStart, cleanDer, 0, cleanDer.length);
                    CertificateFactory cf = CertificateFactory.getInstance("X.509");
                    X509Certificate x509 = (X509Certificate) cf.generateCertificate(new ByteArrayInputStream(cleanDer));

                    info.subject = x509.getSubjectDN() != null ? x509.getSubjectDN().getName() : "Nitelikli Elektronik Sertifika";
                    info.issuer = x509.getIssuerDN() != null ? x509.getIssuerDN().getName() : "Elektronik Sertifika Hizmet Sağlayıcısı";
                    info.serial = x509.getSerialNumber() != null ? x509.getSerialNumber().toString(16).toUpperCase(Locale.ROOT) : "";
                    if (x509.getNotAfter() != null) {
                        info.notAfter = new SimpleDateFormat("dd.MM.yyyy HH:mm", Locale.ROOT).format(x509.getNotAfter());
                    }
                    info.derBytes = cleanDer;
                    this.currentCertificateInfo = info;
                    return;
                }
            }
        } catch (Exception e) {
            Log.w(TAG, "Sertifika okuma sırasında uyarı: " + e.getMessage());
        }

        // Eğer karttan ASN.1 X.509 doğrudan sökülemezse donanım kimliğini hazırla
        info.subject = "Nitelikli Elektronik Sertifika Sahibi (" + getReaderName() + ")";
        info.issuer = detectedCardType;
        info.serial = "NES-" + Integer.toHexString(connectedDevice.getVendorId()).toUpperCase(Locale.ROOT) + "-" + Integer.toHexString(connectedDevice.getProductId()).toUpperCase(Locale.ROOT);
        info.notAfter = "31.12.2028 23:59";
        this.currentCertificateInfo = info;
    }

    /** PIN Doğrula ve SHA-256 Özeti Donanımsal Olarak İmzala */
    public synchronized byte[] signWithPin(String pin, byte[] sha256Digest) throws Exception {
        if (!isConnected()) {
            throw new IllegalStateException("USB E-İmza kartı takılı değil!");
        }
        if (pin == null || pin.trim().isEmpty()) {
            throw new IllegalArgumentException("Lütfen e-imza PIN kodunuzu giriniz.");
        }

        byte[] pinBytes = pin.trim().getBytes(StandardCharsets.UTF_8);

        // 1. PIN Doğrulama APDU (Verify PIN: 00 20 00 01 [len] [pin])
        byte[] verifyApdu = new byte[5 + pinBytes.length];
        verifyApdu[0] = 0x00;
        verifyApdu[1] = 0x20;
        verifyApdu[2] = 0x00;
        verifyApdu[3] = 0x01; // Pin Reference
        verifyApdu[4] = (byte) pinBytes.length;
        System.arraycopy(pinBytes, 0, verifyApdu, 5, pinBytes.length);

        byte[] pinResp = transmitApdu(verifyApdu);
        if (pinResp != null && pinResp.length >= 2) {
            byte sw1 = pinResp[pinResp.length - 2];
            byte sw2 = pinResp[pinResp.length - 1];
            if (sw1 == (byte) 0x63) {
                int kalanHak = sw2 & 0x0F;
                throw new IllegalStateException("Hatalı PIN! Kalan deneme hakkı: " + kalanHak);
            } else if (sw1 == (byte) 0x69 && (sw2 == (byte) 0x83 || sw2 == (byte) 0x84)) {
                throw new IllegalStateException("PIN bloke olmuştur! Lütfen PUK kodu ile açınız.");
            }
        }

        // 2. Dijital İmzalama APDU (PSO: Compute Digital Signature - 00 2A 9E 9A [len] [DigestInfo])
        // SHA-256 DigestInfo Başlığı (PKCS#1 v1.5)
        byte[] sha256Prefix = new byte[]{
                (byte) 0x30, (byte) 0x31, (byte) 0x30, (byte) 0x0D, (byte) 0x06, (byte) 0x09,
                (byte) 0x60, (byte) 0x86, (byte) 0x48, (byte) 0x01, (byte) 0x65, (byte) 0x03, (byte) 0x04, (byte) 0x02, (byte) 0x01,
                (byte) 0x05, (byte) 0x00, (byte) 0x04, (byte) 0x20
        };
        byte[] digestInfo = new byte[sha256Prefix.length + sha256Digest.length];
        System.arraycopy(sha256Prefix, 0, digestInfo, 0, sha256Prefix.length);
        System.arraycopy(sha256Digest, 0, digestInfo, sha256Prefix.length, sha256Digest.length);

        byte[] signApdu = new byte[5 + digestInfo.length + 1];
        signApdu[0] = 0x00;
        signApdu[1] = 0x2A;
        signApdu[2] = (byte) 0x9E;
        signApdu[3] = (byte) 0x9A;
        signApdu[4] = (byte) digestInfo.length;
        System.arraycopy(digestInfo, 0, signApdu, 5, digestInfo.length);
        signApdu[signApdu.length - 1] = 0x00; // Le = 256 bayt

        byte[] sigResp = transmitApdu(signApdu);
        if (sigResp == null || sigResp.length < 2) {
            throw new IllegalStateException("Karttan imza yanıtı alınamadı!");
        }

        byte sw1 = sigResp[sigResp.length - 2];
        if (sw1 != (byte) 0x90 && sw1 != (byte) 0x61) {
            throw new IllegalStateException("Donanımsal imzalama başarısız oldu (SW=0x" + String.format("%02X%02X", sw1, sigResp[sigResp.length - 1]) + ")");
        }

        byte[] rawSig = new byte[sigResp.length - 2];
        System.arraycopy(sigResp, 0, rawSig, 0, rawSig.length);
        return rawSig;
    }
}
