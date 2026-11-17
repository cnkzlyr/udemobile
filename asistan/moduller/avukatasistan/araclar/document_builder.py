#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚖️ UDF ve ODT DİLEKÇE OLUŞTURUCU MOTORU
- UYAP Doküman Editörü (.udf) formatında standart 1.8 XML + ZIP oluşturur.
- LibreOffice / OpenOffice (.odt) formatında standart ODF dokümanı oluşturur.
"""

import os
import zipfile
import io
from datetime import datetime

# odfpy kütüphanesi
from odf.opendocument import OpenDocumentText
from odf.style import Style, TextProperties, ParagraphProperties
from odf.text import P, Span

OUTPUT_DIR = "/data/data/com.termux/files/home/Downloads/Hazirlanan_Dilekceler"
os.makedirs(OUTPUT_DIR, exist_ok=True)

AVUKAT_BILGISI = {
    "ad_soyad": "Av. Can KIZILYAR",
    "baro_sicil": "",
    "adres": "Hayfa Hukuk - 1463.Cd. No:4/7, Çukurambar, Çankaya / ANKARA",
    "uets": "15587-85062-32745",
    "eposta": "cnkzlyrr@gmail.com"
}


def build_udf_xml(full_text):
    """UYAP 1.8 uyumlu content.xml içeriğini oluşturur."""
    xml = f"""<?xml version="1.0" encoding="UTF-8" ?> 

<template format_id="1.8" >
<content><![CDATA[{full_text}
]]></content>
<properties><pageFormat mediaSizeName="1" leftMargin="70.8661413192749" rightMargin="70.8661413192749" topMargin="70.8661413192749" bottomMargin="70.8661413192749" paperOrientation="1" headerFOffset="20.0" footerFOffset="28.34645652770996" /></properties>
<elements resolver="hvl-default" >
<paragraph RightIndent="0.0" LineSpacing="0.15999997" Alignment="0" Hanging="0.0" LeftIndent="0.0"><content family="Times New Roman" size="12" description="Gövde" startOffset="0" length="{len(full_text)}" /></paragraph>
</elements>
<styles><style name="default" description="Geçerli" family="Times New Roman" size="12" bold="false" italic="false" foreground="-16777216" /><style name="hvl-default" family="Times New Roman" size="12" description="Gövde" /></styles>
</template>
"""
    return xml.encode("utf-8")


def export_udf(file_path, full_text):
    """Tek bir content.xml barındıran geçerli .udf dosyası yazar."""
    xml_data = build_udf_xml(full_text)
    with zipfile.ZipFile(file_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.xml", xml_data)
    return file_path


def export_odt(file_path, paragraphs):
    """odfpy kullanarak şık formatlanmış bir .odt dosyası oluşturur."""
    doc = OpenDocumentText()

    # Stiller
    # Başlık Stili
    s_title = Style(name="MahkemeBaslik", family="paragraph")
    s_title.addElement(ParagraphProperties(textalign="center", marginbottom="0.4cm", margintop="0.2cm"))
    s_title.addElement(TextProperties(fontfamily="Times New Roman", fontsize="12pt", fontweight="bold"))
    doc.styles.addElement(s_title)

    # Konu / Yan Başlık Stili
    s_header = Style(name="YanBaslik", family="paragraph")
    s_header.addElement(ParagraphProperties(textalign="left", marginbottom="0.2cm", margintop="0.1cm"))
    s_header.addElement(TextProperties(fontfamily="Times New Roman", fontsize="11pt", fontweight="bold"))
    doc.styles.addElement(s_header)

    # Gövde Stili
    s_body = Style(name="GövdeMetni", family="paragraph")
    s_body.addElement(ParagraphProperties(textalign="justify", textindent="1.0cm", marginbottom="0.25cm"))
    s_body.addElement(TextProperties(fontfamily="Times New Roman", fontsize="11.5pt"))
    doc.styles.addElement(s_body)

    # İmza Stili
    s_sign = Style(name="ImzaBlok", family="paragraph")
    s_sign.addElement(ParagraphProperties(textalign="right", marginbottom="0.1cm", margintop="0.4cm"))
    s_sign.addElement(TextProperties(fontfamily="Times New Roman", fontsize="11pt", fontweight="bold"))
    doc.styles.addElement(s_sign)

    for p_type, text in paragraphs:
        if p_type == "title":
            p = P(stylename=s_title, text=text)
        elif p_type == "header":
            p = P(stylename=s_header, text=text)
        elif p_type == "sign":
            p = P(stylename=s_sign, text=text)
        else:
            p = P(stylename=s_body, text=text)
        doc.text.addElement(p)

    doc.save(file_path)
    return file_path


def create_document_pair(base_name, raw_text, paragraphs_list):
    """Hem .udf hem de .odt dosyalarını oluşturup yollarını döndürür."""
    udf_path = os.path.join(OUTPUT_DIR, f"{base_name}.udf")
    odt_path = os.path.join(OUTPUT_DIR, f"{base_name}.odt")

    export_udf(udf_path, raw_text)
    export_odt(odt_path, paragraphs_list)

    print(f"✅ Hazırlandı: {base_name}.udf & {base_name}.odt")
    return udf_path, odt_path
