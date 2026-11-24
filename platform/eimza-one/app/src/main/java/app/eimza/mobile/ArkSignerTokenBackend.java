package app.eimza.mobile;

import java.io.ByteArrayInputStream;
import java.io.IOException;
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
import javax.smartcardio.Card;
import javax.smartcardio.CardChannel;
import javax.smartcardio.CardException;
import javax.smartcardio.CardTerminal;
import javax.smartcardio.CommandAPDU;
import javax.smartcardio.ResponseAPDU;
import javax.smartcardio.TerminalFactory;

import org.bouncycastle.asn1.x500.RDN;
import org.bouncycastle.asn1.x500.X500Name;
import org.bouncycastle.asn1.x500.style.BCStyle;
import org.bouncycastle.asn1.x500.style.IETFUtils;

/**
 * Native cryptographic smart card driver for ArkSigner / Arkİmza hardware tokens.
 * Supports Feitian ePass2003, Atos CardOS 5.x, SafeNet/Gemalto IDPrime, and standard ISO 7816-15 PKCS#15 tokens.
 * Directly executes APDUs with PIN retry tracking, MSE setup, and PSO digital signature generation.
 */
public final class ArkSignerTokenBackend implements SignerBackend {
    private final Object lock = new Object();
    private final List<Entry> entries = new ArrayList<>();
    private final List<CertificateSummary> summaries = new ArrayList<>();
    private State state = State.WAITING_FOR_READER;
    private Card card;
    private CardChannel channel;
    private String lastApduStage = "";
    private int remainingPinRetries = -1;
    private byte activePinRef = 0x01;
    private byte activeKeyRef = 0x01;

    // Standard PKCS#15 and manufacturer AIDs for ArkSigner / Arkİmza tokens
    private static final byte[][] CANDIDATE_AIDS = {
            // Standard PKCS#15 application AID
            new byte[]{(byte) 0xA0, 0x00, 0x00, 0x00, 0x63, 0x50, 0x4B, 0x43, 0x53, 0x2D, 0x31, 0x35},
            // Feitian PKI application AID (ePass2003 / ArkSigner token)
            new byte[]{(byte) 0xA0, 0x00, 0x00, 0x03, 0x08, 0x00, 0x00, 0x10, 0x00, 0x01},
            // SafeNet / Gemalto IDPrime AID
            new byte[]{(byte) 0xA0, 0x00, 0x00, 0x00, 0x18, 0x50, 0x4B, 0x43, 0x53, 0x2D, 0x31, 0x35},
            // CardOS 5.x PKCS#15 AID
            new byte[]{(byte) 0xE8, 0x28, (byte) 0xBD, 0x08, 0x0F, (byte) 0xF2, 0x50, 0x4B, 0x43, 0x53, 0x2D, 0x31, 0x35}
    };

    // Candidate Certificate Elementary Files (EF) on ArkSigner / PKCS#15 smartcards
    private static final byte[][] CANDIDATE_CERT_FIDS = {
            new byte[]{0x2F, 0x04}, // Standard PKCS#15 CDF
            new byte[]{0x50, 0x01}, // PKCS#15 Cert 1
            new byte[]{0x50, 0x02}, // PKCS#15 Cert 2
            new byte[]{(byte) 0xC0, 0x01}, // Feitian ePass Cert 1
            new byte[]{(byte) 0xC0, 0x02}, // Feitian ePass Cert 2
            new byte[]{0x43, 0x01}, // Token Certificate 1
            new byte[]{0x43, 0x02}, // Token Certificate 2
            new byte[]{0x2F, 0x10}, // AKİS / KamuSM Cert 1
            new byte[]{0x2F, 0x11}, // AKİS / KamuSM Cert 2
            new byte[]{0x2F, 0x12}  // AKİS / KamuSM Cert 3
    };

    @Override public String id() { return "arksigner_token"; }
    @Override public String displayName() { return "ArkSigner Arkİmza Token"; }
    @Override public State state() { synchronized (lock) { return state; } }

    public int getRemainingPinRetries() {
        synchronized (lock) { return remainingPinRetries; }
    }

    @Override
    public List<CertificateSummary> certificates() throws SignerException {
        synchronized (lock) {
            ensureSession();
            try {
                entries.clear();
                summaries.clear();
                CertificateFactory cf = CertificateFactory.getInstance("X.509");
                List<byte[]> certDers = discoverCertificates();

                if (certDers.isEmpty()) {
                    throw new SignerException("ArkSigner kartında geçerli imza sertifikası bulunamadı");
                }

                for (byte[] der : certDers) {
                    if (der == null || der.length == 0) continue;
                    X509Certificate cert = (X509Certificate) cf.generateCertificate(new ByteArrayInputStream(der));
                    String id = hex(MessageDigest.getInstance("SHA-256").digest(der));
                    String subject = cert.getSubjectX500Principal().getName(X500Principal.RFC2253);
                    String until = cert.getNotAfter().toInstant().toString();
                    entries.add(new Entry(id, der.clone(), cert));
                    summaries.add(new CertificateSummary(id, subject, until));
                    DiagnosticLogger.i(DiagnosticLogger.Tag.CERT, "ArkSigner sertifikası yüklendi: CN="
                            + extractCN(cert) + ", Bitiş=" + until);
                }
                return Collections.unmodifiableList(new ArrayList<>(summaries));
            } catch (SignerException e) {
                state = State.ERROR;
                throw e;
            } catch (Exception e) {
                state = State.ERROR;
                throw new SignerException("ArkSigner sertifikaları okunamadı: " + e.getMessage(), e);
            }
        }
    }

    List<AkisSignerBackend.ArkCertificate> arkCertificates() throws SignerException {
        certificates();
        synchronized (lock) {
            List<AkisSignerBackend.ArkCertificate> out = new ArrayList<>();
            for (Entry e : entries) {
                out.add(new AkisSignerBackend.ArkCertificate(e.id, e.der.clone(), e.certificate,
                        e.certificate.getSerialNumber().toString(16).toUpperCase(Locale.ROOT)));
            }
            return out;
        }
    }

    String idForSerial(String serial) throws SignerException {
        if (serial == null || serial.isEmpty()) return null;
        String wantedHex = serial.replaceAll("[^0-9A-Fa-f]", "").replaceFirst("^(?i)0+", "");
        java.math.BigInteger wantedDec = null;
        try { wantedDec = new java.math.BigInteger(serial.replaceAll("[^0-9]", "")); }
        catch (Exception ignored) {}

        for (AkisSignerBackend.ArkCertificate e : arkCertificates()) {
            String hexSerial = e.serial.replaceFirst("^(?i)0+", "");
            if (hexSerial.equalsIgnoreCase(wantedHex)) return e.id;
            if (wantedDec != null) {
                try {
                    if (new java.math.BigInteger(e.serial, 16).equals(wantedDec)) return e.id;
                    if (wantedDec.equals(e.certificate.getSerialNumber())) return e.id;
                } catch (Exception ignored) {}
            }
        }
        return null;
    }

    @Override
    public byte[] sign(byte[] payload, String certificateId, char[] pin) throws SignerException {
        if (payload == null || payload.length == 0) throw new SignerException("İmzalanacak veri boş");
        if (pin == null || pin.length == 0) throw new SignerException("PIN boş");
        synchronized (lock) {
            ensureSession();
            try {
                Entry selected = find(certificateId);
                verifyPin(pin);
                setSecurityEnvironment(selected.certificate);

                boolean rsa = selected.certificate.getPublicKey() instanceof RSAPublicKey;
                byte[] signingInput = rsa ? RsaDigestInfo.sha256(payload) : payload;

                byte[] signature = executePsoSign(signingInput);

                // Self-verification with public key
                Signature verifier = Signature.getInstance(rsa ? "SHA256withRSA" : "SHA256withECDSA");
                verifier.initVerify(selected.certificate.getPublicKey());
                verifier.update(payload);
                if (!verifier.verify(signature)) {
                    throw new SignerException("ArkSigner kart imzası sertifika açık anahtarıyla doğrulanamadı");
                }
                DiagnosticLogger.i(DiagnosticLogger.Tag.SIGN, "ArkSigner imza başarıyla üretildi ve doğrulandı (" + signature.length + " bayt)");
                return signature;
            } catch (SignerException e) {
                throw e;
            } catch (Exception e) {
                throw new SignerException("ArkSigner kart imzalama işlemi başarısız: " + e.getMessage(), e);
            } finally {
                Arrays.fill(pin, '\0');
                closeSession();
            }
        }
    }

    @Override
    public byte[] signRawPkcs1(byte[] payload, String certificateId, char[] pin) throws SignerException {
        if (payload == null || payload.length == 0) throw new SignerException("İmzalanacak veri boş");
        if (pin == null || pin.length == 0) throw new SignerException("PIN boş");
        synchronized (lock) {
            ensureSession();
            try {
                Entry selected = find(certificateId);
                if (!(selected.certificate.getPublicKey() instanceof RSAPublicKey)) {
                    throw new SignerException("Ham PKCS#1 işlemi için RSA sertifikası gerekir");
                }
                RSAPublicKey publicKey = (RSAPublicKey) selected.certificate.getPublicKey();
                verifyPin(pin);
                setSecurityEnvironment(selected.certificate);

                byte[] signature = executePsoSign(payload);

                Signature verifier = Signature.getInstance("NONEwithRSA");
                verifier.initVerify(publicKey);
                verifier.update(payload);
                if (!verifier.verify(signature)) {
                    throw new SignerException("Ham ArkSigner kart imzası doğrulanamadı");
                }
                DiagnosticLogger.i(DiagnosticLogger.Tag.SIGN, "ArkSigner ham PKCS#1 imza başarıyla üretildi (" + signature.length + " bayt)");
                return signature;
            } catch (SignerException e) {
                throw e;
            } catch (Exception e) {
                throw new SignerException("Ham ArkSigner PKCS#1 imzası başarısız: " + e.getMessage(), e);
            } finally {
                Arrays.fill(pin, '\0');
                closeSession();
            }
        }
    }

    private void ensureSession() throws SignerException {
        if (card != null && AndroidCardSession.presentQuietly()) return;
        state = State.STARTING;
        closeSession();
        try {
            card = AndroidCcidProvider.directCard();
            channel = card.getBasicChannel();
            selectApplication();
            queryRemainingPinAttempts();
            state = State.READY;
            DiagnosticLogger.i(DiagnosticLogger.Tag.DRIVER, "ArkSigner token oturumu açıldı");
        } catch (Exception e) {
            state = State.ERROR;
            closeSession();
            throw new SignerException("ArkSigner token oturumu açılamadı: " + e.getMessage(), e);
        }
    }

    private void selectApplication() {
        // Try candidate PKCS#15 and token AIDs
        for (byte[] aid : CANDIDATE_AIDS) {
            try {
                CommandAPDU select = new CommandAPDU(0x00, 0xA4, 0x04, 0x00, aid);
                ResponseAPDU resp = channel.transmit(select);
                if (resp.getSW() == 0x9000 || (resp.getSW() >>> 8) == 0x61) {
                    DiagnosticLogger.i(DiagnosticLogger.Tag.DRIVER, "ArkSigner uygulama seçildi: AID " + hex(aid));
                    return;
                }
            } catch (Exception ignored) { }
        }

        // Try selecting DF 5015 (PKCS#15 directory)
        try {
            CommandAPDU selectDf = new CommandAPDU(0x00, 0xA4, 0x00, 0x00, new byte[]{0x50, 0x15});
            ResponseAPDU resp = channel.transmit(selectDf);
            if (resp.getSW() == 0x9000) {
                DiagnosticLogger.i(DiagnosticLogger.Tag.DRIVER, "ArkSigner DF 5015 seçildi");
                return;
            }
        } catch (Exception ignored) { }

        // Try selecting Master File 3F00
        try {
            CommandAPDU selectMf = new CommandAPDU(0x00, 0xA4, 0x00, 0x00, new byte[]{0x3F, 0x00});
            channel.transmit(selectMf);
        } catch (Exception ignored) { }
    }

    private List<byte[]> discoverCertificates() {
        List<byte[]> certDers = new ArrayList<>();

        for (byte[] fid : CANDIDATE_CERT_FIDS) {
            try {
                // Select EF
                CommandAPDU select = new CommandAPDU(0x00, 0xA4, 0x00, 0x00, fid);
                ResponseAPDU resp = channel.transmit(select);
                if (resp.getSW() != 0x9000 && (resp.getSW() >>> 8) != 0x61) continue;

                // Read binary file contents
                byte[] content = readFileBinary();
                if (content == null || content.length < 32) continue;

                // Check if this file is a direct X.509 certificate (starts with ASN.1 SEQUENCE 0x30 0x82...)
                if ((content[0] & 0xFF) == 0x30 && (content[1] & 0xFF) == 0x82) {
                    certDers.add(content);
                    DiagnosticLogger.i(DiagnosticLogger.Tag.CERT, "Doğrudan sertifika EF bulundu: " + hex(fid) + " (" + content.length + " bayt)");
                } else {
                    // Try parsing as PKCS#15 CDF to locate certificate paths
                    List<byte[]> parsed = extractCertificatesFromCdf(content);
                    if (!parsed.isEmpty()) {
                        certDers.addAll(parsed);
                    }
                }
            } catch (Exception e) {
                DiagnosticLogger.d(DiagnosticLogger.Tag.CERT, "EF " + hex(fid) + " sorgulanırken atlandı: " + e.getMessage());
            }
        }
        return certDers;
    }

    private List<byte[]> extractCertificatesFromCdf(byte[] cdf) {
        List<byte[]> list = new ArrayList<>();
        // Search for sub-files or nested certificates in CDF
        int offset = 0;
        while (offset < cdf.length - 4) {
            if ((cdf[offset] & 0xFF) == 0x30 && (cdf[offset + 1] & 0xFF) == 0x82) {
                int len = ((cdf[offset + 2] & 0xFF) << 8) | (cdf[offset + 3] & 0xFF);
                int total = len + 4;
                if (offset + total <= cdf.length) {
                    byte[] candidate = Arrays.copyOfRange(cdf, offset, offset + total);
                    try {
                        CertificateFactory.getInstance("X.509").generateCertificate(new ByteArrayInputStream(candidate));
                        list.add(candidate);
                        DiagnosticLogger.i(DiagnosticLogger.Tag.CERT, "CDF içinden gömülü sertifika çıkarıldı (" + candidate.length + " bayt)");
                    } catch (Exception ignored) { }
                    offset += total;
                    continue;
                }
            } else if ((cdf[offset] & 0xFF) == 0x04) { // ASN.1 OCTET STRING (often Path to certificate EF)
                int pathLen = cdf[offset + 1] & 0xFF;
                if ((pathLen == 2 || pathLen == 4) && offset + 2 + pathLen <= cdf.length) {
                    byte[] fid = new byte[]{cdf[offset + pathLen], cdf[offset + pathLen + 1]};
                    try {
                        CommandAPDU select = new CommandAPDU(0x00, 0xA4, 0x00, 0x00, fid);
                        ResponseAPDU resp = channel.transmit(select);
                        if (resp.getSW() == 0x9000 || (resp.getSW() >>> 8) == 0x61) {
                            byte[] certData = readFileBinary();
                            if (certData != null && certData.length > 32 && (certData[0] & 0xFF) == 0x30) {
                                CertificateFactory.getInstance("X.509").generateCertificate(new ByteArrayInputStream(certData));
                                list.add(certData);
                                DiagnosticLogger.i(DiagnosticLogger.Tag.CERT, "CDF yolundan sertifika okundu: " + hex(fid) + " (" + certData.length + " bayt)");
                            }
                        }
                    } catch (Exception ignored) { }
                }
            }
            offset++;
        }
        return list;
    }

    private byte[] readFileBinary() throws CardException {
        java.io.ByteArrayOutputStream bout = new java.io.ByteArrayOutputStream();
        int offset = 0;
        int chunkSize = 240;

        while (offset < 8192) {
            int p1 = (offset >> 8) & 0xFF;
            int p2 = offset & 0xFF;
            CommandAPDU read = new CommandAPDU(0x00, 0xB0, p1, p2, chunkSize);
            ResponseAPDU resp = channel.transmit(read);
            int sw = resp.getSW();

            if (sw == 0x9000) {
                byte[] data = resp.getData();
                if (data.length == 0) break;
                bout.write(data, 0, data.length);
                if (data.length < chunkSize) break;
                offset += data.length;
            } else if ((sw >>> 8) == 0x6C) {
                // Wrong Le: retry with exact Le requested by card
                int correctLe = sw & 0xFF;
                if (correctLe == 0) correctLe = 256;
                CommandAPDU retry = new CommandAPDU(0x00, 0xB0, p1, p2, correctLe);
                ResponseAPDU retryResp = channel.transmit(retry);
                if (retryResp.getSW() == 0x9000 && retryResp.getData().length > 0) {
                    bout.write(retryResp.getData(), 0, retryResp.getData().length);
                }
                break;
            } else if (sw == 0x6B00 || sw == 0x6A82 || sw == 0x6A86) {
                // End of file reached
                break;
            } else {
                break;
            }
        }
        return bout.toByteArray();
    }

    private void queryRemainingPinAttempts() {
        byte[] pinRefs = new byte[]{0x01, (byte) 0x81, 0x02, (byte) 0x82};
        for (byte ref : pinRefs) {
            try {
                // Verify with Lc=0 to query trial count
                CommandAPDU query = new CommandAPDU(0x00, 0x20, 0x00, ref & 0xFF);
                ResponseAPDU resp = channel.transmit(query);
                int sw = resp.getSW();
                if ((sw >>> 8) == 0x63) {
                    remainingPinRetries = sw & 0x0F;
                    activePinRef = ref;
                    DiagnosticLogger.i(DiagnosticLogger.Tag.PIN, String.format(Locale.ROOT,
                            "PIN durumu (Ref %02X): Kalan deneme hakkı = %d", ref, remainingPinRetries));
                    return;
                } else if (sw == 0x9000) {
                    activePinRef = ref;
                    remainingPinRetries = 3;
                    DiagnosticLogger.d(DiagnosticLogger.Tag.PIN, "PIN zaten doğrulanmış (Ref " + ref + ")");
                    return;
                }
            } catch (Exception ignored) { }
        }
    }

    private void verifyPin(char[] pin) throws SignerException {
        byte[] pinBytes = new byte[pin.length];
        for (int i = 0; i < pin.length; i++) {
            pinBytes[i] = (byte) pin[i];
        }

        byte[] tryRefs = new byte[]{activePinRef, 0x01, (byte) 0x81, 0x02, (byte) 0x82};
        SignerException lastError = null;

        for (byte ref : tryRefs) {
            try {
                CommandAPDU verifyCmd = new CommandAPDU(0x00, 0x20, 0x00, ref & 0xFF, pinBytes);
                lastApduStage = String.format(Locale.ROOT, "PIN doğrulama (Ref=%02X)", ref);
                ResponseAPDU resp = channel.transmit(verifyCmd);
                int sw = resp.getSW();

                if (sw == 0x9000) {
                    activePinRef = ref;
                    remainingPinRetries = 3;
                    DiagnosticLogger.i(DiagnosticLogger.Tag.PIN, "PIN doğrulaması başarılı (Ref=" + ref + ")");
                    return;
                } else if ((sw >>> 8) == 0x63) {
                    int remaining = sw & 0x0F;
                    remainingPinRetries = remaining;
                    DiagnosticLogger.w(DiagnosticLogger.Tag.PIN, "PIN hatalı! Kalan deneme: " + remaining);
                    throw new SignerException("Hatalı PIN! Kalan deneme hakkı: " + remaining);
                } else if (sw == 0x6983 || sw == 0x6984) {
                    remainingPinRetries = 0;
                    DiagnosticLogger.e(DiagnosticLogger.Tag.PIN, "PIN kilitlendi / bloke oldu!", null);
                    throw new SignerException("E-imza PIN'i bloke oldu / kilitlendi! PUK ile açılması gerekir.");
                } else if (sw == 0x6A88) {
                    // Key/reference not found, try next candidate reference
                    continue;
                } else {
                    lastError = new SignerException(String.format(Locale.ROOT, "PIN doğrulanamadı (SW=%04X)", sw));
                }
            } catch (SignerException e) {
                throw e;
            } catch (Exception e) {
                lastError = new SignerException("PIN APDU hatası: " + e.getMessage(), e);
            }
        }
        if (lastError != null) throw lastError;
        throw new SignerException("PIN doğrulama başarısız");
    }

    private void setSecurityEnvironment(X509Certificate cert) throws Exception {
        boolean rsa = cert.getPublicKey() instanceof RSAPublicKey;
        byte alg = (byte) (rsa ? 0x02 : 0x42); // 0x02: RSA PKCS#1 SHA-256, 0x42: ECDSA

        // MSE Set Format 1: 00 22 41 B6 06 80 01 [ALG] 84 01 [KEY_REF]
        byte[] mseData1 = new byte[]{(byte) 0x80, 0x01, alg, (byte) 0x84, 0x01, activeKeyRef};
        CommandAPDU mse1 = new CommandAPDU(0x00, 0x22, 0x41, 0xB6, mseData1);
        lastApduStage = "MSE Güvenlik Ortamı Ayarı (41 B6)";
        ResponseAPDU resp = channel.transmit(mse1);
        if (resp.getSW() == 0x9000) return;

        // MSE Set Format 2: 00 22 41 B6 with algorithm 0x92 (ArkSigner / AKİS local key format)
        byte[] mseData2 = new byte[]{(byte) 0x80, 0x01, (byte) 0x92, (byte) 0x84, 0x01, (byte) (0x80 | (activeKeyRef & 0x7F))};
        CommandAPDU mse2 = new CommandAPDU(0x00, 0x22, 0x41, 0xB6, mseData2);
        ResponseAPDU resp2 = channel.transmit(mse2);
        if (resp2.getSW() == 0x9000) return;

        // MSE Set Format 3: CardOS / ePass style 00 22 C1 A4 03 83 01 [KEY_REF]
        CommandAPDU mse3 = new CommandAPDU(0x00, 0x22, 0xC1, 0xA4, new byte[]{(byte) 0x83, 0x01, activeKeyRef});
        ResponseAPDU resp3 = channel.transmit(mse3);
        if (resp3.getSW() == 0x9000) return;

        // MSE Set Format 4: Legacy key-index MSE: 00 22 C3 22 [KEY_REF]
        CommandAPDU mse4 = new CommandAPDU(0x00, 0x22, 0xC3, 0x22, new byte[]{activeKeyRef});
        ResponseAPDU resp4 = channel.transmit(mse4);
        if (resp4.getSW() != 0x9000) {
            DiagnosticLogger.w(DiagnosticLogger.Tag.DRIVER, String.format(Locale.ROOT,
                    "MSE Set komutları uyarı verdi (SW=%04X), PSO doğrudan deneniyor", resp4.getSW()));
        }
    }

    private byte[] executePsoSign(byte[] input) throws Exception {
        lastApduStage = "PSO Sayısal İmza Hesaplama (2A 9E 9A)";
        // PSO: Compute Digital Signature (00 2A 9E 9A [LEN] [INPUT])
        CommandAPDU pso = new CommandAPDU(0x00, 0x2A, 0x9E, 0x9A, input, 256);
        ResponseAPDU resp = channel.transmit(pso);
        int sw = resp.getSW();

        if (sw == 0x9000) {
            return resp.getData();
        }

        // SW 61 xx: GET RESPONSE required to fetch signature bytes
        if ((sw >>> 8) == 0x61) {
            int len = sw & 0xFF;
            if (len == 0) len = 256;
            CommandAPDU getResponse = new CommandAPDU(0x00, 0xC0, 0x00, 0x00, len);
            ResponseAPDU grResp = channel.transmit(getResponse);
            if (grResp.getSW() == 0x9000) {
                return grResp.getData();
            }
        }

        // Fallback: Alternative PSO instruction (00 2A 80 86) used by some CardOS/ePass tokens
        if (sw == 0x6D00 || sw == 0x6A86 || sw == 0x6A88) {
            lastApduStage = "PSO Yedek İmza Komutu (2A 80 86)";
            CommandAPDU psoAlt = new CommandAPDU(0x00, 0x2A, 0x80, 0x86, input, 256);
            ResponseAPDU altResp = channel.transmit(psoAlt);
            if (altResp.getSW() == 0x9000) {
                return altResp.getData();
            }
            if ((altResp.getSW() >>> 8) == 0x61) {
                CommandAPDU gr = new CommandAPDU(0x00, 0xC0, 0x00, 0x00, altResp.getSW() & 0xFF);
                ResponseAPDU grResp = channel.transmit(gr);
                if (grResp.getSW() == 0x9000) return grResp.getData();
            }
            throw new SignerException(String.format(Locale.ROOT, "ArkSigner PSO imza hatası: SW=%04X", altResp.getSW()));
        }

        throw new SignerException(String.format(Locale.ROOT, "ArkSigner PSO imza komutu başarısız: SW=%04X", sw));
    }

    private Entry find(String id) throws SignerException {
        if (id == null) throw new SignerException("Sertifika seçilmedi");
        for (Entry entry : entries) if (entry.id.equals(id)) return entry;
        certificates();
        for (Entry entry : entries) if (entry.id.equals(id)) return entry;
        throw new SignerException("Seçilen sertifika kartta bulunamadı");
    }

    private void closeSession() {
        if (card != null) {
            try { card.disconnect(false); } catch (CardException ignored) { }
            card = null;
        }
        channel = null;
    }

    @Override
    public void close() {
        synchronized (lock) {
            closeSession();
            state = State.STOPPED;
        }
    }

    String cardFailureDetail() {
        synchronized (lock) {
            return "ArkSigner Sürücüsü: sonAşama=" + lastApduStage
                    + (remainingPinRetries >= 0 ? "; kalanHak=" + remainingPinRetries : "");
        }
    }

    private static String extractCN(X509Certificate cert) {
        try {
            X500Name name = new X500Name(cert.getSubjectX500Principal().getName(X500Principal.RFC2253));
            RDN[] rdns = name.getRDNs(BCStyle.CN);
            if (rdns.length == 0) return "";
            return IETFUtils.valueToString(rdns[0].getFirst().getValue());
        } catch (Exception e) {
            return "";
        }
    }

    private static String hex(byte[] bytes) {
        if (bytes == null) return "";
        StringBuilder out = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) out.append(String.format(Locale.ROOT, "%02X", b & 0xFF));
        return out.toString();
    }

    private static final class Entry {
        final String id;
        final byte[] der;
        final X509Certificate certificate;
        Entry(String id, byte[] der, X509Certificate certificate) {
            this.id = id;
            this.der = der;
            this.certificate = certificate;
        }
    }
}
