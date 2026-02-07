"""
Modelos para informes de compañías generados con Gemini
"""
from datetime import datetime
from app import db


class ReportSettings(db.Model):
    """
    (Legacy) Una plantilla por usuario. Sustituido por ReportTemplate.
    Se mantiene para migración.
    """
    __tablename__ = 'report_settings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True, index=True)
    description = db.Column(db.Text, nullable=True)
    points = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('report_settings', uselist=False))

    def get_points_list(self):
        import json
        if self.points:
            try:
                return json.loads(self.points)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def has_valid_description(self):
        return bool(self.description and self.description.strip())


class ReportTemplate(db.Model):
    """
    Plantilla de informe por usuario. Varias plantillas por usuario.
    Cada plantilla tiene: título, descripción, puntos.
    """
    __tablename__ = 'report_templates'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    title = db.Column(db.String(200), nullable=False)  # Nombre de la plantilla
    description = db.Column(db.Text, nullable=False)  # Descripción de la investigación
    points = db.Column(db.Text, nullable=True)  # JSON array de strings

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('report_templates', lazy=True))

    def get_points_list(self):
        import json
        if self.points:
            try:
                return json.loads(self.points)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_points_list(self, data):
        import json
        self.points = json.dumps(data) if isinstance(data, list) and data else None

    def has_valid_description(self):
        return bool(self.description and self.description.strip())


class CompanyReport(db.Model):
    """
    Informe de Deep Research generado para un asset.
    Máximo 5 por (user_id, asset_id); al generar el 6º se borra el más antiguo.
    """
    __tablename__ = 'company_reports'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False, index=True)
    template_id = db.Column(db.Integer, db.ForeignKey('report_templates.id'), nullable=True, index=True)
    template_title = db.Column(db.String(200), nullable=True)  # Nombre mostrado (denormalizado)

    content = db.Column(db.Text, nullable=True)  # Contenido del informe (Markdown)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, processing, completed, failed
    error_msg = db.Column(db.Text, nullable=True)
    gemini_interaction_id = db.Column(db.String(100), nullable=True)

    # Audio TTS resumen
    audio_path = db.Column(db.String(500), nullable=True)  # ruta al archivo WAV
    audio_status = db.Column(db.String(20), nullable=True)  # pending, processing, completed, failed
    audio_error_msg = db.Column(db.Text, nullable=True)
    audio_completed_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref=db.backref('company_reports', lazy=True))
    asset = db.relationship('Asset', backref=db.backref('company_reports', lazy=True))

    def __repr__(self):
        return f"CompanyReport(id={self.id}, user_id={self.user_id}, asset_id={self.asset_id}, status={self.status})"


class AssetAboutSummary(db.Model):
    """
    Resumen "About the Company" por usuario y asset.
    Se sobrescribe al regenerar. Se borra si el asset sale de la watchlist.
    """
    __tablename__ = 'asset_about_summary'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False, index=True)

    summary = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'asset_id', name='unique_user_asset_about_summary'),
    )

    user = db.relationship('User', backref=db.backref('asset_about_summaries', lazy=True))
    asset = db.relationship('Asset', backref=db.backref('asset_about_summaries', lazy=True))

    def __repr__(self):
        return f"AssetAboutSummary(user_id={self.user_id}, asset_id={self.asset_id})"
