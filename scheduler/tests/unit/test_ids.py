"""Тесты генератора уникальных идентификаторов."""

from app.infrastructure.ids import UuidGenerator


def test_generates_unique_ids() -> None:
    generator = UuidGenerator()

    ids = {generator.new_id() for _ in range(100)}

    assert len(ids) == 100
