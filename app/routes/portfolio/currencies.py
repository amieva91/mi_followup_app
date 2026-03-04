"""
Rutas de divisas / tasas de cambio
"""
from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.routes import portfolio_bp
from app import db
from app.models import Asset, PortfolioHolding


@portfolio_bp.route('/currencies')
@login_required
def currencies():
    """Muestra tasas de conversión de monedas en portfolio"""
    from app.services.currency_service import get_cache_info, get_exchange_rates

    cache_info = get_cache_info()
    all_rates = get_exchange_rates()

    user_currencies = db.session.query(Asset.currency, db.func.count(Asset.id)).join(
        PortfolioHolding, PortfolioHolding.asset_id == Asset.id
    ).filter(
        PortfolioHolding.user_id == current_user.id,
        PortfolioHolding.quantity > 0
    ).group_by(Asset.currency).all()

    currency_names = {
        'EUR': 'Euro', 'USD': 'Dólar estadounidense', 'GBP': 'Libra esterlina',
        'GBX': 'Penique británico', 'JPY': 'Yen japonés', 'CHF': 'Franco suizo',
        'AUD': 'Dólar australiano', 'CAD': 'Dólar canadiense', 'HKD': 'Dólar de Hong Kong',
        'SGD': 'Dólar de Singapur', 'NOK': 'Corona noruega', 'SEK': 'Corona sueca',
        'DKK': 'Corona danesa', 'PLN': 'Zloty polaco', 'CNY': 'Yuan chino',
    }

    currency_flags = {
        'EUR': '🇪🇺', 'USD': '🇺🇸', 'GBP': '🇬🇧', 'GBX': '🇬🇧', 'JPY': '🇯🇵',
        'CHF': '🇨🇭', 'AUD': '🇦🇺', 'CAD': '🇨🇦', 'HKD': '🇭🇰', 'SGD': '🇸🇬',
        'NOK': '🇳🇴', 'SEK': '🇸🇪', 'DKK': '🇩🇰', 'PLN': '🇵🇱', 'CNY': '🇨🇳',
    }

    currency_rates = []
    for currency, count in user_currencies:
        if currency in all_rates:
            to_eur = all_rates[currency]
            from_eur = 1 / to_eur if to_eur > 0 else 0
            currency_rates.append({
                'currency': currency,
                'currency_name': currency_names.get(currency, currency),
                'flag': currency_flags.get(currency, '🌐'),
                'to_eur': to_eur,
                'from_eur': from_eur,
                'asset_count': count
            })

    currency_rates.sort(key=lambda x: x['currency'])
    return render_template('portfolio/currencies.html',
                          currency_rates=currency_rates,
                          cache_info=cache_info)


@portfolio_bp.route('/currencies/refresh', methods=['POST'])
@login_required
def currencies_refresh():
    """Fuerza actualización de tasas de cambio"""
    from app.services.currency_service import get_exchange_rates

    try:
        rates = get_exchange_rates(force_refresh=True)
        flash(f'✅ Tasas actualizadas correctamente ({len(rates)} monedas)', 'success')
    except Exception as e:
        flash(f'❌ Error al actualizar tasas: {str(e)}', 'error')

    return redirect(url_for('portfolio.currencies'))
