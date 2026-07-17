# scheduler

Недостающий **триггер** конвейера. По расписанию публикует команды парсинга в
RabbitMQ: каждые N секунд кладёт `ParseRequest` в очередь `parse.requests` (её
читает `parser-worker`), со свежим уникальным `request_id`.

```
[scheduler] ──каждые N сек, свежий request_id──▶ parse.requests ──▶ parser-worker
```

## Стек

- **Taskiq + taskiq-faststream** — расписание и публикация (**без Taskiq worker**:
  крутится только scheduler, который сам публикует в брокер).
- **FastStream + RabbitMQ** — «пустой» брокер (только паблиш, без подписчиков).
- **Pydantic v2** — структурированный payload команды.
- **uv**, **pytest**, **ruff**, **mypy**.

## Что делает

1. По расписанию (интервал из env) формирует `ParseRequest` со **свежим `request_id`**.
2. Публикует его в durable-очередь `parse.requests` (default exchange).
3. Логирует (structured JSON), считает метрики, отдаёт `/health` `/ready` `/metrics`.

**Одна реплика** (несколько инстансов дублировали бы команды) — деплой `replicas: 1`.

## Контракт (из `parser-worker`)

`parse.requests` (`ParseRequest`), snake_case:

```jsonc
{
  "request_id": "5f1c…",      // уникальный на каждый тик
  "filter": { "search_query": "", "page_size": 10, "sort": "DEFAULT",
              "all_verticals": true, "use_saved_filter": true },
  "max_pages": 1
}
```

## Архитектура (Clean Architecture)

```
app/
├── domain/            # ParseCommand + BoardFilter + SortOrder (value objects)
├── application/       # порты (IdGenerator, Logger, Metrics) + сценарий build_parse_command
├── infrastructure/    # config, messaging (пустой брокер + taskiq-faststream), ids, observability
├── main.py            # composition root: AsgiFastStream + запуск StreamScheduler
└── asgi.py            # точка входа: uvicorn app.asgi:app
```

## Конфигурация

Полный список — в [.env.example](.env.example). Ключевое:

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `SCHEDULER__PARSE_INTERVAL_SECONDS` | `300` | интервал публикации |
| `SCHEDULER__PARSE_QUEUE` | `parse.requests` | целевая очередь |
| `SCHEDULER__PARSE_MAX_PAGES` | `1` | страниц доски за прогон |
| `SCHEDULER__PARSE_SEARCH_QUERY` | `` | поисковый запрос |
| `RABBITMQ__HOST` … | `localhost` … | доступ к RabbitMQ |

## Запуск

```bash
uv sync
uv run uvicorn app.asgi:app --host 0.0.0.0 --port 8000
```

Health: `GET /ready` (пинг брокера), `/health`, метрики — `/metrics`.

## Тесты

```bash
uv run pytest                 # unit + integration (in-memory брокер)
uv run pytest --cov=app       # покрытие (≥80%)
uv run ruff check app tests && uv run mypy app
```

Messaging тестируется in-memory через `TestRabbitBroker` — реальный брокер не нужен.
