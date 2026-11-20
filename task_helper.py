import re
from datetime import datetime, timedelta
from config import ASTANA_TZ

def parse_task_time_and_title(text: str) -> tuple[str, str, str]:
    """
    Анализирует текст задачи и определяет дату и время напоминания.
    Возвращает (title, target_date, target_time)
    """
    clean_text = text.strip()
    now = datetime.now(ASTANA_TZ)
    target_date = now.strftime("%Y-%m-%d")
    target_time = ""

    # Проверка "завтра"
    if re.search(r'\bзавтра\b', clean_text, re.IGNORECASE):
        target_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        clean_text = re.sub(r'\bзавтра\b', '', clean_text, flags=re.IGNORECASE).strip()
    # Проверка "послезавтра"
    elif re.search(r'\bпослезавтра\b', clean_text, re.IGNORECASE):
        target_date = (now + timedelta(days=2)).strftime("%Y-%m-%d")
        clean_text = re.sub(r'\bпослезавтра\b', '', clean_text, flags=re.IGNORECASE).strip()
    # Проверка "сегодня"
    elif re.search(r'\bсегодня\b', clean_text, re.IGNORECASE):
        target_date = now.strftime("%Y-%m-%d")
        clean_text = re.sub(r'\bсегодня\b', '', clean_text, flags=re.IGNORECASE).strip()

    # Поиск времени формата "в 15:00" или "15:30"
    time_match = re.search(r'(?:в\s*)?(\d{1,2})[:.](\d{2})', clean_text, re.IGNORECASE)
    if time_match:
        h, m = int(time_match.group(1)), int(time_match.group(2))
        if 0 <= h <= 23 and 0 <= m <= 59:
            target_time = f"{h:02d}:{m:02d}"
            clean_text = clean_text[:time_match.start()] + clean_text[time_match.end():]
    else:
        hour_match = re.search(r'(?:в\s*)(\d{1,2})\s*(?:час|ч)', clean_text, re.IGNORECASE)
        if hour_match:
            h = int(hour_match.group(1))
            if 0 <= h <= 23:
                target_time = f"{h:02d}:00"
                clean_text = clean_text[:hour_match.start()] + clean_text[hour_match.end():]

    # Убираем служебные слова
    clean_text = re.sub(r'^(напомни|напомнить|запиши|добавь|поставь)\s+(мне\s+)?(что\s+)?', '', clean_text, flags=re.IGNORECASE).strip()
    clean_text = re.sub(r'\s+', ' ', clean_text).strip(' ,.;:-')

    if not clean_text:
        clean_text = text.strip()

    if clean_text:
        clean_text = clean_text[0].upper() + clean_text[1:]

    return clean_text, target_date, target_time
