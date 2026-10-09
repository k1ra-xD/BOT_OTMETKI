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
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: var(--tg-theme-bg-color, #f4f4f9); color: var(--tg-theme-text-color, #222); padding: 16px; margin: 0; }
        .card { background: var(--tg-theme-secondary-bg-color, #fff); border-radius: 12px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .stat-num { font-size: 24px; font-weight: bold; color: var(--tg-theme-button-color, #0088cc); }
        .status-badge { display: inline-block; padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: bold; }
        .active { background: #e3f8e0; color: #2e7d32; }
        ul { list-style: none; padding: 0; margin: 8px 0 0 0; }
        li { padding: 10px 0; border-bottom: 1px solid rgba(0,0,0,0.05); font-size: 14px; display: flex; justify-content: space-between; align-items: center; }
        li:last-child { border-bottom: none; }
        .time { font-size: 12px; color: #888; font-weight: normal; }
        .sub-text { font-size: 12px; color: #666; display: block; margin-top: 2px; }
    </style>
</head>
<body>
    <h2>📊 Дашборд Посещаемости</h2>
    <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <span>Статус базы:</span>
            <span id="session-status" class="status-badge active">Подключено</span>
        </div>
    </div>
    <div class="stat-grid">
        <div class="card"><div>Всего студентов</div><div id="total-students" class="stat-num">0</div></div>
        <div class="card"><div>Всего отметок</div><div id="responded-count" class="stat-num">0</div></div>
    </div>
    <div class="card">
        <h3>📍 Последние отметки:</h3>
        <ul id="responses-list"><li><i>Загрузка данных...</i></li></ul>
    </div>
    <script>
        const tg = window.Telegram.WebApp; 
        tg.ready();
        tg.expand();

        async function loadStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                
                document.getElementById('total-students').innerText = data.total_students || 0;
                document.getElementById('responded-count').innerText = data.responded_count || 0;
                
                const list = document.getElementById('responses-list');
                list.innerHTML = '';
                
                if (data.responses && data.responses.length > 0) {
                    data.responses.forEach(r => {
                        const li = document.createElement('li');
                        const subj = r.subject ? ` (${r.subject})` : '';
                        const time = r.time ? `<span class="time">${r.time}</span>` : '';
                        const statusBadge = r.status ? `<span style="font-size:11px; margin-left:6px; padding:2px 6px; border-radius:4px; background:rgba(0,0,0,0.06); font-weight:bold;">${r.status}</span>` : '';
                        li.innerHTML = `
                            <div>
                                <b>${r.name}</b> ${statusBadge}
                                <span class="sub-text">Дистанция: ~${Math.round(r.dist)}м ${subj}</span>
                            </div>
                            ${time}
                        `;
                        list.appendChild(li);
                    });
                } else {
                    list.innerHTML = '<li><i>Пока нет сохранённых отметок</i></li>';
                }
            } catch(e) { 
                console.error(e); 
            }
        }
        loadStats();
        setInterval(loadStats, 3000);
    </script>
</body>
</html>
"""

def create_web_app(get_db_pool, current_session=None):
    app = web.Application()

    async def handle_dashboard(request):
        return web.Response(text=DASHBOARD_HTML, content_type='text/html')

    async def handle_api_stats(request):
        db_pool = get_db_pool()
        if not db_pool:
            return web.json_response({"error": "No DB connection"}, status=500)

        async with db_pool.acquire() as conn:
            # Общее количество зарегистрированных студентов
            total_students = await conn.fetchval("SELECT COUNT(*) FROM students")
            
            # Чтение отметок из таблицы attendance
            rows = await conn.fetch("""
                SELECT 
                    COALESCE(s.full_name, 'ID: ' || a.telegram_id::text) AS name,
                    a.distance,
                    a.subject,
                    a.checkin_time,
                    a.status
                FROM attendance a
                LEFT JOIN students s ON a.telegram_id = s.telegram_id
                ORDER BY a.checkin_time DESC
                LIMIT 50
            """)

        responses_data = []
        for r in rows:
            time_formatted = r['checkin_time'].strftime("%d.%m %H:%M") if r['checkin_time'] else ""
            responses_data.append({
                "name": r['name'],
                "dist": r['distance'] or 0,
                "subject": r['subject'] or "",
                "time": time_formatted,
                "status": r['status'] or ""
            })
                
        return web.json_response({
            "is_active": True,
            "total_students": total_students or 0,
            "responded_count": len(responses_data),
            "responses": responses_data
        })

    async def handle_root(request):
        return web.Response(text="Bot is running! 🚀", content_type="text/plain", status=200)

    app.router.add_get('/', handle_root)
    app.router.add_get('/ping', handle_root)
    app.router.add_get('/dashboard', handle_dashboard)
    app.router.add_get('/api/stats', handle_api_stats)
    return app