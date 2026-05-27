#!/usr/bin/env bash
# Instala o actualiza todos los crons de FollowUp (idempotente).
# Inventario: scripts/README_CRONS.md
#
# Uso:
#   ./scripts/install_all_crons.sh
#   ./scripts/install_all_crons.sh --dry-run
#   ./scripts/install_all_crons.sh --dev
#   ./scripts/install_all_crons.sh --remove
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for arg in "$@"; do
  case "$arg" in
    -h|--help)
      sed -n '1,14p' "$0"
      exit 0
      ;;
  esac
done

INSTALLERS=(
  install_price_poll_cron.sh
  install_cache_rebuild_cron.sh
  install_benchmark_global_cron.sh
  install_analyst_consensus_cron.sh
  install_global_strategy_macro_cron.sh
  install_interest_rate_context_cron.sh
)

for name in "${INSTALLERS[@]}"; do
  path="${SCRIPT_DIR}/${name}"
  if [[ ! -x "$path" ]]; then
    echo "Error: falta o no es ejecutable: ${path}" >&2
    exit 1
  fi
  echo "=== ${name} ==="
  bash "$path" "$@"
done

echo ""
echo "Todos los crons de FollowUp procesados. Comprueba con: crontab -l"
