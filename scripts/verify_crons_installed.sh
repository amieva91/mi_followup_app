#!/usr/bin/env bash
# Comprueba que el crontab del usuario actual incluye las entradas de FollowUp.
# No modifica crontab ni ejecuta los jobs.
#
# Uso (producción):
#   sudo -u followup bash -lc 'cd /var/www/followup && ./scripts/verify_crons_installed.sh'
#
set -euo pipefail

# Marcadores (# followup-...) definidos en install_*_cron.sh
EXPECTED_MARKERS=(
  followup-price-poll-one
  followup-cache-rebuild-worker-0s
  followup-cache-rebuild-worker-30s
  followup-benchmark-global-daily
  followup-analyst-consensus-refresh
  followup-global-strategy-macro-daily
  followup-interest-rate-context
)

CRON_USER="${USER:-unknown}"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

if ! crontab -l 2>/dev/null >"$TMP"; then
  echo "ERROR: no hay crontab para el usuario ${CRON_USER}." >&2
  exit 1
fi

MISSING=0
EXTRA_FOLLOWUP=0

echo "Usuario crontab: ${CRON_USER}"
echo ""

for marker in "${EXPECTED_MARKERS[@]}"; do
  if grep -qF "# ${marker}" "$TMP"; then
    echo "OK   # ${marker}"
  else
    echo "FALTA # ${marker}"
    MISSING=$((MISSING + 1))
  fi
done

echo ""
echo "--- Líneas FollowUp en crontab ---"
grep -F '# followup-' "$TMP" || echo "(ninguna)"

# Entradas followup en crontab que no están en la lista esperada
while IFS= read -r line; do
  tag="${line##*# }"
  found=0
  for marker in "${EXPECTED_MARKERS[@]}"; do
    if [[ "$tag" == "$marker" ]]; then
      found=1
      break
    fi
  done
  if [[ "$found" -eq 0 ]]; then
    echo ""
    echo "AVISO: marcador followup no catalogado: # ${tag}"
    EXTRA_FOLLOWUP=$((EXTRA_FOLLOWUP + 1))
  fi
done < <(grep -F '# followup-' "$TMP" || true)

echo ""
if [[ "$MISSING" -eq 0 ]]; then
  echo "Resultado: todas las entradas esperadas están presentes."
  exit 0
fi

echo "Resultado: faltan ${MISSING} entrada(s) esperada(s)." >&2
exit 1
