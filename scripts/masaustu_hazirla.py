#!/usr/bin/env python3
"""Masaüstü paketine gömülecekleri hazırlar: kullanıcı Java, Python veya kart sürücüsü KURMAZ.

1. Gömülü Java (jlink, küçültülmüş JRE)
   - Resmî Adalet E-İmza'yı çalıştırır: kart PC/SC + işletim sisteminin kendi CCID sürücüsüyle,
     karta doğrudan APDU ile okunur → AKİS/ArkSigner PKCS#11 sürücüsü gerekmez.
   - Hukuk Asistanı görevleri (UDF→PDF dönüştürme) de bu Java'yı kullanır.
   Çıktı: src-tauri/eimza/jre (Windows, Linux) · src-tauri/eimza/jre-<mimari> (macOS universal)
2. Hukuk Asistanı sunucusu (PyInstaller, scripts/asistan_paketle.py) → src-tauri/sidecar/asistan-sunucu-<mimari>
3. Gömülü görünmez tarayıcı (Chrome for Testing: chrome-headless-shell + uyumlu chromedriver)
   → src-tauri/tarayici-<mimari>/{chrome/, chromedriver}. Penceresi yoktur; UETS ve UYAP otomasyonu
   kullanıcının bilgisayarında Chrome kurulu olmasa da arka planda çalışır.

Kullanım (JDK 21 ve Python 3 + asistan/requirements.txt + pyinstaller kurulu ortamda):
  python scripts/masaustu_hazirla.py                          # bu makinenin mimarisi
  python scripts/masaustu_hazirla.py --java-home /x64/jdk --mimari x86_64 --jre-ekli   # macOS Intel ek JRE
  python scripts/masaustu_hazirla.py --sadece java|asistan|tarayici
"""
from __future__ import annotations

import argparse
import io
import json
import os
import stat
import urllib.request
import zipfile
import platform
import shutil
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
EIMZA = KOK / "src-tauri" / "eimza"

# Adalet E-İmza (TÜBİTAK MA3) ve modül görevleri için gereken modüller
JRE_MODULLERI = [
    "java.base", "java.desktop", "java.smartcardio", "java.instrument", "java.logging", "java.management",
    "java.naming", "java.prefs", "java.sql", "java.xml", "java.net.http", "java.security.jgss", "java.security.sasl",
    "java.scripting", "java.xml.crypto", "java.transaction.xa", "jdk.crypto.cryptoki", "jdk.crypto.ec",
    "jdk.unsupported", "jdk.charsets", "jdk.localedata", "jdk.zipfs", "jdk.naming.dns", "jdk.management",
    "jdk.httpserver", "jdk.accessibility",
]


def mimari_adi(m: str | None = None) -> str:
    m = (m or platform.machine()).lower()
    return {"amd64": "x86_64", "x64": "x86_64", "arm64": "aarch64"}.get(m, m)


def jre_hazirla(java_home: Path, hedef: Path) -> None:
    jlink = java_home / "bin" / ("jlink.exe" if os.name == "nt" else "jlink")
    if not jlink.is_file():
        raise SystemExit(f"jlink bulunamadı: {jlink} (JDK 21 gerekir; --java-home ile gösterin)")
    moduller = list(JRE_MODULLERI)
    if sys.platform == "win32":
        moduller.append("jdk.crypto.mscapi")  # Windows sertifika deposu (yalnız Windows JDK'sında var)
    if hedef.exists():
        shutil.rmtree(hedef)
    subprocess.run([str(jlink), "--add-modules", ",".join(moduller), "--include-locales=tr,en", "--strip-debug",
                    "--no-header-files", "--no-man-pages", "--compress=zip-6", "--output", str(hedef)], check=True)
    java = hedef / "bin" / ("java.exe" if os.name == "nt" else "java")
    r = subprocess.run([str(java), "-version"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit(f"Gömülü Java çalışmadı: {r.stderr}")
    # Kart katmanı yüklenebiliyor mu (CI'da okuyucu yok; yalnız sınıfın varlığı denetlenir)
    r = subprocess.run([str(java), "--list-modules"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if "java.smartcardio" not in r.stdout:
        raise SystemExit("Gömülü Java'da java.smartcardio yok")
    boyut = sum(f.stat().st_size for f in hedef.rglob("*") if f.is_file()) / 1_048_576
    print(f"[masaustu_hazirla] JRE hazır: {hedef} ({boyut:.0f} MB)")


CFT_JSON = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"


def cft_platformu(mimari: str) -> str:
    if sys.platform == "win32":
        return "win64"
    if sys.platform == "darwin":
        return "mac-arm64" if mimari == "aarch64" else "mac-x64"
    return "linux-arm64" if mimari == "aarch64" else "linux64"


def _indir_ac(url: str, hedef: Path) -> Path:
    """Zip'i indirip açar; tek üst klasörün içini hedefe taşır, çalıştırma izinlerini korur."""
    with urllib.request.urlopen(url, timeout=600) as r:
        veri = r.read()
    with zipfile.ZipFile(io.BytesIO(veri)) as z:
        for bilgi in z.infolist():
            parca = Path(bilgi.filename).parts[1:]  # "chrome-headless-shell-linux64/..." üst klasörünü at
            if not parca:
                continue
            yol = hedef.joinpath(*parca)
            if bilgi.is_dir():
                yol.mkdir(parents=True, exist_ok=True)
                continue
            yol.parent.mkdir(parents=True, exist_ok=True)
            yol.write_bytes(z.read(bilgi))
            mod = (bilgi.external_attr >> 16) & 0o777
            if mod:
                yol.chmod(mod)
            elif os.name != "nt" and "." not in yol.name:
                yol.chmod(yol.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return hedef


def tarayici_hazirla(mimari: str) -> None:
    plat = cft_platformu(mimari)
    with urllib.request.urlopen(CFT_JSON, timeout=60) as r:
        kanal = json.load(r)["channels"]["Stable"]
    adres = {t: next(x["url"] for x in kanal["downloads"][t] if x["platform"] == plat)
             for t in ("chrome-headless-shell", "chromedriver")}
    for u in adres.values():
        if not u.startswith("https://storage.googleapis.com/chrome-for-testing-public/"):
            raise SystemExit(f"Beklenmeyen indirme adresi: {u}")
    kok = KOK / "src-tauri" / f"tarayici-{mimari}"
    if kok.exists():
        shutil.rmtree(kok)
    _indir_ac(adres["chrome-headless-shell"], kok / "chrome")
    gecici = _indir_ac(adres["chromedriver"], kok / "_surucu")
    uz = ".exe" if sys.platform == "win32" else ""
    shutil.move(str(gecici / f"chromedriver{uz}"), str(kok / f"chromedriver{uz}"))
    shutil.rmtree(gecici)
    # Yalnız Türkçe ve İngilizce dil paketleri kalsın (~50 MB tasarruf)
    for pak in (kok / "chrome" / "locales").glob("*.pak"):
        if pak.stem not in ("tr", "en-US"):
            pak.unlink()
    (kok / "SURUM").write_text(kanal["version"] + "\n", encoding="utf-8")
    kabuk = kok / "chrome" / f"chrome-headless-shell{uz}"
    if not kabuk.is_file():
        raise SystemExit(f"chrome-headless-shell bulunamadı: {kabuk}")
    surucu = kok / f"chromedriver{uz}"
    r = subprocess.run([str(surucu), "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    if r.returncode != 0 or kanal["version"].split(".")[0] not in r.stdout:
        raise SystemExit(f"chromedriver çalışmadı / sürüm uyuşmuyor: {r.stdout} {r.stderr}")
    boyut = sum(f.stat().st_size for f in kok.rglob("*") if f.is_file()) / 1_048_576
    print(f"[masaustu_hazirla] Tarayıcı hazır: Chrome for Testing {kanal['version']} ({plat}) {boyut:.0f} MB")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--java-home", default=os.environ.get("JAVA_HOME"), help="JDK 21 dizini (varsayılan: JAVA_HOME)")
    ap.add_argument("--mimari", default=None, help="x86_64 | aarch64")
    ap.add_argument("--sadece", choices=["java", "asistan", "tarayici"], default=None)
    ap.add_argument("--tkintersiz", action="store_true")
    a = ap.parse_args()
    mimari = mimari_adi(a.mimari)

    if a.sadece in (None, "java"):
        if not a.java_home:
            raise SystemExit("JAVA_HOME tanımlı değil (JDK 21)")
        # macOS universal pakette iki mimari yan yana durur; diğerlerinde tek "jre"
        hedef = EIMZA / (f"jre-{mimari}" if sys.platform == "darwin" else "jre")
        jre_hazirla(Path(a.java_home), hedef)

    if a.sadece in (None, "tarayici"):
        tarayici_hazirla(mimari)

    if a.sadece in (None, "asistan"):
        komut = [sys.executable, str(KOK / "scripts" / "asistan_paketle.py"), "--mimari", mimari]
        if a.tkintersiz:
            komut.append("--tkintersiz")
        subprocess.run(komut, check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
