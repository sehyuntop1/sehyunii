import google.generativeai as genai
from config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)


def get_model(temperature: float) -> genai.GenerativeModel:
    return genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        generation_config=genai.GenerationConfig(temperature=temperature),
    )


async def generate(prompt: str, temperature: float) -> str:
    model = get_model(temperature)
    response = await model.generate_content_async(prompt)
    return response.text
