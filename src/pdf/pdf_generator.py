import io
import re
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    HRFlowable,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from config import EMPHASIS_PHRASES

PAGE_W, PAGE_H = A4
MARGIN = 15 * mm

_FONT_REGISTERED = False


def _register_korean_font():
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return

    # Windows 한국어 폰트 경로
    font_candidates = [
        "C:/Windows/Fonts/malgun.ttf",       # 맑은 고딕
        "C:/Windows/Fonts/gulim.ttc",         # 굴림
        "C:/Windows/Fonts/batang.ttc",        # 바탕
        "C:/Windows/Fonts/NanumGothic.ttf",   # 나눔고딕 (설치된 경우)
        # Linux fallback
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]

    for path in font_candidates:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont("KoreanFont", path))
                _FONT_REGISTERED = True
                return
            except:
                continue

    _FONT_REGISTERED = False


def _get_styles() -> dict:
    _register_korean_font()
    base = "KoreanFont" if _FONT_REGISTERED else "Helvetica"

    styles = getSampleStyleSheet()
    script_style = ParagraphStyle(
        "ScriptText",
        parent=styles["Normal"],
        fontName=base,
        fontSize=10,
        leading=15,
        textColor=colors.black,
        spaceAfter=4,
    )
    summary_style = ParagraphStyle(
        "SummaryText",
        parent=styles["Normal"],
        fontName=base,
        fontSize=9,
        leading=14,
        textColor=colors.HexColor("#1a5276"),
        spaceAfter=3,
    )
    label_style = ParagraphStyle(
        "LabelText",
        parent=styles["Normal"],
        fontName=base,
        fontSize=8,
        leading=12,
        textColor=colors.HexColor("#7f8c8d"),
        spaceBefore=6,
        spaceAfter=2,
    )
    return {"script": script_style, "summary": summary_style, "label": label_style}


def _highlight_emphasis(text: str, style: ParagraphStyle) -> list:
    """Split text into Paragraphs, coloring emphasis phrases red."""
    pattern = "(" + "|".join(re.escape(p) for p in EMPHASIS_PHRASES) + ")"
    segments = re.split(pattern, text)

    base = "KoreanFont" if _FONT_REGISTERED else "Helvetica"
    paragraphs = []
    current = ""
    for seg in segments:
        if any(seg == p for p in EMPHASIS_PHRASES):
            current += f'<font color="red"><b>{seg}</b></font>'
        else:
            current += seg

    for line in current.split("\n"):
        line = line.strip()
        if line:
            paragraphs.append(Paragraph(line, style))
    return paragraphs


def _slide_to_image(page: fitz.Page, max_width: float) -> RLImage | None:
    mat = fitz.Matrix(2, 2)
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("png")

    img = Image.open(io.BytesIO(img_data))
    w, h = img.size
    scale = min(max_width / w, (PAGE_H * 0.4) / h)
    new_w, new_h = int(w * scale), int(h * scale)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return RLImage(buf, width=new_w, height=new_h)


def generate_pdf(
    lecture_pdf_path: str,
    page_mappings: list[dict],
    summaries: list[str],
    output_path: str,
) -> str:
    styles = _get_styles()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )

    source_pdf = fitz.open(lecture_pdf_path)
    content_width = PAGE_W - 2 * MARGIN
    story = []

    for i, mapping in enumerate(page_mappings):
        page_num = mapping["page"]
        script_text = mapping.get("script", "")
        summary_text = summaries[i] if i < len(summaries) else ""

        if page_num <= len(source_pdf):
            slide_img = _slide_to_image(source_pdf[page_num - 1], content_width)
            if slide_img:
                story.append(slide_img)
                story.append(Spacer(1, 4 * mm))

        if script_text:
            story.append(Paragraph("📝 강의 대본", styles["label"]))
            story.extend(_highlight_emphasis(script_text, styles["script"]))
            story.append(Spacer(1, 3 * mm))

        if summary_text:
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#aed6f1")))
            story.append(Paragraph("🔵 AI 페이지별 요약", styles["label"]))
            for line in summary_text.split("\n"):
                line = line.strip()
                if line:
                    story.append(Paragraph(line, styles["summary"]))
            story.append(Spacer(1, 6 * mm))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2980b9")))
            story.append(Spacer(1, 6 * mm))

    source_pdf.close()
    doc.build(story)
    return output_path
