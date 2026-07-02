from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.bot_utils.markup import drop_keyboard
from bot.bot_utils.routers import BaseRouter, UserRouter
from bot.callbacks import PickerCancelCallback, ProjectPickCallback, TicketKindPickCallback
from bot.filters.password import PasswordFilter
from bot.handlers.admin import command_getcmds
from bot.keyboards.inline import kb_kind_picker, kb_project_picker
from bot.keyboards.reply import kb_compose_cancel, kb_contact, kb_in_ticket
from bot.metrics import tickets_created
from bot.services.relay import extract_content, notify_new_suggestion, notify_new_ticket, relay_user_message
from bot.states import SupportSG
from db.models import ProjectModel, TicketKind, TicketMessageModel, UserModel
from db.repositories.projects import ProjectsRepository
from db.repositories.ticket_messages import TicketMessagesRepository
from db.repositories.tickets import TicketsRepository
from db.repositories.users import UsersRepository
from phrases import PHRASES_RU
from utils.format_string import project_link

router = UserRouter()


async def _show_idle(message: Message, state: FSMContext, text: str | None = None) -> None:
    await state.clear()
    await message.answer(text or PHRASES_RU.support.idle, reply_markup=kb_contact())


async def _show_picker(message: Message, container, state: FSMContext) -> None:
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    projects = projects_repo.get_active_projects()
    if not projects:
        await message.answer(PHRASES_RU.support.no_projects)
        return
    await state.set_state(SupportSG.choosing_project)
    await message.answer(PHRASES_RU.support.choose_project, reply_markup=kb_project_picker(projects))


async def _show_kind_picker(message: Message, project: ProjectModel, state: FSMContext) -> None:
    """Показывает пикер типа обращения. Тикет ещё не создаётся — родится в composing.

    Активный тикет НЕ проверяем: предложение (fire-and-forget) допустимо параллельно с открытым
    диалогом; для bug/question блокировка на дубли — в handler'е выбора kind.
    """
    await state.set_state(SupportSG.choosing_kind)
    await state.update_data(project_id=project.project_id, project_slug=project.slug)
    await message.answer(
        PHRASES_RU.replace('support.choose_kind', project=project_link(project.title, project.url)),
        reply_markup=kb_kind_picker(project.slug),
    )


@router.message(CommandStart(deep_link=True))
async def _(message: Message, command: CommandObject, state: FSMContext, **kwargs):
    container = kwargs['dishka_container']
    payload = command.args or ''
    slug, _, _extra = payload.partition('__')
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    project = projects_repo.get_by_slug(slug)
    if not project or not project.is_active:
        await _show_idle(message, state, PHRASES_RU.support.unknown_project)
        return
    await _show_kind_picker(message, project, state)


@router.command('start', 'обратиться в поддержку')
async def _(message: Message, state: FSMContext, **kwargs):
    await _show_idle(message, state, PHRASES_RU.commands.start)


@router.message(F.text == PHRASES_RU.button.user_contact)
async def _(message: Message, state: FSMContext, **kwargs):
    await _show_picker(message, kwargs['dishka_container'], state)


@router.callback_query(ProjectPickCallback.filter())
async def _(callback: CallbackQuery, callback_data: ProjectPickCallback, state: FSMContext, **kwargs):
    container = kwargs['dishka_container']
    slug = callback_data.slug
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    project = projects_repo.get_by_slug(slug)
    if not project or not project.is_active:
        await callback.answer(PHRASES_RU.support.unknown_project, show_alert=True)
        await drop_keyboard(callback)
        await state.clear()
        return
    await drop_keyboard(callback)
    await _show_kind_picker(callback.message, project, state)
    await callback.answer()


_PICKER_STATES = {SupportSG.choosing_project.state, SupportSG.choosing_kind.state}


@router.callback_query(PickerCancelCallback.filter())
async def _(callback: CallbackQuery, state: FSMContext, **kwargs):
    await drop_keyboard(callback)
    # Только если реально стоим на пикере — иначе клик по stale-кнопке из истории
    # молча снимает клавиатуру, без лишнего idle-сообщения.
    if (await state.get_state()) in _PICKER_STATES:
        await state.clear()
        await callback.message.answer(PHRASES_RU.support.contact_cancelled, reply_markup=kb_contact())
    await callback.answer()


@router.callback_query(TicketKindPickCallback.filter())
async def _(callback: CallbackQuery, callback_data: TicketKindPickCallback, state: FSMContext, **kwargs):
    container = kwargs['dishka_container']
    user_row: UserModel = kwargs['user_row']
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    project = projects_repo.get_by_slug(callback_data.slug)
    if not project or not project.is_active:
        await callback.answer(PHRASES_RU.support.unknown_project, show_alert=True)
        await drop_keyboard(callback)
        await state.clear()
        return
    try:
        kind = TicketKind(callback_data.kind)
    except ValueError:
        await callback.answer(PHRASES_RU.support.unknown_kind, show_alert=True)
        await drop_keyboard(callback)
        await state.clear()
        return

    # Активный тикет запрещает только новый диалог (bug/question). Предложения — fire-and-forget,
    # закрываются в момент создания и не конкурируют за внимание оператора.
    if kind is not TicketKind.FEATURE:
        tickets_repo: TicketsRepository = await container.get(TicketsRepository)
        existing = tickets_repo.get_active_ticket_for_user(user_row.user_id)
        if existing is not None:
            title = (
                project_link(existing.project.title, existing.project.url)
                if existing.project
                else project_link(project.title, project.url)
            )
            await drop_keyboard(callback)
            await state.clear()
            await callback.message.answer(
                PHRASES_RU.replace('support.ticket_already_open', project=title),
                reply_markup=kb_in_ticket(),
            )
            await callback.answer()
            return

    await drop_keyboard(callback)
    await state.set_state(SupportSG.composing)
    await state.update_data(project_id=project.project_id, project_slug=project.slug, kind=kind.value)
    prompt_key = 'support.compose_suggestion_prompt' if kind is TicketKind.FEATURE else 'support.compose_prompt'
    await callback.message.answer(
        PHRASES_RU.replace(prompt_key, project=project_link(project.title, project.url)),
        reply_markup=kb_compose_cancel(),
    )
    await callback.answer()


@router.command('help', 'как пользоваться ботом')  # /help
async def _(message: Message):
    await message.answer(PHRASES_RU.commands.help)


@router.command('about', 'о разработчиках')  # /about
async def _(message: Message):
    await message.answer_photo(
        caption=PHRASES_RU.commands.about,
        photo='https://yan-toples.ru/Phasalo/color-black-phasalo-project-margin.png',
        disable_web_page_preview=True,
    )


@router.command(('commands', 'cmds'), 'список всех команд (это сообщение)')  # /commands /cmds
async def _(message: Message):
    commands_text = '\n'.join(
        str(command) for command in BaseRouter.available_commands if not command.is_admin and not command.is_operator
    )
    await message.answer(PHRASES_RU.title.commands + commands_text)


def register_password_handler(target: Router, password: str) -> None:
    @target.message(PasswordFilter(password))
    async def _(message: Message, **data):
        users_repo: UsersRepository = await data['dishka_container'].get(UsersRepository)
        if users_repo.set_admin(message.from_user.id, message.from_user.id):
            await message.delete()
            await message.answer(PHRASES_RU.success.promoted)
            await command_getcmds(message)
        else:
            await message.answer(PHRASES_RU.error.db)


@router.message(StateFilter(SupportSG.composing), F.text == PHRASES_RU.button.user_cancel)
async def _(message: Message, state: FSMContext, **kwargs):
    await _show_idle(message, state, PHRASES_RU.support.contact_cancelled)


@router.message(StateFilter(SupportSG.composing))
async def _(message: Message, bot: Bot, state: FSMContext, **kwargs):
    container = kwargs['dishka_container']
    user_row: UserModel = kwargs['user_row']
    data = await state.get_data()
    project_id = data.get('project_id')
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    project = projects_repo.get_by_id(project_id) if project_id else None
    if project is None or not project.is_active:
        await _show_idle(message, state, PHRASES_RU.support.unknown_project)
        return
    try:
        kind = TicketKind(data.get('kind', TicketKind.QUESTION.value))
    except ValueError:
        kind = TicketKind.QUESTION
    tickets_repo: TicketsRepository = await container.get(TicketsRepository)
    ticket, created = tickets_repo.get_or_create_active(user_row.user_id, project.project_id, kind)
    await state.clear()
    project_title = project_link(project.title, project.url)

    if kind is TicketKind.FEATURE:
        messages_repo: TicketMessagesRepository = await container.get(TicketMessagesRepository)
        content_type, text, file_id = extract_content(message)
        messages_repo.add_message(
            TicketMessageModel(
                ticket_id=ticket.ticket_id,
                sender_role='user',
                sender_id=user_row.user_id,
                content_type=content_type,
                text=text,
                file_id=file_id,
                tg_message_id=message.message_id,
            )
        )
        await message.answer(
            PHRASES_RU.replace('support.suggestion_sent', project=project_title),
            reply_markup=kb_contact(),
        )
        if created:
            tickets_created.labels(project=project.slug, kind=kind.value).inc()
        await notify_new_suggestion(bot, container, ticket, message)
        return

    await message.answer(
        PHRASES_RU.replace('support.ticket_created', project=project_title),
        reply_markup=kb_in_ticket(),
    )
    if created:
        tickets_created.labels(project=project.slug, kind=kind.value).inc()
        await notify_new_ticket(bot, container, ticket)
    await relay_user_message(bot, container, ticket, message, skip_header=created)


@router.message()
async def _(message: Message, state: FSMContext, **kwargs):
    await _show_idle(message, state)
