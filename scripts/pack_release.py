import os
import sys
import glob
import shutil
import zipfile
import subprocess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BUILD_TOOLS = r"C:\Users\C\AppData\Local\Android\Sdk\build-tools\30.0.3"
PLATFORM_JAR = r"C:\Users\C\AppData\Local\Android\Sdk\platforms\android-34\android.jar"
JAVA_HOME = r"C:\Program Files\Microsoft\jdk-14.0.2"
JAVAC = os.path.join(JAVA_HOME, "bin", "javac.exe")
JAVA = os.path.join(JAVA_HOME, "bin", "java.exe")
KEYTOOL = os.path.join(JAVA_HOME, "bin", "keytool.exe")
AAPT = os.path.join(BUILD_TOOLS, "aapt.exe")
ZIPALIGN = os.path.join(BUILD_TOOLS, "zipalign.exe")
D8_JAR = os.path.join(BUILD_TOOLS, "lib", "d8.jar")
APKSIGNER_JAR = os.path.join(BUILD_TOOLS, "lib", "apksigner.jar")

def step(msg):
    print("=" * 60)
    print(msg)
    print("=" * 60)

def main():
    os.chdir(PROJECT_ROOT)
    os.makedirs("release", exist_ok=True)
    temp_dir = os.path.join(PROJECT_ROOT, "temp_build")
    shutil.rmtree(temp_dir, ignore_errors=True)
    os.makedirs(temp_dir, exist_ok=True)

    # 1. Portable Web GUI zip
    step("1. Building Portable Web GUI zip v3.4.8")
    zip_path = os.path.join("release", "CanEditor-Portable-Web-GUI-v3.4.8.zip")
    if os.path.exists(zip_path):
        os.remove(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for fname in ["desktop_bridge.js", "editor.css", "editor.js", "favicon.svg", "history.js", "icons.svg", "jszip.min.js", "updater.js"]:
            p = os.path.join("frontend", "public", fname)
            if os.path.exists(p):
                z.write(p, arcname=fname)
                print(f"  Added {fname}")
        index_p = os.path.join("frontend", "index.html")
        z.write(index_p, arcname="index.html")
        print("  Added index.html")
    print(f"Created {zip_path} ({os.path.getsize(zip_path)} bytes)")

    # 2. Compile Java classes
    step("2. Compiling Java classes with javac")
    classes_dir = os.path.join(temp_dir, "classes")
    os.makedirs(classes_dir, exist_ok=True)
    java_files = glob.glob("android/src/**/*.java", recursive=True) + glob.glob("android/gen/**/*.java", recursive=True)
    cmd = [
        JAVAC,
        "-encoding", "UTF-8",
        "-source", "8",
        "-target", "8",
        "-cp", PLATFORM_JAR,
        "-d", classes_dir
    ] + java_files
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("javac failed:", res.stderr)
        sys.exit(1)
    print("javac completed successfully.")

    # 3. Run D8 to generate classes.dex
    step("3. Generating classes.dex with D8")
    dex_dir = os.path.join(temp_dir, "dex")
    os.makedirs(dex_dir, exist_ok=True)
    class_files = glob.glob(f"{classes_dir}/**/*.class", recursive=True)
    cmd = [
        JAVA,
        "-cp", D8_JAR,
        "com.android.tools.r8.D8",
        "--lib", PLATFORM_JAR,
        "--output", dex_dir
    ] + class_files
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("D8 failed:", res.stderr)
        sys.exit(1)
    dex_file = os.path.join(dex_dir, "classes.dex")
    print(f"classes.dex generated ({os.path.getsize(dex_file)} bytes).")

    # 4. Generate base APK with aapt
    step("4. Packaging base APK with aapt")
    unaligned_apk = os.path.join(temp_dir, "unaligned.apk")
    cmd = [
        AAPT,
        "package", "-f", "-m",
        "-M", "android/AndroidManifest.xml",
        "-S", "android/res",
        "-I", PLATFORM_JAR,
        "-F", unaligned_apk,
        "-A", "android/assets"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("aapt failed:", res.stderr)
        sys.exit(1)
    print("Base APK created.")

    # 5. Add classes.dex to base APK
    step("5. Adding classes.dex to APK")
    cmd = [AAPT, "add", unaligned_apk, "classes.dex"]
    # Run in dex_dir so classes.dex is added at root
    res = subprocess.run(cmd, cwd=dex_dir, capture_output=True, text=True)
    if res.returncode != 0:
        print("aapt add failed:", res.stderr)
        sys.exit(1)
    print("classes.dex added.")

    # 6. Zipalign
    step("6. Aligning APK with zipalign")
    aligned_apk = os.path.join(temp_dir, "aligned.apk")
    cmd = [ZIPALIGN, "-f", "-p", "4", unaligned_apk, aligned_apk]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("zipalign failed:", res.stderr)
        sys.exit(1)
    print("APK aligned.")

    # 7. Check or create debug.keystore
    keystore_path = os.path.join(PROJECT_ROOT, "debug.keystore")
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
    out_apk = os.path.join("release", "CanEditor-v3.4.8.apk")
    cmd = [
        JAVA,
        "-jar", APKSIGNER_JAR,
        "sign",
        "--ks", keystore_path,
        "--ks-pass", "pass:android",
        "--ks-key-alias", "androiddebugkey",
        "--key-pass", "pass:android",
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

    # 9. Verify
    step("8. Verifying APK signature")
    cmd = [JAVA, "-jar", APKSIGNER_JAR, "verify", "--verbose", out_apk]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout)
    if res.returncode != 0:
        print("apksigner verify failed:", res.stderr)
        sys.exit(1)

    # Clean up temp
    shutil.rmtree(temp_dir, ignore_errors=True)
    print("Done! Release packaging complete.")

if __name__ == "__main__":
    main()
