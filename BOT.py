import os
import asyncio
from datetime import datetime, timedelta
import asyncpg
from aiohttp import web
from aiogram import Bot, Dispatcher

from config import TOKEN, DATABASE_URL, ASTANA_TZ, ADMIN_ID
from db import init_db
from handlers import router, set_db_pool, get_db_pool
from web import create_web_app
from drive_handlers import drive_router

notified_lessons = set()

async def schedule_notifications_loop(bot: Bot):
    while True:
        try:
            now = datetime.now(ASTANA_TZ)
            current_day = now.weekday()
            current_time = now.strftime("%H:%M")
            target_time = (now + timedelta(minutes=10)).strftime("%H:%M")
            date_key = now.strftime("%Y-%m-%d")

            pool = get_db_pool()
            if pool:
                async with pool.acquire() as conn:
                    # 1. Рассылка на самой первой паре дня (ровно в начале пары для подтверждения присутствия)
                    first_lesson = await conn.fetchrow(
                        "SELECT * FROM schedule WHERE day_of_week = $1 ORDER BY time_start ASC LIMIT 1",
                        current_day
                    )
                    if first_lesson and first_lesson['time_start'] == current_time:
                        first_key = f"first_start_{date_key}_{first_lesson['id']}"
                        if first_key not in notified_lessons:
                            notified_lessons.add(first_key)
                            text_first = (
                                f"🔔 <b>Первая пара началась!</b>\n"
                                f"⏰ <b>Время:</b> {first_lesson['time_start']} - {first_lesson['time_end']}\n"
                                f"📖 <b>Предмет:</b> {first_lesson['subject']} ({first_lesson['lesson_type']})\n"
                                f"👨‍🏫 <b>Преподаватель:</b> {first_lesson['teacher']}\n"
                                f"🚪 <b>Аудитория:</b> {first_lesson['room']}\n\n"
                                f"📍 <b>Подтвердите присутствие в университете:</b>\n"
                                f"Нажмите кнопку <b>«📍 Я здесь»</b> внизу, чтобы отметиться!"
                            )
                            students = await conn.fetch("SELECT telegram_id FROM students")
                            recipients = {s['telegram_id'] for s in students}
                            if ADMIN_ID:
                                recipients.add(ADMIN_ID)
                            for user_id in recipients:
                                try:
                                    await bot.send_message(user_id, text_first, parse_mode="HTML")
                                except Exception:
                                    pass

                    # 2. Обычные напоминания за 10 минут до пар
                    lessons = await conn.fetch(
                        "SELECT * FROM schedule WHERE day_of_week = $1 AND time_start = $2", 
                        current_day, target_time
                    )
                    if lessons:
                        students = await conn.fetch("SELECT telegram_id FROM students")
                        recipients = {s['telegram_id'] for s in students}
                        if ADMIN_ID:
                            recipients.add(ADMIN_ID)

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
                                for user_id in recipients:
                                    try:
                                        await bot.send_message(user_id, text, parse_mode="HTML")
                                    except Exception:
                                        pass
        except Exception as e:
            print(f"Ошибка в рассылке: {e}")
        await asyncio.sleep(30)

async def main():
    print("🚀 Запуск бота...")
    db_pool = await asyncpg.create_pool(DATABASE_URL, statement_cache_size=0)
    set_db_pool(db_pool)
    await init_db(db_pool)

    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    dp.include_router(drive_router)

    asyncio.create_task(schedule_notifications_loop(bot))

    app = create_web_app(get_db_pool, None)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 WebApp запущен на порту {port}")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())