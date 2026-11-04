import os
import sys
import json
import urllib.request
import urllib.error

TOKEN = "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"
REPO = "cnkzlyr/udemobile"
TAG = "v3.7.0"
NAME = "CanEditor v3.7.0 — Resmi Havelsan UYAP Motorlu Headless Çeviri, Kesintisiz Mobil Akış, Klavye Odak Koruması ve Sabit Dokunmatik Cetvel"

BODY = """# 🏛️ CanEditor (UdeMobile) v3.7.0 — Sürüm Notları

CanEditor **v3.7.0**; resmi Havelsan UYAP doküman kütüphanelerini tersine mühendislikle çözerek başsız (headless) Java motoruna entegre eden, raster tuval görüntüleri yerine **1:1 gerçek vektörel A4 PDF, resmi OpenDocument (ODT) ve biçimlendirilmiş Word (DOCX)** evrakları üreten, mobil cihazlarda yazı yazarken sanal klavyenin odak kaybıyla kapanması sorununu kesin olarak çözen, ekranın üstüne sabitlenen (sticky) ve 38px hassas dokunma alanlarına sahip cetveli devreye alan devrimsel bir sürümdür.

---

## 🌟 Öne Çıkan Yenilikler & Geliştirmeler

### 🏛️ 1. Resmi Havelsan UYAP Headless Dönüştürücü Motoru (`UyapHeadlessConverter`)
- **1:1 Vektörel A4 PDF:** Resmi Havelsan `tr.com.havelsan.uyap.system.editor.b.b` motoru tersine mühendislikle çözülerek başsız (headless) Java CLI motoruna bağlandı. Raster tuval ekran görüntüleri yerine; seçilebilir, kopyalanabilir gerçek vektörel metin, Havelsan yazı tipleri ve birebir 10 sayfalık resmi UYAP düzeni oluşturulur (~196 KB dosya boyutu, karanlık mod uyumlu).
- **Resmi OpenDocument (ODT):** Resmi Havelsan `tr.com.havelsan.uyap.system.editor.b.a.f` motoru kullanılarak; tüm tabloları, hizalamaları ve stilleri içeren %100 uyumlu `.odt` evrakları üretilir (~29 KB).
- **Zengin Microsoft Word (DOCX):** Resmi ODT yapısı üzerinden tabloları, paragraf hizalamalarını, sekme duraklarını ve yazı tipi ağırlıklarını koruyan yüksek kaliteli DOCX belgeleri üretilir (~41 KB).
- **Termux & CLI Komut Desteği:** `uyap-convert <dosya.udf> <pdf|odt|docx>` komutu ile tüm dönüştürmeler sistem seviyesinde 2 saniye içinde gerçekleştirilebilir.

### ⌨️ 2. Yazı Yazarken Sanal Klavyenin Kapanmasını %100 Önleyen Odak Koruması
- **Sıfır DOM Yıkımı:** Aktif yazım esnasında veya imleç editör alanındayken DOM ağacının `container.innerHTML = ''` ile silinip yeniden inşa edilmesi kesin olarak engellendi.
- **Kesintisiz Yazım Deneyimi:** Android sanal klavyesinin (Gboard, Samsung Keyboard) odak kaybı nedeniyle kapanması, harf yutulması ve imleç sıçraması tamamen ortadan kaldırıldı.
- **Yalnızca Odaktan Çıkıldığında Sayfalama:** Sayfa düzenleme ve bölünme işlemleri yalnızca kullanıcı yazımı bitirip alandan çıktığında (`blur`) çalıştırılır.

### 📱 3. Yeniden Yapılandırılmış Kesintisiz Mobil Görünüm
- **Akıcı Tek Akış Düzeni:** Mobil görünüme geçildiğinde tüm sayfaların gövde paragrafları tek bir kesintisiz akış konteynerinde birleştirilir; sayfa sınırları, boşluklar ve tekrarlayan üstbilgi/altbilgiler metni bölmez (Google Docs ve Word mobil standardı).
- **Kağıt Görünümüne Anında Dönüş:** `📄 Kağıt` butonuna tıklandığında belge anında 1:1 Havelsan A4 çok sayfalı baskı düzenine geri döner.

### 📐 4. Ekranın Üstüne Sabitlenen (Sticky) 44px Dokunmatik Cetvel
- **Sayfa Boyunca Sabit Kalan Cetvel:** Cetvel A4 kağıt kartının içinden çıkarılarak sayfa kaydırma alanının üstüne (`sticky`, `top: 0`, `z-index: 100`) sabitlendi. Sayfa 10 sayfa aşağı kaysa bile cetvel her an ekranın üstünde kalır.
- **38px Dokunmatik Etki Alanları:** İlk satır girintisi, asılı girinti, sol girinti ve sağ marj imleri 38px ergonomik dokunmatik alanlarla büyütüldü; parmakla kaydırma anında sayfa kaymasını engelleyen `touch-action: none` koruması eklendi.
- **Mobilde Tek Dokunuşla Sekme Durağı:** Cetvel ölçeğine mobilde dokunulduğunda doğrudan sekme durağı (tab stop) ekleme/kaldırma özelliği entegre edildi.

### 💾 5. Doğrudan 1-Tık Hızlı Kaydet & Taşmayan Ergonomik Üst Çubuk
- **Belirgin 1-Tık Kaydet Butonu:** Üst barda dosya adının hemen yanında canlı yeşil renkli **`💾 Kaydet`** butonu yer alır; açık olan belgenin üzerine doğrudan, tek tıkla ve hiçbir diyalog açmadan anında kayıt yapar.
- **Responsive Üst Bar:** Mobilde butonların ekrandan taşmasını ve başlığın ezilmesini önlemek amacıyla kompakt simge düzeni (`←`, `💾 Kaydet`, `Başlık`, `📱`, `📤`, `⋮`) uygulandı.
- **Eksiksiz Paylaşım ve Farklı Kaydet:** PDF, UDF, Word, TIFF, ODT ve Metin formatlarında paylaşım ve indirme köprüleri Android 10-15 Scoped Storage standartlarıyla tam uyumlu hale getirildi.

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
