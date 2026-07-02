from enum import Enum

from aiogram.filters.callback_data import CallbackData


class OperatorAction(str, Enum):
    open = 'open'
    reply = 'reply'
    close = 'close'


class TicketCallback(CallbackData, prefix='ticket'):
    action: OperatorAction
    ticket_id: int


class ReplyDoneCallback(CallbackData, prefix='reply_done'):
    pass


class ProjectPickCallback(CallbackData, prefix='pick_project'):
    slug: str


class TicketKindPickCallback(CallbackData, prefix='pick_kind'):
    slug: str
    kind: str


class PickerCancelCallback(CallbackData, prefix='pick_cancel'):
    pass
