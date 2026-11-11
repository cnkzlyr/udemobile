#!/usr/bin/env python3
"""
UYAP Mobil: resmi UYAP Doküman Editörü'nü Android'de Termux / X11 / Termux:API OLMADAN çalıştıracak çalışma zamanını hazırlar.

Bileşenler (hepsi sabit SHA-256 ile indirilir ve doğrulanır):
  * AdoptOpenJDK 14.0.2+12 aarch64 (resmi Linux/glibc sürümü) → jlink ile küçültülmüş JRE (Nashorn dahil)
    jlink için aynı sürümün x64 JDK'sı (openjdk-14.0.2) kullanılır (jlink sürümü hedefle aynı olmalı).
  * Termux glibc deposu (aarch64; Android için derlenmiş glibc 2.4x) — yalnızca JRE'nin ihtiyaç duyduğu kitaplıklar
    (DT_NEEDED özyinelemeli taranır; eksik kalırsa derleme durur).
  * uyapjava: libjvm.so'yu doğrudan yükleyen başlatıcı (android/uyapmobil/baslatici/uyapjava.c, aarch64-linux-gnu-gcc).
  * Caciocavallo 1.11.1 (Maven Central) + JDK 14 yaması (android/uyapmobil/awtpatch14) → awt-patch14.jar
  * uyapmobil-kopru.jar: ekran/olay köprüsü (android/uyapmobil/kopru)
  * Liberation yazı tipleri (Debian fonts-liberation 2.1.5; Times New Roman / Arial / Courier New ile aynı ölçüler)

Resmi UYAP editörü DAĞITILMAZ: telefon onu ilk açılışta resmi adresten (rayp.adalet.gov.tr) indirir.

Çıktı: build/uyapmobil/{rt-arm64.zip, awt-patch14.jar, uyapmobil-kopru.jar, surum.txt}
Kullanım: python3 scripts/uyapmobil_hazirla.py [--yeniden]
"""
import glob
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CIKTI = os.path.join(KOK, "build", "uyapmobil")
ON = os.path.join(KOK, "build", "onbellek")
KAYNAK = os.path.join(KOK, "android", "uyapmobil")

JDK_AARCH64 = ("https://github.com/AdoptOpenJDK/openjdk14-binaries/releases/download/jdk-14.0.2%2B12/"
               "OpenJDK14U-jdk_aarch64_linux_hotspot_14.0.2_12.tar.gz",
               "ee87e9f03b1fbe6f328429b78fe1a9f44900026d220c90dfd747fe0bcd62d904")
JDK_X64 = ("https://download.java.net/java/GA/jdk14.0.2/205943a0976c4ed48cb16f1043c5c647/12/GPL/"
           "openjdk-14.0.2_linux-x64_bin.tar.gz",
           "91310200f072045dc6cef2c8c23e7e6387b37c46e9de49623ce0fa461a24623d")
CACIO = {
    "cacio-shared-1.11.1.jar": ("https://repo1.maven.org/maven2/com/github/caciocavallosilano/cacio-shared/1.11.1/cacio-shared-1.11.1.jar",
                                "36dbd1bdee39a7c7e1b0f643e1f6e1a2b22195e736d57b3a708334bf783dd912"),
    "cacio-tta-1.11.1.jar": ("https://repo1.maven.org/maven2/com/github/caciocavallosilano/cacio-tta/1.11.1/cacio-tta-1.11.1.jar",
                             "08e6a5011b967eec28e5df6737a0f10dec7d064bb94d4cfc0c34589459b2a92d"),
}
FLATLAF = ("https://repo1.maven.org/maven2/com/formdev/flatlaf/3.5.4/flatlaf-3.5.4.jar",
           "3c34b6aeb2f170a954c4358647eb43b68b447a2c351ff311072f7157a5d4e2fe")
FONTLAR = ("http://deb.debian.org/debian/pool/main/f/fonts-liberation/fonts-liberation_2.1.5-3_all.deb",
           "3d5c47480067b9615f6bf9b0eda6eefcab9d837af609827015445e8e759b5b8c")
GLIBC_DEPO = "https://packages-cf.termux.dev/apt/termux-glibc"
GLIBC_PAKETLER = ["glibc", "gcc-libs-glibc", "zlib-glibc", "libx11-glibc", "libxext-glibc", "libxrender-glibc",
                  "libxtst-glibc", "libxi-glibc", "libxau-glibc", "libxdmcp-glibc", "libxcb-glibc", "freetype-glibc",
                  "fontconfig-glibc", "libpng-glibc", "libexpat-glibc", "alsa-lib-glibc", "libbz2-glibc", "brotli-glibc",
                  "libxfixes-glibc"]
GLIBC_ON = "data/data/com.termux/files/usr/glibc/lib"
MODULLER = ("java.base,java.desktop,java.datatransfer,java.xml,java.xml.crypto,java.logging,java.naming,java.prefs,"
            "java.sql,java.sql.rowset,java.scripting,jdk.scripting.nashorn,jdk.dynalink,java.security.jgss,"
            "java.security.sasl,java.smartcardio,jdk.crypto.cryptoki,jdk.crypto.ec,java.net.http,java.management,"
            "jdk.management,jdk.unsupported,jdk.charsets,jdk.localedata,jdk.zipfs,jdk.naming.dns,java.instrument,"
            "java.transaction.xa,java.rmi,jdk.httpserver,jdk.xml.dom,jdk.accessibility,jdk.net,jdk.security.auth")
# JRE'de gereksiz: ses (Android'de yok), başlangıç ekranı, araçlar
GEREKSIZ = ["lib/libjsound.so", "lib/libsplashscreen.so", "bin"]


def adim(m):
    print("==", m, flush=True)


def indir(url, sha, ad=None):
    os.makedirs(ON, exist_ok=True)
    hedef = os.path.join(ON, ad or os.path.basename(url.split("?")[0]).replace("%2B", "+"))
    if not os.path.exists(hedef) or ozet(hedef) != sha:
        print("   indiriliyor:", os.path.basename(hedef), flush=True)
        istek = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
        with urllib.request.urlopen(istek, timeout=600) as r, open(hedef + ".tmp", "wb") as f:
            shutil.copyfileobj(r, f, 1 << 20)
        os.replace(hedef + ".tmp", hedef)
    if ozet(hedef) != sha:
        sys.exit("SHA256 uyuşmuyor: " + hedef)
    return hedef


def ozet(yol):
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for p in iter(lambda: f.read(1 << 20), b""):
            h.update(p)
    return h.hexdigest()


def tar_ac(arsiv, hedef):
    shutil.rmtree(hedef, ignore_errors=True)
    os.makedirs(hedef)
    with tarfile.open(arsiv) as t:
        uyeler = t.getmembers()
        on = os.path.commonprefix([m.name for m in uyeler]).split("/")[0]
        for m in uyeler:
            if m.name == on:
                continue
            m.name = m.name[len(on) + 1:] if m.name.startswith(on + "/") else m.name
            if not m.name or m.name.startswith("/") or ".." in m.name.split("/"):
                continue
            t.extract(m, hedef)


def deb_veri(deb):
    """.deb içindeki data.tar.* → (TarFile)"""
    with open(deb, "rb") as f:
        veri = f.read()
    if not veri.startswith(b"!<arch>\n"):
        sys.exit("deb değil: " + deb)
    i = 8
    while i < len(veri):
        ad = veri[i:i + 16].decode().strip().rstrip("/")
        boy = int(veri[i + 48:i + 58].decode().strip())
        icerik = veri[i + 60:i + 60 + boy]
        i += 60 + boy + (boy & 1)
        if ad.startswith("data.tar"):
            if ad.endswith(".zst"):
                import zstandard  # yalnızca gerekirse
                return tarfile.open(fileobj=io.BytesIO(zstandard.ZstdDecompressor().decompress(icerik, max_output_size=1 << 30)))
            return tarfile.open(fileobj=io.BytesIO(icerik))
    sys.exit("data.tar yok: " + deb)


def glibc_paketleri(hedef):
    adim("Termux glibc paketleri (aarch64)")
    istek = urllib.request.Request(GLIBC_DEPO + "/dists/glibc/stable/binary-aarch64/Packages", headers={"User-Agent": "curl/8"})
    with urllib.request.urlopen(istek, timeout=120) as r:
        dizin = r.read().decode()
    bilgi = {}
    for blok in dizin.split("\n\n"):
        a = dict(re.findall(r"^([A-Za-z0-9-]+): (.*)$", blok, re.M))
        if "Package" in a:
            bilgi[a["Package"]] = a
    surumler = {}
    os.makedirs(hedef, exist_ok=True)
    for p in GLIBC_PAKETLER:
        if p not in bilgi:
            sys.exit("glibc paketi bulunamadı: " + p)
        deb = indir(GLIBC_DEPO + "/" + bilgi[p]["Filename"], bilgi[p]["SHA256"])
        surumler[p] = bilgi[p]["Version"]
        with deb_veri(deb) as t:
            for m in t.getmembers():
                ad = m.name.lstrip("./")
                if not ad.startswith(GLIBC_ON + "/") or "/" in ad[len(GLIBC_ON) + 1:]:
                    continue
                if not (m.isfile() or m.issym()):
                    continue
                kisa = ad[len(GLIBC_ON) + 1:]
                if not (".so" in kisa or kisa == "ld.so"):
                    continue
                m.name = kisa
                t.extract(m, hedef)
    return surumler


def elf_gerekenler(yol):
    with open(yol, "rb") as f:
        if f.read(4) != b"\x7fELF":
            return []
    r = subprocess.run(["readelf", "-d", yol], capture_output=True, text=True)
    return re.findall(r"\(NEEDED\)\s+Shared library: \[([^\]]+)\]", r.stdout)


def gerceklestir(dizin, ad):
    """Sembolik bağı çöz: dizin/ad → gerçek dosya yolu (yoksa None)."""
    p = os.path.join(dizin, ad)
    for _ in range(10):
        if os.path.islink(p):
            p = os.path.join(dizin, os.readlink(p))
        else:
            break
    return p if os.path.isfile(p) else None


def glibc_sec(jre, uyapjava, glibc_ham, cikis):
    """JRE + başlatıcının ihtiyaç duyduğu glibc kitaplıklarını özyinelemeli topla (ld-linux dahil)."""
    adim("glibc bağımlılıkları")
    os.makedirs(cikis, exist_ok=True)
    jre_libler = set()
    for kokd, _, dosyalar in os.walk(jre):
        for d in dosyalar:
            jre_libler.add(d)
    kuyruk = [uyapjava] + [os.path.join(k, d) for k, _, ds in os.walk(jre) for d in ds if ".so" in d]
    secilen = {"ld-linux-aarch64.so.1"}
    shutil.copyfile(gerceklestir(glibc_ham, "ld-linux-aarch64.so.1"), os.path.join(cikis, "ld-linux-aarch64.so.1"))
    eksik = set()
    while kuyruk:
        yol = kuyruk.pop()
        for ad in elf_gerekenler(yol):
            if ad in secilen or ad in jre_libler:
                continue
            gercek = gerceklestir(glibc_ham, ad)
            if not gercek:
                eksik.add(ad + " (" + os.path.basename(yol) + ")")
                continue
            hedef = os.path.join(cikis, ad)
            shutil.copyfile(gercek, hedef)
            secilen.add(ad)
            kuyruk.append(hedef)
    # libawt_xawt'ın dlopen ile yüklediği (DT_NEEDED'de görünmeyen) kitaplıklar
    for ad in ("libfontconfig.so.1", "libfreetype.so.6", "libXrender.so.1", "libXext.so.6", "libXi.so.6", "libXtst.so.6",
               "libX11.so.6", "libnss_files.so.2", "libresolv.so.2", "libutil.so.1", "libgcc_s.so.1"):
        if ad in secilen:
            continue
        gercek = gerceklestir(glibc_ham, ad)
        if gercek:
            shutil.copyfile(gercek, os.path.join(cikis, ad))
            secilen.add(ad)
            kuyruk.append(os.path.join(cikis, ad))
    while kuyruk:
        yol = kuyruk.pop()
        for ad in elf_gerekenler(yol):
            if ad in secilen or ad in jre_libler:
                continue
            gercek = gerceklestir(glibc_ham, ad)
            if gercek:
                shutil.copyfile(gercek, os.path.join(cikis, ad))
                secilen.add(ad)
                kuyruk.append(os.path.join(cikis, ad))
            else:
                eksik.add(ad)
    if eksik:
        sys.exit("çözülemeyen glibc bağımlılıkları: " + ", ".join(sorted(eksik)))
    print("   " + str(len(secilen)) + " kitaplık:", ", ".join(sorted(secilen)), flush=True)


def soy(dizin):
    s = shutil.which("aarch64-linux-gnu-strip")
    if not s:
        print("   (aarch64-linux-gnu-strip yok: yerel kitaplıklar küçültülmedi)")
        return
    for kokd, _, dosyalar in os.walk(dizin):
        for d in dosyalar:
            p = os.path.join(kokd, d)
            if ".so" in d and not os.path.islink(p) and d != "ld-linux-aarch64.so.1":
                subprocess.run([s, "--strip-unneeded", p], capture_output=True)


def javac_derle(javac, jar, kaynaklar, cikti_jar, ek_args=(), manifest=None, ekler=()):
    with tempfile.TemporaryDirectory() as tmp:
        sin = os.path.join(tmp, "c")
        os.makedirs(sin)
        subprocess.run([javac, "-encoding", "UTF-8", "-nowarn", "-d", sin] + list(ek_args) + kaynaklar, check=True)
        for e in ekler:
            with zipfile.ZipFile(e) as z:
                for ad in z.namelist():
                    if ad.startswith("META-INF/") or ad.endswith("/") or ad == "module-info.class":
                        continue
                    hedef = os.path.join(sin, ad)
                    if os.path.exists(hedef):     # yama sınıfı Cacio'nunkini ezer
                        continue
                    os.makedirs(os.path.dirname(hedef), exist_ok=True)
                    with open(hedef, "wb") as f:
                        f.write(z.read(ad))
        with zipfile.ZipFile(cikti_jar + ".tmp", "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n" + (manifest or "") + "\n")
            for kokd, _, dosyalar in os.walk(sin):
                for d in sorted(dosyalar):
                    tam = os.path.join(kokd, d)
                    z.write(tam, os.path.relpath(tam, sin).replace(os.sep, "/"))
        os.replace(cikti_jar + ".tmp", cikti_jar)


def main():
    yeniden = "--yeniden" in sys.argv
    os.makedirs(CIKTI, exist_ok=True)
    jdk_x64 = os.path.join(ON, "jdk14-x64")
    if not os.path.exists(os.path.join(jdk_x64, "bin", "jlink")):
        adim("JDK 14.0.2 x64 (jlink/javac için)")
        tar_ac(indir(*JDK_X64), jdk_x64)
    javac = os.path.join(jdk_x64, "bin", "javac")
    ortam = dict(os.environ)
    ortam.pop("JAVA_TOOL_OPTIONS", None)

    rt_zip = os.path.join(CIKTI, "rt-arm64.zip")
    if yeniden or not os.path.exists(rt_zip):
        adim("JDK 14.0.2 aarch64 (resmi AdoptOpenJDK)")
        jdk_arm = os.path.join(ON, "jdk14-aarch64")
        if not os.path.exists(os.path.join(jdk_arm, "jmods", "java.base.jmod")):
            tar_ac(indir(*JDK_AARCH64), jdk_arm)
        rt = os.path.join(CIKTI, "_rt")
        shutil.rmtree(rt, ignore_errors=True)
        jre = os.path.join(rt, "jre")
        adim("jlink")
        subprocess.run([os.path.join(jdk_x64, "bin", "jlink"), "--module-path", os.path.join(jdk_arm, "jmods"),
                        "--add-modules", MODULLER, "--include-locales=tr,en", "--strip-java-debug-attributes",
                        "--no-header-files", "--no-man-pages", "--compress=2", "--output", jre], check=True, env=ortam)
        for g in GEREKSIZ:
            p = os.path.join(jre, g)
            if os.path.isdir(p):
                shutil.rmtree(p)
            elif os.path.exists(p):
                os.remove(p)
        adim("uyapjava başlatıcısı (aarch64)")
        gcc = shutil.which("aarch64-linux-gnu-gcc")
        if not gcc:
            sys.exit("aarch64-linux-gnu-gcc yok (apt install gcc-aarch64-linux-gnu)")
        os.makedirs(os.path.join(rt, "bin"), exist_ok=True)
        uyapjava = os.path.join(rt, "bin", "uyapjava")
        subprocess.run([gcc, "-O2", "-s", "-I", os.path.join(jdk_x64, "include"), "-I", os.path.join(jdk_x64, "include", "linux"),
                        "-o", uyapjava, os.path.join(KAYNAK, "baslatici", "uyapjava.c"), "-ldl", "-lpthread"], check=True)
        glibc_ham = os.path.join(ON, "glibc-ham")
        shutil.rmtree(glibc_ham, ignore_errors=True)
        surumler = glibc_paketleri(glibc_ham)
        glibc_sec(jre, uyapjava, glibc_ham, os.path.join(rt, "glibc"))
        soy(rt)
        adim("yazı tipleri (Liberation)")
        fd = os.path.join(rt, "fonts")
        os.makedirs(fd, exist_ok=True)
        with deb_veri(indir(*FONTLAR)) as t:
            for m in t.getmembers():
                if m.isfile() and m.name.endswith(".ttf"):
                    with t.extractfile(m) as kaynak, open(os.path.join(fd, os.path.basename(m.name)), "wb") as f:
                        shutil.copyfileobj(kaynak, f)
        # lisanslar
        hk = os.path.join(rt, "LISANSLAR")
        os.makedirs(hk, exist_ok=True)
        with open(os.path.join(hk, "OKU.txt"), "w", encoding="utf-8") as f:
            f.write("UYAP Mobil çalışma zamanı bileşenleri:\n"
                    "- AdoptOpenJDK 14.0.2+12 (GPLv2 + Classpath Exception) — kaynak: https://github.com/AdoptOpenJDK/openjdk-jdk14u\n"
                    "- Termux glibc paketleri (LGPL-2.1+/GPL; gcc-libs: GPLv3 + GCC Runtime Library Exception; X11: MIT)\n"
                    "  kaynak: https://github.com/termux-pacman/glibc-packages · sürümler: " + ", ".join(f"{k} {v}" for k, v in surumler.items()) + "\n"
                    "- Liberation Fonts 2.1.5 (SIL Open Font License 1.1)\n"
                    "- Caciocavallo 1.11.1 (GPLv2 + Classpath Exception)\n")
        for lis in glob.glob(os.path.join(jre, "legal", "java.base", "*")):
            shutil.copyfile(lis, os.path.join(hk, "JDK-" + os.path.basename(lis)))
        adim("rt-arm64.zip")
        with zipfile.ZipFile(rt_zip + ".tmp", "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for kokd, _, dosyalar in os.walk(rt):
                for d in sorted(dosyalar):
                    tam = os.path.join(kokd, d)
                    if os.path.islink(tam):
                        continue
                    z.write(tam, os.path.relpath(tam, rt))
        os.replace(rt_zip + ".tmp", rt_zip)
        shutil.rmtree(rt, ignore_errors=True)

    adim("awt-patch14.jar (Caciocavallo 1.11.1 + JDK 14 yaması)")
    cacio = [indir(u, s, ad) for ad, (u, s) in CACIO.items()]
    yama = sorted(glob.glob(os.path.join(KAYNAK, "awtpatch14", "**", "*.java"), recursive=True))
    javac_derle(javac, None, yama, os.path.join(CIKTI, "awt-patch14.jar"),
                ek_args=["--patch-module", "java.desktop=" + os.pathsep.join([os.path.join(KAYNAK, "awtpatch14")] + cacio)],
                ekler=cacio)
    adim("uyapmobil-kopru.jar")
    javac_derle(javac, None, sorted(glob.glob(os.path.join(KAYNAK, "kopru", "**", "*.java"), recursive=True)),
                os.path.join(CIKTI, "uyapmobil-kopru.jar"), ek_args=["--release", "11"],
                manifest="Premain-Class: uyapmobil.Kopru\nImplementation-Title: UYAP Mobil kopru\n")
    adim("uyap-modern.jar (uyap-editor-modern: akıcı kaydırma, tema, PDF yazı tipi düzeltmesi)")
    # Kaynak: github.com/cnkzlyr/uyap-editor-modern core/src. Lisans denetimini değiştiren sınıflar (tr/gov/tubitak/**) ALINMAZ.
    javac_derle(javac, None, sorted(glob.glob(os.path.join(KAYNAK, "modern", "src", "**", "*.java"), recursive=True)),
                os.path.join(CIKTI, "uyap-modern.jar"), ek_args=["--release", "11", "-cp", indir(*FLATLAF)],
                manifest="Premain-Class: tr.gov.uyap.modernizer.ModernizerAgent\nImplementation-Title: UYAP Editor Modern\n",
                ekler=[indir(*FLATLAF)])
    h = hashlib.sha256()
    for ad in ("rt-arm64.zip", "awt-patch14.jar", "uyapmobil-kopru.jar", "uyap-modern.jar"):
        h.update(open(os.path.join(CIKTI, ad), "rb").read())
    with open(os.path.join(CIKTI, "surum.txt"), "w") as f:
        f.write(h.hexdigest()[:16])
    for ad in ("rt-arm64.zip", "awt-patch14.jar", "uyapmobil-kopru.jar", "uyap-modern.jar", "surum.txt"):
        print(f"   {ad}: {os.path.getsize(os.path.join(CIKTI, ad))} bayt")


if __name__ == "__main__":
    main()
