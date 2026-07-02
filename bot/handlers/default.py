from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.bot_utils.markup import drop_keyboard
from bot.bot_utils.routers import BaseRouter, UserRouter
from bot.callbacks import ProjectPickCallback
from bot.filters.password import PasswordFilter
from bot.handlers.admin import command_getcmds
from bot.keyboards.inline import kb_project_picker
from bot.keyboards.reply import kb_compose_cancel, kb_contact, kb_in_ticket
from bot.services.relay import notify_new_ticket, relay_user_message
from bot.states import SupportSG
from db.models import ProjectModel, UserModel
from db.repositories.projects import ProjectsRepository
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


async def _start_contact(
    message: Message, container, user_row: UserModel, project: ProjectModel, state: FSMContext
) -> None:
    """Не создаёт тикет, а переводит в режим написания: тикет родится на первом сообщении.

    Так мисклик по deep-link/пикеру ничего не создаёт — пользователь просто не пишет и выходит.
    """
    tickets_repo: TicketsRepository = await container.get(TicketsRepository)
    existing = tickets_repo.get_active_ticket_for_user(user_row.user_id)
    if existing is not None:
        title = (
            project_link(existing.project.title, existing.project.url)
            if existing.project
            else project_link(project.title, project.url)
        )
        await state.clear()
        await message.answer(
            PHRASES_RU.replace('support.ticket_already_open', project=title),
            reply_markup=kb_in_ticket(),
        )
        return
    await state.set_state(SupportSG.composing)
    await state.update_data(project_id=project.project_id)
    await message.answer(
        PHRASES_RU.replace('support.compose_prompt', project=project_link(project.title, project.url)),
        reply_markup=kb_compose_cancel(),
    )


@router.message(CommandStart(deep_link=True))
async def _(message: Message, command: CommandObject, state: FSMContext, **kwargs):
    container = kwargs['dishka_container']
    user_row: UserModel = kwargs['user_row']
    payload = command.args or ''
    slug, _, _extra = payload.partition('__')
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    project = projects_repo.get_by_slug(slug)
    if not project or not project.is_active:
        await _show_idle(message, state, PHRASES_RU.support.unknown_project)
        return
    await _start_contact(message, container, user_row, project, state)


@router.command('start', 'обратиться в поддержку')
async def _(message: Message, state: FSMContext, **kwargs):
    await _show_idle(message, state, PHRASES_RU.commands.start)


@router.message(F.text == PHRASES_RU.button.user_contact)
async def _(message: Message, state: FSMContext, **kwargs):
    await _show_picker(message, kwargs['dishka_container'], state)


@router.callback_query(ProjectPickCallback.filter())
async def _(callback: CallbackQuery, callback_data: ProjectPickCallback, state: FSMContext, **kwargs):
    container = kwargs['dishka_container']
    user_row: UserModel = kwargs['user_row']
    slug = callback_data.slug
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    project = projects_repo.get_by_slug(slug)
    if not project or not project.is_active:
        await callback.answer(PHRASES_RU.support.unknown_project, show_alert=True)
        await drop_keyboard(callback)
        return
    await drop_keyboard(callback)
    await _start_contact(callback.message, container, user_row, project, state)
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
    tickets_repo: TicketsRepository = await container.get(TicketsRepository)
    ticket, created = tickets_repo.get_or_create_active(user_row.user_id, project.project_id)
    await state.clear()
    await message.answer(
        PHRASES_RU.replace('support.ticket_created', project=project_link(project.title, project.url)),
        reply_markup=kb_in_ticket(),
    )
    if created:
        await notify_new_ticket(bot, container, ticket)
    await relay_user_message(bot, container, ticket, message, skip_header=created)


@router.message()
async def _(message: Message, state: FSMContext, **kwargs):
    await _show_idle(message, state)
