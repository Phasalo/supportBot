from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.callbacks import OperatorAction, ProjectPickCallback, ReplyDoneCallback, TicketCallback
from db.models import ProjectModel
from phrases import PHRASES_RU


def kb_project_picker(projects: list[ProjectModel]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for project in projects:
        builder.button(text=project.title, callback_data=ProjectPickCallback(slug=project.slug))
    builder.adjust(1)
    return builder.as_markup()


def kb_open_ticket(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=PHRASES_RU.button.open_ticket,
        callback_data=TicketCallback(action=OperatorAction.open, ticket_id=ticket_id),
    )
    builder.button(
        text=PHRASES_RU.button.reply_ticket,
        callback_data=TicketCallback(action=OperatorAction.reply, ticket_id=ticket_id),
    )
    builder.adjust(2)
    return builder.as_markup()


def kb_ticket_actions(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=PHRASES_RU.button.reply_ticket,
        callback_data=TicketCallback(action=OperatorAction.reply, ticket_id=ticket_id),
    )
    builder.button(
        text=PHRASES_RU.button.close_ticket,
        callback_data=TicketCallback(action=OperatorAction.close, ticket_id=ticket_id),
    )
    builder.adjust(2)
    return builder.as_markup()


def kb_reply_session(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=PHRASES_RU.button.done_reply, callback_data=ReplyDoneCallback())
    builder.button(
        text=PHRASES_RU.button.close_ticket,
        callback_data=TicketCallback(action=OperatorAction.close, ticket_id=ticket_id),
    )
    builder.adjust(2)
    return builder.as_markup()
