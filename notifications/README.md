# notifications

Лёгкий сервис доставки уведомлений в Telegram-канал. Забирает сообщения из
RabbitMQ, валидирует их, отправляет текст в **один** Telegram-канал и подтверждает
сообщение только после успешной доставки. Временные и постоянные ошибки
обрабатываются по-разному: временные уходят в retry-очередь, постоянные и
«исчерпавшие попытки» — в DLQ.

Сервис **не** принимает команды от пользователей и **не** обрабатывает входящие
Telegram-updates. Это односторонний потребитель очереди.

## Стек

- **Bun** + **TypeScript** — рантайм и язык.
- **rabbitmq-client** — потребитель и публикатор AMQP.
- **zod** — валидация payload и переменных окружения.
- Нативный **fetch** — вызовы Telegram Bot API.
- **bun test** — тесты (unit + integration), покрытие ≥ 80 %.
- **Bun.serve** — только для эндпоинтов `/health`, `/ready`, `/metrics`.

Никаких тяжёлых фреймворков (NestJS, Moleculer, grammY, Telegraf, Elysia и т.п.).

## Архитектура (Clean Architecture)

Зависимости направлены **внутрь**: внешние слои знают о внутренних, но не наоборот.
Бизнес-логика не зависит ни от RabbitMQ, ни от Telegram, ни от zod.

```
src/
├── domain/            ← Сущности (Entities). Чистые правила, ноль зависимостей.
│   └── notification.ts     — что такое «валидное сообщение» (createNotification)
├── application/       ← Сценарии (Use Cases) и порты.
│   ├── ports.ts            — интерфейсы NotificationSender, Logger
│   ├── errors.ts           — Transient/Permanent DeliveryError
│   ├── delivery-decision.ts— решение: ack | retry | dead-letter
│   └── send-notification.ts— оркестрация «отправить и решить, что делать дальше»
├── infrastructure/    ← Адаптеры и фреймворки (детали).
│   ├── config/             — env → типизированный AppConfig (zod)
│   ├── telegram/           — NotificationSender через fetch к Bot API
│   ├── messaging/          — consumer, topology, схема payload (zod), retry
│   ├── http/               — Bun.serve: health / ready / metrics
│   └── observability/      — JSON-логгер и метрики (Prometheus)
└── main.ts            ← Composition Root: единственное место сборки зависимостей
```

Ключевое правило: `main.ts` создаёт конкретные реализации и «прокидывает» их
внутрь через интерфейсы. `domain` и `application` не импортируют ничего из
`infrastructure`.

## Топология RabbitMQ

```mermaid
flowchart LR
    P([producer]) -->|notify| EX{{notifications}}
    EX --> Q[(notifications)]
    Q -->|nack: временная ошибка| RX{{notifications.retry}}
    RX --> RQ[(notifications.retry\nTTL = NOTIFY_RETRY_DELAY_MS)]
    RQ -->|TTL истёк| EX
    Q -.->|постоянная ошибка / исчерпаны попытки| DLX{{notifications.dlx}}
    DLX --> DLQ[(notifications.dlq)]
```

- **Основная очередь** (`notifications`) — отсюда потребляем. При временной ошибке
  сообщение отклоняется (`nack`, requeue=false) и по dead-letter уходит в
  **retry-обменник**.
- **Retry-очередь** (`notifications.retry`) — держит сообщение `NOTIFY_RETRY_DELAY_MS`
  миллисекунд (per-queue TTL), затем dead-letter возвращает его обратно в основную
  очередь на новую попытку.
- **DLQ** (`notifications.dlq`) — постоянные ошибки и сообщения, исчерпавшие лимит
  попыток. Публикуются приложением напрямую в `notifications.dlx` (с подтверждением
  публикации), и только потом исходное сообщение подтверждается.

Число попыток считается из заголовка `x-death` (сколько раз сообщение было
отклонено основной очередью), поэтому счётчик не теряется между перезапусками.

### Гарантии доставки

- **ack только после успеха.** При успешной отправке возвращается `ACK`. При
  временной ошибке — `nack` в retry (сообщение не подтверждается). В DLQ сообщение
  уходит через публикацию с confirm, и лишь затем исходник подтверждается — потери
  сообщений исключены (at-least-once).
- **Временная ошибка** (сеть, таймаут, `429`, `5xx`) → retry, пока есть попытки.
- **Постоянная ошибка** (`400`, `401`, `403`, `404`, невалидный payload) → сразу DLQ.

## Контракт сообщения

Тело сообщения — JSON (`content-type: application/json`):

```jsonc
{
  "text": "Привет, канал!",          // обязательно, 1..4096 символов
  "parseMode": "MarkdownV2",          // опционально: HTML | MarkdownV2 | Markdown
  "disableNotification": false,       // опционально
  "disableWebPagePreview": true       // опционально
}
```

Неизвестные поля игнорируются. Невалидный payload (нет `text`, неверный тип,
пустой текст, длиннее 4096) отправляется в DLQ без ретраев.

## Переменные окружения

Скопируйте `.env.example` в `.env` и заполните. Обязательны:
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `RABBITMQ_URL`.

| Переменная | По умолчанию | Описание |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Токен бота от @BotFather. Бот должен быть админом канала. |
| `TELEGRAM_CHAT_ID` | — | Канал: числовой id (`-100…`) или `@username`. |
| `TELEGRAM_API_BASE_URL` | `https://api.telegram.org` | Базовый URL Bot API. |
| `TELEGRAM_TIMEOUT_MS` | `10000` | Таймаут HTTP-запроса к Telegram. |
| `RABBITMQ_URL` | — | AMQP-строка подключения. |
| `RABBITMQ_PREFETCH` | `10` | QoS prefetch (сообщений «в полёте»). |
| `RABBITMQ_CONCURRENCY` | `5` | Параллельных обработчиков. |
| `NOTIFY_EXCHANGE` | `notifications` | Основной обменник. |
| `NOTIFY_QUEUE` | `notifications` | Основная очередь. |
| `NOTIFY_ROUTING_KEY` | `notify` | Routing key. |
| `NOTIFY_RETRY_EXCHANGE` | `notifications.retry` | Retry-обменник. |
| `NOTIFY_RETRY_QUEUE` | `notifications.retry` | Retry-очередь. |
| `NOTIFY_DLX` | `notifications.dlx` | Dead-letter обменник. |
| `NOTIFY_DLQ` | `notifications.dlq` | Dead-letter очередь. |
| `NOTIFY_MAX_ATTEMPTS` | `5` | Попыток доставки до DLQ. |
| `NOTIFY_RETRY_DELAY_MS` | `30000` | Задержка в retry-очереди (TTL). |
| `HTTP_HOST` | `0.0.0.0` | Хост HTTP-сервера. |
| `HTTP_PORT` | `3000` | Порт health/ready/metrics. |
| `LOG_LEVEL` | `info` | `debug` \| `info` \| `warn` \| `error`. |

## Запуск

### Локально

```bash
bun install
cp .env.example .env   # и заполнить значения
bun start              # или: bun run dev  (watch-режим)
```

### Docker Compose (RabbitMQ + сервис)

```bash
export TELEGRAM_BOT_TOKEN=...      # или положить в .env
export TELEGRAM_CHAT_ID=@my_channel
docker compose up --build
```

Management UI RabbitMQ: http://localhost:15672 (guest/guest).

### Отправить тестовое сообщение

```bash
bun run publish:sample "Проверка связи ✅"
```

## HTTP-эндпоинты

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/health` (`/healthz`, `/livez`) | Liveness — процесс жив. |
| GET | `/ready` (`/readyz`) | Readiness — есть коннект к RabbitMQ и активный потребитель (иначе `503`). |
| GET | `/metrics` | Метрики в формате Prometheus. |

Метрики: `notifications_received_total`, `notifications_delivered_total`,
`notifications_retried_total`, `notifications_dead_lettered_total{category=…}`.

## Тесты

```bash
bun test                 # unit + integration
bun test --coverage      # с отчётом покрытия (порог 80 %)
bun run typecheck        # tsc --noEmit
```

Тесты не требуют ни RabbitMQ, ни сети: транспорт и брокер подменяются фейками, а
чистая логика (валидация, решения о ретраях, подсчёт попыток) покрыта unit-тестами.

Отдельно есть **e2e-тест против реального брокера** — он пропускается, если не
задан `RABBITMQ_TEST_URL`:

```bash
docker compose up -d rabbitmq
RABBITMQ_TEST_URL=amqp://guest:guest@localhost:5672 bun test tests/integration/broker.test.ts
```
