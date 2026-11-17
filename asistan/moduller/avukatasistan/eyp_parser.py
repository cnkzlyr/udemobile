#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UETS .EYP (Elektronik Yazışma Paketi) Ayrıştırıcı
EYP zip arşivlerini, içindeki XML'leri, üst yazıları ve PDF eklerini çözümler.
"""

import os
import glob
import zipfile
import io
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from config import CONFIG, TZ_TURKEY
from utils import calculate_deadlines, is_excluded

def scan_all_eyp_files():
    """Download dizinlerindeki tüm benzersiz .eyp dosyalarını bulur."""
    eyp_files = []
    seen_names = set()
    for d in CONFIG["DOWNLOAD_DIRS"]:
        if os.path.exists(d):
            patterns = [os.path.join(d, "*.eyp"), os.path.join(d, "*.EYP")]
            for pat in patterns:
                for fpath in glob.glob(pat):
                    bname = os.path.basename(fpath).lower()
                    if bname not in seen_names:
                        seen_names.add(bname)
                        eyp_files.append(fpath)
    eyp_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return eyp_files

def extract_pdf_info(pdf_bytes, filename=""):
    """
    PDF içeriğini tarayarak evrak türünü ve varsa duruşma gün/saatini yakalar.
    """
    text = ""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages[:3]: # İlk 3 sayfa genellikle yeterlidir
            t = page.extract_text() or ""
            text += t + "\n"
    except Exception:
        pass
        
    doc_type = ""
    upper_name = filename.upper()
    upper_text = text.upper()
    
    # Dosya adından veya metinden evrak türü
    if "DURUSMAZAPTI" in upper_name or "DURUŞMA TUTANAĞI" in upper_text or "DURUSMA TUTANAGI" in upper_text:
        doc_type = "Duruşma Tutanağı"
    elif "TENSIP" in upper_name or "TENSİP" in upper_text:
        doc_type = "Tensip Zaptı"
    elif "BILIRKISI" in upper_name or "BİLİRKİŞİ" in upper_text:
        doc_type = "Bilirkişi Raporu"
    elif "GEREKCELI" in upper_name or "GEREKÇELİ KARAR" in upper_text:
        doc_type = "Gerekçeli Karar"
    elif "DAVADILEKCESI" in upper_name or "DAVA DİLEKÇESİ" in upper_text:
        doc_type = "Dava Dilekçesi"
    elif "CEVAP" in upper_name or "CEVAP DİLEKÇESİ" in upper_text:
        doc_type = "Cevap Dilekçesi"
    elif "IDDIANAME" in upper_name or "İDDİANAME" in upper_text:
        doc_type = "İddianame"
    elif "USTYAZI" in upper_name or "TEBLİĞ MAZBATASI" in upper_text:
        doc_type = "Tebliğ Mazbatası / Üst Yazı"
        
    # Duruşma Günü ve Saati Yakalama
    hearing_date = None
    hearing_time = None
    
    m_date = re.search(r"(\d{2}/\d{2}/\d{4})\s*(\d{2}:\d{2})", text)
    if m_date:
        hearing_date = m_date.group(1)
        hearing_time = m_date.group(2)
    else:
        m_day = re.search(r"(?:Duruşma Günü|Duruşma Tarihi)[^\d]*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
        m_tm = re.search(r"(?:Duruşma Saati|Saat)[^\d]*(\d{2}:\d{2})", text, re.IGNORECASE)
        if m_day:
            hearing_date = m_day.group(1)
        if m_tm:
            hearing_time = m_tm.group(1)
            
    return {
        "doc_type": doc_type,
        "hearing_date": hearing_date,
        "hearing_time": hearing_time,
        "snippet": text[:300].strip()
    }

def parse_eyp_file(eyp_path, extract_files=True):
    """
    Tek bir .eyp dosyasını derinlemesine analiz eder.
    """
    if not os.path.exists(eyp_path):
        return None
        
    court = ""
    esas_no = ""
    barcode = ""
    konu_raw = ""
    creation_date = None
    parties = []
    documents = []
    extracted_paths = []
    
    try:
        with zipfile.ZipFile(eyp_path, "r") as z:
            namelist = z.namelist()
            
            # 1. Ustveri/Ustveri.xml İncelemesi
            for n in namelist:
                if n.endswith("Ustveri.xml") or "Ustveri" in n:
                    xml_data = z.read(n).decode("utf-8", errors="ignore")
                    m_konu = re.search(r"<Konu>(.*?)</Konu>", xml_data)
                    if m_konu:
                        konu_raw = m_konu.group(1).strip()
                    m_tarih = re.search(r"<Tarih>(.*?)</Tarih>", xml_data)
                    if m_tarih:
                        try:
                            t_str = m_tarih.group(1).split(".")[0] # ms temizle
                            creation_date = datetime.fromisoformat(t_str).astimezone(TZ_TURKEY)
                        except Exception:
                            pass
                            
            # 2. Ekler/(1)dosyaBilgileriV1.xml İncelemesi (Taraflar ve Barkod)
            for n in namelist:
                if "dosyaBilgileri" in n or n.endswith(".xml"):
                    if "Ustveri" in n or "PaketOzeti" in n or "BelgeHedef" in n or "docProps" in n:
                        continue
                    try:
                        xml_data = z.read(n)
                        root = ET.fromstring(xml_data)
                        b_node = root.find(".//barkodNo")
                        if b_node is not None and b_node.text:
                            raw_b = b_node.text.strip()
                            barcode = raw_b.split("-")[0]
                            
                        for t_node in root.findall(".//taraf"):
                            adi = (t_node.findtext("tarafadi") or "").strip()
                            rol = (t_node.findtext("tarafrolu") or "").strip()
                            if adi:
                                parties.append({"adi": adi, "rol": rol})
                    except Exception:
                        pass
                        
            # Konu içerisinden mahkeme ve esas no çıkarımı
            if konu_raw:
                m_esas = re.search(r"\[(\d{4}/\d+)\]", konu_raw)
                if m_esas:
                    esas_no = m_esas.group(1)
                m_bar = re.search(r"-(\d{11,15})-", konu_raw)
                if m_bar and not barcode:
                    barcode = m_bar.group(1)
                if "[" in konu_raw:
                    court = konu_raw.split("[")[0].strip()
                else:
                    court = konu_raw.strip()
                    
            if is_excluded(court + " " + esas_no):
                return None
                
            # 3. PDF Dokümanları Analizi ve Dışa Aktarma
            export_dir = None
            if extract_files and esas_no:
                safe_esas = esas_no.replace("/", "_")
                dir_suffix = barcode if barcode else os.path.splitext(os.path.basename(eyp_path))[0][:16]
                export_dir = os.path.join(CONFIG["EVRAK_OUTPUT_DIR"], f"{safe_esas}_{dir_suffix}")
                os.makedirs(export_dir, exist_ok=True)
                
            for n in namelist:
                if n.endswith(".pdf") or n.endswith(".udf") or n.endswith(".png") or n.endswith(".jpg"):
                    file_bytes = z.read(n)
                    base_name = os.path.basename(n)
                    
                    pdf_meta = {}
                    if n.endswith(".pdf"):
                        pdf_meta = extract_pdf_info(file_bytes, base_name)
                        
                    saved_path = None
                    if export_dir:
                        saved_path = os.path.join(export_dir, base_name)
                        with open(saved_path, "wb") as out_f:
                            out_f.write(file_bytes)
                        extracted_paths.append(saved_path)
                        
                    documents.append({
                        "name": base_name,
                        "doc_type": pdf_meta.get("doc_type", ""),
                        "hearing_date": pdf_meta.get("hearing_date"),
                        "hearing_time": pdf_meta.get("hearing_time"),
                        "saved_path": saved_path
                    })
                    
    except Exception as e:
        print(f"⚠️ EYP ayrıştırma hatası ({eyp_path}): {e}")
        return None
        
    if not creation_date:
        creation_date = datetime.fromtimestamp(os.path.getmtime(eyp_path), tz=TZ_TURKEY)
        
    now_dt = datetime.now(TZ_TURKEY)
    if (now_dt - creation_date).days > CONFIG["MAX_SCAN_DAYS"]:
        return None
        
    deadlines = calculate_deadlines(creation_date, court=court)
    
    return {
        "source": "eyp",
        "eyp_path": eyp_path,
        "court": court,
        "esas_no": esas_no,
        "barcode": barcode,
        "konu_raw": konu_raw,
        "creation_date": creation_date,
        "deadlines": deadlines,
        "parties": parties,
        "documents": documents,
        "extracted_paths": extracted_paths
    }

def scan_standalone_durusma_pdfs():
    """
    Download dizinlerindeki müstakil duruşma tutanakları veya tensip zaptı PDF'lerini tarar.
    """
    import glob
    import pypdf
    found_items = []
    
    patterns = [
        "*durusma*.pdf", "*duruşma*.pdf", "*DURUSMA*.pdf", "*DURUŞMA*.pdf",
        "*tutanak*.pdf", "*zabit*.pdf", "*tensip*.pdf", "*TENSİP*.pdf"
    ]
    
    seen_files = set()
    for d in CONFIG["DOWNLOAD_DIRS"]:
        if os.path.exists(d):
            for pat in patterns:
                for fpath in glob.glob(os.path.join(d, pat)):
                    if fpath not in seen_files:
                        seen_files.add(fpath)
                        
    for fpath in seen_files:
        try:
            mtime = os.path.getmtime(fpath)
            f_dt = datetime.fromtimestamp(mtime, tz=TZ_TURKEY)
            if (datetime.now(TZ_TURKEY) - f_dt).days > CONFIG["MAX_SCAN_DAYS"]:
                continue
                
            with open(fpath, "rb") as f:
                pdf_bytes = f.read()
                
            info = extract_pdf_info(pdf_bytes, os.path.basename(fpath))
            if info.get("hearing_date"):
                reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
                full_txt = ""
                for page in reader.pages[:3]:
                    full_txt += (page.extract_text() or "") + "\n"
                    
                m_esas = re.search(r"ESAS\s*NO\s*[:\s]*(\d{4}/\d+)", full_txt, re.IGNORECASE)
                if not m_esas:
                    m_esas = re.search(r"(\d{4}/\d+)\s*E(?:sas|\.)?", full_txt, re.IGNORECASE)
                esas_no = m_esas.group(1) if m_esas else ""
                
                m_court = re.search(r"T\.C\.\s*([^\n\r]+MAHKEMES[İI])", full_txt, re.IGNORECASE)
                court = m_court.group(1).strip() if m_court else ""
                
                if esas_no:
                    found_items.append({
                        "court": court or "Mahkeme",
                        "esas_no": esas_no,
                        "hearing_date": info["hearing_date"],
                        "hearing_time": info.get("hearing_time") or "",
                        "doc_type": info.get("doc_type") or "Duruşma Tutanağı",
                        "file_path": fpath
                    })
        except Exception:
            continue
            
    return found_items
