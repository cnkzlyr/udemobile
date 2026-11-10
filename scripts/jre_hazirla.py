#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UdeMobile (Android) için gömülü Java 21 + Adalet E-İmza yardımcılarını hazırlar.

Çıktılar (build/eimza/, git'e girmez):
  jre-arm64.zip     Android (aarch64, bionic) Java 21: Termux openjdk-21 paketlerinden jlink ile küçültülmüş;
                    yanında gereken yerel kütüphaneler (zlib, freetype, X11 istemci kütüphaneleri, fontconfig...).
  eimza-agent.jar   -javaagent: javax.smartcardio'yu UdeMobile'ın USB CCID köprüsüne bağlar, PIN'i Android
                    penceresinden ister (android/eimza/agent).
  awt-patch.jar     --patch-module java.desktop: X sunucusu olmadan Swing pencereleri Caciocavallo ile bellekte
                    çizilir (resmi Adalet uygulaması açılışta pencere oluşturur; ekransız modda çöker).
  surum.txt         bu dosyaların özeti (uygulama sürüm değişince yeniden açar)

Gerekenler: JDK 21 (jlink, javac, jar). İnternet: packages-cf.termux.dev (paketler SHA256 ile doğrulanır).
Resmi Adalet E-İmza uygulaması APK'ya KONMAZ; telefon, Adalet'in kendi sunucusundan (cdn.uyap.gov.tr) indirir.

Kullanım:  python3 scripts/jre_hazirla.py [--yeniden]
"""
import glob
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CIKTI = os.path.join(KOK, "build", "eimza")
ON = os.path.join(CIKTI, "_on")          # indirilen paketler (önbellek)
DEPO = os.environ.get("TERMUX_DEPO", "https://packages-cf.termux.dev/apt/termux-main")
PREFIX = "data/data/com.termux/files/usr"

PAKETLER = [
    "openjdk-21", "openjdk-21-x", "libandroid-shmem", "libandroid-spawn", "libandroid-support", "libiconv",
    "libjpeg-turbo", "zlib", "littlecms", "freetype", "libpng", "giflib", "brotli", "libbz2",
    "libx11", "libxcb", "libxau", "libxdmcp", "libxext", "libxi", "libxrender", "libxtst", "libxfixes",
    "fontconfig", "libexpat",
]
MODULLER = ("java.base,java.desktop,java.smartcardio,java.instrument,java.logging,java.management,java.naming,"
            "java.prefs,java.sql,java.xml,java.net.http,java.security.jgss,java.security.sasl,java.scripting,"
            "java.xml.crypto,java.transaction.xa,jdk.crypto.cryptoki,jdk.crypto.ec,jdk.unsupported,jdk.charsets,"
            "jdk.localedata,jdk.zipfs,jdk.naming.dns,jdk.management,jdk.httpserver")
# JRE'nin yanına konacak yerel kütüphaneler (Termux önekinden; sembolik bağlar çözülerek)
YEREL = ["libandroid-shmem.so", "libandroid-spawn.so", "libandroid-support.so", "libiconv.so", "libjpeg.so.8",
         "libz.so.1", "liblcms2.so", "libfreetype.so", "libpng16.so", "libbz2.so.1.0", "libbrotlidec.so",
         "libbrotlicommon.so", "libX11.so", "libxcb.so", "libXau.so", "libXdmcp.so", "libXext.so", "libXi.so",
         "libXrender.so", "libXtst.so", "libXfixes.so", "libfontconfig.so", "libexpat.so.1", "libgif.so"]
GEREKSIZ = ["bin/jrunscript", "bin/jwebserver", "lib/libjsound.so", "lib/libsplashscreen.so"]


def adim(m):
    print("== " + m, flush=True)


def calistir(cmd, **kw):
    env = dict(os.environ)
    env.pop("JAVA_TOOL_OPTIONS", None)
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit("HATA: " + " ".join(cmd[:3]) + " ...\n" + r.stdout[-2000:] + r.stderr[-2000:])
    return r


def indir(url, hedef):
    istek = urllib.request.Request(url, headers={"User-Agent": "curl/8.5.0"})
    with urllib.request.urlopen(istek, timeout=300) as r, open(hedef + ".tmp", "wb") as f:
        shutil.copyfileobj(r, f)
    os.replace(hedef + ".tmp", hedef)


def paket_listesi():
    yol = os.path.join(ON, "Packages")
    if not os.path.exists(yol):
        indir(DEPO + "/dists/stable/main/binary-aarch64/Packages", yol)
    bilgi = {}
    for blok in open(yol, encoding="utf-8").read().split("\n\n"):
        al = lambda k: (re.search(r"^" + k + r": (.*)$", blok, re.M) or [None, None])[1]
        if al("Package"):
            bilgi[al("Package")] = {"dosya": al("Filename"), "sha256": al("SHA256"), "surum": al("Version")}
    return bilgi


def deb_ac(deb, hedef):
    """ar arşivinden data.tar.* çıkarır (xz/gz/zst desteklenir)."""
    with open(deb, "rb") as f:
        veri = f.read()
    if veri[:8] != b"!<arch>\n":
        sys.exit("deb değil: " + deb)
    i = 8
    while i < len(veri):
        ad = veri[i:i + 16].decode().strip().rstrip("/")
        boy = int(veri[i + 48:i + 58].decode().strip())
        icerik = veri[i + 60:i + 60 + boy]
        i += 60 + boy + (boy & 1)
        if ad.startswith("data.tar"):
            if ad.endswith(".zst"):
                import zstandard  # pip install zstandard
                icerik = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(icerik)).read()
                mod = "r:"
            else:
                mod = "r:*"
            with tarfile.open(fileobj=io.BytesIO(icerik), mode=mod) as t:
                t.extractall(hedef, filter="tar") if sys.version_info >= (3, 12) else t.extractall(hedef)
            return
    sys.exit("data.tar yok: " + deb)


def jre_olustur(kok):
    jdk = os.path.join(kok, PREFIX, "lib/jvm/java-21-openjdk")
    lib = os.path.join(kok, PREFIX, "lib")
    jre = os.path.join(CIKTI, "jre")
    shutil.rmtree(jre, ignore_errors=True)
    adim("jlink (modüller: java.base, java.desktop, java.smartcardio, ...)")
    calistir(["jlink", "--module-path", os.path.join(jdk, "jmods"), "--add-modules", MODULLER,
              "--include-locales=tr,en", "--strip-java-debug-attributes", "--no-header-files", "--no-man-pages",
              "--compress=zip-6", "--output", jre])
    # jlink hedef JDK'nın yerel dosyalarını jmods'tan alır; X11 araç takımı dahil (Caciocavallo onu yükler, X'e bağlanmaz)
    for g in GEREKSIZ:
        p = os.path.join(jre, g)
        if os.path.exists(p):
            os.remove(p)
    adim("yerel kütüphaneler")
    for ad in YEREL:
        kaynak = os.path.join(lib, ad)
        if not os.path.exists(kaynak):
            sys.exit("eksik yerel kütüphane: " + ad)
        shutil.copyfile(os.path.realpath(kaynak), os.path.join(jre, "lib", ad))
    # fontconfig: yazı tipleri Android'in /system/fonts klasöründen
    os.makedirs(os.path.join(jre, "conf", "fonts"), exist_ok=True)
    with open(os.path.join(jre, "conf", "fonts", "fonts.conf"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n<fontconfig>\n'
                '  <dir>/system/fonts</dir>\n  <cachedir>FC_CACHE</cachedir>\n</fontconfig>\n')
    # lisanslar
    hukuk = os.path.join(jre, "legal", "termux-kutuphaneleri")
    os.makedirs(hukuk, exist_ok=True)
    for lisans in glob.glob(os.path.join(kok, PREFIX, "share/doc/*/copyright")) + \
            glob.glob(os.path.join(kok, PREFIX, "share/LICENSES/*")):
        hedef = os.path.join(hukuk, os.path.basename(os.path.dirname(lisans)) + "-" + os.path.basename(lisans))
        if os.path.isfile(lisans):
            shutil.copyfile(lisans, hedef)
    zip_yol = os.path.join(CIKTI, "jre-arm64.zip")
    adim("jre-arm64.zip")
    with zipfile.ZipFile(zip_yol + ".tmp", "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for kokd, _, dosyalar in os.walk(jre):
            for d in sorted(dosyalar):
                tam = os.path.join(kokd, d)
                z.write(tam, os.path.relpath(tam, jre))
    os.replace(zip_yol + ".tmp", zip_yol)
    shutil.rmtree(jre, ignore_errors=True)
    return zip_yol


def jar_derle(kaynak_dizin, cikti_jar, release, ekler=(), manifest=None, patch=None, sinif_yolu=None):
    tmp = os.path.join(CIKTI, "_derle_" + os.path.basename(cikti_jar))
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    for ek in ekler:                     # hazır sınıflar (Caciocavallo) aynı jar'a
        with zipfile.ZipFile(ek) as z:
            for n in z.namelist():
                if n.startswith("META-INF/") or "/junit/" in n:
                    continue
                z.extract(n, tmp)
    kaynaklar = glob.glob(os.path.join(kaynak_dizin, "**", "*.java"), recursive=True)
    cmd = ["javac", "--release", str(release), "-encoding", "UTF-8", "-d", tmp]
    if patch:
        cmd += ["--patch-module", "java.desktop=" + tmp + os.pathsep + kaynak_dizin]
    if sinif_yolu:
        cmd += ["-cp", sinif_yolu]
    calistir(cmd + kaynaklar)
    jar = ["jar", "cf" + ("m" if manifest else ""), cikti_jar]
    if manifest:
        mf = os.path.join(CIKTI, "_manifest.txt")
        with open(mf, "w") as f:
            f.write(manifest)
        jar.append(mf)
    calistir(jar + ["-C", tmp, "."])
    shutil.rmtree(tmp, ignore_errors=True)


def main():
    os.makedirs(ON, exist_ok=True)
    yeniden = "--yeniden" in sys.argv
    zip_yol = os.path.join(CIKTI, "jre-arm64.zip")
    if yeniden or not os.path.exists(zip_yol):
        adim("Termux paketleri (aarch64)")
        bilgi = paket_listesi()
        kok = os.path.join(CIKTI, "_kok")
        shutil.rmtree(kok, ignore_errors=True)
        surumler = {}
        for p in PAKETLER:
            if p not in bilgi:
                sys.exit("paket bulunamadı: " + p)
            b = bilgi[p]
            deb = os.path.join(ON, os.path.basename(b["dosya"]))
            if not os.path.exists(deb) or hashlib.sha256(open(deb, "rb").read()).hexdigest() != b["sha256"]:
                print("   indiriliyor:", os.path.basename(deb), flush=True)
                indir(DEPO + "/" + b["dosya"], deb)
            if hashlib.sha256(open(deb, "rb").read()).hexdigest() != b["sha256"]:
                sys.exit("SHA256 uyuşmuyor: " + deb)
            deb_ac(deb, kok)
            surumler[p] = b["surum"]
        jre_olustur(kok)
        shutil.rmtree(kok, ignore_errors=True)
        with open(os.path.join(CIKTI, "paketler.json"), "w") as f:
            json.dump(surumler, f, indent=1)
    adim("eimza-agent.jar")
    jar_derle(os.path.join(KOK, "android", "eimza", "agent"), os.path.join(CIKTI, "eimza-agent.jar"), 11,
              manifest="Premain-Class: eimza.Agent\nCan-Redefine-Classes: false\nCan-Retransform-Classes: false\n"
                       "Implementation-Title: UdeMobile Adalet E-Imza Koprusu\n")
    adim("awt-patch.jar (Caciocavallo)")
    cacio = sorted(glob.glob(os.path.join(KOK, "android", "eimza", "lib", "cacio-*.jar")))
    jar_derle(os.path.join(KOK, "android", "eimza", "awtpatch"), os.path.join(CIKTI, "awt-patch.jar"), 21,
              ekler=cacio, patch=True)
    ozet = hashlib.sha256()
    for ad in ("jre-arm64.zip", "eimza-agent.jar", "awt-patch.jar"):
        with open(os.path.join(CIKTI, ad), "rb") as f:
            for parca in iter(lambda: f.read(1 << 20), b""):
                ozet.update(parca)
    with open(os.path.join(CIKTI, "surum.txt"), "w") as f:
        f.write(ozet.hexdigest()[:16])
    for ad in ("jre-arm64.zip", "eimza-agent.jar", "awt-patch.jar", "surum.txt"):
        print(f"   {ad}: {os.path.getsize(os.path.join(CIKTI, ad))} bayt")


if __name__ == "__main__":
    main()
