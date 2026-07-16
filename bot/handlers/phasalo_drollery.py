from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import Message

router = Router()


@router.message(StateFilter(None), F.text.lower().in_(['спасибо', 'от души', 'благодарю']))
async def _(message: Message):
    await message.answer_sticker(sticker='CAACAgEAAxkBAAEKShplAfTsN4pzL4pB_yuGKGksXz2oywACZQEAAnY3dj9hlcwZRAnaOjAE')
