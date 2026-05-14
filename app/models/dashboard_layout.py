"""
Persistencia del layout (orden) del Dashboard global (/dashboard) por usuario.

NOTA: La visibilidad de tarjetas se decide por módulos/datos; aquí solo guardamos orden+lane.
"""
from datetime import datetime

from app import db

# Tarjeta fija ancho completo (carril wide); no debe persistirse en normal/tail.
_GLOBAL_STRATEGY_CARD_ID = "global_strategy"


def normalize_dashboard_layout_lanes(
    wide: list[str],
    tail: list[str],
    normal: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """
    Garantiza que la tarjeta de estrategia global solo exista en el carril `wide`.
    Si faltaba en wide (p. ej. layout antiguo), la inserta tras `health_score` o `evolution_chart`.
    """
    w = [x for x in (wide or []) if isinstance(x, str) and x.strip()]
    t = [x for x in (tail or []) if isinstance(x, str) and x.strip()]
    n = [x for x in (normal or []) if isinstance(x, str) and x.strip()]
    cid = _GLOBAL_STRATEGY_CARD_ID
    t = [x for x in t if x != cid]
    n = [x for x in n if x != cid]
    w = [x for x in w if x != cid]
    insert_at = len(w)
    for anchor in ("health_score", "evolution_chart"):
        if anchor in w:
            insert_at = w.index(anchor) + 1
            break
    w.insert(insert_at, cid)

    def _dedupe(seq: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for x in seq:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

    return _dedupe(w), _dedupe(t), _dedupe(n)


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
        w, t, n = normalize_dashboard_layout_lanes(out["wide"], out["tail"], out["normal"])
        out["wide"], out["tail"], out["normal"] = w, t, n
        return out

