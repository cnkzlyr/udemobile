#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TickTick Entegrasyon, Görev Oluşturucu, Ek (Attachment) ve Mükerrer Temizleme Modülü (v8.1)
- Önceden tamamlanmış (status=2) ve yapılmayacak (status=-1) tebligatları otomatik tespit eder ve mükerrer açmaz.
- Mahkeme türüne göre doğru yasal süreyi (İcra/Ceza: 7 gün, Hukuk: 14 gün, İdari: 30 gün) ve hafta sonu kuralını seçer.
- E-posta ile ek yükleme sırasında tarih bozulmalarını (2003/2024 ve 'Son Gün: 26' hatalarını) önler.
- Otomatik sağlık denetimi (audit & heal): Parent'sız görevleri tespit edip bağlar, etiketleri kurala göre düzeltir.
"""

import os
import time
import requests
import json
import re
from datetime import datetime
import gatekeeper as gk
import kimlik
from config import CONFIG, PROJECT_IDS
from utils import normalize_tr, clean_text, determine_list, normalize_tags
from mail_sender import send_task_via_email
from state_manager import get_barcode_state, update_barcode_state

_PROJECT_TASKS_CACHE = {}
_COMPLETED_TASKS_CACHE = None
_LAST_COMPLETED_FETCH = 0

def get_ticktick_headers():
    return {
        "Authorization": f"Bearer {CONFIG['TICKTICK_TOKEN']}",
        "Content-Type": "application/json"
    }

import baglanti


class TickTickOkumaHatasi(baglanti.BaglantiHatasi):
    """TickTick'ten okuma, yeniden denemelere ve bağlantı beklemesine rağmen yapılamadı. Okuma başarısızken liste
    "boş" SAYILMAZ (sayılırsa var olan kart/görev "yok" görünür ve KOPYASI açılır): yazma yapmadan durulur."""


def _yeniden_deneme_beklemeleri():
    return baglanti.kisa_beklemeler()


def tt_oku(url, what="görevler", method="GET", json_body=None, timeout=15):
    """TickTick'ten OKUMA: kısa yeniden denemeler, sonra internet gelene kadar bekleyip AYNI yerden devam.
    200 ya da 404 yanıtını döndürür; başaramazsa TickTickOkumaHatasi (asla sessizce boş liste döndürmez)."""
    return baglanti.oku(method, url, get_ticktick_headers(), json_body=json_body, timeout=timeout,
                        ne=f"TickTick {what}", hata_sinifi=TickTickOkumaHatasi,
                        yetki_mesaji="TickTick erişim anahtarı reddedildi: TICKTICK_TOKEN geçersiz ya da süresi dolmuş")


def _olusturulmus_gorev(payload):
    """Yanıtı kaybolan 'görev oluştur' isteği sunucuda gerçekleşmiş mi? Aynı listede aynı başlık ve (varsa) aynı
    KİMLİK satırıyla görev arar. Bulursa görevi döndürür."""
    pid = payload.get("projectId") or "inbox"
    baslik = (payload.get("title") or "").strip()
    k = kimlik.oku(payload.get("content") or "")
    for t in get_project_tasks_live(pid, force_refresh=True):
        if t.get("status", 0) != 0:
            continue
        tk = kimlik.oku(t.get("content") or "")
        if k and tk == k and (t.get("parentId") or "") == (payload.get("parentId") or ""):
            return t
        if not k and (t.get("title") or "").strip() == baslik and (t.get("parentId") or "") == (payload.get("parentId") or ""):
            return t
    return None


def tt_post(url, payload, what="görev", timeout=12):
    """TickTick'e POST atar; 200 dışındaki yanıtları SESSİZCE yutmaz (eskiden görev açılamayınca hiçbir iz kalmıyordu).
    401/403: token geçersiz/süresi dolmuş. 400: tarih biçimi, proje kimliği vb. Döner: dict (başarılı) ya da None."""
    # Bağlantı koparsa bekleyip devam eder. OLUŞTURMA isteğinin yanıtı kaybolursa önce "oluşmuş mu?" bakılır:
    # oluşmuşsa o görev döner (kopya açılmaz). Güncelleme (url'de görev kimliği var) güvenle tekrar gönderilir.
    olusturma = url.rstrip("/").endswith("/task") and not payload.get("id")
    resp, var = baglanti.yaz("POST", url, get_ticktick_headers(), json_body=payload, timeout=timeout, ne=f"TickTick {what}",
                             olusturma=olusturma, dogrula=(lambda: _olusturulmus_gorev(payload)) if olusturma else None,
                             anahtar=(payload.get("title") or payload.get("id") or "")[:120])
    if var is not None:
        return var
    if resp is None:
        print(f"⚠️ TickTick {what} gönderilemedi (bağlantı); bir sonraki çalışmada yeniden denenecek.")
        return None
    if resp.status_code == 200:
        try:
            return resp.json() if resp.content else {}
        except ValueError:
            return {}
    body = (resp.text or "")[:300].replace("\n", " ")
    if resp.status_code in (401, 403):
        print(f"❌ TickTick {what} REDDEDİLDİ ({resp.status_code}): erişim anahtarı (TICKTICK_TOKEN) geçersiz ya da süresi dolmuş. "
              f"TickTick > Ayarlar > Hesap > API Token'dan yenisini alıp .env dosyasına yazın.")
    else:
        print(f"❌ TickTick {what} açılamadı/güncellenemedi: HTTP {resp.status_code} {body}")
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ticktick_hatalar.log"), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{what}\t{resp.status_code}\t{payload.get('title', payload.get('id', ''))}\t{body}\n")
    except Exception:
        pass
    return None

_TUM_GOREVLER = None
_TUM_GOREVLER_ZAMAN = 0
SON_KART_YENI = False   # find_or_create_parent_task son çağrıda YENİ kart mı açtı (yoksa var olanı mı buldu)


def tum_aktif_gorevler(force=False):
    """TÜM listelerdeki aktif görevler (yalnızca PROJECT_IDS'teki listeler değil: kullanıcı görevi başka
    bir listeye taşırsa da bulunur). 60 sn önbellek. Her görevde _pid alanı vardır."""
    global _TUM_GOREVLER, _TUM_GOREVLER_ZAMAN
    if not force and _TUM_GOREVLER is not None and time.time() - _TUM_GOREVLER_ZAMAN < 300:
        return _TUM_GOREVLER
    pids = []
    r = tt_oku(f"{CONFIG['TICKTICK_API_BASE']}/project", what="liste adları", timeout=20)
    if r.status_code == 200:
        pids = [p["id"] for p in r.json() if not p.get("closed")]
    for pid in list(PROJECT_IDS.values()) + ["inbox"]:
        if pid and pid not in pids:
            pids.append(pid)
    gorevler, gorulen = [], set()
    for pid in pids:
        for t in get_project_tasks_live(pid, force_refresh=force):
            if t.get("id") in gorulen:
                continue
            gorulen.add(t.get("id"))
            t["_pid"] = t.get("projectId") or pid
            gorevler.append(t)
    _TUM_GOREVLER, _TUM_GOREVLER_ZAMAN = gorevler, time.time()
    return gorevler


def gorev_getir(project_id, task_id):
    """Tek görevi kimliğiyle getirir (başlık ya da liste değişse de). Yoksa None."""
    if not (project_id and task_id) or str(task_id).startswith("pending"):
        return None
    try:
        r = requests.get(f"{CONFIG['TICKTICK_API_BASE']}/project/{project_id}/task/{task_id}", headers=get_ticktick_headers(), timeout=8)
        if r.status_code == 200 and r.content:
            return r.json()
    except Exception:
        pass
    return None


def etiket_birlestir(mevcut, sistem):
    """Kullanıcının elle eklediği etiketleri KORUR, sistemin zorunlu etiketlerini ekler."""
    sonuc = list(mevcut or [])
    for e in sistem or []:
        if e not in sonuc:
            sonuc.append(e)
    return sonuc


def kimlige_gore_bul(tur, barkod="", esas="", mahkeme="", uets_no="", durusma=""):
    """Aktif görevler arasında KİMLİK satırına (yoksa nottaki barkoda) göre arar; başlığa BAKMAZ."""
    mahkeme_t = clean_text(mahkeme) if mahkeme else ""
    for t in tum_aktif_gorevler():
        icerik = t.get("content") or ""
        k = kimlik.oku(icerik)
        if barkod:
            if (k and k.get("tur") == tur and k.get("barkod") == barkod) or (not k and tur == "TEBLİGAT" and extract_barcode_from_text(icerik) == barkod):
                return t
            continue
        if uets_no:
            if k.get("uets_no") == uets_no:
                return t
            continue
        if not k or k.get("tur") != tur or not esas or k.get("esas") != esas:
            continue
        if durusma:
            gun = durusma.replace(".", "/").strip()[:10]
            if not (k.get("durusma") or "").replace(".", "/").startswith(gun):
                continue
        if mahkeme_t and k.get("mahkeme") and clean_text(k["mahkeme"]) != mahkeme_t:
            continue
        return t
    return None


def _yerel_gun(iso):
    """TickTick tarih alanı ("2026-12-10T11:25:00+0300" ya da "+0000") -> Türkiye günü "2026-12-10"."""
    if not iso:
        return ""
    try:
        from config import TZ_TURKEY
        dt = datetime.strptime(iso[:24].replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")
        return dt.astimezone(TZ_TURKEY).strftime("%Y-%m-%d")
    except ValueError:
        return iso[:10]


def _gun_anahtari(tarih):
    """'10/12/2026' ya da '10.12.2026' -> '2026-12-10'"""
    m = re.match(r"\s*(\d{1,2})[./](\d{1,2})[./](\d{4})", tarih or "")
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else ""


def durusma_gorevi_mi(t):
    k = kimlik.oku(t.get("content") or "")
    if k:
        return k.get("tur") == "DURUŞMA"
    ti = (t.get("title") or "")
    tags = [x.lower() for x in (t.get("tags") or [])]
    return "DURUŞMA" in ti.upper() or "DURUSMA" in ti.upper() or "⚖️" in ti or "duruşma" in tags or "durusma" in tags


def durusma_mukerrerlerini_birlestir(gorevler=None):
    """Aynı esas + aynı GÜN için birden çok AKTİF duruşma görevi varsa birleştirir.
    Kalan: alt görevi olan, yoksa EN ESKİ görev (kullanıcının asıl görevi; başlığı, notları, etiketleri korunur).
    Kalan göreve kimlik satırı eklenir; kopyaların farklı not satırları ve etiketleri taşınır; kopya silinir.
    Alt görevi olan kopya silinmez. Döner: (birlesen_grup, silinen)."""
    gorevler = gorevler if gorevler is not None else tum_aktif_gorevler(force=True)
    gruplar = {}
    for t in gorevler:
        if t.get("status", 0) != 0 or not durusma_gorevi_mi(t):
            continue
        k = kimlik.oku(t.get("content") or "")
        esas = k.get("esas") or extract_esas_from_text(t.get("content") or "") or extract_esas_from_text(t.get("title") or "")
        gun = _gun_anahtari(k.get("durusma", "")) or _yerel_gun(t.get("dueDate"))
        if esas and gun:
            gruplar.setdefault((esas, gun), []).append(t)
    birlesen = silinen = 0
    for (esas, gun), liste in gruplar.items():
        if len(liste) < 2:
            continue
        liste.sort(key=lambda x: (0 if x.get("childIds") else 1, x.get("createdTime") or "9999"))
        ana, kopyalar = liste[0], liste[1:]
        icerik = ana.get("content") or ""
        etiketler = list(ana.get("tags") or [])
        kimlik_s = next((kimlik.oku(x.get("content") or "") for x in liste if kimlik.var_mi(x.get("content") or "")), None)
        mevcut = {l.strip() for l in icerik.splitlines() if l.strip()}
        ek = []
        for c in kopyalar:
            for tg in c.get("tags") or []:
                if tg not in etiketler:
                    etiketler.append(tg)
            for l in (c.get("content") or "").splitlines():
                l2 = l.strip()
                if l2 and l2 not in mevcut and not kimlik.var_mi(l2) and not l2.startswith(("⚖️ **DURUŞMA BİLGİSİ", "- **Merci:**",
                        "- **Dosya:**", "- **Duruşma Tarihi:**", "- **Duruşma Saati:**", "### DURUŞMA NOTLARI")):
                    ek.append(l2)
                    mevcut.add(l2)
        if kimlik_s and not kimlik.var_mi(icerik):
            icerik = kimlik.ekle(icerik, kimlik.satir("DURUŞMA", mahkeme=kimlik_s.get("mahkeme", ""), esas=esas,
                                                      durusma=kimlik_s.get("durusma", "")))
        elif not kimlik.var_mi(icerik):
            icerik = kimlik.ekle(icerik, kimlik.satir("DURUŞMA", esas=esas, durusma=gun))
        if ek:
            icerik += "\n\n📌 **BİRLEŞTİRİLEN NOTLAR (mükerrer duruşma görevinden):**\n" + "\n".join(ek)
        tt_post(f"{CONFIG['TICKTICK_API_BASE']}/task/{ana['id']}",
                {"id": ana["id"], "projectId": ana.get("projectId"), "content": icerik, "tags": etiketler,
                 **({"items": ana["items"]} if ana.get("items") else {})}, what="duruşma birleştirme")
        for c in kopyalar:
            if c.get("childIds"):
                print(f"   🛡️ Mükerrer duruşma silinmedi (alt görevleri var): {(c.get('title') or '')[:60]}")
                continue
            try:
                r = requests.delete(f"{CONFIG['TICKTICK_API_BASE']}/project/{c.get('projectId')}/task/{c['id']}",
                                    headers=get_ticktick_headers(), timeout=8)
                if r.status_code == 200:
                    silinen += 1
            except Exception as e:
                print(f"   ⚠️ Silinemedi ({c['id']}): {e}")
        birlesen += 1
        print(f"   🔗 Duruşma birleştirildi: {esas} {gun} -> \"{(ana.get('title') or '')[:50]}\" ({len(kopyalar)} kopya)")
    global _TUM_GOREVLER
    _TUM_GOREVLER = None
    return birlesen, silinen


def gercek_ek_var(task, barcode=None):
    """Görevde GERÇEKTEN dosya eki var mı? Tek kural, her yerde aynı (indirici + senkronizasyon).
    Eskiden notta "EKLİ EVRAKLAR" / "Cihazdaki Dosya Yolu" yazısı ya da durum dosyasındaki has_eyp
    "ek var" sayılıyordu: dosyası hiç yüklenmemiş görevler her çalışmada "eki eksik" diye işaretlenip
    senkronizasyonda "zaten mevcut" denerek HİÇ eklenmiyordu.
    - TickTick eki notta ![file](...) olarak görünür -> var.
    - Ekler son 24 saatte e-postayla gönderildiyse TickTick'in işlemesi beklenir -> var (yeniden gönderilmez)."""
    if "![file]" in ((task or {}).get("content") or ""):
        return True
    st = get_barcode_state(barcode) if barcode else None
    if (st or {}).get("ek_gorevi"):
        return True   # ekler bu görevin altındaki "📎 EYP ekleri" alt görevinde
    try:
        return time.time() - float((st or {}).get("ek_gonderildi") or 0) < 24 * 3600
    except (TypeError, ValueError):
        return False

def get_project_tasks_live(project_id, force_refresh=False):
    """Belirli bir projedeki aktif görevleri çeker ve önbelleğe alır."""
    global _PROJECT_TASKS_CACHE
    if not force_refresh and project_id in _PROJECT_TASKS_CACHE:
        return _PROJECT_TASKS_CACHE[project_id]
        
    # Okunamazsa TickTickOkumaHatasi: eskiden [] dönüyordu ve liste BOŞ sanılıp kartların kopyası açılabiliyordu.
    url = f"{CONFIG['TICKTICK_API_BASE']}/project/{project_id}/data"
    resp = tt_oku(url, what=f"liste görevleri ({project_id})")
    if resp.status_code == 404:
        print(f"⚠️ TickTick listesi bulunamadı (silinmiş/arşivlenmiş?): {project_id}")
        tasks = []
    else:
        tasks = (resp.json() or {}).get("tasks", []) if resp.content else []
    _PROJECT_TASKS_CACHE[project_id] = tasks
    return tasks

def get_completed_tasks_live(force_refresh=False):
    """TickTick'teki yakın zamanda tamamlanmış veya kapatılmış görevleri çeker."""
    global _COMPLETED_TASKS_CACHE, _LAST_COMPLETED_FETCH
    now = time.time()
    if not force_refresh and _COMPLETED_TASKS_CACHE is not None and (now - _LAST_COMPLETED_FETCH < 60):
        return _COMPLETED_TASKS_CACHE

    # Tamamlanmış görevler, kapatılmış tebligat/kartların YENİDEN açılmasını önler: okunamazsa durulur.
    url = f"{CONFIG['TICKTICK_API_BASE']}/task/completed"
    resp = tt_oku(url, what="tamamlanmış görevler", method="POST", json_body={})
    tasks = resp.json() if resp.status_code == 200 and resp.content else []
    _COMPLETED_TASKS_CACHE = tasks
    _LAST_COMPLETED_FETCH = now
    return tasks

def extract_barcode_from_text(text):
    """
    Metin içerisinden gerçek UETS barkod numarasını (11-15 haneli, genellikle 500 ile başlayan) çeker.
    Notion linklerindeki rastgele sayıları barkod olarak almaz!
    """
    if not text:
        return None
        
    # 1. Öncelik: Açıkça "Barkod: `...`" veya "Barkod: 500..." formatında yazılanlar
    m1 = re.search(r"(?:Barkod|barkod)[^\d]*(\d{11,15})", text)
    if m1:
        return m1.group(1)
        
    # 2. Öncelik: UETS 500 ile başlayan 13 haneli PTT barkodu
    m2 = re.search(r"\b(500\d{10})\b", text)
    if m2:
        return m2.group(1)
        
    # 3. Öncelik: URL dışındaki bağımsız 11-15 haneli sayılar
    clean_lines = []
    for line in text.splitlines():
        if "notion.com" in line.lower() or "http://" in line or "https://" in line:
            continue
        clean_lines.append(line)
    clean_str = " ".join(clean_lines)
    m3 = re.search(r"`?(\d{11,15})`?", clean_str)
    if m3:
        return m3.group(1)
        
    return None

def extract_esas_from_text(text):
    """Metin içinden Yıl/Sayı formatında esas numarasını çeker."""
    if not text:
        return None
    m = re.search(r"\[(\d{4}/\d+)\]", text) or re.search(r"\b(\d{4}/\d+)\b", text)
    return m.group(1) if m else None

def is_case_card(task):
    """Görevin duruşma veya tebligat değil, bir 'Ana Dava Dosyası Kartı' olup olmadığını doğrular."""
    t = (task.get("title") or "").upper()
    return not any(k in t for k in ["#DURUŞMA", "#TEBLİGAT", "#KEŞİF", "#SATIŞ", "DURUŞMA", "TEBLİGAT", "📨"])

def get_related_court_projects(court):
    c = normalize_tr(court)
    if "ceza" in c:
        return ["AsliyeCezaMahkemesi", "AğırCezaMahkemesi", "BAM-CezaDairesi", "Yargıtay-CezaDairesi", "ÇocukMahkemesi"]
    if any(k in c for k in ["idare", "vergi", "danıştay", "bim"]):
        return ["İdareMahkemesi", "VergiMahkemesi", "BİM_İdareDosyaları", "DanıştayDosyaları"]
    return ["AsliyeHukukMahkemesi", "AsliyeTicaretMahkemesi", "İşMahkemesi", "SulhHukukMahkemesi", "AileMahkemesi", "BAM_HukukDairesi", "Yargıtay-HukukDairesi"]

def find_or_create_parent_task(court, esas_no, project_id, client_tag="", notion_url=""):
    """
    Mahkeme ve esas no için Ana Dava Kartını bulur; yoksa otomatik açar.
    Daima (parent_id, actual_project_id) çifti döndürür ki TickTick içinde subtask ile parent aynı projede olsun.
    """
    global SON_KART_YENI
    SON_KART_YENI = False
    # 1. Mevcut projede ara (okunamazsa TickTickOkumaHatasi: kart "yok" sanılıp kopyası AÇILMAZ)
    tasks = get_project_tasks_live(project_id)
    for t in tasks:
        if is_case_card(t) and esas_no in (t.get("title") or ""):
            return t["id"], project_id
            
    # 2. İlgili diğer mahkeme listelerinde ara
    for rel_name in get_related_court_projects(court):
        r_pid = PROJECT_IDS.get(rel_name)
        if not r_pid or r_pid == project_id or r_pid == "inbox":
            continue
        r_tasks = get_project_tasks_live(r_pid)
        for t in r_tasks:
            if is_case_card(t) and esas_no in (t.get("title") or ""):
                # Parent bu projede! Alt görev de bu projede olmalı
                return t["id"], r_pid
                
    # 3. Bulunamadıysa yeni Ana Dava Dosyası Kartı oluştur
    raw_tag = client_tag.replace("#", "").strip() if client_tag else ""
    is_cmk_parent = raw_tag.startswith("cmk_") or "cmk" in raw_tag.lower()
    tags = normalize_tags([raw_tag] if raw_tag else [], is_cmk=is_cmk_parent)
    # Parent kartlarına ASLA 'uets' etiketi verilmez!
    tags = [tg for tg in tags if tg != "uets"]
            
    content = kimlik.satir("DOSYA", mahkeme=court, esas=esas_no) + "\n\n⚖️ **Dava Dosyası**\n"
    content += f"- **Merci:** {court}\n- **Dosya:** {esas_no} Esas\n"
    if raw_tag:
        content += f"👤 **Müvekkil:** #{raw_tag}\n"
    if notion_url:
        content += f"🔗 **Notion Dosyası:** {notion_url}\n"
        
    url = f"{CONFIG['TICKTICK_API_BASE']}/task"
    payload = {
        "title": f"{court} - {esas_no} Esas",
        "projectId": project_id,
        "content": content,
        "tags": tags,
        "priority": 0
    }
    
    if not gk.guard_create(payload, kind="kart", source="find_or_create_parent_task"):
        print(f"🛑 GATEKEEPER: Dava kartı sözleşmeyi ihlal ettiği için engellendi: {payload.get('title')}")
        return None, project_id

    created = tt_post(url, payload, what="ana dava kartı")
    if created and created.get("id"):
        tasks.append(created)
        SON_KART_YENI = True
        return created.get("id"), project_id
        
    return None, project_id

def find_existing_tebligat_in_completed(barcode, esas_no, court, deadlines=None):
    """
    Tamamlanmış veya kapatılmış (yapılmayacak) görevler arasında bu tebligatın olup olmadığını inceler.
    - Barkod varsa: YALNIZCA aynı barkodu taşıyan görevle eşleşir. Farklı barkodlu tebligatlar ASLA eşleşmez!
    - Görevde barkod yoksa: Yalnızca aynı dosya ve aynı son gün tarihi eşleşiyorsa kabul edilir.
      (Geçmiş yıllara veya farklı tebligatlara ait kapatılmış görevler yeni tebligatı ASLA engellemez!)
    """
    completed_tasks = get_completed_tasks_live()
    court_clean = clean_text(court) if court else ""
    
    for t in completed_tasks:
        c = t.get("content") or ""
        t_title = t.get("title") or ""
        t_bar = extract_barcode_from_text(c) or extract_barcode_from_text(t_title)
        
        # 1. Barkod varsa kesin barkod kontrolü
        if barcode:
            if t_bar:
                if t_bar == barcode:
                    return t
                else:
                    # Görev başka bir barkod taşıyor, bu kesinlikle farklı bir tebligattır!
                    continue
            else:
                # Görevde barkod yok: Eski veya elle açılmış görev olabilir.
                # Yalnızca esas no, mahkeme ve TARİH (yıl ve son gün) uyuyorsa eşleştir!
                if esas_no and ("TEBLİGAT" in t_title.upper() or "📨" in t_title or "#TEBLİGAT" in t_title.upper() or "uets" in (t.get("tags") or [])):
                    t_esas = extract_esas_from_text(t_title) or extract_esas_from_text(c)
                    if t_esas == esas_no:
                        t_court_clean = clean_text(t_title + " " + c)
                        if not court_clean or (court_clean in t_court_clean or t_court_clean in court_clean):
                            # Tarih kontrolü: Eğer tebligatın yasal süresi ile görev tarihi uyumsuzsa (ör. 2023 vs 2026) ASLA eşleştirme!
                            if deadlines:
                                target_str = deadlines.get("target_str") or deadlines.get("d14_str") or ""
                                d_due = (t.get("dueDate") or "")[:10]
                                m_title_due = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", t_title)
                                if m_title_due and target_str:
                                    t_due_formatted = f"{m_title_due.group(1)}.{m_title_due.group(2)}.{m_title_due.group(3)}"
                                    if t_due_formatted != target_str:
                                        continue
                                elif d_due and deadlines.get("due_iso"):
                                    if d_due != deadlines["due_iso"][:10]:
                                        continue
                                return t
        else:
            # Gelen tebligatta da barkod yoksa (nadir durum)
            if esas_no and ("TEBLİGAT" in t_title.upper() or "📨" in t_title or "#TEBLİGAT" in t_title.upper() or "uets" in (t.get("tags") or [])):
                t_esas = extract_esas_from_text(t_title) or extract_esas_from_text(c)
                if t_esas == esas_no:
                    t_court_clean = clean_text(t_title + " " + c)
                    if not court_clean or (court_clean in t_court_clean or t_court_clean in court_clean):
                        return t
                        
    return None

def find_existing_tebligat_in_active(barcode, esas_no, court, project_id, deadlines=None):
    """
    Aktif görevler arasında bu tebligatın olup olmadığını inceler.
    Farklı barkodlu tebligatları asla birbirinin üzerine yazmaz ve birleştirmez!
    """
    # 0. Bu barkod için daha önce açılan görev (kullanıcı başlığını değiştirse, listesini taşısa da aynı görev)
    if barcode:
        st = get_barcode_state(barcode) or {}
        t0 = gorev_getir(st.get("project_id"), st.get("task_id"))
        if t0 and t0.get("status", 0) == 0:
            return t0, t0.get("projectId") or st.get("project_id")
    # 0.5 TÜM listelerde kimlik satırı / nottaki barkod ile ara
    t1 = kimlige_gore_bul("TEBLİGAT", barkod=barcode) if barcode else None
    if not t1 and esas_no and not barcode:
        t1 = kimlige_gore_bul("TEBLİGAT", esas=esas_no, mahkeme=court)
    if t1:
        return t1, t1.get("_pid") or t1.get("projectId") or project_id

    proj_tasks = get_project_tasks_live(project_id)
    court_clean = clean_text(court) if court else ""
    
    # 1. Barkod ile ara (en kesin)
    if barcode:
        for t in proj_tasks:
            t_bar = extract_barcode_from_text(t.get("content") or "") or extract_barcode_from_text(t.get("title") or "")
            if t_bar == barcode:
                return t, project_id
                
        # Inbox'ta ara (eğer mevcut project_id Inbox değilse)
        inbox_pid = PROJECT_IDS.get("Inbox", "inbox")
        if inbox_pid != project_id:
            inbox_tasks = get_project_tasks_live(inbox_pid)
            for ot in inbox_tasks:
                ot_bar = extract_barcode_from_text(ot.get("content") or "") or extract_barcode_from_text(ot.get("title") or "")
                if ot_bar == barcode:
                    return ot, inbox_pid

    # 2. Esas No ve Mahkeme ile ara (Yalnızca görevde barkod yoksa veya bilinmiyorsa)
    if esas_no:
        for t in proj_tasks:
            t_title = t.get("title") or ""
            t_cnt = t.get("content") or ""
            if "TEBLİGAT" in t_title.upper() or "📨" in t_title or "uets" in (t.get("tags") or []):
                t_esas = extract_esas_from_text(t_title) or extract_esas_from_text(t_cnt)
                if t_esas == esas_no:
                    t_bar = extract_barcode_from_text(t_cnt) or extract_barcode_from_text(t_title)
                    # Eğer görev farklı bir barkod taşıyorsa, KESİNLİKLE farklı bir tebligattır!
                    if barcode and t_bar and barcode != t_bar:
                        continue
                    # Eğer görevde barkod yoksa, ancak tarih parametresi verildiyse tarihleri doğrula:
                    if deadlines and not t_bar:
                        target_str = deadlines.get("target_str") or deadlines.get("d14_str") or ""
                        d_due = (t.get("dueDate") or "")[:10]
                        m_title_due = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", t_title)
                        if m_title_due and target_str:
                            t_due_formatted = f"{m_title_due.group(1)}.{m_title_due.group(2)}.{m_title_due.group(3)}"
                            if t_due_formatted != target_str:
                                continue
                        elif d_due and deadlines.get("due_iso"):
                            if d_due != deadlines["due_iso"][:10]:
                                continue
                    t_court_clean = clean_text(t_title + " " + t_cnt)
                    if not court_clean or (court_clean in t_court_clean or t_court_clean in court_clean):
                        return t, project_id

        # Inbox'ta Esas No ara
        inbox_pid = PROJECT_IDS.get("Inbox", "inbox")
        if inbox_pid != project_id:
            inbox_tasks = get_project_tasks_live(inbox_pid)
            for t in inbox_tasks:
                t_title = t.get("title") or ""
                t_cnt = t.get("content") or ""
                if "TEBLİGAT" in t_title.upper() or "📨" in t_title or "uets" in (t.get("tags") or []):
                    t_esas = extract_esas_from_text(t_title) or extract_esas_from_text(t_cnt)
                    if t_esas == esas_no:
                        t_bar = extract_barcode_from_text(t_cnt) or extract_barcode_from_text(t_title)
                        if barcode and t_bar and barcode != t_bar:
                            continue
                        if deadlines and not t_bar:
                            target_str = deadlines.get("target_str") or deadlines.get("d14_str") or ""
                            d_due = (t.get("dueDate") or "")[:10]
                            m_title_due = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", t_title)
                            if m_title_due and target_str:
                                t_due_formatted = f"{m_title_due.group(1)}.{m_title_due.group(2)}.{m_title_due.group(3)}"
                                if t_due_formatted != target_str:
                                    continue
                            elif d_due and deadlines.get("due_iso"):
                                if d_due != deadlines["due_iso"][:10]:
                                    continue
                        t_court_clean = clean_text(t_title + " " + t_cnt)
                        if not court_clean or (court_clean in t_court_clean or t_court_clean in court_clean):
                            return t, inbox_pid

    return None, project_id

def create_task_direct_api(title, project_id, parent_id, content, start_iso, due_iso, tags=None, priority=5):
    """TickTick REST API ile doğrudan görev açar."""
    if isinstance(parent_id, (tuple, list)):
        p_id = parent_id[0] if parent_id else None
        p_pid = parent_id[1] if len(parent_id) > 1 else project_id
        parent_id = p_id
        if p_pid:
            project_id = p_pid
    url = f"{CONFIG['TICKTICK_API_BASE']}/task"
    payload = {
        "title": title,
        "projectId": project_id,
        "content": content,
        "startDate": start_iso,
        "dueDate": due_iso,
        "isAllDay": False,
        "timeZone": "Europe/Istanbul",
        "priority": priority,
        "tags": tags or []
    }
    if parent_id:
        payload["parentId"] = parent_id
    if not gk.guard_create(payload, source="create_task_direct_api"):
        print(f"🛑 GATEKEEPER: Görev sözleşmeyi ihlal ettiği için engellendi: {title}")
        return None
    created = tt_post(url, payload, what="görev")
    return created if created and created.get("id") else None

def create_or_update_uets_subtask(tebligat, project_id, parent_id, client_tag="", notion_url="", list_name="Inbox", is_cmk=False, force=False):
    """
    UETS Tebligatı için alt görev oluşturur veya var olan görevi mükerrer yapmadan günceller.
    - Tamamlanmış / yapılmayacak görevleri kontrol eder.
    - Merci türüne göre doğru süreyi (İcra/Ceza: 7 gün, Hukuk: 14 gün, İdari: 30 gün) ve hafta sonu kuralını seçer.
    - E-posta ile ek gönderiminde tarih bozulmasını engeller.
    - Kullanıcının elle girdiği notları ASLA bozmaz.
    """
    if isinstance(parent_id, (tuple, list)):
        p_id = parent_id[0] if parent_id else None
        p_pid = parent_id[1] if len(parent_id) > 1 else project_id
        parent_id = p_id
        if p_pid:
            project_id = p_pid

    court = tebligat["court"]
    esas_no = tebligat["esas_no"]
    barcode = tebligat.get("barcode") or ""
    deadlines = tebligat["deadlines"]
    parties = tebligat.get("parties", [])
    documents = tebligat.get("documents", [])
    extracted_paths = tebligat.get("extracted_paths", [])
    
    # Uygulanacak yasal süreyi belirle (7, 14 veya 30 gün)
    target_deadline_str = deadlines.get("target_str") or deadlines["d14_str"]
    target_due_iso = deadlines.get("due_iso") or deadlines["due_iso"]
    target_label = deadlines.get("target_label") or "Yasal Süre"
    
    title = f"📨 TEBLİGAT - {court} - {esas_no} Esas (Son Gün: {target_deadline_str})"
    
    # -------------------------------------------------------------------------
    # ADIM 1: Tamamlanmış (status=2) veya Kapatılmış / Yapılmayacak Görev Kontrolü
    # -------------------------------------------------------------------------
    completed_task = find_existing_tebligat_in_completed(barcode, esas_no, court, deadlines=deadlines)
    if completed_task:
        c_status = completed_task.get("status")
        lbl = "Tamamlandı" if c_status == 2 else "Yapılmayacak"
        print(f"   🛡️ Bu tebligat daha önce '{lbl}' olarak kapatılmış ({court} - {esas_no}, Barkod: {barcode}). Yeniden açılmadı.")
        update_barcode_state(barcode, completed_task["id"], has_eyp=True, project_id=completed_task.get("projectId"))
        return completed_task["id"], False, "completed"
        
    b_state = get_barcode_state(barcode) if barcode else {}
    if b_state and (b_state.get("status") in ["completed", 2, "2"]):
        print(f"   🛡️ Bu tebligat daha önce 'Tamamlandı' olarak kapatılmış ({court} - {esas_no}, Barkod: {barcode}). Yeniden açılmadı.")
        return b_state.get("task_id", "completed"), False, "completed"
        
    if b_state and b_state.get("task_id") and b_state.get("project_id"):
        tid = b_state["task_id"]
        pid = b_state["project_id"]
        try:
            r = requests.get(f"{CONFIG['TICKTICK_API_BASE']}/project/{pid}/task/{tid}", headers=get_ticktick_headers(), timeout=6)
            if r.status_code == 200:
                t_obj = r.json()
                if t_obj.get("status", 0) != 0:
                    lbl = "Tamamlandı" if t_obj.get("status") == 2 else "Yapılmayacak"
                    print(f"   🛡️ Bu tebligat daha önce '{lbl}' olarak kapatılmış ({court} - {esas_no}). Yeniden açılmadı.")
                    update_barcode_state(barcode, tid, has_eyp=True, project_id=pid, status="completed")
                    return tid, False, "completed"
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # ADIM 2: Aktif Görevler Arasında Mükerrer Kontrolü
    # -------------------------------------------------------------------------
    existing_task, task_pid = find_existing_tebligat_in_active(barcode, esas_no, court, project_id, deadlines=deadlines)
    if existing_task:
        project_id = task_pid

    # Etiketleri Kurala Göre Normalize Et (#erolatmaca, #cmk_..., #cmk, #uets vb.)
    raw_tag = client_tag.replace("#", "").strip() if client_tag else ""
    initial_tags = ["uets"]
    if raw_tag:
        initial_tags.append(raw_tag)
    tags = normalize_tags(initial_tags, is_cmk=is_cmk)
            
    kimlik_s = kimlik.satir("TEBLİGAT", mahkeme=court, esas=esas_no, barkod=barcode,
                            uets_no=tebligat.get("uets_no", ""), gonderen=tebligat.get("gonderen", ""))
    content = kimlik_s + "\n\n🔔 **YENİ ELEKTRONİK TEBLİGAT**\n\n"
    if notion_url:
        content += f"🔗 **Notion Dosyası:** {notion_url}\n\n"
        
    content += f"- **Merci:** {court}\n"
    content += f"- **Dosya:** {esas_no} Esas\n"
    content += f"- **Barkod:** `{barcode}`\n"
    content += f"- **Geliş:** {deadlines['gelis_str']}\n"
    content += f"- **Tebliğ Sayılma (5. Gün):** {deadlines['teblig_str']}\n"
    content += f"- ⏳ **UYGULANAN YASAL SÜRE:** **{target_deadline_str} (17:00)** ✅ ({target_label})\n"
    content += f"- **7 Günlük Süre Sonu:** {deadlines['d7_str']}\n"
    content += f"- **14 Günlük Süre Sonu:** {deadlines['d14_str']} (17:00)\n\n"
    
    if parties:
        content += "👥 **TARAFLAR:**\n"
        for p in parties:
            content += f"- **{p['rol']}:** {p['adi']}\n"
        content += "\n"
        
    if documents:
        content += "📑 **EKLİ EVRAKLAR (EYP Paketi):**\n"
        for doc in documents:
            line = f"- 📄 `{doc['name']}`"
            if doc.get("doc_type"):
                line += f" ({doc['doc_type']})"
            if doc.get("hearing_date"):
                line += f" ⚖️ **Duruşma: {doc['hearing_date']} {doc.get('hearing_time') or ''}**"
            content += line + "\n"
        content += "\n"
        
    if extracted_paths:
        folder_dir = os.path.dirname(extracted_paths[0])
        content += f"📁 **Cihazdaki Dosya Yolu:**\n`{folder_dir}`\n\n"
        
    content += "### YAPILACAK İŞLEM & CEVAP NOTU:\n\n"

    # -------------------------------------------------------------------------
    # SENARYO 1: Görev zaten var AMA daha önce ekler (EYP) yüklenmemişti, şimdi EYP indi!
    # -------------------------------------------------------------------------
    # Önceki turda e-postası gönderilip TickTick'te geç oluşan "📎 EYP ekleri" görevi varsa şimdi bağlanır
    if existing_task and barcode:
        st_ek = get_barcode_state(barcode) or {}
        if st_ek.get("ek_gonderildi") and not st_ek.get("ek_gorevi"):
            bekleyen = kimlige_gore_bul("EK", barkod=barcode)
            if bekleyen:
                ek_pid0 = existing_task.get("projectId") or project_id
                if bekleyen.get("parentId") != existing_task["id"]:
                    tt_post(f"{CONFIG['TICKTICK_API_BASE']}/task/{bekleyen['id']}",
                            {"id": bekleyen["id"], "projectId": ek_pid0, "parentId": existing_task["id"]}, what="ek alt görevi bağlama")
                update_barcode_state(barcode, existing_task["id"], has_eyp=True, project_id=ek_pid0, ek_gorevi=bekleyen["id"])
                print("   🔗 Önceki turda gönderilen ekler görevin altına bağlandı.")
    has_real_attachment = gercek_ek_var(existing_task, barcode) if existing_task else False
    if existing_task and extracted_paths and not has_real_attachment:
        # ESKİ DAVRANIŞ: ekler için görevi e-postayla YENİDEN açıp eskisini siliyordu -> kullanıcının alt
        # görevleri, hatırlatmaları, yorumları, kendi kurduğu üst/alt düzeni kayboluyordu.
        # YENİ: kullanıcının görevine HİÇ dokunulmaz; EYP dosyaları onun altına "📎 EYP ekleri" alt görevi
        # olarak eklenir (TickTick'e dosya ancak e-postayla yüklenebiliyor).
        print(f"   📎 Sonradan İndirilen EYP Tespit Edildi! Ekler, mevcut görevin ALTINA ekleniyor ({court} - {esas_no})...")
        ek_pid = existing_task.get("projectId") or project_id
        ek_kimlik = kimlik.satir("EK", mahkeme=court, esas=esas_no, barkod=barcode)

        def _ek_gorevini_bagla(ek):
            if ek.get("parentId") != existing_task["id"]:
                tt_post(f"{CONFIG['TICKTICK_API_BASE']}/task/{ek['id']}",
                        {"id": ek["id"], "projectId": ek_pid, "parentId": existing_task["id"]}, what="ek alt görevi bağlama")
            update_barcode_state(barcode, existing_task["id"], has_eyp=True, project_id=ek_pid, ek_gorevi=ek["id"])

        # Daha önce gönderilmiş ama henüz bağlanmamış ek görevi var mı?
        onceki = kimlige_gore_bul("EK", barkod=barcode) if barcode else None
        if onceki:
            _ek_gorevini_bagla(onceki)
            print("   🔗 Önceki ek görevi bulunup mevcut görevin altına bağlandı.")
            return existing_task["id"], False, "updated"

        list_tag = f" ~{list_name}" if list_name and list_name != "Inbox" else ""
        ek_konu = f"📎 EYP ekleri - {court} - {esas_no} Esas{list_tag}"
        ek_govde = (ek_kimlik + "\n\n📎 Bu alt görev, üstteki tebligatın EYP paketinden çıkan evrakları taşır.\n"
                    "Asıl iş üst görevde; bu görevi tamamlayabilir ya da silebilirsiniz.\n")
        known_ids = {t["id"] for t in tum_aktif_gorevler(force=True)}
        sent = send_task_via_email(ek_konu, ek_govde, extracted_paths)
        if sent and barcode:
            update_barcode_state(barcode, existing_task["id"], has_eyp=True, project_id=ek_pid, ek_gonderildi=time.time())
        if sent:
            print("   ⏳ TickTick ekleri işliyor (en çok 70 sn)...")
            for _ in range(14):
                time.sleep(5)
                for ct in tum_aktif_gorevler(force=True):
                    if ct["id"] not in known_ids and kimlik.oku(ct.get("content") or "").get("tur") == "EK" \
                            and kimlik.oku(ct.get("content") or "").get("barkod") == barcode:
                        _ek_gorevini_bagla(ct)
                        print("   ✅ Ekler mevcut görevin altına bağlandı (başlık, alt görevler, düzen korunuyor).")
                        return existing_task["id"], False, "updated"
            print("   ⏳ E-posta TickTick'e ulaştı; ek görevi gelince bir sonraki turda bağlanacak.")
        # Mevcut görevin tarihlerini/etiketlerini/kimliğini koru-düzelt (başlığa, üste, alt görevlere dokunmadan)
        eski_icerik = existing_task.get("content") or ""
        update_task_details(existing_task["id"], project_id, parent_id, deadlines["start_iso"], target_due_iso,
                            etiket_birlestir(existing_task.get("tags"), tags), title=None,
                            content=None if kimlik.var_mi(eski_icerik) else kimlik.ekle(eski_icerik, kimlik_s))
        return existing_task["id"], False, "updated"

    # -------------------------------------------------------------------------
    # SENARYO 2: Görev zaten mevcut -> Yasal süreyi, etiketleri ve parent'ı doğrula/düzelt (Başlığı ASLA EZME!)
    # -------------------------------------------------------------------------
    if existing_task:
        # KULLANICI KURALI: Kullanıcının elle girdiği veya düzenlediği görev başlığı (title) ASLA ezilmez (title=None)!
        # Etiketler: kullanıcının eklediği etiketler korunur. Öncelik: kullanıcının değiştirdiği korunur.
        # Not: kimlik satırı yoksa en üste eklenir (esas no/mahkeme başlık değişse de görevde kalır).
        eski_icerik = existing_task.get("content") or ""
        update_task_details(existing_task["id"], project_id, parent_id, deadlines["start_iso"], target_due_iso,
                            etiket_birlestir(existing_task.get("tags"), tags), title=None,
                            content=None if kimlik.var_mi(eski_icerik) else kimlik.ekle(eski_icerik, kimlik_s))
        update_barcode_state(barcode, existing_task["id"], has_eyp=has_real_attachment, project_id=project_id)
        return existing_task["id"], False, "updated"

    # -------------------------------------------------------------------------
    # SENARYO 3: YEPYENİ Görev ve EYP Ekleri Mevcut -> Mail ile EK YÜKLE
    # -------------------------------------------------------------------------
    guard_entry = {
        "title": title,
        "projectId": project_id,
        "parentId": parent_id,
        "content": content,
        "startDate": deadlines["start_iso"],
        "dueDate": target_due_iso,
        "tags": tags,
        "priority": 5
    }
    if not gk.guard_create(guard_entry, kind="tebligat", source="create_or_update_uets_subtask"):
        print(f"🛑 GATEKEEPER: Tebligat görevi sözleşmeyi ihlal ettiği için engellendi: {title}")
        return None, False, "quarantined"

    if extracted_paths:
        print(f"   📎 EYP Ekleri E-posta ile TickTick'e Yükleniyor ({court} - {esas_no})...")
        list_tag = f" ~{list_name}" if list_name and list_name != "Inbox" else ""
        clean_email_subj = f"📨 TEBLİGAT - {court} - {esas_no} Esas{list_tag} #uets !high"
        if raw_tag:
            clean_email_subj += f" #{raw_tag}"
            
        proj_tasks = get_project_tasks_live(project_id, force_refresh=True)
        inbox_tasks = get_project_tasks_live(PROJECT_IDS.get("Inbox", "inbox"), force_refresh=True)
        known_ids = {t["id"] for t in (proj_tasks + inbox_tasks)}
        
        sent = send_task_via_email(clean_email_subj, content, extracted_paths)
        if sent and barcode:
            update_barcode_state(barcode, "pending_email", has_eyp=True, project_id=project_id, ek_gonderildi=time.time())
        if sent:
            print("   ⏳ TickTick ekleri işliyor, senkronize ediliyor (70 sn)...")
            new_task = None
            for _ in range(14):
                time.sleep(5)
                cur_tasks = get_project_tasks_live(project_id, force_refresh=True) + get_project_tasks_live(PROJECT_IDS.get("Inbox", "inbox"), force_refresh=True)
                for ct in cur_tasks:
                    if ct["id"] not in known_ids and (barcode in (ct.get("content") or "") or esas_no in (ct.get("title") or "")):
                        new_task = ct
                        break
                if new_task:
                    break
                    
            if new_task:
                update_task_details(new_task["id"], project_id, parent_id, deadlines["start_iso"], target_due_iso, tags, title=title, priority=5)
                update_barcode_state(barcode, new_task["id"], has_eyp=True, project_id=project_id)
                return new_task["id"], True, "new"
            else:
                print("   ⏳ E-posta TickTick'e ulaştı, ekler işleniyor. Mükerrer açılmaması için API ile ikinci görev açılmadı.")
                update_barcode_state(barcode, "pending_email", has_eyp=True, project_id=project_id)
                return "pending_email", True, "new"

    # -------------------------------------------------------------------------
    # SENARYO 4: Henüz EYP inmemiş -> KULLANICI KURALI / ZORLA EKLEME
    # -------------------------------------------------------------------------
    # Güvenlik ağı: EYP indirilemiyorsa (UETS oturumu, ağ, portal değişikliği...) yasal süre görevi HİÇ açılmıyordu.
    # Tebligatın gelişinden EYP_BEKLEME_SAAT (varsayılan 6) saat geçtiyse görev eksiz açılır, ek sonra eklenir.
    if not force:
        try:
            bekleme = float(CONFIG.get("EYP_BEKLEME_SAAT", 6))
            gelis = deadlines.get("gelis_dt")
            if bekleme >= 0 and gelis is not None:
                gecen_saat = (datetime.now(gelis.tzinfo) - gelis).total_seconds() / 3600
                if gecen_saat >= bekleme:
                    print(f"   ⚠️ EYP {gecen_saat:.0f} saattir indirilemedi; yasal süre kaçmasın diye görev eksiz açılıyor.")
                    force = True
        except Exception:
            pass

    if force:
        print(f"   ⚡ EYP henüz yerel arşivde olmasa da kullanıcı/sistem talebiyle görev REST API ile açılıyor ({court} - {esas_no})...")
        created_task = create_task_direct_api(
            title=title,
            project_id=project_id,
            parent_id=parent_id,
            content=content + "\n\n⚠️ **NOT:** EYP ekleri henüz indirilmedi. UETS'den indirildiğinde ekler otomatik yüklenecektir.",
            start_iso=deadlines["start_iso"],
            due_iso=target_due_iso,
            tags=tags,
            priority=5
        )
        if created_task:
            tid = created_task.get("id")
            update_barcode_state(barcode, tid, has_eyp=False, project_id=project_id)
            print(f"   ⭐ TickTick: GÖREV BAŞARIYLA OLUŞTURULDU (ID: {tid})")
            return tid, True, "new"

    print(f"   ⏳ EYP paketi henüz yerel arşivde mevcut değil ({court} - {esas_no}, Barkod: {barcode}).")
    print(f"   🛑 Standart akış gereği üstyazı ve ekleri olmayan eksiz görev açılmadı (EYP indirildiğinde eklenecek).")
    print(f"   💡 İpucu: Eksiz olarak hemen açmak için --force / -f parametresini veya GUI'deki 'Zorla Ekle' butonunu kullanabilirsiniz.")
    return None, False, "pending_eyp"

def update_task_details(task_id, project_id, parent_id, start_iso=None, due_iso=None, tags=None, title=None, content=None, priority=None):
    if isinstance(parent_id, (tuple, list)):
        p_id = parent_id[0] if parent_id else None
        p_pid = parent_id[1] if len(parent_id) > 1 else project_id
        parent_id = p_id
        if p_pid:
            project_id = p_pid
    url = f"{CONFIG['TICKTICK_API_BASE']}/task/{task_id}"
    # KULLANICI DÜZENİNE SAYGI: görevin ŞU ANKİ hâli okunur.
    #  - Liste: kullanıcı görevi başka listeye taşıdıysa geri taşınmaz (mevcut projectId kullanılır).
    #  - Üst görev: görevin zaten bir üstü varsa (kullanıcı kendi görevinin altına koymuş olabilir)
    #    DEĞİŞTİRİLMEZ; yalnızca üstü olmayan (yetim) görev, AYNI listedeki dava kartına bağlanır.
    #  - Alt görevler (childIds) ve kontrol listesi maddeleri (items) olduğu gibi korunur.
    mevcut = gorev_getir(project_id, task_id)
    if mevcut is None:
        for t in tum_aktif_gorevler():
            if t.get("id") == task_id:
                mevcut = t
                break
    if mevcut:
        project_id = mevcut.get("projectId") or project_id
        if mevcut.get("parentId"):
            parent_id = None
        elif parent_id:
            ust = gorev_getir(project_id, parent_id)
            if not ust:   # dava kartı başka listede: TickTick'te alt görev üstüyle aynı listede olmalı
                parent_id = None
    payload = {
        "id": task_id,
        "projectId": project_id,
    }
    if mevcut and mevcut.get("items"):
        payload["items"] = mevcut["items"]
    # Öncelik yalnızca açıkça istenirse yazılır (eskiden her güncelleme kullanıcının önceliğini 5'e çekiyordu)
    if priority is not None:
        payload["priority"] = priority
    if start_iso:
        payload["startDate"] = start_iso
    if due_iso:
        payload["dueDate"] = due_iso
        payload["isAllDay"] = False
        payload["timeZone"] = "Europe/Istanbul"
    if parent_id:
        payload["parentId"] = parent_id
    if tags is not None:
        payload["tags"] = tags
    if title:
        payload["title"] = title
    if content:
        payload["content"] = content
    tt_post(url, payload, what="görev güncelleme", timeout=8)

def create_or_update_esassiz_tebligat(item):
    """Barkodu/esas numarası olmayan tebligat (ör. noter AZİLNAME) için görev açar ya da var olanı korur.
    Tekil anahtar: UETS mesaj numarası (yoksa konu + geliş zamanı). Dava kartına bağlanmaz (dosyası yok).
    Döner: (görev_id, yeni_mi)."""
    uets_no = (item.get("uets_no") or "").strip()
    if not uets_no and not (item.get("konu_raw") or "").strip():
        # Yalnızca UETS listesinden gelen (konu satırı/UETS no taşıyan) kayıtlar görev açar; içi okunamayan
        # tek başına bir EYP dosyası boş "Tebligat" görevi açmamalı.
        return None, False
    konu = re.sub(r"\s+", " ", (item.get("konu_raw") or item.get("court") or "Tebligat")).strip()
    gonderen = (item.get("gonderen") or "").strip()
    deadlines = item["deadlines"]
    anahtar = f"UETS:{uets_no}" if uets_no else f"KONU:{clean_text(konu)}:{deadlines.get('gelis_str', '')}"
    print(f"\n📨 İşleniyor (esas nosuz): {konu[:70]} — {gonderen[:50]}")

    # 1) Daha önce açıldı mı? (durum dosyası -> kimlik satırı; başlık/liste değişse de bulunur)
    st = get_barcode_state(anahtar) or {}
    t0 = gorev_getir(st.get("project_id"), st.get("task_id"))
    if t0:
        if t0.get("status", 0) != 0:
            print("   🛡️ Bu tebligat daha önce kapatılmış. Yeniden açılmadı.")
            return t0["id"], False
        print("   🛡️ TickTick: Görev zaten mevcut (başlık/liste değişmiş olabilir).")
        return t0["id"], False
    if uets_no:
        t1 = kimlige_gore_bul("TEBLİGAT", uets_no=uets_no)
        if t1:
            update_barcode_state(anahtar, t1["id"], project_id=t1.get("projectId"))
            print("   🛡️ TickTick: Görev zaten mevcut.")
            return t1["id"], False
        for ct in get_completed_tasks_live():
            if kimlik.oku(ct.get("content") or "").get("uets_no") == uets_no:
                update_barcode_state(anahtar, ct["id"], project_id=ct.get("projectId"), status="completed")
                print("   🛡️ Bu tebligat daha önce kapatılmış. Yeniden açılmadı.")
                return ct["id"], False

    # 2) Yeni görev (eksiz de olsa açılır; hiçbir tebligat kaçırılmaz)
    pid = PROJECT_IDS.get("Inbox", "inbox")
    kimlik_s = kimlik.satir("TEBLİGAT", uets_no=uets_no, gonderen=gonderen, konu=konu)
    target = deadlines.get("target_str") or deadlines.get("d14_str")
    content = kimlik_s + "\n\n🔔 **YENİ ELEKTRONİK TEBLİGAT (esas numarası yok)**\n\n"
    content += f"- **Konu:** {konu}\n- **Gönderen:** {gonderen}\n"
    if uets_no:
        content += f"- **UETS No:** `{uets_no}`\n"
    content += f"- **Geliş:** {deadlines.get('gelis_str', '')}\n"
    content += f"- ⏳ **Hatırlatma / süre:** {target} (17:00) — {deadlines.get('target_label', '')}\n\n"
    eyp_yolu = None
    for d in CONFIG.get("DOWNLOAD_DIRS", []):
        aday = os.path.join(d, f"{uets_no}.eyp") if uets_no else ""
        if aday and os.path.exists(aday):
            eyp_yolu = aday
            break
    if eyp_yolu:
        content += f"📁 **EYP Paketi:** `{eyp_yolu}`\n\n"
    else:
        content += "⚠️ **NOT:** EYP paketi henüz indirilmedi.\n\n"
    content += "### YAPILACAK İŞLEM & CEVAP NOTU:\n\n"
    title = f"📨 TEBLİGAT - {konu[:80]} (Son Gün: {target})"
    created = create_task_direct_api(title=title, project_id=pid, parent_id=None, content=content,
                                     start_iso=deadlines["start_iso"], due_iso=deadlines["due_iso"],
                                     tags=["uets"], priority=5)
    if created:
        update_barcode_state(anahtar, created["id"], has_eyp=bool(eyp_yolu), project_id=created.get("projectId") or pid)
        print(f"   ⭐ TickTick: YENİ GÖREV OLUŞTURULDU (esas nosuz) (ID: {created['id']})")
        return created["id"], True
    return None, False


def create_or_update_durusma_subtask(court, esas_no, project_id, parent_id, hearing_date, hearing_time="", client_tag="", notion_url="", doc_name="", is_cmk=False):
    """
    Duruşma için TickTick'te ana dava dosyasının altına duruşma alt görevi oluşturur veya günceller.
    - Tarih ve saati tam olarak ayarlar (Europe/Istanbul UTC+3 duvar saati korunur).
    - Duruşma görevlerine ASLA 'uets' etiketi vermez.
    - Mükerrer açılmasını engeller (aynı esas ve aynı duruşma günü varsa tekrar açmaz).
    - Üst dava kartıyla aynı proje ID'sini garanti eder.
    """
    if isinstance(parent_id, (tuple, list)):
        p_id = parent_id[0] if parent_id else None
        p_pid = parent_id[1] if len(parent_id) > 1 else project_id
        parent_id = p_id
        if p_pid:
            project_id = p_pid

    from utils import parse_hearing_datetime
    dt, due_iso = parse_hearing_datetime(hearing_date, hearing_time)
    if not due_iso:
        try:
            parts = hearing_date.replace(".", "/").split("/")
            due_iso = f"{parts[2]}-{parts[1]}-{parts[0]}T09:00:00+0300"
        except Exception:
            due_iso = None

    proj_tasks = get_project_tasks_live(project_id)
    inbox_tasks = get_project_tasks_live(PROJECT_IDS.get("Inbox", "inbox"))
    # Önce kimlik satırıyla TÜM listelerde (başlık değişmiş/taşınmış olabilir)
    existing_durusma = kimlige_gore_bul("DURUŞMA", esas=esas_no, mahkeme=court, durusma=hearing_date)
    # Kimliksiz eski görevler (bulut betiği / elle açılan): TÜM listelerde; tarih notta YOKSA TickTick'in
    # tarih alanından (dueDate) karşılaştırılır. Eskiden yalnızca nottaki tarihe bakılıyordu: notunda tarih
    # yazmayan duruşma görevi tanınmıyor, takvimden aynı duruşma için ikinci görev açılıyordu.
    hd_gun = _gun_anahtari(hearing_date)
    for t in ([] if existing_durusma else tum_aktif_gorevler()):
        if not durusma_gorevi_mi(t):
            continue
        t_title = t.get("title") or ""
        t_cnt = t.get("content") or ""
        if esas_no in t_title or esas_no in t_cnt:
            clean_hd = hearing_date.replace(".", "/")
            if clean_hd in t_cnt.replace(".", "/") or clean_hd in t_title.replace(".", "/") \
                    or (hd_gun and _yerel_gun(t.get("dueDate")) == hd_gun):
                existing_durusma = t
                break

    if not existing_durusma:
        # Kullanıcı duruşma görevini TAMAMLADIYSA (duruşma geçtiği için) yeniden açılmaz. Eskiden yalnızca
        # aktif görevlere bakılıyordu: tamamlanan duruşma için ertesi turda aynı görev tekrar açılıyordu.
        gun = hearing_date.replace(".", "/").strip()[:10]
        for ct in get_completed_tasks_live():
            c_t, c_c = ct.get("title") or "", ct.get("content") or ""
            k_c = kimlik.oku(c_c)
            durusma_mi = k_c.get("tur") == "DURUŞMA" or "DURUŞMA" in c_t.upper() or "⚖️" in c_t
            if durusma_mi and (esas_no in c_t or esas_no in c_c or k_c.get("esas") == esas_no) \
                    and (gun in c_c.replace(".", "/") or gun in c_t.replace(".", "/") or (k_c.get("durusma") or "").replace(".", "/").startswith(gun)):
                print(f"   🛡️ Duruşma görevi daha önce kapatılmış ({hearing_date}). Yeniden açılmadı.")
                return ct["id"], False
        # Tarihi geçmiş duruşma için yeni görev açılmaz (yalnızca var olan güncellenir)
        if dt is not None:
            from config import TZ_TURKEY as _TZ
            from datetime import datetime as _dt
            if dt.date() < _dt.now(_TZ).date():
                print(f"   ⏭️ Duruşma tarihi geçmiş ({hearing_date}); yeni görev açılmadı.")
                return None, False

    raw_tag = client_tag.replace("#", "").strip() if client_tag else ""
    initial_tags = ["duruşma"]
    if raw_tag:
        initial_tags.append(raw_tag)
    # Duruşma görevlerine ASLA 'uets' etiketi verilmez!
    tags = normalize_tags(initial_tags, is_cmk=is_cmk, is_uets=False)
    tags = [tg for tg in tags if tg != "uets"]

    title = f"⚖️ DURUŞMA - {court} - {esas_no} Esas"
    if hearing_time:
        title += f" (Saat: {hearing_time})"

    kimlik_d = kimlik.satir("DURUŞMA", mahkeme=court, esas=esas_no,
                            durusma=f"{hearing_date} {hearing_time}".strip())
    content = kimlik_d + "\n\n⚖️ **DURUŞMA BİLGİSİ**\n\n"
    if notion_url:
        content += f"🔗 **Notion Dosyası:** {notion_url}\n\n"
    content += f"- **Merci:** {court}\n"
    content += f"- **Dosya:** {esas_no} Esas\n"
    content += f"- **Duruşma Tarihi:** {hearing_date}\n"
    if hearing_time:
        content += f"- **Duruşma Saati:** {hearing_time}\n"
    if doc_name:
        content += f"- **Dayanak Belge:** `{doc_name}`\n"
    content += "\n### DURUŞMA NOTLARI & HAZIRLIK:\n"

    if existing_durusma:
        # KULLANICI KURALI: Duruşma görevi zaten mevcutsa başlığı ezme (title=None)
        eski_icerik = existing_durusma.get("content") or ""
        update_task_details(existing_durusma["id"], existing_durusma.get("projectId") or project_id, parent_id,
                            due_iso=due_iso, tags=etiket_birlestir(existing_durusma.get("tags"), tags), title=None,
                            content=None if kimlik.var_mi(eski_icerik) else kimlik.ekle(eski_icerik, kimlik_d))
        return existing_durusma["id"], False

    url = f"{CONFIG['TICKTICK_API_BASE']}/task"
    payload = {
        "title": title,
        "projectId": project_id,
        "content": content,
        "startDate": due_iso,
        "dueDate": due_iso,
        "timeZone": "Europe/Istanbul",
        "isAllDay": False,
        "priority": 5,
        "tags": tags,
        "parentId": parent_id
    }

    if not gk.guard_create(payload, kind="durusma", source="create_or_update_durusma_subtask"):
        print(f"🛑 GATEKEEPER: Duruşma görevi sözleşmeyi ihlal ettiği için engellendi: {title}")
        return None, False

    created = tt_post(url, payload, what="duruşma görevi")
    if created and created.get("id"):
        proj_tasks.append(created)
        return created.get("id"), True

    return None, False

def clean_and_merge_duplicates():
    """
    Tüm projelerdeki (ve Inbox'taki) mükerrer görevleri tarar, elle girilmiş notları birleştirir,
    bozulmuş başlık ve süreleri düzeltir, fazlalıkları siler.
    """
    print("🧹 TickTick mükerrer görev taraması ve birleştirme başlıyor...")
    birlestirilen = 0
    silinen = 0
    
    all_projects = list(PROJECT_IDS.items())
    all_tasks = []
    seen_pids = set()
    
    for pname, pid in all_projects:
        if pid in seen_pids:
            continue
        seen_pids.add(pid)
        tasks = get_project_tasks_live(pid, force_refresh=True)
        for t in tasks:
            t["_list_name"] = pname
            t["_actual_pid"] = pid
            all_tasks.append(t)
            
    groups = {}
    for t in all_tasks:
        if t.get("status", 0) != 0:
            continue
            
        title = t.get("title") or ""
        content = t.get("content") or ""
        tags = t.get("tags") or []
        
        # Tür ve dosya bilgisi önce KİMLİK satırından okunur: kullanıcı başlığı değiştirse de görev tanınır.
        k = kimlik.oku(content)
        if k:
            if k.get("tur") != "TEBLİGAT":
                continue
        elif not ("TEBLİGAT" in title.upper() or "uets" in tags or "📨" in title):
            continue

        barcode = k.get("barkod") or extract_barcode_from_text(content) or extract_barcode_from_text(title)
        esas_no = k.get("esas") or extract_esas_from_text(content) or extract_esas_from_text(title)

        court_part = clean_text(k["mahkeme"]) if k.get("mahkeme") else ""
        if not court_part and " - " in title and not kimlik.kullanici_basligi_mi(title):
            parts = title.split(" - ")
            if len(parts) >= 2:
                court_part = clean_text(parts[1].split("(")[0])

        group_key = None
        # 1. Barkod varsa tekil anahtar KESİNLİKLE barkoddur! Farklı barkodlar ASLA birleştirilemez!
        if barcode:
            group_key = f"BAR_{barcode}"
        elif k.get("uets_no"):
            group_key = f"UETS_{k['uets_no']}"
        # 2. Barkod yoksa aynı dosya ve aynı son gün tarihi eşleşiyorsa mükerrerdir:
        elif esas_no and court_part:
            m_due = re.search(r"\(Son Gün:[^\)]*\)", title)
            due_str = m_due.group(0) if m_due else ((t.get("dueDate") or "")[:10])
            if due_str:
                group_key = f"CASE_{court_part}_{esas_no}_{due_str}"
        elif esas_no:
            m_due = re.search(r"\(Son Gün:[^\)]*\)", title)
            due_str = m_due.group(0) if m_due else ((t.get("dueDate") or "")[:10])
            if due_str:
                group_key = f"ESAS_{esas_no}_{due_str}_{t.get('projectId')}"
            
        if group_key:
            groups.setdefault(group_key, []).append(t)
            
    for g_key, dup_list in groups.items():
        if len(dup_list) <= 1:
            continue
            
        def score(x):
            cnt = x.get("content") or ""
            s = x.get("startDate") or ""
            sc = 0
            if x.get("childIds"):
                sc += 100000   # alt görevleri olan kopya ANA görev olur (alt görevler kaybolmasın)
            if "![file]" in cnt:
                sc += 5000
            if x.get("parentId"):
                sc += 500
            if s and ("2025" in s or "2026" in s) and not ("2003" in s or "2024" in s):
                sc += 300
            if x.get("projectId") != "inbox" and not str(x.get("projectId", "")).startswith("inbox"):
                sc += 400
            sc += len(cnt)
            return sc
            
        dup_list.sort(key=score, reverse=True)
        master = dup_list[0]
        duplicates = dup_list[1:]
        # KULLANICI BAŞLIĞI KAZANIR: kopyalardan birini kullanıcı yeniden adlandırdıysa (standart biçim dışı),
        # kalan görev o başlığı alır. Birden çoksa en son değiştirileni.
        ozel = [x for x in dup_list if kimlik.kullanici_basligi_mi(x.get("title"))]
        ozel_baslik = None
        if ozel:
            ozel.sort(key=lambda x: x.get("modifiedTime") or "", reverse=True)
            ozel_baslik = ozel[0].get("title")
        
        master_content = master.get("content") or ""
        master_tags = list(master.get("tags") or [])
        extra_lines = []
        
        for d in duplicates:
            d_content = d.get("content") or ""
            for tg in d.get("tags") or []:
                if tg not in master_tags:
                    master_tags.append(tg)
                    
            if not master.get("parentId") and d.get("parentId") and d.get("projectId") == master.get("projectId"):
                master["parentId"] = d["parentId"]
                master["_ust_kopyadan"] = True

            for line in d_content.splitlines():
                l_str = line.strip()
                if l_str and "YENİ ELEKTRONİK TEBLİGAT" not in l_str and not kimlik.var_mi(l_str) and \
                   "- **Merci:**" not in l_str and "- **Barkod:**" not in l_str and \
                   "### YAPILACAK İŞLEM" not in l_str and l_str not in master_content:
                    extra_lines.append(l_str)
                    
            if d.get("childIds"):
                print(f"   🛡️ Mükerrer silinmedi (alt görevleri var): {(d.get('title') or '')[:60]}")
                continue
            try:
                del_url = f"{CONFIG['TICKTICK_API_BASE']}/project/{d['projectId']}/task/{d['id']}"
                del_resp = requests.delete(del_url, headers=get_ticktick_headers(), timeout=8)
                if del_resp.status_code == 200:
                    silinen += 1
            except Exception as e:
                print(f"Silme hatası ({d['id']}): {e}")
                
        if extra_lines:
            master_content += "\n\n📌 **BİRLEŞTİRİLEN EK NOTLAR (Mükerrer Görevden):**\n" + "\n".join(extra_lines)
            
        is_tebligat = (master.get("title") or "").startswith("📨") or "TEBLİGAT" in (master.get("title") or "").upper()
        master_tags = normalize_tags(master_tags, is_uets=True if is_tebligat else False)
        if not is_tebligat:
            master_tags = [tg for tg in master_tags if tg != "uets"]
            
        try:
            up_url = f"{CONFIG['TICKTICK_API_BASE']}/task/{master['id']}"
            update_payload = {
                "id": master["id"],
                "projectId": master["projectId"],
                "content": master_content,
                "tags": master_tags
            }
            if master.get("parentId") and master.get("_ust_kopyadan"):
                update_payload["parentId"] = master["parentId"]
            m_title = master.get("title") or ""
            if ozel_baslik and ozel_baslik != m_title:
                update_payload["title"] = ozel_baslik
                print(f"   ✏️ Kullanıcı başlığı korundu: {ozel_baslik[:60]}")
            elif ("Son Gün: 26)" in m_title or "(Son Gün: 26.10)" in m_title) and not kimlik.kullanici_basligi_mi(m_title):
                m_fixed = re.sub(r"\(Son Gün:[^\)]*\)", "", m_title).strip()
                m_due14 = re.search(r"14 Günlük Süre Sonu:\*\*?\s*([^\s\(]+)", master_content)
                m_due7 = re.search(r"7 Günlük Süre Sonu:\*\*?\s*([^\s\(]+)", master_content)
                is_short = any(k in m_fixed.lower() for k in ["icra", "ceza", "soruşturma"])
                date_to_use = (m_due7.group(1) if is_short and m_due7 else None) or (m_due14.group(1) if m_due14 else None)
                if date_to_use:
                    m_fixed += f" (Son Gün: {date_to_use})"
                update_payload["title"] = m_fixed
                
            requests.post(up_url, headers=get_ticktick_headers(), json=update_payload, timeout=8)
            birlestirilen += 1
        except Exception:
            pass
            
    try:
        d_b, d_s = durusma_mukerrerlerini_birlestir()
        birlestirilen += d_b
        silinen += d_s
    except Exception as e:
        print(f"⚠️ Duruşma mükerrer kontrolü yapılamadı: {e}")
    print(f"✅ Mükerrer temizlik tamamlandı: {birlestirilen} grup birleştirildi, {silinen} fazla kopya silindi.")
    return birlestirilen, silinen

def clean_completed_duplicates(max_passes=5):
    """
    Tamamlanmış görevler arasındaki mükerrer tebligat, duruşma ve aynı gün tamamlanan mükerrer görevleri temizler.
    """
    print("\n🧹 TickTick tamamlanmış görevler mükerrer taraması ve temizliği başlıyor...")
    headers = get_ticktick_headers()
    base = CONFIG["TICKTICK_API_BASE"]
    
    def normalize_date(d_str):
        if not d_str: return ""
        m = re.search(r"(\d{2})[./](\d{2})[./](\d{4})", d_str)
        if m:
            return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        m2 = re.search(r"(\d{4})-(\d{2})-(\d{2})", d_str)
        if m2:
            return m2.group(0)
        return ""

    total_deleted = 0
    
    for pass_num in range(1, max_passes + 1):
        try:
            r = requests.post(f"{base}/task/completed", headers=headers, json={}, timeout=15)
            if r.status_code != 200:
                break
            tasks = r.json()
        except Exception as e:
            print(f"⚠️ Tamamlanmış görevler çekilemedi: {e}")
            break
            
        to_delete = []
        seen_ids = set()
        
        # 1. Tebligat Mükerrerleri
        teb_groups = {}
        for t in tasks:
            title = t.get("title") or ""
            cnt = t.get("content") or ""
            tags = t.get("tags") or []
            if not ("📨" in title or "TEBLİGAT" in title.upper() or "uets" in tags):
                continue
            esas = extract_esas_from_text(title) or extract_esas_from_text(cnt)
            bar = extract_barcode_from_text(cnt) or extract_barcode_from_text(title)
            court = ""
            if " - " in title:
                parts = title.split(" - ")
                if len(parts) >= 2:
                    court = clean_text(parts[1].split("(")[0])
            m_due = re.search(r"\(Son Gün:[^\)]*\)", title)
            due_str = m_due.group(0) if m_due else ((t.get("dueDate") or "")[:10])
            # Barkod varsa KESİNLİKLE barkoda göre grupla; farklı barkodları asla birleştirme!
            key = f"BAR_{bar}" if bar else (f"{court}_{esas}_{due_str}" if (esas and court and due_str) else None)
            if key:
                teb_groups.setdefault(key, []).append(t)
                
        for k, group in teb_groups.items():
            if len(group) > 1:
                def score(x):
                    sc = 0
                    c = x.get("content") or ""
                    if "![file]" in c: sc += 10000
                    if x.get("parentId"): sc += 500
                    sc += len(c)
                    return sc
                group.sort(key=score, reverse=True)
                master = group[0]
                for dup in group[1:]:
                    if dup["id"] not in seen_ids:
                        seen_ids.add(dup["id"])
                        to_delete.append((dup, master, f"Tebligat mükerreri ({k})"))
                        
        # 2. Duruşma Mükerrerleri
        hearing_groups = {}
        for t in tasks:
            title = t.get("title") or ""
            if not ("#DURUŞMA" in title.upper() or "DURUŞMA" in title.upper() or "⚖️" in title):
                continue
            esas = extract_esas_from_text(title)
            court = ""
            if " - " in title:
                parts = title.split(" - ")
                if len(parts) >= 2:
                    court = clean_text(parts[1].split("(")[0])
            h_date = normalize_date(title) or normalize_date(t.get("dueDate") or "") or normalize_date(t.get("startDate") or "")
            if esas and court and h_date:
                key = f"{court}_{esas}_{h_date}"
                hearing_groups.setdefault(key, []).append(t)
                
        for k, group in hearing_groups.items():
            if len(group) > 1:
                def score(x):
                    sc = 0
                    tit = x.get("title") or ""
                    if re.search(r"\d{2}:\d{2}", tit): sc += 500
                    if x.get("parentId"): sc += 200
                    sc += len(x.get("content") or "")
                    return sc
                group.sort(key=score, reverse=True)
                master = group[0]
                for dup in group[1:]:
                    if dup["id"] not in seen_ids:
                        seen_ids.add(dup["id"])
                        to_delete.append((dup, master, f"Duruşma mükerreri ({k})"))
                        
        # 3. Aynı projede aynı gün tamamlanan birebir aynı görevler
        identical_groups = {}
        for t in tasks:
            if t["id"] in seen_ids:
                continue
            title = (t.get("title") or "").strip().lower()
            if not title or title in ["alışveriş", "ödenecek", "google gemini 359,99"]:
                continue
            pid = t.get("projectId") or ""
            c_time = (t.get("completedTime") or "")[:10]
            key = f"{pid}_{title}_{c_time}"
            identical_groups.setdefault(key, []).append(t)
            
        for k, group in identical_groups.items():
            if len(group) > 1:
                group.sort(key=lambda x: (len(x.get("content") or ""), 1 if x.get("parentId") else 0), reverse=True)
                master = group[0]
                for dup in group[1:]:
                    if dup["id"] not in seen_ids:
                        seen_ids.add(dup["id"])
                        to_delete.append((dup, master, f"Aynı gün mükerrer ({k[:40]})"))
                        
        if not to_delete:
            break
            
        silinecek_var = False
        for dup, master, reason in to_delete:
            d_pid = dup.get("projectId")
            d_id = dup.get("id")
            if dup.get("childIds"):
                # Alt görevi olan görev silinirse alt görevleri de gider: ASLA silinmez.
                print(f"   🛡️ Silinmedi (alt görevleri var): \"{(dup.get('title') or '')[:50]}\"")
                continue
            silinecek_var = True
            try:
                del_r = requests.delete(f"{base}/project/{d_pid}/task/{d_id}", headers=headers, timeout=8)
                if del_r.status_code == 200:
                    print(f"   🗑️ Silindi (Tamamlanmış Mükerrer): \"{dup.get('title')[:50]}\" ({reason})")
                    total_deleted += 1
            except Exception as e:
                print(f"   ⚠️ Silme hatası ({d_id}): {e}")
            time.sleep(0.15)
            
    print(f"✅ Tamamlanmış mükerrer temizliği bitti: Toplam {total_deleted} gereksiz kopya silindi.")
    return total_deleted

def audit_and_heal_all_tasks():
    """
    TickTick'teki tüm aktif tebligat görevlerini denetler ve otomatik iyileştirir:
    1. Parent kartı eksik olan görevleri tespit edip üst dava kartını bulur ve bağlar.
    2. Hatalı etiketleri normalize eder (#atmacamadencilik -> #erolatmaca, #ardadogan -> #cmk_ardadogan vb.).
    3. Mükerrerleri birleştirip temizler.
    Dönüş olarak yapılan tüm düzeltmelerin raporunu verir.
    """
    print("\n🔍 TickTick Sağlık ve Bütünlük Denetimi (Audit & Self-Heal) Başlıyor...")
    healed_parents = []
    healed_tags = []
    
    all_projects = list(PROJECT_IDS.items())
    seen_pids = set()
    
    for pname, pid in all_projects:
        if pid in seen_pids:
            continue
        seen_pids.add(pid)
        tasks = get_project_tasks_live(pid, force_refresh=True)
        
        for t in tasks:
            title = t.get("title") or ""
            content = t.get("content") or ""
            tags = list(t.get("tags") or [])
            
            k = kimlik.oku(content)
            if k:
                is_durusma = k.get("tur") == "DURUŞMA"
                is_tebligat = k.get("tur") == "TEBLİGAT"
            else:
                is_durusma = "DURUŞMA" in title.upper() or "⚖️" in title
                is_tebligat = "TEBLİGAT" in title.upper() or "uets" in tags or "📨" in title
            
            if not is_durusma and not is_tebligat:
                continue
                
            parent_id = t.get("parentId")
            # Esas no ve mahkeme: önce kimlik satırı, sonra not (Merci/Dosya satırları), en son STANDART başlık.
            # Kullanıcının yeniden adlandırdığı başlıktan bilgi okunmaz.
            standart = not kimlik.kullanici_basligi_mi(title)
            m_esas = k.get("esas") or extract_esas_from_text(content) or (extract_esas_from_text(title) if standart else None)
            court = k.get("mahkeme") or ""
            if not court:
                m_merci = re.search(r"Merci:\**\s*([^\n]+)", content.replace("\\", ""))
                if m_merci:
                    court = m_merci.group(1).strip()
            if not court and standart and " - " in title:
                parts = title.split(" - ")
                if len(parts) >= 2:
                    court = parts[1].split("(")[0].strip()

            # 0. KİMLİK satırı yoksa ekle (başlık değişse de mahkeme/esas/barkod görevde kalsın)
            if not k and (m_esas or extract_barcode_from_text(content)):
                m_tarih = re.search(r"Duruşma Tarihi:\**\s*([0-9./]+)", content.replace("\\", ""))
                m_saat = re.search(r"Duruşma Saati:\**\s*([0-9:]+)", content.replace("\\", ""))
                yeni_k = kimlik.satir("DURUŞMA" if is_durusma else "TEBLİGAT", mahkeme=court, esas=m_esas or "",
                                      barkod="" if is_durusma else (extract_barcode_from_text(content) or ""),
                                      durusma=(f"{m_tarih.group(1)} {m_saat.group(1) if m_saat else ''}".strip() if (is_durusma and m_tarih) else ""))
                update_task_details(t["id"], pid, parent_id, content=kimlik.ekle(content, yeni_k))
                content = kimlik.ekle(content, yeni_k)
                print(f"   🔖 Kimlik satırı eklendi: {title[:50]}")
                    
            # 1. Parent Kontrolü ve Onarımı
            if not parent_id and m_esas:
                p_res = find_or_create_parent_task(court, m_esas, pid)
                p_id = p_res[0] if isinstance(p_res, (tuple, list)) else p_res
                target_pid = p_res[1] if isinstance(p_res, (tuple, list)) and len(p_res) > 1 else pid
                if p_id:
                    update_task_details(t["id"], target_pid, p_id)
                    parent_id = p_id
                    healed_parents.append(f"{court} [{m_esas}] -> Parent bağlandı")
                    print(f"   🔧 Parent Kartı Bağlandı: {title[:40]}")
                    
            # 2. Etiket Kontrolü ve Onarımı
            is_cmk_task = any("cmk" in tg.lower() for tg in tags) or any(k in title.lower() for k in ["ceza", "soruşturma"])
            if is_durusma:
                # Duruşma görevinden 'uets' KESİNLİKLE kaldırılır
                norm_tags = normalize_tags(tags, is_cmk=is_cmk_task, is_uets=False)
                norm_tags = [tg for tg in norm_tags if tg != "uets"]
            else:
                norm_tags = normalize_tags(tags, is_cmk=is_cmk_task, is_uets=True)
                
            if sorted(tags) != sorted(norm_tags):
                update_task_details(t["id"], pid, parent_id, tags=norm_tags)
                healed_tags.append(f"{title[:35]}: {tags} ➔ {norm_tags}")
                print(f"   🏷️ Etiket Düzeltildi: {tags} ➔ {norm_tags}")
                
            # 3. Saat Dilimi Onarımı (14:00 yerine 17:00, veya duruşma saati 06:xx/08:xx yerine tam saat)
            d_due = t.get("dueDate") or ""
            # TickTick tarihleri kullanıcı saat diliminde (+0300) döndürür. Eski sürüm yerel saati "+0000" ile yazdığı
            # için son gün 20:00+0300 görünüyordu; 14:00 (eski hata) ve 20:00 (saat dilimi hatası) 17:00'ye çekilir.
            if is_tebligat and d_due and re.search(r"T(14|20):00:00\+0300$", d_due):
                fixed_due = re.sub(r"T(14|20):00:00\+0300$", "T17:00:00+0300", d_due)
                update_task_details(t["id"], pid, parent_id, due_iso=fixed_due)
            elif is_durusma and "Saat:" in title:
                m_saat = re.search(r"Saat:\s*(\d{2}:\d{2})", title)
                if m_saat and d_due:
                    exact_time = m_saat.group(1)
                    date_part = d_due.split("T")[0]
                    fixed_hearing_iso = f"{date_part}T{exact_time}:00+0300"
                    if not d_due.startswith(f"{date_part}T{exact_time}:00"):
                        update_task_details(t["id"], pid, parent_id, start_iso=fixed_hearing_iso, due_iso=fixed_hearing_iso)
                
    # 3. Mükerrer Temizliği (Aktif ve Tamamlanmış)
    merged_cnt, deleted_cnt = clean_and_merge_duplicates()
    completed_deleted = clean_completed_duplicates()
    
    return {
        "healed_parents": healed_parents,
        "healed_tags": healed_tags,
        "merged_duplicates": merged_cnt,
        "deleted_duplicates": deleted_cnt + completed_deleted
    }
