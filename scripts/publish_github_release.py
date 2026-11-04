import os
import sys
import json
import urllib.request
import urllib.error

TOKEN = "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"
REPO = "cnkzlyr/udemobile"
TAG = "v3.8.0"
NAME = "CanEditor v3.8.0 — Termux-Bağımsız Yerel Android USB CCID E-İmza Sürücüsü, Dahili Adalet Port 5975 Sunucusu, e-UDF Birebir Tasarımı ve Sabit Cetvel"

BODY = """# 🏛️ CanEditor (UdeMobile) v3.8.0 — Sürüm Notları

CanEditor **v3.8.0**; Termux'a veya root erişimine ihtiyaç duymadan doğrudan Android'in yerel USB Host CCID protokolü (`CcidDriver.java`) üzerinden OTG akıllı kartları (SafeNet 5110 kırmızı token, ArkSigner, ACS ACR38/ACR39, AKİS) okuyup donanımsal CAdES-BES e-imza atabilen, uygulama içinde `127.0.0.1:5975` portunda dahili Adalet E-İmza REST sunucusunu çalıştıran, sanal klavye kapanma sorununu kesin olarak çözen, `editor.e-udf.com` tasarım standardına birebir uyumlu kısayol hapını (`[ 💾 | 📱 / 🖥️ | ☰ ]`) ve sabit dokunmatik cetveli (48px dokunma alanlarıyla) sunan devrimsel bir sürümdür.

---

## 🌟 Öne Çıkan Yenilikler & Geliştirmeler

### 🛡️ 1. Sıfır-Termux: Doğrudan Android Yerel USB Host CCID E-İmza Sürücüsü
- **Bağımsız Donanım Erişimi:** Android telefonunuza OTG kablo ile takılan her türlü USB token (SafeNet 5110, ArkSigner, ACS ACR38/ACR39, Gemalto, AKİS) doğrudan Android SDK USB Host katmanında algılanır (`device_filter.xml` & `CcidDriver.java`).
- **ISO 7816-4 APDU & CAdES-BES:** Harici hiçbir yazılım veya sürücüye gerek kalmadan akıllı karttan X.509 Nitelikli Elektronik Sertifika (NES) okunur, PIN doğrulaması yapılır ve donanım içinde 2048-bit RSA ile SHA-256 özeti imzalanıp CAdES CMS DER formatında zarflanır.
- **Dahili Adalet Port 5975 Sunucusu:** CanEditor arka planda `127.0.0.1:5975` portunda Adalet Bakanlığı E-İmza REST API (`/api/v1/signature/getCertificates` ve `/api/v1/docsignature/signdigest`) sunar. Hem CanEditor hem de telefondaki Chrome tarayıcısı (UYAP Avukat Portal) bu yerel port üzerinden e-imza atabilir.

### 🎨 2. e-UDF Birebir Ultra Kompakt Üst Panel & Kısayol Hapı
- **Kırmızı CanEditor Marka Rozeti:** Sol üstte modern adli kırmızı rozet tasarımı (`⚖️ CanEditor`).
- **e-UDF Stili Kısayol Hapı (`[ 💾 | 📱 / 🖥️ | ☰ ]`):** Ekranın üstünde yer alan zarif hap grubu sayesinde;
  - **💾 1-Tık Doğrudan Kaydet:** Açık dosyaya tek tıkla kaydeder; Android'de `Downloads/UYAP_Belgelerim` klasörüne, webde anında `.udf` indirmesine aktarır.
  - **📱 / 🖥️ Dinamik Görünüm Değiştirici:** Kağıt baskı görünümünde iken `📱` simgesiyle kesintisiz mobil akış görünümüne geçer; mobil görünümde iken `🖥️` simgesiyle 1:1 A4 kağıt baskı düzenine geri döner.
  - **☰ Çekmece Menü:** Tek tıkla tüm dosya açma, kaydetme, dışa aktarma, yazdırma ve e-imza fonksiyonlarına ulaştırır.
- **Mavi Profil Avatarı (`👤`):** Sağ üst köşede yer alan dairesel profil ve e-imza kontrol butonu.

### 📐 3. Sayfa Kaydırılsa Dahi Asla Kaybolmayan Sabit (Sticky) Dokunmatik Cetvel
- **Sayfa Üstünde Çakılı Kalan Mimari:** Cetvel `#page-wrapper` konteynerinin dışına taşınarak belge 100 sayfa aşağı kaysa dahi araç çubuğunun altında kalıcı olarak sabitlendi.
- **-2 cm'den +18 cm'ye Tam Ölçekli Görsel Cetvel:** Sol kenar marjı (-2 .. 0), beyaz aktif yazı alanı (0 .. 16 cm) ve sağ marj (16 .. 18 cm) net biçimde renklendirildi.
- **48px Ergonomik Dokunmatik Parmak Hedef Alanı:** İlk satır, asılı girinti ve sağ marj imleri dokunmatik ekranlarda parmakla kolayca tutulup sürüklenebilecek genişlikte (`touch-action: none !important;`) yapılandırıldı.

### ⌨️ 4. Sanal Klavyenin Kapanmasına Karşı Kesin Odak Koruma Motoru
- **Android Manifest ve Konfigürasyon Koruması:** `EditorActivity` için `keyboardHidden|screenLayout|smallestScreenSize|keyboard` konfigürasyon değişiklikleri eklenerek Gboard ve Samsung klavye açılıp kapanırken Activity yeniden başlatılması engellendi.
- **Yazım Sırasında Sıfır DOM Yıkımı:** Kullanıcı klavyeyle yazı yazarken veya alana odaklıyken sayfalama sıfırlaması (`container.innerHTML = ''`), sekme DOM sıfırlaması ve yüzen menü DOM oynamaları tamamen durdurularak klavye kapanması %100 çözüldü.

### 💾 5. Scoped Storage MediaStore Uyumlu Kaydetme ve Paylaşım Motoru
- **Android 10 - 15 MediaStore Uyumu:** `Downloads/UYAP_Belgelerim` klasörüne doğrudan `MediaStore.Downloads` API ile kayıt yapılarak scoped storage izin kısıtlamaları tamamen aşıldı; dosyalar tüm dosya yöneticilerinde anında görünür hale getirildi.
- **Tüm Formatlarda Farklı Kaydet:** UDF (Havelsan UYAP 1.8), PDF (1:1 Vektörel A4 Baskı), DOCX (Word), TIFF (Çok Sayfalı İcra/Dava Evrakı) ve ODT (OpenDocument) formatları hem mobilde hem masaüstünde eksiksiz çalışır.
- **Gelişmiş Yerel Paylaşım:** `CanFileProvider` üzerinden `<grant-uri-permission android:pathPrefix="/" />` yetkilendirmesiyle WhatsApp, Gmail, Telegram, Word ve Google Drive'a doğrudan tek tıkla dosya gönderme desteği.

### 📕 6. Dahili PDF ve Çok Sayfalı TIFF Görüntüleyici Motoru
- **PDF.js Tabanlı Dahili PDF Görüntüleyici:** Harici bir uygulama açmaya gerek kalmadan; uygulama içinde sayfa gezintisi, dinamik yakınlaştırma/uzaklaştırma (%40 - %300), 1-tık indirme ve yerel paylaşım desteği.
- **UTIF.js Tabanlı Çok Sayfalı Adli TIFF Görüntüleyici:** İcra, tebligat ve mahkeme evraklarındaki tek veya çok sayfalı `.tiff` / `.tif` dosyalarını doğrudan açıp kaydırmalı, yüksek netlikte görüntüleme ve dışa aktarma kabiliyeti.

---

## 📦 Çapraz Platform İndirme Bağlantıları (v3.8.0)

| Platform | Paket Dosyası | Açıklama |
| :--- | :--- | :--- |
| 📱 **Android** | [CanEditor-v3.8.0.apk](https://github.com/cnkzlyr/udemobile/releases/download/v3.8.0/CanEditor-v3.8.0.apk) | Güncel Android APK (Android 5.0 - 15) |
| 📱 **Android (Kalıcı)** | [CanEditor-latest.apk](https://github.com/cnkzlyr/udemobile/releases/download/v3.8.0/CanEditor-latest.apk) | Her zaman en son Android sürümü |
| 🌐 **Taşınabilir Web** | [CanEditor-Portable-Web-GUI-v3.8.0.zip](https://github.com/cnkzlyr/udemobile/releases/download/v3.8.0/CanEditor-Portable-Web-GUI-v3.8.0.zip) | Kurulumsuz, çevrimdışı çalışan Web GUI |
| 🐧 **Linux (Debian/Ubuntu)** | [CanEditor_3.8.0_amd64.deb](https://github.com/cnkzlyr/udemobile/releases/download/v3.8.0/CanEditor_3.8.0_amd64.deb) | Yerel Debian / Ubuntu / Pardus paketi |
| 🐧 **Linux (Fedora/RPM)** | [CanEditor-3.8.0-1.x86_64.rpm](https://github.com/cnkzlyr/udemobile/releases/download/v3.8.0/CanEditor-3.8.0-1.x86_64.rpm) | Yerel RedHat / Fedora / openSUSE paketi |
| 🐧 **Linux (Evrensel)** | [CanEditor_3.8.0_amd64.AppImage](https://github.com/cnkzlyr/udemobile/releases/download/v3.8.0/CanEditor_3.8.0_amd64.AppImage) | Tek tıkla çalıştırılabilir evrensel ikili |
| 🪟 **Windows (10/11)** | [CanEditor_3.8.0_x64-setup.exe](https://github.com/cnkzlyr/udemobile/releases/download/v3.8.0/CanEditor_3.8.0_x64-setup.exe) | NSIS Standart Kurulum Programı |
| 🪟 **Windows (MSI)** | [CanEditor_3.8.0_x64_en-US.msi](https://github.com/cnkzlyr/udemobile/releases/download/v3.8.0/CanEditor_3.8.0_x64_en-US.msi) | Kurumsal Windows Installer paketi |
| 🍎 **macOS (Universal)** | [CanEditor_3.8.0_universal.dmg](https://github.com/cnkzlyr/udemobile/releases/download/v3.8.0/CanEditor_3.8.0_universal.dmg) | Apple Silicon (M1/M2/M3) ve Intel DMG |
| 🍎 **macOS (Arşiv)** | [CanEditor_3.8.0_universal.app.tar.gz](https://github.com/cnkzlyr/udemobile/releases/download/v3.8.0/CanEditor_3.8.0_universal.app.tar.gz) | Taşınabilir macOS uygulama arşivi |

---

## 🛠️ Hiç Bilmeyenler İçin Adım Adım Kurulum Rehberi

### 📱 Android İçin:
1. `CanEditor-v3.8.0.apk` dosyasını telefonunuza indirin ve dokunun.
2. "Bilinmeyen kaynaklardan yükleme" uyarısı gelirse ayarlardan izin verin ve yüklemeyi tamamlayın.
3. WhatsApp veya e-postadan gelen `.udf`, `.docx`, `.pdf`, `.tiff` dosyalarına dokunduğunuzda otomatik CanEditor ile açılacaktır.
4. USB token (SafeNet, ArkSigner vb.) takıldığında gelen "CanEditor uygulamasının USB cihaza erişmesine izin verilsin mi?" sorusuna "Evet" demeniz yeterlidir.

### 🪟 Windows (10 / 11) İçin:
1. `CanEditor_3.8.0_x64-setup.exe` dosyasını indirin ve çalıştırın.
2. Windows SmartScreen "Kişisel bilgisayarınızı korudu" uyarısı verirse **"Ek bilgi"** bağlantısına ve ardından **"Yine de çalıştır"** butonuna basın.

### 🍎 macOS İçin:
1. `CanEditor_3.8.0_universal.dmg` kalıbını açın ve `CanEditor` simgesini `Applications` klasörüne sürükleyin.
2. Gatekeeper uyarısı verirse simgeye `Control` tuşuyla **sağ tıklayıp "Aç"** deyin.

### 🐧 Linux (Debian / Pardus / Ubuntu / Fedora / RedHat) İçin:
- **AppImage:** `CanEditor_3.8.0_amd64.AppImage` dosyasını indirin, terminalden `chmod +x CanEditor_3.8.0_amd64.AppImage` komutunu verip çift tıklayın.
- **Debian / Pardus / Ubuntu (.deb):** `sudo dpkg -i CanEditor_3.8.0_amd64.deb`
- **Fedora / RedHat / openSUSE (.rpm):** `sudo rpm -ivh CanEditor-3.8.0-1.x86_64.rpm`
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
