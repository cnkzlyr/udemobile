package app.eimza.mobile;
import java.security.*;
import java.security.cert.X509Certificate;
import java.util.*;
import java.math.BigInteger;
import org.bouncycastle.asn1.x500.X500Name;
import org.bouncycastle.cert.jcajce.*;
import org.bouncycastle.operator.jcajce.*;
import org.bouncycastle.cms.*;
import org.bouncycastle.cms.jcajce.*;
public class SigningHarness {
 public static void main(String[] args) throws Exception {
  try(java.io.InputStream encrypted=new java.io.FileInputStream("app/src/main/assets/tubitak/lisans.xml.enc");
      java.io.InputStream in=AdaletEsyaConfig.decrypt(encrypted)){
   tr.gov.tubitak.uekae.esya.api.common.util.LicenseUtil.setLicenseXml(in);
  }
  Security.addProvider(new org.bouncycastle.jce.provider.BouncyCastleProvider());
  KeyPairGenerator gen=KeyPairGenerator.getInstance("RSA");gen.initialize(2048);KeyPair pair=gen.generateKeyPair();
  X500Name name=new X500Name("CN=Test only");
  X509Certificate cert=new JcaX509CertificateConverter().setProvider("BC").getCertificate(new JcaX509v3CertificateBuilder(name,BigInteger.ONE,new Date(System.currentTimeMillis()-1000),new Date(System.currentTimeMillis()+3600000),name,pair.getPublic()).build(new JcaContentSignerBuilder("SHA256withRSA").build(pair.getPrivate())));
  SignerBackend backend=new SignerBackend(){
   public String id(){return "test";}public String displayName(){return "test";}public State state(){return State.READY;}public List<CertificateSummary> certificates(){return Collections.emptyList();}public void close(){}
   public byte[] sign(byte[] payload,String id,char[] pin)throws SignerException{try{Signature sig=Signature.getInstance("SHA256withRSA");sig.initSign(pair.getPrivate());sig.update(payload);return sig.sign();}catch(Exception e){throw new SignerException("test",e);}}
   public byte[] signRawPkcs1(byte[] payload,String id,char[] pin)throws SignerException{try{Signature sig=Signature.getInstance("NONEwithRSA");sig.initSign(pair.getPrivate());sig.update(payload);return sig.sign();}catch(Exception e){throw new SignerException("test raw",e);}}
  };
  byte[] content="Literal UTF-8 içerik; Zm9v is not decoded".getBytes(java.nio.charset.StandardCharsets.UTF_8);
  Signature raw=Signature.getInstance("NONEwithRSA");raw.initSign(pair.getPrivate());raw.update(RsaDigestInfo.sha256(content));byte[] onCard=raw.sign();
  Signature verify=Signature.getInstance("SHA256withRSA");verify.initVerify(pair.getPublic());verify.update(content);if(!verify.verify(onCard))throw new AssertionError("DigestInfo padding contract");
  for(boolean attached:new boolean[]{false,true}){
   byte[] encoded=CadesSupport.sign(content,"test",cert,new char[0],backend,attached);
   CMSSignedData cms=attached?new CMSSignedData(encoded):new CMSSignedData(new CMSProcessableByteArray(content),encoded);
   SignerInformation info=cms.getSignerInfos().getSigners().iterator().next();
   if(!info.verify(new JcaSimpleSignerInfoVerifierBuilder().setProvider("BC").build(cert)))throw new AssertionError("CMS signature");
   if((new CMSSignedData(encoded).getSignedContent()!=null)!=attached)throw new AssertionError("encapsulation");
   if(!attached){byte[] wrong=content.clone();wrong[0]^=1;try{SignerInformation bad=new CMSSignedData(new CMSProcessableByteArray(wrong),encoded).getSignerInfos().getSigners().iterator().next();if(bad.verify(new JcaSimpleSignerInfoVerifierBuilder().setProvider("BC").build(cert)))throw new AssertionError("tampered content accepted");}catch(CMSException expected){}}
  }
  byte[] edevlet=EdevletCmsSupport.sign(content,"test",cert,new char[0],backend);
  CMSSignedData edevletCms=new CMSSignedData(edevlet);
  if(edevletCms.getSignedContent()==null)throw new AssertionError("e-Devlet content must be embedded");
  SignerInformation edevletSigner=edevletCms.getSignerInfos().getSigners().iterator().next();
  if(!edevletSigner.verify(new JcaSimpleSignerInfoVerifierBuilder().setProvider("BC").build(cert)))
   throw new AssertionError("e-Devlet CMS signature");
  if(edevletSigner.getSignedAttributes().get(org.bouncycastle.asn1.pkcs.PKCSObjectIdentifiers.id_aa_signingCertificateV2)==null)
   throw new AssertionError("e-Devlet SigningCertificateV2 missing");
  if(edevletSigner.getSignedAttributes().get(org.bouncycastle.asn1.cms.CMSAttributes.signingTime)==null)
   throw new AssertionError("e-Devlet signingTime missing");
  if(!org.bouncycastle.asn1.pkcs.PKCSObjectIdentifiers.rsaEncryption.getId().equals(
      edevletSigner.getEncryptionAlgOID()))
   throw new AssertionError("e-Devlet must use official rsaEncryption SignerInfo algorithm");
  // Android's preinstalled provider uses the BC name but lacks bundled CMS algorithms.
  // Generation must use the bundled provider object without replacing the OS provider.
  Provider original=Security.getProvider("BC");Security.removeProvider("BC");
  Provider reduced=new Provider("BC",1.0,"Android provider-name collision simulation"){};
  Security.addProvider(reduced);
  try {
   byte[] encoded=CadesSupport.sign(content,"test",cert,new char[0],backend,false);
   if(Security.getProvider("BC")!=reduced)throw new AssertionError("OS provider changed");
   CMSSignedData cms=new CMSSignedData(new CMSProcessableByteArray(content),encoded);
   if(!cms.getSignerInfos().getSigners().iterator().next().verify(new JcaSimpleSignerInfoVerifierBuilder().setProvider(original).build(cert)))throw new AssertionError("BC name collision signature");
  } finally {Security.removeProvider("BC");Security.addProvider(original);}
  System.err.println("PASS: CMS generation with preinstalled reduced BC provider");
  String nonce=ArkBootstrap.nonce();System.out.println(nonce);System.out.println(ArkBootstrap.cypher("bootstrap-test",nonce));
  System.err.println("PASS: attached/detached CAdES RSA verification; tampered content rejected");
 }
}
