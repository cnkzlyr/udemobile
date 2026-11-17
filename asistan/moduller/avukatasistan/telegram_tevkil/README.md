# ⚡ Telegram Ankara Tevkil Hızlı Yanıtlayıcı

Bu sistem, Telegram tevkil gruplarında Ankara ile ilgili bir tevkil (duruşma, yetki belgesi, dosya inceleme vb.) talebi paylaşıldığı anda milisaniyeler içinde herkesten önce **"Ben"** yazarak görevi almanızı sağlayan yerel bir userbot'tur.

---

## 🔒 Güvenlik Notu
Telefon numaranızı, Telegram doğrulama kodunuzu veya şifrenizi **asla hiçbir sohbete veya üçüncü şahsa vermeyiniz**.
Bu script tamamen sizin kendi cihazınızda (Termux ortamında) çalışır ve Telegram ile doğrudan şifreli (MTProto) bağlantı kurar.

---

## 🚀 Kurulum ve İlk Çalıştırma (2 Adım)

### Adım 0: Telegram API Bilgilerini Alma (1 Kez Yapılır)
Telegram'da bot/istemci çalıştırmak için Telegram'ın resmi geliştirici kimlikleri gerekir:
1. Tarayıcınızdan **https://my.telegram.org** adresine gidin.
2. Telefon numaranızla giriş yapın (Telegram uygulamanıza gelen onay kodunu girin).
3. Açılan sayfada **API development tools** seçeneğine tıklayın.
4. **App title** ve **Short name** kısımlarına örneğin `TevkilApp` yazıp onaylayın.
5. Sayfada size verilen **`api_id`** (sayı) ve **`api_hash`** (harf/sayı karışımı metin) değerlerini kopyalayın.

---

### Adım 1: Tevkil Grubunu ve Geçmiş Mesajları İnceleme (`tevkil_kesif.py`)
Önce grubunuzu bulmak ve gruptaki Ankara tevkillerinin nasıl paylaşıldığını incelemek için şu komutu çalıştırın:

```bash
cd ~/avukatasistan/telegram_tevkil
python3 tevkil_kesif.py
```

Bu script çalıştığında:
1. İlk seferde sizden `api_id` ve `api_hash`'i ister ve kaydeder.
2. Terminalinizde telefon numaranızı ve Telegram'a gelen doğrulama kodunu sorar (güvenli, yerel giriş).
3. Üye olduğunuz grupları tarayıp Tevkil gruplarını listeler.
4. İlgili grubu seçtiğinizde gruptaki son mesajları ekrana döker ve Ankara ile eşleşenleri analiz eder.
5. Seçtiğiniz grubu otomatik olarak botun hedef listesine kaydeder.

---

### Adım 2: Hızlı Botu Başlatma (`tevkil_bot.py`)
Grup kaydedildikten sonra botu çalıştırmak için:

```bash
cd ~/avukatasistan/telegram_tevkil
python3 tevkil_bot.py
```

Artık sistem arka planda veya açık terminalde grubu dinler. Ankara ile ilgili yeni bir mesaj düştüğü anda milisaniyeler içinde mesajı alıntılayıp **"Ben"** yazar!
