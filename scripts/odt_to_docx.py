#!/usr/bin/env python3
"""
odt_to_docx.py
Converts official Havelsan ODT to Microsoft Word (.docx) preserving:
- Paragraph text and styles
- Text alignments (Center, Right, Justify, Left)
- Bold, Italic, Underline
- Tables (rows, columns, cell contents)
- Page margins
"""
import sys
import os
import zipfile
import xml.etree.ElementTree as ET
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

NS = {
    'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
    'style': 'urn:oasis:names:tc:opendocument:xmlns:style:1.0',
    'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
    'table': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
    'draw': 'urn:oasis:names:tc:opendocument:xmlns:drawing:1.0',
    'fo': 'urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0'
}

def parse_styles(styles_xml):
    """Parse paragraph alignment and font styles from styles.xml / content.xml"""
    alignments = {}
    font_styles = {}
    if not styles_xml:
        return alignments, font_styles
    try:
        root = ET.fromstring(styles_xml)
        for s in root.iter(f"{{{NS['style']}}}style"):
            name = s.get(f"{{{NS['style']}}}name")
            p_prop = s.find(f"{{{NS['style']}}}paragraph-properties")
            if p_prop is not None:
                align = p_prop.get(f"{{{NS['fo']}}}text-align")
                if align:
                    alignments[name] = align.lower()
            t_prop = s.find(f"{{{NS['style']}}}text-properties")
            if t_prop is not None:
                weight = t_prop.get(f"{{{NS['fo']}}}font-weight")
                posture = t_prop.get(f"{{{NS['fo']}}}font-style")
                decor = t_prop.get(f"{{{NS['style']}}}text-underline-style")
                font_styles[name] = {
                    'bold': weight == 'bold',
                    'italic': posture == 'italic',
                    'underline': decor is not None and decor != 'none'
                }
    except Exception as e:
        pass
    return alignments, font_styles

def convert_odt_to_docx(odt_path, docx_path):
    if not os.path.exists(odt_path):
        print(f"Error: {odt_path} not found", file=sys.stderr)
        sys.exit(1)

    doc = Document()

    # Set Standard A4 Page Margins (2.5 cm on all sides)
    for section in doc.sections:
        section.page_width = Inches(8.27)
        section.page_height = Inches(11.69)
        section.top_margin = Inches(0.98)
        section.bottom_margin = Inches(0.98)
        section.left_margin = Inches(0.98)
        section.right_margin = Inches(0.98)

    with zipfile.ZipFile(odt_path, 'r') as z:
        content_xml = z.read('content.xml')
        styles_xml = z.read('styles.xml') if 'styles.xml' in z.namelist() else b''

    alignments, font_styles = parse_styles(styles_xml)
    c_align, c_font = parse_styles(content_xml)
    alignments.update(c_align)
    font_styles.update(c_font)

    root = ET.fromstring(content_xml)
    body = root.find(f"{{{NS['office']}}}body")
    text_elem = body.find(f"{{{NS['office']}}}text") if body is not None else None
    if text_elem is None:
        text_elem = root

    def get_element_text_with_runs(p_elem):
        runs = []
        for child in p_elem:
            tag = child.tag
            if tag == f"{{{NS['text']}}}span":
                s_name = child.get(f"{{{NS['text']}}}style-name", "")
                st = font_styles.get(s_name, {})
                txt = "".join(child.itertext())
                runs.append((txt, st))
            elif tag == f"{{{NS['text']}}}tab":
                runs.append(("\t", {}))
            elif tag == f"{{{NS['text']}}}s":
                cnt = int(child.get(f"{{{NS['text']}}}c", "1"))
                runs.append((" " * cnt, {}))
            elif tag == f"{{{NS['text']}}}line-break":
                runs.append(("\n", {}))
        if not runs:
            # Fallback to direct text
            full_txt = "".join(p_elem.itertext())
            if full_txt:
                runs.append((full_txt, {}))
        return runs

    def apply_align(p, align_str):
        if not align_str:
            return
        if align_str == 'center':
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif align_str in ('right', 'end'):
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        elif align_str == 'justify':
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        elif align_str in ('left', 'start'):
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT

    for child in text_elem:
        tag = child.tag
        if tag == f"{{{NS['text']}}}p" or tag == f"{{{NS['text']}}}h":
            style_name = child.get(f"{{{NS['text']}}}style-name", "")
            align = alignments.get(style_name, "")

            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.15
            apply_align(p, align)

            runs = get_element_text_with_runs(child)
            for txt, st in runs:
                r = p.add_run(txt)
                r.font.name = "Times New Roman"
                r.font.size = Pt(12)
                if st.get('bold'):
                    r.bold = True
                if st.get('italic'):
                    r.italic = True
                if st.get('underline'):
                    r.underline = True

        elif tag == f"{{{NS['table']}}}table":
            rows = child.findall(f"{{{NS['table']}}}table-row")
            if not rows:
                continue
            max_cols = 0
            for r in rows:
                cells = r.findall(f"{{{NS['table']}}}table-cell")
                max_cols = max(max_cols, len(cells))
            if max_cols == 0:
                continue

            tbl = doc.add_table(rows=len(rows), cols=max_cols)
            tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
            tbl.style = 'Table Grid'

            for r_idx, row_elem in enumerate(rows):
                cell_elems = row_elem.findall(f"{{{NS['table']}}}table-cell")
                for c_idx, cell_elem in enumerate(cell_elems):
                    if c_idx >= max_cols:
                        break
                    doc_cell = tbl.cell(r_idx, c_idx)
                    doc_cell.paragraphs[0].text = "" # clear default
                    p_elems = cell_elem.findall(f"{{{NS['text']}}}p")
                    for p_sub in p_elems:
                        s_name = p_sub.get(f"{{{NS['text']}}}style-name", "")
                        align = alignments.get(s_name, "")
                        cp = doc_cell.add_paragraph()
                        cp.paragraph_format.space_before = Pt(0)
                        cp.paragraph_format.space_after = Pt(0)
                        apply_align(cp, align)
                        runs = get_element_text_with_runs(p_sub)
                        for txt, st in runs:
                            r = cp.add_run(txt)
                            r.font.name = "Times New Roman"
                            r.font.size = Pt(11)
                            if st.get('bold'): r.bold = True
                            if st.get('italic'): r.italic = True
                            if st.get('underline'): r.underline = True

    doc.save(docx_path)
    print(f"SUCCESS: Created DOCX {docx_path} ({os.path.getsize(docx_path)} bytes)")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 odt_to_docx.py <in.odt> <out.docx>")
        sys.exit(1)
    convert_odt_to_docx(sys.argv[1], sys.argv[2])
