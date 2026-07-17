"""Маппинг доменной `ParseCommand` в wire-payload очереди `parse.requests`."""

from typing import Any

from app.domain.command import ParseCommand
from app.infrastructure.messaging.schemas import BoardFilterMessage, ParseRequestMessage


def to_parse_request(command: ParseCommand) -> dict[str, Any]:
    message = ParseRequestMessage(
        request_id=command.request_id,
        filter=BoardFilterMessage(
            search_query=command.filter.search_query,
            page_size=command.filter.page_size,
            sort=command.filter.sort.value,
            all_verticals=command.filter.all_verticals,
            use_saved_filter=command.filter.use_saved_filter,
        ),
        max_pages=command.max_pages,
    )
    return message.model_dump(exclude_none=True)
