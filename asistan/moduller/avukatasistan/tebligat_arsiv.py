#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UETS tebligat arşivi — Google Drive'da kalıcı, klasörlenmiş, aranabilir arşiv + yerel kayıt defteri
==================================================================================================

TR: Her UETS turunda (uets-senkron) indirilen taze CSV ve içindeki HER tebligat arşivlenir:

      Google Drive / UYAP_Arsiv /
        UETS_Tebligat/_CSV/<YYYY-AA>/tebligatlar_<YYYYAAGG-SSDDss>.csv     ← her tur indirilen liste (birikir)
        UETS_Tebligat/<Mahkeme>/<Esas | Esassiz>/<GelisTarihi>_<Barkod>/
            <barkod>.eyp              özgün UETS paketi
            ekler/…                   EYP'den ayıklanan üstyazı ve ekler (UDF'ler ayrıca resmî motorla PDF)
            tebligat.json             çıkarılan TÜM bilgi: gönderen, konu, mahkeme, esas, barkod, UETS no,
                                      geliş/tebliğ/7-14-30 gün/hedef süreler, taraflar, evrak listesi,
                                      dosya SHA-256'ları, TickTick görev kimliği, Notion bağlantısı…
            ozet.md                   TickTick görevindeki ayrıntının okunur (daha ayrıntılı) hâli

    Kayıt defteri (veri/tebligat_arsiv.db) her tebligatın arşiv durumunu tutar; asistan (/api/tebligat/arsiv,
    caneditor tebligat arsiv, Tebligatlar → 🗄️ Arşiv) buradan arar ve Drive bağlantılarını gösterir.
    Aynı EYP ikinci kez yüklenmez (SHA-256); EYP sonradan gelirse ya da değişirse klasör güncellenir.
    Drive tanımlı değilse aynı düzen yerelde (veri/tebligat_arsiv/) kurulur; Drive bağlanınca yüklenir.
    Yerel EYP önbelleği: Drive'a arşivlenmiş ve TEBLIGAT_YEREL_GUN (varsayılan 30) günden eski paketler
    yerelden silinir — arşivin asıl yeri Drive'dır (yerelde olmaması yeniden indirme sebebi sayılmaz).

EN: Durable Drive archive of every UETS list and tebligat package with JSON metadata, summaries and a registry.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path

BURASI = Path(__file__).resolve().parent
EVRAK = BURASI.parent / "evrak"
VERI = BURASI / "veri"
DB = VERI / "tebligat_arsiv.db"
KOK = "UETS_Tebligat"

SEMA = """
CREATE TABLE IF NOT EXISTS tebligat (
  anahtar TEXT PRIMARY KEY,           -- barkod; yoksa UETS:<no>
  barkod TEXT, uets_no TEXT, mahkeme TEXT, esas TEXT, gonderen TEXT, konu TEXT,
  gelis TEXT, teblig TEXT, son_gun TEXT, sure_etiketi TEXT, muvekkil TEXT,
  ticktick_id TEXT, ticktick_proje TEXT, notion_url TEXT,
  eyp_sha TEXT, ek_sayisi INTEGER DEFAULT 0, drive_klasor TEXT, drive_url TEXT,
  durum TEXT, ilk_gorulme TEXT, son_guncelleme TEXT, json TEXT
);
CREATE INDEX IF NOT EXISTS ix_tb_gelis ON tebligat(gelis DESC);
CREATE INDEX IF NOT EXISTS ix_tb_esas ON tebligat(esas);
CREATE TABLE IF NOT EXISTS csv_arsiv (sha TEXT PRIMARY KEY, ad TEXT, zaman TEXT, satir INTEGER, drive_yol TEXT);
"""


def db():
    VERI.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB), timeout=30)
    c.row_factory = sqlite3.Row
    c.executescript(SEMA)
    return c


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _temiz(s: str, uz: int = 80) -> str:
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", str(s or "")).strip(" .")
    return re.sub(r"\s+", " ", s)[:uz] or "Bilinmeyen"


def _iso(v) -> str:
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    return str(v or "")


def _drive():
    """Evrak modülünün Drive ayarı (watcher_config.json) ile istemci; yoksa None."""
    try:
        if str(EVRAK) not in sys.path:
            sys.path.insert(0, str(EVRAK))
        import google_drive_entegrasyonu as gde
        veri = Path(os.environ.get("UYAP_VERI_DIZINI") or EVRAK)
        cfg = json.loads((veri / "watcher_config.json").read_text(encoding="utf-8"))
        c = gde.GoogleDriveCloudClient(webhook_url=str(cfg.get("google_drive_webhook") or ""),
                                       local_drive_dir=str(cfg.get("google_drive_dir") or ""))
        return c if c.is_configured else None
    except Exception:  # noqa: BLE001
        return None


def _yukle(drive, yerel: Path, klasor: str, kopya_kok: Path) -> dict:
    """Drive'a yükler; Drive yoksa yerel arşiv kopyasına koyar. Döner: {status, url|path}."""
    if drive:
        r = drive.upload_file(yerel, remote_folder_path=f"{klasor}", uzerine_yaz=True) or {}
        if r.get("status") == "success":
            return r
    hedef = kopya_kok / klasor / yerel.name
    hedef.parent.mkdir(parents=True, exist_ok=True)
    if yerel.resolve() != hedef.resolve():
        shutil.copy2(yerel, hedef)
    return {"status": "yerel", "path": str(hedef)}


def anahtar_of(item: dict) -> str:
    return str(item.get("barcode") or "") or (f"UETS:{item['uets_no']}" if item.get("uets_no") else "")


def ozet_md(kayit: dict) -> str:
    d = kayit.get("sureler") or {}
    satir = [f"# 📨 Tebligat — {kayit.get('mahkeme') or kayit.get('gonderen')} {kayit.get('esas') or ''}".rstrip(), ""]
    for ad, k in (("Gönderen", "gonderen"), ("Konu", "konu"), ("Mahkeme / Birim", "mahkeme"), ("Esas No", "esas"),
                  ("Barkod", "barkod"), ("UETS No", "uets_no"), ("Müvekkil", "muvekkil")):
        if kayit.get(k):
            satir.append(f"- **{ad}:** {kayit[k]}")
    satir += ["", "## ⏱️ Süreler"]
    for ad, k in (("Geliş (UETS)", "gelis_str"), ("Tebliğ sayılan", "teblig_str"), ("7 gün", "d7_str"),
                  ("14 gün", "d14_str"), ("30 gün", "d30_str"), ("Hedef son gün", "target_str")):
        if d.get(k):
            satir.append(f"- **{ad}:** {d[k]}")
    if d.get("target_label"):
        satir.append(f"- **Süre türü:** {d['target_label']}")
    if kayit.get("taraflar"):
        satir += ["", "## 👥 Taraflar"] + [f"- {t}" for t in kayit["taraflar"]]
    if kayit.get("evraklar"):
        satir += ["", "## 📄 Paketteki evraklar"]
        for e in kayit["evraklar"]:
            satir.append(f"- {e.get('ad') or e.get('name') or e}" + (f" — {e.get('tur')}" if isinstance(e, dict) and e.get("tur") else ""))
    if kayit.get("dosyalar"):
        satir += ["", "## 📎 Arşivdeki dosyalar"] + [f"- {f['ad']} ({f['boyut']} bayt, SHA-256 {f['sha256'][:16]}…)" for f in kayit["dosyalar"]]
    if kayit.get("ticktick_id") or kayit.get("notion_url"):
        satir += ["", "## 🔗 Bağlantılar"]
        if kayit.get("ticktick_id"):
            satir.append(f"- TickTick görevi: {kayit['ticktick_id']}")
        if kayit.get("notion_url"):
            satir.append(f"- Notion: {kayit['notion_url']}")
    satir += ["", f"_CanEditor tebligat arşivi · {kayit.get('arsiv_zamani')}_", ""]
    return "\n".join(satir)


def csv_arsivle(csv_path: str, satir: int = 0, drive=None) -> dict:
    p = Path(csv_path)
    if not p.is_file():
        return {"durum": "yok"}
    sha = _sha(p)
    c = db()
    if c.execute("SELECT 1 FROM csv_arsiv WHERE sha=?", (sha,)).fetchone():
        c.close()
        return {"durum": "zaten"}
    drive = drive if drive is not None else _drive()
    simdi = dt.datetime.now()
    ad = f"tebligatlar_{simdi:%Y%m%d-%H%M%S}.csv"
    gecici = VERI / "_csv_gecici" / ad
    gecici.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, gecici)
    klasor = f"{KOK}/_CSV/{simdi:%Y-%m}"
    r = _yukle(drive, gecici, klasor, VERI / "tebligat_arsiv")
    gecici.unlink(missing_ok=True)
    c.execute("INSERT OR REPLACE INTO csv_arsiv VALUES (?,?,?,?,?)",
              (sha, ad, simdi.isoformat(timespec="seconds"), satir, r.get("url") or r.get("path") or ""))
    c.commit()
    c.close()
    return {"durum": r.get("status"), "ad": ad}


def tebligat_arsivle(item: dict, eyp_yolu: str | None = None, drive=None, zorla: bool = False) -> dict:
    """Tek tebligatı arşivler (idempotent). EN: archive one tebligat package + metadata."""
    anahtar = anahtar_of(item)
    if not anahtar:
        return {"durum": "anahtarsiz"}
    eyp = Path(eyp_yolu) if eyp_yolu else None
    eyp_sha = _sha(eyp) if eyp and eyp.is_file() else ""
    c = db()
    eski = c.execute("SELECT * FROM tebligat WHERE anahtar=?", (anahtar,)).fetchone()
    if eski and not zorla and eski["durum"] == "arsivlendi" and (not eyp_sha or eski["eyp_sha"] == eyp_sha):
        c.close()
        return {"durum": "zaten", "anahtar": anahtar}
    drive = drive if drive is not None else _drive()
    d = item.get("deadlines") or {}
    gelis = _iso(d.get("gelis_dt"))[:10] or dt.date.today().isoformat()
    klasor = f"{KOK}/{_temiz(item.get('court') or item.get('gonderen'))}/{_temiz(str(item.get('esas_no') or 'Esassiz').replace('/', '-'), 30)}/" \
             f"{gelis}_{_temiz(item.get('barcode') or item.get('uets_no'), 30)}"
    kopya_kok = VERI / "tebligat_arsiv"
    dosyalar, evraklar, url = [], [], ""
    calisma = VERI / "_arsiv_calisma" / _temiz(anahtar, 40)
    try:
        if eyp and eyp.is_file():
            r = _yukle(drive, eyp, klasor, kopya_kok)
            url = r.get("url") or url
            dosyalar.append({"ad": eyp.name, "boyut": eyp.stat().st_size, "sha256": eyp_sha, "yer": r.get("url") or r.get("path")})
            try:
                from eyp_parser import parse_eyp_file
                tam = parse_eyp_file(str(eyp), extract_files=True) or {}
            except Exception as e:  # noqa: BLE001
                tam = {"hata": str(e)}
            evraklar = [x if isinstance(x, dict) else {"ad": str(x)} for x in (tam.get("documents") or [])]
            for k in ("parties", "extra_info", "esas_no", "court"):
                if tam.get(k) and not item.get(k):
                    item[k] = tam[k]
            for ek in tam.get("extracted_paths") or []:
                ep = Path(ek)
                if not ep.is_file():
                    continue
                r = _yukle(drive, ep, f"{klasor}/ekler", kopya_kok)
                dosyalar.append({"ad": f"ekler/{ep.name}", "boyut": ep.stat().st_size, "sha256": _sha(ep), "yer": r.get("url") or r.get("path")})
                if ep.suffix.lower() == ".udf":
                    try:
                        if str(EVRAK) not in sys.path:
                            sys.path.insert(0, str(EVRAK))
                        import donusturucu
                        calisma.mkdir(parents=True, exist_ok=True)
                        pdf = donusturucu.udf_to_pdf(ep, calisma / (ep.stem + ".pdf"), timeout=120)
                        if pdf and Path(pdf).is_file():
                            r = _yukle(drive, Path(pdf), f"{klasor}/ekler", kopya_kok)
                            dosyalar.append({"ad": f"ekler/{Path(pdf).name}", "boyut": Path(pdf).stat().st_size,
                                             "sha256": _sha(Path(pdf)), "yer": r.get("url") or r.get("path")})
                    except Exception:  # noqa: BLE001
                        pass
        try:
            from state_manager import get_barcode_state
            st = get_barcode_state(item.get("barcode")) or {} if item.get("barcode") else {}
        except Exception:  # noqa: BLE001
            st = {}
        kayit = {
            "anahtar": anahtar, "barkod": item.get("barcode") or "", "uets_no": item.get("uets_no") or "",
            "mahkeme": item.get("court") or "", "esas": item.get("esas_no") or "", "gonderen": item.get("gonderen") or "",
            "konu": item.get("konu_raw") or "", "muvekkil": item.get("client_name") or item.get("muvekkil") or "",
            "taraflar": [str(t) for t in (item.get("parties") or [])], "ek_bilgi": item.get("extra_info") or "",
            "sureler": {k: _iso(v) for k, v in d.items()}, "evraklar": evraklar, "dosyalar": dosyalar,
            "ticktick_id": st.get("task_id") or "", "ticktick_proje": st.get("project_id") or "",
            "ticktick_durum": st.get("status") or "", "ek_gonderildi": st.get("ek_gonderildi"),
            "notion_url": item.get("notion_url") or "", "csv": Path(item.get("csv_path") or "").name,
            "drive_klasor": klasor, "arsiv_zamani": dt.datetime.now().isoformat(timespec="seconds"),
        }
        calisma.mkdir(parents=True, exist_ok=True)
        (calisma / "tebligat.json").write_text(json.dumps(kayit, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        (calisma / "ozet.md").write_text(ozet_md(kayit), encoding="utf-8")
        for f in ("tebligat.json", "ozet.md"):
            _yukle(drive, calisma / f, klasor, kopya_kok)
        durum = "arsivlendi" if eyp_sha else "eyp_yok"
        simdi = kayit["arsiv_zamani"]
        c.execute("""INSERT INTO tebligat(anahtar,barkod,uets_no,mahkeme,esas,gonderen,konu,gelis,teblig,son_gun,
                     sure_etiketi,muvekkil,ticktick_id,ticktick_proje,notion_url,eyp_sha,ek_sayisi,drive_klasor,drive_url,
                     durum,ilk_gorulme,son_guncelleme,json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(anahtar) DO UPDATE SET mahkeme=excluded.mahkeme, esas=excluded.esas, konu=excluded.konu,
                     son_gun=excluded.son_gun, muvekkil=excluded.muvekkil, ticktick_id=excluded.ticktick_id,
                     ticktick_proje=excluded.ticktick_proje, notion_url=excluded.notion_url, eyp_sha=excluded.eyp_sha,
                     ek_sayisi=excluded.ek_sayisi, drive_klasor=excluded.drive_klasor, drive_url=excluded.drive_url,
                     durum=excluded.durum, son_guncelleme=excluded.son_guncelleme, json=excluded.json""",
                  (anahtar, kayit["barkod"], kayit["uets_no"], kayit["mahkeme"], kayit["esas"], kayit["gonderen"],
                   kayit["konu"], gelis, _iso(d.get("teblig_dt"))[:10], _iso(d.get("target_dt"))[:10],
                   d.get("target_label") or "", kayit["muvekkil"], kayit["ticktick_id"], kayit["ticktick_proje"],
                   kayit["notion_url"], eyp_sha, max(0, len(dosyalar) - 1), klasor, url, durum, simdi, simdi,
                   json.dumps(kayit, ensure_ascii=False, default=str)))
        c.commit()
        return {"durum": durum, "anahtar": anahtar, "dosya": len(dosyalar), "drive": bool(drive)}
    finally:
        c.close()
        shutil.rmtree(calisma, ignore_errors=True)


def tur(csv_path: str, csv_items: list, eyp_dizin: dict, log=print) -> dict:
    """Bir UETS turunun tamamını arşivler: CSV + CSV'deki her tebligat. EN: archive a whole UETS round."""
    drive = _drive()
    sonuc = {"csv": csv_arsivle(csv_path, len(csv_items), drive), "arsivlenen": 0, "zaten": 0, "eyp_yok": 0, "hata": 0,
             "drive": bool(drive)}
    for it in csv_items:
        try:
            eyp = eyp_dizin.get(it.get("barcode")) if it.get("barcode") else None
            if not eyp and it.get("uets_no"):
                eyp = eyp_dizin.get(f"UETS:{it['uets_no']}")
            r = tebligat_arsivle(it, eyp, drive)
            sonuc[{"arsivlendi": "arsivlenen", "zaten": "zaten", "eyp_yok": "eyp_yok"}.get(r.get("durum"), "hata")] += 1
        except Exception as e:  # noqa: BLE001
            sonuc["hata"] += 1
            log(f"   ⚠️ Tebligat arşivlenemedi ({it.get('barcode') or it.get('uets_no')}): {e}")
    log(f"🗄️ Tebligat arşivi: {sonuc['arsivlenen']} yeni/güncellenen, {sonuc['zaten']} zaten arşivde, "
        f"{sonuc['eyp_yok']} EYP'siz (yalnız bilgi), {sonuc['hata']} hata — {'Google Drive' if drive else 'yerel arşiv (Drive tanımlı değil)'}.")
    yerel_temizle(log)
    return sonuc


def arsivde_mi(barkod: str) -> bool:
    """EYP'si arşive (Drive/yerel arşiv) alınmış mı? Yerelde olmaması yeniden indirme sebebi değildir."""
    if not barkod or not DB.exists():
        return False
    c = db()
    try:
        return bool(c.execute("SELECT 1 FROM tebligat WHERE anahtar=? AND durum='arsivlendi' AND COALESCE(eyp_sha,'')<>''",
                              (str(barkod),)).fetchone())
    finally:
        c.close()


def yerel_temizle(log=print) -> int:
    """Drive'a arşivlenmiş ve TEBLIGAT_YEREL_GUN günden eski yerel EYP'leri siler (arşivin asıl yeri Drive)."""
    try:
        gun = int(os.environ.get("TEBLIGAT_YEREL_GUN") or 30)
    except ValueError:
        gun = 30
    if gun <= 0 or not _drive():
        return 0
    try:
        from eyp_parser import scan_all_eyp_files
        from uets_downloader import eyp_barkod_dizini
        from eyp_parser import parse_eyp_file
        dizin = eyp_barkod_dizini(scan_all_eyp_files(), parse_eyp_file)
    except Exception:  # noqa: BLE001
        return 0
    sinir = time.time() - gun * 86400
    silinen = 0
    for barkod, yol in dizin.items():
        try:
            if os.path.getmtime(yol) < sinir and arsivde_mi(barkod):
                os.remove(yol)
                silinen += 1
        except OSError:
            continue
    if silinen:
        log(f"🧹 Drive'a arşivlenmiş {silinen} eski EYP yerelden kaldırıldı (>{gun} gün).")
    return silinen


def ara(q: str = "", mahkeme: str = "", baslangic: str = "", bitis: str = "", durum: str = "", limit: int = 200) -> dict:
    """Arşiv defterinde arama (Türkçe-duyarsız, -kelime hariç). EN: search the registry."""
    if not DB.exists():
        return {"tebligatlar": [], "toplam": 0}
    def katla(t):
        return str(t or "").translate(str.maketrans("İIıŞşĞğÜüÖöÇç", "iiissgguuoocc")).lower()
    c = db()
    try:
        sql, p = "SELECT * FROM tebligat WHERE 1=1", []
        if mahkeme:
            sql += " AND mahkeme LIKE ?"; p.append(f"%{mahkeme}%")
        if baslangic:
            sql += " AND gelis >= ?"; p.append(baslangic[:10])
        if bitis:
            sql += " AND gelis <= ?"; p.append(bitis[:10])
        if durum:
            sql += " AND durum = ?"; p.append(durum)
        rows = c.execute(sql + " ORDER BY gelis DESC", p).fetchall()
        terimler = katla(q).split()
        art = [t for t in terimler if not t.startswith("-")]
        eks = [t[1:] for t in terimler if t.startswith("-") and len(t) > 1]
        out = []
        for r in rows:
            metin = katla(" ".join(str(r[k] or "") for k in ("barkod", "uets_no", "mahkeme", "esas", "gonderen", "konu", "muvekkil", "json")))
            if all(t in metin for t in art) and not any(t in metin for t in eks):
                d = dict(r)
                d.pop("json", None)
                out.append(d)
        return {"tebligatlar": out[:limit], "toplam": len(out)}
    finally:
        c.close()


def detay(anahtar: str) -> dict:
    c = db()
    try:
        r = c.execute("SELECT * FROM tebligat WHERE anahtar=?", (anahtar,)).fetchone()
        if not r:
            return {"hata": "Arşivde bulunamadı"}
        d = dict(r)
        d["kayit"] = json.loads(d.pop("json") or "{}")
        d["ozet_md"] = ozet_md(d["kayit"])
        return d
    finally:
        c.close()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="UETS tebligat arşivi")
    ap.add_argument("komut", choices=["ara", "detay", "temizle"])
    ap.add_argument("q", nargs="*")
    a = ap.parse_args()
    if a.komut == "ara":
        print(json.dumps(ara(" ".join(a.q)), ensure_ascii=False, indent=2, default=str))
    elif a.komut == "detay":
        print(json.dumps(detay(" ".join(a.q)), ensure_ascii=False, indent=2, default=str))
    else:
        print(yerel_temizle())
