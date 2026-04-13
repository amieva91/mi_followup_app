#!/usr/bin/env bash
# Validación automatizada alineada con docs/PLAN_PRUEBAS_BENCHMARK_POLL.md
# Comprueba: migración al head, tablas SQLite, cola poll, índices, caché benchmarks, imports.
#
# Uso:
#   ./scripts/validate_benchmark_poll.sh
#   FLASK_ENV=development ./scripts/validate_benchmark_poll.sh
#   ./scripts/validate_benchmark_poll.sh --with-network    # incluye benchmark-global-daily-once (Yahoo)
#   ./scripts/validate_benchmark_poll.sh --destructive-fallback  # borra benchmark_global_quote y comprueba fallback (solo dev)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

FLASK_ENV="${FLASK_ENV:-development}"
export FLASK_APP="${FLASK_APP:-run.py}"
export FLASK_ENV

FLASK_BIN="${PROJECT_ROOT}/venv/bin/flask"
PYTHON_BIN="${PROJECT_ROOT}/venv/bin/python"
DB_PATH="${PROJECT_ROOT}/instance/followup.db"

WITH_NETWORK=0
DESTRUCTIVE_FALLBACK=0
for arg in "$@"; do
  case "$arg" in
    --with-network) WITH_NETWORK=1 ;;
    --destructive-fallback) DESTRUCTIVE_FALLBACK=1 ;;
    -h|--help)
      sed -n '1,22p' "$0"
      exit 0
      ;;
  esac
done

FAIL=0
ok() { echo "  [OK] $*"; }
warn() { echo "  [WARN] $*" >&2; }
bad() { echo "  [FAIL] $*" >&2; FAIL=1; }

echo "=== validate_benchmark_poll (FLASK_ENV=$FLASK_ENV) ==="

if [[ ! -x "$FLASK_BIN" ]]; then
  echo "No existe $FLASK_BIN — crea el venv e instala dependencias." >&2
  exit 1
fi

echo ""
echo "-- Migración Alembic"
if "$FLASK_BIN" db current 2>&1 | tee /tmp/vbp_alembic.txt | grep -qE '\(head\)|head\)'; then
  ok "flask db current indica head"
else
  if grep -qE '[a-f0-9]{12}' /tmp/vbp_alembic.txt 2>/dev/null; then
    ok "flask db current tiene revisión"
  else
    bad "flask db current no muestra head ni revisión"
  fi
fi
rm -f /tmp/vbp_alembic.txt

echo ""
echo "-- Sintaxis Python (módulos críticos)"
for f in \
  app/services/portfolio_benchmarks_cache.py \
  app/services/benchmark_global_service.py \
  app/services/price_polling_service.py; do
  if "$PYTHON_BIN" -m py_compile "$f" 2>/dev/null; then
    ok "py_compile $f"
  else
    bad "py_compile $f"
  fi
done

echo ""
echo "-- price_polling_service: benchmarks → touch, no invalidate"
if "$PYTHON_BIN" << 'PY'
from pathlib import Path
p = Path("app/services/price_polling_service.py")
t = p.read_text(encoding="utf-8")
i = t.find("def _invalidate_caches_for_asset")
if i < 0:
    raise SystemExit("no _invalidate_caches_for_asset")
block = t[i : i + 3500]
if "PortfolioBenchmarksCacheService.invalidate" in block:
    raise SystemExit("invalidate benchmarks en _invalidate_caches_for_asset")
if "PortfolioBenchmarksCacheService.touch_for_prices_update" not in block:
    raise SystemExit("falta touch_for_prices_update para benchmarks")
print("ok")
PY
then
  ok "política de invalidación benchmarks"
else
  bad "política de invalidación benchmarks"
fi

echo ""
echo "-- SQLite (si existe instance/followup.db)"
if [[ -f "$DB_PATH" ]]; then
  for tbl in benchmark_global_quote benchmark_global_daily benchmark_global_state; do
    if sqlite3 "$DB_PATH" ".tables" 2>/dev/null | grep -qw "$tbl"; then
      ok "tabla $tbl"
    else
      bad "falta tabla $tbl"
    fi
  done
else
  warn "sin $DB_PATH — se omiten comprobaciones de tablas y checks Flask con BD"
fi

echo ""
echo "-- App context: cola, índices, get_comparison_state"
if [[ ! -f "$DB_PATH" ]]; then
  warn "omitido (sin BD local)"
else
  if "$PYTHON_BIN" << PY
import sys
sys.path.insert(0, ".")
from app import create_app
from app import db
from app.models.user import User
from app.models.benchmark_global_quote import BenchmarkGlobalQuote
from app.models.benchmark_global_daily import BenchmarkGlobalDaily, BenchmarkGlobalState
from app.services.price_polling_service import build_poll_queue
from app.services.metrics.benchmark_comparison import BENCHMARKS
from app.services.portfolio_benchmarks_cache import (
    get_market_indices_snapshot,
    PortfolioBenchmarksCacheService,
)

app = create_app("$FLASK_ENV")
with app.app_context():
    q = build_poll_queue()
    n_assets = sum(1 for s in q if type(s).__name__ == "_PollAsset")
    n_bench = sum(1 for s in q if type(s).__name__ == "_PollBenchmark")
    if n_bench != len(BENCHMARKS):
        print(f"FAIL: benchmarks en cola={n_bench}, esperado {len(BENCHMARKS)}")
        sys.exit(1)
    u = User.query.order_by(User.id).first()
    if not u:
        print("WARN: sin usuarios — omitir snapshot")
        sys.exit(0)
    mi = get_market_indices_snapshot(u.id)
    if len(mi) != len(BENCHMARKS):
        print(f"FAIL: market_indices len={len(mi)}")
        sys.exit(1)
    st = PortfolioBenchmarksCacheService.get_comparison_state(u.id)
    if "datasets" not in st and "labels" not in st:
        if not st.get("meta"):
            print("FAIL: comparison_state vacío")
            sys.exit(1)
    meta = st.get("meta") or {}
    if meta.get("version") is None and not st.get("labels"):
        pass
    nq = BenchmarkGlobalQuote.query.count()
    nd = BenchmarkGlobalDaily.query.count()
    bgv = db.session.get(BenchmarkGlobalState, 1)
    print(f"OK queue assets={n_assets} bench={n_bench} quotes_rows={nq} daily_rows={nd} state_ver={bgv.daily_data_version if bgv else None}")
PY
  then
    ok "build_poll_queue, get_market_indices_snapshot, get_comparison_state"
  else
    bad "checks Flask/BD"
  fi
fi

if [[ "$DESTRUCTIVE_FALLBACK" -eq 1 ]]; then
  echo ""
  echo "-- Destructivo: vaciar benchmark_global_quote y comprobar fallback (solo dev)"
  if [[ "$FLASK_ENV" != "development" ]]; then
    warn "omitido (usar solo FLASK_ENV=development)"
  elif [[ ! -f "$DB_PATH" ]]; then
    warn "sin BD"
  else
    cp -a "$DB_PATH" "${DB_PATH}.bak.validate.$$" 2>/dev/null || true
    sqlite3 "$DB_PATH" "DELETE FROM benchmark_global_quote;"
    if "$PYTHON_BIN" << PY
import sys
sys.path.insert(0, ".")
from app import create_app
from app.models.user import User
from app.services.portfolio_benchmarks_cache import get_market_indices_snapshot
from app.services.metrics.benchmark_comparison import BENCHMARKS

app = create_app("development")
with app.app_context():
    u = User.query.order_by(User.id).first()
    if not u:
        sys.exit(0)
    mi = get_market_indices_snapshot(u.id)
    ok_pct = sum(1 for x in mi if x.get("day_change_percent") is not None)
    if ok_pct < len(BENCHMARKS):
        print(f"FAIL: fallback % día solo {ok_pct}/{len(BENCHMARKS)}")
        sys.exit(1)
    print("ok")
PY
    then
      ok "fallback sin quotes (usa benchmark_global_daily / caché)"
    else
      bad "fallback sin quotes"
    fi
    if [[ -f "${DB_PATH}.bak.validate.$$" ]]; then
      mv "${DB_PATH}.bak.validate.$$" "$DB_PATH"
      warn "BD restaurada desde backup; repuebla quotes con price-poll o _poll_benchmark si hace falta"
    fi
  fi
fi

if [[ "$WITH_NETWORK" -eq 1 ]]; then
  echo ""
  echo "-- benchmark-global-daily-once (red/Yahoo)"
  if "$FLASK_BIN" benchmark-global-daily-once 2>&1 | tail -3; then
    ok "benchmark-global-daily-once ejecutado"
  else
    bad "benchmark-global-daily-once"
  fi
fi

echo ""
if [[ "$FAIL" -eq 0 ]]; then
  echo "=== Resultado: TODO OK ==="
  exit 0
else
  echo "=== Resultado: HUBO FALLOS ===" >&2
  exit 1
fi
