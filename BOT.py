import os
import asyncio
from datetime import datetime, timedelta
import asyncpg
from aiohttp import web
from aiogram import Bot, Dispatcher

from config import TOKEN, DATABASE_URL, ASTANA_TZ, ADMIN_ID
from db import init_db
from handlers import router, set_db_pool, get_db_pool, current_session
from web import create_web_app

notified_lessons = set()

async def schedule_notifications_loop(bot: Bot):
    while True:
        try:
            now = datetime.now(ASTANA_TZ)
            current_day = now.weekday()
            target_time = (now + timedelta(minutes=10)).strftime("%H:%M")
            date_key = now.strftime("%Y-%m-%d")

            pool = get_db_pool()
            if pool:
                async with pool.acquire() as conn:
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

    asyncio.create_task(schedule_notifications_loop(bot))

    app = create_web_app(get_db_pool, current_session)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 WebApp запущен на порту {port}")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())