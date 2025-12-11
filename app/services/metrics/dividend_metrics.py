"""
Dividend Metrics Service
Calcula métricas relacionadas con dividendos
"""

from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy import func
from app.models.transaction import Transaction
from app.services.currency_service import convert_to_eur


class DividendMetrics:
    """
    Servicio para calcular métricas de dividendos
    """
    
    @staticmethod
    def get_monthly_dividends_last_12_months(user_id):
        """
        Calcula dividendos mes a mes de los últimos 12 meses
        
        Returns:
            list: Lista de dicts con dividendos por mes:
            [
                {
                    'year': int,
                    'month': int,
                    'month_name': str,  # 'Enero', 'Febrero', etc.
                    'period': str,  # '2024-01', '2024-02', etc.
                    'dividends_eur': float,
                    'dividends_count': int
                },
                ...
            ]
            Ordenado por fecha descendente (más reciente primero)
        """
        # Fecha de inicio: hace 12 meses
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        # Obtener todos los dividendos en el período
        dividends = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == 'DIVIDEND',
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        ).order_by(Transaction.transaction_date.desc()).all()
        
        # Agrupar por año-mes
        monthly_data = defaultdict(lambda: {'dividends_eur': 0.0, 'dividends_count': 0})
        
        for div in dividends:
            year = div.transaction_date.year
            month = div.transaction_date.month
            period_key = f"{year}-{month:02d}"
            
            # Convertir a EUR
            amount_eur = convert_to_eur(abs(div.amount), div.currency)
            monthly_data[period_key]['dividends_eur'] += amount_eur
            monthly_data[period_key]['dividends_count'] += 1
        
        # Convertir a lista y formatear
        month_names = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        
        result = []
        for period_key in sorted(monthly_data.keys(), reverse=True):
            year, month = map(int, period_key.split('-'))
            result.append({
                'year': year,
                'month': month,
                'month_name': month_names[month],
                'period': period_key,
                'dividends_eur': round(monthly_data[period_key]['dividends_eur'], 2),
                'dividends_count': monthly_data[period_key]['dividends_count']
            })
        
        return result
    
    @staticmethod
    def get_annualized_dividends_ytd(user_id):
        """
        Calcula dividendos anualizados desde el inicio hasta YTD
        
        Returns:
            dict: {
                'total_dividends_ytd': float,  # Dividendos del año actual (YTD)
                'total_dividends_all_time': float,  # Dividendos totales desde el inicio
                'annualized_dividends': float,  # Proyección anualizada basada en YTD
                'years_investing': float,  # Años desde la primera transacción
                'average_annual_dividends': float,  # Promedio anual histórico
                'first_transaction_date': datetime,
                'ytd_start_date': datetime,  # 1 enero del año actual
                'ytd_days': int  # Días transcurridos en el año actual
            }
        """
        # Obtener primera transacción
        first_txn = Transaction.query.filter_by(
            user_id=user_id
        ).order_by(Transaction.transaction_date).first()
        
        if not first_txn:
            return {
                'total_dividends_ytd': 0.0,
                'total_dividends_all_time': 0.0,
                'annualized_dividends': 0.0,
                'years_investing': 0.0,
                'average_annual_dividends': 0.0,
                'first_transaction_date': None,
                'ytd_start_date': None,
                'ytd_days': 0
            }
        
        first_date = first_txn.transaction_date
        current_year = datetime.now().year
        ytd_start = datetime(current_year, 1, 1)
        
        # Si la primera transacción es después del 1 enero, usar esa fecha
        if first_date > ytd_start:
            ytd_start = first_date
        
        today = datetime.now()
        ytd_days = (today - ytd_start).days
        if ytd_days == 0:
            ytd_days = 1  # Evitar división por 0
        
        # Dividendos YTD (año actual)
        ytd_dividends = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == 'DIVIDEND',
            Transaction.transaction_date >= ytd_start,
            Transaction.transaction_date <= today
        ).all()
        
        total_ytd_eur = 0.0
        for div in ytd_dividends:
            amount_eur = convert_to_eur(abs(div.amount), div.currency)
            total_ytd_eur += amount_eur
        
        # Dividendos totales (desde el inicio)
        all_dividends = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == 'DIVIDEND'
        ).all()
        
        total_all_time_eur = 0.0
        for div in all_dividends:
            amount_eur = convert_to_eur(abs(div.amount), div.currency)
            total_all_time_eur += amount_eur
        
        # Calcular proyección anualizada basada en YTD
        # Si han pasado X días del año y hemos recibido Y EUR, proyectamos: Y * (365 / X)
        if ytd_days > 0:
            annualized_ytd = total_ytd_eur * (365.25 / ytd_days)
        else:
            annualized_ytd = 0.0
        
        # Calcular años de inversión
        years_investing = (today - first_date).days / 365.25
        
        # Promedio anual histórico
        if years_investing > 0:
            average_annual = total_all_time_eur / years_investing
        else:
            average_annual = 0.0
        
        return {
            'total_dividends_ytd': round(total_ytd_eur, 2),
            'total_dividends_all_time': round(total_all_time_eur, 2),
            'annualized_dividends': round(annualized_ytd, 2),
            'years_investing': round(years_investing, 2),
            'average_annual_dividends': round(average_annual, 2),
            'first_transaction_date': first_date,
            'ytd_start_date': ytd_start,
            'ytd_days': ytd_days
        }
    
    @staticmethod
    def get_yearly_dividends_from_start(user_id):
        """
        Calcula dividendos año a año desde el inicio hasta hoy
        
        Returns:
            list: Lista de dicts con dividendos por año:
            [
                {
                    'year': int,
                    'dividends_eur': float,
                    'dividends_count': int,
                    'is_ytd': bool  # True si es el año actual
                },
                ...
            ]
            Ordenado por año descendente (más reciente primero)
        """
        # Obtener primera transacción
        first_txn = Transaction.query.filter_by(
            user_id=user_id
        ).order_by(Transaction.transaction_date).first()
        
        if not first_txn:
            return []
        
        first_year = first_txn.transaction_date.year
        current_year = datetime.now().year
        
        # Obtener todos los dividendos
        all_dividends = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == 'DIVIDEND'
        ).order_by(Transaction.transaction_date).all()
        
        # Agrupar por año
        yearly_data = defaultdict(lambda: {'dividends_eur': 0.0, 'dividends_count': 0})
        
        for div in all_dividends:
            year = div.transaction_date.year
            amount_eur = convert_to_eur(abs(div.amount), div.currency)
            yearly_data[year]['dividends_eur'] += amount_eur
            yearly_data[year]['dividends_count'] += 1
        
        # Convertir a lista
        result = []
        for year in range(first_year, current_year + 1):
            if year in yearly_data:
                result.append({
                    'year': year,
                    'dividends_eur': round(yearly_data[year]['dividends_eur'], 2),
                    'dividends_count': yearly_data[year]['dividends_count'],
                    'is_ytd': (year == current_year)
                })
            else:
                # Incluir años sin dividendos para mantener continuidad
                result.append({
                    'year': year,
                    'dividends_eur': 0.0,
                    'dividends_count': 0,
                    'is_ytd': (year == current_year)
                })
        
        # Ordenar por año descendente (más reciente primero)
        result.sort(key=lambda x: x['year'], reverse=True)
        
        return result

