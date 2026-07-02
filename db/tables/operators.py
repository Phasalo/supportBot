import sqlite3
from datetime import UTC, datetime

from db.models import OperatorModel, ProjectModel, UserModel
from db.tables.base import BaseTable
from db.utils import MSK


class OperatorsTable(BaseTable):
    __tablename__ = 'operators'

    def create_table(self):
        self.cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {self.__tablename__} (
            operator_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, project_id),
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (project_id) REFERENCES projects (project_id)
        )""")
        self.cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_operators_project ON {self.__tablename__}(project_id)')
        self.cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_operators_user ON {self.__tablename__}(user_id)')
        self.conn.commit()
        self._log('CREATE_TABLE')

    def add_operator(self, user_id: int, project_id: int) -> bool:
        try:
            self.cursor.execute(
                f'INSERT INTO {self.__tablename__} (user_id, project_id) VALUES (?, ?)',
                (user_id, project_id),
            )
            self.conn.commit()
            self._log('ADD_OPERATOR', user_id=user_id, project_id=project_id)
            return True
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False

    def remove_operator(self, user_id: int, project_id: int) -> bool:
        self.cursor.execute(
            f'DELETE FROM {self.__tablename__} WHERE user_id = ? AND project_id = ?',
            (user_id, project_id),
        )
        self.conn.commit()
        removed = self.cursor.rowcount > 0
        if removed:
            self._log('REMOVE_OPERATOR', user_id=user_id, project_id=project_id)
        return removed

    def is_operator(self, user_id: int) -> bool:
        self.cursor.execute(f'SELECT 1 FROM {self.__tablename__} WHERE user_id = ? LIMIT 1', (user_id,))
        return self.cursor.fetchone() is not None

    def is_operator_of(self, user_id: int, project_id: int) -> bool:
        self.cursor.execute(
            f'SELECT 1 FROM {self.__tablename__} WHERE user_id = ? AND project_id = ? LIMIT 1',
            (user_id, project_id),
        )
        return self.cursor.fetchone() is not None

    def get_project_ids_for_user(self, user_id: int) -> list[int]:
        self.cursor.execute(f'SELECT project_id FROM {self.__tablename__} WHERE user_id = ?', (user_id,))
        return [row['project_id'] for row in self.cursor]

    def get_operators_for_project(self, project_id: int) -> list[OperatorModel]:
        self.cursor.execute(
            f"""
            SELECT o.operator_id, o.user_id, o.project_id, o.created_at,
                   u.username, u.first_name, u.last_name, u.is_admin
            FROM {self.__tablename__} o
            LEFT JOIN users u ON o.user_id = u.user_id
            WHERE o.project_id = ?
            ORDER BY o.created_at""",
            (project_id,),
        )
        return [self._row_to_operator(row) for row in self.cursor]

    @staticmethod
    def _row_to_operator(row: sqlite3.Row) -> OperatorModel:
        user = (
            UserModel(
                user_id=row['user_id'],
                username=row['username'],
                first_name=row['first_name'],
                last_name=row['last_name'],
                is_admin=bool(row['is_admin']),
            )
            if 'username' in row.keys()
            else None
        )
        project = (
            ProjectModel(project_id=row['project_id'], slug=row['slug'], title=row['title'])
            if 'slug' in row.keys()
            else None
        )
        return OperatorModel(
            operator_id=row['operator_id'],
            user_id=row['user_id'],
            project_id=row['project_id'],
            created_at=(
                datetime.fromisoformat(row['created_at']).replace(tzinfo=UTC).astimezone(MSK)
                if row['created_at']
                else None
            ),
            user=user,
            project=project,
        )
