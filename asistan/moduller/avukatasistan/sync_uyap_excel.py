#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚖️ UYAP EXCEL (DOSYALAR.XLSX) OTOMATİK SENKRONİZASYON MOTORU
UYAP'tan indirilen dosya listesini (dosyalar.xlsx) okur, Notion veritabanı ("Tüm Dosyalar Düzenli")
ve TickTick ile tam senkronize eder.

Özellikler:
1. UYAP çoklu satır formatını (Birim, Dosya No, Taraflar, Durum, Açılış Tarihi) hatasız ayrıştırır.
2. Notion'daki mevcut dosyaları karşılaştırır:
   - Kapanan / durumu değişen dosyaların (Açık -> Kapalı vb.) durumunu Notion'da günceller.
   - Notion'da olmayan yeni dosyaları otomatik oluşturur (Mahkeme Türü, Açılış Tarihi, Durum).
3. Müvekkiller veritabanı (312+ müvekkil) ile tarafları eşleştirip dosyayı ilgili müvekkile bağlar.
4. TickTick'te aktif dosyaların Ana Dava Kartlarını (Parent Task) oluşturur; kapananları arşivler.
5. Varsayılan olarak '--dry-run' (önizleme) modunda çalışır; '--apply' ile canlı uygular.
"""

import os
import sys
import re
import argparse
import time
from datetime import datetime
import openpyxl
import requests

from config import CONFIG, PROJECT_IDS
from utils import clean_text, normalize_tr, resolve_client_tag, determine_list, is_excluded
from notion_sync import get_notion_headers
from ticktick_sync import get_ticktick_headers, get_project_tasks_live, is_case_card, find_or_create_parent_task
import baglanti


class NotionOkumaHatasi(baglanti.BaglantiHatasi):
    """Notion listesi tam okunamadı: yarım listeyle dosyalar "yeni" sanılıp Notion'da KOPYASI açılmasın."""

# Mahkeme adı -> Notion 'DOSYA TÜRÜ' select seçeneği eşleme tablosu
NOTION_COURT_TYPES = [
    'Ağır Ceza Mahkemesi', 'Aile Mahkemesi', 'Arabuluculuk', 'Asliye Ceza Mahkemesi',
    'Asliye Hukuk Mahkemesi', 'Asliye Ticaret Mahkemesi', 'BAM Ceza', 'BAM Hukuk',
    'BİLGİ NOTU', 'BİM İdare', 'BİM Vergi', 'Çocuk Mahkemesi', 'Danıştay',
    'Fikri ve Sınai Haklar Ceza', 'Fikri ve Sınai Haklar Hukuk', 'İcra Hukuk Mahkemesi',
    'İcra Takibi', 'İdare Mahkemesi', 'İş Mahkemesi', 'Kadastro Mahkemesi',
    'Soruşturma', 'Sulh Hukuk Mahkemesi', 'Tüketici Mahkemesi', 'Vergi Mahkemesi',
    'Yargıtay Hukuk', 'Yargıtay Ceza'
]

# UYAP Durumu -> Notion 'DURUM' select seçeneği eşleme tablosu
VALID_NOTION_STATUSES = [
    'Açık', 'Kapalı', 'Karara Çıkmış', 'Arşivde', 'İstinafta', 'İstinaftan Döndü',
    'İstinaftan Kısmi Döndü', 'Yargıtayda', 'Yargıtaydan Döndü', 'Danıştayda',
    'Bölge İdare Mahkemesinde', 'Açık (Durdurulmuş : Takibe İtiraz)',
    'Açık (Durdurulmuş : Diğer)', 'Açık (Durdurulmuş : Tehir-i İcra Kararı)',
    'Açık (Durdurulmuş : İcra Mahkemesine İtiraz)', 'bilgi notu yazıldı'
]

def map_court_to_notion_type(court_name):
    """Mahkeme isminden Notion DOSYA TÜRÜ değerini tespit eder."""
    c = normalize_tr(court_name)
    if "fikri ve sınai" in c or "fshm" in c:
        return "Fikri ve Sınai Haklar Ceza" if "ceza" in c else "Fikri ve Sınai Haklar Hukuk"
    if "bölge adliye" in c or "bam" in c:
        return "BAM Ceza" if "ceza" in c else "BAM Hukuk"
    if "yargıtay" in c:
        return "Yargıtay Ceza" if "ceza" in c else "Yargıtay Hukuk"
    if "danıştay" in c:
        return "Danıştay"
    if "bölge idare" in c or "bim" in c or "idari dava" in c or "vergi dava" in c:
        return "BİM Vergi" if "vergi" in c else "BİM İdare"
    if "çocuk" in c:
        return "Çocuk Mahkemesi"
    if "ağır ceza" in c or "infaz" in c or "agir ceza" in c:
        return "Ağır Ceza Mahkemesi"
    if "asliye ceza" in c or "sulh ceza" in c:
        return "Asliye Ceza Mahkemesi"
    if "asliye ticaret" in c:
        return "Asliye Ticaret Mahkemesi"
    if "asliye hukuk" in c:
        return "Asliye Hukuk Mahkemesi"
    if "iş mahkemesi" in c or "is mahkemesi" in c:
        return "İş Mahkemesi"
    if "aile" in c:
        return "Aile Mahkemesi"
    if "tüketici" in c:
        return "Tüketici Mahkemesi"
    if "sulh hukuk" in c:
        return "Sulh Hukuk Mahkemesi"
    if "icra hukuk" in c:
        return "İcra Hukuk Mahkemesi"
    if "icra" in c:
        return "İcra Takibi"
    if "idare" in c:
        return "İdare Mahkemesi"
    if "vergi" in c:
        return "Vergi Mahkemesi"
    if "kadastro" in c:
        return "Kadastro Mahkemesi"
    if "arabuluculuk" in c:
        return "Arabuluculuk"
    if any(k in c for k in ["soruşturma", "sorusturma", "savcı", "savci", "savcılık", "savciligi", "hazırlık", "hazirlik", "başsavcılık", "bassavcilik", "c.başsavcılığı", "c.bassavciligi"]):
        return "Soruşturma"
    return "Asliye Ceza Mahkemesi"

def normalize_uyap_status(status_str):
    """UYAP durum metnini Notion DURUM seçenekleriyle eşleştirir."""
    if not status_str:
        return None
    s = str(status_str).strip()
    if s.startswith("Kapalı"):
        return "Kapalı"
    if s in VALID_NOTION_STATUSES:
        return s
    # Yakın eşleşmeler
    for v in VALID_NOTION_STATUSES:
        if v.lower() == s.lower():
            return v
    return None

def extract_party_name(party_line):
    """'1. Sanık:EROL ATAŞ' formatından 'EROL ATAŞ' adını ayıklar."""
    if not party_line:
        return ""
    if ":" in party_line:
        return party_line.split(":", 1)[1].strip()
    return re.sub(r"^\d+\.\s*", "", party_line).strip()

def parse_uyap_excel(file_path):
    """
    UYAP Excel dosyasını (dosyalar.xlsx) okur.
    Birim/Dosya No ilk satırda yer alırken alt satırlardaki tarafları tek dosya altında toplar.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Excel dosyası bulunamadı: {file_path}")

    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active

    cases = []
    current_case = None

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        no, birim, dosya_no, taraf, tur, durum, acilis = (row + (None,)*7)[:7]
        
        if birim and dosya_no:
            if current_case:
                cases.append(current_case)
            
            # Açılış tarihi formatlama (DD.MM.YYYY -> YYYY-MM-DD)
            iso_date = None
            if acilis:
                try:
                    iso_date = datetime.strptime(str(acilis).strip(), "%d.%m.%Y").strftime("%Y-%m-%d")
                except Exception:
                    pass

            current_case = {
                "no": str(no).strip() if no else "",
                "birim": str(birim).strip(),
                "dosya_no": str(dosya_no).strip(),
                "taraflar": [str(taraf).strip()] if taraf else [],
                "tur": str(tur).strip() if tur else "",
                "raw_durum": str(durum).strip() if durum else "",
                "durum": normalize_uyap_status(durum),
                "acilis_str": str(acilis).strip() if acilis else "",
                "acilis_iso": iso_date
            }
        else:
            if current_case and taraf:
                current_case["taraflar"].append(str(taraf).strip())

    if current_case:
        cases.append(current_case)

    return cases

def fetch_all_notion_clients():
    """Notion 'Müvekkiller' veritabanındaki tüm müvekkilleri çeker."""
    url = f"{CONFIG['NOTION_API_BASE']}/databases/3bfff354-1194-80f7-b3d6-d62a4c69459d/query"
    headers = get_notion_headers()
    clients = {}
    has_more = True
    cursor = None

    while has_more:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        # Yarım liste kullanılmaz: sayfa okunamazsa (bağlantı) bekleyip devam eder, olmazsa NotionOkumaHatasi.
        if True:
            r = baglanti.oku("POST", url, headers, json_body=payload, timeout=15, ne="Notion müvekkil listesi",
                             hata_sinifi=NotionOkumaHatasi, kabul=(200,)).json()
            for p in r.get("results", []):
                t_objs = p.get("properties", {}).get("Name", {}).get("title", [])
                name = t_objs[0].get("plain_text", "") if t_objs else ""
                vk = (p.get("properties", {}).get("Vekalet İlişkisi", {}).get("select") or {}).get("name") or ""
                if name:
                    c_clean = clean_text(name)
                    clients[c_clean] = {
                        "id": p["id"],
                        "name": name,
                        "vekalet": vk,
                        "is_cmk": "cmk" in vk.lower()
                    }
            has_more = r.get("has_more", False)
            cursor = r.get("next_cursor")

    return clients

def fetch_all_notion_pages():
    """Notion 'Tüm Dosyalar Düzenli' veritabanındaki TÜM sayfaları çeker (arşivdekiler dahil)."""
    url = f"{CONFIG['NOTION_API_BASE']}/databases/{CONFIG['NOTION_DB_DOSYALAR']}/query"
    headers = get_notion_headers()
    pages = []
    has_more = True
    cursor = None

    while has_more:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        if True:
            r = baglanti.oku("POST", url, headers, json_body=payload, timeout=20, ne="Notion dosya listesi",
                             hata_sinifi=NotionOkumaHatasi, kabul=(200,)).json()
            for p in r.get("results", []):
                props = p.get("properties", {})
                t_objs = props.get("NOTION DOSYA", {}).get("title", [])
                title = t_objs[0].get("plain_text", "") if t_objs else ""
                durum = (props.get("DURUM", {}).get("select") or {}).get("name") or ""
                tur = (props.get("DOSYA TÜRÜ", {}).get("select") or {}).get("name") or ""
                muv_rels = props.get("MÜVEKKİLLER", {}).get("relation", [])
                
                parts = title.split(" - ")
                esas = parts[-1].strip() if len(parts) > 1 else ""
                court = parts[0].strip() if len(parts) > 1 else ""

                pages.append({
                    "id": p["id"],
                    "url": p.get("url", ""),
                    "title": title,
                    "court": court,
                    "esas_no": esas,
                    "durum": durum,
                    "tur": tur,
                    "client_rel_count": len(muv_rels)
                })
            has_more = r.get("has_more", False)
            cursor = r.get("next_cursor")

    return pages

def find_matched_client_for_case(case_parties, clients_db):
    """Dosyadaki taraf listesinden Müvekkiller veritabanındaki kişiyi tespit eder.
    Önce TÜM taraflarda birebir eşleşme aranır; kısmi eşleşme yalnızca uzun (15+ karakter, genelde şirket) adlarda
    yapılır. Eskiden kısa adlarda da kısmi eşleşiyordu: "MURAT GÜL" müvekkili karşı taraftaki "MURAT GÜLER"e
    bağlanabiliyor, ilk tarafın kısmi eşleşmesi sonraki tarafın birebir eşleşmesinin önüne geçiyordu."""
    adlar = [clean_text(extract_party_name(t)) for t in case_parties]
    for cl_p in adlar:
        if cl_p in clients_db:
            return clients_db[cl_p]
    for cl_p in adlar:
        if len(cl_p) < 15:
            continue
        for k, cl_obj in clients_db.items():
            if len(k) >= 15 and (k in cl_p or cl_p in k):
                return cl_obj
    return None

def update_notion_status(page_id, new_status):
    """Notion'daki bir dosyanın 'DURUM' sütununu günceller."""
    url = f"{CONFIG['NOTION_API_BASE']}/pages/{page_id}"
    payload = {
        "properties": {
            "DURUM": {"select": {"name": new_status}}
        }
    }
    # Aynı durumu iki kez yazmak zararsız: bağlantı koparsa bekleyip tekrar gönderilir.
    r, _ = baglanti.yaz("PATCH", url, get_notion_headers(), json_body=payload, timeout=10, ne="Notion durum güncelleme",
                        anahtar=f"{page_id} -> {new_status}")
    return bool(r is not None and r.status_code == 200)

def create_notion_case(birim, dosya_no, court_type, durum, acilis_iso, client_id=None):
    """Notion 'Tüm Dosyalar Düzenli' veritabanına yeni dosya kartı açar."""
    url = f"{CONFIG['NOTION_API_BASE']}/pages"
    title = f"{birim} - {dosya_no}"
    
    props = {
        "NOTION DOSYA": {
            "title": [{"text": {"content": title}}]
        },
        "DOSYA TÜRÜ": {
            "select": {"name": court_type}
        }
    }
    
    if durum:
        props["DURUM"] = {"select": {"name": durum}}
        
    if acilis_iso:
        props["AÇILIŞ TARİHİ"] = {"date": {"start": acilis_iso}}
        
    if client_id:
        props["MÜVEKKİLLER"] = {"relation": [{"id": client_id}]}
        
    payload = {
        "parent": {"database_id": CONFIG["NOTION_DB_DOSYALAR"]},
        "properties": props
    }
    
    # Yanıt kaybolursa önce "bu başlıkla sayfa oluşmuş mu?" bakılır; oluşmuşsa tekrar AÇILMAZ (kopya olmaz).
    r, var = baglanti.yaz("POST", url, get_notion_headers(), json_body=payload, timeout=12, ne="Notion dosya oluşturma",
                          olusturma=True, dogrula=lambda: notion_sayfa_bul(title), anahtar=title)
    if var is not None:
        return var
    if r is not None and r.status_code == 200:
        return r.json()
    if r is not None:
        print(f"⚠️ Notion dosya oluşturma hatası: {r.status_code} - {r.text[:200]}")
    return None


def notion_sayfa_bul(baslik):
    """Dosyalar veritabanında bu başlıkta (arşivlenmemiş) sayfa varsa döndürür."""
    url = f"{CONFIG['NOTION_API_BASE']}/databases/{CONFIG['NOTION_DB_DOSYALAR']}/query"
    r = baglanti.oku("POST", url, get_notion_headers(), timeout=15, ne="Notion sayfa kontrolü", hata_sinifi=NotionOkumaHatasi,
                     json_body={"page_size": 5, "filter": {"property": "NOTION DOSYA", "title": {"equals": baslik}}}, kabul=(200,))
    sonuc = (r.json() or {}).get("results") or []
    return sonuc[0] if sonuc else None

def acik_alt_isler(project_id, task_id):
    """Kartın altındaki AÇIK alt görevlerin başlıkları (iç içe, en çok 4 kat). Kart kapanırsa bunlar gözden kaybolur."""
    from ticktick_sync import gorev_getir
    acik, bak = [], [(task_id, 0)]
    gorulen = set()
    while bak:
        tid, kat = bak.pop()
        if tid in gorulen or kat > 4:
            continue
        gorulen.add(tid)
        t = gorev_getir(project_id, tid)
        if not t:
            continue
        if kat > 0 and t.get("status", 0) == 0:
            acik.append(t.get("title") or "(başlıksız)")
        for c in t.get("childIds") or []:
            bak.append((c, kat + 1))
    return acik


def complete_ticktick_parent_task(project_id, task_id):
    """TickTick'te kapanmış bir dosya kartını 'Tamamlandı' (status=2) olarak kapatır."""
    url = f"{CONFIG['TICKTICK_API_BASE']}/project/{project_id}/task/{task_id}/complete"
    r, _ = baglanti.yaz("POST", url, get_ticktick_headers(), json_body={}, timeout=10, ne="TickTick kart kapatma",
                        anahtar=task_id)
    return bool(r is not None and r.status_code == 200)

def _telegram(metin):
    try:
        from main import send_telegram_alert
        send_telegram_alert(metin[:3800])
    except Exception:
        pass


def _defter_bildirimleri(defter, d_sonuc):
    """Liste değişiklik özeti ve YENİ olası çıkar çatışmaları Telegram'a (aynı uyarı ikinci kez gitmez)."""
    if d_sonuc and not d_sonuc.get("atlandi") and (d_sonuc["yeni"] or d_sonuc["durum_degisen"] or d_sonuc["listeden_cikan"]):
        # İlk aktarımda bütün dosyalar "yeni" görünür: yalnızca sayı bildirilir
        if d_sonuc["yeni"] and len(d_sonuc["yeni"]) == d_sonuc["toplam"]:
            _telegram(f"📚 Dosya defteri ilk kez oluşturuldu: {d_sonuc['toplam']} dosya kaydedildi.")
        else:
            _telegram(defter.ozet_metni(d_sonuc))
    try:
        yeni = []
        for c in defter.catismalar():
            metin = f"{c['dosya']} ({c['durum'] or '—'}): " + "; ".join(c["a_taraf"]) + "  ⟷  " + "; ".join(c["b_taraf"])
            if defter.uyari_yeni_mi("catisma:" + c["dosya"], metin):
                yeni.append(metin)
        if yeni:
            print("\n⚠️ OLASI ÇIKAR ÇATIŞMASI (aynı dosyada karşı karşıya taraflarda müvekkillerimiz):")
            for y in yeni:
                print("   • " + y)
            _telegram("⚠️ OLASI ÇIKAR ÇATIŞMASI — aynı dosyada karşı karşıya taraflarda müvekkillerimiz:\n" +
                      "\n".join("• " + y for y in yeni[:15]))
    except Exception as e:
        print(f"⚠️ Çatışma kontrolü yapılamadı: {e}")


def run_sync(excel_path=None, apply=False, mod=None):
    """Senkronizasyon işlemini başlatır.
    mod: "onizleme" (Notion/TickTick'e dokunmaz), "guvenli" (durum güncelle + yeni dosya + yeni kart; KART KAPATMAZ),
         "tam" (hepsi; kart kapatma yalnızca altında açık iş olmayan kartlar için). apply=True eski çağrılar için "tam".
    Her modda liste yerel DOSYA DEFTERİNE işlenir (defter.py). Döner: özet sözlüğü."""
    mod = mod or ("tam" if apply else "onizleme")
    apply = mod in ("guvenli", "tam")
    ozet_sonuc = {"mod": mod, "defter": None, "durum_guncellenen": 0, "yeni_notion": 0, "kart_bekleyen": []}
    import glob
    if not excel_path or not os.path.exists(excel_path):
        # Otomatik olarak en güncel dosyalar*.xlsx dosyasını bul
        search_patterns = [
            "/sdcard/Download/Quick Share/dosyalar*.xlsx",
            "/sdcard/Download/dosyalar*.xlsx",
            "/sdcard/download/Quick Share/dosyalar*.xlsx",
            "/sdcard/download/dosyalar*.xlsx",
            os.path.expanduser("~/Downloads/dosyalar*.xlsx")
        ]
        found_files = []
        for pat in search_patterns:
            found_files.extend(glob.glob(pat))
        
        if found_files:
            # En son değiştirilme tarihine göre sırala
            found_files.sort(key=os.path.getmtime, reverse=True)
            excel_path = found_files[0]
                
    if not excel_path or not os.path.exists(excel_path):
        print(f"❌ HATA: UYAP 'dosyalar.xlsx' dosyası bulunamadı!")
        print("   Lütfen UYAP'tan indirdiğiniz dosyanın tablet üzerinde '/sdcard/Download/dosyalar.xlsx'")
        print("   veya 'Quick Share' klasöründe olduğundan emin olun.")
        return ozet_sonuc

    print("=" * 70)
    print("⚖️  UYAP EXCEL (DOSYALAR.XLSX) SENKRONİZASYON MOTORU")
    print("=" * 70)
    print(f"📁 Kaynak Excel: {excel_path}")
    mode_str = {"tam": "🚀 CANLI UYGULAMA (Notion ve TickTick değişir)",
                "guvenli": "🛡️ GÜVENLİ UYGULAMA (durum + yeni dosya + yeni kart; kart kapatılmaz)",
                "onizleme": "🔍 ÖNİZLEME (Notion/TickTick'e dokunulmaz; yalnızca yerel dosya defteri güncellenir)"}[mod]
    print(f"⚙️  Çalışma Modu: {mode_str}")
    print("=" * 70)

    # 1. Excel dosyasını ayrıştır
    print("\n[1/4] 📄 Excel Dosyası Okunuyor...")
    excel_cases = parse_uyap_excel(excel_path)
    print(f"   ↳ {len(excel_cases)} adet dosya kaydı başarıyla ayrıştırıldı.")

    # 2. Notion Müvekkiller ve Dosyalar listesini çek
    print("\n[2/4] 🔄 Notion Veritabanları Çekiliyor...")
    clients_db = fetch_all_notion_clients()
    print(f"   ↳ {len(clients_db)} adet kayıtlı müvekkil yüklendi.")
    notion_pages = fetch_all_notion_pages()
    print(f"   ↳ {len(notion_pages)} adet mevcut Notion dosya kartı yüklendi.")

    # 2.5 Yerel DOSYA DEFTERİ: tüm dosyalar, taraflar, durum geçmişi (müvekkil Notion eşleşmesinden)
    try:
        import defter
        def _muv(taraf_satirlari):
            m = find_matched_client_for_case(taraf_satirlari, clients_db) if clients_db else None
            return {"name": m["name"], "tag": resolve_client_tag(m["name"], is_cmk=m.get("is_cmk"))} if m else None
        d_sonuc = defter.liste_aktar(excel_cases, os.path.basename(excel_path), defter.dosya_ozeti(excel_path), _muv,
                                     muvekkil_adlari=[v["name"] for v in clients_db.values()])
        ozet_sonuc["defter"] = d_sonuc
        print("\n📚 Dosya defteri:\n" + defter.ozet_metni(d_sonuc))
        _defter_bildirimleri(defter, d_sonuc)
    except Exception as e_def:
        print(f"⚠️ Dosya defterine yazılamadı: {e_def}")

    # Notion indexleme
    notion_by_clean_title = {clean_text(p["title"]): p for p in notion_pages}
    notion_by_esas = {}
    for p in notion_pages:
        e = p["esas_no"]
        if e:
            if e not in notion_by_esas:
                notion_by_esas[e] = []
            notion_by_esas[e].append(p)

    # 3. Karşılaştırma ve Analiz
    print("\n[3/4] 🔍 Dosyalar ve Durumlar Karşılaştırılıyor...")
    to_update_status = []
    to_create_notion = []
    already_synced = 0

    for ec in excel_cases:
        expected_title = f"{ec['birim']} - {ec['dosya_no']}"
        cl_exp = clean_text(expected_title)
        
        # Notion'da var mı?
        found_page = None
        if cl_exp in notion_by_clean_title:
            found_page = notion_by_clean_title[cl_exp]
        elif ec["dosya_no"] in notion_by_esas:
            c_birim = clean_text(ec["birim"])
            for cand in notion_by_esas[ec["dosya_no"]]:
                c_cand = clean_text(cand["title"])
                if c_birim in c_cand or c_cand in c_birim:
                    found_page = cand
                    break
                    
        if found_page:
            # Durum değişikliği kontrolü
            e_durum = ec["durum"]
            n_durum = found_page["durum"]
            if e_durum and e_durum != n_durum:
                to_update_status.append({
                    "page_id": found_page["id"],
                    "title": found_page["title"],
                    "old_status": n_durum,
                    "new_status": e_durum,
                    "excel_raw_status": ec["raw_durum"]
                })
            else:
                already_synced += 1
        else:
            # Notion'da hiç yok! Yeni dosya
            m_client = find_matched_client_for_case(ec["taraflar"], clients_db)
            c_type = map_court_to_notion_type(ec["birim"])
            to_create_notion.append({
                "case": ec,
                "court_type": c_type,
                "matched_client": m_client
            })

    # GÜVENLİK: Notion dosya listesi okunamadıysa (anahtar/ağ hatası) her dosya "yeni" görünür; bu durumda
    # Notion'a YAZILMAZ (yüzlerce kopya dosya açılırdı). Eklenecek sayı olağandışı yüksekse (otomatik modda)
    # de yazılmaz; elle --uygula ile onaylanır.
    notion_yazma_engeli = None
    if not notion_pages:
        notion_yazma_engeli = "Notion dosya listesi okunamadı (0 kart)"
    elif mod == "guvenli" and len(to_create_notion) > max(20, len(excel_cases) // 5):
        notion_yazma_engeli = (f"{len(to_create_notion)} yeni dosya olağandışı çok (listenin %{100 * len(to_create_notion) // max(1, len(excel_cases))}'i); "
                               f"kontrol edip 'asistan uyap-liste --uygula' ile onaylayın")
    if notion_yazma_engeli:
        print(f"\n🛑 NOTION'A YAZILMAYACAK: {notion_yazma_engeli}.")
        ozet_sonuc["notion_engeli"] = notion_yazma_engeli
        if apply:
            _telegram(f"🛑 UYAP listesi: Notion'a yazılmadı — {notion_yazma_engeli}.")
    print(f"   ↳ ✅ Birebir Güncel: {already_synced} dosya")
    print(f"   ↳ 🔄 Durumu Güncellenecek: {len(to_update_status)} dosya")
    print(f"   ↳ ➕ Notion'a Yeni Eklenecek: {len(to_create_notion)} dosya")

    # 4. Detaylı Listeleme
    if to_update_status:
        print("\n" + "-" * 70)
        print("📋 DURUM GÜNCELLEMESİ YAPILACAK DOSYALAR:")
        print("-" * 70)
        for item in to_update_status:
            print(f"   • {item['title']}: '{item['old_status']}' ➡️ '{item['new_status']}'")

    if to_create_notion:
        print("\n" + "-" * 70)
        print("📋 NOTION'A YENİ EKLENECEK DOSYALAR:")
        print("-" * 70)
        for item in to_create_notion:
            c = item["case"]
            cl_name = item["matched_client"]["name"] if item["matched_client"] else "⚠️ Tespit Edilemedi"
            print(f"   • {c['birim']} - {c['dosya_no']}")
            print(f"     Tür: {item['court_type']} | Durum: {c['durum']} | Açılış: {c['acilis_str']} | Müvekkil: {cl_name}")

    # 5. TickTick Açık Dosya Kartları Analizi
    print("\n[4/4] ⏱️ TickTick Dosya Kartları Denetleniyor...")
    # Sadece 'Açık' durumdaki ve kara listede olmayan dosyalar için TickTick parent kartı açılır
    acik_excel_cases = [c for c in excel_cases if c["durum"] == "Açık" and not is_excluded(c["birim"] + " " + c["dosya_no"])]
    print(f"   ↳ Toplam Aktif (Açık) Dosya: {len(acik_excel_cases)}")

    # Tamamlanmış veya kapatılmış (status=2, -1) görevleri çek (Mükerrer açılmaması için)
    from ticktick_sync import get_completed_tasks_live, clean_and_merge_duplicates
    completed_tt_tasks = get_completed_tasks_live()

    # TickTick'teki eksik parent kartları tespit et
    tt_missing_parents = []
    for ec in acik_excel_cases:
        m_client = find_matched_client_for_case(ec["taraflar"], clients_db)
        if m_client and is_excluded(m_client["name"]):
            continue

        c_tag = resolve_client_tag(m_client["name"], is_cmk=m_client["is_cmk"]) if m_client else ""
        if c_tag and is_excluded(c_tag):
            continue

        # Tamamlanmış görevlerde var mı kontrol et (status=2 veya status=-1)
        # Regex ile tam sınır kontrolü: '2026/38' -> '2026/3883' ile karışmaz!
        esas_pattern = rf"\b{re.escape(ec['dosya_no'])}(?:\s+Esas|\b)"
        is_already_in_completed = any(
            is_case_card(t) and re.search(esas_pattern, t.get("title") or "")
            for t in completed_tt_tasks
        )
        if is_already_in_completed:
            # Kullanıcı daha önce bu kartı kapatmış, yeniden açma!
            continue

        p_name = determine_list(ec["birim"])
        pid = PROJECT_IDS.get(p_name, "inbox")
        tasks = get_project_tasks_live(pid) if pid != "inbox" else []
        
        has_card = any(
            is_case_card(t) and re.search(esas_pattern, t.get("title") or "")
            for t in tasks
        )
        if not has_card:
            # Notion sayfa URL'sini bul
            cl_exp = clean_text(f"{ec['birim']} - {ec['dosya_no']}")
            n_page = notion_by_clean_title.get(cl_exp)
            n_url = n_page.get("url", "") if n_page else ""

            tt_missing_parents.append({
                "case": ec,
                "project_name": p_name,
                "project_id": pid,
                "client_tag": c_tag,
                "notion_url": n_url
            })

    print(f"   ↳ TickTick'te Kartı Eksik Aktif Dosyalar: {len(tt_missing_parents)}")
    if tt_missing_parents:
        print("\n" + "-" * 70)
        print("📋 TICKTICK'TE AÇILACAK ANA DAVA KARTLARI:")
        print("-" * 70)
        for item in tt_missing_parents:
            c = item["case"]
            print(f"   • [{item['project_name']}] {c['birim']} - {c['dosya_no']} (Etiket: {item['client_tag'] or 'Yok'})")

    # Kapanan dosyalar için TickTick'te hala açık kart var mı?
    tt_to_close = []
    closed_excel_cases = [item for item in to_update_status if item["new_status"] == "Kapalı"]
    for item in closed_excel_cases:
        parts = item["title"].split(" - ")
        c_esas = parts[-1].strip() if len(parts) > 1 else ""
        c_court = parts[0].strip() if len(parts) > 1 else ""
        if c_esas:
            p_name = determine_list(c_court)
            pid = PROJECT_IDS.get(p_name, "inbox")
            if pid != "inbox":
                tasks = get_project_tasks_live(pid)
                e_pat = rf"\b{re.escape(c_esas)}(?:\s+Esas|\b)"
                import kimlik
                for t in tasks:
                    k = kimlik.oku(t.get("content") or "")
                    kart_mi = (k.get("tur") == "DOSYA" and k.get("esas") == c_esas) or \
                              (not k and is_case_card(t) and re.search(e_pat, t.get("title") or ""))
                    if kart_mi:
                        tt_to_close.append({"task_id": t["id"], "title": t.get("title", ""), "project": p_name, "project_id": pid})

    # Altında AÇIK iş (tebligat, duruşma, kendi alt görevleriniz) olan kart KAPATILMAZ: kapanırsa bu işler gözden
    # kaybolur. Bunlar size raporlanır; işler bitince kart bir sonraki listede kapanır.
    kart_bekleyen = []
    for tc in list(tt_to_close):
        acik = acik_alt_isler(tc["project_id"], tc["task_id"])
        if acik:
            tc["acik"] = acik
            kart_bekleyen.append(tc)
            tt_to_close.remove(tc)
    if tt_to_close:
        print("\n" + "-" * 70)
        print("📋 TICKTICK'TE KAPATILACAK (TAMAMLANACAK) ANA DAVA KARTLARI:")
        print("-" * 70)
        for tc in tt_to_close:
            print(f"   • [{tc['project']}] {tc['title']}")
    ozet_sonuc["kart_bekleyen"] = kart_bekleyen
    if mod == "guvenli" and tt_to_close:
        print("\n🛡️ Güvenli mod: kart kapatma atlanıyor (onay için: asistan uyap-liste --uygula).")
        tt_to_close = []
    if kart_bekleyen:
        print("\n" + "-" * 70)
        print("⚠️ DOSYA KAPANDI AMA KARTIN ALTINDA AÇIK İŞ VAR (kart KAPATILMAYACAK, kontrol edin):")
        print("-" * 70)
        for tc in kart_bekleyen:
            print(f"   • [{tc['project']}] {tc['title']}: " + "; ".join(a[:50] for a in tc["acik"][:5]))

    # 6. Uygulama Aşaması (--apply)
    if not apply:
        print("\n" + "=" * 70)
        print("✨ ÖNİZLEME TAMAMLANDI!")
        print("Bu değişiklikleri Notion ve TickTick üzerinde CANLI uygulamak için:")
        print(f"   python3 asistan.py uyap-liste --uygula")
        print("=" * 70)
        return ozet_sonuc

    # CANLI UYGULAMA BAŞLIYOR
    print("\n" + "=" * 70)
    print("🚀 CANLI DEĞİŞİKLİKLER UYGULANIYOR...")
    print("=" * 70)

    if notion_yazma_engeli:
        to_update_status, to_create_notion = [], []
        tt_missing_parents = []   # Notion bağlantısı olmadan toplu kart açılmasın
        tt_to_close = []
    # A) Notion Durumlarını Güncelle
    if to_update_status:
        print(f"\n🔄 [1/4] Notion Durumları Güncelleniyor ({len(to_update_status)} dosya)...")
        updated_n = 0
        for item in to_update_status:
            ok = update_notion_status(item["page_id"], item["new_status"])
            if ok:
                updated_n += 1
                print(f"   ✅ Güncellendi: {item['title']} -> {item['new_status']}")
            else:
                print(f"   ❌ Başarısız: {item['title']}")
            time.sleep(0.2)
        print(f"   ↳ Toplam {updated_n}/{len(to_update_status)} durum güncellendi.")
        ozet_sonuc["durum_guncellenen"] = updated_n

    # B) Notion'a Yeni Dosyaları Ekle
    created_notion_map = {}
    if to_create_notion:
        print(f"\n➕ [2/4] Notion'a Yeni Dosyalar Ekleniyor ({len(to_create_notion)} dosya)...")
        created_n = 0
        for item in to_create_notion:
            c = item["case"]
            cl_id = item["matched_client"]["id"] if item["matched_client"] else None
            res = create_notion_case(
                birim=c["birim"],
                dosya_no=c["dosya_no"],
                court_type=item["court_type"],
                durum=c["durum"],
                acilis_iso=c["acilis_iso"],
                client_id=cl_id
            )
            if res:
                created_n += 1
                created_notion_map[f"{c['birim']} - {c['dosya_no']}"] = res.get("url", "")
                print(f"   ✅ Eklendi: {c['birim']} - {c['dosya_no']}")
            else:
                print(f"   ❌ Eklenemedi: {c['birim']} - {c['dosya_no']}")
            time.sleep(0.2)
        print(f"   ↳ Toplam {created_n}/{len(to_create_notion)} yeni dosya Notion'a kaydedildi.")
        ozet_sonuc["yeni_notion"] = created_n

    # C) TickTick'te Kapanan Dosyaların Kartlarını Kapat
    if tt_to_close:
        print(f"\n📁 [3/4] TickTick'te Kapanan Dosya Kartları Tamamlanıyor ({len(tt_to_close)} kart)...")
        closed_cnt = 0
        for tc in tt_to_close:
            ok = complete_ticktick_parent_task(tc["project_id"], tc["task_id"])
            if ok:
                closed_cnt += 1
                print(f"   ✅ Tamamlandı Olarak Kapatıldı: {tc['title']}")
            time.sleep(0.2)
        print(f"   ↳ Toplam {closed_cnt}/{len(tt_to_close)} dosya kartı kapatıldı.")

    # D) TickTick Parent Kartlarını Oluştur
    if tt_missing_parents:
        print(f"\n⏱️ [4/4] TickTick Ana Dava Kartları Açılıyor ({len(tt_missing_parents)} kart)...")
        created_tt = 0
        bulunan_tt = 0
        import ticktick_sync as _tts
        for item in tt_missing_parents:
            c = item["case"]
            pid = item["project_id"]
            if pid == "inbox":
                continue
            case_title = f"{c['birim']} - {c['dosya_no']}"
            n_url = item["notion_url"] or created_notion_map.get(case_title, "")
            parent_id, actual_pid = find_or_create_parent_task(
                court=c["birim"],
                esas_no=c["dosya_no"],
                project_id=pid,
                client_tag=item["client_tag"],
                notion_url=n_url
            )
            if parent_id and _tts.SON_KART_YENI:
                created_tt += 1
                print(f"   ✅ Kart Açıldı: [{item['project_name']}] {c['birim']} - {c['dosya_no']}")
            elif parent_id:
                # Ön kontrolde görünmeyen kart açmadan hemen önce yeniden okununca bulundu: kopya AÇILMADI.
                bulunan_tt += 1
                print(f"   ↪️ Kart zaten var (açılmadı): [{item['project_name']}] {c['birim']} - {c['dosya_no']}")
            else:
                print(f"   ❌ Kart açılamadı: [{item['project_name']}] {c['birim']} - {c['dosya_no']}")
            time.sleep(0.2)
        print(f"   ↳ Toplam {created_tt}/{len(tt_missing_parents)} dosya kartı TickTick'te açıldı"
              + (f", {bulunan_tt} kart zaten vardı." if bulunan_tt else "."))

    # E) Sistem Sağlığı ve Hiyerarşi İyileştirmesi (Audit & Heal)
    print("\n" + "-" * 70)
    print("🩺 Sistem Sağlık Denetimi & Hiyerarşi Eşitleme (Audit & Heal)...")
    try:
        # Tebligat/duruşma/dava kartı mükerrerleri, Notion'da aynı başlıklı sayfalar, yarım kalmış yazmalar
        import butunluk
        ozet_sonuc["butunluk"] = butunluk.tam_denetim(bildir=_telegram)
    except Exception as e:
        if not baglanti.baglanti_hatasi_mi(e):
            raise
        # Okuma tamamlanmadan HİÇBİR görev silinmez/birleştirilmez.
        ozet_sonuc["eksik"] = str(e)
        print(f"⚠️ Bütünlük denetimi YAPILAMADI, hiçbir görev silinmedi/değiştirilmedi: {e}")

    print("\n" + "=" * 70)
    if ozet_sonuc.get("eksik"):
        print("⚠️ SENKRONİZASYON TAMAMLANDI, AMA SON DENETİM BAĞLANTI SORUNU YÜZÜNDEN ATLANDI.")
        print("   İnternet düzelince aynı komutu yeniden çalıştırın (yapılmış işler tekrar yapılmaz).")
    else:
        print("🎉 TÜM SENKRONİZASYON BAŞARIYLA TAMAMLANDI!")
    print("=" * 70)
    return ozet_sonuc

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UYAP Excel (dosyalar.xlsx) Senkronizasyon Aracı")
    parser.add_argument("excel_path", nargs="?", default=None, help="UYAP Excel dosyasının tam yolu")
    parser.add_argument("--apply", "-a", action="store_true", help="Değişiklikleri canlı uygula (Notion ve TickTick)")
    args = parser.parse_args()

    run_sync(args.excel_path, apply=args.apply)
