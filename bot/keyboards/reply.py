from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from phrases import PHRASES_RU


def kb_contact() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=PHRASES_RU.button.user_contact)]],
        resize_keyboard=True,
        is_persistent=True,
    )


def kb_in_ticket() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=PHRASES_RU.button.user_close)]],
        resize_keyboard=True,
        is_persistent=True,
    )


def kb_compose_cancel() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=PHRASES_RU.button.user_cancel)]],
        resize_keyboard=True,
        is_persistent=True,
    )
