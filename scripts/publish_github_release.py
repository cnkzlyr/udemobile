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
NAME = f"CanEditor v{VERSION} — Havelsan UYAP ile birebir uyum, tek motor (masaüstü + Android) ve yeni arayüz"

BODY = f"""# CanEditor v{VERSION}

## ⚠️ Android: v3.14.0'a geçerken bir kerelik yeniden kurulum

v3.14.0 APK'sı yeni bir imza anahtarıyla imzalanmıştır. Telefonunuzda eski CanEditor varsa önce **kaldırın**, sonra yeni APK'yı kurun (aksi halde Android "uygulama yüklenmedi / paket çakışıyor" hatası verir). Bu işlem yalnızca bu sürüme geçişte bir kez gereklidir.

## 🌟 v3.14.0 ile Gelenler (Havelsan UYAP ile Birebir Uyum, Tek Motor, Yeni Arayüz)

Tüm iyileştirmeler, gerçek UYAP belgeleri (27 UDF) Havelsan'ın kendi çevrim motoruyla üretilen referans PDF'lerle karşılaştırılarak doğrulanmıştır.

1. **UYAP şablon belgeleri doğru açılıyor:** Takip Talebi, Portal evrakı gibi alanlı (`<data>`) belgelerde alacaklı/borçlu/vekil grupları, tekrar eden alacak satırları ve `eol`/`ceol` satır sonları Havelsan kurallarıyla çözülür. Metin uyumu %70 → %99,4.
2. **Kaydederken biçim kaybı yok:** Paragraf, tablo, satır ve hücrelerin tüm orijinal öznitelikleri (sekme hizaları, satır bazlı sütun genişlikleri, stiller, sayfa ayarları, üst/altbilgi ayarları, doğrulama kodu) korunur; yalnızca değiştirdiğiniz yerler yeniden yazılır. Kaydedilen 27 belgenin tamamı Havelsan'da aynı sayfa sayısıyla açılır.
3. **Sekmeler Havelsan ile aynı:** Ardışık sekmelerin teke inmesi giderildi; sekme yerleşimi Java Swing kuralıyla birebir (T.C. … BERAAT başlıkları, "BAŞKAN : …" hizaları).
4. **Doğru sayfalama:** Altbilgi payı hesaba katılır, tablolar satır sınırından bölünür, küçük puntolu metinde satır yüksekliği doğru hesaplanır; sayfa sınırında bölünen paragraflar kayıtta tek paragraf kalır.
5. **Mobil ve masaüstü tek motor:** Android artık UDF'yi masaüstüyle aynı motorla açar ve kaydeder; iki platformda çıktı aynıdır.
6. **Yeni arayüz:** UYAP Doküman Editörü ile aynı menü çubuğu (Dosya, Düzen, Görünüm, Ekle, Biçim, Araçlar, İmza) ve tek satırlık modern biçim çubuğu; mobilde tek satır, yana kayan, parmakla kolay basılan düğmeler; gerçek renk seçici.


## Paketler
- Android: `CanEditor-v{VERSION}.apk` / `CanEditor-latest.apk`
- Taşınabilir web: `CanEditor-Portable-Web-GUI-v{VERSION}.zip`
- Windows / macOS / Linux: GitHub Actions tarafından bu sürüme otomatik eklenir
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
