import os
import re
import shutil
import asyncio
import platform
import aiohttp
from aiogram import Bot
from aiogram.types import WebAppInfo, MenuButtonWebApp
from config import ADMIN_ID, set_webapp_url


async def _ensure_cloudflared_binary() -> str | None:
    """Возвращает путь к бинарнику cloudflared; на Linux скачивает при отсутствии."""
    existing = shutil.which("cloudflared")
    if existing:
        return existing

    system = platform.system()
    if system == "Windows":
        local_win = os.path.join(os.getcwd(), "cloudflared.exe")
        return local_win if os.path.exists(local_win) else None

    if system != "Linux":
        return None

    local_bin = os.path.join(os.getcwd(), "cloudflared")
    if os.path.exists(local_bin):
        os.chmod(local_bin, 0o755)
        return local_bin

    machine = platform.machine().lower()
    arch = "arm64" if ("aarch64" in machine or "arm64" in machine) else "amd64"
    url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{arch}"

    print(f"⬇️ Скачиваю cloudflared ({arch}) для HTTPS-туннеля...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    print(f"⚠️ Не удалось скачать cloudflared: HTTP {resp.status}")
                    return None
                with open(local_bin, "wb") as f:
                    while True:
                        chunk = await resp.content.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
        os.chmod(local_bin, 0o755)
        print("✅ cloudflared скачан и готов к работе")
        return local_bin
    except Exception as e:
        print(f"⚠️ Ошибка загрузки cloudflared: {e}")
        return None


async def start_cloudflared_tunnel(port: int, bot: Bot):
    """Запускает бесплатный HTTPS-туннель Cloudflare и обновляет ссылку WebApp для админа."""
    bin_path = await _ensure_cloudflared_binary()
    if not bin_path:
        print("ℹ️ cloudflared недоступен, WebApp будет использовать URL из конфига")
        return

    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    while True:
        try:
            proc = await asyncio.create_subprocess_exec(
                bin_path, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )

            found_url = None
            while True:
                line_bytes = await proc.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="ignore")
                if not found_url:
                    match = url_pattern.search(line)
                    if match:
                        found_url = match.group(0)
                        set_webapp_url(found_url)
                        print(f"🔗 WebApp HTTPS-туннель запущен: {found_url}/dashboard")
                        if ADMIN_ID and bot:
                            try:
                                await bot.set_chat_menu_button(
                                    chat_id=ADMIN_ID,
                                    menu_button=MenuButtonWebApp(
                                        text="📊 Дашборд",
                                        web_app=WebAppInfo(url=f"{found_url}/dashboard?v=3")
                                    )
                                )
                            except Exception as e:
                                print(f"⚠️ Не удалось обновить кнопку меню админа: {e}")

            await proc.wait()
            print("⚠️ Туннель cloudflared остановился, перезапуск через 5 секунд...")
        except Exception as e:
            print(f"⚠️ Ошибка туннеля cloudflared: {e}")
        await asyncio.sleep(5)
