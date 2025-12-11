"""
Modified Dietz Method Calculator

Calcula la rentabilidad del portfolio usando el método Modified Dietz,
estándar de la industria (GIPS compliant).

Fórmula:
R = (VF - VI - CF) / (VI + Σ(CF_i × W_i))

Donde:
- VF = Valor Final
- VI = Valor Inicial
- CF = Flujos de Caja totales
- W_i = Peso temporal del flujo i = días_restantes / días_totales
"""

from datetime import datetime, timedelta
from app.models.transaction import Transaction
from app.services.metrics.portfolio_valuation import PortfolioValuation
from app.services.currency_service import convert_to_eur


class ModifiedDietzCalculator:
    """
    Calcula rentabilidad usando Modified Dietz Method
    """
    
    @staticmethod
    def calculate_return(user_id, start_date, end_date, use_current_prices_end=None):
        """
        Calcula rentabilidad Modified Dietz para un período específico
        
        Args:
            user_id: ID del usuario
            start_date: Fecha inicial (datetime)
            end_date: Fecha final (datetime)
            use_current_prices_end: Si True, usa precios actuales para VF. 
                                   Si None, determina automáticamente (solo si end_date es HOY)
        
        Returns:
            dict: {
                'return': float,  # Rentabilidad decimal (0.15 = 15%)
                'return_pct': float,  # Rentabilidad en porcentaje (15.0)
                'absolute_gain': float,  # Ganancia absoluta en EUR
                'start_value': float,  # Valor inicial
                'end_value': float,  # Valor final
                'cash_flows': float,  # Flujos netos
                'weighted_capital': float,  # Capital ponderado
                'days': int  # Días del período
            }
        """
        # 1. Valor inicial del portfolio (sin usar precios actuales)
        VI = PortfolioValuation.get_value_at_date(
            user_id, 
            start_date, 
            use_current_prices=False
        )
        
        # 2. Valor final del portfolio
        # Determinar si usar precios actuales: solo si end_date es HOY o muy reciente
        if use_current_prices_end is None:
            today = datetime.now().date()
            use_current_prices_end = (end_date.date() >= today)
        
        VF = PortfolioValuation.get_value_at_date(
            user_id, 
            end_date, 
            use_current_prices=use_current_prices_end
        )
        
        # 3. Obtener cash flows externos en el período
        # Solo DEPOSIT y WITHDRAWAL (dinero que entra/sale desde fuera)
        # DIVIDENDS NO son cash flows externos, son ingresos del portfolio
        cash_flows = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.transaction_date > start_date,
            Transaction.transaction_date <= end_date,
            Transaction.transaction_type.in_(['DEPOSIT', 'WITHDRAWAL'])
        ).order_by(Transaction.transaction_date).all()
        
        # 4. Calcular capital ponderado y flujos netos
        total_days = (end_date - start_date).days
        if total_days == 0:
            total_days = 1  # Evitar división por 0
        
        weighted_capital = VI
        total_cash_flows = 0.0
        
        for cf in cash_flows:
            # Días desde el cash flow hasta el final del período
            days_remaining = (end_date - cf.transaction_date).days
            weight = days_remaining / total_days
            
            # Convertir monto a EUR
            amount_eur = convert_to_eur(abs(cf.amount), cf.currency)
            
            # Ajustar signo según tipo
            if cf.transaction_type == 'WITHDRAWAL':
                amount_eur = -amount_eur
            # DEPOSIT y DIVIDEND son positivos
            
            # Sumar al capital ponderado
            weighted_capital += amount_eur * weight
            total_cash_flows += amount_eur
        
        # 5. Calcular rentabilidad
        if weighted_capital == 0:
            return {
                'return': 0.0,
                'return_pct': 0.0,
                'absolute_gain': 0.0,
                'start_value': VI,
                'end_value': VF,
                'cash_flows': total_cash_flows,
                'weighted_capital': weighted_capital,
                'days': total_days
            }
        
        # Ganancia absoluta = Valor Final - Valor Inicial - Flujos Netos
        absolute_gain = VF - VI - total_cash_flows
        
        # Rentabilidad = Ganancia / Capital Ponderado
        period_return = absolute_gain / weighted_capital
        
        return {
            'return': round(period_return, 6),  # Decimal
            'return_pct': round(period_return * 100, 2),  # Porcentaje
            'absolute_gain': round(absolute_gain, 2),
            'start_value': round(VI, 2),
            'end_value': round(VF, 2),
            'cash_flows': round(total_cash_flows, 2),
            'weighted_capital': round(weighted_capital, 2),
            'days': total_days
        }
    
    @staticmethod
    def calculate_annualized_return(user_id):
        """
        Calcula rentabilidad anualizada desde el inicio hasta hoy
        
        Anualiza usando la fórmula:
        Rentabilidad Anualizada = (1 + R)^(365.25/días) - 1
        
        Args:
            user_id: ID del usuario
        
        Returns:
            dict: {
                'annualized_return': float,  # Rentabilidad anualizada en decimal
                'annualized_return_pct': float,  # En porcentaje
                'total_return': float,  # Rentabilidad total del período
                'total_return_pct': float,
                'absolute_gain': float,
                'days': int,
                'years': float,
                'start_date': datetime,
                'end_date': datetime,
                'start_value': float,
                'end_value': float
            }
        """
        # Buscar primera transacción del usuario
        first_txn = Transaction.query.filter_by(
            user_id=user_id
        ).order_by(Transaction.transaction_date).first()
        
        if not first_txn:
            return {
                'annualized_return': 0.0,
                'annualized_return_pct': 0.0,
                'total_return': 0.0,
                'total_return_pct': 0.0,
                'absolute_gain': 0.0,
                'days': 0,
                'years': 0.0,
                'start_date': None,
                'end_date': None,
                'start_value': 0.0,
                'end_value': 0.0
            }
        
        start_date = first_txn.transaction_date
        end_date = datetime.now()
        
        # Calcular rentabilidad del período completo
        result = ModifiedDietzCalculator.calculate_return(
            user_id, start_date, end_date
        )
        
        # Anualizar rentabilidad
        years = result['days'] / 365.25  # GIPS usa 365.25 días/año
        
        if years > 0 and result['return'] > -1:  # Evitar valores imposibles
            annualized = ((1 + result['return']) ** (1 / years)) - 1
        else:
            annualized = result['return']
        
        return {
            'annualized_return': round(annualized, 6),
            'annualized_return_pct': round(annualized * 100, 2),
            'total_return': result['return'],
            'total_return_pct': result['return_pct'],
            'absolute_gain': result['absolute_gain'],
            'days': result['days'],
            'years': round(years, 2),
            'start_date': start_date,
            'end_date': end_date,
            'start_value': result['start_value'],
            'end_value': result['end_value']
        }
    
    @staticmethod
    def calculate_ytd_return(user_id):
        """
        Calcula rentabilidad Year-To-Date (desde 1 enero del año actual)
        
        Args:
            user_id: ID del usuario
        
        Returns:
            dict: Similar a calculate_return pero solo para el año actual
        """
        # Fecha inicio: 1 enero del año actual
        current_year = datetime.now().year
        start_date = datetime(current_year, 1, 1)
        end_date = datetime.now()
        
        # Verificar si hay transacciones antes del 1 enero
        first_txn = Transaction.query.filter_by(
            user_id=user_id
        ).order_by(Transaction.transaction_date).first()
        
        if not first_txn or first_txn.transaction_date > start_date:
            # No hay datos antes del 1 enero, usar fecha de primera transacción
            if first_txn:
                start_date = first_txn.transaction_date
            else:
                return {
                    'return': 0.0,
                    'return_pct': 0.0,
                    'absolute_gain': 0.0,
                    'start_value': 0.0,
                    'end_value': 0.0,
                    'days': 0
                }
        
        result = ModifiedDietzCalculator.calculate_return(
            user_id, start_date, end_date
        )
        
        return result
    
    @staticmethod
    def get_yearly_returns(user_id):
        """
        Calcula rentabilidades año a año desde el inicio hasta hoy
        
        Returns:
            list: Lista de dicts con rentabilidades por año:
            [
                {
                    'year': int,  # 2023, 2024, etc.
                    'return_pct': float,  # Rentabilidad en %
                    'absolute_gain': float,  # Ganancia absoluta en EUR
                    'is_ytd': bool,  # True si es el año actual (YTD)
                    'start_date': datetime,
                    'end_date': datetime
                },
                ...
            ]
        """
        # Obtener primera transacción para saber desde cuándo calcular
        first_txn = Transaction.query.filter_by(
            user_id=user_id
        ).order_by(Transaction.transaction_date).first()
        
        if not first_txn:
            return []
        
        first_year = first_txn.transaction_date.year
        current_year = datetime.now().year
        yearly_returns = []
        
        # Calcular para cada año desde el primero hasta el actual
        for year in range(first_year, current_year + 1):
            # Fechas del año
            year_start = datetime(year, 1, 1)
            year_end = datetime(year, 12, 31, 23, 59, 59)
            
            # Si es el año actual, usar fecha de hoy como fin
            is_ytd = (year == current_year)
            if is_ytd:
                year_end = datetime.now()
            
            # Si la primera transacción es después del 1 enero, usar esa fecha
            if year == first_year and first_txn.transaction_date > year_start:
                year_start = first_txn.transaction_date
            
            # Calcular rentabilidad del año
            # Para años pasados, NO usar precios actuales en el valor final
            # Solo usar precios actuales si es el año actual (YTD)
            use_current_for_end = is_ytd
            result = ModifiedDietzCalculator.calculate_return(
                user_id, year_start, year_end, use_current_prices_end=use_current_for_end
            )
            
            yearly_returns.append({
                'year': year,
                'return_pct': result.get('return_pct', 0.0),
                'absolute_gain': result.get('absolute_gain', 0.0),
                'is_ytd': is_ytd,
                'start_date': year_start,
                'end_date': year_end,
                'start_value': result.get('start_value', 0.0),
                'end_value': result.get('end_value', 0.0)
            })
        
        # Ordenar por año descendente (más reciente primero)
        yearly_returns.sort(key=lambda x: x['year'], reverse=True)
        
        return yearly_returns
    
    @staticmethod
    def get_all_returns(user_id, start_date=None, end_date=None):
        """
        Calcula todas las métricas de rentabilidad de una vez
        
        Si se proporcionan start_date/end_date, calcula rentabilidad para ese período específico.
        Si no, calcula las métricas estándar (total, anualizada, YTD).
        
        Args:
            user_id: ID del usuario
            start_date (datetime, opcional): Fecha inicio del período
            end_date (datetime, opcional): Fecha fin del período
        
        Returns:
            dict: {
                'total': {...},  # Rentabilidad total desde inicio (o del período)
                'annualized': {...},  # Rentabilidad anualizada (o del período)
                'ytd': {...}  # Rentabilidad del año actual (o del período)
            }
        """
        # Verificar que hay transacciones
        first_txn = Transaction.query.filter_by(
            user_id=user_id
        ).order_by(Transaction.transaction_date).first()
        
        if not first_txn:
            return {
                'total': {
                    'return_pct': 0.0,
                    'absolute_gain': 0.0,
                    'start_value': 0.0,
                    'end_value': 0.0,
                    'days': 0
                },
                'annualized': {
                    'return_pct': 0.0,
                    'years': 0.0
                },
                'ytd': {
                    'return_pct': 0.0,
                    'days': 0
                }
            }
        
        # Si se especifica un período personalizado
        if start_date and end_date:
            period_return = ModifiedDietzCalculator.calculate_return(user_id, start_date, end_date)
            
            # Calcular anualización del período personalizado
            days = period_return['days']
            years = days / 365.25
            
            if years > 0 and period_return['return'] != -1:
                annualized_return = (1 + period_return['return']) ** (1 / years) - 1
                annualized_return_pct = annualized_return * 100
            else:
                annualized_return_pct = 0.0
            
            return {
                'total': {
                    'return_pct': period_return['return_pct'],
                    'absolute_gain': period_return['absolute_gain'],
                    'start_value': period_return['start_value'],
                    'end_value': period_return['end_value'],
                    'days': period_return['days']
                },
                'annualized': {
                    'return_pct': round(annualized_return_pct, 2),
                    'years': round(years, 2)
                },
                'ytd': {
                    'return_pct': period_return['return_pct'],  # Mismo que total para período personalizado
                    'absolute_gain': period_return['absolute_gain'],
                    'days': period_return['days']
                }
            }
        
        # Si no hay período personalizado, usar cálculos estándar
        # Calcular rentabilidad anualizada (incluye total)
        annualized = ModifiedDietzCalculator.calculate_annualized_return(user_id)
        
        # Calcular YTD
        ytd = ModifiedDietzCalculator.calculate_ytd_return(user_id)
        
        return {
            'total': {
                'return_pct': annualized['total_return_pct'],
                'absolute_gain': annualized['absolute_gain'],
                'start_value': annualized['start_value'],
                'end_value': annualized['end_value'],
                'days': annualized['days']
            },
            'annualized': {
                'return_pct': annualized['annualized_return_pct'],
                'years': annualized['years']
            },
            'ytd': {
                'return_pct': ytd['return_pct'],
                'absolute_gain': ytd['absolute_gain'],
                'days': ytd['days']
            }
        }

