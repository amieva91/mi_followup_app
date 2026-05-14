"""
Serie diaria de Score Global (SG) por usuario.

Una fila por (user_id, snapshot_date). indicator_as_of = fecha de cierre de los
indicadores macro usados (p. ej. viernes en fin de semana).
"""
from __future__ import annotations

from datetime import date, datetime

from app import db


class GlobalStrategySgDaily(db.Model):
    __tablename__ = "global_strategy_sg_daily"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    snapshot_date = db.Column(db.Date, nullable=False, index=True)
    sg = db.Column(db.Float, nullable=False)
    s_us = db.Column(db.Float, nullable=True)
    s_eu = db.Column(db.Float, nullable=True)
    s_as = db.Column(db.Float, nullable=True)
    indicator_as_of = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "snapshot_date", name="uq_global_strategy_sg_user_day"),
    )
