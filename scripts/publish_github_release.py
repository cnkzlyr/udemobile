import os
import sys
import json
import urllib.request
import urllib.error

import os
# Token koda yazılmaz: GITHUB_TOKEN ortam değişkeninden okunur.
TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    raise SystemExit("GITHUB_TOKEN ortam değişkeni gerekli")
REPO = "cnkzlyr/udemobile"

with open(os.path.join(os.path.dirname(__file__), "..", "package.json")) as f:
    VERSION = json.load(f)["version"]

TAG = f"v{VERSION}"
NAME = f"CanEditor v{VERSION} — Birleşik Hukuk Platformu, Termux'suz Asistan ve Çapraz Platform UYAP Editörü"

BODY = f"""# CanEditor v{VERSION} — Birleşik Hukuk Platformu

## 🌟 v{VERSION} ile Gelenler

### 1. 🛡️ Android Çökme Düzeltmesi (Yeni Belge & Belge Aç)
- **NetworkOnMainThread Giderildi:** Hukuk Asistanı arka plan servis denetimi ana iş parçacığından tamamen izole edilerek arka plan iş parçacığına taşındı. "Yeni Belge" ve "Belge Aç" butonlarına dokunulduğunda oluşan anlık çökme tamamen giderildi.
- **Android WebView Yerel Dosya Seçici Entegrasyonu:** Editör içindeki dosya açma eylemlerinde Android sistem dosya seçicisi (`onShowFileChooser`) devreye sokuldu.
- **Geriye Dönük Uyumluluk:** Android API 21+ cihazlar için dosya akış okumaları güvenceye alındı.

### 2. 🏛️ Birleşik Platform Mimarisi (Masaüstü, Android, Web)
- **Tek Uygulama (CanEditor):** Orijinal UYAP Editör karmaşası kaldırılarak tüm UYAP ve Hukuk Asistanı yetenekleri CanEditor çatısı altında birleştirildi.
- **UYAP Dosya Yönetim Merkezi:** Dava dosyaları, notlar, Google Drive eşleşmesi ve doğrudan Notion/TickTick aktarımı.
- **Resmî Havelsan JAR Dönüştürme Motoru:** Doğrudan Havelsan kütüphaneleriyle milimetrik UDF → PDF, ODT ve DOCX dönüştürme.
- **Google Drive Veritabanı İndeksi:** Yerel SQLite indeksleme, Türkçe-duyarsız arama ve otomatik esas numarası tespiti.
- **Notion & TickTick Canlı Entegrasyonu:** Görev takibi, duruşma ve tebligatların otomatik görev ve dava kartına dönüştürülmesi.
- **HAYFA Hukuk Bilgi Köprüsü:** Yargıtay İçtihat arama (tek tıkla dilekçeye ekleme), mevzuat, Resmî Gazete, haberler ve %100 çevrimdışı Adliye & IBAN rehberi.
- **7/7 Hukuk Hesaplayıcısı:** Vekâlet, Faiz, Harç, SMM, CMK, İnfaz (5275 s.K.) ve Ceza Artırım/İndirim (TCK m.61/62).

### 3. ⚙️ Gömülü Çalışma Ortamı (Termux'suz & Sürücüsüz)
- **Android:** Gömülü CPython 3.12 (aarch64) ve gömülü Java 21 ile Termux gerekmeden tek APK olarak çalışır.
- **Masaüstü (Windows / macOS / Linux):** Kurulum gerektirmeden arka planda çalışan görünmez tarayıcı ve e-İmza köprüsü.

## 📦 İndirme Bağlantıları
- **Android:** `CanEditor-v{VERSION}.apk` / `CanEditor-latest.apk`
- **Windows:** `CanEditor_{VERSION}_x64-setup.exe` (NSIS) / `CanEditor_{VERSION}_x64_en-US.msi` (MSI)
- **macOS:** `CanEditor_{VERSION}_universal.dmg` (Apple Silicon & Intel)
- **Linux:** `CanEditor_{VERSION}_amd64.AppImage` / `CanEditor_{VERSION}_amd64.deb` / `CanEditor-{VERSION}-1.x86_64.rpm`
- **Taşınabilir Web:** `CanEditor-Portable-Web-GUI-v{VERSION}.zip`
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
        print(f"Creating new release for {TAG}...")
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
        (f"release/CanEditor-Portable-Web-GUI-{TAG}.zip", "application/zip"),
        (f"release/CanEditor-{TAG}.apk", "application/vnd.android.package-archive"),
        ("release/CanEditor-latest.apk", "application/vnd.android.package-archive"),
        (f"release/UYAP-Editor-{TAG}.apk", "application/vnd.android.package-archive"),
        ("release/UYAP-Editor-latest.apk", "application/vnd.android.package-archive"),
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
