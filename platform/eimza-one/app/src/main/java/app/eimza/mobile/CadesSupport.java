package app.eimza.mobile;

import java.security.cert.X509Certificate;
import java.security.spec.AlgorithmParameterSpec;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.math.BigInteger;
import java.net.HttpURLConnection;
import java.net.URL;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.Map;

import org.bouncycastle.asn1.ASN1EncodableVector;
import org.bouncycastle.asn1.DERSet;
import org.bouncycastle.asn1.cms.Attribute;
import org.bouncycastle.asn1.cms.AttributeTable;
import org.bouncycastle.asn1.nist.NISTObjectIdentifiers;
import org.bouncycastle.asn1.pkcs.PKCSObjectIdentifiers;
import org.bouncycastle.cms.CMSSignedData;
import org.bouncycastle.cms.SignerInformation;
import org.bouncycastle.cms.SignerInformationStore;
import org.bouncycastle.tsp.TimeStampRequest;
import org.bouncycastle.tsp.TimeStampRequestGenerator;
import org.bouncycastle.tsp.TimeStampResponse;
import org.bouncycastle.tsp.TimeStampToken;
import tr.gov.tubitak.uekae.esya.api.crypto.alg.DigestAlg;
import tr.gov.tubitak.uekae.esya.api.infra.tsclient.TSClient;
import tr.gov.tubitak.uekae.esya.api.infra.tsclient.TSSettings;

import tr.gov.tubitak.uekae.esya.api.asn.x509.ECertificate;
import tr.gov.tubitak.uekae.esya.api.cmssignature.SignableByteArray;
import tr.gov.tubitak.uekae.esya.api.cmssignature.attribute.EParameters;
import tr.gov.tubitak.uekae.esya.api.cmssignature.signature.BaseSignedData;
import tr.gov.tubitak.uekae.esya.api.cmssignature.signature.ESignatureType;
import tr.gov.tubitak.uekae.esya.api.common.ESYAException;
import tr.gov.tubitak.uekae.esya.api.common.crypto.Algorithms;
import tr.gov.tubitak.uekae.esya.api.common.crypto.BaseSigner;

/** CAdES-BES using the same ESYA call sequence as Adalet's supplied desktop client. */
final class CadesSupport {
    private CadesSupport() { }

    static byte[] sign(byte[] content, String certificateId, X509Certificate certificate,
                       char[] pin, SignerBackend backend, boolean attached) throws Exception {
        if (content == null || content.length == 0) throw new IllegalArgumentException("İmzalanacak içerik boş");
        BaseSignedData signedData = new BaseSignedData();
        signedData.addContent(new SignableByteArray(content), attached);
        ECertificate esyaCertificate = new ECertificate(certificate.getEncoded());
        BaseSigner signer = new BaseSigner() {
            @Override public byte[] sign(byte[] bytes) throws ESYAException {
                try { return backend.sign(bytes, certificateId, pin); }
                catch (SignerBackend.SignerException e) {
                    throw new ESYAException("AKİS kart imzası başarısız", e);
                }
            }
            @Override public String getSignatureAlgorithmStr() {
                String algorithm = certificate.getPublicKey() == null ? "" :
                        certificate.getPublicKey().getAlgorithm();
                return "EC".equalsIgnoreCase(algorithm) || "ECDSA".equalsIgnoreCase(algorithm)
                        ? Algorithms.SIGNATURE_ECDSA_SHA256
                        : Algorithms.SIGNATURE_RSA_SHA256;
            }
            @Override public AlgorithmParameterSpec getAlgorithmParameterSpec() { return null; }
        };
        Map<String, Object> parameters = new HashMap<>();
        parameters.put(EParameters.P_VALIDATE_CERTIFICATE_BEFORE_SIGNING, Boolean.FALSE);
        signedData.addSigner(ESignatureType.TYPE_BES, esyaCertificate, signer, null, parameters);
        return signedData.getEncoded();
    }

    /** Upgrade a BES CMS signature to CAdES-T using an RFC 3161 TSA. */
    static byte[] addTimestamp(byte[] cmsBytes, String tsaUrl, String username, char[] password) throws Exception {
        if (tsaUrl == null) throw new IllegalArgumentException("CAdES-T için TSA adresi gerekli");
        URL endpoint = new URL(tsaUrl.trim());
        boolean kamuSm = "zd.kamusm.gov.tr".equalsIgnoreCase(endpoint.getHost());
        if (!("https".equalsIgnoreCase(endpoint.getProtocol())
                || (kamuSm && "http".equalsIgnoreCase(endpoint.getProtocol()))))
            throw new IllegalArgumentException("Yalnız HTTPS TSA veya resmî KamuSM HTTP servisi kullanılabilir");
        CMSSignedData cms = new CMSSignedData(cmsBytes);
        Collection<SignerInformation> updated = new ArrayList<>();
        for (SignerInformation signer : cms.getSignerInfos().getSigners()) {
            byte[] imprint = MessageDigest.getInstance("SHA-256").digest(signer.getSignature());
            TimeStampToken token;
            if (kamuSm) {
                if (username == null || username.trim().isEmpty() || password == null || password.length == 0)
                    throw new IllegalArgumentException("KamuSM müşteri numarası ve parolası gerekli");
                final int customerId;
                try { customerId = Integer.parseInt(username.trim()); }
                catch (NumberFormatException e) { throw new IllegalArgumentException("KamuSM müşteri numarası sayısal olmalı"); }
                TSSettings settings = new TSSettings(tsaUrl.trim(), customerId, password, DigestAlg.SHA256);
                tr.gov.tubitak.uekae.esya.api.asn.pkixtsp.ETimeStampResponse response =
                        new TSClient().timestamp(imprint, settings);
                token = new TimeStampToken(new CMSSignedData(response.getContentInfo().getEncoded()));
            } else {
                TimeStampRequestGenerator generator = new TimeStampRequestGenerator();
                generator.setCertReq(true);
                TimeStampRequest request = generator.generate(NISTObjectIdentifiers.id_sha256,
                        imprint, new BigInteger(128, new SecureRandom()));
                byte[] responseBytes = requestTimestamp(tsaUrl.trim(), request.getEncoded(), username, password);
                TimeStampResponse response = new TimeStampResponse(responseBytes);
                response.validate(request);
                token = response.getTimeStampToken();
            }
            if (token == null) throw new IllegalStateException("TSA geçerli zaman damgası döndürmedi");

            ASN1EncodableVector attributes = signer.getUnsignedAttributes() == null
                    ? new ASN1EncodableVector()
                    : signer.getUnsignedAttributes().toASN1EncodableVector();
            attributes.add(new Attribute(PKCSObjectIdentifiers.id_aa_signatureTimeStampToken,
                    new DERSet(token.toCMSSignedData().toASN1Structure())));
            updated.add(SignerInformation.replaceUnsignedAttributes(signer, new AttributeTable(attributes)));
        }
        return CMSSignedData.replaceSigners(cms, new SignerInformationStore(updated)).getEncoded();
    }

    private static byte[] requestTimestamp(String tsaUrl, byte[] request,
                                           String username, char[] password) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(tsaUrl).openConnection();
        connection.setRequestMethod("POST");
        connection.setConnectTimeout(15000);
        connection.setReadTimeout(30000);
        connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type", "application/timestamp-query");
        connection.setRequestProperty("Accept", "application/timestamp-reply");
        if (username != null && !username.isEmpty()) {
            String credentials = username + ":" + (password == null ? "" : new String(password));
            String encoded = java.util.Base64.getEncoder().encodeToString(
                    credentials.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            connection.setRequestProperty("Authorization", "Basic " + encoded);
        }
        connection.getOutputStream().write(request);
        int status = connection.getResponseCode();
        InputStream input = status >= 200 && status < 300
                ? connection.getInputStream() : connection.getErrorStream();
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[4096]; int count;
        while (input != null && (count = input.read(buffer)) >= 0) output.write(buffer, 0, count);
        connection.disconnect();
        String responseType = connection.getContentType();
        if (status == 401 || status == 403)
            throw new java.io.IOException("TSA kimlik doğrulaması reddedildi (HTTP " + status + ")");
        if (status == 405)
            throw new java.io.IOException("TSA HTTP 405: Bu adres RFC 3161 endpoint'i değil; sağlayıcının tam TSA servis yolunu girin");
        if (status < 200 || status >= 300) throw new java.io.IOException("TSA HTTP " + status);
        if (responseType != null && !responseType.toLowerCase(java.util.Locale.ROOT)
                .contains("application/timestamp-reply"))
            throw new java.io.IOException("TSA geçersiz içerik türü döndürdü: " + responseType);
        return output.toByteArray();
    }
}
