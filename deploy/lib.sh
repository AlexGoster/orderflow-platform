#!/usr/bin/env bash
#
# Общие функции deploy.sh / rollback.sh.
# Подключение:  source "$(dirname "$0")/lib.sh"
set -euo pipefail

SSH_HOST="${SSH_HOST:?SSH_HOST is required}"
SSH_USER="${SSH_USER:-deploy}"
SSH_KEY_PATH="${SSH_KEY_PATH:-}"
REMOTE_DIR="${REMOTE_DIR:-/opt/orderflow}"
PROJECT_NAME="${PROJECT_NAME:-orderflow}"
COMPOSE_FILE="${COMPOSE_FILE:-infra/docker-compose.prod.yml}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/ready}"
HEALTH_RETRIES="${HEALTH_RETRIES:-30}"
HEALTH_INTERVAL="${HEALTH_INTERVAL:-2}"

SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)
if [ -n "$SSH_KEY_PATH" ]; then
  SSH_OPTS+=(-i "$SSH_KEY_PATH")
fi

log() {
  printf '[orderflow] %s\n' "$*"
}

fail() {
  printf '[orderflow] ERROR: %s\n' "$*" >&2
  exit 1
}

remote() {
  ssh "${SSH_OPTS[@]}" "${SSH_USER}@${SSH_HOST}" "$@"
}

# compose <аргументы docker compose>; IMAGE_TAG берётся из окружения.
compose() {
  local cmd="$*"
  remote "cd '${REMOTE_DIR}' && IMAGE_TAG='${RELEASE_TAG}' docker compose --project-directory '${REMOTE_DIR}' -f '${COMPOSE_FILE}' -p '${PROJECT_NAME}' ${cmd}"
}

# Ожидание /ready; 0 — жив, 1 — не дождались.
wait_healthy() {
  local attempt=1
  while [ "$attempt" -le "$HEALTH_RETRIES" ]; do
    if remote "curl -fsS --max-time 5 '${HEALTH_URL}'" > /dev/null 2>&1; then
      log "healthy after ${attempt} attempt(s)"
      return 0
    fi
    log "waiting for ${HEALTH_URL} (${attempt}/${HEALTH_RETRIES})"
    sleep "$HEALTH_INTERVAL"
    attempt=$((attempt + 1))
  done
  return 1
}
