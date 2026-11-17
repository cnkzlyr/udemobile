# UYAP Editör Modern - Android Desteği

UYAP Doküman Editörü'nü Android cihazlarda (özellikle Samsung Galaxy Tab, Xiaomi Pad vb. tabletlerde veya telefonlarda) çalıştırmak için iki temel yöntem bulunmaktadır:

---

## 1. Yöntem: Termux & Termux:X11 ile Tam Masaüstü UYAP (Tavsiye Edilen)
Bu yöntem ile masaüstündeki resmi UYAP Editör'ün birebir aynısını, tüm şablonları, dipnotları, tabloları ve yazdırma işlevleriyle tabletinizde kullanabilirsiniz.

### Kurulum Adımları:
1. Cihazınıza **F-Droid** üzerinden **Termux** ve **Termux:X11** uygulamalarını yükleyin.
2. Termux'u açıp aşağıdaki tek komutu çalıştırın:
   ```bash
   curl -sL https://raw.githubusercontent.com/cnkzlyr/uyap-editor-modern/main/platforms/android/termux-install.sh | bash
   ```
3. Kurulum tamamlandıktan sonra terminale:
   ```bash
   uyap
   ```
   yazarak Termux:X11 penceresinden tam doküman editörünü kullanabilirsiniz.

---

## 2. Yöntem: UDF Mobil Web Görüntüleyici
`.udf` dosyaları aslında birer ZIP arşivdir ve içerisinde `content.xml` bulundurur. UYAP'ın karmaşık yapısını Android'de hafif bir web görünümünde açmak için:
* UDF dosyası ZIP olarak açılır.
* `content.xml` içindeki paragraflar, stiller ve tablolar HTML DOM yapısına dönüştürülür.
* Modern mobil tarayıcılarda anında okunabilir ve PDF olarak dışa aktarılabilir.
