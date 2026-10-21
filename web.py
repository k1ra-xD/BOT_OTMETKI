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
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
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
            margin-bottom: 14px;
            gap: 2px;
        }

        .tab-btn {
            flex: 1;
            text-align: center;
            background: none;
            border: none;
            padding: 8px 4px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            color: var(--hint-color);
            border-radius: 8px;
            transition: all 0.2s ease;
            white-space: nowrap;
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
            width: 100%;
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
            margin-left: 8px;
        }

        .badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 5px;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.2px;
            white-space: nowrap;
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

        /* Стили для вкладки Аналитика */
        .analytics-block {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 12px;
            padding: 12px;
            margin-bottom: 14px;
        }

        .analytics-block:last-child {
            margin-bottom: 0;
        }

        .chart-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }

        .chart-title {
            font-size: 13px;
            font-weight: 700;
            color: var(--text-color);
            margin: 0;
        }

        .chart-subtitle {
            font-size: 11px;
            color: var(--hint-color);
        }

        .chart-wrapper {
            position: relative;
            height: 190px;
            width: 100%;
        }

        .chart-wrapper-small {
            position: relative;
            height: 160px;
            width: 100%;
        }

        .progress-bar-bg {
            width: 100%;
            height: 6px;
            background: rgba(255, 255, 255, 0.06);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 5px;
        }

        .progress-bar-fill {
            height: 100%;
            background: linear-gradient(90deg, #3b82f6, #4ade80);
            border-radius: 4px;
            transition: width 0.4s ease;
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
            <button id="tab-present" class="tab-btn active" onclick="switchTab('present')">📍 Сегодня (<span id="tab-present-num">0</span>)</button>
            <button id="tab-absent" class="tab-btn" onclick="switchTab('absent')">🚫 Прогулы (<span id="tab-absent-num">0</span>)</button>
            <button id="tab-analytics" class="tab-btn" onclick="switchTab('analytics')">📈 Аналитика</button>
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

        <!-- Контейнер Аналитики за 30 дней -->
        <div id="analytics-container" style="display:none;">
            <div class="analytics-block">
                <div class="chart-header">
                    <h3 class="chart-title">📅 Динамика за 30 дней</h3>
                    <span class="chart-subtitle">Уникальные студенты</span>
                </div>
                <div class="chart-wrapper">
                    <canvas id="dailyChart"></canvas>
                </div>
            </div>

            <div class="analytics-block">
                <div class="chart-header">
                    <h3 class="chart-title">⏱ Дисциплина (Статусы)</h3>
                    <span class="chart-subtitle">За месяц</span>
                </div>
                <div class="chart-wrapper-small">
                    <canvas id="statusChart"></canvas>
                </div>
            </div>

            <div class="analytics-block">
                <div class="chart-header">
                    <h3 class="chart-title">📚 Активность по предметам</h3>
                    <span class="chart-subtitle">Топ дисциплин</span>
                </div>
                <div class="chart-wrapper">
                    <canvas id="subjectsChart"></canvas>
                </div>
            </div>

            <div class="analytics-block">
                <div class="chart-header">
                    <h3 class="chart-title">🏆 Рейтинг студентов (30 дней)</h3>
                    <span class="chart-subtitle">Дней с отметкой</span>
                </div>
                <ul id="top-students-list">
                    <li><i>Загрузка аналитики...</i></li>
                </ul>
            </div>
        </div>
    </div>

    <script>
        const tg = window.Telegram.WebApp; 
        tg.ready();
        tg.expand();

        let allData = { responses: [], absent: [], subjects: [] };
        let activeTab = 'present';
        let dailyChartInstance = null;
        let statusChartInstance = null;
        let subjectsChartInstance = null;

        function switchTab(tab) {
            activeTab = tab;
            document.getElementById('tab-present').className = 'tab-btn' + (tab === 'present' ? ' active' : '');
            document.getElementById('tab-absent').className = 'tab-btn' + (tab === 'absent' ? ' active' : '');
            document.getElementById('tab-analytics').className = 'tab-btn' + (tab === 'analytics' ? ' active' : '');
            
            document.getElementById('present-container').style.display = tab === 'present' ? 'block' : 'none';
            document.getElementById('absent-container').style.display = tab === 'absent' ? 'block' : 'none';
            document.getElementById('analytics-container').style.display = tab === 'analytics' ? 'block' : 'none';
            document.getElementById('filter-wrapper').style.display = tab === 'present' ? 'block' : 'none';
            
            if (tab === 'analytics') {
                loadAnalytics();
            } else {
                renderLists();
            }
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
                
                if (activeTab !== 'analytics') {
                    renderLists();
                }
            } catch(e) { 
                console.error(e); 
            }
        }

        async function loadAnalytics() {
            try {
                const res = await fetch('/api/analytics');
                const data = await res.json();
                renderAnalyticsCharts(data);
            } catch(e) {
                console.error("Ошибка загрузки аналитики:", e);
            }
        }

        function renderAnalyticsCharts(data) {
            const textColor = getComputedStyle(document.documentElement).getPropertyValue('--hint-color').trim() || '#94a3b8';
            const gridColor = 'rgba(255, 255, 255, 0.05)';

            // 1. График по дням (Line Chart)
            const dailyCtx = document.getElementById('dailyChart').getContext('2d');
            if (dailyChartInstance) dailyChartInstance.destroy();

            const gradient = dailyCtx.createLinearGradient(0, 0, 0, 180);
            gradient.addColorStop(0, 'rgba(59, 130, 246, 0.4)');
            gradient.addColorStop(1, 'rgba(59, 130, 246, 0.0)');

            dailyChartInstance = new Chart(dailyCtx, {
                type: 'line',
                data: {
                    labels: data.daily.labels,
                    datasets: [
                        {
                            label: 'Студентов',
                            data: data.daily.unique_students,
                            borderColor: '#3b82f6',
                            backgroundColor: gradient,
                            borderWidth: 2.5,
                            pointBackgroundColor: '#60a5fa',
                            pointRadius: 3,
                            fill: true,
                            tension: 0.35
                        },
                        {
                            label: 'Всего отметок',
                            data: data.daily.total_checkins,
                            borderColor: '#4ade80',
                            borderWidth: 1.5,
                            borderDash: [4, 4],
                            pointRadius: 2,
                            fill: false,
                            tension: 0.35
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { labels: { color: textColor, font: { size: 11 } } }
                    },
                    scales: {
                        x: { ticks: { color: textColor, font: { size: 10 } }, grid: { display: false } },
                        y: { beginAtZero: true, ticks: { color: textColor, stepSize: 1, font: { size: 10 } }, grid: { color: gridColor } }
                    }
                }
            });

            // 2. График статусов (Doughnut Chart)
            const statusCtx = document.getElementById('statusChart').getContext('2d');
            if (statusChartInstance) statusChartInstance.destroy();

            statusChartInstance = new Chart(statusCtx, {
                type: 'doughnut',
                data: {
                    labels: data.statuses.labels,
                    datasets: [{
                        data: data.statuses.counts,
                        backgroundColor: ['#4ade80', '#facc15', '#f87171', '#60a5fa'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '65%',
                    plugins: {
                        legend: { position: 'right', labels: { color: textColor, font: { size: 11 }, boxWidth: 12 } }
                    }
                }
            });

            // 3. График по предметам (Horizontal Bar Chart)
            const subjCtx = document.getElementById('subjectsChart').getContext('2d');
            if (subjectsChartInstance) subjectsChartInstance.destroy();

            subjectsChartInstance = new Chart(subjCtx, {
                type: 'bar',
                data: {
                    labels: data.subjects.labels,
                    datasets: [{
                        label: 'Отметок',
                        data: data.subjects.counts,
                        backgroundColor: 'rgba(96, 165, 250, 0.75)',
                        borderRadius: 6
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { beginAtZero: true, ticks: { color: textColor, font: { size: 10 } }, grid: { color: gridColor } },
                        y: { ticks: { color: textColor, font: { size: 10 } }, grid: { display: false } }
                    }
                }
            });

            // 4. Рейтинг студентов
            const topList = document.getElementById('top-students-list');
            topList.innerHTML = '';
            const maxDays = data.max_active_days || 1;

            if (data.students_ranking && data.students_ranking.length > 0) {
                data.students_ranking.forEach((st, idx) => {
                    const percent = Math.min(100, Math.round((st.days_present / maxDays) * 100));
                    const medal = idx === 0 ? '🥇' : (idx === 1 ? '🥈' : (idx === 2 ? '🥉' : '👤'));
                    const li = document.createElement('li');
                    li.innerHTML = `
                        <div class="student-info">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span class="student-name">${medal} ${st.name}</span>
                                <span class="badge badge-info">${st.days_present} дн. (${st.total_checkins} отм.)</span>
                            </div>
                            <div class="progress-bar-bg">
                                <div class="progress-bar-fill" style="width: ${percent}%;"></div>
                            </div>
                        </div>
                    `;
                    topList.appendChild(li);
                });
            } else {
                topList.innerHTML = '<div class="empty-box">Нет данных за последние 30 дней</div>';
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

    async def handle_api_analytics(request):
        db_pool = get_db_pool()
        if not db_pool:
            return web.json_response({"error": "No DB connection"}, status=500)

        now = datetime.now(ASTANA_TZ)
        month_ago = datetime(now.year, now.month, now.day) - timedelta(days=29)

        async with db_pool.acquire() as conn:
            # 1. Динамика по дням за последние 30 дней
            daily_rows = await conn.fetch("""
                SELECT 
                    TO_CHAR(checkin_time, 'DD.MM') AS day_label,
                    DATE(checkin_time) AS dt,
                    COUNT(DISTINCT telegram_id) AS unique_students,
                    COUNT(*) AS total_checkins
                FROM attendance
                WHERE checkin_time >= $1
                GROUP BY dt, day_label
                ORDER BY dt ASC
            """, month_ago)

            # 2. Статистика по предметам (Топ-7)
            subject_rows = await conn.fetch("""
                SELECT 
                    COALESCE(NULLIF(subject, ''), 'Без предмета') AS subj,
                    COUNT(*) AS cnt
                FROM attendance
                WHERE checkin_time >= $1
                  AND subject NOT IN ('Вне пар', 'Вне зоны ВУЗа')
                GROUP BY subj
                ORDER BY cnt DESC
                LIMIT 7
            """, month_ago)

            # 3. Распределение по статусам (Вовремя / Опоздание / Вне зоны)
            status_rows = await conn.fetch("""
                SELECT 
                    CASE 
                        WHEN status ILIKE '%Вовремя%' THEN 'Вовремя'
                        WHEN status ILIKE '%Опоздание%' THEN 'Опоздание'
                        WHEN status ILIKE '%Вне зоны%' THEN 'Вне зоны'
                        ELSE 'Другое'
                    END AS st_group,
                    COUNT(*) AS cnt
                FROM attendance
                WHERE checkin_time >= $1
                GROUP BY st_group
            """, month_ago)

            # 4. Рейтинг посещаемости студентов за 30 дней
            student_rows = await conn.fetch("""
                SELECT 
                    s.full_name AS name,
                    COUNT(DISTINCT DATE(a.checkin_time)) AS days_present,
                    COUNT(a.telegram_id) AS total_checkins
                FROM students s
                LEFT JOIN attendance a 
                    ON s.telegram_id = a.telegram_id AND a.checkin_time >= $1
                GROUP BY s.telegram_id, s.full_name
                ORDER BY days_present DESC, total_checkins DESC, s.full_name ASC
            """, month_ago)

        status_order = ['Вовремя', 'Опоздание', 'Вне зоны', 'Другое']
        status_map = {r['st_group']: r['cnt'] for r in status_rows}
        status_labels = [s for s in status_order if status_map.get(s, 0) > 0]
        status_counts = [status_map[s] for s in status_labels]

        max_active_days = max([len(daily_rows), 1])

        return web.json_response({
            "daily": {
                "labels": [r['day_label'] for r in daily_rows],
                "unique_students": [r['unique_students'] for r in daily_rows],
                "total_checkins": [r['total_checkins'] for r in daily_rows]
            },
            "subjects": {
                "labels": [r['subj'] for r in subject_rows],
                "counts": [r['cnt'] for r in subject_rows]
            },
            "statuses": {
                "labels": status_labels,
                "counts": status_counts
            },
            "students_ranking": [
                {
                    "name": r['name'],
                    "days_present": r['days_present'],
                    "total_checkins": r['total_checkins']
                }
                for r in student_rows
            ],
            "max_active_days": max_active_days
        })

    async def handle_root(request):
        return web.Response(text="Bot is running! 🚀", content_type="text/plain", status=200)

    app.router.add_get('/', handle_root)
    app.router.add_get('/ping', handle_root)
    app.router.add_get('/dashboard', handle_dashboard)
    app.router.add_get('/api/stats', handle_api_stats)
    app.router.add_get('/api/analytics', handle_api_analytics)
    return app