import os
import sys
import json
import urllib.request
import urllib.error

TOKEN = "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"
REPO = "cnkzlyr/udemobile"
TAG = "v3.6.3"
NAME = "CanEditor v3.6.3 — Kesintisiz Adım Adım Geri Al/Yinele Motoru, Akıllı Biçim Boyacısı ve Sıfır DOM Kaybı"

BODY = """# 🏛️ CanEditor (UdeMobile) v3.6.3 — Sürüm Notları

CanEditor **v3.6.3**, geri alma/yinele (Undo/Redo) motorunu tarayıcının yerel C++ UndoManager katmanına bağlayarak yüzlerce adım derinlikte gerçek harf-harf, kelime-kelime ve biçim-biçim geri alabilme/yineleyebilme yeteneği kazandıran, biçim boyacısını (Format Painter) akıllı diff mimarisiyle yeniden inşa eden ve yazım anında DOM yıkımlarını tamamen durduran büyük bir kullanıcı deneyimi sürümüdür.

---

## 🌟 Öne Çıkan Yenilikler & Hata Düzeltmeleri

### ↶ 1. Kesintisiz Yerel Adım Adım (Step-by-Step) Geri Al & Yinele Motoru
- **Kaba HTML Yedekleme Yerine Hassas İşlem Yığını:** Önceki sürümlerde `history.js` motorunun tüm sayfa HTML'ini blok halinde yedekleyip `innerHTML` üzerinden geri yüklemesi sebebiyle oluşan "belgenin yedeğini alıp geri yüklüyor gibi çalışma" hissi tamamen ortadan kaldırıldı.
- **Yüzlerce Adım Derinlik:** Kelime arasına yazılan tek bir boşluk, silinen tek bir harf veya uygulanan tek bir kalınlaştırma işlemi doğrudan yerel hafızaya kaydedilir; `Ctrl+Z` (Geri Al) veya `Ctrl+Y` (Yinele) ile tam işlem anındaki imleç noktasında adım adım geri alınıp yinelenebilir.
- **Yinele (Redo) Dalı Artık Asla Silinmez:** Geri alma işlemleri sırasında arka planda çalışan mutasyon gözlemcisinin ileri adımları silmesi engellendi.

### ⚡ 2. DOM Sayfalama Koruması (Zero-DOM-Thrashing)
- **Gereksiz Sayfa Yıkımı Engellendi:** Düzenleyicide yazı yazarken, boşluk bırakırken veya silerken sayfa sayısı ve paragraf düzeni değişmediği sürece `container.innerHTML = ''` asla çalıştırılmaz. Böylece tarayıcının yerel Undo/Redo yığıtı, imleç seçimi ve aktif odak sıfır kayıpla %100 korunur.

### 🖌️ 3. Akıllı ve İki Yönlü Biçim Boyacısı (Format Painter)
- **Gerçek Yaprak Düğüm (Leaf Node) Analizi:** Boyacı artık kapsayıcı paragrafların varsayılan stillerini değil, seçili metnin gerçek `<strong>`, `<em>`, `<u>` ve punto değerlerini `document.queryCommandState` ile eksiksiz okur.
- **Akıllı Fark (Diff) Uygulama:** Hedef metinle kaynak metin arasındaki stiller karşılaştırılır; sadece farklı olan özellikler (örneğin yalnızca kalınlık veya yalnızca yazı rengi) uygulanır. Bu sayede gereksiz biçimlendirme komutları üretilmez ve boyacı işlemi `Geri Al` ile tek hamlede geri alınabilir.
- **Evrensel Sayfa Desteği:** Boyacı açıkken tüm sayfalarda kopyalama imleci (`cursor: copy !important`) gösterilir ve tıklanan veya seçilen tüm sayfalardaki metinlere sorunsuz uygulanır.

---

## 🚀 Hızlı İndirme Bağlantıları (v3.6.3)

| Platform | Dosya | Açıklama |
| :--- | :--- | :--- |
| **Android (Telefon / Tablet)** | [**CanEditor-v3.6.3.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.6.3/CanEditor-v3.6.3.apk) | Güncel mobil uygulama kurulum paketi |
| **Android (Her Zaman En Son)** | [**CanEditor-latest.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.6.3/CanEditor-latest.apk) | Kalıcı son sürüm bağlantısı |
| **Taşınabilir Web & Masaüstü** | [**CanEditor-Portable-Web-GUI-v3.6.3.zip**](https://github.com/cnkzlyr/udemobile/releases/download/v3.6.3/CanEditor-Portable-Web-GUI-v3.6.3.zip) | **Kurulumsuz;** Zipten çıkartıp `index.html` tıklayarak hemen kullanın |
| **Windows Kurulum (.exe)** | `CanEditor_3.6.3_x64-setup.exe` | Windows 10/11 64-bit doğrudan kurulum paketi *(CI tarafından eklenir)* |
| **Windows MSI Paketi (.msi)** | `CanEditor_3.6.3_x64_en-US.msi` | Windows kurumsal MSI yükleyici *(CI tarafından eklenir)* |
| **macOS Paketi (.dmg)** | `CanEditor_3.6.3_universal.dmg` | Apple Silicon (M1/M2/M3/M4) ve Intel Mac evrensel paket *(CI tarafından eklenir)* |
| **Linux (AppImage / .deb / .rpm)** | `CanEditor_3.6.3_amd64.AppImage` | Tüm Linux dağıtımları için kurulumsuz AppImage *(CI tarafından eklenir)* |

---

## 📖 Hiç Bilmeyenler İçin Adım Adım İndirme ve Kurulum Kılavuzu

### 📱 Android Telefon ve Tabletler İçin:
1. Yukarıdaki [**CanEditor-latest.apk**](https://github.com/cnkzlyr/udemobile/releases/download/v3.6.3/CanEditor-latest.apk) bağlantısına dokunarak dosyayı indirin.
2. Tarayıcınız *"Dosya zararlı olabilir"* uyarısı verirse **"Yine de İndir"** butonuna dokunun (Google Play harici dosyalarda standart Android uyarısıdır).
3. İndirilen dosyaya dokunun. *"Bilinmeyen kaynaklar"* uyarısı çıkarsa **Ayarlar -> Bu kaynaktan izin ver** seçeneğini açıp geri dönün ve **"Yükle"** deyin.
4. WhatsApp, Telegram veya Dosyalarım'dan bir `.udf` dosyasına tıkladığınızda çıkan menüde **CanEditor -> "Her Zaman"** seçin.
5. Dosyanızı açıp düzenledikten sonra **Kaydet -> PDF Olarak Kaydet** ile doğrudan İndirilenler klasörüne A4 PDF olarak kaydedebilirsiniz.

### 💻 Windows (10 / 11) İçin:
- **Kurulumsuz Kullanım (Tavsiye Edilen):** `CanEditor-Portable-Web-GUI-v3.6.3.zip` dosyasını indirin, sağ tıklayıp "Tümünü Ayıkla" deyin ve içindeki `index.html` dosyasına çift tıklayın. Tamamen çevrimdışı çalışır.
- **Masaüstü Uygulaması:** `CanEditor_3.6.3_x64-setup.exe` indirip çift tıklayın. Windows SmartScreen uyarısı çıkarsa **"Ek bilgi" -> "Yine de çalıştır"** butonuna basın.

### 🍎 macOS İçin:
- `CanEditor_3.6.3_universal.dmg` dosyasını indirip açın ve CanEditor simgesini Uygulamalar klasörüne sürükleyin. Açılışta güvenlik uyarısı verirse simgeye `Control` tuşuyla **sağ tıklayıp "Aç"** deyin.

### 🐧 Linux (Debian / Pardus / Ubuntu / Fedora / RedHat) İçin:
- **AppImage:** `CanEditor_3.6.3_amd64.AppImage` dosyasını indirin, terminalden `chmod +x CanEditor_3.6.3_amd64.AppImage` komutunu verip çift tıklayın.
- **Debian / Pardus / Ubuntu (.deb):** `sudo dpkg -i CanEditor_3.6.3_amd64.deb`
- **Fedora / RedHat / openSUSE (.rpm):** `sudo rpm -ivh CanEditor-3.6.3-1.x86_64.rpm`
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
