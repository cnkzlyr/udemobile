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
NAME = f"CanEditor v{VERSION} — Menü/arayüz düzeltmeleri, canlı sayfalama, tüm platformlarda e-imza & mobil imza, yeni PDF/TIFF/ODT motoru"

BODY = f"""# CanEditor v{VERSION}

## ⚠️ Android: v3.15.0'a geçerken bir kerelik yeniden kurulum

Önceki sürümler farklı derleme ortamlarında farklı imza anahtarlarıyla imzalanmıştı. v3.15.0'dan itibaren APK **sabit bir proje anahtarıyla** imzalanır; telefonunuzda eski CanEditor varsa bir kez **kaldırıp** yeni APK'yı kurun (aksi halde Android "paket çakışıyor" hatası verir). Sonraki güncellemeler kaldırmadan, üzerine kurulur.

## 🌟 v3.15.0 ile Gelenler (Arayüz Hataları, Canlı Sayfalama, Tüm Platformlarda Gerçek E-İmza / Mobil İmza, Yeni PDF·TIFF·ODT Motoru)

Tüm düzeltmeler otomatik tarayıcı testleriyle (masaüstü + mobil dokunmatik) ve **Havelsan UYAP Doküman Editörü 5.4.20** ile karşılaştırılarak doğrulanmıştır.

**Arayüz**
1. **Menüler artık üst üste binmiyor:** "Dosya > Yeni / Aç / Kaydet" öğeleri biçim çubuğunun ve cetvelin altında kalıp tıklanamıyordu (katman/z-index hatası). Menü çubuğu en üst katmana alındı.
2. **Alt menüler açılıyor:** "Farklı Kaydet / Paylaş / Yazdır" alt menüleri bir kez tıklandıktan sonra bir daha hiç açılmıyordu. Düzeltildi; dokunmatik ekranda tıklayınca açılır.
3. **Masaüstü kendini Android sanıyordu:** Masaüstü/Web sürümü sahte bir Android köprüsü yüzünden Android gibi davranıyordu (paylaşım, alt çubuk). Düzeltildi.
4. **Cetvel rakamları ("8 17 9") üst üste binmiyor**, dar ekranda alt durum çubuğu yüzen düğmenin üstüne çıkmıyor.
5. **Dosya > Yeni** artık gerçekten yeni belge açar (Ctrl+N); kaydedilmemiş değişiklik varsa sorar. Yeni belgede görünmeyen örnek üst bilgi UDF'ye yazılmıyor.

**Sayfalama ve kaydırma (Word gibi)**
6. **Yazarken yeni sayfa açılıyor:** Eskiden 1. sayfa dolunca yazılan metin gizleniyor, belge "tek sayfa" kalıyor ve aşağı kaydırılamıyordu. Yeni canlı sayfa akışı taşan paragrafları sonraki sayfaya taşır, gerekirse yeni sayfa açar, silince geri çeker; imleç ve Android klavyesi korunur.
7. **Sayfalar arası düzenleme:** Sayfa başında Backspace önceki sayfayla birleştirir, sayfa sonunda Delete sonraki sayfayı çeker; ↑ ↓ PageUp PageDown sayfalar arasında geçer.

**Biçimlendirme / kaydetme / dönüştürme**
8. **Punto ve yazı tipi:** Seçim yokken punto değiştirmek TÜM belgenin puntosunu değiştiriyordu; artık Word gibi imleçten sonra yazılacak metne uygulanır.
9. **PDF baştan yazıldı:** Ekrandaki sayfanın birebir yerleşiminden **vektör PDF** (seçilebilir/aranabilir Türkçe metin, gömülü Times New Roman/Arial, sekme hizaları, tablo çizgileri, logo ve UYAP karekodu). Dosya boyutu ~8 kat küçüldü.
10. **TIFF:** Aynı yerleşimden 192 DPI, gri tonlamalı, PackBits sıkıştırmalı çok sayfalı TIFF (eskisi sıkıştırmasız ve ~7 kat büyüktü).
11. **ODT yazma/okuma yeniden yazıldı:** Sekmeler, sekme durakları, girintiler, satır aralığı, punto/renk, tablolar, görseller, üst/alt bilgi ve kenar boşlukları korunuyor (eskisi hepsini kaybediyordu). DOCX okurken punto/renk/yazı tipi de alınıyor.
12. **Masaüstünde Kaydet gerçekten kaydediyor:** Tauri (Windows/macOS/Linux) içinde indirme bağlantısı çalışmadığından kaydetme sessizce başarısız oluyordu. Artık yerel "Aç / Kaydet / Farklı Kaydet" pencereleri kullanılır, "Kaydet" açık dosyanın üzerine yazar.

**E-İmza ve Mobil İmza — tüm platformlarda tek motor**
13. **Mobil imza artık çalışıyor (Android + Windows + macOS + Linux):** UYAP mobil imza servisi (`vatandas.uyap.gov.tr/mimzaclient`) Havelsan editörüyle birebir aynı biçimde çağrılır. Eski Android sürümü telefon numarasının başındaki 0'ı siliyor ve SOAP alan adlarını yanlış gönderiyordu. Termux/yerel sunucu gerekmez.
14. **Akıllı kart e-imza (masaüstü):** PKCS#11 ile AKİS (Kamu SM, TürkTrust, E-Güven), SafeNet/eToken (E-Tuğra, e-imzaTR), SafeSign, CardOS, Gemalto/Thales, ArkSigner, OpenSC sürücüleri işletim sistemine göre otomatik bulunur. Sürücü yoksa uygulama resmi indirme bağlantılarını gösterir. Özel sürücü yolu için `CANEDITOR_PKCS11` ortam değişkeni kullanılabilir.
15. **Akıllı kart e-imza (Android):** USB OTG CCID okuyucu ile, Termux olmadan.
16. **UYAP uyumlu imza:** CAdES-BES (contentType, signingTime, messageDigest, signingCertificateV2), sha256WithRSA / ECDSA; mevcut imzalar korunarak paralel imza eklenir. Üretilen imzalar TÜBİTAK ESYA kütüphanesiyle `TYPE_BES, özet doğrulaması başarılı` olarak doğrulandı; mahkeme imzalı belgelere eklenen imzalarda önceki imzalar geçerli kalır.
17. **İmzayı Doğrula** her platformda yerel kriptografik doğrulama yapar (özet + imza; RSA ve ECDSA).

> Not: E-imza kartı sürücüleri (AKİS vb.) üreticilerine ait lisanslı yazılımlar olduğundan uygulamanın içine gömülemez; uygulama kurulu sürücüyü otomatik bulur, yoksa resmi indirme adresine yönlendirir. Web (taşınabilir zip) sürümünde tarayıcı güvenlik kısıtları nedeniyle e-imza/mobil imza yapılamaz; masaüstü veya Android uygulamasını kullanın.


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
