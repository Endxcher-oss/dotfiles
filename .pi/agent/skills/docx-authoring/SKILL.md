---
name: docx-authoring
description: 在没有 python-docx / pandoc / LibreOffice 的机器上直接手写 OOXML 生成可用的 Word 文档：(1) 把照片/截图里的表格按原结构转录成 .docx（PPT 投影翻拍、教室或会议室实拍、书本/白板表格、手机截图）；(2) 把 CSV 转成表格 docx；(3) 把结构化文本（标题、列表、混合表格、速记框、错例对照）生成分页 .docx。含坐标换算裁剪、逐格转录、遮挡标注、block 规格、行内加粗、结构校验与计数对账的完整流程。
---

# docx 生成与表格还原（无 python-docx / pandoc / LibreOffice）

目标：在本机**没有** docx 工具链的情况下，产出能直接编辑、Word 能正常打开的 `.docx`：
- **路线 A**：照片/截图里的表格 → 按原表结构转录（合并单元格、表头、列宽、遮挡标注）
- **路线 B**：CSV → 表格 docx；结构化文本（标题 / 列表 / 混排表格）→ 分页 docx

铁律：**不编造看不清的内容**；**交付前必须跑结构校验**；**条目数必须与源文对账**。

## 0. 环境侦察与路线选择

```bash
python3 -c "import docx; print('python-docx ok')" 2>&1
which pandoc libreoffice soffice tesseract 2>&1
python3 -c "import PIL; print('PIL', PIL.__version__)" 2>&1
```

| 输入 | 路线 | 脚本 |
|---|---|---|
| 照片/截图里的表格（有合并单元格） | A | `scripts/zoom_crop.py` → `scripts/table_to_docx.py` |
| CSV（二维表，无合并） | B | `scripts/docxgen.py --csv` |
| 粘贴来的结构化文本（章节 + 列表 + 表格混排） | B | `scripts/docxgen.py spec.json` |

有 `python-docx` 时也建议用本 skill 的脚本（**只用标准库**，无版本/依赖问题）。
没有 `pip` 时不要死磕安装（`python3 -m ensurepip` 常需网络）；直接用手写 OOXML 路线。

---

# 路线 A：照片表格 → docx

## A1. 定位并读图

```bash
ls -la <目录>            # 找到用户 @ 的附件实际路径（常见：~/Pictures、~/Downloads）
```

用 `read` 读图，一次可读多张，省往返。`read` 会在结果里给出换算提示，例如：

```
[Image: original 4096x3072, displayed at 2000x1500. Multiply coordinates by 2.05 to map to original image.]
```

## A2. 裁剪放大（必做，且必须换算坐标）

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

## A3. 逐格转录

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

## A4. 写 spec.json（表格版）

照着 `assets/spec.example.json` 改（那就是本 skill 的来源案例：两张 PPT 投影表格）。要点：

- `columns` 是相对列宽比例，脚本自动归一到页面宽度。
- `header_row: true` → 首行加粗、浅灰底纹、跨页重复。
- 纵向合并：第一个格写 `{"text": "...", "rowspan": N}`，**后面 N-1 行的同列仍要占位**（元素值会被忽略，写 `""` 即可）。
- 多段落单元格：`"text": ["第一行", "第二行"]`。
- 页面：A4 横向 `landscape`（默认，适合 4 列中文表）；窄表用 `portrait`。
- 每个 section 之间默认分页。

## A5. 生成并校验

```bash
python3 scripts/table_to_docx.py out.docx spec.json
```

脚本自身会做结构校验并打印 `tables / rows / cells per row`，例如 `[8, 8]` 与 `[[4,4,4,4,4,4,4,4], ...]`
—— 行数、每行格数与 spec 一致才算通过。再用 `verify_docx.py` 复核（见下文"通用校验"）。

---

# 路线 B：CSV / 结构化文本 → docx

## B1. CSV → 表格 docx

```bash
python3 scripts/docxgen.py --csv in.csv out.docx \
    --title "学历的中英对照" --cols 18,82                       # 列宽为相对比例
python3 scripts/docxgen.py --csv 招待.csv out.docx \
    --title "招待客人的几种译法总结" --cols 20,80 --split-on "；"   # 长列表按 ；拆成逐条独立段落
python3 scripts/docxgen.py --csv in.csv out.docx --notes "由 in.csv 生成" --no-header
```

- 编码自动尝试 `utf-8-sig → utf-8 → gb18030`；自动丢弃全空行、补齐列数。
- 表头行（默认首行）加粗 + 浅蓝底纹 + 跨页重复；首列加粗。
- `--split-on "；"`：只有当某个单元格是"用分号连写的长串"时才用；**拆出来的条数要在回复里报数**
  （如 7/9/6/9/8 条），方便用户核对。`--split-cols 2,3` 可限定列（默认 `rest` = 除首列外全部）。
- 输出路径按上面的约定放回**源文件所在目录**。

## B2. 结构化文本 → docx

把用户给的成稿文本（如"英语表达总结""知识点清单"）变成 `spec.json`，再：

```bash
python3 scripts/docxgen.py spec.json out.docx
```

`assets/spec.doc.example.json` 覆盖了全部 block 类型，直接复制改造。block 一览：

| type | 字段 | 效果 |
|---|---|---|
| `h1` / `h2` / `h3` | `text` | 一/二/三级标题；`h1` 带浅蓝下划边线；均有大纲级别（Word 导航窗格可见） |
| `para` | `text`（字符串或字符串数组） | 正文段落；数组 = 多段 |
| `label` | `text` | 深蓝加粗小标签（如 `常配：`、`例：`、`英式：`、`口诀：`） |
| `bullet` | `text`、`level`、`split` | 项目符号；`level` 0/1/2 逐级缩进（符号 • / o 交替）；`split:"en_zh"` = 英文加粗 + 中文释义 |
| `bullets` | `items`、`level`、`split` | 批量项目符号 |
| `indent` | `text`、`level` | 左缩进正文（无符号），用于缩写表、读法、例句 |
| `example` | `en`、`zh` | 英文加粗 + 换行 + 灰色中文（对比例句专用） |
| `error` | `text`（含 `→`） | 箭头左红色、右绿色（`❌ … → ✅ …` 常见错误） |
| `table` | `columns`、`rows` | 真表格；单元格可写 `"文本"` 或 `["多行","文本"]`；首行表头 |
| `shade` | `lines`、`fill` | 底纹提示块（`FFF2CC` 浅黄 = 速记 / 注意） |
| `pagebreak` / `gap` | — | 分页 / 占位空段 |

文档级键：`title`、`notes`（字符串或数组 → 标题下灰色斜体，适合"来源/说明"）、`orientation`。
行内标记：任意文本里 `**加粗**` 生效（`para`/`label`/`bullet`/表格单元格）。

排版映射经验（用户认可的做法）：

- 词组条目 → `bullet` + `split:"en_zh"`（英文部分加粗，中文释义常规）。
- "英式：日 + 月 + 年" 这类引导语 → `label`；下面的 5 May 2024 → `indent`。
- 原稿里的 `·` 子条目 → `bullet` + `level:1`，不要用空格硬缩进。
- 三列以上的对照表（介词用法、语境译法）→ `table`，**不要**塞进项目符号。
- 文末"最简速记 / 注意" → `shade`。
- **不要**把源文的 `---` 分隔线转成横线字符；用 `h1` 的边线或 `pagebreak` 表达层级。

---

# 通用：生成后必须校验

```bash
python3 scripts/verify_docx.py out.docx --dump
python3 scripts/verify_docx.py out.docx --expect-bullets 96 --expect-tables 1 --expect-paragraphs 255
```

检查：zip 完整性、每个 XML/rels 部件可解析、`sectPr` 在 `body` 末尾、段落/项目符号/表格/每行单元格数，
并在 `--dump` 时打印全文供人工逐条核对。**`--expect-*` 不匹配时 exit 1，此时不要交付。**

**计数对账（本 skill 最重要的质检动作）**：把源文的条目数算出来，与 docx 的计数比对。
例：主动 44 条 + 被动 49 条 + 例句 7 条 = 100 个项目符号，`verify_docx.py` 必须报 `bullets: 100`。
数字不吻合 = 有内容漏抄或重复，回去查，不要靠肉眼看。

```bash
python3 -c "
import zipfile, xml.etree.ElementTree as ET
z=zipfile.ZipFile('out.docx'); print(z.namelist())
r=ET.fromstring(z.read('word/document.xml')); q='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
print('tables', len(r.findall('.//%stbl'%q)))"
```

注意：没有 LibreOffice/pandoc 时**无法真正渲染预览**。结构校验通过 ≠ 版式完美，
所以要在回复里说明"未做渲染验证"，并请用户打开确认。

---

# 交付

- 输出到**源文件所在目录**（图片/CSV 旁边），文件名用内容命名（如 `宪法分类表格.docx`、
  `学历对照表.docx`、`英语日期与时间表达系统整理.docx`）。
- 回复里给一个小表格：文件名 → 内容；再列"已还原要点"和"被遮挡/存疑处"，并附校验数字
  （段落 / 项目符号 / 表格行×列）。
- 需要多份产出时给"合表文件 + 每张图单独 .docx"很省事：把 spec 复制成两份，
  每份只留一个 section（表格版）或只留相关 blocks（文本版），跑两次脚本即可。
- 改了源文结构（如把 `；` 长串拆成逐条）之类的**非等价改动必须显式说明**，并给出"改回去"的办法。

# 常见错误清单

| 症状 | 原因 |
|---|---|
| 裁出来是天花板/地板/黑板 | 用了 displayed 坐标当原图坐标 |
| 小字看不清 | 没放大（`--zoom`）或没 `--gray --enhance`；应分块裁 |
| 表格串行/错格 | 没先按列边界切；应在表头处标定每列 x 范围 |
| Word 打开报错 | XML 未转义 `& < >`（脚本已 `esc()`）、`sectPr` 不在 body 末尾 |
| 合并单元格错位 | 忘记给被合并行写占位元素；`rowspan` 与实际行数不符 |
| 文档里出现虚构内容 | 对被遮挡格做了臆测补全 |
| 中文释义前多出空格 | `en_zh` 切分处未判全角标点：`1999 ：nineteen` → 应 `1999：nineteen`（脚本已处理 `：，；、。！？）】》` 与 `- =`） |
| 箭头挤在一起 | `❌ in Monday→✅` → 应 `❌ in Monday → ✅ on Monday`（左右各留一个空格，箭头灰色） |
| ❌/✅ 显示成方块 | 依赖系统 Emoji 字体：Windows/macOS 正常，个别 Linux 可能缺字形 —— 交付时提示用户，必要时改成 `(×)` / `(√)` |
| 条目数对不上 | 没做计数对账；漏抄/重复，用 `--expect-bullets` 卡住 |
| 长列表在某格中间折行难看 | CSV 单元格用 `；` 连写；改用 `--split-on "；"` 拆成逐条段落 |
| 表格被拆到两页或表头丢失 | 表格版依赖 `header_row: true`；文本版表格已默认 `tblHeader` + `cantSplit` |
