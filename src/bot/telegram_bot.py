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
        "안녕하세요! 강의록 자동 정리 봇입니다.\n\n"
        "📋 사용법:\n"
        "1. 강의 슬라이드 PDF 파일을 전송해 주세요.\n"
        "2. 그 다음 교수님 강의 대본 텍스트를 붙여넣어 주세요.\n"
        "3. AI가 자동으로 정리된 PDF를 생성해 드립니다!\n\n"
        "먼저 강의 슬라이드 PDF를 보내주세요."
    )
    return WAIT_PDF


async def receive_pdf(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    document: Document = update.message.document

    if not document.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("PDF 파일만 업로드 가능합니다.")
        return WAIT_PDF

    await update.message.reply_text("PDF 수신 중... 잠시만 기다려 주세요.")

    file = await ctx.bot.get_file(document.file_id)
    pdf_path = os.path.join(UPLOAD_DIR, f"{user_id}_{int(time.time())}.pdf")
    await file.download_to_drive(pdf_path)

    user_sessions[user_id] = {"pdf_path": pdf_path}
    await update.message.reply_text(
        f"✅ PDF 수신 완료! ({document.file_name})\n\n"
        "이제 교수님의 강의 대본 텍스트를 붙여넣어 주세요.\n"
        "(슬라이드 전환 표시가 있다면 [슬라이드 N] 형태로 포함해 주시면 더 정확합니다)"
    )
    return WAIT_SCRIPT


async def receive_script(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw_script = update.message.text

    if user_id not in user_sessions or "pdf_path" not in user_sessions[user_id]:
        await update.message.reply_text("먼저 강의 슬라이드 PDF를 보내주세요. /start")
        return ConversationHandler.END

    pdf_path = user_sessions[user_id]["pdf_path"]

    status_msg = await update.message.reply_text(
        "⚙️ 처리 중입니다...\n"
        "1/4 강의 대본 정제 중 (Gemini temperature=0)..."
    )

    try:
        refined = await refine_script(raw_script)
        await status_msg.edit_text(
            "⚙️ 처리 중입니다...\n"
            "✅ 1/4 강의 대본 정제 완료\n"
            "2/4 슬라이드 텍스트 추출 중..."
        )

        slide_texts = extract_slide_texts(pdf_path)
        await status_msg.edit_text(
            "⚙️ 처리 중입니다...\n"
            "✅ 1/4 강의 대본 정제 완료\n"
            f"✅ 2/4 슬라이드 {len(slide_texts)}페이지 추출 완료\n"
            "3/4 대본-슬라이드 매핑 중 (Gemini)..."
        )

        mappings = await map_script_to_pages(slide_texts, refined)
        await status_msg.edit_text(
            "⚙️ 처리 중입니다...\n"
            "✅ 1/4 강의 대본 정제 완료\n"
            f"✅ 2/4 슬라이드 {len(slide_texts)}페이지 추출 완료\n"
            "✅ 3/4 대본-슬라이드 매핑 완료\n"
            "4/4 AI 요약 생성 및 PDF 합성 중..."
        )

        summaries = await asyncio.gather(*[
            generate_page_summary(
                m["page"],
                slide_texts[i] if i < len(slide_texts) else "",
                m.get("script", ""),
            )
            for i, m in enumerate(mappings)
        ])

        output_path = os.path.join(OUTPUT_DIR, f"lecture_notes_{user_id}_{int(time.time())}.pdf")
        generate_pdf(pdf_path, mappings, list(summaries), output_path)

        await status_msg.edit_text("✅ 모든 처리 완료! PDF 전송 중...")

        with open(output_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename="강의_정리노트.pdf",
                caption=(
                    "📚 강의 정리 노트가 완성되었습니다!\n"
                    "• 빨간 글씨: 교수님 강조 포인트\n"
                    "• 파란 박스: AI 요약 및 해석"
                ),
            )

        os.remove(pdf_path)
        del user_sessions[user_id]

    except Exception as e:
        await status_msg.edit_text(f"❌ 오류가 발생했습니다: {str(e)}\n/start로 다시 시도해 주세요.")
        return ConversationHandler.END

    return ConversationHandler.END


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_sessions:
        pdf_path = user_sessions[user_id].get("pdf_path")
        if pdf_path and os.path.exists(pdf_path):
            os.remove(pdf_path)
        del user_sessions[user_id]
    await update.message.reply_text("취소되었습니다. /start로 다시 시작하세요.")
    return ConversationHandler.END


def build_application() -> Application:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAIT_PDF: [MessageHandler(filters.Document.PDF, receive_pdf)],
            WAIT_SCRIPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_script)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv_handler)
    return app
