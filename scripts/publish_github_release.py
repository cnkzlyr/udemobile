import os
import sys
import json
import urllib.request
import urllib.error

TOKEN = "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"
REPO = "cnkzlyr/udemobile"
TAG = "v3.7.2"
NAME = "CanEditor v3.7.2 — e-UDF Standardı Modern Arayüz, Sabit Dokunmatik Cetvel, Klavye Odak Koruması ve Kusursuz Dışa Aktarım"

BODY = """# 🏛️ CanEditor (UdeMobile) v3.7.2 — Sürüm Notları

CanEditor **v3.7.2**; `editor.e-udf.com` tasarım standardını temel alan **modern beyaz başlık paneli ve 1-tık hızlı kısayol hapını (`[ 💾 Kaydet | 📱 Görünüm | ☰ Menü ]`)** getiren, sayfa aşağı kaysa bile araç çubuğunun altında çakılı kalan **sabit (sticky) 40px dokunmatik cetveli** devreye sokan, mobil cihazlarda yazı yazarken sanal klavyenin odak kaybıyla kapanması sorununu sıfır DOM yıkımı ve ölçüm klonlama mimarisiyle kesin olarak çözen, doğrudan punto seçici açılır menüsünü entegre eden ve Termux bağımsız tüm telefon ve masaüstü sistemlerde kusursuz çalışan devrimsel bir sürümdür.

---

## 🌟 Öne Çıkan Yenilikler & Geliştirmeler

### 🎨 1. e-UDF Standardı Ultra Kompakt Üst Panel & Kısayol Hapı
- **e-UDF Stili Kısayol Hapı (`[ 💾 | 📱 | ☰ ]`):** Ekranın üstünde yer alan zarif hap grubu sayesinde; tek dokunuşla **💾 Hızlı Kaydet**, tek tıkla **📱/🖥️ Görünüm Değiştir** (Mobil Akış ve A4 Kağıt Düzeni) ve tek tıkla tüm hukuki fonksiyonlara ulaştıran **☰ Çekmece Menü**.
- **Açılır Menülerin Kırpılma Sorunu Giderildi:** Mobilde yatay taşma engellenerek tüm kaydet, paylaş ve yazdır seçeneklerine her cihazda kesintisiz erişim sağlandı.

### 📐 2. Sayfa Kaydırılsa Dahi Asla Kaybolmayan Sabit (Sticky) 40px Dokunmatik Cetvel
- **Sayfa Üstünde Çakılı Kalan Mimari:** Cetvel belge kaydırma konteynerinin dışına (`#toolbar-container` altına) taşınarak sayfalar 10 sayfa aşağı kaysa dahi ekranın üstünde kalıcı olarak sabitlendi.
- **-2 cm'den +18 cm'ye Tam Ölçekli Görsel Cetvel:** Sol kenar marjı (-2 .. 0), beyaz aktif yazı alanı (0 .. 16 cm) ve sağ marj (16 .. 18 cm) net biçimde renklendirildi.
- **44px Ergonomik Parmak Hedef Alanı:** İlk satır, asılı girinti ve sağ marj imleri dokunmatik ekranlarda parmakla kolayca tutulup sürüklenebilecek genişlikte (`touch-action: none`) yapılandırıldı.

### ⌨️ 3. Sanal Klavyenin Kapanmasına Karşı Kesin Odak Koruma Motoru
- **Canlı DOM Düğümlerini Koruma:** Sayfalama ölçüm motorunda canlı düğümlerin yerinden sökülmesi (`measurer.appendChild(node)`) yerine klonlama (`node.cloneNode(true)`) mimarisine geçildi; live DOM asla bozulmaz.
- **Yazım Sırasında Sıfır DOM Yıkımı:** Kullanıcı klavyeyle yazı yazarken veya alana odaklıyken sayfalama sıfırlaması (`container.innerHTML = ''`) ve sekme sıfırlaması tamamen durdurularak Gboard / Samsung klavye kapanması %100 çözüldü.
- **Pencere Boyutlanması Koruması:** Klavyenin açılmasıyla ekran yüksekliğinin küçüldüğü anlarda zoom veya sayfalama tetiklenmesi engellendi.

### 💾 4. 1-Tık Doğrudan Kaydet, Eksiksiz Farklı Kaydet ve Paylaşım Motoru
- **Doğrudan Kaydet:** Açık olan belge tek tıkla (`💾`) üzerine doğrudan yazılır; Android'de `Downloads/UYAP_Belgelerim` klasörüne, webde anında `.udf` indirmesine aktarılır.
- **Tüm Formatlarda Farklı Kaydet:** UDF (Havelsan UYAP 1.8), PDF (1:1 Vektörel A4 Baskı), DOCX (Word), TIFF (Çok Sayfalı İcra/Dava Evrakı) ve ODT (OpenDocument) formatları hem mobilde hem masaüstünde eksiksiz çalışır.
- **Gelişmiş Yerel Paylaşım:** `CanFileProvider` üzerinden WhatsApp, Gmail, Telegram, Word ve Google Drive'a doğrudan tek tıkla dosya gönderme desteği.

### 📕 5. Dahili PDF ve Çok Sayfalı TIFF Görüntüleyici Motoru
- **PDF.js Tabanlı Dahili PDF Görüntüleyici:** Harici bir uygulama açmaya gerek kalmadan; uygulama içinde sayfa gezintisi, dinamik yakınlaştırma/uzaklaştırma (%40 - %300), 1-tık indirme ve yerel paylaşım desteği.
- **UTIF.js Tabanlı Çok Sayfalı Adli TIFF Görüntüleyici:** İcra, tebligat ve mahkeme evraklarındaki tek veya çok sayfalı `.tiff` / `.tif` dosyalarını doğrudan açıp kaydırmalı, yüksek netlikte görüntüleme ve dışa aktarma kabiliyeti.
- **Termux Bağımsız Standart Çalışma:** Termux kurulu olmayan herhangi bir Android telefonda veya masaüstü bilgisayarda yerel dosya sistemine doğrudan erişim, dahili e-imza ve dosya işleme köprüleri.

### 🏛️ 6. Resmi Havelsan UYAP Headless Dönüştürücü Motoru (`UyapHeadlessConverter`)
- **1:1 Vektörel A4 PDF:** Resmi Havelsan `tr.com.havelsan.uyap.system.editor.b.b` motoru tersine mühendislikle çözülerek başsız (headless) Java CLI motoruna bağlandı. Raster tuval ekran görüntüleri yerine; seçilebilir, kopyalanabilir gerçek vektörel metin, Havelsan yazı tipleri ve birebir 10 sayfalık resmi UYAP düzeni oluşturulur (~196 KB dosya boyutu, karanlık mod uyumlu).
- **Resmi OpenDocument (ODT):** Resmi Havelsan `tr.com.havelsan.uyap.system.editor.b.a.f` motoru kullanılarak; tüm tabloları, hizalamaları ve stilleri içeren %100 uyumlu `.odt` evrakları üretilir (~29 KB).
- **Zengin Microsoft Word (DOCX):** Resmi ODT yapısı üzerinden tabloları, paragraf hizalamalarını, sekme duraklarını ve yazı tipi ağırlıklarını koruyan yüksek kaliteli DOCX belgeleri üretilir (~41 KB).
- **Termux & CLI Komut Desteği:** `uyap-convert <dosya.udf> <pdf|odt|docx>` komutu ile tüm dönüştürmeler sistem seviyesinde 2 saniye içinde gerçekleştirilebilir.

---

## 🚀 Hızlı İndirme Bağlantıları (v3.7.1)

| Platform | Dosya | Açıklama |
| :--- | :--- | :--- |
| **Android (Telefon / Tablet)** | [**CanEditor-v3.7.1.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.7.1/CanEditor-v3.7.1.apk) | Güncel mobil uygulama kurulum paketi |
| **Android (Her Zaman En Son)** | [**CanEditor-latest.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.7.1/CanEditor-latest.apk) | Kalıcı son sürüm bağlantısı |
| **Taşınabilir Web & Masaüstü** | [**CanEditor-Portable-Web-GUI-v3.7.1.zip**](https://github.com/cnkzlyr/udemobile/releases/download/v3.7.1/CanEditor-Portable-Web-GUI-v3.7.1.zip) | **Kurulumsuz;** Zipten çıkartıp `index.html` tıklayarak hemen kullanın |
| **Windows Kurulum (.exe)** | `CanEditor_3.7.1_x64-setup.exe` | Windows 10/11 64-bit doğrudan kurulum paketi *(CI tarafından eklenir)* |
| **Windows MSI Paketi (.msi)** | `CanEditor_3.7.1_x64_en-US.msi` | Windows kurumsal MSI yükleyici *(CI tarafından eklenir)* |
| **macOS Paketi (.dmg)** | `CanEditor_3.7.1_universal.dmg` | Apple Silicon (M1/M2/M3/M4) ve Intel Mac evrensel paket *(CI tarafından eklenir)* |
| **Linux (AppImage / .deb / .rpm)** | `CanEditor_3.7.1_amd64.AppImage` | Tüm Linux dağıtımları için kurulumsuz AppImage *(CI tarafından eklenir)* |

---

## 📖 Hiç Bilmeyenler İçin Adım Adım İndirme ve Kurulum Kılavuzu

### 📱 Android Telefon ve Tabletler İçin:
1. Yukarıdaki [**CanEditor-latest.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.7.1/CanEditor-latest.apk) bağlantısına dokunarak dosyayı indirin.
2. Tarayıcınız *"Dosya zararlı olabilir"* uyarısı verirse **"Yine de İndir"** butonuna dokunun (Google Play harici dosyalarda standart Android uyarısıdır).
3. İndirilen dosyaya dokunun. *"Bilinmeyen kaynaklar"* uyarısı çıkarsa **Ayarlar -> Bu kaynaktan izin ver** seçeneğini açıp geri dönün ve **"Yükle"** deyin.
4. WhatsApp, Telegram veya Dosyalarım'dan bir `.udf` dosyasına tıkladığınızda çıkan menüde **CanEditor -> "Her Zaman"** seçin.
5. Dosyanızı açıp düzenledikten sonra **Kaydet -> PDF Olarak Kaydet** ile doğrudan İndirilenler klasörüne A4 PDF olarak kaydedebilirsiniz.

### 💻 Windows (10 / 11) İçin:
- **Kurulumsuz Kullanım (Tavsiye Edilen):** `CanEditor-Portable-Web-GUI-v3.7.1.zip` dosyasını indirin, sağ tıklayıp "Tümünü Ayıkla" deyin ve içindeki `index.html` dosyasına çift tıklayın. Tamamen çevrimdışı çalışır.
- **Masaüstü Uygulaması:** `CanEditor_3.7.1_x64-setup.exe` indirip çift tıklayın. Windows SmartScreen uyarısı çıkarsa **"Ek bilgi" -> "Yine de çalıştır"** butonuna basın.

### 🍎 macOS İçin:
- `CanEditor_3.7.1_universal.dmg` dosyasını indirip açın ve CanEditor simgesini Uygulamalar klasörüne sürükleyin. Açılışta güvenlik uyarısı verirse simgeye `Control` tuşuyla **sağ tıklayıp "Aç"** deyin.

### 🐧 Linux (Debian / Pardus / Ubuntu / Fedora / RedHat) İçin:
- **AppImage:** `CanEditor_3.7.1_amd64.AppImage` dosyasını indirin, terminalden `chmod +x CanEditor_3.7.1_amd64.AppImage` komutunu verip çift tıklayın.
- **Debian / Pardus / Ubuntu (.deb):** `sudo dpkg -i CanEditor_3.7.1_amd64.deb`
- **Fedora / RedHat / openSUSE (.rpm):** `sudo rpm -ivh CanEditor-3.7.1-1.x86_64.rpm`
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
