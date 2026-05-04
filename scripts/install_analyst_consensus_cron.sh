#!/usr/bin/env bash
# Inventario: scripts/README_CRONS.md
#
# Cron diario a las 00:00 (hora del servidor): refresco de consenso de analistas
# (quoteSummary) para activos pollables con datos vacíos o antiguos (>90 días).
#
# Uso:
#   ./scripts/install_analyst_consensus_cron.sh
#   ./scripts/install_analyst_consensus_cron.sh --dev
#   ./scripts/install_analyst_consensus_cron.sh --dry-run
#   ./scripts/install_analyst_consensus_cron.sh --remove
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MARKER="followup-analyst-consensus-refresh"
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
      sed -n '1,18p' "$0"
      exit 0
      ;;
  esac
done

LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/analyst_consensus_cron.log"

FLASK_BIN="${PROJECT_ROOT}/venv/bin/flask"
if [[ ! -x "$FLASK_BIN" ]]; then
  echo "Error: no existe ${FLASK_BIN} (ejecutable)." >&2
  exit 1
fi

LOCK_FILE="${PROJECT_ROOT}/instance/analyst_consensus_cron.flock"
CRON_LINE="0 0 * * * cd \"${PROJECT_ROOT}\" && mkdir -p \"${PROJECT_ROOT}/instance\" && flock -n \"${LOCK_FILE}\" -c 'FLASK_APP=run.py FLASK_ENV=${FLASK_ENV_CRON} \"${FLASK_BIN}\" analyst-consensus-refresh-stale' >> \"${LOG_FILE}\" 2>&1 ${CRON_TAG}"

cron_daemon_running() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl is-active --quiet cron 2>/dev/null && return 0
    systemctl is-active --quiet crond 2>/dev/null && return 0
  fi
  pgrep -x cron >/dev/null 2>&1 && return 0
  pgrep -x crond >/dev/null 2>&1 && return 0
  return 1
}

start_cron_daemon_noninteractive() {
  local ok=1
  if command -v systemctl >/dev/null 2>&1; then
    if sudo -n systemctl start cron 2>/dev/null; then ok=0; fi
    if [[ "$ok" -ne 0 ]] && sudo -n systemctl start crond 2>/dev/null; then ok=0; fi
  fi
  if [[ "$ok" -ne 0 ]] && command -v service >/dev/null 2>&1; then
    if sudo -n service cron start 2>/dev/null; then ok=0; fi
    if [[ "$ok" -ne 0 ]] && sudo -n service crond start 2>/dev/null; then ok=0; fi
  fi
  return "$ok"
}

start_cron_daemon_interactive() {
  [[ -t 0 ]] || return 1
  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl start cron 2>/dev/null && return 0
    sudo systemctl start crond 2>/dev/null && return 0
  fi
  if command -v service >/dev/null 2>&1; then
    sudo service cron start 2>/dev/null && return 0
    sudo service crond start 2>/dev/null && return 0
  fi
  return 1
}

ensure_cron_daemon() {
  if cron_daemon_running; then
    echo "Demonio cron: activo."
    return 0
  fi
  echo "Demonio cron: no activo; intentando arranque (sudo -n)..."
  if start_cron_daemon_noninteractive; then
    sleep 1
    if cron_daemon_running; then
      echo "Demonio cron: arrancado correctamente."
      return 0
    fi
  fi
  if [[ -t 0 ]]; then
    echo "Intentando arranque interactivo con sudo..."
    if start_cron_daemon_interactive; then
      sleep 1
      if cron_daemon_running; then
        echo "Demonio cron: arrancado correctamente."
        return 0
      fi
    fi
  fi
  echo "No se pudo arrancar el demonio cron automáticamente." >&2
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
echo "Horario:  00:00 cada día (hora del servidor)"
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

echo "Cron instalado. crontab -l"
ensure_cron_daemon || true
