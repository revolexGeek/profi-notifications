"""Wire-схема очереди `parse.requests` — зеркало `ParseRequest` парсера (snake_case).

`filter` и `max_pages` необязательны на стороне парсера (у него дефолты); мы шлём
структурированно. `sort` — строка (парсер принимает только "DEFAULT"/"DATE",
это гарантирует доменный `SortOrder`).
"""

from pydantic import BaseModel, Field


class BoardFilterMessage(BaseModel):
    search_query: str = ""
    page_size: int = 10
    sort: str = "DEFAULT"
    all_verticals: bool = True
    use_saved_filter: bool = True


class ParseRequestMessage(BaseModel):
    request_id: str
    filter: BoardFilterMessage = Field(default_factory=BoardFilterMessage)
    max_pages: int | None = None
