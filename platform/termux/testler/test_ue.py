"""ue.py birim testleri (UYAP jar'ı ya da ekran gerekmez):  python3 -m unittest discover -s testler"""
import importlib.util
import os
import tempfile
import unittest
import zipfile

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("ue", os.path.join(KOK, "bilesenler", "ue.py"))
ue = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ue)


def udf_yaz(yol, xml):
    with zipfile.ZipFile(yol, "w") as z:
        z.writestr("content.xml", xml)


class UdfTesti(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_cdata_havuzu_okunur(self):
        p = os.path.join(self.d, "a.udf")
        udf_yaz(p, '<?xml version="1.0" encoding="UTF-8" ?><template format_id="1.8"><content><![CDATA[Başlık\nGövde & <metin>\n]]></content>'
                   '<properties><pageFormat mediaSizeName="1"/></properties><elements resolver="x"><paragraph><content startOffset="0" length="7"/></paragraph></elements></template>')
        self.assertEqual(ue.udf_metni(p), "Başlık\nGövde & <metin>\n")

    def test_bos_content_xml_cokmez(self):
        p = os.path.join(self.d, "bos.udf")
        udf_yaz(p, "")
        self.assertEqual(ue.udf_metni(p), "")

    def test_doc_html_kacisi(self):
        p = os.path.join(self.d, "b.udf")
        udf_yaz(p, '<template><content><![CDATA[<script>x</script>\n]]></content></template>')
        self.assertEqual(ue.udf_to_doc(p), 0)
        with open(os.path.join(self.d, "b_Disari_Aktarilan.doc"), encoding="utf-8") as f:
            s = f.read()
        self.assertIn("&lt;script&gt;", s)
        self.assertNotIn("<script>", s)


class ArgumanTesti(unittest.TestCase):
    def test_file_uri_ve_bosluk(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "dilekçe örnek.udf")
        open(p, "w").close()
        from urllib.parse import quote
        self.assertEqual(ue.dosya_argumanlari(["file://" + quote(p)]), [p])
        self.assertEqual(ue.dosya_argumanlari([p, "/yok/boyle.udf", "--x"]), [p])


class AyarTesti(unittest.TestCase):
    def test_varsayilanlar_ve_dosya(self):
        d = tempfile.mkdtemp()
        yol = os.path.join(d, "u", "ayarlar.ini")
        a = ue.ayarlari_yukle(yol)
        self.assertTrue(os.path.exists(yol))
        self.assertEqual(a["arayuz"]["tema"], "acik")
        a["arayuz"]["tema"] = "koyu"
        with open(yol, "w", encoding="utf-8") as f:
            a.write(f)
        self.assertEqual(ue.ayarlari_yukle(yol)["arayuz"]["tema"], "koyu")

    def test_satir_ici_yorum_ve_renk(self):
        yol = os.path.join(tempfile.mkdtemp(), "a.ini")
        with open(yol, "w", encoding="utf-8") as f:
            f.write("[arayuz]\ntema = koyu   ; acik | koyu\nvurgu = #C0392B\n")
        a = ue.ayarlari_yukle(yol)
        self.assertEqual(a["arayuz"]["tema"], "koyu")
        self.assertEqual(a["arayuz"]["vurgu"], "#C0392B")

    def test_evet(self):
        for s in ("evet", "E", "true", "1", "açık"):
            self.assertTrue(ue.evet(s), s)
        for s in ("hayir", "0", "", "false"):
            self.assertFalse(ue.evet(s), s)


class KomutTesti(unittest.TestCase):
    def setUp(self):
        self.a = ue.ayarlari_yukle(os.path.join(tempfile.mkdtemp(), "a.ini"))

    def test_olcek(self):
        self.assertEqual(ue.olcek_degeri("1,5"), "1.5")
        self.assertEqual(ue.olcek_degeri("9"), "3")
        self.assertEqual(ue.olcek_degeri("otomatik", dpi=144), "1.5")
        self.assertEqual(ue.olcek_degeri("otomatik", dpi=72), "1")

    def test_modul_izinleri(self):
        k = ue.komut_olustur("java", 21, "cp", self.a, True, False, [], "/w")
        self.assertIn("--add-opens=java.desktop/sun.swing=ALL-UNNAMED", k)   # seçim vurgusu
        self.assertIn("--add-opens=jdk.crypto.cryptoki/sun.security.pkcs11.wrapper=ALL-UNNAMED", k)

    def test_bellek(self):
        self.assertEqual(ue.bellek_mb("2048"), 2048)
        self.assertEqual(ue.bellek_mb("100"), 256)
        m = ue.bellek_mb("otomatik")
        self.assertTrue(768 <= m <= 4096, m)

    def test_baslatici_komutu(self):
        k = ue.komut_olustur("java", 21, "cp", self.a, True, True, ["/x/a.usf"], "/w")
        self.assertIn("uyaptermux.Baslatici", k)
        self.assertEqual(k[-1], "/x/a.usf")
        self.assertIn("-Dsun.java2d.uiScale=1.2", k)
        self.assertFalse(any(x.startswith("-Dflatlaf.uiScale") for x in k), "cift olcekleme")
        self.assertFalse(any("d3d" in x for x in k))
        self.assertTrue(any(x.startswith("-Deimza.dir=") for x in k))
        self.assertIn("-Duyap.alt.menu=false", k)

    def test_duz_modda_usf_sablon_acilir(self):
        k = ue.komut_olustur("java", 11, "cp", self.a, False, False, ["/x/A.USF"], "/w")
        self.assertEqual(k[-2:], ["EDITOR_TYPE_TEMPLATE", "/x/A.USF"])
        k = ue.komut_olustur("java", 11, "cp", self.a, False, False, ["/x/a.udf"], "/w")
        self.assertEqual(k[-2:], ["EDITOR_TYPE_DOCUMENT", "/x/a.udf"])

    def test_java8_add_opens_almaz(self):
        k = ue.komut_olustur("java", 8, "cp", self.a, False, False, [], "/w")
        self.assertFalse(any(x.startswith("--add-opens") for x in k))


class GlibcTesti(unittest.TestCase):
    def test_elf_yorumlayici(self):
        import sys
        self.assertIn("ld", ue.elf_yorumlayici(os.path.realpath(sys.executable)))
        self.assertEqual(ue.elf_yorumlayici(os.path.join(KOK, "kur.sh")), "")

    def test_bionic_java_ortami_degismez(self):
        eski = ue.glibc_jdk
        try:
            ue.glibc_jdk = lambda j: ""
            os.environ["LD_PRELOAD"] = "/x/libtermux-exec.so"
            self.assertEqual(ue.java_ortami("/j21/bin/java").get("LD_PRELOAD"), "/x/libtermux-exec.so")
            ue.glibc_jdk = lambda j: "glibc"
            self.assertNotIn("LD_PRELOAD", ue.java_ortami("/jdk14/bin/java"))
            self.assertEqual(ue.java_on_ek("/jdk14/bin/java"), ["-Xshare:off"])
            k = ue.komut_olustur("/jdk14/bin/java", 14, "cp", ue.ayarlari_yukle(os.path.join(tempfile.mkdtemp(), "a.ini")),
                                 True, False, [], "/w")
            self.assertEqual(k[:2], ["/jdk14/bin/java", "-Xshare:off"])
            ue.glibc_jdk = lambda j: ""
            self.assertEqual(ue.java_on_ek("/j21/bin/java"), [])
        finally:
            ue.glibc_jdk = eski
            os.environ.pop("LD_PRELOAD", None)


class JavaSecimTesti(unittest.TestCase):
    def test_11_tercih_edilir(self):
        eski_a, eski_s = ue.jdk_adaylari, ue._jdk_surumu
        try:
            ue.jdk_adaylari = lambda: ["/j21", "/j17", "/j11"]
            ue._jdk_surumu = lambda j: int(j[2:])
            self.assertEqual(ue.java_bul(""), ("/j11", 11))
            ue.jdk_adaylari = lambda: ["/j21", "/j17"]
            self.assertEqual(ue.java_bul(""), ("/j17", 17))
            ue.jdk_adaylari = lambda: []
            self.assertEqual(ue.java_bul(""), (None, 0))
        finally:
            ue.jdk_adaylari, ue._jdk_surumu = eski_a, eski_s


if __name__ == "__main__":
    unittest.main()
