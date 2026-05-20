import json
import re
from config import GEMINI_MAPPING_TEMPERATURE, GEMINI_SUMMARY_TEMPERATURE
from src.ai.gemini_client import generate

MAPPING_PROMPT = """당신은 강의 대본과 슬라이드를 매핑하는 전문가입니다.
아래 슬라이드 내용과 강의 대본을 보고, 각 슬라이드 페이지에 해당하는 대본 내용을 매핑해주세요.

슬라이드 내용:
{slide_contents}

강의 대본:
{refined_script}

반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "mapping": [
    {{"page": 1, "script": "해당 페이지 대본 내용"}},
    {{"page": 2, "script": "해당 페이지 대본 내용"}}
  ]
}}
"""

SUMMARY_PROMPT = """강의 슬라이드 {page_num}페이지의 핵심 내용을 요약해주세요.
슬라이드 텍스트와 대본을 참고하여 3-5개의 bullet point로 핵심만 정리해주세요.

슬라이드 텍스트:
{slide_text}

대본 내용:
{script_text}

bullet point 형식으로 응답하세요 (JSON 없이 텍스트만):
"""


def _parse_slide_markers(script: str, total_pages: int) -> list[dict] | None:
    """
    [슬라이드 N] 또는 [페이지 N] 마커가 있으면 바로 파싱해서 반환.
    마커가 없으면 None 반환.
    """
    pattern = re.compile(r'\[(?:슬라이드|페이지)\s*(\d+)\]', re.IGNORECASE)
    matches = list(pattern.finditer(script))

    if not matches:
        return None

    result = {}
    for i, match in enumerate(matches):
        page_num = int(match.group(1))
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(script)
        result[page_num] = script[start:end].strip()

    return [
        {"page": i + 1, "script": result.get(i + 1, "")}
        for i in range(total_pages)
    ]


async def _gemini_mapping_chunked(
    slide_texts: list[str], script: str
) -> list[dict]:
    """
    슬라이드 20개씩 나눠서 매핑.
    스크립트는 앞 8000자만 사용 (프롬프트 크기 제한).
    """
    BATCH_SIZE = 20
    script_trimmed = script[:8000]  # 너무 길면 자름
    result = {}

    for batch_start in range(0, len(slide_texts), BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, len(slide_texts))
        batch = slide_texts[batch_start:batch_end]

        slide_contents = "\n".join(
            f"[슬라이드 {batch_start + i + 1}]\n{text[:150]}"
            for i, text in enumerate(batch)
        )

        prompt = MAPPING_PROMPT.format(
            slide_contents=slide_contents,
            refined_script=script_trimmed,
        )
        response = await generate(prompt, GEMINI_MAPPING_TEMPERATURE)

        mapping = []
        for pattern in [
            r"```json\s*(.*?)\s*```",
            r"```\s*(.*?)\s*```",
        ]:
            m = re.search(pattern, response, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                    mapping = data.get("mapping", [])
                    break
                except:
                    pass

        if not mapping:
            m = re.search(r"\{.*\}", response, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group())
                    mapping = data.get("mapping", [])
                except:
                    pass

        for item in mapping:
            result[item["page"]] = item.get("script", "")

    return [
        {"page": i + 1, "script": result.get(i + 1, "")}
        for i in range(len(slide_texts))
    ]


async def map_script_to_pages(
    slide_texts: list[str], refined_script: str
) -> list[dict]:
    # 1순위: [슬라이드 N] 마커 직접 파싱 (Gemini 호출 없음)
    parsed = _parse_slide_markers(refined_script, len(slide_texts))
    if parsed:
        return parsed

    # 2순위: 청크 단위 Gemini 매핑
    return await _gemini_mapping_chunked(slide_texts, refined_script)


async def generate_page_summary(
    page_num: int, slide_text: str, script_text: str
) -> str:
    prompt = SUMMARY_PROMPT.format(
        page_num=page_num,
        slide_text=slide_text,
        script_text=script_text,
    )
    return await generate(prompt, GEMINI_SUMMARY_TEMPERATURE)
