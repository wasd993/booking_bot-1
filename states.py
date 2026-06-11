from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    choosing_date = State()
    choosing_time = State()


class CancelStates(StatesGroup):
    choosing_appointment = State()


class SupportStates(StatesGroup):
    writing_message = State()


class AdminStates(StatesGroup):
    # Профиль
    editing_business_name   = State()
    editing_specialist_name = State()
    editing_specialist_profession = State()
    adding_specialist_name = State()
    adding_specialist_profession = State()
    # Расписание
    adding_schedule_date = State()
    selecting_schedule_times = State()
    # Контакты
    adding_contact_label = State()
    adding_contact_value = State()
    # Поддержка
    replying_support = State()
