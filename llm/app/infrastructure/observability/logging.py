"""Структурный JSON-логгер (реализация порта Logger).

Одна JSON-строка на запись в stdout (warning/error — в stderr), порог по
уровню. Инжектируется в сценарий — в домен не импортируется.
"""

import json
import sys
from datetime import UTC, datetime

_LEVELS = {"debug": 10, "info": 20, "warning": 30, "error": 40}


class JsonLogger:
    def __init__(self, service: str = "llm", level: str = "info") -> None:
        self._service = service
        self._threshold = _LEVELS.get(level.lower(), 20)

    def _emit(self, level: str, event: str, fields: dict[str, object]) -> None:
        if _LEVELS[level] < self._threshold:
            return
        record = {
            "level": level,
            "time": datetime.now(UTC).isoformat(),
            "service": self._service,
            "event": event,
            **fields,
        }
        stream = sys.stderr if _LEVELS[level] >= _LEVELS["warning"] else sys.stdout
        print(json.dumps(record, ensure_ascii=False, default=str), file=stream)

    def debug(self, event: str, **fields: object) -> None:
        self._emit("debug", event, fields)

    def info(self, event: str, **fields: object) -> None:
        self._emit("info", event, fields)

    def warning(self, event: str, **fields: object) -> None:
        self._emit("warning", event, fields)

    def error(self, event: str, **fields: object) -> None:
        self._emit("error", event, fields)
