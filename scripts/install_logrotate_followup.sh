#!/usr/bin/env bash
# Instala reglas de logrotate para /var/www/followup/logs/*.log (producción).
# Evita que price_poll_cron.log, cache_rebuild_worker.log, followup.log, etc. llenen el disco.
#
# Requiere: sudo (escribe /etc/logrotate.d/followup)
#
# Uso:
#   sudo ./scripts/install_logrotate_followup.sh
#   APP_DIR=/var/www/followup sudo ./scripts/install_logrotate_followup.sh
#   ./scripts/install_logrotate_followup.sh --dry-run   # solo muestra el bloque
#
# Tras instalar, comprobar sintaxis:
#   sudo logrotate -d /etc/logrotate.d/followup
# Forzar una rotación (cuidado en producción):
#   sudo logrotate -f /etc/logrotate.d/followup

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${APP_DIR:-/var/www/followup}"
LOG_GLOB="${APP_DIR}/logs/*.log"

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) sed -n '1,22p' "$0"; exit 0 ;;
  esac
done

# Rotación por tamaño o cada día; conservar 10 copias comprimidas; copytruncate para procesos
# que mantienen el descriptor abierto (Gunicorn / redirecciones cron).
BLOCK=$(cat <<EOF
${LOG_GLOB} {
    su followup followup
    daily
    maxsize 50M
    rotate 10
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
EOF
)

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "$BLOCK"
  exit 0
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Ejecuta con sudo: sudo $0" >&2
  exit 1
fi

printf '%s\n' "$BLOCK" > /etc/logrotate.d/followup
chmod 0644 /etc/logrotate.d/followup

echo "Instalado: /etc/logrotate.d/followup"
echo "  → ${LOG_GLOB}"
echo "Comprobar: logrotate -d /etc/logrotate.d/followup"
