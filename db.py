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
            CREATE TABLE IF NOT EXISTS island_tasks (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                title TEXT,
                target_date TEXT,
                target_time TEXT,
                is_completed BOOLEAN DEFAULT FALSE,
                is_spoken BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

# ==========================================
# Dynamic Island Task Helpers
# ==========================================

async def add_island_task(pool, user_id: int, title: str, target_date: str = "", target_time: str = ""):
    """Добавить задачу для Dynamic Island"""
    if not pool:
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO island_tasks (user_id, title, target_date, target_time, is_completed, is_spoken)
            VALUES ($1, $2, $3, $4, FALSE, FALSE)
            RETURNING id, title, target_date, target_time, is_completed, is_spoken
        """, user_id, title, target_date, target_time)
        return dict(row) if row else None

async def get_active_island_tasks(pool, user_id: int = None):
    """Получить незавершенные задачи"""
    if not pool:
        return []
    async with pool.acquire() as conn:
        if user_id:
            rows = await conn.fetch("""
                SELECT id, user_id, title, target_date, target_time, is_completed, is_spoken, created_at
                FROM island_tasks
                WHERE user_id = $1 AND is_completed = FALSE
                ORDER BY created_at ASC
            """, user_id)
        else:
            rows = await conn.fetch("""
                SELECT id, user_id, title, target_date, target_time, is_completed, is_spoken, created_at
                FROM island_tasks
                WHERE is_completed = FALSE
                ORDER BY created_at ASC
            """)
        return [dict(r) for r in rows]

async def mark_island_task_spoken(pool, task_id: int):
    """Отметить задачу как проговоренную вслух"""
    if not pool:
        return False
    async with pool.acquire() as conn:
        await conn.execute("UPDATE island_tasks SET is_spoken = TRUE WHERE id = $1", task_id)
        return True

async def mark_island_task_completed(pool, task_id: int):
    """Отметить задачу как выполненную"""
    if not pool:
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE island_tasks 
            SET is_completed = TRUE 
            WHERE id = $1
            RETURNING id, user_id, title
        """, task_id)
        return dict(row) if row else None
