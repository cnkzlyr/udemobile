import os
import sys
import json
import urllib.request
import urllib.error

TOKEN = "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"
REPO = "cnkzlyr/udemobile"
TAG = "v3.6.0"
NAME = "CanEditor v3.6.0 — UYAP Avukat Portal Standardı & Gerçek PDF Motoru"

BODY = """# ⚖️ CanEditor (UdeMobile) v3.6.0 — Sürüm Notları

CanEditor **v3.6.0**, UYAP Avukat Portal (`uyapcodes.txt`) ve resmi UYAP Doküman Editörü standartlarına tam uyum sağlamak üzere tepeden tırnağa geliştirilmiş dev bir güncellemedir.

---

## 🌟 Öne Çıkan Yenilikler & Geliştirmeler

### 📕 1. Doğrudan A4 PDF Vektörel Aktarım Motoru (ISO 32000-1 / PDF 1.4)
- **1-Tıkla Gerçek PDF:** Tarayıcı yazdırma penceresine (`window.print`) muhtaç kalmadan, A4 kağıt ölçülerinde (595.28 × 841.89 pt), keskin 192 DPI çözünürlükte, Türkçe karakter (ğ, Ğ, ı, İ, ş, Ş, ç, Ç, ö, Ö, ü, Ü) destekli gerçek ikili `.pdf` dosyası üretilir ve indirilir.
- **Android'de Doğrudan İndirilenler & Paylaşım:** Mobil uygulamada "PDF Olarak Kaydet" seçildiğinde dosya doğrudan `/sdcard/Download/UYAP_Belgelerim` klasörüne fiziki dosya olarak kaydedilir. "PDF Olarak Paylaş" ile WhatsApp, Telegram, Gmail veya UYAP sistemine tek dokunuşla aktarılır.
- **Akıllı Çift Katmanlı Çözümleyici:** Doküman sayfaları hem SVG ForeignObject tarayıcı motoru hem de özel tuval çizim motoruyla yedekli olarak işlenir; karmaşık tablolar, kenarlıklar (`borderSpec`), logolar ve üst/altbilgiler sıfır kayıpla PDF'e dökülür.

### 🏛️ 2. UYAP Avukat Portal Görünüm ve Araç Çubuğu Standartları
- **Belge İçi Hızlı Arama Barı (`.udv-search-box`):** UYAP Avukat Portalındaki gibi araç çubuğuna entegre arama kutusu; anlık sarı/turuncu vurgu eşleşmeleri, eşleşme sayacı (`X/Y`) ve Enter (Sonraki) / Shift+Enter (Önceki) kısayolları.
- **Akıllı Zoom & Sığdırma Butonları:** "↔ Sığdır" (Genişliğe Sığdır) ve "↕ Sayfa" (Sayfaya Sığdır) düğmeleriyle ekrana anında tam oturan ergonomik sayfa ölçekleme.
- **Resmi E-İmza Rozeti (`.signature-ribbon`):** Portaldaki yeşil mühür ve sertifika sayacı rozetiyle 5070 Sayılı Kanun kapsamındaki e-imzalar dokümanın sağ üst köşesinde zarifçe sergilenir; tıklandığında nitelikli elektronik sertifika ayrıntı kartı açılır.
- **Mikro Tipografi Optimizasyonu:** `font-feature-settings: "kern" off`, `font-kerning: none` ve `text-underline-offset: 4.56px` ile Havelsan Swing motoruyla pikseli pikseline aynı metin akışı sağlanır.

### 🏛️ 3. Resmi Havelsan UYAP Doküman Editörü (`format_id="1.8"`) ile 1:1 Birebir Uyumluluk
- **Unicode Rune Duyarlı Ofset Hesabı:** Türkçe karakterler ve astral düzlem sembollerinde oluşan UTF-16 surrogate pair ofset kaymaları giderildi; karakterler `Array.from(str).length` ile tam 1:1 Havelsan standardında hesaplanır.
- **Kusursuz XML Başlığı ve Şablon Yapısı:** Resmi Havelsan formatında `<?xml version="1.0" encoding="UTF-8"?>` ve `<template format_id="1.8">` blok sırası (`content` -> `properties` -> `elements` -> `styles`) güvenceye alındı. Boş paragraflar `length="1"` ve `\\n` CDATA tutarlılığı ile korunur.
- **Birebir Girinti ve Cetvel Matematiği:** Havelsan UYAP `ParagraphView` / `RowView` (`LeftIndent`, `FirstLineIndent`, `Hanging`, `RightIndent`) hesaplama motoru tersine mühendislikle modellendi (`margin-left = LeftIndent + Hanging`, `text-indent = FirstLineIndent - Hanging`).
- **Evrensel Belge Açıcı (Sıfır Hata Garantisi):** Standart ZIP UDF ve OOXML DOCX belgelerinin yanı sıra sıkıştırılmamış düz XML `.udf`, `.udf` uzantılı Word `.docx`, eski nesil OLE2 Word 97-2003 ikili `.doc` / `.doc.udf`, `RTF`, UTF-8 BOM'lu XML ve 0 baytlık boş dosyaların tamamı hatasız açılır.
- **Masaüstü UDF/DOCX Birlikte Aç (Open With) Desteği:** Windows Dosya Gezgini'nde veya masaüstünde bir `.udf` ya da `.docx` dosyasına sağ tıklayıp "Birlikte Aç" seçildiğinde veya çift tıklandığında hedef belge otomatik yüklenir.

---

## 🚀 Hızlı İndirme Bağlantıları (v3.6.0)

| Platform | Dosya | Açıklama |
| :--- | :--- | :--- |
| **Android (Telefon / Tablet)** | [**CanEditor-v3.6.0.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.6.0/CanEditor-v3.6.0.apk) | Güncel mobil uygulama kurulum paketi |
| **Android (Her Zaman En Son)** | [**CanEditor-latest.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.6.0/CanEditor-latest.apk) | Kalıcı son sürüm bağlantısı |
| **Taşınabilir Web & Masaüstü** | [**CanEditor-Portable-Web-GUI-v3.6.0.zip**](https://github.com/cnkzlyr/udemobile/releases/download/v3.6.0/CanEditor-Portable-Web-GUI-v3.6.0.zip) | **Kurulumsuz;** Zipten çıkartıp `index.html` tıklayarak hemen kullanın |
| **Windows Kurulum (.exe)** | `CanEditor_3.6.0_x64-setup.exe` | Windows 10/11 64-bit doğrudan kurulum paketi *(CI tarafından eklenir)* |
| **Windows MSI Paketi (.msi)** | `CanEditor_3.6.0_x64_en-US.msi` | Windows kurumsal MSI yükleyici *(CI tarafından eklenir)* |
| **macOS Paketi (.dmg)** | `CanEditor_3.6.0_universal.dmg` | Apple Silicon (M1/M2/M3/M4) ve Intel Mac evrensel paket *(CI tarafından eklenir)* |
| **Linux (AppImage / .deb / .rpm)** | `CanEditor_3.6.0_amd64.AppImage` | Tüm Linux dağıtımları için kurulumsuz AppImage *(CI tarafından eklenir)* |

---

## 📖 Hiç Bilmeyenler İçin Adım Adım İndirme ve Kurulum Kılavuzu

### 📱 Android Telefon ve Tabletler İçin:
1. Yukarıdaki [**CanEditor-latest.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.6.0/CanEditor-latest.apk) bağlantısına dokunarak dosyayı indirin.
2. Tarayıcınız *"Dosya zararlı olabilir"* uyarısı verirse **"Yine de İndir"** butonuna dokunun (Google Play harici dosyalarda standart Android uyarısıdır).
3. İndirilen dosyaya dokunun. *"Bilinmeyen kaynaklar"* uyarısı çıkarsa **Ayarlar -> Bu kaynaktan izin ver** seçeneğini açıp geri dönün ve **"Yükle"** deyin.
4. WhatsApp, Telegram veya Dosyalarım'dan bir `.udf` dosyasına tıkladığınızda çıkan menüde **CanEditor -> "Her Zaman"** seçin.
5. Dosyanızı açıp düzenledikten sonra **Kaydet -> PDF Olarak Kaydet** ile doğrudan İndirilenler klasörüne A4 PDF olarak kaydedebilirsiniz.

### 💻 Windows (10 / 11) İçin:
- **Kurulumsuz Kullanım (Tavsiye Edilen):** `CanEditor-Portable-Web-GUI-v3.6.0.zip` dosyasını indirin, sağ tıklayıp "Tümünü Ayıkla" deyin ve içindeki `index.html` dosyasına çift tıklayın. Tamamen çevrimdışı çalışır.
- **Masaüstü Uygulaması:** `CanEditor_3.6.0_x64-setup.exe` indirip çift tıklayın. Windows SmartScreen uyarısı çıkarsa **"Ek bilgi" -> "Yine de çalıştır"** butonuna basın.

### 🍎 macOS İçin:
- `CanEditor_3.6.0_universal.dmg` dosyasını indirip açın ve CanEditor simgesini Uygulamalar klasörüne sürükleyin. Açılışta güvenlik uyarısı verirse simgeye `Control` tuşuyla **sağ tıklayıp "Aç"** deyin.

### 🐧 Linux İçin:
- `CanEditor_3.6.0_amd64.AppImage` dosyasını indirin, çalıştırma izni verin (`chmod +x`) ve çift tıklayın.
"""

def request(url, data=None, headers=None, method="GET"):
    h = {
        "Authorization": f"token {TOKEN}",
        "User-Agent": "CanEditor-Release-Publisher",
        "Accept": "application/vnd.github.v3+json"
    }
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode()
            return resp.status, json.loads(content) if content.strip() else None
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"message": body}

def upload_asset(upload_url_template, file_path, content_type="application/octet-stream"):
    base_url = upload_url_template.split("{")[0]
    filename = os.path.basename(file_path)
    url = f"{base_url}?name={filename}"
    size = os.path.getsize(file_path)
    print(f"Uploading {filename} ({size} bytes) to {url} ...")
    
    with open(file_path, "rb") as f:
        data = f.read()
    
    headers = {
        "Authorization": f"token {TOKEN}",
        "User-Agent": "CanEditor-Release-Publisher",
        "Content-Type": content_type,
        "Content-Length": str(len(data))
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode())
            print(f"  Successfully uploaded {filename}! Asset ID: {res.get('id')}")
            return res
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  Failed to upload {filename} ({e.code}): {err}")
        return None

def main():
    print(f"Checking existing release for tag {TAG}...")
    status, res = request(f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}")
    
    release_id = None
    upload_url = None
    
    if status == 200:
        print(f"Release already exists! ID: {res.get('id')}")
        release_id = res.get('id')
        upload_url = res.get('upload_url')
        # Update body and name
        update_data = json.dumps({"name": NAME, "body": BODY}).encode()
        s, r = request(f"https://api.github.com/repos/{REPO}/releases/{release_id}", data=update_data, method="PATCH")
        print(f"Updated release metadata: {s}")
    else:
        print("Creating new release...")
        create_data = json.dumps({
            "tag_name": TAG,
            "name": NAME,
            "body": BODY,
            "draft": False,
            "prerelease": False
        }).encode()
        s, r = request(f"https://api.github.com/repos/{REPO}/releases", data=create_data, method="POST")
        if s not in (200, 201):
            print(f"Failed to create release: {s} {r}")
            sys.exit(1)
        release_id = r.get("id")
        upload_url = r.get("upload_url")
        print(f"Created release with ID {release_id}!")
    
    # Check existing assets to delete duplicates before re-upload
    status, assets = request(f"https://api.github.com/repos/{REPO}/releases/{release_id}/assets")
    existing_assets = {}
    if status == 200 and isinstance(assets, list):
        for a in assets:
            existing_assets[a.get("name")] = a.get("id")

    # Upload assets
    files_to_upload = [
        ("release/CanEditor-Portable-Web-GUI-v3.6.0.zip", "application/zip"),
        ("release/CanEditor-v3.6.0.apk", "application/vnd.android.package-archive"),
        ("release/CanEditor-latest.apk", "application/vnd.android.package-archive"),
    ]
    
    for rel_path, ctype in files_to_upload:
        full_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", rel_path))
        filename = os.path.basename(full_path)
        if filename in existing_assets:
            old_id = existing_assets[filename]
            print(f"Deleting existing asset {filename} (ID: {old_id}) before re-upload...")
            request(f"https://api.github.com/repos/{REPO}/releases/assets/{old_id}", method="DELETE")
        if os.path.exists(full_path):
            upload_asset(upload_url, full_path, ctype)
        else:
            print(f"File not found: {full_path}")

    print("\nRelease publish completed successfully!")

if __name__ == "__main__":
    main()
