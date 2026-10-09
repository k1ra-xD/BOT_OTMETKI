# Обработка геопозиции от студентов и смена координат ВУЗа
@router.message(F.location)
async def handle_location(message: Message, state: FSMContext):
    current_state = await state.get_state()
    pool = get_db_pool()

    if current_state == RegStates.waiting_for_uni_location.state:
        if message.from_user.id != ADMIN_ID: return
        await set_setting(pool, 'lat', message.location.latitude)
        await set_setting(pool, 'lon', message.location.longitude)
        await state.clear()
        return await message.answer("✅ Координаты ВУЗа сохранены!", parse_mode="HTML")

    lat, lon = message.location.latitude, message.location.longitude
    uni_lat = await get_setting(pool, 'lat', DEFAULT_UNI_LAT)
    uni_lon = await get_setting(pool, 'lon', DEFAULT_UNI_LON)
    radius = await get_setting(pool, 'radius', DEFAULT_RADIUS)
    
    dist = calculate_distance(uni_lat, uni_lon, lat, lon)
    is_inside = dist <= radius

    now = datetime.now(ASTANA_TZ)
    now_minutes = now.hour * 60 + now.minute
    day_code = now.weekday()

    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT,
                subject TEXT,
                checkin_time TIMESTAMP,
                status TEXT,
                distance INT
            );
        """)

        # Если человек ВНЕ ЗОНЫ, всё равно сохраняем попытку в БД с соответствующим статусом
        if not is_inside:
            await conn.execute("""
                INSERT INTO attendance (telegram_id, subject, checkin_time, status, distance)
                VALUES ($1, $2, $3, $4, $5)
            """, message.from_user.id, "Вне зоны ВУЗа", now, "❌ Вне зоны", int(dist))

            return await message.answer(
                f"❌ <b>Вы вне зоны ВУЗа!</b>\n"
                f"Расстояние до ВУЗа: ~<b>{int(dist)}м</b> (допустимо: {radius}м).\n"
                f"Отметка сохраненa в историю как 'Вне зоны'.",
                parse_mode="HTML",
                reply_markup=student_main_kb
            )

        # Если человек В ЗОНЕ ВУЗа
        lessons = await conn.fetch("SELECT * FROM schedule WHERE day_of_week = $1 ORDER BY time_start ASC", day_code)
        
        current_lesson = None
        status_text = ""

        for l in lessons:
            start_min = parse_time_to_minutes(l['time_start'])
            end_min = parse_time_to_minutes(l['time_end'])

            if (start_min - 15) <= now_minutes <= end_min:
                current_lesson = l
                if now_minutes <= (start_min + 5):
                    status_text = "✅ Вовремя"
                else:
                    late_by = now_minutes - start_min
                    status_text = f"⚠️ Опоздание на {late_by} мин."
                break

        if current_lesson:
            subject_name = current_lesson['subject']
            await conn.execute("""
                INSERT INTO attendance (telegram_id, subject, checkin_time, status, distance)
                VALUES ($1, $2, $3, $4, $5)
            """, message.from_user.id, subject_name, now, status_text, int(dist))

            msg = (
                f"🎯 <b>Отметка принята!</b>\n\n"
                f"📖 Предмет: <b>{subject_name}</b>\n"
                f"⏰ Статус: <b>{status_text}</b>\n"
                f"📍 Расстояние: ~<b>{int(dist)}м</b>"
            )
        else:
            msg = (
                f"📍 <b>Геопозиция принята!</b> (~{int(dist)}м)\n"
                f"ℹ️ Сейчас по расписанию нет активных пар, отметка сохранена."
            )
            await conn.execute("""
                INSERT INTO attendance (telegram_id, subject, checkin_time, status, distance)
                VALUES ($1, $2, $3, $4, $5)
            """, message.from_user.id, "Вне пар", now, "Вне расписания", int(dist))

    await message.answer(msg, parse_mode="HTML", reply_markup=student_main_kb)