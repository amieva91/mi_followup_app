from __future__ import annotations

import logging


def main() -> None:
    from app import create_app
    from app.services.company_report_jobs_worker import run_forever

    logging.basicConfig(level=logging.INFO)
    app = create_app()
    run_forever(app)


if __name__ == "__main__":
    main()

