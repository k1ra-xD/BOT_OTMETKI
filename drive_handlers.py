import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from drive_helper import upload_file_to_subject
from handlers import BannedMiddleware, get_db_pool
from config import ADMIN_ID

drive_router = Router()
drive_router.message.middleware(BannedMiddleware())

pending_files = {}

@drive_router.message(F.document | F.photo)
async def handle_incoming_file(message: Message):
    # Ограничение прав: доступ к загрузке только у админа
    if message.from_user.id != ADMIN_ID:
        return

    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
    else:
        file_id = message.photo[-1].file_id
        file_name = f"photo_{message.date.strftime('%Y%m%d_%H%M%S')}.jpg"

    buttons = []
    subject_map = {}
    pool = get_db_pool()

    if pool:
        async with pool.acquire() as conn:
            # Получаем все уникальные предметы из расписания
            rows = await conn.fetch("SELECT DISTINCT subject FROM schedule WHERE subject IS NOT NULL AND subject != '' ORDER BY subject ASC")
            subjects = [r['subject'] for r in rows]

            # Формируем сетку из кнопок (по 2 предмета в ряд)
            # В callback_data передаем только короткий индекс i, чтобы уложиться в 64 байта
            row_buttons = []
            for i, subj in enumerate(subjects):
                subject_map[str(i)] = subj
                # Сокращаем текст на самой кнопке, если имя слишком длинное
                btn_text = f"📚 {subj[:25]}..." if len(subj) > 28 else f"📚 {subj}"
                row_buttons.append(InlineKeyboardButton(text=btn_text, callback_data=f"drive_sub:{i}"))
                
                if len(row_buttons) == 2:
                    buttons.append(row_buttons)
                    row_buttons = []
            if row_buttons:
                buttons.append(row_buttons)

    # Запасная кнопка, если расписание ещё не заполнено
    if not buttons:
        subject_map["default"] = "Общее"
        buttons.append([InlineKeyboardButton(text="📁 Общее", callback_data="drive_sub:default")])

    # Сохраняем данные файла и карту предметов для текущего пользователя
    pending_files[message.from_user.id] = {
        'file_id': file_id,
        'file_name': file_name,
        'subject_map': subject_map
    }

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.reply("📁 В какую папку сохранить файл на Google Диске?", reply_markup=kb)

@drive_router.callback_query(F.data.startswith("drive_sub:"))
async def process_drive_upload(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав для загрузки файлов.", show_alert=True)
        return

    user_id = callback.from_user.id

    if user_id not in pending_files:
        await callback.answer("Файл не найден или сессия истекла. Отправьте файл заново.", show_alert=True)
        return

    subj_key = callback.data.split(":")[1]
    file_info = pending_files.pop(user_id)
    subject = file_info['subject_map'].get(subj_key, "Общее")

    await callback.message.edit_text(f"⏳ Загружаю файл в папку **{subject}**...", parse_mode="Markdown")

    try:
        tg_file = await bot.get_file(file_info['file_id'])
        downloaded_file = await bot.download_file(tg_file.file_path)

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