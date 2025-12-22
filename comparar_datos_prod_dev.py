"""
Script para comparar datos críticos entre dev y prod
Ejecutar en ambos entornos y comparar resultados
"""
from app import create_app, db
from app.models import Asset, PortfolioHolding, Transaction
from app.services.metrics.modified_dietz import ModifiedDietzCalculator
from datetime import datetime, date
from decimal import Decimal

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("🔍 COMPARACIÓN DE DATOS CRÍTICOS")
    print("="*80 + "\n")
    
    # 1. Comparar precios actuales de assets con holdings
    print("1️⃣  PRECIOS ACTUALES DE ASSETS CON HOLDINGS:")
    print("-" * 80)
    
    holdings = PortfolioHolding.query.filter(PortfolioHolding.quantity > 0).all()
    print(f"Total holdings: {len(holdings)}")
    
    total_value = Decimal('0')
    assets_with_prices = []
    assets_without_prices = []
    
    for holding in holdings[:10]:  # Primeros 10
        asset = holding.asset
        if asset:
            if asset.current_price:
                try:
                    quantity = Decimal(str(holding.quantity))
                    price = Decimal(str(asset.current_price))
                    value = quantity * price
                    total_value += value
                    assets_with_prices.append({
                        'symbol': asset.symbol,
                        'quantity': float(holding.quantity),
                        'price': float(asset.current_price),
                        'value': float(value),
                        'yahoo_ticker': asset.yahoo_ticker
                    })
                except:
                    assets_without_prices.append({
                        'symbol': asset.symbol,
                        'quantity': holding.quantity,
                        'yahoo_ticker': asset.yahoo_ticker,
                        'issue': 'Error calculando valor'
                    })
            else:
                assets_without_prices.append({
                    'symbol': asset.symbol,
                    'quantity': holding.quantity,
                    'yahoo_ticker': asset.yahoo_ticker
                })
    
    print(f"\nAssets con precio ({len(assets_with_prices)}):")
    for a in assets_with_prices[:5]:
        print(f"  • {a['symbol']}: {a['quantity']} x {a['price']} = {a['value']:.2f} EUR (ticker: {a['yahoo_ticker']})")
    
    if assets_without_prices:
        print(f"\nAssets sin precio ({len(assets_without_prices)}):")
        for a in assets_without_prices[:5]:
            print(f"  • {a['symbol']}: {a['quantity']} (ticker: {a['yahoo_ticker']})")
    
    # 2. Comparar rentabilidad YTD 2025
    print("\n" + "="*80)
    print("2️⃣  RENTABILIDAD YTD 2025:")
    print("-" * 80)
    
    try:
        # Obtener user_id (asumiendo que hay al menos un usuario)
        from app.models import User
        user = User.query.first()
        if user:
            user_id = user.id
            
            # Calcular rentabilidad YTD 2025
            start_date = datetime(2025, 1, 1)
            end_date = datetime.now()
            
            result = ModifiedDietzCalculator.calculate_return(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date
            )
            
            if result:
                print(f"User ID: {user_id}")
                print(f"Período: {start_date.date()} a {end_date.date()}")
                print(f"Rentabilidad: {result.get('return_percent', 0):.2f}%")
                print(f"Ganancia/Pérdida: {result.get('return_amount', 0):.2f} EUR")
                print(f"Valor Inicial (VI): {result.get('initial_value', 0):.2f} EUR")
                print(f"Valor Final (VF): {result.get('final_value', 0):.2f} EUR")
                print(f"Flujos Netos: {result.get('net_cash_flows', 0):.2f} EUR")
            else:
                print("❌ No se pudo calcular la rentabilidad YTD")
        else:
            print("⚠️  No hay usuarios en la BD")
    except Exception as e:
        print(f"❌ Error calculando rentabilidad: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. Comparar transacciones en 2025
    print("\n" + "="*80)
    print("3️⃣  TRANSACCIONES EN 2025:")
    print("-" * 80)
    
    if user:
        transactions_2025 = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= datetime(2025, 1, 1)
        ).all()
        
        print(f"Total transacciones en 2025: {len(transactions_2025)}")
        
        # Agrupar por tipo
        buys = [t for t in transactions_2025 if t.transaction_type == 'BUY']
        sells = [t for t in transactions_2025 if t.transaction_type == 'SELL']
        
        print(f"  • Compras: {len(buys)}")
        print(f"  • Ventas: {len(sells)}")
        
        # Sumar valores
        total_buy_value = sum(Decimal(str(t.quantity)) * Decimal(str(t.price)) for t in buys if t.quantity and t.price)
        total_sell_value = sum(Decimal(str(t.quantity)) * Decimal(str(t.price)) for t in sells if t.quantity and t.price)
        
        print(f"  • Valor total compras: {float(total_buy_value):.2f} EUR")
        print(f"  • Valor total ventas: {float(total_sell_value):.2f} EUR")
        print(f"  • Diferencia: {float(total_buy_value - total_sell_value):.2f} EUR")
    
    # 4. Comparar cash flows en 2025
    print("\n" + "="*80)
    print("4️⃣  CASH FLOWS EN 2025:")
    print("-" * 80)
    
    if user:
        from app.models.transaction import CashFlow
        cashflows_2025 = CashFlow.query.filter(
            CashFlow.user_id == user_id,
            CashFlow.flow_date >= date(2025, 1, 1)
        ).all()
        
        print(f"Total cash flows en 2025: {len(cashflows_2025)}")
        
        deposits = [cf for cf in cashflows_2025 if cf.amount > 0]
        withdrawals = [cf for cf in cashflows_2025 if cf.amount < 0]
        
        total_deposits = sum(cf.amount for cf in deposits)
        total_withdrawals = abs(sum(cf.amount for cf in withdrawals))
        
        print(f"  • Depósitos: {len(deposits)} → {float(total_deposits):.2f} EUR")
        print(f"  • Retiradas: {len(withdrawals)} → {float(total_withdrawals):.2f} EUR")
        print(f"  • Neto: {float(total_deposits - total_withdrawals):.2f} EUR")
    
    # 5. Comparar assets problemáticos
    print("\n" + "="*80)
    print("5️⃣  ASSETS CON POSIBLES PROBLEMAS:")
    print("-" * 80)
    
    # Assets con precios muy diferentes o sin precio
    problematic_assets = []
    for holding in holdings:
        asset = holding.asset
        if asset:
            if not asset.current_price:
                problematic_assets.append({
                    'symbol': asset.symbol,
                    'isin': asset.isin,
                    'yahoo_ticker': asset.yahoo_ticker,
                    'issue': 'Sin precio'
                })
            elif asset.yahoo_ticker and '.' not in asset.yahoo_ticker and asset.yahoo_suffix:
                # Ticker sin sufijo pero debería tenerlo
                problematic_assets.append({
                    'symbol': asset.symbol,
                    'isin': asset.isin,
                    'yahoo_ticker': asset.yahoo_ticker,
                    'yahoo_suffix': asset.yahoo_suffix,
                    'issue': 'Ticker puede estar mal construido'
                })
    
    if problematic_assets:
        print(f"Total assets problemáticos: {len(problematic_assets)}")
        for a in problematic_assets[:10]:
            print(f"  • {a['symbol']} ({a['isin'][:12]}...): {a['issue']}")
            if 'yahoo_ticker' in a:
                print(f"    Ticker: {a['yahoo_ticker']}")
    else:
        print("✅ No se encontraron assets problemáticos obvios")
    
    print("\n" + "="*80)
    print("✅ COMPARACIÓN COMPLETADA")
    print("="*80 + "\n")
    print("💡 Ejecuta este script en ambos entornos y compara los resultados")
    print()

