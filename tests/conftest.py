"""Configuracion compartida de pytest."""
from __future__ import annotations

import pytest

from app import create_app, db
from app.models import User, MODULES


@pytest.fixture
def app():
    application = create_app("testing")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _make_user(
    *,
    username: str,
    email: str,
    password: str = "testpass123",
    is_admin: bool = False,
) -> User:
    user = User(
        username=username,
        email=email.lower(),
        is_admin=is_admin,
        enabled_modules=list(MODULES.keys()),
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def user(app):
    return _make_user(username="smokeuser", email="smoke@example.com")


@pytest.fixture
def admin_user(app):
    return _make_user(
        username="adminuser",
        email="admin@example.com",
        is_admin=True,
    )


@pytest.fixture
def auth_client(client, user):
    """Cliente con sesion iniciada como usuario normal."""
    response = client.post(
        "/auth/login",
        data={"email": user.email, "password": "testpass123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    return client


@pytest.fixture
def admin_client(client, admin_user):
    response = client.post(
        "/auth/login",
        data={"email": admin_user.email, "password": "testpass123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    return client
