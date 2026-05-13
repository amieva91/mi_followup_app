from __future__ import annotations

import logging
import os

os.environ.setdefault("FOLLOWUP_IN_JOBS_WORKER", "1")


def main() -> None:
    from app import create_app
    from app.services.company_report_jobs_worker import run_forever

    logging.basicConfig(level=logging.INFO)
    app = create_app()
    run_forever(app)


if __name__ == "__main__":
    main()

