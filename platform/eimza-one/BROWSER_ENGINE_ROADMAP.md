# Tarayıcı motoru yol haritası

## Şimdiki sürüm

Uygulama Android System WebView kullanır. Adres geçmişi, otomatik tamamlama,
çoklu sekme, sekme grupları, favoriler, masaüstü User-Agent ve portal imza
köprüleri uygulama katmanında sağlanır.

System WebView, masaüstü Chromium/Firefox eklentilerini çalıştıran bir eklenti
API'si sunmaz. Bu nedenle kullanıcıya çalışıyormuş gibi görünen sahte bir
"eklenti yükle" işlevi eklenmemiştir.

## GeckoView / Firefox tabanlı sürüm taslağı

1. WebView erişimleri `BrowserEngine` arayüzünün arkasına alınacak.
2. GeckoView ayrı bir ürün çeşidi olarak eklenecek; mevcut imza köprüleri
   yalnız izin verilen kökenlerde `WebExtension`/message bridge üzerinden
   taşınacak.
3. Sekme oturumu, geçmiş ve favoriler motor bağımsız bir depoya geçirilecek.
4. ArkSigner Firefox mesaj protokolü, haricî tarayıcı loopback sunucusuna
   güvenli origin/nonce kontrolüyle bağlanacak.
5. Eklenti izinleri, imza ve PIN verilerinden kesin olarak ayrılacak.

GeckoView geçişi tamamlanana kadar `.xpi` veya Chromium eklentisi yükleme
desteklenmez.
