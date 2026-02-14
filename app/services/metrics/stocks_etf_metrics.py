"""
StocksEtfMetrics - Métricas filtradas solo para Stock y ETF (Cartera de Acciones)
Usado en la vista Cartera para mostrar indicadores de Dinero, Apalancamiento, B/P
"""
from decimal import Decimal
from collections import defaultdict
from app.models import Transaction, PortfolioHolding, Asset
from app.services.currency_service import convert_to_eur
from app.services.fifo_calculator import FIFOCalculator
from app.services.metrics.basic_metrics import BasicMetrics


class StocksEtfMetrics:
    """
    Métricas financieras filtradas por Stock y ETF solamente.
    Excluye Crypto, Commodity y otros tipos de activos.
    """

    @staticmethod
    def get_stocks_etf_ids(user_id):
        """
        Obtiene account_ids y asset_ids que corresponden a Stock o ETF.

        Usa HISTORIAL de transacciones, no solo posiciones actuales, para incluir:
        - P&L realizado de acciones vendidas por completo
        - Dividendos de acciones ya vendidas
        - Depósitos/retiradas de cuentas que ya no tienen posiciones

        Returns:
            tuple: (account_ids: set, asset_ids: set)
        """
        # asset_ids y account_ids: del historial de transacciones Stock/ETF (BUY/SELL/DIVIDEND)
        stock_etf_txns = (
            Transaction.query
            .join(Asset, Transaction.asset_id == Asset.id)
            .filter(
                Transaction.user_id == user_id,
                Transaction.transaction_type.in_(['BUY', 'SELL']),
                Transaction.asset_id.isnot(None),
                Asset.asset_type.in_(['Stock', 'ETF'])
            )
            .all()
        )
        asset_ids = {t.asset_id for t in stock_etf_txns if t.asset_id}
        account_ids = {t.account_id for t in stock_etf_txns}

        # account_ids: añadir cuentas con depósitos que tienen o han tenido Stock/ETF
        # (por si hay cuentas con solo DEPOSIT/WITHDRAWAL y sin BUY/SELL recientes)
        # Las cuentas de stock_etf_txns ya las tenemos; las de dividendos también
        div_txns = (
            Transaction.query
            .join(Asset, Transaction.asset_id == Asset.id)
            .filter(
                Transaction.user_id == user_id,
                Transaction.transaction_type == 'DIVIDEND',
                Asset.asset_type.in_(['Stock', 'ETF'])
            )
            .all()
        )
        for t in div_txns:
            account_ids.add(t.account_id)
            if t.asset_id:
                asset_ids.add(t.asset_id)

        return account_ids, asset_ids

    @staticmethod
    def _calculate_pl_realized_filtered(user_id, asset_ids):
        """
        P&L Realizado solo para activos Stock/ETF.
        """
        if not asset_ids:
            return {'realized_pl': 0.0, 'realized_pl_pct': 0.0, 'total_sales': 0}

        transactions = (
            Transaction.query
            .filter(
                Transaction.user_id == user_id,
                Transaction.transaction_type.in_(['BUY', 'SELL']),
                Transaction.asset_id.in_(asset_ids)
            )
            .order_by(Transaction.transaction_date, Transaction.created_at)
            .all()
        )

        asset_transactions = defaultdict(list)
        for txn in transactions:
            asset_transactions[txn.asset_id].append(txn)

        total_realized_pl_eur = 0.0
        total_cost_basis_eur = 0.0
        total_sales_count = 0

        for asset_id, txns in asset_transactions.items():
            fifo = FIFOCalculator(symbol=f"Asset_{asset_id}")

            for txn in txns:
                if txn.transaction_type == 'BUY':
                    total_cost = (txn.quantity * txn.price) + (txn.commission or 0) + (txn.fees or 0) + (txn.tax or 0)
                    fifo.add_buy(
                        quantity=txn.quantity,
                        price=txn.price,
                        date=txn.transaction_date,
                        total_cost=total_cost
                    )
                elif txn.transaction_type == 'SELL':
                    cost_basis = float(fifo.add_sell(quantity=txn.quantity, date=txn.transaction_date))
                    cost_basis_eur = convert_to_eur(cost_basis, txn.currency)
                    proceeds = (txn.quantity * txn.price) - (txn.commission or 0) - (txn.fees or 0) - (txn.tax or 0)
                    proceeds_eur = convert_to_eur(proceeds, txn.currency)
                    pl_eur = proceeds_eur - cost_basis_eur
                    total_realized_pl_eur += pl_eur
                    total_cost_basis_eur += cost_basis_eur
                    total_sales_count += 1

        realized_pl_pct = (total_realized_pl_eur / total_cost_basis_eur * 100) if total_cost_basis_eur > 0 else 0

        return {
            'realized_pl': round(total_realized_pl_eur, 2),
            'realized_pl_pct': round(realized_pl_pct, 2),
            'total_sales': total_sales_count,
        }

    @staticmethod
    def _calculate_leverage_filtered(user_id, account_ids, asset_ids, current_portfolio_value, total_cost_current, pl_unrealized):
        """
        Apalancamiento/Cash solo para cuentas y activos Stock/ETF.
        """
        if not account_ids:
            return {
                'broker_money': 0.0,
                'user_money': 0.0,
                'leverage_ratio': 0.0,
                'total_deposits': 0.0,
                'total_withdrawals': 0.0,
                'pl_realized': 0.0,
                'pl_unrealized': pl_unrealized,
                'total_dividends': 0.0,
                'total_fees': 0.0,
            }

        deposits = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == 'DEPOSIT',
            Transaction.account_id.in_(account_ids)
        ).all()
        total_deposits = sum(convert_to_eur(abs(d.amount), d.currency) for d in deposits)

        withdrawals = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == 'WITHDRAWAL',
            Transaction.account_id.in_(account_ids)
        ).all()
        total_withdrawals = sum(convert_to_eur(abs(w.amount), w.currency) for w in withdrawals)

        if asset_ids:
            dividends = Transaction.query.filter(
                Transaction.user_id == user_id,
                Transaction.transaction_type == 'DIVIDEND',
                Transaction.asset_id.in_(asset_ids)
            ).all()
        else:
            dividends = []
        total_dividends = sum(convert_to_eur(abs(d.amount), d.currency) for d in dividends)

        fees = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type.in_(['FEE', 'COMMISSION']),
            Transaction.account_id.in_(account_ids)
        ).all()
        total_fees = sum(convert_to_eur(abs(f.amount), f.currency) for f in fees)

        pl_realized_data = StocksEtfMetrics._calculate_pl_realized_filtered(user_id, asset_ids)
        pl_realized = pl_realized_data['realized_pl']

        user_money = total_deposits - total_withdrawals + pl_realized + total_dividends - total_fees
        broker_money = total_cost_current - user_money
        leverage_ratio = (broker_money / user_money * 100) if user_money > 0 else 0

        return {
            'broker_money': round(broker_money, 2),
            'user_money': round(user_money, 2),
            'leverage_ratio': round(leverage_ratio, 2),
            'total_deposits': round(total_deposits, 2),
            'total_withdrawals': round(total_withdrawals, 2),
            'pl_realized': round(pl_realized, 2),
            'pl_unrealized': round(pl_unrealized, 2),
            'total_dividends': round(total_dividends, 2),
            'total_fees': round(total_fees, 2),
        }

    @staticmethod
    def get_all_metrics(user_id, total_value, total_cost, pl_unrealized):
        """
        Métricas básicas para la Cartera de Acciones (solo Stock y ETF).

        Args:
            user_id: ID del usuario
            total_value: Valor actual de la cartera Stock+ETF en EUR
            total_cost: Coste total de posiciones Stock+ETF en EUR
            pl_unrealized: P&L no realizado de la cartera Stock+ETF

        Returns:
            dict: Con leverage, total_account y total_pl (para indicadores)
        """
        account_ids, asset_ids = StocksEtfMetrics.get_stocks_etf_ids(user_id)

        pl_realized_data = StocksEtfMetrics._calculate_pl_realized_filtered(user_id, asset_ids)
        leverage_metrics = StocksEtfMetrics._calculate_leverage_filtered(
            user_id, account_ids, asset_ids, total_value, total_cost, pl_unrealized
        )

        pl_realized = pl_realized_data['realized_pl']
        total_dividends = leverage_metrics['total_dividends']
        total_fees = leverage_metrics['total_fees']

        total_pl = pl_realized + pl_unrealized + total_dividends - total_fees

        deposits = leverage_metrics['total_deposits']
        withdrawals = leverage_metrics['total_withdrawals']
        total_account_value = deposits - withdrawals + pl_realized + pl_unrealized + total_dividends - total_fees

        total_pl_pct = (total_pl / (deposits - withdrawals) * 100) if (deposits - withdrawals) > 0 else 0

        account_components = {
            'total_account_value': round(total_account_value, 2),
            'deposits': deposits,
            'withdrawals': withdrawals,
            'pl_realized': pl_realized,
            'pl_unrealized': round(pl_unrealized, 2),
            'dividends': total_dividends,
            'fees': total_fees,
            'cash': round(abs(min(0, total_cost - (deposits - withdrawals + pl_realized + total_dividends - total_fees))), 2),
            'leverage': round(max(0, total_cost - (deposits - withdrawals + pl_realized + total_dividends - total_fees)), 2),
        }

        return {
            'leverage': leverage_metrics,
            'total_account': account_components,
            'total_pl': {
                'total_pl': round(total_pl, 2),
                'total_pl_pct': round(total_pl_pct, 2),
                'pl_realized': pl_realized,
                'pl_unrealized': round(pl_unrealized, 2),
                'dividends': total_dividends,
                'fees': total_fees,
            },
        }
