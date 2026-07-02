from aiogram import Bot, F, Router
from aiogram.types import Message

from bot.bot_utils.filters import HasOpenTicketFilter, NotCommandFilter
from bot.keyboards.reply import kb_contact
from bot.services.relay import notify_user_closed, relay_user_message
from db.models import UserModel
from db.repositories.tickets import TicketsRepository
from phrases import PHRASES_RU

router = Router()


@router.message(F.text == PHRASES_RU.button.user_close, HasOpenTicketFilter())
async def _(message: Message, bot: Bot, **kwargs):
    container = kwargs['dishka_container']
    user_row: UserModel = kwargs['user_row']
    tickets_repo: TicketsRepository = await container.get(TicketsRepository)
    ticket = tickets_repo.get_active_ticket_for_user(user_row.user_id)
    if ticket is None:
        return
    tickets_repo.close_ticket(ticket.ticket_id)
    await message.answer(PHRASES_RU.support.ticket_closed_user, reply_markup=kb_contact())
    await notify_user_closed(bot, container, ticket)


@router.message(NotCommandFilter(), HasOpenTicketFilter())
async def _(message: Message, bot: Bot, **kwargs):
    container = kwargs['dishka_container']
    user_row: UserModel = kwargs['user_row']
    tickets_repo: TicketsRepository = await container.get(TicketsRepository)
    ticket = tickets_repo.get_active_ticket_for_user(user_row.user_id)
    if ticket is None:
        return
    await relay_user_message(bot, container, ticket, message)
