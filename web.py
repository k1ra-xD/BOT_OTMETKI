from aiohttp import web

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Дашборд Посещаемости</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { font-family: sans-serif; background: var(--tg-theme-bg-color, #f4f4f9); color: var(--tg-theme-text-color, #222); padding: 16px; margin: 0; }
        .card { background: var(--tg-theme-secondary-bg-color, #fff); border-radius: 12px; padding: 16px; margin-bottom: 12px; }
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .stat-num { font-size: 24px; font-weight: bold; color: var(--tg-theme-button-color, #0088cc); }
        .status-badge { display: inline-block; padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: bold; }
        .active { background: #e3f8e0; color: #2e7d32; }
        .inactive { background: #ffebee; color: #c62828; }
        ul { list-style: none; padding: 0; margin: 8px 0 0 0; }
        li { padding: 6px 0; border-bottom: 1px solid rgba(0,0,0,0.05); font-size: 14px; }
    </style>
</head>
<body>
    <h2>📊 Дашборд Посещаемости</h2>
    <div class="card"><div style="display:flex; justify-content:space-between; align-items:center;"><span>Статус проверки:</span><span id="session-status" class="status-badge inactive">Завершена</span></div></div>
    <div class="stat-grid">
        <div class="card"><div>Всего студентов</div><div id="total-students" class="stat-num">0</div></div>
        <div class="card"><div>Ответили сейчас</div><div id="responded-count" class="stat-num">0</div></div>
    </div>
    <div class="card"><h3>📍 Откликнулись:</h3><ul id="responses-list"><li><i>Список пуст</i></li></ul></div>
    <script>
        const tg = window.Telegram.WebApp; tg.expand();
        async function loadStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                document.getElementById('total-students').innerText = data.total_students;
                document.getElementById('responded-count').innerText = data.responded_count;
                const statusBadge = document.getElementById('session-status');
                if (data.is_active) { 
                    statusBadge.innerText = 'Активна'; 
                    statusBadge.className = 'status-badge active'; 
                } else { 
                    statusBadge.innerText = 'Завершена'; 
                    statusBadge.className = 'status-badge inactive'; 
                }
                const list = document.getElementById('responses-list');
                list.innerHTML = '';
                if (data.responses && data.responses.length > 0) {
                    data.responses.forEach(r => {
                        const li = document.createElement('li');
                        li.innerText = `${r.name} — ~${Math.round(r.dist)}м`;
                        list.appendChild(li);
                    });
                } else {
                    list.innerHTML = '<li><i>Список пуст</i></li>';
                }
            } catch(e) { console.error(e); }
        }
        loadStats();
        setInterval(loadStats, 3000);
    </script>
</body>
</html>
"""

def create_web_app(get_db_pool, current_session):
    app = web.Application()

    async def handle_dashboard(request):
        return web.Response(text=DASHBOARD_HTML, content_type='text/html')

    async def handle_api_stats(request):
        db_pool = get_db_pool()
        async with db_pool.acquire() as conn:
            total_students = await conn.fetchval("SELECT COUNT(*) FROM students")
            
        responses_data = []
        async with db_pool.acquire() as conn:
            for t_id, d in current_session["responses"].items():
                row = await conn.fetchrow("SELECT full_name FROM students WHERE telegram_id = $1", t_id)
                name = row['full_name'] if row else "Неизвестный"
                responses_data.append({"name": name, "dist": d["dist"]})
                
        return web.json_response({
            "is_active": current_session["is_active"],
            "total_students": total_students or 0,
            "responded_count": len(current_session["responses"]),
            "responses": responses_data
        })

    async def handle_root(request):
        return web.Response(text="Bot is running! 🚀", content_type="text/plain", status=200)

    app.router.add_get('/', handle_root)
    app.router.add_get('/ping', handle_root)
    app.router.add_get('/dashboard', handle_dashboard)
    app.router.add_get('/api/stats', handle_api_stats)
    return app