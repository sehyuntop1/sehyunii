import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

EMPHASIS_PHRASES = [
    "기억하셔야합니다", "기억하세요", "기억해두세요",
    "외워두세요", "외워야합니다", "암기하세요",
    "중요합니다", "중요해요", "매우 중요", "아주 중요",
    "꼭 기억", "반드시 기억", "시험에 나옵니다", "시험 문제",
]

GEMINI_REFINE_TEMPERATURE = 0.0
GEMINI_MAPPING_TEMPERATURE = 0.2
GEMINI_SUMMARY_TEMPERATURE = 0.3

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
