import fitz


def extract_slide_texts(pdf_path: str) -> list[str]:
    """Extract text content from each page of the lecture PDF."""
    doc = fitz.open(pdf_path)
    texts = []
    for page in doc:
        text = page.get_text("text").strip()
        texts.append(text if text else "(텍스트 없음 - 이미지 슬라이드)")
    doc.close()
    return texts
