# 📖 UYAP Hukuk Otomasyonu Kolay Kullanım Kılavuzu & Tutorial
**© 2026 Av. Can KIZILYAR — Tüm hakları saklıdır.**

Bu kılavuz; UYAP dava dosyalarını tek komutla indirip Google Drive'a yedekleyen **`uyap-arsiv`** ile UDF belgelerini USB token veya Mobil İmza ile saniyeler içinde imzalayan **`uyap-imzala`** araçlarının adım adım kullanımını açıklar.

Platformlar: **Android (Termux)**, **Windows 10/11**, **Linux (Ubuntu / Fedora)** ve **macOS**.

---

## 🧭 Hangi Araç Ne İşe Yarar?

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 UYAP AVUKAT ARAÇLARI                                   │
├───────────────────────────────┬────────────────────────────────────────────────────────┤
│ 📦 uyap-arsiv                 │ İstediğiniz bir davanın tüm evraklarını (UDF, TIFF,    │
│                               │ PDF) UYAP'tan çeker, PDF'e çevirir, mükerrerleri atlar,│
│                               │ Google Drive'a aktarır ve duruşma analizini çıkarır.   │
├───────────────────────────────┼────────────────────────────────────────────────────────┤
│ ✍️ uyap-imzala                │ UDF dilekçelerini donanım USB e-imza (ArkSigner vb.)   │
│                               │ ile 0.3 sn'de SIFIR POPUP ile sessizce; kart yoksa     │
│                               │ SIM kartınıza onay göndererek Mobil İmza ile imzalar.  │
├───────────────────────────────┼────────────────────────────────────────────────────────┤
│ 🔍 uyap-imzala --dogrula      │ İmzalı bir UDF dosyasının bozulup bozulmadığını ve     │
│                               │ içerik özetinin (SHA-256) doğruluğunu denetler.        │
└───────────────────────────────┴────────────────────────────────────────────────────────┘
```

---

## 🚀 Senaryo 1: Dava Dosyasını İndirip Google Drive'a Aktarma (`uyap-arsiv`)

UYAP'taki herhangi bir dosyanızın (derdest veya kapalı) tüm evraklarını tek komutla arşivlemek için:

### 1.1. Adım: Terminali Açın
* **Telefonda (Termux):** Termux uygulamasını açın.
* **Windows'ta:** PowerShell veya Komut İstemi'ni (CMD) açın.
* **Linux / Mac'te:** Terminal'i açın.

### 1.2. Adım: Komutu Çalıştırın
Sadece esas numarasını veya mahkeme adını yazmanız yeterlidir:

```bash
# Sadece Esas No ile (En pratik yol)
uyap-arsiv 2022/504

# Mahkeme adı ve Esas No ile (Birden fazla aynı esas numaralı dosya varsa)
uyap-arsiv "Ankara Batı 1. Asliye Hukuk 2022/504"

# Ağır Ceza veya Asliye Ceza dosyası için
uyap-arsiv "Ankara 81. Asliye Ceza 2025/289"
```

### 1.3. Adım: Arka Planda Neler Olur?
Komutu girdiğinizde sistem şu adımları otomatik tamamlar:
1. **Oturum Denetimi:** UYAP oturumu açıksa hemen bağlanır. Oturum düşmüşse takılı ArkSigner token'ı ile arka planda 2 saniyede oturumu yeniler.
2. **Evrak Taraması:** Dosyadaki tüm tensip zabıtları, layihalar, bilirkişi raporları ve ekler listelenir.
3. **Mükerrer Kontrolü:** Daha önceden indirilmiş evraklar tekrar indirilmez; sadece yeni gelen evraklar çekilir.
4. **Vektörel PDF Dönüşümü:** İndirilen `.udf` ve `.tiff` dosyaları Havelsan UYAP motoruyla taranabilir net PDF'lere dönüştürülür.
5. **Resmi Standartta Adlandırma:** `2026-11-24_Bilirkişi_Raporu_Mali_Heyet.pdf` gibi tarih ve evrak türüne göre düzenlenir.
6. **Google Drive Eşitlemesi:** Google Apps Script Webhook üzerinden dosyalar Google Drive hesabınızdaki `UYAP_Arsiv/<Mahkeme>_<Esas>/` klasörüne aktarılır.
7. **Telegram Bildirimi:** Dosyada bilirkişi raporu gelmiş mi, duruşma ne zaman, önceki ara kararlar yerine getirilmiş mi analizi Telegram adresinize gönderilir.

### 1.4. İsteğe Bağlı Seçenekler
```bash
# Drive'a yüklemeden sadece yerel bilgisayara/telefona indirmek için:
uyap-arsiv 2022/504 --no-drive

# Evrakları PDF'e çevirmeden saf halleriyle (UDF/TIFF) indirmek için:
uyap-arsiv 2022/504 --no-convert
```

---

## ✍️ Senaryo 2: UDF Dilekçesi İmzalatma (`uyap-imzala`)

UYAP Doküman Editörü veya CanEditor ile hazırladığınız `.udf` dosyalarını resmi geçerlilikle imzalamak için:

### 2.1. Yöntem A: USB E-İmza ile Sessiz (Headless) İmzalama (Önerilen)
ArkSigner veya Akis USB e-imzanız takılıyken:

```bash
uyap-imzala Mazeret_Dilekcesi.udf
```
* **Sonuç:** Ekrana **hiçbir pencere, onay kutusu veya popup gelmez**.
* Komut satırından PIN doğrudan karta gönderilir (`VERIFY PIN`).
* **0.3 saniye içinde** `Mazeret_Dilekcesi_IMZALI.udf` oluşturulur.

Özel bir PIN belirtmek isterseniz:
```bash
uyap-imzala Mazeret_Dilekcesi.udf --pin 455625
```

---

### 2.2. Yöntem B: E-İmza Takılı Değilken UYAP Mobil İmza ile İmzalama
USB e-imzanız yanınızda değilse sistem otomatik olarak Mobil İmza kanalına geçer:

```bash
uyap-imzala Mazeret_Dilekcesi.udf
```
Veya doğrudan mobil imzayı zorlamak için:
```bash
uyap-imzala Mazeret_Dilekcesi.udf --mobil --operator 2 --gsm 05525286225
```
*(Operatör kodları: 1 = Turkcell, 2 = Türk Telekom, 3 = Vodafone)*

* **Akış:**
  1. Terminalde doğrulama parmak izi görünür: `🔑 Parmak İzi: 1234`
  2. SIM kartınıza güvenli operatör bildirimi gelir.
  3. Telefon ekranından PIN kodunuzu girip "Tamam" dersiniz.
  4. Terminal imzayı alır ve geçerli `Mazeret_Dilekcesi_IMZALI.udf` dosyasını üretir.

---

### 2.3. Yöntem C: İmzalandıktan Sonra Anında Vektörel PDF Üretme
Mahkemeye veya müvekkile göndermek üzere imzalı UDF ile birlikte anında PDF çıktısı almak için `--pdf` parametresini ekleyin:

```bash
uyap-imzala Mazeret_Dilekcesi.udf --pdf
```
Çıktı olarak hem `Mazeret_Dilekcesi_IMZALI.udf` hem de `Mazeret_Dilekcesi_IMZALI.pdf` üretilir.

---

### 2.4. Yöntem D: UDF Belgesinin İmzasını Doğrulama (`--dogrula`)
Elinizdeki bir UDF belgesinin sahte olup olmadığını veya üzerinde oynama yapılıp yapılmadığını denetlemek için:

```bash
uyap-imzala /sdcard/Download/Mazeret_Ankara_Bati_1_AHM_2022_504_IMZALI.udf --dogrula
```

**Örnek Çıktı:**
```text
🔍 Doğrulanıyor: Mazeret_Ankara_Bati_1_AHM_2022_504_IMZALI.udf
✅ İMZA GEÇERLİ! (İçerik Özeti Uyuşuyor)
   • SHA-256 Özeti: 214f69a27f5891317a6a5fd6651d3178cbdd1f5b8ffc636a5c8a35b7742c4ea5
   • İmza Boyutu  : 2387 bayt
   • İmzacı       : CAN KIZILYAR
   • Sağlayıcı    : Avea Mobil NES Hizmet Sağlayıcısı S7
   • Geçerlilik   : 2026-05-26 - 2027-05-26
```

---

### 2.5. Yöntem E: Donanım ve Servis Durumunu Sorgulama (`--durum`)
Akıllı kartınızın takılı olup olmadığını ve servislerin çalıştığını görmek için:

```bash
uyap-imzala --durum
```

---

## 💻 3. İşletim Sistemi Bazlı Hızlı Komut Tablosu (Cheat Sheet)

| Senaryo | Android (Termux) | Windows (CMD / PowerShell) | Linux / macOS Terminal |
|---|---|---|---|
| **Dosya Arşivle & Drive'a At** | `uyap-arsiv 2022/504` | `uyap-arsiv.bat 2022/504` *(veya `.\uyap-arsiv.ps1`)* | `./uyap-arsiv 2022/504` |
| **Sessiz E-İmza ile İmzala** | `uyap-imzala dilekce.udf` | `uyap-imzala.bat dilekce.udf` | `./uyap-imzala dilekce.udf` |
| **Mobil İmza ile İmzala** | `uyap-imzala dilekce.udf -m` | `uyap-imzala.bat dilekce.udf -m` | `./uyap-imzala dilekce.udf -m` |
| **İmza + Vektörel PDF Al** | `uyap-imzala dilekce.udf --pdf` | `uyap-imzala.bat dilekce.udf --pdf` | `./uyap-imzala dilekce.udf --pdf` |
| **İmza & Hash Doğrula** | `uyap-imzala dosya.udf -d` | `uyap-imzala.bat dosya.udf -d` | `./uyap-imzala dosya.udf -d` |
| **Sistem & Kart Durumu** | `uyap-imzala --durum` | `uyap-imzala.bat --durum` | `./uyap-imzala --durum` |

---

## 🛠️ 4. Sık Karşılaşılan Sorular ve Çözümleri (SSS)

### S1: "Takılı Kart Bulunamadı" uyarısı alıyorum, ne yapmalıyım?
* **Çözüm (Android/Termux):** OTG adaptörünün ve ArkSigner USB token'ının telefona tam oturduğundan emin olun. Telefonun OTG ayarının açık olduğunu kontrol edin. Kart takılı değilse komut kendiliğinden Mobil İmza kanalına geçer.
* **Çözüm (Windows/Mac/Linux):** Adalet E-İmza Servisi simgesinin sağ altta (sistem tepsisinde) çalıştığından emin olun.

### S2: CanEditor'de "İçerik özeti uyuşmuyor" hatası neden çıkıyordu ve nasıl çözüldü?
* **Cevap:** Adalet E-İmza tepsisindeki standart `/api/v1/signature/sign` uç noktası UYAP portala giriş doğrulama kodlarını imzalamak için tasarlanmıştır. Belge imzalama için doğrudan `content.xml`'in SHA-256 özetini CAdES standardında imzalayan `/api/v1/docsignature/signdigest` entegrasyonu yazıldı. Artık belgeler CanEditor ve UYAP Editör'de %100 kusursuz ve yeşil onaylı açılır.

### S3: Mobil İmzada neden ekrana onay bildirimi çıkıyor?
* **Cevap:** 5070 Sayılı Elektronik İmza Kanunu ve GSM ETSI TS 102 204 standardı gereğince, mobil imza anahtarları SIM kartın güvenli çipindedir. Operatör ikili SMS gönderdiğinde SIM kart donanımsal olarak ekrana `GET INPUT` modalı açar. Kullanıcı onaylamadan imza üretilemez; bu güvenlik kuralı işletim sistemi düzeyinde zorunludur.
