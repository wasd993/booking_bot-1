from datetime import date as dt_date, timedelta

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ──────────────────────────────────────────────
# Reply-клавиатуры
# ──────────────────────────────────────────────

def admin_menu_kb(accepting: bool) -> ReplyKeyboardMarkup:
    status = "✅ ВКЛ" if accepting else "❌ ВЫКЛ"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль"),
             KeyboardButton(text=f"🔄 Приём: {status}")],
            [KeyboardButton(text="📅 Расписание"),
             KeyboardButton(text="📋 Записи сегодня")],
            [KeyboardButton(text="🧑‍⚕️ Специалисты"),
             KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="⚙️ Контакты"),
             KeyboardButton(text="📩 Вопросы")],
            [KeyboardButton(text="📤 Экспорт Excel")],
        ],
        resize_keyboard=True,
    )


def cancel_admin_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="◀️ Отмена")]],
        resize_keyboard=True,
    )


def profile_admin_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="названия"), KeyboardButton(text="Специалист"), KeyboardButton(text="Специальность")],
            [KeyboardButton(text="◀️ Назад")],
        ],
        resize_keyboard=True,
    )


# ──────────────────────────────────────────────
# Inline-клавиатуры — расписание
# ──────────────────────────────────────────────

def schedule_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="➕ Добавить слот",   callback_data="sched_add")
    b.button(text="🗑 Удалить слот",    callback_data="sched_remove")
    b.button(text="📋 Показать все",    callback_data="sched_show")
    b.adjust(1)
    return b.as_markup()


def _fmt_date(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


def schedule_dates_kb(days: int = 14) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    today = dt_date.today()
    for offset in range(days):
        slot = today + timedelta(days=offset)
        iso = slot.isoformat()
        builder.button(
            text=_fmt_date(iso),
            callback_data=f"sched_date:{iso}",
        )
    builder.adjust(4)
    builder.button(text="◀️ Назад", callback_data="sched_back")
    return builder.as_markup()


def schedule_times_kb(date: str, selected: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for hour in range(24):
        time = f"{hour:02d}:00"
        marker = " ✅" if time in selected else ""
        builder.button(
            text=f"{time}{marker}",
            callback_data=f"sched_time:{date}:{time}",
        )
    builder.adjust(4)
    builder.button(text="✅ Сохранить", callback_data="sched_time_done")
    builder.button(text="◀️ Назад", callback_data="sched_back")
    return builder.as_markup()


def specialists_manage_kb(specialists: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for sp in specialists:
        prefix = "✅" if sp["is_active"] == 1 else "▫️"
        builder.button(
            text=f"{prefix} {sp['name']} ({sp['profession']})",
            callback_data=f"spec_active:{sp['id']}",
        )
        builder.button(
            text=f"🗑 {sp['name']}",
            callback_data=f"spec_delete:{sp['id']}",
        )
    builder.adjust(2)
    builder.button(text="➕ Добавить", callback_data="spec_add")
    builder.button(text="◀️ Назад", callback_data="spec_back")
    return builder.as_markup()


def slots_remove_kb(slots: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for date, time in slots:
        b.button(
            text=f"🗑 {_fmt_date(date)} {time}",
            callback_data=f"del_slot:{date}:{time}",
        )
    b.adjust(1)
    b.button(text="◀️ Назад", callback_data="sched_back")
    return b.as_markup()


# ──────────────────────────────────────────────
# Inline-клавиатуры — контакты
# ──────────────────────────────────────────────

def contacts_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="➕ Добавить",    callback_data="contact_add")
    b.button(text="🗑 Удалить",     callback_data="contact_remove")
    b.button(text="📋 Показать",    callback_data="contact_show")
    b.adjust(1)
    return b.as_markup()


def contacts_remove_kb(contacts: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in contacts:
        b.button(
            text=f"🗑 {c['label']}: {c['value']}",
            callback_data=f"del_contact:{c['id']}",
        )
    b.adjust(1)
    b.button(text="◀️ Назад", callback_data="contact_back")
    return b.as_markup()


# ──────────────────────────────────────────────
# Inline-клавиатуры — поддержка
# ──────────────────────────────────────────────

def support_messages_kb(messages: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for msg in messages:
        name = msg.get("full_name") or f"@{msg.get('username')}" or str(msg["user_id"])
        preview = msg["message"][:28] + ("…" if len(msg["message"]) > 28 else "")
        b.button(
            text=f"#{msg['id']} {name}: {preview}",
            callback_data=f"reply_support:{msg['id']}",
        )
    b.adjust(1)
    return b.as_markup()
