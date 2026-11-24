package app.eimza.mobile;

import java.io.ByteArrayInputStream;
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

import tubitak.akis.cif.akisExceptions.AkisCIFException;
import tubitak.akis.cif.akisExceptions.AkisCardException;
import tubitak.akis.cif.akisExceptions.AkisSWException;
import tubitak.akis.cif.akisExceptions.UnrecognizedCardException;
import tubitak.akis.cif.commands.AbstractAkisCommands;
import tubitak.akis.cif.commands.PKCS11Functions;
import tubitak.akis.cif.dataStructures.AkisKey;
import tubitak.akis.cif.dataStructures.KeyType;
import tubitak.akis.cif.functions.Conversions;
import tubitak.akis.cif.functions.ICommandTransmitter;

/**
 * Unified master signer backend supporting the three major Turkish e-signature tokens:
 * 1) ArkSigner Arkİmza Token
 * 2) TÜRKTRUST / TBB Kırmızı Token (Baro Kart)
 * 3) Kamu SM / TÜBİTAK (ATR19)
 *
 * Automatically detects the card model from ATR and hardware descriptors, selects the optimal driver
 * (native ArkSigner PKCS#15 or TÜBİTAK AKİS CIF), and provides transparent fallback.
 */
public final class AkisSignerBackend implements SignerBackend {
    public enum TokenType {
        ARKSIGNER_ARKIMZA("ArkSigner Arkİmza Token", "#1565C0"),
        TURKTRUST_TBB("TÜRKTRUST / TBB Kırmızı Token (Baro Kart)", "#C62828"),
        KAMUSM_ATR19("Kamu SM / TÜBİTAK (ATR19)", "#2E7D32"),
        GENERIC_AKIS("AKİS / TÜBİTAK E-İmza Kartı", "#00838F"),
        GENERIC_PKCS15("Standart PKCS#15 E-İmza Tokenı", "#455A64"),
        UNKNOWN("Akıllı Kart / E-İmza Tokenı", "#37474F");

        public final String title;
        public final String badgeColor;
        TokenType(String title, String badgeColor) {
            this.title = title;
            this.badgeColor = badgeColor;
        }
    }

    private final Object lock = new Object();
    private final List<Entry> entries = new ArrayList<>();
    private final List<CertificateSummary> summaries = new ArrayList<>();
    private MobilePkcs11Functions functions;
    private AndroidTransmitter transmitter;
    private ArkSignerTokenBackend arkBackend;
    private SignerBackend activeDriver;
    private TokenType detectedTokenType = TokenType.UNKNOWN;
    private State state = State.WAITING_FOR_READER;
    private int signingKey = -1;
    private String lastCardProfile = "";

    @Override public String id() {
        synchronized (lock) {
            return activeDriver != null ? activeDriver.id() : "eimza_unified";
        }
    }

    @Override public String displayName() {
        synchronized (lock) {
            return detectedTokenType.title;
        }
    }

    public String detectedTokenDisplayName() {
        synchronized (lock) {
            return detectedTokenType.title;
        }
    }

    public TokenType detectedTokenType() {
        synchronized (lock) {
            return detectedTokenType;
        }
    }

    @Override public State state() {
        synchronized (lock) { return state; }
    }

    /**
     * Identifies token type based on ATR and reader device properties.
     */
    private static TokenType identifyToken(byte[] atr, String readerName) {
        if (atr == null || atr.length < 2) return TokenType.UNKNOWN;
        String atrHex = hex(atr).toUpperCase(Locale.ROOT);
        String reader = readerName != null ? readerName.toLowerCase(Locale.ROOT) : "";

        // Check for ArkSigner / Feitian ePass2003 / CardOS tokens
        if (atrHex.startsWith("3BF21800008131FE454654") || atrHex.contains("454654") // "EFT"
                || atrHex.startsWith("3BD218008131FE58") || atrHex.startsWith("3BD518008131FE58") // CardOS 5
                || atrHex.startsWith("3B7F96000080318065B085") // SafeNet IDPrime
                || atrHex.startsWith("3B9F978131FE4580655443") // ArkSigner ARK-IMZA TC Token
                || reader.contains("arksigner") || reader.contains("arkimza") || reader.contains("ark-imza") || reader.contains("ark") || reader.contains("epass")) {
            return TokenType.ARKSIGNER_ARKIMZA;
        }

        // Check for TürkTrust TBB Kırmızı Token (Baro Kart)
        if (atrHex.startsWith("3B7B1800000031C0739E010B")
                || reader.contains("tbb") || reader.contains("turktrust") || reader.contains("türktrust")
                || reader.contains("baro") || reader.contains("acr38") || reader.contains("acr39")) {
            return TokenType.TURKTRUST_TBB;
        }

        // Check for Kamu SM / TÜBİTAK ATR19
        if (atrHex.startsWith("3BB718008131FE65") || atrHex.startsWith("3B7D180000")
                || atrHex.startsWith("3B7F1800000031C0739E010B")
                || reader.contains("atr19") || reader.contains("mini lector") || reader.contains("kamusm")) {
            return TokenType.KAMUSM_ATR19;
        }

        // General AKİS pattern
        if (atrHex.startsWith("3BB7") || atrHex.startsWith("3BBA11008131FE4D55454B4145") || atrHex.contains("55454B4145")) { // "UEKAE"
            return TokenType.GENERIC_AKIS;
        }

        return TokenType.GENERIC_PKCS15;
    }

    @Override public List<CertificateSummary> certificates() throws SignerException {
        synchronized (lock) {
            ensureSession();
            // If active driver is ArkSignerTokenBackend, delegate directly
            if (activeDriver != null && activeDriver != this) {
                List<CertificateSummary> certs = activeDriver.certificates();
                summaries.clear();
                summaries.addAll(certs);
                return certs;
            }

            String stage = "AKİS imza sertifikaları isteği";
            try {
                entries.clear();
                summaries.clear();
                CertificateFactory cf = CertificateFactory.getInstance("X.509");
                stage = "AKİS kartından imza sertifikalarını alma";
                List<byte[]> certificateBytes = functions.getSignatureCertificates();
                if (certificateBytes == null || certificateBytes.isEmpty()) {
                    // Try fallback to ArkSigner/PKCS#15 driver to find certificates
                    DiagnosticLogger.w(DiagnosticLogger.Tag.DRIVER, "AKİS CIF sertifika döndürmedi; ArkSigner PKCS#15 sürücüsü deneniyor");
                    return fallbackToArkDriver();
                }
                stage = "X.509 sertifikalarını çözümleme";
                for (byte[] der : certificateBytes) {
                    if (der == null || der.length == 0) continue;
                    X509Certificate cert = (X509Certificate) cf.generateCertificate(new ByteArrayInputStream(der));
                    String id = hex(MessageDigest.getInstance("SHA-256").digest(der));
                    String subject = cert.getSubjectX500Principal().getName(X500Principal.RFC2253);
                    String until = cert.getNotAfter().toInstant().toString();
                    entries.add(new Entry(id, der.clone(), cert));
                    summaries.add(new CertificateSummary(id, subject, until));
                    DiagnosticLogger.i(DiagnosticLogger.Tag.CERT, "AKİS sertifikası yüklendi: CN="
                            + extractCN(cert) + ", Bitiş=" + until);
                }
                return Collections.unmodifiableList(new ArrayList<>(summaries));
            } catch (Exception e) {
                // If AKİS CIF reading fails, try ArkSigner PKCS#15 fallback
                try {
                    return fallbackToArkDriver();
                } catch (Exception fallbackErr) {
                    state = State.ERROR;
                    throw new SignerException(stage + " başarısız: " + describeCause(e), e);
                }
            }
        }
    }

    private List<CertificateSummary> fallbackToArkDriver() throws SignerException {
        DiagnosticLogger.i(DiagnosticLogger.Tag.DRIVER, "ArkSigner PKCS#15 sürücü yedekleme yoluna geçiliyor");
        if (arkBackend == null) arkBackend = new ArkSignerTokenBackend();
        List<CertificateSummary> certs = arkBackend.certificates();
        activeDriver = arkBackend;
        summaries.clear();
        summaries.addAll(certs);
        return certs;
    }

    List<ArkCertificate> arkCertificates() throws SignerException {
        certificates();
        synchronized (lock) {
            if (activeDriver != null && activeDriver != this && activeDriver instanceof ArkSignerTokenBackend) {
                return ((ArkSignerTokenBackend) activeDriver).arkCertificates();
            }
            List<ArkCertificate> out = new ArrayList<>();
            for (Entry e : entries) {
                out.add(new ArkCertificate(e.id, e.der.clone(), e.certificate,
                        e.certificate.getSerialNumber().toString(16).toUpperCase(Locale.ROOT)));
            }
            return out;
        }
    }

    /** Sertifikadan CN değerini BouncyCastle ile güvenli şekilde çeker. */
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
            return value.replaceAll("[^0-9]", "");
        } catch (Exception e) {
            return "";
        }
    }

    public static final class ArkCertificate {
        public final String id, serial;
        public final byte[] der;
        public final X509Certificate certificate;
        public final String subjectCN;
        public final String subjectSerial;

        public ArkCertificate(String id, byte[] der, X509Certificate certificate, String serial) {
            this.id = id; this.der = der; this.certificate = certificate; this.serial = serial;
            this.subjectCN = extractCN(certificate);
            this.subjectSerial = extractTCKN(certificate);
        }
    }

    String idForSerial(String serial) throws SignerException {
        if (serial == null || serial.isEmpty()) return null;
        if (activeDriver != null && activeDriver != this && activeDriver instanceof ArkSignerTokenBackend) {
            return ((ArkSignerTokenBackend) activeDriver).idForSerial(serial);
        }

        String wantedHex = serial.replaceAll("[^0-9A-Fa-f]", "").replaceFirst("^(?i)0+", "");
        java.math.BigInteger wantedDec = null;
        try { wantedDec = new java.math.BigInteger(serial.replaceAll("[^0-9]", "")); }
        catch (Exception ignored) {}

        for (ArkCertificate e : arkCertificates()) {
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

    @Override public byte[] sign(byte[] payload, String certificateId, char[] pin) throws SignerException {
        if (payload == null || payload.length == 0) throw new SignerException("İmzalanacak veri boş");
        if (pin == null || pin.length == 0) throw new SignerException("PIN boş");
        synchronized (lock) {
            ensureSession();
            if (activeDriver != null && activeDriver != this) {
                return activeDriver.sign(payload, certificateId, pin);
            }
            try {
                Entry selected = find(certificateId);
                requireSupportedKey(selected.certificate);
                byte keyId = prepareSigning(selected, pin);
                AbstractAkisCommands commands = functions.commandsForSigning();
                boolean rsa = selected.certificate.getPublicKey() instanceof RSAPublicKey;
                byte[] signingInput = rsa ? RsaDigestInfo.sha256(payload) : payload;
                byte[] signature = cardSign(commands, keyId, signingInput, !rsa);
                Signature verifier = Signature.getInstance(rsa ? "SHA256withRSA" : "SHA256withECDSA");
                verifier.initVerify(selected.certificate.getPublicKey());
                verifier.update(payload);
                if (!verifier.verify(signature)) throw new SignerException("Kart imzası sertifikayla doğrulanmadı");
                DiagnosticLogger.i(DiagnosticLogger.Tag.SIGN, "AKİS kart imzası başarıyla oluşturuldu");
                return signature;
            } catch (SignerException e) {
                throw e;
            } catch (Exception e) {
                throw new SignerException("AKİS kart imzalama işlemi başarısız: " + e.getMessage(), e);
            } finally {
                Arrays.fill(pin, '\0');
                closeSession();
            }
        }
    }

    @Override public byte[] signRawPkcs1(byte[] payload, String certificateId, char[] pin) throws SignerException {
        if (payload == null || payload.length == 0) throw new SignerException("İmzalanacak veri boş");
        if (pin == null || pin.length == 0) throw new SignerException("PIN boş");
        synchronized (lock) {
            ensureSession();
            if (activeDriver != null && activeDriver != this) {
                return activeDriver.signRawPkcs1(payload, certificateId, pin);
            }
            try {
                Entry selected = find(certificateId);
                if (!(selected.certificate.getPublicKey() instanceof RSAPublicKey))
                    throw new SignerException("PKCS#1 işlemi için RSA sertifikası gerekiyor; seçilen kart sertifikası "
                            + keyAlgorithm(selected.certificate));
                RSAPublicKey publicKey = (RSAPublicKey) selected.certificate.getPublicKey();
                if (payload.length > (publicKey.getModulus().bitLength() + 7) / 8 - 11)
                    throw new SignerException("Ham PKCS#1 verisi RSA blok sınırını aşıyor");
                byte keyId = prepareSigning(selected, pin);
                byte[] signed = cardSign(functions.commandsForSigning(), keyId, payload, false);
                Signature verifier = Signature.getInstance("NONEwithRSA");
                verifier.initVerify(publicKey);
                verifier.update(payload);
                if (!verifier.verify(signed)) throw new SignerException("Ham kart imzası doğrulanmadı");
                DiagnosticLogger.i(DiagnosticLogger.Tag.SIGN, "AKİS ham PKCS#1 imza başarıyla üretildi");
                return signed;
            } catch (SignerException e) {
                throw e;
            } catch (Exception e) {
                throw new SignerException("Ham AKİS PKCS#1 imzası başarısız: " + e.getMessage(), e);
            } finally {
                Arrays.fill(pin, '\0');
                closeSession();
            }
        }
    }

    private Entry find(String id) throws SignerException {
        if (id == null) throw new SignerException("Sertifika seçilmedi");
        for (Entry entry : entries) if (entry.id.equals(id)) return entry;
        certificates();
        for (Entry entry : entries) if (entry.id.equals(id)) return entry;
        throw new SignerException("Seçilen sertifika kartta bulunamadı");
    }

    private byte prepareSigning(Entry selected, char[] pin) throws Exception {
        signingKey = -1;
        requireSupportedKey(selected.certificate);
        AbstractAkisCommands commands = functions.commandsForSigning();
        if (usesPkcs15Metadata(commands)) {
            byte key = AkisV25Signing.prepare(commands, pin, functions.fileForCertificate(selected.der));
            signingKey = key & 255;
            return key;
        }
        functions.login(new String(pin));
        return findPrivateKeyId(selected.certificate);
    }

    private static byte[] cardSign(AbstractAkisCommands commands, byte key, byte[] input,
                                   boolean ecc) throws Exception {
        if (usesPkcs15Metadata(commands)) {
            return ecc ? AkisV25Signing.signEcc(commands, key, input)
                    : AkisV25Signing.sign(commands, key, input);
        }
        return ecc
                ? commands.sign(tubitak.akis.cif.dataStructures.Algorithm.ECC,
                tubitak.akis.cif.dataStructures.Algorithm.SHA_256, key, input)
                : commands.sign(input, key);
    }

    private static boolean usesPkcs15Metadata(AbstractAkisCommands commands) {
        return commands instanceof tubitak.akis.cif.commands.CommandsV20
                || commands instanceof tubitak.akis.cif.commands.CommandsV25
                || commands instanceof tubitak.akis.cif.commands.CommandsGezgin10;
    }

    private byte findRsaKeyId(RSAPublicKey publicKey) throws Exception {
        AkisKey[] keys = functions.commandsForSigning().getKeyInfos();
        for (AkisKey key : keys) {
            if (key.getKeyType() != KeyType.PRIVATE_RSA) continue;
            byte[] modulus = functions.commandsForSigning().getModulus(key.getKeyID());
            if (modulus != null && new java.math.BigInteger(1, modulus).equals(publicKey.getModulus())) {
                return key.getKeyID();
            }
        }
        throw new SignerException("Sertifikayla eşleşen RSA özel anahtarı kartta bulunamadı");
    }

    private byte findPrivateKeyId(X509Certificate certificate) throws Exception {
        if (certificate.getPublicKey() instanceof RSAPublicKey)
            return findRsaKeyId((RSAPublicKey) certificate.getPublicKey());
        List<Byte> ecc = new ArrayList<>();
        for (AkisKey key : functions.commandsForSigning().getKeyInfos()) {
            if (key.getKeyType() == KeyType.PRIVATE_ECC) ecc.add(key.getKeyID());
        }
        if (ecc.size() == 1) return ecc.get(0);
        if (ecc.isEmpty()) throw new SignerException("EC sertifikası için özel anahtar bulunamadı");
        throw new SignerException("Birden fazla EC özel anahtarı var; sertifika-anahtar eşleşmesi belirsiz");
    }

    private static void requireSupportedKey(X509Certificate certificate) throws SignerException {
        String algorithm = certificate.getPublicKey() == null ? "" :
                certificate.getPublicKey().getAlgorithm();
        if (!(certificate.getPublicKey() instanceof RSAPublicKey)
                && !"EC".equalsIgnoreCase(algorithm)
                && !"ECDSA".equalsIgnoreCase(algorithm)) {
            throw new SignerException("AKİS sertifikası " + keyAlgorithm(certificate)
                    + "; desteklenen imza profilleri RSA ve ECDSA");
        }
    }

    private static String keyAlgorithm(X509Certificate certificate) {
        java.security.PublicKey key = certificate.getPublicKey();
        String algorithm = key == null ? "bilinmiyor" : key.getAlgorithm();
        int size = key instanceof RSAPublicKey
                ? ((RSAPublicKey) key).getModulus().bitLength() : 0;
        return size == 0 ? algorithm : algorithm + "-" + size;
    }

    private void ensureSession() throws SignerException {
        if ((functions != null || activeDriver != null) && AndroidCardSession.presentQuietly()) return;
        state = State.STARTING;
        closeSession();
        try {
            byte[] atr = AndroidCardSession.atr();
            String readerName = AndroidCardSession.readerName();

            // Identify token type
            detectedTokenType = identifyToken(atr, readerName);
            DiagnosticLogger.i(DiagnosticLogger.Tag.DRIVER, "Kart kimliği tespit edildi: " + detectedTokenType.title);

            // If token is identified as ArkSigner Arkİmza, prioritize ArkSigner driver
            if (detectedTokenType == TokenType.ARKSIGNER_ARKIMZA) {
                try {
                    if (arkBackend == null) arkBackend = new ArkSignerTokenBackend();
                    arkBackend.certificates();
                    activeDriver = arkBackend;
                    state = State.READY;
                    DiagnosticLogger.i(DiagnosticLogger.Tag.DRIVER, "ArkSigner birincil sürücüsü başarıyla başlatıldı");
                    return;
                } catch (Exception arkErr) {
                    DiagnosticLogger.w(DiagnosticLogger.Tag.DRIVER, "ArkSigner birincil sürücü hatası: " + arkErr.getMessage() + ", AKİS CIF deneniyor");
                }
            }

            // Standard AKİS / TÜBİTAK CIF connection path
            CardTerminal terminal = AndroidCcidProvider.directTerminal();
            try {
                transmitter = new AndroidTransmitter(terminal);
                functions = new MobilePkcs11Functions();
                functions.openSession(transmitter);
                lastCardProfile = functions.cardProfile();
                activeDriver = this;
                state = State.READY;
                DiagnosticLogger.i(DiagnosticLogger.Tag.DRIVER, "AKİS CIF sürücüsü başarıyla başlatıldı (Profil: " + lastCardProfile + ")");
            } catch (UnrecognizedCardException uce) {
                // If AKİS CIF does not recognize this ATR, smoothly fallback to ArkSigner native driver
                DiagnosticLogger.w(DiagnosticLogger.Tag.DRIVER, "AKİS CIF ATR'yi tanımadı; ArkSigner yerel sürücüsüne geçiliyor");
                if (arkBackend == null) arkBackend = new ArkSignerTokenBackend();
                arkBackend.certificates();
                activeDriver = arkBackend;
                state = State.READY;
            }
        } catch (SignerException e) {
            state = State.ERROR;
            throw e;
        } catch (Exception e) {
            // Last chance fallback: try ArkSigner driver before giving up
            try {
                if (arkBackend == null) arkBackend = new ArkSignerTokenBackend();
                arkBackend.certificates();
                activeDriver = arkBackend;
                state = State.READY;
                DiagnosticLogger.i(DiagnosticLogger.Tag.DRIVER, "Son çare ArkSigner sürücüsü başarıyla bağlandı");
            } catch (Exception finalErr) {
                state = State.ERROR;
                closeSession();
                throw new SignerException("E-imza kart oturumu açılamadı: " + describeCause(e), e);
            }
        }
    }

    private void closeSession() {
        if (functions != null) functions.closeSession();
        functions = null;
        if (transmitter != null) transmitter.closeCardTerminal();
        transmitter = null;
        if (arkBackend != null) arkBackend.close();
        activeDriver = null;
    }

    @Override public void close() {
        synchronized (lock) {
            closeSession();
            state = State.STOPPED;
        }
    }

    String cardFailureDetail() {
        synchronized (lock) {
            if (activeDriver != null && activeDriver != this && activeDriver instanceof ArkSignerTokenBackend) {
                return ((ArkSignerTokenBackend) activeDriver).cardFailureDetail();
            }
            String transport = transmitter == null ? "" : transmitter.failure;
            StringBuilder detail = new StringBuilder();
            if (!lastCardProfile.isEmpty()) detail.append("profil=").append(lastCardProfile);
            if (!transport.isEmpty()) {
                if (detail.length() > 0) detail.append("; ");
                detail.append(transport);
            }
            if (signingKey >= 0) detail.append(String.format(Locale.ROOT,
                    "%sPKCS15 keyRef=%02X", detail.length() == 0 ? "" : "; ", signingKey));
            return detail.toString();
        }
    }

    private static final class Entry {
        final String id; final byte[] der; final X509Certificate certificate;
        Entry(String id, byte[] der, X509Certificate certificate) { this.id = id; this.der = der; this.certificate = certificate; }
    }

    private static final class MobilePkcs11Functions extends PKCS11Functions {
        AbstractAkisCommands commandsForSigning() { return commands; }
        String cardProfile() {
            return commands == null ? "bilinmiyor"
                    : commands.getClass().getSimpleName() + "/" + commands.getVersion();
        }
        private final java.util.Map<String, byte[]> certificateFiles = new java.util.HashMap<>();
        byte[] fileForCertificate(byte[] der) throws SignerException {
            byte[] path = certificateFiles.get(hex(der));
            if (path == null) throw new SignerException("Sertifika dosyasının kart yolu bulunamadı");
            return path.clone();
        }

        @Override public List<byte[]> getSignatureCertificates()
                throws AkisCIFException, AkisCardException, AkisSWException {
            List<byte[]> result = new ArrayList<>();
            serialCertID.clear();
            certificateFiles.clear();
            byte[] fid = new byte[]{0x2F, 0x0F};
            int certificateIndex = 1;
            int consecutiveMissingFiles = 0;
            final CertificateFactory factory;
            try {
                factory = CertificateFactory.getInstance("X.509");
            } catch (java.security.cert.CertificateException e) {
                throw new AkisCIFException(e);
            }

            while (fid[1] != (byte) 0x7F && consecutiveMissingFiles < 16) {
                fid[1]++;
                try {
                    byte[] der = commands.readFileBySelectingUnderActiveDF(fid.clone());
                    if (der == null || der.length == 0) {
                        consecutiveMissingFiles++;
                        continue;
                    }
                    X509Certificate certificate = (X509Certificate) factory.generateCertificate(
                            new ByteArrayInputStream(der));
                    boolean[] usage = certificate.getKeyUsage();
                    boolean signingUsage = usage == null
                            || (usage.length > 0 && usage[0])
                            || (usage.length > 1 && usage[1]);
                    if (signingUsage) {
                        result.add(der.clone());
                        certificateFiles.put(hex(der), fid.clone());
                        String serial = Conversions.hexBytetoHexString(
                                certificate.getSerialNumber().toByteArray());
                        serialCertID.put(serial, Integer.valueOf(certificateIndex));
                    }
                    certificateIndex++;
                    consecutiveMissingFiles = 0;
                } catch (AkisCIFException e) {
                    String message = e.getMessage();
                    String normalized = message == null ? "" : message.toLowerCase(Locale.ROOT);
                    if (!normalized.contains("boş sertifika dosyası")
                            && !normalized.contains("bos sertifika dosyasi")
                            && !normalized.contains("empty certificate file")) throw e;
                    consecutiveMissingFiles++;
                } catch (AkisSWException e) {
                    if (e.getErrorCode() != 0x6A82L) throw e;
                    consecutiveMissingFiles++;
                } catch (java.security.cert.CertificateException e) {
                    throw new AkisCIFException(e);
                }
            }
            return result;
        }
    }

    private static final class AndroidTransmitter implements ICommandTransmitter {
        private final CardTerminal terminal;
        private Card card;
        private CardChannel channel;
        private String failure = "";

        AndroidTransmitter(CardTerminal terminal) throws CardException {
            this.terminal = terminal;
            connect();
        }

        private void connect() throws CardException {
            if (card != null) try { card.disconnect(false); } catch (CardException ignored) { }
            try {
                card = terminal.connect("T=1");
            } catch (CardException t1Failure) {
                try {
                    card = terminal.connect("T=0");
                } catch (CardException t0Failure) {
                    card = terminal.connect("*");
                }
            }
            channel = card.getBasicChannel();
        }

        @Override public synchronized ResponseAPDU transmit(CommandAPDU command) throws AkisCardException {
            try {
                if (channel == null) connect();
                failure = "";
                ResponseAPDU response = channel.transmit(command);
                if (response.getSW() != 0x9000) {
                    int ins = command.getINS();
                    String stage = ins == 0x20 ? "PIN doğrulama" : ins == 0x22 ? "MSE anahtar seçimi"
                            : ins == 0x2A ? "PSO imza" : ins == 0xA4 ? "Dosya/uygulama seçimi"
                            : ins == 0xB0 || ins == 0xB1 ? "Dosya okuma" : "Kart komutu";
                    failure = stage + String.format(Locale.ROOT," INS=%02X P1=%02X P2=%02X SW=%04X",
                            ins, command.getP1(), command.getP2(), response.getSW());
                    DiagnosticLogger.w(DiagnosticLogger.Tag.APDU, failure);
                }
                return response;
            } catch (CardException e) {
                DiagnosticLogger.e(DiagnosticLogger.Tag.APDU, "APDU iletim hatası", e);
                throw new AkisCardException(e);
            }
        }

        @Override public byte[] control(byte[] command) throws AkisCardException {
            throw new AkisCardException(new CardException("USB CCID control transfer is not used by AKIS"));
        }

        @Override public synchronized ATR atr() throws AkisCardException {
            try {
                if (card == null) connect();
                return card.getATR();
            } catch (CardException e) {
                throw new AkisCardException(e);
            }
        }

        @Override public synchronized void reset() throws AkisCardException {
            try { connect(); } catch (CardException e) { throw new AkisCardException(e); }
        }

        @Override public synchronized void reset(String ignored) throws AkisCardException { reset(); }

        @Override public synchronized void closeCardTerminal() {
            if (card != null) try { card.disconnect(false); } catch (CardException ignored) { }
            card = null; channel = null;
        }

        @Override public int getCommandBufferSize() { return 65536; }
    }

    private static String hex(byte[] bytes) {
        if (bytes == null) return "";
        StringBuilder out = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) out.append(String.format(Locale.ROOT, "%02X", b & 0xff));
        return out.toString();
    }

    private static String describeCause(Throwable error) {
        Throwable cause = error;
        while (cause.getCause() != null && cause.getCause() != cause) cause = cause.getCause();
        String message = cause.getMessage();
        if (message == null || message.trim().isEmpty()) message = cause.getClass().getSimpleName();
        message = message.replaceAll("[\\r\\n\\t]+", " ").trim();
        if (message.length() > 220) message = message.substring(0, 220) + "…";
        return cause.getClass().getSimpleName() + ": " + message;
    }
}
