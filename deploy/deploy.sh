#!/usr/bin/env bash
#
# Деплой OrderFlow Platform на production-хост.
#
# CI (stage 6) передаёт: SSH_HOST, SSH_KEY_PATH, RELEASE_TAG.
# Вручную: SSH_HOST=10.0.0.5 RELEASE_TAG=v1.4.0 bash deploy/deploy.sh
set -euo pipefail

source "$(dirname "$0")/lib.sh"

RELEASE_TAG="${RELEASE_TAG:?RELEASE_TAG is required (git sha or v* tag)}"

main() {
  log "deploy ${RELEASE_TAG} -> ${SSH_USER}@${SSH_HOST}:${REMOTE_DIR}"

  command -v rsync > /dev/null 2>&1 || fail "rsync not found in PATH"
  command -v ssh > /dev/null 2>&1 || fail "ssh not found in PATH"

  local previous_tag
  previous_tag="$(remote "cat '${REMOTE_DIR}/.release-version' 2>/dev/null || true")"
  log "previous release: ${previous_tag:-<none>}"

  log "step 1/6 — rsync compose, nginx and monitoring configs"
  rsync -az --delete \
    --exclude '.git' --exclude '.env' --exclude '__pycache__' --exclude '*.pyc' \
    deploy infra observability \
    "${SSH_USER}@${SSH_HOST}:${REMOTE_DIR}/"

  log "step 2/6 — remember previous release for rollback"
  remote "if [ -f '${REMOTE_DIR}/.release-version' ]; then cp '${REMOTE_DIR}/.release-version' '${REMOTE_DIR}/.release-previous'; fi"

  log "step 3/6 — docker compose pull (${RELEASE_TAG})"
  compose pull

  log "step 4/6 — database migrations"
  compose run --rm migrate

  log "step 5/6 — docker compose up"
  compose up -d --remove-orphans

  log "step 6/6 — health check ${HEALTH_URL}"
  if wait_healthy; then
    remote "printf '%s\n' '${RELEASE_TAG}' > '${REMOTE_DIR}/.release-version'"
    compose ps
    log "deploy of ${RELEASE_TAG} finished"
    return 0
  fi

  log "health check FAILED — collecting logs and rolling back"
  compose logs --tail=100 api || true
  if [ -n "$previous_tag" ]; then
    SSH_HOST="$SSH_HOST" \
      SSH_USER="$SSH_USER" \
      SSH_KEY_PATH="$SSH_KEY_PATH" \
      REMOTE_DIR="$REMOTE_DIR" \
      TARGET_TAG="$previous_tag" \
      bash "$(dirname "$0")/rollback.sh"
  fi
  exit 1
}

main "$@"
