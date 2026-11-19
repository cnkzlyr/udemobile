#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚖️ AVUKAT BULUT OTOMASYONU - TERMUX ANA ÇALIŞTIRICI (v7.0)
Tebligatlar CSV, EYP Paketleri, Notion ve TickTick Entegrasyonu
"""

# Android (Termux'suz): gömülü glibc ad çözümleyemez → bağımsız DNS çözücüyü bu süreçte de kur
# (sitecustomize'a güvenmeden; v4.4.0'da nöbetçi "Temporary failure in name resolution" veriyordu)
if __import__("os").environ.get("CANASISTAN_ANDROID") == "1":
    try:
        import sys as _s, pathlib as _p
        _s.path.insert(0, str(_p.Path(__file__).resolve().parents[2]))
        import dns_cozucu as _dns
        _dns.yama_kur()
    except Exception:  # noqa: BLE001
        pass

import os
import sys
import time
import argparse
import requests

sys.stdout.reconfigure(line_buffering=True)

from config import CONFIG, PROJECT_IDS, TZ_TURKEY
from utils import determine_list, clean_text, resolve_client_tag
from csv_parser import parse_csv_file, find_latest_tebligat_csv
from eyp_parser import scan_all_eyp_files, parse_eyp_file, scan_standalone_durusma_pdfs
from ics_parser import scan_all_ics_files, parse_ics_file
from notion_sync import fetch_notion_cases, find_notion_case, update_notion_tebligat_column, update_notion_tebligat_callout, update_notion_durusma_column
from ticktick_sync import find_or_create_parent_task, create_or_update_uets_subtask, create_or_update_durusma_subtask, clean_and_merge_duplicates

def send_telegram_alert(text):
    token = CONFIG.get("TELEGRAM_BOT_TOKEN")
    chat_id = CONFIG.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=8)
    except Exception:
        pass

def merge_and_cross_validate(csv_items, eyp_items):
    """
    CSV ve EYP dosyalarından gelen tebligatları barkod ve esas no üzerinden eşleştirip zenginleştirir.
    """
    unified = {} # key: barcode or esas_no -> item
    
    # 1. EYP Verilerini Ekle (En detaylı içerik: taraflar, evraklar, duruşma zaptı vb.)
    for e in eyp_items:
        key = e.get("barcode") or f"{clean_text(e.get('court'))}_{e.get('esas_no')}"
        if key:
            unified[key] = dict(e)
            
    # 2. CSV Verileriyle Doğrula ve Tamamla
    for c in csv_items:
        c_bar = c.get("barcode")
        c_esas = c.get("esas_no")
        # Barkodu ve esas nosu olmayanlar (noter AZİLNAME vb.) UETS mesaj numarasıyla tekilleşir;
        # eskiden hepsi "azilname_" anahtarında birleşip biri kayboluyordu.
        c_key = c_bar or (f"UETS_{c['uets_no']}" if (not c_esas and c.get("uets_no")) else f"{clean_text(c.get('court'))}_{c_esas}")
        
        # Eğer barkod ile eşleşen EYP varsa birleştir
        match_key = None
        if c_bar and c_bar in unified:
            match_key = c_bar
        elif not c_bar and not c_esas and c.get("uets_no"):
            # Barkodsuz/esassız (ör. AZİLNAME): API ile inen EYP dosyasının adı UETS mesaj numarasıdır.
            # Eşleşmeyince aynı tebligat CSV'den ve EYP'den İKİ kayıt oluyor, ikincisi boş görev açmaya çalışıyordu.
            for k, val in unified.items():
                kok = os.path.splitext(os.path.basename(val.get("eyp_path") or ""))[0]
                if kok and kok == c["uets_no"]:
                    match_key = k
                    break
        else:
            # Sadece EYP'de barkod tespit edilemediyse mahkeme ve esas no üzerinden eşleştir
            for k, val in unified.items():
                if not val.get("barcode") and val.get("esas_no") == c_esas and c_esas:
                    c_court_clean = clean_text(c.get("court"))
                    val_court_clean = clean_text(val.get("court"))
                    if c_court_clean == val_court_clean or c_court_clean in val_court_clean or val_court_clean in c_court_clean:
                        match_key = k
                        break
                    
        if match_key:
            # Var olan EYP kaydını CSV teslim tarihi ile güncelle
            existing = unified[match_key]
            for alan in ("konu_raw", "uets_no"):
                if c.get(alan) and not existing.get(alan):
                    existing[alan] = c[alan]
            existing["gonderen"] = c.get("gonderen")
            if c.get("uets_no"):
                existing["uets_no"] = c["uets_no"]
            # CSV teslim tarihi resmi UETS tarihi olduğu için önceliklidir
            if c.get("deadlines"):
                existing["deadlines"] = c["deadlines"]
        else:
            unified[c_key] = dict(c)
            
    res_list = list(unified.values())
    # Her zaman en yeni tebligat en başta olacak şekilde tarihe göre sırala!
    def sort_key(x):
        dt = x.get("deadlines", {}).get("gelis_dt")
        if dt:
            try:
                return dt.timestamp()
            except Exception:
                pass
        return 0
    res_list.sort(key=sort_key, reverse=True)
    return res_list

def infer_client_tag_from_context(parties, court="", esas_no=""):
    """
    Notion'da henüz kartı açılmamış tebligatlarda, evraktaki taraflardan ve
    UYAP Excel listesinden müvekkili ve etiketini tespit eder.
    Avukatın kendisi (Can KIZILYAR) müvekkil olarak seçilmez; temsil ettiği taraf bulunur.
    """
    if parties:
        for p in parties:
            p_adi = p.get("adi", "")
            p_rol = p.get("rol", "").lower()
            if not p_adi:
                continue
            if "kizilyar" in p_adi.lower() or ("can" in p_adi.lower() and "vekil" in p_rol):
                continue
            c_tag = resolve_client_tag(p_adi)
            raw_clean = clean_text(p_adi)
            if c_tag and (c_tag != f"#{raw_clean}" or any(kw in raw_clean for kw in CONFIG.get("COMPANY_KEYWORD_OVERRIDES", {}))):
                return c_tag, p_adi

        for p in parties:
            p_adi = p.get("adi", "")
            p_rol = p.get("rol", "").lower()
            if not p_adi or "vekil" in p_rol or "kizilyar" in p_adi.lower():
                continue
            c_tag = resolve_client_tag(p_adi)
            if c_tag:
                return c_tag, p_adi

    try:
        from sync_uyap_excel import find_latest_uyap_excel, parse_uyap_excel, fetch_all_notion_clients, find_matched_client_for_case
        ex_path = find_latest_uyap_excel()
        if ex_path and os.path.exists(ex_path):
            ex_cases = parse_uyap_excel(ex_path)
            for ec in ex_cases:
                if esas_no and ec.get("dosya_no") == esas_no:
                    c_clean = clean_text(court)
                    b_clean = clean_text(ec.get("birim", ""))
                    if not court or c_clean in b_clean or b_clean in c_clean:
                        cl_db = fetch_all_notion_clients()
                        m_cl = find_matched_client_for_case(ec.get("taraflar", []), cl_db)
                        if m_cl:
                            c_tag = resolve_client_tag(m_cl["name"], is_cmk=m_cl.get("is_cmk", False))
                            if c_tag:
                                return c_tag, m_cl["name"]
    except Exception:
        pass

    return "", ""

def run_synchronization(csv_path=None, force=False):
    print("\n" + "="*65)
    print("⚖️  AVUKAT BULUT v8.0 - TEBLİGAT & DOSYA SENKRONİZASYONU")
    print("="*65)
    print(f"🕒  TARAMA ARALIĞI: Son {CONFIG['MAX_SCAN_DAYS']} Gün (31+ gün önceki tebligatlar atlanır)")
    print("="*65)
    
    # 1. Download Klasöründeki CSV'yi Oku
    if csv_path and os.path.exists(csv_path):
        latest_csv = csv_path
    else:
        latest_csv = find_latest_tebligat_csv()
    csv_items = []
    if latest_csv:
        print(f"📄 Bulunan CSV: {os.path.basename(latest_csv)}")
        csv_items = parse_csv_file(latest_csv)
        print(f"   ↳ {len(csv_items)} adet tebligat kaydı okundu.")
    else:
        print("ℹ️ Download klasöründe 'tebligatlar*.csv' bulunamadı.")
        
    # 2. Download Klasöründeki EYP Paketlerinin Başlıklarını Hızlı Oku (extract_files=False)
    eyp_paths = scan_all_eyp_files()
    eyp_items = []
    if eyp_paths:
        print(f"📦 Bulunan Benzersiz EYP Paket Sayısı: {len(eyp_paths)}")
        for p in eyp_paths:
            res = parse_eyp_file(p, extract_files=False)
            if res:
                eyp_items.append(res)
    else:
        print("ℹ️ Download klasöründe '.eyp' dosyası bulunamadı.")
        
    # 3. Çapraz Eşleştirme ve Doğrulama
    all_tebligatlar = merge_and_cross_validate(csv_items, eyp_items)
    print(f"\n📊 Toplam İncelenecek Tekil Tebligat Sayısı: {len(all_tebligatlar)}")
    
    if not all_tebligatlar:
        print("✨ İşlenecek yeni veya okunmamış tebligat bulunmuyor.")
        return
        
    # 4. Notion Veritabanını Önbelleğe Al
    print("\n🔄 Notion dosyaları kontrol ediliyor...")
    cases = fetch_notion_cases()
    print(f"   ↳ Notion'da {len(cases)} adet aktif dosya yüklendi.")
    
    # 5. Tebligatları TickTick ve Notion'a Aktar
    from ticktick_sync import find_existing_tebligat_in_completed, find_existing_tebligat_in_active
    yeni_eklenen = 0
    guncellenen = 0
    
    for item in all_tebligatlar:
        court = item.get("court") or "Bilinmeyen Merci"
        esas_no = item.get("esas_no") or ""
        barcode = item.get("barcode") or ""
        deadlines = item["deadlines"]
        target_deadline_str = deadlines.get("target_str") or deadlines["d14_str"]
        target_label = deadlines.get("target_label") or "Yasal Süre"
        
        if not esas_no and not item.get("uets_no"):
            # Yalnızca EYP dosyasından gelen, UETS listesinde karşılığı olmayan esassız kayıt: görev açılmaz
            # (UETS listesindeki kaydı zaten işleniyor; aksi halde boş bir ikinci görev oluşuyordu).
            print(f"\n📄 Esas nosuz EYP kaydı UETS listesiyle eşleşmedi, atlandı: {os.path.basename(item.get('eyp_path') or '')}")
            continue
        if not esas_no:
            # Esas numarası olmayan tebligat (noter AZİLNAME, kurum yazıları...) da KAÇIRILMAZ: ayrı görev açılır.
            try:
                from ticktick_sync import create_or_update_esassiz_tebligat
                tid, yeni = create_or_update_esassiz_tebligat(item)
                try:
                    import defter
                    defter.tebligat_kaydet(item, tid)
                except Exception:
                    pass
                if yeni:
                    yeni_eklenen += 1
                elif tid:
                    guncellenen += 1
            except Exception as e_esassiz:
                print(f"   ⚠️ Esas nosuz tebligat işlenemedi ({item.get('konu_raw') or court}): {e_esassiz}")
            continue

        # -------------------------------------------------------------
        # HIZLI ÖN KONTROL: Kapatılmış / Yapılmayacak / Tamamlanmış ise atla (Tarih & Barkod Doğrulamalı)
        # -------------------------------------------------------------
        comp_task = find_existing_tebligat_in_completed(barcode, esas_no, court, deadlines=deadlines)
        if comp_task:
            c_lbl = "Tamamlandı" if comp_task.get("status") == 2 else "Yapılmayacak"
            print(f"\n📨 {court} - {esas_no} Esas (Barkod: {barcode}):")
            print(f"   🛡️ Bu tebligat daha önce '{c_lbl}' olarak kapatılmış. Yeniden açılmadı.")
            continue
            
        print(f"\n📨 İşleniyor: {court} - {esas_no} Esas (Barkod: {barcode})")
        
        # -------------------------------------------------------------
        # EYP Evraklarını YALNIZCA GEREKTİĞİNDE Ayıkla (Yeni veya eksik ekli görevler için)
        # -------------------------------------------------------------
        list_name = determine_list(court, gonderen=item.get("gonderen", ""))
        project_id = PROJECT_IDS.get(list_name) or PROJECT_IDS["Inbox"]
        
        existing_t, _ = find_existing_tebligat_in_active(barcode, esas_no, court, project_id, deadlines=deadlines)
        from state_manager import get_barcode_state
        b_st = get_barcode_state(barcode) if barcode else {}
        from ticktick_sync import gercek_ek_var
        has_att = gercek_ek_var(existing_t, barcode) if existing_t else False
        
        if item.get("eyp_path") and (not existing_t or not has_att):
            full_eyp = parse_eyp_file(item["eyp_path"], extract_files=True)
            if full_eyp:
                item["documents"] = full_eyp.get("documents", [])
                item["extracted_paths"] = full_eyp.get("extracted_paths", [])
                if item["extracted_paths"]:
                    print(f"   📦 EYP Evrakları Ayıklandı: {len(item['extracted_paths'])} adet dosya.")

        # Notion Eşleştirmesi
        notion_case = find_notion_case(esas_no, court)
        notion_url = ""
        client_tag = ""
        page_id = None
        
        # Dosya defteri (UYAP listesinden): müvekkil + dosyanın UYAP'taki durumu
        defter_kaydi = None
        try:
            import defter
            defter_kaydi = defter.dosya_bul(esas_no, court)
        except Exception as e_def:
            print(f"   ℹ️ Dosya defteri okunamadı: {e_def}")
        if defter_kaydi and defter.kapali_mi(defter_kaydi.get("durum")):
            uyari = (f"⚠️ KAPALI DOSYAYA TEBLİGAT: {court} {esas_no} UYAP listesinde '{defter_kaydi.get('ham_durum') or defter_kaydi.get('durum')}' "
                     f"görünüyor ama yeni tebligat geldi (barkod {barcode}). Dosya yeniden açılmış ya da karar sonrası işlem olabilir.")
            print("   " + uyari)
            try:
                if defter.uyari_yeni_mi(f"kapali_teb:{barcode or esas_no}", uyari):
                    send_telegram_alert(uyari)
            except Exception:
                pass

        if notion_case and not notion_case.get("client_tag") and defter_kaydi and defter_kaydi.get("muvekkil_etiket"):
            notion_case["client_tag"] = defter_kaydi["muvekkil_etiket"]
            notion_case["client_name"] = notion_case.get("client_name") or defter_kaydi.get("muvekkil")
        if notion_case:
            court = notion_case["court"] # Mahkeme adını standartlaştır
            client_tag = notion_case["client_tag"]
            notion_url = notion_case["url"]
            page_id = notion_case["page_id"]
            print(f"   ✅ Notion Eşleşti: {notion_case['client_name']} ({client_tag})")
        elif defter_kaydi and defter_kaydi.get("muvekkil_etiket"):
            client_tag = defter_kaydi["muvekkil_etiket"]
            print(f"   📚 Müvekkil dosya defterinden (UYAP listesi): {defter_kaydi.get('muvekkil')} (#{client_tag})")
        else:
            print("   ℹ️ Notion'da dosya kartı bulunamadı.")
            inferred_tag, inferred_name = infer_client_tag_from_context(item.get("parties", []), court, esas_no)
            if inferred_tag:
                client_tag = inferred_tag
                print(f"   👤 Evrak/UYAP Verilerinden Müvekkil Tespit Edildi: {inferred_name} ({client_tag})")
            else:
                print("   ℹ️ Müvekkil tespit edilemedi (Genel dosya olarak işlenecek).")
            
        # CMK Dosyası Tespiti
        is_cmk = (notion_case.get("is_cmk", False) if notion_case else False) or "cmk" in (client_tag or "").lower() or any(k in court.lower() for k in ["ceza", "soruşturma", "ağır ceza", "asliye ceza"])

        # TickTick Proje ve Parent Görev Tespiti (Parent ile Subtask aynı listede garanti edilir)
        parent_res = find_or_create_parent_task(court, esas_no, project_id, client_tag, notion_url)
        parent_id = parent_res[0] if isinstance(parent_res, (tuple, list)) else parent_res
        if isinstance(parent_res, (tuple, list)) and len(parent_res) > 1 and parent_res[1]:
            project_id = parent_res[1]
        
        # Tebligat Alt Görevini Oluştur/Güncelle
        sub_res = create_or_update_uets_subtask(item, project_id, parent_id, client_tag, notion_url, list_name=list_name, is_cmk=is_cmk, force=force)
        sub_id = sub_res[0] if sub_res else None
        is_new = sub_res[1] if sub_res and len(sub_res) > 1 else False
        try:
            import defter
            defter.tebligat_kaydet(item, sub_id)
        except Exception:
            pass
        
        if sub_id:
            tt_link = f"https://ticktick.com/webapp/#p/{project_id}/tasks/{sub_id}"
            if is_new:
                yeni_eklenen += 1
                print(f"   ⭐ TickTick: YENİ GÖREV OLUŞTURULDU (ID: {sub_id})")
                # Telegram Bildirimi
                alert_msg = (
                    f"🔔 YENİ ELEKTRONİK TEBLİGAT!\n\n"
                    f"🏛️ Merci: {court}\n"
                    f"📌 Dosya: {esas_no} Esas\n"
                    f"🏷️ Müvekkil: {client_tag or 'Belirtilmedi'}\n"
                    f"⏳ {target_label}: {target_deadline_str} (17:00)\n"
                    f"🔗 TickTick: {tt_link}"
                )
                send_telegram_alert(alert_msg)
            else:
                guncellenen += 1
                print(f"   🛡️ TickTick: Görev zaten mevcuttu (Mükerrer açılmadı, doğrulandı).")
                
            # Notion Güncellemesi
            if page_id:
                update_notion_tebligat_column(page_id, target_deadline_str, "Tebligat", tt_link)
                update_notion_tebligat_callout(page_id, target_deadline_str, "Tebligat", tt_link)
                print("   📝 Notion kartı ve Callout alanı güncellendi.")
                
        # Duruşma Bilgisi Tespiti ve Entegrasyonu
        documents = item.get("documents", [])
        for doc in documents:
            h_date = doc.get("hearing_date")
            h_time = doc.get("hearing_time") or ""
            doc_type = doc.get("doc_type") or doc.get("name")
            if h_date:
                d_id, d_is_new = create_or_update_durusma_subtask(
                    court, esas_no, project_id, parent_id,
                    h_date, h_time, client_tag, notion_url, doc_type, is_cmk=is_cmk
                )
                if d_id and d_is_new:
                    print(f"   ⚖️ TickTick: YENİ DURUŞMA GÖREVİ OLUŞTURULDU ({h_date} {h_time})")
                    alert_durusma = (
                        f"⚖️ YENİ DURUŞMA GÜNÜ BELİRLENDİ!\n\n"
                        f"🏛️ Merci: {court}\n"
                        f"📌 Dosya: {esas_no} Esas\n"
                        f"🏷️ Müvekkil: {client_tag or 'Belirtilmedi'}\n"
                        f"📅 Duruşma: {h_date} Saat: {h_time or 'Belirtilmedi'}\n"
                        f"📄 Belge: {doc_type}"
                    )
                    send_telegram_alert(alert_durusma)
                elif d_id:
                    print(f"   🛡️ TickTick: Duruşma görevi zaten mevcut ({h_date}).")
                
                if page_id:
                    update_notion_durusma_column(page_id, h_date, h_time)
                    print(f"   📅 Notion '📅 Sıradaki Duruşma' güncellendi: {h_date} {h_time}")

        time.sleep(0.15)
        
    # 5.b. Müstakil Duruşma PDF'lerini Tara ve İşle
    standalone_durusmalar = scan_standalone_durusma_pdfs()
    if standalone_durusmalar:
        print(f"\n📑 Bulunan Müstakil Duruşma/Tensip Evrak Sayısı: {len(standalone_durusmalar)}")
        for sd in standalone_durusmalar:
            s_court = sd["court"]
            s_esas = sd["esas_no"]
            s_hdate = sd["hearing_date"]
            s_htime = sd["hearing_time"]
            s_doc = sd["doc_type"]
            
            s_notion = find_notion_case(s_esas, s_court)
            s_url = s_notion["url"] if s_notion else ""
            s_pid = s_notion["page_id"] if s_notion else None
            s_tag = s_notion["client_tag"] if s_notion else ""
            s_cmk = s_notion.get("is_cmk", False) if s_notion else False
            
            s_list = determine_list(s_court)
            s_proj_id = PROJECT_IDS.get(s_list) or PROJECT_IDS["Inbox"]
            s_parent_res = find_or_create_parent_task(s_court, s_esas, s_proj_id, s_tag, s_url)
            s_parent_id = s_parent_res[0] if isinstance(s_parent_res, (tuple, list)) else s_parent_res
            if isinstance(s_parent_res, (tuple, list)) and len(s_parent_res) > 1 and s_parent_res[1]:
                s_proj_id = s_parent_res[1]
            
            d_id, d_is_new = create_or_update_durusma_subtask(
                s_court, s_esas, s_proj_id, s_parent_id,
                s_hdate, s_htime, s_tag, s_url, s_doc, is_cmk=s_cmk
            )
            if d_id and d_is_new:
                print(f"   ⚖️ Müstakil Duruşma Eklendi: {s_court} - {s_esas} ({s_hdate})")
                alert_durusma = (
                    f"⚖️ YENİ DURUŞMA GÜNÜ BELİRLENDİ (Müstakil Evrak)!\n\n"
                    f"🏛️ Merci: {s_court}\n"
                    f"📌 Dosya: {s_esas} Esas\n"
                    f"🏷️ Müvekkil: {s_tag or 'Belirtilmedi'}\n"
                    f"📅 Duruşma: {s_hdate} Saat: {s_htime or 'Belirtilmedi'}\n"
                    f"📄 Belge: {s_doc}"
                )
                send_telegram_alert(alert_durusma)
            if s_pid:
                update_notion_durusma_column(s_pid, s_hdate, s_htime)
                print(f"   📅 Notion '📅 Sıradaki Duruşma' güncellendi: {s_hdate} {s_htime}")

    # 5.c. Celse & UYAP Takvim (.ics) Dosyalarını Tara ve İşle
    ics_files = scan_all_ics_files()
    if ics_files:
        print(f"\n📅 Bulunan Celse/UYAP Takvim (.ics) Sayısı: {len(ics_files)}")
        for ics_p in ics_files:
            ics_hearings = parse_ics_file(ics_p)
            for ih in ics_hearings:
                i_court = ih["court"]
                i_esas = ih["esas_no"]
                i_hdate = ih["hearing_date"]
                i_htime = ih["hearing_time"]
                i_doc = ih["doc_type"]
                
                i_notion = find_notion_case(i_esas, i_court)
                i_url = i_notion["url"] if i_notion else ""
                i_pid = i_notion["page_id"] if i_notion else None
                i_tag = i_notion["client_tag"] if i_notion else ""
                i_cmk = i_notion.get("is_cmk", False) if i_notion else False
                
                i_list = determine_list(i_court)
                i_proj_id = PROJECT_IDS.get(i_list) or PROJECT_IDS["Inbox"]
                i_parent_id = find_or_create_parent_task(i_court, i_esas, i_proj_id, i_tag, i_url)
                
                d_id, d_is_new = create_or_update_durusma_subtask(
                    i_court, i_esas, i_proj_id, i_parent_id,
                    i_hdate, i_htime, i_tag, i_url, i_doc, is_cmk=i_cmk
                )
                if d_id and d_is_new:
                    print(f"   📅 Takvim Duruşması Eklendi: {i_court} - {i_esas} ({i_hdate} {i_htime})")
                    alert_ics = (
                        f"📅 CELSE TAKVİMİNDEN YENİ DURUŞMA!\n\n"
                        f"🏛️ Merci: {i_court}\n"
                        f"📌 Dosya: {i_esas} Esas\n"
                        f"🏷️ Müvekkil: {i_tag or 'Belirtilmedi'}\n"
                        f"📅 Duruşma: {i_hdate} Saat: {i_htime or 'Belirtilmedi'}\n"
                        f"📑 Başlık: {i_doc}"
                    )
                    send_telegram_alert(alert_ics)
                if i_pid:
                    update_notion_durusma_column(i_pid, i_hdate, i_htime)

    print(f"\n🎉 SENKRONİZASYON TAMAMLANDI! (Yeni Eklenen: {yeni_eklenen}, Doğrulanan: {guncellenen})")
    
    # 6. Bütünlük denetimi: mükerrer tebligat/duruşma/dava kartı, yarım kalmış yazmalar (Notion taraması izleyicide)
    import butunluk
    butunluk.tam_denetim(bildir=send_telegram_alert, notion=False)
    return {"yeni": yeni_eklenen, "dogrulanan": guncellenen}

def main():
    parser = argparse.ArgumentParser(description="Avukat Bulut Termux Tebligat Otomasyonu")
    parser.add_argument("--watch", "-w", action="store_true", help="Sürekli izleme modunda çalıştır (5 dakikada bir kontrol eder)")
    parser.add_argument("--dedup", "-d", action="store_true", help="Yalnızca mevcut mükerrerleri temizle ve birleştir")
    parser.add_argument("--offline", "--no-download", action="store_true", help="UETS portalına bağlanma, yerel taze CSV ve arşiv ile çalış")
    parser.add_argument("--force", "-f", action="store_true", help="EYP paketi henüz inmemiş olsa bile TickTick görevini zorla oluştur")
    parser.add_argument("--autocontrol", "-ac", action="store_true", help="Tüm tebligatlar için otokontrol ve doğrulama raporu çalıştır")
    parser.add_argument("--count", "-c", type=int, default=None, help="UETS'den indirilecek son tebligat sayısı (varsayılan: tümü)")
    parser.add_argument("--headless", action="store_true", help="Tarayıcıyı başsız (ekransız) modda çalıştır")
    parser.add_argument("--csv", type=str, default=None, help="İşlenecek özel CSV dosya yolu")
    parser.add_argument("--excel", "-xl", type=str, nargs="?", const="/sdcard/Download/dosyalar.xlsx", default=None, help="UYAP Excel dosyasını (dosyalar.xlsx) Notion ve TickTick ile senkronize et")
    parser.add_argument("--apply", "-a", action="store_true", help="Excel senkronizasyonundaki değişiklikleri canlı uygula")
    parser.add_argument("--tani", action="store_true", help="Teşhis kaydı: her adımda ekran görüntüsü, sayfa kodu, ağ/konsol kaydı; sonunda tek zip")
    args = parser.parse_args()
    import uets_tani
    if args.tani:
        uets_tani.etkinlestir()
    if uets_tani.aktif():
        uets_tani.dis_yonetim()
        uets_tani.basla()
        try:
            return _main(args)
        except BaseException as e:
            uets_tani.hata(None, "main", e)
            raise
        finally:
            uets_tani.bitir(kesin=True)
    return _main(args)


def _main(args):
    
    if args.autocontrol:
        from autocontrol import print_autocontrol_report
        print_autocontrol_report(csv_path=args.csv)
        return

    if args.excel:
        from sync_uyap_excel import run_sync
        run_sync(excel_path=args.excel, apply=args.apply)
        return

    if args.dedup:
        clean_and_merge_duplicates()
        return

    active_csv = args.csv
    # ÖN KONTROL: internet yoksa gelene kadar bekler; anahtar geçersizse yarım iş başlatmadan durur.
    import baglanti
    tamam, sorunlar = baglanti.on_kontrol()
    if not tamam:
        print("🛑 Ön kontrol başarısız, işlem başlatılmadı (yarım iş olmasın): " + "; ".join(sorunlar))
        sys.exit(3)
    # KURAL: Hiçbir zaman eski indirilmiş CSV ile çalışılmaz! Her zaman UETS'den günceli çekilir.
    if not args.offline and not args.csv:
        from uets_downloader import login_and_download
        print("🤖 [KURAL]: UETS portalına bağlanılıyor, en güncel taze CSV ve eksik EYP paketleri indiriliyor...")
        try:
            dis_surucu = None
            if os.environ.get("CANASISTAN_ANDROID") == "1":
                # Telefon (Termux'suz): Chrome yok → CanEditor'un gizli WebView'ı CDP ile Selenium gibi sürülür
                from cdp_surucu import CdpSurucu
                print("📱 Android: UETS, CanEditor'un gizli tarayıcısıyla açılıyor (Chrome gerekmez)...")
                dis_surucu = CdpSurucu()
            dl_csv = login_and_download(headless=args.headless, count=args.count, auto_sync=False, external_driver=dis_surucu)
            if dl_csv and isinstance(dl_csv, str) and os.path.exists(dl_csv):
                active_csv = dl_csv
        except Exception as dl_err:
            print(f"⚠️ UETS canlı indirme sırasında hata: {dl_err}")
            print("   ↳ Çevrimdışı/arşivdeki en güncel CSV aranıyor...")

    if args.watch:
        print("👀 Sürekli İzleme Modu Aktif (Çıkış için Ctrl+C)...")
        while True:
            try:
                run_synchronization(csv_path=active_csv, force=args.force)
            except Exception as e:
                print(f"⚠️ Hata oluştu: {e}")
            print("\n💤 5 dakika bekleniyor...")
            time.sleep(300)
    else:
        run_synchronization(csv_path=active_csv, force=args.force)

if __name__ == "__main__":
    try:
        main()
    except Exception as _e:
        if not getattr(_e, "baglanti_hatasi", False):
            raise
        # Bağlantı koptu: yarım okumayla görev açılmadı/silinmedi. Bir sonraki çalışma kaldığı yerden tamamlar.
        print(f"\n📶 Bağlantı sorunu, işlem güvenle durduruldu: {_e}\n"
              "   Okuma tamamlanmadan görev açılmadı ya da silinmedi. İnternet gelince tekrar çalıştırın.")
        sys.exit(3)
