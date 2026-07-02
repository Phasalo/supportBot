import contextlib

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message


async def drop_keyboard(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_reply_markup(reply_markup=None)
