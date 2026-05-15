"""Tests: % inversión/liquidez vs Capital Operativo."""
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PATH = _ROOT / "app" / "services" / "global_strategy" / "co_ratio_display.py"
_spec = importlib.util.spec_from_file_location("co_ratio_display", _PATH)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

investment_and_liquidity_pct = _mod.investment_and_liquidity_pct
format_pct_for_message = _mod.format_pct_for_message


def test_investment_and_liquidity_pct_sum_to_100():
    co, ir = 100_000.0, 65_000.0
    inv, liq = investment_and_liquidity_pct(co, ir)
    assert inv is not None and liq is not None
    assert abs(inv + liq - 100.0) < 0.01
    assert abs(inv - 65.0) < 0.01


def test_format_pct_for_message():
    assert format_pct_for_message(65.432) == "65.4 %"
    assert format_pct_for_message(None) == "—"
