import logging
from collections.abc import Iterator
from pathlib import Path

from prometheus_client import REGISTRY, Counter
from prometheus_client.core import GaugeMetricFamily

from db.repositories.tickets import TicketsRepository

logger = logging.getLogger(__name__)

tickets_created = Counter(
    'bot_tickets_created_total',
    'Support tickets opened',
    ['project'],
)


class ActiveTicketsCollector:
    def __init__(self, tickets_repo: TicketsRepository) -> None:
        self._tickets = tickets_repo

    def describe(self) -> Iterator[GaugeMetricFamily]:
        yield GaugeMetricFamily('bot_tickets_active', 'Currently open support tickets', labels=['project'])

    def collect(self) -> Iterator[GaugeMetricFamily]:
        gauge = GaugeMetricFamily(
            'bot_tickets_active',
            'Currently open support tickets',
            labels=['project'],
        )
        try:
            for slug, count in self._tickets.count_active_by_project():
                gauge.add_metric([slug], count)
        except Exception:
            logger.exception('failed to collect bot_tickets_active')
        yield gauge


def register_domain_metrics(db_path: Path) -> None:
    REGISTRY.register(ActiveTicketsCollector(TicketsRepository(db_path)))
