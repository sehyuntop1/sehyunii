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


async def map_script_to_pages(
    slide_texts: list[str], refined_script: str
) -> list[dict]:
    slide_contents = "\n".join(
        f"[슬라이드 {i+1}]\n{text}" for i, text in enumerate(slide_texts)
    )
    prompt = MAPPING_PROMPT.format(
        slide_contents=slide_contents,
        refined_script=refined_script,
    )
    response = await generate(prompt, GEMINI_MAPPING_TEMPERATURE)

    # JSON 추출 시도 - 여러 방법으로 시도
    mapping = []
    
    # 방법 1: ```json ... ``` 블록
    json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            mapping = data.get("mapping", [])
        except:
            pass

    # 방법 2: ``` ... ``` 블록
    if not mapping:
        json_match = re.search(r"```\s*(.*?)\s*```", response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                mapping = data.get("mapping", [])
            except:
                pass

    # 방법 3: { ... } 전체
    if not mapping:
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                mapping = data.get("mapping", [])
            except:
                pass

    # 방법 4: 그냥 빈 매핑 반환
    if not mapping:
        return [{"page": i + 1, "script": ""} for i in range(len(slide_texts))]

    result = {item["page"]: item["script"] for item in mapping}
    return [
        {"page": i + 1, "script": result.get(i + 1, "")}
        for i in range(len(slide_texts))
    ]


async def generate_page_summary(
    page_num: int, slide_text: str, script_text: str
) -> str:
    prompt = SUMMARY_PROMPT.format(
        page_num=page_num,
        slide_text=slide_text,
        script_text=script_text,
    )
    return await generate(prompt, GEMINI_SUMMARY_TEMPERATURE)
