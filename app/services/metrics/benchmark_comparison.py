"""
Benchmark Comparison Service
Obtiene datos históricos de índices de referencia y calcula rentabilidades comparativas.
HITO 4 - Comparación con Benchmarks
"""
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from collections import defaultdict
from calendar import monthrange
import requests
from app import db
from app.models.transaction import Transaction
from app.services.metrics.modified_dietz import ModifiedDietzCalculator
from app.services.metrics.portfolio_valuation import PortfolioValuation

# Configuración de Chart API (igual que price_updater.py)
CHART_API_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
CHART_API_BASE_URL = 'https://query1.finance.yahoo.com/v8/finance/chart'

# Definir benchmarks
BENCHMARKS = {
    'S&P 500': '^GSPC',
    'NASDAQ 100': '^NDX',  # Cambiado de ^IXIC (NASDAQ Composite) a ^NDX (NASDAQ 100) - índice más común como benchmark
    'MSCI World': 'URTH',
    'EuroStoxx 50': '^STOXX50E'
}


class BenchmarkComparisonService:
    """Servicio para obtener y comparar rentabilidades con benchmarks"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.start_date = self._get_user_start_date()
    
    def _get_user_start_date(self) -> Optional[date]:
        """Obtiene la fecha del primer depósito del usuario"""
        first_deposit = Transaction.query.filter_by(
            user_id=self.user_id,
            transaction_type='DEPOSIT'
        ).order_by(Transaction.transaction_date.asc()).first()
        
        if not first_deposit:
            return None
        
        return first_deposit.transaction_date.date()
    
    def get_benchmark_historical_data(self, ticker: str, start_date: date, end_date: date = None) -> Optional[Dict[str, Any]]:
        """
        Obtiene datos históricos de un benchmark usando Chart API
        
        Returns:
            Dict con timestamps y precios de cierre, o None si falla
        """
        if end_date is None:
            end_date = datetime.now().date()
        
        try:
            url = f"{CHART_API_BASE_URL}/{ticker}"
            
            # Convertir fechas a timestamps Unix
            start_timestamp = int((datetime.combine(start_date, datetime.min.time()) - datetime(1970, 1, 1)).total_seconds())
            end_timestamp = int((datetime.combine(end_date, datetime.max.time()) - datetime(1970, 1, 1)).total_seconds())
            
            params = {
                'period1': start_timestamp,
                'period2': end_timestamp,
                'interval': '1d'  # Datos diarios
            }
            
            response = requests.get(url, headers=CHART_API_HEADERS, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Verificar errores
            if data.get('chart', {}).get('error'):
                return None
            
            if not data.get('chart', {}).get('result'):
                return None
            
            result = data['chart']['result'][0]
            
            if 'timestamp' not in result or not result['timestamp']:
                return None
            
            timestamps = result['timestamp']
            
            # Obtener precios de cierre
            if 'indicators' not in result or 'quote' not in result['indicators']:
                return None
            
            quotes = result['indicators']['quote'][0]
            if 'close' not in quotes:
                return None
            
            closes = quotes['close']
            
            # Filtrar None y crear lista de (fecha, precio)
            data_points = []
            for i, (ts, price) in enumerate(zip(timestamps, closes)):
                if price is not None:
                    date_obj = datetime.fromtimestamp(ts).date()
                    data_points.append({
                        'date': date_obj,
                        'price': float(price)
                    })
            
            return {
                'ticker': ticker,
                'data_points': data_points
            }
            
        except Exception as e:
            print(f"Error obteniendo datos para {ticker}: {str(e)}")
            return None
    
    def get_comparison_data(self) -> Dict[str, Any]:
        """
        Obtiene datos comparativos de todos los benchmarks vs portfolio del usuario
        
        Returns:
            Dict con datos para gráfico y tabla comparativa
        """
        if not self.start_date:
            return self._empty_response()
        
        end_date = datetime.now().date()
        start_datetime = datetime.combine(self.start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        # 1. Obtener datos históricos de todos los benchmarks
        benchmark_data = {}
        for name, ticker in BENCHMARKS.items():
            data = self.get_benchmark_historical_data(ticker, self.start_date, end_date)
            if data:
                benchmark_data[name] = data
        
        # 2. Calcular rentabilidades mensuales para normalización
        # Agrupar datos por mes (primer día de cada mes)
        monthly_data = {}
        
        # Portfolio del usuario: usar Modified Dietz mensual
        portfolio_monthly = self._calculate_portfolio_monthly_returns(start_datetime, end_datetime)
        
        # Benchmarks: agrupar por mes y calcular rentabilidad
        for name, data in benchmark_data.items():
            monthly_prices = self._group_by_month(data['data_points'])
            monthly_data[name] = monthly_prices
        
        # 3. Normalizar todos a 100 desde inicio
        normalized_data = self._normalize_to_100(portfolio_monthly, monthly_data)
        
        # 4. Calcular rentabilidades anuales para tabla
        annual_returns = self._calculate_annual_returns(portfolio_monthly, monthly_data, benchmark_data)
        
        # 5. Preparar datos para gráfico (mensual)
        chart_labels = normalized_data['labels']
        chart_datasets = {
            'portfolio': normalized_data['portfolio'],
            **{name: normalized_data['benchmarks'][name] for name in BENCHMARKS.keys() if name in normalized_data['benchmarks']}
        }
        
        return {
            'labels': chart_labels,
            'datasets': chart_datasets,
            'annual_returns': annual_returns,
            'start_date': self.start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'benchmarks': list(BENCHMARKS.keys())
        }
    
    def _calculate_portfolio_monthly_returns(self, start_datetime: datetime, end_datetime: datetime) -> Dict[date, float]:
        """
        Calcula rentabilidades mensuales del portfolio usando Modified Dietz
        Retorna dict: {fecha_mes: rentabilidad_acumulada}
        
        Optimización: Calcula solo los meses necesarios (último día de cada mes)
        """
        monthly_returns = {}
        current = start_datetime.replace(day=1)  # Empezar en primer día del mes
        
        # Obtener el último día del mes inicial si no estamos en el día 1
        last_day = monthrange(start_datetime.year, start_datetime.month)[1]
        if start_datetime.day != 1:
            # Si no empezamos en día 1, calcular para el último día del mes de inicio
            month_end = start_datetime.replace(day=last_day, hour=23, minute=59, second=59)
            if month_end <= end_datetime:
                return_data = ModifiedDietzCalculator.calculate_return(
                    user_id=self.user_id,
                    start_date=start_datetime,
                    end_date=month_end
                )
                if return_data:
                    monthly_returns[month_end.date()] = return_data['return_pct']
        
        # Avanzar al siguiente mes
        if start_datetime.month == 12:
            current = start_datetime.replace(year=start_datetime.year + 1, month=1, day=1)
        else:
            current = start_datetime.replace(month=start_datetime.month + 1, day=1)
        
        # Calcular para cada mes completo
        while current <= end_datetime:
            last_day = monthrange(current.year, current.month)[1]
            month_end = current.replace(day=last_day, hour=23, minute=59, second=59)
            
            # Calcular Modified Dietz desde inicio hasta el último día de este mes
            return_data = ModifiedDietzCalculator.calculate_return(
                user_id=self.user_id,
                start_date=start_datetime,
                end_date=month_end
            )
            
            if return_data:
                monthly_returns[month_end.date()] = return_data['return_pct']
            
            # Avanzar al siguiente mes
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1, day=1)
            else:
                current = current.replace(month=current.month + 1, day=1)
        
        # Asegurar que incluimos el último día (puede no ser fin de mes)
        if end_datetime.date() not in monthly_returns:
            return_data = ModifiedDietzCalculator.calculate_return(
                user_id=self.user_id,
                start_date=start_datetime,
                end_date=end_datetime
            )
            if return_data:
                monthly_returns[end_datetime.date()] = return_data['return_pct']
        
        return monthly_returns
    
    def _group_by_month(self, data_points: List[Dict[str, Any]]) -> Dict[date, float]:
        """
        Agrupa datos diarios por mes, tomando el precio del último día de cada mes
        Retorna dict: {fecha_mes: precio}
        """
        monthly_prices = {}
        
        # Agrupar por año-mes
        by_month = defaultdict(list)
        for point in data_points:
            date_obj = point['date']
            month_key = date_obj.replace(day=1)
            by_month[month_key].append(point)
        
        # Para cada mes, tomar el último día
        for month_key in sorted(by_month.keys()):
            month_points = sorted(by_month[month_key], key=lambda x: x['date'])
            last_point = month_points[-1]
            monthly_prices[last_point['date']] = last_point['price']
        
        return monthly_prices
    
    def _normalize_to_100(self, portfolio_monthly: Dict[date, float], benchmarks_monthly: Dict[str, Dict[date, float]]) -> Dict[str, Any]:
        """
        Normaliza todas las series a 100 desde inicio
        Convierte rentabilidades en índices base 100
        """
        # Obtener todas las fechas únicas
        all_dates = set(portfolio_monthly.keys())
        for benchmark_data in benchmarks_monthly.values():
            all_dates.update(benchmark_data.keys())
        
        sorted_dates = sorted(all_dates)
        
        # Obtener primer precio de cada benchmark (para normalizar)
        benchmark_first_prices = {}
        for name, monthly_data in benchmarks_monthly.items():
            if monthly_data:
                first_date = min(monthly_data.keys())
                benchmark_first_prices[name] = monthly_data[first_date]
        
        # Normalizar portfolio (ya está en % acumulado, convertir a índice)
        portfolio_normalized = []
        for date_obj in sorted_dates:
            if date_obj in portfolio_monthly:
                # Modified Dietz ya da % acumulado, convertir a índice: 100 + %
                portfolio_normalized.append(100 + portfolio_monthly[date_obj])
            else:
                # Interpolar o usar último valor conocido
                portfolio_normalized.append(portfolio_normalized[-1] if portfolio_normalized else 100)
        
        # Normalizar benchmarks
        benchmarks_normalized = {}
        for name, monthly_data in benchmarks_monthly.items():
            if name not in benchmark_first_prices:
                continue
            
            first_price = benchmark_first_prices[name]
            normalized = []
            
            for date_obj in sorted_dates:
                if date_obj in monthly_data:
                    # Normalizar: (precio_actual / precio_inicial) * 100
                    price = monthly_data[date_obj]
                    normalized.append((price / first_price) * 100)
                else:
                    # Interpolar o usar último valor conocido
                    normalized.append(normalized[-1] if normalized else 100)
            
            benchmarks_normalized[name] = normalized
        
        return {
            'labels': [d.strftime('%Y-%m-%d') for d in sorted_dates],
            'portfolio': portfolio_normalized,
            'benchmarks': benchmarks_normalized
        }
    
    def _calculate_annual_returns(self, portfolio_monthly: Dict[date, float], benchmarks_monthly: Dict[str, Dict[date, float]], benchmark_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calcula rentabilidades anuales para la tabla comparativa
        
        Args:
            portfolio_monthly: Rentabilidades mensuales del portfolio
            benchmarks_monthly: Datos mensuales agrupados de benchmarks (para cálculos anuales)
            benchmark_data: Datos diarios originales de benchmarks (para cálculo de total)
        """
        # Agrupar por año
        years = set()
        
        # Portfolio: obtener años desde monthly_returns
        for date_obj in portfolio_monthly.keys():
            years.add(date_obj.year)
        
        # Benchmarks: obtener años
        for monthly_data in benchmarks_monthly.values():
            for date_obj in monthly_data.keys():
                years.add(date_obj.year)
        
        sorted_years = sorted(years)
        
        annual_data = []
        
        for year in sorted_years:
            year_start = datetime(year, 1, 1)
            year_end = datetime(year, 12, 31)
            
            # Portfolio: Modified Dietz para este año
            portfolio_return_data = ModifiedDietzCalculator.calculate_return(
                user_id=self.user_id,
                start_date=year_start,
                end_date=year_end
            )
            portfolio_return = portfolio_return_data['return_pct'] if portfolio_return_data else 0.0
            
            # Benchmarks: rentabilidad del año
            benchmark_returns = {}
            for name, monthly_data in benchmarks_monthly.items():
                year_start_date = year_start.date()
                year_end_date = year_end.date()
                
                # Buscar precios del año
                year_prices = {d: p for d, p in monthly_data.items() if year_start_date <= d <= year_end_date}
                
                if year_prices:
                    first_price = year_prices[min(year_prices.keys())]
                    last_price = year_prices[max(year_prices.keys())]
                    if first_price > 0:
                        return_pct = ((last_price - first_price) / first_price) * 100
                        benchmark_returns[name] = return_pct
            
            # Calcular diferencias
            differences = {}
            for name, bench_return in benchmark_returns.items():
                differences[name] = portfolio_return - bench_return
            
            annual_data.append({
                'year': year,
                'portfolio': portfolio_return,
                'benchmarks': benchmark_returns,
                'differences': differences
            })
        
        # Calcular total acumulado (desde inicio hasta hoy) - USAR RENTABILIDADES ANUALIZADAS
        # para ser consistente con el dashboard que muestra rentabilidades anualizadas
        end_date = datetime.now().date()
        end_datetime = datetime.combine(end_date, datetime.max.time())
        start_datetime = datetime.combine(self.start_date, datetime.min.time())
        
        # Portfolio: usar rentabilidad total acumulada (no anualizada para la tabla "Total")
        portfolio_total_data = ModifiedDietzCalculator.calculate_return(
            user_id=self.user_id,
            start_date=start_datetime,
            end_date=end_datetime
        )
        portfolio_total = portfolio_total_data['return_pct'] if portfolio_total_data else 0.0
        
        # Benchmarks: usar rentabilidad total acumulada usando datos DIARIOS
        # (igual que el Dashboard para que los totales coincidan)
        benchmark_totals = {}
        for name, data in benchmark_data.items():
            data_points = data.get('data_points', [])
            if len(data_points) >= 2:
                # Usar primer y último precio diario (mismo método que Dashboard)
                first_price = data_points[0]['price']
                last_price = data_points[-1]['price']
                if first_price > 0:
                    total_return = ((last_price - first_price) / first_price) * 100
                    benchmark_totals[name] = total_return
        
        # Diferencias totales (portfolio - benchmark)
        total_differences = {}
        for name, bench_total in benchmark_totals.items():
            total_differences[name] = portfolio_total - bench_total
        
        return {
            'annual': annual_data,
            'total': {
                'portfolio': portfolio_total,
                'benchmarks': benchmark_totals,
                'differences': total_differences
            }
        }
    
    def get_annualized_returns_summary(self) -> Dict[str, Any]:
        """
        Obtiene un resumen rápido de rentabilidades anualizadas (portfolio + benchmarks)
        Para mostrar en el dashboard principal
        
        IMPORTANTE: Para ser consistente con la tabla "Total" en performance, las diferencias
        se calculan usando rentabilidades TOTALES ACUMULADAS, no anualizadas.
        La rentabilidad principal del portfolio sí se muestra anualizada.
        
        Returns:
            Dict con portfolio annualized return, benchmarks total returns, y diferencias basadas en totales
        """
        if not self.start_date:
            return {
                'portfolio_annualized': None,
                'benchmarks': {},
                'benchmarks_annualized': {},
                'differences': {},
                'differences_annualized': {},
                'start_date': None
            }
        
        end_date = datetime.now().date()
        start_datetime = datetime.combine(self.start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        # Calcular rentabilidad anualizada del portfolio (para mostrar como título principal)
        portfolio_annualized_data = ModifiedDietzCalculator.calculate_annualized_return(
            user_id=self.user_id
        )
        portfolio_annualized = portfolio_annualized_data.get('annualized_return_pct', 0.0) if portfolio_annualized_data else 0.0
        
        # Calcular rentabilidad TOTAL acumulada del portfolio (para comparar con benchmarks)
        portfolio_total_data = ModifiedDietzCalculator.calculate_return(
            user_id=self.user_id,
            start_date=start_datetime,
            end_date=end_datetime
        )
        portfolio_total = portfolio_total_data.get('return_pct', 0.0) if portfolio_total_data else 0.0
        
        # Obtener datos históricos de benchmarks
        benchmark_data = {}
        for name, ticker in BENCHMARKS.items():
            data = self.get_benchmark_historical_data(ticker, self.start_date, end_date)
            if data and data['data_points']:
                benchmark_data[name] = data
        
        # Calcular años transcurridos (para anualización)
        days_total = (end_date - self.start_date).days
        years_total = days_total / 365.25 if days_total > 0 else 1
        
        # Calcular rentabilidades TOTALES acumuladas y ANUALIZADAS de benchmarks
        benchmark_totals = {}
        benchmark_annualized = {}
        
        for name, data in benchmark_data.items():
            data_points = data['data_points']
            if len(data_points) >= 2:
                first_price = data_points[0]['price']
                last_price = data_points[-1]['price']
                
                if first_price > 0:
                    # Rentabilidad total acumulada: (last - first) / first
                    total_return = (last_price - first_price) / first_price
                    total_return_pct = total_return * 100
                    benchmark_totals[name] = total_return_pct
                    
                    # Rentabilidad anualizada: (1 + R)^(1/years) - 1
                    if years_total > 0 and total_return > -1:  # Evitar raíz negativa
                        annualized_return = ((1 + total_return) ** (1 / years_total)) - 1
                        annualized_return_pct = annualized_return * 100
                        benchmark_annualized[name] = annualized_return_pct
                    else:
                        benchmark_annualized[name] = None
        
        # Calcular diferencias usando totales acumulados (portfolio_total - benchmark_total)
        # Esto hace que las diferencias sean consistentes con la tabla "Total" en performance
        differences = {}
        for name, bench_total in benchmark_totals.items():
            differences[name] = portfolio_total - bench_total
        
        # Calcular diferencias en rentabilidades anualizadas (portfolio_annualized - benchmark_annualized)
        differences_annualized = {}
        for name, bench_annualized in benchmark_annualized.items():
            if bench_annualized is not None:
                differences_annualized[name] = portfolio_annualized - bench_annualized
        
        return {
            'portfolio_annualized': portfolio_annualized,  # Se muestra anualizado como título
            'benchmarks': benchmark_totals,  # Totales acumulados para consistencia con tabla
            'benchmarks_annualized': benchmark_annualized,  # Anualizadas desde fecha inicio
            'differences': differences,  # Diferencias calculadas con totales
            'differences_annualized': differences_annualized,  # Diferencias en anualizadas
            'start_date': self.start_date.strftime('%Y-%m-%d'),
            'years': round(years_total, 2)
        }
    
    def _empty_response(self) -> Dict[str, Any]:
        """Respuesta vacía cuando no hay datos"""
        return {
            'labels': [],
            'datasets': {},
            'annual_returns': {'annual': [], 'total': {}},
            'start_date': None,
            'end_date': None,
            'benchmarks': []
        }

