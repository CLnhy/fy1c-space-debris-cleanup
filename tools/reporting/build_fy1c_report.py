import json
import os
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "outputs" / "fy1c_cleanup_report"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT = OUT_DIR / "风云一号C碎片典型清理任务说明.docx"
FIGURE = OUT_DIR / "orbit_figure.png"
DATA = ROOT / "public_debris_calculation" / "screening_result.json"

with DATA.open("r", encoding="utf-8") as f:
    result = json.load(f)


# compact_reference_guide preset tokens
PAGE_W = Inches(8.5)
PAGE_H = Inches(11)
MARGIN = Inches(1)
HEADER_DIST = Inches(0.492)
FOOTER_DIST = Inches(0.492)
TABLE_WIDTH_DXA = 9360
TABLE_INDENT_DXA = 120
CELL_MARGINS = {"top": 80, "bottom": 80, "start": 120, "end": 120}

BLUE = "2E74B5"
DARK_BLUE = "1F4D78"
INK = "0B2545"
NAVY = "203748"
MUTED = "5B6573"
GOLD = "9A7410"
HEADER_FILL = "E8EEF5"
LIGHT_FILL = "F2F4F7"
CALLOUT_FILL = "F4F6F9"
GREEN_FILL = "E7F1E3"
YELLOW_FILL = "FFF4CC"
BORDER = "B8C4CE"
WHITE = "FFFFFF"
BLACK = "1F2937"


def set_run_font(run, name="Calibri", east_asia="Microsoft YaHei", size=None,
                 color=None, bold=None, italic=None):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.rFonts
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)
    rfonts.set(qn("w:eastAsia"), east_asia)
    if size is not None:
        run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic


def set_cell_margins(cell, margins=CELL_MARGINS):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for edge, value in margins.items():
        node = tc_mar.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_cell_width(cell, width_dxa):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.first_child_found_in("w:tcW")
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(width_dxa))
    tc_w.set(qn("w:type"), "dxa")


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)
    shd.set(qn("w:val"), "clear")


def set_table_borders(table, color=BORDER, size="6"):
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = borders.find(qn(f"w:{edge}"))
        if tag is None:
            tag = OxmlElement(f"w:{edge}")
            borders.append(tag)
        tag.set(qn("w:val"), "single")
        tag.set(qn("w:sz"), size)
        tag.set(qn("w:space"), "0")
        tag.set(qn("w:color"), color)


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = tr_pr.find(qn("w:tblHeader"))
    if tbl_header is None:
        tbl_header = OxmlElement("w:tblHeader")
        tr_pr.append(tbl_header)
    tbl_header.set(qn("w:val"), "true")


def set_table_geometry(table, widths):
    if sum(widths) != TABLE_WIDTH_DXA:
        raise ValueError(f"Table widths sum to {sum(widths)}, expected {TABLE_WIDTH_DXA}")
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(TABLE_WIDTH_DXA))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), str(TABLE_INDENT_DXA))
    tbl_ind.set(qn("w:type"), "dxa")
    layout = tbl_pr.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        tbl_pr.append(layout)
    layout.set(qn("w:type"), "fixed")

    tbl_grid = table._tbl.tblGrid
    for child in list(tbl_grid):
        tbl_grid.remove(child)
    for width in widths:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        tbl_grid.append(col)

    # Keep each logical row on one page.  This avoids orphaned cell fragments
    # such as a single trailing word at the top of the following page.
    for row in table.rows:
        tr_pr = row._tr.get_or_add_trPr()
        cant_split = tr_pr.find(qn("w:cantSplit"))
        if cant_split is None:
            cant_split = OxmlElement("w:cantSplit")
            tr_pr.append(cant_split)
        cant_split.set(qn("w:val"), "true")
    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            set_cell_width(cell, widths[idx])
            set_cell_margins(cell)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    set_table_borders(table)


def set_cell_text(cell, text, bold=False, color=BLACK, size=9.3,
                  align=WD_ALIGN_PARAGRAPH.LEFT, italic=False):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = align
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.08
    p.paragraph_format.keep_together = True
    run = p.add_run(str(text))
    set_run_font(run, size=size, color=color, bold=bold, italic=italic)


def add_table(doc, headers, rows, widths, aligns=None, font_size=9.3,
              header_fill=HEADER_FILL):
    table = doc.add_table(rows=1, cols=len(headers))
    set_table_geometry(table, widths)
    hdr = table.rows[0]
    set_repeat_table_header(hdr)
    for idx, text in enumerate(headers):
        set_cell_shading(hdr.cells[idx], header_fill)
        set_cell_text(hdr.cells[idx], text, bold=True, color=INK, size=9.2,
                      align=WD_ALIGN_PARAGRAPH.CENTER)
    for row_values in rows:
        row = table.add_row()
        for idx, value in enumerate(row_values):
            align = aligns[idx] if aligns else WD_ALIGN_PARAGRAPH.LEFT
            set_cell_text(row.cells[idx], value, size=font_size, align=align)
    set_table_geometry(table, widths)
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    return table


def add_source_note(doc, text):
    p = doc.add_paragraph(style="Source Note")
    p.add_run(text)
    return p


def add_label_para(doc, label, text, fill=None):
    if fill:
        table = doc.add_table(rows=1, cols=1)
        set_table_geometry(table, [TABLE_WIDTH_DXA])
        set_cell_shading(table.cell(0, 0), fill)
        p = table.cell(0, 0).paragraphs[0]
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.2
    else:
        p = doc.add_paragraph()
    r = p.add_run(label)
    set_run_font(r, bold=True, color=INK)
    r = p.add_run(text)
    set_run_font(r)
    return p


def add_hyperlink(paragraph, text, url):
    part = paragraph.part
    rel_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), rel_id)
    new_run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), BLUE)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    rpr.append(color)
    rpr.append(underline)
    new_run.append(rpr)
    text_node = OxmlElement("w:t")
    text_node.text = text
    new_run.append(text_node)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
    return hyperlink


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run("第 ")
    set_run_font(run, size=8.5, color=MUTED)
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for el in (begin, instr, separate, text, end):
        run._r.append(el)
    tail = paragraph.add_run(" 页")
    set_run_font(tail, size=8.5, color=MUTED)


def add_heading(doc, text, level=1):
    p = doc.add_paragraph(text, style=f"Heading {level}")
    p.paragraph_format.keep_with_next = True
    return p


def add_body(doc, text, bold_prefix=None):
    p = doc.add_paragraph()
    if bold_prefix and text.startswith(bold_prefix):
        r = p.add_run(bold_prefix)
        set_run_font(r, bold=True, color=INK)
        r = p.add_run(text[len(bold_prefix):])
        set_run_font(r)
    else:
        r = p.add_run(text)
        set_run_font(r)
    return p


def set_paragraph_bottom_border(paragraph, color="D7DBE2", size="8"):
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = p_pr.find(qn("w:pBdr"))
    if p_bdr is None:
        p_bdr = OxmlElement("w:pBdr")
        p_pr.append(p_bdr)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), "8")
    bottom.set(qn("w:color"), color)
    p_bdr.append(bottom)


doc = Document()
section = doc.sections[0]
section.page_width = PAGE_W
section.page_height = PAGE_H
section.top_margin = MARGIN
section.bottom_margin = MARGIN
section.left_margin = MARGIN
section.right_margin = MARGIN
section.header_distance = HEADER_DIST
section.footer_distance = FOOTER_DIST
section.different_first_page_header_footer = True

# Styles
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
normal.font.size = Pt(11)
normal.font.color.rgb = RGBColor.from_string(BLACK)
normal.paragraph_format.space_before = Pt(0)
normal.paragraph_format.space_after = Pt(6)
normal.paragraph_format.line_spacing = 1.25

heading_tokens = {
    1: (16, BLUE, 18, 10),
    2: (13, BLUE, 14, 7),
    3: (12, DARK_BLUE, 10, 5),
}
for level, (size, color, before, after) in heading_tokens.items():
    style = doc.styles[f"Heading {level}"]
    style.font.name = "Calibri"
    style._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
    style._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    style.font.size = Pt(size)
    style.font.bold = True
    style.font.color.rgb = RGBColor.from_string(color)
    style.paragraph_format.space_before = Pt(before)
    style.paragraph_format.space_after = Pt(after)
    style.paragraph_format.keep_with_next = True

for style_name in ("Caption", "Source Note"):
    if style_name not in [s.name for s in doc.styles]:
        doc.styles.add_style(style_name, 1)

caption = doc.styles["Caption"]
caption.font.name = "Calibri"
caption._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
caption.font.size = Pt(9.5)
caption.font.italic = False
caption.font.color.rgb = RGBColor.from_string(MUTED)
caption.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
caption.paragraph_format.space_before = Pt(4)
caption.paragraph_format.space_after = Pt(8)

source_note = doc.styles["Source Note"]
source_note.font.name = "Calibri"
source_note._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
source_note.font.size = Pt(9)
source_note.font.color.rgb = RGBColor.from_string(MUTED)
source_note.paragraph_format.space_before = Pt(4)
source_note.paragraph_format.space_after = Pt(4)
source_note.paragraph_format.line_spacing = 1.1

# Running header/footer
header = section.header
hp = header.paragraphs[0]
hp.text = "风云一号C碎片典型清理任务说明"
hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
set_run_font(hp.runs[0], size=8.5, color=MUTED)
set_paragraph_bottom_border(hp)
footer = section.footer
add_page_number(footer.paragraphs[0])

# Cover: editorial_cover pattern
spacer = doc.add_paragraph()
spacer.paragraph_format.space_before = Pt(104)
spacer.paragraph_format.space_after = Pt(0)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(18)
r = p.add_run("技术研究报告")
set_run_font(r, size=11, color=GOLD, bold=True)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(10)
r = p.add_run("风云一号C约10 cm碎片\n典型多目标清理任务说明")
set_run_font(r, size=28, color=NAVY, bold=True)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(28)
r = p.add_run("清理背景 · 选择原因 · 清理过程 · 相关指标")
set_run_font(r, size=15, color=DARK_BLUE)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(62)
r = p.add_run("规划级基准场景 | 公开轨道数据可复现计算")
set_run_font(r, size=10.5, color=GOLD, bold=True)

for text in (
    "数据基准：CelesTrak GP/OMM 与 SATCAT 快照（2026-09-02）",
    "共同历元：2026-09-01 23:06:52 UTC",
    "编制日期：2026年9月3日",
):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text)
    set_run_font(r, size=10, color=MUTED)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(34)
p.paragraph_format.space_after = Pt(0)
r = p.add_run("说明：本文结果用于方案论证，不替代任务级精密定轨、相对导航、接触动力学和再入安全分析。")
set_run_font(r, size=9.5, color=MUTED, italic=True)

doc.add_page_break()

# Executive summary
add_heading(doc, "结论摘要", 1)
metric_rows = [
    ("5个", "目标数量"),
    ("121.75天", "基准任务周期"),
    ("539.88 m/s", "含20%余量设计Δv"),
    ("11.13个/年", "继续型有效清理率"),
]
metric_table = doc.add_table(rows=2, cols=4)
set_table_geometry(metric_table, [2340, 2340, 2340, 2340])
for i, (value, label) in enumerate(metric_rows):
    set_cell_shading(metric_table.cell(0, i), GREEN_FILL)
    set_cell_text(metric_table.cell(0, i), value, bold=True, color=INK, size=14,
                  align=WD_ALIGN_PARAGRAPH.CENTER)
    set_cell_text(metric_table.cell(1, i), label, color=MUTED, size=8.8,
                  align=WD_ALIGN_PARAGRAPH.CENTER)
set_table_borders(metric_table, color="D6E2D0")
doc.add_paragraph()

add_label_para(doc, "研究场景：", "单艘服务航天器依次接近、抓取并收纳5个约10 cm的风云一号C碎片，最后携带组合体整体离轨。", CALLOUT_FILL)
add_label_para(doc, "核心路线：", "36668 → 30741 → 35089 → 35175 → 31150。该顺序是5个已选目标的120种排列中按目标间Δv最小得到的定时路线。")
add_label_para(doc, "数据口径：", "公开目录量、模型计算量和规划假设分别标注；90天首目标获取、每目标2天操作、每目标5 m/s近距离操作和7天末段处置均为规划假设，不是CelesTrak目录数据。")

# 1 Background
add_heading(doc, "1 清理背景", 1)
add_heading(doc, "1.1 风云一号C碎片的来源", 2)
add_body(doc, "风云一号C（Fengyun-1C，国际编号1999-025A，NORAD 25730）是一颗气象卫星。2007年1月11日，该卫星在约860 km高度的反卫星试验中被高速拦截器撞击并彻底破碎，形成大量长期在轨碎片。[1][2]")
add_body(doc, "NASA资料记录，该事件累计编目碎片达到3532个；截至2025年1月3日仍有2557个在轨。事件发生轨道约为845×865 km、倾角约98.6°。由于高度较高、大气阻力弱，相当一部分碎片可持续存在数十年至更长时间。[2][3]")

event_rows = [
    ["母体", "风云一号C气象卫星", "NASA ODPO [1]"],
    ["破碎时间", "2007-01-11 22:26 UTC（约）", "NASA ODPO [1]"],
    ["破碎高度", "约860 km", "NASA/ESA [1][3]"],
    ["原轨道", "约845×865 km，倾角约98.6°", "NASA NTRS [2]"],
    ["累计编目碎片", "3532个", "2025-01-03统计 [2]"],
    ["当时仍在轨", "2557个", "2025-01-03统计 [2]"],
]
add_table(doc, ["项目", "事实", "来源"], event_rows,
          [1900, 4500, 2960],
          [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT])
add_source_note(doc, "数据来源：NASA Orbital Debris Program Office、NASA NTRS及ESA公开资料 [1]-[3]。")

add_heading(doc, "1.2 为什么需要研究清理", 2)
add_body(doc, "约800-900 km太阳同步轨道带聚集了大量气象与遥感航天器。风云一号C碎片云长期占据这一高度区间，并持续参与近距离交会。约10 cm碎片已足以对运行航天器造成严重破坏，却缺少主动避让和自我离轨能力。[3][4]")
add_body(doc, "需要区分两类治理目标：清除小型可跟踪碎片主要降低当前航天器遭受撞击的直接风险；移除大型完整废弃卫星和火箭级则更有利于避免未来再次产生碎片云。NASA和ESA均指出，控制长期环境增长时应优先考虑大型、高质量、高碰撞概率且长期驻留的完整物体。[7]")

# 2 Selection reasons
add_heading(doc, "2 选择风云一号C碎片的原因", 1)
selection_rows = [
    ["目标池充足", "同一破碎事件形成大量已编目目标。本研究按尺寸、轨道高度、偏心率和根数时效筛选出145个候选。", "模型筛选 [10]"],
    ["长期驻留", "目标位于约780-880 km，空气阻力弱，自然衰减慢，具有持续风险。", "NASA/ESA [2][3]"],
    ["尺寸具有代表性", "RCS等效直径8-12 cm，位于公开监视系统可跟踪的小碎片量级。", "SATCAT+计算 [6][10]"],
    ["轨道相对集中", "5个目标倾角均约98.6°、轨道高度接近，适合研究单航天器连续访问。", "GP/OMM+SGP4 [5][10]"],
    ["数据可追溯", "NORAD编号、国际编号、OMM根数及RCS均可从CelesTrak公开获取。", "CelesTrak [5][6]"],
    ["适合装置验证", "小尺寸、非合作、可能翻滚，可用于评估识别、柔顺抓取、收纳与安全撤离能力。", "研究场景定义"],
]
add_table(doc, ["选择因素", "说明", "数据依据"], selection_rows,
          [1800, 5100, 2460],
          [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT],
          font_size=9.0)
add_source_note(doc, "说明：选择这5个目标用于约10 cm多目标抓取能力研究，并不表示其已被国际机构正式列为优先清除目标。")

if FIGURE.exists():
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    orbit_shape = p.add_run().add_picture(str(FIGURE), width=Inches(6.15))
    orbit_shape._inline.docPr.set(
        "descr",
        "五个风云一号C碎片目标在共同历元下的三维轨道示意图；五条彩色轨道围绕地球分布，轨道面差为便于辨识放大十倍。",
    )
    orbit_shape._inline.docPr.set("title", "五个目标共同历元三维轨道示意")
    cap = doc.add_paragraph("图1  五个目标共同历元三维轨道示意（轨道面差放大10倍，仅用于辨识）", style="Caption")
    cap.paragraph_format.keep_with_next = False
    add_source_note(doc, "数据来源：CelesTrak GP/OMM快照；SGP4传播至共同历元；图由本研究计算生成 [5][8][10]。")

# 3 Full cleanup process
add_heading(doc, "3 清理过程", 1)
process_rows = [
    ["1", "获取与冻结数据", "从CelesTrak下载风云一号C碎片GP/OMM与SATCAT数据；记录接口、UTC时间和SHA-256。", "原始JSON快照", "公开目录"],
    ["2", "筛选目标", "筛选RCS等效直径8-12 cm、近地点≥700 km、远地点≤900 km、e≤0.02、根数时效≤3天的目标。", "145个候选", "模型规则"],
    ["3", "轨道统一", "使用SGP4把各目标不同历元的平均根数传播到2026-09-01 23:06:52 UTC，得到同一TEME时刻的位置速度。", "共同历元状态", "模型计算"],
    ["4", "路线优化", "对5个目标的120种访问排列进行定时仿真，以目标间Δv最小为主要判据。", "5目标访问顺序", "模型计算"],
    ["5", "首目标获取", "入轨、平台检查、远距离搜索、定轨和接近第1目标。", "90天、30 m/s", "规划假设"],
    ["6", "近距离交会", "建立安全等待点，逐步缩短距离；识别外形、翻滚轴和角速度；保留中止与撤离走廊。", "目标状态估计", "任务操作"],
    ["7", "抓取与收纳", "同步局部运动，柔顺接触、锁紧、抑制残余运动，重新确定组合体质心并收纳。", "每目标2天、5 m/s", "规划假设"],
    ["8", "目标间转移", "等待互轨道面交点，执行等效圆轨道霍曼/轨道面合并机动，再通过高轨或低轨相位闭合沿轨差。", "4段、192.74 m/s", "模型计算"],
    ["9", "末目标离轨", "抓取第5目标后，在组合体远地点实施逆行脉冲，将新近地点降至100 km。", "202.16 m/s", "二体模型"],
    ["10", "再入与任务闭环", "跟踪离轨轨迹、确认进入大气层；评估碎片落区和地面人员风险；归档轨道与处置证据。", "7天操作窗口", "规划假设"],
]
add_table(doc, ["序号", "阶段", "主要工作", "输出/指标", "性质"], process_rows,
          [600, 1500, 4260, 1600, 1400],
          [WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT,
           WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.CENTER], font_size=8.7)
add_source_note(doc, "数据来源：CelesTrak公开数据 [5][6]；路线与时序来自本地计算结果 [10]；交会、抓取和处置流程结合IADC与联合国减缓原则整理 [11][12]。")

add_heading(doc, "3.1 单目标交会与抓取的关键控制", 2)
add_label_para(doc, "远距离段：", "依靠地面更新与星载传感器重新捕获目标，从数十千米逐步进入共轨区域。公开GP数据只用于初始规划，不能直接作为末端抓取导航数据。")
add_label_para(doc, "近距离段：", "在安全等待点完成外形、相对位置、翻滚轴和角速度估计；接近轨迹应具备被动安全性，并设置中止、后退和避碰逻辑。")
add_label_para(doc, "接触段：", "抓取机构需要与目标局部运动同步，以低接触速度、柔顺力控和有限冲击完成包覆或夹持，避免目标破裂产生新碎片。")
add_label_para(doc, "抓取后：", "确认锁紧状态，抑制组合体残余角动量，更新质量、质心和惯量参数，再将碎片固定或收纳后执行下一段轨道机动。")

add_heading(doc, "3.2 目标间转移计算方法", 2)
add_body(doc, "每段转移速度增量按“几何转移+相位机动”计算：Δv_leg = Δv_geometry + Δv_phase。分段时间由节点等待、约51分钟霍曼飞行和相位轨道时间组成。基准情景将单次相位机动限制为不超过10 m/s，因此第2、3段相位闭合时间较长。")
add_body(doc, "目标间阶段时间还包含5次目标交会、抓取和收纳停留：t_inter = Σt_leg + 5×2天 = 24.751天。")

add_heading(doc, "3.3 末目标离轨", 2)
add_body(doc, "末目标31150的共同历元半长轴为7228.801 km、偏心率为0.002110。模型在约865.915 km远地点实施逆行脉冲，将新轨道近地点降至100 km，计算离轨Δv为202.160 m/s，滑行至新近地点约47.132分钟。")
add_body(doc, "该结果采用二体瞬时脉冲模型；尚未计入有限推力、组合体质量变化、姿态控制、发动机安装误差、再入走廊和地面风险约束。")

# 4 Metrics
add_heading(doc, "4 相关指标", 1)
add_heading(doc, "4.1 目标清理顺序与轨道参数", 2)
route = result["timed_route_minimum_dv"]["route"]
targets_by_id = {t["norad"]: t for t in result["selected_targets"]}
ordered = [targets_by_id[n] for n in route]
target_rows = []
for idx, t in enumerate(ordered, 1):
    target_rows.append([
        idx,
        t["norad"],
        t["object_id"],
        f'{t["perigee_km"]:.0f}×{t["apogee_km"]:.0f}',
        f'{t["rcs_m2"]:.4f}',
        f'{t["rcs_equiv_d_cm"]:.2f}',
    ])
add_table(doc, ["顺序", "NORAD", "国际编号", "轨道高度 km", "RCS m²", "等效直径 cm"],
          target_rows, [600, 1000, 1700, 1900, 1500, 2660],
          [WD_ALIGN_PARAGRAPH.CENTER] * 6)
add_source_note(doc, "数据来源：CelesTrak GP/OMM和SATCAT快照 [8][9]。轨道高度与等效直径为本研究计算值 [10]；等效直径不等于实测几何尺寸。")

add_heading(doc, "4.2 四段目标间转移", 2)
leg_rows = []
for idx, leg in enumerate(result["timed_route_minimum_dv"]["legs"], 1):
    leg_rows.append([
        idx,
        f'{leg["from"]}→{leg["to"]}',
        f'{leg["plane_angle_deg"]:.3f}',
        f'{leg["geometry_dv_mps"]:.3f}',
        f'{leg["phasing_dv_mps"]:.3f}',
        f'{leg["leg_dv_mps"]:.3f}',
        f'{leg["leg_duration_days"]:.3f}',
    ])
leg_rows.append(["合计", "—", "—", "119.481", "73.260", "192.741", "14.751"])
add_table(doc, ["段", "路线", "面夹角 °", "几何Δv", "相位Δv", "分段Δv", "历时 day"],
          leg_rows, [600, 1500, 1250, 1450, 1450, 1450, 1660],
          [WD_ALIGN_PARAGRAPH.CENTER] * 7, font_size=8.9)
add_source_note(doc, "数据来源：SGP4互轨道面交点搜索、等效圆轨道霍曼/轨道面合并机动及相位模型 [10]。Δv单位均为m/s。")

add_heading(doc, "4.3 任务周期与Δv", 2)
metrics = result["mission_metrics"]
metric_rows = [
    ["首目标获取", "90.000", "day", "规划假设"],
    ["目标间阶段", f'{result["timed_route_minimum_dv"]["inter_target_elapsed_days"]:.3f}', "day", "模型计算；含5次×2天停留"],
    ["最终处置操作", "7.000", "day", "规划假设"],
    ["任务总周期", f'{metrics["total_mission_days"]:.3f}', "day", "90+24.751+7"],
    ["目标间转移Δv", f'{result["timed_route_minimum_dv"]["inter_target_dv_mps"]:.3f}', "m/s", "模型计算"],
    ["首目标获取Δv", "30.000", "m/s", "规划假设"],
    ["5目标RPO Δv", "25.000", "m/s", "5×5 m/s规划假设"],
    ["末目标离轨Δv", f'{result["last_target_deorbit"]["burn_mps"]:.3f}', "m/s", "二体模型"],
    ["余量前总Δv", f'{metrics["delta_v_before_reserve_mps"]:.3f}', "m/s", "以上四项之和"],
    ["设计总Δv", f'{metrics["design_delta_v_with_20pct_reserve_mps"]:.3f}', "m/s", "含20%规划余量"],
]
add_table(doc, ["指标", "数值", "单位", "数据性质/计算口径"], metric_rows,
          [3000, 1500, 1200, 3660],
          [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.RIGHT,
           WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT], font_size=9.0)
add_source_note(doc, "数据来源：本地模型结果 [10]。90天、30 m/s、2天/目标、5 m/s/目标、7天和20%余量均为规划假设，不是公开目录量。")

add_heading(doc, "4.4 清理能力指标", 2)
ability_rows = [
    ["名义目标数", "5.000", "target", "5个目标全部完成"],
    ["名义清理率", f'{metrics["nominal_rate_targets_per_year"]:.3f}', "target/year", "5×365/121.751"],
    ["继续型期望有效数", f'{metrics["effective_targets_continue_after_safe_failure"]:.3f}', "target", "失败后安全跳过并继续；q=75%，处置=99%"],
    ["继续型有效清理率", f'{metrics["effective_rate_continue_per_year"]:.3f}', "target/year", "期望有效数×365/周期"],
    ["终止型期望有效数", f'{metrics["effective_targets_abort_after_failure"]:.3f}', "target", "任一失败即终止；q=75%，处置=99%"],
    ["终止型有效清理率", f'{metrics["effective_rate_abort_per_year"]:.3f}', "target/year", "期望有效数×365/周期"],
]
add_table(doc, ["指标", "数值", "单位", "口径"], ability_rows,
          [3000, 1500, 1500, 3360],
          [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.RIGHT,
           WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT], font_size=9.0)
add_source_note(doc, "数据来源：本地能力计算 [10]。成功率参数属于敏感性假设，不能视为实际任务已验证可靠性。")

add_heading(doc, "4.5 指标解读优先级", 2)
priority_rows = [
    ["一级：任务可行性", "设计总Δv、任务总周期、末目标离轨能力", "决定平台推进与处置架构是否可实现"],
    ["二级：多目标效率", "目标间Δv、相位时间、停留时间、清理率", "决定一次任务能够处理多少目标"],
    ["三级：抓取安全", "相对导航误差、接触速度、抓取成功率、撤离能力", "目前未纳入严格数值模型，需后续试验验证"],
    ["四级：环境效果", "被移除质量、风险降低量、避免碰撞数量", "本研究以10 cm小碎片能力验证为主，尚未完成环境收益评估"],
]
add_table(doc, ["优先级", "指标", "意义"], priority_rows,
          [1800, 3600, 3960],
          [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT],
          font_size=9.0)

# 5 Sources and boundaries
doc.add_page_break()
add_heading(doc, "5 数据来源与适用边界", 1)
add_heading(doc, "5.1 数据溯源", 2)
source_rows = [
    ["轨道根数", "CelesTrak GP/OMM", "EPOCH、平均运动、e、i、RAAN、近地点幅角、平近点角", "公开目录"],
    ["目标属性", "CelesTrak SATCAT", "NORAD、国际编号、对象类型、RCS", "公开目录"],
    ["共同历元状态", "SGP4 2.25", "TEME位置速度、统一时刻轨道参数", "模型计算"],
    ["路线与时序", "public_debris_mission_calc.py", "目标顺序、节点等待、霍曼、相位、Δv和历时", "模型计算"],
    ["操作与成功率", "本研究基准假设", "90天、2天/目标、5 m/s/目标、7天、q与处置成功率", "规划假设"],
]
add_table(doc, ["类别", "来源", "主要字段/用途", "性质"], source_rows,
          [1600, 2400, 3900, 1460],
          [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT,
           WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.CENTER], font_size=9.0)

add_heading(doc, "5.2 原始文件完整性", 2)
hash_rows = [
    ["GP/OMM快照", "celestrak_fy1c_gp_snapshot.json", "B36CEEB9AFC492717BAE22527F8235AF92D187C6B1B321BC6BA1577B95AC6262"],
    ["SATCAT快照", "celestrak_fy1c_satcat_snapshot.json", "E5E1AB3B976D2B4007F3E9361AC18D89185D50F966081A2761C0DE171E58CC95"],
]
add_table(doc, ["文件类型", "文件名", "SHA-256"], hash_rows,
          [1500, 3000, 4860],
          [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT],
          font_size=8.4)
add_source_note(doc, "哈希用于证明当前保存文件后续未被修改；若要进一步证明历史轨道真实性，应以相同历元的Space-Track或CelesTrak历史GP数据进行交叉核验。")

add_heading(doc, "5.3 模型边界", 2)
boundary_rows = [
    ["尚未计入", "精密轨道协方差、有限推力、照明通信窗口、地面测控、姿态翻滚、接触动力学、推进剂质量变化、故障恢复和再入地面风险。"],
    ["结果用途", "适用于目标筛选、路线比较、抓取系统能力边界和方案阶段资源估算。"],
    ["不得替代", "任务级精密定轨、制导导航控制设计、真实推进剂预算、结构接触仿真和安全审查。"],
]
add_table(doc, ["项目", "说明"], boundary_rows, [2000, 7360],
          [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT], font_size=9.2)

add_heading(doc, "参考资料", 1)
references = [
    ("[1] NASA Orbital Debris Program Office. History of On-Orbit Satellite Fragmentations: FENGYUN 1C event sheet.", "https://www.orbitaldebris.jsc.nasa.gov/library/HOOSF_16e.pdf"),
    ("[2] NASA NTRS. Characterization of the Catalog Fengyun-1C Fragments and Their Long-term Effect on the LEO Environment.", "https://ntrs.nasa.gov/citations/20080012520"),
    ("[3] ESA. Space Debris FAQ: deliberate satellite intercepts and the Fengyun-1C debris cloud.", "https://www.esa.int/Space_Safety/Space_Debris/Space_Debris_FAQ_Frequently_asked_questions"),
    ("[4] NASA Orbital Debris Quarterly News, Vol. 27 Issue 3. Major debris cloud contributions to LEO spatial density.", "https://orbitaldebris.jsc.nasa.gov/quarterly-news/pdfs/ODQNv27i3.pdf"),
    ("[5] CelesTrak. GP/OMM data formats and query documentation.", "https://celestrak.org/NORAD/documentation/gp-data-formats.php"),
    ("[6] CelesTrak. SATCAT format documentation.", "https://celestrak.org/satcat/satcat-format.php"),
    ("[7] NASA Orbital Debris Program Office. Debris Remediation.", "https://orbitaldebris.jsc.nasa.gov/remediation/"),
]
for label, url in references:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.18)
    p.paragraph_format.first_line_indent = Inches(-0.18)
    p.paragraph_format.space_after = Pt(5)
    r = p.add_run(label + " ")
    set_run_font(r, size=9.5)
    add_hyperlink(p, url, url)

for text in (
    "[8] CelesTrak GP/OMM本地冻结快照：public_debris_calculation/celestrak_fy1c_gp_snapshot.json；获取时间2026-09-02 06:39:51 UTC。",
    "[9] CelesTrak SATCAT本地冻结快照：public_debris_calculation/celestrak_fy1c_satcat_snapshot.json；获取时间2026-09-02 06:39:51 UTC。",
    "[10] 本地计算结果与程序：public_debris_calculation/screening_result.json；public_debris_mission_calc.py。",
    "[11] IADC Space Debris Mitigation Guidelines, Revision 4，以及用户提供的中文版材料。",
    "[12] United Nations COPUOS Space Debris Mitigation Guidelines，以及用户提供的中文版材料。",
):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.18)
    p.paragraph_format.first_line_indent = Inches(-0.18)
    p.paragraph_format.space_after = Pt(5)
    r = p.add_run(text)
    set_run_font(r, size=9.5)

# Core properties
doc.core_properties.title = "风云一号C约10 cm碎片典型多目标清理任务说明"
doc.core_properties.subject = "清理背景、选择原因、清理过程与相关指标"
doc.core_properties.author = "User"
doc.core_properties.keywords = "空间碎片, 风云一号C, 主动清理, SGP4, CelesTrak"

doc.save(OUTPUT)
print(str(OUTPUT))
