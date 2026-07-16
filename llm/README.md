# llm

Stateless-сервис-оценщик: звено между сервисом-«мозгом» и оценкой заявок Profi.ru
через LLM (Groq + LangChain). Читает заказы из очереди `assess.requests` (их шлёт
«мозг», уже отдедупленные), оценивает соответствие профилю исполнителя и кладёт
вердикт с готовым уведомлением в `assess.results`. Решение «слать в Telegram» и
публикацию в `notifications` делает «мозг».

```
[мозг] ─assess.requests→ [ llm: оценка ] ─assess.results→ [мозг] ─notify→ [notifications] → Telegram
                              │
                         Groq (structured output)
```

## Что делает

1. Читает батч заказов из очереди `assess.requests` (проксирует «мозг»; форма — та
   же, что шлёт `parser-worker`).
2. Для каждого заказа через Groq извлекает требования и оценивает соответствие
   профилю (0–100) + помечает неподдерживаемые навыки и нежелательные типы заказов.
3. Доменная политика: жёсткие фильтры (unsupported/rejected) важнее балла, иначе
   сравнение с порогом `SUITABILITY_THRESHOLD`.
4. Для подходящих формирует готовое HTML-уведомление и публикует
   `AssessmentResult` в `assess.results` — дальше решает «мозг».

## Поведение

- **Stateless, без дедупа и без прямой связи с телега-сервисом.** Дедуп/новизну и
  финальную отправку в `notifications` держит «мозг»; llm — чистый оценщик.
- **Только подходящие** попадают в `assess.results`; неподходящие логируются.
- **Best-effort.** Сбой одного заказа (напр. rate limit Groq) логируется и не рушит
  батч. Нераспарсиваемый конверт уходит в `assess.requests.dlq`. Retry-очереди нет.

## Контракты

### Вход — `assess.requests` (`ParseResultMessage`)

Default exchange (routing key = имя очереди), snake_case, батч заказов. Заказ:
`id`, `title`, `description`, `price` (`{prefix, value, suffix}`), `geo`,
`client.tags`, `score` (релевантность Profi.ru — не наша оценка) и др.

### Выход — `assess.results` (`AssessmentResultMessage`)

Durable-очередь (persist). Вердикт с готовым Telegram-уведомлением внутри
(вложенный объект — camelCase-контракт TS-сервиса `notifications`):

```jsonc
{
  "order_id": "91668753",
  "suitability_score": 90,
  "notification": { "text": "…", "parseMode": "HTML", "disableWebPagePreview": true }
}
```

`notification.text` ≤ 4096: заголовок-ссылка (`https://profi.ru/backoffice/n.php?o=<id>`),
краткое описание от модели, бюджет (если есть), оценка соответствия.

## Архитектура (Clean Architecture)

```
app/
├── domain/            # заявка, профиль, оценка, решение, уведомление, результат
├── application/       # порты (LlmAssessor, ResultPublisher, Logger) + сценарий
├── infrastructure/    # config, llm (Groq), messaging (RabbitMQ), observability
├── main.py            # composition root (build_app)
└── asgi.py            # точка входа: uvicorn app.asgi:app
```

Зависимости направлены внутрь; подписчик — Humble Object; LLM/RabbitMQ/Groq —
детали во внешнем кольце.

## Конфигурация

Настройки сгруппированы по внешним системам, каждая группа читает свой префикс
`GROUP__` (вложенный `Settings`, `get_settings()`).

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `RABBITMQ__HOST` / `RABBITMQ__PORT` | `localhost` / `5672` | адрес RabbitMQ |
| `RABBITMQ__USERNAME` / `RABBITMQ__PASSWORD` | `guest` / `guest` | доступ к RabbitMQ |
| `RABBITMQ__VHOST` | `/` | virtual host |
| `MESSAGING__INPUT_QUEUE` | `assess.requests` | вход (от «мозга») |
| `MESSAGING__RESULT_QUEUE` | `assess.results` | выход (в «мозг») |
| `MESSAGING__PREFETCH` | `1` | prefetch (троттлинг батчей) |
| `GROQ__API_KEY` | — (обязательно) | ключ Groq |
| `GROQ__MODEL` | `llama-3.3-70b-versatile` | модель (с function calling) |
| `GROQ__TEMPERATURE` / `GROQ__TIMEOUT` | `0` / `30` | параметры вызова |
| `ASSESSMENT__SUITABILITY_THRESHOLD` | `60` | порог решения |
| `LOG_LEVEL` | `info` | уровень логов |

Пример — в [.env.example](.env.example). В общем стеке значения берутся из
корневого `.env`.

## Запуск

### В составе стека (рекомендуется)

Из корня репозитория (нужен `GROQ__API_KEY` в `.env`):

```bash
docker compose up -d llm
```

Health: `GET http://127.0.0.1:8000/ready` (и `/health`). Полезную работу сервис
начнёт, когда «мозг» будет класть заказы в `assess.requests`.

### Локально

Нужен запущенный RabbitMQ (`docker compose up -d rabbitmq`):

```bash
GROQ__API_KEY=... uv run uvicorn app.asgi:app --host 0.0.0.0 --port 8000
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
