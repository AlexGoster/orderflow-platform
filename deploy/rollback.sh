#!/usr/bin/env bash
#
# Откат на предыдущий релиз (файл .release-previous) или на явный TARGET_TAG.
#
# Вручную: SSH_HOST=10.0.0.5 TARGET_TAG=v1.3.9 bash deploy/rollback.sh
set -euo pipefail

source "$(dirname "$0")/lib.sh"

main() {
  local target="${TARGET_TAG:-}"

  if [ -z "$target" ]; then
    target="$(remote "cat '${REMOTE_DIR}/.release-previous' 2>/dev/null || true")"
  fi
  [ -n "$target" ] || fail "no target tag: pass TARGET_TAG or create .release-previous"

  RELEASE_TAG="$target"
  log "rollback ${SSH_USER}@${SSH_HOST}:${REMOTE_DIR} -> ${RELEASE_TAG}"

  log "1/3 — pull previous image"
  compose pull api

  log "2/3 — restart stack"
  compose up -d --remove-orphans

  log "3/3 — health check ${HEALTH_URL}"
  if wait_healthy; then
    remote "printf '%s\n' '${RELEASE_TAG}' > '${REMOTE_DIR}/.release-version'"
    compose ps
    log "rollback to ${RELEASE_TAG} finished"
    return 0
  fi

  compose logs --tail=100 api || true
  fail "rollback to ${RELEASE_TAG} is not healthy — manual intervention required"
}

main "$@"
