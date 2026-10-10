---
name: photo-table-to-docx
description: 把照片/截图里的表格还原成可编辑的 Word 文档（.docx）。用于 PPT 投影翻拍、教室或会议室实拍、书本/白板表格、手机截图的表格转录；也用于在没有 python-docx、pandoc、LibreOffice 的机器上直接生成可用的 Word 表格。包含坐标换算裁剪、逐格转录、遮挡标注、手写 OOXML 生成与结构校验的完整流程。
---

# 照片表格 → docx

目标：把照片里的表格**按原表结构**转录成能直接编辑的 .docx（合并单元格、表头、列宽都要对），
并且**不编造**看不清的内容。

## 流程总览

1. 环境侦察（有没有 python-docx / pandoc / LibreOffice）
2. 定位图片并用 `read` 看图（一次可读多张）
3. **坐标换算**后分块裁剪放大，逐格确认文字（最容易翻车的一步）
4. 写成 spec.json
5. 用 `scripts/table_to_docx.py` 生成 .docx 并结构校验
6. 交付 + 报告（含被遮挡/存疑处清单）

## 0. 环境侦察

```bash
python3 -c "import docx; print('python-docx ok')" 2>&1
python3 -c "import PIL; print('PIL', PIL.__version__)" 2>&1
python3 -m pip --version 2>&1 | head -1
which pandoc libreoffice soffice tesseract 2>&1
```

- 有 `python-docx` → 可以直接用它；但本 skill 的脚本**只用标准库**，通常更省事。
- 没有 `pip` 时不要死磕安装（`python3 -m ensurepip` 常需要网络）；直接走 `scripts/table_to_docx.py`。

## 1. 定位并读图

```bash
ls -la <目录>            # 找到用户 @ 的附件实际路径（常见：~/Pictures、~/Downloads）
```

用 `read` 读图，一次可读多张，省往返。`read` 会在结果里给出换算提示，例如：

```
[Image: original 4096x3072, displayed at 2000x1500. Multiply coordinates by 2.05 to map to original image.]
```

## 2. 裁剪放大（必做，且必须换算坐标）

**核心坑：`read` 返回的预览是缩小的。** 你在预览上量出的坐标是 displayed 坐标，
直接拿去找 PIL 裁剪会裁到天花板/地板。原图坐标 = displayed 坐标 × 比例因子。

用 `scripts/zoom_crop.py`（自动换算 + 放大 + 增强，并打印原图坐标便于复现）：

```bash
# 优先：直接给 displayed 坐标和 read 报告的显示尺寸，脚本自己换算
python3 scripts/zoom_crop.py photo.jpg /tmp/zoom/table.png \
    --display-box 150,340,1620,900 --display-size 2000x1500 --zoom 2 --gray --enhance

# 也可以：已经算好原图坐标
python3 scripts/zoom_crop.py photo.jpg /tmp/zoom/lower.png \
    --box 300,890,3350,1900 --zoom 2 --gray --enhance
```

实用技巧：

- `--gray --enhance`：投影幕布照片去色 + 自动对比 + 轻微锐化后，小字可读性明显提高。
- 深底白字的幻灯片：灰度化后 `ImageOps.invert`（脚本外一行代码）常更好读。
- 表格宽（宽于 3000px 原图）时**分左右两半**分别裁剪，比整体缩小看得清。
- 一定要裁剪**表格四周留白**当作尺子参考，方便后续微调坐标。
- 屏幕倾斜/透视畸变：先粗裁再用 `--rotate -1.5` 之类的旋转校正。
- 一次看不全就多裁几块：先读表头确定列边界，再按行带（每 2-4 行一条）逐条确认。

## 3. 逐格转录

- 先切出**四列各自的 x 范围**（用表头文字定位），再按行带横向读；这样不会串行。
- 读表顺序：表头 → 自上而下（或自下而上，避免被前排人头遮挡的底部行被漏掉）。
- 数字与专名（年份、法条号、书名号）**必须放大到原图分辨率逐字核对**，不要凭印象。
- 原 PPT 里的换行只是列宽所迫，不要照抄成硬换行，除非要保留版式。

### 被遮挡 / 模糊怎么办

1. **不要臆测补全**。把该格写成 `【原图被遮挡】`／`【字迹模糊】`，并在 docx 里用灰字标出
   （spec 里加 `"color": "808080"`）。
2. 允许在**回复里**给出"按常见教材/规范口径可能的补全"，并明确标注是推测、是否要写进文件由用户决定。
3. 明确告知用户哪些格不可辨认 —— 这是交付质量的一部分，而不是缺陷。
4. 同一事实若另一张照片/另一页出现，用它交叉验证。

## 4. 写 spec.json

照着 `assets/spec.example.json` 改（那就是本 skill 的来源案例：两张 PPT 投影表格）。要点：

- `columns` 是相对列宽比例，脚本自动归一到页面宽度。
- `header_row: true` → 首行加粗、浅灰底纹、跨页重复。
- 纵向合并：第一个格写 `{"text": "...", "rowspan": N}`，**后面 N-1 行的同列仍要占位**（元素值会被忽略，写 `""` 即可）。
- 多段落单元格：`"text": ["第一行", "第二行"]`。
- 页面：A4 横向 `landscape`（默认，适合 4 列中文表）；窄表用 `portrait`。
- 每个 section 之间默认分页。

## 5. 生成并校验

```bash
python3 scripts/table_to_docx.py out.docx spec.json
```

脚本自身会做结构校验并打印 `tables / rows / cells per row`，例如 `[8, 8]` 与 `[[4,4,4,4,4,4,4,4], ...]`
—— 行数、每行格数与 spec 一致才算通过。额外可手工复核：

```bash
python3 -c "
import zipfile, xml.etree.ElementTree as ET
z=zipfile.ZipFile('out.docx'); print(z.namelist())
r=ET.fromstring(z.read('word/document.xml')); q='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
print('tables', len(r.findall('.//%stbl'%q)))"
```

注意：没有 LibreOffice/pandoc 时**无法真正渲染预览**。结构校验通过 ≠ 版式完美，
所以要在回复里说明"未做渲染验证"，并请用户打开确认。

## 6. 交付

- 输出到**图片所在目录**，文件名用内容命名（如 `宪法分类表格.docx`）。
- 同时给一份"合表文件 + 每张图单独的 .docx"很省事：把 spec 复制成两份，
  每份只留一个 section，跑两次脚本即可。
- 回复里给一个小表格：文件名 → 内容；再列"已还原要点"和"被遮挡/存疑处"。

## 常见错误清单

| 症状 | 原因 |
|---|---|
| 裁出来是天花板/地板/黑板 | 用了 displayed 坐标当原图坐标 |
| 小字看不清 | 没放大（`--zoom`）或没 `--gray --enhance`；应分块裁 |
| 表格串行/错格 | 没先按列边界切；应在表头处标定每列 x 范围 |
| Word 打开报错 | XML 未转义 `& < >`（脚本已 `esc()`）、`sectPr` 不在 body 末尾 |
| 合并单元格错位 | 忘记给被合并行写占位元素；`rowspan` 与实际行数不符 |
| 文档里出现虚构内容 | 对被遮挡格做了臆测补全 |
