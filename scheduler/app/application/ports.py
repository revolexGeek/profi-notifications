"""Выходные порты приложения (реализуются в infrastructure).

Сценарий зависит только от этих интерфейсов — конкретные адаптеры (uuid, логгер,
метрики) подставляются в composition root.
"""

from typing import Protocol


class IdGenerator(Protocol):
    def new_id(self) -> str: ...


class Metrics(Protocol):
    def command_published(self) -> None: ...


class Logger(Protocol):
    def debug(self, event: str, **fields: object) -> None: ...
    def info(self, event: str, **fields: object) -> None: ...
    def warning(self, event: str, **fields: object) -> None: ...
    def error(self, event: str, **fields: object) -> None: ...
