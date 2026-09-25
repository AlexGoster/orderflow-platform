# Runbook OrderFlow Platform

Эксплуатационная памятка дежурного. Порядок действий: **сначала диагностика, потом
лечение**. Все команды выполняются на прод-хосте (см. `deploy/inventory.example.ini`),
переменные окружения — в `.env` рядом с `docker-compose.prod.yml`.

```bash
# 0. Общая диагностика — 30 секунд
docker compose -f /opt/orderflow/docker-compose.prod.yml ps
curl -fsS https://orderflow.example.com/health      # liveness
curl -sS  https://orderflow.example.com/ready       # readiness (БД)
curl -fsS http://127.0.0.1:8000/metrics | head -50  # метрики напрямую
docker compose -f .../docker-compose.prod.yml logs --tail=200 api
```

Полезные фильтры логов (JSON): `jq 'select(.level=="ERROR")'`, поиск по
`request_id` из ответа клиенту — этот же id есть в Sentry.

---

## 1. Высокая ошибка или просадка p95

**Алерты:** `HighErrorRate` (critical, 5% 5xx / 5 мин), `HighP95Latency`
(warning, p95 > 200 мс / 10 мин).

**Диагностика**

1. Grafana → *API Overview*: смотрим `Requests by status` — это **5xx** или **4xx**?
   4xx = проблема клиента, 5xx = наша.
2. Совпадает ли начало всплеска со временем последнего релиза (`gh release list`,
   панель Traffic)? Если да — почти наверняка регрессия в релизе.
3. `curl -sS .../ready` → `checks.database` = `down`? Перейти к §3.
4. Последние ошибки: `docker compose logs --since=15m api | grep -E '"level": ?"(ERROR|WARNING)"'`.
5. Латентность: панель Latency — p50 в норме, а p95 взлетел = узкий круг запросов
   (медленный SQL, N+1); p50 тоже взлетел = проблема в БД или сети.
6. Нагрузка: `docker stats --no-stream`, в PostgreSQL `SELECT count(*) FROM pg_stat_activity;`.

**Лечение**

```bash
# после подтверждения, что проблема в последнем релизе:
RELEASE_TAG=<предыдущий_тег> bash ./deploy/rollback.sh   # см. §4
```

Если релиз ни при чём — не откатываем: чиним причину (индекс, таймаут, конфиг).

**Эскалация:** critical-алерт дольше 15 минут без прогресса → SEV-2, поднимаем
владельца сервиса.

---

## 2. Упавший API

**Алерт:** `ApiDown` (critical, `up{job="api"} == 0` дольше 2 минут).

**Диагностика**

```bash
docker compose ps                       # статус api
docker compose logs --tail=200 api      # причина рестарта / стектрейс
docker inspect -f '{{json .State.Health}}' $(docker ps -qf name=api) | jq
```

Типовые причины: не прошёл healthcheck `/ready` (⇒ смотреть §3), OOM (`docker
inspect` → `OOMKilled`), падение при старте из-за миграции.

**Лечение**

```bash
docker compose up -d --force-recreate api      # мягкий рестарт
docker compose restart api                     # если только процесс завис
docker compose exec api python -c "import os; print(os.environ.get('DATABASE_URL','').split('@')[-1])"  # не выводить целиком!
```

После восстановления — проверить `curl -fsS .../health` и дождаться, что алерт
ушёл в `Resolved`. Если контейнер падает в цикле — переходить к §4 (откат).

---

## 3. База данных недоступна (`/ready` → 503)

**Симптом:** `checks.database: "down"`, API отвечает на `/health`, но не готов.

```bash
docker compose ps postgres
docker compose logs --tail=200 postgres
docker compose exec postgres pg_isready -U orderflow
docker compose exec postgres psql -U orderflow -d orderflow -c "SELECT now(), count(*) FROM pg_stat_activity;"
df -h /var/lib/docker/volumes/orderflow_postgres_data/_data   # диск?
```

**Лечение:** недостаточно места → почистить `docker system prune` (не `prune -a`
с volumes!); диск полон на уровне хоста → подключается дежурный по хостеру.
Миграции уже накатились, а контейнер не поднимается — смотреть
`docker compose run --rm migrate` с выводом, не откатывать миграции вслепую.

**Бэкап и восстановление** (выполняется вручную, см. ограничения в SECURITY.md):

```bash
docker compose exec postgres pg_dump -U orderflow -Fc orderflow > backup_$(date +%F).dump
docker compose exec -T postgres pg_restore -U orderflow -d orderflow --clean --if-exists < backup_2026-09-25.dump
```

---

## 4. Откат релиза

Откат идёт автоматически, если health-чек деплоя не прошёл (`deploy/deploy.sh`
шаг 6). Ручной запуск:

```bash
# с CI: Actions → CI → stage 6 → Re-run with old SHA, либо локально:
SSH_HOST=<host> RELEASE_TAG=<предыдущий_тег> bash deploy/rollback.sh

# проверка
cat /opt/orderflow/.release-version     # актуальный тег
cat /opt/orderflow/.release-previous    # что откатили
docker compose ps
curl -fsS https://orderflow.example.com/health
```

`rollback.sh` ставит `TARGET_TAG`, перечитывает `.env` (`IMAGE_TAG`), делает
`compose pull && compose up -d` и ждёт health-чек. Миграции **не** откатываются
автоматически: миграции обязаны быть обратно совместимыми (expand/contract) —
поэтому в `alembic/versions/` старые ревизии не удаляются.

---

## 5. Секрет попал в репозиторий

**Что делать немедленно**

1. Не пушить историю с секретом; если уже запушен — считать ключ скомпрометированным.
2. Ротировать ключ в источнике (GitHub token, пароль БД, DSN Sentry).
3. Очистить историю (`git filter-repo`), сделать **force-push только после** ревью.
4. Добавить правило в allowlist, если это была ложная тревога, и убедиться, что
   `gitleaks dir . --config security/.gitleaks.toml --exit-code 1` зелёный.
5. Постмортем: как секрет оказался в рабочем дереве, почему гейт стадии 4 не поймал.

Проверка локально:

```bash
gitleaks dir . --config security/.gitleaks.toml --redact --exit-code 1
```

---

## 6. Мониторинг молчит (Grafana/Prometheus)

```bash
docker compose ps prometheus grafana
curl -fsS http://127.0.0.1:9090/-/healthy
curl -fsS http://127.0.0.1:9090/api/v1/targets | jq '.data.activeTargets[] | {job, health}'
curl -sS http://127.0.0.1:3000/api/health
```

`health: down` у цели api → это не поломка мониторинга, а поломка API (§2).
Слишком много series / медленные запросы → уменьшить `scrape_interval` или
перенести агрегаты в recording rules.

---

## 7. Сертификат TLS

```bash
sudo certbot renew --dry-run
docker compose restart nginx
```

Просроченный сертификат = отказ в обслуживании → критический инцидент (SLO-1).
Автопродление настраивается cron-ом хостера, dry-run проверяем при каждом релизе.

---

## Чеклист дежурного после инцидента

- [ ] Алерт ушёл в `Resolved`, `/ready` отвечает 200.
- [ ] Затронутые `request_id` найдены в Sentry, ошибки сгруппированы.
- [ ] В `.release-version` записан работающий тег.
- [ ] Бюджет ошибок за 30 дней пересчитан (`docs/SLO.md` §3).
- [ ] Постмортем: таймлайн, первопричина, action items с владельцами и сроками.
- [ ] Если причина в конфиге — обновлены `rules.yml` / `alerts.yml` / `docs/SLO.md` в одном PR.
