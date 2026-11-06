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
NAME = f"CanEditor v{VERSION} — Havelsan ile sayfa uyumu, cetvel, e-imza takınca donma ve mobil imza düzeltmeleri"

BODY = f"""# CanEditor v{VERSION}

## 🌟 v3.16.0 ile Gelenler (Havelsan ile Sayfa Uyumu, Cetvel, E-İmza Takınca Donma, Mobil İmza Doğrulaması)

Sayfa düzeni, cihazdaki 13 gerçek UYAP belgesinin **Havelsan UYAP Editörü'nün kendi çevrim motoruyla** üretilen PDF'leriyle sayfa sayfa karşılaştırılarak ayarlandı.

1. **Satır aralığı Havelsan ile aynı:** Havelsan (Java Swing) satır yüksekliğini tam sayıya yuvarlar ve `LineSpacing` payını satır yüksekliğinin tam sayı katı olarak ekler. Eskiden `1 + LineSpacing` oranı kullanılıyordu ve 12 pt'lik satırlar 16 pt yerine 14 pt çıkıyordu; bu yüzden sayfalar kayıyordu. Aynı satırdaki farklı puntolar artık satırı büyütmüyor.
2. **Paragraf boşlukları toplanıyor:** Havelsan önceki paragrafın alt boşluğu ile sonrakinin üst boşluğunu toplar. Tarayıcı ise bunları çakıştırıyordu; her paragraf geçişinde birkaç punto kayıyordu.
3. **Altbilgi, karekod ve sayfa numarası:** Sayfa numarası UDF'deki biçimle yazılıyor ("1/2", "Sayfa:1/10"; Arial 11). Karekod Havelsan boyutunda (51 pt) ve sağ altta; doğrulama metni çizginin altında. Logolu altbilgide logo, sayfa numarası ve karekod aynı satırda. Gövdenin alt sınırı gerçek altbilgi yüksekliğine göre hesaplanıyor; eski formül alt kenar boşluğu geniş belgelerde 1. sayfayı ~40 pt erken kesiyordu.
4. **Sayfa sonunda paragraf bölme:** Sonraki sayfadan geri çekilen paragraf, sığan satırları kadar bölünüyor. Belge sonundaki boş satırlar yeni sayfa açmıyor.
5. **Cetvel:** Asılı girinti üçgeni sol girinti dikdörtgeninin altında kalıp kullanılamıyordu. Artık ▼ ilk satır, ▲ asılı girinti ve ▭ tüm paragraf ayrı ayrı tutulup sürüklenebiliyor.
6. **Android: e-imza takınca yeni pencere ve donma giderildi:** Editör ekranı her USB takılışında yeni bir kopyasını açıyordu (`USB_DEVICE_ATTACHED` filtresi). Kaldırıldı; editör tek örnek çalışıyor.
7. **Android: USB izin sonucu artık alınıyor:** Android 14'te izin/tak-çıkar alıcısı bayraksız kaydedildiği için sessizce başarısız oluyordu. İzin `PendingIntent`'i de değiştirilemez (immutable) olduğundan sistem sonucu yazamıyordu. İkisi düzeltildi ve izin penceresinin tekrar tekrar açılması önlendi.
8. **Mobil imza:** UYAP'tan gelen içerik gömülü imza Havelsan gibi ayrılıyor (`detachContent`). İmza belgeyle doğrulanmadan **asla kaydedilmiyor**; eşleşmezse ayrıntılı tanı veriliyor.

> **Bilinen sınırlar:** Android'de USB akıllı kartla (AKİS, ArkSigner) imza, kartın kendine özgü komut setini gerektirir ve henüz gerçek kartla doğrulanmadı; Android'de **mobil imza**, masaüstünde **kart ile e-imza** (PKCS#11) önerilir. Çok sayfalı belgelerde bazı sayfa sonları Havelsan'dan hâlâ ±1 satır farklı olabilir.

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
