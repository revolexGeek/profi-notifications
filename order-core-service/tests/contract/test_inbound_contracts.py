"""Контракт-тесты входящих сообщений: точные фикстуры соседей должны разбираться.

Фикстуры взяты дословно из README соседних сервисов (parser-worker, llm). Если
их контракт изменится — эти тесты упадут и подсветят расхождение.
"""

from app.infrastructure.messaging.schemas import AssessmentResultMessage, ParseResultMessage

# Точная форма parse.results из parser-worker/README.md.
PARSE_RESULTS_FIXTURE = {
    "request_id": "req-1",
    "fetched_at": 1784135987,
    "total_count": 29,
    "next_cursor": "WzgwLjA5...",
    "orders": [
        {
            "id": "91635361",
            "title": "Девопс услуги",
            "description": "...",
            "price": {"prefix": "до", "value": "700", "suffix": ""},
            "geo": {
                "remote": {"prefix": "Дистанционно", "suffix": "", "address": None},
                "order_location": None,
                "client_may_come": None,
            },
            "client": {"name": "Георгий", "tags": []},
            "badges": [{"id": "b1", "image_key": "PERCENT", "label": "Скидка на отклик"}],
            "schedule": None,
            "last_update": 1784135813,
            "score": 80.5,
            "is_fresh": False,
            "is_viewed": False,
            "coordinates": None,
        }
    ],
}

# Точная форма assess.results из llm/README.md (notification — camelCase).
ASSESS_RESULTS_FIXTURE = {
    "order_id": "91668753",
    "suitability_score": 90,
    "notification": {"text": "…", "parseMode": "HTML", "disableWebPagePreview": True},
}


def test_parse_results_deserializes() -> None:
    message = ParseResultMessage.model_validate(PARSE_RESULTS_FIXTURE)

    assert message.request_id == "req-1"
    assert len(message.orders) == 1
    order = message.orders[0]
    assert order.id == "91635361"
    assert order.price is not None
    assert order.price.prefix == "до"
    assert order.geo.remote is not None
    assert order.badges[0].image_key == "PERCENT"
    assert order.score == 80.5


def test_assess_results_deserializes_camel_case_notification() -> None:
    message = AssessmentResultMessage.model_validate(ASSESS_RESULTS_FIXTURE)

    assert message.order_id == "91668753"
    assert message.suitability_score == 90
    assert message.notification.parse_mode == "HTML"
    assert message.notification.disable_web_page_preview is True
    assert message.notification.disable_notification is None
