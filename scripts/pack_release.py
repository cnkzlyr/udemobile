import os
import urllib.request
import hashlib
import sys
import glob
import shutil
import zipfile
import subprocess

VERSION = "4.3.0"
XZ_SHA256 = "211b306cfc44f8f96df3a0a3ddaf75ba8c5289eed77d60d72f889bb855f535e5"
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    # Android SDK: ANDROID_HOME > ANDROID_SDK_ROOT > %LOCALAPPDATA%\Android\Sdk (Android Studio / sdkmanager varsayılanı)
    SDK = (os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
           or os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk"))
    _bt = sorted(glob.glob(os.path.join(SDK, "build-tools", "*")))
    BUILD_TOOLS = _bt[-1] if _bt else os.path.join(SDK, "build-tools", "35.0.0")
    _pl = sorted(glob.glob(os.path.join(SDK, "platforms", "android-34", "android.jar"))) or \
          sorted(glob.glob(os.path.join(SDK, "platforms", "android-*", "android.jar")))
    PLATFORM_JAR = _pl[-1] if _pl else os.path.join(SDK, "platforms", "android-34", "android.jar")
    # JDK: JAVA_HOME (windows_yayin.ps1 Temurin 21'i verir) > eski sabit yol
    JAVA_HOME = os.environ.get("JAVA_HOME") or r"C:\Program Files\Microsoft\jdk-14.0.2"
    JAVAC = os.path.join(JAVA_HOME, "bin", "javac.exe")
    JAVA = os.path.join(JAVA_HOME, "bin", "java.exe")
    KEYTOOL = os.path.join(JAVA_HOME, "bin", "keytool.exe")
    AAPT = os.path.join(BUILD_TOOLS, "aapt.exe")
    AAPT2 = os.path.join(BUILD_TOOLS, "aapt2.exe") if os.path.exists(os.path.join(BUILD_TOOLS, "aapt2.exe")) else shutil.which("aapt2")
    ZIPALIGN = os.path.join(BUILD_TOOLS, "zipalign.exe")
    D8_CMD = [JAVA, "-cp", os.path.join(BUILD_TOOLS, "lib", "d8.jar"), "com.android.tools.r8.D8"]
    APKSIGNER_CMD = [JAVA, "-jar", os.path.join(BUILD_TOOLS, "lib", "apksigner.jar")]
elif os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT"):
    # CI (GitHub Actions) / standart Android SDK kurulumu: araçlar ANDROID_HOME altından bulunur
    SDK = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    _bt = sorted(glob.glob(os.path.join(SDK, "build-tools", "*")))
    BUILD_TOOLS = _bt[-1] if _bt else ""
    _pl = sorted(glob.glob(os.path.join(SDK, "platforms", "android-34", "android.jar"))) or \
          sorted(glob.glob(os.path.join(SDK, "platforms", "android-*", "android.jar")))
    PLATFORM_JAR = _pl[-1] if _pl else ""
    JAVAC = shutil.which("javac") or "javac"
    JAVA = shutil.which("java") or "java"
    KEYTOOL = shutil.which("keytool") or "keytool"
    _arac = lambda ad: os.path.join(BUILD_TOOLS, ad) if os.path.exists(os.path.join(BUILD_TOOLS, ad)) else shutil.which(ad)
    AAPT = _arac("aapt")
    AAPT2 = _arac("aapt2")
    ZIPALIGN = _arac("zipalign") or "zipalign"
    D8_CMD = [_arac("d8") or "d8"]
    APKSIGNER_CMD = [_arac("apksigner") or "apksigner"]
else:
    alt_sdk_jar = os.path.expanduser("~/.android-sdk/android-34/android.jar")
    if os.path.exists(alt_sdk_jar):
        PLATFORM_JAR = alt_sdk_jar
    else:
        PLATFORM_JAR = os.path.expanduser("~/android-sdk/android-34/android.jar")
    JAVAC = shutil.which("javac") or "javac"
    JAVA = shutil.which("java") or "java"
    KEYTOOL = shutil.which("keytool") or "keytool"
    AAPT = shutil.which("aapt")
    AAPT2 = shutil.which("aapt2")
    ZIPALIGN = shutil.which("zipalign") or "zipalign"
    D8_CMD = [shutil.which("d8") or "d8"]
    APKSIGNER_CMD = [shutil.which("apksigner") or "apksigner"]


# Android sınıfları için ayrı JDK (CANEDITOR_ANDROID_JDK): JDK 21 javac'ı -source 8'de bile anonim sınıf
# kurucularına İSİMSİZ "MethodParameters" (mandated) kaydı yazar; build-tools 34/35'teki D8 (8.2.x) bu boş adı
# okurken çöker ("Cannot invoke String.length() because <parameter1> is null"). JDK 17 bu kaydı üretmez.
_ANDROID_JDK = os.environ.get("CANEDITOR_ANDROID_JDK")
if _ANDROID_JDK and os.path.isdir(_ANDROID_JDK):
    _uz = ".exe" if IS_WINDOWS else ""
    JAVAC = os.path.join(_ANDROID_JDK, "bin", "javac" + _uz)
    JAVA = os.path.join(_ANDROID_JDK, "bin", "java" + _uz)
    KEYTOOL = os.path.join(_ANDROID_JDK, "bin", "keytool" + _uz)
    if IS_WINDOWS:
        D8_CMD = [JAVA, "-cp", os.path.join(BUILD_TOOLS, "lib", "d8.jar"), "com.android.tools.r8.D8"]
        APKSIGNER_CMD = [JAVA, "-jar", os.path.join(BUILD_TOOLS, "lib", "apksigner.jar")]


def step(msg):
    print("=" * 60)
    print(msg)
    print("=" * 60)


def sync_frontend_to_android_assets():
    step("0. Syncing frontend/public/* to android/assets/editor/*")
    assets_dir = os.path.join(PROJECT_ROOT, "android", "assets", "editor")
    os.makedirs(assets_dir, exist_ok=True)
    for fname in ["desktop_bridge.js", "editor.css", "editor.js", "favicon.svg", "history.js", "icons.svg", "jszip.min.js", "updater.js", "ui-shell.js", "flow.js", "esign.js", "pdfexport.js", "jspdf.umd.min.js", "pdf.min.js", "pdf.worker.min.js", "utif.js", "asistan.js", "hukuk_hesap.js", "hayfa.js"]:
        src = os.path.join(PROJECT_ROOT, "frontend", "public", fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(assets_dir, fname))
            print(f"  Synced {fname} -> android/assets/editor/{fname}")
    fonts_src = os.path.join(PROJECT_ROOT, "frontend", "public", "fonts")
    if os.path.exists(fonts_src):
        fonts_dest = os.path.join(assets_dir, "fonts")
        os.makedirs(fonts_dest, exist_ok=True)
        for f in os.listdir(fonts_src):
            shutil.copy2(os.path.join(fonts_src, f), os.path.join(fonts_dest, f))
        print("  Synced fonts -> android/assets/editor/fonts/")
    index_src = os.path.join(PROJECT_ROOT, "frontend", "index.html")
    if os.path.exists(index_src):
        shutil.copy2(index_src, os.path.join(assets_dir, "editor.html"))
        print("  Synced frontend/index.html -> android/assets/editor/editor.html")


def main():
    os.chdir(PROJECT_ROOT)
    sync_frontend_to_android_assets()

    os.makedirs("release", exist_ok=True)
    temp_dir = os.path.join(PROJECT_ROOT, "temp_build")
    shutil.rmtree(temp_dir, ignore_errors=True)
    os.makedirs(temp_dir, exist_ok=True)

    # 1. Portable Web GUI zip
    step(f"1. Building Portable Web GUI zip v{VERSION}")
    zip_path = os.path.join("release", f"CanEditor-Portable-Web-GUI-v{VERSION}.zip")
    if os.path.exists(zip_path):
        os.remove(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for fname in ["desktop_bridge.js", "editor.css", "editor.js", "favicon.svg", "history.js", "icons.svg", "jszip.min.js", "updater.js", "ui-shell.js", "flow.js", "esign.js", "pdfexport.js", "jspdf.umd.min.js", "pdf.min.js", "pdf.worker.min.js", "utif.js", "asistan.js", "hukuk_hesap.js", "hayfa.js"]:
            p = os.path.join("frontend", "public", fname)
            if os.path.exists(p):
                z.write(p, arcname=fname)
                print(f"  Added {fname}")
        fonts_p = os.path.join("frontend", "public", "fonts")
        if os.path.exists(fonts_p):
            for ff in os.listdir(fonts_p):
                fp = os.path.join(fonts_p, ff)
                z.write(fp, arcname=f"fonts/{ff}")
            print("  Added fonts/ to zip")
        index_p = os.path.join("frontend", "index.html")
        z.write(index_p, arcname="index.html")
        print("  Added index.html")
    print(f"Created {zip_path} ({os.path.getsize(zip_path)} bytes)")

    # 2. Package resources & generate R.java
    if not (AAPT or AAPT2) or not os.path.exists(PLATFORM_JAR) or not shutil.which("javac"):
        print("=" * 60)
        print("Android SDK derleme araçları (aapt/javac/android.jar) yerel ortamda bulunamadı.")
        print(f"CanEditor-Portable-Web-GUI-v{VERSION}.zip başarıyla üretildi ve varlıklar senkronize edildi.")
        print("APK derlemesi GitHub Actions CI tarafından otomatik olarak tamamlanacaktır.")
        print("=" * 60)
        return

    unaligned_apk = os.path.join(temp_dir, "unaligned.apk")
    gen_dir = os.path.join(temp_dir, "gen")
    os.makedirs(gen_dir, exist_ok=True)

    if AAPT2 and not IS_WINDOWS:
        step("2. Compiling & Linking Android resources with aapt2")
        compiled_res_zip = os.path.join(temp_dir, "compiled_res.zip")
        res_cmd = [AAPT2, "compile", "--dir", "android/res", "-o", compiled_res_zip]
        res = subprocess.run(res_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print("aapt2 compile failed:", res.stderr)
            sys.exit(1)

        link_cmd = [
            AAPT2, "link",
            "-I", PLATFORM_JAR,
            "--manifest", "android/AndroidManifest.xml",
            "-A", "android/assets",
            "--java", gen_dir,
            "-o", unaligned_apk,
            compiled_res_zip
        ]
        res = subprocess.run(link_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print("aapt2 link failed:", res.stderr)
            sys.exit(1)
        print("Base APK and R.java generated via aapt2.")
    else:
        step("2. Packaging base APK with aapt")
        cmd = [
            AAPT, "package", "-f", "-m",
            "-M", "android/AndroidManifest.xml",
            "-S", "android/res",
            "-I", PLATFORM_JAR,
            "-J", gen_dir,
            "-F", unaligned_apk,
            "-A", "android/assets"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print("aapt failed:", res.stderr)
            sys.exit(1)
        print("Base APK created.")

    # 3. Compile Java classes
    step("3. Compiling Java classes with javac")
    classes_dir = os.path.join(temp_dir, "classes")
    os.makedirs(classes_dir, exist_ok=True)
    java_files = glob.glob("android/src/**/*.java", recursive=True) + glob.glob(f"{gen_dir}/**/*.java", recursive=True)
    if not glob.glob(f"{gen_dir}/**/*.java", recursive=True):
        java_files += glob.glob("android/gen/**/*.java", recursive=True)
    # xz-java (org.tukaani:xz 1.9, kamu malı): resmi UYAP Editör Debian paketindeki data.tar.xz'yi açmak için
    xz_jar = os.path.join(PROJECT_ROOT, "build", "onbellek", "xz-1.9.jar")
    if not os.path.exists(xz_jar) or hashlib.sha256(open(xz_jar, "rb").read()).hexdigest() != XZ_SHA256:
        os.makedirs(os.path.dirname(xz_jar), exist_ok=True)
        _istek = urllib.request.Request("https://repo1.maven.org/maven2/org/tukaani/xz/1.9/xz-1.9.jar", headers={"User-Agent": "curl/8"})
        with urllib.request.urlopen(_istek, timeout=120) as _r, open(xz_jar + ".tmp", "wb") as _f:
            _f.write(_r.read())
        os.replace(xz_jar + ".tmp", xz_jar)
    if hashlib.sha256(open(xz_jar, "rb").read()).hexdigest() != XZ_SHA256:
        print("xz-1.9.jar SHA256 uyuşmuyor"); sys.exit(1)
    cmd = [
        JAVAC,
        "-encoding", "UTF-8",
        "-source", "8",
        "-target", "8",
        "-cp", PLATFORM_JAR + os.pathsep + xz_jar,
        "-d", classes_dir
    ] + java_files
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("javac failed:", res.stderr)
        sys.exit(1)
    print("javac completed successfully.")

    # 4. Run D8 to generate classes.dex
    step("4. Generating classes.dex with D8")
    dex_dir = os.path.join(temp_dir, "dex")
    os.makedirs(dex_dir, exist_ok=True)
    class_files = glob.glob(f"{classes_dir}/**/*.class", recursive=True)
    cmd = D8_CMD + ["--lib", PLATFORM_JAR, "--output", dex_dir, "--min-api", "21"] + class_files + [xz_jar]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("D8 failed:", res.stderr)
        sys.exit(1)
    dex_file = os.path.join(dex_dir, "classes.dex")
    print(f"classes.dex generated ({os.path.getsize(dex_file)} bytes).")

    # 5. Add classes.dex to base APK
    step("5. Adding classes.dex to APK")
    with zipfile.ZipFile(unaligned_apk, "a", zipfile.ZIP_DEFLATED) as zf:
        zf.write(dex_file, arcname="classes.dex")
    print("classes.dex added to APK.")

    # 5b. Adalet E-İmza (Termux'suz): gömülü Java 21 + köprü ajanı + AWT yaması (scripts/jre_hazirla.py üretir)
    step("5b. Adding embedded Java 21 for Adalet E-Imza")
    eimza_dir = os.path.join(PROJECT_ROOT, "build", "eimza")
    gerekli = ["jre-arm64.zip", "eimza-agent.jar", "awt-patch.jar", "surum.txt"]
    if not all(os.path.exists(os.path.join(eimza_dir, g)) for g in gerekli) or os.environ.get("CANEDITOR_JRE_YENIDEN") == "1":
        r = subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "scripts", "jre_hazirla.py")])
        if r.returncode != 0:
            print("jre_hazirla.py başarısız (Adalet E-İmza gömülü Java'sı hazırlanamadı).")
            sys.exit(1)
    with zipfile.ZipFile(unaligned_apk, "a") as zf:
        for g in gerekli:
            # jre-arm64.zip zaten sıkıştırılmış: tekrar sıkıştırılmaz (STORED), kurulumda hızlı açılır
            zf.write(os.path.join(eimza_dir, g), arcname="assets/eimza/" + g,
                     compress_type=zipfile.ZIP_STORED if g.endswith(".zip") else zipfile.ZIP_DEFLATED)
    print("assets/eimza/* added to APK.")

    # 5c. UYAP Editör (resmi editör, Java 14) artık AYRI uygulamadır: scripts/uyapeditor_apk.py (en sonda çağrılır)

    # 5d. Hukuk Asistanı sunucusu (Termux'suz): CPython aarch64 + tekerlekler + Termux glibc + asistan/
    #     (scripts/asistan_android_hazirla.py üretir; AsistanServisi.java açar ve glibc yükleyicisiyle başlatır)
    step("5d. Adding Hukuk Asistani runtime (Python, Termux'suz)")
    asistan_dir = os.path.join(PROJECT_ROOT, "build", "asistan-android")
    gerekli = ["asistan-rt-arm64.zip", "surum.txt"]
    # Windows'ta readelf/qemu yok: CANEDITOR_ASISTAN_ANDROID=0 ile atlanır (APK çalışır; asistan sekmesi
    # "bu derlemede çalışma ortamı yok" der). Linux/CI'da varsayılan olarak eklenir.
    if os.environ.get("CANEDITOR_ASISTAN_ANDROID") == "0" and not all(os.path.exists(os.path.join(asistan_dir, g)) for g in gerekli):
        print("Android asistan çalışma ortamı atlandı (CANEDITOR_ASISTAN_ANDROID=0).")
        gerekli = []
    elif not all(os.path.exists(os.path.join(asistan_dir, g)) for g in gerekli) or os.environ.get("CANEDITOR_ASISTAN_YENIDEN") == "1":
        r = subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "scripts", "asistan_android_hazirla.py")])
        if r.returncode != 0:
            print("asistan_android_hazirla.py başarısız (Android asistan çalışma ortamı hazırlanamadı).")
            sys.exit(1)
    with zipfile.ZipFile(unaligned_apk, "a") as zf:
        for g in gerekli:
            zf.write(os.path.join(asistan_dir, g), arcname="assets/asistan/" + g,
                     compress_type=zipfile.ZIP_STORED if g.endswith(".zip") else zipfile.ZIP_DEFLATED)
    print("assets/asistan/* added to APK.")

    # 6. Zipalign
    step("6. Aligning APK with zipalign")
    aligned_apk = os.path.join(temp_dir, "aligned.apk")
    if ZIPALIGN and (os.path.exists(ZIPALIGN) or shutil.which(ZIPALIGN)):
        cmd = [ZIPALIGN, "-f", "-p", "4", unaligned_apk, aligned_apk]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print("zipalign failed:", res.stderr)
            shutil.copy2(unaligned_apk, aligned_apk)
        else:
            print("APK aligned.")
    else:
        print("zipalign bulunamadı, APK doğrudan apksigner ile imzalanacak.")
        shutil.copy2(unaligned_apk, aligned_apk)

    # 7. İmza anahtarı. Telefona GÜNCELLEME olarak kurulabilmesi için HER sürüm AYNI anahtarla imzalanmalı.
    #    Öncelik: ANDROID_KEYSTORE ortam değişkeni (CI'da GitHub secret'tan) > ~/.android-sdk > proje kökü.
    #    CANEDITOR_IMZA_ZORUNLU=1 iken anahtar yoksa YENİSİ ÜRETİLMEZ, derleme durur (CI: yanlış anahtarla
    #    "paket çakışıyor" hatası veren APK yayınlanmasın).
    ks_sifre = os.environ.get("ANDROID_KEYSTORE_PASS", "android")
    ks_alias = os.environ.get("ANDROID_KEY_ALIAS", "androiddebugkey")
    ks_key_sifre = os.environ.get("ANDROID_KEY_PASS", ks_sifre)
    alt_ks = os.path.expanduser("~/.android-sdk/debug.keystore")
    if os.environ.get("ANDROID_KEYSTORE"):
        keystore_path = os.environ["ANDROID_KEYSTORE"]
    elif os.path.exists(alt_ks):
        keystore_path = alt_ks
    else:
        keystore_path = os.path.join(PROJECT_ROOT, "debug.keystore")
    if not os.path.exists(keystore_path) and os.environ.get("CANEDITOR_IMZA_ZORUNLU") == "1":
        print("❌ İmza anahtarı bulunamadı ve CANEDITOR_IMZA_ZORUNLU=1: yeni anahtar üretilmedi.")
        print("   Önceki sürümlerle aynı anahtar (debug.keystore) olmadan üretilen APK telefona güncelleme olarak kurulamaz.")
        sys.exit(2)
    if not os.path.exists(keystore_path):
        print("Creating debug.keystore")
        cmd = [
            KEYTOOL,
            "-genkey", "-v",
            "-keystore", keystore_path,
            "-storepass", "android",
            "-alias", "androiddebugkey",
            "-keypass", "android",
            "-keyalg", "RSA",
            "-keysize", "2048",
            "-validity", "10000",
            "-dname", "CN=Android Debug, O=Android, C=US"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print("keytool failed:", res.stderr)
            sys.exit(1)

    # 8. Sign APK with apksigner
    step("7. Signing APK with apksigner (v1, v2, v3)")
    out_apk = os.path.join("release", f"CanEditor-v{VERSION}.apk")
    cmd = APKSIGNER_CMD + [
        "sign",
        "--ks", keystore_path,
        "--ks-pass", f"pass:{ks_sifre}",
        "--ks-key-alias", ks_alias,
        "--key-pass", f"pass:{ks_key_sifre}",
        "--v1-signing-enabled", "true",
        "--v2-signing-enabled", "true",
        "--v3-signing-enabled", "true",
        "--out", out_apk,
        aligned_apk
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("apksigner failed:", res.stderr)
        sys.exit(1)
    print(f"Created {out_apk} ({os.path.getsize(out_apk)} bytes).")

    # Copy to latest
    latest_apk = os.path.join("release", "CanEditor-latest.apk")
    shutil.copy2(out_apk, latest_apk)
    print(f"Copied to {latest_apk}.")

    # Tek uygulama politikası (v4.1.0+): ayrı UYAP-Editor APK artık üretilmez; tüm editör + asistan CanEditor'da birleşiktir.

    # 9. Verify
    step("8. Verifying APK signature")
    cmd = APKSIGNER_CMD + ["verify", "--verbose", out_apk]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout)
    if res.returncode != 0:
        print("apksigner verify failed:", res.stderr)
        sys.exit(1)

    shutil.rmtree(temp_dir, ignore_errors=True)
    print(f"Done! Release packaging for v{VERSION} complete.")


if __name__ == "__main__":
    main()
