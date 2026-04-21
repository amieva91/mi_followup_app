"""
Persistencia del estado de onboarding guiado del Dashboard.

Guarda qué hitos ya fueron notificados al usuario para no repetir popups.
"""
from datetime import datetime

from app import db


class DashboardOnboardingState(db.Model):
    __tablename__ = "dashboard_onboarding_states"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    notified_milestones = db.Column(db.JSON, nullable=False, default=list)
    last_notified_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get_or_create(user_id: int) -> "DashboardOnboardingState":
        row = DashboardOnboardingState.query.filter_by(user_id=user_id).first()
        if row:
            return row
        row = DashboardOnboardingState(user_id=user_id, notified_milestones=[])
        db.session.add(row)
        db.session.commit()
        return row

