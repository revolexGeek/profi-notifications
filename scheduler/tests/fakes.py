"""Фейковые реализации портов приложения для тестов."""


class FakeIdGenerator:
    def __init__(self, ids: list[str]) -> None:
        self._ids = ids
        self._index = 0

    def new_id(self) -> str:
        value = self._ids[self._index % len(self._ids)]
        self._index += 1
        return value


class FakeMetrics:
    def __init__(self) -> None:
        self.published = 0

    def command_published(self) -> None:
        self.published += 1


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
