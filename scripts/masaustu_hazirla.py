#!/usr/bin/env python3
"""Masaüstü paketine gömülecekleri hazırlar: kullanıcı Java, Python veya kart sürücüsü KURMAZ.

1. Gömülü Java (jlink, küçültülmüş JRE)
   - Resmî Adalet E-İmza'yı çalıştırır: kart PC/SC + işletim sisteminin kendi CCID sürücüsüyle,
     karta doğrudan APDU ile okunur → AKİS/ArkSigner PKCS#11 sürücüsü gerekmez.
   - Hukuk Asistanı görevleri (UDF→PDF dönüştürme) de bu Java'yı kullanır.
   Çıktı: src-tauri/eimza/jre (Windows, Linux) · src-tauri/eimza/jre-<mimari> (macOS universal)
2. Hukuk Asistanı sunucusu (PyInstaller, scripts/asistan_paketle.py) → src-tauri/sidecar/asistan-sunucu-<mimari>

Kullanım (JDK 21 ve Python 3 + asistan/requirements.txt + pyinstaller kurulu ortamda):
  python scripts/masaustu_hazirla.py                          # bu makinenin mimarisi
  python scripts/masaustu_hazirla.py --java-home /x64/jdk --mimari x86_64 --jre-ekli   # macOS Intel ek JRE
  python scripts/masaustu_hazirla.py --sadece java|asistan
"""
from __future__ import annotations

import argparse
import os
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
    r = subprocess.run([str(java), "-version"], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"Gömülü Java çalışmadı: {r.stderr}")
    # Kart katmanı yüklenebiliyor mu (CI'da okuyucu yok; yalnız sınıfın varlığı denetlenir)
    r = subprocess.run([str(java), "--list-modules"], capture_output=True, text=True)
    if "java.smartcardio" not in r.stdout:
        raise SystemExit("Gömülü Java'da java.smartcardio yok")
    boyut = sum(f.stat().st_size for f in hedef.rglob("*") if f.is_file()) / 1_048_576
    print(f"[masaustu_hazirla] JRE hazır: {hedef} ({boyut:.0f} MB)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--java-home", default=os.environ.get("JAVA_HOME"), help="JDK 21 dizini (varsayılan: JAVA_HOME)")
    ap.add_argument("--mimari", default=None, help="x86_64 | aarch64")
    ap.add_argument("--sadece", choices=["java", "asistan"], default=None)
    ap.add_argument("--tkintersiz", action="store_true")
    a = ap.parse_args()
    mimari = mimari_adi(a.mimari)

    if a.sadece in (None, "java"):
        if not a.java_home:
            raise SystemExit("JAVA_HOME tanımlı değil (JDK 21)")
        # macOS universal pakette iki mimari yan yana durur; diğerlerinde tek "jre"
        hedef = EIMZA / (f"jre-{mimari}" if sys.platform == "darwin" else "jre")
        jre_hazirla(Path(a.java_home), hedef)

    if a.sadece in (None, "asistan"):
        komut = [sys.executable, str(KOK / "scripts" / "asistan_paketle.py"), "--mimari", mimari]
        if a.tkintersiz:
            komut.append("--tkintersiz")
        subprocess.run(komut, check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
