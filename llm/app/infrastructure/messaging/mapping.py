"""Маппинг wire-заказа `Order` в доменный `Listing`."""

from app.domain.listing import Budget, Listing
from app.infrastructure.messaging.schemas import Geo, Order


def _location(geo: Geo) -> str | None:
    for place in (geo.order_location, geo.remote, geo.client_may_come):
        if place is not None and place.prefix.strip():
            return place.prefix.strip()
    return None


def order_to_listing(order: Order) -> Listing:
    budget = None
    if order.price is not None:
        budget = Budget.from_price(order.price.prefix, order.price.value, order.price.suffix)
    return Listing(
        id=order.id,
        title=order.title,
        description=order.description,
        budget=budget,
        is_remote=order.geo.remote is not None,
        location=_location(order.geo),
        client_tags=order.client.tags,
    )
