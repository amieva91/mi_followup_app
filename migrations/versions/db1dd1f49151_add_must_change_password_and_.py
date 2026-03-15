"""add_must_change_password_and_administrador_user

Revision ID: db1dd1f49151
Revises: 8023fcfde247
Create Date: 2026-03-15 22:49:36.446545

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'db1dd1f49151'
down_revision = '8023fcfde247'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()))
    # Usuario administrador fijo: crear si no existe
    from app import create_app, db
    from app.models import User
    app = create_app()
    with app.app_context():
        if User.query.filter_by(username='administrador').first() is None:
            password = app.config.get('ADMIN_INITIAL_PASSWORD', 'CambiarPassword1!')
            admin = User(
                username='administrador',
                email='followup.fit@gmail.com',
                is_active=True,
                is_admin=True,
                must_change_password=True,
            )
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()


def downgrade():
    op.drop_column('users', 'must_change_password')
    # No eliminamos el usuario administrador (podría tener datos); opcional: DELETE FROM users WHERE username='administrador'
