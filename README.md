# profi-notifications

По расписанию собирает доску объявлений profi.ru, прогоняет заказы через ИИ и присылает их в заданный топик Telegram.

## Что делает

1. По расписанию забирает свежие заказы с доски profi.ru.
2. Прогоняет их через ИИ: отбирает подходящие и оформляет.
3. Присылает готовые в заданный топик Telegram.

## Запуск

Нужен установленный Docker.

1. Создай файл настроек из шаблона и заполни доступы:
   ```bash
   cp .env.example .env
   ```
2. Положи свежие cookies profi.ru в `auth-worker/data/cookies.json` ([экспорт из браузера](https://chromewebstore.google.com/detail/j2team-cookies/okpidcojinmlaakglciglbpcpajaibco) после входа в аккаунт).
3. Подними сервис:
   ```bash
   docker compose up -d
   ```

Остановить: `docker compose down`.
