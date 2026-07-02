import sqlite3
from datetime import UTC, datetime

from db.models import Pagination, ProjectModel, TicketModel, TicketStatus, UserModel
from db.tables.base import BaseTable
from db.utils import MSK


def _row_to_ticket(row: sqlite3.Row) -> TicketModel:
    keys = row.keys()
    user = (
        UserModel(
            user_id=row['user_id'],
            username=row['username'],
            first_name=row['first_name'],
            last_name=row['last_name'],
            is_admin=bool(row['is_admin']),
        )
        if 'username' in keys
        else None
    )
    project = (
        ProjectModel(
            project_id=row['project_id'],
            slug=row['slug'],
            title=row['title'],
            url=row['url'] if 'url' in keys else None,
        )
        if 'slug' in keys
        else None
    )
    return TicketModel(
        ticket_id=row['ticket_id'],
        project_id=row['project_id'],
        user_id=row['user_id'],
        status=TicketStatus(row['status']),
        assigned_operator_id=row['assigned_operator_id'],
        is_active=bool(row['is_active']),
        created_at=(
            datetime.fromisoformat(row['created_at']).replace(tzinfo=UTC).astimezone(MSK) if row['created_at'] else None
        ),
        closed_at=(
            datetime.fromisoformat(row['closed_at']).replace(tzinfo=UTC).astimezone(MSK) if row['closed_at'] else None
        ),
        user=user,
        project=project,
    )


class TicketsTable(BaseTable):
    __tablename__ = 'tickets'

    def create_table(self):
        self.cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {self.__tablename__} (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            assigned_operator_id INTEGER,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects (project_id),
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )""")
        self.cursor.execute(
            f'CREATE UNIQUE INDEX IF NOT EXISTS uq_tickets_one_active '
            f'ON {self.__tablename__}(user_id) WHERE is_active = 1'
        )
        self.cursor.execute(
            f'CREATE INDEX IF NOT EXISTS idx_tickets_user_active ON {self.__tablename__}(user_id, is_active)'
        )
        self.cursor.execute(
            f'CREATE INDEX IF NOT EXISTS idx_tickets_project_status ON {self.__tablename__}(project_id, status)'
        )
        self.conn.commit()
        self._log('CREATE_TABLE')

    def get_ticket(self, ticket_id: int) -> TicketModel | None:
        self.cursor.execute(
            f"""
            SELECT t.*, u.username, u.first_name, u.last_name, u.is_admin, p.slug, p.title, p.url
            FROM {self.__tablename__} t
            LEFT JOIN users u ON t.user_id = u.user_id
            LEFT JOIN projects p ON t.project_id = p.project_id
            WHERE t.ticket_id = ?""",
            (ticket_id,),
        )
        row = self.cursor.fetchone()
        return _row_to_ticket(row) if row else None

    def get_active_ticket_for_user(self, user_id: int) -> TicketModel | None:
        self.cursor.execute(
            f"""
            SELECT t.*, u.username, u.first_name, u.last_name, u.is_admin, p.slug, p.title, p.url
            FROM {self.__tablename__} t
            LEFT JOIN users u ON t.user_id = u.user_id
            LEFT JOIN projects p ON t.project_id = p.project_id
            WHERE t.user_id = ? AND t.is_active = 1""",
            (user_id,),
        )
        row = self.cursor.fetchone()
        return _row_to_ticket(row) if row else None

    def get_or_create_active(self, user_id: int, project_id: int) -> tuple[TicketModel, bool]:
        existing = self.get_active_ticket_for_user(user_id)
        if existing:
            return existing, False
        try:
            self.cursor.execute(
                f'INSERT INTO {self.__tablename__} (project_id, user_id, status, is_active) VALUES (?, ?, ?, 1)',
                (project_id, user_id, TicketStatus.OPEN.value),
            )
            self.conn.commit()
            ticket_id = self.cursor.lastrowid
            self._log('CREATE_TICKET', ticket_id=ticket_id, user_id=user_id, project_id=project_id)
            return self.get_ticket(ticket_id), True
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return self.get_active_ticket_for_user(user_id), False

    def claim_ticket(self, ticket_id: int, operator_id: int) -> bool:
        self.cursor.execute(
            f"""
            UPDATE {self.__tablename__}
            SET assigned_operator_id = ?, status = ?
            WHERE ticket_id = ? AND assigned_operator_id IS NULL AND is_active = 1""",
            (operator_id, TicketStatus.ASSIGNED.value, ticket_id),
        )
        self.conn.commit()
        won = self.cursor.rowcount > 0
        if won:
            self._log('CLAIM_TICKET', ticket_id=ticket_id, operator_id=operator_id)
        return won

    def close_ticket(self, ticket_id: int) -> bool:
        self.cursor.execute(
            f"""
            UPDATE {self.__tablename__}
            SET status = ?, is_active = 0, closed_at = CURRENT_TIMESTAMP
            WHERE ticket_id = ? AND is_active = 1""",
            (TicketStatus.CLOSED.value, ticket_id),
        )
        self.conn.commit()
        closed = self.cursor.rowcount > 0
        if closed:
            self._log('CLOSE_TICKET', ticket_id=ticket_id)
        return closed

    def get_tickets_for_project(
        self, project_id: int, page: int = 1, per_page: int = 8
    ) -> tuple[list[TicketModel], Pagination]:
        pagination = Pagination(page=page, per_page=per_page, total_items=0, total_pages=0)
        self.cursor.execute(
            f"""
            SELECT t.*, u.username, u.first_name, u.last_name, u.is_admin, p.slug, p.title, p.url
            FROM {self.__tablename__} t
            LEFT JOIN users u ON t.user_id = u.user_id
            LEFT JOIN projects p ON t.project_id = p.project_id
            WHERE t.project_id = ?
            ORDER BY t.is_active DESC, t.created_at DESC, t.ticket_id DESC
            LIMIT ? OFFSET ?""",
            (project_id, pagination.per_page, pagination.offset),
        )
        tickets = [_row_to_ticket(row) for row in self.cursor]
        self.cursor.execute(
            f'SELECT COUNT(*) as total FROM {self.__tablename__} WHERE project_id = ?',
            (project_id,),
        )
        total = self.cursor.fetchone()['total']
        pagination.total_items = total
        pagination.total_pages = (total + per_page - 1) // per_page
        return tickets, pagination

    def count_for_project(self, project_id: int) -> int:
        self.cursor.execute(
            f'SELECT COUNT(*) as total FROM {self.__tablename__} WHERE project_id = ?',
            (project_id,),
        )
        return self.cursor.fetchone()['total']

    def get_active_tickets_for_operator(self, user_id: int) -> list[TicketModel]:
        self.cursor.execute(
            f"""
            SELECT t.*, u.username, u.first_name, u.last_name, u.is_admin, p.slug, p.title, p.url
            FROM {self.__tablename__} t
            JOIN operators o ON t.project_id = o.project_id AND o.user_id = ?
            LEFT JOIN users u ON t.user_id = u.user_id
            LEFT JOIN projects p ON t.project_id = p.project_id
            WHERE t.is_active = 1
            ORDER BY t.created_at""",
            (user_id,),
        )
        return [_row_to_ticket(row) for row in self.cursor]
