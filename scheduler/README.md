# scheduler

Недостающий **триггер** конвейера. По расписанию публикует команды парсинга в
RabbitMQ: каждые N секунд кладёт `ParseRequest` со свежим уникальным `request_id` в
очередь `parse.requests` (её читает `parser-worker`).

```
[scheduler] ──каждые N сек, свежий request_id──▶ parse.requests ──▶ parser-worker
```

## Стек

- **Taskiq + taskiq-faststream** — расписание и публикация. Крутится только сам
  scheduler, который публикует в брокер, — **без отдельного Taskiq worker**.
- **FastStream + RabbitMQ** — «пустой» брокер (только паблиш, без подписчиков).
- **Pydantic v2** — структурированный payload команды.
- **uv**, **pytest**, **ruff**, **mypy**.

## Что делает

1. По расписанию (интервал из env) формирует `ParseRequest` со **свежим `request_id`**.
2. Публикует его в durable-очередь `parse.requests` (default exchange).
3. Пишет structured-логи (JSON), считает метрики, отдаёт `/health`, `/ready`, `/metrics`.

Разворачивай **в одной реплике**: несколько инстансов дублировали бы команды на каждый
тик (`replicas: 1`).

## Контракт — `parse.requests` (`ParseRequest`)

Default exchange (routing key = имя очереди), snake_case. Зеркалит контракт
`parser-worker`:

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

Сценарий отвечает только за содержимое команды; публикацию делает taskiq-faststream.

## Конфигурация

Полный список — в [.env.example](.env.example). Ключевое:

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `SCHEDULER__PARSE_INTERVAL_SECONDS` | `300` | интервал публикации, сек |
| `SCHEDULER__PARSE_QUEUE` | `parse.requests` | целевая очередь (контракт `parser-worker`) |
| `SCHEDULER__PARSE_MAX_PAGES` | `1` | страниц доски за прогон |
| `SCHEDULER__PARSE_SEARCH_QUERY` | `` | поисковый запрос фильтра |
| `RABBITMQ__HOST` / `RABBITMQ__PORT` | `localhost` / `5672` | адрес RabbitMQ |
| `RABBITMQ__USERNAME` / `RABBITMQ__PASSWORD` | `guest` / `guest` | доступ к RabbitMQ |
| `LOG_LEVEL` | `info` | уровень логов |

## Запуск

### В составе стека (рекомендуется)

Из корня репозитория:

```bash
docker compose up -d scheduler
```

Порт наружу не публикуется — статус смотри в `docker compose ps` (контейнерный
healthcheck пингует `/ready`).

### Локально

Нужен запущенный RabbitMQ (`docker compose up -d rabbitmq`):

```bash
uv sync
uv run uvicorn app.asgi:app --host 0.0.0.0 --port 8000
```

Health: `GET /health` (liveness), `/ready` (пинг брокера), метрики — `/metrics`.

## Тесты

```bash
uv run pytest                 # unit + integration (in-memory брокер)
uv run pytest --cov=app       # покрытие (≥80%)
uv run ruff check app tests && uv run mypy app
```

Messaging тестируется in-memory через `TestRabbitBroker` — реальный брокер не нужен.
