# =====================================================================
# АВТОРСКИЕ ПРАВА И УСЛОВИЯ ИСПОЛЬЗОВАНИЯ
#
# Продукт: Telegram-бот для записи на приём (Пакет 1)
# Правообладатель: Павлов А. С.
# © 2026 Павлов А. С. Все права защищены.
#
# Лицензия: неисключительная, для одного проекта.
# Запрещено: перепродажа, публичное распространение кода,
# удаление копирайтов, создание производных для распространения.
# Нарушение: ст. 1301 ГК РФ, компенсация до 5 000 000 руб.
# Контакты: red1dark.studio@mail.ru
# =====================================================================

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from handlers import payments, admin, client   # порядок важен!

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s]  %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


async def main() -> None:
    await init_db()
    log.info("База данных инициализирована.")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Порядок роутеров: payments → admin → client
    # payments первый — чтобы pre_checkout/successful_payment
    # обрабатывались без конкуренции с другими хэндлерами.
    dp.include_routers(payments.router, admin.router, client.router)

    log.info("Бот запущен. Ожидаю обновления…")
    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
    )


if __name__ == "__main__":
    asyncio.run(main())
