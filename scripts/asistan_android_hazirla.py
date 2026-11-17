#!/usr/bin/env python3
"""Hukuk Asistanı sunucusunu Android'de TERMUX OLMADAN çalıştıracak çalışma zamanını hazırlar.

UYAP Mobil'in (scripts/uyapmobil_hazirla.py) Java için kullandığı yöntemin aynısı: standart Linux aarch64
(glibc) programları, APK'ya gömülen Termux glibc'sinin yükleyicisiyle (ld-linux-aarch64.so.1) doğrudan
başlatılır. targetSdkVersion 28 olduğundan uygulama dizininden çalıştırma serbesttir.

Bileşenler (hepsi sabit SHA-256 ile doğrulanır):
  * CPython 3.12 aarch64-unknown-linux-gnu (astral-sh/python-build-standalone, install_only_stripped)
  * Asistan bağımlılıkları: manylinux aarch64 tekerlekleri (pip --platform; derleme yok)
    Android'de tarayıcı otomasyonu yoktur → Selenium alınmaz; UETS/UYAP indirme görevleri masaüstündedir.
  * Termux glibc (yalnız Python ve tekerleklerin DT_NEEDED ile istediği kitaplıklar, özyinelemeli)
  * asistan/sunucu.py + asistan/moduller
Çıktı: build/asistan-android/{asistan-rt-arm64.zip, surum.txt}  → APK assets/asistan/

Doğrulama: qemu-aarch64 varsa çalışma zamanı, Android'deki başlatma komutunun AYNISIYLA (yükleyici +
--library-path) çalıştırılıp her bağımlılık içe aktarılır ve sunucu /api/merhaba'ya yanıt verir.

Kullanım: python3 scripts/asistan_android_hazirla.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / "scripts"))
import uyapmobil_hazirla as um  # noqa: E402  (indir, deb_veri, elf_gerekenler, gerceklestir, glibc deposu)

CIKTI = KOK / "build" / "asistan-android"
PBS_ETIKET = "20261110"
PBS_AD = f"cpython-3.12.16+{PBS_ETIKET}-aarch64-unknown-linux-gnu-install_only_stripped.tar.gz"
PBS_URL = f"https://github.com/astral-sh/python-build-standalone/releases/download/{PBS_ETIKET}/{PBS_AD}"
PBS_SHA = "b6a41defec4975d94b4ff1950236e7383e5c02ba40ea48c9ec33c66087a35aab"
PY_SURUM = "3.12"

# Android'de kullanılacak bağımlılıklar (tarayıcı otomasyonu hariç)
ANDROID_BAGIMLILIKLAR = ["requests>=2.28", "sqlalchemy>=2.0,<2.1", "openpyxl>=3.1", "pypdf>=3.0", "pillow>=10",
                         "reportlab>=4.0", "websocket-client>=1.5"]
GLIBC_PAKETLERI = ["glibc", "gcc-libs-glibc", "zlib-glibc"]
# İçe aktarma duman testi (Android'de sunucu ve görevlerin kullandığı modüller)
DUMAN_IMPORTLARI = ["ssl", "sqlite3", "zlib", "lzma", "bz2", "ctypes", "hashlib", "json", "email.mime.multipart",
                    "requests", "sqlalchemy", "openpyxl", "pypdf", "PIL.Image", "reportlab.pdfgen.canvas", "websocket",
                    "certifi", "imaplib", "smtplib", "csv", "zipfile", "xml.etree.ElementTree"]


def adim(m):
    print(f"== {m}", flush=True)


def python_indir(hedef: Path) -> None:
    adim("CPython aarch64 (python-build-standalone)")
    arsiv = um.indir(PBS_URL, PBS_SHA, PBS_AD)
    if hedef.exists():
        shutil.rmtree(hedef)
    hedef.mkdir(parents=True)
    with tarfile.open(arsiv) as t:
        t.extractall(hedef.parent / "_pbs", filter="tar")
    shutil.move(str(hedef.parent / "_pbs" / "python"), str(hedef / "python"))
    shutil.rmtree(hedef.parent / "_pbs")
    # Gereksiz: başlık dosyaları, test paketi, tkinter/idle (Android'de pencere yok)
    py = hedef / "python"
    for alt in ["include", "share", f"lib/python{PY_SURUM}/test", f"lib/python{PY_SURUM}/idlelib",
                f"lib/python{PY_SURUM}/tkinter", f"lib/python{PY_SURUM}/turtledemo", f"lib/python{PY_SURUM}/ensurepip",
                f"lib/python{PY_SURUM}/lib2to3"]:
        shutil.rmtree(py / alt, ignore_errors=True)
    for f in py.glob("lib/libtcl*"):
        f.unlink()
    for f in py.glob("lib/libtk*"):
        f.unlink()
    # _tkinter: Android'de pencere yok · _crypt: kullanılmıyor (3.13'te kaldırıldı), libcrypt.so.1 ister
    for kalip in ("_tkinter*", "_crypt*"):
        for f in (py / f"lib/python{PY_SURUM}/lib-dynload").glob(kalip):
            f.unlink()


def bagimliliklar(site: Path) -> None:
    adim("manylinux aarch64 tekerlekleri")
    if site.exists():
        shutil.rmtree(site)
    komut = [sys.executable, "-m", "pip", "install", "--quiet", "--no-compile", "--target", str(site),
             "--python-version", PY_SURUM, "--implementation", "cp", "--only-binary=:all:",
             "--platform", "manylinux2014_aarch64", "--platform", "manylinux_2_28_aarch64",
             "--platform", "manylinux_2_17_aarch64", *ANDROID_BAGIMLILIKLAR]
    subprocess.run(komut, check=True)
    for p in list(site.rglob("__pycache__")):
        shutil.rmtree(p, ignore_errors=True)
    shutil.rmtree(site / "bin", ignore_errors=True)


def glibc_topla(rt: Path) -> None:
    adim("Termux glibc kitaplıkları")
    ham = CIKTI / "_glibc_ham"
    um.GLIBC_PAKETLER[:] = GLIBC_PAKETLERI
    um.glibc_paketleri(str(ham))
    cikis = rt / "glibc"
    if cikis.exists():
        shutil.rmtree(cikis)
    cikis.mkdir(parents=True)
    # Kendi .so'larını taşıyan dizinler: bunlardaki adlar glibc'den alınmaz
    yerel = {f.name for f in rt.rglob("*.so*") if "glibc" not in f.parts}
    kuyruk = [str(f) for f in rt.rglob("*") if f.is_file() and (f.suffix == ".so" or ".so." in f.name or f.name == f"python{PY_SURUM}")]
    secilen = {"ld-linux-aarch64.so.1"}
    shutil.copyfile(um.gerceklestir(str(ham), "ld-linux-aarch64.so.1"), cikis / "ld-linux-aarch64.so.1")
    # Python'un dlopen ile yüklediği ad çözümleme kitaplıkları (DT_NEEDED'de görünmez)
    for ad in ("libnss_files.so.2", "libnss_dns.so.2", "libresolv.so.2", "libutil.so.1", "libgcc_s.so.1"):
        g = um.gerceklestir(str(ham), ad)
        if g:
            shutil.copyfile(g, cikis / ad)
            secilen.add(ad)
            kuyruk.append(str(cikis / ad))
    eksik = set()
    while kuyruk:
        yol = kuyruk.pop()
        for ad in um.elf_gerekenler(yol):
            # "$ORIGIN/../lib/libpython3.12.so.1.0" gibi yol içeren kayıtlar paketin kendi dosyasıdır
            if "/" in ad:
                ad = ad.rsplit("/", 1)[1]
            if ad in secilen or ad in yerel:
                continue
            g = um.gerceklestir(str(ham), ad)
            if not g:
                eksik.add(f"{ad} ({Path(yol).name})")
                continue
            shutil.copyfile(g, cikis / ad)
            secilen.add(ad)
            kuyruk.append(str(cikis / ad))
    if eksik:
        raise SystemExit("çözülemeyen glibc bağımlılıkları: " + ", ".join(sorted(eksik)))
    print(f"   {len(secilen)} kitaplık: {', '.join(sorted(secilen))}", flush=True)


def uygulama_kopyala(rt: Path) -> None:
    adim("asistan sunucusu ve modüller")
    app = rt / "app"
    if app.exists():
        shutil.rmtree(app)
    shutil.copytree(KOK / "asistan", app, ignore=shutil.ignore_patterns("__pycache__", "testler", "*.pyc"))


def android_komutu(rt: Path, *arg) -> list[str]:
    """Android'deki AsistanServisi.java ile AYNI başlatma biçimi."""
    lib = f"{rt / 'glibc'}:{rt / 'python' / 'lib'}"
    return [str(rt / "glibc" / "ld-linux-aarch64.so.1"), "--library-path", lib,
            str(rt / "python" / "bin" / f"python{PY_SURUM}"), *arg]


def android_ortami(rt: Path, veri: Path) -> dict:
    return {"PATH": "/usr/bin:/bin", "HOME": str(veri), "TMPDIR": str(veri), "LANG": "C.UTF-8",
            "PYTHONHOME": str(rt / "python"), "PYTHONPATH": str(rt / "site"), "PYTHONDONTWRITEBYTECODE": "1",
            "SSL_CERT_FILE": str(rt / "site" / "certifi" / "cacert.pem"), "CANASISTAN_VERI": str(veri),
            "CANASISTAN_ANDROID": "1", "CANASISTAN_PYTHON_KOMUT": json.dumps(android_komutu(rt))}


def qemu_dogrula(rt: Path) -> None:
    qemu = shutil.which("qemu-aarch64") or shutil.which("qemu-aarch64-static")
    if not qemu:
        print("   (qemu-aarch64 yok: doğrulama atlandı)")
        return
    adim("qemu-aarch64 ile doğrulama (Android başlatma komutunun aynısı)")
    veri = CIKTI / "_dogrulama"
    shutil.rmtree(veri, ignore_errors=True)
    veri.mkdir(parents=True)
    env = android_ortami(rt, veri)
    kod = "import " + ", ".join(DUMAN_IMPORTLARI) + "; import sys; print('IMPORT TAMAM', sys.version.split()[0])"
    r = subprocess.run([qemu, *android_komutu(rt, "-c", kod)], env=env, capture_output=True, text=True, timeout=600)
    print("  ", (r.stdout or r.stderr).strip()[-400:])
    if r.returncode != 0:
        raise SystemExit("Android çalışma zamanı içe aktarma testi başarısız")
    p = subprocess.Popen([qemu, *android_komutu(rt, str(rt / "app" / "sunucu.py"), "--port", "8797")], env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(120):
            time.sleep(1)
            try:
                with urllib.request.urlopen("http://127.0.0.1:8797/api/merhaba", timeout=2) as y:
                    print("   sunucu:", y.read().decode())
                    break
            except OSError:
                if p.poll() is not None:
                    raise SystemExit("sunucu başlamadı:\n" + (p.stdout.read() if p.stdout else ""))
        else:
            raise SystemExit("sunucu 120 sn içinde yanıt vermedi")
    finally:
        p.terminate()


def main() -> int:
    CIKTI.mkdir(parents=True, exist_ok=True)
    rt = CIKTI / "rt"
    python_indir(rt)
    bagimliliklar(rt / "site")
    uygulama_kopyala(rt)
    glibc_topla(rt)
    qemu_dogrula(rt)
    adim("zip")
    zp = CIKTI / "asistan-rt-arm64.zip"
    zp.unlink(missing_ok=True)
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(rt.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                bilgi = zipfile.ZipInfo.from_file(f, f.relative_to(rt).as_posix())
                bilgi.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(bilgi, f.read_bytes())
    surum = hashlib.sha256(zp.read_bytes()).hexdigest()[:16]
    (CIKTI / "surum.txt").write_text(surum + "\n", encoding="utf-8")
    print(f"[asistan_android] hazır: {zp} ({zp.stat().st_size / 1_048_576:.0f} MB) sürüm {surum}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
