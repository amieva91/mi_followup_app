#!/bin/bash
# Conectar a la VM FollowUp en Google Cloud
# Uso:
#   ./connect-gcp.sh              # Sesión interactiva
#   ./connect-gcp.sh "comando"    # Ejecutar comando en remoto

PROJECT="gen-lang-client-0658912226"
INSTANCE="followup"
ZONE="us-central1-c"

gcloud config set project "$PROJECT" 2>/dev/null

if [ -n "$1" ]; then
    # Ejecutar comando remoto
    gcloud compute ssh "$INSTANCE" --zone="$ZONE" --command="$*"
else
    # Sesión interactiva
    gcloud compute ssh "$INSTANCE" --zone="$ZONE"
fi
