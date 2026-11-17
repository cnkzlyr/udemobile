# -*- coding: utf-8 -*-
"""🧭 Asistan notu: TickTick görevlerinin ve Notion dava sayfalarının SONUNA yardımcı bilgi ve eksik listesi ekler.

    asistan notlar            # ÖNİZLEME: neler yazılacağını gösterir, hiçbir şeyi değiştirmez
    asistan notlar --uygula   # yazar (izleyici her denetim turunda kendiliğinden günceller)

KURALLAR (var olan hiçbir şey silinmez/bozulmaz):
  * Not, görevin/sayfanın EN SONUNA, işaretli bir bölüm olarak eklenir. Sizin yazdıklarınız, başlık, tarih, etiket,
    alt görev, kontrol listesi, hatırlatıcı OLDUĞU GİBİ kalır (görevin geri kalanı okunup aynen geri gönderilir).
  * Sonraki çalışmalarda YALNIZCA bu işaretli bölüm güncellenir; içerik değişmediyse hiç yazılmaz.
  * Bölümü silerseniz bir daha eklenmez (o görev/sayfa için kapatılmış sayılır).
  * Tarihler "kalan gün" değil kesin tarih olarak yazılır: not her gün boşuna değişmez.
  * Yasal süre hatırlatmaları genel bilgidir; dosyadaki ara karar/kesin süre esastır ("kontrol edin").
"""
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone

import kimlik

HERE = os.path.dirname(os.path.abspath(__file__))
DURUM = os.path.join(HERE, "veri", "asistan_notu.json")
TZ = timezone(timedelta(hours=3))

BAS = "🧭 **ASİSTAN NOTU**"
SON = "🧭 _asistan notu sonu_"
_BLOK_RE = re.compile(r"\n*(?:---\n)?" + re.escape(BAS) + r".*?" + re.escape(SON) + r"[^\n]*\n?", re.S)
NOTION_BAS = "🧭 ASİSTAN NOTU"

SISTEM_ETIKETLERI = {"uets", "duruşma", "durusma", "tevkil", "tebligat"}
GUNLER = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


# ----------------------------------------------------------------------------------------------- yardımcılar
def _tarih(iso):
    """TickTick tarihi -> Türkiye saatiyle datetime."""
    if not iso:
        return None
    try:
        s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", iso.replace("Z", "+00:00"))
        return datetime.fromisoformat(s).astimezone(TZ)
    except ValueError:
        return None


def _gun(dt, saat=True):
    if not dt:
        return ""
    return dt.strftime("%d.%m.%Y") + f" {GUNLER[dt.weekday()]}" + (dt.strftime(" %H:%M") if saat and (dt.hour or dt.minute) else "")


def yargi_turu(mahkeme):
    m = (mahkeme or "").lower()
    if any(k in m for k in ("ceza", "çocuk", "infaz", "soruşturma", "cumhuriyet başsavcılığı")):
        return "ceza"
    if any(k in m for k in ("idare", "vergi", "danıştay", "idari dava")):
        return "idare"
    if "icra dairesi" in m:
        return "icra"
    return "hukuk"


def _norm(s):
    tablo = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return re.sub(r"[^a-z0-9]", "", (s or "").translate(tablo).lower())


def musteri_etiketi(t):
    return [g for g in (t.get("tags") or []) if g.lower() not in SISTEM_ETIKETLERI]


def tur_bul(t):
    """TEBLİGAT / DURUŞMA / DOSYA (dava kartı) / None."""
    from ticktick_sync import is_case_card
    k = kimlik.oku(t.get("content") or "")
    if k.get("tur") in ("TEBLİGAT", "DURUŞMA", "DOSYA"):
        return k["tur"]
    if k.get("tur"):
        return None
    baslik = (t.get("title") or "")
    b = baslik.upper()
    if "TEBLİGAT" in b or "📨" in baslik or "uets" in (t.get("tags") or []):
        return "TEBLİGAT"
    if "DURUŞMA" in b or "duruşma" in (t.get("tags") or []):
        return "DURUŞMA"
    if not t.get("parentId") and is_case_card(t) and re.search(r"\d{4}/\d+\s+Esas\b", baslik) and \
            re.search(r"Mahkemesi|Dairesi|İcra|Başkanlığı|Yargıtay|Danıştay", baslik):
        return "DOSYA"
    return None


def _icerik(t):
    """Görev notu, asistan bölümü ÇIKARILMIŞ olarak (kendi yazdığımız not analizi etkilemesin)."""
    c = t.get("content") or ""
    return _BLOK_RE.sub("\n", c) if BAS in c else c


_BILGI_ON = {}


def _bilgi(t):
    """Görevden mahkeme ve esas (önce kimlik satırı, sonra not, en son standart başlık)."""
    anahtar = (t.get("id"), t.get("modifiedTime"), len(t.get("content") or ""))
    if anahtar in _BILGI_ON:
        return _BILGI_ON[anahtar]
    _BILGI_ON[anahtar] = sonuc = _bilgi_hesapla(t)
    return sonuc


def _bilgi_hesapla(t):
    from ticktick_sync import extract_esas_from_text
    k = kimlik.oku(t.get("content") or "")
    icerik = _icerik(t).replace("\\", "")
    esas = k.get("esas") or extract_esas_from_text(icerik) or extract_esas_from_text(t.get("title") or "")
    mahkeme = k.get("mahkeme") or ""
    if not mahkeme:
        m = re.search(r"Merci:\**\s*([^\n]+)", icerik)
        if m:
            mahkeme = m.group(1).strip()
    if not mahkeme:
        m = re.match(r"^(?:[^\w]*(?:DURUŞMA|TEBLİGAT)\s*-\s*)?(.*?)\s*-?\s*\d{4}/\d+", t.get("title") or "", re.I)
        if m and re.search(r"Mahkemesi|Dairesi|İcra|Başkanlığı|Yargıtay|Danıştay", m.group(1)):
            mahkeme = m.group(1).strip(" -")
    return mahkeme, esas or ""


# ----------------------------------------------------------------------------------------------- evraka göre ipuçları
def evrak_ipuclari(icerik, mahkeme):
    """Tebligattaki evrak adlarına göre yapılacak iş hatırlatmaları (genel bilgi; dosyadaki kesin süre esastır)."""
    n = _norm(icerik)
    yt = yargi_turu(mahkeme)
    ip = []

    def ekle(s):
        if s not in ip:
            ip.append(s)
    if "bilirkisi" in n:
        ekle("Bilirkişi raporu: itiraz/beyan dilekçesi" + (" — HMK m.281: tebliğden itibaren 2 hafta." if yt == "hukuk" else
             " — CMK m.67/4: rapora karşı görüş bildirilebilir." if yt == "ceza" else " — mahkemenin verdiği süreyi kontrol edin."))
    if "gerekce" in n or "gerekcelikarar" in n or "kararevraki" in n or "hukum" in n:
        ekle({"hukuk": "Karar: istinaf (HMK m.345) / temyiz (HMK m.361) süresi tebliğden itibaren 2 hafta; kesinlik sınırını kontrol edin.",
              "idare": "Karar: istinaf (İYUK m.45) / temyiz (İYUK m.46) süresi tebliğden itibaren 30 gün.",
              "ceza": "Karar: istinaf/temyiz süresini ve kanun yolunu karardaki açıklamadan kontrol edin (CMK m.273, m.291).",
              "icra": "Karar/işlem: şikâyet/itiraz süresini kontrol edin (İİK m.16: 7 gün)."}[yt])
    if "istinafbasvuru" in n or ("istinaf" in n and "dilekce" in n):
        ekle("Karşı tarafın istinaf dilekçesi: cevap " + ("HMK m.347 — tebliğden itibaren 2 hafta." if yt == "hukuk" else "süresini kontrol edin."))
    if "temyizdilekce" in n or ("temyiz" in n and "dilekce" in n):
        ekle("Temyiz dilekçesi: cevap " + ("HMK m.364 — tebliğden itibaren 2 hafta." if yt == "hukuk" else "süresini kontrol edin."))
    if "davadilekce" in n or "cevapdilekce" in n:
        ekle("Dilekçe tebliği: cevap/cevaba cevap " + ("HMK m.127/136 — 2 hafta (cevap için uzatma istenebilir)." if yt == "hukuk"
             else "İYUK m.16 — 30 gün." if yt == "idare" else "süresini kontrol edin."))
    if "tensip" in n:
        ekle("Tensip zaptı: delil listesi, gider/delil avansı ve kesin süreleri not edin; duruşma günü TickTick'te var mı bakın.")
    if "arakarar" in n or "arakarari" in n:
        ekle("Ara karar: kesin süre verildiyse süreyi ve yapılacak işi bu göreve yazın (kesin süre kaçırılırsa hak kaybı).")
    if "iddianame" in n:
        ekle("İddianame: savunma hazırlığı; tensip/duruşma gününü kontrol edin.")
    if "mutalaa" in n:
        ekle("Esas hakkında mütalaa: savunma için verilen süreyi/duruşma gününü kontrol edin.")
    if "odemeemri" in n or "icraemri" in n:
        ekle("Ödeme/icra emri: borçlu tarafta isek itiraz süresi (ilamsız takipte İİK m.62: 7 gün).")
    if "avans" in n or "masraf" in n or "harc" in n:
        ekle("Gider/delil avansı ya da harç: verilen kesin süre içinde yatırılmazsa hak kaybı olabilir.")
    if "durusma" in n and ("davetiye" in n or "celp" in n or "zapt" in n or "tutanak" in n):
        ekle("Duruşma evrakı: duruşma günü TickTick'te ayrı görev olarak var mı kontrol edin.")
    return ip


# ----------------------------------------------------------------------------------------------- dizinler
def ayni_mahkeme(m1, m2):
    """Mahkeme adları aynı dosyayı mı gösteriyor? Biri bilinmiyorsa evet sayılır (esas zaten aynı)."""
    a, b = _norm(m1).replace("mahkemesi", ""), _norm(m2).replace("mahkemesi", "")
    return not a or not b or a == b or a in b or b in a


def _esas_dizini(baglam):
    """esas -> aktif görevler (bir kez kurulur; her görev için tüm listeyi taramamak için)."""
    if "_esas" not in baglam:
        d = {}
        for x in baglam.get("gorevler", []):
            if x.get("status", 0) == 0:
                e = _bilgi(x)[1]
                if e:
                    d.setdefault(e, []).append(x)
        baglam["_esas"] = d
    return baglam["_esas"]


def _gun_dizini(baglam):
    """gün -> aktif duruşma görevleri."""
    if "_gun" not in baglam:
        d = {}
        for x in baglam.get("gorevler", []):
            if x.get("status", 0) == 0 and tur_bul(x) == "DURUŞMA":
                dt = _tarih(x.get("dueDate"))
                if dt:
                    d.setdefault(dt.date(), []).append(x)
        baglam["_gun"] = d
    return baglam["_gun"]


# ----------------------------------------------------------------------------------------------- not metni
def not_satirlari(t, baglam):
    """Bir görev için (bilgi, eksikler) satırları. baglam: tum gorevler, defter, simdi, notion_var."""
    tur = tur_bul(t)
    if not tur:
        return None
    icerik = _icerik(t)
    mahkeme, esas = _bilgi(t)
    simdi = baglam.get("simdi") or datetime.now(TZ)
    defter_k = baglam["defter"](esas, mahkeme) if esas and baglam.get("defter") else None
    bilgi, eksik = [], []
    due = _tarih(t.get("dueDate"))

    if defter_k:
        bilgi.append(f"UYAP durumu: {defter_k.get('ham_durum') or defter_k.get('durum') or '—'}"
                     + (f" · açılış {defter_k['acilis'][8:10]}.{defter_k['acilis'][5:7]}.{defter_k['acilis'][:4]}" if defter_k.get("acilis") else ""))
        tar = defter_k.get("taraflar") or []
        if tar:
            ozet = "; ".join(f"{x.get('rol') or ''}: {x.get('ad')}" + (" (müvekkil)" if x.get("muvekkil_mi") else "") for x in tar[:4])
            bilgi.append("Taraflar: " + ozet + (f" (+{len(tar) - 4})" if len(tar) > 4 else ""))
        if defter_k.get("muvekkil") and not musteri_etiketi(t):
            bilgi.append(f"Müvekkil (UYAP listesinden): {defter_k['muvekkil']}")

    ayni = [x for x in _esas_dizini(baglam).get(esas, []) if x.get("id") != t.get("id") and ayni_mahkeme(_bilgi(x)[0], mahkeme)] if esas else []
    if tur in ("TEBLİGAT", "DOSYA"):
        sonraki = sorted((d for d in (_tarih(x.get("dueDate")) for x in ayni if tur_bul(x) == "DURUŞMA") if d and d >= simdi))
        if sonraki:
            bilgi.append(f"Sıradaki duruşma: {_gun(sonraki[0])}")
    if tur == "DOSYA":
        teb = [x for x in ayni if tur_bul(x) == "TEBLİGAT"]
        if teb:
            sg = sorted(d for d in (_tarih(x.get("dueDate")) for x in teb) if d)
            bilgi.append(f"Açık tebligat: {len(teb)}" + (f" · en yakın son gün {_gun(sg[0], saat=False)}" if sg else ""))
        acik_alt = len(t.get("childIds") or [])
        if acik_alt:
            bilgi.append(f"Alt görev: {acik_alt}")

    if tur == "TEBLİGAT":
        if due:
            if due < simdi:
                eksik.append(f"Son gün geçmiş ({_gun(due)}). İşlem yapıldıysa görevi tamamlayın; yapılmadıysa eski hâle getirme/mazeret değerlendirin.")
            else:
                bilgi.append(f"Son gün: {_gun(due)}")
        else:
            eksik.append("Son gün (tarih) girilmemiş.")
        for s in evrak_ipuclari(icerik, mahkeme):
            bilgi.append("💡 " + s)
        k = kimlik.oku(icerik)
        if "EKLİ EVRAKLAR" in icerik and baglam.get("ek_var") and not baglam["ek_var"](t, k.get("barkod")):
            eksik.append("EYP evrakı göreve eklenmemiş görünüyor (asistan calistir yeniden dener).")
        if defter_k and baglam.get("kapali_mi") and baglam["kapali_mi"](defter_k.get("durum")):
            eksik.append("UYAP'ta dosya KAPALI görünüyor ama tebligat geldi: karar sonrası işlem/yeniden açılma olabilir.")
    if tur == "DURUŞMA":
        if due:
            bilgi.append(f"Duruşma: {_gun(due)}")
            if due < simdi:
                eksik.append("Duruşma tarihi geçmiş: tutanağı ekleyip görevi tamamlayın; yeni duruşma günü takvime işlendi mi bakın.")
            ayni_gun = []
            for x in _gun_dizini(baglam).get(due.date(), []):
                if x.get("id") == t.get("id"):
                    continue
                d2 = _tarih(x.get("dueDate"))
                if d2 and d2.date() == due.date() and _bilgi(x)[1] != esas:
                    ayni_gun.append((d2, _bilgi(x)))
            for d2, (m2, e2) in sorted(ayni_gun)[:3]:
                yakin = abs((d2 - due).total_seconds()) <= 2 * 3600
                (eksik if yakin else bilgi).append(("⚠️ Çakışma: " if yakin else "Aynı gün: ") + f"{d2.strftime('%H:%M')} {m2} {e2}"
                                                   + (" — tevkil/mazeret gerekebilir." if yakin else ""))
        else:
            eksik.append("Duruşma tarihi/saati girilmemiş.")
        bos = [b for b in ("DURUŞMA TUTANAĞI", "ÖNCEKİ TENSİP/DURUŞMA TUTANAĞI") if re.search(re.escape(b) + r":\s*\n\s*(?:###|\*\*|$)", icerik)]
        if bos:
            bilgi.append("Hazırlık: önceki tensip/duruşma tutanağı henüz eklenmemiş; beyan notu bölümü boş.")
        if defter_k and baglam.get("kapali_mi") and baglam["kapali_mi"](defter_k.get("durum")):
            eksik.append("UYAP'ta dosya KAPALI görünüyor: duruşma hâlâ geçerli mi kontrol edin.")
    if tur == "DOSYA":
        if defter_k and baglam.get("kapali_mi") and baglam["kapali_mi"](defter_k.get("durum")):
            eksik.append("UYAP'ta dosya kapalı: altındaki işler bitince kart kapatılabilir.")
        if not defter_k and baglam.get("defter_dolu"):
            eksik.append("Bu dosya son UYAP listesinde yok (esas no/mahkeme farklı yazılmış ya da dosya başka avukatta olabilir).")

    if tur in ("TEBLİGAT", "DURUŞMA") and not t.get("parentId"):
        eksik.append("Dava kartına bağlı değil (denetim aynı listedeki karta bağlamayı dener).")
    if not musteri_etiketi(t):
        eksik.append("Müvekkil etiketi yok" + (f" — UYAP listesine göre: {defter_k['muvekkil']}" if defter_k and defter_k.get("muvekkil") else "."))
    if esas and "notion" not in icerik.lower():
        eksik.append("Notion dosya bağlantısı yok" + ("" if baglam.get("notion_var", lambda *a: True)(esas, mahkeme) else " (Notion'da bu dosyanın sayfası da bulunamadı)") + ".")
    if not kimlik.var_mi(icerik) and tur in ("TEBLİGAT", "DURUŞMA"):
        eksik.append("Kimlik satırı yok (denetim ekler; başlığı değiştirseniz de görev tanınır).")
    return {"tur": tur, "bilgi": bilgi, "eksik": eksik}


def blok_metni(sat):
    """TickTick notunun sonuna eklenecek işaretli bölüm (Markdown)."""
    if not sat or (not sat["bilgi"] and not sat["eksik"]):
        return ""
    s = ["---", f"{BAS} _(otomatik; bu bölümü silebilirsiniz — üstteki notlarınıza dokunulmaz)_"]
    s += [f"- {b}" for b in sat["bilgi"]]
    if sat["eksik"]:
        s.append("**Eksik / kontrol edilecek:**")
        s += [f"- ⚠️ {e}" if not e.startswith("⚠️") else f"- {e}" for e in sat["eksik"]]
    else:
        s.append("- ✅ Eksik görünmüyor.")
    s.append(SON)
    return "\n".join(s) + "\n"


def blok_var_mi(icerik):
    return BAS in (icerik or "")


def blok_yerlestir(icerik, blok):
    """Var olan içeriğe DOKUNMADAN: eski asistan bölümünü yenisiyle değiştirir, yoksa en sona ekler."""
    icerik = icerik or ""
    if blok_var_mi(icerik):
        yeni, n = _BLOK_RE.subn(lambda m: ("\n\n" + blok) if blok else "\n", icerik, count=1)
        if n:
            return yeni.rstrip("\n") + "\n" if not blok else yeni
    if not blok:
        return icerik
    return icerik.rstrip("\n") + "\n\n" + blok


def _ozet(metin):
    return hashlib.sha1(metin.encode("utf-8")).hexdigest()[:16]


# ----------------------------------------------------------------------------------------------- durum dosyası
def _durum_oku():
    try:
        with open(DURUM, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    d.setdefault("tt", {})
    d.setdefault("notion", {})
    d.setdefault("kapatilan", [])
    return d


def _durum_yaz(d):
    try:
        os.makedirs(os.path.dirname(DURUM), exist_ok=True)
        tmp = DURUM + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, DURUM)
    except OSError:
        pass


# ----------------------------------------------------------------------------------------------- TickTick
def _baglam(gorevler):
    from ticktick_sync import gercek_ek_var
    b = {"gorevler": gorevler, "simdi": datetime.now(TZ), "ek_var": gercek_ek_var}
    try:
        import defter
        b["defter"] = defter.dosya_bul
        b["kapali_mi"] = defter.kapali_mi
        b["defter_dolu"] = (defter.istatistik() or {}).get("dosya", 0) > 0
    except Exception:
        b["defter"] = None
    try:
        from notion_sync import find_notion_case
        b["notion_var"] = lambda esas, mahkeme: bool(find_notion_case(esas, mahkeme))
    except Exception:
        pass
    return b


def _guvenli_icerik_yaz(t, yeni_icerik):
    """Görevin YALNIZCA notunu değiştirir: güncel hâli okunur, diğer tüm alanlar aynen geri gönderilir."""
    from config import CONFIG
    from ticktick_sync import gorev_getir, tt_post
    guncel = gorev_getir(t.get("projectId") or t.get("_pid"), t["id"]) or t
    if (guncel.get("content") or "") != (t.get("content") or ""):
        return False      # okuduğumuzdan beri kullanıcı değiştirmiş: bu tur atla (bir sonrakinde güncel hâliyle)
    payload = {"id": t["id"], "projectId": guncel.get("projectId") or t.get("projectId"), "content": yeni_icerik}
    for alan in ("title", "tags", "priority", "startDate", "dueDate", "isAllDay", "timeZone", "reminders", "items",
                 "repeatFlag", "kind"):
        if guncel.get(alan) is not None:
            payload[alan] = guncel[alan]
    return tt_post(f"{CONFIG['TICKTICK_API_BASE']}/task/{t['id']}", payload, what="asistan notu") is not None


def ticktick_notlari(uygula=False, en_cok=None, ornek=3):
    """Tüm aktif tebligat/duruşma/dava kartı görevleri. Döner: özet sözlüğü."""
    from ticktick_sync import tum_aktif_gorevler
    gorevler = tum_aktif_gorevler(force=True)
    baglam = _baglam(gorevler)
    durum = _durum_oku()
    ozet = {"incelenen": 0, "yazilacak": 0, "yazilan": 0, "ayni": 0, "kapatilmis": 0, "eksikli": 0, "atlanan": 0}
    ornekler = []
    for t in gorevler:
        if t.get("status", 0) != 0 or t.get("kind") == "CHECKLIST":
            continue
        sat = not_satirlari(t, baglam)
        if not sat:
            continue
        ozet["incelenen"] += 1
        tid = t["id"]
        icerik = t.get("content") or ""
        if tid in durum["kapatilan"]:
            ozet["kapatilmis"] += 1
            continue
        if tid in durum["tt"] and not blok_var_mi(icerik):
            durum["kapatilan"].append(tid)      # kullanıcı bölümü sildi: bir daha eklenmez
            ozet["kapatilmis"] += 1
            continue
        if sat["eksik"]:
            ozet["eksikli"] += 1
        blok = blok_metni(sat)
        yeni = blok_yerlestir(icerik, blok)
        if yeni == icerik:
            ozet["ayni"] += 1
            durum["tt"].setdefault(tid, _ozet(blok))
            continue
        ozet["yazilacak"] += 1
        if len(ornekler) < ornek:
            ornekler.append((t.get("title") or "", blok))
        if uygula and (en_cok is None or ozet["yazilan"] < en_cok):
            if _guvenli_icerik_yaz(t, yeni):
                ozet["yazilan"] += 1
                durum["tt"][tid] = _ozet(blok)
            else:
                ozet["atlanan"] += 1
    if uygula:
        _durum_yaz(durum)
    ozet["ornekler"] = ornekler
    return ozet


# ----------------------------------------------------------------------------------------------- Notion
def notion_satirlari(sayfa, gorevler, defter_bul=None, kapali_mi=None, simdi=None, baglam=None):
    """Notion dava sayfası için not satırları: UYAP durumu, taraflar, TickTick'teki işler, eksikler."""
    simdi = simdi or datetime.now(TZ)
    esas, mahkeme = sayfa.get("esas_no") or "", sayfa.get("court") or ""
    d = defter_bul(esas, mahkeme) if (defter_bul and esas) else None
    bilgi, eksik = [], []
    if d:
        bilgi.append(f"UYAP durumu: {d.get('ham_durum') or d.get('durum') or '—'}")
        tar = d.get("taraflar") or []
        if tar:
            bilgi.append("Taraflar: " + "; ".join(f"{x.get('rol') or ''}: {x.get('ad')}" for x in tar[:6]) + (f" (+{len(tar) - 6})" if len(tar) > 6 else ""))
        if (sayfa.get("durum") or "") and d.get("durum") and _norm(sayfa["durum"]) != _norm(d["durum"]):
            eksik.append(f"Notion durumu '{sayfa['durum']}', UYAP '{d['durum']}' (uyap-liste --guvenli eşitler).")
        if d.get("muvekkil") and not sayfa.get("client_rel_count"):
            eksik.append(f"MÜVEKKİLLER alanı boş — UYAP listesine göre müvekkil: {d['muvekkil']}.")
    baglam = baglam if baglam is not None else {"gorevler": gorevler}
    ilgili = [x for x in _esas_dizini(baglam).get(esas, []) if ayni_mahkeme(_bilgi(x)[0], mahkeme)] if esas else []
    kart = [t for t in ilgili if tur_bul(t) == "DOSYA"]
    dur = sorted((x for x in ((_tarih(t.get("dueDate")), t) for t in ilgili if tur_bul(t) == "DURUŞMA") if x[0] and x[0] >= simdi),
                 key=lambda x: x[0])
    teb = [t for t in ilgili if tur_bul(t) == "TEBLİGAT"]
    if dur:
        bilgi.append(f"Sıradaki duruşma: {_gun(dur[0][0])}")
    if teb:
        sg = sorted(x for x in (_tarih(t.get("dueDate")) for t in teb) if x)
        bilgi.append(f"Açık tebligat: {len(teb)}" + (f" · en yakın son gün {_gun(sg[0], saat=False)}" if sg else ""))
    linkler = [(t.get("title") or "")[:60] + " → https://ticktick.com/webapp/#p/" + (t.get("projectId") or "") + "/tasks/" + t["id"]
               for t in (kart[:1] + [x[1] for x in dur[:1]] + teb[:2])]
    if not kart and not (d and kapali_mi and kapali_mi(d.get("durum"))) and (sayfa.get("durum") or "").lower().startswith("açık"):
        eksik.append("TickTick'te dava kartı yok (uyap-liste --guvenli açar).")
    if not sayfa.get("tur"):
        eksik.append("DOSYA TÜRÜ alanı boş.")
    return {"bilgi": bilgi, "eksik": eksik, "linkler": linkler}


def notion_blok_metni(sat):
    if not sat or (not sat["bilgi"] and not sat["eksik"] and not sat["linkler"]):
        return ""
    s = [NOTION_BAS + " (otomatik; bu kutuyu silebilirsiniz — sayfadaki diğer içeriğe dokunulmaz)"]
    s += ["• " + b for b in sat["bilgi"]]
    s += ["• TickTick: " + l for l in sat["linkler"]]
    if sat["eksik"]:
        s.append("Eksik / kontrol edilecek:")
        s += ["⚠️ " + e for e in sat["eksik"]]
    else:
        s.append("✅ Eksik görünmüyor.")
    return "\n".join(s)


def _rich(metin):
    return [{"type": "text", "text": {"content": metin[i:i + 1900]}} for i in range(0, len(metin), 1900)][:40]


def notion_notlari(uygula=False, hepsi=False, en_cok=None, ornek=2):
    import baglanti
    from config import CONFIG
    from notion_sync import get_notion_headers
    from sync_uyap_excel import fetch_all_notion_pages
    from ticktick_sync import tum_aktif_gorevler
    try:
        import defter
        dbul, kmi = defter.dosya_bul, defter.kapali_mi
    except Exception:
        dbul = kmi = None
    gorevler = tum_aktif_gorevler(force=True)
    sayfalar = fetch_all_notion_pages()
    durum = _durum_oku()
    tbag = {"gorevler": gorevler}
    h = get_notion_headers()
    base = CONFIG["NOTION_API_BASE"]
    ozet = {"incelenen": 0, "yazilacak": 0, "yazilan": 0, "ayni": 0, "kapatilmis": 0, "eksikli": 0, "ornekler": []}
    for p in sayfalar:
        if not p.get("esas_no"):
            continue
        if not hepsi and (p.get("durum") or "").lower().startswith("kapal"):
            if p["esas_no"] not in _esas_dizini(tbag):
                continue
        sat = notion_satirlari(p, gorevler, dbul, kmi, baglam=tbag)
        metin = notion_blok_metni(sat)
        if not metin:
            continue
        ozet["incelenen"] += 1
        pid = p["id"]
        if pid in durum["kapatilan"]:
            ozet["kapatilmis"] += 1
            continue
        if sat["eksik"]:
            ozet["eksikli"] += 1
        kayit = durum["notion"].get(pid) or {}
        if kayit.get("ozet") == _ozet(metin):
            ozet["ayni"] += 1
            continue
        ozet["yazilacak"] += 1
        if len(ozet["ornekler"]) < ornek:
            ozet["ornekler"].append((p.get("title") or "", metin))
        if not uygula or (en_cok is not None and ozet["yazilan"] >= en_cok):
            continue
        govde = {"callout": {"rich_text": _rich(metin), "icon": {"emoji": "🧭"}, "color": "gray_background"}}
        if kayit.get("blok"):
            r = baglanti.oku("GET", f"{base}/blocks/{kayit['blok']}", h, ne="Notion asistan notu", kabul=(200, 404))
            if r.status_code == 404 or (r.json() or {}).get("archived") or (r.json() or {}).get("in_trash"):
                durum["kapatilan"].append(pid)     # kullanıcı kutuyu sildi: bir daha eklenmez
                ozet["kapatilmis"] += 1
                continue
            r, _ = baglanti.yaz("PATCH", f"{base}/blocks/{kayit['blok']}", h, json_body=govde, ne="Notion asistan notu güncelleme",
                                anahtar=pid)
            if r is not None and r.status_code == 200:
                ozet["yazilan"] += 1
                durum["notion"][pid] = {"blok": kayit["blok"], "ozet": _ozet(metin)}
        else:
            # Sayfanın SONUNA eklenir (var olan bloklara dokunulmaz). Eklemenin yanıtı kaybolursa aynı kutu
            # tekrar eklenmesin diye önce sayfada "🧭 ASİSTAN NOTU" kutusu aranır.
            def _bul():
                rr = baglanti.oku("GET", f"{base}/blocks/{pid}/children?page_size=100", h, ne="Notion sayfa blokları", kabul=(200,))
                for b in (rr.json() or {}).get("results", []):
                    if b.get("type") == "callout" and "".join(x.get("plain_text", "") for x in b["callout"].get("rich_text", [])).startswith(NOTION_BAS):
                        return b
                return None
            var = _bul()
            if var:
                durum["notion"][pid] = {"blok": var["id"], "ozet": ""}
                r, _ = baglanti.yaz("PATCH", f"{base}/blocks/{var['id']}", h, json_body=govde, ne="Notion asistan notu güncelleme", anahtar=pid)
                if r is not None and r.status_code == 200:
                    ozet["yazilan"] += 1
                    durum["notion"][pid] = {"blok": var["id"], "ozet": _ozet(metin)}
                continue
            r, dogru = baglanti.yaz("PATCH", f"{base}/blocks/{pid}/children", h,
                                    json_body={"children": [dict(object="block", type="callout", **govde)]},
                                    ne="Notion asistan notu ekleme", olusturma=True, dogrula=_bul, anahtar=pid)
            blok_id = None
            if dogru:
                blok_id = dogru.get("id")
            elif r is not None and r.status_code == 200:
                blok_id = ((r.json() or {}).get("results") or [{}])[-1].get("id")
            if blok_id:
                ozet["yazilan"] += 1
                durum["notion"][pid] = {"blok": blok_id, "ozet": _ozet(metin)}
        if uygula and ozet["yazilan"] % 25 == 0:
            _durum_yaz(durum)
    if uygula:
        _durum_yaz(durum)
    return ozet


# ----------------------------------------------------------------------------------------------- komut
def calistir(uygula=False, notion=True, hepsi=False, en_cok=None, sessiz=False):
    print(f"🧭 Asistan notları — {'UYGULA' if uygula else 'ÖNİZLEME (hiçbir şey değiştirilmez)'}")
    tt = ticktick_notlari(uygula=uygula, en_cok=en_cok)
    print(f"☑️ TickTick: {tt['incelenen']} görev incelendi · eksikli {tt['eksikli']} · "
          + (f"yazılan {tt['yazilan']}" if uygula else f"yazılacak {tt['yazilacak']}")
          + f" · değişmeyen {tt['ayni']} · notu kapatılmış {tt['kapatilmis']}" + (f" · atlanan {tt['atlanan']}" if tt.get("atlanan") else ""))
    if not sessiz:
        for baslik, blok in tt["ornekler"]:
            print(f"\n   ── Örnek: {baslik[:70]}\n   " + blok.replace("\n", "\n   "))
    sonuc = {"ticktick": tt}
    if notion:
        nt = notion_notlari(uygula=uygula, hepsi=hepsi, en_cok=en_cok)
        print(f"📄 Notion: {nt['incelenen']} dosya sayfası · eksikli {nt['eksikli']} · "
              + (f"yazılan {nt['yazilan']}" if uygula else f"yazılacak {nt['yazilacak']}")
              + f" · değişmeyen {nt['ayni']} · notu kapatılmış {nt['kapatilmis']}")
        if not sessiz:
            for baslik, metin in nt["ornekler"]:
                print(f"\n   ── Örnek Notion: {baslik[:70]}\n   " + metin.replace("\n", "\n   "))
        sonuc["notion"] = nt
    if not uygula:
        print("\nYazmak için:  asistan notlar --uygula   (önce birkaç tanesini denemek için: --en-cok 5)")
    return sonuc
