from pathlib import Path

from db.models import Pagination, TicketKind, TicketModel
from db.tables.tickets import TicketsTable


class TicketsRepository:
    def __init__(self, db_path: Path):
        self._db_path = db_path

    def get_ticket(self, ticket_id: int) -> TicketModel | None:
        with TicketsTable(self._db_path) as t:
            return t.get_ticket(ticket_id)

    def get_active_ticket_for_user(self, user_id: int) -> TicketModel | None:
        with TicketsTable(self._db_path) as t:
            return t.get_active_ticket_for_user(user_id)

    def get_or_create_active(self, user_id: int, project_id: int, kind: TicketKind) -> tuple[TicketModel, bool]:
        with TicketsTable(self._db_path) as t:
            return t.get_or_create_active(user_id, project_id, kind)

    def claim_ticket(self, ticket_id: int, operator_id: int) -> bool:
        with TicketsTable(self._db_path) as t:
            return t.claim_ticket(ticket_id, operator_id)

    def close_ticket(self, ticket_id: int) -> bool:
        with TicketsTable(self._db_path) as t:
            return t.close_ticket(ticket_id)

    def count_for_project(self, project_id: int) -> int:
        with TicketsTable(self._db_path) as t:
            return t.count_for_project(project_id)

    def count_active_by_project(self) -> list[tuple[str, int]]:
        with TicketsTable(self._db_path) as t:
            return t.count_active_by_project()

    def get_tickets_for_project(
        self, project_id: int, page: int = 1, per_page: int = 8
    ) -> tuple[list[TicketModel], Pagination]:
        with TicketsTable(self._db_path) as t:
            return t.get_tickets_for_project(project_id, page, per_page)

    def get_active_tickets_for_operator(self, user_id: int) -> list[TicketModel]:
        with TicketsTable(self._db_path) as t:
            return t.get_active_tickets_for_operator(user_id)
