import math
import asyncio
import os
from datetime import datetime, timedelta, timezone
import asyncpg
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router, BaseMiddleware
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, 
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove, WebAppInfo
)

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.environ.get("BOT_TOKEN", "8932791447:AAGB5HfDMv1Jq7yMwVwko9YVl7rubu7F3tM")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres.stduhsqtkysawtahgftq:7htTw1GOgUV7XXb2@aws-0-eu-west-1.pooler.supabase.com:6543/postgres")
ADMIN_ID = 1231388093  # Ваш ID

DEFAULT_UNI_LAT = 51.159555 
DEFAULT_UNI_LON = 71.458555
DEFAULT_RADIUS = 150

ASTANA_TZ = timezone(timedelta(hours=5))

db_pool: asyncpg.Pool = None
router = Router()

DAYS_MAP = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье"
}

# Исходное расписание для заливки в БД
INITIAL_SCHEDULE = [
    # Понедельник (0)
    (0, "10:00", "10:50", "История Казахстана", "лекция", "Сеитов Е.Т.", "ауд. 211"),
    (0, "11:00", "11:50", "История Казахстана", "лекция", "Сеитов Е.Т.", "ауд. 211"),
    (0, "12:00", "12:50", "Дискретная математика и теория вероятностей", "семинар", "Есентемирова А.К.", "ауд. 212"),
    (0, "13:00", "13:50", "Объектно-ориентированное программирование", "лекция", "ст. преп. Исаева М.А.", "ауд. 211"),

    # Вторник (1)
    (1, "11:00", "11:50", "Модернизация и ремонт ПК", "семинар", "Мысжанов З.М.", "ауд. 410"),
    (1, "12:00", "12:50", "Философия", "семинар", "Жукенова А.А.", "не указана"),
    (1, "13:00", "13:50", "Дискретная математика и теория вероятностей", "лекция", "ст. преп. Есентемирова А.К.", "ауд. 212"),
    (1, "14:00", "14:50", "Модернизация и ремонт ПК", "лекция", "к.т.н. Кульмамиров С.А.", "ауд. 414"),
    (1, "15:00", "15:50", "Модернизация и ремонт ПК", "семинар", "Мысжанов З.М.", "ауд. 410"),

    # Среда (2)
    (2, "15:00", "15:50", "Объектно-ориентированное программирование", "семинар", "ст. преп. Исаева М.А.", "ауд. 400"),
    (2, "16:00", "16:50", "Дискретная математика и теория вероятностей", "семинар", "Есентемирова А.К.", "не указана"),

    # Четверг (3)
    (3, "10:00", "10:50", "Философия", "лекция", "Жукенова А.А.", "Онлайн"),
    (3, "11:00", "11:50", "Философия", "лекция", "Жукенова А.А.", "Онлайн"),

    # Пятница (4)
    (4, "10:00", "10:50", "Системы искусственного интеллекта", "семинар", "Мысжанов З.М.", "не указана"),
    (4, "11:00", "11:50", "Системы искусственного интеллекта", "семинар", "Мысжанов З.М.", "не указана"),
    (4, "13:00", "13:50", "Системы искусственного интеллекта", "лекция", "ст. преп. Абдрахманова А.З.", "ауд. 212"),
    (4, "14:00", "14:50", "История Казахстана", "семинар", "Сеитов Э.Т.", "не указана")
]


# --- ИНИЦИАЛИЗАЦИЯ БД ---
async def init_db():
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                telegram_id BIGINT PRIMARY KEY,
                full_name TEXT
            );
            CREATE TABLE IF NOT EXISTS banned_users (
                telegram_id BIGINT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS schedule (
                id SERIAL PRIMARY KEY,
                day_of_week INT,
                time_start TEXT,
                time_end TEXT,
                subject TEXT,
                lesson_type TEXT,
                teacher TEXT,
                room TEXT
            );
        """)
        
        await conn.execute("INSERT INTO settings (key, value) VALUES ('lat', $1) ON CONFLICT (key) DO NOTHING", str(DEFAULT_UNI_LAT))
        await conn.execute("INSERT INTO settings (key, value) VALUES ('lon', $1) ON CONFLICT (key) DO NOTHING", str(DEFAULT_UNI_LON))
        await conn.execute("INSERT INTO settings (key, value) VALUES ('radius', $1) ON CONFLICT (key) DO NOTHING", str(DEFAULT_RADIUS))

        # Наполнение расписанием, если таблица пуста
        count = await conn.fetchval("SELECT COUNT(*) FROM schedule")
        if count == 0:
            for item in INITIAL_SCHEDULE:
                await conn.execute("""
                    INSERT INTO schedule (day_of_week, time_start, time_end, subject, lesson_type, teacher, room)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, *item)


async def get_setting(key: str, default):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT value FROM settings WHERE key = $1", key)
        if not row:
            return default
        val = row['value']
        if key in ['lat', 'lon']:
            return float(val)
        elif key == 'radius':
            return int(val)
        return val

async def set_setting(key: str, value):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO settings (key, value) VALUES ($1, $2)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, key, str(value))


# --- Middleware для проверки блокировки ---
class BannedMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data):
        user = data.get("event_from_user")
        if user and user.id != ADMIN_ID:
            async with db_pool.acquire() as conn:
                banned = await conn.fetchrow("SELECT telegram_id FROM banned_users WHERE telegram_id = $1", user.id)
            
            if banned:
                if isinstance(event, Message):
                    await event.answer("⛔️ Доступ закрыт. Вы заблокированы администратором.", reply_markup=ReplyKeyboardRemove())
                return
        return await handler(event, data)

router.message.middleware(BannedMiddleware())


# Состояния FSM
class RegStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_radius = State()
    waiting_for_ban_id = State()
    waiting_for_unban_id = State()
    waiting_for_uni_location = State()

class ScheduleAdminStates(StatesGroup):
    waiting_for_schedule_text = State()


# Состояние текущей проверки
current_session = {
    "is_active": False,
    "responses": {}
}


def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000   
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# --- ФОНОВЫЙ ТАЙМЕР НАПОМИНАНИЙ ЗА 10 МИНУТ ---
notified_lessons = set()

async def schedule_notifications_loop(bot: Bot):
    while True:
        try:
            now = datetime.now(ASTANA_TZ)
            current_day = now.weekday()
            target_time = (now + timedelta(minutes=10)).strftime("%H:%M")
            date_key = now.strftime("%Y-%m-%d")

            async with db_pool.acquire() as conn:
                lessons = await conn.fetch("""
                    SELECT * FROM schedule 
                    WHERE day_of_week = $1 AND time_start = $2
                """, current_day, target_time)

                if lessons:
                    students = await conn.fetch("SELECT telegram_id FROM students")
                    for lesson in lessons:
                        lesson_id_key = f"{date_key}_{lesson['id']}"
                        if lesson_id_key not in notified_lessons:
                            notified_lessons.add(lesson_id_key)
                            
                            text = (
                                f"🔔 <b>Напоминание о паре!</b>\n"
                                f"⏰ <b>Начало:</b> через 10 минут ({lesson['time_start']} - {lesson['time_end']})\n"
                                f"📖 <b>Предмет:</b> {lesson['subject']} ({lesson['lesson_type']})\n"
                                f"👨‍🏫 <b>Преподаватель:</b> {lesson['teacher']}\n"
                                f"🚪 <b>Аудитория:</b> {lesson['room']}"
                            )
                            
                            for student in students:
                                try:
                                    await bot.send_message(student['telegram_id'], text, parse_mode="HTML")
                                except Exception:
                                    pass
        except Exception as e:
            print(f"Ошибка в рассылке расписания: {e}")

        await asyncio.sleep(30)


# --- КЛАВИАТУРЫ ДЛЯ СТУДЕНТОВ И АДМИНА ---
student_main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Расписание"), KeyboardButton(text="📍 Отметиться")]
    ],
    resize_keyboard=True
)

schedule_inline_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="Сегодня", callback_data="sched_today"),
        InlineKeyboardButton(text="Завтра", callback_data="sched_tomorrow")
    ],
    [InlineKeyboardButton(text="📅 На всю неделю", callback_data="sched_week")]
])


# --- ПАНЕЛЬ УПРАВЛЕНИЯ И СТАРТ ---
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        radius = await get_setting('radius', DEFAULT_RADIUS)
        lat = await get_setting('lat', DEFAULT_UNI_LAT)
        lon = await get_setting('lon', DEFAULT_UNI_LON)
        
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
            [InlineKeyboardButton(text="✏️ Обновить расписание", callback_data="admin_edit_schedule")]
        ])

        await message.answer(
            f"👋 <b>Панель администратора</b>\n\n"
            f"📍 Координаты ВУЗа: <code>{lat}, {lon}</code>\n"
            f"📏 Радиус зоны: <b>{radius}м</b>",
            reply_markup=admin_kb,
            parse_mode="HTML"
        )
        await message.answer("Дополнительные инструменты управления:", reply_markup=admin_inline_panel)
        return

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT full_name FROM students WHERE telegram_id = $1", message.from_user.id)

    if row:
        await message.answer(
            f"Привет, {row['full_name']}! Вы зарегистрированы в системе.",
            reply_markup=student_main_kb
        )
    else:
        await message.answer("Привет! Для регистрации отправьте свои **Имя и Фамилию** (например: *Иван Иванов*).")
        await state.set_state(RegStates.waiting_for_name)

@router.message(RegStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    full_name = message.text.strip()
    if len(full_name.split()) < 2:
        await message.answer("Пожалуйста, введите корректно Имя и Фамилию.")
        return

    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO students (telegram_id, full_name) VALUES ($1, $2)
            ON CONFLICT (telegram_id) DO UPDATE SET full_name = EXCLUDED.full_name
        """, message.from_user.id, full_name)

    await state.clear()
    await message.answer(f"Спасибо, {full_name}! Регистрация прошла успешно.", reply_markup=student_main_kb)


# --- ХЭНДЛЕРЫ ПРОСМОТРА РАСПИСАНИЯ ---
@router.message(F.text == "📅 Расписание")
async def show_schedule_menu(message: Message):
    await message.answer("Выберите период для просмотра расписания:", reply_markup=schedule_inline_kb)

async def format_day_schedule(conn, day_code: int) -> str:
    lessons = await conn.fetch("""
        SELECT * FROM schedule WHERE day_of_week = $1 ORDER BY time_start ASC
    """, day_code)
    
    day_name = DAYS_MAP.get(day_code, "")
    if not lessons:
        return f"<b>{day_name}:</b>\n🎉 Парочек нет, отдыхаем!\n"
    
    text = f"🗓 <b>{day_name}:</b>\n\n"
    for l in lessons:
        text += (
            f"⏰ <code>{l['time_start']} - {l['time_end']}</code>\n"
            f"📖 <b>{l['subject']}</b> ({l['lesson_type']})\n"
            f"👨‍🏫 {l['teacher']} | 🚪 <b>{l['room']}</b>\n"
            f"-------------------------------\n"
        )
    return text

@router.callback_query(F.data.startswith("sched_"))
async def process_schedule_callback(callback: CallbackQuery):
    now = datetime.now(ASTANA_TZ)
    async with db_pool.acquire() as conn:
        if callback.data == "sched_today":
            day_code = now.weekday()
            text = await format_day_schedule(conn, day_code)
        elif callback.data == "sched_tomorrow":
            day_code = (now.weekday() + 1) % 7
            text = await format_day_schedule(conn, day_code)
        elif callback.data == "sched_week":
            text = "📅 <b>Расписание на всю неделю:</b>\n\n"
            for d in range(5):
                text += await format_day_schedule(conn, d) + "\n"
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=schedule_inline_kb)
    await callback.answer()


# --- РЕДАКТИРОВАНИЕ РАСПИСАНИЯ АДМИНОМ ---
@router.callback_query(F.data == "admin_edit_schedule")
async def start_schedule_edit(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("У вас нет прав.", show_alert=True)
        
    await state.set_state(ScheduleAdminStates.waiting_for_schedule_text)
    await callback.message.answer(
        "📝 <b>Отправьте новое расписание текстом в формате:</b>\n\n"
        "<code>Понедельник\n"
        "10.00-10.50 Предмет, лекция, Преподаватель ауд 211\n"
        "11.00-11.50 Предмет, семинар, Преподаватель ауд 212</code>\n\n"
        "Для отмены отправьте /cancel"
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
    
    day_mapping = {
        "понедельник": 0, "вторник": 1, "среда": 2, 
        "четверг": 3, "пятница": 4, "суббота": 5, "воскресенье": 6
    }

    try:
        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue
            
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

                parsed_items.append((current_day, t_start, t_end, details.strip(", "), "занятие", "", room))

        if not parsed_items:
            return await message.answer("⚠️ Не удалось распознать формат. Попробуйте еще раз или нажмите /cancel.")

        async with db_pool.acquire() as conn:
            await conn.execute("TRUNCATE TABLE schedule")
            for item in parsed_items:
                await conn.execute("""
                    INSERT INTO schedule (day_of_week, time_start, time_end, subject, lesson_type, teacher, room)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, *item)

        await state.clear()
        await message.answer("✅ <b>Расписание успешно обновлено в Supabase!</b>", parse_mode="HTML")

    except Exception as e:
        await message.answer(f"❌ Ошибка разбора: {e}")


# --- ЭКСПРЕСС-ПРОВЕРКА И ГЕОПОЗИЦИЯ ---
@router.message(F.text == "🟢 Проверить присутствие")
async def cmd_start_check(message: Message, bot: Bot):
    if message.from_user.id != ADMIN_ID:
        return
    
    current_session["is_active"] = True
    current_session["responses"].clear()
    
    geo_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Я в ВУЗе (Отправить гео)", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    async with db_pool.acquire() as conn:
        students = await conn.fetch("SELECT telegram_id FROM students")

    count = 0
    for row in students:
        t_id = row['telegram_id']
        try:
            await bot.send_message(
                t_id, 
                "⚠️ <b>Проверка присутствия!</b>\n"
                "Пожалуйста, нажмите кнопку ниже и подтвердите нахождение на территории ВУЗа:", 
                reply_markup=geo_kb,
                parse_mode="HTML"
            )
            count += 1
        except Exception:
            pass  

    await message.answer(
        f"🚀 <b>Проверка запущена!</b>\n"
        f"Запросы отправлены студентам ({count} чел.).\n\n"
        f"Используйте кнопку «👀 Кто ответил» для наблюдения или «🔴 Завершить проверку» для получения отчета.",
        parse_mode="HTML"
    )

@router.message(F.text == "📍 Отметиться")
async def student_manual_checkin(message: Message):
    if not current_session["is_active"]:
        return await message.answer("Сейчас нет активной проверки присутствия.")
    
    geo_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Я в ВУЗе (Отправить гео)", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Нажмите кнопку ниже для отправки геопозиции:", reply_markup=geo_kb)

@router.message(F.location)
async def handle_location(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == RegStates.waiting_for_uni_location.state:
        if message.from_user.id != ADMIN_ID:
            return
        
        new_lat = message.location.latitude
        new_lon = message.location.longitude
        await set_setting('lat', new_lat)
        await set_setting('lon', new_lon)
        
        await state.clear()
        await message.answer(
            f"✅ <b>Новые координаты ВУЗа сохранены!</b>\n"
            f"Широта: <code>{new_lat}</code>\nДолгота: <code>{new_lon}</code>",
            parse_mode="HTML"
        )
        return

    if not current_session["is_active"]:
        await message.answer("Сейчас нет активной проверки присутствия.", reply_markup=ReplyKeyboardRemove())
        return

    if message.from_user.id in current_session["responses"]:
        await message.answer("⚠️ Вы уже отправили свою геопозицию для этой проверки.", reply_markup=ReplyKeyboardRemove())
        return

    accuracy = getattr(message.location, 'horizontal_accuracy', None)
    if accuracy and accuracy > 200:
        await message.answer(
            f"⚠️ Высокая погрешность GPS (~{int(accuracy)}м).\n"
            "Подойдите ближе к окну, включите Wi-Fi для точности и отправьте геопозицию снова."
        )
        return

    lat = message.location.latitude
    lon = message.location.longitude
    
    uni_lat = await get_setting('lat', DEFAULT_UNI_LAT)
    uni_lon = await get_setting('lon', DEFAULT_UNI_LON)
    
    dist = calculate_distance(uni_lat, uni_lon, lat, lon)
    current_session["responses"][message.from_user.id] = {
        "lat": lat, "lon": lon, "dist": dist
    }

    await message.answer(f"✅ Геопозиция принята! Расстояние до корпуса: ~{int(dist)}м.", reply_markup=student_main_kb)


# --- МОНИТОРИНГ И ИТОГОВЫЙ ОТЧЕТ ---
@router.message(F.text == "👀 Кто ответил")
async def cmd_who_responded(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    if not current_session["is_active"]:
        await message.answer("Проверка присутствия сейчас не проводится.")
        return

    responses = current_session["responses"]
    if not responses:
        await message.answer("Пока ни один студент не прислал геопозицию.")
        return

    text = f"⏳ <b>Ответили на проверку ({len(responses)} чел.):</b>\n\n"
    async with db_pool.acquire() as conn:
        for idx, (t_id, data) in enumerate(responses.items(), 1):
            row = await conn.fetchrow("SELECT full_name FROM students WHERE telegram_id = $1", t_id)
            name = row['full_name'] if row else "Неизвестный"
            text += f"{idx}. {name} — ~{int(data['dist'])}м\n"
        
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🔴 Завершить проверку")
async def cmd_stop_check(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    if not current_session["is_active"]:
        await message.answer("Нет активной проверки для завершения.")
        return

    current_session["is_active"] = False
    responses = current_session["responses"]
    
    radius = await get_setting('radius', DEFAULT_RADIUS)
    uni_lat = await get_setting('lat', DEFAULT_UNI_LAT)
    uni_lon = await get_setting('lon', DEFAULT_UNI_LON)

    async with db_pool.acquire() as conn:
        all_students = await conn.fetch("SELECT telegram_id, full_name FROM students")

    if not all_students:
        await message.answer("📋 Список зарегистрированных студентов пуст.")
        return

    report = f"📊 <b>Отчет присутствия в ВУЗе:</b>\n"
    report += f"📍 Зона: {radius}м от (<code>{uni_lat:.4f}, {uni_lon:.4f}</code>)\n\n"

    in_count = 0
    out_count = 0
    no_resp_count = 0

    for idx, row in enumerate(all_students, 1):
        t_id = row['telegram_id']
        name = row['full_name']
        if t_id in responses:
            dist = responses[t_id]["dist"]
            if dist <= radius:
                report += f"{idx}. ✅ <b>{name}</b> — В ВУЗе (~{int(dist)}м)\n"
                in_count += 1
            else:
                report += f"{idx}. ❌ <b>{name}</b> — Вне зоны ({int(dist)}м)\n"
                out_count += 1
        else:
            report += f"{idx}. ⚙️ <b>{name}</b> — Не ответил\n"
            no_resp_count += 1

    report += f"\n📈 <b>Итого:</b> В ВУЗе: {in_count} | Вне зоны: {out_count} | Проигнорировали: {no_resp_count}"
    await message.answer(report, parse_mode="HTML")


# --- НАСТРОЙКИ АДМИНИСТРАТОРА ---
@router.message(F.text == "🎯 Установить центр ВУЗа")
async def admin_set_uni_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Отправить текущие координаты", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Отправьте вашу геопозицию. Она станет новым центром ВУЗа:", reply_markup=kb)
    await state.set_state(RegStates.waiting_for_uni_location)

@router.message(F.text == "👥 Список студентов")
async def admin_list_students(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT telegram_id, full_name FROM students")
        banned_rows = await conn.fetch("SELECT telegram_id FROM banned_users")

    banned_ids = [r['telegram_id'] for r in banned_rows]

    if not rows:
        await message.answer("📁 База студентов пуста.")
        return

    text = f"📋 <b>Зарегистрированные студенты ({len(rows)}):</b>\n\n"
    for idx, row in enumerate(rows, 1):
        t_id = row['telegram_id']
        name = row['full_name']
        status = " (🚫 Забанен)" if t_id in banned_ids else ""
        text += f"{idx}. {name} (ID: <code>{t_id}</code>){status}\n"
    
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🗑 Удалить студента")
async def admin_start_delete(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT telegram_id, full_name FROM students")

    if not rows:
        await message.answer("📁 База студентов пуста, некого удалять.")
        return

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[])
    for row in rows:
        t_id = row['telegram_id']
        name = row['full_name']
        inline_kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"❌ {name}", callback_data=f"del_{t_id}")
        ])

    await message.answer("👇 Выберите студента для удаления:", reply_markup=inline_kb)

@router.callback_query(F.data.startswith("del_"))
async def admin_process_delete_callback(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас нет прав.", show_alert=True)
        return

    target_id = int(callback.data.split("_")[1])

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT full_name FROM students WHERE telegram_id = $1", target_id)
        if row:
            await conn.execute("DELETE FROM students WHERE telegram_id = $1", target_id)
            name = row['full_name']
            await callback.message.edit_text(f"✅ Студент <b>{name}</b> успешно удален из базы.", parse_mode="HTML")
        else:
            await callback.answer("❌ Студент уже удален или не найден.", show_alert=True)
    
    await callback.answer()

@router.message(F.text == "🚫 Блокировать ID")
async def admin_start_ban(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Введите Telegram ID пользователя для <b>блокировки</b>:", parse_mode="HTML")
    await state.set_state(RegStates.waiting_for_ban_id)

@router.message(RegStates.waiting_for_ban_id)
async def admin_process_ban(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        target_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректный ID (только цифры).")
        return

    if target_id == ADMIN_ID:
        await message.answer("❌ Вы не можете заблокировать самого себя.")
        await state.clear()
        return

    async with db_pool.acquire() as conn:
        await conn.execute("INSERT INTO banned_users (telegram_id) VALUES ($1) ON CONFLICT (telegram_id) DO NOTHING", target_id)
        await conn.execute("DELETE FROM students WHERE telegram_id = $1", target_id)
    
    await state.clear()
    await message.answer(f"✅ Пользователь <code>{target_id}</code> заблокирован.", parse_mode="HTML")

@router.message(F.text == "✅ Разблокировать ID")
async def admin_start_unban(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Введите Telegram ID пользователя для <b>разблокировки</b>:", parse_mode="HTML")
    await state.set_state(RegStates.waiting_for_unban_id)

@router.message(RegStates.waiting_for_unban_id)
async def admin_process_unban(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        target_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректный ID (только цифры).")
        return

    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM banned_users WHERE telegram_id = $1", target_id)
    
    await state.clear()
    await message.answer(f"✅ Пользователь <code>{target_id}</code> разблокирован.", parse_mode="HTML")

@router.message(F.text == "⚙️ Изменить радиус зоны")
async def admin_start_radius(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    current_r = await get_setting('radius', DEFAULT_RADIUS)
    await message.answer(f"Текущий радиус: <b>{current_r}м</b>. Введите новый радиус в метрах:", parse_mode="HTML")
    await state.set_state(RegStates.waiting_for_radius)

@router.message(RegStates.waiting_for_radius)
async def admin_process_radius(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        new_radius = int(message.text.strip())
        if new_radius <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Введите корректное число.")
        return

    await set_setting('radius', new_radius)
    await state.clear()
    await message.answer(f"✅ Новый радиус зоны: <b>{new_radius}м</b>", parse_mode="HTML")


# --- WEB-СЕРВЕР И TELEGRAM MINI APP DASHBOARD ---
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Дашборд Посещаемости</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { font-family: sans-serif; background: var(--tg-theme-bg-color, #f4f4f9); color: var(--tg-theme-text-color, #222); padding: 16px; margin: 0; }
        .card { background: var(--tg-theme-secondary-bg-color, #fff); border-radius: 12px; padding: 16px; margin-bottom: 12px; }
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .stat-num { font-size: 24px; font-weight: bold; color: var(--tg-theme-button-color, #0088cc); }
        .status-badge { display: inline-block; padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: bold; }
        .active { background: #e3f8e0; color: #2e7d32; }
        .inactive { background: #ffebee; color: #c62828; }
        ul { list-style: none; padding: 0; margin: 8px 0 0 0; }
        li { padding: 6px 0; border-bottom: 1px solid rgba(0,0,0,0.05); font-size: 14px; }
    </style>
</head>
<body>
    <h2>📊 Дашборд Посещаемости</h2>
    <div class="card"><div style="display:flex; justify-content:space-between; align-items:center;"><span>Статус проверки:</span><span id="session-status" class="status-badge inactive">Завершена</span></div></div>
    <div class="stat-grid">
        <div class="card"><div>Всего студентов</div><div id="total-students" class="stat-num">0</div></div>
        <div class="card"><div>Ответили сейчас</div><div id="responded-count" class="stat-num">0</div></div>
    </div>
    <div class="card"><h3>📍 Откликнулись:</h3><ul id="responses-list"><li><i>Список пуст</i></li></ul></div>
    <script>
        const tg = window.Telegram.WebApp; tg.expand();
        async function loadStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                document.getElementById('total-students').innerText = data.total_students;
                document.getElementById('responded-count').innerText = data.responded_count;
                const statusBadge = document.getElementById('session-status');
                if (data.is_active) { statusBadge.innerText = '🟢 Активна'; statusBadge.className = 'status-badge active'; }
                else { statusBadge.innerText = '🔴 Завершена'; statusBadge.className = 'status-badge inactive'; }
                const list = document.getElementById('responses-list');
                if (data.responses.length > 0) {
                    list.innerHTML = data.responses.map(r => `<li><b>${r.name}</b> — ~${Math.round(r.dist)}м</li>`).join('');
                } else { list.innerHTML = '<li><i>Список пуст</i></li>'; }
            } catch (e) { console.error(e); }
        }
        loadStats(); setInterval(loadStats, 3000);
    </script>
</body>
</html>
"""

async def handle_index(request): 
    return web.Response(text="Bot is running!")

async def handle_dashboard(request): 
    return web.Response(text=DASHBOARD_HTML, content_type='text/html')

async def handle_api_stats(request):
    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM students")
        responses_data = []
        for t_id, data in current_session["responses"].items():
            row = await conn.fetchrow("SELECT full_name FROM students WHERE telegram_id = $1", t_id)
            name = row['full_name'] if row else f"ID: {t_id}"
            responses_data.append({"name": name, "dist": data["dist"]})
    return web.json_response({
        "is_active": current_session["is_active"],
        "total_students": total or 0,
        "responded_count": len(current_session["responses"]),
        "responses": responses_data
    })

async def start_web_server():
    app = web.Application()
    app.add_routes([
        web.get('/', handle_index),
        web.get('/dashboard', handle_dashboard),
        web.get('/api/stats', handle_api_stats)
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


# --- ЗАПУСК БОТА И СЕРВИСОВ ---
async def main():
    global db_pool
    print("Подключение к базе данных Supabase PostgreSQL...")
    db_pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        statement_cache_size=0
    )
    
    await init_db()
    print("База данных и расписание инициализированы.")

    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    
    print("Запуск веб-сервера, бота и фоновой рассылки...")
    await asyncio.gather(
        start_web_server(),
        dp.start_polling(bot),
        schedule_notifications_loop(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())