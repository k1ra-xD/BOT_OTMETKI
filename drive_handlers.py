import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from drive_helper import upload_file_to_subject
from handlers import BannedMiddleware, get_db_pool
from config import ADMIN_ID

drive_router = Router()
drive_router.message.middleware(BannedMiddleware())

# Хранилище для медиагрупп и одиночных файлов
pending_batches = {}  # {user_id: {'files': [...], 'task': asyncio_task}}
single_pending_files = {} # для одиночных файлов

@drive_router.message(F.document | F.photo)
async def handle_incoming_files(message: Message, bot: Bot):
    if message.from_user.id != ADMIN_ID:
        return

    user_id = message.from_user.id

    # Извлекаем файл
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
    else:
        file_id = message.photo[-1].file_id
        file_name = f"photo_{message.date.strftime('%Y%m%d_%H%M%S_%f')}.jpg"

    file_info = {'file_id': file_id, 'file_name': file_name}

    # Если пользователь еще не начинал собирать пачку или предыдущая уже ушла в меню
    if user_id not in pending_batches or 'timer_task' not in pending_batches[user_id]:
        pending_batches[user_id] = {
            'files': [],
            'chat_id': message.chat.id
        }

    # Добавляем файл в общую копилку текущей пачки
    pending_batches[user_id]['files'].append(file_info)

    # Перезапускаем таймер ожидания (даем время долететь всем частям большой пачки)
    if 'timer_task' in pending_batches[user_id] and pending_batches[user_id]['timer_task']:
        pending_batches[user_id]['timer_task'].cancel()

    async def send_album_prompt():
        # Увеличили задержку до 1.5 секунд, чтобы Telegram успел прислать все части тяжелой пачки
        await asyncio.sleep(1.5) 
        if user_id in pending_batches:
            data = pending_batches.pop(user_id)
            await show_subject_selection(bot, data['chat_id'], user_id, data['files'])

    pending_batches[user_id]['timer_task'] = asyncio.create_task(send_album_prompt())


async def show_subject_selection(bot: Bot, chat_id: int, user_id: int, files: list):
    buttons = []
    subject_map = {}
    pool = get_db_pool()

    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT DISTINCT subject FROM schedule WHERE subject IS NOT NULL AND subject != '' ORDER BY subject ASC")
            subjects = [r['subject'] for r in rows]

            row_buttons = []
            for i, subj in enumerate(subjects):
                subject_map[str(i)] = subj
                btn_text = f"📚 {subj[:25]}..." if len(subj) > 28 else f"📚 {subj}"
                row_buttons.append(InlineKeyboardButton(text=btn_text, callback_data=f"drive_sub:{i}"))
                
                if len(row_buttons) == 2:
                    buttons.append(row_buttons)
                    row_buttons = []
            if row_buttons:
                buttons.append(row_buttons)

    if not buttons:
        subject_map["default"] = "Общее"
        buttons.append([InlineKeyboardButton(text="📁 Общее", callback_data="drive_sub:default")])

    # Сохраняем файлы для этого пользователя под уникальным ключом выбора
    single_pending_files[user_id] = {
        'files': files,
        'subject_map': subject_map
    }

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    count = len(files)
    text = f"📁 Найдено файлов: **{count}**. В какую папку сохранить их на Google Диске?" if count > 1 else "📁 В какую папку сохранить файл на Google Диске?"
    await bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")


@drive_router.callback_query(F.data.startswith("drive_sub:"))
async def process_drive_upload(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав для загрузки файлов.", show_alert=True)
        return

    user_id = callback.from_user.id

    if user_id not in single_pending_files:
        await callback.answer("Файлы не найдены или сессия истекла. Отправьте их заново.", show_alert=True)
        return

    subj_key = callback.data.split(":")[1]
    batch_data = single_pending_files.pop(user_id)
    files = batch_data['files']
    subject = batch_data['subject_map'].get(subj_key, "Общее")

    total = len(files)
    await callback.message.edit_text(f"⏳ Начинаю загрузку {total} файл(ов) в папку **{subject}**...", parse_mode="Markdown")

    success_count = 0
    for idx, file_info in enumerate(files, 1):
        try:
            await callback.message.edit_text(
                f"⏳ Загрузка файла **{idx} из {total}** (`{file_info['file_name']}`) в папку **{subject}**...",
                parse_mode="Markdown"
            )

            tg_file = await bot.get_file(file_info['file_id'])
            downloaded_file = await bot.download_file(tg_file.file_path)

            await asyncio.to_thread(
                upload_file_to_subject,
                file_bytes=downloaded_file.getvalue(),
                filename=file_info['file_name'],
                subject_name=subject
            )
            success_count += 1
        except Exception as e:
            print(f"Ошибка загрузки файла {file_info['file_name']}: {e}")

    await callback.message.edit_text(
        f"✅ Успешно загружено файлов: **{success_count} из {total}** в папку **{subject}**!",
        parse_mode="Markdown"
    )