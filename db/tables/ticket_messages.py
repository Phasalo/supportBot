import sqlite3
from datetime import UTC, datetime

from db.models import Pagination, TicketMessageModel
from db.tables.base import BaseTable
from db.utils import MSK


def _row_to_message(row: sqlite3.Row) -> TicketMessageModel:
    return TicketMessageModel(
        message_id=row['message_id'],
        ticket_id=row['ticket_id'],
        sender_role=row['sender_role'],
        sender_id=row['sender_id'],
        content_type=row['content_type'],
        text=row['text'],
        file_id=row['file_id'],
        tg_message_id=row['tg_message_id'],
        created_at=(
            datetime.fromisoformat(row['created_at']).replace(tzinfo=UTC).astimezone(MSK) if row['created_at'] else None
        ),
    )


class TicketMessagesTable(BaseTable):
    __tablename__ = 'ticket_messages'

    def create_table(self):
        self.cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {self.__tablename__} (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            sender_role TEXT NOT NULL,
            sender_id INTEGER NOT NULL,
            content_type TEXT NOT NULL,
            text TEXT,
            file_id TEXT,
            tg_message_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id)
        )""")
        self.cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_ticket_messages ON {self.__tablename__}(ticket_id)')
        self.conn.commit()
        self._log('CREATE_TABLE')

    def add_message(self, msg: TicketMessageModel) -> TicketMessageModel:
        self.cursor.execute(
            f"""
            INSERT INTO {self.__tablename__}
                (ticket_id, sender_role, sender_id, content_type, text, file_id, tg_message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                msg.ticket_id,
                msg.sender_role,
                msg.sender_id,
                msg.content_type,
                msg.text,
                msg.file_id,
                msg.tg_message_id,
            ),
        )
        self.conn.commit()
        message_id = self.cursor.lastrowid
        self._log('ADD_MESSAGE', message_id=message_id, ticket_id=msg.ticket_id, role=msg.sender_role)
        msg.message_id = message_id
        return msg

    def get_ticket_messages(
        self, ticket_id: int, page: int = 1, per_page: int = 10
    ) -> tuple[list[TicketMessageModel], Pagination]:
        pagination = Pagination(page=page, per_page=per_page, total_items=0, total_pages=0)
        self.cursor.execute(
            f'SELECT * FROM {self.__tablename__} WHERE ticket_id = ? ORDER BY message_id LIMIT ? OFFSET ?',
            (ticket_id, pagination.per_page, pagination.offset),
        )
        messages = [_row_to_message(row) for row in self.cursor]

        self.cursor.execute(f'SELECT COUNT(*) as total FROM {self.__tablename__} WHERE ticket_id = ?', (ticket_id,))
        total = self.cursor.fetchone()['total']
        pagination.total_items = total
        pagination.total_pages = (total + per_page - 1) // per_page
        return messages, pagination
