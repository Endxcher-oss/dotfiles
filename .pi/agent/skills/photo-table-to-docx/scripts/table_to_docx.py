#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""table_to_docx.py — build a Word .docx (OOXML) from a JSON table spec.

Standard library only: works where python-docx, pandoc and LibreOffice are all
absent (the common case on a minimal Linux box).

Usage:
    python3 table_to_docx.py out.docx spec.json
    python3 table_to_docx.py out.docx -        # spec on stdin

Spec (JSON, UTF-8):

{
  "orientation": "landscape",              // "landscape" (default) | "portrait"
  "title": "宪法分类",                      // optional, large centered line
  "notes": ["说明：原图被遮挡处未作补全。"],   // optional, small gray lines at the end
  "page_break_between_sections": true,     // default true
  "sections": [
    {
      "heading": "（一）形式分类",            // optional centered heading
      "columns": [0.20, 0.12, 0.33, 0.35], // relative column widths (normalized)
      "header_row": true,                  // default false: bold + shaded + repeat
      "rows": [
        ["分类标准", "类型", "特征", "典型国家"],
        ["1. 是否宪法典（布赖斯）", "成文", "具有统一法典形式", "1787 年美宪…"],
        [{"text": "3. 制定机关", "rowspan": 3}, "钦定", "由君主…", "1814 法宪…"],
        ["", "协定", "君民协商制定", "英国 1215《自由大宪章》"],
        ["", "民定", "【原图被遮挡】", "【原图被遮挡】"]
      ]
    }
  ]
}

Cell forms
    "text"                      -> plain string
    {"text": "...",             -> full form; every key is optional except text
     "rowspan": 3,              // vertical merge starting here; the following
                                // rows must still carry a placeholder element
                                // for this column (its value is ignored)
     "align": "center",         // left (default) | center | right
     "bold": true,
     "italic": true,
     "color": "808080",         // character color, hex RGB
     "shade": "DFEDE7"}         // cell fill, hex RGB

Notes
    * Every row of a section must contain the same number of elements as the
      header row; merged positions are simply placeholders.
    * Text inside a cell is wrapped by Word; write multi-line content as a list
      of strings under "text" to force paragraph breaks:
      {"text": ["line one", "line two"]}
"""

import json
import sys
import zipfile

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = ('xmlns:w="%s" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"' % W)

PAGE = {  # page size in twips (A4)
    'landscape': (16838, 11906),
    'portrait': (11906, 16838),
}
MARGIN = 1134
HEADER_FILL = 'DFEDE7'
FONT_SZ = 21        # 10.5 pt body
HEAD_SZ = 32        # 16 pt section heading
TITLE_SZ = 36       # 18 pt document title
NOTE_SZ = 18        # 9 pt note

CONTENT_TYPES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>'''

RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

DOC_RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles ''' + NS + '''>
<w:docDefaults><w:rPrDefault><w:rPr>
<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="\u5b8b\u4f53" w:cs="Times New Roman"/>
<w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:line="300" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
</w:styles>'''

BORDERS = ('<w:tblBorders>'
           + ''.join('<w:%s w:val="single" w:sz="6" w:space="0" w:color="000000"/>' % s
                     for s in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'))
           + '</w:tblBorders>')


def esc(t):
    return (t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def run_xml(text, bold=False, italic=False, sz=FONT_SZ, color=None):
    rpr = ['<w:rPr>']
    if bold:
        rpr.append('<w:b/>')
    if italic:
        rpr.append('<w:i/>')
    if color:
        rpr.append('<w:color w:val="%s"/>' % color)
    rpr.append('<w:sz w:val="%d"/><w:szCs w:val="%d"/></w:rPr>' % (sz, sz))
    return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (''.join(rpr), esc(text))


def para_xml(text='', bold=False, italic=False, sz=FONT_SZ, color=None, align=None):
    ppr = '<w:pPr>'
    if align:
        ppr += '<w:jc w:val="%s"/>' % align
    ppr += '</w:pPr>'
    return '<w:p>%s%s</w:p>' % (ppr, run_xml(text, bold, italic, sz, color))


def norm_cell(item):
    """normalize a spec cell into a dict"""
    if isinstance(item, dict):
        c = dict(item)
    else:
        c = {'text': '' if item is None else item}
    c.setdefault('rowspan', 1)
    c.setdefault('align', None)
    c.setdefault('bold', False)
    c.setdefault('italic', False)
    c.setdefault('color', None)
    c.setdefault('shade', None)
    return c


def tc_xml(cell_dict, width, vmerge=None):
    """vmerge: None | 'restart' | 'continue'"""
    texts = cell_dict.get('text', '')
    if not isinstance(texts, (list, tuple)):
        texts = [texts]
    if vmerge == 'continue':
        texts, cell_dict = [], dict(cell_dict, bold=False, color=None)

    tcpr = ['<w:tcPr><w:tcW w:w="%d" w:type="dxa"/>' % width]
    if cell_dict.get('shade'):
        tcpr.append('<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % cell_dict['shade'])
    if vmerge == 'restart':
        tcpr.append('<w:vMerge w:val="restart"/>')
    elif vmerge == 'continue':
        tcpr.append('<w:vMerge/>')
    tcpr.append('<w:vAlign w:val="center"/></w:tcPr>')

    body = ''.join(
        para_xml(t, bold=cell_dict.get('bold'), italic=cell_dict.get('italic'),
                 color=cell_dict.get('color'), align=cell_dict.get('align'))
        for t in texts)
    if not body:
        body = '<w:p/>'
    return '<w:tc>%s%s</w:tc>' % (''.join(tcpr), body)


def table_xml(section, text_width):
    rows = section['rows']
    ncols = max(len(r) for r in rows)
    weights = section.get('columns') or [1.0] * ncols
    total = float(sum(weights))
    widths = [int(round(text_width * w / total)) for w in weights]
    header = bool(section.get('header_row'))

    out = ['<w:tbl><w:tblPr><w:tblW w:w="%d" w:type="dxa"/><w:jc w:val="center"/>'
           '<w:tblLayout w:type="fixed"/>' % sum(widths), BORDERS,
           '<w:tblCellMar><w:top w:w="60" w:type="dxa"/><w:left w:w="100" w:type="dxa"/>'
           '<w:bottom w:w="60" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar>',
           '</w:tblPr>',
           '<w:tblGrid>%s</w:tblGrid>'
           % ''.join('<w:gridCol w:w="%d"/>' % w for w in widths)]

    occupied = {}   # row index -> set of column indexes continued from above
    for ri, row in enumerate(rows):
        cells = [norm_cell(c) for c in row] + [norm_cell('')] * (ncols - len(row))
        trpr = '<w:trPr><w:tblHeader/></w:trPr>' if (header and ri == 0) else ''
        out.append('<w:tr>%s' % trpr)
        for ci in range(ncols):
            if ci in occupied.get(ri, ()):
                out.append(tc_xml(cells[ci], widths[ci], vmerge='continue'))
                continue
            c = cells[ci]
            if header and ri == 0:
                c = dict(c, bold=True, shade=c.get('shade') or HEADER_FILL, align='center')
            span = max(1, int(c.get('rowspan') or 1))
            vmerge = 'restart' if span > 1 else None
            for k in range(1, span):
                occupied.setdefault(ri + k, set()).add(ci)
            out.append(tc_xml(c, widths[ci], vmerge=vmerge))
        out.append('</w:tr>')
    out.append('</w:tbl>')
    return ''.join(out)


def document_xml(spec):
    orientation = spec.get('orientation', 'landscape')
    pw, ph = PAGE.get(orientation, PAGE['landscape'])
    text_width = pw - 2 * MARGIN
    body = []
    if spec.get('title'):
        body.append(para_xml(spec['title'], bold=True, sz=TITLE_SZ, align='center'))
    for i, sec in enumerate(spec.get('sections', [])):
        if i and spec.get('page_break_between_sections', True):
            body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        if sec.get('heading'):
            body.append(para_xml(sec['heading'], bold=True, sz=HEAD_SZ, align='center'))
        body.append(table_xml(sec, text_width))
    for note in spec.get('notes', []):
        body.append(para_xml(note, sz=NOTE_SZ, color='808080'))
    sect = ('<w:sectPr><w:pgSz w:w="%d" w:h="%d"%s/>'
            '<w:pgMar w:top="%d" w:right="%d" w:bottom="%d" w:left="%d" '
            'w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
            % (pw, ph, ' w:orient="landscape"' if orientation == 'landscape' else '',
               MARGIN, MARGIN, MARGIN, MARGIN))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document ' + NS + '><w:body>' + ''.join(body) + sect
            + '</w:body></w:document>')


def write_docx(path, spec):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', CONTENT_TYPES)
        z.writestr('_rels/.rels', RELS)
        z.writestr('word/_rels/document.xml.rels', DOC_RELS)
        z.writestr('word/styles.xml', STYLES)
        z.writestr('word/document.xml', document_xml(spec))
    return path


def verify(path):
    """structural check: package parts present, XML parses, table geometry."""
    import xml.etree.ElementTree as ET
    report = {}
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        root = ET.fromstring(z.read('word/document.xml'))
    q = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    tables = root.findall('.//%stbl' % q)
    report['parts'] = names
    report['tables'] = len(tables)
    report['rows'] = [len(t.findall('%str' % q)) for t in tables]
    report['cells_per_row'] = [[len(r.findall('%stc' % q)) for r in t.findall('%str' % q)]
                               for t in tables]
    return report


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    out, src = argv[0], argv[1]
    raw = sys.stdin.read() if src == '-' else open(src, encoding='utf-8').read()
    spec = json.loads(raw)
    write_docx(out, spec)
    rep = verify(out)
    print('written: %s' % out)
    print('tables: %d  rows/table: %s' % (rep['tables'], rep['rows']))
    print('cells per row: %s' % rep['cells_per_row'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
