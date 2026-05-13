"""
Regresión contra snapshot de producción (JSON en ``instance/``).

Solo comprueba filas con EPS > 0: el cambio de valoración en pérdidas (general, EPS ≤ 0)
no debe alterar el pipeline rentable ni bancos/REIT.

Generar/actualizar snapshot: export en VM o local → ``instance/watchlist_baseline_amieva91_production.json``.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional
from unittest.mock import patch

import pytest

from app.services.watchlist_metrics_service import WatchlistMetricsService

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "instance" / "watchlist_baseline_amieva91_production.json"

META_ROW_KEYS = frozenset(
    {
        "_valuation_mode",
        "_asset_symbol",
        "_asset_name",
        "_baseline_positive_eps",
    }
)


def _parse_date(val: Any) -> Any:
    if val is None or val == "":
        return None
    if isinstance(val, str):
        return datetime.strptime(val, "%Y-%m-%d").date()
    return val


def _row_to_watchlist_namespace(row: Dict[str, Any]) -> SimpleNamespace:
    d: Dict[str, Any] = {}
    for k, v in row.items():
        if k in META_ROW_KEYS:
            continue
        if k == "next_earnings_date":
            d[k] = _parse_date(v)
        else:
            d[k] = v
    return SimpleNamespace(**d)


def _config_from_baseline(cfg_block: Optional[Dict[str, Any]]) -> SimpleNamespace:
    if not cfg_block:
        return SimpleNamespace(
            max_weight_threshold=10.0,
            tier_ranges="{}",
            tier_amounts="{}",
            color_thresholds="{}",
        )

    class _Cfg:
        def __init__(self, raw: Dict[str, Any]):
            self.max_weight_threshold = raw.get("max_weight_threshold", 10.0)
            self.tier_ranges = raw.get("tier_ranges") or "{}"
            self.tier_amounts = raw.get("tier_amounts") or "{}"
            self.color_thresholds = raw.get("color_thresholds") or "{}"

        def get_tier_ranges_dict(self):
            tr = self.tier_ranges
            return json.loads(tr) if isinstance(tr, str) else (tr or {})

        def get_tier_amounts_dict(self):
            ta = self.tier_amounts
            return json.loads(ta) if isinstance(ta, str) else (ta or {})

        def get_color_thresholds_dict(self):
            ct = self.color_thresholds
            return json.loads(ct) if isinstance(ct, str) else (ct or {})

    return _Cfg(cfg_block)


def _assert_close(name: str, actual: Any, expected: Any, abs_tol: float) -> None:
    if actual is None and expected is None:
        return
    if actual is None or expected is None:
        pytest.fail(f"{name}: {actual!r} vs {expected!r}")
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        assert abs(float(actual) - float(expected)) <= abs_tol, (
            f"{name}: got {actual}, expected {expected}"
        )
        return
    assert actual == expected, f"{name}: got {actual!r}, expected {expected!r}"


@pytest.mark.skipif(not BASELINE_PATH.is_file(), reason=f"Missing baseline file {BASELINE_PATH}")
def test_baseline_positive_eps_rows_unchanged():
    raw = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    cfg = _config_from_baseline(raw.get("watchlist_config"))
    modes_by_asset: Dict[int, str] = {}
    for row in raw["rows"]:
        aid = row.get("asset_id")
        vm = row.get("_valuation_mode")
        if aid is not None and vm is not None:
            modes_by_asset[int(aid)] = str(vm)

    def _fake_resolve(asset, _config):
        if asset is None:
            return "general"
        return modes_by_asset.get(int(asset.id), "general")

    tol_pct = 0.02
    tol_price = 0.02

    for row in raw["rows"]:
        eps = row.get("eps")
        if eps is None or eps <= 0:
            continue

        wl = _row_to_watchlist_namespace(row)
        p0 = row.get("precio_actual")
        asset = SimpleNamespace(id=row["asset_id"], current_price=p0)

        with patch(
            "app.services.valuation_mode_service.resolve_valuation_mode",
            side_effect=_fake_resolve,
        ):
            WatchlistMetricsService.update_all_metrics(
                wl,
                config=cfg,
                current_value_eur=None,
                asset=asset,
            )

        _assert_close("valoracion_12m", wl.valoracion_12m, row.get("valoracion_12m"), tol_pct)
        _assert_close("target_price_5yr", wl.target_price_5yr, row.get("target_price_5yr"), tol_price)
        _assert_close("rentabilidad_5yr", wl.rentabilidad_5yr, row.get("rentabilidad_5yr"), tol_pct)
        _assert_close("rentabilidad_anual", wl.rentabilidad_anual, row.get("rentabilidad_anual"), tol_pct)
        _assert_close("tier", wl.tier, row.get("tier"), 0.0)
        _assert_close(
            "target_price_5yr_gross",
            wl.target_price_5yr_gross,
            row.get("target_price_5yr_gross"),
            tol_price,
        )
        _assert_close(
            "valuation_adjustment_factor",
            wl.valuation_adjustment_factor,
            row.get("valuation_adjustment_factor"),
            1e-4,
        )
