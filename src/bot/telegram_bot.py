import asyncio
import os
import time

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
from src.ai.script_validator import validate_script_match
from src.mapping.page_mapper import map_script_to_pages, generate_page_summary
from src.pdf.slide_extractor import extract_slide_texts
from src.pdf.pdf_generator import generate_pdf

WAIT_PDF, WAIT_SCRIPT, WAIT_CONFIRM = range(3)

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
        "또는 대본 텍스트 파일(.txt)을 전송해도 됩니다."
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
        "1/3 슬라이드 텍스트 추출 중..."
    )

    try:
        # 1단계: 슬라이드 추출
        slide_texts = extract_slide_texts(pdf_path)
        total_pages = len(slide_texts)
        await status_msg.edit_text(
            "⏳ 처리 중입니다...\n"
            f"✅ 1/3 슬라이드 {total_pages}페이지 추출 완료\n"
            "2/3 대본-슬라이드 일치 확인 중..."
        )

        # 2단계: 대본 일치 확인
        is_match, reason = await validate_script_match(slide_texts, raw_script)

        if not is_match:
            # 불일치 시 경고 후 계속할지 물어봄
            user_sessions[user_id].update({
                "raw_script": raw_script,
                "slide_texts": slide_texts,
                "total_pages": total_pages,
                "status_msg_id": status_msg.message_id,
            })
            await status_msg.edit_text(
                f"⚠️ 슬라이드와 대본이 다른 강의일 수 있습니다.\n"
                f"사유: {reason}\n\n"
                "그래도 계속 진행할까요?\n"
                "계속하려면 /continue, 취소하려면 /cancel"
            )
            return WAIT_CONFIRM

        # 일치하면 바로 다음 단계
        user_sessions[user_id].update({
            "raw_script": raw_script,
            "slide_texts": slide_texts,
            "total_pages": total_pages,
        })
        await status_msg.edit_text(
            "⏳ 처리 중입니다...\n"
            f"✅ 1/3 슬라이드 {total_pages}페이지 추출 완료\n"
            "✅ 2/3 대본-슬라이드 일치 확인 완료\n"
            "3/3 대본-슬라이드 매핑 중 (Gemini)..."
        )

        await process_mapping(update, ctx, user_id, status_msg)

    except Exception as e:
        await status_msg.edit_text(f"오류가 발생했습니다: {str(e)}\n/start로 다시 시도해 주세요.")
        return ConversationHandler.END

    return ConversationHandler.END


async def continue_anyway(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_sessions:
        await update.message.reply_text("세션이 만료됐습니다. /start로 다시 시작해주세요.")
        return ConversationHandler.END

    status_msg = await update.message.reply_text(
        "⏳ 처리 중입니다...\n"
        "✅ 슬라이드 추출 완료\n"
        "✅ 일치 확인 (경고 무시)\n"
        "대본-슬라이드 매핑 중 (Gemini)..."
    )
    user_sessions[user_id]["status_msg_id"] = status_msg.message_id

    await process_mapping(update, ctx, user_id, status_msg)
    return ConversationHandler.END


async def process_mapping(update, ctx, user_id, status_msg):
    session = user_sessions[user_id]
    raw_script = session["raw_script"]
    slide_texts = session["slide_texts"]
    total_pages = session["total_pages"]
    pdf_path = session["pdf_path"]

    try:
        # 매핑
        mappings = await map_script_to_pages(slide_texts, raw_script)
        await status_msg.edit_text(
            "⏳ 처리 중입니다...\n"
            f"✅ 슬라이드 {total_pages}페이지 추출 완료\n"
            "✅ 대본-슬라이드 매핑 완료\n"
            f"AI 요약 생성 중... (0/{total_pages}페이지)"
        )

        # 요약 생성
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
                f"✅ 슬라이드 {total_pages}페이지 추출 완료\n"
                "✅ 대본-슬라이드 매핑 완료\n"
                f"AI 요약 생성 중... ({batch_end}/{total_pages}페이지 완료)"
            )

        # PDF 생성
        await status_msg.edit_text(
            "⏳ 처리 중입니다...\n"
            f"✅ 슬라이드 {total_pages}페이지 추출 완료\n"
            "✅ 대본-슬라이드 매핑 완료\n"
            f"✅ AI 요약 {total_pages}페이지 완료\n"
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
            WAIT_CONFIRM: [CommandHandler("continue", continue_anyway)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv_handler)
    return app
