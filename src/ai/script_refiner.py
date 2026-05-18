from config import GEMINI_REFINE_TEMPERATURE
from src.ai.gemini_client import generate

REFINE_PROMPT = """다음은 교수님의 강의 대본입니다. 아래 규칙에 따라 아주 가볍게만 다듬어 주세요.

규칙:
1. 공지사항, 출석, 과제, 시험 일정 등 수업 운영 관련 잡소리만 제거합니다.
2. 주제와 완전히 무관한 사설, 잡담만 제거합니다.
3. "어~", "그~", "음~" 같은 단순 추임새만 제거합니다.
4. 그 외 모든 의학 설명, 기전, 수치, 예시, 비유는 절대 손대지 마세요.
5. 교수님 강조 표현("기억하세요", "외워두세요", "중요합니다" 등)은 반드시 그대로 보존합니다.
6. 교수님 농담, 질문-답변 대화는 그대로 유지합니다.
7. 슬라이드 전환 마커([슬라이드 N], [페이지 N])가 있다면 반드시 유지합니다.
8. 요약하거나 재구성하지 말고, 원문을 최대한 그대로 둡니다.
9. 출력은 다듬어진 대본만 출력하고 다른 설명은 추가하지 마세요.

---
강의 대본:
{raw_script}
---
"""


async def refine_script(raw_script: str) -> str:
    prompt = REFINE_PROMPT.format(raw_script=raw_script)
    return await generate(prompt, GEMINI_REFINE_TEMPERATURE)
