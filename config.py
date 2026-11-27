import os
from datetime import timezone, timedelta

TOKEN = os.environ.get("BOT_TOKEN", "8932791447:AAGB5HfDMv1Jq7yMwVwko9YVl7rubu7F3tM")
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    "mysql://u1962_P3X4q5c0aC:CSGN0uttr!VqxpO7Ts8n!73p@ast.altyn.games:13306/s1962_schedule"
)
MYSQL_HOST = os.environ.get("MYSQL_HOST", "ast.altyn.games")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 13306))
MYSQL_USER = os.environ.get("MYSQL_USER", "u1962_P3X4q5c0aC")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "CSGN0uttr!VqxpO7Ts8n!73p")
MYSQL_DB = os.environ.get("MYSQL_DB", "s1962_schedule")

ADMIN_ID = 1231388093
ADMIN_NAME = "Кирович Георгий"

SCHEDULE_PAGE_URL = "https://esil.edu.kz/students_schedule/"
LOCAL_FILE_NAME = "target_schedule.xlsx"
TARGET_GROUP = "Б-ИТЗД 26/23 Р" 
TARGET_SHEET = "рус Прик 1,3 1,2"

DEFAULT_UNI_LAT = 51.159555 
DEFAULT_UNI_LON = 71.458555
DEFAULT_RADIUS = 150

ASTANA_TZ = timezone(timedelta(hours=5))

DAYS_MAP = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье"
}