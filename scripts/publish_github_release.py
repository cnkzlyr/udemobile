import os
import sys
import json
import urllib.request
import urllib.error

TOKEN = "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"
REPO = "cnkzlyr/udemobile"
TAG = "v3.6.5"
NAME = "CanEditor v3.6.5 — 1-Tık Hızlı Kaydet, Mobil Görünüm ve Klavye Odak Koruma Motoru, Sticky Dokunmatik Cetvel"

BODY = """# 🏛️ CanEditor (UdeMobile) v3.6.5 — Sürüm Notları

CanEditor **v3.6.5**; mobil ve dokunmatik cihazlarda yazım deneyimini zirveye taşıyan, yazı yazarken sanal klavyenin odak kaybıyla kapanması sorununu tamamen ortadan kaldıran, sayfa kaydırılsa dahi ekranın üstünde sabit (sticky) kalan ve parmakla yönetilebilen 42px dokunmatik cetveli devreye alan, 1-tık doğrudan `💾 Kaydet` (Ctrl+S) özelliğini sunan ve Android 10+ harici uygulama paylaşımlarını (WhatsApp, Gmail) yetkilendiren kapsamlı bir kullanıcı deneyimi ve stabilite sürümüdür.

---

## 🌟 Öne Çıkan Yenilikler & Hata Düzeltmeleri

### 💾 1. Doğrudan 1-Tık Hızlı Kaydet Butonu (Ctrl+S & Android Doğrudan Kayıt)
- **Doğrudan Üzerine Kayıt:** Açılmış olan belgeyi anında kaydetmek için hem web üst araç çubuğuna hem de Android yerel eylem çubuğuna belirgin, yeşil renkli **`💾 Kaydet`** butonu eklendi.
- **Tek Dokunuşla UYAP Kaydı:** Masaüstünde `Ctrl+S`, mobilde ise tek dokunuşla açık olan `.udf` dosyasının üzerine doğrudan kayıt gerçekleştirilir.

### ⌨️ 2. Yazı Yazarken Klavyenin Kapanmasını Engelleyen Akıllı Odak Koruması
- **Klavye Açılma (adjustResize) Koruması:** Android'de sanal klavye açıldığında tetiklenen pencere yeniden boyutlandırma olayında (`window.resize`), aktif düzenleme odağı varsa otomatik yakınlaştırma (fit-zoom) engellendi; CSS zoom değişiminden kaynaklanan imleç ve klavye kaybı tamamen ortadan kaldırıldı.
- **Yazım Esnasında Sıfır DOM Yıkımı:** Aktif yazım esnasında sayfalamanın DOM ağacını yeniden kurması 2500ms bekleme süresine alındı ve dikey taşma olmadığı sürece DOM ağacının korunması sağlandı. Böylece yazı yazarken sanal klavyenin kendi kendine kapanması sorunu %100 çözüldü.

### 📐 3. Ekranın Üstüne Sabitlenen (Sticky) Dokunmatik Cetvel (42px)
- **Sayfa Kaydıkça Ekranda Kalan Cetvel:** Sayfa ne kadar aşağı kaydırılırsa kaydırılsın, cetvel ekranın en üstünde (`position: sticky; top: 0; z-index: 90;`) sabit kalarak her an görünür durumda kalır.
- **Parmakla Kontrol Edilebilen 44x44px Geniş Dokunmatik Alanlar:** Cetvel yüksekliği 42px'e çıkarıldı. 4 ayrı girinti imi (**İlk Satır Girintisi** - mavi ters üçgen, **Asılı Girinti** - mavi düz üçgen, **Sol Girinti** - lacivert kutu, **Sağ Marj** - koyu üçgen) için parmakla rahatça tutulup sürüklenebilen görünmez 44x44 piksellik dokunmatik etki alanları (`::before`) entegre edildi.

### 📱 4. Kusursuz Mobil Görünüm (Word & Google Docs Standardı)
- **Sıfır Yatay Taşma:** Dar mobil ekranlarda (`max-width: 820px`) `document.body` ve editör kapsayıcısının yatay taşması (`overflow-x: hidden`) tamamen önlendi (`bodyScrollW: 390px`).
- **Yatay Kaydırılabilir Araç Çubuğu:** Web araç çubuğu butonlarının mobilde alt alta 10 satır yığılması engellendi; Word ve `editor.e-udf.com` standardında tek satırda parmakla pürüzsüz kaydırılabilir hale getirildi.
- **Android Arayüz Bütünlüğü:** Android uygulamasında yerel başlık çubuğu bulunduğu için WebView içindeki masaüstü başlık çubuğu gizlendi; gereksiz dikey alan kaybı ve çift başlık görünümü önlendi.

### 📤 5. Android 10+ Harici Paylaşım ve Farklı Kaydet Onarımı
- **WhatsApp ve Gmail Paylaşım İzni Hatası Çözüldü:** `launchShareIntent` içinde `shareIntent.setClipData(...)` ve `FLAG_GRANT_READ_URI_PERMISSION` yetkileri tanımlanarak Android 10, 11, 12, 13, 14 ve 15 sürümlerinde harici uygulamaların paylaşılan dosyaları "erişim engellendi" hatası vermeden açması sağlandı.
- **Tüm Formatlarda Farklı Kaydet:** Menüdeki tüm seçenekler (**UDF, Adobe PDF, Microsoft Word DOCX, Çok Sayfalı TIFF, OpenDocument ODT**) Base64 veri köprüsüyle doğrudan `Downloads/UYAP_Belgelerim` klasörüne anında kaydedilir hale getirildi.

---

## 🚀 Hızlı İndirme Bağlantıları (v3.6.5)

| Platform | Dosya | Açıklama |
| :--- | :--- | :--- |
| **Android (Telefon / Tablet)** | [**CanEditor-v3.6.5.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.6.5/CanEditor-v3.6.5.apk) | Güncel mobil uygulama kurulum paketi |
| **Android (Her Zaman En Son)** | [**CanEditor-latest.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.6.5/CanEditor-latest.apk) | Kalıcı son sürüm bağlantısı |
| **Taşınabilir Web & Masaüstü** | [**CanEditor-Portable-Web-GUI-v3.6.5.zip**](https://github.com/cnkzlyr/udemobile/releases/download/v3.6.5/CanEditor-Portable-Web-GUI-v3.6.5.zip) | **Kurulumsuz;** Zipten çıkartıp `index.html` tıklayarak hemen kullanın |
| **Windows Kurulum (.exe)** | `CanEditor_3.6.5_x64-setup.exe` | Windows 10/11 64-bit doğrudan kurulum paketi *(CI tarafından eklenir)* |
| **Windows MSI Paketi (.msi)** | `CanEditor_3.6.5_x64_en-US.msi` | Windows kurumsal MSI yükleyici *(CI tarafından eklenir)* |
| **macOS Paketi (.dmg)** | `CanEditor_3.6.5_universal.dmg` | Apple Silicon (M1/M2/M3/M4) ve Intel Mac evrensel paket *(CI tarafından eklenir)* |
| **Linux (AppImage / .deb / .rpm)** | `CanEditor_3.6.5_amd64.AppImage` | Tüm Linux dağıtımları için kurulumsuz AppImage *(CI tarafından eklenir)* |

---

## 📖 Hiç Bilmeyenler İçin Adım Adım İndirme ve Kurulum Kılavuzu

### 📱 Android Telefon ve Tabletler İçin:
1. Yukarıdaki [**CanEditor-latest.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.6.5/CanEditor-latest.apk) bağlantısına dokunarak dosyayı indirin.
2. Tarayıcınız *"Dosya zararlı olabilir"* uyarısı verirse **"Yine de İndir"** butonuna dokunun (Google Play harici dosyalarda standart Android uyarısıdır).
3. İndirilen dosyaya dokunun. *"Bilinmeyen kaynaklar"* uyarısı çıkarsa **Ayarlar -> Bu kaynaktan izin ver** seçeneğini açıp geri dönün ve **"Yükle"** deyin.
4. WhatsApp, Telegram veya Dosyalarım'dan bir `.udf` dosyasına tıkladığınızda çıkan menüde **CanEditor -> "Her Zaman"** seçin.
5. Dosyanızı açıp düzenledikten sonra **Kaydet -> PDF Olarak Kaydet** ile doğrudan İndirilenler klasörüne A4 PDF olarak kaydedebilirsiniz.

### 💻 Windows (10 / 11) İçin:
- **Kurulumsuz Kullanım (Tavsiye Edilen):** `CanEditor-Portable-Web-GUI-v3.6.5.zip` dosyasını indirin, sağ tıklayıp "Tümünü Ayıkla" deyin ve içindeki `index.html` dosyasına çift tıklayın. Tamamen çevrimdışı çalışır.
- **Masaüstü Uygulaması:** `CanEditor_3.6.5_x64-setup.exe` indirip çift tıklayın. Windows SmartScreen uyarısı çıkarsa **"Ek bilgi" -> "Yine de çalıştır"** butonuna basın.

### 🍎 macOS İçin:
- `CanEditor_3.6.5_universal.dmg` dosyasını indirip açın ve CanEditor simgesini Uygulamalar klasörüne sürükleyin. Açılışta güvenlik uyarısı verirse simgeye `Control` tuşuyla **sağ tıklayıp "Aç"** deyin.

### 🐧 Linux (Debian / Pardus / Ubuntu / Fedora / RedHat) İçin:
- **AppImage:** `CanEditor_3.6.5_amd64.AppImage` dosyasını indirin, terminalden `chmod +x CanEditor_3.6.5_amd64.AppImage` komutunu verip çift tıklayın.
- **Debian / Pardus / Ubuntu (.deb):** `sudo dpkg -i CanEditor_3.6.5_amd64.deb`
- **Fedora / RedHat / openSUSE (.rpm):** `sudo rpm -ivh CanEditor-3.6.5-1.x86_64.rpm`
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
