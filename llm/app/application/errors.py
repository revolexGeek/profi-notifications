"""Ошибки уровня приложения — классификация сбоев оценки."""


class AssessmentError(Exception):
    """Базовая ошибка обработки заказа."""


class TransientError(AssessmentError):
    """Временный сбой (сеть, таймаут, 429, 5xx). Заказ вернётся с ре-поллом."""


class PermanentError(AssessmentError):
    """Постоянный сбой (auth, битый запрос/данные). Повтор не поможет."""
