import io
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from config import ADMIN_ID
from db import add_island_task, get_active_island_tasks, mark_island_task_completed
from voice_helper import transcribe_audio_bytes, parse_task_time_and_title

island_router = Router()

# Ограничиваем весь роутер только для администратора (Георгия)
island_router.message.filter(F.from_user.id == ADMIN_ID)
island_router.callback_query.filter(F.from_user.id == ADMIN_ID)

@island_router.message(F.voice)
async def handle_voice_task(message: Message, bot: Bot):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return

    status_msg = await message.answer("🎧 <i>Слушаю и расшифровываю голосовое...</i>", parse_mode="HTML")

    try:
        voice = message.voice
        voice_file = await bot.get_file(voice.file_id)
        
        file_buffer = io.BytesIO()
        await bot.download_file(voice_file.file_path, file_buffer)
        audio_bytes = file_buffer.getvalue()

        # Распознаем речь
        transcribed_text = await transcribe_audio_bytes(audio_bytes, filename=f"voice_{voice.file_id}.ogg")

        if not transcribed_text:
            return await status_msg.edit_text(
                "⚠️ <b>Не удалось распознать голосовое сообщение.</b>\n\n"
                "💡 <i>Подсказка:</i> для работы распознавания голоса добавьте в переменные окружения Render бесплатный ключ <code>GROQ_API_KEY</code> (создается за 10 секунд на <a href='https://console.groq.com'>console.groq.com</a>).\n\n"
                "Вы также можете просто отправить задачу текстом: <code>/task сдать СРО завтра в 14:00</code>",
                parse_mode="HTML",
                disable_web_page_preview=True
            )

        # Выделяем название задачи и время
        title, target_date, target_time = parse_task_time_and_title(transcribed_text)

        # Сохраняем в базу данных
        from handlers import get_db_pool
        pool = get_db_pool()
        task = await add_island_task(pool, user_id, title, target_date, target_time)

        time_str = f" в {target_time}" if target_time else ""

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Выполнено", callback_data=f"itask_done:{task['id'] if task else 0}"),
                InlineKeyboardButton(text="📋 Все задачи", callback_data="itask_list")
            ]
        ])

        await status_msg.edit_text(
            f"🎙️ <b>Распознано:</b> <i>«{transcribed_text}»</i>\n\n"
            f"🏝️ <b>Задача для Dynamic Island сохранена!</b>\n"
            f"📌 <b>Дело:</b> {title}\n"
            f"⏰ <b>Срок:</b> {target_date}{time_str}\n\n"
            f"🔊 <i>Dynamic Island на компьютере напомнит и проговорит эту задачу вслух!</i>",
            parse_mode="HTML",
            reply_markup=kb
        )

    except Exception as e:
        print(f"Ошибка обработки голосового: {e}")
        await status_msg.edit_text(f"⚠️ Ошибка при обработке аудио: {e}")

@island_router.message(Command("task", "remind", "todo"))
async def handle_text_task(message: Message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return

    raw_text = message.text or ""
    parts = raw_text.split(maxsplit=1)
    
    if len(parts) < 2 or not parts[1].strip():
        return await message.answer(
            "📝 <b>Как создать задачу для Dynamic Island:</b>\n\n"
            "• Просто отправьте <b>голосовое сообщение</b> 🎙️\n"
            "• Либо напишите команду: <code>/task сдать СРО завтра в 14:00</code>",
            parse_mode="HTML"
        )

    task_content = parts[1].strip()
    title, target_date, target_time = parse_task_time_and_title(task_content)

    from handlers import get_db_pool
    pool = get_db_pool()
    task = await add_island_task(pool, user_id, title, target_date, target_time)

    time_str = f" в {target_time}" if target_time else ""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выполнено", callback_data=f"itask_done:{task['id'] if task else 0}"),
            InlineKeyboardButton(text="📋 Все задачи", callback_data="itask_list")
        ]
    ])

    await message.answer(
        f"🏝️ <b>Задача для Dynamic Island сохранена!</b>\n\n"
        f"📌 <b>Дело:</b> {title}\n"
        f"⏰ <b>Срок:</b> {target_date}{time_str}\n\n"
        f"🔊 <i>Dynamic Island на компьютере напомнит и проговорит эту задачу вслух!</i>",
        parse_mode="HTML",
        reply_markup=kb
    )

@island_router.message(Command("tasks"))
async def handle_list_tasks(message: Message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return
    await show_tasks_list(message, user_id)

async def show_tasks_list(message_or_query, user_id: int):
    if user_id != ADMIN_ID:
        return

    from handlers import get_db_pool
    pool = get_db_pool()
    tasks = await get_active_island_tasks(pool, user_id)

    if not tasks:
        text = "🏝️ <b>Задач для Dynamic Island нет!</b>\nВсе дела выполнены ✨"
        if isinstance(message_or_query, CallbackQuery):
            await message_or_query.message.edit_text(text, parse_mode="HTML")
        else:
            await message_or_query.answer(text, parse_mode="HTML")
        return

    text = "📋 <b>Активные задачи Dynamic Island:</b>\n\n"
    buttons = []
    for i, t in enumerate(tasks, 1):
        t_time = f" ({t['target_time']})" if t.get('target_time') else ""
        text += f"<b>{i}.</b> {t['title']} — <i>{t.get('target_date', '')}{t_time}</i>\n"
        buttons.append([
            InlineKeyboardButton(text=f"✅ Выполнить: {t['title'][:20]}...", callback_data=f"itask_done:{t['id']}")
        ])

    buttons.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="itask_list")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    if isinstance(message_or_query, CallbackQuery):
        await message_or_query.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message_or_query.answer(text, parse_mode="HTML", reply_markup=kb)

@island_router.callback_query(F.data.startswith("itask_done:"))
async def handle_task_done_callback(query: CallbackQuery):
    if query.from_user.id != ADMIN_ID:
        return await query.answer("Доступно только администратору.", show_alert=True)

    task_id_str = query.data.split(":")[1]
    if task_id_str.isdigit():
        task_id = int(task_id_str)
        from handlers import get_db_pool
        pool = get_db_pool()
        row = await mark_island_task_completed(pool, task_id)
        if row:
            await query.answer("Задача отмечена выполненной! 🎉")
            await show_tasks_list(query, query.from_user.id)
            return
    await query.answer("Не удалось завершить задачу.")

@island_router.callback_query(F.data == "itask_list")
async def handle_task_list_callback(query: CallbackQuery):
    if query.from_user.id != ADMIN_ID:
        return await query.answer("Доступно только администратору.", show_alert=True)
    await show_tasks_list(query, query.from_user.id)
    await query.answer()
