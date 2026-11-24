package app.eimza.mobile;
import java.util.*;
import java.io.*;
import javax.smartcardio.*;
import tubitak.akis.cif.commands.*;
import tubitak.akis.cif.functions.*;
import tubitak.akis.cif.dataStructures.*;
import tubitak.akis.cif.akisExceptions.*;
import org.bouncycastle.asn1.*;
public class AkisV25Harness {
 static byte[] cert(int id,int file)throws Exception {
  return new DERSequence(new ASN1Encodable[]{new DERSequence(),new DERSequence(new DEROctetString(new byte[]{(byte)id})),new DERTaggedObject(true,1,new DERSequence(new DERSequence(new DEROctetString(new byte[]{0x3F,0,0x3D,1,0x2F,(byte)file}))))}).getEncoded();
 }
 static byte[] key(int id,int ref)throws Exception {
  return new DERSequence(new ASN1Encodable[]{new DERSequence(),new DERSequence(new ASN1Encodable[]{new DEROctetString(new byte[]{(byte)id}),new DERBitString(new byte[]{0x20}),new ASN1Integer(ref)}),new DERTaggedObject(true,1,new DERSequence(new ASN1Integer(2048)))}).getEncoded();
 }
 static byte[] join(byte[]...chunks)throws Exception{ByteArrayOutputStream out=new ByteArrayOutputStream();for(byte[] b:chunks)out.write(b);return out.toByteArray();}
 public static void main(String[] args)throws Exception {
  byte[] cdf=join(cert(7,0x10),cert(9,0x12),new byte[]{0,(byte)255});
  byte[] prkdf=join(key(9,5),key(7,3));
  if(AkisPkcs15.keyReference(cdf,prkdf,new byte[]{0x2F,0x10})!=3)throw new AssertionError("certificate/key association");
  if(AkisPkcs15.keyReference(cdf,prkdf,new byte[]{0x2F,0x12})!=5)throw new AssertionError("multiple keys");
  try{AkisPkcs15.keyReference(cdf,prkdf,new byte[]{0x2F,0x14});throw new AssertionError("key guessed");}catch(IOException expected){}
  try{AkisPkcs15.keyReference(new byte[]{0x30,0x10,0},prkdf,new byte[]{0x2F,0x10});throw new AssertionError("truncated DER accepted");}catch(IOException expected){}
  List<byte[]> sent=new ArrayList<>();
  boolean[] signingDf={false};
  boolean[] authenticated={false};
  boolean[] rejectLegacyMse={false}, selectedKey={false}, rejectPso={false};
  ICommandTransmitter fake=new ICommandTransmitter(){
   public ResponseAPDU transmit(CommandAPDU c){
    sent.add(c.getBytes());
    if(c.getINS()==0xA4 && c.getP1()==4) signingDf[0]=true;
    if(c.getINS()==0x20 && !signingDf[0])return new ResponseAPDU(new byte[]{0x69,(byte)0x82});
    if(c.getINS()==0x20)authenticated[0]=true;
    if(c.getINS()==0x22 && c.getP1()==0xC3){
     if(rejectLegacyMse[0])return new ResponseAPDU(new byte[]{0x6A,(byte)0x86});
     selectedKey[0]=(c.getBytes()[4]&255)==3;
    }
    if(c.getINS()==0x22 && c.getP1()==0x41){byte[] data=c.getData();selectedKey[0]=data.length==6 && (data[2]&255)==0x92 && (data[5]&255)==0x83;}
    if(c.getINS()==0x2A && (!selectedKey[0] || rejectPso[0]))return new ResponseAPDU(new byte[]{0x6A,(byte)0x88});
    return new ResponseAPDU(new byte[]{(byte)0x90,0});
   }
   public byte[] control(byte[] b){return new byte[0];}public ATR atr(){return new ATR(new byte[]{0x3B,0});}
   public void closeCardTerminal(){}public int getCommandBufferSize(){return 65536;}public void reset(){}public void reset(String ignored){}
  };
  CommandsV25 commands=new CommandsV25(fake,Version.V25_UEKAE_NXP){
   @Override public byte[] readFileBySelectingUnderActiveDF(byte[] file) throws AkisCIFException {
    if(!authenticated[0])throw new AkisCIFException("Protected directory read before PIN");
    return file[1]==4?cdf:prkdf;
   }
  };
  try{commands.verify(new byte[]{1},false);throw new AssertionError("legacy API unexpectedly supported");}catch(UnsupportedVersionException expected){}
  try{commands.verify((byte)1,new byte[]{'1','2','3','4'},false);throw new AssertionError("EF context accepted");}catch(AkisSWException expected){if(expected.getErrorCode()!=0x6982)throw expected;}
  if(AkisV25Signing.prepare(commands,new char[]{'1','2','3','4'},new byte[]{0x2F,0x10})!=3)throw new AssertionError("production key selection");
  byte[] verify=sent.get(sent.size()-1);
  if(verify[1]!=0x20 || (verify[3]&255)!=0x81)throw new AssertionError("wrong V25 PIN reference");
  try{commands.sign(Algorithm.PKCS_1_5,Algorithm.SHA_256,(byte)3,new byte[]{1,2,3});throw new AssertionError("CIF plain-index/82 accepted");}catch(AkisSWException expected){if(expected.getErrorCode()!=0x6A88)throw expected;}
  AkisV25Signing.sign(commands,(byte)3,new byte[]{1,2,3});
  rejectLegacyMse[0]=true;
  AkisV25Signing.sign(commands,(byte)3,new byte[]{1,2,3});
  rejectPso[0]=true;
  int psoBefore=0;for(byte[] c:sent)if(c[1]==0x2A)psoBefore++;
  try{AkisV25Signing.sign(commands,(byte)3,new byte[]{1,2,3});throw new AssertionError("PSO failure ignored");}catch(AkisSWException expected){if(expected.getErrorCode()!=0x6A88)throw expected;}
  int psoAfter=0;for(byte[] c:sent)if(c[1]==0x2A)psoAfter++;
  if(psoAfter!=psoBefore+1)throw new AssertionError("PSO retried");
  boolean mse=false,pso=false;for(byte[] c:sent){if(c[1]==0x22)mse=true;if(c[1]==0x2A)pso=true;}
  if(!mse||!pso)throw new AssertionError("V25 signing command missing");
  authenticated[0]=false; signingDf[0]=false; selectedKey[0]=false; rejectLegacyMse[0]=false; rejectPso[0]=false;
  CommandsV20 commands20=new CommandsV20(fake,Version.V22_UEKAE_NXP){
   @Override public byte[] readFileBySelectingUnderActiveDF(byte[] file) throws AkisCIFException {
    if(!authenticated[0])throw new AkisCIFException("Protected directory read before PIN");
    return file[1]==4?cdf:prkdf;
   }
  };
  if(AkisV25Signing.prepare(commands20,new char[]{'1','2','3','4'},new byte[]{0x2F,0x10})!=3)throw new AssertionError("V20 key selection");
  AkisV25Signing.sign(commands20,(byte)3,new byte[]{1,2,3});
  System.out.println("PASS: V20/V25 PIN and PKCS#15 metadata; native legacy MSE and 92/local-key fallback; failed PSO never retried");
 }
}
