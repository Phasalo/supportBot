from db.models import Pagination, QueryModel, TicketMessageModel, TicketModel, UserModel
from phrases import PHRASES_RU
from utils import format_string
from utils.format_string import clear_string, project_link


def format_user_list(users_info: list[UserModel], pagination: Pagination) -> str:
    txt = [PHRASES_RU.title.users, PHRASES_RU.replace('footnote.total', total=pagination.total_items)]

    for user in users_info:
        line_data = {
            'username': user.display_name() or PHRASES_RU.icon.not_username,
            'user_id': str(user.user_id).ljust(12),
            'query_stat': f'{format_string.get_query_count_emoji(user.query_count)} {user.query_count}',
            'registration_date': user.registration_date.strftime('%d.%m.%Y'),
        }

        user_line = PHRASES_RU.replace('template.user', **line_data)

        if user.is_banned:
            txt.append(f'<s>{user_line}</s>')
        elif user.is_admin:
            txt.append(f'<b>{user_line}</b>')
        else:
            txt.append(user_line)

    if pagination.total_pages > 1:
        txt.append(PHRASES_RU.icon.row_placeholder * (pagination.per_page - len(users_info)))

    return ''.join(txt)


def format_queries_text(
    queries: list[QueryModel],
    name: str | None = None,
    user_id: int | None = None,
    footnote_template: str = PHRASES_RU.footnote.user_query,
    line_template: str = PHRASES_RU.template.user_query,
) -> str:
    """
    Форматирует список запросов в текстовое сообщение.

    Args:
        queries: Список объектов QueryModel
        name: Юзернейм или имя пользователя (если есть)
        user_id: ID пользователя (если предыдущий аргумент None)
        footnote_template: Шаблон заголовка с {username} placeholder
        line_template: Шаблон строки запроса с {time} и {query} placeholders

    Returns:
        Отформатированная строка с историей запросов
    """
    username_display = name or user_id or PHRASES_RU.error.unknown
    txt = [PHRASES_RU.title.query, footnote_template.format(username=username_display, user_id=user_id)]

    for query in queries:
        line_data = {
            'user_id': query.user.user_id,
            'time': query.query_date.strftime('%d.%m.%Y %H:%M:%S') if query.query_date else PHRASES_RU.error.unknown,
            'query': query.query_text,
            'username': query.user.display_name() if query.user else '',
        }
        txt.append(line_template.format(**line_data))

    return ''.join(txt)


def _role_label(role: str) -> str:
    try:
        return PHRASES_RU.replace(f'role.{role}')
    except AttributeError:
        return role


def _content_kind(content_type: str) -> str:
    try:
        return PHRASES_RU.replace(f'content_kind.{content_type}')
    except AttributeError:
        return PHRASES_RU.content_kind.unknown


def _message_body(msg: TicketMessageModel) -> str:
    content_type = msg.content_type.rsplit('.', 1)[-1].lower()
    if content_type == 'text':
        return clear_string(msg.text) if msg.text else PHRASES_RU.icon.not_text
    kind = _content_kind(content_type)
    if msg.text:
        return f'{kind}\n{clear_string(msg.text)}'
    return kind


def format_ticket_history(ticket: TicketModel, messages: list[TicketMessageModel]) -> str:
    status = PHRASES_RU.replace(f'status.{ticket.status.value}')
    kind = PHRASES_RU.replace(f'ticket_kind.{ticket.kind.value}')
    user_name = ticket.user.html_mention if ticket.user else str(ticket.user_id)
    created = ticket.created_at.strftime('%d.%m.%Y %H:%M') if ticket.created_at else PHRASES_RU.error.unknown

    header = [f'<b>{PHRASES_RU.ticket.label_ticket} #{ticket.ticket_id}</b> · {kind} · {status}']
    if ticket.project:
        header.append(f'{PHRASES_RU.ticket.header_project} {project_link(ticket.project.title, ticket.project.url)}')
    header.append(f'{PHRASES_RU.ticket.header_user} {user_name}')
    header.append(f'{PHRASES_RU.ticket.header_created} {created}')
    if ticket.closed_at:
        header.append(f'{PHRASES_RU.ticket.header_closed} {ticket.closed_at.strftime("%d.%m.%Y %H:%M")}')

    text = '\n'.join(header)
    if not messages:
        return text + PHRASES_RU.ticket.history_empty

    lines = [text, '\n\n']
    for msg in messages:
        time = msg.created_at.strftime('%d.%m %H:%M') if msg.created_at else ''
        lines.append(f'{_role_label(msg.sender_role)} · <i>{time}</i>\n<blockquote>{_message_body(msg)}</blockquote>\n')
    return ''.join(lines)
