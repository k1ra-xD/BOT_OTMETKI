STUDENT_APP_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Студенческий Портал</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root {
            --bg-color: var(--tg-theme-bg-color, #0f172a);
            --card-bg: var(--tg-theme-secondary-bg-color, #1e293b);
            --text-color: var(--tg-theme-text-color, #f8fafc);
            --hint-color: var(--tg-theme-hint-color, #94a3b8);
            --button-color: var(--tg-theme-button-color, #3b82f6);
            --button-text: var(--tg-theme-button-text-color, #ffffff);
            --success-color: #22c55e;
            --warning-color: #f59e0b;
            --danger-color: #ef4444;
            --accent-gradient: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            -webkit-tap-highlight-color: transparent;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            padding: 12px;
            padding-bottom: 85px; /* space for fixed bottom nav */
            margin: 0;
            -webkit-font-smoothing: antialiased;
        }

        /* Header */
        .app-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 4px 16px 4px;
        }

        .user-info {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .avatar-circle {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: var(--accent-gradient);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            font-weight: 700;
            color: #fff;
            box-shadow: 0 4px 10px rgba(59, 130, 246, 0.3);
        }

        .greeting {
            font-size: 16px;
            font-weight: 700;
            letter-spacing: -0.3px;
        }

        .subtitle {
            font-size: 12px;
            color: var(--hint-color);
        }

        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
            background: rgba(34, 197, 94, 0.15);
            color: var(--success-color);
            border: 1px solid rgba(34, 197, 94, 0.3);
        }

        /* Main Tabs Content */
        .tab-content {
            display: none;
            animation: fadeIn 0.25s ease-in-out;
        }

        .tab-content.active {
            display: block;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(4px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Day Chips for Schedule */
        .days-scroll {
            display: flex;
            gap: 8px;
            overflow-x: auto;
            padding: 4px 2px 14px 2px;
            scrollbar-width: none;
        }
        .days-scroll::-webkit-scrollbar { display: none; }

        .day-chip {
            flex: 0 0 auto;
            padding: 8px 16px;
            border-radius: 14px;
            background: var(--card-bg);
            border: 1px solid rgba(255, 255, 255, 0.05);
            color: var(--hint-color);
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }

        .day-chip.active {
            background: var(--button-color);
            color: var(--button-text);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.35);
            border-color: transparent;
        }

        .day-chip .today-dot {
            display: inline-block;
            width: 6px;
            height: 6px;
            background: var(--success-color);
            border-radius: 50%;
            margin-right: 4px;
        }

        /* Lesson Card */
        .lesson-card {
            background: var(--card-bg);
            border-radius: 16px;
            padding: 14px 16px;
            margin-bottom: 12px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15);
            position: relative;
            overflow: hidden;
            transition: transform 0.15s;
        }

        .lesson-card.active-now {
            border: 1px solid rgba(34, 197, 94, 0.5);
            box-shadow: 0 4px 20px rgba(34, 197, 94, 0.2);
        }

        .active-stripe {
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 5px;
            background: var(--success-color);
        }

        .lesson-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }

        .lesson-time {
            font-size: 13px;
            font-weight: 700;
            color: #60a5fa;
            display: flex;
            align-items: center;
            gap: 5px;
        }

        .lesson-badge {
            font-size: 11px;
            font-weight: 600;
            padding: 3px 8px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.06);
            color: var(--hint-color);
        }

        .badge-live {
            background: rgba(34, 197, 94, 0.2);
            color: #4ade80;
            border: 1px solid rgba(34, 197, 94, 0.4);
            animation: pulseText 2s infinite;
        }

        @keyframes pulseText {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }

        .lesson-title {
            font-size: 15px;
            font-weight: 700;
            margin-bottom: 6px;
            line-height: 1.3;
        }

        .lesson-details {
            font-size: 12px;
            color: var(--hint-color);
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .lesson-detail-item {
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .btn-online-link {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            margin-top: 10px;
            padding: 6px 12px;
            border-radius: 10px;
            background: rgba(59, 130, 246, 0.15);
            color: #60a5fa;
            text-decoration: none;
            font-size: 12px;
            font-weight: 600;
            border: 1px solid rgba(59, 130, 246, 0.3);
        }

        /* Checkin / Radar Section */
        .radar-card {
            background: var(--card-bg);
            border-radius: 20px;
            padding: 24px 16px;
            text-align: center;
            margin-bottom: 16px;
            border: 1px solid rgba(255, 255, 255, 0.06);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.2);
            position: relative;
            overflow: hidden;
        }

        .radar-animation {
            width: 140px;
            height: 140px;
            margin: 0 auto 18px auto;
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .radar-circle {
            position: absolute;
            border-radius: 50%;
            border: 2px solid var(--button-color);
            opacity: 0;
            animation: radarRipple 3s infinite cubic-bezier(0, 0.2, 0.8, 1);
        }

        .radar-circle:nth-child(1) { width: 40px; height: 40px; animation-delay: 0s; }
        .radar-circle:nth-child(2) { width: 80px; height: 80px; animation-delay: 1s; }
        .radar-circle:nth-child(3) { width: 120px; height: 120px; animation-delay: 2s; }

        @keyframes radarRipple {
            0% { transform: scale(0.3); opacity: 0.9; }
            100% { transform: scale(1.3); opacity: 0; }
        }

        .radar-center-icon {
            width: 50px;
            height: 50px;
            background: var(--accent-gradient);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            box-shadow: 0 0 16px rgba(59, 130, 246, 0.6);
            z-index: 2;
        }

        .radar-title {
            font-size: 18px;
            font-weight: 700;
            margin-bottom: 6px;
        }

        .radar-desc {
            font-size: 13px;
            color: var(--hint-color);
            margin-bottom: 16px;
            line-height: 1.4;
        }

        .distance-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 16px;
            border-radius: 30px;
            font-size: 13px;
            font-weight: 700;
            margin-bottom: 20px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .dist-ok {
            background: rgba(34, 197, 94, 0.15);
            color: #4ade80;
            border-color: rgba(34, 197, 94, 0.4);
        }

        .dist-out {
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
            border-color: rgba(239, 68, 68, 0.4);
        }

        .btn-checkin {
            width: 100%;
            padding: 15px;
            border-radius: 14px;
            border: none;
            background: var(--button-color);
            color: var(--button-text);
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            box-shadow: 0 4px 16px rgba(59, 130, 246, 0.4);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            transition: transform 0.1s, opacity 0.2s;
        }

        .btn-checkin:active {
            transform: scale(0.98);
        }

        .btn-checkin:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        /* SRO section */
        .sro-card {
            background: var(--card-bg);
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 14px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }

        .form-label {
            display: block;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--hint-color);
            margin-bottom: 8px;
        }

        .custom-select {
            width: 100%;
            padding: 12px 14px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: var(--text-color);
            font-size: 14px;
            outline: none;
            margin-bottom: 16px;
        }

        .custom-select option {
            background: var(--card-bg);
            color: var(--text-color);
        }

        .sro-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 18px;
        }

        .sro-chip {
            padding: 8px 14px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: var(--hint-color);
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }

        .sro-chip.active {
            background: var(--button-color);
            color: var(--button-text);
            border-color: transparent;
        }

        .info-box {
            background: rgba(59, 130, 246, 0.1);
            border: 1px solid rgba(59, 130, 246, 0.25);
            border-radius: 12px;
            padding: 12px;
            font-size: 12px;
            color: #93c5fd;
            line-height: 1.4;
            margin-bottom: 16px;
        }

        /* Fixed Bottom Navigation */
        .bottom-nav {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: rgba(15, 23, 42, 0.92);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            justify-content: space-around;
            padding: 8px 6px 16px 6px;
            z-index: 100;
        }

        .nav-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
            color: var(--hint-color);
            text-decoration: none;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            padding: 4px 12px;
            border-radius: 12px;
            transition: all 0.15s;
        }

        .nav-item.active {
            color: #60a5fa;
        }

        .nav-icon {
            font-size: 20px;
        }

        .empty-state {
            text-align: center;
            padding: 40px 16px;
            color: var(--hint-color);
            font-size: 14px;
        }

        .empty-icon {
            font-size: 48px;
            margin-bottom: 12px;
        }
    </style>
</head>
<body>

    <!-- Header -->
    <div class="app-header">
        <div class="user-info">
            <div class="avatar-circle" id="user-avatar">🎓</div>
            <div>
                <div class="greeting" id="user-name">Привет, Студент!</div>
                <div class="subtitle" id="user-sub">Учебный портал</div>
            </div>
        </div>
        <div class="status-pill" id="today-status-badge">
            <span style="display:inline-block; width:6px; height:6px; background:#4ade80; border-radius:50%;"></span>
            <span id="today-status-text">Онлайн</span>
        </div>
    </div>

    <!-- TAB 1: РАСПИСАНИЕ -->
    <div id="tab-schedule" class="tab-content active">
        <div class="days-scroll" id="days-container">
            <div class="day-chip active" onclick="selectDay(0)">Понедельник</div>
            <div class="day-chip" onclick="selectDay(1)">Вторник</div>
            <div class="day-chip" onclick="selectDay(2)">Среда</div>
            <div class="day-chip" onclick="selectDay(3)">Четверг</div>
            <div class="day-chip" onclick="selectDay(4)">Пятница</div>
            <div class="day-chip" onclick="selectDay(5)">Суббота</div>
        </div>

        <div id="lessons-list">
            <div class="empty-state">
                <div class="empty-icon">⏳</div>
                Загрузка расписания...
            </div>
        </div>
    </div>

    <!-- TAB 2: Я ЗДЕСЬ (РАДАР) -->
    <div id="tab-checkin" class="tab-content">
        <div class="radar-card">
            <div class="radar-animation">
                <div class="radar-circle"></div>
                <div class="radar-circle"></div>
                <div class="radar-circle"></div>
                <div class="radar-center-icon">📍</div>
            </div>

            <div class="radar-title">Отметка присутствия</div>
            <div class="radar-desc" id="current-lesson-info">
                Определение текущей пары...
            </div>

            <div class="distance-pill" id="distance-badge">
                <span>📏 Дистанция: </span><b id="dist-val">Определение гео...</b>
            </div>

            <button class="btn-checkin" id="btn-submit-checkin" onclick="performCheckin()">
                <span>📍 Я здесь! (Отметиться)</span>
            </button>
        </div>

        <div id="checkin-result-box" style="display:none; margin-top:14px;"></div>
    </div>

    <!-- TAB 3: СДАТЬ СРО -->
    <div id="tab-sro" class="tab-content">
        <div class="sro-card">
            <span class="form-label">Предмет</span>
            <select id="sro-subject" class="custom-select">
                <option value="">Загрузка предметов...</option>
            </select>

            <span class="form-label">Номер СРО</span>
            <div class="sro-chips" id="sro-num-chips">
                <div class="sro-chip active" onclick="selectSroNum(1)">СРО 1</div>
                <div class="sro-chip" onclick="selectSroNum(2)">СРО 2</div>
                <div class="sro-chip" onclick="selectSroNum(3)">СРО 3</div>
                <div class="sro-chip" onclick="selectSroNum(4)">СРО 4</div>
                <div class="sro-chip" onclick="selectSroNum(5)">СРО 5</div>
                <div class="sro-chip" onclick="selectSroNum(6)">СРО 6</div>
            </div>

            <div class="info-box">
                ℹ️ <b>Как происходит сдача:</b><br>
                Файлы загружаются прямо в вашу персональную папку студента на Google Диске преподавателя.
            </div>

            <button class="btn-checkin" onclick="openSroInBot()">
                <span>📤 Перейти к отправке файла</span>
            </button>
        </div>
    </div>

    <!-- TAB 4: МАТЕРИАЛЫ / ДИСК -->
    <div id="tab-drive" class="tab-content">
        <div class="radar-card" style="text-align:left;">
            <div class="radar-title" style="margin-bottom:12px;">📁 Учебные материалы</div>
            <div class="radar-desc">
                Все лекции, методички и презентации преподавателей синхронизируются в единой папке на Google Диске группы.
            </div>
            <button class="btn-checkin" onclick="openDriveFolder()">
                <span>🚀 Открыть Google Диск</span>
            </button>
        </div>
    </div>

    <!-- Bottom Navigation -->
    <nav class="bottom-nav">
        <div class="nav-item active" id="nav-schedule" onclick="switchMainTab('schedule')">
            <span class="nav-icon">📅</span>
            <span>Расписание</span>
        </div>
        <div class="nav-item" id="nav-checkin" onclick="switchMainTab('checkin')">
            <span class="nav-icon">📍</span>
            <span>Я здесь</span>
        </div>
        <div class="nav-item" id="nav-sro" onclick="switchMainTab('sro')">
            <span class="nav-icon">📤</span>
            <span>Сдать СРО</span>
        </div>
        <div class="nav-item" id="nav-drive" onclick="switchMainTab('drive')">
            <span class="nav-icon">📁</span>
            <span>Лекции</span>
        </div>
    </nav>

    <script>
        const tg = window.Telegram?.WebApp;
        if (tg) {
            tg.ready();
            tg.expand();
        }

        let currentSelectedDay = 0;
        let scheduleData = {};
        let selectedSroNumber = 1;
        let uniLocation = { lat: 51.1801, lon: 71.446, radius: 250 };
        let studentUser = { id: 0, first_name: 'Студент' };

        // Инициализация пользователя
        try {
            if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
                studentUser = tg.initDataUnsafe.user;
                document.getElementById('user-name').innerText = studentUser.first_name || 'Студент';
                const avatar = document.getElementById('user-avatar');
                if (studentUser.first_name) {
                    avatar.innerText = studentUser.first_name.charAt(0).toUpperCase();
                }
            }
        } catch(e) {}

        // Навигация
        function switchMainTab(tabName) {
            if (tg?.HapticFeedback) tg.HapticFeedback.selectionChanged();
            
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

            const targetTab = document.getElementById('tab-' + tabName);
            const targetNav = document.getElementById('nav-' + tabName);

            if (targetTab) targetTab.classList.add('active');
            if (targetNav) targetNav.classList.add('active');

            if (tabName === 'checkin') {
                detectLocation();
            }
        }

        // Авто-переключение по хэшу URL (#checkin, #schedule, etc.)
        window.addEventListener('load', () => {
            const hash = window.location.hash.replace('#', '');
            if (['schedule', 'checkin', 'sro', 'drive'].includes(hash)) {
                switchMainTab(hash);
            }
            loadUniInfo();
            loadSchedule();
            loadSubjects();
        });

        // Загрузка информации о координатах ВУЗа
        async function loadUniInfo() {
            try {
                const res = await fetch('/api/uni_info');
                const data = await res.json();
                if (data.lat) uniLocation = data;
            } catch(e) { console.error(e); }
        }

        // Загрузка расписания
        async function loadSchedule() {
            try {
                const res = await fetch('/api/schedule');
                const data = await res.json();
                if (data.success) {
                    scheduleData = data.schedule || {};
                    const todayDay = typeof data.today_day === 'number' ? data.today_day : new Date().getDay() - 1;
                    const safeDay = todayDay >= 0 && todayDay <= 5 ? todayDay : 0;
                    selectDay(safeDay);
                }
            } catch(e) {
                document.getElementById('lessons-list').innerHTML = '<div class="empty-state">Ошибка загрузки расписания</div>';
            }
        }

        function selectDay(dayIndex) {
            currentSelectedDay = dayIndex;
            const chips = document.querySelectorAll('.day-chip');
            chips.forEach((c, idx) => {
                c.classList.toggle('active', idx === dayIndex);
            });
            renderScheduleDay(dayIndex);
        }

        function renderScheduleDay(dayIndex) {
            const list = document.getElementById('lessons-list');
            const lessons = scheduleData[dayIndex] || [];

            if (lessons.length === 0) {
                list.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">🎉</div>
                        <b>На этот день пар нет!</b><br>
                        Отдыхайте и набирайтесь сил.
                    </div>
                `;
                return;
            }

            const now = new Date();
            const nowMinutes = now.getHours() * 60 + now.getMinutes();

            let html = '';
            lessons.forEach(l => {
                // Проверка идет ли пара сейчас
                let isLive = false;
                try {
                    const [sH, sM] = l.time_start.replace('.', ':').split(':').map(Number);
                    const [eH, eM] = l.time_end.replace('.', ':').split(':').map(Number);
                    const startMin = sH * 60 + sM;
                    const endMin = eH * 60 + eM;
                    if (nowMinutes >= startMin && nowMinutes <= endMin) {
                        isLive = true;
                    }
                } catch(e) {}

                const activeClass = isLive ? 'active-now' : '';
                const liveBadge = isLive ? '<span class="lesson-badge badge-live">● Идёт сейчас</span>' : '';
                const onlineBtn = l.online_link ? `<a href="${l.online_link}" target="_blank" class="btn-online-link">🔗 Войти на онлайн-пару</a>` : '';

                html += `
                    <div class="lesson-card ${activeClass}">
                        ${isLive ? '<div class="active-stripe"></div>' : ''}
                        <div class="lesson-top">
                            <div class="lesson-time">⏰ ${l.time_start} - ${l.time_end}</div>
                            ${liveBadge}
                            <span class="lesson-badge">${l.lesson_type || 'Занятие'}</span>
                        </div>
                        <div class="lesson-title">${escapeHtml(l.subject)}</div>
                        <div class="lesson-details">
                            <div class="lesson-detail-item">🚪 <b>Аудитория:</b> ${escapeHtml(l.room || 'Не указана')}</div>
                            <div class="lesson-detail-item">👨‍🏫 <b>Преподаватель:</b> ${escapeHtml(l.teacher || 'Не указан')}</div>
                        </div>
                        ${onlineBtn}
                    </div>
                `;
            });
            list.innerHTML = html;
        }

        // Определение геолокации и дистанции
        let userCoords = null;

        function detectLocation() {
            const distBadge = document.getElementById('distance-badge');
            const distVal = document.getElementById('dist-val');
            distVal.innerText = 'Запрос GPS...';

            if (!navigator.geolocation) {
                distVal.innerText = 'GPS не поддерживается';
                return;
            }

            navigator.geolocation.getCurrentPosition(
                pos => {
                    userCoords = {
                        lat: pos.coords.latitude,
                        lon: pos.coords.longitude
                    };
                    const dist = Math.round(calcDistance(userCoords.lat, userCoords.lon, uniLocation.lat, uniLocation.lon));
                    const isInside = dist <= uniLocation.radius;

                    distBadge.className = 'distance-pill ' + (isInside ? 'dist-ok' : 'dist-out');
                    distVal.innerText = `~${dist} м до корпуса (${isInside ? 'В зоне ВУЗа ✅' : 'Вне зоны ❌'})`;

                    const btn = document.getElementById('btn-submit-checkin');
                    if (isInside) {
                        btn.innerHTML = '<span>✅ Отметиться на паре</span>';
                    } else {
                        btn.innerHTML = '<span>📍 Отметиться (вне зоны)</span>';
                    }
                },
                err => {
                    distVal.innerText = 'Геолокация недоступна';
                },
                { enableHighAccuracy: true, timeout: 10000 }
            );
        }

        function calcDistance(lat1, lon1, lat2, lon2) {
            const R = 6371000;
            const dLat = (lat2 - lat1) * Math.PI / 180;
            const dLon = (lon2 - lon1) * Math.PI / 180;
            const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                      Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                      Math.sin(dLon/2) * Math.sin(dLon/2);
            const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
            return R * c;
        }

        // Отправка отметки
        async function performCheckin() {
            if (!userCoords) {
                alert('Сначала разрешите доступ к геолокации!');
                detectLocation();
                return;
            }

            const btn = document.getElementById('btn-submit-checkin');
            btn.disabled = true;
            btn.innerText = 'Отправка...';

            try {
                const res = await fetch('/api/checkin', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        telegram_id: studentUser.id,
                        lat: userCoords.lat,
                        lon: userCoords.lon
                    })
                });
                const data = await res.json();
                const resBox = document.getElementById('checkin-result-box');
                resBox.style.display = 'block';

                if (data.success) {
                    if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
                    resBox.innerHTML = `
                        <div class="info-box" style="background:rgba(34,197,94,0.15); border-color:#22c55e; color:#4ade80;">
                            🎉 <b>Отметка успешно принята!</b><br>
                            📖 Предмет: ${escapeHtml(data.subject)}<br>
                            📊 Статус: ${data.status} (Дистанция: ~${data.distance}м)
                        </div>
                    `;
                    btn.innerText = '✓ Вы отмечены';
                } else {
                    if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred('warning');
                    resBox.innerHTML = `
                        <div class="info-box" style="background:rgba(239,68,68,0.15); border-color:#ef4444; color:#f87171;">
                            ⚠️ ${data.error || 'Ошибка отметки'}
                        </div>
                    `;
                    btn.disabled = false;
                    btn.innerText = 'Попробовать снова';
                }
            } catch(e) {
                alert('Ошибка сети: ' + e.message);
                btn.disabled = false;
                btn.innerText = 'Попробовать снова';
            }
        }

        // Загрузка предметов для СРО
        async function loadSubjects() {
            try {
                const res = await fetch('/api/subjects');
                const data = await res.json();
                const select = document.getElementById('sro-subject');
                if (data.subjects && data.subjects.length > 0) {
                    select.innerHTML = data.subjects.map(s => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join('');
                } else {
                    select.innerHTML = '<option value="Общее">Общие предметы</option>';
                }
            } catch(e) {}
        }

        function selectSroNum(num) {
            selectedSroNumber = num;
            const chips = document.querySelectorAll('.sro-chip');
            chips.forEach((c, idx) => {
                c.classList.toggle('active', (idx + 1) === num);
            });
        }

        function openSroInBot() {
            if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');
            if (tg) {
                tg.close();
            }
        }

        function openDriveFolder() {
            window.open('https://drive.google.com', '_blank');
        }

        function escapeHtml(str) {
            return (str || '').replace(/[&<>'"]/g, 
                tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
            );
        }
    </script>
</body>
</html>
"""
