"""Сценарий формирования команды парсинга.

Каждый вызов даёт свежий уникальный `request_id`, применяет параметры фильтра из
конфига, считает метрику и логирует. Публикацию делает инфраструктура (taskiq-
faststream) — сценарий отвечает только за содержимое команды.
"""

from app.application.ports import IdGenerator, Logger, Metrics
from app.domain.command import BoardFilter, ParseCommand


class BuildParseCommand:
    def __init__(
        self,
        *,
        id_generator: IdGenerator,
        search_query: str,
        max_pages: int,
        logger: Logger,
        metrics: Metrics,
    ) -> None:
        self._id_generator = id_generator
        self._search_query = search_query
        self._max_pages = max_pages
        self._logger = logger
        self._metrics = metrics

    def build(self) -> ParseCommand:
        command = ParseCommand(
            request_id=self._id_generator.new_id(),
            filter=BoardFilter(search_query=self._search_query),
            max_pages=self._max_pages,
        )
        self._metrics.command_published()
        self._logger.info(
            "parse_command_scheduled",
            request_id=command.request_id,
            max_pages=command.max_pages,
        )
        return command
