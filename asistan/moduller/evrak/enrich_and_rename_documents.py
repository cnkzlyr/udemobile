#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır. / All rights reserved.
"""
UYAP Evrak Zenginleştirme ve Akıllı Yeniden Adlandırma Motoru
============================================================
Bu betik:
1. İndirilen tüm UDF evraklarını (ve eşleşen PDF'leri) analiz eder.
2. content.xml içerisinden Mahkeme, Dosya No, Karar No, Duruşma Tarihi,
   Celse No, Bağlantılı İlk Derece Dosyası ve Av. Can Kızılyar'ın temsil ettiği
   Müvekkil bilgisini eksiksiz ve hatasız tespit eder.
3. Aynı dosyadaki tüm evraklar için müvekkil eşleştirmesini (Case-Client Mapping) tamamlar.
4. UDF dosyasının documentproperties.xml özniteliklerine tüm bu zengin hukuki
   meta-verileri (Mahkeme, Esas, Karar, Duruşma T., Müvekkil, Karşı Taraf, Hakim, Katip vb.) işler.
5. Dosya adını klasörlerden bağımsız, tek başına %100 tanımlayıcı olacak şekilde
   standart formata dönüştürür ve hem UDF hem de PDF'i atomik olarak yeniden adlandırır:
   Format: {Tarih}_{Birim}_{Esas}_{Muv-Muvekkil}_{EvrakTuru}_{Karar/DT/Celse/Baglanti}_{EvrakId}.{ext}
6. İndirme geçmişini (indirme_gecmisi.json) ve CSV indekslerini yeni yollarla günceller.
"""

import os
import sys
import re
import glob
import json
import csv
import zipfile
import shutil
import argparse
import datetime as dt
from pathlib import Path
from collections import defaultdict

# Paketlenmiş uygulamada yazılabilir veri klasörü UYAP_VERI_DIZINI ile verilir
BASE_DIR = Path(os.environ.get("UYAP_VERI_DIZINI") or Path(__file__).resolve().parent)
if Path("/sdcard/Download/UYAP_Indirilenler").exists():
    DEFAULT_DOWNLOAD_DIR = Path("/sdcard/Download/UYAP_Indirilenler")
elif (BASE_DIR.parent / "UYAP_Indirilenler").exists():
    DEFAULT_DOWNLOAD_DIR = (BASE_DIR.parent / "UYAP_Indirilenler").resolve()
elif (BASE_DIR / "UYAP_Indirilenler").exists():
    DEFAULT_DOWNLOAD_DIR = (BASE_DIR / "UYAP_Indirilenler").resolve()
else:
    DEFAULT_DOWNLOAD_DIR = BASE_DIR / "UYAP_Indirilenler"

if (BASE_DIR / "indirme_gecmisi.json").exists():
    DEFAULT_HISTORY_FILE = (BASE_DIR / "indirme_gecmisi.json").resolve()
else:
    DEFAULT_HISTORY_FILE = BASE_DIR / "indirme_gecmisi.json"

ROLE_REGEX = (
    r'(?:DAVALI\s*-\s*KARŞI\s*DAVACI|DAVACI\s*-\s*KARŞI\s*DAVALI|'
    r'KARŞI\s*DAVACI|KARŞI\s*DAVALI|'
    r'BİRLEŞEN\s*DOSYA\s*(?:DAVACISI|DAVALISI)|'
    r'ASIL\s*DAVACI|ASIL\s*DAVALI|'
    r'DAVACI|DAVALI|SANIK|KATILAN|MÜŞTEKİ|ŞİKAYETÇİ|MAĞDUR|'
    r'ALACAKLI|BORÇLU|İTİRAZ\s+EDEN|İSTİNAF\s+EDEN|TEMYİZ\s+EDEN)'
)

def tr_upper(text: str) -> str:
    if not text:
        return ""
    return text.replace("i", "İ").replace("ı", "I").upper()

def tr_lower(text: str) -> str:
    if not text:
        return ""
    return text.replace("İ", "i").replace("I", "ı").lower()

def clean_text(s: str) -> str:
    if not s:
        return ""
    return re.sub(r'\s+', ' ', str(s)).strip()

def sanitize_name_component(text: str, max_len: int = 50) -> str:
    if not text:
        return ""
    s = str(text).replace("/", "-").replace("\\", "-").replace(":", "-").replace('"', '').replace("'", "")
    s = re.sub(r'[<>|?*&;%$#@!+=\[\]{}()]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:max_len]

def format_court_abbreviation(court_name: str) -> str:
    c = tr_upper(court_name)
    c = re.sub(r'^T\.C\.\s*', '', c).strip()
    c = c.replace('BÖLGE ADLİYE MAHKEMESİ', 'BAM')
    c = c.replace('ASLİYE HUKUK MAHKEMESİ', 'AHM')
    c = c.replace('ASLİYE CEZA MAHKEMESİ', 'ACM')
    c = c.replace('AĞIR CEZA MAHKEMESİ', 'AgirCeza')
    c = c.replace('AİLE MAHKEMESİ', 'Aile')
    c = c.replace('İŞ MAHKEMESİ', 'Is')
    c = c.replace('İCRA DAİRESİ', 'Icra')
    c = c.replace('SULH CEZA HÂKİMLİĞİ', 'SCH')
    c = c.replace('SULH CEZA HAKİMLİĞİ', 'SCH')
    c = c.replace('SULH HUKUK MAHKEMESİ', 'SHM')
    c = c.replace('TÜKETİCİ MAHKEMESİ', 'Tuketici')
    c = c.replace('FİKRİ VE SINAİ HAKLAR HUKUK MAHKEMESİ', 'FSHHM')
    c = c.replace('CUMHURİYET BAŞSAVCILIĞI', 'CBS')
    c = re.sub(r'\s+', '', c)
    return c[:25]

def format_lower_court_slug(raw_court: str, raw_num: str) -> str:
    abbr = format_court_abbreviation(clean_text(raw_court))
    m_num = re.search(r'([0-9]{4})\s*/\s*([0-9]+)', raw_num)
    if m_num:
        return f"Ilk-{abbr}-{m_num.group(1)}-{m_num.group(2)}"
    return f"Ilk-{abbr}"

def clean_party_name(raw_name: str) -> str:
    if not raw_name:
        return ""
    name = re.sub(r'<[^>]+>', ' ', raw_name)
    name = re.sub(r'\b[0-9]{11}\b', '', name)
    name = re.sub(r'\[[0-9\-]+\]\s*(?:UETS)?', '', name)
    name = re.sub(r'\bT\.?C\.?\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\b(?:Vekilleri|Vekili|Müdafii|Müdafi|Vekil|Adına|Tarafından|ve\s+Vekili)\b.*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^(?:1-|2-|3-|[0-9]+\))\s*', '', name)
    name = re.sub(r'^(?:birleşen\s+dava\s+(?:davacısı|davalısı)|asıl\s+dava\s+(?:davacısı|davalısı)|karşı\s+davacı|karşı\s+davalı)\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^(?:Sanık|Davacı|Davalı|Katılan|Müşteki|Alacaklı|Borçlu|İtiraz\s+Eden|İstinaf\s+Eden)\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[,:;\-_/\(\)]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    words = name.split()
    if not words:
        return ""
    if len(words) == 1:
        return words[0].upper()
    
    first_names = [w.capitalize() for w in words[:-1]]
    last_name = words[-1].upper()
    return ' '.join(first_names + [last_name])

def extract_meta_from_udf(udf_path: Path) -> dict:
    data = {
        "mahkeme": "",
        "esas_no": "",
        "karar_no": "",
        "durusma_tarihi": "",
        "celse_no": "",
        "baglantili_dosya": "",
        "muvekkil": "",
        "muvekkil_rol": "",
        "karsi_taraf": "",
        "hakim": "",
        "katip": "",
        "dogrulama_kodu": "",
        "muhatap": "",
        "ptt_barkod": "",
        "teblig_sonuc": "",
    }
    
    if not zipfile.is_zipfile(udf_path):
        return data

    try:
        with zipfile.ZipFile(udf_path, "r") as z:
            names = z.namelist()
            if "documentproperties.xml" in names:
                try:
                    p_xml = z.read("documentproperties.xml").decode("utf-8", errors="replace")
                    m_code = re.search(r'<entry key="uyapdogrulamakodu">([^<]+)</entry>', p_xml)
                    if m_code:
                        data["dogrulama_kodu"] = m_code.group(1).strip()
                except Exception:
                    pass

            if "content.xml" in names:
                xml_text = z.read("content.xml").decode("utf-8", errors="replace")
                
                # 1. Mahkeme / Birim
                m_mahkeme = re.search(r'T\.C\.\s+([^\n\r\t]+?)(?:\s{2,}|\t|\n|Duruşma|ESAS|Esas|DOSYA|Karar)', xml_text)
                if m_mahkeme:
                    data["mahkeme"] = clean_text(m_mahkeme.group(1))

                # 2. Esas No
                m_esas = re.search(r'(?:ESAS\s*NO|DOSYA\s*NO|TALİMAT\s*NO|SAYI)\s*[:\s]+([0-9]{4}\s*/\s*[0-9]+(?:\s*(?:Talimat|D\.İş|Esas))?)', xml_text, re.IGNORECASE)
                if m_esas:
                    data["esas_no"] = clean_text(m_esas.group(1))

                # 3. Karar No
                m_karar = re.search(r'KARAR\s*NO\s*[:\s]+([0-9]{4}\s*/\s*[0-9]+)', xml_text, re.IGNORECASE)
                if m_karar:
                    data["karar_no"] = clean_text(m_karar.group(1))

                # 4. Duruşma Tarihi
                m_dt = re.search(r'(?:DURUŞMA\s*TARİHİ|Duruşma\s*Tar(?:ihi)?|CELSE\s*TARİHİ)\s*[:\s]+([0-9]{1,2}[./][0-9]{1,2}[./][0-9]{4})', xml_text, re.IGNORECASE)
                if m_dt:
                    data["durusma_tarihi"] = clean_text(m_dt.group(1)).replace("/", ".")

                # 5. Celse No
                m_celse = re.search(r'CELSE\s*NO\s*[:\s]+([0-9]+)', xml_text, re.IGNORECASE)
                if m_celse:
                    data["celse_no"] = clean_text(m_celse.group(1))

                # 6. Bağlantılı İlk Derece Dosyası (BAM / Yargıtay)
                m_ilk = re.search(r'İNCELENEN\s+KARARIN\s+MAHKEMESİ\s*:\s*([^\n\r\t]+)[\s\S]*?NUMARASI\s*:\s*([0-9]{4}\s*/\s*[0-9]+)', xml_text, re.IGNORECASE)
                if m_ilk:
                    data["baglantili_dosya"] = format_lower_court_slug(m_ilk.group(1), m_ilk.group(2))

                # 7. Hakim & Katip
                m_hakim = re.search(r'(?:HAKİM|BAŞKAN)\s*[:\t\s]+([^\n\r\t]+)', xml_text, re.IGNORECASE)
                if m_hakim:
                    data["hakim"] = clean_text(m_hakim.group(1))
                m_katip = re.search(r'KATİP\s*[:\t\s]+([^\n\r\t]+)', xml_text, re.IGNORECASE)
                if m_katip:
                    data["katip"] = clean_text(m_katip.group(1))

                # 8. Müvekkil ve Karşı Taraf Tespiti
                txt_upper = tr_upper(xml_text)
                if "CAN KIZILYAR" in txt_upper:
                    # Gelişmiş taraf bloğu taraması
                    party_blocks = re.findall(
                        rf'({ROLE_REGEX})\s*(?:\([^)]*\))?\s*[:\t\-]+\s*([A-ZÇĞİÖŞÜa-zçğıöşü0-9\s\.\-]{{3,50}}?)(?:\s*-\s*[0-9]{{11}}|\s*TC|\s*Vekili|\s*Vekilleri|\s*Müdaf|\n|\r|\t)',
                        xml_text,
                        re.IGNORECASE
                    )
                    found_client = None
                    for r_role, r_name in party_blocks:
                        clean_n = clean_party_name(r_name)
                        if not clean_n or "BARO" in clean_n.upper() or "VEKİL" in clean_n.upper():
                            continue
                        # Can Kızılyar bu rolün vekili mi?
                        idx = xml_text.find(r_name)
                        if idx != -1:
                            sub_text = txt_upper[idx : idx + 450]
                            if "CAN KIZILYAR" in sub_text:
                                found_client = clean_n
                                data["muvekkil"] = clean_n
                                data["muvekkil_rol"] = tr_upper(r_role)
                                break

                    if not found_client:
                        m_inline = re.search(
                            r'(Sanık|Davacı|Davalı|Katılan|Müşteki|Borçlu|Alacaklı)\s+([A-ZÇĞİÖŞÜ ]{3,35})\s+[\s\S]{0,120}?(?:müdafisi|müdafi|vekili|vekilleri)\s+(?:Av\.?\s*)?CAN\s+KIZILYAR',
                            xml_text,
                            re.IGNORECASE
                        )
                        if m_inline:
                            data["muvekkil"] = clean_party_name(m_inline.group(2))
                            data["muvekkil_rol"] = tr_upper(m_inline.group(1))

                    if not data["muvekkil"]:
                        m_multi = re.search(
                            r'(Davacı|Davalı|Sanık)\s+([A-ZÇĞİÖŞÜa-zçğıöşü ]{3,35})\s*-\s*[0-9]{11}[\s\S]{0,150}?(?:Vekili|Vekilleri)\s+Av\.?\s*CAN\s+KIZILYAR',
                            xml_text,
                            re.IGNORECASE
                        )
                        if m_multi:
                            data["muvekkil"] = clean_party_name(m_multi.group(2))
                            data["muvekkil_rol"] = tr_upper(m_multi.group(1))

                    # Karşı Taraf Tespiti
                    for r_role, r_name in party_blocks:
                        clean_n = clean_party_name(r_name)
                        if clean_n and clean_n != data["muvekkil"] and "BARO" not in clean_n.upper() and "VEKİL" not in clean_n.upper():
                            data["karsi_taraf"] = clean_n
                            break

                # 9. Tebligat / Mazbata ve UETS Bilgileri
                t_lower = tr_lower(xml_text)
                is_uets = (
                    "uets" in t_lower
                    or "elektronik tebligat" in t_lower
                    or "delil kodu" in t_lower
                    or "pttkep" in t_lower
                )
                if is_uets:
                    data["is_uets"] = True
                    data["tebligat_turu"] = "UETS Elektronik"
                    m_delil = re.search(r'(?:Delil\s*No|Delil\s*Numarası|İşlem\s*ID|UETS\s*No|Delil\s*Kodu)\s*[:\s]+([0-9a-zA-Z\-_]{8,35})', xml_text, re.IGNORECASE)
                    if m_delil:
                        data["ptt_barkod"] = m_delil.group(1).strip()
                    m_tarih = re.search(r'(?:Ulaşma|İletim|Postalanma|Gönderim)\s*(?:Zamanı|Tarihi)?\s*[:\s]+([0-9]{1,2}[./\-][0-9]{1,2}[./\-][0-9]{4})', xml_text, re.IGNORECASE)
                    if m_tarih:
                        try:
                            from tebligat_yoneticisi import calculate_uets_legal_date
                            h_tarih, h_not = calculate_uets_legal_date(m_tarih.group(1))
                            data["hukuki_teblig_tarihi"] = h_tarih
                            data["yasal_sure_notu"] = h_not
                        except Exception:
                            pass
                    data["teblig_sonuc"] = "UETS-Teblig-Edildi"
                else:
                    data["tebligat_turu"] = "Fiziki PTT"
                    m_ptt = re.search(r'\b([A-Z]{2}[0-9]{9}[A-Z]{2}|KP[0-9]{11}|[0-9]{13})\b', xml_text)
                    if m_ptt:
                        data["ptt_barkod"] = m_ptt.group(1).strip()

                m_muh = re.search(r'(?:Muhatap|Kime|Tebliğ\s*Edilen|Tebliğ\s*Çıkarılan|Sayın|Alıcı)\s*[:\-]?\s*([A-ZÇĞİÖŞÜa-zçğıöşü\s]{3,40}?)(?:\n|\r|\t|TC|T\.C|\-|,|UETS)', xml_text, re.IGNORECASE)
                if m_muh:
                    data["muhatap"] = clean_party_name(m_muh.group(1))

                # Tebliğ Durumu / Sonucu Tespiti
                if not is_uets:
                    if any(k in t_lower for k in ("21/2", "21. madde", "mernis 21")):
                        data["teblig_sonuc"] = "Teblig-Mernis-21-2"
                    elif any(k in t_lower for k in ("muhtara teslim", "mahalle muhtar")):
                        data["teblig_sonuc"] = "Teblig-Muhtar"
                    elif any(k in t_lower for k in ("bizzat tebliğ", "kendisine tebliğ", "bizzat teslim")):
                        data["teblig_sonuc"] = "Teblig-Bizzat"
                    elif any(k in t_lower for k in ("vekiline tebliğ", "vekiline teslim", "avukatına tebliğ")):
                        data["teblig_sonuc"] = "Teblig-Vekile"
                    elif any(k in t_lower for k in ("bila tebliğ", "iade", "adreste tanınmıyor", "taşınmış", "adres yetersiz", "teslim edilemedi")):
                        data["teblig_sonuc"] = "Iade-Edildi"
                    elif "tebliğ edildi" in t_lower or "teblig edildi" in t_lower or "teslim edildi" in t_lower:
                        data["teblig_sonuc"] = "Teblig-Edildi"
                    elif "dağıtımda" in t_lower or "sevk edildi" in t_lower:
                        data["teblig_sonuc"] = "Dagitimda"

    except Exception:
        pass

    return data

def update_udf_properties(udf_path: Path, meta: dict) -> bool:
    if not zipfile.is_zipfile(udf_path):
        return False

    try:
        with zipfile.ZipFile(udf_path, "r") as zin:
            entries = {name: zin.read(name) for name in zin.namelist()}

        orig_xml = entries.get("documentproperties.xml", b"").decode("utf-8", errors="replace")
        props = {}
        for m in re.finditer(r'<entry key="([^"]+)">([\s\S]*?)</entry>', orig_xml):
            props[m.group(1)] = m.group(2)

        field_mappings = [
            ("mahkeme", meta.get("mahkeme")),
            ("dosya_no", meta.get("dosya_no")),
            ("karar_no", meta.get("karar_no")),
            ("durusma_tarihi", meta.get("durusma_tarihi")),
            ("celse_no", meta.get("celse_no")),
            ("baglantili_dosya", meta.get("baglantili_dosya")),
            ("muvekkil", meta.get("muvekkil")),
            ("muvekkil_rol", meta.get("muvekkil_rol")),
            ("karsi_taraf", meta.get("karsi_taraf")),
            ("muhatap", meta.get("muhatap")),
            ("ptt_barkod", meta.get("ptt_barkod")),
            ("teblig_sonuc", meta.get("teblig_sonuc")),
            ("avukat", "Av. CAN KIZILYAR"),
            ("evrak_turu", meta.get("evrak_turu")),
            ("evrak_tarihi", meta.get("evrak_tarihi")),
            ("evrak_id", meta.get("evrak_id")),
            ("hakim", meta.get("hakim")),
            ("katip", meta.get("katip")),
            ("zenginlestirme_zamani", dt.datetime.now().isoformat(timespec="seconds")),
        ]

        for k, v in field_mappings:
            if v:
                esc_v = str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', '&quot;')
                props[k] = esc_v

        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE properties SYSTEM "http://java.sun.com/dtd/properties.dtd">',
            '<properties>'
        ]
        for k, v in props.items():
            xml_lines.append(f'<entry key="{k}">{v}</entry>')
        xml_lines.append('</properties>')
        new_xml = "\n".join(xml_lines).encode("utf-8")

        entries["documentproperties.xml"] = new_xml

        tmp_udf = udf_path.with_suffix(udf_path.suffix + ".tmp_meta")
        with zipfile.ZipFile(tmp_udf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for name, content in entries.items():
                zout.writestr(name, content)

        tmp_udf.replace(udf_path)
        return True
    except Exception:
        tmp_udf = udf_path.with_suffix(udf_path.suffix + ".tmp_meta")
        if tmp_udf.exists():
            tmp_udf.unlink(missing_ok=True)
        return False

def build_enriched_filename(
    tarih: str,
    birim: str,
    dosya_no: str,
    muvekkil: str,
    evrak_turu: str,
    karar_no: str = "",
    durusma_tarihi: str = "",
    celse_no: str = "",
    baglantili_dosya: str = "",
    muhatap: str = "",
    ptt_barkod: str = "",
    teblig_sonuc: str = "",
    hukuki_teblig_tarihi: str = "",
    is_uets: bool = False,
    evrak_id: str = "",
    ext: str = ".udf"
) -> str:
    parts = []

    # 1. Tarih (YYYY-MM-DD)
    t_clean = sanitize_name_component(tarih, 10)
    parts.append(t_clean)

    # 2. Birim Adı
    b_clean = sanitize_name_component(birim, 45)
    parts.append(b_clean)

    # 3. Dosya No
    dno_clean = sanitize_name_component(dosya_no.replace('/', '-'), 20)
    parts.append(dno_clean)

    # 4. Müvekkil
    if muvekkil:
        m_clean = sanitize_name_component(muvekkil, 30)
        parts.append(f"Muv-{m_clean}")

    # 5. Evrak Türü
    et_clean = sanitize_name_component(evrak_turu, 30)
    parts.append(et_clean)

    # 6. Ek Detaylar (Karar No, Bağlantılı Dosya, Celse, DT, Muhatap, PTT, Sonuç)
    extras = []
    if karar_no:
        k_clean = sanitize_name_component(karar_no.replace('/', '-'), 15)
        extras.append(f"K{k_clean}")
    if baglantili_dosya:
        extras.append(sanitize_name_component(baglantili_dosya, 35))
    if celse_no:
        extras.append(f"Celse-{celse_no}")
    if durusma_tarihi:
        dt_clean = sanitize_name_component(durusma_tarihi.replace('/', '.'), 12)
        t_dots = t_clean.replace('-', '.')
        t_ymd = '.'.join(t_clean.split('-')[::-1]) if '-' in t_clean else t_clean
        if dt_clean != t_dots and dt_clean != t_ymd and dt_clean != t_clean:
            extras.append(f"DT{dt_clean}")
    if muhatap:
        extras.append(f"Muhatap-{sanitize_name_component(muhatap, 25)}")
    if ptt_barkod:
        tag = "UETS" if is_uets else "PTT"
        extras.append(f"{tag}-{sanitize_name_component(ptt_barkod, 18)}")
    if hukuki_teblig_tarihi:
        extras.append(f"TebligT-{sanitize_name_component(hukuki_teblig_tarihi.replace('/', '.'), 12)}")
    if teblig_sonuc:
        extras.append(sanitize_name_component(teblig_sonuc, 25))

    if extras:
        parts.append("_".join(extras))

    # 7. Evrak ID
    if evrak_id:
        clean_eid = str(evrak_id).replace('"', '').replace("'", "").strip()
        if not clean_eid.startswith("evrak_") and not clean_eid.startswith("islem_"):
            clean_eid = f"evrak_{clean_eid}"
        parts.append(clean_eid)

    base_stem = "_".join([p for p in parts if p])
    return f"{base_stem}{ext}"

def main():
    parser = argparse.ArgumentParser(description="UYAP Evrak Zenginleştirme ve Akıllı Yeniden Adlandırma")
    parser.add_argument("--dir", default=str(DEFAULT_DOWNLOAD_DIR), help="İndirilen UYAP evrakları ana dizini")
    parser.add_argument("--history", default=str(DEFAULT_HISTORY_FILE), help="indirme_gecmisi.json dosyası yolu")
    parser.add_argument("--dry-run", action="store_true", help="Diskte değişiklik yapmadan simülasyon çıktısı üretir")
    args = parser.parse_args()

    base_dir = Path(args.dir)
    history_path = Path(args.history)

    if not base_dir.exists():
        print(f"[x] Hedef dizin bulunamadı: {base_dir}")
        sys.exit(1)

    print("=" * 75)
    print("  UYAP Evrak Zenginleştirme & Akıllı Yeniden Adlandırma Motoru")
    print("=" * 75)
    print(f"[*] Hedef Dizin    : {base_dir}")
    print(f"[*] Geçmiş Dosyası : {history_path}")
    print(f"[*] Mod            : {'SİMÜLASYON (--dry-run)' if args.dry_run else 'CANLI İCRA (Tüm Dosyalar Güncellenecek)'}\n")

    history = {}
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
            print(f"[✓] {len(history)} adet geçmiş indirme kaydı yüklendi.")
        except Exception as e:
            print(f"[!] Geçmiş dosyası okunamadı: {e}")

    # 1. AŞAMA: Tüm UDF'leri tara ve Dosya-Müvekkil Haritasını Oluştur (Pass 1)
    all_udfs = [Path(p) for p in glob.glob(str(base_dir / "**/*.udf"), recursive=True)]
    print(f"[*] Toplam {len(all_udfs)} adet UDF evrakı taranıyor...")

    case_clients = defaultdict(set)
    udf_extracted_cache = {}

    for idx, udf in enumerate(all_udfs, start=1):
        meta = extract_meta_from_udf(udf)
        udf_extracted_cache[str(udf)] = meta

        c_court = meta.get("mahkeme")
        c_case = meta.get("esas_no")

        if not c_case:
            for part in udf.parts:
                m_case = re.search(r'^([0-9]{4}_[0-9]+)', part)
                if m_case:
                    c_case = m_case.group(1).replace('_', '/')
                    break

        if not c_court:
            for i, part in enumerate(udf.parts):
                if re.search(r'^[0-9]{4}_[0-9]+', part) and i > 0:
                    c_court = udf.parts[i - 1]
                    break

        if c_court and c_case and meta.get("muvekkil"):
            norm_k = (tr_upper(clean_text(c_court)), clean_text(c_case))
            case_clients[norm_k].add(meta["muvekkil"])

    print(f"[✓] 1. Aşama Tamamlandı: {len(case_clients)} dava dosyası için müvekkil eşleştirmesi yapıldı.\n")

    # 2. AŞAMA: Zenginleştirme ve Yeniden Adlandırma (Pass 2)
    renamed_count = 0
    updated_meta_count = 0
    path_remap = {}

    for idx, udf in enumerate(all_udfs, start=1):
        meta = udf_extracted_cache.get(str(udf)) or {}
        
        doc_court = meta.get("mahkeme")
        doc_case = meta.get("esas_no")

        for i, part in enumerate(udf.parts):
            if re.search(r'^[0-9]{4}_[0-9]+', part):
                if not doc_case:
                    doc_case = part.replace('_', '/')
                if not doc_court and i > 0:
                    doc_court = udf.parts[i - 1]
                break

        fname = udf.name
        m_fn = re.search(r'^([0-9]{4}-[0-9]{2}-[0-9]{2})_([^_]+)_([0-9]{4}_[0-9]+)_(.*?)_([0-9]+)\.udf$', fname)
        doc_tarih = ""
        doc_evrak_turu = ""
        doc_id = ""

        if m_fn:
            doc_tarih = m_fn.group(1)
            if not doc_court:
                doc_court = m_fn.group(2)
            if not doc_case:
                doc_case = m_fn.group(3).replace('_', '/')
            doc_evrak_turu = m_fn.group(4)
            doc_id = m_fn.group(5)
        else:
            m_fn2 = re.search(r'^([0-9]{4}-[0-9]{2}-[0-9]{2})_(.*?)_([0-9]+)\.udf$', fname)
            if m_fn2:
                doc_tarih = m_fn2.group(1)
                doc_evrak_turu = m_fn2.group(2)
                doc_id = m_fn2.group(3)

        if not doc_tarih:
            m_dt = re.search(r'([0-9]{4}-[0-9]{2}-[0-9]{2})', fname)
            doc_tarih = m_dt.group(1) if m_dt else dt.date.today().strftime("%Y-%m-%d")

        if not doc_evrak_turu:
            doc_evrak_turu = "Evrak"

        doc_muvekkil = meta.get("muvekkil", "")
        if not doc_muvekkil and doc_court and doc_case:
            norm_k = (tr_upper(clean_text(doc_court)), clean_text(doc_case))
            cls = case_clients.get(norm_k)
            if cls:
                doc_muvekkil = next(iter(cls))

        meta["mahkeme"] = doc_court or meta.get("mahkeme", "")
        meta["dosya_no"] = doc_case or meta.get("dosya_no", "")
        meta["evrak_tarihi"] = doc_tarih
        meta["evrak_turu"] = doc_evrak_turu
        meta["evrak_id"] = doc_id
        meta["muvekkil"] = doc_muvekkil

        new_name = build_enriched_filename(
            tarih=doc_tarih,
            birim=doc_court or "Birim",
            dosya_no=doc_case or "DosyaNo",
            muvekkil=doc_muvekkil,
            evrak_turu=doc_evrak_turu,
            karar_no=meta.get("karar_no", ""),
            durusma_tarihi=meta.get("durusma_tarihi", ""),
            celse_no=meta.get("celse_no", ""),
            baglantili_dosya=meta.get("baglantili_dosya", ""),
            evrak_id=doc_id,
            ext=".udf"
        )

        new_udf_path = udf.parent / new_name

        if not args.dry_run:
            if update_udf_properties(udf, meta):
                updated_meta_count += 1

        if udf.name != new_name:
            if not args.dry_run:
                try:
                    udf.rename(new_udf_path)
                    
                    old_pdf = udf.with_suffix(".pdf")
                    new_pdf = new_udf_path.with_suffix(".pdf")
                    if old_pdf.exists():
                        old_pdf.rename(new_pdf)

                    path_remap[str(udf)] = str(new_udf_path)
                    if old_pdf.exists():
                        path_remap[str(old_pdf)] = str(new_pdf)

                    renamed_count += 1
                except Exception as e:
                    print(f"[!] Hata: {udf.name} -> {new_name}: {e}")
            else:
                renamed_count += 1
                if idx <= 15:
                    print(f"[{idx}] {udf.name}\n  --> {new_name}\n")

    # 3. AŞAMA: indirme_gecmisi.json ve indeks dosyalarını güncelle
    if not args.dry_run and history:
        # Normalize path_remap with realpath
        real_remap = {os.path.realpath(k): v for k, v in path_remap.items()}
        for k, v in path_remap.items():
            real_remap[k] = v

        # Build ID index of disk files
        id_to_file = {}
        for p in glob.glob(str(base_dir / "**/*"), recursive=True):
            if os.path.isfile(p):
                m_id = re.search(r'(?:evrak_|islem_|_)([0-9]+)\.(?:udf|pdf|png|jpe?g)$', os.path.basename(p), re.IGNORECASE)
                if m_id:
                    doc_id = m_id.group(1)
                    if doc_id not in id_to_file or p.endswith('.udf'):
                        id_to_file[doc_id] = p

        updated_history_entries = 0
        for k, v in history.items():
            old_p = v.get("path", "")
            real_old = os.path.realpath(old_p) if old_p else ""
            if old_p in real_remap:
                v["path"] = real_remap[old_p]
                updated_history_entries += 1
            elif real_old in real_remap:
                v["path"] = real_remap[real_old]
                updated_history_entries += 1
            elif not os.path.exists(old_p):
                m_id = re.search(r'([0-9]+)$', k)
                doc_id = m_id.group(1) if m_id else None
                if not doc_id:
                    m_id2 = re.search(r'_([0-9]+)\.(?:udf|pdf)$', old_p)
                    if m_id2:
                        doc_id = m_id2.group(1)
                if doc_id and doc_id in id_to_file:
                    v["path"] = id_to_file[doc_id]
                    updated_history_entries += 1

        try:
            history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[✓] indirme_gecmisi.json güncellendi: {updated_history_entries} kayıt yeni dosya yollarına bağlandı.")
        except Exception as e:
            print(f"[!] indirme_gecmisi.json yazılamadı: {e}")

    print("\n" + "=" * 75)
    print("  İŞLEM SONUCU")
    print("=" * 75)
    print(f"[✓] Taranan Toplam UDF Evrakı  : {len(all_udfs)} adet")
    print(f"[✓] Yeniden Adlandırılan Evrak : {renamed_count} adet")
    if not args.dry_run:
        print(f"[✓] Metadata İşlenen UDF Sayısı: {updated_meta_count} adet")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    main()
