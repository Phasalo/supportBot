import re
from operator import itemgetter

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Cancel, Column, Row, ScrollingGroup, Select, SwitchTo
from aiogram_dialog.widgets.text import Const, Format

from config.const import PROJECTS_PER_PAGE, TICKET_HISTORY_PER_PAGE, TICKETS_PER_PAGE
from db.models import TicketStatus
from db.repositories.operators import OperatorsRepository
from db.repositories.projects import ProjectsRepository
from db.repositories.ticket_messages import TicketMessagesRepository
from db.repositories.tickets import TicketsRepository
from phrases import PHRASES_RU
from utils.format_list import format_ticket_history
from utils.format_string import clear_string, project_link

from ._pagination import SCROLL_ID, build_pagination_data, current_page, pagination_row, pagination_scroll

_SLUG_RE = re.compile(r'[A-Za-z0-9_-]+')
_URL_RE = re.compile(r'(https?|tg)://\S+')


def _valid_slug(slug: str) -> bool:
    return bool(_SLUG_RE.fullmatch(slug)) and '__' not in slug


class ProjectsSG(StatesGroup):
    list = State()
    card = State()
    tickets = State()
    ticket_history = State()
    add_slug = State()
    add_title = State()
    edit_title = State()
    edit_slug = State()
    edit_url = State()
    confirm_delete = State()


_STATUS_ICON = {
    TicketStatus.OPEN: '🟢',
    TicketStatus.ASSIGNED: '🟡',
    TicketStatus.CLOSED: '⚪️',
}


class MyProjectsSG(StatesGroup):
    list = State()


# ---------- getters ----------


async def list_getter(dialog_manager: DialogManager, **kwargs):
    container = kwargs['dishka_container']
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    projects = projects_repo.get_all()
    items = [(f'{"🟢" if p.is_active else "🔴"} {p.title}', p.project_id) for p in projects]
    return {
        'projects': items,
        'text': PHRASES_RU.project.list_title if items else PHRASES_RU.project.none,
    }


async def _project_stats(container, project_id: int) -> tuple[int, int]:
    operators_repo: OperatorsRepository = await container.get(OperatorsRepository)
    tickets_repo: TicketsRepository = await container.get(TicketsRepository)
    return len(operators_repo.get_operators_for_project(project_id)), tickets_repo.count_for_project(project_id)


async def card_getter(dialog_manager: DialogManager, **kwargs):
    container = kwargs['dishka_container']
    bot = dialog_manager.middleware_data['bot']
    project_id = dialog_manager.dialog_data.get('project_id')
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    project = projects_repo.get_by_id(project_id)
    if not project:
        return {'text': PHRASES_RU.project.gone, 'toggle_label': '—'}
    me = await bot.me()
    operators, tickets = await _project_stats(container, project_id)
    text = PHRASES_RU.replace(
        'project.card',
        title=project_link(project.title, project.url),
        slug=project.slug,
        deeplink=f'https://t.me/{me.username}?start={project.slug}',
        status=PHRASES_RU.project.active if project.is_active else PHRASES_RU.project.inactive,
        operators=operators,
        tickets=tickets,
    )
    toggle = PHRASES_RU.button.disable_project if project.is_active else PHRASES_RU.button.enable_project
    return {'text': text, 'toggle_label': toggle}


async def confirm_getter(dialog_manager: DialogManager, **kwargs):
    container = kwargs['dishka_container']
    project_id = dialog_manager.dialog_data.get('project_id')
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    project = projects_repo.get_by_id(project_id)
    if not project:
        return {'text': PHRASES_RU.project.gone}
    operators, tickets = await _project_stats(container, project_id)
    return {
        'text': PHRASES_RU.replace(
            'project.confirm_delete', title=clear_string(project.title), operators=operators, tickets=tickets
        )
    }


def _ticket_item_label(ticket) -> str:
    icon = _STATUS_ICON.get(ticket.status, '⚪️')
    name = ticket.user.full_name() if ticket.user else str(ticket.user_id)
    if len(name) > 18:
        name = f'{name[:17]}…'
    date = ticket.created_at.strftime('%d.%m.%y') if ticket.created_at else ''
    return f'{icon} #{ticket.ticket_id} · {name} · {date}'


async def project_tickets_getter(dialog_manager: DialogManager, **kwargs):
    container = kwargs['dishka_container']
    project_id = dialog_manager.dialog_data.get('project_id')
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    tickets_repo: TicketsRepository = await container.get(TicketsRepository)
    project = projects_repo.get_by_id(project_id)
    if not project:
        return {'tickets': [], 'text': PHRASES_RU.project.gone, 'multipage': False}
    if dialog_manager.dialog_data.get('tickets_for') != project_id:
        dialog_manager.dialog_data['tickets_for'] = project_id
        dialog_manager.dialog_data['tickets_page'] = 1
    page = dialog_manager.dialog_data.get('tickets_page', 1)
    tickets, pagination = tickets_repo.get_tickets_for_project(project_id, page, TICKETS_PER_PAGE)
    if page > pagination.total_pages >= 1:
        page = pagination.total_pages
        dialog_manager.dialog_data['tickets_page'] = page
        tickets, pagination = tickets_repo.get_tickets_for_project(project_id, page, TICKETS_PER_PAGE)
    dialog_manager.dialog_data['tickets_total_pages'] = pagination.total_pages
    if not tickets:
        return {'tickets': [], 'text': PHRASES_RU.ticket.list_empty, 'multipage': False}
    items = [(_ticket_item_label(t), t.ticket_id) for t in tickets]
    total = PHRASES_RU.replace('ticket.list_total', total=pagination.total_items)
    text = f'{PHRASES_RU.ticket.list_title} · {project_link(project.title, project.url)}\n<i>{total}</i>'
    return {
        'tickets': items,
        'text': text,
        'page': page,
        'pages_count': pagination.total_pages,
        'multipage': pagination.total_pages > 1,
        'not_first': pagination.has_prev,
        'not_last': pagination.has_next,
    }


async def ticket_history_getter(dialog_manager: DialogManager, **kwargs):
    container = kwargs['dishka_container']
    ticket_id = dialog_manager.dialog_data.get('ticket_id')
    tickets_repo: TicketsRepository = await container.get(TicketsRepository)
    messages_repo: TicketMessagesRepository = await container.get(TicketMessagesRepository)
    ticket = tickets_repo.get_ticket(ticket_id)
    if not ticket:
        return {'text': PHRASES_RU.ticket.gone, **build_pagination_data(dialog_manager, 1, False, False)}
    if dialog_manager.dialog_data.get('history_for') != ticket_id:
        dialog_manager.dialog_data['history_for'] = ticket_id
        if scroll := dialog_manager.find(SCROLL_ID):
            await scroll.set_page(0)
    page = await current_page(dialog_manager)
    messages, pagination = messages_repo.get_ticket_messages(ticket_id, page, TICKET_HISTORY_PER_PAGE)
    return {
        'text': format_ticket_history(ticket, messages),
        **build_pagination_data(dialog_manager, pagination.total_pages, pagination.has_prev, pagination.has_next),
    }


# ---------- handlers ----------


async def on_pick_history_ticket(callback: CallbackQuery, _widget, manager: DialogManager, item_id: str):
    manager.dialog_data['ticket_id'] = int(item_id)
    await manager.switch_to(ProjectsSG.ticket_history)


async def _noop(callback: CallbackQuery, _button, _manager: DialogManager):
    pass


async def on_tickets_first(callback: CallbackQuery, _button, manager: DialogManager):
    manager.dialog_data['tickets_page'] = 1


async def on_tickets_prev(callback: CallbackQuery, _button, manager: DialogManager):
    manager.dialog_data['tickets_page'] = max(1, manager.dialog_data.get('tickets_page', 1) - 1)


async def on_tickets_next(callback: CallbackQuery, _button, manager: DialogManager):
    total = manager.dialog_data.get('tickets_total_pages', 1)
    manager.dialog_data['tickets_page'] = min(total, manager.dialog_data.get('tickets_page', 1) + 1)


async def on_tickets_last(callback: CallbackQuery, _button, manager: DialogManager):
    manager.dialog_data['tickets_page'] = manager.dialog_data.get('tickets_total_pages', 1)


async def on_pick(callback: CallbackQuery, _widget, manager: DialogManager, item_id: str):
    manager.dialog_data['project_id'] = int(item_id)
    await manager.switch_to(ProjectsSG.card)


async def on_toggle(callback: CallbackQuery, _button, manager: DialogManager):
    container = manager.middleware_data['dishka_container']
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    project = projects_repo.get_by_id(manager.dialog_data.get('project_id'))
    if not project:
        await manager.switch_to(ProjectsSG.list)
        return
    new_state = not project.is_active
    projects_repo.set_active(project.slug, new_state)
    await callback.answer(PHRASES_RU.project.enabled if new_state else PHRASES_RU.project.disabled)


async def on_add_slug(message: Message, _input: MessageInput, manager: DialogManager):
    slug = (message.text or '').strip()
    if not _valid_slug(slug):
        await message.answer(PHRASES_RU.project.bad_slug)
        return
    container = manager.middleware_data['dishka_container']
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    if projects_repo.get_by_slug(slug):
        await message.answer(PHRASES_RU.project.exists)
        return
    manager.dialog_data['new_slug'] = slug
    await manager.switch_to(ProjectsSG.add_title)


async def on_add_title(message: Message, _input: MessageInput, manager: DialogManager):
    title = (message.text or '').strip()
    if not title:
        await message.answer(PHRASES_RU.project.empty_title)
        return
    container = manager.middleware_data['dishka_container']
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    project = projects_repo.add_project(manager.dialog_data['new_slug'], title)
    if not project:
        await message.answer(PHRASES_RU.project.exists)
        await manager.switch_to(ProjectsSG.list)
        return
    await message.answer(PHRASES_RU.replace('project.added', title=clear_string(title)))
    manager.dialog_data['project_id'] = project.project_id
    await manager.switch_to(ProjectsSG.card)


async def on_edit_title(message: Message, _input: MessageInput, manager: DialogManager):
    title = (message.text or '').strip()
    if not title:
        await message.answer(PHRASES_RU.project.empty_title)
        return
    container = manager.middleware_data['dishka_container']
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    projects_repo.set_title(manager.dialog_data['project_id'], title)
    await message.answer(PHRASES_RU.project.renamed)
    await manager.switch_to(ProjectsSG.card)


async def on_edit_slug(message: Message, _input: MessageInput, manager: DialogManager):
    slug = (message.text or '').strip()
    if not _valid_slug(slug):
        await message.answer(PHRASES_RU.project.bad_slug)
        return
    container = manager.middleware_data['dishka_container']
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    project_id = manager.dialog_data['project_id']
    existing = projects_repo.get_by_slug(slug)
    if existing and existing.project_id != project_id:
        await message.answer(PHRASES_RU.project.exists)
        return
    projects_repo.set_slug(project_id, slug)
    await message.answer(PHRASES_RU.project.reslugged)
    await manager.switch_to(ProjectsSG.card)


async def on_edit_url(message: Message, _input: MessageInput, manager: DialogManager):
    raw = (message.text or '').strip()
    container = manager.middleware_data['dishka_container']
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    project_id = manager.dialog_data['project_id']
    if raw == '-':
        projects_repo.set_url(project_id, None)
        await message.answer(PHRASES_RU.project.url_cleared)
        await manager.switch_to(ProjectsSG.card)
        return
    if not _URL_RE.fullmatch(raw):
        await message.answer(PHRASES_RU.project.bad_url)
        return
    projects_repo.set_url(project_id, raw)
    await message.answer(PHRASES_RU.project.url_updated)
    await manager.switch_to(ProjectsSG.card)


async def on_delete(callback: CallbackQuery, _button, manager: DialogManager):
    container = manager.middleware_data['dishka_container']
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    project = projects_repo.get_by_id(manager.dialog_data.get('project_id'))
    title = clear_string(project.title) if project else ''
    if project:
        projects_repo.delete_project(project.project_id)
    await callback.answer(PHRASES_RU.replace('project.deleted', title=title), show_alert=True)
    await manager.switch_to(ProjectsSG.list)


# ---------- my projects (self-assign toggle) ----------


async def my_projects_getter(dialog_manager: DialogManager, **kwargs):
    container = kwargs['dishka_container']
    user_id = dialog_manager.middleware_data['event_from_user'].id
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    operators_repo: OperatorsRepository = await container.get(OperatorsRepository)
    projects = projects_repo.get_active_projects()
    mine = set(operators_repo.get_project_ids_for_user(user_id))
    items = [(f'{"✅" if p.project_id in mine else "⬜️"} {p.title}', p.project_id) for p in projects]
    return {
        'projects': items,
        'text': PHRASES_RU.operator.my_projects_title if items else PHRASES_RU.operator.my_projects_empty,
    }


async def on_toggle_project(callback: CallbackQuery, _widget, manager: DialogManager, item_id: str):
    container = manager.middleware_data['dishka_container']
    operators_repo: OperatorsRepository = await container.get(OperatorsRepository)
    user_id = callback.from_user.id
    project_id = int(item_id)
    if operators_repo.is_operator_of(user_id, project_id):
        operators_repo.remove_operator(user_id, project_id)
    else:
        operators_repo.add_operator(user_id, project_id)


# ---------- dialogs ----------

projects_dialog = Dialog(
    Window(
        Format('{text}'),
        ScrollingGroup(
            Select(
                Format('{item[0]}'),
                id='proj_sel',
                item_id_getter=itemgetter(1),
                items='projects',
                on_click=on_pick,
            ),
            id='proj_scroll',
            width=1,
            height=PROJECTS_PER_PAGE,
            hide_on_single_page=True,
        ),
        SwitchTo(Const(PHRASES_RU.button.add_project), id='add', state=ProjectsSG.add_slug),
        Cancel(Const(PHRASES_RU.button.close_panel)),
        state=ProjectsSG.list,
        getter=list_getter,
        parse_mode='HTML',
        disable_web_page_preview=True,
    ),
    Window(
        Format('{text}'),
        SwitchTo(Const(PHRASES_RU.button.tickets), id='tickets', state=ProjectsSG.tickets),
        Button(Format('{toggle_label}'), id='toggle', on_click=on_toggle),
        Row(
            SwitchTo(Const(PHRASES_RU.button.edit_title), id='edit_title', state=ProjectsSG.edit_title),
            SwitchTo(Const(PHRASES_RU.button.edit_slug), id='edit_slug', state=ProjectsSG.edit_slug),
        ),
        SwitchTo(Const(PHRASES_RU.button.edit_url), id='edit_url', state=ProjectsSG.edit_url),
        SwitchTo(Const(PHRASES_RU.button.delete_project), id='del', state=ProjectsSG.confirm_delete),
        SwitchTo(Const(PHRASES_RU.button.back_to_list), id='back', state=ProjectsSG.list),
        state=ProjectsSG.card,
        getter=card_getter,
        parse_mode='HTML',
        disable_web_page_preview=True,
    ),
    Window(
        Format('{text}'),
        Column(
            Select(
                Format('{item[0]}'),
                id='hist_ticket_sel',
                item_id_getter=itemgetter(1),
                items='tickets',
                on_click=on_pick_history_ticket,
            ),
        ),
        Row(
            Button(
                Format(f'{PHRASES_RU.button.first_page} 1'), id='t_first', on_click=on_tickets_first, when='not_first'
            ),
            Button(Const(PHRASES_RU.button.prev_page), id='t_prev', on_click=on_tickets_prev, when='not_first'),
            Button(Format('{page} / {pages_count}'), id='t_page', on_click=_noop),
            Button(Const(PHRASES_RU.button.next_page), id='t_next', on_click=on_tickets_next, when='not_last'),
            Button(
                Format('{pages_count} ' + PHRASES_RU.button.last_page),
                id='t_last',
                on_click=on_tickets_last,
                when='not_last',
            ),
            when='multipage',
        ),
        SwitchTo(Const(PHRASES_RU.button.back_to_card), id='tickets_back', state=ProjectsSG.card),
        state=ProjectsSG.tickets,
        getter=project_tickets_getter,
        parse_mode='HTML',
        disable_web_page_preview=True,
    ),
    Window(
        Format('{text}'),
        pagination_scroll(),
        pagination_row(),
        SwitchTo(Const(PHRASES_RU.button.back_to_tickets), id='history_back', state=ProjectsSG.tickets),
        state=ProjectsSG.ticket_history,
        getter=ticket_history_getter,
        parse_mode='HTML',
        disable_web_page_preview=True,
    ),
    Window(
        Const(PHRASES_RU.project.add_slug_prompt),
        MessageInput(on_add_slug),
        SwitchTo(Const(PHRASES_RU.button.back_to_list), id='cancel_add', state=ProjectsSG.list),
        state=ProjectsSG.add_slug,
        parse_mode='HTML',
    ),
    Window(
        Const(PHRASES_RU.project.add_title_prompt),
        MessageInput(on_add_title),
        SwitchTo(Const(PHRASES_RU.button.cancel), id='cancel_add_t', state=ProjectsSG.list),
        state=ProjectsSG.add_title,
        parse_mode='HTML',
    ),
    Window(
        Const(PHRASES_RU.project.edit_title_prompt),
        MessageInput(on_edit_title),
        SwitchTo(Const(PHRASES_RU.button.cancel), id='cancel_et', state=ProjectsSG.card),
        state=ProjectsSG.edit_title,
        parse_mode='HTML',
    ),
    Window(
        Const(PHRASES_RU.project.edit_slug_prompt),
        MessageInput(on_edit_slug),
        SwitchTo(Const(PHRASES_RU.button.cancel), id='cancel_es', state=ProjectsSG.card),
        state=ProjectsSG.edit_slug,
        parse_mode='HTML',
    ),
    Window(
        Const(PHRASES_RU.project.edit_url_prompt),
        MessageInput(on_edit_url),
        SwitchTo(Const(PHRASES_RU.button.cancel), id='cancel_eu', state=ProjectsSG.card),
        state=ProjectsSG.edit_url,
        parse_mode='HTML',
    ),
    Window(
        Format('{text}'),
        Row(
            Button(Const(PHRASES_RU.button.confirm_delete), id='confirm_del', on_click=on_delete),
            SwitchTo(Const(PHRASES_RU.button.cancel), id='cancel_del', state=ProjectsSG.card),
        ),
        state=ProjectsSG.confirm_delete,
        getter=confirm_getter,
        parse_mode='HTML',
    ),
)

my_projects_dialog = Dialog(
    Window(
        Format('{text}'),
        ScrollingGroup(
            Select(
                Format('{item[0]}'),
                id='my_proj_toggle',
                item_id_getter=itemgetter(1),
                items='projects',
                on_click=on_toggle_project,
            ),
            id='my_proj_scroll',
            width=1,
            height=PROJECTS_PER_PAGE,
            hide_on_single_page=True,
        ),
        Cancel(Const(PHRASES_RU.button.close_panel)),
        state=MyProjectsSG.list,
        getter=my_projects_getter,
        parse_mode='HTML',
    ),
)
