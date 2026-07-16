"""Тесты структурного JSON-логгера."""

import json

import pytest

from app.infrastructure.observability.logging import JsonLogger


def test_emits_json_with_fields(capsys: pytest.CaptureFixture[str]) -> None:
    JsonLogger(service="llm", level="info").info("order_notified", order_id="1", score=88)

    record = json.loads(capsys.readouterr().out.strip())
    assert record["event"] == "order_notified"
    assert record["service"] == "llm"
    assert record["level"] == "info"
    assert record["order_id"] == "1"
    assert record["score"] == 88


def test_respects_level_threshold(capsys: pytest.CaptureFixture[str]) -> None:
    JsonLogger(level="warning").info("ignored")

    assert capsys.readouterr().out == ""


def test_warning_goes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    JsonLogger(level="info").warning("order_failed", order_id="7")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err.strip())["event"] == "order_failed"
