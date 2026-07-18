# order-core-service

Сервис-**«core»** конвейера profi.ru. Стоит в центре: принимает заявки от
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
2. Дедуплицирует по `(source, external_id)` — уникальное ограничение в БД.
3. Сохраняет заявку и её статус жизненного цикла в PostgreSQL.
4. Через Outbox инициирует оценку: кладёт каждый **новый** заказ в `assess.requests`
   (контракт `llm`).
5. Принимает вердикт из `assess.results` (контракт `llm`).
6. Применяет политику «слать / не слать» уведомление (порог + идемпотентность).
7. Через Outbox публикует готовое уведомление в обменник `notifications`.

## Жизненный цикл заявки

```
(новая) ──ingest──▶ ASSESS_REQUESTED ──notify──▶ NOTIFY_REQUESTED
                            └────────── skip ───▶ NO_NOTIFY
```

Вердикт применяется только к заявке в статусе `ASSESS_REQUESTED`. Повторная доставка
вердикта по уже обработанной заявке — no-op (идемпотентность). Вердикт по неизвестной
заявке — постоянная ошибка (в DLQ): Outbox гарантирует «сначала persist, потом
publish», поэтому `llm` не может ответить по заявке, которой у «core» нет.

## Гарантии

- **Идемпотентность обработчиков** — уникальные ограничения `(source, external_id)` и
  `outbox.dedup_key` + guard'ы переходов статуса. Повторная доставка любого сообщения
  безопасна.
- **Транзакции (Unit of Work)** — вся работа обработчика идёт в одной транзакции.
- **Outbox Pattern** — событие пишется в ту же транзакцию, что и изменение состояния;
  фоновое реле публикует его в RabbitMQ (at-least-once) с `FOR UPDATE SKIP LOCKED`.
  Потребители идемпотентны, поэтому возможный дубль при публикации безопасен.

### Надёжность приёма

DLQ живёт на уровне приложения (`assess.results` объявляется сервисом `llm` без
dead-letter-аргументов, брокерный DLX на неё навесить нельзя):

- **Невалидный payload** или **постоянная ошибка** (например, вердикт по неизвестной
  заявке) → сообщение публикуется в `order.dlq` и подтверждается, чтобы не крутиться
  в hot-loop.
- **Временный сбой** (БД, сеть) → сообщение возвращается в очередь (`NACK`) и
  обрабатывается повторно.

## Контракты очередей (выведены из соседей, не заданы вручную)

| Ребро | Напр. | Exchange | Queue / routing key | Схема | Источник контракта |
|---|---|---|---|---|---|
| `parse.results` | IN ← parser | default `""` | `parse.results` | `ParseResult` (snake_case, батч) | `parser-worker` |
| `assess.requests` | OUT → llm | default `""` | `assess.requests` | `ParseResultMessage` (snake_case) | `llm` |
| `assess.results` | IN ← llm | default `""` | `assess.results` (durable) | `AssessmentResultMessage` | `llm` |
| `notify` | OUT → notifications | `notifications` (direct) | rk `notify` | `NotificationMessage` (camelCase) | `notifications` |

## Схема БД

Две таблицы (миграции — в [`alembic/`](alembic/)):

- **`orders`** — заявки. Идентичность `(source, external_id)` с уникальным ограничением
  (дедуп). Хранит статус, балл соответствия и сырой заказ (`payload`) для форварда в `llm`.
- **`outbox`** — исходящие события. `dedup_key` уникален (идемпотентность создания
  события); реле забирает `pending`-строки и помечает `published`.

## Архитектура (Clean Architecture)

```
app/
├── domain/            # заявка, статус, оценка, уведомление, решение, источник, ошибки
├── application/       # порты (репозитории, UoW, publisher, logger) + сценарии
├── infrastructure/    # config, db (SQLAlchemy 2 async), messaging (FastStream), outbox, observability
├── main.py            # composition root (build_app)
└── asgi.py            # точка входа: uvicorn app.asgi:app
alembic/               # миграции схемы БД
```

Зависимости направлены внутрь; `domain`/`application` не импортируют `infrastructure`.
Подписчики — Humble Objects. Три сценария: `IngestOrders` (приём + дедуп),
`ProcessAssessment` (вердикт → решение), `RelayOutbox` (фоновая публикация событий).

## Конфигурация

Настройки сгруппированы по внешним системам, каждая читает свой префикс `GROUP__`
(вложенный `Settings`, `get_settings()`). Дефолты messaging совпадают с контрактами
соседей. Полный список — в [.env.example](.env.example). Ключевое:

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `RABBITMQ__HOST` … | `localhost` … | адрес и доступ к RabbitMQ |
| `POSTGRES__HOST` / `POSTGRES__DB` | `localhost` / `order_core` | адрес и имя БД |
| `POSTGRES__USERNAME` / `POSTGRES__PASSWORD` | `postgres` / `postgres` | доступ к БД |
| `MESSAGING__PARSE_QUEUE` | `parse.results` | вход от `parser-worker` |
| `MESSAGING__ASSESS_RESULT_QUEUE` | `assess.results` | вход от `llm` |
| `MESSAGING__ASSESS_REQUEST_QUEUE` | `assess.requests` | выход в `llm` |
| `MESSAGING__NOTIFY_EXCHANGE` / `MESSAGING__NOTIFY_ROUTING_KEY` | `notifications` / `notify` | выход в `notifications` |
| `MESSAGING__PREFETCH` | `10` | prefetch консюмеров |
| `ASSESSMENT__NOTIFY_THRESHOLD` | `0` | порог «core» поверх `llm` (`0` = доверять `llm`) |
| `OUTBOX__POLL_INTERVAL_MS` | `1000` | период опроса outbox |
| `OUTBOX__BATCH_SIZE` | `100` | размер батча публикации |
| `LOG_LEVEL` | `info` | уровень логов |

## Запуск

### В составе стека (рекомендуется)

Из корня репозитория (нужны запущенные RabbitMQ + PostgreSQL). Миграции накатываются
автоматически на старте контейнера:

```bash
docker compose up -d order-core-service
```

Health: `GET http://127.0.0.1:8001/ready` (пинг брокера и БД) и `/health` (пинг брокера).

### Локально

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.asgi:app --host 0.0.0.0 --port 8000
```

## Тесты

```bash
uv run pytest                    # unit + contract (+ integration, если задан POSTGRES_TEST_URL)
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
