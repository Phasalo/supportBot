import logging

from aiogram import Router
from aiogram.filters import ExceptionTypeFilter
from aiogram.types import CallbackQuery, ErrorEvent
from aiogram_dialog.api.exceptions import OutdatedIntent, UnknownIntent

from bot.bot_utils.markup import drop_keyboard
from phrases import PHRASES_RU

logger = logging.getLogger(__name__)

router = Router()


@router.errors(ExceptionTypeFilter(UnknownIntent, OutdatedIntent))
async def on_outdated_dialog(event: ErrorEvent) -> None:
    logger.warning('Dialog context lost: %s', event.exception)
    callback = event.update.callback_query
    if isinstance(callback, CallbackQuery):
        await callback.answer(PHRASES_RU.error.dialog_expired, show_alert=True)
        await drop_keyboard(callback)
