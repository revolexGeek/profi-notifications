# llm

Stateless-сервис: оценивает заявки с доски Profi.ru через LLM (Groq + LangChain),
сопоставляет их с профилем исполнителя и подходящие отправляет в очередь
`notifications` (оттуда TS-сервис шлёт их в Telegram).

```
[parser-worker] ─parse.results→ [ llm ] ─notify→ [notifications] → Telegram
                                   │
                              Groq (structured output)
```


## Что делает

1. Читает батч заказов из очереди `parse.results` (публикует `parser-worker`).
2. Для каждого заказа через Groq извлекает требования и оценивает соответствие
   профилю исполнителя (0–100) + помечает неподдерживаемые навыки и нежелательные
   типы заказов.
3. Доменная политика решает: жёсткие фильтры (unsupported/rejected) важнее балла,
   иначе сравнение с порогом `SUITABILITY_THRESHOLD`.
4. Подходящие форматирует в HTML и публикует в обменник `notifications`.

## Поведение

- **Stateless, без дедупа.** Один и тот же заказ приходит каждый опрос доски —
  дедупликацию/новизну возьмёт будущий отдельный сервис («мозг»). Пока сервис
  запущен сам по себе, он пересылает повторяющиеся заказы на каждом тике.
- **Только подходящие.** Неподходящие логируются и не публикуются.
- **Best-effort.** Сбой одного заказа (например, rate limit Groq) логируется и не
  рушит батч — заказ вернётся со следующим опросом. Нераспарсиваемый конверт
  уходит в `parse.results.dlq`. Retry-очереди нет: фид самоисцеляется.

## Контракты

### Вход — `parse.results` (`ParseResultMessage`)

Публикуется `parser-worker` в default exchange (routing key = имя очереди),
snake_case, батч заказов. Заказ: `id`, `title`, `description`, `price`
(`{prefix, value, suffix}`), `geo`, `client.tags`, `score` (релевантность
Profi.ru — не наша оценка) и др.

### Выход — `notifications` (`NotificationMessage`)

Durable direct обменник `notifications`, routing key `notify`, camelCase:

```jsonc
{ "text": "…", "parseMode": "HTML", "disableWebPagePreview": true }
```

`text` ≤ 4096: заголовок-ссылка (`https://profi.ru/backoffice/n.php?o=<id>`),
краткое описание от модели, бюджет (если есть), оценка соответствия.

## Архитектура (Clean Architecture)

```
app/
├── domain/            # заявка, профиль, оценка, решение, форматирование уведомления
├── application/       # порты (LlmAssessor, NotificationPublisher, Logger) + сценарий
├── infrastructure/    # config, llm (Groq), messaging (RabbitMQ), observability
├── main.py            # composition root (build_app)
└── asgi.py            # точка входа: uvicorn app.asgi:app
```

Зависимости направлены внутрь; подписчик — Humble Object; LLM/RabbitMQ/Groq —
детали во внешнем кольце.

## Конфигурация

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `LLM_AMQP_URL` | `amqp://guest:guest@localhost:5672/` | подключение к RabbitMQ |
| `LLM_INPUT_QUEUE` | `parse.results` | входная очередь |
| `LLM_NOTIFY_EXCHANGE` / `LLM_NOTIFY_ROUTING_KEY` | `notifications` / `notify` | выход |
| `LLM_PREFETCH` | `1` | prefetch (троттлинг батчей) |
| `GROQ_API_KEY` | — (обязательно) | ключ Groq |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | модель (с function calling) |
| `LLM_TEMPERATURE` / `LLM_TIMEOUT` | `0` / `30` | параметры вызова |
| `SUITABILITY_THRESHOLD` | `60` | порог решения |
| `HTTP_HOST` / `HTTP_PORT` | `0.0.0.0` / `8000` | health-эндпоинты |
| `LOG_LEVEL` | `info` | уровень логов |

Пример — в [.env.example](.env.example). В общем стеке значения берутся из
корневого `.env`.

## Запуск

### В составе стека (рекомендуется)

Из корня репозитория (нужен `GROQ_API_KEY` в `.env`):

```bash
docker compose up -d llm
```

Health: `GET http://127.0.0.1:8000/ready` (и `/health`).

### Локально

Нужен запущенный RabbitMQ (`docker compose up -d rabbitmq`):

```bash
GROQ_API_KEY=... uv run uvicorn app.asgi:app --host 0.0.0.0 --port 8000
```

## Тесты

```bash
uv run pytest                      # прогон
uv run pytest --cov=app            # с покрытием (≥80%)
uv run ruff check app tests        # линт
uv run mypy app                    # типы
```

Messaging тестируется in-memory через `TestRabbitBroker` (реальный брокер не нужен),
Groq — через фейковый structured-раннабл (без сети).

## Подключение к «мозгу»

Когда появится сервис-оркестратор («мозг»), который сам дедуплицирует заказы и
кладёт только новые в отдельную очередь, переключение — одной переменной:

```
LLM_INPUT_QUEUE=assess.requests
```

Код менять не нужно — сервис уже stateless.
