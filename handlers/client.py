import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS, STARS_PRICE
from database import (
    get_setting,
    get_available_dates, get_available_times, try_create_appointment,
    get_user_appointments, get_appointment_by_id, cancel_appointment,
    get_contacts, add_support_message,
)
from states import BookingStates, CancelStates, SupportStates
from keyboards.client_kb import (
    main_menu_kb, cancel_state_kb,
    dates_kb, times_kb,
    appointments_kb, confirm_cancel_kb,
)

router = Router()
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# /start
# ══════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    business    = await get_setting("business_name")
    specialist  = await get_setting("specialist_name")
    profession  = await get_setting("specialist_profession")
    await message.answer(
        f"👋 Добро пожаловать в <b>{business}</b>!\n"
        f"👩‍⚕️ Специалист: <b>{specialist}</b>\n"
        f"🩺 Специальность: <b>{profession}</b>\n\n"
        f"Выберите действие:\n"
        f"Сделано ИП Павлов А.С.",
        reply_markup=main_menu_kb(),
    )


# ══════════════════════════════════════════════
# Записаться на приём
# ══════════════════════════════════════════════

@router.message(F.text == "📅 Записаться на приём")
async def book_start(message: Message, state: FSMContext) -> None:
    if (await get_setting("accepting")) != "1":
        await message.answer("⛔ Запись временно приостановлена. Попробуйте позже.")
        return

    dates = await get_available_dates()
    if not dates:
        await message.answer("📭 Свободных окошек пока нет. Загляните позже.")
        return

    await state.set_state(BookingStates.choosing_date)
    await message.answer("📅 Выберите удобную дату:", reply_markup=dates_kb(dates))


@router.callback_query(BookingStates.choosing_date, F.data.startswith("date:"))
async def cb_choose_date(callback: CallbackQuery, state: FSMContext) -> None:
    date = callback.data.removeprefix("date:")
    times = await get_available_times(date)

    if not times:
        await callback.answer("На эту дату нет свободного времени", show_alert=True)
        return

    await state.update_data(chosen_date=date)
    await state.set_state(BookingStates.choosing_time)

    y, m, d = date.split("-")
    await callback.message.edit_text(
        f"📅 Дата: <b>{d}.{m}.{y}</b>\n⏰ Выберите время:",
        reply_markup=times_kb(date, times),
    )
    await callback.answer()


@router.callback_query(BookingStates.choosing_date, F.data == "book_cancel")
async def cb_book_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.delete()
    await callback.answer()


@router.callback_query(BookingStates.choosing_time, F.data == "back_to_dates")
async def cb_back_to_dates(callback: CallbackQuery, state: FSMContext) -> None:
    dates = await get_available_dates()
    if not dates:
        await state.clear()
        await callback.message.edit_text("📭 Нет доступных дат.")
        await callback.answer()
        return

    await state.set_state(BookingStates.choosing_date)
    await callback.message.edit_text(
        "📅 Выберите удобную дату:",
        reply_markup=dates_kb(dates),
    )
    await callback.answer()


@router.callback_query(BookingStates.choosing_time, F.data.startswith("time:"))
async def cb_choose_time(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    _, payload = callback.data.split(":", 1)
    date, time = payload.split(":", 1)
    user = callback.from_user

    apt_id = await try_create_appointment(
        user_id=user.id,
        username=user.username or "",
        full_name=user.full_name or "",
        date=date,
        time=time,
    )

    if apt_id is None:
        # Слот заняли в другом окне — обновляем список
        await callback.answer("⚠️ Это время только что заняли. Выберите другое.", show_alert=True)
        times = await get_available_times(date)
        y, m, d = date.split("-")
        if times:
            await callback.message.edit_text(
                f"📅 Дата: <b>{d}.{m}.{y}</b>\n⏰ Выберите другое время:",
                reply_markup=times_kb(date, times),
            )
        else:
            await state.clear()
            await callback.message.edit_text(
                "😔 Все слоты на эту дату только что заняли.",
                reply_markup=None,
            )
        return

    # Состояние очищаем сразу — invoice живёт отдельно
    await state.clear()

    y, m, d = date.split("-")
    business = await get_setting("business_name")

    await callback.message.edit_text(
        f"💳 <b>Подтверждение и оплата</b>\n\n"
        f"📅 Дата: <b>{d}.{m}.{y}</b>\n"
        f"⏰ Время: <b>{time}</b>\n"
        f"💫 Стоимость: <b>{STARS_PRICE} ⭐️</b>\n\n"
        f"Оплатите следующим сообщением:"
    )
    await callback.answer()

    await bot.send_invoice(
        chat_id=user.id,
        title="Запись на приём",
        description=f"{business} · {d}.{m}.{y} · {time}",
        payload=f"apt:{apt_id}",
        currency="XTR",            # Telegram Stars
        prices=[LabeledPrice(label="Запись на приём", amount=STARS_PRICE)],
        provider_token="",         # пустой для Stars
    )


# ══════════════════════════════════════════════
# Мои записи
# ══════════════════════════════════════════════

@router.message(F.text == "📋 Мои записи")
async def my_appointments(message: Message) -> None:
    apts = await get_user_appointments(message.from_user.id)
    if not apts:
        await message.answer("📭 У вас нет активных записей.")
        return

    lines = []
    for apt in apts:
        y, m, d = apt["date"].split("-")
        stars = apt["stars_paid"]
        lines.append(f"• <b>{d}.{m}.{y}</b> в <b>{apt['time']}</b>  ⭐️ {stars}")

    await message.answer(
        "📋 <b>Ваши активные записи:</b>\n\n" + "\n".join(lines)
    )


# ══════════════════════════════════════════════
# Отменить запись
# ══════════════════════════════════════════════

@router.message(F.text == "❌ Отменить запись")
async def cancel_start(message: Message, state: FSMContext) -> None:
    apts = await get_user_appointments(message.from_user.id)
    if not apts:
        await message.answer("📭 Нет активных записей для отмены.")
        return

    await state.set_state(CancelStates.choosing_appointment)
    await message.answer(
        "Выберите запись для отмены:",
        reply_markup=appointments_kb(apts),
    )


@router.callback_query(CancelStates.choosing_appointment, F.data.startswith("cancel_apt:"))
async def cb_confirm_cancel(callback: CallbackQuery) -> None:
    apt_id = int(callback.data.removeprefix("cancel_apt:"))
    apt = await get_appointment_by_id(apt_id)

    if not apt or apt["user_id"] != callback.from_user.id:
        await callback.answer("Запись не найдена", show_alert=True)
        return

    y, m, d = apt["date"].split("-")
    stars = apt.get("stars_paid", 0)
    refund_note = (
        f"\n💫 Возврат <b>{stars} ⭐️</b> будет выполнен автоматически."
        if stars > 0 else ""
    )

    await callback.message.edit_text(
        f"❗ Отмена записи:\n"
        f"📅 <b>{d}.{m}.{y}</b> в <b>{apt['time']}</b>"
        f"{refund_note}\n\n"
        f"Подтвердить?",
        reply_markup=confirm_cancel_kb(apt_id),
    )
    await callback.answer()


@router.callback_query(CancelStates.choosing_appointment, F.data == "cancel_back")
async def cb_cancel_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "back_to_my_apts")
async def cb_back_to_my_apts(callback: CallbackQuery, state: FSMContext) -> None:
    apts = await get_user_appointments(callback.from_user.id)
    if not apts:
        await state.clear()
        await callback.message.edit_text("📭 Нет активных записей.")
        await callback.answer()
        return

    await state.set_state(CancelStates.choosing_appointment)
    await callback.message.edit_text(
        "Выберите запись для отмены:",
        reply_markup=appointments_kb(apts),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_cancel:"))
async def cb_do_cancel(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    apt_id = int(callback.data.removeprefix("confirm_cancel:"))
    apt = await get_appointment_by_id(apt_id)

    if not apt or apt["user_id"] != callback.from_user.id:
        await callback.answer("Запись не найдена", show_alert=True)
        await state.clear()
        return

    # Возврат Stars
    refunded = False
    if apt.get("charge_id") and apt.get("stars_paid", 0) > 0:
        try:
            await bot.refund_star_payment(
                user_id=callback.from_user.id,
                telegram_payment_charge_id=apt["charge_id"],
            )
            refunded = True
        except Exception as e:
            log.error("Refund failed apt_id=%s: %s", apt_id, e)

    await cancel_appointment(apt_id)
    await state.clear()

    y, m, d = apt["date"].split("-")
    refund_text = (
        f"\n💫 Возврат <b>{apt['stars_paid']} ⭐️</b> выполнен."
        if refunded
        else ("\n⚠️ Не удалось вернуть звёзды. Обратитесь в поддержку."
              if apt.get("stars_paid", 0) > 0 else "")
    )

    await callback.message.edit_text(
        f"✅ Запись <b>{d}.{m}.{y}</b> в <b>{apt['time']}</b> отменена.{refund_text}"
    )
    await callback.answer()


# ══════════════════════════════════════════════
# Контакты
# ══════════════════════════════════════════════

@router.message(F.text == "📞 Контакты")
async def show_contacts(message: Message) -> None:
    contacts = await get_contacts()
    business  = await get_setting("business_name")

    if not contacts:
        text = f"📞 <b>Контакты {business}</b>\n\nКонтактная информация пока не добавлена."
    else:
        lines = [f"• <b>{c['label']}:</b> {c['value']}" for c in contacts]
        text = f"📞 <b>Контакты {business}</b>\n\n" + "\n".join(lines)

    await message.answer(text)


# ══════════════════════════════════════════════
# Поддержка
# ══════════════════════════════════════════════

@router.message(F.text == "💬 Поддержка")
async def support_start(message: Message, state: FSMContext) -> None:
    await state.set_state(SupportStates.writing_message)
    await message.answer(
        "💬 Напишите ваш вопрос — администратор ответит как можно скорее:",
        reply_markup=cancel_state_kb(),
    )


@router.message(SupportStates.writing_message, F.text == "◀️ Отмена")
async def support_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Главное меню:", reply_markup=main_menu_kb())


@router.message(SupportStates.writing_message)
async def support_send(message: Message, state: FSMContext, bot: Bot) -> None:
    msg_id = await add_support_message(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name or "",
        message=message.text,
    )
    await state.clear()
    await message.answer(
        "✅ Вопрос отправлен. Ожидайте ответа в этом чате.",
        reply_markup=main_menu_kb(),
    )

    # Уведомляем всех администраторов
    name = (
        message.from_user.full_name
        or f"@{message.from_user.username}"
        or str(message.from_user.id)
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"💬 <b>Новый вопрос #{msg_id}</b>\n"
                f"От: {name} (id: <code>{message.from_user.id}</code>)\n\n"
                f"<i>{message.text}</i>\n\n"
                f"Ответить: /admin → 📩 Вопросы",
            )
        except Exception:
            pass
