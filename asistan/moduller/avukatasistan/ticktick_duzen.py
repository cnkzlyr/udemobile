#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TICKTICK DÜZENİ — "hiçbir iş kaçmasın" denetimi (asistan görevi: ticktick-duzen)

Sırasıyla:
  1. MÜKERRER TEMİZLİĞİ (TÜM listeler; aktif + tamamlanan + YAPILMAYACAK görevler birlikte):
     - Aynı kimlikli (tebligatta barkod, duruşmada dosya+gün, dosya kartında mahkeme+esas) birden çok AKTİF görev:
       en dolu olanı (eki olan > alt görevi olan > notu uzun olan > en eski) kalır; diğerlerinin alt görevleri
       kalana taşınır, kullanıcı notu kalanın sonuna eklenir, kopya SİLİNMEZ, "tamamlandı" yapılır (geri alınabilir).
     - Aynı kimlikli görev daha önce TAMAMLANMIŞ / YAPILMAYACAK yapılmışsa yeniden açılmış aktif kopya kapatılır.
     - Eski tebligat birleştiricisi (clean_and_merge_duplicates, clean_completed_duplicates) de çalışır.
  2. STANDART BİÇİM DENETİMİ (gorev_format): her tebligat/duruşma/dosya kartının zorunlu öğeleri denetlenir;
     eksik görev "⚠️ EKSİK: ..." satırı ve 'eksik' etiketi alır (tamamlanınca kalkar). Eki ya da üstyazısı olmayan
     tebligatların barkodları 'eksik_tebligatlar.json'a yazılır: bir sonraki UETS turu bunları yeniden indirip
     görevi tamamlar (uets_downloader.check_missing_tebligatlar_in_ticktick).
  3. HER NOTION DOSYASINA BİR TICKTICK DOSYA KARTI: Notion'da açık (Kapalı/Arşivde olmayan) her dosyanın kartı
     yoksa açılır (kapalı kopyası varsa açılmaz); her kartın "📌 Dosya konusu" bölümü Notion'daki DOSYA KONUSU
     ile güncellenir. BİLGİ NOTU türündeki kayıtlar "📝 Bilgi Notu - <başlık>" kartı alır, konu onlara da yazılır.
     Kartsız (yetim) tebligat/duruşma görevleri kartlarına bağlanır (audit_and_heal_all_tasks).

Kullanım:  python ticktick_duzen.py            (önizleme: yalnızca rapor)
           python ticktick_duzen.py --uygula   (düzeltir)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

BURASI = Path(__file__).resolve().parent
sys.path.insert(0, str(BURASI))
sys.path.insert(0, str(BURASI.parent.parent))  # asistan/ (notion_uyap, entegrasyon)

import gorev_format as gf  # noqa: E402
import kimlik  # noqa: E402
import ticktick_sync as ts  # noqa: E402
from config import CONFIG, PROJECT_IDS  # noqa: E402
from utils import clean_text, determine_list, is_excluded, resolve_client_tag  # noqa: E402

EKSIK_DOSYA = BURASI / "eksik_tebligatlar.json"
KAPALI_DURUMLAR = {"Kapalı", "Arşivde"}


def _baslik_kimlik(t):
    """Kimlik satırı olmayan eski görevlerden kimlik çıkarır (yalnız standart başlıklı olanlar)."""
    k = kimlik.oku(t.get("content") or "")
    if k:
        return k
    baslik = t.get("title") or ""
    # v4.5 ve öncesinin kimliksiz "📄 <tür> — <birim> <esas>" UYAP evrak görevleri (mükerrerlerin kaynağıydı)
    if baslik.startswith("📄"):
        c = (t.get("content") or "").replace("\\", "")
        mb, md, mt = (re.search(r"Mahkeme/Birim:\s*(.+)", c), re.search(r"Dosya No:\s*(\d{4}/\d+)", c),
                      re.search(r"Evrak Türü:\s*(.+)", c))
        if mb and md:
            tarih = re.search(r"Tarih:\s*(\S+)", c)
            return {"tur": "EVRAK", "mahkeme": mb.group(1).strip(), "esas": md.group(1),
                    "konu": f"{(mt.group(1).strip() if mt else 'Evrak')} {(tarih.group(1)[:10] if tarih else '')}".strip(), "_eski": True}
        return {}
    tur = gf.tur_bul(t)
    m = re.search(r"^(?:📨\s*TEBLİGAT - |⚖️\s*DURUŞMA - )?(.*?) - (\d{4}/\d+) Esas", baslik)
    if not tur or not m:
        return {}
    k = {"tur": tur, "mahkeme": m.group(1).strip(), "esas": m.group(2)}
    if tur == "TEBLİGAT":
        k["barkod"] = ts.extract_barcode_from_text(t.get("content") or "") or ""
        if not k["barkod"]:
            return {}
    if tur == "DURUŞMA":
        md = re.search(r"Duruşma Tarihi:\**\s*([0-9./]+)", (t.get("content") or "").replace("\\", ""))
        if not md:
            return {}
        k["durusma"] = md.group(1)
    return k


def _puan(t):
    c = t.get("content") or ""
    return ("![file]" in c, bool(t.get("childIds")), len(c), -int(str(t.get("id") or "0")[:8], 16) if re.match(r"^[0-9a-f]{8}", str(t.get("id") or "")) else 0)


def _kullanici_notu(c):
    """Sistem satırları dışında kalan (kullanıcının yazdığı olası) not satırları."""
    out = []
    for s in (c or "").replace("\\", "").splitlines():
        st = s.strip()
        if not st or st.startswith(kimlik.ONEK) or st.startswith(gf.EKSIK_ONEK) or st.startswith("- **") \
                or st.startswith("🔔") or st.startswith("⚖️") or st.startswith("🔗") or st.startswith("👤") or "![file]" in st:
            continue
        out.append(s)
    return "\n".join(out).strip()


def _tamamla(t, not_metni, uygula, rapor, neden):
    rapor["kapatilan"].append(f"{(t.get('title') or '')[:70]} — {neden}")
    if not uygula:
        return
    pid = t.get("projectId") or t.get("_pid")
    ts.tt_post(f"{CONFIG['TICKTICK_API_BASE']}/task/{t['id']}",
               {"id": t["id"], "projectId": pid, "content": ((t.get("content") or "") + f"\n\n♻️ {not_metni}").strip()},
               what="mükerrer işaretleme")
    try:
        ts.requests.post(f"{CONFIG['TICKTICK_API_BASE']}/project/{pid}/task/{t['id']}/complete",
                         headers=ts.get_ticktick_headers(), timeout=10)
    except Exception as e:  # noqa: BLE001
        rapor["hatalar"].append(f"Tamamlanamadı {t['id']}: {e}")


def mukerrer_temizle(uygula, rapor):
    aktif = ts.tum_aktif_gorevler(force=True)
    kapali = ts.get_completed_tasks_live(force_refresh=True)
    kapali_anahtar = {}
    for t in kapali:
        a = ts._kimlik_anahtari(_baslik_kimlik(t))
        if a:
            kapali_anahtar.setdefault(a, t)
    gruplar: dict = {}
    for t in aktif:
        if t.get("status", 0) != 0:
            continue
        a = ts._kimlik_anahtari(_baslik_kimlik(t))
        if a:
            gruplar.setdefault(a, []).append(t)
    rapor["kapali_sayisi"] = len(kapali)
    rapor["yapilmayacak_sayisi"] = sum(1 for t in kapali if t.get("status") == -1)
    for a, liste in gruplar.items():
        # (a) kapatılmış görevin yeniden açılmış kopyaları
        kt = kapali_anahtar.get(a)
        if kt and a[0] in ("TEBLİGAT", "EK"):
            lbl = "yapılmayacak" if kt.get("status") == -1 else "tamamlandı"
            for t in liste:
                _tamamla(t, f"Bu görev daha önce '{lbl}' yapılmış aynı tebligatın kopyasıydı; otomatik kapatıldı.", uygula, rapor,
                         f"kapalı ({lbl}) kopya")
            continue
        if len(liste) < 2:
            t0 = liste[0]
            k0 = _baslik_kimlik(t0)
            if k0.get("_eski") and uygula:   # eski kimliksiz evrak görevine kimlik satırı: bundan sonra tanınır
                ts.tt_post(f"{CONFIG['TICKTICK_API_BASE']}/task/{t0['id']}",
                           {"id": t0["id"], "projectId": t0.get("projectId"),
                            "content": kimlik.ekle(t0.get("content") or "", kimlik.satir("EVRAK", mahkeme=k0["mahkeme"], esas=k0["esas"], konu=k0["konu"]))},
                           what="kimlik ekleme")
            continue
        # (b) aynı kimlikli birden çok aktif görev: en dolusu kalır
        liste.sort(key=_puan, reverse=True)
        kalan, fazlalar = liste[0], liste[1:]
        ek_notlar = []
        for f in fazlalar:
            n = _kullanici_notu(f.get("content"))
            if n and n not in _kullanici_notu(kalan.get("content")):
                ek_notlar.append(n)
            for cid in f.get("childIds") or []:
                rapor["tasinan_alt"] += 1
                if uygula and (f.get("projectId") == kalan.get("projectId")):
                    ts.tt_post(f"{CONFIG['TICKTICK_API_BASE']}/task/{cid}",
                               {"id": cid, "projectId": kalan.get("projectId"), "parentId": kalan["id"]}, what="alt görev taşıma")
            _tamamla(f, "Aynı işin kopyasıydı; notları ve alt görevleri asıl göreve taşındı, bu kopya kapatıldı.", uygula, rapor, "aktif kopya")
        if ek_notlar and uygula:
            ts.tt_post(f"{CONFIG['TICKTICK_API_BASE']}/task/{kalan['id']}",
                       {"id": kalan["id"], "projectId": kalan.get("projectId"),
                        "content": (kalan.get("content") or "") + "\n\n♻️ **Birleştirilen kopyalardaki notlar:**\n" + "\n---\n".join(ek_notlar)},
                       what="not birleştirme")
    # Eski (yalnız tebligat) birleştiriciler: başlık/son gün bozulmalarını da düzeltir
    if uygula:
        try:
            m, d = ts.clean_and_merge_duplicates()
            rapor["eski_birlestirici"] = {"birlesen": m, "silinen": d, "kapali_silinen": ts.clean_completed_duplicates()}
        except Exception as e:  # noqa: BLE001
            rapor["hatalar"].append(f"Eski birleştirici: {e}")


def bicim_denetle(uygula, rapor, konular):
    eksik_barkod = set()
    for t in ts.tum_aktif_gorevler(force=True):
        if t.get("status", 0) != 0:
            continue
        tur = gf.tur_bul(t)
        if tur not in ("TEBLİGAT", "DURUŞMA", "DOSYA"):
            continue
        k = _baslik_kimlik(t)
        content = t.get("content") or ""
        yeni_c = content
        # Dosya kartına Notion konusu (aynı mahkeme+esas)
        if tur == "DOSYA":
            anahtar = (k.get("esas") or "", clean_text(k.get("mahkeme") or ""))
            kayit = konular.get(anahtar) or konular.get((k.get("esas") or "", ""))
            if kayit and kayit.get("konu") and gf.konu_oku(content) != kayit["konu"].strip():
                yeni_c = gf.konu_blogu(yeni_c, kayit["konu"], "Notion")
                rapor["konu_yazilan"] += 1
            if not kimlik.var_mi(yeni_c) and k:
                yeni_c = kimlik.ekle(yeni_c, kimlik.satir("DOSYA", mahkeme=k.get("mahkeme"), esas=k.get("esas")))
        ek_var = None
        if tur == "TEBLİGAT":
            barkod = k.get("barkod") or ts.extract_barcode_from_text(content) or ""
            ek_var = ts.gercek_ek_var(t, barkod) if barkod else False
        eksik = gf.eksikler({**t, "content": yeni_c}, ek_var=ek_var)
        if tur == "TEBLİGAT" and eksik and k.get("barkod"):
            eksik_barkod.add(k["barkod"])
        yeni_c, yeni_tags, degisti = gf.eksik_isaretle(yeni_c, t.get("tags") or [], eksik)
        if eksik:
            rapor["eksik"].append(f"{(t.get('title') or '')[:60]}: {', '.join(eksik)}")
        if (degisti or yeni_c != content) and uygula:
            ts.tt_post(f"{CONFIG['TICKTICK_API_BASE']}/task/{t['id']}",
                       {"id": t["id"], "projectId": t.get("projectId") or t.get("_pid"), "content": yeni_c, "tags": yeni_tags},
                       what="standart biçim")
    rapor["eksik_tebligat_barkod"] = len(eksik_barkod)
    if uygula:
        EKSIK_DOSYA.write_text(json.dumps({"zaman": time.strftime("%Y-%m-%d %H:%M:%S"), "barkodlar": sorted(eksik_barkod)},
                                          ensure_ascii=False, indent=1), encoding="utf-8")


def notion_dosyalari():
    """Notion 'Tüm Dosyalar' kayıtları (tamamı): mahkeme, esas, durum, tür, konu, url, müvekkil, CMK."""
    import entegrasyon
    import notion_uyap as nu
    ayar = entegrasyon.env_oku(BURASI)
    token = (ayar.get("NOTION_TOKEN") or CONFIG.get("NOTION_TOKEN") or "").strip()
    if not token:
        return None
    n = nu.Notion(token)
    out = []
    for p in n.tum_sayfalar((ayar.get("NOTION_DB_DOSYALAR") or entegrasyon.VARSAYILAN_NOTION_DB).strip()):
        pr = p.get("properties") or {}
        baslik = nu._metin(pr.get("NOTION DOSYA"))
        mahkeme, esas = nu._metin(pr.get("MAHKEME/BİRİM")), nu._metin(pr.get("DOSYA NO"))
        if (not mahkeme or not esas) and " - " in baslik:
            parca = baslik.split(" - ")
            mahkeme, esas = mahkeme or parca[0].strip(), esas or parca[-1].strip()
        muv = ""
        for x in ((pr.get("Müvekkil Adı") or {}).get("rollup") or {}).get("array") or []:
            muv = nu._metin(x) or muv
        vk = [((x.get("select") or {}).get("name") or "").upper() for x in ((pr.get("VEKALET İLİŞKİSİ") or {}).get("rollup") or {}).get("array") or []]
        out.append({"baslik": baslik, "mahkeme": mahkeme.strip(), "esas": nu.esas_norm(esas), "durum": nu._metin(pr.get("DURUM")),
                    "tur": nu._metin(pr.get("DOSYA TÜRÜ")), "konu": nu._metin(pr.get("DOSYA KONUSU")), "url": p.get("url", ""),
                    "muvekkil": muv, "cmk": "CMK" in vk})
    return out


def dosya_kartlari(uygula, rapor, nd):
    for d in nd:
        if d["durum"] in KAPALI_DURUMLAR:
            continue
        bilgi_notu = (d["tur"] or "").upper() == "BİLGİ NOTU" or not (d["mahkeme"] and d["esas"])
        if is_excluded(f"{d['mahkeme']} {d['esas']} {d['muvekkil']}"):
            continue
        if bilgi_notu:
            if not d["baslik"]:
                continue
            k = {"tur": "DOSYA", "konu": d["baslik"][:150]}
            var = None
            for t in ts.tum_aktif_gorevler():
                if ts._kimlik_anahtari(kimlik.oku(t.get("content") or "")) == ts._kimlik_anahtari(k):
                    var = t
                    break
            if var or ts.kapali_kopya_bul({"content": kimlik.satir("DOSYA", konu=k["konu"])}):
                continue
            rapor["yeni_kart"].append("📝 Bilgi Notu - " + d["baslik"][:60])
            if uygula:
                icerik = gf.dosya_karti_icerigi("", "", "", d["url"], konu=d["konu"], baslik_konu=k["konu"])
                ts.tt_post(f"{CONFIG['TICKTICK_API_BASE']}/task",
                           {"title": f"📝 Bilgi Notu - {d['baslik'][:120]}", "projectId": PROJECT_IDS.get("Inbox") or "inbox",
                            "content": icerik, "priority": 0, "tags": ["bilgi_notu"]}, what="bilgi notu kartı")
            continue
        var = ts.kimlige_gore_bul("DOSYA", esas=d["esas"], mahkeme=d["mahkeme"])
        if var:
            continue
        # Kimliksiz eski kartlar: başlığa göre (aynı esas + mahkeme)
        eski = None
        for t in ts.tum_aktif_gorevler():
            if gf.tur_bul(t) == "DOSYA" and d["esas"] in (t.get("title") or "") and \
                    clean_text(d["mahkeme"])[:20] in clean_text(t.get("title") or ""):
                eski = t
                break
        if eski:
            continue
        if ts.kapali_kopya_bul({"content": kimlik.satir("DOSYA", mahkeme=d["mahkeme"], esas=d["esas"])}):
            continue
        rapor["yeni_kart"].append(f"{d['mahkeme']} - {d['esas']} Esas")
        if uygula:
            liste = determine_list(d["mahkeme"])
            pid = PROJECT_IDS.get(liste) or PROJECT_IDS.get("Inbox") or "inbox"
            tag = resolve_client_tag(d["muvekkil"], is_cmk=d["cmk"]) if d["muvekkil"] else ""
            try:
                ts.find_or_create_parent_task(d["mahkeme"], d["esas"], pid, client_tag=tag, notion_url=d["url"], konu=d["konu"])
            except Exception as e:  # noqa: BLE001
                rapor["hatalar"].append(f"Kart {d['esas']}: {e}")


def calistir(uygula=False):
    rapor = {"mod": "uygula" if uygula else "onizleme", "kapatilan": [], "tasinan_alt": 0, "eksik": [], "konu_yazilan": 0,
             "yeni_kart": [], "hatalar": []}
    print("🧹 1/4 Mükerrerler (aktif + tamamlanan + yapılmayacak)...", flush=True)
    mukerrer_temizle(uygula, rapor)
    print(f"   ↳ {len(rapor['kapatilan'])} kopya {'kapatıldı' if uygula else 'kapatılacak'} "
          f"({rapor.get('kapali_sayisi', 0)} kapalı görev, {rapor.get('yapilmayacak_sayisi', 0)} yapılmayacak dahil denetlendi)", flush=True)
    print("📒 2/4 Notion dosyaları okunuyor...", flush=True)
    try:
        nd = notion_dosyalari() or []
    except Exception as e:  # noqa: BLE001
        nd = []
        rapor["hatalar"].append(f"Notion okunamadı: {e}")
    konular = {}
    for d in nd:
        if d["konu"] and d["esas"]:
            konular[(d["esas"], clean_text(d["mahkeme"]))] = d
            konular.setdefault((d["esas"], ""), d)
    if nd:
        print(f"🗂️ 3/4 Dosya kartları ({len(nd)} Notion dosyası)...", flush=True)
        dosya_kartlari(uygula, rapor, nd)
        print(f"   ↳ {len(rapor['yeni_kart'])} eksik kart {'açıldı' if uygula else 'açılacak'}", flush=True)
        ts._TUM_GOREVLER = None
    print("🧾 4/4 Standart biçim ve eksik tebligat denetimi...", flush=True)
    bicim_denetle(uygula, rapor, konular)
    print(f"   ↳ {len(rapor['eksik'])} eksik görev, {rapor['konu_yazilan']} dosya konusu, "
          f"{rapor.get('eksik_tebligat_barkod', 0)} tebligat bir sonraki UETS turunda yeniden indirilecek", flush=True)
    if uygula:
        try:
            ts.audit_and_heal_all_tasks()
        except Exception as e:  # noqa: BLE001
            rapor["hatalar"].append(f"Denetim: {e}")
    for h in rapor["hatalar"][:10]:
        print("   ⚠️ " + h, flush=True)
    return rapor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true")
    a = ap.parse_args()
    if not CONFIG.get("TICKTICK_TOKEN"):
        print("[!] TickTick anahtarı yok (Entegrasyonlar sekmesinden girin).")
        return 2
    r = calistir(uygula=a.uygula)
    ozet = {k: (len(v) if isinstance(v, list) else v) for k, v in r.items()}
    print("@@SONUC@@" + json.dumps(ozet, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
