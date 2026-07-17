"""Тесты маппинга доменной команды в wire-контракт парсера."""

from app.domain.command import BoardFilter, ParseCommand, SortOrder
from app.infrastructure.messaging.mapping import to_parse_request
from app.infrastructure.messaging.schemas import ParseRequestMessage


def test_maps_command_to_parser_contract() -> None:
    command = ParseCommand(
        request_id="abc",
        filter=BoardFilter(search_query="go", sort=SortOrder.DATE),
        max_pages=3,
    )

    payload = to_parse_request(command)

    assert payload["request_id"] == "abc"
    assert payload["filter"]["search_query"] == "go"
    assert payload["filter"]["sort"] == "DATE"
    assert payload["filter"]["use_saved_filter"] is True
    assert payload["max_pages"] == 3
    # Парсер читает это своей ParseRequest — проверяем round-trip через зеркало.
    assert ParseRequestMessage.model_validate(payload).request_id == "abc"


def test_omits_unset_max_pages() -> None:
    payload = to_parse_request(ParseCommand(request_id="abc"))

    assert "max_pages" not in payload  # exclude_none → парсер применит свой дефолт
