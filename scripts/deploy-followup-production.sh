#!/usr/bin/env bash
# Despliega el último código de main en la VM FollowUp (GCP):
#   git pull como usuario followup + restart del servicio Gunicorn.
#
# Requisitos: gcloud instalado, autenticado, y acceso SSH a la instancia
# (mismo proyecto/zona que connect-gcp.sh).
#
# Uso:
#   ./scripts/deploy-followup-production.sh
#   ./scripts/deploy-followup-production.sh --no-restart   # solo pull
#
set -euo pipefail

PROJECT="gen-lang-client-0658912226"
INSTANCE="followup"
ZONE="us-central1-c"
APP_DIR="/var/www/followup"

RESTART=1
for arg in "$@"; do
  case "$arg" in
    --no-restart) RESTART=0 ;;
    -h|--help)
      sed -n '1,18p' "$0"
      exit 0
      ;;
  esac
done

gcloud config set project "$PROJECT" >/dev/null

echo "=== Despliegue: ${INSTANCE} (${ZONE}) → ${APP_DIR} ==="

if [ "$RESTART" -eq 1 ]; then
  gcloud compute ssh "$INSTANCE" --zone="$ZONE" \
    --command="sudo -u followup git -C ${APP_DIR} pull origin main && sudo systemctl restart followup && sleep 1 && sudo systemctl is-active followup && echo 'Listo: código actualizado y followup reiniciado.'"
else
  gcloud compute ssh "$INSTANCE" --zone="$ZONE" \
    --command="sudo -u followup git -C ${APP_DIR} pull origin main && echo 'Listo: solo git pull (sin restart).'"
fi
