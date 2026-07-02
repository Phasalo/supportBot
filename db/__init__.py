from pathlib import Path

from db.repositories import (
    OperatorsRepository,
    ProjectsRepository,
    QueriesRepository,
    TicketMessagesRepository,
    TicketsRepository,
    UsersRepository,
)
from db.tables import (
    OperatorsTable,
    ProjectsTable,
    QueriesTable,
    TicketMessagesTable,
    TicketsTable,
    UsersTable,
)

__all__ = [
    'OperatorsRepository',
    'ProjectsRepository',
    'QueriesRepository',
    'TicketMessagesRepository',
    'TicketsRepository',
    'UsersRepository',
    'init_database',
]


def init_database(db_path: Path) -> None:
    with UsersTable(db_path) as users_db:
        users_db.create_table()

    with QueriesTable(db_path) as queries_db:
        queries_db.create_table()

    with ProjectsTable(db_path) as projects_db:
        projects_db.create_table()

    with OperatorsTable(db_path) as operators_db:
        operators_db.create_table()

    with TicketsTable(db_path) as tickets_db:
        tickets_db.create_table()

    with TicketMessagesTable(db_path) as ticket_messages_db:
        ticket_messages_db.create_table()
