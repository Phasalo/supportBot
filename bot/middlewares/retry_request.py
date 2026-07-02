import asyncio
import logging

from aiogram import Bot
from aiogram.client.session.middlewares.base import BaseRequestMiddleware, NextRequestMiddlewareType
from aiogram.methods import TelegramMethod
from aiogram.methods.base import Response, TelegramType
from aiohttp import ClientConnectorError, ClientOSError, ClientProxyConnectionError, ServerDisconnectedError

logger = logging.getLogger(__name__)

_TRANSIENT: tuple[type[BaseException], ...] = (
    ClientConnectorError,
    ClientProxyConnectionError,
    ServerDisconnectedError,
    ClientOSError,
)

try:
    from python_socks import ProxyError

    _TRANSIENT = (*_TRANSIENT, ProxyError)
except ImportError:
    pass


class RetryRequestMiddleware(BaseRequestMiddleware):
    """Повторяет запрос при транзиентных ошибках транспорта (флапающий прокси отдаёт 403/обрыв)."""

    def __init__(self, retries: int = 2, delay: float = 1.0):
        self.retries = retries
        self.delay = delay

    async def __call__(
        self,
        make_request: NextRequestMiddlewareType[TelegramType],
        bot: Bot,
        method: TelegramMethod[TelegramType],
    ) -> Response[TelegramType]:
        attempt = 0
        while True:
            try:
                return await make_request(bot, method)
            except _TRANSIENT as e:
                if attempt >= self.retries:
                    raise
                attempt += 1
                logger.warning(
                    'Transient transport error on %s (%s: %s), retry %d/%d',
                    type(method).__name__,
                    type(e).__name__,
                    e,
                    attempt,
                    self.retries,
                )
                await asyncio.sleep(self.delay)
