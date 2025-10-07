# 🧮 FÓRMULAS Y CÁLCULOS - REFERENCIA TÉCNICA

## 📊 ÍNDICE DE FÓRMULAS

1. [Métricas Operacionales](#1-métricas-operacionales)
2. [Patrimonio y Balance](#2-patrimonio-y-balance)
3. [Deudas y Cuotas](#3-deudas-y-cuotas)
4. [Inversiones y PnL](#4-inversiones-y-pnl)
5. [Criptomonedas](#5-criptomonedas)
6. [Metales Preciosos](#6-metales-preciosos)
7. [Bienes Raíces](#7-bienes-raíces)
8. [Recurrencias Temporales](#8-recurrencias-temporales)
9. [Benchmarks y Objetivos](#9-benchmarks-y-objetivos)

---

## 1. MÉTRICAS OPERACIONALES

### 1.1. Ingresos Mensuales Promedio
```python
def calcular_ingresos_promedio(user_id: int, start_date: date, end_date: date, 
                                months_in_period: int) -> float:
    """
    Calcula el promedio mensual de ingresos en un período.
    
    Fuentes de ingreso:
    - VariableIncome (puntuales y recurrentes)
    - BrokerOperation tipo 'Retirada'
    """
    total_income = 0.0
    
    # Ingresos variables
    variable_incomes = VariableIncome.query.filter_by(user_id=user_id).all()
    
    for income in variable_incomes:
        if income.is_recurring:
            # Expandir fechas recurrentes en el período
            recurring_dates = expand_recurring_dates_in_period(
                start_date=start_date,
                end_date=end_date,
                base_date=income.start_date or income.date,
                recurrence_months=income.recurrence_months or 1,
                end_date_limit=income.end_date
            )
            total_income += income.amount * len(recurring_dates)
        elif start_date <= income.date <= end_date:
            total_income += income.amount
    
    # Retiradas de broker
    retiradas = BrokerOperation.query.filter_by(
        user_id=user_id, 
        operation_type='Retirada'
    ).filter(
        BrokerOperation.date.between(start_date, end_date)
    ).all()
    
    for op in retiradas:
        total_income += abs(op.amount)
    
    # Promedio mensual
    avg_monthly_income = total_income / months_in_period if months_in_period > 0 else 0
    
    return avg_monthly_income
```

### 1.2. Gastos Mensuales Promedio
```python
def calcular_gastos_promedio(user_id: int, start_date: date, end_date: date, 
                              months_in_period: int) -> tuple[float, float]:
    """
    Calcula el promedio mensual de gastos en un período.
    
    Fuentes de gasto:
    - Expense (puntuales y recurrentes)
    - DebtInstallmentPlan (cuotas de deuda activas)
    - BrokerOperation tipo 'Ingreso'
    
    Returns:
        tuple: (avg_monthly_expenses, monthly_debt_payment_total)
    """
    total_expenses = 0.0
    monthly_debt_payment_total = 0.0
    
    # Gastos normales
    expenses = Expense.query.filter_by(user_id=user_id).all()
    
    for expense in expenses:
        if expense.is_recurring:
            recurring_dates = expand_recurring_dates_in_period(
                start_date=start_date,
                end_date=end_date,
                base_date=expense.start_date or expense.date,
                recurrence_months=expense.recurrence_months or 1,
                end_date_limit=expense.end_date
            )
            total_expenses += expense.amount * len(recurring_dates)
        elif start_date <= expense.date <= end_date:
            total_expenses += expense.amount
    
    # Planes de deuda activos
    debt_plans = DebtInstallmentPlan.query.filter_by(
        user_id=user_id, 
        is_active=True
    ).all()
    
    for plan in debt_plans:
        # Cuota mensual actual (para ratio deuda/ingresos)
        monthly_debt_payment_total += plan.monthly_payment
        
        # Expandir cuotas en el período (para gastos totales)
        recurring_dates = expand_recurring_dates_in_period(
            start_date=start_date,
            end_date=end_date,
            base_date=plan.start_date,
            recurrence_months=1,  # Mensual
            end_date_limit=plan.end_date
        )
        total_expenses += plan.monthly_payment * len(recurring_dates)
    
    # Ingresos a broker (son salidas de efectivo)
    ingresos_broker = BrokerOperation.query.filter_by(
        user_id=user_id, 
        operation_type='Ingreso'
    ).filter(
        BrokerOperation.date.between(start_date, end_date)
    ).all()
    
    for op in ingresos_broker:
        total_expenses += abs(op.amount)
    
    avg_monthly_expenses = total_expenses / months_in_period if months_in_period > 0 else 0
    
    return avg_monthly_expenses, monthly_debt_payment_total
```

### 1.3. Ratios Financieros
```python
def calcular_ratios_financieros(avg_monthly_income: float, 
                                avg_monthly_expenses: float,
                                monthly_debt_payment: float) -> dict:
    """
    Calcula ratios financieros básicos.
    
    Returns:
        dict con:
        - monthly_savings: Ahorro mensual
        - savings_rate: Tasa de ahorro (%)
        - debt_to_income: Ratio deuda/ingresos (%)
    """
    # Ahorro mensual
    monthly_savings = avg_monthly_income - avg_monthly_expenses
    
    # Tasa de ahorro
    if avg_monthly_income > 0:
        savings_rate = (monthly_savings / avg_monthly_income) * 100
    else:
        savings_rate = 0.0
    
    # Ratio deuda/ingresos
    if avg_monthly_income > 0:
        debt_to_income = (monthly_debt_payment / avg_monthly_income) * 100
    else:
        debt_to_income = 0.0
    
    return {
        'monthly_savings': monthly_savings,
        'savings_rate': savings_rate,
        'debt_to_income': debt_to_income
    }
```

---

## 2. PATRIMONIO Y BALANCE

### 2.1. Cálculo de Activos
```python
def calcular_activos_totales(user_id: int) -> dict:
    """
    Calcula el total de activos del usuario.
    
    Returns:
        dict con desglose de activos y total
    """
    # Efectivo en cuentas bancarias
    total_cash = db.session.query(func.sum(BankAccount.current_balance))\
        .filter_by(user_id=user_id).scalar() or 0.0
    
    # Inversiones (portfolio de acciones/ETFs)
    total_investments = 0.0
    portfolio = UserPortfolio.query.filter_by(user_id=user_id).first()
    if portfolio and portfolio.portfolio_data:
        portfolio_data = json.loads(portfolio.portfolio_data)
        total_investments = sum(
            float(item.get('market_value_eur', 0) or 0) 
            for item in portfolio_data
        )
    
    # Criptomonedas
    total_crypto = calcular_valor_crypto(user_id)
    
    # Metales preciosos
    total_metals = calcular_valor_metales(user_id)
    
    # Planes de pensiones
    total_pension = db.session.query(func.sum(PensionPlan.current_balance))\
        .filter_by(user_id=user_id).scalar() or 0.0
    
    # Bienes raíces
    total_real_estate = db.session.query(
        func.sum(RealEstateAsset.current_market_value)
    ).filter_by(user_id=user_id).scalar() or 0.0
    
    total_assets = (
        total_cash + 
        total_investments + 
        total_crypto + 
        total_metals + 
        total_pension + 
        total_real_estate
    )
    
    return {
        'cash': total_cash,
        'investments': total_investments,
        'crypto': total_crypto,
        'metals': total_metals,
        'pension': total_pension,
        'real_estate': total_real_estate,
        'total': total_assets
    }
```

### 2.2. Cálculo de Pasivos
```python
def calcular_pasivos_totales(user_id: int) -> dict:
    """
    Calcula el total de pasivos (deudas) del usuario.
    
    Returns:
        dict con desglose de pasivos y total
    """
    # Deudas activas (saldo pendiente)
    debt_plans = DebtInstallmentPlan.query.filter_by(
        user_id=user_id, 
        is_active=True
    ).all()
    
    total_debt = sum(plan.remaining_amount for plan in debt_plans)
    
    # Desglose por tipo
    mortgage_debt = sum(
        plan.remaining_amount 
        for plan in debt_plans 
        if plan.is_mortgage
    )
    
    other_debt = total_debt - mortgage_debt
    
    return {
        'mortgage': mortgage_debt,
        'other': other_debt,
        'total': total_debt
    }
```

### 2.3. Patrimonio Neto
```python
def calcular_patrimonio_neto(user_id: int) -> dict:
    """
    Calcula el patrimonio neto (activos - pasivos).
    
    Returns:
        dict con activos, pasivos y patrimonio neto
    """
    activos = calcular_activos_totales(user_id)
    pasivos = calcular_pasivos_totales(user_id)
    
    patrimonio_neto = activos['total'] - pasivos['total']
    
    # Equity inmobiliario (valor inmuebles - hipotecas)
    real_estate_equity = activos['real_estate'] - pasivos['mortgage']
    
    return {
        'activos': activos,
        'pasivos': pasivos,
        'patrimonio_neto': patrimonio_neto,
        'real_estate_equity': real_estate_equity
    }
```

---

## 3. DEUDAS Y CUOTAS

### 3.1. Fecha de Finalización de Deuda
```python
def calcular_fecha_fin_deuda(start_date: date, duration_months: int) -> date:
    """
    Calcula la fecha de finalización de un plan de pagos.
    
    Formula:
        mes_final = mes_inicio + duracion_meses
        año_final = año_inicio + (mes_final - 1) // 12
        mes_final = ((mes_final - 1) % 12) + 1
    """
    month = start_date.month - 1 + duration_months
    year = start_date.year + month // 12
    month = month % 12 + 1
    
    try:
        return date(year, month, 1)
    except ValueError:
        # Fecha inválida (ej: 31 de febrero)
        return None
```

### 3.2. Cuotas Restantes
```python
def calcular_cuotas_restantes(plan: DebtInstallmentPlan) -> int:
    """
    Calcula el número de cuotas restantes de un plan de pagos.
    
    Lógica:
    1. Si el plan no está activo → 0
    2. Si hoy < fecha_inicio → todas las cuotas
    3. Calcular meses transcurridos desde inicio
    4. Si hoy.day > 1 → suma 1 (se cuenta el mes actual)
    5. Restar cuotas pagadas de total
    """
    if not plan.is_active:
        return 0
    
    today = date.today()
    start_date = plan.start_date
    
    # Si aún no ha empezado
    if today < start_date:
        return plan.duration_months
    
    # Meses transcurridos
    months_since_start = (today.year - start_date.year) * 12 + \
                         (today.month - start_date.month)
    
    # Si ya pasó el día 1 del mes actual, cuenta este mes como pagado
    if today.day > 1 and start_date <= today:
        months_since_start += 1
    
    # Cuotas restantes
    remaining = plan.duration_months - months_since_start
    
    return max(0, remaining)
```

### 3.3. Saldo Pendiente
```python
def calcular_saldo_pendiente(plan: DebtInstallmentPlan) -> float:
    """
    Calcula el saldo pendiente de pagar.
    
    Formula:
        saldo_pendiente = cuota_mensual × cuotas_restantes
    """
    remaining_installments = calcular_cuotas_restantes(plan)
    return plan.monthly_payment * remaining_installments
```

### 3.4. Progreso de Pago
```python
def calcular_progreso_pago(plan: DebtInstallmentPlan) -> float:
    """
    Calcula el porcentaje de progreso del plan de pagos.
    
    Formula:
        progreso = ((cuotas_totales - cuotas_restantes) / cuotas_totales) × 100
    """
    if plan.duration_months == 0:
        return 100.0
    
    remaining = calcular_cuotas_restantes(plan)
    completed = plan.duration_months - remaining
    
    # Asegurar que completed esté en rango válido
    completed = max(0, min(completed, plan.duration_months))
    
    progress = (completed / plan.duration_months) * 100
    
    return round(progress, 2)
```

### 3.5. Cálculo de Cuota Mensual (Amortización Francesa)
```python
def calcular_cuota_mensual_hipoteca(principal: float, 
                                   annual_rate: float, 
                                   years: int) -> float:
    """
    Calcula la cuota mensual de una hipoteca usando amortización francesa.
    
    Formula:
        C = P × [r(1+r)^n] / [(1+r)^n - 1]
        
    Donde:
        C = Cuota mensual
        P = Principal (cantidad prestada)
        r = Tasa mensual (tasa_anual / 12 / 100)
        n = Número de pagos (años × 12)
    """
    if annual_rate == 0:
        # Sin intereses
        return principal / (years * 12)
    
    monthly_rate = (annual_rate / 100) / 12
    num_payments = years * 12
    
    # Fórmula de amortización francesa
    numerator = monthly_rate * ((1 + monthly_rate) ** num_payments)
    denominator = ((1 + monthly_rate) ** num_payments) - 1
    
    monthly_payment = principal * (numerator / denominator)
    
    return round(monthly_payment, 2)
```

---

## 4. INVERSIONES Y PnL

### 4.1. Costo Base Promedio Ponderado
```python
def calcular_costo_base(transactions: list) -> dict:
    """
    Calcula el costo base promedio ponderado por activo.
    
    Formula:
        costo_base = Σ(cantidad_compra × precio_compra) / Σ(cantidad_compra)
    
    Returns:
        dict: {isin: {'quantity': float, 'cost_basis': float}}
    """
    holdings = {}
    
    for tx in transactions:
        isin = tx.isin
        
        if isin not in holdings:
            holdings[isin] = {
                'quantity': 0.0,
                'total_cost': 0.0,
                'cost_basis': 0.0
            }
        
        if tx.transaction_type == 'buy':
            # Compra
            holdings[isin]['quantity'] += tx.quantity
            holdings[isin]['total_cost'] += (tx.quantity * tx.price)
        
        elif tx.transaction_type == 'sell':
            # Venta
            if holdings[isin]['quantity'] > 0:
                # Calcular costo de lo vendido (FIFO o promedio)
                cost_per_unit = holdings[isin]['total_cost'] / holdings[isin]['quantity']
                cost_of_sold = tx.quantity * cost_per_unit
                
                holdings[isin]['quantity'] -= tx.quantity
                holdings[isin]['total_cost'] -= cost_of_sold
    
    # Calcular costo base unitario final
    for isin, data in holdings.items():
        if data['quantity'] > 0:
            data['cost_basis'] = data['total_cost'] / data['quantity']
        else:
            data['cost_basis'] = 0.0
    
    return holdings
```

### 4.2. PnL No Realizado
```python
def calcular_pnl_no_realizado(holdings: dict, current_prices: dict) -> dict:
    """
    Calcula ganancias/pérdidas no realizadas.
    
    Formula:
        PnL = (precio_actual - costo_base) × cantidad
        PnL% = ((precio_actual - costo_base) / costo_base) × 100
    """
    pnl_data = {}
    
    for isin, holding in holdings.items():
        if holding['quantity'] <= 0:
            continue
        
        current_price = current_prices.get(isin, 0.0)
        cost_basis = holding['cost_basis']
        quantity = holding['quantity']
        
        # Valores actuales
        current_value = quantity * current_price
        cost_value = quantity * cost_basis
        
        # PnL
        pnl_amount = current_value - cost_value
        pnl_percentage = ((current_price - cost_basis) / cost_basis * 100) if cost_basis > 0 else 0.0
        
        pnl_data[isin] = {
            'quantity': quantity,
            'cost_basis': cost_basis,
            'current_price': current_price,
            'cost_value': cost_value,
            'current_value': current_value,
            'pnl_amount': pnl_amount,
            'pnl_percentage': round(pnl_percentage, 2)
        }
    
    return pnl_data
```

### 4.3. Distribución de Portfolio
```python
def calcular_distribucion_portfolio(holdings: dict, current_prices: dict) -> dict:
    """
    Calcula la distribución porcentual del portfolio.
    
    Returns:
        dict: {isin: {'value': float, 'percentage': float}}
    """
    # Calcular valor total
    total_value = 0.0
    values = {}
    
    for isin, holding in holdings.items():
        if holding['quantity'] > 0:
            current_price = current_prices.get(isin, 0.0)
            value = holding['quantity'] * current_price
            values[isin] = value
            total_value += value
    
    # Calcular porcentajes
    distribution = {}
    for isin, value in values.items():
        percentage = (value / total_value * 100) if total_value > 0 else 0.0
        distribution[isin] = {
            'value': value,
            'percentage': round(percentage, 2)
        }
    
    return distribution
```

---

## 5. CRIPTOMONEDAS

### 5.1. Holdings de Crypto
```python
def calcular_holdings_crypto(user_id: int) -> dict:
    """
    Calcula las tenencias actuales de criptomonedas desde transacciones.
    
    Returns:
        dict: {ticker: {'quantity': float, 'avg_cost': float}}
    """
    transactions = CryptoTransaction.query.filter_by(user_id=user_id)\
        .order_by(CryptoTransaction.date).all()
    
    holdings = {}
    
    for tx in transactions:
        ticker = tx.ticker_symbol.upper()
        
        if ticker not in holdings:
            holdings[ticker] = {
                'quantity': 0.0,
                'total_cost': 0.0,
                'avg_cost': 0.0
            }
        
        if tx.transaction_type == 'buy':
            # Compra
            holdings[ticker]['quantity'] += tx.quantity
            cost = (tx.quantity * tx.price_per_unit) + (tx.fees or 0)
            holdings[ticker]['total_cost'] += cost
        
        elif tx.transaction_type == 'sell':
            # Venta
            if holdings[ticker]['quantity'] > 0:
                # Reducir cantidad
                sell_ratio = tx.quantity / holdings[ticker]['quantity']
                cost_reduction = holdings[ticker]['total_cost'] * sell_ratio
                
                holdings[ticker]['quantity'] -= tx.quantity
                holdings[ticker]['total_cost'] -= cost_reduction
    
    # Calcular costo promedio
    for ticker, data in holdings.items():
        if data['quantity'] > 0:
            data['avg_cost'] = data['total_cost'] / data['quantity']
        else:
            data['avg_cost'] = 0.0
    
    # Eliminar holdings con cantidad cero
    holdings = {k: v for k, v in holdings.items() if v['quantity'] > 1e-9}
    
    return holdings
```

### 5.2. PnL Crypto
```python
def calcular_pnl_crypto(holdings: dict, current_prices: dict) -> dict:
    """
    Calcula PnL de criptomonedas.
    """
    pnl_data = {}
    
    for ticker, holding in holdings.items():
        current_price = current_prices.get(ticker, 0.0)
        quantity = holding['quantity']
        avg_cost = holding['avg_cost']
        
        current_value = quantity * current_price
        cost_value = holding['total_cost']
        
        pnl_amount = current_value - cost_value
        pnl_percentage = ((current_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0.0
        
        pnl_data[ticker] = {
            'quantity': quantity,
            'avg_cost': avg_cost,
            'current_price': current_price,
            'cost_value': cost_value,
            'current_value': current_value,
            'pnl_amount': pnl_amount,
            'pnl_percentage': round(pnl_percentage, 2)
        }
    
    return pnl_data
```

---

## 6. METALES PRECIOSOS

### 6.1. Conversión de Unidades
```python
# Constante de conversión
GRAMOS_A_ONZAS_TROY = 0.0321507466

def convertir_a_onzas(cantidad: float, unit_type: str) -> float:
    """
    Convierte cantidad de metal a onzas troy.
    
    Args:
        cantidad: Cantidad en la unidad original
        unit_type: 'g' (gramos) o 'oz' (onzas)
    
    Returns:
        float: Cantidad en onzas troy
    """
    if unit_type == 'oz':
        return cantidad
    elif unit_type == 'g':
        return cantidad * GRAMOS_A_ONZAS_TROY
    else:
        raise ValueError(f"Unidad no reconocida: {unit_type}")
```

### 6.2. Holdings de Metales
```python
def calcular_holdings_metales(user_id: int) -> dict:
    """
    Calcula las tenencias actuales de metales preciosos.
    
    Returns:
        dict: {'gold': float (oz), 'silver': float (oz)}
    """
    transactions = PreciousMetalTransaction.query.filter_by(user_id=user_id).all()
    
    holdings = {
        'gold': 0.0,
        'silver': 0.0
    }
    
    for tx in transactions:
        # Convertir a onzas
        qty_oz = convertir_a_onzas(tx.quantity, tx.unit_type)
        
        # Sumar o restar según tipo de transacción
        if tx.transaction_type == 'buy':
            holdings[tx.metal_type] += qty_oz
        elif tx.transaction_type == 'sell':
            holdings[tx.metal_type] -= qty_oz
    
    return holdings
```

### 6.3. Valor de Metales
```python
def calcular_valor_metales(user_id: int, current_prices: dict = None) -> float:
    """
    Calcula el valor actual de los metales preciosos.
    
    Args:
        current_prices: dict con {'gold': precio_eur_oz, 'silver': precio_eur_oz}
    
    Returns:
        float: Valor total en EUR
    """
    if current_prices is None:
        current_prices = {
            'gold': get_precious_metal_price('gold'),
            'silver': get_precious_metal_price('silver')
        }
    
    holdings = calcular_holdings_metales(user_id)
    
    gold_value = holdings['gold'] * current_prices['gold']
    silver_value = holdings['silver'] * current_prices['silver']
    
    total_value = gold_value + silver_value
    
    return total_value
```

---

## 7. BIENES RAÍCES

### 7.1. Equity Inmobiliario
```python
def calcular_equity_inmueble(asset: RealEstateAsset, 
                             mortgage: RealEstateMortgage = None) -> dict:
    """
    Calcula el equity (patrimonio) de un inmueble.
    
    Formula:
        equity = valor_mercado - saldo_hipoteca
        equity_percentage = (equity / valor_mercado) × 100
    
    Returns:
        dict con equity absoluto y porcentual
    """
    market_value = asset.current_market_value or 0.0
    
    # Saldo de hipoteca
    mortgage_balance = 0.0
    if mortgage:
        mortgage_balance = mortgage.current_principal_balance or 0.0
    
    # Equity
    equity = market_value - mortgage_balance
    
    # Porcentaje de equity
    equity_percentage = (equity / market_value * 100) if market_value > 0 else 0.0
    
    return {
        'market_value': market_value,
        'mortgage_balance': mortgage_balance,
        'equity': equity,
        'equity_percentage': round(equity_percentage, 2)
    }
```

### 7.2. Rentabilidad de Alquiler
```python
def calcular_rentabilidad_alquiler(asset: RealEstateAsset,
                                   monthly_rent: float,
                                   annual_expenses: float) -> dict:
    """
    Calcula métricas de rentabilidad de una propiedad de alquiler.
    
    Formulas:
        ingresos_anuales = renta_mensual × 12
        rentabilidad_bruta = (ingresos_anuales / valor_mercado) × 100
        rentabilidad_neta = ((ingresos_anuales - gastos_anuales) / valor_mercado) × 100
    """
    market_value = asset.current_market_value or 0.0
    
    if market_value == 0:
        return {
            'error': 'Valor de mercado no disponible'
        }
    
    # Ingresos anuales
    annual_rent = monthly_rent * 12
    
    # Rentabilidad bruta
    gross_yield = (annual_rent / market_value) * 100
    
    # Rentabilidad neta
    net_income = annual_rent - annual_expenses
    net_yield = (net_income / market_value) * 100
    
    return {
        'annual_rent': annual_rent,
        'annual_expenses': annual_expenses,
        'net_income': net_income,
        'gross_yield': round(gross_yield, 2),
        'net_yield': round(net_yield, 2)
    }
```

---

## 8. RECURRENCIAS TEMPORALES

### 8.1. Próxima Fecha de Recurrencia
```python
def calcular_proxima_recurrencia(current_date: date, 
                                 recurrence_months: int) -> date:
    """
    Calcula la siguiente fecha de recurrencia.
    
    Formula:
        mes_siguiente = mes_actual + meses_recurrencia
        año_siguiente = año_actual + (mes_siguiente - 1) // 12
        mes_siguiente = ((mes_siguiente - 1) % 12) + 1
    
    Ejemplo:
        Fecha actual: 2024-10-15
        Recurrencia: 3 meses
        → Próxima fecha: 2025-01-15
    """
    if not current_date or not recurrence_months:
        return None
    
    try:
        # Calcular mes y año siguiente
        next_month = current_date.month + recurrence_months
        next_year = current_date.year + (next_month - 1) // 12
        month = ((next_month - 1) % 12) + 1
        
        # Intentar crear fecha con el mismo día
        return current_date.replace(year=next_year, month=month)
    
    except ValueError:
        # Día inválido para el mes (ej: 31 de febrero)
        # Usar último día del mes
        from calendar import monthrange
        last_day = monthrange(next_year, month)[1]
        return date(next_year, month, last_day)
```

### 8.2. Expansión de Fechas Recurrentes
```python
def expand_recurring_dates_in_period(start_date: date,
                                    end_date: date,
                                    base_date: date,
                                    recurrence_months: int,
                                    end_date_limit: date = None) -> list[date]:
    """
    Expande todas las fechas recurrentes que caen en un período.
    
    Args:
        start_date: Inicio del período de análisis
        end_date: Fin del período de análisis
        base_date: Fecha inicial de la recurrencia
        recurrence_months: Meses entre ocurrencias
        end_date_limit: Fecha límite de la recurrencia (opcional)
    
    Returns:
        list[date]: Lista de fechas que caen en el período
    
    Ejemplo:
        start_date: 2024-01-01
        end_date: 2024-12-31
        base_date: 2024-02-15
        recurrence_months: 3
        → [2024-02-15, 2024-05-15, 2024-08-15, 2024-11-15]
    """
    if not all([start_date, end_date, base_date, recurrence_months]):
        return []
    
    dates = []
    current_date = base_date
    
    while current_date <= end_date:
        # Verificar que esté en el rango
        if current_date >= start_date:
            # Verificar límite de recurrencia
            if end_date_limit and current_date > end_date_limit:
                break
            dates.append(current_date)
        
        # Calcular siguiente fecha
        current_date = calcular_proxima_recurrencia(current_date, recurrence_months)
        
        if not current_date:
            break
    
    return dates
```

### 8.3. Parseo de Período
```python
def parse_period_string(period_str: str) -> dict:
    """
    Parsea string de período y retorna información estructurada.
    
    Formatos soportados:
        'current' → Mes actual
        '3m' → Últimos 3 meses
        '12m' → Últimos 12 meses
    
    Returns:
        dict: {
            'type': 'current' | 'period',
            'months': int,
            'description': str
        }
    """
    if period_str == 'current':
        return {
            'type': 'current',
            'months': 1,
            'description': 'Mes Actual'
        }
    
    try:
        if period_str.endswith('m'):
            months = int(period_str[:-1])
            if months <= 0:
                months = 12
            
            return {
                'type': 'period',
                'months': months,
                'description': f'Promedio de los últimos {months} meses'
            }
        else:
            return None
    
    except (ValueError, TypeError):
        return None
```

### 8.4. Cálculo de Rango de Fechas
```python
def calculate_date_range_from_period(period_info: dict) -> tuple[date, date, int]:
    """
    Calcula rango de fechas basado en información del período.
    
    Returns:
        tuple: (start_date, end_date, months_in_period)
    """
    if not period_info:
        return None, None, 0
    
    today = date.today()
    
    if period_info['type'] == 'current':
        # Mes actual (desde día 1 hasta hoy)
        start_date = today.replace(day=1)
        end_date = today
        months_in_period = 1
    
    else:
        # Período de N meses
        months_in_period = period_info['months']
        end_date = today
        
        # Retroceder al primer día del mes
        start_date = (end_date.replace(day=1) - timedelta(days=1)).replace(day=1)
        
        # Retroceder meses adicionales
        for _ in range(months_in_period - 1):
            start_date = (start_date - timedelta(days=1)).replace(day=1)
    
    return start_date, end_date, months_in_period
```

---

## 9. BENCHMARKS Y OBJETIVOS

### 9.1. Objetivo de Ahorro por Edad
```python
def calculate_savings_target_by_age(age: int, annual_net_salary: float) -> float:
    """
    Calcula objetivo de ahorro según edad usando interpolación lineal.
    
    Puntos de control (edad, multiplicador de salario):
        0-21: 0.1×, 22: 0.2×, 30: 1.0×, 35: 2.0×, 40: 3.0×
        45: 4.0×, 50: 6.0×, 55: 7.0×, 60: 8.0×, 65: 9.0×
        70: 10.0×, 75+: 11.0×
    
    Formula de interpolación:
        ratio = (edad - edad1) / (edad2 - edad1)
        multiplicador = mult1 + (mult2 - mult1) × ratio
        objetivo = salario_anual × multiplicador
    """
    if age is None or annual_net_salary is None:
        return None
    
    # Puntos de control
    control_points = [
        (0, 0.1), (21, 0.1),
        (22, 0.2), (30, 1.0),
        (35, 2.0), (40, 3.0), (45, 4.0), (50, 6.0),
        (55, 7.0), (60, 8.0), (65, 9.0), (70, 10.0), (75, 11.0)
    ]
    
    # Casos extremos
    if age <= 21:
        multiplier = 0.1
    elif age >= 75:
        multiplier = 11.0
    else:
        # Interpolar entre puntos
        multiplier = 0.1  # Default
        
        for i in range(len(control_points) - 1):
            age1, mult1 = control_points[i]
            age2, mult2 = control_points[i + 1]
            
            if age1 <= age <= age2:
                # Interpolación lineal
                if age2 == age1:
                    multiplier = mult1
                else:
                    ratio = (age - age1) / (age2 - age1)
                    multiplier = mult1 + (mult2 - mult1) * ratio
                break
    
    target = annual_net_salary * multiplier
    
    return round(target, 2)
```

### 9.2. Estado de Benchmark
```python
def get_savings_benchmark_status(current_savings: float, 
                                target_savings: float) -> tuple[str, float, float]:
    """
    Determina el estado del benchmark de ahorro.
    
    Niveles:
        ≥ 100%: excellent (🌟)
        ≥ 80%: good (✅)
        ≥ 60%: average (🟡)
        < 60%: poor (⚠️)
    
    Returns:
        tuple: (status, percentage_of_target, shortfall_amount)
    """
    if target_savings is None or target_savings <= 0:
        return "unknown", 0, 0
    
    # Porcentaje de cumplimiento
    percentage = (current_savings / target_savings) * 100
    
    # Déficit
    shortfall = max(0, target_savings - current_savings)
    
    # Determinar estado
    if percentage >= 100:
        status = "excellent"
    elif percentage >= 80:
        status = "good"
    elif percentage >= 60:
        status = "average"
    else:
        status = "poor"
    
    return status, round(percentage, 2), round(shortfall, 2)
```

### 9.3. Edad del Usuario
```python
def get_user_age(user: User) -> int:
    """
    Calcula edad del usuario desde birth_year.
    
    Formula:
        edad = año_actual - año_nacimiento
    """
    if not user.birth_year:
        return None
    
    from datetime import datetime
    current_year = datetime.now().year
    
    return current_year - user.birth_year
```

---

## 📚 CONSTANTES IMPORTANTES

```python
# Conversiones
GRAMOS_A_ONZAS_TROY = 0.0321507466
MESES_POR_AÑO = 12

# Frecuencias de recurrencia
FRECUENCIAS = {
    'monthly': 1,
    'bimonthly': 2,
    'quarterly': 3,
    'semiannual': 6,
    'annual': 12
}

# Umbrales de benchmarks
BENCHMARK_THRESHOLDS = {
    'excellent': 100,
    'good': 80,
    'average': 60,
    'poor': 0
}

# Tipos de transacción
TRANSACTION_TYPES = {
    'buy': 'Compra',
    'sell': 'Venta',
    'dividend': 'Dividendo',
    'deposit': 'Depósito',
    'withdrawal': 'Retirada'
}

# Categorías de gastos predeterminadas
DEFAULT_EXPENSE_CATEGORIES = [
    'Vivienda',
    'Alimentación',
    'Transporte',
    'Salud',
    'Educación',
    'Ocio',
    'Servicios',
    'Otros'
]
```

---

## 🔍 ÍNDICE DE BÚSQUEDA RÁPIDA

**Por Dominio:**
- Ingresos: 1.1
- Gastos: 1.2
- Ratios: 1.3
- Activos: 2.1
- Pasivos: 2.2
- Patrimonio Neto: 2.3
- Deudas: 3.1-3.5
- Inversiones: 4.1-4.3
- Crypto: 5.1-5.2
- Metales: 6.1-6.3
- Bienes Raíces: 7.1-7.2
- Recurrencias: 8.1-8.4
- Benchmarks: 9.1-9.3

**Por Tipo de Cálculo:**
- Promedios: 1.1, 1.2
- Porcentajes: 1.3, 2.3, 3.4, 4.2, 7.1
- PnL: 4.2, 5.2
- Fechas: 3.1, 8.1-8.4
- Interpolación: 9.1
- Holdings: 4.1, 5.1, 6.2

---

## 📝 NOTAS DE IMPLEMENTACIÓN

### Precisión Decimal
```python
from decimal import Decimal, ROUND_HALF_UP

# Para cálculos financieros, usar Decimal en lugar de float
def round_currency(amount: float) -> Decimal:
    """Redondea a 2 decimales para moneda"""
    return Decimal(str(amount)).quantize(
        Decimal('0.01'), 
        rounding=ROUND_HALF_UP
    )
```

### Manejo de Divisas
```python
# Para multi-divisa (futuro)
def convert_to_base_currency(amount: float, 
                             from_currency: str,
                             to_currency: str,
                             exchange_rate: float = None) -> float:
    """Convierte cantidad de una divisa a otra"""
    if from_currency == to_currency:
        return amount
    
    if exchange_rate is None:
        exchange_rate = get_exchange_rate(from_currency, to_currency)
    
    return amount * exchange_rate
```

### Cache de Cálculos
```python
from functools import lru_cache
from datetime import date

@lru_cache(maxsize=128)
def calculate_metrics_cached(user_id: int, 
                             period_str: str, 
                             cache_date: str) -> dict:
    """
    Versión cacheada de cálculos.
    cache_date invalida el cache diariamente.
    """
    return calculate_operational_averages(user_id, period_str)

# Uso
cache_date = date.today().strftime('%Y-%m-%d')
metrics = calculate_metrics_cached(user_id, '12m', cache_date)
```

---

## 🎯 PRIORIZACIÓN PARA MVP

### ✅ CRÍTICAS (Implementar primero)
- 1.1-1.3: Métricas operacionales
- 2.1-2.3: Patrimonio y balance
- 3.2-3.4: Cálculos de deuda básicos
- 8.1-8.4: Sistema de recurrencias

### 🟡 IMPORTANTES (Fase 2)
- 3.5: Cálculo de hipotecas
- 4.1-4.3: Inversiones completas
- 9.1-9.3: Benchmarks personalizados

### 🟢 OPCIONALES (Según necesidad)
- 5.1-5.2: Criptomonedas
- 6.1-6.3: Metales preciosos
- 7.1-7.2: Bienes raíces

---

**Este documento es una referencia técnica completa. Úsalo para:**
1. Validar lógica de negocio
2. Implementar tests unitarios
3. Revisar fórmulas antes de migrar
4. Documentar el nuevo sistema

