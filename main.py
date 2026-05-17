import logging
from src.bot.telegram_bot import build_application

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def main():
    app = build_application()
    print("봇 시작! Ctrl+C로 종료하세요.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
