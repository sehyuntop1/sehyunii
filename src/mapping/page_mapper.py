import json
import re
from config import GEMINI_MAPPING_TEMPERATURE, GEMINI_SUMMARY_TEMPERATURE
from src.ai.gemini_client import generate

MAPPING_PROMPT = """강의 슬라이드의 각 페이지 내용과 교수님의 강의 대본이 주어집니다.
대본의 어느 부분이 어느 슬라이드 페이지에 해당하는지 매핑해 주세요.

출력 형식 (JSON만 출력, 다른 설명 없이):
{{
  "mapping": [
    {{"page": 1, "script": "해당 페이지에 대한 강의 대본 내용"}},
    {{"page": 2, "script": "해당 페이지에 대한 강의 대본 내용"}},
    ...
  ]
}}

슬라이드 페이지 내용:
{slide_contents}

강의 대본:
{refined_script}
"""

SUMMARY_PROMPT = """다음은 강의 슬라이드 {page_num}페이지의 내용과 해당 페이지에 대한 교수님 강의 대본입니다.
이 페이지의 핵심 내용을 학생이 이해하기 쉽게 3~5개의 bullet point로 요약/해석해 주세요.

슬라이드 내용:
{slide_text}

교수님 설명:
{script_text}

출력 형식 (요약 bullet point만, 다른 설명 없이):
"""


async def map_script_to_pages(
    slide_texts: list[str], refined_script: str
) -> list[dict]:
    slide_contents = "\n\n".join(
        f"[페이지 {i+1}]\n{text}" for i, text in enumerate(slide_texts)
    )
    prompt = MAPPING_PROMPT.format(
        slide_contents=slide_contents,
        refined_script=refined_script,
    )
    response = await generate(prompt, GEMINI_MAPPING_TEMPERATURE)

    json_match = re.search(r"\{.*\}", response, re.DOTALL)
    if not json_match:
        return [{"page": i + 1, "script": ""} for i in range(len(slide_texts))]

    data = json.loads(json_match.group())
    mapping = data.get("mapping", [])

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
