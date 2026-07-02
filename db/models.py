from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from utils.format_string import clear_string


class TicketStatus(StrEnum):
    OPEN = 'open'
    ASSIGNED = 'assigned'
    CLOSED = 'closed'


@dataclass
class UserModel:
    user_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_admin: bool = False
    is_banned: bool = False
    registration_date: datetime | None = None
    query_count: int = 0

    def display_name(self) -> str | None:
        return f'@{self.username}' if self.username else self.first_name

    def full_name(self) -> str:
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return ' '.join(parts) if parts else str(self.user_id)

    @property
    def html_mention(self) -> str:
        if self.username:
            label = f'@{self.username}'
        elif self.first_name:
            label = self.first_name
        elif self.last_name:
            label = self.last_name
        else:
            label = str(self.user_id)
        return f'<a href="tg://user?id={self.user_id}">{clear_string(label)}</a>'


@dataclass
class QueryModel:
    user_id: int
    query_text: str
    query_id: int | None = None
    query_date: datetime | None = None
    user: UserModel | None = None


@dataclass
class ProjectModel:
    slug: str
    title: str
    project_id: int | None = None
    url: str | None = None
    is_active: bool = True
    created_at: datetime | None = None


@dataclass
class OperatorModel:
    user_id: int
    project_id: int
    operator_id: int | None = None
    created_at: datetime | None = None
    user: UserModel | None = None
    project: ProjectModel | None = None


@dataclass
class TicketModel:
    project_id: int
    user_id: int
    ticket_id: int | None = None
    status: TicketStatus = TicketStatus.OPEN
    assigned_operator_id: int | None = None
    is_active: bool = True
    created_at: datetime | None = None
    closed_at: datetime | None = None
    user: UserModel | None = None
    project: ProjectModel | None = None


@dataclass
class TicketMessageModel:
    ticket_id: int
    sender_role: str
    sender_id: int
    content_type: str
    text: str | None = None
    file_id: str | None = None
    tg_message_id: int | None = None
    message_id: int | None = None
    created_at: datetime | None = None


@dataclass
class Pagination:
    page: int
    per_page: int
    total_items: int
    total_pages: int

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page
