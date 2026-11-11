#!/usr/bin/env python3
"""
CanEditor masaüstü e-imza ajanı (eimza-win-agent.jar) derler.

Ajan, gömülü Java ile çalışan resmi Adalet E-İmza'nın javax.smartcardio sağlayıcısını "UnicodePCSC" ile değiştirir:
JDK'nın sağlayıcısı Windows'ta okuyucu adlarını ANSI→UTF-8 yanlış çevirir; adında Türkçe karakter olan okuyucular
(ArkSigner: "Microsoft Usbccid Akıllı Kart Okuyucusu (WUDF) 0") açılamaz. Kaynak: src-tauri/eimza-agent/src.
JNA (Apache-2.0) Maven Central'dan sabit SHA-256 ile indirilip jar'ın içine konur (yalnızca gerekli yerel dosyalar).

Çıktı: src-tauri/eimza/eimza-win-agent.jar   (Kullanım: python3 scripts/win_ajan_derle.py)
"""
import glob
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KAYNAK = os.path.join(KOK, "src-tauri", "eimza-agent", "src")
CIKTI = os.path.join(KOK, "src-tauri", "eimza", "eimza-win-agent.jar")
JNA_URL = "https://repo1.maven.org/maven2/net/java/dev/jna/jna/5.14.0/jna-5.14.0.jar"
JNA_SHA256 = "34ed1e1f27fa896bca50dbc4e99cf3732967cec387a7a0d5e3486c09673fe8c6"
YEREL = ("com/sun/jna/win32-x86-64/", "com/sun/jna/win32-aarch64/", "com/sun/jna/linux-x86-64/",
         "com/sun/jna/linux-aarch64/", "com/sun/jna/darwin-")


def arac(ad):
    jh = os.environ.get("JAVA_HOME")
    if jh:
        for uzanti in ("", ".exe"):
            p = os.path.join(jh, "bin", ad + uzanti)
            if os.path.exists(p):
                return p
    return ad


def main():
    on = os.path.join(KOK, "build", "onbellek")
    os.makedirs(on, exist_ok=True)
    jna = os.path.join(on, "jna-5.14.0.jar")
    if not os.path.exists(jna) or hashlib.sha256(open(jna, "rb").read()).hexdigest() != JNA_SHA256:
        istek = urllib.request.Request(JNA_URL, headers={"User-Agent": "curl/8"})
        with urllib.request.urlopen(istek, timeout=120) as r, open(jna + ".tmp", "wb") as f:
            shutil.copyfileobj(r, f)
        os.replace(jna + ".tmp", jna)
    if hashlib.sha256(open(jna, "rb").read()).hexdigest() != JNA_SHA256:
        sys.exit("JNA SHA256 uyuşmuyor")
    with tempfile.TemporaryDirectory() as tmp:
        siniflar = os.path.join(tmp, "c")
        os.makedirs(siniflar)
        kaynaklar = sorted(glob.glob(os.path.join(KAYNAK, "**", "*.java"), recursive=True))
        subprocess.run([arac("javac"), "--release", "17", "-encoding", "UTF-8", "-nowarn", "-cp", jna, "-d", siniflar]
                       + kaynaklar, check=True)
        os.makedirs(os.path.dirname(CIKTI), exist_ok=True)
        manifest = ("Manifest-Version: 1.0\nPremain-Class: eimzawin.Agent\nCan-Redefine-Classes: false\n"
                    "Implementation-Title: CanEditor Unicode PC/SC\nImplementation-Vendor: CanEditor\n\n")
        with zipfile.ZipFile(CIKTI + ".tmp", "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("META-INF/MANIFEST.MF", manifest)
            for kokd, _, dosyalar in os.walk(siniflar):
                for d in sorted(dosyalar):
                    tam = os.path.join(kokd, d)
                    z.write(tam, os.path.relpath(tam, siniflar).replace(os.sep, "/"))
            with zipfile.ZipFile(jna) as j:
                for ad in j.namelist():
                    if ad.endswith("/"):
                        continue
                    sinif = ad.startswith("com/sun/jna/") and ad.endswith(".class") and ad.count("/") <= 4
                    yerel = any(ad.startswith(y) for y in YEREL)
                    if sinif or yerel:
                        z.writestr(ad, j.read(ad))
                    elif ad == "META-INF/LICENSE":
                        z.writestr("META-INF/JNA-LICENSE", j.read(ad))
                for lis in ("META-INF/AL2.0", "META-INF/LGPL2.1"):
                    if lis in j.namelist():
                        z.writestr(lis.replace("META-INF/", "META-INF/JNA-"), j.read(lis))
        os.replace(CIKTI + ".tmp", CIKTI)
    print("eimza-win-agent.jar:", os.path.getsize(CIKTI), "bayt ->", CIKTI)


if __name__ == "__main__":
    main()
