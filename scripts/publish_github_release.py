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
NAME = f"CanEditor v{VERSION} — Birleşik Hukuk Platformu, Termux'suz Asistan ve Çapraz Platform UYAP Editörü"

BODY = f"""# CanEditor v{VERSION} — Birleşik Hukuk Platformu & Çapraz Platform UYAP Editörü

## 🌟 v{VERSION} ile Gelen Yenilikler ve Düzeltmeler

### 1. ✍️ Çoklu E-İmza & Birlikte İmza (Co-signing) & Sürücüsüz Token Desteği
- **Çift Smart Kart & Hotplug Desteği:** İki e-imza tokenı aynı anda takıldığında veya biri çıkarıldığında sistem çıkarılan cihazı anında bellekten temizler, kalan/takılan yeni kartı anında aktif eder.
- **Birlikte İmzalama (Co-signing):** Önceden imzalanmış bir belgeye ikinci bir avukat/yetkili imza atmak istediğinde karşılaşılan `"Bu belge imzalı ve değişiklik yaptınız"` engeli giderildi. Belge içeriği snapshot karşılaştırmasıyla doğrulanarak imzalı belgenin e-imza zarfına (`sign.sgn`) ikinci imza blokları eklendi.
- **Android Bağımsız İmza Birleştirme:** Android cihazlarda yerel mikroservis portuna ihtiyaç kalmadan WebView içindeki `window.ESign.combineB64` köprüsüyle doğrudan uygulama içinde imza birleştirilir.

### 2. 📄 Sayfalama Motoru & Yetim Başlık Koruması (Keep-With-Next)
- **Yetim Başlık Koruması:** `NETİCE-İ TALEP:`, `SONUÇ VE İSTEM:`, `AÇIKLAMALAR:` gibi hukuki başlıkların sayfa dibinde tek satır kalması engellendi. Başlıklar otomatik olarak bir sonraki paragrafla birlikte yeni sayfaya taşınır.
- **Akıllı Bölme Sınırları:** Başlık niteliğindeki satırlarda paragraf bölme devre dışı bırakıldı.

### 3. 🖼️ Taranmış PDF ve TIFF Görüntüleyici Düzeltmesi (GPU Bellek Aşımı)
- **Beyaz / Boş Sayfa Çözümü:** CamScanner veya tarayıcılardan gelen yüksek çözünürlüklü (3000x4000+) makbuz ve evrakların Android WebView doku sınırını (4096px) aşması nedeniyle oluşan beyaz sayfa hatası giderildi. Maksimum tuval boyutu güvenli 2048px ile sınırlandı ve arka plan beyazla dolduruldu.

### 4. 🐍 Java Bağımsız Saf Python UDF → PDF Motoru (ReportLab)
- **Java Yokken Bile PDF Çıktısı:** Sistemde Java/JRE bulunmadığında devreye giren saf Python ReportLab motoru eklendi. UDF XML verisi doğrudan okunarak standart A4 PDF üretilir.

### 5. 🔍 Genişletilmiş Türkçe UYAP Evrak Araması
- **10 Farklı Alanda Tam Arama:** Evrak arama; evrak türü, açıklama, gönderen, mahkeme birimi, dosya esas no, taraflar ve müvekkil alanlarının tamamında arama yapar.
- **Türkçe Karakter Duyarsızlığı:** Türkçe İ/ı, Ş/s, Ğ/g, Ç/c, Ö/o, Ü/u harfleri SQLite LIKE sorgularında çapraz varyantlarla desteklenir.

### 6. 🔔 Yeni Evraklar Toplu Yönetimi & Sayfalama
- **Toplu Seçim:** Her evrak için onay kutusu (checkbox) ve "Tümünü Seç" kutusu eklendi.
- **Toplu Eylemler:** "Seçilenleri İndir", "Seçilenleri PDF'e Dönüştür", "Drive'a Gönder" ve "Görüldü Say" işlemleri eklendi.
- **Doğrudan İndirme:** Henüz indirilmemiş evraklar için tek tıkla `⬇️ İndir` butonu ve mahkemeye doğrudan gidiş bağlantısı eklendi.
- **Sayfalama:** 2000+ yeni evrak bulunan durumlarda WebView donmasını önleyen +50'şer dinamik sayfalama getirildi.

### 7. 📁 Dosyalar Sekmesi: Kart, Tablo, Ağaç (Hiyerarşik) ve Dosya Hesapları
- **4 Farklı Görünüm:** Kart, Tablo, Ağaç (Ceza / Hukuk / İcra / İdare / BAM hiyerarşisi) ve Dosya Hesapları modları arasında tek tıkla geçiş.
- **Gelişmiş Filtreleme:** Yargı türü (Ceza, Hukuk, İcra, İdare, BAM) ve sıralama seçenekleri.

### 8. 💰 İcra & Dosya Hesapları Paneli
- **Finansal Göstergeler:** Toplam Takip & Alacak, Tahsil Edilen Tutar (% tahsilat oranı), Kalan Tahsil Edilmemiş Bakiye ve Mahkemede Artan Gider Avansı kartları.
- **Ayrıntılı Hesap Tablosu:** Asıl alacak, işlemiş faiz, vekalet ücreti, masraf/harç, toplam borç, tahsilat ve bakiye borç dökümü.
- **Dışa Aktarım:** Tüm dosya hesaplarını tek tıkla Türkçe Excel / CSV olarak indirme.

### 9. ☁️ Kesintisiz Google Drive Sync & Webhook Rehberi
- **Sürekli Durum Rozeti:** Asistan başlığında her an canlı Drive senkronizasyon durumu (Bulut / Bağlı / Salt Okunur / Boşta) gösterilir.
- **Adım Adım Kurulum Kılavuzu:** Telefon tarayıcısından 1 dakikada kurulabilen Google Apps Script Web App rehberi ve URL doğrulama denetimleri.

### 10. ⚖️ Zenginleştirilmiş HAYFA İçtihat & Uygulama İçi Mevzuat Okuyucusu
- **Yargıtay Daire & Konu Filtreleri:** 1-12. Hukuk, 1-16. Ceza, HGK, CGK daire filtreleri ve hızlı konu etiketleri.
- **Asla Anonimleştirilmeyen Metin:** Kararlar tüm gerekçe, taraf ve kanun maddeleriyle sansürsüz ve tam metin olarak sunulur.
- **Uygulama İçi Mevzuat Okuyucusu:** Kanun ve yönetmelikler harici tarayıcıya gitmeden uygulama içinde okunabilir ve dilekçeye aktarılabilir.

### 11. 📅 Ajanda & Süreli İşler
- **Hızlı Tarih Filtreleri:** Son 1 Gün, 3 Gün, 1 Hafta, 2 Hafta, 1 Ay, 3 Ay, 6 Ay ve özel tarih aralığı butonları.
- **UETS Yasal Süre Sayacı:** Kalan gün sayacı ve son gün renkli uyarı rozetleri.

### 12. 📊 Rolling Loglama & Hata Teşhis ZIP Paketi
- **Otomatik Rotasyon:** 2MB boyut sınırıyla 10 adet yedekli dönen log sistemi.
- **Tek Tıkla İndirme:** Destek ve hata çözümü için tüm logları ve sistem tanısını içeren `CanEditor_Loglar.zip` paketi indirme imkanı.

### 13. 🚀 Android Ana Ekrandan Doğrudan Hukuk Asistanı
- **Tek Dokunuşla Asistan:** `MainActivity` açılış ekranına eklenen "⚖️ CanEditor Hukuk Asistanı" butonuyla editöre girmeden dosyalara, ajandaya ve içtihatlara erişim.
- **UDF ve USF Varsayılan Açıcı:** Android sisteminde `.udf` ve `.usf` dosyaları CanEditor ile doğrudan ilişkilendirildi.

## 📦 İndirme Bağlantıları
- **Android:** `CanEditor-v{VERSION}.apk` / `CanEditor-latest.apk`
- **Windows:** `CanEditor_{VERSION}_x64-setup.exe` (NSIS) / `CanEditor_{VERSION}_x64_en-US.msi` (MSI)
- **macOS:** `CanEditor_{VERSION}_universal.dmg` (Apple Silicon & Intel)
- **Linux:** `CanEditor_{VERSION}_amd64.AppImage` / `CanEditor_{VERSION}_amd64.deb` / `CanEditor-{VERSION}-1.x86_64.rpm`
- **Taşınabilir Web:** `CanEditor-Portable-Web-GUI-v{VERSION}.zip`
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
