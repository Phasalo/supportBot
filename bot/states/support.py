from aiogram.fsm.state import State, StatesGroup


class SupportSG(StatesGroup):
    choosing_project = State()
    composing = State()


class OperatorReplySG(StatesGroup):
    in_reply = State()
