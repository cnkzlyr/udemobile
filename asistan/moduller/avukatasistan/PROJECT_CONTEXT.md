# ⚖️ AVUKAT ASİSTANI & TICKTICK ENTEGRASYON SİSTEMİ
**Proje Durum ve Mimari Devir Belgesi (Context Handover)**

Bu belge, bu projenin başka bir bilgisayarda (örneğin MacBook) Antigravity ile açıldığında ajanın projenin tüm yapısını, veritabanını ve en son tasarım kurallarını eksiksiz kavraması için hazırlanmıştır.

---

## 📌 Proje Genel Bakışı
Bu proje, bir avukatlık ofisinin **Google Takvim (Celse/Duruşmalar)** ve **UETS Elektronik Tebligatlarını (Gmail)** doğrudan **TickTick Open API** üzerinden TickTick görevlerine dönüştüren çift katmanlı (Bulut + Yerel Python) bir otomasyondur.

---

## 📁 Temel Dosyalar ve Rolleri

1. **`Avukat_Bulut_Otomasyonu_v4.js` (Google Apps Script - 7/24 Bulut Motoru):**
   - Google Cloud üzerinde periyodik tetikleyicilerle (Trigger) 7/24 çalışır.
   - Google Takvim'deki "AJANDA" takvimini tarar (`senkronizeDurusmalar`).
   - Gmail gelen kutusundaki "Yeni Elektronik Tebligat" maillerini tarar (`senkronizeUetsTebligatlari`).
   - Dosya kartlarını (Parent Task) mahkeme projelerinde otomatik açar.
   - Duruşma ve Tebligatları bu dosya kartlarına alt görev (subtask) olarak bağlar.
   - E-Tablo / Sheet üzerindeki müvekkil etiketlerini mevcut görevlere otomatik yansıtır (`senkronizeMevcutGorevEtiketleri`).
   - Duruşma günü/saati takvimde değişirse TickTick'teki mevcut görevin tarihini canlı günceller.

2. **`sync_hearings.py` (Yerel Duruşma Senkronizasyon Motoru):**
   - Celse / Google Takvim (.ics) dosyalarını okuyup TickTick API'ye senkronize eder.
   - Canlı mükerrer kontrolü ve parent task bağlama desteği vardır.

3. **`sync_uets.py` (Yerel UETS Senkronizasyon Motoru):**
   - Gmail IMAP veya indirilen `.eml` dosyalarından tebligatları ayrıştırır.

4. **`sync_uyap_excel.py` (UYAP Excel Dosyalar Senkronizasyon Motoru):**
   - UYAP'tan indirilen `dosyalar.xlsx` listesini Notion ("Tüm Dosyalar Düzenli") ve TickTick ile senkronize eder.
   - Dosya durumlarını (Açık -> Kapalı vb.) Notion'da otomatik günceller, yeni açılan davaları kaydeder.
   - Taraflardan müvekkili tanıyıp `Müvekkiller` veritabanı ile ilişkilendirir.
   - TickTick üzerinde eksik olan aktif Ana Dava Dosyası Kartlarını müvekkil etiketi ve Notion linkiyle açar.

5. **`clean_duplicates.py` & `ticktick_sync.py` (Mükerrer Temizleme ve Sağlık İyileştirme):**
   - Mükerrer görevleri not kaybetmeden birleştirir, üst-alt görev bağlarını ve etiketleri eşitler.

6. **Konfigürasyon ve Durum Dosyaları:**
   - `config.py`: Proje sabitleri, API anahtarları, kara liste ve etiket kuralları.
   - `state_manager.py`: İşlenen barkod ve görev hafızası.

---

## 📐 Kritik Tasarım Kuralları ve Bozulmaması Gereken Standartlar (Invariants)

1. **Elle Düzenlenen Başlıkların ve Notların Korunması (Title & Description Immutability):**
   - Kullanıcının TickTick veya Notion'da elle değiştirdiği görev başlıkları (`title`) ve eklediği notlar hiçbir senkronizasyon adımında **ASLA EZİLMEZ** (`title=None` kuralı).
   - Mükerrer birleştirme sırasında dahi silinecek kopyadaki özel notlar ana göreve `📌 BİRLEŞTİRİLEN EK NOTLAR` başlığı altında aktarılır; hiçbir veri kaybolmaz.

2. **Kapatılmış ve Yapılmayacak Görevlerin Mükerrer Koruması (Completed Tasks Safeguard):**
   - Kullanıcının `Tamamlandı` (status=2) veya `Yapılmayacak` (status=-1) olarak kapattığı görevler mükerrer aramasında mutlaka taranır (`get_completed_tasks_live()`).
   - Daha önce kapatılmış olan bir duruşma, tebligat veya ana dava kartı için **YENİDEN GÖREV AÇILMAZ**.

3. **CMK Müvekkil Etiketleri (`#cmk_isim`) ve Etiket Bütünlüğü:**
   - CMK dosyalarında `#cmk #necatican` gibi çoklu veya bölünmüş etiketleme **KESİNLİKLE KULLANILMAZ**.
   - Standart format tekildir: `#cmk_necatican`, `#cmk_ferhatakbas`, `#cmk_baneenzaid` vb. ve sistem otomatik olarak `#cmk` üst etiketini ekler.
   - Ana Dava Dosyası Kartlarına (Parent Tasks) ve Duruşmalara **ASLA `#uets` etiketi verilmez**; `#uets` yalnızca aktif e-tebligat görevlerine aittir.
   - `PARENT_TAG_MAP` (`aile`, `finans`, `tevkil` vb.) hiyerarşisi korunur.

4. **Alt Görev / Üst Görev (Parent-Child) Hiyerarşisi ve İyileştirme (Audit & Heal):**
   - Bir dava dosyasının Duruşma ve Tebligat görevleri her zaman ilgili mahkeme listesindeki **Ana Dava Dosyası Kartına (`parentId`)** bağlı olmalıdır.
   - Ana kart ve alt görevler her zaman aynı müvekkil etiketini taşır.
   - Yetim kalan (orphan) alt görevler otomatik olarak tespit edilip üst dava kartına bağlanır.

5. **Dosya Ekleri (Attachments & Notion Linkleri) Güvencesi:**
   - Görevlere eklenen e-posta ekleri (`.pdf`, `.udf`, `.eyp`) ve Notion dosya bağlantıları (`🔗 **Notion Dosyası:**`) hiçbir koşulda bozulamaz veya silinemez.

6. **Tebligat Görevleri (Tarih Aralığı & Sadelik):**
   - Etiket olarak `#TEBLİGAT` etiketi kullanılmaz. Yalnızca `#UETS` ve müvekkil etiketi kullanılır.
   - Tebligat görevleri tek bir gün değil, **e-Tebligatın ulaştığı günden yasal sürenin son gününe (14. gün, saat 17:00) kadar bir SÜRE ÇUBUĞU (Date Range / `startDate` - `dueDate`)** olarak kaydedilir.

---

## 🔑 Bağlantı Bilgileri
- **TickTick API Base:** `https://api.ticktick.com/open/v1`
- **Token:** `.env` dosyasında (`TICKTICK_TOKEN`), koda yazılmaz.
- **Takvim Adı:** `AJANDA`
- **Saat Dilimi:** `Europe/Istanbul` (GMT+3)

