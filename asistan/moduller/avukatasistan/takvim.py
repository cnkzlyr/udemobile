#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📅 AJANDA TAKVİMİ -> TickTick DURUŞMA EŞİTLEMESİ

Duruşmaların ASIL KAYNAĞI Google Takvim'deki AJANDA takvimidir (UYAP'tan kendiliğinden yükleniyor).
Bu modül takvimi düzenli okur ve TickTick'teki duruşma görevlerini ona göre tutar:

  • Yeni duruşma/keşif/ön inceleme  -> dava kartının altına "⚖️ DURUŞMA" görevi (tarih, saat, müvekkil etiketi)
  • Duruşma ERTELENDİ / saati değişti -> aynı görevin tarihi kaydırılır (yeni görev açılmaz)
  • Duruşma takvimden SİLİNDİ/iptal    -> görev silinmez, Telegram'dan haber verilir
  • Aynı duruşma takvimde iki kez varsa (UYAP + elle girilen) tek görev olur
  • Müvekkil, açıklamadaki "[Vekil: ... SİZİN ADINIZ ...]" yazan taraftan KESİN olarak bulunur

Ayar (.env):
  AJANDA_ICS_URL=https://calendar.google.com/calendar/ical/.../private-.../basic.ics
     Google Takvim > Ayarlar > AJANDA > "Takvimi entegre et" > "iCal biçimindeki gizli adres"
  AVUKAT_ADI=AD SOYAD     (açıklamadaki vekil adınız; yazılmazsa en sık geçen vekil adı kullanılır)

Çalıştırma:  python3 asistan.py takvim      (izleyici her turda kendiliğinden çalıştırır)
"""

import collections
import os
import re
from datetime import datetime, timedelta, timezone

from config import CONFIG, TZ_TURKEY, PROJECT_IDS

TURLER = ("DURUŞMA", "DURUSMA", "KEŞİF", "KESIF", "KEŞIF", "ÖN İNCELEME", "ON INCELEME", "ÖN INCELEME",
          "TENSİP", "BİLİRKİŞİ", "İSTİNAF DURUŞMASI", "CELSE")
ESAS_RE = re.compile(r"(\d{4}/\d+)")


# ---------------------------------------------------------------- iCal okuma (bağımlılıksız)
def _satirlari_ac(metin):
    """iCal satır katlamasını açar (devam satırları boşluk/sekme ile başlar)."""
    satirlar = []
    for ham in metin.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if ham[:1] in (" ", "\t") and satirlar:
            satirlar[-1] += ham[1:]
        else:
            satirlar.append(ham)
    return satirlar


def _kacis_coz(v):
    return v.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _tarih(deger, parametreler):
    """DTSTART değeri -> TR saatinde datetime. 'Z' (UTC), TZID'li yerel ve tüm gün (VALUE=DATE) desteklenir."""
    v = deger.strip()
    try:
        if re.fullmatch(r"\d{8}", v):
            return datetime.strptime(v, "%Y%m%d").replace(tzinfo=TZ_TURKEY), True
        if v.endswith("Z"):
            return datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(TZ_TURKEY), False
        dt = datetime.strptime(v[:15], "%Y%m%dT%H%M%S")
        # TZID=Europe/Istanbul ya da yerel: Türkiye saati kabul edilir (UTC+3, yaz saati yok)
        return dt.replace(tzinfo=TZ_TURKEY), False
    except ValueError:
        return None, False


def ics_olaylari(metin):
    """iCal metnindeki VEVENT'leri sözlük listesine çevirir."""
    olaylar, cur = [], None
    for s in _satirlari_ac(metin):
        if s == "BEGIN:VEVENT":
            cur = {}
        elif s == "END:VEVENT":
            if cur is not None:
                olaylar.append(cur)
            cur = None
        elif cur is not None and ":" in s:
            ad_param, deger = s.split(":", 1)
            ad, *param = ad_param.split(";")
            if ad in ("DTSTART", "DTEND"):
                dt, tum_gun = _tarih(deger, param)
                cur[ad] = dt
                if ad == "DTSTART":
                    cur["TUM_GUN"] = tum_gun
            elif ad in ("SUMMARY", "DESCRIPTION", "LOCATION", "UID", "STATUS", "LAST-MODIFIED", "RECURRENCE-ID"):
                cur[ad] = _kacis_coz(deger)
    return olaylar


# ---------------------------------------------------------------- duruşma ayrıştırma
_TARAF_RE = re.compile(r"^\s*([^:\n\[\]]{2,60}):\s*([^\[\n]+?)\s*\[Vekil:\s*([^\]]*)\]", re.M)


def taraflar(aciklama):
    """'Davacı:ADEM TAŞDEMİR[Vekil: CAN KIZILYAR]' satırları -> [(rol, ad, [vekiller])]"""
    out = []
    for m in _TARAF_RE.finditer(aciklama or ""):
        vekiller = [v.strip() for v in m.group(3).split(",") if v.strip()]
        out.append((m.group(1).strip(), m.group(2).strip(), vekiller))
    return out


def durusma_mi(olay):
    ozet = (olay.get("SUMMARY") or "").upper()
    return bool(ESAS_RE.search(ozet + " " + (olay.get("DESCRIPTION") or "")[:200])) and \
        (any(t in ozet for t in TURLER) or ozet.startswith(("DURUŞMA", "DURUSMA")))


def ayristir(olay):
    """Takvim olayı -> {uid, tur, esas, mahkeme, baslangic, taraflar}. Duruşma değilse None."""
    if not durusma_mi(olay) or not olay.get("DTSTART"):
        return None
    ozet = (olay.get("SUMMARY") or "").strip()
    m = re.match(r"^\s*([^-–:]+?)\s*[-–:]\s*(\d{4}/\d+)\s*(.*)$", ozet)
    if m:
        tur, esas, mahkeme = m.group(1).strip().upper(), m.group(2), m.group(3).strip()
    else:
        me = ESAS_RE.search(ozet) or ESAS_RE.search(olay.get("DESCRIPTION") or "")
        tur, esas, mahkeme = (ozet.split()[0].upper() if ozet else "DURUŞMA"), me.group(1), ""
    mahkeme = mahkeme or (olay.get("LOCATION") or "").strip()
    return {"uid": olay.get("UID") or f"{esas}|{olay['DTSTART'].isoformat()}", "tur": tur, "esas": esas,
            "mahkeme": mahkeme, "baslangic": olay["DTSTART"], "tum_gun": olay.get("TUM_GUN", False),
            "iptal": (olay.get("STATUS") or "").upper() == "CANCELLED",
            "taraflar": taraflar(olay.get("DESCRIPTION") or ""), "ozet": ozet}


def avukat_adi(durusmalar):
    """AVUKAT_ADI yoksa açıklamalarda vekil olarak EN SIK geçen ad (takvim sahibinin kendisi)."""
    ad = (os.environ.get("AVUKAT_ADI") or CONFIG.get("AVUKAT_ADI") or "").strip()
    if ad:
        return ad.upper()
    sayac = collections.Counter(v.upper() for d in durusmalar for _, _, vs in d["taraflar"] for v in vs)
    return sayac.most_common(1)[0][0] if sayac else ""


def muvekkiller(durusma, avukat):
    return [(rol, ad) for rol, ad, vs in durusma["taraflar"] if avukat and any(avukat == v.upper() for v in vs)]


def tekillestir(durusmalar):
    """Aynı esas + aynı başlangıç saati = aynı duruşma (UYAP'tan gelen + elle girilen kopya). Ayrıntılı olan kalır."""
    gruplar = {}
    for d in durusmalar:
        an = (d["esas"], d["baslangic"].strftime("%Y%m%d%H%M"))
        onceki = gruplar.get(an)
        if onceki is None or (len(d["taraflar"]), len(d["mahkeme"])) > (len(onceki["taraflar"]), len(onceki["mahkeme"])):
            if onceki is not None and not d["mahkeme"]:
                d["mahkeme"] = onceki["mahkeme"]
            gruplar[an] = d
    return list(gruplar.values())


# ---------------------------------------------------------------- TickTick eşitleme
def takvimi_indir(url=None):
    import requests
    url = url or os.environ.get("AJANDA_ICS_URL") or CONFIG.get("AJANDA_ICS_URL")
    if not url:
        raise RuntimeError("AJANDA_ICS_URL ayarlı değil (.env). Google Takvim > AJANDA ayarları > 'iCal biçimindeki gizli adres'.")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.text


def esitle(ics_metni=None, gun_geri=1, gun_ileri=400, bildir=None):
    """Takvimdeki duruşmaları TickTick'e işler. Döner: özet sözlüğü."""
    import defter
    import kimlik
    from ticktick_sync import (find_or_create_parent_task, create_or_update_durusma_subtask, gorev_getir,
                               update_task_details, tum_aktif_gorevler)
    from utils import determine_list, resolve_client_tag, tt_iso

    metin = ics_metni if ics_metni is not None else takvimi_indir()
    simdi = datetime.now(TZ_TURKEY)
    hepsi = [d for d in (ayristir(o) for o in ics_olaylari(metin)) if d]
    avukat = avukat_adi(hepsi)
    pencere = [d for d in hepsi if simdi - timedelta(days=gun_geri) <= d["baslangic"] <= simdi + timedelta(days=gun_ileri)]
    durusmalar = tekillestir(pencere)
    ozet = {"takvim_durusma": len(durusmalar), "yeni": 0, "ertelenen": 0, "ayni": 0, "iptal": 0, "hata": 0}
    print(f"📅 AJANDA: {len(hepsi)} duruşma kaydı, işlenecek (yakın/gelecek, tekil): {len(durusmalar)}"
          + (f" · vekil adı: {avukat}" if avukat else ""))
    import time as _time
    t0 = _time.time()
    print("   ⏳ TickTick görevleri okunuyor (ilk seferde listelerin sayısına göre biraz sürebilir)...", flush=True)
    tum_aktif_gorevler()
    print(f"   ↳ {len(tum_aktif_gorevler())} aktif görev okundu ({_time.time() - t0:.0f} sn)", flush=True)
    for sira, d in enumerate(durusmalar, 1):
        print(f"   [{sira}/{len(durusmalar)}] {d['baslangic'].strftime('%d.%m.%Y %H:%M')} {d['mahkeme'][:45]} {d['esas']}"
              f"  ({_time.time() - t0:.0f} sn)", flush=True)
        try:
            tarih = d["baslangic"].strftime("%d/%m/%Y")
            saat = "" if d["tum_gun"] else d["baslangic"].strftime("%H:%M")
            kayit = defter.durusma_getir(d["uid"])
            if d["iptal"]:
                if kayit and kayit.get("ticktick_id") and not kayit.get("iptal"):
                    m = f"⚠️ Takvimde İPTAL: {d['ozet']} ({tarih} {saat}). TickTick görevi silinmedi, kontrol edin."
                    print("   " + m)
                    if bildir and defter.uyari_yeni_mi("iptal:" + d["uid"], m):
                        bildir(m)
                defter.durusma_kaydet(d["uid"], d["mahkeme"], d["esas"], d["baslangic"], d["ozet"], iptal=True)
                ozet["iptal"] += 1
                continue

            # ERTELENME: aynı takvim olayı, farklı başlangıç -> mevcut görevin tarihi kaydırılır
            if kayit and kayit.get("ticktick_id") and kayit.get("baslangic") and \
                    kayit["baslangic"].strftime("%Y%m%d%H%M") != d["baslangic"].strftime("%Y%m%d%H%M"):
                t = next((x for x in tum_aktif_gorevler() if x.get("id") == kayit["ticktick_id"]), None)
                if t:
                    yeni_iso = tt_iso(d["baslangic"])
                    icerik = t.get("content") or ""
                    k_satir = kimlik.satir("DURUŞMA", mahkeme=d["mahkeme"], esas=d["esas"], durusma=f"{tarih} {saat}".strip())
                    icerik = kimlik.ekle(icerik, k_satir)
                    icerik += f"\n\n📅 Takvimde ertelendi: {kayit['baslangic'].strftime('%d.%m.%Y %H:%M')} → {tarih} {saat}"
                    update_task_details(t["id"], t.get("projectId"), None, start_iso=yeni_iso, due_iso=yeni_iso, content=icerik)
                    defter.durusma_kaydet(d["uid"], d["mahkeme"], d["esas"], d["baslangic"], d["ozet"], ticktick_id=t["id"])
                    print(f"   🔁 Ertelendi: {d['mahkeme']} {d['esas']} → {tarih} {saat} (görev güncellendi, başlığınız korunuyor)")
                    if bildir:
                        bildir(f"🔁 Duruşma ertelendi: {d['mahkeme']} {d['esas']} → {tarih} {saat}")
                    ozet["ertelenen"] += 1
                    continue

            # Müvekkil: takvimde vekili biz olan taraf (kesin); yoksa dosya defteri
            muv = muvekkiller(d, avukat)
            etiket = resolve_client_tag(muv[0][1]) if muv else ""
            if not etiket:
                try:
                    dk = defter.dosya_bul(d["esas"], d["mahkeme"])
                    etiket = (dk or {}).get("muvekkil_etiket") or ""
                except Exception:
                    pass
            notion_url = ""
            try:
                from notion_sync import find_notion_case
                nc = find_notion_case(d["esas"], d["mahkeme"])
                if nc:
                    notion_url = nc.get("url") or ""
                    etiket = etiket or nc.get("client_tag") or ""
            except Exception:
                pass
            liste = determine_list(d["mahkeme"])
            pid = PROJECT_IDS.get(liste) or PROJECT_IDS.get("Inbox", "inbox")
            is_cmk = "cmk" in (etiket or "").lower() or any(k in d["mahkeme"].lower() for k in ("ceza", "soruşturma"))
            parent = find_or_create_parent_task(d["mahkeme"], d["esas"], pid, etiket, notion_url)
            parent_id = parent[0] if isinstance(parent, (tuple, list)) else parent
            if isinstance(parent, (tuple, list)) and len(parent) > 1 and parent[1]:
                pid = parent[1]
            belge = f"AJANDA takvimi ({d['tur'].title()})"
            if muv:
                belge += " · Müvekkil: " + ", ".join(f"{ad} ({rol})" for rol, ad in muv[:3])
            tid, yeni = create_or_update_durusma_subtask(d["mahkeme"], d["esas"], pid, parent_id, tarih, saat,
                                                         etiket, notion_url, belge, is_cmk=is_cmk)
            defter.durusma_kaydet(d["uid"], d["mahkeme"], d["esas"], d["baslangic"], d["ozet"], ticktick_id=tid)
            if yeni:
                ozet["yeni"] += 1
                print(f"   ⚖️ Yeni duruşma görevi: {d['mahkeme']} {d['esas']} {tarih} {saat}")
            else:
                ozet["ayni"] += 1
        except Exception as e:
            ozet["hata"] += 1
            print(f"   ⚠️ {d.get('ozet')}: {e}")
    # Aynı dosya + aynı gün için birden çok duruşma görevi (ör. eski görevler + takvimden açılan) birleştirilir;
    # kullanıcının eski görevi (başlık, notlar, alt görevler) kalır.
    try:
        from ticktick_sync import durusma_mukerrerlerini_birlestir
        print("   🔎 Mükerrer duruşma görevleri aranıyor...", flush=True)
        b_say, s_say = durusma_mukerrerlerini_birlestir()
        ozet["birlesen"], ozet["silinen_kopya"] = b_say, s_say
        if b_say:
            print(f"🔗 Mükerrer duruşma görevleri birleştirildi: {b_say} grup, {s_say} kopya silindi")
    except Exception as e:
        print(f"⚠️ Mükerrer duruşma kontrolü yapılamadı: {e}")
    print(f"📅 Takvim eşitlemesi: yeni {ozet['yeni']}, ertelenen {ozet['ertelenen']}, değişmeyen {ozet['ayni']}, "
          f"iptal {ozet['iptal']}, hata {ozet['hata']}")
    return ozet


if __name__ == "__main__":
    esitle()
