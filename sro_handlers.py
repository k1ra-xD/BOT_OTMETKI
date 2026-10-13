import asyncio
from config import ADMIN_ID, ADMIN_NAME
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from handlers import BannedMiddleware, get_db_pool
from sro_helper import upload_sro_file, get_existing_student_folders

sro_router = Router()
sro_router.message.middleware(BannedMiddleware())
sro_router.callback_query.middleware(BannedMiddleware())

class SroStates(StatesGroup):
    waiting_for_subject = State()
    waiting_for_sro_choice = State()
    waiting_for_sro_num = State()
    waiting_for_custom_num = State()
    waiting_for_files = State()

pending_sro_batches = {}

@sro_router.message(F.text == "📤 Сдать СРО")
async def start_sro_submission(message: Message, state: FSMContext):
    pool = get_db_pool()
    if not pool:
        return await message.answer("⚠️ Ошибка подключения к базе данных. Попробуйте позже.")

    # Проверяем, зарегистрирован ли студент
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT full_name FROM students WHERE telegram_id = $1", message.from_user.id)

    if row:
        student_name = row['full_name']
    elif message.from_user.id == ADMIN_ID:
        student_name = ADMIN_NAME  # Берет ваше Ф.И из config.py
    else:
        return await message.answer(
            "⚠️ Вы ещё не зарегистрированы в боте. Отправьте команду /start и введите своё Имя и Фамилию."
        )
    else:
        student_name = row['full_name']

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
        f"📖 Выберите предмет, по которому вы хотите сдать работу:",
        reply_markup=kb,
        parse_mode="HTML"
    )

@sro_router.callback_query(F.data == "sro_cancel")
async def cancel_sro(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Сдача СРО отменена.")
    await callback.answer()

async def render_new_sro_grid(callback: CallbackQuery, selected_subject: str, state: FSMContext):
    """Показывает стандартную сетку для создания новой папки/задания."""
    await state.set_state(SroStates.waiting_for_sro_num)

    grid_buttons = []
    row = []
    for num in range(1, 11):
        row.append(InlineKeyboardButton(text=f"СРО {num}", callback_data=f"sro_num:СРО {num}"))
        if len(row) == 2:
            grid_buttons.append(row)
            row = []
    if row:
        grid_buttons.append(row)

    grid_buttons.append([InlineKeyboardButton(text="✏️ Ввести другое название / тему", callback_data="sro_num:manual")])
    grid_buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="sro_cancel")])

    kb = InlineKeyboardMarkup(inline_keyboard=grid_buttons)
    await callback.message.edit_text(
        f"✅ <b>Предмет:</b> {selected_subject}\n\n"
        f"🔢 <b>Выберите номер нового СРО или введите своё название:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@sro_router.callback_query(SroStates.waiting_for_subject, F.data.startswith("sro_sub:"))
async def process_subject_chosen(callback: CallbackQuery, state: FSMContext):
    subj_key = callback.data.split(":")[1]
    data = await state.get_data()
    subject_map = data.get('subject_map', {})
    selected_subject = subject_map.get(subj_key, "Общее")
    student_name = data.get('student_name', "")

    await state.update_data(selected_subject=selected_subject)

    # Проверяем существующие папки на Диске
    await callback.message.edit_text(f"🔍 Проверяю ваши папки по предмету <b>{selected_subject}</b>...", parse_mode="HTML")
    existing_folders = await asyncio.to_thread(get_existing_student_folders, student_name, selected_subject)

    if existing_folders:
        await state.set_state(SroStates.waiting_for_sro_choice)
        exist_map = {str(i): name for i, name in enumerate(existing_folders)}
        await state.update_data(exist_map=exist_map)

        buttons = []
        row = []
        for i, name in enumerate(existing_folders):
            btn_title = f"📁 {name[:20]}..." if len(name) > 23 else f"📁 {name}"
            row.append(InlineKeyboardButton(text=btn_title, callback_data=f"sro_exist:{i}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        buttons.append([InlineKeyboardButton(text="➕ Создать новую папку / СРО", callback_data="sro_create_new")])
        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="sro_cancel")])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text(
            f"✅ <b>Предмет:</b> {selected_subject}\n\n"
            f"📂 <b>У вас уже есть созданные папки.</b>\n"
            f"Выберите папку, чтобы <u>добавить файлы</u> в неё, либо создайте новую:",
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        # Если папок еще нет — открываем выбор нового номера
        await render_new_sro_grid(callback, selected_subject, state)

    await callback.answer()

@sro_router.callback_query(SroStates.waiting_for_sro_choice, F.data == "sro_create_new")
async def choose_create_new(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_subject = data.get('selected_subject', "Общее")
    await render_new_sro_grid(callback, selected_subject, state)
    await callback.answer()

@sro_router.callback_query(SroStates.waiting_for_sro_choice, F.data.startswith("sro_exist:"))
async def process_existing_folder_chosen(callback: CallbackQuery, state: FSMContext):
    idx = callback.data.split(":")[1]
    data = await state.get_data()
    exist_map = data.get('exist_map', {})
    sro_num = exist_map.get(idx, "СРО 1")
    selected_subject = data.get('selected_subject', "Общее")

    await state.update_data(sro_num=sro_num)
    await state.set_state(SroStates.waiting_for_files)

    await callback.message.edit_text(
        f"📖 <b>Предмет:</b> {selected_subject}\n"
        f"📂 <b>Выбрана папка:</b> <code>{sro_num}</code>\n\n"
        f"📎 Отправьте файлы (Word, PDF, архивы, фото).\n"
        f"<i>Они будут добавлены в эту же папку на Диске.</i>\n\n"
        f"Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await callback.answer()

@sro_router.callback_query(SroStates.waiting_for_sro_num, F.data == "sro_num:manual")
async def ask_manual_sro_num(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SroStates.waiting_for_custom_num)
    await callback.message.edit_text(
        "✏️ <b>Введите номер или название работы:</b>\n\n"
        "<i>Например: <code>12</code>, <code>Лабораторная 3</code> или <code>Курсовая</code></i>\n\n"
        "Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await callback.answer()

@sro_router.message(SroStates.waiting_for_custom_num, F.text)
async def process_manual_sro_input(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        return await message.answer("❌ Загрузка отменена.")

    text = message.text.strip()
    sro_num = f"СРО {text}" if text.isdigit() else text

    await state.update_data(sro_num=sro_num)
    await state.set_state(SroStates.waiting_for_files)

    data = await state.get_data()
    selected_subject = data.get('selected_subject', "Общее")

    await message.answer(
        f"📖 <b>Предмет:</b> {selected_subject}\n"
        f"📑 <b>Раздел:</b> {sro_num}\n\n"
        f"📎 Теперь отправьте <b>файл или несколько файлов</b>.\n"
        f"<i>Бот сохранит работы в папку «{sro_num}» на Google Диске.</i>\n\n"
        f"Для отмены отправьте /cancel",
        parse_mode="HTML"
    )

@sro_router.callback_query(SroStates.waiting_for_sro_num, F.data.startswith("sro_num:"))
async def process_sro_num_chosen(callback: CallbackQuery, state: FSMContext):
    sro_num = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected_subject = data.get('selected_subject', "Общее")

    await state.update_data(sro_num=sro_num)
    await state.set_state(SroStates.waiting_for_files)

    await callback.message.edit_text(
        f"📖 <b>Предмет:</b> {selected_subject}\n"
        f"📑 <b>Раздел:</b> {sro_num}\n\n"
        f"📎 Отправьте <b>один или несколько файлов</b>.\n"
        f"<i>Бот автоматически сложит их в папку «{sro_num}» на Google Диске.</i>\n\n"
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
    sro_num = state_data.get('sro_num', "СРО 1")

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

    if 'timer_task' in pending_sro_batches[user_id] and pending_sro_batches[user_id]['timer_task']:
        pending_sro_batches[user_id]['timer_task'].cancel()

    async def execute_upload():
        await asyncio.sleep(1.5)
        if user_id in pending_sro_batches:
            batch = pending_sro_batches.pop(user_id)
            files = batch['files']
            total = len(files)

            status_msg = await bot.send_message(
                batch['chat_id'],
                f"⏳ Получено файлов: <b>{total}</b>. Начинаю загрузку в <b>{sro_num}</b>...",
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
                        subject_name=selected_subject,
                        sro_num=sro_num
                    )
                    success_count += 1
                except Exception as e:
                    print(f"Ошибка загрузки СРО: {e}")

            await status_msg.edit_text(
                f"🎉 <b>Файлы успешно сохранены!</b>\n\n"
                f"👤 <b>Студент:</b> {student_name}\n"
                f"📖 <b>Предмет:</b> {selected_subject}\n"
                f"📂 <b>Папка:</b> <code>{sro_num}</code>\n"
                f"📊 <b>Загружено файлов:</b> {success_count} из {total}",
                parse_mode="HTML"
            )
            await state.clear()

    pending_sro_batches[user_id]['timer_task'] = asyncio.create_task(execute_upload())