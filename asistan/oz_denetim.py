#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Öz-denetim: birleşik günlük + kendi kendini test etme + onarım
==============================================================

TR: CanEditor'un tüm modülleri (sunucu, UYAP evrak, UETS/TickTick, dönüştürücü, e-imza, CLI) tek bir günlüğe
    yazar ve bu modül uygulamayı DÜZENLİ ARALIKLARLA kendi kendine sınar:

      Denetim                       Ne yapar                                   Onarım (onar=True)
      ───────────────────────────── ────────────────────────────────────────── ─────────────────────────────────
      python-moduller               her modülü içe aktarmayı dener             — (eksik bağımlılığı raporlar)
      java-jar-font                 Java, resmî UYAP jar'ları, TTF'ler        —
      pdf-motoru                    örnek UDF → PDF (resmî motor), font gömülü —
                                    mü, Türkçe metin doğru mu
      bozuk-pdf                     katalogdaki 0 baytlık PDF'ler ile eski     yeniden dönüştürür (resmî motor)
                                    bozuk yedek motorun ürettiği PDF'ler
                                    (Helvetica, ReportLab, CanEditor imzasız)
      sqlite-butunluk               katalog + defter PRAGMA integrity_check   REINDEX; bozuksa yedek alıp uyarır
      katalog                       diskte olmayan indirmeler, mükerrer ekler  Katalog.sync_disk + finalize_scan
                                                                                 (kataloğun kendi onarımı; dosya silinmez)
      kisisel-ayar                  PIN / GSM / TC tanımlı mı (değer yazılmaz) —
      ticktick-duzen                TickTick anahtarı varsa son düzen turu     'ticktick-duzen' görevini başlatır
                                    6 saatten eskiyse                          (tamamlanan + yapılmayacak dahil)
      disk                          boş alan < 1 GB                            —

    Her denetim sonucu günlüğe ve son_denetim.json'a yazılır; GUI'deki "Sağlık / Öz-denetim" paneli ve
    `caneditor oz-denetim` aynı raporu gösterir. Sunucu açıkken her 3 saatte bir kendiliğinden çalışır.

EN: unified log + periodic self-test & self-repair. Never deletes user documents; repairs are idempotent.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import traceback
import zipfile
from pathlib import Path

KOK = Path(__file__).resolve().parent
_KILIT = threading.Lock()
AZAMI_GUNLUK_BAYT = 8 * 1024 * 1024


# ─────────────────────────────────────────────────────────────────────────────
# Birleşik günlük / unified log
# ─────────────────────────────────────────────────────────────────────────────
def veri_dizini() -> Path:
    d = os.environ.get("CANASISTAN_VERI")
    if d:
        p = Path(d)
    elif os.name == "nt":
        p = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CanEditor" / "asistan"
    else:
        p = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "caneditor-asistan"
    p.mkdir(parents=True, exist_ok=True)
    return p


def gunluk_yolu() -> Path:
    d = veri_dizini() / "gunluk"
    d.mkdir(parents=True, exist_ok=True)
    return d / "caneditor.log"


def kaydet(kaynak: str, mesaj: str, seviye: str = "BILGI") -> None:
    """Tek satırlık günlük kaydı: '2026-11-24 20:00:00 [BILGI] kaynak: mesaj'. Dönerli (8 MB × 3).
    Kişisel değerler (PIN) asla yazılmaz: 'pin=' içeren satırlar maskelenir."""
    import re
    mesaj = re.sub(r"(?i)(pin[\"'\s:=]+)[0-9]{4,8}", r"\1******", str(mesaj)).replace("\n", " ⏎ ")[:4000]
    satir = f"{time.strftime('%Y-%m-%d %H:%M:%S')} [{seviye}] {kaynak}: {mesaj}\n"
    try:
        with _KILIT:
            p = gunluk_yolu()
            if p.exists() and p.stat().st_size > AZAMI_GUNLUK_BAYT:
                for i in (2, 1):
                    eski = p.with_suffix(f".log.{i}")
                    if eski.exists():
                        if i == 2:
                            eski.unlink()
                        else:
                            eski.rename(p.with_suffix(".log.2"))
                p.rename(p.with_suffix(".log.1"))
            with open(p, "a", encoding="utf-8") as f:
                f.write(satir)
    except OSError:
        pass


def son_kayitlar(n: int = 80, kaynak: str = "") -> list[str]:
    try:
        satirlar = gunluk_yolu().read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    if kaynak:
        satirlar = [s for s in satirlar if f"] {kaynak}" in s]
    return satirlar[-n:]


def izle(kaynak: str = ""):
    p = gunluk_yolu()
    p.touch(exist_ok=True)
    with open(p, encoding="utf-8", errors="replace") as f:
        f.seek(0, 2)
        while True:
            s = f.readline()
            if not s:
                time.sleep(0.5)
                continue
            if not kaynak or f"] {kaynak}" in s:
                yield s.rstrip("\n")


# ─────────────────────────────────────────────────────────────────────────────
# Denetimler / checks — her biri (durum, ayrinti, onarilan) döndürür; durum: tamam | uyari | hata
# ─────────────────────────────────────────────────────────────────────────────
def _evrak_modulu():
    p = str(KOK / "moduller" / "evrak")
    if p not in sys.path:
        sys.path.insert(0, p)
    import donusturucu  # noqa: WPS433
    return donusturucu


def d_python_moduller(onar: bool, **_):
    eksik = []
    for ad in ("sunucu", "entegrasyon", "jar_donustur", "hayfa_kopru", "kisisel_ayar", "imza"):
        try:
            __import__(ad)
        except Exception as e:  # noqa: BLE001
            eksik.append(f"{ad}: {type(e).__name__}: {e}"[:200])
    for paket in ("requests", "reportlab", "PIL", "pypdf"):
        try:
            __import__(paket)
        except Exception:  # noqa: BLE001
            eksik.append(f"paket yok: {paket}")
    return ("tamam" if not eksik else "uyari"), {"eksik": eksik}, 0


def d_java_jar_font(onar: bool, **_):
    dn = _evrak_modulu()
    java, jars, fonts = dn.java_exe(), dn.jars_dir(), dn.font_dirs()
    tnr = any((Path(d) / f).exists() for d in fonts for f in ("TimesNewRoman.TTF", "timesnewroman.ttf", "times.ttf"))
    ayr = {"java": java, "jar_dizini": str(jars) if jars else None, "font_dizinleri": fonts, "times_new_roman": tnr}
    if not java or not jars:
        return "uyari", ayr | {"not": "Resmî motor kullanılamıyor; UDF→PDF yedek (ReportLab) motorla yapılır."}, 0
    return ("tamam" if tnr else "uyari"), ayr, 0


def _ornek_udf(yol: Path) -> None:
    metin = "İSTANBUL 1. ASLİYE HUKUK MAHKEMESİ'NE\nŞükrü Çağlar Öztürk — ğüşiöçĞÜŞİÖÇ denetim satırı\n"
    els, off = [], 0
    for i, s in enumerate(metin.splitlines(keepends=True)):
        uz = len(s.encode("utf-16-le")) // 2
        els.append(f'<paragraph Alignment="{1 if i == 0 else 3}" size="12"><content startOffset="{off}" '
                   f'length="{uz}" family="Times New Roman" size="12"{" bold=\"true\"" if i == 0 else ""}/></paragraph>')
        off += uz
    xml = (f'<?xml version="1.0" encoding="UTF-8" ?><template format_id="1.8"><content><![CDATA[{metin}]]></content>'
           '<properties><pageFormat mediaSizeName="1" leftMargin="42.525" rightMargin="42.525" topMargin="42.525" '
           'bottomMargin="42.525" paperOrientation="1" headerFOffset="20.0" footerFOffset="20.0" /></properties>'
           f'<elements resolver="hvl-default">{"".join(els)}</elements><styles><style name="hvl-default" '
           'family="Times New Roman" size="12" description="Gövde" /></styles></template>')
    with zipfile.ZipFile(yol, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.xml", xml)


def _pdf_metin_font(pdf: Path) -> tuple[str, bool]:
    try:
        from pypdf import PdfReader
        r = PdfReader(str(pdf))
        metin = r.pages[0].extract_text() or ""
    except Exception:  # noqa: BLE001
        metin = ""
    b = pdf.read_bytes()
    gomulu = b"/FontFile2" in b or b"TimesNewRoman" in b
    return metin, gomulu


def d_pdf_motoru(onar: bool, **_):
    dn = _evrak_modulu()
    with tempfile.TemporaryDirectory(prefix="caneditor_oz_") as td:
        udf = Path(td) / "denetim.udf"
        _ornek_udf(udf)
        bas = time.time()
        pdf = dn.udf_to_pdf(udf, timeout=120)
        sure = round(time.time() - bas, 1)
        if not pdf or not Path(pdf).is_file():
            return "hata", {"not": "Örnek UDF PDF'e çevrilemedi", "sure_sn": sure}, 0
        metin, gomulu = _pdf_metin_font(Path(pdf))
        turkce = "ğüşiöçĞÜŞİÖÇ" in metin.replace(" ", "") or "Öztürk" in metin
        ayr = {"sure_sn": sure, "turkce_dogru": turkce, "font_gomulu": gomulu, "boyut": Path(pdf).stat().st_size}
        return ("tamam" if turkce and gomulu else "hata"), ayr, 0


def _katalog_yolu() -> Path | None:
    for p in (Path(os.environ.get("UYAP_VERI_DIZINI") or "") / "uyap_katalog.db",
              KOK / "moduller" / "evrak" / "uyap_katalog.db",
              veri_dizini() / "moduller" / "evrak" / "uyap_katalog.db"):
        if str(p) and p.is_file():
            return p
    return None


def _bozuk_pdf_mi(p: Path) -> str:
    """'' = sağlam; aksi hâlde neden. Eski (v4.2–v4.9.4) yedek motor ReportLab + gömülmemiş Helvetica üretiyordu."""
    try:
        if p.stat().st_size == 0:
            return "0 bayt"
        bas = p.read_bytes()[:200_000]
    except OSError:
        return ""
    if b"ReportLab" in bas and b"CanEditor (yedek PDF motoru)" not in bas and b"/FontFile2" not in bas:
        return "eski bozuk yedek motor (Helvetica, Türkçe glif yok)"
    return ""


def d_bozuk_pdf(onar: bool, sinir: int = 400, **_):
    kat = _katalog_yolu()
    if not kat:
        return "tamam", {"not": "katalog yok"}, 0
    dn = _evrak_modulu()
    bozuk, onarilan = [], 0
    con = sqlite3.connect(str(kat), timeout=30)
    try:
        satirlar = con.execute("SELECT skey, path, pdf_path FROM evrak WHERE path LIKE '%.udf' AND COALESCE(pdf_path,'')<>''").fetchall()
    except sqlite3.Error as e:
        con.close()
        return "uyari", {"hata": str(e)}, 0
    con.close()
    for skey, udf, pdf in satirlar:
        pp = Path(pdf)
        if not pp.exists():
            continue
        neden = _bozuk_pdf_mi(pp)
        if not neden:
            continue
        bozuk.append({"skey": skey, "pdf": pdf, "neden": neden})
        if onar and onarilan < sinir and Path(udf).is_file():
            try:
                yedek = pp.with_suffix(".bozuk.pdf")
                shutil.move(str(pp), str(yedek))
                yeni = dn.udf_to_pdf(Path(udf), pp, timeout=120)
                if yeni and Path(yeni).is_file() and not _bozuk_pdf_mi(Path(yeni)):
                    yedek.unlink(missing_ok=True)
                    onarilan += 1
                    kaydet("oz-denetim", f"PDF yeniden üretildi: {pp.name} ({neden})")
                else:
                    shutil.move(str(yedek), str(pp))
            except Exception as e:  # noqa: BLE001
                kaydet("oz-denetim", f"PDF onarılamadı {pp.name}: {e}", "HATA")
    durum = "tamam" if len(bozuk) == onarilan else "uyari"
    return durum, {"bozuk": len(bozuk), "ornekler": bozuk[:20]}, onarilan


def d_sqlite_butunluk(onar: bool, **_):
    sonuc, onarilan, kotu = {}, 0, False
    dbler = [x for x in (_katalog_yolu(), KOK / "moduller" / "avukatasistan" / "veri" / "defter.db") if x and Path(x).is_file()]
    for db in dbler:
        try:
            con = sqlite3.connect(str(db), timeout=30)
            r = con.execute("PRAGMA integrity_check").fetchone()[0]
            if r != "ok" and onar:
                shutil.copy2(db, str(db) + f".yedek-{time.strftime('%Y%m%d%H%M%S')}")
                con.execute("REINDEX")
                con.commit()
                r2 = con.execute("PRAGMA integrity_check").fetchone()[0]
                onarilan += int(r2 == "ok")
                r = f"{r} → REINDEX → {r2}"
            con.close()
            sonuc[Path(db).name] = r
            kotu |= not r.endswith("ok")
        except sqlite3.Error as e:
            sonuc[Path(db).name] = f"hata: {e}"
            kotu = True
    return ("hata" if kotu else "tamam"), sonuc, onarilan


def d_katalog(onar: bool, **_):
    """Katalog tutarlılığı — KATALOĞUN KENDİ onarımları çağrılır (aynı mantık iki yerde olmasın):
      * Katalog.sync_disk(): diskte olmayan indirmeleri 'yeni'ye döndürür → nöbetçi yeniden indirir
      * Katalog.finalize_scan(): aynı ad anahtarlı ekleri 'mukerrer' işaretler (dosya silinmez)
    Salt-okuma kipinde yalnız sayılar raporlanır. EN: delegates to the catalogue's own self-heal methods."""
    kat = _katalog_yolu()
    if not kat:
        return "tamam", {"not": "katalog yok"}, 0
    con = sqlite3.connect(str(kat), timeout=30)
    try:
        st = dict(zip(("toplam", "indirildi", "mukerrer", "yeni"), con.execute(
            "SELECT COUNT(*), SUM(durum='indirildi'), SUM(durum='mukerrer'), SUM(durum='yeni') FROM evrak").fetchone()))
        yollar = [r[0] for r in con.execute(
            "SELECT DISTINCT path FROM evrak WHERE durum IN ('indirildi','mukerrer') AND path IS NOT NULL LIMIT 200000")]
    except sqlite3.Error as e:
        return "uyari", {"hata": str(e)}, 0
    finally:
        con.close()
    eksik = sum(1 for p in yollar if not os.path.exists(p))
    st["diskte_yok"] = eksik
    onarilan = 0
    if onar:
        try:
            _evrak_modulu()
            from evrak_katalog import Katalog  # noqa: WPS433
            k = Katalog(kat)
            onarilan += k.sync_disk() or 0
            k.finalize_scan()
            if onarilan:
                kaydet("oz-denetim", f"{onarilan} evrak diskte yok → yeniden indirme kuyruğuna alındı")
        except Exception as e:  # noqa: BLE001
            return "uyari", st | {"hata": f"onarım: {e}"}, onarilan
    return ("tamam" if not eksik or onar else "uyari"), st, onarilan


def d_kisisel_ayar(onar: bool, **_):
    import kisisel_ayar as ka
    var = {k: bool(ka.al(k)) for k in ("pin", "tc", "gsm", "operator")}
    eksik = [k for k, v in var.items() if not v]
    not_ = ""
    if not var["pin"]:
        not_ = "PIN yok: e-imza takılı olsa bile otomatik giriş/imza Mobil İmza ile yapılır."
    if not var["gsm"] or not var["tc"]:
        not_ += " Mobil İmza için TC ve GSM gerekli (~/.caneditor/kisisel.json ya da UYAP_TC/UYAP_GSM)."
    return ("tamam" if not eksik else "uyari"), {"tanimli": var, "not": not_.strip()}, 0


def d_ticktick_duzen(onar: bool, baglanti=None, **_):
    """TickTick anahtarı tanımlıysa düzen turunun 6 saatten eski olmamasını sağlar (Notion anahtarı şart değil).
    EN: ensure the TickTick housekeeping (dedupe incl. completed & won't-do) ran within 6h."""
    try:
        import entegrasyon
        e = entegrasyon.env_oku(KOK / "moduller" / "avukatasistan")
    except Exception as ex:  # noqa: BLE001
        return "uyari", {"hata": str(ex)}, 0
    if not e.get("TICKTICK_TOKEN"):
        return "tamam", {"not": "TickTick bağlı değil"}, 0
    durum_dosyasi = veri_dizini() / "ticktick_duzen_son.txt"
    try:
        son = float(durum_dosyasi.read_text())
    except (OSError, ValueError):
        son = 0.0
    yas_saat = (time.time() - son) / 3600 if son else None
    if yas_saat is not None and yas_saat < 6:
        return "tamam", {"son_tur_saat_once": round(yas_saat, 1)}, 0
    if not onar:
        return "uyari", {"son_tur_saat_once": yas_saat}, 0
    try:
        if baglanti is not None:
            baglanti.istek("POST", "/api/gorev/ticktick-duzen")
        else:
            import sunucu
            g = sunucu.GOREV_DURUM["ticktick-duzen"]
            if not g.calisiyor():
                g.baslat()
        durum_dosyasi.write_text(str(time.time()))
        kaydet("oz-denetim", "TickTick düzen turu başlatıldı (mükerrer + eksik; tamamlanan ve yapılmayacak dahil)")
        return "tamam", {"baslatildi": True}, 1
    except Exception as ex:  # noqa: BLE001
        return "uyari", {"hata": str(ex)}, 0


def d_disk(onar: bool, **_):
    try:
        bos = shutil.disk_usage(str(veri_dizini())).free
    except OSError:
        return "uyari", {}, 0
    return ("tamam" if bos > 1 << 30 else "uyari"), {"bos_gb": round(bos / (1 << 30), 2)}, 0


DENETIMLER = [
    ("python-moduller", d_python_moduller),
    ("java-jar-font", d_java_jar_font),
    ("pdf-motoru", d_pdf_motoru),
    ("bozuk-pdf", d_bozuk_pdf),
    ("sqlite-butunluk", d_sqlite_butunluk),
    ("katalog", d_katalog),
    ("kisisel-ayar", d_kisisel_ayar),
    ("ticktick-duzen", d_ticktick_duzen),
    ("disk", d_disk),
]


def tam_denetim(onar: bool = True, baglanti=None, sadece: list[str] | None = None) -> dict:
    """Tüm denetimleri çalıştırır; her biri yalıtılmıştır (biri çökerse diğerleri sürer)."""
    bas = time.time()
    rapor = {"zaman": dt.datetime.now().isoformat(timespec="seconds"), "onar": onar, "denetimler": {}}
    ozet = {"tamam": 0, "uyari": 0, "hata": 0, "onarilan": 0}
    for ad, fn in DENETIMLER:
        if sadece and ad not in sadece:
            continue
        t0 = time.time()
        try:
            durum, ayr, onarilan = fn(onar, baglanti=baglanti)
        except Exception as e:  # noqa: BLE001
            durum, ayr, onarilan = "hata", {"istisna": f"{type(e).__name__}: {e}", "iz": traceback.format_exc()[-800:]}, 0
        rapor["denetimler"][ad] = {"durum": durum, "onarilan": onarilan, "sure_sn": round(time.time() - t0, 2), **(ayr or {})}
        ozet[durum] = ozet.get(durum, 0) + 1
        ozet["onarilan"] += onarilan
        seviye = {"tamam": "BILGI", "uyari": "UYARI", "hata": "HATA"}[durum]
        kaydet("oz-denetim", f"{ad}: {durum}" + (f" (onarılan {onarilan})" if onarilan else "")
               + (f" — {json.dumps(ayr, ensure_ascii=False, default=str)[:400]}" if durum != "tamam" else ""), seviye)
    rapor["ozet"] = ozet
    rapor["sure_sn"] = round(time.time() - bas, 1)
    try:
        (veri_dizini() / "son_denetim.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=2, default=str),
                                                         encoding="utf-8")
    except OSError:
        pass
    return rapor


def son_rapor() -> dict:
    try:
        return json.loads((veri_dizini() / "son_denetim.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class OzDenetimZamanlayici:
    """Sunucu açıkken ilk tur 5 dk sonra, sonra her OZ_DENETIM_SAAT (varsayılan 3) saatte bir tam denetim+onarım.
    CANEDITOR_OZ_DENETIM=0 ile kapatılır."""

    def __init__(self):
        self.calisiyor = False

    def baslat(self):
        if os.environ.get("CANEDITOR_OZ_DENETIM") == "0":
            return
        threading.Thread(target=self._dongu, daemon=True, name="oz-denetim").start()

    def simdi(self):
        if self.calisiyor:
            return False
        threading.Thread(target=self._tur, daemon=True, name="oz-denetim-simdi").start()
        return True

    def _tur(self):
        self.calisiyor = True
        try:
            tam_denetim(onar=True)
        finally:
            self.calisiyor = False

    def _dongu(self):
        time.sleep(300)
        while True:
            try:
                self._tur()
            except Exception:  # noqa: BLE001
                pass
            try:
                saat = float(os.environ.get("OZ_DENETIM_SAAT") or 3)
            except ValueError:
                saat = 3.0
            time.sleep(max(0.5, saat) * 3600)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="CanEditor öz-denetim (test + onarım)")
    ap.add_argument("--salt-oku", action="store_true")
    ap.add_argument("--sadece", nargs="*")
    a = ap.parse_args()
    r = tam_denetim(onar=not a.salt_oku, sadece=a.sadece)
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    sys.exit(0 if r["ozet"].get("hata", 0) == 0 else 1)
