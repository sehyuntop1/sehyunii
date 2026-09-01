import asyncio
import random

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)

from config import (
    OPENAI_API_KEY,
    OPENAI_MAX_OUTPUT_TOKENS,
    OPENAI_MODEL,
    OPENAI_REASONING_DEFAULT,
)

_client: AsyncOpenAI | None = None
_RETRYABLE_ERRORS = (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
    asyncio.TimeoutError,
)
MAX_RETRIES = 10


def _get_client() -> AsyncOpenAI:
    global _client
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
    if _client is None:
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY, timeout=120.0)
    return _client


async def generate(
    prompt: str,
    reasoning_effort: str = OPENAI_REASONING_DEFAULT,
) -> str:
    for attempt in range(MAX_RETRIES):
        try:
            response = await asyncio.wait_for(
                _get_client().responses.create(
                    model=OPENAI_MODEL,
                    input=prompt,
                    reasoning={"effort": reasoning_effort},
                    max_output_tokens=OPENAI_MAX_OUTPUT_TOKENS,
                    store=False,
                ),
                timeout=120.0,
            )
            text = response.output_text.strip()
            if not text:
                raise RuntimeError("OpenAI API가 빈 응답을 반환했습니다.")
            return text
        except _RETRYABLE_ERRORS:
            if attempt >= MAX_RETRIES - 1:
                raise
            base_wait = min(2 ** attempt, 60)
            await asyncio.sleep(base_wait + random.uniform(0, base_wait * 0.3))

    raise RuntimeError("OpenAI API 재시도 횟수를 초과했습니다.")
