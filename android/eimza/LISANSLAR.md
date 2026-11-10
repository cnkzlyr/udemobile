# Adalet E-İmza (Termux'suz) bileşenleri — lisanslar

| Bileşen | Kaynak | Lisans |
|---|---|---|
| Gömülü Java 21 (jre-arm64.zip) | Termux `openjdk-21`, `openjdk-21-x` paketleri (OpenJDK) | GPL-2.0 + Classpath Exception |
| Yerel kütüphaneler (zlib, freetype, libpng, libjpeg-turbo, littlecms, libiconv, brotli, bzip2, giflib, X11 istemci kütüphaneleri, fontconfig, expat, libandroid-*) | Termux paketleri | Her paketin kendi lisansı (jre/legal içinde) |
| Caciocavallo (lib/cacio-*.jar) | https://github.com/CaciocavalloSilano/caciocavallo | GPL-2.0 + Classpath Exception |
| eimza-agent (agent/), CCID köprüsü | uyap-termux-pro, © 2026 Av. Can KIZILYAR | Bkz. LICENSE.txt |

**Resmi Adalet E-İmza uygulaması UdeMobile ile dağıtılmaz.** Telefon onu Adalet Bakanlığı'nın kendi
sunucusundan (cdn.uyap.gov.tr) indirir; kullanım koşulları Adalet Bakanlığı'na aittir.
Tüm uç noktalar (/client/info dahil) resmi uygulamanın kendisi tarafından yanıtlanır; UdeMobile taklit etmez.
