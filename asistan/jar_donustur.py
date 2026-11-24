#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CanEditor Birleşik JAR Dönüştürme Motoru
========================================
Tamamen resmî Havelsan UYAP Editör JAR'larındaki metodları kullanarak
(.udf → .pdf / .odt / .docx) birebir vektörel dönüşüm yapar; görsel/TIFF/PDF
dosyalarını NAPS2 A4 motoruyla UYAP uyumlu A4 PDF'e çevirir.

Kullanılan Havelsan JAR sınıfları:
  * tr.com.havelsan.uyap.system.editor.b.b     — iText vektörel PDF motoru (+ TrueType font gömme)
  * tr.com.havelsan.uyap.system.editor.b.a.f   — ODFDOM ODT dışa aktarım motoru
  * tr.com.havelsan.uyap.system.editor.common.gui.lo / text.J — DocumentEx yükleyici
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KOK = Path(__file__).resolve().parent
PROJE_KOK = KOK.parent
_NO_WINDOW = {"creationflags": 0x08000000} if os.name == "nt" else {}


def _moduller_koku() -> Path:
    d = os.environ.get("CANASISTAN_VERI")
    if d and (Path(d) / "moduller").is_dir():
        return Path(d) / "moduller"
    return KOK / "moduller"


def java_yolu() -> str | None:
    exe = "java.exe" if os.name == "nt" else "java"
    for env_key in ("CANASISTAN_JAVA_HOME", "JAVA_HOME"):
        jh = os.environ.get(env_key)
        if jh:
            p = Path(jh) / "bin" / exe
            if p.is_file():
                return str(p)
    # Gömülü JRE adayları
    for aday in (
        PROJE_KOK / "src-tauri" / "eimza" / "jre" / "bin" / exe,
        KOK / "runtime" / "jre" / "bin" / exe,
    ):
        if aday.is_file():
            return str(aday)
    return shutil.which("java")


def jar_dizini() -> Path | None:
    """Resmî Havelsan UYAP Editör JAR klasörünü bulur."""
    adaylar: list[Path] = []
    # v4.10.0: paket içi resmî jar'lar (asistan/jars/uyap-editor) her zaman son çaredir; kullanıcının
    # indirdiği/kurduğu daha yeni editör önceliklidir. EN: bundled official jars as guaranteed fallback.
    for env_key in ("UYAP_JARS", "CANASISTAN_UYAP_JARS", "CANASISTAN_PAKET_JARS"):
        v = os.environ.get(env_key)
        if v:
            adaylar.append(Path(v))
    home = Path.home()
    adaylar += [
        home / ".uyap_evrak" / "jars",
        home / "UYAPEditorModern",
        home / "UYAPEditorModern" / "jars",
        Path("/data/data/com.termux/files/home/jars"),
        Path("/usr/share/uyapeditor/editor"),
        Path("/opt/uyapeditor/editor"),
    ]
    for env_dir in (os.environ.get("LOCALAPPDATA"), os.environ.get("APPDATA")):
        if env_dir:
            ed = Path(env_dir)
            adaylar += [
                ed / "UYAPEditorModern",
                ed / "UYAPEditorModern" / "jars",
                ed / "com.caneditor.app" / "uyap-editor" / "editor",
                ed / "CanEditor" / "uyap-editor" / "editor",
            ]
    for pf in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), r"C:\\"):
        if pf:
            for ad in ("UYAP Editor", "UYAP Editör", "UYAPEditor", "UYAP\\UYAP Editor", "Uyap", "UYAP"):
                adaylar += [Path(pf) / ad / "lib", Path(pf) / ad / "jars", Path(pf) / ad]
    adaylar.append(KOK / "jars" / "uyap-editor")
    for d in adaylar:
        try:
            if d and d.is_dir() and (d / "editor_lib.jar").is_file():
                return d
        except OSError:
            continue
    return None


def _exporter_jar() -> Path | None:
    m = _moduller_koku()
    for aday in (
        m / "a4" / "java" / "uyap-exporter.jar",
        KOK / "moduller" / "a4" / "java" / "uyap-exporter.jar",
    ):
        if aday.is_file():
            return aday
    return None


def _batch_class_root() -> Path | None:
    m = _moduller_koku()
    for aday in (m / "evrak", KOK / "moduller" / "evrak"):
        if (aday / "uyap" / "UdfBatchPdfConverter.class").is_file():
            return aday
    return None


def _font_dizinleri() -> list[str]:
    out = []
    for aday in (
        Path(os.environ["CANASISTAN_FONTS"]) if os.environ.get("CANASISTAN_FONTS") else KOK / "fonts",
        KOK / "fonts",
        PROJE_KOK / "frontend" / "public" / "fonts",
        PROJE_KOK / "android" / "assets" / "editor" / "fonts",
        KOK / "fonts",
    ):
        if aday.is_dir():
            out.append(str(aday))
    if os.name == "nt":
        wf = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        if wf.is_dir():
            out.append(str(wf))
    return out


def durum() -> dict:
    java = java_yolu()
    jars = jar_dizini()
    exp = _exporter_jar()
    batch = _batch_class_root()
    jar_listesi = sorted(p.name for p in jars.glob("*.jar")) if jars else []
    hazir = bool(java and jars and (exp or batch))
    return {
        "hazir": True if hazir else True,  # Python motoru her zaman hazır
        "java": java or "Saf Python (ReportLab) Etkin",
        "jars_dizini": str(jars) if jars else "Paket İçi Python Motoru",
        "jar_sayisi": len(jar_listesi),
        "exporter_jar": str(exp) if exp else "",
        "batch_sinif": str(batch) if batch else "",
        "desteklenen": ["pdf", "odt", "docx"] if hazir else ["pdf"],
        "uyari": "" if hazir else "Java kütüphaneleri bulunamadığında yerleşik Python ReportLab motoruyla A4 PDF üretilir.",
    }


def _java_calistir(cp_parcalari: list[str], sinif: str, args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    java = java_yolu()
    if not java:
        raise RuntimeError("Java çalışma zamanı bulunamadı.")
    env = dict(os.environ)
    fd = _font_dizinleri()
    if fd:
        mevcut = env.get("UYAP_FONT_DIR", "")
        env["UYAP_FONT_DIR"] = os.pathsep.join(fd + ([mevcut] if mevcut else []))
    cmd = [
        java,
        "-Xmx512m",
        "-Djava.awt.headless=true",
        "-Dfile.encoding=UTF-8",
        "--add-opens=java.base/java.util=ALL-UNNAMED",
        "--add-opens=java.base/java.lang=ALL-UNNAMED",
        "--add-opens=java.desktop/java.awt=ALL-UNNAMED",
        "--add-opens=java.desktop/javax.swing=ALL-UNNAMED",
        "-cp", os.pathsep.join(cp_parcalari),
        sinif,
        *args,
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
        **_NO_WINDOW,
    )


def udf_jar_donustur(girdi: Path, hedef_format: str, cikti: Path | None = None, timeout: int = 120) -> Path:
    """UDF dosyasını doğrudan resmî Havelsan JAR metodlarıyla PDF, ODT veya DOCX'e dönüştürür."""
    girdi = Path(girdi).resolve()
    if not girdi.is_file():
        raise FileNotFoundError(f"Girdi dosyası bulunamadı: {girdi}")
    fmt = hedef_format.lower().lstrip(".")
    if fmt not in ("pdf", "odt", "docx"):
        raise ValueError(f"Desteklenmeyen hedef biçim: {hedef_format} (desteklenen: pdf, odt, docx)")

    java = java_yolu()
    jars = jar_dizini()
    if not java or not jars:
        if fmt == "pdf":
            try:
                from moduller.evrak.donusturucu import udf_python_to_pdf
                if cikti is None:
                    cikti = girdi.with_suffix(".pdf")
                res = udf_python_to_pdf(girdi, cikti)
                if res and res.is_file():
                    return res
            except Exception as pe:
                raise RuntimeError(f"Python PDF dönüştürme hatası: {pe}")
        raise RuntimeError(durum()["uyari"] or "Java veya UYAP JAR kütüphaneleri eksik.")

    if cikti is None:
        cikti = girdi.with_suffix(f".{fmt}")
    else:
        cikti = Path(cikti).resolve()
    cikti.parent.mkdir(parents=True, exist_ok=True)

    jar_glob = str(jars / "*")
    exp = _exporter_jar()
    batch = _batch_class_root()

    # 1. PDF: önce font gömme destekli UdfBatchPdfConverter, yoksa UyapVectorExporter
    if fmt == "pdf":
        if batch and cikti == girdi.with_suffix(".pdf"):
            r = _java_calistir([str(batch), jar_glob], "uyap.UdfBatchPdfConverter", ["--force", str(girdi)], timeout=timeout)
            if r.returncode == 0 and cikti.is_file() and cikti.stat().st_size > 0:
                return cikti
        if exp:
            r = _java_calistir([str(exp), jar_glob], "uyap.UyapVectorExporter", ["pdf", str(girdi), str(cikti)], timeout=timeout)
            if r.returncode == 0 and cikti.is_file() and cikti.stat().st_size > 0:
                return cikti
            raise RuntimeError(f"JAR PDF dönüşümü başarısız: {(r.stderr or r.stdout)[-400:]}")
        if batch:
            # Farklı çıktı yolu istendiyse geçici kopyayla çevir
            with tempfile.TemporaryDirectory(prefix="caneditor_jar_") as td:
                tmp_in = Path(td) / girdi.name
                shutil.copy2(girdi, tmp_in)
                r = _java_calistir([str(batch), jar_glob], "uyap.UdfBatchPdfConverter", ["--force", str(tmp_in)], timeout=timeout)
                tmp_out = tmp_in.with_suffix(".pdf")
                if r.returncode == 0 and tmp_out.is_file() and tmp_out.stat().st_size > 0:
                    shutil.copy2(tmp_out, cikti)
                    return cikti
                raise RuntimeError(f"JAR PDF dönüşümü başarısız: {(r.stderr or r.stdout)[-400:]}")
        raise RuntimeError("UYAP PDF dönüştürücü sınıfı (uyap-exporter.jar / UdfBatchPdfConverter) bulunamadı.")

    # 2. ODT: resmî Havelsan ODFDOM motoru (UyapVectorExporter)
    if fmt == "odt":
        if not exp:
            raise RuntimeError("uyap-exporter.jar bulunamadı.")
        r = _java_calistir([str(exp), jar_glob], "uyap.UyapVectorExporter", ["odt", str(girdi), str(cikti)], timeout=timeout)
        if r.returncode == 0 and cikti.is_file() and cikti.stat().st_size > 0:
            return cikti
        raise RuntimeError(f"JAR ODT dönüşümü başarısız: {(r.stderr or r.stdout)[-400:]}")

    # 3. DOCX: Havelsan JAR ile ODT üret → scripts/odt_to_docx.py ile saf Python DOCX'e dönüştür (LibreOffice gerekmez)
    with tempfile.TemporaryDirectory(prefix="caneditor_docx_") as td:
        tmp_odt = Path(td) / (girdi.stem + ".odt")
        udf_jar_donustur(girdi, "odt", tmp_odt, timeout=timeout)
        odt_conv = PROJE_KOK / "scripts" / "odt_to_docx.py"
        if odt_conv.is_file():
            sys.path.insert(0, str(odt_conv.parent))
            import odt_to_docx  # type: ignore
            if hasattr(odt_to_docx, "convert_odt_to_docx"):
                odt_to_docx.convert_odt_to_docx(str(tmp_odt), str(cikti))
                if cikti.is_file() and cikti.stat().st_size > 0:
                    return cikti
        # Yedek: LibreOffice varsa kullan
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if soffice:
            subprocess.run([soffice, "--headless", "--convert-to", "docx", "--outdir", str(cikti.parent), str(tmp_odt)],
                           capture_output=True, timeout=timeout, **_NO_WINDOW)
            uretilen = cikti.parent / (tmp_odt.stem + ".docx")
            if uretilen.is_file():
                if uretilen != cikti:
                    shutil.move(str(uretilen), str(cikti))
                return cikti
        raise RuntimeError("ODT → DOCX dönüştürücü bulunamadı (scripts/odt_to_docx.py veya LibreOffice).")


def bayttan_donustur(dosya_adi: str, icerik: bytes, hedef_format: str) -> tuple[bytes, str, str]:
    """Ham dosya baytlarını (UDF / görsel / TIFF) JAR motoruyla hedef biçime dönüştürür.
    Döner: (cikti_bayt, cikti_dosya_adi, mime_turu)."""
    if not icerik:
        raise ValueError("Boş dosya gönderildi.")
    temiz_ad = Path(dosya_adi or "Belge.udf").name
    uz = Path(temiz_ad).suffix.lower()
    fmt = hedef_format.lower().lstrip(".")
    mime_map = {
        "pdf": "application/pdf",
        "odt": "application/vnd.oasis.opendocument.text",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    if fmt not in mime_map:
        raise ValueError(f"Desteklenmeyen hedef biçim: {hedef_format}")

    with tempfile.TemporaryDirectory(prefix="caneditor_conv_") as td:
        girdi = Path(td) / temiz_ad
        girdi.write_bytes(icerik)
        hedef = Path(td) / (girdi.stem + f".{fmt}")

        if uz == ".udf":
            sonuc = udf_jar_donustur(girdi, fmt, hedef)
        elif fmt == "pdf" and uz in (".tif", ".tiff", ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".pdf"):
            m = _moduller_koku()
            sys.path.insert(0, str(m / "a4" / "python"))
            import a4_pdf_engine  # type: ignore
            a4_pdf_engine.merge_all_to_single_pdf([str(girdi)], str(hedef))
            sonuc = hedef
        else:
            raise ValueError(f"{uz or 'Bu'} dosya türü {fmt.upper()} biçimine JAR motoruyla dönüştürülemiyor.")

        return sonuc.read_bytes(), sonuc.name, mime_map[fmt]
