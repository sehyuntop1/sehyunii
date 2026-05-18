import asyncio
from google import genai
from google.genai import types
from config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)


async def generate(prompt: str, temperature: float, max_retries: int = 5) -> str:
    for attempt in range(max_retries):
        try:
            response = await client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=temperature),
            )
            return response.text

        except Exception as e:
            err_str = str(e)
            is_retryable = (
                "503" in err_str or
                "504" in err_str or
                "UNAVAILABLE" in err_str or
                "CANCELLED" in err_str or
                "429" in err_str
            )
            if is_retryable and attempt < max_retries - 1:
                wait = 2 ** attempt  # 1초 → 2초 → 4초 → 8초
                await asyncio.sleep(wait)
                continue
            else:
                raise
