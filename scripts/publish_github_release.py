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
NAME = f"CanEditor v{VERSION} — %100 Havelsan UYAP Kaynak Koruma Motoru, Komut Paleti, Belge Anahattı, Odak & Gece Modu"

BODY = f"""# CanEditor v{VERSION}

## 🌟 v{VERSION} ile Gelenler (%100 Havelsan UYAP Kaynak Koruma Motoru & Modern Hukuk Çalışma Alanı)

### 1. 🏛️ %100 Havelsan UYAP Uyumluluk ve Kaynak Koruma Motoru (`Layer-1 + Layer-2 XML Span Splicer`)
- **Dokunulmadan Kaydedilen Belgelerde %100 Bayt-Bayt Birebirlik:** Açılan herhangi bir `.udf` belgesi (imzalı kararlar, Yargıtay ilamları, `<data>` şablonlu evraklar dahil) düzenlenmeden kaydedildiğinde `content.xml`, `documentproperties.xml` ve `sign.sgn` **%100 bayt-bayt birebir** korunur.
- **Kısmi Düzenlenen Belgelerde Katman-1 & Katman-2 Kaynak Koruma:** Belgedeki bir paragraf veya cümle düzenlendiğinde, dokunulmayan tüm paragraflar, tablolar, çoklu `<header>` / `<footer>` blokları, `<styles>` tanımları, `<field>`, `<space>`, `<tab>` etiketleri ve hassas kayan nokta girintileri (`SpaceAbove="5.67"`, `FirstLineIndent="35.4375"`, `Hanging="151.42857"`) orijinal XML kaynağından birebir korunur; yalnızca düzenlenen metin parçasının `startOffset` ve `length` öznitelikleri yerinde güncellenir.
- **Sıfır Yapay Biçim Bozulması:** Sabit satır yüksekliğinin (`data-udf-pitch`) kaydetme sırasında yapay `LineSpacing="12.85"` olarak yazılması ve sayfa bölme (`flow.js` / `editor.js`) sırasında `SpaceBelow` (`data-orig-mb`) niteliğinin silinmesi tamamen giderildi.
- **Bölünen Paragraf ve Sekme Seçimi Düzeltmeleri:** Aynı sayfaya düşen bölünmüş paragraf parçalarının birleştirilmemesi sorunu ve `.udf-tab-space` içeren satırlarda `Home` → `Shift+End` tuşlarının 9 paragraf birden seçmesi sorunu giderildi.

### 2. ✨ Modern Hukuk Çalışma Alanı Özellikleri
- **⚡ Komut Paleti (`Ctrl+K` / `⌘K`):** Dosya, UYAP/Havelsan, e-imza, dilekçe şablonları, AI formatlama ve görünüm komutlarına anında arama ile erişim.
- **📑 Belge Anahattı & Hukuki Bölüm Gezgini:** Mahkeme başlığı, Dosya/Esas/Karar No, Davacı/Davalı/Sanık, Konu, Açıklamalar, Hukuki Sebepler, Deliller, Sonuç ve İstem / Hüküm bölümlerini otomatik algılayan ve tek tıkla ilgili sayfaya/paragrafa kaydıran yan çekmece.
- **🏛️ Havelsan UYAP %100 Uyumluluk Raporu & Canlı Doğrulama:** Üst çubuktaki `🏛️ UYAP %100` rozetiyle belgenin kaynak koruma istatistiklerini ve tek tıkla çalışan canlı ZIP/XML doğrulama testini görüntüleme.
- **🧘 Odak Modu (Zen) & 🌙 Gece Modu / 📜 Gece Kağıdı:** Kaydedilen `.udf` dosyalarının iç stillerini hiçbir şekilde etkilemeyen, salt CSS tabanlı gece arayüzü, koyu kağıt ve dikkat dağıtmayan tam ekran yazım modu.
- **🔐 Chrome E-İmza Köprüsü, Yerel E-İmza & Gömülü Java Korundu:** Chrome UYAP/Celse e-imza köprüsü (`Adalet E-İmza`), editör içi Akıllı Kart (PKCS#11 / CCID), Mobil İmza ve gömülü OpenJDK 14 çalışma ortamı eksiksiz korundu.

## 📦 Paketler
- Android (CanEditor): `CanEditor-v{VERSION}.apk` / `CanEditor-latest.apk`
- Android (Orijinal UYAP Editör): `UYAP-Editor-v{VERSION}.apk` / `UYAP-Editor-latest.apk`
- Taşınabilir Web: `CanEditor-Portable-Web-GUI-v{VERSION}.zip`
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
