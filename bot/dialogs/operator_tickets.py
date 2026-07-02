from operator import itemgetter

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager, Window
from aiogram_dialog.widgets.kbd import Cancel, ScrollingGroup, Select
from aiogram_dialog.widgets.text import Const, Format

from bot.bot_utils.dialogs import QuietDialog
from bot.keyboards.inline import kb_open_ticket
from config.const import TICKETS_PER_PAGE
from db.repositories.operators import OperatorsRepository
from db.repositories.tickets import TicketsRepository
from phrases import PHRASES_RU
from utils.format_string import project_link


class OperatorTicketsSG(StatesGroup):
    list = State()


async def panel_getter(dialog_manager: DialogManager, **kwargs):
    container = kwargs['dishka_container']
    user_id = dialog_manager.middleware_data['event_from_user'].id
    tickets_repo: TicketsRepository = await container.get(TicketsRepository)
    tickets = tickets_repo.get_active_tickets_for_operator(user_id)
    items = [
        (
            f'#{t.ticket_id} · {t.project.title if t.project else "?"} · {t.user.full_name() if t.user else t.user_id}',
            t.ticket_id,
        )
        for t in tickets
    ]
    return {
        'tickets': items,
        'text': PHRASES_RU.operator.panel_title if items else PHRASES_RU.operator.panel_empty,
    }


async def on_pick_ticket(callback: CallbackQuery, _widget, manager: DialogManager, item_id: str):
    container = manager.middleware_data['dishka_container']
    bot = manager.middleware_data['bot']
    ticket_id = int(item_id)
    tickets_repo: TicketsRepository = await container.get(TicketsRepository)
    ticket = tickets_repo.get_ticket(ticket_id)
    await manager.done()
    if not ticket or not ticket.is_active:
        await callback.message.answer(PHRASES_RU.operator.reply_ticket_closed)
        return
    operators_repo: OperatorsRepository = await container.get(OperatorsRepository)
    if not operators_repo.is_operator_of(callback.from_user.id, ticket.project_id):
        await callback.message.answer(PHRASES_RU.operator.foreign_ticket)
        return
    card = PHRASES_RU.replace(
        'operator.ticket_card',
        ticket_id=ticket.ticket_id,
        project=project_link(ticket.project.title, ticket.project.url) if ticket.project else '',
        user=ticket.user.html_mention if ticket.user else ticket.user_id,
        kind=PHRASES_RU.replace(f'ticket_kind.{ticket.kind.value}'),
        status=PHRASES_RU.replace(f'status.{ticket.status.value}'),
    )
    await bot.send_message(callback.from_user.id, card, reply_markup=kb_open_ticket(ticket_id))


operator_tickets_dialog = QuietDialog(
    Window(
        Format('{text}'),
        ScrollingGroup(
            Select(
                Format('{item[0]}'),
                id='ticket_sel',
                item_id_getter=itemgetter(1),
                items='tickets',
                on_click=on_pick_ticket,
            ),
            id='tickets_scroll',
            width=1,
            height=TICKETS_PER_PAGE,
            hide_on_single_page=True,
        ),
        Cancel(Const(PHRASES_RU.button.close_panel)),
        state=OperatorTicketsSG.list,
        getter=panel_getter,
        parse_mode='HTML',
    )
)
