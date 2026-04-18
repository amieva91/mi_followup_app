#!/usr/bin/env python3
"""
Rellena una fila en `interest_rate_context_snapshots` (BCE Euribor 12M + Yahoo ESR=F).

Ejemplo cron (UTC servidor), una vez al día a las 07:00:
  0 7 * * * cd /var/www/followup && ./venv/bin/python scripts/refresh_interest_rate_context_snapshot.py >> /var/log/followup_interest_context.log 2>&1

Requiere migración aplicada: interest_rate_context_snapshots.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app  # noqa: E402
from app.services import interest_rate_context_service as irctx  # noqa: E402


def main() -> int:
    app = create_app()
    with app.app_context():
        row = irctx.refresh_snapshot()
        print(
            f"OK id={row.id} fetched_at={row.fetched_at.isoformat()} "
            f"bce={row.bce_euribor_12m_percent} period={row.bce_time_period} "
            f"esr_impl={row.yahoo_implied_percent} trend={row.trend_label}"
        )
        if row.bce_fetch_error:
            print(f"bce_error={row.bce_fetch_error}")
        if row.yahoo_fetch_error:
            print(f"yahoo_error={row.yahoo_fetch_error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
