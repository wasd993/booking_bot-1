"""
Обработчики платежей Telegram Stars.

Схема:
  1. bot.send_invoice(currency='XTR', provider_token='')  ← в client.py
  2. PreCheckoutQuery → проверяем статус pending → answer ok/fail
  3. SuccessfulPayment → confirm_appointment (status=active, charge_id)
"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, PreCheckoutQuery

from database import confirm_appointment, cancel_appointment, get_appointment_by_id
from keyboards.client_kb import main_menu_kb

router = Router()
log = logging.getLogger(__name__)


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    payload = query.invoice_payload

    if not payload.startswith("apt:"):
        await query.answer(ok=False, error_message="Неверный запрос оплаты.")
        return

    try:
        apt_id = int(payload.removeprefix("apt:"))
    except ValueError:
        await query.answer(ok=False, error_message="Неверный ID записи.")
        return

    apt = await get_appointment_by_id(apt_id)

    if apt is None:
        await query.answer(ok=False, error_message="Запись не найдена.")
        return

    if apt["status"] != "pending":
        await query.answer(ok=False, error_message="Запись уже оплачена или отменена.")
        return

    if apt["user_id"] != query.from_user.id:
        await query.answer(ok=False, error_message="Запись принадлежит другому пользователю.")
        return

    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    sp      = message.successful_payment
    payload = sp.invoice_payload

    if not payload.startswith("apt:"):
        log.error("Unknown payment payload: %s", payload)
        return

    apt_id    = int(payload.removeprefix("apt:"))
    charge_id = sp.telegram_payment_charge_id
    stars     = sp.total_amount          # число звёзд

    await confirm_appointment(apt_id, charge_id, stars)
    apt = await get_appointment_by_id(apt_id)

    if apt:
        y, m, d = apt["date"].split("-")
        await message.answer(
            f"✅ <b>Запись подтверждена!</b>\n\n"
            f"📅 Дата: <b>{d}.{m}.{y}</b>\n"
            f"⏰ Время: <b>{apt['time']}</b>\n"
            f"⭐️ Оплачено: <b>{stars}</b> звёзд\n\n"
            f"Ждём вас! 😊",
            reply_markup=main_menu_kb(),
        )
    else:
        await message.answer("✅ Оплата прошла успешно!", reply_markup=main_menu_kb())
