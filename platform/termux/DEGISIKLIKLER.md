# Değişiklikler

## 2.0 (UYAP-Termux Pro)

### Hata düzeltmeleri
- **JDK 15+ ile editör açılmıyordu** ("Java sürümünüz uygun değil, 6–14 arası olmalı"). Termux ana deposunda
  yalnızca openjdk-17/21 olduğundan openjdk-11 bulunamayan cihazlarda kurulum çalışmıyordu. Başlatıcı açılışta
  `java.version`'ı 11 gösterir, ilk pencere açılınca gerçeğini geri yazar; jar'lar değiştirilmez.
- `.usf` şablonları Doküman Editörü'nde açılıyordu → Şablon Editörü (`EDITOR_TYPE_TEMPLATE`).
- Akıcı kaydırma Ctrl/Shift/Alt+tekerlek olaylarını da yutuyordu → editörün kendi dinleyicilerine iletiliyor.
- `-Xmx4096M` sabitti (düşük RAM'li cihazlarda JVM açılmayabilir) → RAM'in ~%40'ı.
- `sun.java2d.uiScale` + `flatlaf.uiScale` birlikte veriliyordu (çift ölçekleme) → yalnızca FlatLaf ölçeği.
- `--oku`/`--doc`: ilk bulunan XML'deki tüm metin düğümleri birleşiyordu; boş belge çöküyordu; `.doc`'ta HTML
  kaçışı yoktu → `content.xml` CDATA havuzu, güvenli çıktı.
- FlatLaf indirmesi doğrulanmıyordu → SHA-256 sabit.
- 1.1'de PIN için Swing yedeği kaldırılmıştı (Termux:API yoksa PIN sorulamıyordu) → görünür ekranda geri geldi;
  görünmez Xvfb'de açılmaz, 120 sn zaman aşımı, PIN dizisi sıfırlanır.
- **Yedekleme gizlilik açığı:** v3 yedeği Firefox profilini (kayıtlı parolalar, çerezler) ve editörün belge
  otomatik kayıtlarını içeriyordu → varsayılan olarak hariç; özel anahtarlar hiç alınmaz; zip 600 izinli.
- `geri_yukle.sh` boşluklu dosya adlarında (`UYAP Editör.desktop`) bozuluyordu.
- Her açılışta `[DEBUG] java -version` dökümü basılıyordu → yalnızca `UYAP_AYRINTI=1`.
- `kur.sh`: find çıktısı üzerinde `for` (SC2044); git kopyasında yanıltıcı "sahte olabilir" mesajı.
- `startxfce4_termux.sh`'deki komutsuz yönlendirme (SC2188) — betik `xfce_baslat.sh` ile değiştirildi.

- Termux:X11'de Ctrl/Alt kısayolları ABD düzeninde tarama kodu olarak, harfler Android düzeninde metin olarak
  gidiyordu (karışık davranış) → `klavye.sh`: "Prefer scancodes" + `setxkbmap tr`, masaüstü açılışında otomatik;
  düzen gerçek tuş haritasından doğrulanır.
- Tek başına Alt, şeritte KeyTips açıp sonraki tuşları yutuyordu → `TekAltEngeli` (Alt+harf, AltGr etkilenmez).

- **Seçili metin görünmüyordu** (Ctrl+A ya da fareyle seçim yapılıyor ama mavi vurgu yoktu): UYAP seçili metni
  çizerken `sun.swing.SwingUtilities2`'yi kullanıyor; Java 9+ bunu engelleyince her boyamada `IllegalAccessError`
  atılıyordu. Editör jar'larında başvurulan tüm JDK iç paketleri (sun.swing, sun.font, sun.java2d, sun.awt,
  sun.print, sun.security.* …) `--add-opens` ile açıldı.
- Ölçek yalnızca FlatLaf bileşenlerine uygulanıyordu (1.25 üstünde şerit kırpılıyordu) → tüm pencere
  `sun.java2d.uiScale` ile ölçeklenir.
- Dosya aç/kaydet pencereleri: Türkçe etiketler, hızlı erişim (İndirilenler, UYAP Belgelerim, Belgeler, Masaüstü),
  ayrıntılı görünüm, ekrana göre büyük ve yeniden boyutlanabilir pencere.
- Termux:X11 dokunmatik modu (dokunulan yere tıklama, sürükleyerek seçme), ekran klavyesi önerileri/kaydırarak
  yazma açık, yerel çözünürlük.
- Ctrl+Shift+F11: odaktaki metnin seçim/imleç durumunu `~/.uyap-editor/tani-secim.txt`'ye yazar.

- İmzalamada "Java sürümünüz imzalama için desteklenmemektedir": UYAP sürümü her imzalamada da denetliyor;
  başlatıcı artık oturum boyunca 11 gösteriyor.
- `uyap jdk14`: JDK 14.0.2'yi (glibc) Termux'ta çalıştırma; elle kurulmuş JDK'lar bulunur, `.bashrc`'yi bozan
  PATH/LD_LIBRARY_PATH satırları temizlenir.
- PREFIX tanımsızken (masaüstü Linux) başlatıcı kendini Termux'ta sanıyordu.

### Yeni
- `uyap` komutu ve dialog menüsü; `uyap durum`, `uyap tani` (jetonları gizleyen rapor), `uyap yazitipi`,
  `uyap kur-editor`, `uyap gunluk`.
- **Kontrol Merkezi** (`uyap panel`): durum kartları, tek dokunuşla işlemler, grafik ayarlar.
- `~/.config/uyap-termux/ayarlar.ini`: tema (açık/koyu/macOS), ölçek (otomatik = DPI), vurgu rengi,
  dokunmatik mod, kaydırma, Java yolu/bellek, e-imza.
- Akıcı kaydırma: kritik sönümlü yay (uyap-editor-modern'den), yalnızca animasyon sırasında çalışan zamanlayıcı, F9.
- PDF'te Times New Roman: yazı tipi eşlemecisine Termux/`~/.fonts` klasörleri (uyap-editor-modern PdfFontFixer'dan).
- XFCE görev çubuğu gruplaması (`WM_CLASS=uyap-editor`), `.desktop` eylemleri, fluxbox UYAP menüsü.
- Birim testleri (Python + Java), GitHub Actions.

## 1.1 / 1.0 (uyap-termux)
- Tek komutla kurulum (`kur.sh`), resmî kaynaklardan indirme, Ed25519 mühür ve doğrulama, telif bildirimi.

## v3 yedeği (21.09.2026)
- Rootsuz USB CCID köprüsü, Adalet E-İmza'nın Termux'ta çalıştırılması, tek örnek servisi, çift tıklama ile açma,
  XFCE tümleşmesi, otomatik başlatma, tam yedek/geri yükleme.
