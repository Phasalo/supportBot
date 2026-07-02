from pathlib import Path

from db.models import Pagination, ProjectModel
from db.tables.projects import ProjectsTable


class ProjectsRepository:
    def __init__(self, db_path: Path):
        self._db_path = db_path

    def add_project(self, slug: str, title: str, url: str | None = None) -> ProjectModel | None:
        with ProjectsTable(self._db_path) as t:
            return t.add_project(slug, title, url)

    def get_by_slug(self, slug: str) -> ProjectModel | None:
        with ProjectsTable(self._db_path) as t:
            return t.get_by_slug(slug)

    def get_by_id(self, project_id: int) -> ProjectModel | None:
        with ProjectsTable(self._db_path) as t:
            return t.get_by_id(project_id)

    def set_active(self, slug: str, is_active: bool) -> bool:
        with ProjectsTable(self._db_path) as t:
            return t.set_active(slug, is_active)

    def set_title(self, project_id: int, title: str) -> bool:
        with ProjectsTable(self._db_path) as t:
            return t.set_title(project_id, title)

    def set_slug(self, project_id: int, slug: str) -> bool:
        with ProjectsTable(self._db_path) as t:
            return t.set_slug(project_id, slug)

    def set_url(self, project_id: int, url: str | None) -> bool:
        with ProjectsTable(self._db_path) as t:
            return t.set_url(project_id, url)

    def delete_project(self, project_id: int) -> bool:
        with ProjectsTable(self._db_path) as t:
            return t.delete_project(project_id)

    def get_active_projects(self) -> list[ProjectModel]:
        with ProjectsTable(self._db_path) as t:
            return t.get_active_projects()

    def get_all(self) -> list[ProjectModel]:
        with ProjectsTable(self._db_path) as t:
            return t.get_all()

    def get_all_projects(self, page: int = 1, per_page: int = 10) -> tuple[list[ProjectModel], Pagination]:
        with ProjectsTable(self._db_path) as t:
            return t.get_all_projects(page, per_page)
