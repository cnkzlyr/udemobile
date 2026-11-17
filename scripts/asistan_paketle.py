#!/usr/bin/env python3
"""Hukuk Asistanı sunucusunu Python KURULUMU GEREKTİRMEYEN tek klasörlük ikiliye çevirir (PyInstaller).

Çıktı: src-tauri/sidecar/asistan-sunucu-<mimari>/asistan-sunucu[.exe]  (+ _internal/)
  <mimari> Rust'taki std::env::consts::ARCH ile aynıdır: x86_64 | aarch64
  Tauri bunu kaynak (resource) olarak pakete koyar; src-tauri/src/asistan.rs çalışma anında seçer.

Modüller (asistan/moduller) pakete veri olarak girer ve görevler "<ikili> --calistir betik.py" ile
aynı ikiliyle çalışır. Bu yüzden modüllerin içe aktardığı her üçüncü taraf ve standart kütüphane paketi
ikiliye gömülmelidir: liste kaynak koddan (ast) otomatik çıkarılır, elle tutulmaz.

Kullanım (önce: pip install -r asistan/requirements.txt pyinstaller):
  python scripts/asistan_paketle.py
  python scripts/asistan_paketle.py --mimari x86_64     # macOS'ta Rosetta Python'u ile Intel paketi
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
ASISTAN = KOK / "asistan"
MODULLER = ASISTAN / "moduller"

# Veri dosyası/ikili taşıyan paketler: yalnızca modülü değil her şeyini topla
TUMUNU_TOPLA = ["selenium", "certifi", "reportlab", "openpyxl", "pypdf", "PIL", "sqlalchemy", "pydantic",
                "websocket", "requests", "charset_normalizer", "tkinter"]
# Derleme ortamında bulunsa da gömülmeyecekler (çok büyük ya da yalnızca geliştirme amaçlı)
HARIC = {"playwright", "pytest", "PyInstaller", "setuptools", "pip", "IPython", "matplotlib", "numpy", "pandas",
         "scipy", "mypy", "ast_serialize", "telethon", "jupyter", "notebook"}


def mimari_adi(m: str | None = None) -> str:
    m = (m or platform.machine()).lower()
    return {"amd64": "x86_64", "x64": "x86_64", "x86_64": "x86_64", "arm64": "aarch64", "aarch64": "aarch64"}.get(m, m)


def yerel_adlar() -> set[str]:
    """Modüllerin kendi dosya ve paket adları (bunlar kaynak olarak gelir, gömülmez)."""
    adlar = set()
    for f in MODULLER.rglob("*.py"):
        adlar.add(f.stem)
        for p in f.relative_to(MODULLER).parts[:-1]:
            adlar.add(p)
    return adlar


def ice_aktarimlar() -> list[str]:
    """Modül kaynaklarındaki tüm import'lar, TAM noktalı adlarıyla (ör. email.mime.multipart).

    Yalnızca üst düzey adı ('email') vermek yetmez: PyInstaller alt modülleri kendiliğinden eklemez."""
    yerel, bulunan = yerel_adlar(), set()
    for f in MODULLER.rglob("*.py"):
        try:
            agac = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for d in ast.walk(agac):
            if isinstance(d, ast.Import):
                bulunan.update(a.name for a in d.names)
            elif isinstance(d, ast.ImportFrom) and d.module and d.level == 0:
                bulunan.add(d.module)
                # "from paket import alt" — alt bir alt modül olabilir
                bulunan.update(f"{d.module}.{a.name}" for a in d.names if a.name != "*")
    sonuc = []
    for ad in sorted(bulunan):
        ust = ad.split(".")[0]
        if ust in yerel or ust in HARIC:
            continue
        try:
            if importlib.util.find_spec(ad) is not None:
                sonuc.append(ad)
        except (ImportError, ValueError, AttributeError):
            pass
    return sonuc


def duman_testi(exe: Path, gizli: list[str], veri: Path, tkinter_var: bool) -> None:
    """Python'suz ortamda: ikili açılır mı, modüllerin her import'u yüklenir mi, görev betikleri başlar mı?"""
    if veri.exists():
        shutil.rmtree(veri)
    veri.mkdir(parents=True)
    # PATH'ten Python'u çıkar: ikili kendi gömülü yorumlayıcısıyla çalışmalı
    yol = os.pathsep.join(p for p in os.environ.get("PATH", "").split(os.pathsep)
                          if not (Path(p) / ("python.exe" if os.name == "nt" else "python3")).exists())
    env = dict(os.environ, CANASISTAN_VERI=str(veri), PATH=yol)
    env.pop("PYTHONPATH", None)

    def calis(argv, cwd=None):
        r = subprocess.run([str(exe), *argv], capture_output=True, text=True, timeout=180, env=env, cwd=cwd)
        if r.returncode != 0:
            print(r.stdout[-3000:], r.stderr[-3000:])
            raise SystemExit(f"[asistan_paketle] duman testi başarısız: {' '.join(argv)}")
        return r

    if not calis(["--anahtar"]).stdout.strip():
        raise SystemExit("[asistan_paketle] anahtar üretilemedi")
    betik = veri / "ice_aktar.py"
    satirlar = [f"import {ad}" for ad in gizli if tkinter_var or not ad.startswith("tkinter")]
    betik.write_text("\n".join(satirlar) + "\nprint('TAMAM', len(%r))\n" % satirlar, encoding="utf-8")
    calis(["--calistir", str(betik)])
    moduller = veri / "moduller"
    gorevler = [("avukatasistan", "main.py"), ("evrak", "uyap_watcher.py")]
    if tkinter_var:
        gorevler.append(("evrak", "uyap_indirici.py"))
    for klasor, ad in gorevler:
        calis(["--calistir", ad, "--help"], cwd=moduller / klasor)
    print(f"[asistan_paketle] duman testi geçti: {len(satirlar)} import, {len(gorevler)} görev betiği")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mimari", default=None, help="x86_64 | aarch64 (varsayılan: bu makine)")
    ap.add_argument("--tkintersiz", action="store_true", help="tkinter yoksa da devam et (pencereli görevler çalışmaz)")
    a = ap.parse_args()
    if importlib.util.find_spec("tkinter") is None:
        if not a.tkintersiz:
            raise SystemExit("[asistan_paketle] Bu Python'da tkinter yok; Avukat Asistanı ve Evrak Kataloğu pencereleri "
                             "pakette çalışmaz. tkinter'lı bir Python kullanın (python.org / actions/setup-python).")
        print("[asistan_paketle] UYARI: tkinter yok, pencereli görevler bu pakette çalışmayacak")
    mimari = mimari_adi(a.mimari)
    hedef = KOK / "src-tauri" / "sidecar" / f"asistan-sunucu-{mimari}"
    is_dizini = KOK / "build" / f"pyinstaller-{mimari}"
    dagitim = is_dizini / "dist"

    gizli = ice_aktarimlar()
    print(f"[asistan_paketle] mimari={mimari} · gömülecek import sayısı: {len(gizli)}")

    komut = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
             "--name", "asistan-sunucu", "--distpath", str(dagitim), "--workpath", str(is_dizini / "work"),
             "--specpath", str(is_dizini),
             "--add-data", f"{MODULLER}{os.pathsep}moduller",
             ]
    for ad in sorted(HARIC):
        komut += ["--exclude-module", ad]
    for ad in gizli:
        komut += ["--hidden-import", ad]
    if os.name != "nt":
        komut.append("--strip")  # hata ayıklama sembollerini at (libpython vb. küçülür)
    for ad in TUMUNU_TOPLA:
        if importlib.util.find_spec(ad) is not None:
            komut += ["--collect-all", ad]
    komut.append(str(ASISTAN / "sunucu.py"))
    subprocess.run(komut, check=True)

    # Test ve önbellek dosyaları pakete gerekmez
    for p in (dagitim / "asistan-sunucu").rglob("__pycache__"):
        if "moduller" in p.parts:
            shutil.rmtree(p, ignore_errors=True)
    # Selenium her işletim sistemi için sürücü yöneticisi taşır; yalnızca bu platformunki kalsın
    bu_os = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    for d in (dagitim / "asistan-sunucu").rglob("selenium-manager*"):
        if d.parent.name in {"windows", "macos", "linux"} and d.parent.name != bu_os:
            shutil.rmtree(d.parent, ignore_errors=True)

    if hedef.exists():
        shutil.rmtree(hedef)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(dagitim / "asistan-sunucu", hedef, symlinks=True)
    exe = hedef / ("asistan-sunucu.exe" if os.name == "nt" else "asistan-sunucu")
    # Duman testi: ikili açılıyor ve gömülü bağımlılıkları görüyor mu?
    duman_testi(exe, gizli, is_dizini / "duman", tkinter_var=importlib.util.find_spec("tkinter") is not None)
    boyut = sum(f.stat().st_size for f in hedef.rglob("*") if f.is_file()) / 1_048_576
    print(f"[asistan_paketle] hazır: {hedef} ({boyut:.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
