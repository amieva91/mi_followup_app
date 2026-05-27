#!/usr/bin/env bash
# Inventario: scripts/README_CRONS.md
#
# Cron diario a las 07:00 UTC: snapshot Euribor 12M (BCE) en interest_rate_context_snapshots.
#
# Uso:
#   ./scripts/install_interest_rate_context_cron.sh
#   ./scripts/install_interest_rate_context_cron.sh --dev
#   ./scripts/install_interest_rate_context_cron.sh --dry-run
#   ./scripts/install_interest_rate_context_cron.sh --remove
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MARKER="followup-interest-rate-context"
CRON_TAG="# ${MARKER}"

DRY_RUN=0
REMOVE=0
FLASK_ENV_CRON="production"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --remove) REMOVE=1 ;;
    --dev) FLASK_ENV_CRON="development" ;;
    -h|--help)
      sed -n '1,12p' "$0"
      exit 0
      ;;
  esac
done

LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/interest_rate_context_cron.log"

PYTHON_BIN="${PROJECT_ROOT}/venv/bin/python"
REFRESH_SCRIPT="${PROJECT_ROOT}/scripts/refresh_interest_rate_context_snapshot.py"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Error: no existe ${PYTHON_BIN} (ejecutable)." >&2
  exit 1
fi
if [[ ! -f "$REFRESH_SCRIPT" ]]; then
  echo "Error: no existe ${REFRESH_SCRIPT}." >&2
  exit 1
fi

LOCK_FILE="${PROJECT_ROOT}/instance/interest_rate_context_cron.flock"
CRON_LINE="0 7 * * * cd \"${PROJECT_ROOT}\" && mkdir -p \"${PROJECT_ROOT}/instance\" && flock -n \"${LOCK_FILE}\" -c 'FLASK_APP=run.py FLASK_ENV=${FLASK_ENV_CRON} \"${PYTHON_BIN}\" scripts/refresh_interest_rate_context_snapshot.py' >> \"${LOG_FILE}\" 2>&1 ${CRON_TAG}"

cron_daemon_running() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl is-active --quiet cron 2>/dev/null && return 0
    systemctl is-active --quiet crond 2>/dev/null && return 0
  fi
  pgrep -x cron >/dev/null 2>&1 && return 0
  pgrep -x crond >/dev/null 2>&1 && return 0
  return 1
}

ensure_cron_daemon() {
  if cron_daemon_running; then
    echo "Demonio cron: activo."
    return 0
  fi
  echo "Demonio cron: no activo (comprueba systemctl status cron)." >&2
  return 1
}

if [[ "$REMOVE" -eq 1 ]]; then
  echo "Quitando entrada de cron (${MARKER})..."
  TMP="$(mktemp)"
  crontab -l 2>/dev/null | grep -vF "${CRON_TAG}" > "$TMP" || true
  if [[ "$DRY_RUN" -eq 1 ]]; then
    cat "$TMP"
    rm -f "$TMP"
    exit 0
  fi
  if [[ ! -s "$TMP" ]]; then
    rm -f "$TMP"
    crontab -r 2>/dev/null || true
    echo "Crontab vacío."
  else
    crontab "$TMP"
    rm -f "$TMP"
    echo "Entrada eliminada."
  fi
  exit 0
fi

echo "Proyecto: ${PROJECT_ROOT}"
echo "Horario:  07:00 UTC cada día"
echo "Log:      ${LOG_FILE}"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "$CRON_LINE"
  exit 0
fi

TMP="$(mktemp)"
crontab -l 2>/dev/null | grep -vF "${CRON_TAG}" > "$TMP" || true
echo "$CRON_LINE" >> "$TMP"
crontab "$TMP"
rm -f "$TMP"

echo "Cron interest-rate-context instalado (07:00 UTC). crontab -l"
ensure_cron_daemon || true
