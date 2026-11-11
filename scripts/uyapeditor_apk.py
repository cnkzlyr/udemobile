#!/usr/bin/env python3
"""
UYAP Editör — ayrı Android uygulaması (paket: com.agy.uyapeditor).

Resmi UYAP Doküman Editörü'nü Java 14 ile Termux / X11 olmadan çalıştıran ekran CanEditor'dan ayrıldı: bazı telefonların
"Şununla aç" penceresi aynı uygulamanın iki ekranını tek simgede topladığı için .udf açılırken UYAP Editör seçilemiyordu.
Kaynak kod CanEditor ile ortaktır (android/src); manifest android/uyapeditor/AndroidManifest.xml, paket adı aapt2
"--rename-manifest-package" ile değiştirilir (sınıflar com.agy.uyapacici paketinde kalır). Varlıklar:
assets/uyapmobil (scripts/uyapmobil_hazirla.py) ve mobil görünüm için assets/editor. İmza: CanEditor ile aynı anahtar.

Çıktı: release/UYAP-Editor-v<sürüm>.apk ve release/UYAP-Editor-latest.apk
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pack_release as pr  # araç yolları (aapt2, d8, zipalign, apksigner) ve sürüm

KOK = pr.PROJECT_ROOT
PAKET = "com.agy.uyapeditor"


def main():
    os.chdir(KOK)
    if not pr.AAPT2 or not os.path.exists(pr.PLATFORM_JAR):
        sys.exit("aapt2 / android.jar bulunamadı (ANDROID_HOME)")
    m = open(os.path.join("android", "AndroidManifest.xml"), encoding="utf-8").read()
    vcode = re.search(r'android:versionCode="(\d+)"', m).group(1)
    with tempfile.TemporaryDirectory() as tmp:
        manifest = os.path.join(tmp, "AndroidManifest.xml")
        s = open(os.path.join("android", "uyapeditor", "AndroidManifest.xml"), encoding="utf-8").read()
        s = s.replace("VERSIONCODE", vcode).replace("VERSIONNAME", pr.VERSION)
        open(manifest, "w", encoding="utf-8").write(s)
        # varlıklar: yalnızca uyapmobil
        um = os.path.join(KOK, "build", "uyapmobil")
        gerekli = ["rt-arm64.zip", "awt-patch14.jar", "uyapmobil-kopru.jar", "uyap-modern.jar", "surum.txt"]
        if not all(os.path.exists(os.path.join(um, g)) for g in gerekli):
            r = subprocess.run([sys.executable, os.path.join(KOK, "scripts", "uyapmobil_hazirla.py")])
            if r.returncode != 0:
                sys.exit("uyapmobil_hazirla.py başarısız")
        pr.step("UYAP Editör: kaynaklar (aapt2)")
        res_zip = os.path.join(tmp, "res.zip")
        subprocess.run([pr.AAPT2, "compile", "--dir", "android/res", "-o", res_zip], check=True)
        gen = os.path.join(tmp, "gen")
        os.makedirs(gen)
        apk0 = os.path.join(tmp, "u.apk")
        subprocess.run([pr.AAPT2, "link", "-I", pr.PLATFORM_JAR, "--manifest", manifest, "--java", gen,
                        "--rename-manifest-package", PAKET, "-o", apk0, res_zip], check=True)
        pr.step("UYAP Editör: Java derleme + dex")
        xz = os.path.join(KOK, "build", "onbellek", "xz-1.9.jar")
        if not os.path.exists(xz):
            sys.exit("xz-1.9.jar yok: önce scripts/pack_release.py çalıştırın")
        sin = os.path.join(tmp, "classes")
        os.makedirs(sin)
        kaynaklar = glob.glob("android/src/**/*.java", recursive=True) + glob.glob(gen + "/**/*.java", recursive=True)
        r = subprocess.run([pr.JAVAC, "-encoding", "UTF-8", "-source", "8", "-target", "8", "-nowarn",
                            "-cp", pr.PLATFORM_JAR + os.pathsep + xz, "-d", sin] + kaynaklar, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr)
            sys.exit("javac başarısız")
        dex = os.path.join(tmp, "dex")
        os.makedirs(dex)
        subprocess.run(pr.D8_CMD + ["--lib", pr.PLATFORM_JAR, "--output", dex, "--min-api", "21"]
                       + glob.glob(sin + "/**/*.class", recursive=True) + [xz], check=True, capture_output=True)
        with zipfile.ZipFile(apk0, "a", zipfile.ZIP_DEFLATED) as z:
            z.write(os.path.join(dex, "classes.dex"), "classes.dex")
            for g in gerekli:
                z.write(os.path.join(um, g), "assets/uyapmobil/" + g,
                        compress_type=zipfile.ZIP_STORED if g.endswith(".zip") else zipfile.ZIP_DEFLATED)
            # Mobil görünüm (EditorActivity): UdeMobile web editörü
            ed = os.path.join(KOK, "android", "assets", "editor")
            for kok, _, dosyalar in os.walk(ed):
                for d in sorted(dosyalar):
                    tam = os.path.join(kok, d)
                    z.write(tam, "assets/" + os.path.relpath(tam, os.path.join(KOK, "android", "assets")).replace(os.sep, "/"))
        hizali = os.path.join(tmp, "h.apk")
        if pr.ZIPALIGN and (os.path.exists(pr.ZIPALIGN) or shutil.which(pr.ZIPALIGN)):
            subprocess.run([pr.ZIPALIGN, "-f", "-p", "4", apk0, hizali], check=True)
        else:
            shutil.copy2(apk0, hizali)
        pr.step("UYAP Editör: imza")
        ks = os.environ.get("ANDROID_KEYSTORE") or os.path.expanduser("~/.android-sdk/debug.keystore")
        if not os.path.exists(ks):
            sys.exit("imza anahtarı yok (ANDROID_KEYSTORE)")
        sifre = os.environ.get("ANDROID_KEYSTORE_PASS", "android")
        cikti = os.path.join("release", f"UYAP-Editor-v{pr.VERSION}.apk")
        subprocess.run(pr.APKSIGNER_CMD + ["sign", "--ks", ks, "--ks-pass", "pass:" + sifre,
                                           "--ks-key-alias", os.environ.get("ANDROID_KEY_ALIAS", "androiddebugkey"),
                                           "--key-pass", "pass:" + os.environ.get("ANDROID_KEY_PASS", sifre),
                                           "--out", cikti, hizali], check=True)
        shutil.copy2(cikti, os.path.join("release", "UYAP-Editor-latest.apk"))
        print(f"Created {cikti} ({os.path.getsize(cikti)} bytes).")


if __name__ == "__main__":
    main()
