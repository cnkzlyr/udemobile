package app.eimza.mobile;

import java.security.MessageDigest;
import java.security.cert.X509Certificate;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;

import org.bouncycastle.asn1.ASN1Encodable;
import org.bouncycastle.asn1.ASN1EncodableVector;
import org.bouncycastle.asn1.ASN1Integer;
import org.bouncycastle.asn1.ASN1ObjectIdentifier;
import org.bouncycastle.asn1.ASN1Primitive;
import org.bouncycastle.asn1.DERNull;
import org.bouncycastle.asn1.DEROctetString;
import org.bouncycastle.asn1.DERSequence;
import org.bouncycastle.asn1.DERSet;
import org.bouncycastle.asn1.DERTaggedObject;
import org.bouncycastle.asn1.cms.Attribute;
import org.bouncycastle.asn1.cms.CMSAttributes;
import org.bouncycastle.asn1.ess.ESSCertID;
import org.bouncycastle.asn1.ess.ESSCertIDv2;
import org.bouncycastle.asn1.ess.SigningCertificate;
import org.bouncycastle.asn1.ess.SigningCertificateV2;
import org.bouncycastle.asn1.nist.NISTObjectIdentifiers;
import org.bouncycastle.asn1.oiw.OIWObjectIdentifiers;
import org.bouncycastle.asn1.pkcs.PKCSObjectIdentifiers;
import org.bouncycastle.asn1.x500.X500Name;
import org.bouncycastle.asn1.x509.AlgorithmIdentifier;
import org.bouncycastle.asn1.x509.DigestInfo;
import org.bouncycastle.asn1.x509.IssuerSerial;
import org.bouncycastle.cms.CMSSignedData;
import org.bouncycastle.cms.SignerInformation;

/** Byte-for-byte CMS profile emitted by the official e-Devlet desktop signer. */
final class EdevletCmsSupport {
    private static final ASN1ObjectIdentifier ECDSA_SHA256 =
            new ASN1ObjectIdentifier("1.2.840.10045.4.3.2");
    private static final ASN1ObjectIdentifier ECDSA_SHA384 =
            new ASN1ObjectIdentifier("1.2.840.10045.4.3.3");
    private static final ASN1ObjectIdentifier ECDSA_SHA512 =
            new ASN1ObjectIdentifier("1.2.840.10045.4.3.4");

    private EdevletCmsSupport() { }

    static byte[] sign(byte[] content, String certificateId, X509Certificate certificate,
                       char[] pin, SignerBackend backend) throws Exception {
        if (content == null || content.length == 0)
            throw new IllegalArgumentException("e-Devlet imzalanacak içerik boş");

        boolean ec = isEc(certificate);
        String digestName = selectOfficialDigest(certificate, ec);
        ASN1ObjectIdentifier digestOid = digestOid(digestName);
        AlgorithmIdentifier digestAlgorithm = new AlgorithmIdentifier(digestOid);

        DERSet signedAttributes = signedAttributes(content, certificate, digestName);
        byte[] signature;
        if (ec) {
            // The AKIS ECC mechanism hashes this DER SET internally. This matches
            // the official signer's CKM_ECDSA input for its SHA-256 EC profile.
            if (!"SHA-256".equals(digestName))
                throw new SignerBackend.SignerException(
                        "Bu EC sertifikasının e-Devlet " + digestName + " profili kart yolunda desteklenmiyor");
            signature = backend.sign(signedAttributes.getEncoded("DER"), certificateId, pin);
        } else {
            // Official signer uses CKM_RSA_PKCS (not SHA256withRSA): it hashes the
            // authenticated attributes, wraps the digest in DigestInfo, and asks
            // the card to apply PKCS#1 v1.5 padding only.
            byte[] attributesDigest = MessageDigest.getInstance(digestName)
                    .digest(signedAttributes.getEncoded("DER"));
            byte[] digestInfo = new DigestInfo(
                    new AlgorithmIdentifier(digestOid, DERNull.INSTANCE), attributesDigest)
                    .getEncoded("DER");
            signature = backend.signRawPkcs1(digestInfo, certificateId, pin);
        }

        byte[] encoded = encodeCms(content, certificate, digestAlgorithm,
                signedAttributes, signature, signatureAlgorithm(ec, digestName));
        verifyLocally(encoded, content, certificate);
        return encoded;
    }

    private static DERSet signedAttributes(byte[] content, X509Certificate certificate,
                                            String digestName) throws Exception {
        List<ASN1Encodable> attributes = new ArrayList<>();
        attributes.add(new Attribute(CMSAttributes.contentType,
                new DERSet(PKCSObjectIdentifiers.data)));
        attributes.add(new Attribute(CMSAttributes.messageDigest,
                new DERSet(new DEROctetString(
                        MessageDigest.getInstance(digestName).digest(content)))));

        // The official helper hashes the certificate with SHA-1 only for the
        // legacy profile and SHA-256 for every SigningCertificateV2 profile.
        byte[] certificateHash = MessageDigest.getInstance(
                "SHA-1".equals(digestName) ? "SHA-1" : "SHA-256")
                .digest(certificate.getEncoded());
        IssuerSerial issuerSerial = new IssuerSerial(
                X500Name.getInstance(certificate.getIssuerX500Principal().getEncoded()),
                certificate.getSerialNumber());
        if ("SHA-1".equals(digestName)) {
            SigningCertificate value = new SigningCertificate(
                    new ESSCertID(certificateHash, issuerSerial));
            attributes.add(new Attribute(PKCSObjectIdentifiers.id_aa_signingCertificate,
                    new DERSet(value)));
        } else {
            SigningCertificateV2 value = new SigningCertificateV2(
                    new ESSCertIDv2(certificateHash, issuerSerial));
            attributes.add(new Attribute(PKCSObjectIdentifiers.id_aa_signingCertificateV2,
                    new DERSet(value)));
        }
        attributes.add(new Attribute(CMSAttributes.signingTime,
                new DERSet(new org.bouncycastle.asn1.DERUTCTime(new Date()))));
        return new DERSet(attributes.toArray(new ASN1Encodable[0]));
    }

    private static byte[] encodeCms(byte[] content, X509Certificate certificate,
                                    AlgorithmIdentifier digestAlgorithm,
                                    DERSet signedAttributes, byte[] signature,
                                    AlgorithmIdentifier signatureAlgorithm) throws Exception {
        X500Name issuer = X500Name.getInstance(
                certificate.getIssuerX500Principal().getEncoded());

        ASN1EncodableVector issuerAndSerial = new ASN1EncodableVector();
        issuerAndSerial.add(issuer);
        issuerAndSerial.add(new ASN1Integer(certificate.getSerialNumber()));

        ASN1EncodableVector signerInfo = new ASN1EncodableVector();
        signerInfo.add(new ASN1Integer(1));
        signerInfo.add(new DERSequence(issuerAndSerial));
        signerInfo.add(digestAlgorithm);
        signerInfo.add(new DERTaggedObject(false, 0, signedAttributes));
        signerInfo.add(signatureAlgorithm);
        signerInfo.add(new DEROctetString(signature));

        ASN1EncodableVector encapsulated = new ASN1EncodableVector();
        encapsulated.add(PKCSObjectIdentifiers.data);
        encapsulated.add(new DERTaggedObject(true, 0, new DEROctetString(content)));

        ASN1Primitive certificateAsn1 = ASN1Primitive.fromByteArray(certificate.getEncoded());
        ASN1EncodableVector signedData = new ASN1EncodableVector();
        signedData.add(new ASN1Integer(1));
        signedData.add(new DERSet(digestAlgorithm));
        signedData.add(new DERSequence(encapsulated));
        signedData.add(new DERTaggedObject(false, 0, new DERSet(certificateAsn1)));
        signedData.add(new DERSet(new DERSequence(signerInfo)));

        ASN1EncodableVector outer = new ASN1EncodableVector();
        outer.add(PKCSObjectIdentifiers.signedData);
        outer.add(new DERTaggedObject(true, 0, new DERSequence(signedData)));
        return new DERSequence(outer).getEncoded("DER");
    }

    private static AlgorithmIdentifier signatureAlgorithm(boolean ec, String digestName) {
        ASN1ObjectIdentifier oid;
        if (!ec) oid = PKCSObjectIdentifiers.rsaEncryption;
        else if ("SHA-384".equals(digestName)) oid = ECDSA_SHA384;
        else if ("SHA-512".equals(digestName)) oid = ECDSA_SHA512;
        else oid = ECDSA_SHA256;
        // The official e-Devlet encoder includes DER NULL for both RSA and EC.
        return new AlgorithmIdentifier(oid, DERNull.INSTANCE);
    }

    private static ASN1ObjectIdentifier digestOid(String digestName) {
        if ("SHA-1".equals(digestName)) return OIWObjectIdentifiers.idSHA1;
        if ("SHA-384".equals(digestName)) return NISTObjectIdentifiers.id_sha384;
        if ("SHA-512".equals(digestName)) return NISTObjectIdentifiers.id_sha512;
        return NISTObjectIdentifiers.id_sha256;
    }

    private static boolean isEc(X509Certificate certificate) {
        String algorithm = certificate.getPublicKey().getAlgorithm();
        return "EC".equalsIgnoreCase(algorithm) || "ECDSA".equalsIgnoreCase(algorithm);
    }

    private static String selectOfficialDigest(X509Certificate certificate, boolean ec) {
        if (!ec) {
            if (certificate.getPublicKey() instanceof java.security.interfaces.RSAKey
                    && ((java.security.interfaces.RSAKey) certificate.getPublicKey())
                    .getModulus().bitLength() != 2048)
                return "SHA-1";
            return "SHA-256";
        }
        String issuerSignature = certificate.getSigAlgName()
                .toUpperCase(java.util.Locale.ROOT);
        if (issuerSignature.contains("SHA384")) return "SHA-384";
        if (issuerSignature.contains("SHA512")) return "SHA-512";
        return "SHA-256";
    }

    /** Refuse to transmit a CMS whose embedded bytes or signature disagree locally. */
    private static void verifyLocally(byte[] encoded, byte[] content,
                                      X509Certificate certificate) throws Exception {
        CMSSignedData parsed = new CMSSignedData(encoded);
        Object embedded = parsed.getSignedContent() == null
                ? null : parsed.getSignedContent().getContent();
        if (!(embedded instanceof byte[]) || !java.util.Arrays.equals(content, (byte[]) embedded))
            throw new IllegalStateException("e-Devlet CMS gömülü içeriği değişti");
        java.util.Collection<?> rows = parsed.getSignerInfos().getSigners();
        if (rows.size() != 1)
            throw new IllegalStateException("e-Devlet CMS imzacı sayısı geçersiz");
        SignerInformation signer = (SignerInformation) rows.iterator().next();
        if (!signer.verify(new org.bouncycastle.cms.jcajce.JcaSimpleSignerInfoVerifierBuilder()
                .build(certificate)))
            throw new IllegalStateException("e-Devlet CMS imzası yerelde doğrulanmadı");
    }
}
