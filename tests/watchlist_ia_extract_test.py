"""Tests: extracción JSON embebido en markdown (sin llamada Gemini)."""
from app.services.watchlist_report_extract_service import (
    extract_watchlist_fields_from_report_md,
)


def test_extract_inline_json_general_mode_no_user():
    md = """
# Informe
```json
{
  "next_earnings_date": null,
  "per_ntm": 12.5,
  "ntm_dividend_yield": 2.0,
  "eps": 1.2,
  "cagr_revenue_yoy": 7.0,
  "per_fair": 14.0,
  "cagr_eps_yoy": 8.0,
  "net_debt_to_ebitda": null,
  "fcf_to_net_income": null,
  "ebitda_margin_pct": null,
  "operating_margin_pct": null,
  "roic_pct": null
}
```
"""
    out = extract_watchlist_fields_from_report_md(md)
    assert out.get("per_ntm") == 12.5
    assert out.get("cagr_eps_yoy") == 8.0
    assert out.get("per_fair") == 14.0
    assert "price_to_book" not in out or out.get("price_to_book") is None


def test_extract_inline_prefers_first_valid_fence():
    md = """
```json
{"oops": 1}
```
```json
{"next_earnings_date": null, "per_ntm": 9, "ntm_dividend_yield": null, "eps": 1, "cagr_revenue_yoy": 5,
 "per_fair": null, "cagr_eps_yoy": null, "net_debt_to_ebitda": null, "fcf_to_net_income": null,
 "ebitda_margin_pct": null, "operating_margin_pct": null, "roic_pct": null}
```
"""
    out = extract_watchlist_fields_from_report_md(md)
    assert out.get("per_ntm") == 9.0
