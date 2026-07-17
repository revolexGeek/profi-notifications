"""Wire-схемы очередей — точные зеркала контрактов соседей.

Вход `parse.results` (`ParseResultMessage`) и исход `assess.requests` — snake_case
форма `parser-worker` (её же читает llm). Вход `assess.results`
(`AssessmentResultMessage`) — вердикт llm; вложенный `notification` — camelCase
контракт сервиса notifications, который «мозг» пробрасывает как есть.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ParseMode = Literal["HTML", "MarkdownV2", "Markdown"]


# --- parse.results / assess.requests (snake_case, контракт parser-worker и llm) ---


class Price(BaseModel):
    prefix: str = ""
    value: str = ""
    suffix: str = ""


class Coordinates(BaseModel):
    lat: float
    lon: float


class GeoPlace(BaseModel):
    prefix: str = ""
    suffix: str = ""
    address: str | None = None


class Geo(BaseModel):
    remote: GeoPlace | None = None
    order_location: GeoPlace | None = None
    client_may_come: GeoPlace | None = None


class Client(BaseModel):
    name: str = ""
    tags: list[str] = Field(default_factory=list)


class Badge(BaseModel):
    id: str = ""
    image_key: str = ""
    label: str = ""


class Order(BaseModel):
    id: str
    title: str = ""
    description: str = ""
    price: Price | None = None
    geo: Geo = Field(default_factory=Geo)
    client: Client = Field(default_factory=Client)
    badges: list[Badge] = Field(default_factory=list)
    schedule: str | None = None
    last_update: int = 0
    score: float = 0.0
    is_fresh: bool = False
    is_viewed: bool = False
    coordinates: Coordinates | None = None


class ParseResultMessage(BaseModel):
    request_id: str
    fetched_at: int = 0
    total_count: int = 0
    next_cursor: str | None = None
    orders: list[Order] = Field(default_factory=list)


# --- assess.results / notify (notification — camelCase, контракт notifications) ---


class NotificationMessage(BaseModel):
    # populate_by_name: читаем camelCase-вход и конструируем по snake_case-полям;
    # by_alias-дамп даёт обратно camelCase для обменника notifications.
    model_config = ConfigDict(populate_by_name=True)

    text: str
    parse_mode: ParseMode | None = Field(default=None, alias="parseMode")
    disable_notification: bool | None = Field(default=None, alias="disableNotification")
    disable_web_page_preview: bool | None = Field(default=None, alias="disableWebPagePreview")
    message_thread_id: int | None = Field(default=None, alias="messageThreadId")


class AssessmentResultMessage(BaseModel):
    order_id: str
    suitability_score: int
    notification: NotificationMessage
