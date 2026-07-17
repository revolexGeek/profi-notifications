"""Генератор уникальных идентификаторов (реализация порта IdGenerator)."""

import uuid


class UuidGenerator:
    def new_id(self) -> str:
        return uuid.uuid4().hex
