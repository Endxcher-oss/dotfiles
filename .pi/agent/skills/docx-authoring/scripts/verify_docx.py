#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_docx.py —— 生成后的结构校验（无渲染环境时的唯一质量闸门）。

用法:
    python3 verify_docx.py out.docx                # 结构 + 计数
    python3 verify_docx.py out.docx --dump         # 再打印全部文本（逐段落一行）
    python3 verify_docx.py out.docx --expect-bullets 96 --expect-tables 1 \
            --expect-paragraphs 255                # 与源文条目数对账，不符则 exit 1

检查项:
    1. zip 完整性（testzip）
    2. 每个 XML / rels 部件可解析（ElementTree）
    3. sectPr 位于 body 末尾、<w:p> 与 <w:tbl> 平衡（Word 打开报错的两大原因）
    4. 段落 / 项目符号 / 表格 / 每行单元格数
    5. （--dump）全文文本，用于人工逐条核对
退出码非 0 = 校验失败，不要交付。
"""
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

Q = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def main(argv):
    path = argv[0]
    dump = "--dump" in argv
    exp = {}
    for k in ("paragraphs", "bullets", "tables", "rows"):
        flag = "--expect-" + k
        if flag in argv:
            exp[k] = int(argv[argv.index(flag) + 1])

    z = zipfile.ZipFile(path)
    bad = z.testzip()
    print("zip ok:", bad is None, "| parts:", len(z.namelist()))
    for n in z.namelist():
        if n.endswith((".xml", ".rels")):
            try:
                ET.fromstring(z.read(n))
            except ET.ParseError as e:
                raise SystemExit("XML 解析失败 %s: %s" % (n, e))
    print("all xml parts parse: ok")

    raw = z.read("word/document.xml").decode("utf-8")
    r = ET.fromstring(z.read("word/document.xml"))
    body = r.find(Q + "body")
    ok_sect = body[-1].tag == Q + "sectPr"
    print("sectPr last:", ok_sect)
    if not ok_sect:
        raise SystemExit("sectPr 不在 body 末尾 —— Word 会报错")

    paras = r.findall(".//" + Q + "p")
    tbls = r.findall(".//" + Q + "tbl")
    bullets = r.findall(".//" + Q + "numPr")
    counts = {
        "paragraphs": len(paras),
        "bullets": len(bullets),
        "tables": len(tbls),
        "rows": sum(len(t.findall(Q + "tr")) for t in tbls),
    }
    print("counts:", counts)
    for t in tbls:
        cells = sorted({len(tr.findall(Q + "tc")) for tr in t.findall(Q + "tr")})
        print("  table: rows=%d, cells-per-row=%s" % (len(t.findall(Q + "tr")), cells))

    fail = []
    for k, v in exp.items():
        if counts.get(k) != v:
            fail.append("%s: got %s want %s" % (k, counts.get(k), v))
    if fail:
        raise SystemExit("计数不符 -> " + "; ".join(fail))
    if exp:
        print("expected counts: ok")

    if dump:
        print("---- text ----")
        for p in paras:
            s = "".join(n.text or "" for n in p.iter(Q + "t"))
            tag = "[*] " if p.findall(".//" + Q + "numPr") else ""
            if s.strip():
                print(tag + s)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
