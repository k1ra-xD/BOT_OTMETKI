import re
from urllib.parse import urlparse, unquote
import aiomysql
from config import (
    DATABASE_URL, MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB,
    DEFAULT_UNI_LAT, DEFAULT_UNI_LON, DEFAULT_RADIUS
)

def get_db_connection_params():
    """Извлекает параметры подключения к MySQL из DATABASE_URL или отдельных переменных."""
    if DATABASE_URL and (DATABASE_URL.startswith("mysql://") or DATABASE_URL.startswith("mariadb://")):
        parsed = urlparse(DATABASE_URL)
        return {
            "host": parsed.hostname or MYSQL_HOST,
            "port": parsed.port or MYSQL_PORT,
            "user": unquote(parsed.username) if parsed.username else MYSQL_USER,
            "password": unquote(parsed.password) if parsed.password else MYSQL_PASSWORD,
            "db": (parsed.path.lstrip("/") if parsed.path else "") or MYSQL_DB
        }
    return {
        "host": MYSQL_HOST,
        "port": MYSQL_PORT,
        "user": MYSQL_USER,
        "password": MYSQL_PASSWORD,
        "db": MYSQL_DB
    }

def _prepare_sql(query: str, has_args: bool = False) -> str:
    """Адаптирует PostgreSQL-запросы к синтаксису MySQL."""
    # 1. Заменяем $1, $2, $3 и уже готовые %s на плейсхолдер
    sql = re.sub(r'\$\d+|%s', '___PARAM___', query)
    if has_args:
        # Экранируем символы процента для PyMySQL
        sql = sql.replace('%', '%%')
    sql = sql.replace('___PARAM___', '%s')
    # 2. Заменяем ILIKE на LIKE (в MySQL utf8mb4 поиск регистронезависим)
    sql = re.sub(r'\bILIKE\b', 'LIKE', sql, flags=re.IGNORECASE)
    return sql

class MySQLConnectionWrapper:
    def __init__(self, raw_conn):
        self._conn = raw_conn
        self.lastrowid = None

    async def execute(self, query: str, *args):
        has_args = bool(args)
        sql = _prepare_sql(query, has_args=has_args)
        async with self._conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, args if has_args else None)
            self.lastrowid = cur.lastrowid
            return cur.rowcount

    async def fetch(self, query: str, *args) -> list[dict]:
        has_args = bool(args)
        sql = _prepare_sql(query, has_args=has_args)
        async with self._conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, args if has_args else None)
            return await cur.fetchall()

    async def fetchrow(self, query: str, *args) -> dict | None:
        has_args = bool(args)
        sql = _prepare_sql(query, has_args=has_args)
        async with self._conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, args if has_args else None)
            return await cur.fetchone()

    async def fetchval(self, query: str, *args):
        has_args = bool(args)
        sql = _prepare_sql(query, has_args=has_args)
        async with self._conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, args if has_args else None)
            row = await cur.fetchone()
            if row:
                return next(iter(row.values()))
            return None


class _PoolAcquireContext:
    def __init__(self, pool):
        self._pool = pool
        self._raw_conn = None

    async def __aenter__(self):
        self._raw_conn = await self._pool._raw_pool.acquire()
        return MySQLConnectionWrapper(self._raw_conn)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._raw_conn is not None:
            self._pool._raw_pool.release(self._raw_conn)


class MySQLPoolWrapper:
    def __init__(self, raw_pool):
        self._raw_pool = raw_pool

    def acquire(self):
        return _PoolAcquireContext(self)

    def close(self):
        self._raw_pool.close()

    async def wait_closed(self):
        await self._raw_pool.wait_closed()


async def create_db_pool():
    """Создает пул подключений к MySQL базе данных."""
    cfg = get_db_connection_params()
    raw_pool = await aiomysql.create_pool(
        host=cfg['host'],
        port=cfg['port'],
        user=cfg['user'],
        password=cfg['password'],
        db=cfg['db'],
        charset='utf8mb4',
        autocommit=True,
        minsize=1,
        maxsize=10
    )
    return MySQLPoolWrapper(raw_pool)


async def init_db(db_pool):
    """Инициализация таблиц базы данных в MySQL."""
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                telegram_id BIGINT PRIMARY KEY,
                full_name VARCHAR(255)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS banned_users (
                telegram_id BIGINT PRIMARY KEY
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                `key` VARCHAR(191) PRIMARY KEY,
                `value` TEXT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schedule (
                id INT AUTO_INCREMENT PRIMARY KEY,
                day_of_week INT,
                time_start VARCHAR(50),
                time_end VARCHAR(50),
                subject VARCHAR(255),
                lesson_type VARCHAR(100),
                teacher VARCHAR(255),
                room VARCHAR(100),
                online_link TEXT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INT AUTO_INCREMENT PRIMARY KEY,
                telegram_id BIGINT,
                subject VARCHAR(255),
                checkin_time DATETIME,
                status VARCHAR(255),
                distance INT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS active_reminders (
                telegram_id BIGINT PRIMARY KEY,
                message_id BIGINT,
                delete_at BIGINT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        await conn.execute("INSERT IGNORE INTO settings (`key`, `value`) VALUES ('lat', %s)", str(DEFAULT_UNI_LAT))
        await conn.execute("INSERT IGNORE INTO settings (`key`, `value`) VALUES ('lon', %s)", str(DEFAULT_UNI_LON))
        await conn.execute("INSERT IGNORE INTO settings (`key`, `value`) VALUES ('radius', %s)", str(DEFAULT_RADIUS))


async def get_setting(pool, key: str, default=None):
    """Получить значение настройки из базы данных"""
    if not pool:
        return default
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT `value` FROM settings WHERE `key` = %s", key)
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
            INSERT INTO settings (`key`, `value`)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE `value` = VALUES(`value`)
        """, key, str(value))
