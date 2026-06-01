import asyncio
import random
from google import genai
from google.genai import types
from config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)

MAX_RETRIES = 10


async def generate(prompt: str, temperature: float) -> str:
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.aio.models.generate_content(
                model="gemini-1.5-pro",
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
                "429" in err_str or
                "overloaded" in err_str.lower() or
                "high demand" in err_str.lower()
            )
            if is_retryable and attempt < MAX_RETRIES - 1:
                base_wait = min(2 ** attempt, 60)
                jitter = random.uniform(0, base_wait * 0.3)
                await asyncio.sleep(base_wait + jitter)
                continue
            else:
                raise
