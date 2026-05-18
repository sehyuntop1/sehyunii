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

PAGE_W, PAGE_H = A4
MARGIN = 15 * mm

# ── 초록 (최상위: 외워라 / 시험 필출) ──────────────────────────────
GREEN_PATTERNS = [
    r"외워\S*",
    r"외우세요",
    r"외우\S+",
    r"시험에\s*(?:꼭|반드시|무조건)?\s*(?:나와|낼|나온|나옵|출제)",
    r"시험\s*문제",
    r"필출",
    r"출제\s*(?:될|예정|합니다|해|돼)",
    r"반드시\s*기억",
    r"꼭\s*기억",
]

# ── 빨간 (중요 뉘앙스) ────────────────────────────────────────────
RED_PATTERNS = [
    r"중요\S*",
    r"기억하\S+",
    r"기억해\S*",
    r"알아두\S*",
    r"알고\s*있어야",
    r"포인트\S*",
    r"핵심\S*",
    r"강조\S*",
    r"주목\S*",
    r"놓치지\s*마",
    r"반드시\s*알",
    r"꼭\s*알",
]

_GREEN_RE = re.compile("(" + "|".join(GREEN_PATTERNS) + ")", re.IGNORECASE)
_RED_RE   = re.compile("(" + "|".join(RED_PATTERNS) + ")", re.IGNORECASE)

_FONT_REGISTERED = False


def _register_korean_font():
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return

    base_dir = Path(__file__).resolve().parent.parent.parent
    font_candidates = [
        base_dir / "fonts" / "NanumGothic.ttf",
        base_dir / "fonts" / "NanumGothicBold.ttf",
        Path("C:/Windows/Fonts/malgun.ttf"),
        Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
    ]

    for path in font_candidates:
        if path.exists():
            try:
                pdfmetrics.registerFont(TTFont("KoreanFont", str(path)))
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


def _apply_highlights(text: str) -> str:
    """
    초록(필출/외워) > 빨간(중요 뉘앙스) 순으로 우선순위.
    겹치는 구간은 초록이 이김.
    """
    # (start, end, color) 목록 수집
    matches = []

    for m in _GREEN_RE.finditer(text):
        matches.append((m.start(), m.end(), "green"))
    for m in _RED_RE.finditer(text):
        matches.append((m.start(), m.end(), "red"))

    if not matches:
        return text

    # start 기준 정렬, 겹치면 green 우선 / 긴 것 우선
    matches.sort(key=lambda x: (x[0], x[1] == "red", -(x[1] - x[0])))

    # 겹치는 구간 제거
    merged = []
    last_end = -1
    for start, end, color in matches:
        if start >= last_end:
            merged.append((start, end, color))
            last_end = end
        elif color == "green" and merged and merged[-1][2] == "red":
            # 초록이 빨간 위에 있으면 빨간 제거하고 초록으로 교체
            merged.pop()
            merged.append((start, end, color))
            last_end = end

    # 문자열 재조립
    result = ""
    prev = 0
    for start, end, color in merged:
        result += text[prev:start]
        word = text[start:end]
        if color == "green":
            result += f'<font color="#1e8449"><b>{word}</b></font>'
        else:
            result += f'<font color="red"><b>{word}</b></font>'
        prev = end
    result += text[prev:]
    return result


def _highlight_emphasis(text: str, style: ParagraphStyle) -> list:
    paragraphs = []
    for line in text.split("\n"):
        line = line.strip()
        if line:
            highlighted = _apply_highlights(line)
            paragraphs.append(Paragraph(highlighted, style))
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
