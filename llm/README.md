# llm

Stateless-сервис-оценщик: звено между сервисом-«core» (`order-core-service`) и
оценкой заявок profi.ru через LLM. Читает заказы из очереди `assess.requests` (их
шлёт «core», уже отдедупленные), оценивает соответствие профилю исполнителя и кладёт
вердикт с готовым уведомлением в `assess.results`. Решение «слать в Telegram» и
публикацию в `notifications` делает «core».

```
[core] ─assess.requests→ [ llm: оценка ] ─assess.results→ [core] ─notify→ [notifications] → Telegram
                              │
                     DeepInfra (OpenAI-совместимый API, structured output)
```

## Что делает

1. Читает заказ из очереди `assess.requests` (конверт — та же snake_case-форма
   `ParseResult`, что шлёт `parser-worker`; «core» форвардит в неё каждый новый заказ).
2. Через LLM извлекает требования заказа и оценивает соответствие профилю (0–100),
   помечает неподдерживаемые навыки и нежелательные типы заказов.
3. Применяет доменную политику: жёсткие фильтры (unsupported/rejected) важнее балла,
   иначе сравнение с порогом `ASSESSMENT__SUITABILITY_THRESHOLD`.
4. Для подходящих формирует готовое HTML-уведомление и публикует `AssessmentResult`
   в `assess.results` — дальше решает «core».

## Поведение

- **Stateless, без дедупа и без прямой связи с сервисом Telegram.** Дедуп и новизну
  держит «core», финальную отправку — `notifications`; `llm` — чистый оценщик.
- **Только подходящие** попадают в `assess.results`; неподходящие логируются и не идут дальше.
- **Best-effort по заказу.** Транзиентный сбой (429/5xx/сеть) не роняет обработку —
  заказ уходит в retry-очередь на отложенный повтор. Постоянный сбой логируется и
  глотается (повтор не поможет). Нераспарсиваемый конверт reject'ится в DLQ.

## Модель оценки

Оценку делает LLM через OpenAI-совместимый эндпоинт (по умолчанию
[DeepInfra](https://deepinfra.com)), подключённый LangChain-адаптером
`ChatOpenAI` со [structured output](https://python.langchain.com/docs/how_to/structured_output/).
Модель получает профиль исполнителя и текст заказа, а возвращает строго
структурированный вердикт: балл, обнаруженные навыки, попадания в «не поддерживаем»,
флаг нежелательного типа и краткое резюме.

Профиль исполнителя (сильные/рабочие/неподдерживаемые навыки, типы проектов, опыт
интеграций и инфраструктуры) задан в
[`app/infrastructure/config/profile.py`](app/infrastructure/config/profile.py). Он
питает и промпт модели, и доменную политику решения.

> Reasoning-модели (Qwen3 и др.): «мышление» выключено (`LLM__ENABLE_THINKING=false`),
> иначе блок `<think>` съедает токены до JSON и ответ обрезается. Для задачи-классификации
> оно не нужно.

## Контракты

### Вход — `assess.requests` (`ParseResultMessage`)

Default exchange (routing key = имя очереди), snake_case. Конверт — заказ (или батч
заказов) в форме `parser-worker`: `id`, `title`, `description`, `price`
(`{prefix, value, suffix}`), `geo`, `client.tags`, `score` (релевантность profi.ru —
это **не** наша оценка) и др.

### Выход — `assess.results` (`AssessmentResultMessage`)

Durable-очередь (persist). Вердикт с готовым Telegram-уведомлением внутри (вложенный
объект — camelCase-контракт TS-сервиса `notifications`):

```jsonc
{
  "order_id": "91668753",
  "suitability_score": 90,
  "notification": { "text": "…", "parseMode": "HTML", "disableWebPagePreview": true }
}
```

`notification.text` (≤ 4096 символов) собирается из: заголовка-ссылки на заказ
(`https://profi.ru/backoffice/n.php?o=<id>`), краткого описания от модели, бюджета
(если есть) и балла соответствия.

## Топология RabbitMQ

Всё на default exchange (routing key = имя очереди):

- **Вход** `assess.requests` — durable; непойманное dead-letter'ится в `assess.requests.dlq`.
- **Retry** `assess.requests.retry` — держит заказ `MESSAGING__RETRY_TTL_MS` мс, затем
  по TTL dead-letter'ит обратно во входную очередь (отложенный повтор — заказ не теряется).
- **DLQ** `assess.requests.dlq` — нераспарсиваемые конверты (`REJECT_ON_ERROR`, не крутятся
  в hot-loop).
- **Выход** `assess.results` — durable, publish с `persist`.

Короткие rate-limit'ы ретраит сам LLM-клиент (`LLM__MAX_RETRIES`); устойчивые
транзиентные сбои — retry-очередь.

## Архитектура (Clean Architecture)

```
app/
├── domain/            # заявка, профиль, оценка, решение, уведомление, результат
├── application/       # порты (LlmAssessor, ResultPublisher, Logger) + сценарий
├── infrastructure/    # config, llm (LangChain/OpenAI), messaging (RabbitMQ), observability
├── main.py            # composition root (build_app)
└── asgi.py            # точка входа: uvicorn app.asgi:app
```

Зависимости направлены внутрь; подписчик — Humble Object; LLM и RabbitMQ — детали во
внешнем кольце. Wire-схема модели в домен не течёт.

## Конфигурация

Настройки сгруппированы по внешним системам, каждая группа читает свой префикс
`GROUP__` (вложенный `Settings`, `get_settings()`).

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `RABBITMQ__HOST` / `RABBITMQ__PORT` | `localhost` / `5672` | адрес RabbitMQ |
| `RABBITMQ__USERNAME` / `RABBITMQ__PASSWORD` | `guest` / `guest` | доступ к RabbitMQ |
| `RABBITMQ__VHOST` | `/` | virtual host |
| `LLM__API_KEY` | — (обязательно) | ключ OpenAI-совместимого провайдера (DeepInfra) |
| `LLM__MODEL` | `Qwen/Qwen3-32B` | модель оценки |
| `LLM__BASE_URL` | `https://api.deepinfra.com/v1/openai` | эндпоинт провайдера |
| `LLM__TEMPERATURE` / `LLM__MAX_TOKENS` | `0` / `2048` | параметры вызова |
| `LLM__TIMEOUT` / `LLM__MAX_RETRIES` | `60` / `3` | таймаут (сек) и ретраи клиента |
| `LLM__SERVICE_TIER` | `flex` | tier запроса (DeepInfra) |
| `LLM__ENABLE_THINKING` | `false` | «мышление» reasoning-моделей |
| `MESSAGING__INPUT_QUEUE` | `assess.requests` | вход (от «core») |
| `MESSAGING__RESULT_QUEUE` | `assess.results` | выход (в «core») |
| `MESSAGING__PREFETCH` | `1` | prefetch (троттлинг) |
| `MESSAGING__RETRY_TTL_MS` | `15000` | задержка в retry-очереди |
| `ASSESSMENT__SUITABILITY_THRESHOLD` | `60` | порог решения (0–100) |
| `LOG_LEVEL` | `info` | уровень логов |

Пример — в [.env.example](.env.example). В общем стеке значения берутся из корневого `.env`.

## Запуск

### В составе стека (рекомендуется)

Из корня репозитория (нужен `LLM__API_KEY` в `.env`):

```bash
docker compose up -d llm
```

Порт наружу не публикуется — статус смотри в `docker compose ps` (контейнерный
healthcheck пингует `/ready`). Полезную работу сервис начнёт, когда «core» будет
класть заказы в `assess.requests`.

### Локально

Нужен запущенный RabbitMQ (`docker compose up -d rabbitmq`):

```bash
LLM__API_KEY=... uv run uvicorn app.asgi:app --host 0.0.0.0 --port 8000
```

Health: `GET http://127.0.0.1:8000/ready` (и `/health`) — оба пингуют брокер.

## Тесты

```bash
uv run pytest                      # прогон
uv run pytest --cov=app            # с покрытием (≥80%)
uv run ruff check app tests        # линт
uv run mypy app                    # типы
```

Messaging тестируется in-memory через `TestRabbitBroker` (реальный брокер не нужен),
LLM — через фейковый structured-раннабл (без сети).
