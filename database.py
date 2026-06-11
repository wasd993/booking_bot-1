"""
Слой доступа к данным — SQLite через aiosqlite.
Все операции асинхронные.
"""

import aiosqlite
from config import DB_PATH


# ──────────────────────────────────────────────
# Инициализация
# ──────────────────────────────────────────────

async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS schedule (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                date  TEXT NOT NULL,
                time  TEXT NOT NULL,
                UNIQUE(date, time)
            );

            CREATE TABLE IF NOT EXISTS specialists (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                profession TEXT    NOT NULL,
                is_active  INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS appointments (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER NOT NULL,
                username       TEXT    DEFAULT '',
                full_name      TEXT    DEFAULT '',
                date           TEXT    NOT NULL,
                time           TEXT    NOT NULL,
                status         TEXT    NOT NULL DEFAULT 'pending',
                charge_id      TEXT,
                stars_paid     INTEGER NOT NULL DEFAULT 0,
                specialist_id  INTEGER,
                specialist_name TEXT   DEFAULT '',
                created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS contacts (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT NOT NULL,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS support_messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                username    TEXT    DEFAULT '',
                full_name   TEXT    DEFAULT '',
                message     TEXT    NOT NULL,
                reply       TEXT,
                is_answered INTEGER NOT NULL DEFAULT 0,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Настройки по умолчанию
        for key, value in [
            ("business_name",      "Моя компания"),
            ("specialist_name",    "Специалист"),
            ("specialist_profession", "Специализация"),
            ("accepting",           "1"),
        ]:
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )

        # Дефолтные контакты (только если таблица пуста)
        async with db.execute("SELECT COUNT(*) FROM contacts") as cur:
            if (await cur.fetchone())[0] == 0:
                await db.execute(
                    "INSERT INTO contacts (label, value) VALUES (?,?)",
                    ("Телефон", "+7 (000) 000-00-00"),
                )
                await db.execute(
                    "INSERT INTO contacts (label, value) VALUES (?,?)",
                    ("Адрес", "г. Город, ул. Улица, д. 1"),
                )

        async with db.execute("SELECT COUNT(*) FROM specialists") as cur:
            if (await cur.fetchone())[0] == 0:
                async with db.execute("SELECT value FROM settings WHERE key='specialist_name'") as cur2:
                    specialist_name = (await cur2.fetchone())[0]
                async with db.execute("SELECT value FROM settings WHERE key='specialist_profession'") as cur3:
                    specialist_profession = (await cur3.fetchone())[0]
                await db.execute(
                    "INSERT INTO specialists (name, profession, is_active) VALUES (?, ?, 1)",
                    (specialist_name, specialist_profession),
                )

        async with db.execute("PRAGMA table_info(appointments)") as cur:
            cols = [row[1] for row in await cur.fetchall()]
        if "specialist_id" not in cols:
            await db.execute("ALTER TABLE appointments ADD COLUMN specialist_id INTEGER")
        if "specialist_name" not in cols:
            await db.execute("ALTER TABLE appointments ADD COLUMN specialist_name TEXT DEFAULT ''")

        await db.commit()


# ──────────────────────────────────────────────
# Настройки
# ──────────────────────────────────────────────

async def get_setting(key: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else ""


async def set_setting(key: str, value: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        await db.commit()


# ──────────────────────────────────────────────
# Расписание
# ──────────────────────────────────────────────

_TAKEN = """
    a.status = 'active'
    OR (a.status = 'pending'
        AND datetime(a.created_at) > datetime('now', '-30 minutes'))
"""


async def get_available_dates() -> list[str]:
    """Даты, в которых есть хотя бы один свободный слот (сегодня и позже)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(f"""
            SELECT DISTINCT s.date
            FROM schedule s
            WHERE s.date >= date('now')
              AND EXISTS (
                  SELECT 1 FROM schedule s2
                  WHERE s2.date = s.date
                    AND NOT EXISTS (
                        SELECT 1 FROM appointments a
                        WHERE a.date = s2.date AND a.time = s2.time
                          AND ({_TAKEN})
                    )
              )
            ORDER BY s.date
        """) as cur:
            return [r[0] for r in await cur.fetchall()]


async def get_available_times(date: str) -> list[str]:
    """Свободные слоты времени для указанной даты."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(f"""
            SELECT s.time FROM schedule s
            WHERE s.date = ?
              AND NOT EXISTS (
                  SELECT 1 FROM appointments a
                  WHERE a.date = s.date AND a.time = s.time
                    AND ({_TAKEN})
              )
            ORDER BY s.time
        """, (date,)) as cur:
            return [r[0] for r in await cur.fetchall()]


async def get_all_schedule() -> list[tuple[str, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT date, time FROM schedule ORDER BY date, time"
        ) as cur:
            return await cur.fetchall()


async def add_schedule_slot(date: str, time: str) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO schedule (date, time) VALUES (?, ?)",
                (date, time),
            )
            await db.commit()
        return True
    except Exception:
        return False


async def delete_schedule_slot(date: str, time: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM schedule WHERE date=? AND time=?",
            (date, time),
        )
        await db.commit()


async def get_specialists() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM specialists ORDER BY is_active DESC, id"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_active_specialist() -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM specialists WHERE is_active=1 LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_specialist_by_id(specialist_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM specialists WHERE id=?",
            (specialist_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def add_specialist(name: str, profession: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM specialists") as cur:
            count = (await cur.fetchone())[0]
        is_active = 1 if count == 0 else 0
        cur = await db.execute(
            "INSERT INTO specialists (name, profession, is_active) VALUES (?, ?, ?)",
            (name, profession, is_active),
        )
        await db.commit()
        return cur.lastrowid


async def set_active_specialist(specialist_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE specialists SET is_active=0")
        await db.execute(
            "UPDATE specialists SET is_active=1 WHERE id=?",
            (specialist_id,),
        )
        await db.commit()


async def delete_specialist(specialist_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT is_active FROM specialists WHERE id=?",
            (specialist_id,),
        ) as cur:
            row = await cur.fetchone()
            active = bool(row and row[0] == 1)
        await db.execute(
            "DELETE FROM specialists WHERE id=?",
            (specialist_id,),
        )
        if active:
            async with db.execute(
                "SELECT id FROM specialists ORDER BY id LIMIT 1"
            ) as cur:
                row = await cur.fetchone()
                if row:
                    await db.execute(
                        "UPDATE specialists SET is_active=1 WHERE id=?",
                        (row[0],),
                    )
        await db.commit()


async def update_specialist(specialist_id: int, name: str, profession: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE specialists SET name=?, profession=? WHERE id=?",
            (name, profession, specialist_id),
        )
        await db.commit()


# ──────────────────────────────────────────────
# Записи (appointments)
# ──────────────────────────────────────────────

async def try_create_appointment(
    user_id: int,
    username: str,
    full_name: str,
    date: str,
    time: str,
    specialist_id: int | None = None,
    specialist_name: str = "",
) -> int | None:
    """
    Атомарная попытка занять слот.
    Возвращает ID записи или None если слот уже занят.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверка доступности (алиас a нужен для _TAKEN)
        async with db.execute(f"""
            SELECT 1 FROM appointments a
            WHERE a.date=? AND a.time=?
              AND ({_TAKEN})
        """, (date, time)) as cur:
            if await cur.fetchone():
                return None  # занято

        cur = await db.execute("""
            INSERT INTO appointments (user_id, username, full_name, date, time, status, specialist_id, specialist_name)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (user_id, username, full_name, date, time, specialist_id, specialist_name))
        await db.commit()
        return cur.lastrowid


async def confirm_appointment(apt_id: int, charge_id: str, stars: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE appointments SET status='active', charge_id=?, stars_paid=? WHERE id=?",
            (charge_id, stars, apt_id),
        )
        await db.commit()


async def cancel_appointment(apt_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE appointments SET status='cancelled' WHERE id=?",
            (apt_id,),
        )
        await db.commit()


async def get_appointment_by_id(apt_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM appointments WHERE id=?", (apt_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_user_appointments(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM appointments
            WHERE user_id=? AND status='active'
            ORDER BY date, time
        """, (user_id,)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_todays_appointments(today: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM appointments
            WHERE date=? AND status='active'
            ORDER BY time
        """, (today,)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_all_appointments() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM appointments
            WHERE status='active'
            ORDER BY date, time
        """) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_stats() -> dict:
    from datetime import date as dt_date
    today = dt_date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM appointments WHERE status='active'"
        ) as cur:
            total = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM appointments WHERE status='active' AND date=?",
            (today,),
        ) as cur:
            today_count = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COALESCE(SUM(stars_paid),0) FROM appointments WHERE status='active'"
        ) as cur:
            total_stars = (await cur.fetchone())[0]
    return {"total": total, "today": today_count, "total_stars": total_stars}


# ──────────────────────────────────────────────
# Контакты
# ──────────────────────────────────────────────

async def get_contacts() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM contacts ORDER BY id") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def add_contact(label: str, value: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO contacts (label, value) VALUES (?, ?)", (label, value)
        )
        await db.commit()


async def delete_contact(contact_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
        await db.commit()


# ──────────────────────────────────────────────
# Поддержка
# ──────────────────────────────────────────────

async def add_support_message(
    user_id: int, username: str, full_name: str, message: str
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO support_messages (user_id, username, full_name, message)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, full_name, message))
        await db.commit()
        return cur.lastrowid


async def get_unanswered_support() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM support_messages
            WHERE is_answered=0 ORDER BY created_at
        """) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_support_message(msg_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM support_messages WHERE id=?", (msg_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def answer_support(msg_id: int, reply: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE support_messages SET reply=?, is_answered=1 WHERE id=?",
            (reply, msg_id),
        )
        await db.commit()
