import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup, Message, ReplyKeyboardMarkup

from bot.keyboards.inline import kb_open_ticket, kb_ticket_actions
from db.models import TicketMessageModel, TicketModel
from db.repositories.operators import OperatorsRepository
from db.repositories.ticket_messages import TicketMessagesRepository
from db.repositories.users import UsersRepository
from phrases import PHRASES_RU
from utils.format_string import project_link

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3


async def safe_send_message(
    bot: Bot, chat_id: int, text: str, reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | None = None
) -> bool:
    for _ in range(_MAX_RETRIES):
        try:
            await bot.send_message(chat_id, text, reply_markup=reply_markup)
            return True
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except TelegramForbiddenError:
            logger.warning('send_message to %s failed: bot blocked / not started', chat_id)
            return False
        except TelegramBadRequest as e:
            logger.warning('send_message to %s failed: %s', chat_id, e)
            return False
    return False


async def safe_copy_message(
    bot: Bot, chat_id: int, from_chat_id: int, message_id: int, reply_markup: InlineKeyboardMarkup | None = None
) -> bool:
    for _ in range(_MAX_RETRIES):
        try:
            await bot.copy_message(
                chat_id=chat_id, from_chat_id=from_chat_id, message_id=message_id, reply_markup=reply_markup
            )
            return True
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except TelegramForbiddenError:
            logger.warning('copy_message to %s failed: bot blocked / not started', chat_id)
            return False
        except TelegramBadRequest as e:
            logger.warning('copy_message to %s failed: %s', chat_id, e)
            return False
    return False


def extract_content(message: Message) -> tuple[str, str | None, str | None]:
    text = message.text or message.caption
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id
    elif message.video:
        file_id = message.video.file_id
    elif message.animation:
        file_id = message.animation.file_id
    elif message.voice:
        file_id = message.voice.file_id
    elif message.audio:
        file_id = message.audio.file_id
    elif message.video_note:
        file_id = message.video_note.file_id
    elif message.sticker:
        file_id = message.sticker.file_id
    return message.content_type.value, text, file_id


async def _project_recipients(container, project_id: int) -> tuple[list[int], bool]:
    """Returns (recipient_ids, is_admin_fallback)."""
    operators_repo: OperatorsRepository = await container.get(OperatorsRepository)
    ops = operators_repo.get_operators_for_project(project_id)
    if ops:
        return [o.user_id for o in ops], False
    users_repo: UsersRepository = await container.get(UsersRepository)
    return [a.user_id for a in users_repo.get_admins()], True


async def notify_new_ticket(bot: Bot, container, ticket: TicketModel) -> None:
    recipients, is_fallback = await _project_recipients(container, ticket.project_id)
    project_title = project_link(ticket.project.title, ticket.project.url) if ticket.project else ''
    kind_label = PHRASES_RU.replace(f'ticket_kind.{ticket.kind.value}')
    if is_fallback:
        text = PHRASES_RU.replace(
            'operator.fallback_admin', ticket_id=ticket.ticket_id, project=project_title, kind=kind_label
        )
        for chat_id in recipients:
            await safe_send_message(bot, chat_id, text)
        return
    user_name = ticket.user.html_mention if ticket.user else str(ticket.user_id)
    text = PHRASES_RU.replace(
        'operator.new_ticket',
        ticket_id=ticket.ticket_id,
        project=project_title,
        user=user_name,
        kind=kind_label,
    )
    markup = kb_open_ticket(ticket.ticket_id)
    for chat_id in recipients:
        await safe_send_message(bot, chat_id, text, markup)


async def notify_new_suggestion(bot: Bot, container, ticket: TicketModel, message: Message) -> None:
    recipients, is_fallback = await _project_recipients(container, ticket.project_id)
    project_title = project_link(ticket.project.title, ticket.project.url) if ticket.project else ''
    if is_fallback:
        text = PHRASES_RU.replace(
            'operator.fallback_admin_suggestion', ticket_id=ticket.ticket_id, project=project_title
        )
    else:
        user_name = ticket.user.html_mention if ticket.user else str(ticket.user_id)
        text = PHRASES_RU.replace(
            'operator.new_suggestion', ticket_id=ticket.ticket_id, project=project_title, user=user_name
        )
    for chat_id in recipients:
        await safe_send_message(bot, chat_id, text)
        await safe_copy_message(bot, chat_id, message.chat.id, message.message_id)


async def notify_user_closed(bot: Bot, container, ticket: TicketModel) -> None:
    if ticket.assigned_operator_id:
        recipients = [ticket.assigned_operator_id]
    else:
        operators_repo: OperatorsRepository = await container.get(OperatorsRepository)
        recipients = [o.user_id for o in operators_repo.get_operators_for_project(ticket.project_id)]
    project_title = project_link(ticket.project.title, ticket.project.url) if ticket.project else ''
    text = PHRASES_RU.replace('operator.closed_by_user', ticket_id=ticket.ticket_id, project=project_title)
    for chat_id in recipients:
        await safe_send_message(bot, chat_id, text)


async def relay_user_message(
    bot: Bot, container, ticket: TicketModel, message: Message, skip_header: bool = False
) -> None:
    messages_repo: TicketMessagesRepository = await container.get(TicketMessagesRepository)
    content_type, text, file_id = extract_content(message)
    messages_repo.add_message(
        TicketMessageModel(
            ticket_id=ticket.ticket_id,
            sender_role='user',
            sender_id=ticket.user_id,
            content_type=content_type,
            text=text,
            file_id=file_id,
            tg_message_id=message.message_id,
        )
    )

    if ticket.assigned_operator_id:
        await safe_copy_message(bot, ticket.assigned_operator_id, message.chat.id, message.message_id)
        return

    recipients, is_fallback = await _project_recipients(container, ticket.project_id)
    if is_fallback:
        # Тикет без операторов: контент сохранён, админы уже получили хинт при создании — не штормим.
        return
    header = None
    markup = None
    if not skip_header:
        project_title = project_link(ticket.project.title, ticket.project.url) if ticket.project else ''
        user_name = ticket.user.html_mention if ticket.user else str(ticket.user_id)
        header = PHRASES_RU.replace(
            'operator.incoming', ticket_id=ticket.ticket_id, project=project_title, user=user_name
        )
        markup = kb_ticket_actions(ticket.ticket_id)
    for chat_id in recipients:
        if header is not None:
            await safe_send_message(bot, chat_id, header, markup)
        await safe_copy_message(bot, chat_id, message.chat.id, message.message_id)


async def relay_operator_message(bot: Bot, container, ticket: TicketModel, message: Message, operator_id: int) -> bool:
    messages_repo: TicketMessagesRepository = await container.get(TicketMessagesRepository)
    content_type, text, file_id = extract_content(message)
    messages_repo.add_message(
        TicketMessageModel(
            ticket_id=ticket.ticket_id,
            sender_role='operator',
            sender_id=operator_id,
            content_type=content_type,
            text=text,
            file_id=file_id,
            tg_message_id=message.message_id,
        )
    )
    return await safe_copy_message(bot, ticket.user_id, message.chat.id, message.message_id)
