"""Ошибки уровня приложения — классификация сбоев обработки для retry/DLQ."""


class OrderCoreError(Exception):
    """Базовая ошибка обработки заявки."""


class TransientError(OrderCoreError):
    """Временный сбой (БД/брокер недоступны). Сообщение уйдёт на повтор."""


class PermanentError(OrderCoreError):
    """Постоянный сбой (битые данные, неизвестная заявка). Повтор не поможет — DLQ."""
