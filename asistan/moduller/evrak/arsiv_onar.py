#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UYAP arşivi PDF onarımı — bozuk ve eksik PDF'leri resmî Havelsan motoruyla BİREBİR yeniden üretir
==================================================================================================

TR: 24.11.2026 öncesi PDF'ler resmî UYAP Editör motoruyla (iText 2.1.7, Times New Roman gömülü) üretiliyordu.
    Bir dönem dönüştürücü hatası yüzünden PDF'ler yedek ReportLab motoruna düştü: Helvetica, gömülmemiş font,
    Türkçe harfler "■", tüm metin tek paragraf, 2-3 KB. Bu araç arşivin TAMAMINI tarar:

      Kaynak                          Bozuk/eksik sayılan                       Yapılan
      ─────────────────────────────── ───────────────────────────────────────── ─────────────────────────────────
      Katalogdaki her UDF/TIFF/görsel PDF'i yok / 0 bayt / < 1,2 KB / eski      Resmî motorla yeniden üretilir,
                                      ReportLab çıktısı (CanEditor imzasız,      katalogdaki pdf_path güncellenir,
                                      gömülü font yok) / TIFF sayfa sayısı ≠     Drive'daki AYNI ADLI dosyanın
                                      PDF sayfa sayısı                           ÜZERİNE yazılır (betik v3)
      Drive indeksi (telefondan vb.   küçük PDF'ler indirilip aynı ölçütle       Kaynağı yereldeyse yeniden üretilip
      yüklenmiş, yerelde olmayanlar)  denetlenir                                 üzerine yazılır; yoksa evrak UYAP'tan
                                                                                 yeniden indirme kuyruğuna alınır
    Hiçbir belge silinmez: Drive'da eski dosya çöp kutusuna (30 gün) gider, yerelde *.bozuk.pdf yedeği onarım
    doğrulanana kadar tutulur. Tekrar tekrar çalıştırılabilir (onarılanlar ikinci kez işlenmez).

EN: archive-wide repair of broken/missing PDFs using the official Havelsan engine; replaces Drive copies in place.

Kullanım:  python arsiv_onar.py [--salt-oku] [--sinir 500] [--drive]    |    caneditor arsiv onar
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

BURASI = Path(__file__).resolve().parent
sys.path.insert(0, str(BURASI))

import donusturucu as dn  # noqa: E402

VERI = Path(os.environ.get("UYAP_VERI_DIZINI") or BURASI)
KAYNAK_UZANTI = {".udf", ".tif", ".tiff", ".jpg", ".jpeg", ".png", ".bmp", ".gif"}


def bozuk_mu(pdf: Path, kaynak: Path | None = None, bayt: bytes | None = None) -> str:
    """'' = sağlam; aksi hâlde Türkçe neden. EN: returns a reason string when the PDF is broken."""
    try:
        if bayt is None:
            if not pdf.exists():
                return "PDF yok"
            bayt = pdf.read_bytes()
    except OSError as e:
        return f"okunamadı: {e}"
    if not bayt:
        return "0 bayt"
    if not bayt.startswith(b"%PDF"):
        return "PDF değil"
    bas = bayt[:400_000]
    if b"ReportLab" in bas and b"CanEditor (yedek PDF motoru)" not in bas and b"/FontFile2" not in bas:
        return "eski bozuk yedek motor (Helvetica, Türkçe harf yok)"
    if len(bayt) < 1200:
        return f"çok küçük ({len(bayt)} bayt)"
    if kaynak is not None and kaynak.suffix.lower() in (".tif", ".tiff") and kaynak.exists():
        try:
            from PIL import Image
            from pypdf import PdfReader
            import io
            with Image.open(kaynak) as im:
                kare = getattr(im, "n_frames", 1)
            sayfa = len(PdfReader(io.BytesIO(bayt)).pages)
            if sayfa != kare:
                return f"TIFF {kare} sayfa, PDF {sayfa} sayfa"
        except Exception:  # noqa: BLE001
            pass
    return ""


def _uret(kaynak: Path, hedef: Path) -> Path | None:
    if kaynak.suffix.lower() == ".udf":
        return dn.udf_to_pdf(kaynak, hedef, timeout=180)
    return dn.images_to_pdf(kaynak, hedef=hedef, zorla=True)


def _drive_istemci():
    try:
        import google_drive_entegrasyonu as gde
        cfg = json.loads((VERI / "watcher_config.json").read_text(encoding="utf-8"))
        c = gde.GoogleDriveCloudClient(webhook_url=str(cfg.get("google_drive_webhook") or ""),
                                       local_drive_dir=str(cfg.get("google_drive_dir") or ""))
        return c if c.is_configured else None
    except Exception:  # noqa: BLE001
        return None


def _yukleme_defteri():
    c = sqlite3.connect(str(VERI / "drive_indeks.db"), timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS drive_yukleme (evrak_id TEXT PRIMARY KEY, boyut INTEGER NOT NULL DEFAULT 0,"
              " hedef TEXT NOT NULL DEFAULT '', drive_id TEXT NOT NULL DEFAULT '', url TEXT NOT NULL DEFAULT '',"
              " zaman TEXT NOT NULL DEFAULT '')")
    return c


def onar(sinir: int = 500, salt_oku: bool = False, drive_tara: bool = True, log=print) -> dict:
    """Arşivi tarar ve onarır. Döner: sayımlar + örnek listesi."""
    rapor = {"taranan": 0, "bozuk": 0, "onarilan": 0, "drive_guncellenen": 0, "yeniden_indirilecek": 0,
             "onarilamayan": 0, "drive_taranan": 0, "drive_bozuk": 0, "betik_surumu": None, "ornekler": []}
    kat_yol = VERI / "uyap_katalog.db"
    if not kat_yol.exists():
        rapor["not"] = "katalog yok"
        return rapor
    drive = _drive_istemci()
    surum = drive.betik_surumu() if (drive and drive.webhook_url) else None
    rapor["betik_surumu"] = surum
    uzerine_yazilabilir = bool(drive and (drive.local_drive_dir and drive.local_drive_dir.exists() or (surum or 0) >= 3))
    if drive and drive.webhook_url and (surum or 0) < 3:
        log("⚠️ Drive webhook betiği eski (v%s): onarılan PDF'ler Drive'daki bozukların ÜZERİNE yazılamaz. "
            "Asistan → Drive Ayarları → '📋 Yeni betiği kopyala' ile v3'e güncelleyin." % (surum or "?"))
    kat = sqlite3.connect(str(kat_yol), timeout=60)
    kat.row_factory = sqlite3.Row
    defter = _yukleme_defteri()
    satirlar = kat.execute(
        "SELECT e.id, e.skey, e.path, e.pdf_path, e.durum, d.birim, d.dosya_no FROM evrak e "
        "LEFT JOIN dosya d ON d.dkey=e.dkey WHERE e.path IS NOT NULL AND e.durum='indirildi'").fetchall()
    for r in satirlar:
        kaynak = Path(r["path"])
        if kaynak.suffix.lower() not in KAYNAK_UZANTI:
            continue
        rapor["taranan"] += 1
        pdf = Path(r["pdf_path"]) if r["pdf_path"] else kaynak.with_suffix(".pdf")
        neden = bozuk_mu(pdf, kaynak)
        if not neden:
            continue
        rapor["bozuk"] += 1
        if len(rapor["ornekler"]) < 30:
            rapor["ornekler"].append({"evrak": pdf.name, "neden": neden})
        if salt_oku or rapor["onarilan"] + rapor["onarilamayan"] >= sinir:
            continue
        if not kaynak.exists():
            # Kaynak UDF/TIFF yerelde yok → UYAP'tan yeniden indir (nöbetçi indirir, dönüştürür, yükler)
            with kat:
                kat.execute("UPDATE evrak SET durum='yeni', path=NULL, pdf_path=NULL, sha256=NULL, indirildi=NULL, "
                            "hata='arsiv-onar: PDF bozuk, kaynak yok' WHERE id=?", (r["id"],))
            defter.execute("DELETE FROM drive_yukleme WHERE evrak_id=?", (str(r["id"]),))
            defter.commit()
            rapor["yeniden_indirilecek"] += 1
            continue
        yedek = pdf.with_suffix(".bozuk.pdf")
        try:
            if pdf.exists():
                shutil.move(str(pdf), str(yedek))
            yeni = _uret(kaynak, pdf)
            if not yeni or bozuk_mu(Path(yeni), kaynak):
                raise RuntimeError(f"yeniden üretilen PDF de geçersiz ({bozuk_mu(Path(yeni), kaynak) if yeni else 'üretilemedi'})")
            yedek.unlink(missing_ok=True)
            with kat:
                kat.execute("UPDATE evrak SET pdf_path=? WHERE id=?", (str(pdf), r["id"]))
            rapor["onarilan"] += 1
            log(f"🛠️ Onarıldı ({neden}): {pdf.name}")
        except Exception as e:  # noqa: BLE001
            if yedek.exists() and not pdf.exists():
                shutil.move(str(yedek), str(pdf))
            rapor["onarilamayan"] += 1
            log(f"✕ Onarılamadı {pdf.name}: {e}")
            continue
        # Drive'daki kopyanın üzerine yaz
        if drive and uzerine_yazilabilir:
            rel = f"DAVA_EVRAKLARI/{r['birim'] or 'Diger'}/{r['dosya_no'] or 'Genel'}"
            eski = defter.execute("SELECT hedef FROM drive_yukleme WHERE evrak_id=?", (str(r["id"]),)).fetchone()
            if eski and eski["hedef"] and "/" in eski["hedef"]:
                rel = eski["hedef"].rsplit("/", 1)[0]
            s = drive.upload_file(pdf, remote_folder_path=rel, uzerine_yaz=True) or {}
            if s.get("status") == "success":
                defter.execute("INSERT OR REPLACE INTO drive_yukleme VALUES (?,?,?,?,?,?)",
                               (str(r["id"]), pdf.stat().st_size, f"{drive.temiz_yol(rel)}/{pdf.name}",
                                str(s.get("fileId") or ""), str(s.get("url") or s.get("path") or ""),
                                time.strftime("%Y-%m-%dT%H:%M:%S")))
                defter.commit()
                rapor["drive_guncellenen"] += 1
    # Drive'da olup yerelde kaydı bulunmayan küçük PDF'ler (telefondan yüklenenler)
    if drive_tara and drive and drive.webhook_url:
        _drive_tara(kat, defter, drive, rapor, sinir, salt_oku, log)
    kat.close()
    defter.close()
    return rapor


def _drive_tara(kat, defter, drive, rapor, sinir, salt_oku, log):
    """Drive indeksindeki (drive_indeks.db) küçük PDF'leri indirip denetler; bozuksa kaynağıyla değiştirir."""
    try:
        c = sqlite3.connect(str(VERI / "drive_indeks.db"), timeout=30)
        c.row_factory = sqlite3.Row
        adaylar = c.execute("SELECT rel_yol, ad, klasor, boyut FROM drive_dosya WHERE uzanti='pdf' AND boyut < 8000 "
                            "AND rel_yol LIKE 'gdrive:%' ORDER BY mtime DESC LIMIT ?", (max(50, sinir * 4),)).fetchall()
        c.close()
    except sqlite3.Error:
        return
    sys.path.insert(0, str(BURASI.parents[1]))
    import drive_indeks
    yerel_ad = {Path(r["pdf_path"]).name: r for r in kat.execute(
        "SELECT id, path, pdf_path FROM evrak WHERE pdf_path IS NOT NULL").fetchall()}
    for a in adaylar:
        rapor["drive_taranan"] += 1
        try:
            bayt, _ = drive_indeks.webhook_dosya_getir(drive.webhook_url, a["rel_yol"].split(":", 1)[1])
        except Exception:  # noqa: BLE001
            continue
        neden = bozuk_mu(Path(a["ad"]), bayt=bayt)
        if not neden:
            continue
        rapor["drive_bozuk"] += 1
        if salt_oku:
            continue
        r = yerel_ad.get(a["ad"])
        if r and r["path"] and Path(r["path"]).exists():
            pdf = Path(r["pdf_path"])
            if bozuk_mu(pdf, Path(r["path"])):
                _uret(Path(r["path"]), pdf)
            if not bozuk_mu(pdf) and (drive.betik_surumu() or 0) >= 3:
                s = drive.upload_file(pdf, remote_folder_path=a["klasor"], uzerine_yaz=True) or {}
                if s.get("status") == "success":
                    rapor["drive_guncellenen"] += 1
                    log(f"☁️ Drive'daki bozuk PDF değiştirildi: {a['klasor']}/{a['ad']}")
        elif r:
            with kat:
                kat.execute("UPDATE evrak SET durum='yeni', path=NULL, pdf_path=NULL, sha256=NULL, indirildi=NULL, "
                            "hata='arsiv-onar: Drive PDF bozuk' WHERE id=?", (r["id"],))
            defter.execute("DELETE FROM drive_yukleme WHERE evrak_id=?", (str(r["id"]),))
            defter.commit()
            rapor["yeniden_indirilecek"] += 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="UYAP arşivi PDF onarımı (resmî Havelsan motoru)")
    ap.add_argument("--salt-oku", action="store_true", help="yalnız raporla")
    ap.add_argument("--sinir", type=int, default=500, help="bir turda en çok onarılacak evrak")
    ap.add_argument("--drive-yok", action="store_true", help="Drive indeksindeki PDF'leri tarama")
    ap.add_argument("--ic-ice-duzelt", action="store_true", help="Drive'daki iç içe UYAP_Arsiv klasörlerini birleştir")
    a = ap.parse_args(argv)
    if a.ic_ice_duzelt:
        d = _drive_istemci()
        print(json.dumps(d.ic_ice_duzelt() if d and d.webhook_url else {"hata": "webhook yok"}, ensure_ascii=False))
    r = onar(a.sinir, a.salt_oku, not a.drive_yok)
    print("@@SONUC@@" + json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
