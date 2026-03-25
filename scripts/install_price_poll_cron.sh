#!/usr/bin/env bash
# Instala o actualiza la entrada de cron para `flask price-poll-one` (1 activo/minuto).
# Idempotente: volver a ejecutar sustituye la línea anterior marcada.
#
# Uso:
#   ./scripts/install_price_poll_cron.sh              # FLASK_ENV=production en la línea cron
#   ./scripts/install_price_poll_cron.sh --dev        # FLASK_ENV=development (máquina local)
#   ./scripts/install_price_poll_cron.sh --dry-run    # solo muestra la línea, no toca crontab
#   ./scripts/install_price_poll_cron.sh --remove     # quita solo esta entrada
#
# Tras desplegar en producción: mismo script desde la raíz del proyecto (con venv y BD/config de pro).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MARKER="followup-price-poll-one"
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
      sed -n '1,20p' "$0"
      exit 0
      ;;
  esac
done

LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/price_poll_cron.log"

FLASK_BIN="${PROJECT_ROOT}/venv/bin/flask"
if [[ ! -x "$FLASK_BIN" ]]; then
  echo "Error: no existe ${FLASK_BIN} (ejecutable)." >&2
  echo "Crea el venv e instala dependencias: python -m venv venv && . venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

# Cron no carga .flaskenv: FLASK_APP y FLASK_ENV van en la línea.
CRON_LINE="* * * * * cd \"${PROJECT_ROOT}\" && FLASK_APP=run.py FLASK_ENV=${FLASK_ENV_CRON} \"${FLASK_BIN}\" price-poll-one >> \"${LOG_FILE}\" 2>&1 ${CRON_TAG}"

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

# Si hay TTY, sudo puede pedir contraseña (útil en WSL sin NOPASSWD).
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
    echo "Intentando arranque interactivo con sudo (puede pedir contraseña)..."
    if start_cron_daemon_interactive; then
      sleep 1
      if cron_daemon_running; then
        echo "Demonio cron: arrancado correctamente."
        return 0
      fi
    fi
  fi
  echo "No se pudo arrancar el demonio cron automáticamente." >&2
  echo "Arráncalo una vez: sudo service cron start   o   sudo systemctl start cron" >&2
  return 1
}

if [[ "$REMOVE" -eq 1 ]]; then
  echo "Quitando entrada de cron (${MARKER})..."
  TMP="$(mktemp)"
  crontab -l 2>/dev/null | grep -vF "${CRON_TAG}" > "$TMP" || true
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "--- crontab resultante (dry-run) ---"
    cat "$TMP"
    rm -f "$TMP"
    exit 0
  fi
  if [[ ! -s "$TMP" ]]; then
    rm -f "$TMP"
    crontab -r 2>/dev/null || true
    echo "Crontab vacío (no quedan entradas)."
  else
    crontab "$TMP"
    rm -f "$TMP"
    echo "Entrada eliminada. Crontab actualizado."
  fi
  exit 0
fi

echo "Proyecto: ${PROJECT_ROOT}"
echo "Flask:    ${FLASK_BIN}"
echo "Log:      ${LOG_FILE}"
echo "Entorno:  FLASK_ENV=${FLASK_ENV_CRON} (en la línea de cron)"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo ""
  echo "--- línea que se instalaría ---"
  echo "$CRON_LINE"
  echo ""
  echo "(En instalación real: se comprueba si el demonio cron está activo y se intenta sudo -n systemctl/service start.)"
  exit 0
fi

TMP="$(mktemp)"
crontab -l 2>/dev/null | grep -vF "${CRON_TAG}" > "$TMP" || true
echo "$CRON_LINE" >> "$TMP"
crontab "$TMP"
rm -f "$TMP"

echo ""
echo "Cron instalado. Comprueba con: crontab -l"
ensure_cron_daemon || true
