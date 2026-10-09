import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from drive_helper import upload_file_to_subject
from handlers import BannedMiddleware

drive_router = Router()
drive_router.message.middleware(BannedMiddleware())

pending_files = {}

@drive_router.message(F.document | F.photo)
async def handle_incoming_file(message: Message):
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
    else:
        file_id = message.photo[-1].file_id
        file_name = f"photo_{message.date.strftime('%Y%m%d_%H%M%S')}.jpg"

    pending_files[message.from_user.id] = {
        'file_id': file_id,
        'file_name': file_name
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📚 Философия", callback_data="drive_sub:Философия"),
            InlineKeyboardButton(text="💻 Программирование", callback_data="drive_sub:Программирование")
        ],
        [
            InlineKeyboardButton(text="📐 Высшая математика", callback_data="drive_sub:Высшая математика"),
            InlineKeyboardButton(text="🇬🇧 Английский язык", callback_data="drive_sub:Английский язык")
        ]
    ])

    await message.reply("📁 В какую папку сохранить файл на Google Диске?", reply_markup=kb)

@drive_router.callback_query(F.data.startswith("drive_sub:"))
async def process_drive_upload(callback: CallbackQuery, bot: Bot):
    subject = callback.data.split(":")[1]
    user_id = callback.from_user.id

    if user_id not in pending_files:
        await callback.answer("Файл не найден. Отправьте файл заново.", show_alert=True)
        return

    await callback.message.edit_text(f"⏳ Загружаю файл в папку **{subject}**...")

    file_info = pending_files.pop(user_id)
    
    try:
        tg_file = await bot.get_file(file_info['file_id'])
        downloaded_file = await bot.download_file(tg_file.file_path)

        # Выполняем синхронную загрузку в отдельном потоке, чтобы не блокировать бота
        drive_url = await asyncio.to_thread(
            upload_file_to_subject,
            file_bytes=downloaded_file.getvalue(),
            filename=file_info['file_name'],
            subject_name=subject
        )

        await callback.message.edit_text(
            f"✅ Файл успешно сохранён в папку **{subject}**!\n"
            f"🔗 [Открыть файл на Google Диске]({drive_url})",
            parse_mode="Markdown"
        )
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка при загрузке на Google Диск: {e}")