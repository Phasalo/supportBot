from pathlib import Path

from db.models import Pagination, TicketMessageModel
from db.tables.ticket_messages import TicketMessagesTable


class TicketMessagesRepository:
    def __init__(self, db_path: Path):
        self._db_path = db_path

    def add_message(self, msg: TicketMessageModel) -> TicketMessageModel:
        with TicketMessagesTable(self._db_path) as t:
            return t.add_message(msg)

    def get_ticket_messages(
        self, ticket_id: int, page: int = 1, per_page: int = 10
    ) -> tuple[list[TicketMessageModel], Pagination]:
        with TicketMessagesTable(self._db_path) as t:
            return t.get_ticket_messages(ticket_id, page, per_page)
