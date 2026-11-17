# CanEditor 4 — Birleşik Hukuk Asistanı ve Editör: Mimari

CanEditor 4.0, sekiz ayrı depoyu tek uygulamada birleştirir. Gövde CanEditor'dur (Tauri masaüstü,
Android WebView, taşınabilir web). Diğer depolar, git geçmişindeki kaynak commit'leriyle bu depoya
alt dizin olarak taşındı.

| Kaynak depo | Yeni konum | Uygulamadaki karşılığı |
|---|---|---|
| `udemobile` (CanEditor) | depo kökü | Editör: UDF/DOCX/PDF/TIFF, e-imza, PDF, şablonlar |
| `avukatasistan` | `asistan/moduller/avukatasistan` | UETS e-tebligat → süre → TickTick/Notion/Telegram, dosya defteri |
| `uyap-evrak-indirici` | `asistan/moduller/evrak` | UYAP Avukat Portal evrak kataloğu, indirme, PDF dönüştürme, nöbetçi |
| `naps-uyap-thunar-tools` | `asistan/moduller/a4` | NAPS2 yöntemli A4 PDF motoru (+ Thunar sağ tık eylemleri) |
| `uyap-editor-modern` | `platform/uyap-editor-modern` | Resmî UYAP Editörü için modernleştirici + paketler (ayrı etiket) |
| `uyap-termux-pro` | `platform/termux` | Android/Termux'ta resmî UYAP Editörü + USB e-imza |
| UYAP Editör (resmî, Havelsan) | dağıtılmaz | CanEditor "Orijinal UYAP Editöründe Aç" ile çağırır; jar'lar lisanslıdır |
| `libreofficemobile` | — | Depo boştu. Ofis belgesi ihtiyacını CanEditor'un DOCX/ODT desteği karşılar |

## Katmanlar

```
┌──────────────────────────── CanEditor arayüzü (frontend/public) ────────────────────────────┐
│ editor.js · esign.js · pdfexport.js …            asistan.js  (Asistan menüsü / Ctrl+K)        │
│                                                  ├─ Süre hesabı   ┐ sunucusuz, her platformda  │
│                                                  ├─ A4 PDF        ┘ (Android ve web dahil)     │
│                                                  └─ Ajanda · UYAP Evrak · Görevler ──┐         │
└──────────────────────────────────────────────────────────────────────────────────────┼────────┘
        Tauri (src-tauri)  asistan.rs: sunucuyu bulur/başlatır, anahtarı verir          │ HTTP + anahtar
                                                                                        ▼
                 asistan/sunucu.py  (127.0.0.1:8765, yalnızca standart kütüphane)
                   ├─ /api/ajanda        defter.db (UETS süreleri, takvim) + uyap_katalog.db (duruşmalar)
                   ├─ /api/evrak/ara     uyap_katalog.db (Türkçe-duyarsız, -hariç)
                   ├─ /api/evrak/dosya   yalnızca katalogda kayıtlı indirilmiş dosya
                   ├─ /api/gorev/<ad>    izin listesindeki modül komutları (alt süreç + günlük)
                   └─ /api/a4            moduller/a4 motoru (yerel dosya yolları)
```

## Platformlara göre ne çalışır

| Özellik | Windows / macOS / Linux | Android (APK) | Taşınabilir web | Termux |
|---|---|---|---|---|
| Editör, e-imza, PDF/DOCX | ✓ | ✓ | ✓ | (APK ile) |
| Süre hesabı, A4 PDF | ✓ | ✓ | ✓ | ✓ |
| Ajanda, UYAP evrak arama, görevler | ✓ Python 3 kuruluysa otomatik | Termux'ta sunucu + eşleştirme | Sunucu + eşleştirme | ✓ `bash asistan/kur.sh` |
| Resmî UYAP Editörü | `platform/uyap-editor-modern` paketleri | `platform/termux` | — | ✓ |

## Güvenlik kuralları (sunucu)

- Yalnızca `127.0.0.1`'e bağlanır; `Host` başlığı yerel değilse 403 döner (DNS rebinding).
- Her `/api` isteğinde `X-Asistan-Anahtar` zorunludur. Özel başlık CORS ön kontrolünü tetikler;
  CORS yalnızca CanEditor kökenlerine açıktır (Tauri, `file://`/Android, localhost).
- Görevler sabit izin listesinden başlar; istemci komut veya yol gönderemez.
- Evrak dosyaları istemcinin verdiği yoldan değil, katalogdaki kayıttan çözülür.

## Süre hesabının tek kaynağı

Kural `asistan/moduller/avukatasistan/utils.py` (`calculate_deadlines`) içindedir. `asistan.js` bunun
JavaScript karşılığıdır; `tests/asistan_sure.test.cjs` 600 rastgele tarih/merci için iki uygulamanın
aynı sonucu verdiğini CI'da doğrular. Resmî ve adli tatiller tarihi ileri almaz, yalnızca uyarı olarak
gösterilir: hata yapılacaksa erken tarafta yapılır.

## Testler (CI: `.github/workflows/asistan-testleri.yml`)

```bash
python3 -m unittest discover -s asistan/testler -v                 # sunucu: güvenlik + gerçek şemalar
(cd asistan/moduller/avukatasistan && python3 -m pytest -q tests)  # UETS asistanı
TZ=Europe/Istanbul node --test tests/*.test.cjs                    # arayüz süre motoru ≡ Python
(cd platform/termux && python3 -m unittest discover -s testler)    # Termux paketi
```

## Yayınlar

| Etiket | İş akışı | Çıktı |
|---|---|---|
| `v*` | `desktop-release.yml` | CanEditor: APK, exe/msi, dmg, deb/rpm/AppImage, taşınabilir web |
| `evrak-v*` | `uyap-evrak-paketleri.yml` | Bağımsız UYAP Evrak Yöneticisi kurulumları |
| `editor-modern-v*` | `uyap-editor-modern.yml` | Resmî UYAP Editörü modernleştirici paketleri |
