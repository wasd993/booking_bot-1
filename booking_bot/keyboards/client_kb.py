from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ──────────────────────────────────────────────
# Reply-клавиатуры
# ──────────────────────────────────────────────

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Записаться на приём")],
            [KeyboardButton(text="📋 Мои записи"),
             KeyboardButton(text="❌ Отменить запись")],
            [KeyboardButton(text="📞 Контакты"),
             KeyboardButton(text="💬 Поддержка")],
        ],
        resize_keyboard=True,
    )


def cancel_state_kb() -> ReplyKeyboardMarkup:
    """Кнопка «Отмена» для любого FSM-состояния."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="◀️ Отмена")]],
        resize_keyboard=True,
    )


# ──────────────────────────────────────────────
# Inline-клавиатуры
# ──────────────────────────────────────────────

def _fmt_date(iso: str) -> str:
    """YYYY-MM-DD → DD.MM.YYYY"""
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


def dates_kb(dates: list[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for date in dates:
        b.button(text=_fmt_date(date), callback_data=f"date:{date}")
    b.adjust(2)
    b.button(text="🚫 Отмена", callback_data="book_cancel")
    b.adjust(2, 1)
    return b.as_markup()


def times_kb(date: str, times: list[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t in times:
        b.button(text=t, callback_data=f"time:{date}:{t}")
    b.adjust(3)
    b.button(text="◀️ Назад к датам", callback_data="back_to_dates")
    b.adjust(3, 1)
    return b.as_markup()


def appointments_kb(apts: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for apt in apts:
        label = f"{_fmt_date(apt['date'])} в {apt['time']}"
        b.button(text=label, callback_data=f"cancel_apt:{apt['id']}")
    b.adjust(1)
    b.button(text="◀️ Назад", callback_data="cancel_back")
    return b.as_markup()


def confirm_cancel_kb(apt_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да, отменить", callback_data=f"confirm_cancel:{apt_id}")
    b.button(text="◀️ Назад", callback_data="back_to_my_apts")
    b.adjust(1)
    return b.as_markup()
