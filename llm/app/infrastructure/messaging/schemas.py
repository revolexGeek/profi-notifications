"""Wire-схемы очередей.

Вход `assess.requests` (`ParseResultMessage`) — та же snake_case-форма, что шлёт
`parser-worker` (батч заказов); её проксирует «мозг». Выход `assess.results`
(`AssessmentResultMessage`) — вердикт llm с готовым Telegram-уведомлением внутри
(camelCase, контракт TS-сервиса notifications) — его потребляет «мозг».
"""

from pydantic import BaseModel, Field

from app.domain.notification import NotificationCommand, ParseMode
from app.domain.result import AssessmentResult


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


class NotificationMessage(BaseModel):
    # serialization_alias: конструируем по snake_case, camelCase — только при by_alias-дампе
    text: str
    parse_mode: ParseMode | None = Field(default=None, serialization_alias="parseMode")
    disable_notification: bool | None = Field(
        default=None, serialization_alias="disableNotification"
    )
    disable_web_page_preview: bool | None = Field(
        default=None, serialization_alias="disableWebPagePreview"
    )
    message_thread_id: int | None = Field(default=None, serialization_alias="messageThreadId")

    @classmethod
    def from_command(cls, command: NotificationCommand) -> "NotificationMessage":
        return cls(
            text=command.text,
            parse_mode=command.parse_mode,
            disable_web_page_preview=command.disable_web_page_preview,
        )


class AssessmentResultMessage(BaseModel):
    order_id: str
    suitability_score: int
    notification: NotificationMessage

    @classmethod
    def from_result(cls, result: AssessmentResult) -> "AssessmentResultMessage":
        return cls(
            order_id=result.order_id,
            suitability_score=result.suitability_score,
            notification=NotificationMessage.from_command(result.notification),
        )
