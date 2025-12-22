"""
Script para diagnosticar diferencias en rentabilidad YTD 2025
Ejecutar en ambos entornos y comparar
"""
from app import create_app, db
from app.models import Transaction, User
from app.services.metrics.modified_dietz import ModifiedDietzCalculator
from app.services.metrics.portfolio_valuation import PortfolioValuation
from datetime import datetime
from app.services.currency_service import convert_to_eur

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("🔍 DIAGNÓSTICO: RENTABILIDAD YTD 2025")
    print("="*80 + "\n")
    
    user = User.query.first()
    if not user:
        print("❌ No hay usuarios en la BD")
        exit(1)
    
    user_id = user.id
    print(f"User ID: {user_id}\n")
    
    # Fechas YTD 2025
    start_date = datetime(2025, 1, 1)
    end_date = datetime.now()
    
    print(f"Período: {start_date.date()} a {end_date.date()}")
    print(f"Días: {(end_date - start_date).days}\n")
    
    # 1. Valor Inicial (VI) - 1 enero 2025
    print("1️⃣  VALOR INICIAL (VI) - 1 Enero 2025:")
    print("-" * 80)
    VI = PortfolioValuation.get_value_at_date(
        user_id, 
        start_date, 
        use_current_prices=False
    )
    print(f"VI = {VI:.2f} EUR")
    
    # Desglose de VI
    from app.models import PortfolioHolding
    holdings_start = PortfolioHolding.query.filter(
        PortfolioHolding.user_id == user_id
    ).all()
    
    print(f"\nDesglose de VI por asset:")
    vi_total = 0
    for holding in holdings_start[:10]:
        asset = holding.asset
        if asset:
            # Obtener precio histórico al 1 enero 2025
            # Por ahora, usar precio actual como aproximación
            price = asset.current_price or 0
            quantity = holding.quantity or 0
            value = price * quantity if price and quantity else 0
            vi_total += value
            if value > 0:
                print(f"  • {asset.symbol or 'N/A'}: {quantity} x {price} = {value:.2f} EUR")
    
    # 2. Valor Final (VF) - Hoy
    print("\n" + "="*80)
    print("2️⃣  VALOR FINAL (VF) - Hoy:")
    print("-" * 80)
    VF = PortfolioValuation.get_value_at_date(
        user_id, 
        end_date, 
        use_current_prices=True  # YTD usa precios actuales
    )
    print(f"VF = {VF:.2f} EUR")
    
    # Desglose de VF por asset
    print(f"\nDesglose de VF por asset (precios actuales):")
    holdings_now = PortfolioHolding.query.filter(
        PortfolioHolding.user_id == user_id,
        PortfolioHolding.quantity > 0
    ).all()
    
    vf_total = 0
    for holding in holdings_now[:15]:
        asset = holding.asset
        if asset:
            price = asset.current_price or 0
            quantity = holding.quantity or 0
            value = price * quantity if price and quantity else 0
            vf_total += value
            if value > 100:  # Solo mostrar assets significativos
                print(f"  • {asset.symbol or 'N/A'}: {quantity} x {price} = {value:.2f} EUR (ticker: {asset.yahoo_ticker or 'N/A'})")
    
    # 3. Cash Flows en 2025
    print("\n" + "="*80)
    print("3️⃣  CASH FLOWS EN 2025:")
    print("-" * 80)
    
    cash_flows = Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.transaction_date > start_date,
        Transaction.transaction_date <= end_date,
        Transaction.transaction_type.in_(['DEPOSIT', 'WITHDRAWAL'])
    ).order_by(Transaction.transaction_date).all()
    
    print(f"Total cash flows: {len(cash_flows)}")
    
    total_deposits = 0
    total_withdrawals = 0
    
    for cf in cash_flows:
        amount_eur = convert_to_eur(abs(cf.amount), cf.currency)
        if cf.transaction_type == 'DEPOSIT':
            total_deposits += amount_eur
            print(f"  • {cf.transaction_date.date()}: DEPOSIT {amount_eur:.2f} EUR ({cf.currency})")
        else:
            total_withdrawals += amount_eur
            print(f"  • {cf.transaction_date.date()}: WITHDRAWAL -{amount_eur:.2f} EUR ({cf.currency})")
    
    net_cash_flows = total_deposits - total_withdrawals
    print(f"\nResumen:")
    print(f"  • Depósitos: {total_deposits:.2f} EUR")
    print(f"  • Retiradas: {total_withdrawals:.2f} EUR")
    print(f"  • Neto: {net_cash_flows:.2f} EUR")
    
    # 4. Calcular rentabilidad Modified Dietz
    print("\n" + "="*80)
    print("4️⃣  CÁLCULO MODIFIED DIETZ:")
    print("-" * 80)
    
    result = ModifiedDietzCalculator.calculate_return(
        user_id, start_date, end_date, use_current_prices_end=True
    )
    
    print(f"Return %: {result.get('return_pct', 0):.2f}%")
    print(f"Ganancia/Pérdida: {result.get('absolute_gain', 0):.2f} EUR")
    print(f"VI: {result.get('start_value', 0):.2f} EUR")
    print(f"VF: {result.get('end_value', 0):.2f} EUR")
    print(f"CF Neto: {result.get('cash_flows', 0):.2f} EUR")
    print(f"Capital Ponderado: {result.get('weighted_capital', 0):.2f} EUR")
    print(f"Días: {result.get('days', 0)}")
    
    # 5. Comparar con get_yearly_returns
    print("\n" + "="*80)
    print("5️⃣  COMPARAR CON get_yearly_returns():")
    print("-" * 80)
    
    yearly_returns = ModifiedDietzCalculator.get_yearly_returns(user_id)
    ytd_2025 = next((yr for yr in yearly_returns if yr['year'] == 2025), None)
    
    if ytd_2025:
        print(f"2025 (YTD) desde get_yearly_returns():")
        print(f"  • Return %: {ytd_2025['return_pct']:.2f}%")
        print(f"  • Ganancia/Pérdida: {ytd_2025['absolute_gain']:.2f} EUR")
        print(f"  • VI: {ytd_2025['start_value']:.2f} EUR")
        print(f"  • VF: {ytd_2025['end_value']:.2f} EUR")
        print(f"  • Is YTD: {ytd_2025['is_ytd']}")
    else:
        print("❌ No se encontró 2025 en yearly_returns")
    
    # 6. Verificar diferencias en precios
    print("\n" + "="*80)
    print("6️⃣  ASSETS CON PRECIOS DIFERENTES O SIN PRECIO:")
    print("-" * 80)
    
    assets_issues = []
    for holding in holdings_now:
        asset = holding.asset
        if asset:
            if not asset.current_price:
                assets_issues.append({
                    'symbol': asset.symbol,
                    'isin': asset.isin,
                    'yahoo_ticker': asset.yahoo_ticker,
                    'quantity': holding.quantity,
                    'issue': 'Sin precio'
                })
            elif asset.yahoo_ticker and '.' not in asset.yahoo_ticker and asset.yahoo_suffix:
                assets_issues.append({
                    'symbol': asset.symbol,
                    'isin': asset.isin,
                    'yahoo_ticker': asset.yahoo_ticker,
                    'yahoo_suffix': asset.yahoo_suffix,
                    'quantity': holding.quantity,
                    'issue': 'Ticker mal construido (falta sufijo)'
                })
    
    if assets_issues:
        print(f"Total: {len(assets_issues)}")
        for a in assets_issues[:10]:
            print(f"  • {a['symbol']} ({a['isin'][:12] if a['isin'] else 'N/A'}...): {a['issue']}")
            if 'yahoo_ticker' in a:
                print(f"    Ticker: {a['yahoo_ticker']}, Suffix: {a.get('yahoo_suffix', 'N/A')}")
            if a['quantity']:
                print(f"    Cantidad: {a['quantity']}")
    else:
        print("✅ No se encontraron problemas obvios")
    
    print("\n" + "="*80)
    print("✅ DIAGNÓSTICO COMPLETADO")
    print("="*80 + "\n")

