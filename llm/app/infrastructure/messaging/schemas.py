"""Wire-схемы очередей.

Вход `parse.results` (`ParseResultMessage`) — точное зеркало serde-JSON от
`parser-worker` (snake_case, батч заказов). Выход `NotificationMessage` —
camelCase-контракт, который потребляет TS-сервис notifications.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.domain.notification import NotificationCommand, ParseMode


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
    model_config = ConfigDict(populate_by_name=True)

    text: str
    parse_mode: ParseMode | None = Field(default=None, alias="parseMode")
    disable_notification: bool | None = Field(default=None, alias="disableNotification")
    disable_web_page_preview: bool | None = Field(default=None, alias="disableWebPagePreview")
    message_thread_id: int | None = Field(default=None, alias="messageThreadId")

    @classmethod
    def from_command(cls, command: NotificationCommand) -> "NotificationMessage":
        return cls(
            text=command.text,
            parse_mode=command.parse_mode,
            disable_web_page_preview=command.disable_web_page_preview,
        )
