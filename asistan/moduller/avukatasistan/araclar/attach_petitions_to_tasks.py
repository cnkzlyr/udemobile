#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TickTick Görevlerine Hazırlanan Dilekçeleri İliştirici
- Mevcut kullanıcı notlarını veya var olan ekleri ASLA silmez.
- Her görevin içeriğine dilekçe özetini, hukuki dayanaklarını ve telefon/cihazdaki dosya yollarını ekler.
"""

import sys, os, requests, json
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # proje kökü (araç araclar/ altında)
sys.path.insert(0, HERE)
from config import CONFIG, PROJECT_IDS

H = {"Authorization": f"Bearer {CONFIG['TICKTICK_TOKEN']}", "Content-Type": "application/json"}
B = CONFIG["TICKTICK_API_BASE"]

PETITION_ATTACHMENTS = [
    {
        "tid": "6ace1edc8f086d8c22f168d6",
        "proj": "AsliyeHukukMahkemesi",
        "title_keyword": "Oltu 2. Asliye Hukuk - 2025/48 Esas",
        "block": """
---
### ⚖️ HAZIRLANAN DİLEKÇE & DOSYA EKLERİ:
- 📄 **UYAP Formatı (.UDF):** `/sdcard/Download/Hazirlanan_Dilekceler/Oltu2AsH_2025_48_Bilirkisi_Raporuna_Itiraz.udf`
- 📝 **Düzenlenebilir (.ODT):** `/sdcard/Download/Hazirlanan_Dilekceler/Oltu2AsH_2025_48_Bilirkisi_Raporuna_Itiraz.odt`
- 📑 **Önizleme (.PDF):** `/sdcard/Download/Hazirlanan_Dilekceler/Oltu2AsH_2025_48_Bilirkisi_Raporuna_Itiraz.pdf`

> 📌 **Dilekçe Özeti & Strateji:**
> - 01.10.2026 tarihli rapordaki %35 davacı kusuruna itiraz edildi.
> - Oltu Orman İşletmesi 393 nolu bölmedeki ağaç kesim ve nakil işinin fiili sevk ve idaresinin dava dışı Ömer Faruk Aktürk'te olduğu vurgulandı.
> - Müteveffa işçi Orhan Sonsuz'un tanık Remzi Yücel'in açık ikazlarına rağmen traktörü dik yamaçta zorlayarak ağır kusuruyla kazaya yol açtığı ve illiyet bağını kestiği belirtildi.
> - Dosyanın üniversite öğretim üyelerinden (İTÜ veya KTÜ) oluşacak yeni bir heyete tevdii talep edildi.
"""
    },
    {
        "tid": "6ad49cc58f08baf7cbd1fdcd",
        "proj": "AsliyeCezaMahkemesi",
        "title_keyword": "Ankara 73. Asliye Ceza - 2026/142 Esas",
        "block": """
---
### ⚖️ HAZIRLANAN DİLEKÇE & DOSYA EKLERİ:
- 📄 **UYAP Formatı (.UDF):** `/sdcard/Download/Hazirlanan_Dilekceler/Ankara73AsC_2026_142_Mutalaaya_Karsi_Beyan.udf`
- 📝 **Düzenlenebilir (.ODT):** `/sdcard/Download/Hazirlanan_Dilekceler/Ankara73AsC_2026_142_Mutalaaya_Karsi_Beyan.odt`
- 📑 **Önizleme (.PDF):** `/sdcard/Download/Hazirlanan_Dilekceler/Ankara73AsC_2026_142_Mutalaaya_Karsi_Beyan.pdf`

> 📌 **Dilekçe Özeti & Strateji:**
> - İddia makamının sanık Abdulkerim Abdullatif Hemod Zhiri'nin TCK 86/2, 86/3-e (silahla kasten yaralama) uyarınca cezalandırılması yönündeki mütalaasına iştirak edildi.
> - Müvekkildeki darp kati hekim raporuyla sabit olup, sanığın pişmanlık göstermeyen tavırları gözetilerek cezasında TCK 62 takdiri indirim uygulanmaksızın üst hadden cezalandırılması ve TCK 53 uyarınca güvenlik tedbirlerine hükmedilmesi talep edildi.
"""
    },
    {
        "tid": "6acf7a0c8f0876e81c516c5a",
        "proj": "ÇocukMahkemesi",
        "title_keyword": "Ankara 2. Çocuk Mahkemesi - 2025/385 Esas",
        "block": """
---
### ⚖️ HAZIRLANAN DİLEKÇE & DOSYA EKLERİ:
- 📄 **UYAP Formatı (.UDF):** `/sdcard/Download/Hazirlanan_Dilekceler/Ankara2Cocuk_2025_385_Istinaf_Basvurusu.udf`
- 📝 **Düzenlenebilir (.ODT):** `/sdcard/Download/Hazirlanan_Dilekceler/Ankara2Cocuk_2025_385_Istinaf_Basvurusu.odt`
- 📑 **Önizleme (.PDF):** `/sdcard/Download/Hazirlanan_Dilekceler/Ankara2Cocuk_2025_385_Istinaf_Basvurusu.pdf`

> 📌 **Dilekçe Özeti & Strateji:**
> - Mahkemenin 13.10.2026 tarihli Ceza Verilmesine Yer Olmadığı (CVYO) kararına karşı BAM Ceza Dairesi nezdinde istinaf kanun yoluna başvuruldu.
> - Usul yönünden: Mağdur Nesrin Tektek'in bizzat dinlenilmesinden vazgeçilerek savunma hakkının kısıtlandığı vurgulandı.
> - Esas yönünden: Kişiyi hürriyetinden yoksun kılma gibi ağır ve planlı bir suçta Adli Tıp Şube'nin tek hekim raporunun hükme esas alınamayacağı, ATK İhtisas Kurulu veya Üniversite Çocuk Psikiyatrisi heyet raporu alınmadan verilen kararın bozulması talep edildi.
"""
    },
    {
        "tid": "6ad899018f0899b8c562b52a",
        "proj": "AsliyeHukukMahkemesi",
        "title_keyword": "Oltu 3. Asliye Hukuk - 2026/24 Esas (Derkenar)",
        "block": """
---
### ⚖️ HAZIRLANAN DİLEKÇE & DOSYA EKLERİ:
- 📄 **UYAP Formatı (.UDF):** `/sdcard/Download/Hazirlanan_Dilekceler/Oltu3AsH_2026_24_Derkenar_Talebi.udf`
- 📝 **Düzenlenebilir (.ODT):** `/sdcard/Download/Hazirlanan_Dilekceler/Oltu3AsH_2026_24_Derkenar_Talebi.odt`
- 📑 **Önizleme (.PDF):** `/sdcard/Download/Hazirlanan_Dilekceler/Oltu3AsH_2026_24_Derkenar_Talebi.pdf`

> 📌 **Dilekçe Özeti:**
> - Oltu İcra Dairesi'nin 2026/345 Esas sayılı dosyasına ibraz edilmek üzere karara karşı tehiri icra talepli istinaf yoluna başvurulduğunu gösterir derkenar yazısının verilmesi talep edildi.
"""
    },
    {
        "tid": "6ad899038f0899b8c562b56e",
        "proj": "AsliyeHukukMahkemesi",
        "title_keyword": "Oltu İcra Dairesi - 2026/345 Esas (Mehil Vesikası)",
        "block": """
---
### ⚖️ HAZIRLANAN DİLEKÇE & DOSYA EKLERİ:
- 📄 **UYAP Formatı (.UDF):** `/sdcard/Download/Hazirlanan_Dilekceler/OltuIcra_2026_345_Mehil_Vesikasi_Talebi.udf`
- 📝 **Düzenlenebilir (.ODT):** `/sdcard/Download/Hazirlanan_Dilekceler/OltuIcra_2026_345_Mehil_Vesikasi_Talebi.odt`
- 📑 **Önizleme (.PDF):** `/sdcard/Download/Hazirlanan_Dilekceler/OltuIcra_2026_345_Mehil_Vesikasi_Talebi.pdf`

> 📌 **Dilekçe Özeti:**
> - İİK m. 36 uyarınca teminat karşılığı Bölge Adliye Mahkemesi'nden tehiri icra kararı getirilmek üzere 60 gün mehil vesikası tanzim edilmesi ve icra takip işlemlerinin durdurulması talep edildi.
"""
    }
]

def apply_attachments():
    print("🚀 Hazırlanan dilekçeler TickTick görevlerine iliştiriliyor...")
    success = 0
    for item in PETITION_ATTACHMENTS:
        tid = item["tid"]
        proj = item["proj"]
        pid = PROJECT_IDS[proj]

        r = requests.get(f"{B}/project/{pid}/task/{tid}", headers=H, timeout=10)
        if r.status_code != 200:
            print(f"⚠️ Görev çekilemedi ({tid}): {r.status_code}")
            continue

        d = r.json()
        current_content = d.get("content") or ""

        # Eğer zaten iliştirilmişse mükerrer yapma
        if "HAZIRLANAN DİLEKÇE & DOSYA EKLERİ" in current_content:
            print(f"ℹ️ Zaten iliştirilmiş: [{proj}] {item['title_keyword']}")
            success += 1
            continue

        new_content = current_content + item["block"]
        payload = {
            "id": tid,
            "projectId": pid,
            "content": new_content
        }

        r_post = requests.post(f"{B}/task/{tid}", headers=H, json=payload, timeout=10)
        if r_post.status_code == 200:
            print(f"✅ Başarıyla iliştirildi -> [{proj}] {item['title_keyword']}")
            success += 1
        else:
            print(f"❌ Güncellenemedi ({tid}): {r_post.status_code}")

    print(f"\n🎉 Tamamlandı: {success}/{len(PETITION_ATTACHMENTS)} görev güncellendi.")

if __name__ == "__main__":
    apply_attachments()
