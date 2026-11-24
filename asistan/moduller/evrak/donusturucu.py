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


def _paket_koku() -> Path:
    """asistan/ kökü (kaynak ağacında: moduller/evrak'ın iki üstü). EN: the asistan/ root."""
    return Path(__file__).resolve().parents[2]


def jars_dir() -> Path | None:
    """Resmî Havelsan UYAP Editör kütüphaneleri (editor_lib.jar, editor_lib2.jar, editor_utility.jar, jai_hvl.jar...).

    v4.10.0: jar'lar artık depoya ve tüm masaüstü paketlerine GÖMÜLÜDÜR (asistan/jars/uyap-editor). Arama sırası:
      1. UYAP_JARS / CANASISTAN_UYAP_JARS (kullanıcının seçtiği ya da CanEditor'un indirdiği güncel editör)
      2. CANASISTAN_PAKET_JARS (Tauri: paket içi kopya) ve kaynak ağacındaki asistan/jars/uyap-editor
      3. Kurulu UYAP Editör klasörleri (Windows Program Files, /usr/share/UYAPEditor, Termux ~/jars)
    EN: official jars are bundled; user-provided/newer editor installs still take precedence."""
    cands: list[Path] = []
    for k in ("UYAP_JARS", "CANASISTAN_UYAP_JARS", "CANASISTAN_PAKET_JARS"):
        v = os.environ.get(k)
        if v:
            cands.append(Path(v))
    cands += [_paket_koku() / "jars" / "uyap-editor"]
    cands += list(_candidates("jars", "uyap-editor")) + list(_candidates("jars"))
    home = Path.home()
    cands += [home / ".uyap_evrak" / "jars", home / "UYAPEditorModern" / "jars", home / "UYAPEditorModern",
              Path("/data/data/com.termux/files/home/jars"), Path("/usr/share/UYAPEditor"), Path("/opt/UYAPEditor")]
    for env_dir in (os.environ.get("LOCALAPPDATA"), os.environ.get("APPDATA")):
        if env_dir:
            ed = Path(env_dir)
            cands += [ed / "UYAPEditorModern", ed / "UYAPEditorModern" / "jars",
                      ed / "com.caneditor.app" / "uyap-editor" / "editor",
                      ed / "CanEditor" / "uyap-editor" / "editor"]
    for pf in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA"), "C:\\"):
        if pf:
            for name in ("UYAP Editor", "UYAP Editör", "UYAPEditor", "UYAP\\UYAP Editor", "Uyap", "UYAP"):
                cands += [Path(pf) / name / "lib", Path(pf) / name / "jars", Path(pf) / name]
    for c in cands:
        try:
            if c and c.is_dir() and (c / "editor_lib.jar").is_file():
                return c
        except OSError:
            continue
    return None


def font_dirs() -> list[str]:
    """Times New Roman / Arial TTF klasörleri. Paket içi asistan/fonts HER ZAMAN ilk sıradadır; böylece Java
    motoru fontu JVM'e kaydeder ve PDF'e gömer (bkz. UdfBatchPdfConverter.registerAwtFonts)."""
    out: list[str] = []
    for c in [os.environ.get("CANASISTAN_FONTS"), str(_paket_koku() / "fonts"),
              *[str(c) for c in _candidates("fonts")],
              str(_paket_koku().parent / "frontend" / "public" / "fonts")]:
        if c and os.path.isdir(c) and c not in out:
            out.append(c)
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


_RL_FONTLAR: dict | None = None


def _reportlab_fontlari() -> dict:
    """ReportLab'a Türkçe glifli TTF'leri kaydeder. Helvetica (Type1, Latin-1) ş/ğ/ı/İ çizemediği için eski
    yedek motor Türkçe harfleri kara kutu yapıyordu. EN: register Turkish-capable TTFs (was Helvetica)."""
    global _RL_FONTLAR
    if _RL_FONTLAR is not None:
        return _RL_FONTLAR
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.fonts import addMapping
    aileler = {
        "Times New Roman": {"normal": ("timesnewroman.ttf", "times.ttf"), "bold": ("timesbd.ttf",),
                            "italic": ("timesi.ttf",), "bolditalic": ("timesbi.ttf",)},
        "Arial": {"normal": ("arial.ttf",), "bold": ("arialbd.ttf",), "italic": ("ariali.ttf",),
                  "bolditalic": ("arialbi.ttf",)},
    }
    dosyalar: dict[str, str] = {}
    for d in font_dirs():
        try:
            for f in os.listdir(d):
                dosyalar.setdefault(f.lower(), os.path.join(d, f))
        except OSError:
            pass
    sonuc: dict = {}
    for aile, stiller in aileler.items():
        kayit = {}
        for stil, adlar in stiller.items():
            yol = next((dosyalar[a] for a in adlar if a in dosyalar), None)
            if not yol:
                continue
            ad = f"{aile.replace(' ', '')}-{stil}"
            try:
                pdfmetrics.registerFont(TTFont(ad, yol))
                kayit[stil] = ad
            except Exception:
                pass
        if "normal" in kayit:
            for stil in ("bold", "italic", "bolditalic"):
                kayit.setdefault(stil, kayit["normal"])
            addMapping(kayit["normal"], 0, 0, kayit["normal"])
            addMapping(kayit["normal"], 1, 0, kayit["bold"])
            addMapping(kayit["normal"], 0, 1, kayit["italic"])
            addMapping(kayit["normal"], 1, 1, kayit["bolditalic"])
            sonuc[aile] = kayit
    _RL_FONTLAR = sonuc
    return sonuc


def udf_python_to_pdf(path: Path, dst: Path | None = None) -> Path | None:
    """YEDEK motor: Java yoksa UDF'i saf Python (ReportLab) ile A4 PDF'e çevirir.

    v4.10.0'da baştan yazıldı. Eski sürüm content.xml'deki TÜM düğüm metinlerini tek paragraf olarak
    Helvetica ile basıyordu: satır sonları kayboluyor, Türkçe harfler bozuluyor, hizalama/kalın/italik yok
    sayılıyordu ("PDF bozuk çevriliyor" şikâyeti). Şimdi Havelsan UDF şeması okunur:
      * <content><![CDATA[...]]>  belge metni; <paragraph><content startOffset length .../> parçaları
        (ofsetler UTF-16 kod birimidir — Java String indeksleri; emoji vb. için vekil çiftler sayılır)
      * Alignment (0 sol, 1 orta, 2 sağ, 3 iki yana), LeftIndent, RightIndent, FirstLineIndent,
        SpaceAbove/SpaceBelow, LineSpacing, bold/italic/underline/size/family, <table><row><cell>
      * <pageFormat> kenar boşlukları ve yönü
    EN: rewritten fallback that honours the UDF offset model, paragraph attributes, tables and TTF fonts."""
    path = Path(path)
    if not path.is_file():
        return None
    dst = Path(dst) if dst else path.with_suffix(".pdf")
    try:
        import html as _html
        import zipfile
        import xml.etree.ElementTree as ET
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors

        with zipfile.ZipFile(path, "r") as z:
            root = ET.fromstring(z.read("content.xml"))
        metin_el = root.find("content")
        ham = (metin_el.text or "") if metin_el is not None else ""
        u16 = ham.encode("utf-16-le")

        def dilim(bas: int, uz: int) -> str:
            # UTF-16 ofsetleri → Python dizesi (Array.from/rune değil; Havelsan Java char indeksi kullanır)
            return u16[2 * bas: 2 * (bas + uz)].decode("utf-16-le", errors="replace")

        fontlar = _reportlab_fontlari()

        def aile_ad(aile: str, kalin: bool = False, egik: bool = False) -> str | None:
            a = (aile or "").lower()
            if "arial" in a or "sans" in a or "dialog" in a or "calibri" in a:
                k = fontlar.get("Arial") or fontlar.get("Times New Roman") or {}
            else:
                k = fontlar.get("Times New Roman") or fontlar.get("Arial") or {}
            stil = ("bold" if kalin else "") + ("italic" if egik else "") or "normal"
            return k.get(stil) or k.get("normal")

        varsayilan_font = aile_ad("Times New Roman") or "Times-Roman"
        hiz = {"0": TA_LEFT, "1": TA_CENTER, "2": TA_RIGHT, "3": TA_JUSTIFY}

        def f(e, ad, vars_=0.0):
            try:
                return float(e.get(ad, vars_))
            except (TypeError, ValueError):
                return vars_

        def paragraf(pe) -> Paragraph | None:
            parcalar = []
            boyut_max = 0.0
            for c in list(pe):
                if c.tag not in ("content", "field", "space", "tab"):
                    continue
                if c.get("startOffset") is None:
                    t = c.text or ""
                else:
                    t = dilim(int(c.get("startOffset", 0)), int(c.get("length", 0)))
                t = t.replace("\r", "").replace("\n", "")
                if c.tag == "tab":
                    t = "\t"
                if not t:
                    continue
                boyut = f(c, "size", f(pe, "size", 12.0)) or 12.0
                boyut_max = max(boyut_max, boyut)
                esc = _html.escape(t).replace("\t", "&nbsp;" * 8).replace("  ", "&nbsp; ")
                kalin, egik = c.get("bold") == "true", c.get("italic") == "true"
                fn = aile_ad(c.get("family") or pe.get("family") or "Times New Roman", kalin, egik)
                if fn:
                    esc = f'<font name="{fn}" size="{boyut:g}">{esc}</font>'
                else:  # TTF bulunamadı: yerleşik Times ailesi + <b>/<i>
                    esc = f'<font size="{boyut:g}">{esc}</font>'
                    esc = f"<b>{esc}</b>" if kalin else esc
                    esc = f"<i>{esc}</i>" if egik else esc
                if c.get("underline") == "true":
                    esc = f"<u>{esc}</u>"
                parcalar.append(esc)
            boyut_max = boyut_max or (f(pe, "size", 12.0) or 12.0)
            satir = f(pe, "LineSpacing", 0.0)
            stil = ParagraphStyle(
                "udf", fontName=varsayilan_font, fontSize=boyut_max,
                leading=boyut_max * (1.15 + max(0.0, satir)),
                alignment=hiz.get(str(pe.get("Alignment", "0")), TA_LEFT),
                leftIndent=f(pe, "LeftIndent"), rightIndent=f(pe, "RightIndent"),
                firstLineIndent=f(pe, "FirstLineIndent"),
                spaceBefore=f(pe, "SpaceAbove"), spaceAfter=f(pe, "SpaceBelow"),
            )
            return Paragraph("".join(parcalar) or "&nbsp;", stil)

        hikaye = []
        elements = root.find("elements")
        for e in (list(elements) if elements is not None else []):
            if e.tag == "paragraph":
                hikaye.append(paragraf(e))
            elif e.tag == "table":
                satirlar = []
                for row in e.findall("row"):
                    satirlar.append([[paragraf(p) for p in cell.findall("paragraph")] or [""]
                                     for cell in row.findall("cell")])
                if satirlar:
                    genislik = max(len(r) for r in satirlar)
                    satirlar = [r + [[""]] * (genislik - len(r)) for r in satirlar]
                    t = Table(satirlar, repeatRows=0)
                    if e.get("border", "borderCell") != "borderNone":
                        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
                    hikaye.append(t)
        if not hikaye and ham.strip():
            # elements yoksa (eski/standart dışı UDF): satır satır düz metin
            st = ParagraphStyle("duz", fontName=varsayilan_font, fontSize=12, leading=14)
            hikaye = [Paragraph(_html.escape(s) or "&nbsp;", st) for s in ham.split("\n")]
        if not hikaye:
            for pe in root.iter("paragraph"):  # E-İmza One örnekleri gibi CDATA'sız biçim
                for c in pe:
                    if c.text:
                        hikaye.append(Paragraph(_html.escape(c.text), ParagraphStyle(
                            "x", fontName=varsayilan_font, fontSize=f(c, "fontSize", 12.0) or 12,
                            alignment=hiz.get(str(pe.get("alignment", "0")), TA_LEFT))))
        if not hikaye:
            hikaye.append(Spacer(1, 1))

        pf = root.find("properties/pageFormat")
        kb = lambda ad, v=42.525: f(pf, ad, v) if pf is not None else v  # noqa: E731
        sayfa = landscape(A4) if pf is not None and pf.get("paperOrientation") == "2" else A4
        tmp = dst.with_name(dst.name + ".part")
        doc = SimpleDocTemplate(str(tmp), pagesize=sayfa, leftMargin=kb("leftMargin"), rightMargin=kb("rightMargin"),
                                topMargin=kb("topMargin"), bottomMargin=kb("bottomMargin"),
                                title=path.stem, creator="CanEditor (yedek PDF motoru)")
        doc.build(hikaye)
        os.replace(tmp, dst)
        if dst.exists() and dst.stat().st_size > 0:
            _gunluk(f"[yedek-motor] {path.name} → ReportLab ile PDF ({'TTF' if fontlar else 'Times-Roman'})")
            return dst
    except Exception as e:
        _gunluk(f"[!] udf_python_to_pdf hatası ({path}): {e}")
    return None


def _gunluk(mesaj: str) -> None:
    """Dönüştürücü günlüğü: konsola ve (varsa) CanEditor öz-denetim günlüğüne. EN: converter log."""
    print(mesaj, file=sys.stderr)
    try:
        sys.path.insert(0, str(_paket_koku()))
        import oz_denetim  # type: ignore
        oz_denetim.kaydet("donusturucu", mesaj)
    except Exception:
        pass


def udf_to_pdf(path: Path, dst=None, timeout: int = 120, **_eski) -> Path | None:
    """Tek UDF dosyasını veya bir klasördeki tüm UDF'leri PDF'e dönüştürür.

    v4.10.0 düzeltmeleri (bozuk PDF şikâyeti):
      * İkinci konumsal argüman artık HEDEF yoludur. sunucu.py `udf_to_pdf(p, pdf_p)` diye çağırıyordu ama eski
        imza (path, timeout) olduğu için Path timeout sanılıyor, subprocess TypeError veriyor, hata yutuluyor ve
        HER UDF bozuk yedek motora düşüyordu. Geriye uyum: ikinci argüman int ise timeout kabul edilir.
      * Java motoru (resmî Havelsan + gömülü TTF) başarısız olursa nedeni günlüğe yazılır; yedek motor ancak o
        zaman ve ayrıca günlüklenerek devreye girer.
    EN: 2nd positional arg is the destination (was silently treated as timeout → always the lossy fallback)."""
    if isinstance(dst, (int, float)) and not isinstance(dst, bool):
        timeout, dst = int(dst), None
    path = Path(path)
    dst = Path(dst) if dst else None
    java, jars = java_exe(), jars_dir()
    if java and jars:
        classes = next((str(c) for c in _candidates() if (c / "uyap" / "UdfBatchPdfConverter.class").exists()), str(BASE_DIR))
        env = dict(os.environ)
        fd = font_dirs()
        if fd:
            env["UYAP_FONT_DIR"] = os.pathsep.join(fd + ([env["UYAP_FONT_DIR"]] if env.get("UYAP_FONT_DIR") else []))
        hedef_ayri = bool(dst and path.is_file() and dst.resolve() != path.with_suffix(".pdf").resolve())
        kaynak = path
        tmpdir = None
        if hedef_ayri:
            import tempfile
            tmpdir = tempfile.mkdtemp(prefix="caneditor_udf_")
            kaynak = Path(tmpdir) / path.name
            shutil.copy2(path, kaynak)
        cmd = [java, "-Xmx768m", "-Djava.awt.headless=true", "-Dfile.encoding=UTF-8",
               "--add-opens=java.base/java.util=ALL-UNNAMED", "--add-opens=java.base/java.lang=ALL-UNNAMED",
               "--add-opens=java.desktop/java.awt=ALL-UNNAMED", "--add-opens=java.desktop/javax.swing=ALL-UNNAMED",
               "-cp", f"{classes}{os.pathsep}{jars / '*'}", "uyap.UdfBatchPdfConverter", "--force", str(kaynak)]
        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=timeout, env=env,
                                 **_NO_WINDOW)
            hata = "\n".join(l for l in (res.stderr or b"").decode("utf-8", "replace").splitlines()
                             if l.strip() and not l.startswith("Picked up "))
            if hata:
                _gunluk(f"[java] {path.name}: {hata[-600:]}")
            uretilen = kaynak.with_suffix(".pdf")
            if kaynak.is_file() and uretilen.exists() and uretilen.stat().st_size > 0:
                if hedef_ayri:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(uretilen), str(dst))
                    return dst
                return uretilen
            if path.is_dir() and res.returncode == 0:
                return path
        except subprocess.TimeoutExpired:
            _gunluk(f"[java] {path.name}: {timeout} sn zaman aşımı")
        except Exception as e:
            _gunluk(f"[java] {path.name}: çalıştırılamadı: {e}")
        finally:
            if tmpdir:
                shutil.rmtree(tmpdir, ignore_errors=True)
    else:
        _gunluk(f"[uyarı] Java={'var' if java else 'YOK'}, UYAP jar={'var' if jars else 'YOK'} → yedek motor")

    # Java yoksa veya başarısız olduysa: Saf Python ReportLab yedek motoru (günlüklenir)
    if path.is_file():
        return udf_python_to_pdf(path, dst)
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
