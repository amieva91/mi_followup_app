#!/usr/bin/env python3
"""
Rellena una fila en `interest_rate_context_snapshots` (solo BCE Euribor 12M).

Cron: `./scripts/install_interest_rate_context_cron.sh` (07:00 UTC, log en
`logs/interest_rate_context_cron.log`). O todos: `./scripts/install_all_crons.sh`.

Prueba manual en la VM:
  sudo -u followup bash -lc 'cd /var/www/followup && source venv/bin/activate && export FLASK_APP=run.py && python scripts/refresh_interest_rate_context_snapshot.py'

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
            f"bce={row.bce_euribor_12m_percent} period={row.bce_time_period}"
        )
        if row.bce_fetch_error:
            print(f"bce_error={row.bce_fetch_error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
