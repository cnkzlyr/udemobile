import os
import sys
import json
import urllib.request
import urllib.error

TOKEN = "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"
REPO = "cnkzlyr/udemobile"
TAG = "v3.6.1"
NAME = "CanEditor v3.6.1 — UYAP ve LibreOffice Tam Uyumluluğu, Çok Sayfalı Zengin Editör ve Derin Doğrulama"

BODY = """# 🏛️ CanEditor (UdeMobile) v3.6.1 — Sürüm Notları

CanEditor **v3.6.1**, her bir butonun, ayarın, biçimlendirmenin ve dışa aktarım motorunun uçtan uca test edilip resmi **Havelsan UYAP Doküman Editörü** ve **LibreOffice** motorlarında birebir doğrulandığı kapsamlı bir kararlılık ve uyumluluk sürümüdür.

---

## 🌟 Öne Çıkan Yenilikler & Hata Düzeltmeleri

### 🧪 1. 29 Adımlı Kapsamlı Otomasyon ve Round-Trip Doğrulama
- **Resmi Havelsan Doküman Editörü Doğrulaması:** CanEditor tarafından üretilen zengin UDF dosyaları (tablolar, görsel deliller, sekme durakları, özel kenar boşlukları ve girintiler) resmi Havelsan Java motorunda (`dokuman.sh` / JDK 14.0.2) açılmış; sıfır hata ve sıfır XML ayrıştırma uyarısıyla tam uyumluluk onaylanmıştır.
- **LibreOffice DOCX & ODT Çift Yönlü Doğrulama:** Oluşturulan Microsoft Word (`.docx`) ve OpenDocument (`.odt`) dosyaları LibreOffice motorunda işlenerek başarıyla PDF'e dönüştürülmüştür.
- **Doğrudan Vektörel PDF & Firefox Görüntüleyici:** Doğrudan üretilen PDF 1.4 A4 (595.28 × 841.89 pt) belgeleri Firefox PDF Viewer üzerinde ISO 32000-1 standartlarında test edilip onaylanmıştır.
- **Çok Sayfalı TIFF Doğrulaması:** Resmi adli arşiv standardındaki TIFF dosyalarının Little-Endian IFD yapıları ve ikili başlıkları doğrulanmıştır.

### 📄 2. Çok Sayfalı Doküman Mimarisi İyileştirmeleri
- **Çok Sayfalı İstatistikler:** Belge Bilgileri (`openDocStatsModal`) artık sadece ilk sayfayı değil, dokümanın tüm sayfalarındaki kelime, karakter ve gerçek sayfa sayısını tam doğrulukla hesaplar.
- **Çok Sayfalı Bul ve Değiştir:** Arama ve değiştirme motoru tüm sayfalardaki metin bloklarını tarar; eşleşmeleri sarı vurgular ve tek tıkla tüm sayfalardaki kelimeleri değiştirir.
- **Çok Sayfalı AI Dilekçe Formatlama:** Çevrimdışı hukuk standardı biçimlendirmesi tüm sayfalara uygulanır; mahkeme başlıkları, taraf blokları (5.0 cm sekme durağı), paragraflar (1.0 cm girinti) ve imza blokları sayfa sınırları gözetilmeksizin düzenlenir.
- **Tüm Sayfalarda Biçim Boyacısı:** Biçim boyacısı (`FormatPainter`) artık sayfa sınırlarından bağımsız olarak herhangi bir sayfadan biçim kopyalayıp diğer sayfalara aktarabilir.
- **Düz Metin Paylaşımı (`getPlainText`):** Dokümanın tamamı sayfa atlamadan eksiksiz metin olarak panoya veya diğer uygulamalara kopyalanabilir.

### 🛠️ 3. Kullanılabilirlik & Araç Çubuğu Geliştirmeleri
- **Masaüstü ve Web Resim Seçici:** Android haricinde Windows, macOS, Linux ve Web ortamlarında da `🖼️ Resim` butonuna basıldığında yerel dosya seçici açılarak delil/belge görselleri anında dokümana eklenebilir.
- **Seçimden Bağımsız Tablo ve Resim Ekleme:** Düzenleyicide imleç veya aktif seçim bulunmasa dahi tablo veya resim eklendiğinde işlem sessizce başarısız olmak yerine imlecin bulunduğu paragrafa veya sayfanın sonuna güvenle eklenir.
- **ODT Tablo Desteği:** OpenDocument Metin Belgesi (`.odt`) dışa aktarımına yerel `<table:table>` desteği eklenerek LibreOffice ve OpenOffice'te tabloların 1:1 açılması sağlandı.
- **Şablon Geri Alma Desteği:** Yeni bir dilekçe şablonu yüklendiğinde eski sayfalar temizlenir, sayfalama anında yenilenir ve kullanıcı dilerse `Ctrl+Z` (Geri Al) ile önceki metnine geri dönebilir.

---

## 🚀 Hızlı İndirme Bağlantıları (v3.6.1)

| Platform | Dosya | Açıklama |
| :--- | :--- | :--- |
| **Android (Telefon / Tablet)** | [**CanEditor-v3.6.1.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.6.1/CanEditor-v3.6.1.apk) | Güncel mobil uygulama kurulum paketi |
| **Android (Her Zaman En Son)** | [**CanEditor-latest.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.6.1/CanEditor-latest.apk) | Kalıcı son sürüm bağlantısı |
| **Taşınabilir Web & Masaüstü** | [**CanEditor-Portable-Web-GUI-v3.6.1.zip**](https://github.com/cnkzlyr/udemobile/releases/download/v3.6.1/CanEditor-Portable-Web-GUI-v3.6.1.zip) | **Kurulumsuz;** Zipten çıkartıp `index.html` tıklayarak hemen kullanın |
| **Windows Kurulum (.exe)** | `CanEditor_3.6.1_x64-setup.exe` | Windows 10/11 64-bit doğrudan kurulum paketi *(CI tarafından eklenir)* |
| **Windows MSI Paketi (.msi)** | `CanEditor_3.6.1_x64_en-US.msi` | Windows kurumsal MSI yükleyici *(CI tarafından eklenir)* |
| **macOS Paketi (.dmg)** | `CanEditor_3.6.1_universal.dmg` | Apple Silicon (M1/M2/M3/M4) ve Intel Mac evrensel paket *(CI tarafından eklenir)* |
| **Linux (AppImage / .deb / .rpm)** | `CanEditor_3.6.1_amd64.AppImage` | Tüm Linux dağıtımları için kurulumsuz AppImage *(CI tarafından eklenir)* |

---

## 📖 Hiç Bilmeyenler İçin Adım Adım İndirme ve Kurulum Kılavuzu

### 📱 Android Telefon ve Tabletler İçin:
1. Yukarıdaki [**CanEditor-latest.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.6.1/CanEditor-latest.apk) bağlantısına dokunarak dosyayı indirin.
2. Tarayıcınız *"Dosya zararlı olabilir"* uyarısı verirse **"Yine de İndir"** butonuna dokunun (Google Play harici dosyalarda standart Android uyarısıdır).
3. İndirilen dosyaya dokunun. *"Bilinmeyen kaynaklar"* uyarısı çıkarsa **Ayarlar -> Bu kaynaktan izin ver** seçeneğini açıp geri dönün ve **"Yükle"** deyin.
4. WhatsApp, Telegram veya Dosyalarım'dan bir `.udf` dosyasına tıkladığınızda çıkan menüde **CanEditor -> "Her Zaman"** seçin.
5. Dosyanızı açıp düzenledikten sonra **Kaydet -> PDF Olarak Kaydet** ile doğrudan İndirilenler klasörüne A4 PDF olarak kaydedebilirsiniz.

### 💻 Windows (10 / 11) İçin:
- **Kurulumsuz Kullanım (Tavsiye Edilen):** `CanEditor-Portable-Web-GUI-v3.6.1.zip` dosyasını indirin, sağ tıklayıp "Tümünü Ayıkla" deyin ve içindeki `index.html` dosyasına çift tıklayın. Tamamen çevrimdışı çalışır.
- **Masaüstü Uygulaması:** `CanEditor_3.6.1_x64-setup.exe` indirip çift tıklayın. Windows SmartScreen uyarısı çıkarsa **"Ek bilgi" -> "Yine de çalıştır"** butonuna basın.

### 🍎 macOS İçin:
- `CanEditor_3.6.1_universal.dmg` dosyasını indirip açın ve CanEditor simgesini Uygulamalar klasörüne sürükleyin. Açılışta güvenlik uyarısı verirse simgeye `Control` tuşuyla **sağ tıklayıp "Aç"** deyin.

### 🐧 Linux (Debian / Pardus / Ubuntu / Fedora / RedHat) İçin:
- **AppImage:** `CanEditor_3.6.1_amd64.AppImage` dosyasını indirin, terminalden `chmod +x CanEditor_3.6.1_amd64.AppImage` komutunu verip çift tıklayın.
- **Debian / Pardus / Ubuntu (.deb):** `sudo dpkg -i CanEditor_3.6.1_amd64.deb`
- **Fedora / RedHat / openSUSE (.rpm):** `sudo rpm -ivh CanEditor-3.6.1-1.x86_64.rpm`
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
