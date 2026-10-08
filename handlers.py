import math
import asyncio
from datetime import datetime
from aiogram import Bot, Router, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, 
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove, WebAppInfo
)

from config import ADMIN_ID, DEFAULT_RADIUS, DEFAULT_UNI_LAT, DEFAULT_UNI_LON, DAYS_MAP, ASTANA_TZ, TARGET_GROUP
from db import get_setting, set_setting
from parser import download_schedule_file, parse_excel_schedule

router = Router()

class RegStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_radius = State()
    waiting_for_ban_id = State()
    waiting_for_unban_id = State()
    waiting_for_uni_location = State()

class ScheduleAdminStates(StatesGroup):
    waiting_for_schedule_text = State()

current_session = {
    "is_active": False,
    "responses": {}
}

db_pool_ref = None

def set_db_pool(pool):
    global db_pool_ref
    db_pool_ref = pool

def get_db_pool():
    return db_pool_ref

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000   
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# Middleware проверки бана
class BannedMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data):
        user = data.get("event_from_user")
        if user and user.id != ADMIN_ID:
            async with get_db_pool().acquire() as conn:
                banned = await conn.fetchrow("SELECT telegram_id FROM banned_users WHERE telegram_id = $1", user.id)
            if banned:
                if isinstance(event, Message):
                    await event.answer("⛔️ Доступ закрыт. Вы заблокированы администратором.", reply_markup=ReplyKeyboardRemove())
                return
        return await handler(event, data)

router.message.middleware(BannedMiddleware())

# Клавиатуры ДЛЯ СТУДЕНТОВ (обычные кнопки, БЕЗ WebApp)
student_main_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📅 Расписание"), KeyboardButton(text="📍 Отметиться")]],
    resize_keyboard=True
)

schedule_inline_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="Сегодня", callback_data="sched_today"),
        InlineKeyboardButton(text="Завтра", callback_data="sched_tomorrow")
    ],
    [InlineKeyboardButton(text="📅 На всю неделю", callback_data="sched_week")]
])

# Команда /start
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    # Раздел только для Администратора (здесь есть WebApp Дашборд)
    if message.from_user.id == ADMIN_ID:
        pool = get_db_pool()
        radius = await get_setting(pool, 'radius', DEFAULT_RADIUS)
        lat = await get_setting(pool, 'lat', DEFAULT_UNI_LAT)
        lon = await get_setting(pool, 'lon', DEFAULT_UNI_LON)
        
        admin_kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🟢 Проверить присутствие"), KeyboardButton(text="🔴 Завершить проверку")],
                [KeyboardButton(text="👀 Кто ответил"), KeyboardButton(text="🎯 Установить центр ВУЗа")],
                [KeyboardButton(text="👥 Список студентов"), KeyboardButton(text="🗑 Удалить студента")],
                [KeyboardButton(text="🚫 Блокировать ID"), KeyboardButton(text="✅ Разблокировать ID")],
                [KeyboardButton(text="⚙️ Изменить радиус зоны"), KeyboardButton(text="📅 Расписание")]
            ],
            resize_keyboard=True
        )

        admin_inline_panel = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 WebApp Дашборд", web_app=WebAppInfo(url="https://bot-otmetki.onrender.com/dashboard"))],
            [InlineKeyboardButton(text="🔄 Авто-обновить с сайта (esil.edu.kz)", callback_data="admin_auto_update_schedule")],
            [InlineKeyboardButton(text="✏️ Ввести расписание вручную", callback_data="admin_edit_schedule")]
        ])

        await message.answer(
            f"👋 <b>Панель администратора</b>\n\n"
            f"📍 Координаты ВУЗа: <code>{lat}, {lon}</code>\n"
            f"📏 Радиус зоны: <b>{radius}м</b>",
            reply_markup=admin_kb,
            parse_mode="HTML"
        )
        await message.answer("Управление расписанием и статистикой:", reply_markup=admin_inline_panel)
        return

    # Раздел для Студентов (ТОЛЬКО обычное меню)
    async with get_db_pool().acquire() as conn:
        row = await conn.fetchrow("SELECT full_name FROM students WHERE telegram_id = $1", message.from_user.id)

    if row:
        await message.answer(f"Привет, {row['full_name']}! Вы зарегистрированы в системе.", reply_markup=student_main_kb)
    else:
        await message.answer("Привет! Для регистрации отправьте свои **Имя и Фамилию** (например: *Иван Иванов*).")
        await state.set_state(RegStates.waiting_for_name)

@router.message(RegStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    full_name = message.text.strip()
    if len(full_name.split()) < 2:
        await message.answer("Пожалуйста, введите корректно Имя и Фамилию.")
        return

    async with get_db_pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO students (telegram_id, full_name) VALUES ($1, $2)
            ON CONFLICT (telegram_id) DO UPDATE SET full_name = EXCLUDED.full_name
        """, message.from_user.id, full_name)

    await state.clear()
    await message.answer(f"Спасибо, {full_name}! Регистрация прошла успешно.", reply_markup=student_main_kb)

# Просмотр расписания
@router.message(F.text == "📅 Расписание")
async def show_schedule_menu(message: Message):
    await message.answer("Выберите период для просмотра расписания:", reply_markup=schedule_inline_kb)

async def format_day_schedule(conn, day_code: int) -> str:
    lessons = await conn.fetch("SELECT * FROM schedule WHERE day_of_week = $1 ORDER BY time_start ASC", day_code)
    day_name = DAYS_MAP.get(day_code, "")
    if not lessons:
        return f"<b>{day_name}:</b>\n🎉 Парочек нет, отдыхаем!\n"
    
    text = f"🗓 <b>{day_name}:</b>\n\n"
    for l in lessons:
        teacher_str = f"👨‍🏫 {l['teacher']} | " if l['teacher'] != 'не указан' else ""
        text += (
            f"⏰ <code>{l['time_start']} - {l['time_end']}</code>\n"
            f"📖 <b>{l['subject']}</b> ({l['lesson_type']})\n"
            f"{teacher_str}🚪 <b>{l['room']}</b>\n"
            f"-------------------------------\n"
        )
    return text

@router.callback_query(F.data.startswith("sched_"))
async def process_schedule_callback(callback: CallbackQuery):
    now = datetime.now(ASTANA_TZ)
    async with get_db_pool().acquire() as conn:
        if callback.data == "sched_today":
            text = await format_day_schedule(conn, now.weekday())
        elif callback.data == "sched_tomorrow":
            text = await format_day_schedule(conn, (now.weekday() + 1) % 7)
        elif callback.data == "sched_week":
            text = "📅 <b>Расписание на всю неделю:</b>\n\n"
            for d in range(5):
                text += await format_day_schedule(conn, d) + "\n"
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=schedule_inline_kb)
    await callback.answer()

# Авто-обновление расписания (только админ)
async def update_schedule_workflow(status_msg: Message):
    try:
        await status_msg.edit_text("⏳ <b>[1/5]</b> Подключение к <code>esil.edu.kz</code> и поиск файла...", parse_mode="HTML")
        await asyncio.to_thread(download_schedule_file)
        await status_msg.edit_text("✅ <b>[1/5]</b> Файл скачан!\n⏳ <b>[2/5]</b> Открытие структуры Excel...", parse_mode="HTML")
    except Exception as e:
        await status_msg.edit_text(f"❌ <b>Ошибка скачивания:</b> {e}", parse_mode="HTML")
        return

    try:
        await status_msg.edit_text("⏳ <b>[3/5]</b> Разбор структуры и объединений ячеек...", parse_mode="HTML")
        parsed_lessons = await asyncio.to_thread(parse_excel_schedule)
        
        step4_text = (
            f"✅ <b>[4/5]</b> Извлечение завершено! Найдено пар: <b>{len(parsed_lessons)}</b>.\n"
            f"⏳ <b>[5/5]</b> Сохранение расписания в Supabase..."
        )
        await status_msg.edit_text(step4_text, parse_mode="HTML")
    except Exception as e:
        await status_msg.edit_text(f"❌ <b>Ошибка при разборе Excel:</b> {e}", parse_mode="HTML")
        return

    try:
        async with get_db_pool().acquire() as conn:
            await conn.execute("TRUNCATE TABLE schedule")
            for item in parsed_lessons:
                await conn.execute("""
                    INSERT INTO schedule (day_of_week, time_start, time_end, subject, lesson_type, teacher, room)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, *item)

        summary = f"🎉 <b>Расписание успешно обновлено в Supabase!</b>\n\n"
        summary += f"👥 <b>Группа:</b> <code>{TARGET_GROUP}</code>\n"
        summary += f"📊 <b>Всего предметов:</b> {len(parsed_lessons)}\n\n"

        by_day = {}
        for l in parsed_lessons:
            by_day.setdefault(l[0], []).append(l)

        for day_code in sorted(by_day.keys()):
            summary += f"• <b>{DAYS_MAP.get(day_code, '')}:</b> {len(by_day[day_code])} пар(ы)\n"

        await status_msg.edit_text(summary, parse_mode="HTML")
    except Exception as e:
        await status_msg.edit_text(f"❌ <b>Ошибка записи в БД:</b> {e}", parse_mode="HTML")

@router.callback_query(F.data == "admin_auto_update_schedule")
async def start_auto_schedule_update(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("У вас нет прав.", show_alert=True)
    await callback.answer()
    status_msg = await callback.message.answer("🚀 <b>Начинаю процесс обновления расписания...</b>", parse_mode="HTML")
    asyncio.create_task(update_schedule_workflow(status_msg))

# Ручной ввод расписания
@router.callback_query(F.data == "admin_edit_schedule")
async def start_schedule_edit(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("У вас нет прав.", show_alert=True)
    await state.set_state(ScheduleAdminStates.waiting_for_schedule_text)
    await callback.message.answer(
        "📝 <b>Отправьте расписание текстом:</b>\n\n"
        "<code>Понедельник\n"
        "10.00-10.50 Предмет, лекция, Преподаватель ауд 211</code>\n\n"
        "Для отмены: /cancel", parse_mode="HTML"
    )
    await callback.answer()

@router.message(ScheduleAdminStates.waiting_for_schedule_text)
async def process_new_schedule_text(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        return await message.answer("Обновление расписания отменено.")
    
    lines = message.text.strip().split("\n")
    current_day = None
    parsed_items = []
    day_mapping = {"понедельник": 0, "вторник": 1, "среда": 2, "четверг": 3, "пятница": 4, "суббота": 5, "воскресенье": 6}

    try:
        for line in lines:
            line_clean = line.strip()
            if not line_clean: continue
            if line_clean.lower() in day_mapping:
                current_day = day_mapping[line_clean.lower()]
                continue
            if current_day is not None and "-" in line_clean:
                parts = line_clean.split(" ", 1)
                times = parts[0].replace(".", ":").split("-")
                t_start, t_end = times[0], times[1]
                details = parts[1] if len(parts) > 1 else ""
                room = "не указана"
                if "ауд" in details.lower():
                    details_split = details.lower().split("ауд")
                    room = "ауд " + details_split[1].strip(" .")
                    details = details[:details.lower().find("ауд")]
                elif "онлайн" in details.lower():
                    room = "Онлайн"
                parsed_items.append((current_day, t_start, t_end, details.strip(", "), "занятие", "не указан", room))

        if not parsed_items:
            return await message.answer("⚠️ Не удалось распознать формат. Нажмите /cancel.")

        async with get_db_pool().acquire() as conn:
            await conn.execute("TRUNCATE TABLE schedule")
            for item in parsed_items:
                await conn.execute("""
                    INSERT INTO schedule (day_of_week, time_start, time_end, subject, lesson_type, teacher, room)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, *item)

        await state.clear()
        await message.answer("✅ <b>Расписание обновлено вручную!</b>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# Проверка присутствия и Геопозиция
@router.message(F.text == "🟢 Проверить присутствие")
async def cmd_start_check(message: Message, bot: Bot):
    if message.from_user.id != ADMIN_ID: return
    current_session["is_active"] = True
    current_session["responses"].clear()
    
    geo_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📍 Я в ВУЗе (Отправить гео)", request_location=True)]], resize_keyboard=True, one_time_keyboard=True)
    async with get_db_pool().acquire() as conn:
        students = await conn.fetch("SELECT telegram_id FROM students")

    count = 0
    for row in students:
        try:
            await bot.send_message(row['telegram_id'], "⚠️ <b>Проверка присутствия!</b>\nОтправьте геопозицию:", reply_markup=geo_kb, parse_mode="HTML")
            count += 1
        except Exception: pass

    await message.answer(f"🚀 <b>Проверка запущена!</b> Запросы отправлены ({count} чел.).", parse_mode="HTML")

@router.message(F.text == "📍 Отметиться")
async def student_manual_checkin(message: Message):
    if not current_session["is_active"]: return await message.answer("Сейчас нет активной проверки.")
    geo_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📍 Я в ВУЗе (Отправить гео)", request_location=True)]], resize_keyboard=True, one_time_keyboard=True)
    await message.answer("Отправьте геопозицию:", reply_markup=geo_kb)

@router.message(F.location)
async def handle_location(message: Message, state: FSMContext):
    current_state = await state.get_state()
    pool = get_db_pool()

    if current_state == RegStates.waiting_for_uni_location.state:
        if message.from_user.id != ADMIN_ID: return
        await set_setting(pool, 'lat', message.location.latitude)
        await set_setting(pool, 'lon', message.location.longitude)
        await state.clear()
        return await message.answer("✅ Координаты ВУЗа сохранены!", parse_mode="HTML")

    if not current_session["is_active"]:
        return await message.answer("Сейчас нет активной проверки.", reply_markup=ReplyKeyboardRemove())

    if message.from_user.id in current_session["responses"]:
        return await message.answer("⚠️ Вы уже отправляли геопозицию.", reply_markup=ReplyKeyboardRemove())

    lat, lon = message.location.latitude, message.location.longitude
    uni_lat = await get_setting(pool, 'lat', DEFAULT_UNI_LAT)
    uni_lon = await get_setting(pool, 'lon', DEFAULT_UNI_LON)
    dist = calculate_distance(uni_lat, uni_lon, lat, lon)

    current_session["responses"][message.from_user.id] = {"lat": lat, "lon": lon, "dist": dist}
    await message.answer(f"✅ Геопозиция принята! Расстояние: ~{int(dist)}м.", reply_markup=student_main_kb)

@router.message(F.text == "👀 Кто ответил")
async def cmd_who_responded(message: Message):
    if message.from_user.id != ADMIN_ID or not current_session["is_active"]: return
    responses = current_session["responses"]
    if not responses: return await message.answer("Пока никто не прислал геопозицию.")
    
    text = f"⏳ <b>Ответили ({len(responses)} чел.):</b>\n\n"
    async with get_db_pool().acquire() as conn:
        for idx, (t_id, data) in enumerate(responses.items(), 1):
            row = await conn.fetchrow("SELECT full_name FROM students WHERE telegram_id = $1", t_id)
            name = row['full_name'] if row else "Неизвестный"
            text += f"{idx}. {name} — ~{int(data['dist'])}м\n"
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🔴 Завершить проверку")
async def cmd_stop_check(message: Message):
    if message.from_user.id != ADMIN_ID or not current_session["is_active"]: return
    current_session["is_active"] = False
    responses = current_session["responses"]
    pool = get_db_pool()
    radius = await get_setting(pool, 'radius', DEFAULT_RADIUS)

    async with pool.acquire() as conn:
        all_students = await conn.fetch("SELECT telegram_id, full_name FROM students")

    report = f"📊 <b>Отчет присутствия:</b>\n\n"
    for idx, row in enumerate(all_students, 1):
        t_id, name = row['telegram_id'], row['full_name']
        if t_id in responses:
            dist = responses[t_id]["dist"]
            st = "✅ В ВУЗе" if dist <= radius else "❌ Вне зоны"
            report += f"{idx}. <b>{name}</b> — {st} (~{int(dist)}м)\n"
        else:
            report += f"{idx}. ⚙️ <b>{name}</b> — Не ответил\n"
    await message.answer(report, parse_mode="HTML")

# Настройки администратора
@router.message(F.text == "🎯 Установить центр ВУЗа")
async def admin_set_uni_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📍 Отправить новые координаты", request_location=True)]], resize_keyboard=True, one_time_keyboard=True)
    await message.answer("Отправьте геопозицию центра ВУЗа:", reply_markup=kb)
    await state.set_state(RegStates.waiting_for_uni_location)

@router.message(F.text == "👥 Список студентов")
async def admin_list_students(message: Message):
    if message.from_user.id != ADMIN_ID: return
    async with get_db_pool().acquire() as conn:
        rows = await conn.fetch("SELECT telegram_id, full_name FROM students")
        banned = [r['telegram_id'] for r in await conn.fetch("SELECT telegram_id FROM banned_users")]
    if not rows: return await message.answer("📁 База студентов пуста.")
    text = f"📋 <b>Студенты ({len(rows)}):</b>\n\n" + "\n".join([f"{i}. {r['full_name']} (<code>{r['telegram_id']}</code>){' (🚫 Забанен)' if r['telegram_id'] in banned else ''}" for i, r in enumerate(rows, 1)])
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🗑 Удалить студента")
async def admin_start_delete(message: Message):
    if message.from_user.id != ADMIN_ID: return
    async with get_db_pool().acquire() as conn:
        rows = await conn.fetch("SELECT telegram_id, full_name FROM students")
    if not rows: return await message.answer("📁 База пуста.")
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"❌ {r['full_name']}", callback_data=f"del_{r['telegram_id']}")] for r in rows])
    await message.answer("👇 Выберите студента для удаления:", reply_markup=inline_kb)

@router.callback_query(F.data.startswith("del_"))
async def admin_process_delete_callback(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    target_id = int(callback.data.split("_")[1])
    async with get_db_pool().acquire() as conn:
        await conn.execute("DELETE FROM students WHERE telegram_id = $1", target_id)
    await callback.message.edit_text("✅ Студент удален.")
    await callback.answer()

@router.message(F.text == "🚫 Блокировать ID")
async def admin_start_ban(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Введите ID для блокировки:")
    await state.set_state(RegStates.waiting_for_ban_id)

@router.message(RegStates.waiting_for_ban_id)
async def admin_process_ban(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try: target_id = int(message.text.strip())
    except ValueError: return await message.answer("❌ Введите корректный ID.")
    async with get_db_pool().acquire() as conn:
        await conn.execute("INSERT INTO banned_users (telegram_id) VALUES ($1) ON CONFLICT DO NOTHING", target_id)
        await conn.execute("DELETE FROM students WHERE telegram_id = $1", target_id)
    await state.clear()
    await message.answer(f"✅ Пользователь <code>{target_id}</code> заблокирован.", parse_mode="HTML")

@router.message(F.text == "✅ Разблокировать ID")
async def admin_start_unban(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Введите ID для разблокировки:")
    await state.set_state(RegStates.waiting_for_unban_id)

@router.message(RegStates.waiting_for_unban_id)
async def admin_process_unban(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try: target_id = int(message.text.strip())
    except ValueError: return await message.answer("❌ Введите корректный ID.")
    async with get_db_pool().acquire() as conn:
        await conn.execute("DELETE FROM banned_users WHERE telegram_id = $1", target_id)
    await state.clear()
    await message.answer(f"✅ Пользователь <code>{target_id}</code> разблокирован.", parse_mode="HTML")

@router.message(F.text == "⚙️ Изменить радиус зоны")
async def admin_start_radius(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    current_r = await get_setting(get_db_pool(), 'radius', DEFAULT_RADIUS)
    await message.answer(f"Текущий радиус: <b>{current_r}м</b>. Введите новый радиус в метрах:", parse_mode="HTML")
    await state.set_state(RegStates.waiting_for_radius)

@router.message(RegStates.waiting_for_radius)
async def admin_process_radius(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try: new_radius = int(message.text.strip())
    except ValueError: return await message.answer("❌ Введите корректное число.")
    await set_setting(get_db_pool(), 'radius', new_radius)
    await state.clear()
    await message.answer(f"✅ Новый радиус: <b>{new_radius}м</b>", parse_mode="HTML")