"""
Persistencia del layout (orden) del Dashboard global (/dashboard) por usuario.

NOTA: La visibilidad de tarjetas se decide por módulos/datos; aquí solo guardamos orden+lane.
"""
from datetime import datetime

from app import db


class UserDashboardLayout(db.Model):
    __tablename__ = "user_dashboard_layouts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # ID estable del DOM: data-card-id
    card_id = db.Column(db.String(80), nullable=False)

    # Carril donde se encuentra la tarjeta
    lane = db.Column(db.String(16), nullable=False)  # wide|normal|tail

    # Posición (0..n) dentro del carril
    position = db.Column(db.Integer, nullable=False, default=0)

    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "card_id", name="uq_user_dashboard_layout_user_card"),
    )

    @classmethod
    def get_layout_dict(cls, user_id: int) -> dict:
        """Orden persistido por carril; mismas claves que la API GET /dashboard/layout."""
        rows = (
            cls.query.filter_by(user_id=user_id).order_by(cls.lane.asc(), cls.position.asc()).all()
        )
        out = {"wide": [], "tail": [], "normal": []}
        for r in rows:
            lane = (r.lane or "").strip().lower()
            if lane in out:
                out[lane].append(r.card_id)
        return out

