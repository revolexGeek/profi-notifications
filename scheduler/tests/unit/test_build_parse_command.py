"""Тесты сценария формирования команды парсинга (на фейках)."""

from app.application.build_parse_command import BuildParseCommand
from tests.fakes import FakeIdGenerator, FakeLogger, FakeMetrics


def _use_case(ids: list[str], search_query: str = "", max_pages: int = 1) -> BuildParseCommand:
    return BuildParseCommand(
        id_generator=FakeIdGenerator(ids),
        search_query=search_query,
        max_pages=max_pages,
        logger=FakeLogger(),
        metrics=FakeMetrics(),
    )


def test_builds_command_from_config() -> None:
    command = _use_case(["id-1"], search_query="go", max_pages=2).build()

    assert command.request_id == "id-1"
    assert command.filter.search_query == "go"
    assert command.max_pages == 2


def test_each_build_uses_a_fresh_id() -> None:
    use_case = _use_case(["id-1", "id-2"])

    assert use_case.build().request_id == "id-1"
    assert use_case.build().request_id == "id-2"


def test_records_metric_and_logs() -> None:
    metrics = FakeMetrics()
    logger = FakeLogger()

    BuildParseCommand(
        id_generator=FakeIdGenerator(["id-1"]),
        search_query="",
        max_pages=1,
        logger=logger,
        metrics=metrics,
    ).build()

    assert metrics.published == 1
    assert logger.events_of("parse_command_scheduled")
