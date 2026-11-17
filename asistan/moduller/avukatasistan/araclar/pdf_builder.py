#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, glob
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT

OUTPUT_DIR = "/data/data/com.termux/files/home/Downloads/Hazirlanan_Dilekceler"

def create_pdf(base_name, paragraphs):
    pdf_path = os.path.join(OUTPUT_DIR, f"{base_name}.pdf")
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        alignment=TA_CENTER,
        spaceAfter=15
    )

    header_style = ParagraphStyle(
        'DocHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10.5,
        leading=15,
        alignment=TA_JUSTIFY,
        firstLineIndent=20,
        spaceAfter=8
    )

    sign_style = ParagraphStyle(
        'DocSign',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        alignment=TA_RIGHT,
        spaceBefore=15
    )

    story = []
    for p_type, text in paragraphs:
        # reportlab XML escaping
        safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
        if p_type == "title":
            story.append(Paragraph(safe_text, title_style))
        elif p_type == "header":
            story.append(Paragraph(safe_text, header_style))
        elif p_type == "sign":
            story.append(Paragraph(safe_text, sign_style))
        else:
            story.append(Paragraph(safe_text, body_style))

    doc.build(story)
    print(f"✅ PDF Hazırlandı: {base_name}.pdf")
    return pdf_path

if __name__ == "__main__":
    from generate_pending_petitions import generate_all
    # We can import the paragraphs from generate_pending_petitions
    pass
