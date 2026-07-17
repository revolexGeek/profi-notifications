"""Доменная команда на запуск парсинга доски Profi.ru.

Value objects, зеркалящие семантику `ParseRequest` парсера. `request_id`
генерирует приложение (уникальный на каждый тик) — в домене это просто строка.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SortOrder(StrEnum):
    DEFAULT = "DEFAULT"
    DATE = "DATE"


class BoardFilter(BaseModel):
    model_config = ConfigDict(frozen=True)

    search_query: str = ""
    page_size: int = Field(default=10, gt=0)
    sort: SortOrder = SortOrder.DEFAULT
    all_verticals: bool = True
    use_saved_filter: bool = True


class ParseCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: str
    filter: BoardFilter = Field(default_factory=BoardFilter)
    max_pages: int | None = None
