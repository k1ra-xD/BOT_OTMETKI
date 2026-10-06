import math
import asyncio
import os
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router, BaseMiddleware
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, 
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)

TOKEN = "8932791447:AAGB5HfDMv1Jq7yMwVwko9YVl7rubu7F3tM"
ADMIN_ID = 1231388093  # Ваш ID

# Координаты 
UNI_LAT = 51.159555 
UNI_LON = 71.458555
ALLOWED_RADIUS_METERS = 150  # радиус зоны в метрах

router = Router()

# --- Инициализация БД ---
def init_db():
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    # Таблица студентов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            telegram_id INTEGER PRIMARY KEY,
            full_name TEXT
        )
    """)
    # Таблица заблокированных пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS banned_users (
            telegram_id INTEGER PRIMARY KEY
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- Middleware для проверки на блокировку ---
class BannedMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data):
        user = data.get("event_from_user")
        
        # Проверяем, есть ли пользователь и не является ли он админом (админа заблокировать нельзя)
        if user and user.id != ADMIN_ID:
            conn = sqlite3.connect("attendance.db")
            cursor = conn.cursor()
            cursor.execute("SELECT telegram_id FROM banned_users WHERE telegram_id = ?", (user.id,))
            banned = cursor.fetchone()
            conn.close()
            
            if banned:
                if isinstance(event, Message):
                    await event.answer("⛔️ Доступ закрыт. Вы заблокированы администратором.", reply_markup=ReplyKeyboardRemove())
                return  # Прерываем обработку сообщения

        return await handler(event, data)

# Подключаем Middleware ко всем сообщениям
router.message.middleware(BannedMiddleware())


# Состояния для FSM
class RegStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_radius = State()
    waiting_for_ban_id = State()    # Состояние для блокировки
    waiting_for_unban_id = State()  # Состояние для разблокировки

# Состояния для сессии пары
current_session = {
    "is_active": False,
    "present_students": set()
}

student_locations = {}
active_admin_chat_id = None


# --- Шаг 1: Регистрация и проверка на админа ---
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        admin_kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🟢 Начать пару"), KeyboardButton(text="🔴 Завершить и проверить")],
                [KeyboardButton(text="👀 Кто уже отметился?")],
                [KeyboardButton(text="👥 Список студентов"), KeyboardButton(text="🗑 Удалить студента")],
                [KeyboardButton(text="🚫 Блокировать ID"), KeyboardButton(text="✅ Разблокировать ID")],
                [KeyboardButton(text="⚙️ Изменить радиус зоны")]
            ],
            resize_keyboard=True
        )
        await message.answer(
            f"👋 Панель администратора.\n"
            f"📍 Текущий радиус геозоны: <b>{ALLOWED_RADIUS_METERS}м</b>",
            reply_markup=admin_kb,
            parse_mode="HTML"
        )
        return

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT full_name FROM students WHERE telegram_id = ?", (message.from_user.id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        await message.answer(f"Привет, {row[0]}! Вы уже зарегистрированы в системе учета.")
    else:
        await message.answer("Привет! Для участия в учете посещаемости отправьте свои **Имя и Фамилию** (например: *Иван Иванов*).")
        await state.set_state(RegStates.waiting_for_name)

@router.message(RegStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    full_name = message.text.strip()
    if len(full_name.split()) < 2:
        await message.answer("Пожалуйста, введите корректно Имя и Фамилию.")
        return

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO students (telegram_id, full_name) VALUES (?, ?)", 
                   (message.from_user.id, full_name))
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(f"Спасибо, {full_name}! Регистрация прошла успешно.")


# --- Студент: Отметка на паре ---
@router.message(F.text == "📍 Я здесь")
@router.message(Command("here"))
async def cmd_here(message: Message):
    if not current_session["is_active"]:
        await message.answer("Сейчас нет активной сессии сбора на пару.")
        return
    
    if message.from_user.id in current_session["present_students"]:
        await message.answer("⚠️ Вы уже отметились на этой паре! Ожидайте запрос геопозиции от преподавателя.", reply_markup=ReplyKeyboardRemove())
        return

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT full_name FROM students WHERE telegram_id = ?", (message.from_user.id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        await message.answer("Сначала зарегистрируйтесь с помощью /start")
        return

    current_session["present_students"].add(message.from_user.id)
    await message.answer("✅ Ваша отметка принята! Ожидайте запрос геопозиции от преподавателя.", reply_markup=ReplyKeyboardRemove())


# --- Админ: Узнать кто отметился в реальном времени ---
@router.message(F.text == "👀 Кто уже отметился?")
async def cmd_who_checked_in(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    if not current_session["is_active"]:
        await message.answer("Сбор отметок сейчас не идет. Начните пару.")
        return

    if not current_session["present_students"]:
        await message.answer("Пока ни один студент не нажал «Я здесь».")
        return

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    
    text = f"⏳ <b>Уже отметились ({len(current_session['present_students'])} чел.):</b>\n\n"
    for idx, t_id in enumerate(current_session["present_students"], 1):
        cursor.execute("SELECT full_name FROM students WHERE telegram_id = ?", (t_id,))
        row = cursor.fetchone()
        name = row[0] if row else "Неизвестный"
        text += f"{idx}. {name}\n"
        
    conn.close()
    await message.answer(text, parse_mode="HTML")


# --- Админ: Управление парой ---
@router.message(F.text == "🟢 Начать пару")
@router.message(Command("start_pair"))
async def cmd_start_pair(message: Message, bot: Bot):
    if message.from_user.id != ADMIN_ID:
        return
    
    current_session["is_active"] = True
    current_session["present_students"].clear()
    student_locations.clear()
    
    student_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Я здесь")]],
        resize_keyboard=True
    )
    
    await message.answer("🔔 Пара началась! Рассылаем приглашения студентам...\n\n"
                         "Вы можете использовать кнопку «👀 Кто уже отметился?», чтобы следить за процессом.")

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM students")
    students = cursor.fetchall()
    conn.close()

    count = 0
    for (t_id,) in students:
        try:
            await bot.send_message(
                t_id, 
                "🔔 Преподаватель открыл сбор отметок на пару! Нажмите кнопку ниже, чтобы отметиться:", 
                reply_markup=student_kb
            )
            count += 1
        except Exception:
            pass  

    await message.answer(f"✅ Пара успешно начата! Уведомления отправлены студентам ({count} чел.).")


@router.message(F.text == "🔴 Завершить и проверить")
@router.message(Command("stop_pair"))
async def cmd_stop_pair(message: Message, bot: Bot):
    if message.from_user.id != ADMIN_ID:
        return
    
    current_session["is_active"] = False
    global active_admin_chat_id
    active_admin_chat_id = message.chat.id

    if not current_session["present_students"]:
        await message.answer("📋 Ни один студент не нажал кнопку «Я здесь» во время пары.")
        return

    await message.answer("🔍 Запрос геопозиции отправлен всем отметившимся. Ожидаем 60 секунд...")

    geo_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Отправить геопозицию", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    for t_id in current_session["present_students"]:
        try:
            await bot.send_message(
                t_id, 
                "⚠️ Преподаватель запросил проверку геолокации. У вас есть 1 минута. Пожалуйста, отправьте текущую геопозицию:", 
                reply_markup=geo_kb
            )
        except Exception:
            pass  

    await asyncio.sleep(60)

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    
    report = "📊 <b>Итоговый отчёт посещаемости:</b>\n\n"
    for idx, t_id in enumerate(current_session["present_students"], 1):
        cursor.execute("SELECT full_name FROM students WHERE telegram_id = ?", (t_id,))
        row = cursor.fetchone()
        name = row[0] if row else "Неизвестный"
        
        if t_id in student_locations:
            lat, lon = student_locations[t_id]
            dist = calculate_distance(UNI_LAT, UNI_LON, lat, lon)
            if dist <= ALLOWED_RADIUS_METERS:
                report += f"{idx}. ✅ <b>{name}</b> — На месте (~{int(dist)}м)\n"
            else:
                report += f"{idx}. ❌ <b>{name}</b> — Далеко ({int(dist)}м от вуза)\n"
        else:
            report += f"{idx}. ❌ <b>{name}</b> — Не прислал геопозицию\n"
            
    conn.close()
    await message.answer(report, parse_mode="HTML")


# --- Обработка геопозиции от студентов ---
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000   
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

@router.message(F.location)
async def handle_location(message: Message, bot: Bot):
    if message.from_user.id in current_session["present_students"]:
        
        accuracy = getattr(message.location, 'horizontal_accuracy', None)
        if accuracy and accuracy > 200:
            await message.answer(
                f"⚠️ Ваш телефон определяет координаты с большой погрешностью (~{int(accuracy)}м). "
                "Это происходит из-за плохих сигналов спутников внутри здания.\n"
                "Пожалуйста, подойдите ближе к окну, включите Wi-Fi для точности и отправьте геопозицию снова."
            )
            return

        lat = message.location.latitude
        lon = message.location.longitude
        
        student_locations[message.from_user.id] = (lat, lon)
        dist = calculate_distance(UNI_LAT, UNI_LON, lat, lon)
        
        if dist > ALLOWED_RADIUS_METERS and active_admin_chat_id:
            conn = sqlite3.connect("attendance.db")
            cursor = conn.cursor()
            cursor.execute("SELECT full_name FROM students WHERE telegram_id = ?", (message.from_user.id,))
            row = cursor.fetchone()
            conn.close()
            name = row[0] if row else "Студент"
            
            await bot.send_message(
                active_admin_chat_id,
                f"⚠️ <b>Внимание!</b> Студент <b>{name}</b> находится вне зоны ({int(dist)}м от вуза) и числится вне пары!",
                parse_mode="HTML"
            )

        await message.answer("Спасибо! Геопозиция принята.", reply_markup=ReplyKeyboardRemove())


# --- Дополнительный админский функционал (Списки, Удаление) ---
@router.message(F.text == "👥 Список студентов")
async def admin_list_students(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id, full_name FROM students")
    rows = cursor.fetchall()
    
    cursor.execute("SELECT telegram_id FROM banned_users")
    banned_rows = [r[0] for r in cursor.fetchall()]
    conn.close()

    if not rows:
        await message.answer("📁 База студентов пуста.")
        return

    text = f"📋 <b>Зарегистрированные студенты ({len(rows)}):</b>\n\n"
    for idx, (t_id, name) in enumerate(rows, 1):
        status = " (🚫 Забанен)" if t_id in banned_rows else ""
        text += f"{idx}. {name} (ID: <code>{t_id}</code>){status}\n"
    
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "🗑 Удалить студента")
async def admin_start_delete(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id, full_name FROM students")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer("📁 База студентов пуста, некого удалять.")
        return

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[])
    for t_id, name in rows:
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

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT full_name FROM students WHERE telegram_id = ?", (target_id,))
    row = cursor.fetchone()

    if row:
        cursor.execute("DELETE FROM students WHERE telegram_id = ?", (target_id,))
        conn.commit()
        name = row[0]
        await callback.message.edit_text(f"✅ Студент <b>{name}</b> успешно удален из базы.", parse_mode="HTML")
    else:
        await callback.answer("❌ Студент уже удален или не найден.", show_alert=True)
    
    conn.close()
    await callback.answer()


# --- НОВОЕ: Блокировка и Разблокировка по ID ---
@router.message(F.text == "🚫 Блокировать ID")
async def admin_start_ban(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Введите Telegram ID пользователя для <b>блокировки</b> (ID можно посмотреть в списке студентов):", parse_mode="HTML")
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

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO banned_users (telegram_id) VALUES (?)", (target_id,))
    
    # Заодно удаляем из активных студентов, если он там есть
    cursor.execute("DELETE FROM students WHERE telegram_id = ?", (target_id,))
    
    conn.commit()
    conn.close()
    
    await state.clear()
    await message.answer(f"✅ Пользователь с ID <code>{target_id}</code> успешно <b>заблокирован</b>.", parse_mode="HTML")


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

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM banned_users WHERE telegram_id = ?", (target_id,))
    conn.commit()
    conn.close()
    
    await state.clear()
    await message.answer(f"✅ Пользователь с ID <code>{target_id}</code> успешно <b>разблокирован</b>.", parse_mode="HTML")


# --- Изменение радиуса ---
@router.message(F.text == "⚙️ Изменить радиус зоны")
async def admin_start_radius(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    await message.answer(f"Текущий радиус: <b>{ALLOWED_RADIUS_METERS}м</b>. Введите новый радиус в метрах:", parse_mode="HTML")
    await state.set_state(RegStates.waiting_for_radius)

@router.message(RegStates.waiting_for_radius)
async def admin_process_radius(message: Message, state: FSMContext):
    global ALLOWED_RADIUS_METERS
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        new_radius = int(message.text.strip())
        if new_radius <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Введите корректное число.")
        return

    ALLOWED_RADIUS_METERS = new_radius
    await state.clear()
    await message.answer(f"✅ Новый радиус зоны: <b>{ALLOWED_RADIUS_METERS}м</b>", parse_mode="HTML")


# --- Настройка фиктивного веб-сервера для Render ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.add_routes([web.get('/', handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


# --- Запуск бота и сервера ---
async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    
    print("Запуск веб-сервера и бота...")
    await asyncio.gather(
        start_web_server(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())