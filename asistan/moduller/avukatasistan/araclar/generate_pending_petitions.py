#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dilekçe Üretici Script: TickTick'te bekleyen görevler için tam metin UDF ve ODT dilekçeleri hazırlar.
"""

import os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # proje kökü (araç araclar/ altında)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # document_builder/pdf_builder
from document_builder import create_document_pair, OUTPUT_DIR
from pdf_builder import create_pdf
import shutil

SDCARD_DIR = "/sdcard/Download/Hazirlanan_Dilekceler"
os.makedirs(SDCARD_DIR, exist_ok=True)

def build_trio(base_name, raw_text, p_list):
    udf_path, odt_path = create_document_pair(base_name, raw_text, p_list)
    pdf_path = create_pdf(base_name, p_list)
    for p in (udf_path, odt_path, pdf_path):
        shutil.copy(p, SDCARD_DIR)
    return udf_path, odt_path, pdf_path

def generate_all():
    generated_files = []

    # =========================================================================
    # DİLEKÇE 1: Oltu 2. Asliye Hukuk - SGK Bilirkişi Raporuna İtiraz
    # =========================================================================
    base_1 = "Oltu2AsH_2025_48_Bilirkisi_Raporuna_Itiraz"
    raw_1 = """OLTU 2. ASLİYE HUKUK MAHKEMESİ SAYIN HÂKİMLİĞİ'NE

DOSYA NO            : 2025/48 Esas
TALİMAT NO          : Bursa 9. İş Mahkemesi 2026/87 D.İş
İTİRAZ EDEN
DAVACILAR           : 1- Atmaca Madencilik İnş. Taah. Pet. San. Tic. Ltd. Şti.
                      (VKN: 1030551690)
                      Adres: Gözalan Mah. Merkez Küme Evleri No:72 Şenkaya / ERZURUM
                      2- Erol ATMACA (TCKN: 37867326226)
VEKİLİ              : Av. Can KIZILYAR
                      Hayfa Hukuk - 1463.Cd. No:4/7 Çukurambar, Çankaya / ANKARA
                      UETS: 15587-85062-32745
DAVALI              : Sosyal Güvenlik Kurumu Başkanlığı (SGK)
D. KONUSU           : 01.10.2026 havale tarihli Bilirkişi Heyet Raporuna karşı itirazlarımızın sunulması ve dosyanın tarafsız yeni bir heyete tevdii talebidir.

AÇIKLAMALAR         :

1- Mahkemenizin yukarıda esas numarası yazılı dosyasında Bursa 9. İş Mahkemesi'nin 2026/87 Talimat sayılı dosyası üzerinden aldırılan 01.10.2026 havale tarihli bilirkişi heyet raporu tarafımıza tebliğ edilmiş olup, yasal süresi içerisinde rapordaki haksız ve fahiş kusur tespitlerine itirazlarımızı sunuyoruz.

2- FİİLİ İŞVEREN VE SEVK-İDARE DAVA DIŞI ÖMER FARUK AKTÜRK'TEDİR:
Sayın heyet, Oltu Orman İşletme Müdürlüğü Hisar Orman İşletme Şefliği 393 nolu bölmedeki ağaç kesim ve nakil ihalesinin müvekkil şirket adına alınmış olmasını tek başına kusur izafesi için yeterli saymıştır. Oysa dosya kapsamındaki tüm tanık beyanları ve belgelerle sabittir ki; söz konusu bölmedeki işlerin fiili yürütümü, çalışanların işe alınması, sevk ve idaresi tamamen dava dışı Ömer Faruk AKTÜRK tarafından yapılmıştır. Müvekkil şirketin ve Erol Atmaca'nın sahadaki operasyonel sevk ve idareye doğrudan bir müdahalesi veya gözetim imkânı bulunmamaktadır.

3- MÜTEVEFFANIN AĞIR KUSURU VE İLLİYET BAĞININ KESİLMESİ:
Raporda müteveffa kazazede Orhan Sonsuz'a yalnızca %30 kusur izafe edilmesi hakkaniyete ve maddi vakıaya açıkça aykırıdır. Olay günü müteveffanın yanında bulunan iş arkadaşı tanık Remzi YÜCEL'in mahkeme ve savcılık huzurundaki açık beyanlarından da anlaşılacağı üzere; müteveffa olay tarihinde 43 yaşında, son derece tecrübeli bir traktör sürücüsü olmasına rağmen, tanık Remzi Yücel'in "Buraya traktör girmez, devrilirsin, aşağıdan dolaş" şeklindeki açık, mükerrer ve ısrarlı sözlü uyarılarını göz ardı etmiştir. Müteveffa, tehlikeli yamacı traktörle çıkmak için defalarca deneme yapmış ve neticede kendi ihtiyatsız ve ağır kusurlu eylemiyle traktörün devrilmesine sebebiyet vermiştir. Ağır işçi kusuru, somut olayda illiyet bağını kesmiştir.

4- MÜVEKKİLLERE ATFEDİLEN %35 KUSUR ORANI KABUL EDİLEMEZ:
Raporda müvekkil şirkete ve Erol Atmaca'ya %35 gibi fahiş bir kusur verilmesi vicdani ve hukuki dayanaktan yoksundur. Müvekkillerin herhangi bir kusur veya ihmali bulunmamaktadır. Kusur oranları belirlenirken 6331 sayılı Kanun ve yerleşik Yargıtay içtihatları gereğince fiili hâkimiyet ve kaçınılmazlık unsurları dikkate alınmamıştır.

5- YENİ HEYETTEN RAPOR ALINMALIDIR:
Yukarıda izah edilen eksiklik ve çelişkiler nedeniyle, dosyanın İstanbul Teknik Üniversitesi (İTÜ) veya Karadeniz Teknik Üniversitesi (KTÜ) Maden / İş Sağlığı ve Güvenliği Anabilim Dalı öğretim üyelerinden teşekkül edecek yeni ve bağımsız bir bilirkişi heyetine tevdii zorunludur.

HUKUKİ SEBEPLER    : HMK m. 281, TBK m. 417, 6331 sayılı İSGK, 5510 sayılı Kanun ve ilgili mevzuat.
NETİCE VE TALEP     : Yukarıda açıklanan nedenlerle;
1- 01.10.2026 tarihli bilirkişi raporuna vaki itirazlarımızın kabulüne,
2- Müvekkillere atfedilen fahiş kusur oranlarının reddi ile dosyanın üniversite öğretim üyelerinden oluşacak tarafsız yeni bir bilirkişi heyetine tevdi edilerek kusur raporu aldırılmasına karar verilmesini saygılarımla vekâleten arz ve talep ederim. 23.10.2026

                                                        Davacılar Vekili
                                                       Av. Can KIZILYAR
                                                (UYAP üzerinden e-imzalıdır)"""

    p_1 = [
        ("title", "OLTU 2. ASLİYE HUKUK MAHKEMESİ SAYIN HÂKİMLİĞİ'NE"),
        ("header", "DOSYA NO        : 2025/48 Esas (Talimat: Bursa 9. İş Mahkemesi 2026/87 D.İş)"),
        ("header", "DAVACILAR       : 1- Atmaca Madencilik İnş. Taah. Pet. San. Tic. Ltd. Şti. (VKN: 1030551690)\n                  2- Erol ATMACA (TCKN: 37867326226)"),
        ("header", "VEKİLİ          : Av. Can KIZILYAR (Hayfa Hukuk - 1463.Cd. No:4/7 Çukurambar, Çankaya/ANKARA)"),
        ("header", "DAVALI          : Sosyal Güvenlik Kurumu Başkanlığı (SGK)"),
        ("header", "D. KONUSU       : 01.10.2026 tarihli Bilirkişi Raporuna itirazlarımız ve yeni heyet raporu talebidir."),
        ("body", "Mahkemenizin yukarıda esas numarası yazılı dosyasında tanzim edilen 01.10.2026 tarihli bilirkişi heyet raporu tarafımıza tebliğ edilmiş olup, yasal süresi içerisinde rapordaki eksik ve fahiş kusur tespitlerine itiraz ediyoruz."),
        ("body", "FİİLİ İŞVEREN VE SEVK-İDARE DAVA DIŞI ÖMER FARUK AKTÜRK'TEDİR: İhale müvekkil şirket adına alınmış ise de ağaç kesim ve nakil işlerinin fiili yürütümü, işçilerin sevk ve idaresi tamamen dava dışı Ömer Faruk Aktürk tarafından yürütülmüştür. Müvekkillerin sahada doğrudan gözetim ve idare imkânı bulunmamaktadır."),
        ("body", "MÜTEVEFFANIN AĞIR KUSURU VE İLLİYET BAĞININ KESİLMESİ: Müteveffa Orhan Sonsuz tecrübeli bir işçi olup, tanık Remzi Yücel'in açık ve mükerrer uyarılarına rağmen dik yamaçta traktörü ısrarla zorlamış ve kendi ağır kusuruyla traktörün devrilmesine sebebiyet vermiştir. Raporda işçiye sadece %30 kusur verilmesi hayatın olağan akışına aykırıdır."),
        ("body", "Müvekkil şirket ve yetkilisine verilen %35 kusur oranı haksız ve dayanaksızdır. Bu nedenlerle dosyanın üniversite öğretim üyelerinden (İTÜ veya KTÜ) oluşacak yeni bir bilirkişi heyetine tevdi edilerek yeniden kusur raporu tanzim edilmesini talep ederiz."),
        ("sign", "Davacılar Vekili\nAv. Can KIZILYAR\n(e-imzalıdır)")
    ]
    generated_files.append(build_trio(base_1, raw_1, p_1))

    # =========================================================================
    # DİLEKÇE 2: Ankara 73. Asliye Ceza - Mütalaaya Karşı Katılan Beyanı
    # =========================================================================
    base_2 = "Ankara73AsC_2026_142_Mutalaaya_Karsi_Beyan"
    raw_2 = """ANKARA 73. ASLİYE CEZA MAHKEMESİ SAYIN HÂKİMLİĞİ'NE

DOSYA NO            : 2026/142 Esas
KATILAN             : Baneen Zaid Khlaf AL-AYID
VEKİLİ              : Av. Can KIZILYAR
                      Hayfa Hukuk - 1463.Cd. No:4/7 Çukurambar, Çankaya / ANKARA
SANIK               : Abdulkerim Abdullatif Hemod ZHİRİ (TCKN: 99035656610)
D. KONUSU           : İddia makamının 08.10.2026 tarihli esas hakkındaki mütalaasına karşı beyanlarımız ve sanığın en üst hadden cezalandırılması talebidir.

BEYANLARIMIZ        :

1- Mahkemenizin 08.10.2026 tarihli 2. celsesinde Sayın Cumhuriyet Savcısı tarafından sunulan esas hakkındaki mütalaada; toplanan deliller, katılan ve müşteki beyanları, adli hekim raporları ve soruşturma evrakı kapsamında sanığın eylemine uyan TCK'nın 86/2, 86/3-e, 53/1 ve 54/1 maddeleri uyarınca cezalandırılması talep edilmiştir. İddia makamının sanığın cezalandırılması yönündeki mütalaasına aynen iştirak ediyoruz.

2- SUÇ SABİTTİR VE SİLAHLA İŞLENMİŞTİR:
Sanık Abdulkerim Abdullatif Hemod Zhiri, müvekkil katılana yönelik kasten yaralama fiilini TCK 6/1-f maddesi anlamında fiilen saldırı ve savunmada kullanılmaya elverişli silahtan sayılan aletle gerçekleştirmiştir. Müvekkilde meydana gelen bedensel zarar dosyada mübrez kati hekim raporu ile sabittir.

3- TAKDİRİ İNDİRİM HÜKÜMLERİ UYGULANMAMALIDIR:
Sanık yargılama boyunca suçtan kurtulmaya yönelik soyut inkâr yolunu seçmiş, hiçbir pişmanlık emaresi göstermemiştir. Suçun işleniş biçimi, vahameti, müvekkil üzerinde bıraktığı travma gözetilerek cezasında TCK m. 62 uyarınca takdiri indirim yapılmaksızın temel cezanın üst hadden tayin edilmesi gerekmektedir. Ayrıca sanık hakkında TCK m. 53 uyarınca güvenlik tedbirlerinin en katı biçimde uygulanmasını talep ederiz.

NETİCE VE TALEP     : Yukarıda arz ve izah edilen nedenlerle;
1- İddia makamının cezalandırma yönündeki mütalaası doğrultusunda sanığın TCK m. 86/2, 86/3-e maddeleri uyarınca ve takdiri indirim uygulanmaksızın EN ÜST HADDEN CEZALANDIRILMASINA,
2- Sanık hakkında TCK m. 53 uyarınca hak yoksunluklarına hükmedilmesine ve suçta kullanılan aletin TCK m. 54 uyarınca MÜSADERESİNE,
3- Katılan vekili olarak lehimize maktu vekalet ücreti takdir edilmesine karar verilmesini saygılarımla vekâleten arz ve talep ederim. 23.10.2026

                                                         Katılan Vekili
                                                        Av. Can KIZILYAR
                                                 (UYAP üzerinden e-imzalıdır)"""

    p_2 = [
        ("title", "ANKARA 73. ASLİYE CEZA MAHKEMESİ SAYIN HÂKİMLİĞİ'NE"),
        ("header", "DOSYA NO    : 2026/142 Esas"),
        ("header", "KATILAN     : Baneen Zaid Khlaf AL-AYID"),
        ("header", "VEKİLİ      : Av. Can KIZILYAR (Hayfa Hukuk - 1463.Cd. No:4/7 Çukurambar, Çankaya/ANKARA)"),
        ("header", "SANIK       : Abdulkerim Abdullatif Hemod ZHİRİ (TCKN: 99035656610)"),
        ("header", "D. KONUSU   : 08.10.2026 tarihli esas hakkındaki mütalaaya karşı beyanlarımız ve cezalandırma talebidir."),
        ("body", "İddia makamının 08.10.2026 tarihli celsede sunduğu sanığın TCK 86/2, 86/3-e, 53/1 ve 54/1 maddeleri uyarınca cezalandırılması yönündeki esas hakkındaki mütalaasına iştirak ediyoruz."),
        ("body", "Sanık müvekkile karşı yaralama fiilini silahtan sayılan aletle icra etmiş olup, müvekkilin yaralandığı kati hekim raporuyla sübut bulmuştur. Sanığın pişmanlıktan uzak tavırları gözetilerek cezasında TCK 62 uygulanmaksızın üst hadden cezalandırılmasına ve TCK 53 uyarınca hak yoksunluklarına karar verilmesini talep ederiz."),
        ("sign", "Katılan Vekili\nAv. Can KIZILYAR\n(e-imzalıdır)")
    ]
    generated_files.append(build_trio(base_2, raw_2, p_2))

    # =========================================================================
    # DİLEKÇE 3: Ankara 2. Çocuk Mahkemesi - İstinaf Başvuru Dilekçesi
    # =========================================================================
    base_3 = "Ankara2Cocuk_2025_385_Istinaf_Basvurusu"
    raw_3 = """ANKARA BÖLGE ADLİYE MAHKEMESİ İLGİLİ CEZA DAİRESİ'NE
Sunulmak Üzere
ANKARA 2. ÇOCUK MAHKEMESİ SAYIN HÂKİMLİĞİ'NE

DOSYA NO            : 2025/385 Esas
KARAR NO            : 2026/705 Karar (Karar Tarihi: 13/10/2026)
İSTİNAF EDEN
KATILAN             : Nesrin TEKTEK (TCKN: 13282096326)
VEKİLİ              : Av. Can KIZILYAR
                      Hayfa Hukuk - 1463.Cd. No:4/7 Çukurambar, Çankaya / ANKARA
ADLİ SÜREÇTEKİ ÇOCUK: Servet SAMİŞ (TCKN: 13471081386)
MÜDAFİİ             : Av. Melike YILMAZ
SUÇ                 : Kişiyi Hürriyetinden Yoksun Kılma (TCK m. 109)
D. KONUSU           : Ankara 2. Çocuk Mahkemesi'nin 13.10.2026 tarih ve 2025/385 E., 2026/705 K. sayılı Ceza Verilmesine Yer Olmadığı (CVYO) kararına karşı istinaf kanun yoluna başvuru dilekçemizdir.

İSTİNAF SEBEPLERİ   :

1- USUL YÖNÜNDEN: MAĞDUR DİNLENİLMEDEN VE SAVUNMA HAKKI KISITLANARAK KARAR VERİLMİŞTİR:
İlk derece mahkemesi gerekçeli kararında; "Mağdurun dinlenilmesi yönündeki ara karardan vazgeçilmesine ve soruşturmadaki beyanı ile yetinilmesine" karar verildiğini belirtmiştir. Mağdur vekili olarak dosyaya sunduğumuz taleplerimize rağmen, mağdurun bizzat huzurda dinlenilmesinden vazgeçilmesi CMK m. 234 ve AİHS m. 6 ile teminat altına alınan adil yargılanma ve hak arama hürriyetini ağır biçimde ihlal etmiştir.

2- ESAS YÖNÜNDEN: TEK HEKİM RAPORUNA DAYALI OLARAK KUSUR YETENEĞİNİN BULUNMADIĞI KABUL EDİLEMEZ:
Mahkemece, Ankara Adli Tıp Şube Müdürlüğü'nün 21.05.2025 tarihli tek hekim tarafından tanzim edilen raporuna dayanılarak adli süreçteki çocuğun suçun hukuki anlam ve sonuçlarını algılayamadığı kabul edilmiş ve TCK 31/2 uyarınca ceza verilmesine yer olmadığına hükmedilmiştir. Kişiyi hürriyetinden yoksun kılma gibi çok aşamalı, iradi ve planlama gerektiren bir suçta tek hekim raporu ile fiilin algılanamayacağının kabulü yerleşik içtihatlara aykırıdır. Adli Tıp İhtisas Kurulu veya Üniversite Çocuk Psikiyatrisi heyetinden kapsamlı kurul raporu aldırılmadan eksik inceleme ile hüküm kurulması yasaya aykırıdır.

3- EYLEM SABİTTİR VE SSÇ CEZALANDIRILMALIDIR:
Toplanan deliller, kolluk tutanakları ve dosya kapsamı adli süreçteki çocuğun suçu bilinçli şekilde işlediğini ortaya koymaktadır. Eksik incelemeye dayalı karar bozulmalıdır.

NETİCE VE TALEP     : Yukarıda arz edilen nedenlerle;
1- İstinaf başvurumuzun KABULÜNE,
2- Ankara 2. Çocuk Mahkemesi'nin 13.10.2026 tarih ve 2025/385 E., 2026/705 K. sayılı hukuka aykırı kararının KALDIRILMASINA,
3- Adli süreçteki çocuk Servet Samiş'in eylemine uyan Kişiyi Hürriyetinden Yoksun Kılma suçundan CEZALANDIRILMASINA karar verilmesini vekaleten saygılarımla arz ve talep ederim. 23.10.2026

                                                         Katılan Vekili
                                                        Av. Can KIZILYAR
                                                 (UYAP üzerinden e-imzalıdır)"""

    p_3 = [
        ("title", "ANKARA BÖLGE ADLİYE MAHKEMESİ İLGİLİ CEZA DAİRESİ'NE\nSunulmak Üzere\nANKARA 2. ÇOCUK MAHKEMESİ SAYIN HÂKİMLİĞİ'NE"),
        ("header", "DOSYA NO        : 2025/385 Esas, 2026/705 Karar (K.T: 13.10.2026)"),
        ("header", "İSTİNAF EDEN    : Katılan Nesrin TEKTEK (TCKN: 13282096326)"),
        ("header", "VEKİLİ          : Av. Can KIZILYAR (Hayfa Hukuk - 1463.Cd. No:4/7 Çukurambar, Çankaya/ANKARA)"),
        ("header", "ADLİ ÇOCUK      : Servet SAMİŞ (Müdafii: Av. Melike YILMAZ)"),
        ("header", "SUÇ             : Kişiyi Hürriyetinden Yoksun Kılma (TCK m. 109)"),
        ("header", "D. KONUSU       : 13.10.2026 tarihli CVYO kararına karşı istinaf başvuru dilekçemizdir."),
        ("body", "İlk derece mahkemesi mağdur Nesrin Tektek'i bizzat dinleme yönündeki ara kararından hukuksuz vazgeçerek ve savunma hakkımızı kısıtlayarak karar vermiştir."),
        ("body", "Kişiyi hürriyetinden yoksun kılma gibi ağır ve planlı bir suçta Adli Tıp Şube Müdürlüğü'nün tek hekim raporuyla SSÇ'nin algılama yeteneğinin bulunmadığının kabulü eksik incelemedir. ATK İhtisas Kurulu veya Üniversite heyet raporu alınmadan hüküm kurulamaz."),
        ("body", "Hukuka aykırı kararın kaldırılarak adli süreçteki çocuğun cezalandırılmasına karar verilmesini vekaleten talep ederiz."),
        ("sign", "Katılan Vekili\nAv. Can KIZILYAR\n(e-imzalıdır)")
    ]
    generated_files.append(build_trio(base_3, raw_3, p_3))

    # =========================================================================
    # DİLEKÇE 4A: Oltu 3. Asliye Hukuk - İstinaf Derkenar Talebi
    # =========================================================================
    base_4a = "Oltu3AsH_2026_24_Derkenar_Talebi"
    raw_4a = """OLTU 3. ASLİYE HUKUK MAHKEMESİ SAYIN HÂKİMLİĞİ'NE

DOSYA NO            : 2026/24 Esas
İCRA TAKİP NO       : Oltu İcra Dairesi 2026/345 Esas
DAVALILAR           : 1- Atmaca Maden, İnşaat, Taahhüt, Petrol San. Tic. Ltd. Şti. (VKN: 1030551690)
                      2- Erol ATMACA (TCKN: 37867326226)
VEKİLİ              : Av. Can KIZILYAR
                      Hayfa Hukuk - 1463.Cd. No:4/7 Çukurambar, Çankaya / ANKARA
                      UETS: 15587-85062-32745
D. KONUSU           : Tehiri İcra Talepli İstinaf Başvuru Derkenarı Verilmesi Talebidir.

TALEP VE BEYANLAR   :

Mahkemenizin yukarıda esas numarası yazılı dosyasında verilen karara karşı süresi içerisinde tehiri icra (icranın geri bırakılması) talepli olarak istinaf kanun yoluna başvurulmuştur.

Oltu İcra Dairesi'nin 2026/345 Esas sayılı icra takip dosyasına ibraz edilerek İİK m. 36 uyarınca mehil vesikası alınabilmesi ve müvekkiller aleyhine başlatılan icra işlemlerinin durdurulması amacıyla;

Mahkemeniz kararına karşı TEHİRİ İCRA TALEPLİ OLARAK İSTİNAF YOLUNA BAŞVURULDUĞUNU gösterir derkenar yazısının tarafımıza verilmesini, ayrıca bir suretinin UYAP sistemi üzerinden ilgili icra dairesine gönderilmesini saygılarımla vekaleten arz ve talep ederim. 23.10.2026

                                                        Davalılar Vekili
                                                       Av. Can KIZILYAR
                                                (UYAP üzerinden e-imzalıdır)"""

    p_4a = [
        ("title", "OLTU 3. ASLİYE HUKUK MAHKEMESİ SAYIN HÂKİMLİĞİ'NE"),
        ("header", "DOSYA NO        : 2026/24 Esas (İcra Dosya No: Oltu İcra Dairesi 2026/345 Esas)"),
        ("header", "DAVALILAR       : 1- Atmaca Maden İnş. Taah. Pet. San. Tic. Ltd. Şti.\n                  2- Erol ATMACA"),
        ("header", "VEKİLİ          : Av. Can KIZILYAR (Hayfa Hukuk - 1463.Cd. No:4/7 Çukurambar, Çankaya/ANKARA)"),
        ("header", "D. KONUSU       : Tehiri İcra Talepli İstinaf Derkenarı Verilmesi Talebidir."),
        ("body", "Mahkemenizin kararına karşı süresi içerisinde tehiri icra talepli olarak istinaf kanun yoluna başvurulmuştur."),
        ("body", "Oltu İcra Dairesi'nin 2026/345 Esas sayılı dosyasına ibraz edilerek mehil vesikası alınabilmesi için mahkemenizce tehiri icra talepli istinaf başvurusu yapıldığına dair derkenar verilmesini talep ederiz."),
        ("sign", "Davalılar Vekili\nAv. Can KIZILYAR\n(e-imzalıdır)")
    ]
    generated_files.append(build_trio(base_4a, raw_4a, p_4a))

    # =========================================================================
    # DİLEKÇE 4B: Oltu İcra Dairesi - İİK m. 36 Mehil Vesikası Talebi
    # =========================================================================
    base_4b = "OltuIcra_2026_345_Mehil_Vesikasi_Talebi"
    raw_4b = """OLTU İCRA DAİRESİ MÜDÜRLÜĞÜ'NE

DOSYA NO            : 2026/345 Esas
DAYANAK MAHKEME     : Oltu 3. Asliye Hukuk Mahkemesi 2026/24 Esas
BORÇLULAR           : 1- Atmaca Maden, İnşaat, Taahhüt, Petrol San. Tic. Ltd. Şti. (VKN: 1030551690)
                      2- Erol ATMACA (TCKN: 37867326226)
VEKİLİ              : Av. Can KIZILYAR
                      Hayfa Hukuk - 1463.Cd. No:4/7 Çukurambar, Çankaya / ANKARA
ALACAKLI            : İlgili Alacaklı Taraf
D. KONUSU           : İİK m. 36 uyarınca teminat mukabilinde mehil vesikası verilmesi ve haciz işlemlerinin ertelenmesi talebidir.

TALEP VE BEYANLAR   :

1- Müdürlüğünüzün yukarıda esas numarası yazılı dosyasında takibe dayanak Oltu 3. Asliye Hukuk Mahkemesi'nin 2026/24 Esas sayılı ilamına karşı süresi içerisinde tehiri icra talepli olarak istinaf kanun yoluna başvurulmuş olup, ekte Mahkemeden alınan istinaf derkenarı sunulmuştur.

2- Dosya kapak hesabı çıkartılarak icra takip borcu, işlemiş faiz ve ferileri karşılayacak miktarda teminat mektubu / nakit teminat dosyanıza depo edilmeye hazırdır.

3- İcra ve İflas Kanunu'nun 36. maddesi uyarınca; Bölge Adliye Mahkemesi İlgili Hukuk Dairesi'nden icranın geri bırakılması (tehiri icra) kararı getirilmek üzere tarafımıza 60 (altmış) gün mehil vesikası verilmesini, dosya kapak hesabı çıkartılarak teminat miktarının belirlenmesini ve bu süre zarfında dosya üzerindeki haciz ve muhafaza işlemlerinin tatbik edilmemesini vekâleten arz ve talep ederim. 23.10.2026

EK                  : Oltu 3. Asliye Hukuk Mahkemesi 2026/24 E. İstinaf Derkenarı

                                                        Borçlular Vekili
                                                       Av. Can KIZILYAR
                                                (UYAP üzerinden e-imzalıdır)"""

    p_4b = [
        ("title", "OLTU İCRA DAİRESİ MÜDÜRLÜĞÜ'NE"),
        ("header", "DOSYA NO        : 2026/345 Esas (Dayanak: Oltu 3. Asliye Hukuk Mahkemesi 2026/24 Esas)"),
        ("header", "BORÇLULAR       : 1- Atmaca Maden İnş. Taah. Pet. San. Tic. Ltd. Şti.\n                  2- Erol ATMACA"),
        ("header", "VEKİLİ          : Av. Can KIZILYAR (Hayfa Hukuk - 1463.Cd. No:4/7 Çukurambar, Çankaya/ANKARA)"),
        ("header", "D. KONUSU       : İİK m. 36 uyarınca teminat karşılığı mehil vesikası verilmesi talebidir."),
        ("body", "Takibe dayanak ilama karşı tehiri icra talepli olarak istinaf kanun yoluna başvurulmuş olup ekte mahkeme derkenarı ibraz edilmiştir."),
        ("body", "İİK m. 36 uyarınca kapak hesabı yapılarak belirlenecek teminat tutarı karşılığında Bölge Adliye Mahkemesi'nden tehiri icra kararı getirilmek üzere 60 gün mehil vesikası tanzim edilmesini ve icra işlemlerinin durdurulmasını talep ederiz."),
        ("sign", "Borçlular Vekili\nAv. Can KIZILYAR\n(e-imzalıdır)")
    ]
    generated_files.append(build_trio(base_4b, raw_4b, p_4b))

    return generated_files

if __name__ == "__main__":
    files = generate_all()
    print(f"\n🎉 Toplam {len(files)} dilekçe seti (.udf, .odt, .pdf) başarıyla oluşturuldu!")
    for udf, odt, pdf in files:
        print(f"  • {os.path.basename(udf)} | {os.path.basename(odt)} | {os.path.basename(pdf)}")
