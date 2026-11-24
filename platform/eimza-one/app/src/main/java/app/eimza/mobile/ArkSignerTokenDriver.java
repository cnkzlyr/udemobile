package app.eimza.mobile;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.Signature;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.security.interfaces.RSAPublicKey;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

import javax.security.auth.x500.X500Principal;
import javax.smartcardio.ATR;
import javax.smartcardio.CardChannel;
import javax.smartcardio.CommandAPDU;
import javax.smartcardio.ResponseAPDU;

import org.bouncycastle.asn1.x500.RDN;
import org.bouncycastle.asn1.x500.X500Name;
import org.bouncycastle.asn1.x500.style.BCStyle;
import org.bouncycastle.asn1.x500.style.IETFUtils;

/**
 * ArkSigner Arkİmza & Standart PKCS#15 / ISO 7816-4 Donanımsal Akıllı Kart Sürücüsü.
 * 
 * Doğrudan USB CCID APDU seviyesinde çalışır:
 * - ArkSigner USB Kriptografik Token (Arkİmza)
 * - SafeNet eToken 5110 / 5100 (TürkTrust TBB Kırmızı Token)
 * - Standart ISO 7816-4 / PKCS#15 e-imza kartları
 */
final class ArkSignerTokenDriver {

    interface ApduTransmitter {
        ResponseAPDU transmit(CommandAPDU command) throws Exception;
        ATR atr() throws Exception;
    }

    enum TokenModel {
        ARKSIGNER_ARKIMZA("ArkSigner Arkİmza Kriptografik Token"),
        TURKTRUST_TBB_RED("SafeNet eToken 5110 (TürkTrust TBB Kırmızı Token)"),
        KAMUSM_ATR19("TÜBİTAK Kamu SM (ATR19 Mini Okuyucu)"),
        GENERIC_PKCS15("5070 Sayılı Kanuna Uyumlu Nitelikli E-İmza Kartı (PKCS#15)");

        final String displayName;
        TokenModel(String displayName) { this.displayName = displayName; }
    }

    private final ApduTransmitter transmitter;
    private TokenModel tokenModel = TokenModel.GENERIC_PKCS15;
    private final List<TokenCertificateEntry> certificates = new ArrayList<>();
    private byte lastPinReference = 0x01;
    private boolean applicationSelected = false;

    static final class TokenCertificateEntry {
        final String id;
        final byte[] der;
        final X509Certificate certificate;
        final String subjectCN;
        final String tckn;
        final String issuer;
        final String serialHex;
        final String validUntil;

        TokenCertificateEntry(String id, byte[] der, X509Certificate cert) {
            this.id = id;
            this.der = der;
            this.certificate = cert;
            this.subjectCN = extractCN(cert);
            this.tckn = extractTCKN(cert);
            this.issuer = cert.getIssuerX500Principal() != null ? cert.getIssuerX500Principal().getName(X500Principal.RFC2253) : "";
            this.serialHex = cert.getSerialNumber() != null ? cert.getSerialNumber().toString(16).toUpperCase(Locale.ROOT) : "";
            this.validUntil = cert.getNotAfter() != null ? cert.getNotAfter().toInstant().toString() : "";
        }
    }

    ArkSignerTokenDriver(ApduTransmitter transmitter) {
        this.transmitter = transmitter;
    }

    TokenModel tokenModel() {
        return tokenModel;
    }

    String tokenDisplayName() {
        return tokenModel.displayName;
    }

    /**
     * ATR dökümü ve USB bilgilerine göre kart/token tipini belirler.
     */
    void identifyToken(String readerName) {
        try {
            ATR atr = transmitter.atr();
            if (atr == null) return;
            byte[] bytes = atr.getBytes();
            String hexAtr = bytesToHex(bytes).toUpperCase(Locale.ROOT);

            DiagnosticLogger.d(DiagnosticLogger.Tag.CARD, "Token ATR: " + hexAtr + " | Okuyucu: " + readerName);

            if (hexAtr.startsWith("3B6F00") || hexAtr.startsWith("3B2400") || (readerName != null && readerName.toLowerCase(Locale.ROOT).contains("arksigner"))) {
                tokenModel = TokenModel.ARKSIGNER_ARKIMZA;
            } else if (hexAtr.startsWith("3BF21800") || hexAtr.startsWith("3B7594") || hexAtr.contains("536166654E6574")
                    || (readerName != null && (readerName.toLowerCase(Locale.ROOT).contains("safenet") || readerName.toLowerCase(Locale.ROOT).contains("tbb")))) {
                tokenModel = TokenModel.TURKTRUST_TBB_RED;
            } else if (hexAtr.startsWith("3B7B") || hexAtr.startsWith("3B9B") || hexAtr.contains("414B4953") /* AKIS */) {
                tokenModel = TokenModel.KAMUSM_ATR19;
            } else {
                tokenModel = TokenModel.GENERIC_PKCS15;
            }

            DiagnosticLogger.i(DiagnosticLogger.Tag.DRIVER, "Tespit edilen donanım: " + tokenModel.displayName);
        } catch (Exception e) {
            DiagnosticLogger.w(DiagnosticLogger.Tag.DRIVER, "Token ATR tespiti sırasında uyarı: " + e.getMessage());
        }
    }

    /**
     * Kart üzerinde PKCS#15 veya ArkSigner uygulamasını seçer.
     */
    void selectApplication() throws SignerBackend.SignerException {
        if (applicationSelected) return;

        DiagnosticLogger.d(DiagnosticLogger.Tag.DRIVER, "Akıllı kart master file ve PKCS#15 seçimi başlatılıyor");
        try {
            // 1. MF Seçimi (00 A4 00 0C 02 3F 00)
            ResponseAPDU resp = transmitter.transmit(new CommandAPDU(0x00, 0xA4, 0x00, 0x0C, new byte[]{0x3F, 0x00}));
            if (resp.getSW() != 0x9000 && (resp.getSW() & 0xFF00) != 0x6100) {
                // Alternatif P1/P2 ile dene
                transmitter.transmit(new CommandAPDU(0x00, 0xA4, 0x00, 0x00, new byte[]{0x3F, 0x00}));
            }

            // 2. PKCS#15 AID Seçimi: A0 00 00 00 63 50 4B 43 53 2D 31 35
            byte[] pkcs15Aid = new byte[]{
                    (byte) 0xA0, 0x00, 0x00, 0x00, 0x63, 0x50, 0x4B, 0x43, 0x53, 0x2D, 0x31, 0x35
            };
            ResponseAPDU aidResp = transmitter.transmit(new CommandAPDU(0x00, 0xA4, 0x04, 0x00, pkcs15Aid));
            if (aidResp.getSW() == 0x9000 || (aidResp.getSW() & 0xFF00) == 0x6100) {
                DiagnosticLogger.i(DiagnosticLogger.Tag.DRIVER, "PKCS#15 uygulaması başarıyla seçildi (SW=9000)");
                applicationSelected = true;
                return;
            }

            // 3. Alternatif PKCS#15 DF Seçimi (Path: 50 15)
            ResponseAPDU dfResp = transmitter.transmit(new CommandAPDU(0x00, 0xA4, 0x00, 0x00, new byte[]{0x50, 0x15}));
            if (dfResp.getSW() == 0x9000 || (dfResp.getSW() & 0xFF00) == 0x6100) {
                DiagnosticLogger.i(DiagnosticLogger.Tag.DRIVER, "PKCS#15 DF(5015) seçildi");
                applicationSelected = true;
                return;
            }

            // 4. Alternatif AKİS AID Denemesi
            byte[] akisAid = new byte[]{
                    (byte) 0xE8, 0x28, (byte) 0xBD, 0x08, 0x0F, (byte) 0xA0, 0x00, 0x00, 0x03, 0x08, 0x00, 0x00, 0x10, 0x00, 0x01, 0x00
            };
            ResponseAPDU akisResp = transmitter.transmit(new CommandAPDU(0x00, 0xA4, 0x04, 0x00, akisAid));
            if (akisResp.getSW() == 0x9000 || (akisResp.getSW() & 0xFF00) == 0x6100) {
                DiagnosticLogger.i(DiagnosticLogger.Tag.DRIVER, "AKİS uygulaması seçildi");
                applicationSelected = true;
                return;
            }

            // Kart doğrudan dosya sistemini açıyor olabilir, devam et
            applicationSelected = true;
        } catch (Exception e) {
            DiagnosticLogger.e(DiagnosticLogger.Tag.DRIVER, "Uygulama seçimi sırasında hata", e);
            throw new SignerBackend.SignerException("Akıllı kart uygulaması seçilemedi: " + e.getMessage(), e);
        }
    }

    /**
     * Karttaki X.509 Nitelikli Elektronik Sertifikaları okur.
     */
    List<TokenCertificateEntry> readCertificates() throws SignerBackend.SignerException {
        selectApplication();
        certificates.clear();

        DiagnosticLogger.d(DiagnosticLogger.Tag.CERT, "Akıllı kart sertifika dosyaları taranıyor...");

        // Denenecek standart EF (Elementary File) yolları:
        // 2F 02: Standart PKCS#15 Certificate EF
        // C0 01: SafeNet eToken / TBB kullanıcı sertifikası
        // 2F 10, 2F 11, 2F 12: AKİS / Kamu SM sertifika indeksleri
        // 45 01: Bazı CardOS profilleri
        byte[][] candidateFids = new byte[][]{
                {0x2F, 0x02},
                {(byte) 0xC0, 0x01},
                {0x2F, 0x10},
                {0x2F, 0x11},
                {0x2F, 0x12},
                {0x45, 0x01}
        };

        CertificateFactory cf;
        try {
            cf = CertificateFactory.getInstance("X.509");
        } catch (Exception e) {
            throw new SignerBackend.SignerException("X.509 sağlayıcısı başlatılamadı", e);
        }

        for (byte[] fid : candidateFids) {
            try {
                byte[] der = readEfBinary(fid);
                if (der != null && der.length > 64) {
                    byte[] cleanDer = extractValidX509Der(der);
                    if (cleanDer != null) {
                        X509Certificate cert = (X509Certificate) cf.generateCertificate(new ByteArrayInputStream(cleanDer));
                        String id = bytesToHex(MessageDigest.getInstance("SHA-256").digest(cleanDer)).replaceAll("\\s+", "");
                        TokenCertificateEntry entry = new TokenCertificateEntry(id, cleanDer, cert);
                        certificates.add(entry);
                        DiagnosticLogger.i(DiagnosticLogger.Tag.CERT, "Sertifika bulundu: " + entry.subjectCN + " (TCKN: " + entry.tckn + ", Bitiş: " + entry.validUntil + ")");
                    }
                }
            } catch (Exception e) {
                DiagnosticLogger.d(DiagnosticLogger.Tag.CERT, "EF " + bytesToHex(fid) + " okunurken atlandı: " + e.getMessage());
            }
        }

        if (certificates.isEmpty()) {
            DiagnosticLogger.w(DiagnosticLogger.Tag.CERT, "Hiçbir adresten X.509 sertifikası çıkarılamadı.");
            throw new SignerBackend.SignerException("Kartta uygun Nitelikli Elektronik Sertifika bulunamadı");
        }

        return Collections.unmodifiableList(certificates);
    }

    /**
     * EF dosyasını seçer ve ikili içeriğini (Read Binary) okur.
     */
    private byte[] readEfBinary(byte[] fid) throws Exception {
        // SELECT FILE APDU: 00 A4 00 00 02 [fid]
        CommandAPDU selectCmd = new CommandAPDU(0x00, 0xA4, 0x00, 0x00, fid);
        ResponseAPDU selectResp = transmitter.transmit(selectCmd);
        int sw = selectResp.getSW();
        if (sw != 0x9000 && (sw & 0xFF00) != 0x6100 && (sw & 0xFF00) != 0x6200 && (sw & 0xFF00) != 0x6300) {
            // Alternatif P1/P2 dene: 00 A4 02 0C 02 [fid]
            selectCmd = new CommandAPDU(0x00, 0xA4, 0x02, 0x0C, fid);
            selectResp = transmitter.transmit(selectCmd);
            sw = selectResp.getSW();
            if (sw != 0x9000 && (sw & 0xFF00) != 0x6100) {
                return null; // Dosya kartta mevcut değil
            }
        }

        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        int offset = 0;
        int maxLen = 4096;

        while (offset < maxLen) {
            int p1 = (offset >> 8) & 0xFF;
            int p2 = offset & 0xFF;
            // READ BINARY: 00 B0 P1 P2 00
            CommandAPDU readCmd = new CommandAPDU(0x00, 0xB0, p1, p2, 0x00);
            ResponseAPDU readResp = transmitter.transmit(readCmd);
            int readSw = readResp.getSW();

            if (readSw != 0x9000 && (readSw & 0xFF00) != 0x6100 && (readSw & 0xFF00) != 0x6200 && (readSw & 0xFF00) != 0x6300) {
                break;
            }

            byte[] chunk = readResp.getData();
            if (chunk == null || chunk.length == 0) break;

            baos.write(chunk);
            offset += chunk.length;

            if (chunk.length < 256) break;
        }

        return baos.size() > 0 ? baos.toByteArray() : null;
    }

    /**
     * Ham ikili veriden ASN.1 Sequence (0x30) ile başlayan geçerli X.509 DER yapısını ayıklar.
     */
    private static byte[] extractValidX509Der(byte[] raw) {
        if (raw == null || raw.length < 64) return null;
        for (int i = 0; i < Math.min(raw.length - 10, 64); i++) {
            if ((raw[i] & 0xFF) == 0x30 && (raw[i + 1] & 0x80) != 0) {
                // ASN.1 DER Sequence başlığı
                int lenByteCount = raw[i + 1] & 0x7F;
                int contentLen = 0;
                if (lenByteCount == 1 && i + 2 < raw.length) {
                    contentLen = raw[i + 2] & 0xFF;
                } else if (lenByteCount == 2 && i + 3 < raw.length) {
                    contentLen = ((raw[i + 2] & 0xFF) << 8) | (raw[i + 3] & 0xFF);
                } else if (lenByteCount == 3 && i + 4 < raw.length) {
                    contentLen = ((raw[i + 2] & 0xFF) << 16) | ((raw[i + 3] & 0xFF) << 8) | (raw[i + 4] & 0xFF);
                }
                int totalLen = 2 + lenByteCount + contentLen;
                if (totalLen > 64 && i + totalLen <= raw.length) {
                    byte[] clean = new byte[totalLen];
                    System.arraycopy(raw, i, clean, 0, totalLen);
                    return clean;
                }
            }
        }
        return null;
    }

    /**
     * PIN doğrular ve SHA-256 özetini donanım üzerinde imzalar.
     */
    byte[] sign(byte[] payload, String certificateId, char[] pin) throws SignerBackend.SignerException {
        if (payload == null || payload.length == 0) throw new SignerBackend.SignerException("İmzalanacak veri boş");
        if (pin == null || pin.length == 0) throw new SignerBackend.SignerException("PIN kodu girilmedi");

        TokenCertificateEntry selected = findCertificate(certificateId);
        DiagnosticLogger.i(DiagnosticLogger.Tag.SIGN, "ArkSigner imzalama: Sertifika=" + selected.subjectCN + ", Boyut=" + payload.length + " bayt");

        try {
            // 1. PIN Doğrulama
            verifyPin(pin);

            // 2. SHA-256 Özeti Hesapla
            byte[] sha256Digest = MessageDigest.getInstance("SHA-256").digest(payload);

            // 3. PKCS#1 v1.5 DigestInfo Başlığını Ekle
            byte[] digestInfo = RsaDigestInfo.sha256(payload);

            // 4. PSO: Compute Digital Signature APDU
            byte[] signature = executePsoComputeDigitalSignature(digestInfo);

            // 5. İmzayı Açık Anahtarla Yerelde Doğrula (Donanım Doğruluk Kontrolü)
            Signature verifier = Signature.getInstance("SHA256withRSA");
            verifier.initVerify(selected.certificate.getPublicKey());
            verifier.update(payload);
            if (!verifier.verify(signature)) {
                DiagnosticLogger.e(DiagnosticLogger.Tag.SIGN, "Donanımsal imza sertifika açık anahtarıyla doğrulanamadı!", null);
                throw new SignerBackend.SignerException("Kart imzası sertifikayla doğrulanmadı");
            }

            DiagnosticLogger.i(DiagnosticLogger.Tag.SIGN, "ArkSigner donanım imzası başarıyla tamamlandı ve doğrulandı (" + signature.length + " bayt)");
            return signature;
        } catch (SignerBackend.SignerException e) {
            throw e;
        } catch (Exception e) {
            DiagnosticLogger.e(DiagnosticLogger.Tag.SIGN, "Donanımsal imzalama başarısız", e);
            throw new SignerBackend.SignerException("ArkSigner kart imzalama işlemi başarısız: " + e.getMessage(), e);
        } finally {
            Arrays.fill(pin, '\0');
        }
    }

    /**
     * Ham RSA PKCS#1 imzası (e-Devlet CMS için doğrudan DigestInfo alır).
     */
    byte[] signRawPkcs1(byte[] digestInfo, String certificateId, char[] pin) throws SignerBackend.SignerException {
        if (digestInfo == null || digestInfo.length == 0) throw new SignerBackend.SignerException("İmzalanacak veri boş");
        if (pin == null || pin.length == 0) throw new SignerBackend.SignerException("PIN kodu girilmedi");

        TokenCertificateEntry selected = findCertificate(certificateId);
        DiagnosticLogger.i(DiagnosticLogger.Tag.SIGN, "Ham PKCS#1 ArkSigner imzalama başlatıldı (" + digestInfo.length + " bayt)");

        try {
            verifyPin(pin);
            byte[] signature = executePsoComputeDigitalSignature(digestInfo);

            Signature verifier = Signature.getInstance("NONEwithRSA");
            verifier.initVerify(selected.certificate.getPublicKey());
            verifier.update(digestInfo);
            if (!verifier.verify(signature)) {
                DiagnosticLogger.e(DiagnosticLogger.Tag.SIGN, "Ham PKCS#1 imzası sertifikayla doğrulanmadı!", null);
                throw new SignerBackend.SignerException("Ham kart imzası doğrulanmadı");
            }

            DiagnosticLogger.i(DiagnosticLogger.Tag.SIGN, "Ham PKCS#1 ArkSigner imzası doğrulandı");
            return signature;
        } catch (SignerBackend.SignerException e) {
            throw e;
        } catch (Exception e) {
            DiagnosticLogger.e(DiagnosticLogger.Tag.SIGN, "Ham PKCS#1 imza hatası", e);
            throw new SignerBackend.SignerException("Ham ArkSigner PKCS#1 imzası başarısız: " + e.getMessage(), e);
        } finally {
            Arrays.fill(pin, '\0');
        }
    }

    /**
     * PIN Kodunu doğrular (ISO 7816-4 VERIFY: 00 20 00 [pinRef] [len] [pinBytes]).
     * Hatalı deneme sayısını ve bloke durumunu net bildirir.
     */
    private void verifyPin(char[] pin) throws Exception {
        byte[] pinBytes = new byte[pin.length];
        for (int i = 0; i < pin.length; i++) {
            pinBytes[i] = (byte) pin[i];
        }

        try {
            byte[] pinRefs = new byte[]{lastPinReference, 0x01, (byte) 0x81, 0x00};
            Exception lastEx = null;

            for (byte ref : pinRefs) {
                CommandAPDU verifyCmd = new CommandAPDU(0x00, 0x20, 0x00, ref & 0xFF, pinBytes);
                ResponseAPDU resp = transmitter.transmit(verifyCmd);
                int sw = resp.getSW();

                if (sw == 0x9000) {
                    lastPinReference = ref;
                    DiagnosticLogger.i(DiagnosticLogger.Tag.PIN, "PIN doğrulaması başarılı (pinRef=0x" + String.format(Locale.ROOT, "%02X", ref) + ")");
                    return;
                }

                // SW 63 CX: Hatalı PIN, X deneme hakkı kaldı
                if ((sw & 0xFFF0) == 0x63C0) {
                    int remaining = sw & 0x0F;
                    DiagnosticLogger.w(DiagnosticLogger.Tag.PIN, "Hatalı PIN! Kalan deneme hakkı: " + remaining);
                    throw new SignerBackend.SignerException("Hatalı PIN kodu! Kalan deneme hakkınız: " + remaining);
                }

                // SW 69 83 / 69 84: PIN Bloke
                if (sw == 0x6983 || sw == 0x6984) {
                    DiagnosticLogger.e(DiagnosticLogger.Tag.PIN, "PIN bloke olmuştur! SW=" + String.format(Locale.ROOT, "%04X", sw), null);
                    throw new SignerBackend.SignerException("E-imza PIN kodu bloke olmuştur! Lütfen PUK kodu ile açınız.");
                }

                // SW 6A 88: Anahtar / PIN referansı bulunamadı -> diğer referansı dene
                if (sw == 0x6A88 || sw == 0x6D00 || sw == 0x6A86) {
                    continue;
                }

                lastEx = new SignerBackend.SignerException("PIN doğrulama başarısız (SW=0x" + String.format(Locale.ROOT, "%04X", sw) + ")");
            }

            if (lastEx != null) throw lastEx;
            throw new SignerBackend.SignerException("Kart PIN doğrulamasını kabul etmedi");
        } finally {
            Arrays.fill(pinBytes, (byte) 0);
        }
    }

    /**
     * PSO: Compute Digital Signature APDU komutunu yürütür (00 2A 9E 9A).
     */
    private byte[] executePsoComputeDigitalSignature(byte[] digestInfo) throws Exception {
        // 1. MSE (Manage Security Environment) - Set for Digital Signature (00 22 41 B6)
        try {
            // Algoritma: 0x02 veya 0x92 (RSA with PKCS#1 v1.5 padding)
            byte[] mseData = new byte[]{(byte) 0x80, 0x01, 0x02, (byte) 0x84, 0x01, 0x01};
            CommandAPDU mseCmd = new CommandAPDU(0x00, 0x22, 0x41, 0xB6, mseData);
            ResponseAPDU mseResp = transmitter.transmit(mseCmd);
            if (mseResp.getSW() != 0x9000) {
                // Alternatif algoritma 0x92 dene
                mseData[2] = (byte) 0x92;
                transmitter.transmit(new CommandAPDU(0x00, 0x22, 0x41, 0xB6, mseData));
            }
        } catch (Exception mseErr) {
            DiagnosticLogger.d(DiagnosticLogger.Tag.SIGN, "MSE komutu atlandı / isteğe bağlı: " + mseErr.getMessage());
        }

        // 2. PSO: Compute Digital Signature: 00 2A 9E 9A [len] [data] 00 (Le=256)
        CommandAPDU psoCmd = new CommandAPDU(0x00, 0x2A, 0x9E, 0x9A, digestInfo, 256);
        ResponseAPDU psoResp = transmitter.transmit(psoCmd);
        int sw = psoResp.getSW();

        if (sw == 0x9000) {
            return psoResp.getData();
        }

        // SW 61 xx: Get Response ile oku
        if ((sw & 0xFF00) == 0x6100) {
            int le = sw & 0xFF;
            CommandAPDU getRespCmd = new CommandAPDU(0x00, 0xC0, 0x00, 0x00, le);
            ResponseAPDU getResp = transmitter.transmit(getRespCmd);
            if (getResp.getSW() == 0x9000) {
                return getResp.getData();
            }
        }

        throw new SignerBackend.SignerException("Donanımsal PSO CDS imza komutu başarısız (SW=0x"
                + String.format(Locale.ROOT, "%04X", sw) + ")");
    }

    private TokenCertificateEntry findCertificate(String certId) throws SignerBackend.SignerException {
        if (certId == null) throw new SignerBackend.SignerException("Sertifika seçilmedi");
        for (TokenCertificateEntry e : certificates) {
            if (e.id.equals(certId)) return e;
        }
        readCertificates();
        for (TokenCertificateEntry e : certificates) {
            if (e.id.equals(certId)) return e;
        }
        throw new SignerBackend.SignerException("Seçilen sertifika kartta bulunamadı");
    }

    private static String extractCN(X509Certificate cert) {
        try {
            X500Name name = new X500Name(cert.getSubjectX500Principal().getName(X500Principal.RFC2253));
            RDN[] rdns = name.getRDNs(BCStyle.CN);
            if (rdns.length == 0) return "E-İmza Sertifikası";
            return IETFUtils.valueToString(rdns[0].getFirst().getValue());
        } catch (Exception e) {
            return "E-İmza Sertifikası";
        }
    }

    private static String extractTCKN(X509Certificate cert) {
        try {
            X500Name name = new X500Name(cert.getSubjectX500Principal().getName(X500Principal.RFC2253));
            RDN[] rdns = name.getRDNs(BCStyle.SERIALNUMBER);
            if (rdns.length > 0) {
                String value = IETFUtils.valueToString(rdns[0].getFirst().getValue());
                String digits = value.replaceAll("[^0-9]", "");
                if (digits.length() == 11) return digits;
            }
        } catch (Exception ignored) {}
        return "";
    }

    private static String bytesToHex(byte[] bytes) {
        if (bytes == null) return "";
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            sb.append(String.format(Locale.ROOT, "%02X ", b & 0xFF));
        }
        return sb.toString().trim();
    }
}
