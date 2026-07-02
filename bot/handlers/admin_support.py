from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode

from bot.bot_utils.routers import AdminRouter
from bot.dialogs import MyProjectsSG, ProjectsSG
from db.repositories.operators import OperatorsRepository
from db.repositories.projects import ProjectsRepository
from db.repositories.users import UsersRepository
from phrases import PHRASES_RU
from utils.format_string import project_link

router = AdminRouter()


def _operator_line(operator) -> str:
    name = operator.user.html_mention if operator.user else ''
    return PHRASES_RU.replace('operator.list_line', user_id=operator.user_id, name=name)


@router.command('projects', 'управление проектами (создать/изменить/удалить)')
async def _(message: Message, dialog_manager: DialogManager):
    await dialog_manager.start(ProjectsSG.list, mode=StartMode.RESET_STACK)


@router.command('my_projects', 'мои проекты (зона ответственности)')
async def _(message: Message, dialog_manager: DialogManager):
    await dialog_manager.start(MyProjectsSG.list, mode=StartMode.RESET_STACK)


@router.command(('add_operator', 'addop'), 'назначить оператора', 'user_id', 'slug')
async def _(message: Message, **kwargs):
    container = kwargs['dishka_container']
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer(PHRASES_RU.operator.usage_add)
        return
    raw_uid, slug = parts[1], parts[2]
    if not raw_uid.isdigit():
        await message.answer(PHRASES_RU.error.not_digit_argument)
        return
    user_id = int(raw_uid)
    users_repo: UsersRepository = await container.get(UsersRepository)
    if not users_repo.is_exists(user_id):
        await message.answer(PHRASES_RU.replace('error.user_not_exist', user_id=user_id))
        return
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    project = projects_repo.get_by_slug(slug)
    if not project:
        await message.answer(PHRASES_RU.replace('project.not_found', slug=slug))
        return
    operators_repo: OperatorsRepository = await container.get(OperatorsRepository)
    if operators_repo.add_operator(user_id, project.project_id):
        await message.answer(PHRASES_RU.replace('operator.added', user_id=user_id, title=project.title))
    else:
        await message.answer(PHRASES_RU.operator.already)


@router.command(('remove_operator', 'removeop', 'rmop'), 'снять оператора', 'user_id', 'slug')
async def _(message: Message, **kwargs):
    container = kwargs['dishka_container']
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer(PHRASES_RU.operator.usage_remove)
        return
    raw_uid, slug = parts[1], parts[2]
    if not raw_uid.isdigit():
        await message.answer(PHRASES_RU.error.not_digit_argument)
        return
    user_id = int(raw_uid)
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    project = projects_repo.get_by_slug(slug)
    if not project:
        await message.answer(PHRASES_RU.replace('project.not_found', slug=slug))
        return
    operators_repo: OperatorsRepository = await container.get(OperatorsRepository)
    if operators_repo.remove_operator(user_id, project.project_id):
        await message.answer(PHRASES_RU.replace('operator.removed', user_id=user_id, title=project.title))
    else:
        await message.answer(PHRASES_RU.operator.not_assigned)


@router.command('operators', 'операторы проекта (или всех)', 'slug')
async def _(message: Message, **kwargs):
    container = kwargs['dishka_container']
    projects_repo: ProjectsRepository = await container.get(ProjectsRepository)
    operators_repo: OperatorsRepository = await container.get(OperatorsRepository)
    parts = message.text.split()

    if len(parts) >= 2:
        slug = parts[1]
        project = projects_repo.get_by_slug(slug)
        if not project:
            await message.answer(PHRASES_RU.replace('project.not_found', slug=slug))
            return
        ops = operators_repo.get_operators_for_project(project.project_id)
        if not ops:
            await message.answer(PHRASES_RU.operator.list_empty)
            return
        txt = [PHRASES_RU.replace('operator.list_title', project=project_link(project.title, project.url))]
        txt += [_operator_line(o) for o in ops]
        await message.answer(''.join(txt))
        return

    txt = [PHRASES_RU.operator.list_all_title]
    has_any = False
    for project in projects_repo.get_active_projects():
        ops = operators_repo.get_operators_for_project(project.project_id)
        if not ops:
            continue
        has_any = True
        txt.append(f'<b>{project_link(project.title, project.url)}</b>\n')
        txt += [_operator_line(o) for o in ops]
        txt.append('\n')
    await message.answer(''.join(txt) if has_any else PHRASES_RU.operator.list_empty)
