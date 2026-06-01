import asyncio
import random
import google.generativeai as genai
from config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

MAX_RETRIES = 10


def get_model(temperature: float) -> genai.GenerativeModel:
    return genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        generation_config=genai.GenerationConfig(temperature=temperature),
    )


async def generate(prompt: str, temperature: float) -> str:
    model = get_model(temperature)

    for attempt in range(MAX_RETRIES):
        try:
            response = await model.generate_content_async(prompt)
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
