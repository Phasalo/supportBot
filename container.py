from dishka import Provider, Scope, make_async_container, provide

from config.settings import Config
from db.repositories.operators import OperatorsRepository
from db.repositories.projects import ProjectsRepository
from db.repositories.queries import QueriesRepository
from db.repositories.ticket_messages import TicketMessagesRepository
from db.repositories.tickets import TicketsRepository
from db.repositories.users import UsersRepository


class AppProvider(Provider):
    scope = Scope.APP

    def __init__(self, config: Config):
        super().__init__()
        self._config = config

    @provide
    def get_config(self) -> Config:
        return self._config

    @provide
    def users_repo(self, config: Config) -> UsersRepository:
        return UsersRepository(config.db_path)

    @provide
    def queries_repo(self, config: Config) -> QueriesRepository:
        return QueriesRepository(config.db_path)

    @provide
    def projects_repo(self, config: Config) -> ProjectsRepository:
        return ProjectsRepository(config.db_path)

    @provide
    def operators_repo(self, config: Config) -> OperatorsRepository:
        return OperatorsRepository(config.db_path)

    @provide
    def tickets_repo(self, config: Config) -> TicketsRepository:
        return TicketsRepository(config.db_path)

    @provide
    def ticket_messages_repo(self, config: Config) -> TicketMessagesRepository:
        return TicketMessagesRepository(config.db_path)


def build_container(config: Config):
    return make_async_container(AppProvider(config))
