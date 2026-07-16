"""Фейковые реализации портов приложения для тестов."""

from app.domain.assessment import Assessment
from app.domain.listing import Listing
from app.domain.notification import NotificationCommand
from app.domain.profile import ContractorProfile


class FakeAssessor:
    """Возвращает заранее заданный Assessment по id заказа или бросает Exception."""

    def __init__(self, responses: dict[str, Assessment | Exception]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    async def assess(self, listing: Listing, profile: ContractorProfile) -> Assessment:
        self.calls.append(listing.id)
        result = self.responses[listing.id]
        if isinstance(result, Exception):
            raise result
        return result


class FakePublisher:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.published: list[NotificationCommand] = []

    async def publish(self, command: NotificationCommand) -> None:
        if self.error is not None:
            raise self.error
        self.published.append(command)


class FakeLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, object]]] = []

    def _record(self, level: str, event: str, **fields: object) -> None:
        self.events.append((level, event, fields))

    def debug(self, event: str, **fields: object) -> None:
        self._record("debug", event, **fields)

    def info(self, event: str, **fields: object) -> None:
        self._record("info", event, **fields)

    def warning(self, event: str, **fields: object) -> None:
        self._record("warning", event, **fields)

    def error(self, event: str, **fields: object) -> None:
        self._record("error", event, **fields)

    def events_of(self, event: str) -> list[dict[str, object]]:
        return [fields for _, name, fields in self.events if name == event]
