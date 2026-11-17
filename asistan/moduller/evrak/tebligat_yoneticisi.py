#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır. / All rights reserved.
"""
UYAP Tebligat ve UETS Yönetim & Raporlama Modülü
===============================================
1. Fiziki PTT Tebligat Mazbataları:
   - PTT Barkod numarası (RR...TR, KP..., 13 haneli) tespiti
   - Muhatap (Tebliğ çıkarılan kişi/kurum) tespiti
   - Tebliğ sonucu (Mernis 21/2, Muhtara, Bizzat, Vekile, İade vb.) tespiti
2. UETS (Ulusal Elektronik Tebligat Sistemi):
   - UETS Delil Kodu / İşlem ID ve UETS Adresi tespiti
   - 7201 sayılı Tebligat Kanunu Madde 7/a f.4 kuralına göre yasal tebliğ tarihi hesabı:
     "Elektronik yolla tebligat, muhatabın elektronik adresine ulaştığı tarihi izleyen
      beşinci günün sonunda yapılmış sayılır."
3. Kalıcı ve Detaylı CSV Veritabanı:
   - İndirilen tüm fiziki ve elektronik tebligatları detaylı olarak Excel uyumlu (UTF-8-BOM)
     tebligat_takip_listesi.csv kütüğüne işler.
"""

import os
import re
import csv
import zipfile
import datetime as dt
from pathlib import Path

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
PRIMARY_CSV_PATH = DEFAULT_DOWNLOAD_DIR / "TEBLIGATLAR" / "tebligat_takip_listesi.csv"
BACKUP_CSV_PATH = BASE_DIR / "tebligat_takip_listesi.csv"

CSV_HEADERS = [
    "Sıra_No",
    "Gonderim_Tarihi",
    "Tebligat_Turu",
    "Birim_Adi",
    "Dosya_No",
    "Dosyadaki_Muvekkil",
    "Muvekkil_Rolu",
    "Tebligat_Muhatabi",
    "Muhatap_Rolu",
    "Barkod_Veya_Delil_No",
    "Hukuki_Teblig_Tarihi",
    "Teblig_Durumu_Sonuc",
    "Yasal_Sure_Hesabi_Notu",
    "Evrak_Adi",
    "Evrak_Id",
    "Dosya_Yolu",
    "Detayli_Icerik_Ozeti",
]


def tr_lower(text: str) -> str:
    if not text:
        return ""
    return (
        str(text)
        .replace("İ", "i")
        .replace("I", "ı")
        .replace("Ş", "ş")
        .replace("Ğ", "ğ")
        .replace("Ü", "ü")
        .replace("Ö", "ö")
        .replace("Ç", "ç")
        .lower()
    )


def tr_upper(text: str) -> str:
    if not text:
        return ""
    return (
        str(text)
        .replace("i", "İ")
        .replace("ı", "I")
        .replace("ş", "Ş")
        .replace("ğ", "Ğ")
        .replace("ü", "Ü")
        .replace("ö", "Ö")
        .replace("ç", "Ç")
        .upper()
    )


def calculate_uets_legal_date(ulasma_date_str: str) -> tuple[str, str]:
    """
    Tebligat Kanunu m.7/a f.4:
    'Elektronik yolla tebligat, muhatabın elektronik adresine ulaştığı tarihi izleyen
     beşinci günün sonunda yapılmış sayılır.'
    (YHGK 2021/484 E. uyarınca muhatabın erken okuması süreyi öne çekmez).
    """
    if not ulasma_date_str:
        return "", ""
    d_clean = ulasma_date_str.strip().replace('/', '-').replace('.', '-')
    dt_obj = None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            dt_obj = dt.datetime.strptime(d_clean[:10], fmt)
            break
        except Exception:
            pass
    if not dt_obj:
        return "", ""

    teblig_obj = dt_obj + dt.timedelta(days=5)
    teblig_str = teblig_obj.strftime("%Y-%m-%d")
    teblig_tr = teblig_obj.strftime("%d.%m.%Y")
    note = f"TK m.7/a: {dt_obj.strftime('%d.%m.%Y')} iletim + 5 gün = {teblig_tr} tebliğ sayıldı"
    return teblig_str, note


def clean_party_name(name: str) -> str:
    if not name:
        return ""
    name = re.sub(r'\bT\.?C\.?\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\b(?:Vekilleri|Vekili|Müdafii|Müdafi|Adına|Tarafından)\b.*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[,:;\-_/\(\)]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    words = name.split()
    if not words:
        return ""
    if len(words) == 1:
        return words[0].upper()
    return ' '.join([w.capitalize() for w in words[:-1]] + [words[-1].upper()])


def parse_tebligat_meta(content_text: str, evrak_adi: str = "", evrak_tarihi: str = "") -> dict:
    """
    Tebligat metninden (UDF XML veya PDF metni) ve evrak adından
    tüm tebligat detaylarını (UETS veya Fiziki PTT) çıkarır.
    """
    raw = content_text or ""
    t_lower = tr_lower(raw)
    ea_lower = tr_lower(evrak_adi)

    is_uets = (
        "uets" in ea_lower
        or "elektronik tebligat" in ea_lower
        or "e-tebligat" in ea_lower
        or "uets" in t_lower
        or "elektronik tebligat" in t_lower
        or "delil kodu" in t_lower
        or "pttkep" in t_lower
    )

    data = {
        "is_tebligat": True,
        "tebligat_turu": "UETS Elektronik" if is_uets else "Fiziki PTT",
        "muhatap": "",
        "muhatap_rolu": "",
        "barkod_veya_delil_no": "",
        "uets_adresi": "",
        "gonderim_tarihi": evrak_tarihi or "",
        "hukuki_teblig_tarihi": "",
        "yasal_sure_notu": "",
        "teblig_sonuc": "",
        "ozet_icerik": "",
    }

    # 1. Muhatap Tespiti
    m_muh = re.search(
        r'(?:Muhatap|Kime|Tebliğ\s*Edilen|Tebliğ\s*Çıkarılan|Alıcı|Sayın)\s*[:\-]?\s*([A-ZÇĞİÖŞÜa-zçğıöşü0-9\s\.\-]{3,45}?)(?:\n|\r|\t|TC|T\.C|\-|,|UETS)',
        raw,
        re.IGNORECASE
    )
    if m_muh:
        data["muhatap"] = clean_party_name(m_muh.group(1))

    # Muhatap Rolü Tespiti (Davalı, Davacı, Tanık, Bilirkişi vb.)
    m_rol = re.search(r'\b(Davalı|Davacı|Sanık|Katılan|Müşteki|Tanık|Bilirkişi|İhbar\s*Olunan|Üçüncü\s*Şahıs|Borçlu|Alacaklı)\b', raw, re.IGNORECASE)
    if m_rol:
        data["muhatap_rolu"] = m_rol.group(1).capitalize()

    # 2. UETS Özel Çıkarımları
    if is_uets:
        # Delil No / İşlem ID
        m_delil = re.search(r'(?:Delil\s*No|Delil\s*Numarası|İşlem\s*ID|UETS\s*No|Delil\s*Kodu)\s*[:\s]+([0-9a-zA-Z\-_]{8,35})', raw, re.IGNORECASE)
        if m_delil:
            data["barkod_veya_delil_no"] = m_delil.group(1).strip()
        else:
            # Yedek UETS işlem no
            m_uets_num = re.search(r'\b(20[2-3][0-9][0-9]{8,18})\b', raw)
            if m_uets_num:
                data["barkod_veya_delil_no"] = m_uets_num.group(1).strip()

        # UETS Adresi
        m_adr = re.search(r'([0-9]{5}\-[0-9]{5}\-[0-9]{5}|[a-zA-Z0-9\._\-]+@hs01\.kep\.tr)', raw)
        if m_adr:
            data["uets_adresi"] = m_adr.group(1).strip()

        # İletim / Ulaşma Tarihi
        m_tarih = re.search(r'(?:Ulaşma|İletim|Postalanma|Gönderim)\s*(?:Zamanı|Tarihi)?\s*[:\s]+([0-9]{1,2}[./\-][0-9]{1,2}[./\-][0-9]{4})', raw, re.IGNORECASE)
        ulasma_t = m_tarih.group(1) if m_tarih else evrak_tarihi
        if ulasma_t:
            data["gonderim_tarihi"] = ulasma_t
            h_tarih, h_not = calculate_uets_legal_date(ulasma_t)
            data["hukuki_teblig_tarihi"] = h_tarih
            data["yasal_sure_notu"] = h_not
            data["teblig_sonuc"] = "UETS-Teblig-Edildi"
        else:
            data["teblig_sonuc"] = "UETS-Iletildi"

        data["ozet_icerik"] = f"UETS Elektronik Tebligat ({data['uets_adresi'] or 'Adres Belirtilmemiş'}). {data['yasal_sure_notu']}"

    # 3. Fiziki PTT Özel Çıkarımları
    else:
        # PTT Barkod Numarası (RR...TR, KP..., 13 hane)
        m_ptt = re.search(r'\b([A-Z]{2}[0-9]{9}[A-Z]{2}|KP[0-9]{11}|[0-9]{13})\b', raw)
        if m_ptt:
            data["barkod_veya_delil_no"] = m_ptt.group(1).strip()

        # Teslim Tarihi
        m_teslim_t = re.search(r'(?:Tebliğ\s*Tarihi|Teslim\s*Tarihi|Tebellüğ\s*Tarihi)\s*[:\s]+([0-9]{1,2}[./\-][0-9]{1,2}[./\-][0-9]{4})', raw, re.IGNORECASE)
        if m_teslim_t:
            data["hukuki_teblig_tarihi"] = m_teslim_t.group(1).replace('/', '.')
        elif evrak_tarihi:
            data["hukuki_teblig_tarihi"] = evrak_tarihi

        # Tebliğ Durumu / Şerhi
        if any(k in t_lower for k in ("21/2", "21. madde", "mernis 21")):
            data["teblig_sonuc"] = "Teblig-Mernis-21-2"
            data["yasal_sure_notu"] = "Tebligat Kanunu 21/2 uyarınca MERNİS adresinde muhtara tebliğ edildi."
        elif any(k in t_lower for k in ("muhtara teslim", "mahalle muhtar", "muhtar")):
            data["teblig_sonuc"] = "Teblig-Muhtar"
            data["yasal_sure_notu"] = "Adreste bulunamaması sebebiyle muhtara teslim edildi, 2 no'lu ihbarname kapıya yapıştırıldı."
        elif any(k in t_lower for k in ("bizzat tebliğ", "kendisine tebliğ", "bizzat teslim")):
            data["teblig_sonuc"] = "Teblig-Bizzat"
            data["yasal_sure_notu"] = "Muhatabın bizzat kendisine tebliğ edildi."
        elif any(k in t_lower for k in ("vekiline tebliğ", "vekiline teslim", "avukatına tebliğ")):
            data["teblig_sonuc"] = "Teblig-Vekile"
            data["yasal_sure_notu"] = "Muhatabın vekiline tebliğ edildi."
        elif any(k in t_lower for k in ("bila tebliğ", "iade", "adreste tanınmıyor", "taşınmış", "adres yetersiz", "teslim edilemedi")):
            data["teblig_sonuc"] = "Iade-Bila-Teblig"
            data["yasal_sure_notu"] = "Muhatap adreste tanınmadığından / taşındığından evrak bila ikmal iade döndü."
        elif any(k in t_lower for k in ("tebliğ edildi", "teblig edildi", "teslim edildi")):
            data["teblig_sonuc"] = "Teblig-Edildi"
            data["yasal_sure_notu"] = "Tebligat teslim edildi."
        elif "dağıtımda" in t_lower or "sevk edildi" in t_lower:
            data["teblig_sonuc"] = "Dagitimda"
            data["yasal_sure_notu"] = "PTT dağıtım sürecinde."
        else:
            data["teblig_sonuc"] = "Tebligat-Mazbatasi"

        data["ozet_icerik"] = f"Fiziki PTT Tebligatı (Barkod: {data['barkod_veya_delil_no'] or 'Okunamadı'}). Sonuç: {data['teblig_sonuc']}."

    return data


def record_tebligat_to_csv(item: dict, csv_paths: list = None) -> bool:
    """
    Bir tebligat kaydını Excel uyumlu UTF-8-BOM CSV takip dosyasına ekler veya günceller.
    Mükerrer satır oluşmasını engeller.
    """
    if csv_paths is None:
        PRIMARY_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        BACKUP_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        csv_paths = [PRIMARY_CSV_PATH, BACKUP_CSV_PATH]

    for p in csv_paths:
        try:
            target = Path(p)
            target.parent.mkdir(parents=True, exist_ok=True)

            existing_rows = []
            evrak_id_set = set()
            if target.exists():
                try:
                    with open(target, "r", encoding="utf-8-sig") as f:
                        reader = csv.DictReader(f, delimiter=";")
                        for row in reader:
                            existing_rows.append(row)
                            eid = row.get("Evrak_Id") or ""
                            if eid:
                                evrak_id_set.add(eid)
                except Exception:
                    pass

            target_eid = str(item.get("Evrak_Id") or item.get("evrak_id") or "").strip()

            row_data = {
                "Sıra_No": str(len(existing_rows) + 1),
                "Gonderim_Tarihi": item.get("Gonderim_Tarihi") or item.get("gonderim_tarihi") or item.get("tarih") or "",
                "Tebligat_Turu": item.get("Tebligat_Turu") or item.get("tebligat_turu") or "",
                "Birim_Adi": item.get("Birim_Adi") or item.get("birim_adi") or "",
                "Dosya_No": item.get("Dosya_No") or item.get("dosya_no") or "",
                "Dosyadaki_Muvekkil": item.get("Dosyadaki_Muvekkil") or item.get("muvekkil") or "",
                "Muvekkil_Rolu": item.get("Muvekkil_Rolu") or item.get("muvekkil_rol") or "",
                "Tebligat_Muhatabi": item.get("Tebligat_Muhatabi") or item.get("muhatap") or "",
                "Muhatap_Rolu": item.get("Muhatap_Rolu") or item.get("muhatap_rolu") or "",
                "Barkod_Veya_Delil_No": item.get("Barkod_Veya_Delil_No") or item.get("barkod_veya_delil_no") or item.get("ptt_barkod") or "",
                "Hukuki_Teblig_Tarihi": item.get("Hukuki_Teblig_Tarihi") or item.get("hukuki_teblig_tarihi") or "",
                "Teblig_Durumu_Sonuc": item.get("Teblig_Durumu_Sonuc") or item.get("teblig_sonuc") or "",
                "Yasal_Sure_Hesabi_Notu": item.get("Yasal_Sure_Hesabi_Notu") or item.get("yasal_sure_notu") or "",
                "Evrak_Adi": item.get("Evrak_Adi") or item.get("evrak_adi") or item.get("evrak_turu") or "",
                "Evrak_Id": target_eid,
                "Dosya_Yolu": item.get("Dosya_Yolu") or item.get("path") or "",
                "Detayli_Icerik_Ozeti": item.get("Detayli_Icerik_Ozeti") or item.get("ozet_icerik") or "",
            }

            if target_eid and target_eid in evrak_id_set:
                # Mevcut satırı güncelle
                for idx, r in enumerate(existing_rows):
                    if r.get("Evrak_Id") == target_eid:
                        row_data["Sıra_No"] = r.get("Sıra_No", str(idx + 1))
                        existing_rows[idx] = row_data
                        break
            else:
                existing_rows.append(row_data)

            # 1. SQLite veritabanına kaydet (uyap_katalog.db)
            try:
                import evrak_katalog as ek
                kat = ek.Katalog()
                kat.upsert_tebligat(row_data)
            except Exception:
                pass

            # 2. Excel uyumlu CSV kütüğüne yaz
            with open(target, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS, delimiter=";")
                writer.writeheader()
                for idx, r in enumerate(existing_rows, start=1):
                    r["Sıra_No"] = str(idx)
                    writer.writerow(r)

        except Exception as e:
            print(f"[!] Tebligat CSV kaydı yazılırken hata ({p}): {e}")
            return False

    return True


def extract_text_from_file(file_path: Path) -> str:
    """UDF (zip) veya PDF dosyasından metin çıkarır."""
    p = Path(file_path)
    if not p.exists():
        return ""

    if p.suffix.lower() == ".udf":
        try:
            with zipfile.ZipFile(p, "r") as z:
                if "content.xml" in z.namelist():
                    return z.read("content.xml").decode("utf-8", errors="replace")
        except Exception:
            pass

    elif p.suffix.lower() == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(p))
            texts = []
            for page in reader.pages:
                txt = page.extract_text()
                if txt:
                    texts.append(txt)
            return "\n".join(texts)
        except Exception:
            pass

    return ""


def scan_and_sync_all_tebligats(base_dir: Path = DEFAULT_DOWNLOAD_DIR) -> int:
    """
    Arşivdeki tüm klasörleri tarar, tebligat ve UETS dosyalarını tespit eder,
    detaylarını çıkarır ve tebligat_takip_listesi.csv dosyasını baştan sona günceller.
    """
    print("=" * 70)
    print("  UYAP Tüm Tebligatlar & UETS Takip Kütüğü Senkronizasyonu")
    print("=" * 70)

    if not base_dir.exists():
        print(f"[!] Dizin bulunamadı: {base_dir}")
        return 0

    candidates = []
    for f in base_dir.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() not in (".pdf", ".udf"):
            continue
        fn_lower = tr_lower(f.name)
        parent_lower = tr_lower(str(f.parent))
        if any(w in fn_lower or w in parent_lower for w in ("tebligat", "teblig", "mazbata", "uets")):
            candidates.append(f)

    print(f"[*] Taranan toplam tebligat/UETS evrakı: {len(candidates)} adet")
    recorded = 0

    # Dosyaları tekilleştir (Aynı evrakın hem UDF hem PDF kopyası varsa PDF'i tercih et)
    evrak_grouped = {}
    for f in candidates:
        m_id = re.search(r'evrak_([0-9]+)', f.name)
        key = m_id.group(1) if m_id else f.stem
        if key not in evrak_grouped or f.suffix.lower() == ".pdf":
            evrak_grouped[key] = f

    for ev_key, f_path in evrak_grouped.items():
        text = extract_text_from_file(f_path)
        meta = parse_tebligat_meta(text, evrak_adi=f_path.name)

        # Dosya adı parçalarından birim ve dosya no çıkarımı
        parts = f_path.name.split('_')
        tarih = parts[0] if len(parts) >= 1 and re.match(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}', parts[0]) else ""
        birim = parts[1] if len(parts) >= 2 else ""
        dosya_no = parts[2] if len(parts) >= 3 else ""

        muv_match = re.search(r'Muv-([^_]+)', f_path.name)
        muv = muv_match.group(1) if muv_match else ""

        item_row = {
            "Gonderim_Tarihi": tarih or meta.get("gonderim_tarihi", ""),
            "Tebligat_Turu": meta.get("tebligat_turu", "Fiziki PTT"),
            "Birim_Adi": birim,
            "Dosya_No": dosya_no,
            "Dosyadaki_Muvekkil": muv,
            "Muvekkil_Rolu": "",
            "Tebligat_Muhatabi": meta.get("muhatap", ""),
            "Muhatap_Rolu": meta.get("muhatap_rolu", ""),
            "Barkod_Veya_Delil_No": meta.get("barkod_veya_delil_no", ""),
            "Hukuki_Teblig_Tarihi": meta.get("hukuki_teblig_tarihi", ""),
            "Teblig_Durumu_Sonuc": meta.get("teblig_sonuc", ""),
            "Yasal_Sure_Hesabi_Notu": meta.get("yasal_sure_notu", ""),
            "Evrak_Adi": f_path.name,
            "Evrak_Id": ev_key,
            "Dosya_Yolu": str(f_path),
            "Detayli_Icerik_Ozeti": meta.get("ozet_icerik", ""),
        }

        if record_tebligat_to_csv(item_row):
            recorded += 1

    print(f"[✓] Başarıyla {recorded} adet tebligat/UETS kaydı CSV kütüğüne işlendi.")
    print(f"[*] CSV Dosyası: {PRIMARY_CSV_PATH}")
    return recorded


if __name__ == "__main__":
    scan_and_sync_all_tebligats()
