# -*- mode: python ; coding: utf-8 -*-
# UYAP Evrak Yöneticisi — PyInstaller yapılandırması (Windows / Linux / macOS)
# Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır.
#
# Çıktı (dist/UYAPEvrak/):
#   UYAPEvrak(.exe)        -> pencereli uygulama (katalog arayüzü, sağ tık PDF dönüştürücü)
#   UYAPEvrakKonsol(.exe)  -> konsollu sürüm (İşlemlerim, duruşma takvimi, komut satırı araçları)
#   runtime/jre/           -> (CI ekler) gömülü Java çalışma ortamı — UDF -> PDF için
#   fonts/                 -> (CI ekler) Liberation yazı tipleri — Linux/macOS'ta Times/Arial uyumlu
#   uyap/*.class           -> UDF -> PDF dönüştürücü sınıfları
# Not: Havelsan UYAP Editör kütüphaneleri (editor_*.jar) lisanslıdır, pakete KONMAZ; uygulama
#      kullanıcının UYAP Editör kurulumunu veya veri klasöründeki jars/ klasörünü kullanır.
import os
import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent
ICON_WIN = str(ROOT / "assets" / "uyap_evrak.ico")
ICON_MAC = str(ROOT / "assets" / "uyap_evrak.icns")

datas = [
    (str(ROOT / "uyap"), "uyap"),
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "README.md"), "."),
    (str(ROOT / "LICENSE"), "."),
]
for extra in ("fonts",):
    if (ROOT / extra).is_dir():
        datas.append((str(ROOT / extra), extra))

hidden = [
    "katalog_gui", "evrak_katalog", "evrak_turleri", "donusturucu", "sag_tik", "gui_ekler",
    "uyap_indirici", "tebligat_yoneticisi", "enrich_and_rename_documents",
    "PIL.Image", "PIL.ImageSequence", "pypdf", "websocket", "requests", "sqlite3",
]

a = Analysis(
    [str(ROOT / "uygulama.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hidden,
    excludes=["playwright", "pydantic", "numpy", "pandas", "matplotlib", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

common = dict(
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    icon=ICON_MAC if sys.platform == "darwin" else ICON_WIN,
    version=str(ROOT / "packaging" / "windows" / "version_info.txt") if os.name == "nt" else None,
)
exe_gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name="UYAPEvrak", console=False, **common)
exe_cli = EXE(pyz, a.scripts, [], exclude_binaries=True, name="UYAPEvrakKonsol", console=True, **common)

coll = COLLECT(exe_gui, exe_cli, a.binaries, a.datas, strip=False, upx=False, name="UYAPEvrak")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="UYAP Evrak Yöneticisi.app",
        icon=ICON_MAC,
        bundle_identifier="tr.av.cankizilyar.uyapevrak",
        info_plist={
            "CFBundleDisplayName": "UYAP Evrak Yöneticisi",
            "CFBundleShortVersionString": "3.0.0",
            "NSHumanReadableCopyright": "© 2026 Av. Can KIZILYAR. Tüm hakları saklıdır.",
            "NSHighResolutionCapable": True,
        },
    )
