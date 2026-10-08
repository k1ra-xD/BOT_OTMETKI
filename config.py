import os
from datetime import timezone, timedelta

TOKEN = os.environ.get("BOT_TOKEN", "8932791447:AAGB5HfDMv1Jq7yMwVwko9YVl7rubu7F3tM")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres.stduhsqtkysawtahgftq:7htTw1GOgUV7XXb2@aws-0-eu-west-1.pooler.supabase.com:6543/postgres")
ADMIN_ID = 1231388093

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