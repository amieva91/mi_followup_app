"""Tests unitarios: resolución de modo de valoración watchlist."""
from types import SimpleNamespace

from app.services.valuation_mode_service import resolve_valuation_mode


class FakeConfig:
    def __init__(self, rules):
        self._rules = rules

    def get_valuation_sector_rules(self):
        return self._rules


def test_no_asset_returns_general():
    assert resolve_valuation_mode(None, None) == "general"


def test_missing_sector_or_industry():
    a = SimpleNamespace(sector="", industry="Banks")
    assert resolve_valuation_mode(a, FakeConfig({"banks": [], "realestate": []})) == "general"
    b = SimpleNamespace(sector="Financials", industry=None)
    assert resolve_valuation_mode(b, FakeConfig({"banks": [], "realestate": []})) == "general"


def test_bank_pair_match():
    a = SimpleNamespace(sector="Financials", industry="Banks")
    cfg = FakeConfig(
        {
            "banks": [{"sector": "Financials", "industry": "Banks"}],
            "realestate": [],
        }
    )
    assert resolve_valuation_mode(a, cfg) == "banks"


def test_realestate_pair_match():
    a = SimpleNamespace(sector="Real Estate", industry="REITs")
    cfg = FakeConfig(
        {
            "banks": [],
            "realestate": [{"sector": "Real Estate", "industry": "REITs"}],
        }
    )
    assert resolve_valuation_mode(a, cfg) == "realestate"


def test_tie_bank_wins():
    a = SimpleNamespace(sector="X", industry="Y")
    pair = {"sector": "X", "industry": "Y"}
    cfg = FakeConfig({"banks": [pair], "realestate": [pair]})
    assert resolve_valuation_mode(a, cfg) == "banks"


def test_case_and_whitespace_insensitive():
    a = SimpleNamespace(sector=" financials ", industry=" banks ")
    cfg = FakeConfig(
        {
            "banks": [{"sector": "Financials", "industry": "Banks"}],
            "realestate": [],
        }
    )
    assert resolve_valuation_mode(a, cfg) == "banks"
