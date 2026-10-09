import asyncpg
from config import DEFAULT_UNI_LAT, DEFAULT_UNI_LON, DEFAULT_RADIUS

async def init_db(db_pool: asyncpg.Pool):
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
            CREATE TABLE IF NOT EXISTS attendance (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT,
                subject TEXT,
                checkin_time TIMESTAMP,
                status TEXT,
                distance INT
            );
        """)
        
        await conn.execute("INSERT INTO settings (key, value) VALUES ('lat', $1) ON CONFLICT (key) DO NOTHING", str(DEFAULT_UNI_LAT))
        await conn.execute("INSERT INTO settings (key, value) VALUES ('lon', $1) ON CONFLICT (key) DO NOTHING", str(DEFAULT_UNI_LON))
        await conn.execute("INSERT INTO settings (key, value) VALUES ('radius', $1) ON CONFLICT (key) DO NOTHING", str(DEFAULT_RADIUS))

async def get_setting(pool, key: str, default=None):
    """Получить значение настройки из базы данных"""
    if not pool:
        return default
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT value FROM settings WHERE key = $1", key)
        if row and row['value'] is not None:
            val = row['value']
            try:
                if '.' in str(val):
                    return float(val)
                return int(val)
            except ValueError:
                return val
        return default

async def set_setting(pool, key: str, value):
    """Сохранить или обновить значение настройки в базе данных"""
    if not pool:
        return
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO settings (key, value)
            VALUES ($1, $2)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, key, str(value))