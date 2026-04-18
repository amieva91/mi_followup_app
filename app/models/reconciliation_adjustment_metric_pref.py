"""
Preferencia por mes: si el ajuste de reconciliación cuenta en métricas / estadísticas.
Por defecto (sin fila) = sí cuenta; el usuario puede excluir meses concretos (p. ej. arranque).
"""
from datetime import datetime

from app import db


class ReconciliationAdjustmentMetricPreference(db.Model):
    __tablename__ = "reconciliation_adjustment_metric_prefs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    include_in_metrics = db.Column(db.Boolean, nullable=False, default=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "year",
            "month",
            name="uq_recon_adj_metric_user_ym",
        ),
    )

    user = db.relationship("User", backref=db.backref("reconciliation_metric_prefs", lazy="dynamic"))

    def __repr__(self):
        return (
            f"<ReconciliationAdjustmentMetricPreference u={self.user_id} "
            f"{self.year}-{self.month:02d} include={self.include_in_metrics}>"
        )
