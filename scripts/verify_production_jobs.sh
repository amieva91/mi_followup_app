#!/usr/bin/env bash
# Comprueba que crons/systemd de producción no referencian scripts archivados
# y que los servicios críticos están activos.
#
# Uso en servidor:
#   ./scripts/verify_production_jobs.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

FAIL=0

echo "=== Verificación jobs producción ==="

echo ""
echo "--- Servicios systemd ---"
for s in followup.service followup-jobs.service nginx.service cron.service; do
  st=$(systemctl is-active "$s" 2>/dev/null || echo "unknown")
  if [[ "$st" != "active" ]]; then
    echo "  FAIL: $s → $st"
    FAIL=1
  else
    echo "  OK:   $s"
  fi
done

echo ""
echo "--- Crontab followup (comandos reales) ---"
CRON_USER="${FOLLOWUP_CRON_USER:-followup}"
if [[ "$(id -un)" == "$CRON_USER" ]]; then
  CRON_TEXT="$(crontab -l 2>/dev/null || true)"
else
  CRON_TEXT="$(crontab -l -u "$CRON_USER" 2>/dev/null || true)"
fi
if [[ -n "$CRON_TEXT" ]]; then
  echo "$CRON_TEXT" | grep -v '^#' | grep -v '^$' || true
else
  echo "  WARN: crontab $CRON_USER vacío o no accesible"
fi

echo ""
echo "--- Rutas prohibidas (scripts archivados / app/services legacy) ---"
PATTERNS=(
  'app/services/test_'
  'app/services/debug_'
  'app/services/check_'
  'app/services/analyze_'
  'app/services/clean_'
  'app/services/importer.py'
  'app/services/update_prices.py'
)

FOUND=0
UNIT_TEXT="$(systemctl cat followup.service followup-jobs.service 2>/dev/null || true)"

for pat in "${PATTERNS[@]}"; do
  if echo "$CRON_TEXT$UNIT_TEXT" | grep -qF "$pat"; then
    echo "  FAIL: referencia a $pat en cron/systemd"
    FOUND=1
    FAIL=1
  fi
done

if [[ "$FOUND" -eq 0 ]]; then
  echo "  OK: ningún cron/systemd usa scripts archivados de app/services/"
fi

echo ""
echo "--- Scripts en scripts/ usados por cron (esperado) ---"
echo "  scripts/refresh_interest_rate_context_snapshot.py (07:00 UTC)"
if [[ -f "$PROJECT_ROOT/scripts/refresh_interest_rate_context_snapshot.py" ]]; then
  echo "  OK: presente"
else
  echo "  FAIL: falta refresh_interest_rate_context_snapshot.py"
  FAIL=1
fi

echo ""
echo "--- HTTP local (Gunicorn) ---"
code="000"
for attempt in 1 2 3 4 5; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:5000/ 2>/dev/null || echo "000")
  if [[ "$code" == "200" || "$code" == "302" ]]; then
    break
  fi
  sleep 2
done
if [[ "$code" == "200" || "$code" == "302" ]]; then
  echo "  OK: :5000 → HTTP $code"
else
  echo "  FAIL: :5000 → HTTP $code (Gunicorn no responde tras reintentos)"
  FAIL=1
fi

echo ""
if [[ "$FAIL" -eq 0 ]]; then
  echo "=== Resultado: OK ==="
  exit 0
fi
echo "=== Resultado: FALLÓ (revisar arriba) ==="
exit 1
