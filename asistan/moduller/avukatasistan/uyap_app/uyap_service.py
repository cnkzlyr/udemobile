#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gerçek UYAP verisi: köprü üzerinden salt-okunur çağrılar. Sahte/örnek veri YOKTUR."""
import os, re, json, time, urllib.parse
from datetime import datetime, timedelta

import uyap_bridge as ub

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(HERE, "last_real_data.json")


def dstr(d):
    return d.strftime("%d.%m.%Y")


def pick(d, pattern, default=""):
    """Anahtar adı desene uyan ilk dolu değeri döner."""
    rx = re.compile(pattern, re.I)
    for k, v in (d or {}).items():
        if rx.search(k) and v not in (None, "", [], {}):
            return v
    return default


def flat_list(r):
    if isinstance(r, list):
        out = []
        for x in r:
            if isinstance(x, dict):
                out.append(x)
            elif isinstance(x, list):
                out.extend(i for i in x if isinstance(i, dict))
        return out
    if isinstance(r, dict):
        for v in r.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
    return []


class UyapService:
    def __init__(self, bridge):
        self.b = bridge
        self._cache = {}
        self.disk = self._load_disk()

    # ---- önbellek ----
    def _load_disk(self):
        try:
            return json.load(open(CACHE_PATH, encoding="utf-8"))
        except Exception:
            return {}

    def _save_disk(self, k, v):
        self.disk[k] = {"ts": time.time(), "data": v}
        try:
            json.dump(self.disk, open(CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False)
        except Exception:
            pass

    def cached(self, key, ttl, fn):
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1], False
        try:
            data = fn()
            self._cache[key] = (time.time(), data)
            self._save_disk(key, data)
            return data, False
        except Exception:
            if key in self.disk:  # oturum yoksa son gerçek veriyi (önbellek) göster
                return self.disk[key]["data"], True
            raise

    # ---- veri ----
    def user(self):
        return self.cached("user", 600, lambda: self.b.call("/kullanici_bilgileri.uyap", {}))[0]

    def cases(self, status_code=0):
        def fetch():
            seen, out = set(), []

            def add(payload):
                for c in flat_list(self.b.call("/search_phrase_detayli.ajx", payload)):
                    cid = c.get("dosyaId")
                    if cid and cid not in seen:
                        seen.add(cid)
                        out.append(self._norm_case(c))
            base = {"birimId": "", "birimTuru2": "", "birimTuru3": "0", "dosyaDurumKod": status_code,
                    "pageNumber": 1, "pageSize": 500}
            add(base)
            if not out:  # boş birimTuru2 hepsini getirmediyse yargı birimi bazında dolaş
                for yt in ["0", "1", "2", "3", "4"]:
                    try:
                        birimler = self.b.call("/yargiBirimleriSorgula_brd.ajx", {"yargiTuru": yt})
                    except ub.BridgeError:
                        continue
                    for bm in flat_list(birimler):
                        t = bm.get("tablo")
                        if t:
                            add(dict(base, birimTuru2=t))
            return out
        return self.cached(f"cases{status_code}", 300, fetch)

    @staticmethod
    def _norm_case(c):
        ad = c.get("dosyaAcilisTarihi")
        acilis = ""
        if isinstance(ad, dict) and isinstance(ad.get("date"), dict):
            x = ad["date"]
            acilis = f"{x.get('day',1):02d}.{x.get('month',1):02d}.{x.get('year','')}"
        return {"dosyaId": c.get("dosyaId", ""), "birimAdi": c.get("birimAdi", ""), "dosyaNo": c.get("dosyaNo", ""),
                "dosyaTur": c.get("dosyaTur", ""), "dosyaDurum": c.get("dosyaDurum", ""), "acilisTarihi": acilis,
                "dosyaTurKod": c.get("dosyaTurKod", 0), "birimId": c.get("birimId", "")}

    def hearings(self, days_back=0, days_fwd=30):
        s, e = datetime.now() - timedelta(days=days_back), datetime.now() + timedelta(days=days_fwd)

        def fetch():
            raw = self.b.call("/avukat_durusma_sorgula_brd.ajx", {"baslangicTarihi": dstr(s), "bitisTarihi": dstr(e)})
            out = []
            for h in flat_list(raw):
                taraflar = h.get("dosyaTaraflari") or []
                ts = str(h.get("tarihSaat") or "")
                try:
                    dt = datetime.strptime(ts.split(".")[0], "%Y-%m-%d %H:%M:%S")
                    tarih, saat = dt.strftime("%d.%m.%Y"), dt.strftime("%H:%M")
                except Exception:
                    tarih, saat = ts, ""
                out.append({"dosyaId": h.get("dosyaId", ""), "dosyaNo": h.get("dosyaNo", ""),
                            "birimAdi": h.get("yerelBirimAd") or pick(h, r"birimAd"),
                            "tarih": tarih, "saat": saat, "tur": h.get("islemTuru", ""),
                            "sonuc": h.get("islemSonucu", ""), "ts": ts,
                            "taraflar": [{"isim": t.get("isim"), "sifat": t.get("sifat"), "vekil": t.get("isVekil")}
                                         for t in taraflar if isinstance(t, dict)],
                            "raw": {k: v for k, v in h.items() if k not in ("dosyaTaraflari",)}})
            return out
        return self.cached(f"hear{days_back}_{days_fwd}", 300, fetch)

    def notifications(self):
        return self.cached("notif", 120, lambda: flat_list(self.b.call("/get_kullanici_bildirimleri.ajx", {})))

    def evraklar(self, dosya_id):
        did = dosya_id if dosya_id.startswith('"') else f'"{dosya_id}"'

        def fetch():
            r = self.b.call("/list_dosya_evraklar.ajx", {"dosyaId": did, "pageNumber": 1})
            items = (r.get("tumEvraklar") or r.get("son20Evrak") or []) if isinstance(r, dict) else []
            out = []
            for e in items:
                if not isinstance(e, dict):
                    continue
                tur = str(pick(e, r"evrakTur|evrakAd|turAciklama"))
                out.append({"evrakId": e.get("evrakId", ""), "aciklama": e.get("aciklama", ""), "tur": tur,
                            "tarih": str(pick(e, r"tarih")), "ekSayisi": len(e.get("ekEvrakListesi") or []),
                            "raw": {k: v for k, v in e.items() if k != "ekEvrakListesi"}})
            return out
        return self.cached("ev:" + dosya_id, 300, fetch)

    def case_detail(self, dosya_id):
        did = dosya_id if dosya_id.startswith('"') else f'"{dosya_id}"'
        d = {"dosyaId": dosya_id}

        def safe(path, payload):
            try:
                return self.b.call(path, payload)
            except ub.BridgeError as ex:
                return {"_hata": str(ex)}
        d["ayrinti"] = safe("/dosyaAyrintiBilgileri_brd.ajx", {"dosyaId": did})
        d["taraflar"] = safe("/dosya_taraf_bilgileri_brd.ajx", {"dosyaId": did})
        sf = safe("/dosya_safahat_bilgileri_brd.ajx", {"dosyaId": did})
        d["safahat"] = [{"tarih": s.get("safahatTarihiSTR", ""), "islem": s.get("safahatTuruAciklama", ""),
                         "aciklama": s.get("aciklama", ""), "birim": s.get("islemYapanBirim", "")}
                        for s in (sf.get("safahatlar") or [])] if isinstance(sf, dict) else []
        d["hesap"] = safe("/dosya_hesap_bilgileri.ajx", {"dosyaId": did})
        d["evraklar"] = self.evraklar(dosya_id)[0]
        return d

    def document(self, evrak_id, dosya_id):
        q = lambda v: urllib.parse.quote(v if v.startswith('"') else f'"{v}"', safe="")
        return self.b.fetch_binary(f"/view_document_brd.uyap?evrakId={q(evrak_id)}&dosyaId={q(dosya_id)}")

    def stats(self):
        cases, c1 = self.cases()
        hear, _ = self.hearings(0, 7)
        notif, _ = self.notifications()
        return {"dosya": len(cases), "yaklasanDurusma": len(hear), "bildirim": len(notif), "onbellek": c1}
