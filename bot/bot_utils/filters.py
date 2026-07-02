from aiogram.filters import BaseFilter
from aiogram.types import Message, TelegramObject

from db.models import UserModel
from db.repositories.operators import OperatorsRepository
from db.repositories.tickets import TicketsRepository


class AdminFilter(BaseFilter):
    async def __call__(self, message: Message, user_row: UserModel | None = None) -> bool:
        return user_row is not None and user_row.is_admin


class OperatorFilter(BaseFilter):
    async def __call__(
        self,
        event: TelegramObject,
        user_row: UserModel | None = None,
        dishka_container=None,
    ) -> bool:
        if user_row is None or dishka_container is None:
            return False
        operators_repo: OperatorsRepository = await dishka_container.get(OperatorsRepository)
        return operators_repo.is_operator(user_row.user_id)


class NotCommandFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return not (message.text and message.text.startswith('/'))


class HasOpenTicketFilter(BaseFilter):
    async def __call__(
        self,
        message: Message,
        user_row: UserModel | None = None,
        dishka_container=None,
    ) -> bool:
        if user_row is None or dishka_container is None:
            return False
        tickets_repo: TicketsRepository = await dishka_container.get(TicketsRepository)
        return tickets_repo.get_active_ticket_for_user(user_row.user_id) is not None
