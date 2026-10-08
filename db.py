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
        """)
        
        await conn.execute("INSERT INTO settings (key, value) VALUES ('lat', $1) ON CONFLICT (key) DO NOTHING", str(DEFAULT_UNI_LAT))
        await conn.execute("INSERT INTO settings (key, value) VALUES ('lon', $1) ON CONFLICT (key) DO NOTHING", str(DEFAULT_UNI_LON))
        await conn.execute("INSERT INTO settings (key, value) VALUES ('radius', $1) ON CONFLICT (key) DO NOTHING", str(DEFAULT_RADIUS))

async def get_setting(db_pool: asyncpg.Pool, key: str, default):
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

async def set_setting(db_pool: asyncpg.Pool, key: str, value):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO settings (key, value) VALUES ($1, $2)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, key, str(value))