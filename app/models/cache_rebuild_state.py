"""
Estado persistido de rebuild de cachés por usuario (HIST/NOW).

Se usa por el worker periódico para ejecutar recomputes en segundo plano
sin bloquear la request del usuario.
"""
from datetime import datetime

from app import db


class CacheRebuildState(db.Model):
    __tablename__ = "cache_rebuild_state"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # FULL domina NOW. Si pending_full_history=True, el worker puede ignorar pending_now.
    pending_full_history = db.Column(db.Boolean, nullable=False, default=False)
    pending_now = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return (
            f"<CacheRebuildState user_id={self.user_id} "
            f"full={self.pending_full_history} now={self.pending_now}>"
        )
