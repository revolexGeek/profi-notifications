"""Тесты маппинга wire-заказа в доменный Listing."""

from app.infrastructure.messaging.mapping import order_to_listing
from app.infrastructure.messaging.schemas import Client, Geo, GeoPlace, Order, Price


def test_maps_core_fields_and_budget() -> None:
    order = Order(
        id="91635361",
        title="Девопс услуги",
        description="настроить tailscale",
        price=Price(prefix="до", value="700 ₽", suffix=""),
        geo=Geo(remote=GeoPlace(prefix="Дистанционно · Москва")),
        client=Client(name="Георгий", tags=["новый"]),
    )

    listing = order_to_listing(order)

    assert listing.id == "91635361"
    assert listing.title == "Девопс услуги"
    assert listing.is_remote is True
    assert listing.location == "Дистанционно · Москва"
    assert listing.client_tags == ["новый"]
    assert listing.budget is not None
    assert listing.budget.amount == 700
    assert listing.url == "https://profi.ru/backoffice/n.php?o=91635361"


def test_maps_without_price_or_geo() -> None:
    order = Order(id="2", title="t", description="d")

    listing = order_to_listing(order)

    assert listing.budget is None
    assert listing.is_remote is False
    assert listing.location is None
