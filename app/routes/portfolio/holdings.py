"""
Rutas de holdings / cartera
"""
from collections import defaultdict
from flask import render_template, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

from app.routes import portfolio_bp
from app.models import BrokerAccount, Asset, PortfolioHolding
from app.services.currency_service import convert_to_eur


@portfolio_bp.route('/holdings')
@login_required
def holdings_list():
    """Lista de posiciones actuales con precios en tiempo real"""
    all_holdings = (
        PortfolioHolding.query.options(
            joinedload(PortfolioHolding.account).joinedload(BrokerAccount.broker),
            joinedload(PortfolioHolding.asset)
        )
        .join(Asset, PortfolioHolding.asset_id == Asset.id)
        .filter(
            PortfolioHolding.user_id == current_user.id,
            PortfolioHolding.quantity > 0,
            Asset.asset_type.in_(['Stock', 'ETF'])
        )
        .all()
    )

    grouped = defaultdict(lambda: {
        'asset': None, 'total_quantity': 0, 'total_cost': 0, 'accounts': [],
        'first_purchase_date': None, 'last_transaction_date': None
    })
    for holding in all_holdings:
        group = grouped[holding.asset_id]
        if group['asset'] is None:
            group['asset'] = holding.asset
        group['total_quantity'] += holding.quantity
        group['total_cost'] += holding.total_cost
        group['accounts'].append({
            'broker': holding.account.broker.name,
            'account_name': holding.account.account_name,
            'quantity': holding.quantity,
            'average_buy_price': holding.average_buy_price
        })
        if group['first_purchase_date'] is None or holding.first_purchase_date < group['first_purchase_date']:
            group['first_purchase_date'] = holding.first_purchase_date
        if group['last_transaction_date'] is None or holding.last_transaction_date > group['last_transaction_date']:
            group['last_transaction_date'] = holding.last_transaction_date

    holdings_unified = []
    for asset_id, data in grouped.items():
        data['average_buy_price'] = data['total_cost'] / data['total_quantity'] if data['total_quantity'] > 0 else 0
        data['asset_id'] = asset_id
        data['brokers'] = sorted(set(acc['broker'] for acc in data['accounts']))
        holdings_unified.append(data)

    holdings_unified = [h for h in holdings_unified if h['asset'] and (h['asset'].asset_type or '').strip() in ('Stock', 'ETF')]

    total_value = 0
    for h in holdings_unified:
        asset = h['asset']
        cost_eur = convert_to_eur(h['total_cost'], asset.currency)
        h['cost_eur'] = cost_eur
        if asset and asset.current_price:
            current_value_local = h['total_quantity'] * asset.current_price
            h['current_value_local'] = current_value_local
            h['local_currency'] = asset.currency
            current_value_eur = convert_to_eur(current_value_local, asset.currency)
            h['current_value_eur'] = current_value_eur
            h['pl_eur'] = current_value_eur - cost_eur
            total_value += current_value_eur
        else:
            total_value += cost_eur
            h['pl_eur'] = 0

    for h in holdings_unified:
        h['weight_pct'] = (h['current_value_eur'] / total_value * 100) if total_value > 0 and 'current_value_eur' in h else 0

    holdings_unified.sort(key=lambda x: (x['asset'].symbol or '') if x['asset'] else '')
    total_cost = sum(h.get('cost_eur', 0) for h in holdings_unified)
    pl_unrealized = total_value - total_cost
    total_pl_pct = (pl_unrealized / total_cost * 100) if total_cost > 0 else 0

    from app.services.metrics.stocks_etf_metrics import StocksEtfMetrics
    metrics = StocksEtfMetrics.get_all_metrics(
        current_user.id, total_value, total_cost, pl_unrealized
    ) if holdings_unified else None

    return render_template(
        'portfolio/holdings.html',
        holdings=holdings_unified,
        unified=True,
        total_value=total_value,
        total_cost=total_cost,
        total_pl=pl_unrealized,
        total_pl_pct=total_pl_pct,
        metrics=metrics,
    )


@portfolio_bp.route('/holdings-debug')
@login_required
def holdings_debug():
    """Endpoint temporal de debug para ver los datos de holdings"""
    all_holdings = PortfolioHolding.query.filter_by(
        user_id=current_user.id
    ).filter(PortfolioHolding.quantity > 0).all()

    grouped = defaultdict(lambda: {
        'asset': None, 'total_quantity': 0, 'total_cost': 0, 'accounts': [],
        'first_purchase_date': None, 'last_transaction_date': None
    })
    for holding in all_holdings:
        group = grouped[holding.asset_id]
        if group['asset'] is None:
            group['asset'] = holding.asset
        group['total_quantity'] += holding.quantity
        group['total_cost'] += holding.total_cost
        group['accounts'].append({
            'broker': holding.account.broker.name if holding.account and holding.account.broker else 'UNKNOWN',
            'account_name': holding.account.account_name if holding.account else 'Unknown',
            'quantity': holding.quantity,
            'average_buy_price': holding.average_buy_price
        })

    holdings_unified = []
    for asset_id, data in grouped.items():
        data['average_buy_price'] = data['total_cost'] / data['total_quantity'] if data['total_quantity'] > 0 else 0
        data['brokers'] = sorted(set(acc['broker'] for acc in data['accounts']))
        asset = data['asset']
        cost_eur = convert_to_eur(data['total_cost'], asset.currency if asset else 'EUR')
        data['cost_eur'] = cost_eur
        if asset and asset.current_price:
            current_value_eur = convert_to_eur(data['total_quantity'] * asset.current_price, asset.currency)
            data['current_value_eur'] = current_value_eur
            data['pl_eur'] = current_value_eur - cost_eur
        else:
            data['pl_eur'] = 0
        holdings_unified.append({
            'asset_id': asset_id,
            'asset_name': asset.name if asset else None,
            'accounts_count': len(data['accounts']),
            'accounts': data['accounts'],
            'brokers': data['brokers'],
            'total_quantity': data['total_quantity'],
            'total_cost': data['total_cost'],
            'cost_eur': cost_eur,
            'current_value_eur': data.get('current_value_eur'),
            'pl_eur': data.get('pl_eur', 0),
        })

    total_value = sum(h.get('current_value_eur', 0) or h.get('cost_eur', 0) for h in holdings_unified)
    for h in holdings_unified:
        h['weight_pct'] = (h['current_value_eur'] / total_value * 100) if h.get('current_value_eur') and total_value > 0 else 0

    return jsonify({
        'total_holdings': len(holdings_unified),
        'total_value': total_value,
        'holdings': holdings_unified[:10]
    })


@portfolio_bp.route('/api/holdings', methods=['GET'])
@login_required
def api_get_holdings():
    """API: Obtener holdings actuales para auto-selección en SELL"""
    try:
        account_id = request.args.get('account_id', type=int)
        user_accounts = BrokerAccount.query.filter_by(user_id=current_user.id).all()
        if not user_accounts:
            return jsonify({'success': True, 'holdings': [], 'total': 0, 'accounts': 0, 'message': 'No tienes cuentas'})
        if account_id:
            account_ids = [account_id] if any(acc.id == account_id for acc in user_accounts) else []
        else:
            account_ids = [acc.id for acc in user_accounts]
        if not account_ids:
            return jsonify({'success': True, 'holdings': [], 'total': 0, 'accounts': 0, 'message': 'Cuenta no encontrada'})

        holdings = PortfolioHolding.query.filter(
            PortfolioHolding.account_id.in_(account_ids),
            PortfolioHolding.quantity > 0
        ).all()
        result = []
        for h in holdings:
            try:
                asset = Asset.query.get(h.asset_id)
                if not asset:
                    continue
                account = BrokerAccount.query.get(h.account_id)
                broker_name = account.broker.name if account and account.broker else 'Unknown'
                result.append({
                    'id': h.asset_id, 'symbol': asset.symbol or 'N/A',
                    'name': asset.name or asset.symbol or 'Sin nombre', 'isin': asset.isin or '',
                    'currency': asset.currency or 'USD', 'asset_type': asset.asset_type or 'Stock',
                    'exchange': asset.exchange or '', 'mic': asset.mic or '', 'yahoo_suffix': asset.yahoo_suffix or '',
                    'quantity': float(h.quantity), 'avg_buy_price': float(h.average_buy_price) if h.average_buy_price else 0,
                    'current_price': float(asset.current_price) if asset.current_price else (float(h.average_buy_price) if h.average_buy_price else 0),
                    'broker': broker_name, 'account_id': h.account_id
                })
            except Exception:
                continue
        return jsonify({'success': True, 'holdings': result, 'total': len(result), 'accounts': len(account_ids)})
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e), 'traceback': traceback.format_exc()}), 500
