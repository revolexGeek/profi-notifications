"""Тесты доменной сущности заявки (идентичность = source + external_id)."""

import pytest
from pydantic import ValidationError

from app.domain.order import Order
from app.domain.source import Source
from app.domain.status import OrderStatus


def test_identity_and_defaults() -> None:
    order = Order(source=Source.PROFI, external_id="42", status=OrderStatus.ASSESS_REQUESTED)

    assert order.source is Source.PROFI
    assert order.external_id == "42"
    assert order.status is OrderStatus.ASSESS_REQUESTED
    assert order.suitability_score is None


def test_is_frozen() -> None:
    order = Order(source=Source.PROFI, external_id="42", status=OrderStatus.ASSESS_REQUESTED)

    with pytest.raises(ValidationError):
        order.status = OrderStatus.NO_NOTIFY  # type: ignore[misc]
