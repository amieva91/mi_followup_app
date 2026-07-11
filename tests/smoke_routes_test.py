"""
Smoke tests: comprobaciones rapidas de que la app arranca y las rutas criticas responden.

Ver docs/PLAN_REFACTOR_MEJORAS_2026.md (Fase 1).
"""
from __future__ import annotations

import pytest

from app.models import CacheRebuildState


@pytest.mark.smoke
def test_index_redirects_anonymous_to_landing(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"FollowUp" in response.data or b"followup" in response.data.lower()


@pytest.mark.smoke
def test_login_page_loads(client):
    response = client.get("/auth/login")
    assert response.status_code == 200


@pytest.mark.smoke
def test_login_success(auth_client, user):
    response = auth_client.get("/dashboard")
    assert response.status_code == 200


@pytest.mark.smoke
def test_dashboard_requires_login(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code in (302, 401)


@pytest.mark.smoke
def test_portfolio_dashboard(auth_client):
    response = auth_client.get("/portfolio/")
    assert response.status_code == 200


@pytest.mark.smoke
def test_expenses_list(auth_client):
    response = auth_client.get("/expenses/")
    assert response.status_code == 200


@pytest.mark.smoke
def test_incomes_list(auth_client):
    response = auth_client.get("/incomes/")
    assert response.status_code == 200


@pytest.mark.smoke
def test_portfolio_import_form(auth_client):
    response = auth_client.get("/portfolio/import")
    assert response.status_code == 200


@pytest.mark.smoke
def test_watchlist_config_api(auth_client):
    response = auth_client.get("/portfolio/watchlist/api/config")
    assert response.status_code == 200
    assert response.is_json


@pytest.mark.smoke
def test_admin_forbidden_for_normal_user(auth_client):
    response = auth_client.get("/admin/", follow_redirects=False)
    assert response.status_code in (403, 302)


@pytest.mark.smoke
def test_admin_accessible_for_admin(admin_client):
    response = admin_client.get("/admin/")
    assert response.status_code == 200


@pytest.mark.smoke
def test_invalidate_user_data_caches_marks_full_history(app, user):
    from app.services.cache_invalidation import invalidate_user_data_caches

    with app.app_context():
        invalidate_user_data_caches(user.id, full_history=True)
        row = CacheRebuildState.query.filter_by(user_id=user.id).first()
        assert row is not None
        assert row.pending_full_history is True


@pytest.mark.smoke
def test_price_poll_cli_exits(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["price-poll-one"])
    assert result.exit_code == 0


@pytest.mark.smoke
def test_cache_rebuild_cli_exits(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["cache-rebuild-worker-once"])
    assert result.exit_code == 0


@pytest.mark.smoke
def test_csrf_enabled_blocks_post_without_token(app, user):
    """Con CSRF activo, POST sin token debe fallar."""
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()

    client.post(
        "/auth/login",
        data={"email": user.email, "password": "testpass123"},
        follow_redirects=True,
    )
    response = client.post(
        "/dashboard/config",
        data={"widgets": "{}"},
        follow_redirects=False,
    )
    assert response.status_code in (400, 403)
