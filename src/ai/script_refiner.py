from config import GEMINI_REFINE_TEMPERATURE
from src.ai.gemini_client import generate

REFINE_PROMPT = """다음은 교수님의 강의 대본입니다. 아래 규칙에 따라 정제해 주세요.

규칙:
1. 불필요한 말버릇, 반복, 잡음을 제거합니다.
2. 문장을 자연스럽고 명확하게 다듬습니다.
3. 강의 내용의 핵심과 흐름은 그대로 유지합니다.
4. 강조 표현("기억하셔야합니다", "외워두세요", "중요합니다" 등)은 반드시 그대로 보존합니다.
5. 각 강의 슬라이드 페이지 전환 마커(예: [슬라이드 N], [페이지 N])가 있다면 유지합니다.
6. 출력은 정제된 대본만 출력하고 다른 설명은 추가하지 마세요.

---
강의 대본:
{raw_script}
---
"""


async def refine_script(raw_script: str) -> str:
    prompt = REFINE_PROMPT.format(raw_script=raw_script)
    return await generate(prompt, GEMINI_REFINE_TEMPERATURE)
