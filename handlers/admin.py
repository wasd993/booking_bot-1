"""
Административная панель.

Вход: /admin
Все хэндлеры проверяют is_admin() для защиты.
Кнопки в admin_menu_kb имеют уникальные названия —
конфликтов с клиентскими кнопками нет.
"""

import logging
from datetime import date as dt_date

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS
from database import (
    get_setting, set_setting,
    get_all_schedule, add_schedule_slot, delete_schedule_slot,
    get_todays_appointments, get_all_appointments, get_stats,
    get_contacts, add_contact, delete_contact,
    get_unanswered_support, get_support_message, answer_support,
)
from states import AdminStates
from keyboards.admin_kb import (
    admin_menu_kb, cancel_admin_kb, profile_admin_kb,
    schedule_menu_kb, slots_remove_kb,
    contacts_menu_kb, contacts_remove_kb,
    support_messages_kb,
)
from utils.export import export_appointments_to_excel

router = Router()
log = logging.getLogger(__name__)


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


# ──────────────────────────────────────────────
# Вход в панель
# ──────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    accepting = (await get_setting("accepting")) == "1"
    await message.answer("🔑 <b>Панель администратора</b>", reply_markup=admin_menu_kb(accepting))


# ──────────────────────────────────────────────
# Профиль
# ──────────────────────────────────────────────

@router.message(F.text == "👤 Профиль")
async def admin_profile(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    business    = await get_setting("business_name")
    specialist  = await get_setting("specialist_name")
    profession  = await get_setting("specialist_profession")
    await message.answer(
        f"👤 <b>Профиль</b>\n\n"
        f"🏢 Название: <b>{business}</b>\n"
        f"👩‍⚕️ Специалист: <b>{specialist}</b>\n"
        f"🩺 Специальность: <b>{profession}</b>\n\n"
        f"Нажмите кнопку, чтобы изменить данные.\n"
        f"Сделано ИП Павлов А.С.",
        reply_markup=profile_admin_kb(),
    )


@router.message(F.text == "◀️ Назад")
async def admin_profile_back(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    accepting = (await get_setting("accepting")) == "1"
    await message.answer("🔑 <b>Панель администратора</b>", reply_markup=admin_menu_kb(accepting))


@router.message(F.text == "названия")
@router.message(Command("edit_business"))
async def edit_business_start(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.editing_business_name)
    await message.answer("Введите новое название компании:", reply_markup=cancel_admin_kb())


@router.message(F.text == "Специалист")
@router.message(Command("edit_specialist"))
async def edit_specialist_start(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.editing_specialist_name)
    await message.answer("Введите ФИО специалиста:", reply_markup=cancel_admin_kb())


@router.message(F.text == "Специальность")
@router.message(Command("edit_speciality"))
async def edit_specialist_profession_start(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.editing_specialist_profession)
    await message.answer("Введите специальность специалиста:", reply_markup=cancel_admin_kb())


@router.message(AdminStates.editing_business_name, F.text == "◀️ Отмена")
async def edit_business_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=admin_menu_kb((await get_setting("accepting")) == "1"))


@router.message(AdminStates.editing_business_name)
async def edit_business_save(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    name = message.text.strip()
    await set_setting("business_name", name)
    await state.clear()
    await message.answer(
        f"✅ Название обновлено: <b>{name}</b>",
        reply_markup=admin_menu_kb((await get_setting("accepting")) == "1"),
    )


@router.message(AdminStates.editing_specialist_name, F.text == "◀️ Отмена")
async def edit_specialist_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=admin_menu_kb((await get_setting("accepting")) == "1"))


@router.message(AdminStates.editing_specialist_name)
async def edit_specialist_save(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    name = message.text.strip()
    await set_setting("specialist_name", name)
    await state.clear()
    await message.answer(
        f"✅ Имя специалиста обновлено: <b>{name}</b>",
        reply_markup=admin_menu_kb((await get_setting("accepting")) == "1"),
    )


@router.message(AdminStates.editing_specialist_profession, F.text == "◀️ Отмена")
async def edit_specialist_profession_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=admin_menu_kb((await get_setting("accepting")) == "1"))


@router.message(AdminStates.editing_specialist_profession)
async def edit_specialist_profession_save(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    profession = message.text.strip()
    await set_setting("specialist_profession", profession)
    await state.clear()
    await message.answer(
        f"✅ Специальность обновлена: <b>{profession}</b>",
        reply_markup=admin_menu_kb((await get_setting("accepting")) == "1"),
    )


# ──────────────────────────────────────────────
# Включить / выключить приём
# ──────────────────────────────────────────────

@router.message(F.text.startswith("🔄 Приём:"))
async def toggle_accepting(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    current   = await get_setting("accepting")
    new_value = "0" if current == "1" else "1"
    await set_setting("accepting", new_value)
    status = "включён ✅" if new_value == "1" else "выключен ❌"
    await message.answer(
        f"🔄 Приём записей {status}.",
        reply_markup=admin_menu_kb(new_value == "1"),
    )


# ──────────────────────────────────────────────
# Расписание
# ──────────────────────────────────────────────

@router.message(F.text == "📅 Расписание")
async def admin_schedule(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    await message.answer("📅 <b>Расписание</b>", reply_markup=schedule_menu_kb())


@router.callback_query(F.data == "sched_show")
async def sched_show(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return
    slots = await get_all_schedule()
    if not slots:
        await callback.answer("Расписание пустое", show_alert=True)
        return

    lines = []
    for date, time in slots:
        y, m, d = date.split("-")
        lines.append(f"• {d}.{m}.{y} — {time}")
    await callback.message.edit_text(
        "📅 <b>Все слоты:</b>\n\n" + "\n".join(lines),
        reply_markup=schedule_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "sched_add")
async def sched_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.adding_date)
    await callback.message.answer(
        "Введите дату в формате <b>ДД.ММ.ГГГГ</b>:",
        reply_markup=cancel_admin_kb(),
    )
    await callback.answer()


@router.message(AdminStates.adding_date, F.text == "◀️ Отмена")
async def sched_add_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=admin_menu_kb((await get_setting("accepting")) == "1"))


@router.message(AdminStates.adding_date)
async def sched_add_date(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip()
    try:
        day, month, year = text.split(".")
        date_iso = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        dt_date.fromisoformat(date_iso)  # валидация
    except Exception:
        await message.answer("❌ Неверный формат. Введите дату как <b>ДД.ММ.ГГГГ</b>:")
        return

    await state.update_data(adding_date=date_iso)
    await state.set_state(AdminStates.adding_time)
    await message.answer(
        f"Дата: <b>{text}</b>\n\n"
        f"Введите время в формате <b>ЧЧ:ММ</b>.\n"
        f"Несколько через запятую: <b>09:00, 10:30, 14:00</b>",
    )


@router.message(AdminStates.adding_time, F.text == "◀️ Отмена")
async def sched_add_time_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=admin_menu_kb((await get_setting("accepting")) == "1"))


@router.message(AdminStates.adding_time)
async def sched_add_time(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    data     = await state.get_data()
    date_iso = data["adding_date"]
    raw      = [t.strip() for t in message.text.split(",")]

    added, errors = 0, []
    for t in raw:
        try:
            h, min_ = t.split(":")
            assert 0 <= int(h) <= 23 and 0 <= int(min_) <= 59
            await add_schedule_slot(date_iso, f"{h.zfill(2)}:{min_.zfill(2)}")
            added += 1
        except Exception:
            errors.append(t)

    await state.clear()
    result = f"✅ Добавлено слотов: <b>{added}</b>"
    if errors:
        result += f"\n❌ Пропущено: {', '.join(errors)}"
    await message.answer(result, reply_markup=admin_menu_kb((await get_setting("accepting")) == "1"))


@router.callback_query(F.data == "sched_remove")
async def sched_remove_start(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return
    slots = await get_all_schedule()
    if not slots:
        await callback.answer("Расписание пустое", show_alert=True)
        return
    await callback.message.edit_text(
        "🗑 Выберите слот для удаления:",
        reply_markup=slots_remove_kb(slots),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("del_slot:"))
async def del_slot(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return
    _, payload = callback.data.split(":", 1)
    date, time = payload.split(":", 1)
    await delete_schedule_slot(date, time)

    slots = await get_all_schedule()
    y, m, d = date.split("-")
    if slots:
        await callback.message.edit_text(
            f"✅ Слот {d}.{m}.{y} {time} удалён. Выберите следующий:",
            reply_markup=slots_remove_kb(slots),
        )
    else:
        await callback.message.edit_text(
            f"✅ Слот {d}.{m}.{y} {time} удалён. Расписание пустое.",
            reply_markup=schedule_menu_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "sched_back")
async def sched_back(callback: CallbackQuery) -> None:
    await callback.message.edit_text("📅 <b>Расписание</b>", reply_markup=schedule_menu_kb())
    await callback.answer()


# ──────────────────────────────────────────────
# Записи на сегодня
# ──────────────────────────────────────────────

@router.message(F.text == "📋 Записи сегодня")
async def todays_appointments(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    today = dt_date.today().isoformat()
    apts  = await get_todays_appointments(today)

    if not apts:
        await message.answer("📭 Сегодня записей нет.")
        return

    y, m, d = today.split("-")
    lines = []
    for apt in apts:
        name = apt.get("full_name") or f"@{apt.get('username')}" or str(apt["user_id"])
        lines.append(f"⏰ <b>{apt['time']}</b> — {name}")

    await message.answer(
        f"📋 <b>Записи на {d}.{m}.{y}:</b>\n\n" + "\n".join(lines)
    )


# ──────────────────────────────────────────────
# Статистика
# ──────────────────────────────────────────────

@router.message(F.text == "📊 Статистика")
async def admin_stats(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    s = await get_stats()
    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"📋 Всего активных записей: <b>{s['total']}</b>\n"
        f"📅 Записей сегодня: <b>{s['today']}</b>\n"
        f"⭐️ Звёзд получено: <b>{s['total_stars']}</b>"
    )


# ──────────────────────────────────────────────
# Контакты (управление)
# ──────────────────────────────────────────────

@router.message(F.text == "⚙️ Контакты")
async def admin_contacts(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    await message.answer("⚙️ <b>Управление контактами</b>", reply_markup=contacts_menu_kb())


@router.callback_query(F.data == "contact_show")
async def contact_show(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return
    contacts = await get_contacts()
    if not contacts:
        await callback.answer("Контакты ещё не добавлены", show_alert=True)
        return
    lines = [f"• <b>{c['label']}:</b> {c['value']}" for c in contacts]
    await callback.message.edit_text(
        "📞 <b>Контакты:</b>\n\n" + "\n".join(lines),
        reply_markup=contacts_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "contact_add")
async def contact_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.adding_contact_label)
    await callback.message.answer(
        "Введите название контакта (например: <b>Телефон</b>, <b>ВКонтакте</b>):",
        reply_markup=cancel_admin_kb(),
    )
    await callback.answer()


@router.message(AdminStates.adding_contact_label, F.text == "◀️ Отмена")
async def contact_add_label_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=admin_menu_kb((await get_setting("accepting")) == "1"))


@router.message(AdminStates.adding_contact_label)
async def contact_add_label(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.update_data(contact_label=message.text.strip())
    await state.set_state(AdminStates.adding_contact_value)
    await message.answer(f"Введите значение для «<b>{message.text.strip()}</b>»:")


@router.message(AdminStates.adding_contact_value, F.text == "◀️ Отмена")
async def contact_add_value_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=admin_menu_kb((await get_setting("accepting")) == "1"))


@router.message(AdminStates.adding_contact_value)
async def contact_add_value(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    data  = await state.get_data()
    label = data["contact_label"]
    value = message.text.strip()
    await add_contact(label, value)
    await state.clear()
    await message.answer(
        f"✅ Добавлено: <b>{label}:</b> {value}",
        reply_markup=admin_menu_kb((await get_setting("accepting")) == "1"),
    )


@router.callback_query(F.data == "contact_remove")
async def contact_remove_start(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return
    contacts = await get_contacts()
    if not contacts:
        await callback.answer("Контактов нет", show_alert=True)
        return
    await callback.message.edit_text(
        "Выберите контакт для удаления:",
        reply_markup=contacts_remove_kb(contacts),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("del_contact:"))
async def del_contact(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return
    cid = int(callback.data.removeprefix("del_contact:"))
    await delete_contact(cid)
    contacts = await get_contacts()
    if contacts:
        await callback.message.edit_text(
            "✅ Удалено. Выберите следующий:",
            reply_markup=contacts_remove_kb(contacts),
        )
    else:
        await callback.message.edit_text(
            "✅ Удалено. Контактов больше нет.",
            reply_markup=contacts_menu_kb(),
        )
    await callback.answer()


@router.callback_query(F.data == "contact_back")
async def contact_back(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "⚙️ <b>Управление контактами</b>", reply_markup=contacts_menu_kb()
    )
    await callback.answer()


# ──────────────────────────────────────────────
# Поддержка (ответы)
# ──────────────────────────────────────────────

@router.message(F.text == "📩 Вопросы")
async def admin_support(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    messages = await get_unanswered_support()
    if not messages:
        await message.answer("📩 Новых вопросов нет.")
        return
    await message.answer(
        f"📩 <b>Вопросы без ответа: {len(messages)}</b>\n\nВыберите:",
        reply_markup=support_messages_kb(messages),
    )


@router.callback_query(F.data.startswith("reply_support:"))
async def reply_support_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return
    msg_id = int(callback.data.removeprefix("reply_support:"))
    msg    = await get_support_message(msg_id)

    if not msg:
        await callback.answer("Сообщение не найдено", show_alert=True)
        return

    name = msg.get("full_name") or f"@{msg.get('username')}" or str(msg["user_id"])
    await state.set_state(AdminStates.replying_support)
    await state.update_data(support_msg_id=msg_id, support_user_id=msg["user_id"])

    await callback.message.answer(
        f"💬 Вопрос <b>#{msg_id}</b> от <b>{name}</b>:\n\n"
        f"<i>{msg['message']}</i>\n\n"
        f"Введите ответ:",
        reply_markup=cancel_admin_kb(),
    )
    await callback.answer()


@router.message(AdminStates.replying_support, F.text == "◀️ Отмена")
async def reply_support_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=admin_menu_kb((await get_setting("accepting")) == "1"))


@router.message(AdminStates.replying_support)
async def reply_support_send(message: Message, state: FSMContext, bot: Bot) -> None:
    if not is_admin(message.from_user.id):
        return
    data    = await state.get_data()
    msg_id  = data["support_msg_id"]
    user_id = data["support_user_id"]

    await answer_support(msg_id, message.text)

    sent = False
    try:
        await bot.send_message(
            user_id,
            f"💬 <b>Ответ администратора:</b>\n\n{message.text}",
        )
        sent = True
    except Exception as e:
        log.error("Cannot send reply to user %s: %s", user_id, e)

    await state.clear()
    status = "✅ Ответ отправлен." if sent else "⚠️ Сохранено, но отправить пользователю не удалось."
    await message.answer(status, reply_markup=admin_menu_kb((await get_setting("accepting")) == "1"))


# ──────────────────────────────────────────────
# Экспорт в Excel
# ──────────────────────────────────────────────

@router.message(F.text == "📤 Экспорт Excel")
async def admin_export(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    apts = await get_all_appointments()
    if not apts:
        await message.answer("📭 Нет активных записей для экспорта.")
        return

    await message.answer("⏳ Формирую файл...")
    file_bytes = await export_appointments_to_excel(apts)
    today = dt_date.today().strftime("%Y-%m-%d")
    await message.answer_document(
        document=BufferedInputFile(file_bytes, filename=f"записи_{today}.xlsx"),
        caption=f"📤 Экспорт записей · {today}",
    )
