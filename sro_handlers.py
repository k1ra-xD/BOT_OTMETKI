import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from handlers import BannedMiddleware, get_db_pool
from sro_helper import upload_sro_file

sro_router = Router()
sro_router.message.middleware(BannedMiddleware())
sro_router.callback_query.middleware(BannedMiddleware())

class SroStates(StatesGroup):
    waiting_for_subject = State()
    waiting_for_files = State()

# Буфер для приема файлов/пачек от студентов
pending_sro_batches = {}

@sro_router.message(F.text == "📤 Сдать СРО")
async def start_sro_submission(message: Message, state: FSMContext):
    pool = get_db_pool()
    if not pool:
        return await message.answer("⚠️ Ошибка подключения к базе данных. Попробуйте позже.")

    # Проверяем, зарегистрирован ли студент
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT full_name FROM students WHERE telegram_id = $1", message.from_user.id)

    if not row:
        return await message.answer(
            "⚠️ Вы ещё не зарегистрированы в боте. Отправьте команду /start и введите своё Имя и Фамилию."
        )

    student_name = row['full_name']

    # Получаем список предметов из расписания
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT DISTINCT subject FROM schedule WHERE subject IS NOT NULL AND subject != '' ORDER BY subject ASC")
        subjects = [r['subject'] for r in rows]

    buttons = []
    subject_map = {}

    if subjects:
        row_buttons = []
        for i, subj in enumerate(subjects):
            subject_map[str(i)] = subj
            btn_text = f"📚 {subj[:25]}..." if len(subj) > 28 else f"📚 {subj}"
            row_buttons.append(InlineKeyboardButton(text=btn_text, callback_data=f"sro_sub:{i}"))
            if len(row_buttons) == 2:
                buttons.append(row_buttons)
                row_buttons = []
        if row_buttons:
            buttons.append(row_buttons)
    else:
        subject_map["default"] = "Общее"
        buttons.append([InlineKeyboardButton(text="📁 Общее", callback_data="sro_sub:default")])

    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="sro_cancel")])

    await state.set_state(SroStates.waiting_for_subject)
    await state.update_data(student_name=student_name, subject_map=subject_map)

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(
        f"👤 <b>Студент:</b> {student_name}\n"
        f"📖 Выберите предмет, по которому вы хотите сдать СРО/лабораторную:",
        reply_markup=kb,
        parse_mode="HTML"
    )

@sro_router.callback_query(SroStates.waiting_for_subject, F.data == "sro_cancel")
async def cancel_sro(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Сдача СРО отменена.")
    await callback.answer()

@sro_router.callback_query(SroStates.waiting_for_subject, F.data.startswith("sro_sub:"))
async def process_subject_chosen(callback: CallbackQuery, state: FSMContext):
    subj_key = callback.data.split(":")[1]
    data = await state.get_data()
    subject_map = data.get('subject_map', {})
    selected_subject = subject_map.get(subj_key, "Общее")

    await state.update_data(selected_subject=selected_subject)
    await state.set_state(SroStates.waiting_for_files)

    await callback.message.edit_text(
        f"✅ <b>Предмет выбран:</b> {selected_subject}\n\n"
        f"📎 Теперь отправьте <b>файл или несколько файлов</b> (документы Word, PDF, фото, архив).\n"
        f"<i>После отправки бот автоматически загрузит их в вашу папку на Диске.</i>\n\n"
        f"Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await callback.answer()

@sro_router.message(SroStates.waiting_for_files, F.text == "/cancel")
async def cancel_waiting_files(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Загрузка файлов отменена.")

@sro_router.message(SroStates.waiting_for_files, F.document | F.photo)
async def handle_sro_files(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    state_data = await state.get_data()
    student_name = state_data.get('student_name', f"Студент_{user_id}")
    selected_subject = state_data.get('selected_subject', "Общее")

    # Извлечение файла
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or "document"
    else:
        file_id = message.photo[-1].file_id
        file_name = f"photo_{message.date.strftime('%Y%m%d_%H%M%S_%f')}.jpg"

    file_info = {'file_id': file_id, 'file_name': file_name}

    if user_id not in pending_sro_batches:
        pending_sro_batches[user_id] = {
            'files': [],
            'chat_id': message.chat.id
        }

    pending_sro_batches[user_id]['files'].append(file_info)

    # Сбрасываем таймер ожидания пачки
    if 'timer_task' in pending_sro_batches[user_id] and pending_sro_batches[user_id]['timer_task']:
        pending_sro_batches[user_id]['timer_task'].cancel()

    async def execute_upload():
        # Ждем 1.5 сек, пока прилетят все файлы из альбома
        await asyncio.sleep(1.5)
        if user_id in pending_sro_batches:
            batch = pending_sro_batches.pop(user_id)
            files = batch['files']
            total = len(files)

            status_msg = await bot.send_message(
                batch['chat_id'],
                f"⏳ Получено файлов: <b>{total}</b>. Начинаю загрузку на Google Диск...",
                parse_mode="HTML"
            )

            success_count = 0
            for idx, f_item in enumerate(files, 1):
                try:
                    await status_msg.edit_text(
                        f"⏳ Загрузка ({idx}/{total}): <code>{f_item['file_name']}</code>...",
                        parse_mode="HTML"
                    )
                    tg_file = await bot.get_file(f_item['file_id'])
                    downloaded_file = await bot.download_file(tg_file.file_path)

                    await asyncio.to_thread(
                        upload_sro_file,
                        file_bytes=downloaded_file.getvalue(),
                        filename=f_item['file_name'],
                        student_name=student_name,
                        subject_name=selected_subject
                    )
                    success_count += 1
                except Exception as e:
                    print(f"Ошибка загрузки СРО: {e}")

            await status_msg.edit_text(
                f"🎉 <b>СРО успешно сдано!</b>\n\n"
                f"👤 <b>Студент:</b> {student_name}\n"
                f"📖 <b>Предмет:</b> {selected_subject}\n"
                f"📂 <b>Загружено файлов:</b> {success_count} из {total}\n\n"
                f"<i>Все файлы сохранены в папку СРО на Диске.</i>",
                parse_mode="HTML"
            )
            await state.clear()

    pending_sro_batches[user_id]['timer_task'] = asyncio.create_task(execute_upload())