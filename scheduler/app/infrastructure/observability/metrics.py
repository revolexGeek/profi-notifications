"""Метрики планировщика в формате Prometheus (реализация порта Metrics).

Лёгкий счётчик без внешних зависимостей: сколько команд опубликовано и когда
была последняя. Отдаётся эндпоинтом `/metrics`.
"""

import time


class PrometheusMetrics:
    def __init__(self) -> None:
        self._published = 0
        self._last_ts = 0.0

    def command_published(self) -> None:
        self._published += 1
        self._last_ts = time.time()

    def render(self) -> str:
        lines = [
            "# HELP scheduler_commands_published_total Всего опубликовано команд парсинга.",
            "# TYPE scheduler_commands_published_total counter",
            f"scheduler_commands_published_total {self._published}",
            "# HELP scheduler_last_command_timestamp_seconds Unix-время последней команды.",
            "# TYPE scheduler_last_command_timestamp_seconds gauge",
            f"scheduler_last_command_timestamp_seconds {self._last_ts}",
        ]
        return "\n".join(lines) + "\n"
