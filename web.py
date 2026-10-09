from datetime import datetime, timedelta
from aiohttp import web
from config import ASTANA_TZ

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Дашборд Посещаемости</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--tg-theme-bg-color, #f4f4f9); color: var(--tg-theme-text-color, #222); padding: 16px; margin: 0; }
        .card { background: var(--tg-theme-secondary-bg-color, #fff); border-radius: 14px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 12px; }
        .stat-card { background: var(--tg-theme-secondary-bg-color, #fff); border-radius: 12px; padding: 12px 6px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .stat-title { font-size: 11px; color: #777; margin-bottom: 4px; }
        .stat-num { font-size: 20px; font-weight: bold; color: var(--tg-theme-button-color, #0088cc); }
        .stat-num.green { color: #2e7d32; }
        .stat-num.red { color: #c62828; }
        .tabs { display: flex; border-bottom: 1px solid rgba(0,0,0,0.08); margin-bottom: 12px; }
        .tab-btn { flex: 1; text-align: center; background: none; border: none; padding: 10px 4px; font-size: 14px; font-weight: 600; cursor: pointer; color: #888; border-bottom: 2px solid transparent; }
        .tab-btn.active { color: var(--tg-theme-button-color, #0088cc); border-bottom: 2px solid var(--tg-theme-button-color, #0088cc); }
        .filter-select { width: 100%; padding: 8px 12px; border-radius: 8px; border: 1px solid #ddd; background: var(--tg-theme-bg-color, #f9f9fc); color: var(--tg-theme-text-color, #222); font-size: 13px; margin-bottom: 12px; box-sizing: border-box; }
        ul { list-style: none; padding: 0; margin: 0; }
        li { padding: 10px 0; border-bottom: 1px solid rgba(0,0,0,0.05); font-size: 14px; display: flex; justify-content: space-between; align-items: center; }
        li:last-child { border-bottom: none; }
        .sub-text { font-size: 12px; color: #666; display: block; margin-top: 3px; }
        .time { font-size: 12px; color: #888; white-space: nowrap; margin-left: 8px; }
        .badge { display: inline-block; padding: 2px 7px; border-radius: 6px; font-size: 11px; font-weight: bold; margin-left: 4px; vertical-align: middle; }
        .badge-success { background: #e8f5e9; color: #2e7d32; border: 1px solid #c8e6c9; }
        .badge-warning { background: #fff8e1; color: #f57f17; border: 1px solid #ffecb3; }
        .badge-danger { background: #ffebee; color: #c62828; border: 1px solid #ffcdd2; }
        .badge-info { background: #e3f2fd; color: #1565c0; border: 1px solid #bbdefb; }
        .status-badge { display: inline-block; padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: bold; background: #e3f8e0; color: #2e7d32; }
        .empty-box { text-align: center; color: #888; padding: 20px 0; font-size: 14px; }
    </style>
</head>
<body>
    <div class="header">
        <h2 style="margin:0; font-size:18px;">📊 Посещаемость сегодня</h2>
        <span class="status-badge">🟢 Онлайн</span>
    </div>

    <div class="stat-grid">
        <div class="stat-card">
            <div class="stat-title">Всего в группе</div>
            <div id="total-students" class="stat-num">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-title">Присутствуют</div>
            <div id="present-count" class="stat-num green">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-title">Отсутствуют</div>
            <div id="absent-count" class="stat-num red">0</div>
        </div>
    </div>

    <div class="card">
        <div class="tabs">
            <button id="tab-present" class="tab-btn active" onclick="switchTab('present')">📍 Отметились (<span id="tab-present-num">0</span>)</button>
            <button id="tab-absent" class="tab-btn" onclick="switchTab('absent')">🚫 Отсутствуют (<span id="tab-absent-num">0</span>)</button>
        </div>

        <div id="filter-wrapper" style="display:block;">
            <select id="subject-filter" class="filter-select" onchange="renderLists()">
                <option value="">Все предметы за сегодня</option>
            </select>
        </div>

        <div id="present-container">
            <ul id="present-list"><li><i>Загрузка данных...</i></li></ul>
        </div>

        <div id="absent-container" style="display:none;">
            <ul id="absent-list"><li><i>Загрузка данных...</i></li></ul>
        </div>
    </div>

    <script>
        const tg = window.Telegram.WebApp; 
        tg.ready();
        tg.expand();

        let allData = { responses: [], absent: [], subjects: [] };
        let activeTab = 'present';

        function switchTab(tab) {
            activeTab = tab;
            document.getElementById('tab-present').className = 'tab-btn' + (tab === 'present' ? ' active' : '');
            document.getElementById('tab-absent').className = 'tab-btn' + (tab === 'absent' ? ' active' : '');
            document.getElementById('present-container').style.display = tab === 'present' ? 'block' : 'none';
            document.getElementById('absent-container').style.display = tab === 'absent' ? 'block' : 'none';
            document.getElementById('filter-wrapper').style.display = tab === 'present' ? 'block' : 'none';
            renderLists();
        }

        function getStatusBadgeClass(status) {
            if (!status) return 'badge-info';
            if (status.includes('Вовремя')) return 'badge-success';
            if (status.includes('Опоздание')) return 'badge-warning';
            if (status.includes('Вне зоны')) return 'badge-danger';
            return 'badge-info';
        }

        function renderLists() {
            // Обновление предметов в фильтре
            const select = document.getElementById('subject-filter');
            const currentSelected = select.value;
            const subjects = allData.subjects || [];
            
            let optionsHtml = '<option value="">Все предметы за сегодня</option>';
            subjects.forEach(s => {
                const sel = s === currentSelected ? 'selected' : '';
                optionsHtml += `<option value="${s}" ${sel}>${s}</option>`;
            });
            select.innerHTML = optionsHtml;

            // Рендер присутствующих
            const selectedSubject = select.value;
            const presentList = document.getElementById('present-list');
            presentList.innerHTML = '';
            
            let filteredResponses = allData.responses || [];
            if (selectedSubject) {
                filteredResponses = filteredResponses.filter(r => r.subject === selectedSubject);
            }

            if (filteredResponses.length > 0) {
                filteredResponses.forEach(r => {
                    const li = document.createElement('li');
                    const subj = r.subject ? ` (${r.subject})` : '';
                    const time = r.time ? `<span class="time">${r.time}</span>` : '';
                    const badgeClass = getStatusBadgeClass(r.status);
                    const badgeHtml = r.status ? `<span class="badge ${badgeClass}">${r.status}</span>` : '';
                    
                    li.innerHTML = `
                        <div>
                            <b>${r.name}</b> ${badgeHtml}
                            <span class="sub-text">📍 ~${Math.round(r.dist)}м ${subj}</span>
                        </div>
                        ${time}
                    `;
                    presentList.appendChild(li);
                });
            } else {
                presentList.innerHTML = '<div class="empty-box">Сегодня пока нет отметок</div>';
            }

            // Рендер отсутствующих
            const absentList = document.getElementById('absent-list');
            absentList.innerHTML = '';
            const absentStudents = allData.absent || [];
            if (absentStudents.length > 0) {
                absentStudents.forEach(s => {
                    const li = document.createElement('li');
                    li.innerHTML = `
                        <div>
                            <b>${s.name}</b>
                            <span class="sub-text" style="color:#d32f2f;">❌ Нет отметки за сегодня</span>
                        </div>
                        <span class="badge badge-danger">Отсутствует</span>
                    `;
                    absentList.appendChild(li);
                });
            } else {
                absentList.innerHTML = '<div class="empty-box" style="color:#2e7d32;">🎉 Все студенты на парах!</div>';
            }
        }

        async function loadStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                allData = data;
                
                document.getElementById('total-students').innerText = data.total_students || 0;
                document.getElementById('present-count').innerText = data.present_count || 0;
                document.getElementById('absent-count').innerText = data.absent_count || 0;
                document.getElementById('tab-present-num').innerText = data.present_count || 0;
                document.getElementById('tab-absent-num').innerText = data.absent_count || 0;
                
                renderLists();
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

        now = datetime.now(ASTANA_TZ)
        today_start = datetime(now.year, now.month, now.day)
        today_end = today_start + timedelta(days=1)

        async with db_pool.acquire() as conn:
            # Все зарегистрированные студенты группы
            all_students = await conn.fetch("SELECT telegram_id, full_name FROM students ORDER BY full_name ASC")
            
            # Чтение отметок из таблицы attendance только за сегодня
            rows = await conn.fetch("""
                SELECT 
                    a.telegram_id,
                    COALESCE(s.full_name, 'ID: ' || a.telegram_id::text) AS name,
                    a.distance,
                    a.subject,
                    a.checkin_time,
                    a.status
                FROM attendance a
                LEFT JOIN students s ON a.telegram_id = s.telegram_id
                WHERE a.checkin_time >= $1 AND a.checkin_time < $2
                ORDER BY a.checkin_time DESC
                LIMIT 100
            """, today_start, today_end)

        checked_in_ids = set()
        responses_data = []
        subjects_today = set()

        for r in rows:
            checked_in_ids.add(r['telegram_id'])
            if r['subject'] and r['subject'] not in ["Вне пар", "Вне зоны ВУЗа"]:
                subjects_today.add(r['subject'])
            time_formatted = r['checkin_time'].strftime("%H:%M") if r['checkin_time'] else ""
            responses_data.append({
                "name": r['name'],
                "dist": r['distance'] or 0,
                "subject": r['subject'] or "",
                "time": time_formatted,
                "status": r['status'] or ""
            })

        # Отсутствующие студенты
        absent_data = []
        for s in all_students:
            if s['telegram_id'] not in checked_in_ids:
                absent_data.append({
                    "name": s['full_name'],
                    "telegram_id": s['telegram_id']
                })

        return web.json_response({
            "is_active": True,
            "total_students": len(all_students),
            "present_count": len(checked_in_ids),
            "absent_count": len(absent_data),
            "responses": responses_data,
            "absent": absent_data,
            "subjects": sorted(list(subjects_today))
        })

    async def handle_root(request):
        return web.Response(text="Bot is running! 🚀", content_type="text/plain", status=200)

    app.router.add_get('/', handle_root)
    app.router.add_get('/ping', handle_root)
    app.router.add_get('/dashboard', handle_dashboard)
    app.router.add_get('/api/stats', handle_api_stats)
    return app
