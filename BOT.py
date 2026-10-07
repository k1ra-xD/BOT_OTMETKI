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

# Начальные значения по умолчанию
DEFAULT_UNI_LAT = 51.159555 
DEFAULT_UNI_LON = 71.458555
DEFAULT_RADIUS = 150

router = Router()

# --- Инициализация БД и работы с настройками ---
def init_db():
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            telegram_id INTEGER PRIMARY KEY,
            full_name TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS banned_users (
            telegram_id INTEGER PRIMARY KEY
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Значения по умолчанию, если таблица пустая
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('lat', ?)", (str(DEFAULT_UNI_LAT),))
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('lon', ?)", (str(DEFAULT_UNI_LON),))
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('radius', ?)", (str(DEFAULT_RADIUS),))
    
    conn.commit()
    conn.close()

init_db()

def get_setting(key, default):
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return float(row[0]) if row and key in ['lat', 'lon'] else (int(row[0]) if row and key == 'radius' else default)

def set_setting(key, value):
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()


# --- Middleware для проверки блокировки ---
class BannedMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data):
        user = data.get("event_from_user")
        if user and user.id != ADMIN_ID:
            conn = sqlite3.connect("attendance.db")
            cursor = conn.cursor()
            cursor.execute("SELECT telegram_id FROM banned_users WHERE telegram_id = ?", (user.id,))
            banned = cursor.fetchone()
            conn.close()
            
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


# Состояние текущей проверки
current_session = {
    "is_active": False,
    "responses": {}  # telegram_id: {"lat": float, "lon": float, "dist": float}
}


def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000   
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# --- Панель управления и Старт ---
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        radius = get_setting('radius', DEFAULT_RADIUS)
        lat = get_setting('lat', DEFAULT_UNI_LAT)
        lon = get_setting('lon', DEFAULT_UNI_LON)
        
        admin_kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🟢 Проверить присутствие"), KeyboardButton(text="🔴 Завершить проверку")],
                [KeyboardButton(text="👀 Кто ответил"), KeyboardButton(text="🎯 Установить центр ВУЗа")],
                [KeyboardButton(text="👥 Список студентов"), KeyboardButton(text="🗑 Удалить студента")],
                [KeyboardButton(text="🚫 Блокировать ID"), KeyboardButton(text="✅ Разблокировать ID")],
                [KeyboardButton(text="⚙️ Изменить радиус зоны")]
            ],
            resize_keyboard=True
        )
        await message.answer(
            f"👋 <b>Панель администратора</b>\n\n"
            f"📍 Координаты ВУЗа: <code>{lat}, {lon}</code>\n"
            f"📏 Радиус зоны: <b>{radius}м</b>",
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
        await message.answer(f"Привет, {row[0]}! Вы зарегистрированы в системе проверки присутствия.")
    else:
        await message.answer("Привет! Для регистрации отправьте свои **Имя и Фамилию** (например: *Иван Иванов*).")
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


# --- Экспресс-проверка присутствия ---
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


# --- Прием геопозиции от студента ---
@router.message(F.location)
async def handle_location(message: Message, state: FSMContext):
    # Если админ устанавливает новый центр ВУЗа
    current_state = await state.get_state()
    if current_state == RegStates.waiting_for_uni_location.state:
        if message.from_user.id != ADMIN_ID:
            return
        
        new_lat = message.location.latitude
        new_lon = message.location.longitude
        set_setting('lat', new_lat)
        set_setting('lon', new_lon)
        
        await state.clear()
        await message.answer(
            f"✅ <b>Новые координаты ВУЗа сохранены!</b>\n"
            f"Широта: <code>{new_lat}</code>\nДолгота: <code>{new_lon}</code>",
            parse_mode="HTML"
        )
        return

    # Обработка ответа студента
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
    
    uni_lat = get_setting('lat', DEFAULT_UNI_LAT)
    uni_lon = get_setting('lon', DEFAULT_UNI_LON)
    
    dist = calculate_distance(uni_lat, uni_lon, lat, lon)
    current_session["responses"][message.from_user.id] = {
        "lat": lat, "lon": lon, "dist": dist
    }

    await message.answer(f"✅ Геопозиция принята! Расстояние до корпуса: ~{int(dist)}м.", reply_markup=ReplyKeyboardRemove())


# --- Мониторинг ответов в реальном времени ---
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

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    
    text = f"⏳ <b>Ответили на проверку ({len(responses)} чел.):</b>\n\n"
    for idx, (t_id, data) in enumerate(responses.items(), 1):
        cursor.execute("SELECT full_name FROM students WHERE telegram_id = ?", (t_id,))
        row = cursor.fetchone()
        name = row[0] if row else "Неизвестный"
        text += f"{idx}. {name} — ~{int(data['dist'])}м\n"
        
    conn.close()
    await message.answer(text, parse_mode="HTML")


# --- Завершение и итоговый отчет ---
@router.message(F.text == "🔴 Завершить проверку")
async def cmd_stop_check(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    if not current_session["is_active"]:
        await message.answer("Нет активной проверки для завершения.")
        return

    current_session["is_active"] = False
    responses = current_session["responses"]
    
    radius = get_setting('radius', DEFAULT_RADIUS)
    uni_lat = get_setting('lat', DEFAULT_UNI_LAT)
    uni_lon = get_setting('lon', DEFAULT_UNI_LON)

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id, full_name FROM students")
    all_students = cursor.fetchall()
    conn.close()

    if not all_students:
        await message.answer("📋 Список зарегистрированных студентов пуст.")
        return

    report = f"📊 <b>Отчет присутствия в ВУЗе:</b>\n"
    report += f"📍 Зона: {radius}м от (<code>{uni_lat:.4f}, {uni_lon:.4f}</code>)\n\n"

    in_count = 0
    out_count = 0
    no_resp_count = 0

    for idx, (t_id, name) in enumerate(all_students, 1):
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


# --- Настройка центра ВУЗа ---
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


# --- Прочий админский функционал ---
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

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO banned_users (telegram_id) VALUES (?)", (target_id,))
    cursor.execute("DELETE FROM students WHERE telegram_id = ?", (target_id,))
    conn.commit()
    conn.close()
    
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

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM banned_users WHERE telegram_id = ?", (target_id,))
    conn.commit()
    conn.close()
    
    await state.clear()
    await message.answer(f"✅ Пользователь <code>{target_id}</code> разблокирован.", parse_mode="HTML")


@router.message(F.text == "⚙️ Изменить радиус зоны")
async def admin_start_radius(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    current_r = get_setting('radius', DEFAULT_RADIUS)
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

    set_setting('radius', new_radius)
    await state.clear()
    await message.answer(f"✅ Новый радиус зоны: <b>{new_radius}м</b>", parse_mode="HTML")


# --- Запуск фиктивного веб-сервера Render и Telegram бота ---
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