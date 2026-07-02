from pathlib import Path

from db.models import OperatorModel
from db.tables.operators import OperatorsTable


class OperatorsRepository:
    def __init__(self, db_path: Path):
        self._db_path = db_path

    def add_operator(self, user_id: int, project_id: int) -> bool:
        with OperatorsTable(self._db_path) as t:
            return t.add_operator(user_id, project_id)

    def remove_operator(self, user_id: int, project_id: int) -> bool:
        with OperatorsTable(self._db_path) as t:
            return t.remove_operator(user_id, project_id)

    def is_operator(self, user_id: int) -> bool:
        with OperatorsTable(self._db_path) as t:
            return t.is_operator(user_id)

    def is_operator_of(self, user_id: int, project_id: int) -> bool:
        with OperatorsTable(self._db_path) as t:
            return t.is_operator_of(user_id, project_id)

    def get_project_ids_for_user(self, user_id: int) -> list[int]:
        with OperatorsTable(self._db_path) as t:
            return t.get_project_ids_for_user(user_id)

    def get_operators_for_project(self, project_id: int) -> list[OperatorModel]:
        with OperatorsTable(self._db_path) as t:
            return t.get_operators_for_project(project_id)
