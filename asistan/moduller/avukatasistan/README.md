# ⚖️ Avukat Asistanı

UETS'ye gelen elektronik tebligatları **kendiliğinden indirir**, yasal süresini hesaplar, **TickTick'te görev**
açar, duruşmaları ayrı görev yapar, Notion'daki dosya kartını günceller ve sorun olursa **Telegram'dan haber verir**.
Android tablette (Termux) çalışır; Linux/Mac/Windows'ta da çalışır.

```
 UETS (e-tebligat)          UYAP dosya listesi (xlsx)
        │                              │
        ▼                              ▼
  liste + EYP paketleri         dosya/taraf/durum bilgisi
        │                              │
        └──────────► Avukat Asistanı ◄─┘
                      │      │      │
              TickTick   Notion   Telegram
              (görev)   (dosya)  (bildirim)
```

---

## 1. İlk kurulum (bir kez)

Termux'ta:

```bash
pkg install -y git python
git clone https://github.com/cnkzlyr/avukatasistan ~/avukatasistan
cd ~/avukatasistan
bash kurulum_telefon.sh        # Chromium, Python paketleri, depolama izni, 'asistan' komutu
source ~/.bashrc
asistan durum                  # her şey ✅ mi?
```

`asistan durum` hangi ayarın eksik olduğunu gösterir. Gizli bilgiler (şifreler, anahtarlar) proje klasöründeki
**`.env`** dosyasındadır — bkz. [Bölüm 8](#8-güvenlik-env-dosyası).

> `asistan` komutu yoksa her yerde `python3 asistan.py ...` yazabilirsiniz (proje klasöründeyken); aynı şeydir.

---

## 2. Günlük kullanım: bilmeniz gereken 4 komut

| Ne istiyorsunuz? | Komut |
|---|---|
| **Şimdi bir kez** kontrol etsin (UETS'ye girer, yeni tebligatları TickTick/Notion'a işler) | `asistan calistir` |
| **Sürekli** kendisi kontrol etsin (30 dk'da bir UETS, 2 saatte bir düzen denetimi) | `asistan izle` |
| UYAP'tan indirdiğim **dosya listesini** işlesin | İndirilenler'e koymanız yeter (izleyici işler) ya da `asistan uyap-liste` |
| Bir şey ters gitti, **size göndermek için kayıt** alsın | `asistan tani` |

Diğerleri:

| Komut | Ne yapar |
|---|---|
| `asistan` | Komut listesini gösterir |
| `asistan durum` | Ayarlar, TickTick erişimi, klasörler, izleyicinin son çalışması |
| `asistan denetim` | UETS'ye girmeden yalnızca TickTick düzen denetimi (kimlik satırları, dava kartları, mükerrerler) |
| `asistan rapor` | **Hiçbir şeyi değiştirmeden** sorunlu görevleri ve tebligat/TickTick/Notion uyumsuzluklarını listeler |
| `asistan takvim` | AJANDA takvimindeki duruşmaları şimdi TickTick'e işle (izleyici bunu her turda yapar) |
| `asistan catisma "AD SOYAD"` | Bu kişi/kurum hangi dosyalarda, hangi rolde geçiyor? (yeni müvekkil almadan önce) |
| `asistan catisma` | Olası çıkar çatışmaları: aynı dosyada karşı karşıya taraflarda müvekkillerimiz |
| `asistan defter` | Dosya defteri özeti; `asistan defter tasi "mysql+pymysql://..."` ile Plesk'e taşıma |
| `asistan panel` | Dokunmatik kontrol paneli (Termux:X11 gerekir) |
| `asistan test` | Otomatik testler (gerçek hesaplara dokunmaz) |

Ek seçenekler:
- `asistan calistir --force` → EYP inmemiş olsa bile görevi hemen aç
- `asistan calistir --offline` → UETS'ye bağlanma, yalnızca diskteki son liste/EYP'lerle çalış
- `asistan izle --uets-dk 15 --denetim-dk 60` → aralıkları değiştir
- `asistan izle --bir-kez` → bir tur çalış ve çık

**`asistan izle` açık kaldığı sürece çalışır.** Termux'u kapatırsanız durur. Ekran kapalıyken de çalışması için
uyku kilidi kendiliğinden alınır. Termux bildiriminden "Exit" demediğiniz sürece arka planda devam eder.

---

## 3. Bir tebligat geldiğinde ne olur?

1. **UETS:** Tarayıcıyla giriş yapılır (şifre + Gmail'e gelen SMS kodu otomatik okunur). Oturum açık tutulur,
   her turda kod istenmez. Gelen kutusu portalın kendi servisinden **eksiksiz** alınır (ekranda görünen 10 satır değil).
2. **EYP paketi** indirilir (üst yazı, karar, rapor vb.). Sırayla 3 yol denenir; biri çalışmazsa diğeri.
3. **Süre hesabı:** Geliş + 5 gün = tebliğ sayılır. Mercie göre **7 gün** (icra/ceza), **14 gün** (hukuk) ya da
   **30 gün** (idari yargı); son gün hafta sonuna denk gelirse ilk iş gününe, saat **17:00**.
4. **TickTick:**
   - Tebligat için görev açılır: süre çubuğu (gelişten son güne), öncelik yüksek, `#uets` + müvekkil etiketi.
   - Görev, mahkeme listesindeki **dava kartının** (üst görev) altına konur. Kart yoksa açılır.
   - EYP'deki evraklar görevin altına **"📎 EYP ekleri"** alt görevi olarak eklenir (dosyalar orada açılır).
   - EYP 6 saat içinde inmezse görev **eksiz** açılır (süre kaçmasın); ek sonra eklenir.
   - Esas numarası olmayan tebligatlar (noter AZİLNAME vb.) da görev olarak açılır.
5. **Duruşma:** Asıl kaynak **AJANDA takvimi** (bkz. Bölüm 5b). Evrakta duruşma günü varsa da görev açılır;
   aynı duruşma için ikinci görev açılmaz. Tarihi geçmiş ya da daha önce kapattığınız duruşma için görev açılmaz.
6. **Dosya defteri:** Dosya UYAP listesinde **kapalı** görünüyorsa Telegram'dan "kapalı dosyaya tebligat" uyarısı
   gelir; müvekkil Notion'da bulunamazsa defterden (UYAP listesi) alınır; tebligat deftere kaydedilir.
7. **Notion:** Dosya kartındaki tebligat/duruşma alanları ve not kutusu güncellenir.
8. **Telegram:** Yeni görev açıldığında ve hata olduğunda bildirim gelir.

---

## 4. TickTick'te sizin serbest olduğunuz şeyler

Sistem görevleri **notun en üstündeki kimlik satırından** tanır, başlıktan değil:

```
🔖 KİMLİK · TEBLİGAT · Mahkeme: Oltu 3. Asliye Hukuk Mahkemesi · Esas: 2026/24 · Barkod: 5003283066058
```

Bu yüzden şunları **istediğiniz gibi** yapabilirsiniz, sistem bozmaz ve geri almaz:

| Siz yaparsınız | Sistem ne yapar |
|---|---|
| Başlığı "Cevap dilekçesi yazılacak" gibi değiştirmek | Başlığa **hiç dokunmaz**; mahkeme/esas kimlik satırında kalır |
| Etiket eklemek, önceliği değiştirmek | Korur |
| Görevi başka listeye taşımak | Orada bulur, geri taşımaz |
| Görevi kendi görevinizin altına koymak | Üst görevi değiştirmez (yalnızca üstü olmayanları dava kartına bağlar) |
| Alt görev, kontrol listesi, hatırlatma eklemek | Korur; alt görevi olan görev hiçbir temizlikte silinmez |
| Görevi tamamlamak / "yapılmayacak" yapmak | Aynı tebligat için **yeniden açmaz** |

Tek rica: **kimlik satırını silmeyin** (silinirse denetim yeniden ekler). Aynı tebligat için ikinci görev açılmaz;
mükerrer olursa birleştirilir, **sizin başlığınız** ve notlarınız kalır. Farklı barkodlu tebligatlar asla birleşmez.

---

## 5. UYAP dosya listesi ve dosya defteri

UYAP Avukat Portalı'ndan dosya listesini (açık + kapalı, taraflarıyla) Excel olarak **İndirilenler'e** kaydedin
(`dosyalar*.xlsx`). **İzleyici açıksa başka bir şey yapmanız gerekmez:** yeni listeyi kendisi fark eder ve işler.
Elle de çalıştırabilirsiniz:

| Komut | Ne yapar |
|---|---|
| `asistan uyap-liste` | **Önizleme**: Notion/TickTick'e dokunmaz; yalnızca dosya defterini günceller ve neyin değişeceğini gösterir |
| `asistan uyap-liste --guvenli` | Notion durumlarını günceller, Notion'a yeni dosyaları ekler, açık dosyalara TickTick kartı açar. **Kart kapatmaz** (izleyici bu modu kullanır) |
| `asistan uyap-liste --uygula` | Yukarıdakiler + kapanan dosyaların TickTick kartlarını kapatır |

Kart kapatma kuralı: **altında açık iş** (tebligat, duruşma ya da kendi alt görevleriniz) olan dava kartı
**kapatılmaz**; size listelenir (izleyicide Telegram'a gelir). İşler bitince bir sonraki listede kapanır.

**Dosya defteri** (`veri/defter.db`) her listeyle güncellenen kalıcı kayıttır:
- Her dosya, tüm tarafları ve rolleri (Davacı, Sanık...), hangisinin müvekkilimiz olduğu (Notion Müvekkiller ile)
- Durum geçmişi (ne zaman Açık → Kapalı oldu), gelen tebligatlar ve takvimdeki duruşmalar
- Her yeni listede **değişiklik özeti** Telegram'a gelir: yeni dosyalar, durumu değişenler, listeden çıkanlar
- **Olası çıkar çatışması**: aynı dosyada karşı karşıya taraflarda (Davacı ↔ Davalı, Katılan ↔ Sanık...) iki
  müvekkilimiz varsa Telegram'a bir kez uyarı gelir. `asistan catisma "AD"` ile bir adın geçtiği her dosyayı görürsünüz.
- Aynı liste iki kez işlenmez. Defter git'e gönderilmez (müvekkil verisi içerir).

Defter ileride **Plesk hostinge** tek ayarla taşınır: adım adım rehber [`docs/PLESK.md`](docs/PLESK.md).

## 5b. Duruşmalar: AJANDA takvimi asıl kaynak

Duruşmalar Google Takvim'deki **AJANDA** takvimine UYAP'tan kendiliğinden geliyor; sistem TickTick'i oradan besler.
Bir kez ayar (`.env`):

```
AJANDA_ICS_URL=...      Google Takvim > Ayarlar > AJANDA > "Takvimi entegre et" > "iCal biçimindeki gizli adres"
AVUKAT_ADI=AD SOYAD     (takvim açıklamasındaki "[Vekil: ...]" adınız; yazmazsanız en sık geçen vekil adı alınır)
```

Sonra (izleyici bunu her turda yapar):
- Yeni duruşma / keşif / ön inceleme → dava kartının altına **⚖️ DURUŞMA** görevi, doğru saatle
- **Ertelenen** duruşma → aynı görevin tarihi kaydırılır, notuna "ertelendi: eski → yeni" yazılır (başlığınız korunur)
- Takvimden **silinen/iptal** edilen duruşma → görev silinmez, Telegram'dan haber verilir
- Takvimde aynı duruşma iki kez varsa (UYAP + elle girilen) **tek görev** olur
- Müvekkil, açıklamada vekili siz olan taraftan **kesin** okunur ("Davacı:… [Vekil: … sizin adınız …]")

> Gizli iCal adresi takviminizi okumaya yeter; başkasıyla paylaşmayın. `.env` dosyasında durur.

## 6. Sorun olduğunda

1. `asistan durum` → kırmızı (❌) satır var mı?
2. `asistan tani` → çalışır, sonunda **`/sdcard/Download/UETS_Arsivi/tani/uets_tani_TARİH.zip`** üretir.
   İçinde her adımın ekran görüntüsü, sayfa kodu, ağ ve hata kayıtları vardır (şifre/TCKN/kodlar maskeli).
   Bu zip'i gönderin.
3. İzleyici kayıtları: `izleyici.log` (proje klasöründe).
4. TickTick'in reddettiği istekler: `ticktick_hatalar.log`. "TICKTICK_TOKEN geçersiz" görürseniz TickTick'ten yeni
   anahtar alıp `.env` dosyasına yazın.

Sık görülenler:

| Belirti | Neden / çözüm |
|---|---|
| "Doğrulama kodu gelmedi" | Gmail'de "UETS Giriş Kodu" etiketi/filtresi duruyor mu? `.env`'de `GMAIL_APP_PASS` doğru mu? |
| "TickTick'te var ama EYP eki eksik" her seferinde | Ek e-postası TickTick'e gidiyor mu? `.env`'de `TICKTICK_EMAIL` doğru mu? |
| Görev açılmadı, "SÖZLEŞME İHLALİ" yazıyor | Görev kurallara uymadığı için durduruldu; ayrıntı `karantina.jsonl` dosyasında |
| İki izleyici açtım | İkincisi kendiliğinden kapanır (aynı anda tek izleyici çalışır) |
| İşlem sırasında internet koptu (Wi-Fi → mobil veri) | Bir şey yapmanız gerekmez: sistem bekler, bağlantı gelince **kaldığı yerden** devam eder (aşağıya bakın) |

### 🧭 Asistan notları (her görevin ve dava sayfasının altında)

```bash
asistan notlar                     # ÖNİZLEME: kaç göreve ne yazılacak, örnekler (hiçbir şey değişmez)
asistan notlar --uygula --en-cok 5 # önce 5 görev/sayfada deneyin, TickTick ve Notion'da bakın
asistan notlar --uygula            # hepsine yaz (sonra izleyici her denetim turunda güncel tutar)
```

Tebligat, duruşma ve dava kartı görevlerinin notunun **en sonuna**, Notion dava sayfalarının **en sonuna** işaretli bir
"🧭 ASİSTAN NOTU" bölümü eklenir:

- **Bilgi:** UYAP durumu ve taraflar (dosya defterinden), son gün / duruşma günü (kesin tarih), sıradaki duruşma,
  açık tebligat sayısı ve en yakın son gün, Notion'da TickTick bağlantıları.
- **Evraka göre hatırlatma:** bilirkişi raporu (HMK 281), karar (istinaf/temyiz: HMK 345/361, İYUK 45/46),
  karşı tarafın istinaf/temyiz dilekçesi (HMK 347/364), dilekçe tebliği (HMK 127/136, İYUK 16), tensip, ara karar,
  iddianame, mütalaa, ödeme emri (İİK 62), avans/harç. Genel bilgidir; dosyadaki ara karar/kesin süre esastır.
- **Eksik / kontrol edilecek:** son günü geçmiş açık tebligat, eklenmemiş EYP evrakı, dava kartına bağlı olmayan görev,
  müvekkil etiketi yok (UYAP listesindeki müvekkil önerilir), Notion bağlantısı yok, kimlik satırı yok, aynı gün ±2 saat
  içinde **çakışan duruşma** (tevkil/mazeret), boş duruşma hazırlık bölümleri, UYAP'ta kapalı dosyaya tebligat/duruşma,
  UYAP listesinde görünmeyen dosya; Notion'da UYAP ile farklı durum, boş MÜVEKKİLLER / DOSYA TÜRÜ alanı, TickTick
  kartı olmayan açık dosya.

Güvence: sizin yazdıklarınız, başlık, tarih, etiket, hatırlatıcı, alt görev ve kontrol listesi **aynen kalır**
(görev okunup diğer alanları olduğu gibi geri gönderilir; okuduktan sonra siz değiştirdiyseniz o tur yazılmaz).
Sonraki çalışmalarda yalnızca bu bölüm güncellenir, değişmediyse hiç yazılmaz. **Bölümü silerseniz bir daha eklenmez.**
Kapalı Notion dosyaları (TickTick'te işi yoksa) atlanır; hepsi için `--hepsi`. Yalnız TickTick için `--notion-yok`.

### Bağlantı kopması ve yarım kalan işler

Telefon Wi-Fi'den mobil veriye geçerken, tünelde ya da uçak modunda istekler yarıda kalabilir. Sistem bunun için:

1. **Ön kontrol:** `calistir`, `uyap-liste`, `takvim` işe başlamadan internet ve anahtarları denetler
   (`🚦 Ön kontrol: ✅ ...`). İnternet yoksa gelene kadar bekler; anahtar geçersizse hiç başlamaz.
2. **Bekle ve devam et:** İş sırasında bağlantı koparsa önce birkaç kez kısa aralıklarla dener
   (`📶 ... yeniden denenecek`), olmazsa bağlantı gelene kadar **15 dakikaya kadar** bekler
   (`📶 Bağlantı yok: ... kaldığı yerden devam edilecek`) ve aynı noktadan sürer.
3. **Kopya yok:** Okuma yarım kalırsa liste asla "boş" sayılmaz (yoksa var olan kart "yok" sanılıp kopyası açılırdı).
   Yanıtı kaybolan bir "oluştur" isteği tekrar gönderilmeden önce "zaten oluşmuş mu?" diye bakılır.
4. **Güvenli durma:** 15 dakikada da bağlantı gelmezse hiçbir şey yazmadan/silmeden durur
   ("Bağlantı sorunu, işlem güvenle durduruldu"). Aynı komutu tekrar çalıştırmak yeter: yapılmış adımlar atlanır.
5. **İşlem günlüğü:** Her yazma `veri/islem_gunlugu.jsonl` dosyasına kaydedilir. Telefon/Termux iş ortasında
   kapanırsa yarım kalanlar `asistan durum` ekranında ve denetimde görünür.
6. **Bütünlük denetimi** (izleyicide her denetim turunda, bağlantı geri geldiğinde hemen, ayrıca `asistan denetim`,
   `uyap-liste --uygula` ve `calistir` sonunda):
   - mükerrer tebligat, duruşma ve **dava kartlarını** birleştirir: notlar ve etiketler ana karta taşınır, boş kopya
     silinir; **alt görevi olan kopya asla silinmez**, size bildirilir,
   - Notion'da aynı başlıklı dosya sayfalarını bildirir (Notion'da silme yapılmaz),
   - yarım kalmış yazmaları kontrol edip bildirir.
   Bulgular Telegram'a bir kez gönderilir.
7. **İzleyici** internet yokken tur başlatmaz (yarım iş olmasın), 2 dakikada bir bakar; bağlantı gelince kaçırılan
   turları ve bütünlük denetimini hemen yapar. Kısa kesintiler Telegram'a hata olarak gitmez.

Ayarlar (`.env`, isteğe bağlı): `BAGLANTI_BEKLEME_SN=900` (en uzun bekleme), `TICKTICK_YENIDEN_DENEME=4`.

---

## 7. Dosyalar ne işe yarar

**Sizin çalıştıracağınız tek dosya `asistan.py`.** Diğerleri onun kullandığı parçalardır.

| Dosya | Görevi |
|---|---|
| `asistan.py` | **Giriş noktası** (bütün komutlar) |
| `main.py` | Bir tur: UETS indir → eşleştir → TickTick/Notion |
| `izleyici.py` | Sürekli çalışan tur + denetim döngüsü |
| `uets_downloader.py` | UETS'ye giriş, liste ve EYP indirme (tarayıcı) |
| `uets_api.py` | UETS portalının servisiyle doğrudan liste/EYP |
| `uets_tani.py` | Teşhis kaydı (`asistan tani`) |
| `csv_parser.py`, `eyp_parser.py`, `ics_parser.py` | Tebligat listesi, EYP paketi, takvim (.ics) okuyucular |
| `ticktick_sync.py` | TickTick görev açma/güncelleme, ekler, mükerrer temizliği, denetim |
| `kimlik.py` | Görev kimlik satırı |
| `gatekeeper.py` | Görev kuralları (kurala uymayan görev açılmaz) |
| `notion_sync.py` | Notion dosya kartları |
| `sync_uyap_excel.py` | UYAP dosya listesi işleme (`asistan uyap-liste`) |
| `baglanti.py` | Bağlantı dayanıklılığı: ön kontrol, kopunca bekleyip devam, yanıtı kaybolan yazmaların doğrulanması, işlem günlüğü |
| `asistan_notu.py` | 🧭 Asistan notları: görev ve Notion sayfalarının sonuna yardımcı bilgi + eksik listesi (var olana dokunmadan) |
| `butunluk.py` | Bütünlük denetimi: mükerrer tebligat/duruşma/dava kartı, Notion'da aynı başlıklı sayfalar, yarım kalmış işler |
| `defter.py` | Dosya defteri: dosyalar, taraflar, durum geçmişi, tebligatlar, duruşmalar (SQLite → Plesk MySQL) |
| `takvim.py` | AJANDA takvimi → TickTick duruşma eşitlemesi |
| `autocontrol.py` | Çapraz denetim raporu (`asistan rapor`) |
| `mail_sender.py` | TickTick'e e-postayla dosya gönderme |
| `state_manager.py` | Hangi tebligatın işlendiğinin hafızası (`~/.avukat_asistan_state.json`) |
| `utils.py`, `config.py` | Yardımcılar, süre hesabı, ayarlar |
| `avukat_gui.py`, `baslat_gui.sh` | Dokunmatik panel (`asistan panel`) |
| `kurulum_telefon.sh` | Termux kurulumu |
| `tests/` | Otomatik testler |
| `araclar/` | Tek seferlik / geliştirici araçları (aşağıda) — günlük kullanımda gerekmez |
| `uyap_app/` | Ayrı proje: UYAP Avukat Portalı keşif aracı ve arayüzü |
| `telegram_tevkil/` | Ayrı proje: Telegram tevkil botu |

`araclar/` içindekiler (gerekirse `python3 araclar/DOSYA.py`):

| Araç | Ne için |
|---|---|
| `sentinel.py` | TickTick kural raporu (salt okunur; `asistan rapor` bunu çağırır) |
| `ticktick_audit.py` | TickTick salt okunur döküm |
| `cleanup_ticktick.py` | Toplu temizlik (önce önizleme, `--apply` ile uygular) |
| `clean_duplicates.py` | Yalnızca mükerrer temizliği |
| `distribute_attachments.py`, `attach_petitions_to_tasks.py` | Eski ek/dilekçe dağıtma araçları |
| `generate_pending_petitions.py`, `document_builder.py`, `pdf_builder.py` | Dilekçe taslağı üretimi (UDF/ODT/PDF) |
| `uets_recorder.py` | UETS'de yaptığınız tıklamaları kaydeden geliştirici aracı |

---

## 8. Güvenlik: `.env` dosyası

Şifreler ve anahtarlar **kodda değil**, proje klasöründeki `.env` dosyasındadır (git'e gönderilmez, yalnızca siz
okuyabilirsiniz). Biçim:

```
TICKTICK_TOKEN=...          NOTION_TOKEN=...
UETS_TCKN=...               UETS_PASSWORD=...
GMAIL_USER=...              GMAIL_APP_PASS=...        (Gmail "uygulama şifresi")
TICKTICK_EMAIL=todo+...@mail.ticktick.com             (TickTick > Ayarlar > E-postayla görev ekle)
TELEGRAM_BOT_TOKEN=...      TELEGRAM_CHAT_ID=...
AJANDA_ICS_URL=...          AVUKAT_ADI=...            (duruşma takvimi, Bölüm 5b)
DEFTER_URL=...              (yalnızca Plesk'e taşıyınca; yoksa tablette veri/defter.db)
EYP_BEKLEME_SAAT=6          (EYP bu kadar saat inmezse görev eksiz açılır; -1: hiç açma)
```

Bu değerler eskiden kodda yazılıydı ve git geçmişinde duruyor: **hepsini yenileyip** `.env` dosyasına yazın.

---

## 9. Geliştirme notları

- Testler: `asistan test` (sahte UETS ve sahte TickTick sunucularıyla; gerçek hesaba istek gitmez).
- Sahte sunucuya yönlendirme: `UETS_PORTAL_URL`, `UETS_API_URL`, `TICKTICK_API_BASE`, `UETS_CHROME_BIN`,
  `UETS_CHROMEDRIVER` ortam değişkenleri.
- Mimari ayrıntıları: `PROJECT_CONTEXT.md`, UYAP servis keşfi: `API_DOCS.md`.
