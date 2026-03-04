"""
Rutas de performance: gráficos, dividendos, comparación, diversificación
"""
from collections import defaultdict
from flask import render_template
from flask_login import login_required, current_user

from app.routes import portfolio_bp
from app.models import PortfolioHolding
from app.services.currency_service import convert_to_eur


@portfolio_bp.route("/performance")
@login_required
def performance():
    return render_template("portfolio/performance.html")


@portfolio_bp.route("/dividendos")
@login_required
def dividendos():
    from app.services.metrics.dividend_metrics import DividendMetrics
    return render_template("portfolio/dividendos.html",
        monthly_dividends=DividendMetrics.get_monthly_dividends_last_12_months(current_user.id),
        annualized_dividends=DividendMetrics.get_annualized_dividends_ytd(current_user.id),
        yearly_dividends=DividendMetrics.get_yearly_dividends_from_start(current_user.id))


@portfolio_bp.route("/index-comparison")
@login_required
def index_comparison():
    from app.services.metrics.benchmark_comparison import BenchmarkComparisonService
    b = BenchmarkComparisonService(current_user.id)
    return render_template("portfolio/index_comparison.html",
        benchmark_annualized=b.get_annualized_returns_summary())


@portfolio_bp.route("/diversificacion")
@login_required
def diversificacion():
    all_h = PortfolioHolding.query.filter_by(user_id=current_user.id).filter(PortfolioHolding.quantity > 0).all()
    g = defaultdict(lambda: {"asset": None, "total_quantity": 0, "total_cost": 0, "accounts": [], "first_purchase_date": None, "last_transaction_date": None})
    for h in all_h:
        gr = g[h.asset_id]
        if gr["asset"] is None: gr["asset"] = h.asset
        gr["total_quantity"] += h.quantity
        gr["total_cost"] += h.total_cost
        gr["accounts"].append({"broker": h.account.broker.name, "account_name": h.account.account_name})
        if gr["first_purchase_date"] is None or h.first_purchase_date < gr["first_purchase_date"]: gr["first_purchase_date"] = h.first_purchase_date
        if gr["last_transaction_date"] is None or h.last_transaction_date > gr["last_transaction_date"]: gr["last_transaction_date"] = h.last_transaction_date
    unified = []
    for aid, d in g.items():
        d["average_buy_price"] = d["total_cost"] / d["total_quantity"] if d["total_quantity"] else 0
        d["asset_id"] = aid
        d["brokers"] = sorted(set(a.get("broker", "Manual") for a in d["accounts"]))
        unified.append(d)
    OZ = 31.1035
    for h in unified:
        a = h["asset"]
        h["cost_eur"] = cost = h["total_cost"] if a.asset_type == "Commodity" else convert_to_eur(h["total_cost"], a.currency)
        if a and a.current_price:
            h["current_value_eur"] = convert_to_eur((h["total_quantity"] / OZ * a.current_price) if a.asset_type == "Commodity" else h["total_quantity"] * a.current_price, "USD" if a.asset_type == "Commodity" else a.currency)
        else:
            h["current_value_eur"] = cost
    cd,sd,ad,id,bd,atd = defaultdict(float),defaultdict(float),defaultdict(float),defaultdict(float),defaultdict(float),defaultdict(float)
    for h in unified:
        a,v = h["asset"], h.get("current_value_eur", h.get("cost_eur", 0))
        if a.country: cd[a.country] += v
        if a.sector: sd[a.sector] += v
        if a.symbol: ad[a.symbol] += v
        if a.industry: id[a.industry] += v
        brokers_in_h = set(acc.get("broker", "Manual") for acc in h.get("accounts", []))
        vpb = v / len(brokers_in_h) if brokers_in_h else v
        for b in brokers_in_h:
            bd[b] += vpb
        at = (a.asset_type or "Stock")
        atd["Stock" if at=="ADR" else at] += v
    asrt = sorted(ad.items(), key=lambda x: x[1], reverse=True)
    at10 = asrt[:10]
    if sum(v for _,v in asrt[10:]): at10.append(("Otros", sum(v for _,v in asrt[10:])))
    return render_template("portfolio/diversificacion.html",
        country_distribution=sorted(cd.items(), key=lambda x: x[1], reverse=True),
        sector_distribution=sorted(sd.items(), key=lambda x: x[1], reverse=True),
        asset_distribution=at10,
        industry_distribution=sorted(id.items(), key=lambda x: x[1], reverse=True),
        broker_distribution=sorted(bd.items(), key=lambda x: x[1], reverse=True),
        asset_type_distribution=sorted(atd.items(), key=lambda x: x[1], reverse=True))
