import asyncio
import os
import time
from pathlib import Path

from telegram import Update, Document
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from config import TELEGRAM_BOT_TOKEN, UPLOAD_DIR, OUTPUT_DIR
from src.ai.script_refiner import refine_script
from src.mapping.page_mapper import map_script_to_pages, generate_page_summary
from src.pdf.slide_extractor import extract_slide_texts
from src.pdf.pdf_generator import generate_pdf

WAIT_PDF, WAIT_SCRIPT = range(2)

user_sessions: dict[int, dict] = {}


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "안녕하세요! 강의 슬라이드 PDF와 대본으로 정리 PDF를 만들어드립니다.\n\n"
        "1. 먼저 강의 슬라이드 PDF 파일을 보내주세요."
    )
    return WAIT_PDF


async def receive_pdf(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    document: Document = update.message.document

    if not document.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("PDF 파일만 가능합니다.")
        return WAIT_PDF

    await update.message.reply_text("PDF 수신 중.. 잠시만 기다려 주세요.")

    file = await ctx.bot.get_file(document.file_id)
    pdf_path = os.path.join(UPLOAD_DIR, f"{user_id}_{int(time.time())}.pdf")
    await file.download_to_drive(pdf_path)

    user_sessions[user_id] = {"pdf_path": pdf_path}
    await update.message.reply_text(
        f"✅ PDF 수신 완료! ({document.file_name})\n\n"
        "이제 교수님의 강의 대본 텍스트를 붙여넣어 주세요.\n"
        "또는 대본 텍스트 파일(.txt)을 전송해도 됩니다.\n"
        "(슬라이드 전환 표시가 있다면 [슬라이드 N] 형태로 포함해 주시면 더 정확합니다)"
    )
    return WAIT_SCRIPT


async def receive_script(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if update.message.document:
        import tempfile
        file = await update.message.document.get_file()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            await file.download_to_drive(tmp.name)
            with open(tmp.name, "r", encoding="utf-8") as f:
                raw_script = f.read()
        os.remove(tmp.name)
    else:
        raw_script = update.message.text

    if user_id not in user_sessions or "pdf_path" not in user_sessions[user_id]:
        await update.message.reply_text("먼저 강의 슬라이드 PDF를 보내주세요. /start")
        return ConversationHandler.END

    pdf_path = user_sessions[user_id]["pdf_path"]

    status_msg = await update.message.reply_text(
        "⏳ 처리 중입니다...\n"
        "1/4 강의 대본 정제 중 (Gemini temperature=0)..."
    )

    try:
        # 1단계: 대본 정제
        refined = await refine_script(raw_script)
        await status_msg.edit_text(
            "⏳ 처리 중입니다...\n"
            "✅ 1/4 강의 대본 정제 완료\n"
            "2/4 슬라이드 텍스트 추출 중..."
        )

        # 2단계: 슬라이드 추출
        slide_texts = extract_slide_texts(pdf_path)
        total_pages = len(slide_texts)
        await status_msg.edit_text(
            "⏳ 처리 중입니다...\n"
            "✅ 1/4 강의 대본 정제 완료\n"
            f"✅ 2/4 슬라이드 {total_pages}페이지 추출 완료\n"
            "3/4 대본-슬라이드 매핑 중 (Gemini)..."
        )

        # 3단계: 매핑
        mappings = await map_script_to_pages(slide_texts, refined)
        await status_msg.edit_text(
            "⏳ 처리 중입니다...\n"
            "✅ 1/4 강의 대본 정제 완료\n"
            f"✅ 2/4 슬라이드 {total_pages}페이지 추출 완료\n"
            "✅ 3/4 대본-슬라이드 매핑 완료\n"
            f"4/4 AI 요약 생성 중... (0/{total_pages}페이지)"
        )

        # 4단계: 10페이지씩 나눠서 요약 (timeout 방지)
        summaries = []
        BATCH_SIZE = 10

        for batch_start in range(0, total_pages, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_pages)
            batch = mappings[batch_start:batch_end]

            batch_summaries = await asyncio.gather(*[
                generate_page_summary(
                    m["page"],
                    slide_texts[i + batch_start] if i + batch_start < len(slide_texts) else "",
                    m.get("script", ""),
                )
                for i, m in enumerate(batch)
            ])
            summaries.extend(batch_summaries)

            await status_msg.edit_text(
                "⏳ 처리 중입니다...\n"
                "✅ 1/4 강의 대본 정제 완료\n"
                f"✅ 2/4 슬라이드 {total_pages}페이지 추출 완료\n"
                "✅ 3/4 대본-슬라이드 매핑 완료\n"
                f"4/4 AI 요약 생성 중... ({batch_end}/{total_pages}페이지 완료)"
            )

        # 5단계: PDF 생성
        await status_msg.edit_text(
            "⏳ 처리 중입니다...\n"
            "✅ 1/4 강의 대본 정제 완료\n"
            f"✅ 2/4 슬라이드 {total_pages}페이지 추출 완료\n"
            "✅ 3/4 대본-슬라이드 매핑 완료\n"
            f"✅ 4/4 AI 요약 {total_pages}페이지 완료\n"
            "📄 PDF 생성 중..."
        )

        output_path = os.path.join(OUTPUT_DIR, f"lecture_notes_{user_id}_{int(time.time())}.pdf")
        generate_pdf(pdf_path, mappings, list(summaries), output_path)

        await status_msg.edit_text("✅ 완료! PDF 전송 중입니다...")

        with open(output_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename="강의_정리_노트.pdf",
                caption=(
                    "📚 강의 정리 PDF입니다.\n"
                    "빨간 강조: 대본 주요 내용\n"
                    "파란 요약: AI 페이지별 요약"
                ),
            )

        os.remove(pdf_path)
        os.remove(output_path)
        del user_sessions[user_id]

    except Exception as e:
        await status_msg.edit_text(f"오류가 발생했습니다: {str(e)}\n/start로 다시 시도해 주세요.")
        return ConversationHandler.END

    return ConversationHandler.END


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_sessions:
        pdf_path = user_sessions[user_id].get("pdf_path")
        if pdf_path and os.path.exists(pdf_path):
            os.remove(pdf_path)
        del user_sessions[user_id]
    await update.message.reply_text("취소되었습니다. /start로 다시 시작할 수 있습니다.")
    return ConversationHandler.END


def build_application() -> Application:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAIT_PDF: [MessageHandler(filters.Document.PDF, receive_pdf)],
            WAIT_SCRIPT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_script),
                MessageHandler(filters.Document.TXT, receive_script),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv_handler)
    return app
