#!/usr/bin/env python3
"""
Marca como fallidos los estados que alimentan la cola global de informes
(``sorted_active_queue_rows``): texto pendiente/en curso, audio encolado, entrega
todo-en-uno a medias, correo en proceso.

Tras ejecutarlo en producción conviene ``sudo systemctl restart followup.service``
para cortar hilos que sigan en memoria.

Uso (en el servidor, con venv activado):
  export FLASK_APP=run.py FLASK_ENV=production
  python scripts/clear_company_report_queue.py
  python scripts/clear_company_report_queue.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("FLASK_APP", "run.py")
os.environ.setdefault("FLASK_ENV", "production")

from sqlalchemy import text  # noqa: E402

from app import create_app, db  # noqa: E402

_MSG = (
    "Cola reiniciada manualmente. Vuelve a generar el informe o el audio si lo necesitas."
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Vaciar cola global company_reports")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo listar qué hay en cola, sin actualizar la BD",
    )
    args = parser.parse_args()

    app = create_app(os.environ.get("FLASK_ENV", "production"))
    with app.app_context():
        from app.services.company_report_queue import sorted_active_queue_rows

        before = sorted_active_queue_rows()
        ids = [x[1] for x in before]
        print(f"Activos en cola antes: {len(before)} → ids {ids}")
        if args.dry_run:
            return

        now = datetime.utcnow()
        msg = _MSG[:8000]

        r1 = db.session.execute(
            text(
                """
                UPDATE company_reports
                SET status = 'failed',
                    error_msg = :msg,
                    completed_at = :now,
                    gemini_interaction_id = NULL
                WHERE status IN ('pending', 'processing')
                """
            ),
            {"msg": msg, "now": now},
        )
        r2 = db.session.execute(
            text(
                """
                UPDATE company_reports
                SET audio_status = 'failed',
                    audio_error_msg = :msg
                WHERE audio_status IN ('queued', 'processing')
                """
            ),
            {"msg": msg},
        )
        r3 = db.session.execute(
            text(
                """
                UPDATE company_reports
                SET delivery_phase_status = 'failed'
                WHERE delivery_mode = 'full_deliver'
                  AND delivery_phase_status = 'processing'
                """
            ),
        )
        r4 = db.session.execute(
            text(
                """
                UPDATE company_reports
                SET email_status = 'failed',
                    email_error_msg = :msg
                WHERE email_status = 'processing'
                """
            ),
            {"msg": msg},
        )

        db.session.commit()

        n1 = int(getattr(r1, "rowcount", 0) or 0)
        n2 = int(getattr(r2, "rowcount", 0) or 0)
        n3 = int(getattr(r3, "rowcount", 0) or 0)
        n4 = int(getattr(r4, "rowcount", 0) or 0)
        print(
            "Filas tocadas: informe texto",
            n1,
            "audio",
            n2,
            "full_deliver",
            n3,
            "email",
            n4,
        )

        after = sorted_active_queue_rows()
        print(f"Activos en cola después: {len(after)} → ids {[x[1] for x in after]}")


if __name__ == "__main__":
    main()
