"""Тесты структурного JSON-логгера."""

import json

import pytest

from app.infrastructure.observability.logging import JsonLogger


def test_emits_json_with_fields(capsys: pytest.CaptureFixture[str]) -> None:
    JsonLogger(service="scheduler", level="info").info("parse_command_scheduled", request_id="r1")

    record = json.loads(capsys.readouterr().out.strip())
    assert record["event"] == "parse_command_scheduled"
    assert record["service"] == "scheduler"
    assert record["request_id"] == "r1"


def test_respects_level_threshold(capsys: pytest.CaptureFixture[str]) -> None:
    JsonLogger(level="warning").info("ignored")

    assert capsys.readouterr().out == ""
