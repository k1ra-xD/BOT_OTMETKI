import os
import re
import io
import aiohttp
from datetime import datetime, timedelta
from config import ASTANA_TZ

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

async def transcribe_audio_bytes(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    """
    Распознает аудио в текст с использованием бесплатных API:
    1. Groq (Whisper-large-v3) - 100% бесплатно, молниеносно, принимает .ogg и .webm напрямую
    2. Google Gemini Flash (если указан GEMINI_API_KEY)
    """
    # Определяем MIME тип по расширению файла
    mime_type = "audio/ogg"
    if filename.endswith(".webm"):
        mime_type = "audio/webm"
    elif filename.endswith(".mp3"):
        mime_type = "audio/mp3"
    elif filename.endswith(".wav"):
        mime_type = "audio/wav"

    # 1. Проверяем Groq API
    groq_key = os.environ.get("GROQ_API_KEY", GROQ_API_KEY)
    if groq_key:
        try:
            url = "https://api.groq.com/openai/v1/audio/transcriptions"
            headers = {"Authorization": f"Bearer {groq_key}"}
            
            data = aiohttp.FormData()
            data.add_field("file", audio_bytes, filename=filename, content_type=mime_type)
            data.add_field("model", "whisper-large-v3")
            data.add_field("language", "ru")
            data.add_field("response_format", "json")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=data, timeout=20) as resp:
                    if resp.status == 200:
                        res_json = await resp.json()
                        text = res_json.get("text", "").strip()
                        if text:
                            return text
                    else:
                        err = await resp.text()
                        print(f"Groq Whisper error {resp.status}: {err}")
        except Exception as e:
            print(f"Ошибка Groq Whisper: {e}")

    # 2. Проверяем Gemini Flash API
    gemini_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)
    if gemini_key:
        try:
            import base64
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            payload = {
                "contents": [{
                    "parts": [
                        {"text": "Точно расшифруй аудио на русском языке. Верни ТОЛЬКО расшифрованный текст без лишних комментариев, пояснений и кавычек."},
                        {"inline_data": {"mime_type": mime_type, "data": audio_b64}}
                    ]
                }]
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=20) as resp:
                    if resp.status == 200:
                        res_json = await resp.json()
                        candidates = res_json.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                return parts[0].get("text", "").strip()
        except Exception as e:
            print(f"Ошибка Gemini Audio: {e}")

    return ""

def parse_task_time_and_title(text: str) -> tuple[str, str, str]:
    """
    Анализирует текст задачи и пытается определить дату и время напоминания.
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

    # Поиск времени формата "в 15:00" или "15:30" или "в 15 часов"
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

    # Убираем вводные слова вроде "напомни", "напомнить", "запиши", лишние знаки
    clean_text = re.sub(r'^(напомни|напомнить|запиши|добавь|поставь)\s+(мне\s+)?(что\s+)?', '', clean_text, flags=re.IGNORECASE).strip()
    clean_text = re.sub(r'\s+', ' ', clean_text).strip(' ,.;:-')

    if not clean_text:
        clean_text = text.strip()

    # Капитализируем первую букву
    if clean_text:
        clean_text = clean_text[0].upper() + clean_text[1:]

    return clean_text, target_date, target_time
