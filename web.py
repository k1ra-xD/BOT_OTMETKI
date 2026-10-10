from datetime import datetime, timedelta
from aiohttp import web
from config import ASTANA_TZ

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Дашборд Посещаемости</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root {
            --bg-color: var(--tg-theme-bg-color, #0f172a);
            --card-bg: var(--tg-theme-secondary-bg-color, #1e293b);
            --text-color: var(--tg-theme-text-color, #f8fafc);
            --hint-color: var(--tg-theme-hint-color, #94a3b8);
            --button-color: var(--tg-theme-button-color, #3b82f6);
            --button-text: var(--tg-theme-button-text-color, #ffffff);
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            padding: 12px;
            margin: 0;
            -webkit-font-smoothing: antialiased;
        }

        .app-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            padding: 4px 8px;
        }

        .app-title {
            font-size: 18px;
            font-weight: 700;
            letter-spacing: -0.3px;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
            background: rgba(34, 197, 94, 0.15);
            color: #4ade80;
            border: 1px solid rgba(34, 197, 94, 0.3);
        }

        .pulse-dot {
            width: 7px;
            height: 7px;
            background-color: #4ade80;
            border-radius: 50%;
            box-shadow: 0 0 0 rgba(74, 222, 128, 0.4);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(74, 222, 128, 0.6); }
            70% { box-shadow: 0 0 0 6px rgba(74, 222, 128, 0); }
            100% { box-shadow: 0 0 0 0 rgba(74, 222, 128, 0); }
        }

        .stat-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
            margin-bottom: 14px;
        }

        .stat-card {
            background: var(--card-bg);
            border-radius: 14px;
            padding: 12px 6px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.04);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }

        .stat-title {
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--hint-color);
            margin-bottom: 6px;
            font-weight: 600;
        }

        .stat-num {
            font-size: 20px;
            font-weight: 800;
        }

        .stat-num.blue { color: #60a5fa; }
        .stat-num.green { color: #4ade80; }
        .stat-num.red { color: #f87171; }

        .card {
            background: var(--card-bg);
            border-radius: 16px;
            padding: 14px;
            margin-bottom: 12px;
            border: 1px solid rgba(255, 255, 255, 0.04);
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
        }

        .tabs {
            display: flex;
            background: rgba(0, 0, 0, 0.15);
            border-radius: 10px;
            padding: 3px;
            margin-bottom: 12px;
        }

        .tab-btn {
            flex: 1;
            text-align: center;
            background: none;
            border: none;
            padding: 8px 4px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            color: var(--hint-color);
            border-radius: 8px;
            transition: all 0.2s ease;
        }

        .tab-btn.active {
            background: var(--button-color);
            color: var(--button-text);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
        }

        .filter-select {
            width: 100%;
            padding: 10px 12px;
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            background: rgba(0, 0, 0, 0.2);
            color: var(--text-color);
            font-size: 13px;
            font-weight: 500;
            margin-bottom: 12px;
            box-sizing: border-box;
            outline: none;
        }

        ul { list-style: none; padding: 0; margin: 0; }
        
        li {
            padding: 10px 12px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 10px;
            margin-bottom: 6px;
            font-size: 13px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border: 1px solid rgba(255, 255, 255, 0.02);
        }

        li:last-child { margin-bottom: 0; }

        .student-info {
            display: flex;
            flex-direction: column;
            gap: 3px;
        }

        .student-name {
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .sub-text {
            font-size: 11px;
            color: var(--hint-color);
        }

        .time {
            font-size: 12px;
            font-weight: 600;
            color: var(--hint-color);
            background: rgba(255, 255, 255, 0.05);
            padding: 3px 8px;
            border-radius: 6px;
            white-space: nowrap;
        }

        .badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 5px;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.2px;
        }

        .badge-success { background: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); }
        .badge-warning { background: rgba(234, 179, 8, 0.15); color: #facc15; border: 1px solid rgba(234, 179, 8, 0.3); }
        .badge-danger { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
        .badge-info { background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }

        .empty-box {
            text-align: center;
            color: var(--hint-color);
            padding: 24px 0;
            font-size: 13px;
        }
    </style>
</head>
<body>
    <div class="app-header">
        <h2 class="app-title">📊 Посещаемость</h2>
        <div class="status-badge">
            <div class="pulse-dot"></div>
            <span>LIVE</span>
        </div>
    </div>

    <div class="stat-grid">
        <div class="stat-card">
            <div class="stat-title">Всего</div>
            <div id="total-students" class="stat-num blue">0</div>
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
            <button id="tab-absent" class="tab-btn" onclick="switchTab('absent')">🚫 Прогуливают (<span id="tab-absent-num">0</span>)</button>
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
            const select = document.getElementById('subject-filter');
            const currentSelected = select.value;
            const subjects = allData.subjects || [];
            
            let optionsHtml = '<option value="">Все предметы за сегодня</option>';
            subjects.forEach(s => {
                const sel = s === currentSelected ? 'selected' : '';
                optionsHtml += `<option value="${s}" ${sel}>${s}</option>`;
            });
            select.innerHTML = optionsHtml;

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
                    const subj = r.subject ? ` • ${r.subject}` : '';
                    const time = r.time ? `<span class="time">${r.time}</span>` : '';
                    const badgeClass = getStatusBadgeClass(r.status);
                    const badgeHtml = r.status ? `<span class="badge ${badgeClass}">${r.status}</span>` : '';
                    
                    li.innerHTML = `
                        <div class="student-info">
                            <div class="student-name">
                                <span>👤 ${r.name}</span>
                                ${badgeHtml}
                            </div>
                            <span class="sub-text">📍 ~${Math.round(r.dist)}м${subj}</span>
                        </div>
                        ${time}
                    `;
                    presentList.appendChild(li);
                });
            } else {
                presentList.innerHTML = '<div class="empty-box">📭 Сегодня пока нет отметок</div>';
            }

            const absentList = document.getElementById('absent-list');
            absentList.innerHTML = '';
            const absentStudents = allData.absent || [];
            
            if (absentStudents.length > 0) {
                absentStudents.forEach(s => {
                    const li = document.createElement('li');
                    li.innerHTML = `
                        <div class="student-info">
                            <div class="student-name">
                                <span>👤 ${s.name}</span>
                            </div>
                            <span class="sub-text" style="color:#f87171;">❌ Нет отметки за сегодня</span>
                        </div>
                        <span class="badge badge-danger">Прогул</span>
                    `;
                    absentList.appendChild(li);
                });
            } else {
                absentList.innerHTML = '<div class="empty-box" style="color:#4ade80;">🎉 Все студенты на парах!</div>';
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
            all_students = await conn.fetch("SELECT telegram_id, full_name FROM students ORDER BY full_name ASC")
            
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