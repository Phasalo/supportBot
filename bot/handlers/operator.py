from aiogram import Bot, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, StartMode

from bot.bot_utils.filters import NotCommandFilter
from bot.bot_utils.markup import drop_keyboard
from bot.bot_utils.routers import OperatorRouter
from bot.callbacks import OperatorAction, ReplyDoneCallback, TicketCallback
from bot.dialogs import OperatorTicketsSG
from bot.keyboards.inline import kb_reply_session, kb_ticket_actions
from bot.keyboards.reply import kb_contact
from bot.services.relay import relay_operator_message, safe_send_message
from bot.states import OperatorReplySG
from db.models import TicketModel
from db.repositories.operators import OperatorsRepository
from db.repositories.tickets import TicketsRepository
from phrases import PHRASES_RU
from utils.format_string import project_link

router = OperatorRouter()


def _ticket_card(ticket: TicketModel) -> str:
    return PHRASES_RU.replace(
        'operator.ticket_card',
        ticket_id=ticket.ticket_id,
        project=project_link(ticket.project.title, ticket.project.url) if ticket.project else '',
        user=ticket.user.html_mention if ticket.user else ticket.user_id,
        kind=PHRASES_RU.replace(f'ticket_kind.{ticket.kind.value}'),
        status=PHRASES_RU.replace(f'status.{ticket.status.value}'),
    )


async def _has_project_access(callback: CallbackQuery, container, ticket: TicketModel) -> bool:
    operators_repo: OperatorsRepository = await container.get(OperatorsRepository)
    if operators_repo.is_operator_of(callback.from_user.id, ticket.project_id):
        return True
    await callback.answer(PHRASES_RU.operator.foreign_ticket, show_alert=True)
    await drop_keyboard(callback)
    return False


@router.command(('panel', 'tickets'), 'панель открытых обращений')
async def _(message: Message, dialog_manager: DialogManager):
    await dialog_manager.start(OperatorTicketsSG.list, mode=StartMode.RESET_STACK)


@router.command('done', 'выйти из режима ответа')
async def _(message: Message, state: FSMContext):
    if await state.get_state() == OperatorReplySG.in_reply.state:
        await state.clear()
        await message.answer(PHRASES_RU.operator.reply_done)


@router.callback_query(TicketCallback.filter(F.action == OperatorAction.open))
async def _(callback: CallbackQuery, callback_data: TicketCallback, **kwargs):
    container = kwargs['dishka_container']
    ticket_id = callback_data.ticket_id
    tickets_repo: TicketsRepository = await container.get(TicketsRepository)
    ticket = tickets_repo.get_ticket(ticket_id)
    if not ticket or not ticket.is_active:
        await callback.answer(PHRASES_RU.operator.reply_ticket_closed, show_alert=True)
        await drop_keyboard(callback)
        return
    if not await _has_project_access(callback, container, ticket):
        return
    operator_id = callback.from_user.id
    if not tickets_repo.claim_ticket(ticket_id, operator_id):
        ticket = tickets_repo.get_ticket(ticket_id)
        if ticket.assigned_operator_id != operator_id:
            await callback.answer(PHRASES_RU.operator.claim_failed, show_alert=True)
            await drop_keyboard(callback)
            return
    else:
        ticket = tickets_repo.get_ticket(ticket_id)
    await callback.answer(PHRASES_RU.replace('operator.claimed', ticket_id=ticket_id))
    await callback.message.answer(_ticket_card(ticket), reply_markup=kb_ticket_actions(ticket_id))


@router.callback_query(TicketCallback.filter(F.action == OperatorAction.reply))
async def _(callback: CallbackQuery, callback_data: TicketCallback, state: FSMContext, **kwargs):
    container = kwargs['dishka_container']
    ticket_id = callback_data.ticket_id
    tickets_repo: TicketsRepository = await container.get(TicketsRepository)
    ticket = tickets_repo.get_ticket(ticket_id)
    if not ticket or not ticket.is_active:
        await callback.answer(PHRASES_RU.operator.reply_ticket_closed, show_alert=True)
        await drop_keyboard(callback)
        return
    if not await _has_project_access(callback, container, ticket):
        return
    operator_id = callback.from_user.id
    if ticket.assigned_operator_id is None:
        tickets_repo.claim_ticket(ticket_id, operator_id)
        ticket = tickets_repo.get_ticket(ticket_id)
    if ticket.assigned_operator_id != operator_id:
        await callback.answer(PHRASES_RU.operator.claim_failed, show_alert=True)
        await drop_keyboard(callback)
        return
    await state.set_state(OperatorReplySG.in_reply)
    await state.update_data(reply_ticket_id=ticket_id)
    await callback.message.answer(
        PHRASES_RU.replace('operator.reply_prompt', ticket_id=ticket_id),
        reply_markup=kb_reply_session(ticket_id),
    )
    await callback.answer()


@router.callback_query(ReplyDoneCallback.filter())
async def _(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(PHRASES_RU.operator.reply_done)
    await callback.answer()


@router.callback_query(TicketCallback.filter(F.action == OperatorAction.close))
async def _(callback: CallbackQuery, callback_data: TicketCallback, bot: Bot, state: FSMContext, **kwargs):
    container = kwargs['dishka_container']
    ticket_id = callback_data.ticket_id
    tickets_repo: TicketsRepository = await container.get(TicketsRepository)
    ticket = tickets_repo.get_ticket(ticket_id)
    if not ticket or not ticket.is_active:
        await callback.answer(PHRASES_RU.operator.reply_ticket_closed, show_alert=True)
        await drop_keyboard(callback)
        return
    if not await _has_project_access(callback, container, ticket):
        return
    tickets_repo.close_ticket(ticket_id)
    if (await state.get_data()).get('reply_ticket_id') == ticket_id:
        await state.clear()
    await callback.answer(PHRASES_RU.replace('operator.closed', ticket_id=ticket_id))
    await drop_keyboard(callback)
    await callback.message.answer(PHRASES_RU.replace('operator.closed', ticket_id=ticket_id))
    await safe_send_message(bot, ticket.user_id, PHRASES_RU.support.ticket_closed_user, kb_contact())


@router.message(StateFilter(OperatorReplySG.in_reply), NotCommandFilter())
async def _(message: Message, bot: Bot, state: FSMContext, **kwargs):
    container = kwargs['dishka_container']
    operator_id = message.from_user.id
    ticket_id = (await state.get_data()).get('reply_ticket_id')
    if not ticket_id:
        await state.clear()
        return
    tickets_repo: TicketsRepository = await container.get(TicketsRepository)
    ticket = tickets_repo.get_ticket(ticket_id)
    if not ticket or not ticket.is_active:
        await message.answer(PHRASES_RU.operator.reply_ticket_closed)
        await state.clear()
        return
    if not await relay_operator_message(bot, container, ticket, message, operator_id):
        await message.answer(PHRASES_RU.operator.reply_failed)
