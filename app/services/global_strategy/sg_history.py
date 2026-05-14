"""
Persistencia atómica de la serie diaria de SG.

Ver §6.3.1 en docs/implementaciones/global_strategy_engine.md.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app import db
from app.models.global_strategy_sg_daily import GlobalStrategySgDaily


def _weekday(d: date) -> int:
    return d.weekday()  # 0=lunes … 4=viernes


def upsert_sg_daily_atomic(
    user_id: int,
    snapshot_date: date,
    sg: float,
    *,
    s_us: float | None = None,
    s_eu: float | None = None,
    s_as: float | None = None,
    indicator_as_of: date | None = None,
    fill_weekend_from_friday: bool = False,
) -> GlobalStrategySgDaily:
    """
    Inserta o actualiza (user_id, snapshot_date) y hace **un único commit**.

    Si ``fill_weekend_from_friday`` es True y ``snapshot_date`` es viernes (laborable UTC),
    en el mismo commit escribe también sábado y domingo siguientes con el mismo SG,
    componentes e ``indicator_as_of`` (evita huecos cuando los indicadores siguen siendo
    cierre del viernes).
    """
    row = (
        GlobalStrategySgDaily.query.filter_by(
            user_id=user_id,
            snapshot_date=snapshot_date,
        ).one_or_none()
    )
    try:
        if row:
            row.sg = float(sg)
            row.s_us = s_us
            row.s_eu = s_eu
            row.s_as = s_as
            row.indicator_as_of = indicator_as_of
        else:
            row = GlobalStrategySgDaily(
                user_id=user_id,
                snapshot_date=snapshot_date,
                sg=float(sg),
                s_us=s_us,
                s_eu=s_eu,
                s_as=s_as,
                indicator_as_of=indicator_as_of,
                created_at=datetime.utcnow(),
            )
            db.session.add(row)

        if fill_weekend_from_friday and _weekday(snapshot_date) == 4:
            d0 = datetime.combine(snapshot_date, datetime.min.time())
            for delta in (1, 2):
                d = (d0 + timedelta(days=delta)).date()
                wk = GlobalStrategySgDaily.query.filter_by(user_id=user_id, snapshot_date=d).one_or_none()
                if wk:
                    wk.sg = row.sg
                    wk.s_us = row.s_us
                    wk.s_eu = row.s_eu
                    wk.s_as = row.s_as
                    wk.indicator_as_of = row.indicator_as_of
                else:
                    db.session.add(
                        GlobalStrategySgDaily(
                            user_id=user_id,
                            snapshot_date=d,
                            sg=row.sg,
                            s_us=row.s_us,
                            s_eu=row.s_eu,
                            s_as=row.s_as,
                            indicator_as_of=row.indicator_as_of,
                            created_at=datetime.utcnow(),
                        )
                    )

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return row
