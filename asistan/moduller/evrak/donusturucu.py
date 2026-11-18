#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UYAP Evrak Yöneticisi — PDF Dönüştürücü
Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır.

Desteklenen biçimler ve yöntem:
  * .udf            -> Havelsan UYAP Editör motoru (Java, uyap.UdfBatchPdfConverter). Yazı tipleri PDF'e gömülür.
  * .tif / .tiff    -> Pillow ile çok sayfalı, A4 boyutlu PDF (yatay sayfalar yatay A4).
  * .jpg/.jpeg/.png/.bmp/.gif -> Pillow ile A4 PDF.
  * .docx/.doc/.rtf/.odt -> Microsoft Word (Windows, COM) varsa Word ile; yoksa LibreOffice (soffice) ile.
  * .pdf            -> zaten PDF, dokunulmaz.

PDF, kaynağın yanına AYNI ADLA (.pdf uzantısıyla) yazılır; var olan PDF'in üzerine yazılmaz.
Komut satırı:  python donusturucu.py dosya1.udf dosya2.tif klasör/ ...
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

UDF = {".udf"}
TIFF = {".tif", ".tiff"}
IMG = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
OFFICE = {".docx", ".doc", ".rtf", ".odt"}
DESTEKLENEN = UDF | TIFF | IMG | OFFICE
A4_PX = (1654, 2339)  # 200 dpi
_NO_WINDOW = {"creationflags": 0x08000000} if os.name == "nt" else {}


# ---------------------------------------------------------------------------
# Java / Havelsan kütüphaneleri / yazı tipleri
# ---------------------------------------------------------------------------
def _candidates(*parts):
    for root in (APP_DIR, BASE_DIR, APP_DIR.parent):
        yield root.joinpath(*parts)


def java_exe() -> str | None:
    """Önce paketle gelen JRE (runtime/jre), sonra JAVA_HOME, sonra PATH."""
    exe = "java.exe" if os.name == "nt" else "java"
    for c in _candidates("runtime", "jre", "bin", exe):
        if c.exists():
            return str(c)
    jh = os.environ.get("JAVA_HOME")
    if jh and (Path(jh) / "bin" / exe).exists():
        return str(Path(jh) / "bin" / exe)
    return shutil.which("java")


def jars_dir() -> Path | None:
    """Havelsan UYAP Editör kütüphaneleri (lisanslı olduğu için depoda/pakette bulunmaz).
    Arama sırası: UYAP_JARS ortam değişkeni, uygulama klasöründeki jars/, kullanıcı ayar klasörü,
    UYAP Editör kurulum klasörleri, Termux ev dizini."""
    env = os.environ.get("UYAP_JARS")
    cands = [Path(env)] if env else []
    cands += list(_candidates("jars"))
    home = Path.home()
    cands += [home / ".uyap_evrak" / "jars", home / "UYAPEditorModern" / "jars", home / "UYAPEditorModern",
              Path("/data/data/com.termux/files/home/jars")]
    for env_dir in (os.environ.get("LOCALAPPDATA"), os.environ.get("APPDATA")):
        if env_dir:
            ed = Path(env_dir)
            cands += [ed / "UYAPEditorModern", ed / "UYAPEditorModern" / "jars",
                      ed / "com.caneditor.app" / "uyap-editor" / "editor",
                      ed / "CanEditor" / "uyap-editor" / "editor"]
    for pf in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA"), r"C:\\"):
        if pf:
            for name in ("UYAP Editor", "UYAP Editör", "UYAPEditor", "UYAP\\UYAP Editor", "Uyap", "UYAP"):
                cands += [Path(pf) / name / "lib", Path(pf) / name / "jars", Path(pf) / name]
    for c in cands:
        try:
            if c and c.is_dir() and any(c.glob("editor*.jar")):
                return c
        except OSError:
            continue
    return None


def font_dirs() -> list[str]:
    out = [str(c) for c in _candidates("fonts") if c.is_dir()]
    if os.name == "nt":
        out.append(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    return out


def udf_hazir_mi() -> tuple[bool, str]:
    if java_exe() and jars_dir():
        return True, ""
    try:
        import reportlab
        return True, ""
    except ImportError:
        return False, "Java veya ReportLab kütüphanesi bulunamadı."


def udf_python_to_pdf(path: Path, dst: Path | None = None) -> Path | None:
    """Java olmadan, saf Python (ReportLab) ile UDF'i yüksek uyumlu A4 PDF'e dönüştürür."""
    path = Path(path)
    if not path.is_file():
        return None
    if dst is None:
        dst = path.with_suffix(".pdf")
    try:
        import zipfile
        import xml.etree.ElementTree as ET
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors

        with zipfile.ZipFile(path, 'r') as z:
            xml_bytes = z.read('content.xml')
        root = ET.fromstring(xml_bytes)

        styles = getSampleStyleSheet()
        normal = styles['Normal']
        normal.fontName = 'Helvetica'
        normal.fontSize = 11
        normal.leading = 14
        normal.textColor = colors.HexColor('#212121')

        story = []
        for elem in root.iter():
            txt = (elem.text or '').strip()
            if txt:
                clean_txt = txt.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(clean_txt, normal))
                story.append(Spacer(1, 6))

        if not story:
            story.append(Paragraph("Belge boş.", normal))

        doc = SimpleDocTemplate(str(dst), pagesize=A4, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=50)
        doc.build(story)
        if dst.exists() and dst.stat().st_size > 0:
            return dst
    except Exception as e:
        print(f"[!] udf_python_to_pdf hatası ({path}): {e}")
    return None


def udf_to_pdf(path: Path, timeout: int = 120) -> Path | None:
    """Tek UDF dosyasını veya bir klasördeki tüm UDF'leri (PDF'i olmayanları) dönüştürür."""
    path = Path(path)
    java, jars = java_exe(), jars_dir()
    if java and jars:
        classes = next((str(c) for c in _candidates() if (c / "uyap" / "UdfBatchPdfConverter.class").exists()), str(BASE_DIR))
        env = dict(os.environ)
        fd = font_dirs()
        if fd:
            env["UYAP_FONT_DIR"] = os.pathsep.join(fd + ([env["UYAP_FONT_DIR"]] if env.get("UYAP_FONT_DIR") else []))
        cmd = [java, "-Xmx512m", "-Djava.awt.headless=true", "-Dfile.encoding=UTF-8",
               "--add-opens=java.base/java.util=ALL-UNNAMED", "--add-opens=java.base/java.lang=ALL-UNNAMED",
               "--add-opens=java.desktop/java.awt=ALL-UNNAMED", "--add-opens=java.desktop/javax.swing=ALL-UNNAMED",
               "-cp", f"{classes}{os.pathsep}{jars / '*'}", "uyap.UdfBatchPdfConverter", str(path)]
        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout, env=env, **_NO_WINDOW)
            if res.returncode == 0:
                pdf = path.with_suffix(".pdf")
                if path.is_file() and pdf.exists() and pdf.stat().st_size > 0:
                    return pdf
                if path.is_dir():
                    return path
        except Exception:
            pass

    # Java yoksa veya başarısız olduysa: Saf Python ReportLab motoru ile dönüştür
    if path.is_file():
        return udf_python_to_pdf(path)
    if path.is_dir():
        for f in path.rglob("*.udf"):
            pdf_f = f.with_suffix(".pdf")
            if not pdf_f.exists() or pdf_f.stat().st_size == 0:
                udf_python_to_pdf(f, pdf_f)
        return path
    return None


# ---------------------------------------------------------------------------
# Görüntü -> PDF
# ---------------------------------------------------------------------------
def images_to_pdf(src: Path) -> Path | None:
    """TIF/TIFF (çok sayfalı) ve diğer görüntüleri A4 boyutlu PDF'e çevirir."""
    try:
        from PIL import Image, ImageSequence
    except ImportError:
        return None
    dst = src.with_suffix(".pdf")
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    pages = []
    try:
        with Image.open(src) as im:
            for frame in ImageSequence.Iterator(im):
                fr = frame.copy()
                fr = fr.convert("L" if fr.mode in ("1", "L", "P", "LA", "I;16", "I") else "RGB")
                w, h = fr.size
                pw, ph = (A4_PX[1], A4_PX[0]) if w > h else A4_PX
                scale = min(pw / w, ph / h)
                nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
                fr = fr.resize((nw, nh), Image.LANCZOS)
                page = Image.new(fr.mode, (pw, ph), 255 if fr.mode == "L" else (255, 255, 255))
                page.paste(fr, ((pw - nw) // 2, (ph - nh) // 2))
                pages.append(page)
        if not pages:
            return None
        tmp = dst.with_name(dst.name + ".part")
        pages[0].save(tmp, "PDF", resolution=200.0, save_all=True, append_images=pages[1:])
        tmp.replace(dst)
        return dst
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Office -> PDF
# ---------------------------------------------------------------------------
def office_to_pdf(src: Path, timeout: int = 180) -> Path | None:
    dst = src.with_suffix(".pdf")
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    if os.name == "nt":
        ps = (
            "$ErrorActionPreference='Stop';"
            "$w=New-Object -ComObject Word.Application;$w.Visible=$false;$w.DisplayAlerts=0;"
            "try{$d=$w.Documents.Open($env:SRC,$false,$true);$d.SaveAs([ref]$env:DST,[ref]17);$d.Close([ref]0)}"
            "finally{$w.Quit()}"
        )
        try:
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                           env=dict(os.environ, SRC=str(src), DST=str(dst)), timeout=timeout,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **_NO_WINDOW)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if dst.exists() and dst.stat().st_size > 0:
            return dst
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    for c in (r"C:\Program Files\LibreOffice\program\soffice.exe", "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        if not soffice and os.path.exists(c):
            soffice = c
    if soffice:
        try:
            subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(src.parent), str(src)],
                           timeout=timeout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **_NO_WINDOW)
        except (OSError, subprocess.TimeoutExpired):
            pass
    return dst if dst.exists() and dst.stat().st_size > 0 else None


# ---------------------------------------------------------------------------
# Toplu dönüştürme
# ---------------------------------------------------------------------------
def collect(paths) -> list[Path]:
    out = []
    for p in paths:
        p = Path(p).expanduser().resolve()  # Word/LibreOffice göreli yolu kendi klasörüne göre çözer
        if p.is_dir():
            out += [f for f in sorted(p.rglob("*")) if f.suffix.lower() in DESTEKLENEN]
        elif p.suffix.lower() in DESTEKLENEN:
            out.append(p)
    seen, uniq = set(), []
    for f in out:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    return uniq


def convert(path: Path) -> tuple[str, Path | None, str]:
    """Tek dosya: (durum, pdf, mesaj) — durum: 'tamam' | 'vardi' | 'hata' | 'desteklenmiyor'."""
    ext = path.suffix.lower()
    pdf = path.with_suffix(".pdf")
    if pdf.exists() and pdf.stat().st_size > 0:
        return "vardi", pdf, "PDF zaten var"
    if ext in UDF:
        ok, msg = udf_hazir_mi()
        if not ok:
            return "hata", None, msg
        res = udf_to_pdf(path)
    elif ext in TIFF | IMG:
        res = images_to_pdf(path)
    elif ext in OFFICE:
        res = office_to_pdf(path)
        if not res:
            return "hata", None, "Word veya LibreOffice bulunamadı / dönüştüremedi"
    else:
        return "desteklenmiyor", None, ext
    return ("tamam", res, "") if res else ("hata", None, "dönüştürülemedi")


def convert_many(paths, progress=None) -> dict:
    files = collect(paths)
    stats = {"tamam": 0, "vardi": 0, "hata": 0, "desteklenmiyor": 0, "hatalar": []}
    for i, f in enumerate(files, 1):
        if progress:
            progress(i - 1, len(files), f.name)
        st, _pdf, msg = convert(f)
        stats[st] += 1
        if st == "hata":
            stats["hatalar"].append(f"{f.name}: {msg}")
    if progress:
        progress(len(files), len(files), "")
    stats["toplam"] = len(files)
    return stats


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print(__doc__)
        sys.exit(1)
    r = convert_many(args, progress=lambda d, t, n: print(f"[{d}/{t}] {n}") if n else None)
    print(f"Bitti: {r['tamam']} dönüştürüldü, {r['vardi']} zaten vardı, {r['hata']} hata.")
    for h in r["hatalar"]:
        print("  -", h)
