# Leady — бэкенд Telegram-бота @LEADYCRM_bot

Серверная часть бота для CRM-продукта Leady: приём заявок, онбординг,
интеграция с внешним API. Модульная архитектура, деплой через Docker Compose.

## Структура

| Путь | Что |
|---|---|
| `bot/` | хендлеры и сценарии Telegram-бота |
| `api/` | REST API |
| `core/`, `botfactory/` | ядро: состояния, бизнес-логика, сборка ботов |
| `alembic` + миграции | схема PostgreSQL |
| `LEADY_BOT_FLOW.md` | зафиксированная логика главного бота (онбординг, тикеты) |
| `docker-compose.yml`, `docker/` | запуск стeka |

## Стек

Python, aiogram, FastAPI, PostgreSQL, Alembic, Docker Compose.

## Запуск

```bash
cp .env.example .env      # заполнить токены и доступы
docker compose up -d --build
```
