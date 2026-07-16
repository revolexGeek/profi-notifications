# parser-worker

Воркер парсинга доски заказов profi.ru. Читает запросы из очереди RabbitMQ,
забирает cookies авторизации у `auth-worker` по gRPC, тянет доску заказов через
GraphQL profi.ru, маппит ответ в доменную модель и публикует результат обратно
в RabbitMQ.

```
parse.requests ─▶ parser-worker ─(gRPC GetCookies)▶ auth-worker
                       │
                       └─(GraphQL boSearchBoardItems)▶ profi.ru
                       │
                       └─▶ parse.results
```

## Архитектура

Clean Architecture, зависимости направлены внутрь
(`infrastructure → application → domain`):

- **domain** — сущности и value-объекты предметной области без I/O и фреймворков:
  `ParseRequest`, `BoardFilter`, `SortOrder`, `ParseResult`, `BoardPage`, `Order`
  (`Price`, `Geo`, `Client`, `Badge`, `Coordinates`), `AuthCookies`, `ParserError`.
- **application** — сценарий `ProcessParseRequest` и порты (трейты), через которые
  он общается с внешним миром: `CookieProvider`, `BoardSource`, `ResultPublisher`.
- **infrastructure** — адаптеры, реализующие порты:
  - `amqp` — `AmqpConsumer` / `AmqpPublisher` поверх `lapin`;
  - `auth` — `GrpcCookieProvider` (клиент `auth-worker` по gRPC, `tonic`);
  - `profi` — `ProfiBoardSource` (запрос GraphQL через `reqwest` + маппинг ответа);
  - `config`, `telemetry`.

Сценарий: получить запрос из `parse.requests` → взять cookies у `auth-worker` →
постранично (до `max_pages`) забрать доску → собрать заказы → опубликовать
`ParseResult` в `parse.results`.

## Контракт сообщений

### Вход — `parse.requests` (`ParseRequest`)

`filter` и `max_pages` необязательны (применяются значения по умолчанию).

```json
{
  "request_id": "req-1",
  "filter": {
    "search_query": "",
    "page_size": 10,
    "sort": "DEFAULT",
    "all_verticals": true,
    "use_saved_filter": true,
    "raw_filter": {}
  },
  "max_pages": 1
}
```

- `sort`: `"DEFAULT"` или `"DATE"`.
- `page_size` по умолчанию `10`, `all_verticals` и `use_saved_filter` — `true`.
- `raw_filter` — произвольный JSON-фильтр, пробрасывается в запрос доски as-is.
- `max_pages` — сколько страниц забрать (по умолчанию `1`); парсинг останавливается раньше, если следующего курсора нет.

### Выход — `parse.results` (`ParseResult`)

```json
{
  "request_id": "req-1",
  "fetched_at": 1784135987,
  "total_count": 29,
  "next_cursor": "WzgwLjA5...",
  "orders": [
    {
      "id": "91635361",
      "title": "Девопс услуги",
      "description": "...",
      "price": { "prefix": "до", "value": "700", "suffix": "" },
      "geo": {
        "remote": { "prefix": "Дистанционно", "suffix": "", "address": null },
        "order_location": null,
        "client_may_come": null
      },
      "client": { "name": "Георгий", "tags": [] },
      "badges": [{ "id": "...", "image_key": "PERCENT", "label": "Скидка на отклик" }],
      "schedule": null,
      "last_update": 1784135813,
      "score": 80.5,
      "is_fresh": false,
      "is_viewed": false,
      "coordinates": null
    }
  ]
}
```

## Конфигурация

Все параметры читаются из окружения (значения по умолчанию — в скобках):

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `PARSER_AMQP_URL` | строка подключения к RabbitMQ | `amqp://guest:guest@127.0.0.1:5672/%2f` |
| `PARSER_REQUEST_QUEUE` | очередь входящих запросов | `parse.requests` |
| `PARSER_RESULT_EXCHANGE` | exchange для результатов (пусто = default) | `` |
| `PARSER_RESULT_ROUTING_KEY` | routing key результатов | `parse.results` |
| `PARSER_PREFETCH` | prefetch (QoS) консьюмера | `8` |
| `PARSER_AUTH_GRPC_ADDR` | адрес gRPC `auth-worker` | `http://127.0.0.1:50051` |
| `PARSER_PROFI_GRAPHQL_URL` | эндпоинт GraphQL profi.ru | `https://profi.ru/graphql` |
| `LOG_LEVEL` | уровень логов (`tracing`) | `info` |

В составе стека значения приходят из корневого `.env` (см. `../docker-compose.yml`
и `../.env`).

## Запуск

### В составе стека (рекомендуется)

Из корня репозитория поднимается весь конвейер (RabbitMQ + auth-worker + parser-worker):

```bash
docker compose up -d
```

### Локально

Нужны запущенные RabbitMQ и `auth-worker`:

```bash
PARSER_AMQP_URL="amqp://profi:profi@127.0.0.1:5672/%2f" \
PARSER_AUTH_GRPC_ADDR="http://127.0.0.1:50051" \
cargo run --release
```

## Тесты

```bash
cargo test
```

Юнит-тесты используют `mockall` (моки портов), `wiremock` (HTTP profi.ru) и
`tokio-test`; маппинг GraphQL-ответа проверяется на фикстуре.

## Структура

```
src/
├── domain/           # сущности, value-объекты, ошибки (без I/O)
├── application/      # сценарий ProcessParseRequest + порты (трейты)
└── infrastructure/   # адаптеры: amqp, auth (gRPC), profi (GraphQL), config, telemetry
proto/cookies.proto   # контракт gRPC CookieService (auth-worker)
build.rs              # кодогенерация gRPC (tonic-prost-build)
```
