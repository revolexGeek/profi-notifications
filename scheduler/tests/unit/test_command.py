"""Тесты доменной команды парсинга (value objects)."""

import pytest
from pydantic import ValidationError

from app.domain.command import BoardFilter, ParseCommand, SortOrder


def test_parse_command_defaults() -> None:
    cmd = ParseCommand(request_id="r1")

    assert cmd.request_id == "r1"
    assert cmd.max_pages is None
    assert cmd.filter.page_size == 10
    assert cmd.filter.sort is SortOrder.DEFAULT
    assert cmd.filter.all_verticals is True
    assert cmd.filter.use_saved_filter is True
    assert cmd.filter.search_query == ""


def test_sort_order_values_match_parser_contract() -> None:
    assert SortOrder.DEFAULT == "DEFAULT"
    assert SortOrder.DATE == "DATE"


def test_is_frozen() -> None:
    cmd = ParseCommand(request_id="r1")

    with pytest.raises(ValidationError):
        cmd.request_id = "changed"  # type: ignore[misc]


def test_page_size_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        BoardFilter(page_size=0)


def test_accepts_custom_filter_and_max_pages() -> None:
    cmd = ParseCommand(
        request_id="r1",
        filter=BoardFilter(search_query="go", sort=SortOrder.DATE),
        max_pages=3,
    )

    assert cmd.filter.search_query == "go"
    assert cmd.filter.sort is SortOrder.DATE
    assert cmd.max_pages == 3
