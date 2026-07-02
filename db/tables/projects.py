import sqlite3
from datetime import UTC, datetime

from db.models import Pagination, ProjectModel
from db.tables.base import BaseTable
from db.utils import MSK


def _row_to_project(row: sqlite3.Row) -> ProjectModel:
    keys = row.keys()
    return ProjectModel(
        project_id=row['project_id'],
        slug=row['slug'],
        title=row['title'],
        url=row['url'] if 'url' in keys else None,
        is_active=bool(row['is_active']),
        created_at=(
            datetime.fromisoformat(row['created_at']).replace(tzinfo=UTC).astimezone(MSK) if row['created_at'] else None
        ),
    )


class ProjectsTable(BaseTable):
    __tablename__ = 'projects'

    def create_table(self):
        self.cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {self.__tablename__} (
            project_id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            url TEXT,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        existing_cols = {r['name'] for r in self.cursor.execute(f'PRAGMA table_info({self.__tablename__})')}
        if 'url' not in existing_cols:
            self.cursor.execute(f'ALTER TABLE {self.__tablename__} ADD COLUMN url TEXT')
        self.cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_projects_active ON {self.__tablename__}(is_active)')
        self.conn.commit()
        self._log('CREATE_TABLE')

    def add_project(self, slug: str, title: str, url: str | None = None) -> ProjectModel | None:
        try:
            self.cursor.execute(
                f'INSERT INTO {self.__tablename__} (slug, title, url) VALUES (?, ?, ?)',
                (slug, title, url),
            )
            self.conn.commit()
            self._log('ADD_PROJECT', slug=slug)
            return self.get_by_slug(slug)
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return None

    def get_by_slug(self, slug: str) -> ProjectModel | None:
        self.cursor.execute(f'SELECT * FROM {self.__tablename__} WHERE slug = ?', (slug,))
        row = self.cursor.fetchone()
        return _row_to_project(row) if row else None

    def get_by_id(self, project_id: int) -> ProjectModel | None:
        self.cursor.execute(f'SELECT * FROM {self.__tablename__} WHERE project_id = ?', (project_id,))
        row = self.cursor.fetchone()
        return _row_to_project(row) if row else None

    def set_active(self, slug: str, is_active: bool) -> bool:
        self.cursor.execute(
            f'UPDATE {self.__tablename__} SET is_active = ? WHERE slug = ?',
            (int(is_active), slug),
        )
        self.conn.commit()
        changed = self.cursor.rowcount > 0
        if changed:
            self._log('SET_ACTIVE', slug=slug, is_active=is_active)
        return changed

    def set_title(self, project_id: int, title: str) -> bool:
        self.cursor.execute(
            f'UPDATE {self.__tablename__} SET title = ? WHERE project_id = ?',
            (title, project_id),
        )
        self.conn.commit()
        changed = self.cursor.rowcount > 0
        if changed:
            self._log('SET_TITLE', project_id=project_id)
        return changed

    def set_slug(self, project_id: int, slug: str) -> bool:
        try:
            self.cursor.execute(
                f'UPDATE {self.__tablename__} SET slug = ? WHERE project_id = ?',
                (slug, project_id),
            )
            self.conn.commit()
            changed = self.cursor.rowcount > 0
            if changed:
                self._log('SET_SLUG', project_id=project_id, slug=slug)
            return changed
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False

    def set_url(self, project_id: int, url: str | None) -> bool:
        self.cursor.execute(
            f'UPDATE {self.__tablename__} SET url = ? WHERE project_id = ?',
            (url, project_id),
        )
        self.conn.commit()
        changed = self.cursor.rowcount > 0
        if changed:
            self._log('SET_URL', project_id=project_id)
        return changed

    def delete_project(self, project_id: int) -> bool:
        self.cursor.execute(
            'DELETE FROM ticket_messages WHERE ticket_id IN (SELECT ticket_id FROM tickets WHERE project_id = ?)',
            (project_id,),
        )
        self.cursor.execute('DELETE FROM tickets WHERE project_id = ?', (project_id,))
        self.cursor.execute('DELETE FROM operators WHERE project_id = ?', (project_id,))
        self.cursor.execute(f'DELETE FROM {self.__tablename__} WHERE project_id = ?', (project_id,))
        self.conn.commit()
        deleted = self.cursor.rowcount > 0
        if deleted:
            self._log('DELETE_PROJECT', project_id=project_id)
        return deleted

    def get_active_projects(self) -> list[ProjectModel]:
        self.cursor.execute(f'SELECT * FROM {self.__tablename__} WHERE is_active = 1 ORDER BY title')
        return [_row_to_project(row) for row in self.cursor]

    def get_all(self) -> list[ProjectModel]:
        self.cursor.execute(f'SELECT * FROM {self.__tablename__} ORDER BY is_active DESC, title')
        return [_row_to_project(row) for row in self.cursor]

    def get_all_projects(self, page: int = 1, per_page: int = 10) -> tuple[list[ProjectModel], Pagination]:
        pagination = Pagination(page=page, per_page=per_page, total_items=0, total_pages=0)
        self.cursor.execute(
            f'SELECT * FROM {self.__tablename__} ORDER BY is_active DESC, title LIMIT ? OFFSET ?',
            (pagination.per_page, pagination.offset),
        )
        projects = [_row_to_project(row) for row in self.cursor]

        self.cursor.execute(f'SELECT COUNT(*) as total FROM {self.__tablename__}')
        total = self.cursor.fetchone()['total']
        pagination.total_items = total
        pagination.total_pages = (total + per_page - 1) // per_page
        return projects, pagination
