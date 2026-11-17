# Dosya defterini (ve sonra tüm sistemi) Plesk hostinge taşıma

Dosya defteri bugün tablette tek bir dosyada durur: `veri/defter.db` (SQLite). Kod veritabanından bağımsızdır;
**tek bir ayar** (`DEFTER_URL`) değiştirerek Plesk'teki MySQL/MariaDB'ye geçer. Tablolar orada kendiliğinden
oluşturulur.

## 1. Plesk'te veritabanı açın (bir kez, 5 dakika)

1. Plesk > **Veritabanları** > **Veritabanı Ekle**
   - Veritabanı adı: örn. `avukat`
   - Tür: **MariaDB/MySQL**
   - Kullanıcı adı ve güçlü bir şifre belirleyin
2. Aynı ekranda kullanıcının **Erişim denetimi** ayarı: tabletten bağlanılacaksa "Uzak bağlantılara izin ver"
   (mümkünse yalnızca kendi IP'nize). Sistem Plesk sunucusunda çalışacaksa "Yalnızca yerel" yeterli.
3. Sunucu adresi ve port Plesk'te yazar (genelde alan adınız ve `3306`).

## 2. Tabletteki defteri oraya taşıyın

```bash
pip install pymysql
asistan defter tasi "mysql+pymysql://KULLANICI:SIFRE@SUNUCU:3306/avukat?charset=utf8mb4"
```

Taşıma, hedef tablolar **boşsa** yapılır (var olan veri ezilmez). Bitince `.env` dosyasına ekleyin:

```
DEFTER_URL=mysql+pymysql://KULLANICI:SIFRE@SUNUCU:3306/avukat?charset=utf8mb4
```

Bundan sonra sistem nerede çalışırsa çalışsın (tablet ya da sunucu) aynı deftere yazar.
`asistan durum` "Plesk/uzak veritabanı" göstermelidir.

> Şifrede `@ : / ?` gibi işaretler varsa yüzde kodlamasıyla yazın (`@` → `%40`).

## 3. İleride: tüm sistemi sunucuda çalıştırmak (telefonla uğraşmamak için)

Sistem zaten sunucuya hazır yazıldı: Termux'a özgü yollar yalnızca tablette kullanılır, ayarlar `.env`'den gelir,
duruşmalar takvimden internet adresiyle okunur.

| Parça | Sunucuda |
|---|---|
| TickTick, Notion, Telegram, takvim, dosya defteri, UYAP listesi | Sorunsuz (yalnızca internet) |
| UETS indirme | Görünmez (headless) Chromium gerekir: **VPS / sanal sunucu** ya da Docker desteği olan Plesk. Paylaşımlı hostingde genelde Chromium kurulamaz |
| UYAP listesini yükleme | Listeyi tablete indirip sunucudaki klasöre bırakmak (ileride küçük bir yükleme sayfası eklenebilir) |

Sunucuda çalıştırma (SSH ile, bir kez):

```bash
git clone https://github.com/cnkzlyr/avukatasistan ~/avukatasistan && cd ~/avukatasistan
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt sqlalchemy pymysql
cp /yol/.env .env            # tabletteki .env (DEFTER_URL Plesk veritabanını göstermeli)
python3 asistan.py durum
```

Sonra Plesk > **Zamanlanmış Görevler** (cron) ile her 30 dakikada:

```
cd ~/avukatasistan && .venv/bin/python asistan.py izle --bir-kez --headless
```

Böylece tablet kapalıyken de tebligatlar, takvim ve denetim çalışır; Telegram bildirimleri aynı kalır.
