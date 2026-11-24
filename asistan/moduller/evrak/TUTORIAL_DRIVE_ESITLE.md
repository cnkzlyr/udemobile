# 🚀 UYAP Google Drive Otonom Arşivleme ve Eşitleme Rehberi (Tutorial)
**Telif Hakkı (c) 2026 Av. Can KIZILYAR — Tüm hakları saklıdır.**

Bu rehber; UYAP Avukat Portalındaki dava ve işlemlerinizin, yereldeki indirilen belgelerinizin ve Google Drive bulut arşivinizin nasıl %100 otonom, güvenli ve düzenli eşitlendiğini adım adım açıklar.

---

## 📌 1. Hızlı Başlangıç (Tek Komutla Çalıştırma)

Termux'ta veya herhangi bir terminalde (Windows, Mac, Linux) nerede olursanız olun aşağıdaki komutlar doğrudan çalışır:

```bash
# 1. Arka planda tam ve kademeli eşitlemeyi başlat (Siz işinize bakın, o yüklesin):
uyap-drive-esitle --start

# 2. Çalışma durumunu ve kaç evrak yüklendiğini kontrol et:
uyap-drive-esitle --status

# 3. İhtiyaç halinde eşitlemeyi güvenle durdur:
uyap-drive-esitle --stop
```

---

## ⏱️ 2. Kademeli Zaman Akışı (Nasıl Çalışır?)

Sistem arşivi kargaşadan kurtarmak ve en acil belgelere anında erişebilmeniz için **5 aşamalı kademeli akış** izler:

1. **Aşama 1 (Son 1 Gün):** Bugün ve dün gelen en taze dilekçe, karar ve tebligatlar.
2. **Aşama 2 (Son 1 Hafta):** Son 7 günün tüm duruşma tutanakları ve portal işlemleri.
3. **Aşama 3 (Son 1 Ay):** Son 30 günlük tüm dava ve icra hareketleri.
4. **Aşama 4 (Son 2 Ay):** Son 60 günün arşivi.
5. **Aşama 5 (Tüm Arşiv):** Geçmiş yıllara ait on binlerce dava evrakı arka planda sessizce tamamlanır.

Belirli bir zaman dilimini tek başına çalıştırmak isterseniz:
```bash
uyap-drive-esitle --asama 1hafta
uyap-drive-esitle --asama 1ay
```

---

## 🛡️ 3. Akıllı Filtreleme ve Güvenlik

- **Hariç Tutulan Dosyalar:** Kullanıcı kuralı uyarınca `baydar`, `casmoni`, `emre oral`, `turan solmaz` anahtar kelimelerini içeren hiçbir dava veya evrak kesinlikle Drive'a aktarılmaz, atlanır.
- **Mükerrerlik Önleme:** Daha önce Google Drive'a yüklenmiş olan evraklar `arsiv_indeksi.json` üzerinden SHA/UUID bazında kontrol edilir; aynı dosya asla iki defa yüklenmez (kota dostudur).
- **Yerel + UYAP Hibrit İndirme:** 
  - Telefonda (`/sdcard/Download/UYAP_Indirilenler`) zaten var olan evraklar UYAP sunucusunu yormadan doğrudan Drive'a aktarılır.
  - Henüz telefona inmemiş eksik evraklar ise UYAP Avukat Portalından arka planda indirilip, UDF formatındaysa anında aranabilir PDF'e çevrilerek Drive'daki ilgili dava klasörüne yüklenir.

---

## 🔍 4. Google Drive Arşiv Denetimi ve Raporlama

Drive arşivinizde bozuk, mükerrer veya adlandırma hatası olan dosya var mı diye tek tuşla denetim yapabilirsiniz:

```bash
# Hızlı özet raporu:
uyap-drive-denetle --ozet

# Detaylı tam denetim ve CSV çıktıları üret:
uyap-drive-denetle
```

Denetim tamamlandığında şu raporlar otomatik oluşturulur:
- `drive_durum_raporu.json`: Sağlık skoru ve genel istatistikler.
- `arsiv_mevcut_dosyalar.csv`: Drive ve yereldeki tüm sağlam evrak listesi.
- `arsiv_sorunlu_dosyalar.csv`: Bozuk (0 byte) veya mükerrer dosyalar.
- `arsiv_eksik_dosyalar.csv`: UYAP'ta olup henüz indirilmeyen evrak listesi.

---

## ✍️ 5. USB E-İmza & Mobil İmza ile İmzalama

Evraklarınızı imzalamak veya doğrulamak için:

```bash
# 1. OTG ile takılı USB E-İmza (ArkSigner) ile sessiz arka plan imzalama:
uyap-imzala dilekce.udf

# 2. Mobil İmza ile imzalama:
uyap-imzala dilekce.udf --mobil --operator 2 --gsm 05XXXXXXXXX

# 3. İmzalı UDF'in imza geçerliliğini doğrulama:
uyap-imzala dilekce_IMZALI.udf --dogrula
```

---

## 📱 6. UdeMobile Editör ile Entegrasyon

UdeMobile Editör'de düzenlediğiniz bir evrakı:
1. Kaydettiğinizde veya farklı kaydettiğinizde eski imzalı baytlar temizlenir ve en güncel haliniz saklanır.
2. E-İmza / Mobil İmza menüsünden imzaladığınızda doğrudan güncel metin imzalanır.
3. Düzenlenen evrak arka plan eşitleyici tarafından otomatik olarak Google Drive arşivinize eşitlenir.
