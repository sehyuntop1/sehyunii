import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
OPENAI_REASONING_DEFAULT = os.getenv("OPENAI_REASONING_EFFORT", "low")
OPENAI_REASONING_REFINEMENT = os.getenv("OPENAI_REASONING_REFINEMENT", "low")
OPENAI_REASONING_MAPPING = os.getenv("OPENAI_REASONING_MAPPING", "low")
OPENAI_REASONING_SUMMARY = os.getenv("OPENAI_REASONING_SUMMARY", "low")
OPENAI_MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "32768"))

EMPHASIS_PHRASES = [
    "기억하셔야합니다", "기억하세요", "기억해두세요",
    "외워두세요", "외워야합니다", "암기하세요",
    "중요합니다", "중요해요", "매우 중요", "아주 중요",
    "꼭 기억", "반드시 기억", "시험에 나옵니다", "시험 문제",
]

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
