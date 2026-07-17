# order-core-service

Сервис-**«мозг»** конвейера Profi.ru. Стоит в центре: принимает заявки от
`parser-worker`, дедуплицирует их, хранит заявки и статусы обработки в PostgreSQL,
инициирует оценку через сервис `llm`, принимает вердикт, решает — слать ли
уведомление, и надёжно (через Outbox) публикует команду в сервис `notifications`.

```
parser-worker ─parse.results→ [ order-core-service ] ─assess.requests→ llm
                                  │ дедуп + PostgreSQL + Outbox           │
notifications ←──notify──────────┘←────────────assess.results────────────┘
   (Telegram)
```

## Что делает

1. Читает батч заказов из `parse.results` (контракт `parser-worker`).
2. Дедуп по `(source, external_id)` — уникальное ограничение в БД.
3. Сохраняет заявку и её статус жизненного цикла в PostgreSQL.
4. Через Outbox инициирует оценку: кладёт заказ в `assess.requests` (контракт `llm`).
5. Принимает вердикт из `assess.results` (контракт `llm`).
6. Применяет политику «слать/не слать» уведомление (порог + идемпотентность).
7. Через Outbox публикует готовое уведомление в обменник `notifications`
   (контракт `notifications`).

## Гарантии

- **Идемпотентность всех обработчиков** — уникальные ограничения `(source,
  external_id)` и `outbox.dedup_key` + guard'ы переходов статуса.
- **Транзакции** — вся работа обработчика в одной транзакции (Unit of Work).
- **Outbox Pattern** — событие пишется в ту же транзакцию, что и изменение
  состояния; фоновое реле публикует его в RabbitMQ (at-least-once) с
  `FOR UPDATE SKIP LOCKED`.
- **Retry + DLQ** — временные сбои уходят на повтор (retry-очередь с TTL),
  «ядовитые»/исчерпавшие попытки — в DLQ.

## Контракты очередей (выведены из соседей, не заданы вручную)

| Ребро | Напр. | Exchange | Queue / routing key | Схема | Источник контракта |
|---|---|---|---|---|---|
| `parse.results` | IN ← parser | default `""` | `parse.results` | `ParseResult` (snake_case, батч) | `parser-worker` |
| `assess.requests` | OUT → llm | default `""` | `assess.requests` | `ParseResultMessage` (snake_case) | `llm` |
| `assess.results` | IN ← llm | default `""` | `assess.results` (durable) | `AssessmentResultMessage` | `llm` |
| `notify` | OUT → notifications | `notifications` (direct) | rk `notify` | `NotificationMessage` (camelCase) | `notifications` |

## Архитектура (Clean Architecture)

```
app/
├── domain/            # заявка, статус, оценка, уведомление, решение, события, ошибки
├── application/       # порты (репозитории, UoW, publisher, logger) + сценарии
├── infrastructure/    # config, db (SQLAlchemy 2 async), messaging (FastStream), outbox, observability
├── main.py            # composition root (build_app)
└── asgi.py            # точка входа: uvicorn app.asgi:app
alembic/               # миграции схемы БД
```

Зависимости направлены внутрь; `domain`/`application` не импортируют
`infrastructure`. Подписчики — Humble Objects.

## Конфигурация

Настройки сгруппированы по внешним системам, каждая читает свой префикс `GROUP__`
(вложенный `Settings`, `get_settings()`). Полный список — в [.env.example](.env.example).
Дефолты messaging совпадают с контрактами соседей.

## Запуск

### В составе стека (рекомендуется)

Из корня репозитория (нужны запущенные RabbitMQ + PostgreSQL):

```bash
docker compose up -d order-core-service
```

Health: `GET http://127.0.0.1:8001/ready` (пинг брокера и БД) и `/health`.

### Локально

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.asgi:app --host 0.0.0.0 --port 8000
```

## Тесты

```bash
uv run pytest                    # unit + contract (+ integration, если доступен POSTGRES_TEST_URL)
uv run pytest --cov=app          # с покрытием (≥80%)
uv run ruff check app tests      # линт
uv run mypy app                  # типы
```

Messaging тестируется in-memory через `TestRabbitBroker` (реальный брокер не нужен).
Интеграционные тесты БД идут против реального PostgreSQL и **пропускаются**, если не
задан `POSTGRES_TEST_URL`:

```bash
docker compose up -d postgres
POSTGRES_TEST_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/order_core \
  uv run pytest -m postgres
```
