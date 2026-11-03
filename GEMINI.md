# 🏛️ CanEditor (UdeMobile) — Geliştirme, Yayınlama ve Sürüm Kuralları (AGENTS.md)

Bu kurallar dosyası, proje üzerinde çalışan tüm yapay zeka asistanları ve geliştiriciler için **kesin ve bağlayıcı ilkeleri** içerir. Projede herhangi bir geliştirme veya düzeltme yapıldığında aşağıdaki kurallara harfiyen uyulmalıdır.

---

## 📌 Temel İlke: "Ne Yapılırsa Yapılsın Tüm Platformlara Eksiksiz Yayınlanır"

Her geliştirme, hata düzeltmesi veya özellik eklendiğinde sürüm yükseltilmeli ve **tüm platformlar için eksiksiz** paketlenip yayımlanmalıdır. Hiçbir platform geride bırakılamaz.

---

## 🚀 1. Çapraz Platform Dağıtım Kapsamı (Zorunlu Liste)

Her yayında aşağıdaki 7 paket türünün tamamı oluşturulmalı ve GitHub Releases sayfasına yüklenmelidir:

1. **Android:**
   - `CanEditor-v<sürüm>.apk` (Güncel sürüm paketi)
   - `CanEditor-latest.apk` (Kalıcı son sürüm bağlantısı)
2. **Linux Debian / Ubuntu / Pardus:**
   - `CanEditor_<sürüm>_amd64.deb` (Yerel Debian paketi)
3. **Linux RedHat / Fedora / openSUSE:**
   - `CanEditor-<sürüm>-1.x86_64.rpm` (Yerel RPM paketi)
4. **Linux Evrensel (Tüm Dağıtımlar):**
   - `CanEditor_<sürüm>_amd64.AppImage` (Kurulumsuz çalıştırılabilir ikili)
5. **Windows (10 / 11 64-bit):**
   - `CanEditor_<sürüm>_x64-setup.exe` (NSIS standart kurulum yükleyicisi)
   - `CanEditor_<sürüm>_x64_en-US.msi` (Kurumsal MSI yükleyicisi)
6. **macOS (Apple Silicon & Intel):**
   - `CanEditor_<sürüm>_universal.dmg` (Tek tıkla Applications klasörüne yüklenen disk kalıbı)
   - `CanEditor_<sürüm>_universal.app.tar.gz` (Arşivlenmiş Mac uygulama paketi)
7. **Taşınabilir Web & Masaüstü (Portable Web GUI):**
   - `CanEditor-Portable-Web-GUI-v<sürüm>.zip` (Kurulum gerektirmeyen, `index.html` tıklanarak her işletim sisteminde tamamen çevrimdışı çalışan web sürümü)

---

## 📝 2. Git Commitleri ve Kod İçi Yorum Standartları

- **Ayrıntılı Conventional Commits:** Her commit; etkilenen bileşenleri, eklenen fonksiyonları, düzeltilen mantıksal hataları ve mimari nedenleri madde madde detaylı olarak içermelidir.
  - Örnek: `feat(v3.6.0): UYAP Avukat Portal standardi gercek A4 PDF motoru, belge ici arama, zoom sigdirma ve 1:1 Havelsan UDF uyumlulugu`
- **Açıklayıcı Kod Yorumları (Comments):**
  - UYAP Havelsan tersine mühendislik formülleri (girinti, sekme durakları, Unicode Rune hesapları `Array.from(str).length`), XML etiket hiyerarşisi ve köprü fonksiyonları hem Türkçe hem teknik İngilizce açıklamalarla belgelenmelidir.
  - Var olan yorumlar korunmalı, yeni eklenen her kritik metoda açıklama başlığı eklenmelidir.

---

## 📚 3. Dokümantasyon & README.md Güncelleme Zorunluluğu

Her yeni sürümde `README.md` ve GitHub Releases sürüm notları eşzamanlı güncellenmelidir:
1. **Sürüm Rozetleri ve Başlıklar:** En güncel sürüme yükseltilmelidir (`vX.Y.Z`).
2. **Hızlı İndirme Tablosu:** Tüm platformların güncel indirme bağlantılarını içermelidir.
3. **Sürüm Notları (Changelog):** Sürümle gelen teknik ve hukuki yetenekler ayrıntılı maddelerle açıklanmalıdır.
4. **Hiç Bilmeyenler İçin Adım Adım Kurulum Rehberi:**
   - Android için güvenlik uyarısı aşma, "Bilinmeyen kaynaklar" izni ve `.udf` dosya ilişkilendirme.
   - Windows için SmartScreen ("Ek bilgi" -> "Yine de çalıştır") aşma ve `.msi` / `.exe` / `Portable ZIP` rehberi.
   - macOS için Gatekeeper ("Geliştirici doğrulanamıyor" -> `Control + Sağ Tık -> Aç`) rehberi.
   - Linux için `chmod +x` AppImage ve `.deb` / `.rpm` paket yöneticisi komutları.
   - Web için kurulumsuz tarayıcıda sürükle-bırak kullanım talimatı.

---

## 🛠️ 4. Sürüm Yayınlama İş Akışı (Release Workflow)

1. Sürüm numaralarını senkronize et:
   - `package.json` -> `version`
   - `src-tauri/tauri.conf.json` -> `version`
   - `android/AndroidManifest.xml` -> `versionCode` (+1) ve `versionName`
   - `scripts/pack_release.py` -> `VERSION`
   - `frontend/public/updater.js` & `android/assets/editor/updater.js` -> `VERSION`
2. `python3 scripts/pack_release.py` çalıştırarak Web varlıklarını senkronize et ve `CanEditor-Portable-Web-GUI-v<sürüm>.zip` üret.
3. `release/CanEditor-latest.apk` dosyasını `release/CanEditor-v<sürüm>.apk` olarak kopyala ve güncelle.
4. `README.md` dosyasını tüm kılavuz ve bağlantılarla güncelle.
5. Değişiklikleri detaylı commit mesajıyla commit et: `git commit -m "..."`.
6. Yeni sürüm etiketini oluştur: `git tag -a v<sürüm> -m "CanEditor v<sürüm> ..."`.
7. Git push yap: `git push origin main && git push origin v<sürüm>`.
8. `python3 scripts/publish_github_release.py` çalıştırarak GitHub Release'i oluştur, APK ve Portable ZIP'i hemen yükle.
9. GitHub Actions CI (`desktop-release.yml`)'nin Windows (`.exe`/`.msi`), macOS (`.dmg`) ve Linux (`.AppImage`/`.deb`/`.rpm`) derlemelerini tamamlayıp release'e otomatik eklemesini doğrula.
