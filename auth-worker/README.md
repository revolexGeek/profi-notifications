# auth-worker

Сервис поддерживает cookies авторизации profi.ru в актуальном состоянии и
отдаёт их другим сервисам по gRPC.

## Что делает

- Читает cookies из JSON (формат экспорта браузера).
- Разбирает JWT-токен (`prfr_bo_tkn`), считает TTL.
- Когда токен близок к истечению — дёргает renew-эндпоинт profi.ru и проверяет,
  что токен реально обновился.
- Атомарно пишет свежие cookies обратно и обновляет `auth-status.json`.
- Отдаёт актуальные cookies по gRPC (`CookieService.GetCookies`).
- Крутится в цикле; при ошибках выбирает разный интервал повтора.

Renew продлевает короткоживущий токен (~10 мин), опираясь на сессию profi.ru.
Пока сессия жива — обновление идёт бесконечно. Когда сессия умирает (истёк срок,
разлогин, смена пароля, отзыв) — статус становится `requires_login`, и нужно
вручную залить свежий `cookies.json`.

## gRPC API

Пакет `auth.v1`, контракт в [`proto/auth/v1/cookies.proto`](proto/auth/v1/cookies.proto).

```proto
service CookieService {
  rpc GetCookies(GetCookiesRequest) returns (GetCookiesResponse);
}
```

`GetCookiesResponse`:
- `cookies` — структурно все cookies (name, value, domain, path, secure, …).
- `cookie_header` — готовая строка `name=value; …` для заголовка `Cookie`.
- `status` — `ok` / `requires_login`.
- `token_ttl`, `has_token` — сколько живёт токен и есть ли он.

Также поднят стандартный `grpc.health.v1.Health`: `SERVING` только когда сервис
может прямо сейчас отдать валидные cookies.

## Конфигурация

Всё через переменные окружения, все опциональны.

| Переменная | Дефолт | Назначение |
|---|---|---|
| `PROFI_GRPC_ADDR` | `127.0.0.1:50051` | адрес gRPC-сервера (в контейнере — `0.0.0.0:50051`) |
| `PROFI_COOKIE_JSON` | `./data/cookies.json` | файл cookies (вход и выход) |
| `PROFI_AUTH_STATUS` | `./data/auth-status.json` | файл статуса |
| `PROFI_COOKIE_LOCK` | `./data/cookies.lock` | файл блокировки |
| `PROFI_RENEW_URL` | `https://profi.ru/auth/token/renew/?login` | renew-эндпоинт |
| `PROFI_CHECK_INTERVAL` | `60` | период проверки, сек |
| `PROFI_REFRESH_BEFORE` | `180` | за сколько секунд до истечения обновлять |
| `PROFI_AUTH_EXPIRED_INTERVAL` | `300` | пауза при `requires_login` / `renew_failed`, сек |
| `PROFI_ERROR_INTERVAL` | `60` | пауза при сетевых/прочих ошибках, сек |
| `PROFI_REQUEST_TIMEOUT` | `30` | таймаут HTTP-запроса, сек |
| `PROFI_LOCK_TIMEOUT` | `30` | таймаут получения блокировки, сек |
| `PROFI_USER_AGENT` | Chrome UA | User-Agent для renew |
| `LOG_LEVEL` | `INFO` | `DEBUG`/`INFO`/`WARN`/`ERROR` |
| `PROFI_RUN_ONCE` | `0` | `1` — один цикл и выход |

## Запуск

### Локально

```bash
mkdir -p data
cp /путь/к/cookies.json data/
go run ./cmd/auth-worker
```

### Docker

```bash
mkdir -p data && cp /путь/к/cookies.json data/
docker compose up -d --build
docker compose ps          # STATUS должен стать (healthy)
docker compose logs -f auth-worker
```

`data/` монтируется бинд-маунтом; сюда кладёшь `cookies.json`, сюда же сервис
пишет обновлённые cookies и `auth-status.json`. Реальные cookies — секреты,
`data/` в `.gitignore` и `.dockerignore`.

## Статус авторизации

`data/auth-status.json`:

| status | смысл | действие |
|---|---|---|
| `ok` | токен свежий | — |
| `requires_login` | сессия умерла | залить свежий `cookies.json` |
| `renew_failed` | renew ответил, но не обновил токены | само ретраится |
| `network_timeout` / `network_error` | сеть | само ретраится |
| `missing_or_invalid_cookies` | нет/битый `cookies.json` | проверить файл |
| `error` | прочее (напр. 429) | само ретраится |

## Проверка gRPC

Health контейнера (без установки чего-либо):

```bash
docker inspect --format '{{.State.Health.Status}}' profi-auth-worker
```

Вызов `GetCookies` через grpcurl (reflection не включён — нужен proto):

```bash
grpcurl -plaintext -import-path proto -proto auth/v1/cookies.proto \
  127.0.0.1:50051 auth.v1.CookieService/GetCookies
```

## Использование из других сервисов

Клиент подключается к `CookieService/GetCookies`, берёт `cookie_header` и
подставляет его в заголовок `Cookie` своих HTTP-запросов. По `status`/`token_ttl`
понимает, жива ли авторизация.

## Разработка

```bash
go test ./...        # тесты
go vet ./...
gofmt -w .
buf lint             # после правок proto
buf generate         # регенерация стабов в internal/gen (нужен PATH к $GOPATH/bin)
```

Хуки (`gofmt`/`go vet`/`go test`) настроены в корневом `prek.toml` и гоняются на
каждом коммите.

## Структура

```
cmd/auth-worker/   composition root: сборка зависимостей, запуск, healthcheck
internal/
  domain/          сущности + бизнес-правила (JWT, TTL, дедуп), без I/O
  usecase/         интеракторы + порты: RefreshAuth, Worker, GetCookies
  adapter/         реализации портов: cookiefile, httprenew, statusfile,
                   filelock, grpcserver, grpcclient
  platform/        инфраструктура: atomicjson, clock, config
  gen/             сгенерированный proto-код
proto/             gRPC-контракты (auth/v1)
```

Зависимости всегда указывают внутрь: `cmd → adapter → usecase → domain`.
