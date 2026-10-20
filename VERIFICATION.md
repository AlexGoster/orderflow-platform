# Проверка проекта

Проверки выполнялись 10–20 октября 2026. Исходная рабочая копия была чистой.

40 тестов прошли. health/ready, feature flags CRUD, метрики; Ruff/strict mypy, Bandit, проверка 13 конфигов. Docker HTTP с настоящим PostgreSQL.

Feature flag API публичен, production доступ не настраивался. Helm/Kubernetes и боевой CI/CD не разворачивались.

## Повторный запуск

Команды из папки проекта после создания и активации Python venv. Для API задайте DATABASE_URL отдельной локальной БД и тестовый SECRET_KEY по примеру конфигурации; не используйте рабочие подключения.

```bash
python -m venv .venv
# Активируйте .venv согласно ОС.
python -m pip install . -r requirements-dev.txt
python -m alembic upgrade head
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Тесты в отдельном тестовом окружении:

```bash
python -m pytest -o addopts= -q
```

Docker-проверки использовали отдельную сеть, PostgreSQL *_test и Redis; реальные данные, платежи и внешние сообщения не затрагивались. Результат локального запуска не означает production-ready.
