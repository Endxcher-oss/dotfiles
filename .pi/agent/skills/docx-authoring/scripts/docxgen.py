#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""docxgen.py —— 无依赖生成 .docx（手写 OOXML）。

适用：没有 python-docx / pandoc / LibreOffice 的机器上，把
      · 结构化文本（标题 / 段落 / 列表 / 混排表格）
      · CSV 表格
      · 照片表格转录结果（复杂合并单元格请用 table_to_docx.py）
输出为真正可编辑的 Word 文档。

用法
----
    # 1) 从 spec.json 生成
    python3 docxgen.py spec.json out.docx

    # 2) 从 CSV 生成（两列以上的表格）
    python3 docxgen.py --csv in.csv out.docx \
        --title "标题" --cols 20,80 --split-on "；" --notes "由 in.csv 生成"

    # 3) 校验生成的文档（结构 + 计数）
    python3 verify_docx.py out.docx --dump

spec.json 支持的 block 类型（blocks 数组，按顺序渲染）
------------------------------------------------------
{"type":"h1"|"h2"|"h3", "text":"..."}               标题（h1 带下划边线，均有大纲级别）
{"type":"para",  "text":"..."}                     正文段落；text 可为 ["行1","行2"]
{"type":"label", "text":"常配："}                  深蓝加粗小标签
{"type":"bullet","text":"...", "level":0}          项目符号；level 0/1/2 逐级缩进
{"type":"bullets","items":["...","..."]}           批量项目符号
{"type":"bullet","text":"want to do 想要做",
                 "split":"en_zh"}                  英文加粗 + 中文释义（自动切分，避免全角标点前多空格）
{"type":"indent","text":"...", "level":1}          左缩进正文（无符号）
{"type":"example","en":"...","zh":"..."}           英文加粗 / 中文换行（灰色）例句
{"type":"error","text":"❌ in Monday → ✅ on Monday"}  → 左侧红色、右侧绿色、箭头灰色
{"type":"table","columns":[20,80],"rows":[[...],[...]]}
                                                  单元格值可为 "文本" 或 ["多行","文本"]；首行为表头
{"type":"shade","lines":["..."],"fill":"FFF2CC"}   底纹提示块（速记 / 注意）
{"type":"pagebreak"}                               分页

文档级键：title / notes（字符串或数组，标题下灰色斜体）/ orientation（portrait|landscape）
行内标记：文本中 **加粗** 生效（para / label / bullet / 表格单元格）。
"""
import csv
import io
import json
import re
import sys
import zipfile

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CJK = re.compile(r"[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]")
PAGE_W = {"portrait": 11906, "landscape": 16838}
PAGE_H = {"portrait": 16838, "landscape": 11906}
MARGIN_LR = 1800


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def run(text, bold=False, italic=False, color=None, size=None):
    if text == "":
        return ""
    rpr = []
    if bold:
        rpr.append("<w:b/><w:bCs/>")
    if italic:
        rpr.append("<w:i/><w:iCs/>")
    if color:
        rpr.append('<w:color w:val="%s"/>' % color)
    if size:
        rpr.append('<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (size, size))
    pre = "<w:rPr>%s</w:rPr>" % "".join(rpr) if rpr else ""
    return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (pre, esc(text))


def markup(text, color=None, bold=False, italic=False):
    """行内 **加粗** 解析；bold=True 表示整段加粗。"""
    parts = str(text).split("**")
    out = []
    for i, seg in enumerate(parts):
        if seg == "":
            continue
        out.append(run(seg, bold=bold or i % 2 == 1, color=color, italic=italic))
    return "".join(out)


def en_zh(text, color=None):
    """英文加粗 + 中文释义；全角标点/连字符前不加空格。"""
    m = CJK.search(text)
    if not m:
        return run(text, bold=True, color=color)
    en, zh = text[:m.start()].rstrip(), text[m.start():]
    sep = "" if zh[:1] in "：，；、。！？）】》" or en.endswith((" ", "-", "=")) else " "
    return run(en, bold=True, color=color) + markup(sep + zh)


def para(runs_xml, style=None, num_lvl=None, before=None, after=None, ind_left=None,
         align=None, keep_next=False, shd=None, line=None, border_left=False,
         page_break_before=False):
    ppr = ["<w:pPr>"]
    if style:
        ppr.append('<w:pStyle w:val="%s"/>' % style)
    if keep_next:
        ppr.append("<w:keepNext/>")
    if page_break_before:
        ppr.append('<w:pageBreakBefore/>')
    if num_lvl is not None:
        ppr.append('<w:numPr><w:ilvl w:val="%d"/><w:numId w:val="1"/></w:numPr>' % num_lvl)
    if ind_left is not None:
        ppr.append('<w:ind w:left="%d"/>' % ind_left)
    if before is not None or after is not None or line is not None:
        ppr.append("<w:spacing%s%s%s/>" % (
            ' w:before="%d"' % before if before is not None else "",
            ' w:after="%d"' % after if after is not None else "",
            ' w:line="%d" w:lineRule="auto"' % line if line is not None else ""))
    if align:
        ppr.append('<w:jc w:val="%s"/>' % align)
    if shd:
        ppr.append('<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % shd)
    if border_left:
        ppr.append('<w:pBdr><w:left w:val="single" w:sz="18" w:space="6" w:color="8EAADB"/></w:pBdr>')
    ppr.append("</w:pPr>")
    return "<w:p>%s%s</w:p>" % ("".join(ppr), runs_xml)


def table(columns, rows, content_w, header=True, bold_first_col=False, fill="D9E2F3",
          border="8EAADB"):
    total = sum(columns)
    ws = [round(c / total * content_w) for c in columns]
    borders = ("<w:tblBorders>"
               + "".join('<w:%s w:val="single" w:sz="6" w:space="0" w:color="%s"/>' % (s, border)
                         for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
               + "</w:tblBorders>")
    out = ['<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/>' + borders
           + '<w:tblLayout w:type="fixed"/>'
           + '<w:tblCellMar><w:top w:w="57" w:type="dxa"/><w:left w:w="85" w:type="dxa"/>'
             '<w:bottom w:w="57" w:type="dxa"/><w:right w:w="85" w:type="dxa"/></w:tblCellMar>'
           + "</w:tblPr><w:tblGrid>"
           + "".join('<w:gridCol w:w="%d"/>' % x for x in ws) + "</w:tblGrid>"]
    for i, r in enumerate(rows):
        is_h = header and i == 0
        trpr = "<w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>" if is_h \
            else "<w:trPr><w:cantSplit/></w:trPr>"
        cells = []
        for j, cell in enumerate(r):
            lines = cell if isinstance(cell, list) else [cell]
            ps = []
            for k, ln in enumerate(lines):
                ps.append(para(markup(str(ln), bold=is_h or (bold_first_col and j == 0)),
                               after=30 if k == len(lines) - 1 else 20, line=260))
            cells.append('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>%s'
                         '<w:vAlign w:val="%s"/></w:tcPr>%s</w:tc>'
                         % (ws[j],
                            '<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % fill if is_h else "",
                            "center" if is_h else "top", "".join(ps)))
        out.append("<w:tr>%s%s</w:tr>" % (trpr, "".join(cells)))
    out.append("</w:tbl>")
    return "".join(out)


def render(doc, content_w):
    """doc -> body XML 列表。"""
    body = []
    if doc.get("title"):
        body.append(para(run(doc["title"], bold=True, color="1F3864", size=32),
                         style="Title1", align="center", after=200))
    notes = doc.get("notes") or []
    if isinstance(notes, str):
        notes = [notes]
    for n in notes:
        body.append(para(markup(n, color="595959", italic=True), after=120))

    for b in doc.get("blocks", []):
        k = b.get("type", "para")
        if k == "h1":
            body.append(para(markup(b["text"], bold=True, color="1F3864"),
                             style="Heading1", before=360, after=160, keep_next=True))
        elif k == "h2":
            body.append(para(markup(b["text"], bold=True, color="2E5496"),
                             style="Heading2", before=240, after=120, keep_next=True))
        elif k == "h3":
            body.append(para(markup(b["text"], bold=True, color="2E5496"),
                             style="Heading3", before=200, after=100, keep_next=True))
        elif k == "label":
            body.append(para(markup(b["text"], bold=True, color="2E5496"),
                             before=140, after=60, keep_next=True))
        elif k == "para":
            lines = b["text"] if isinstance(b["text"], list) else [b["text"]]
            for ln in lines:
                body.append(para(markup(ln), after=100))
        elif k == "bullet":
            txt = b["text"]
            runs = en_zh(txt) if b.get("split") == "en_zh" else markup(txt)
            body.append(para(runs, num_lvl=int(b.get("level", 0)),
                             after=40))
        elif k == "bullets":
            for it in b["items"]:
                split = "en_zh" if b.get("split") == "en_zh" else None
                runs = en_zh(it) if split else markup(it)
                body.append(para(runs, num_lvl=int(b.get("level", 0)), after=40))
        elif k == "indent":
            body.append(para(markup(b["text"], italic=b.get("italic", False)),
                             ind_left=720 + 360 * int(b.get("level", 1)), after=60))
        elif k == "example":
            body.append(para(run(b["en"], bold=True) + "<w:br/>"
                             + markup(b.get("zh", ""), color="404040"),
                             num_lvl=int(b.get("level", 0)), after=80))
        elif k == "error":
            t = b["text"]
            if "→" in t:
                left, right = t.split("→", 1)
                runs = markup(left.rstrip(), color="C00000") + run(" → ", color="808080") \
                    + markup(right.lstrip(), color="2F7D32")
            else:
                runs = markup(t, color="C00000")
            body.append(para(runs, num_lvl=int(b.get("level", 0)), after=40))
        elif k == "table":
            body.append(table(b["columns"], b["rows"], content_w,
                              header=b.get("header", True),
                              bold_first_col=b.get("bold_first_col", False),
                              fill=b.get("fill", "D9E2F3")))
        elif k == "shade":
            lines = b["lines"]
            for i, ln in enumerate(lines):
                body.append(para(markup(ln, bold=True), ind_left=200,
                                 before=60 if i == 0 else 0,
                                 after=60 if i == len(lines) - 1 else 0,
                                 shd=b.get("fill", "FFF2CC"), line=280))
        elif k == "pagebreak":
            body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        elif k == "gap":
            body.append(para("", after=0))
        else:
            raise ValueError("unknown block type: %r" % k)
    return body


def build(doc, out_path, orientation=None):
    ori = orientation or doc.get("orientation", "portrait")
    pw, ph = PAGE_W[ori], PAGE_H[ori]
    content_w = pw - 2 * MARGIN_LR
    body = render(doc, content_w)
    sect = ('<w:sectPr><w:pgSz w:w="%d" w:h="%d"%s/>'
            '<w:pgMar w:top="1440" w:right="%d" w:bottom="1440" w:left="%d" '
            'w:header="851" w:footer="992" w:gutter="0"/>'
            '<w:cols w:space="425"/><w:docGrid w:linePitch="312"/></w:sectPr>'
            % (pw, ph, ' w:orient="landscape"' if ori == "landscape" else "",
               MARGIN_LR, MARGIN_LR))
    title = doc.get("title", "document")
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<w:document xmlns:w="%s"><w:body>%s%s</w:body></w:document>'
                % (W, "".join(body), sect))
    return write_package(out_path, document, title)


def write_package(out_path, document, title):
    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="%s">
<w:docDefaults><w:rPrDefault><w:rPr>
<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="宋体" w:cs="Calibri"/>
<w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:line="300" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:styleId="Title1"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:spacing w:before="240" w:after="200"/></w:pPr>
<w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="黑体"/><w:b/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:outlineLvl w:val="0"/><w:spacing w:before="360" w:after="160"/>
<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="2" w:color="B4C7E7"/></w:pBdr></w:pPr>
<w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="黑体"/><w:b/><w:color w:val="1F3864"/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:outlineLvl w:val="1"/><w:spacing w:before="240" w:after="120"/></w:pPr>
<w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="黑体"/><w:b/><w:color w:val="2E5496"/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:outlineLvl w:val="2"/><w:spacing w:before="200" w:after="100"/></w:pPr>
<w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="黑体"/><w:b/><w:color w:val="2E5496"/><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr></w:style>
</w:styles>''' % W

    lvls = []
    for i in range(9):
        ch, font = ("\u2022", "Symbol") if i % 2 == 0 else ("o", "Courier New")
        lvls.append('<w:lvl w:ilvl="%d"><w:start w:val="1"/><w:numFmt w:val="bullet"/>'
                    '<w:lvlText w:val="%s"/><w:lvlJc w:val="left"/>'
                    '<w:pPr><w:ind w:left="%d" w:hanging="360"/></w:pPr>'
                    '<w:rPr><w:rFonts w:ascii="%s" w:hAnsi="%s" w:hint="default"/></w:rPr>'
                    '</w:lvl>' % (i, ch, 720 + i * 360, font, font))
    numbering = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                 '<w:numbering xmlns:w="%s"><w:abstractNum w:abstractNumId="0">'
                 '<w:multiLevelType w:val="hybridMultilevel"/>%s</w:abstractNum>'
                 '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>'
                 % (W, "".join(lvls)))
    settings = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<w:settings xmlns:w="%s"><w:zoom w:percent="100"/>'
                '<w:defaultTabStop w:val="420"/><w:compat/></w:settings>' % W)
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:title>%s</dc:title><cp:lastModifiedBy>pi</cp:lastModifiedBy>'
            '<dcterms:created xsi:type="dcterms:W3CDTF">2024-01-01T00:00:00Z</dcterms:created>'
            '</cp:coreProperties>' % esc(title))
    app = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
           'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
           '<Application>pi-ooxml</Application></Properties>')
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>'''
    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''
    doc_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
</Relationships>'''
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("word/document.xml", document)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        z.writestr("word/styles.xml", styles)
        z.writestr("word/numbering.xml", numbering)
        z.writestr("word/settings.xml", settings)
        z.writestr("docProps/core.xml", core)
        z.writestr("docProps/app.xml", app)
    return out_path


def read_csv(path):
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with io.open(path, encoding=enc) as f:
                return list(csv.reader(f))
        except (UnicodeDecodeError, LookupError):
            continue
    raise SystemExit("无法解码 CSV: %s" % path)


def csv_to_doc(csv_path, title=None, columns=None, split_on=None, split_cols="rest",
               notes=None, header=True):
    rows = read_csv(csv_path)
    rows = [r for r in rows if any(c.strip() for c in r)]  # 丢空行
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    if split_on:
        idx = range(1, ncol) if split_cols == "rest" else \
            [int(x) - 1 for x in str(split_cols).split(",")]
        rows = [[c if (i == 0 and header) or j not in idx
                 else [x for x in re.split(split_on, c) if x.strip()]
                 for j, c in enumerate(r)] for i, r in enumerate(rows)]
    if not columns:
        first = max(len(str(c[0]) if isinstance(c[0], str) else "") for c in rows) + 4
        columns = [max(14, min(34, first)), 0]
    doc = {"title": title or csv_path.split("/")[-1].rsplit(".", 1)[0],
           "orientation": "portrait",
           "blocks": [{"type": "table", "columns": columns, "rows": rows,
                       "header": header, "bold_first_col": True}]}
    if notes:
        doc["notes"] = notes if isinstance(notes, list) else [notes]
    return doc


def main(argv):
    if argv and argv[0] == "--csv":
        csv_path, out = argv[1], argv[2]
        opts = argv[3:]
        kw = {}
        if "--title" in opts:
            kw["title"] = opts[opts.index("--title") + 1]
        if "--cols" in opts:
            kw["columns"] = [float(x) for x in opts[opts.index("--cols") + 1].split(",")]
        if "--split-on" in opts:
            kw["split_on"] = opts[opts.index("--split-on") + 1]
        if "--split-cols" in opts:
            kw["split_cols"] = opts[opts.index("--split-cols") + 1]
        if "--notes" in opts:
            kw["notes"] = opts[opts.index("--notes") + 1]
        if "--no-header" in opts:
            kw["header"] = False
        doc = csv_to_doc(csv_path, **kw)
        print("csv rows: %d cols: %d" % (len(doc["blocks"][0]["rows"]),
                                         len(doc["blocks"][0]["rows"][0])))
    else:
        spec, out = argv[0], argv[1]
        doc = json.load(io.open(spec, encoding="utf-8"))
    print("written:", build(doc, out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
