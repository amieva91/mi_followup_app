# 📊 SPRINT 3 - FASE FINAL: Precios y Valoración en Tiempo Real

**Fecha de inicio:** 3 Noviembre 2025  
**Duración estimada:** 1-2 semanas  
**Objetivo:** Completar el ecosistema de Portfolio con precios actualizados y valoración de mercado

---

## 🎯 ALCANCE DE ESTA FASE

### **✅ QUÉ SE IMPLEMENTA AHORA (Sprint 3 Final):**

1. **Actualización de Precios Yahoo Finance**
   - Integración con Yahoo Finance API
   - Actualización manual de precios (botón "🔄 Actualizar Precios")
   - Almacenamiento de datos de mercado en Asset model

2. **Campos de Yahoo Finance a Implementar:**
   ```python
   # PRECIOS Y CAMBIOS
   - currentPrice           # Precio actual
   - previousClose          # Cierre anterior
   - currency               # Moneda del precio
   - regularMarketChangePercent  # % cambio del día
   
   # VALORACIÓN
   - marketCap             # Capitalización (con formato K/M/B y EUR)
   - trailingPE            # P/E Ratio (trailing)
   - forwardPE             # P/E Ratio (forward)
   
   # INFORMACIÓN CORPORATIVA
   - sector                # Sector (Technology, Healthcare, etc.)
   - industry              # Industria específica
   
   # RIESGO Y RENDIMIENTO
   - beta                  # Volatilidad vs mercado
   - dividendRate          # Dividendo anual
   - dividendYield         # Yield de dividendos
   
   # ANÁLISIS DE MERCADO
   - recommendationKey     # Recomendación (buy/hold/sell/strong buy/strong sell)
   - numberOfAnalystOpinions  # Número de analistas
   - targetMeanPrice       # Precio objetivo promedio
   ```

3. **Cálculo de Valores de Mercado**
   - `current_market_value` en PortfolioHolding
   - Valor total del portfolio
   - P&L No Realizado por holding
   - P&L No Realizado total

4. **Dashboard Mejorado**
   - Card de resumen con:
     - Valor Total del Portfolio (EUR)
     - Costo Total
     - P&L Total (Realizado + No Realizado)
     - % Rendimiento Total
   - Tabla de holdings con:
     - Precio actual
     - Cambio del día (% y color)
     - Valor de mercado
     - P&L No Realizado

5. **Utilidades para Formato de Números**
   - Formatear marketCap: `1.5B`, `234.5M`, `45.3K`
   - Conversión de marketCap a EUR (con tipo de cambio)
   - Colores para indicadores (verde +, rojo -)

---

## ❌ QUÉ SE DEJA PARA MÁS ADELANTE:

### **→ Sprint 4: Calculadora de Métricas Avanzadas**
- Gráfico de evolución temporal del portfolio
- Gráfico de P&L acumulado (line/area chart)
- Time-Weighted Return (TWR)
- Money-Weighted Return (IRR)
- Sharpe Ratio
- Max Drawdown
- Volatilidad
- Comparación con benchmarks (S&P 500, etc.)

### **→ Sprint 5: Actualización Automática de Precios**
- Cron job para actualizar precios diariamente
- Histórico de precios (tabla `price_history`)
- Gráfico de precio histórico por asset (candlestick/line)
- Websockets para precios en tiempo real (opcional)

### **→ Sprint 6: Análisis y Diversificación**
- Gráfico de distribución por sector (pie chart)
- Gráfico de distribución por país (pie chart)
- Gráfico de distribución por asset (pie chart)
- Análisis de concentración de riesgo
- Recomendaciones de rebalanceo
- Watchlist (assets sin comprar pero vigilados)

### **→ Sprint 7: Alertas y Notificaciones**
- Alertas de precio (email/app)
- Calendario de dividendos
- Notificaciones de eventos corporativos
- Alertas de cambios en recomendaciones de analistas

---

## 📋 PLAN DE IMPLEMENTACIÓN DETALLADO

### **FASE 1: Base de Datos y Modelos (Día 1)**

#### **A. Migración para Asset model**

```python
# migrations/versions/xxx_add_yahoo_finance_fields_to_assets.py

def upgrade():
    # PRECIOS
    op.add_column('assets', sa.Column('current_price', sa.Float(), nullable=True))
    op.add_column('assets', sa.Column('previous_close', sa.Float(), nullable=True))
    op.add_column('assets', sa.Column('day_change_percent', sa.Float(), nullable=True))
    op.add_column('assets', sa.Column('last_price_update', sa.DateTime(), nullable=True))
    
    # VALORACIÓN
    op.add_column('assets', sa.Column('market_cap', sa.Float(), nullable=True))
    op.add_column('assets', sa.Column('market_cap_formatted', sa.String(20), nullable=True))
    op.add_column('assets', sa.Column('market_cap_eur', sa.Float(), nullable=True))
    op.add_column('assets', sa.Column('trailing_pe', sa.Float(), nullable=True))
    op.add_column('assets', sa.Column('forward_pe', sa.Float(), nullable=True))
    
    # INFO CORPORATIVA
    op.add_column('assets', sa.Column('sector', sa.String(100), nullable=True))
    op.add_column('assets', sa.Column('industry', sa.String(100), nullable=True))
    
    # RIESGO Y RENDIMIENTO
    op.add_column('assets', sa.Column('beta', sa.Float(), nullable=True))
    op.add_column('assets', sa.Column('dividend_rate', sa.Float(), nullable=True))
    op.add_column('assets', sa.Column('dividend_yield', sa.Float(), nullable=True))
    
    # ANÁLISIS
    op.add_column('assets', sa.Column('recommendation_key', sa.String(20), nullable=True))
    op.add_column('assets', sa.Column('number_of_analyst_opinions', sa.Integer(), nullable=True))
    op.add_column('assets', sa.Column('target_mean_price', sa.Float(), nullable=True))
```

#### **B. Actualizar Asset model**

```python
# app/models/asset.py

class Asset(db.Model):
    # ... campos existentes ...
    
    # PRECIOS
    current_price = db.Column(db.Float)
    previous_close = db.Column(db.Float)
    day_change_percent = db.Column(db.Float)
    last_price_update = db.Column(db.DateTime)
    
    # VALORACIÓN
    market_cap = db.Column(db.Float)                    # En moneda original
    market_cap_formatted = db.Column(db.String(20))     # "1.5B", "234M"
    market_cap_eur = db.Column(db.Float)                # Convertido a EUR
    trailing_pe = db.Column(db.Float)
    forward_pe = db.Column(db.Float)
    
    # INFO CORPORATIVA
    sector = db.Column(db.String(100))
    industry = db.Column(db.String(100))
    
    # RIESGO Y RENDIMIENTO
    beta = db.Column(db.Float)
    dividend_rate = db.Column(db.Float)
    dividend_yield = db.Column(db.Float)
    
    # ANÁLISIS
    recommendation_key = db.Column(db.String(20))      # buy, hold, sell, strong buy, strong sell
    number_of_analyst_opinions = db.Column(db.Integer)
    target_mean_price = db.Column(db.Float)
    
    @property
    def price_change_today(self):
        """Cambio de precio hoy vs cierre anterior"""
        if self.current_price and self.previous_close:
            return self.current_price - self.previous_close
        return None
    
    @property
    def recommendation_badge_color(self):
        """Color del badge según recomendación"""
        colors = {
            'strong buy': 'bg-green-600',
            'buy': 'bg-green-400',
            'hold': 'bg-gray-400',
            'sell': 'bg-red-400',
            'strong sell': 'bg-red-600'
        }
        return colors.get(self.recommendation_key, 'bg-gray-400')
```

#### **C. Actualizar PortfolioHolding model**

```python
# app/models/portfolio.py

class PortfolioHolding(db.Model):
    # ... campos existentes ...
    
    @property
    def current_market_value(self):
        """Valor de mercado actual"""
        if not self.asset.current_price or not self.quantity:
            return None
        # Valor en moneda del asset
        return self.asset.current_price * self.quantity
    
    @property
    def current_market_value_eur(self):
        """Valor de mercado en EUR (por ahora, asumimos conversión manual)"""
        # TODO: Implementar conversión automática con API de forex
        return self.current_market_value
    
    @property
    def unrealized_pl(self):
        """P&L no realizado"""
        if not self.current_market_value_eur or not self.total_cost:
            return None
        return self.current_market_value_eur - self.total_cost
    
    @property
    def unrealized_pl_percent(self):
        """% P&L no realizado"""
        if not self.unrealized_pl or not self.total_cost or self.total_cost == 0:
            return None
        return (self.unrealized_pl / self.total_cost) * 100
    
    @property
    def total_return(self):
        """Retorno total (P&L realizado + no realizado)"""
        realized = self.realized_pl or 0
        unrealized = self.unrealized_pl or 0
        return realized + unrealized
    
    @property
    def total_return_percent(self):
        """% retorno total"""
        if not self.total_return or not self.total_cost or self.total_cost == 0:
            return None
        return (self.total_return / self.total_cost) * 100
```

---

### **FASE 2: Servicio de Actualización de Precios (Días 2-3)**

#### **A. Crear PriceUpdater service**

```python
# app/services/market_data/price_updater.py

import yfinance as yf
from datetime import datetime
from app.models import Asset, PortfolioHolding, BrokerAccount, db

class PriceUpdater:
    """Servicio para actualizar precios de assets desde Yahoo Finance"""
    
    def __init__(self):
        self.forex_rates = self._get_forex_rates()
    
    def _get_forex_rates(self):
        """Obtener tipos de cambio actuales (EUR como base)"""
        # Hardcoded por ahora, luego integrar API
        return {
            'EUR': 1.0,
            'USD': 0.92,  # 1 USD = 0.92 EUR
            'GBP': 1.15,  # 1 GBP = 1.15 EUR
            'HKD': 0.12,  # 1 HKD = 0.12 EUR
            # ... más monedas
        }
    
    def _format_market_cap(self, value):
        """Formatear market cap: 1.5B, 234M, 45K"""
        if value is None:
            return None
        
        abs_value = abs(value)
        
        if abs_value >= 1_000_000_000:
            return f"{value / 1_000_000_000:.1f}B"
        elif abs_value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M"
        elif abs_value >= 1_000:
            return f"{value / 1_000:.1f}K"
        else:
            return f"{value:.0f}"
    
    def _convert_to_eur(self, value, currency):
        """Convertir valor a EUR"""
        if value is None or currency is None:
            return None
        rate = self.forex_rates.get(currency, 1.0)
        return value * rate
    
    def update_asset_price(self, asset: Asset):
        """Actualizar precio de un asset individual"""
        if not asset.yahoo_ticker:
            return False
        
        try:
            ticker = yf.Ticker(asset.yahoo_ticker)
            info = ticker.info
            
            # Actualizar campos
            asset.current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            asset.previous_close = info.get('previousClose')
            asset.day_change_percent = info.get('regularMarketChangePercent')
            
            # Valoración
            asset.market_cap = info.get('marketCap')
            if asset.market_cap:
                asset.market_cap_formatted = self._format_market_cap(asset.market_cap)
                asset.market_cap_eur = self._convert_to_eur(
                    asset.market_cap,
                    info.get('currency')
                )
            
            asset.trailing_pe = info.get('trailingPE')
            asset.forward_pe = info.get('forwardPE')
            
            # Info corporativa
            asset.sector = info.get('sector')
            asset.industry = info.get('industry')
            
            # Riesgo y rendimiento
            asset.beta = info.get('beta')
            asset.dividend_rate = info.get('dividendRate')
            asset.dividend_yield = info.get('dividendYield')
            
            # Análisis
            asset.recommendation_key = info.get('recommendationKey')
            asset.number_of_analyst_opinions = info.get('numberOfAnalystOpinions')
            asset.target_mean_price = info.get('targetMeanPrice')
            
            # Timestamp
            asset.last_price_update = datetime.utcnow()
            
            return True
            
        except Exception as e:
            print(f"❌ Error updating {asset.symbol}: {e}")
            return False
    
    def update_all_prices(self, user_id: int):
        """Actualizar precios de todos los assets con holdings activos"""
        
        # Obtener assets únicos con holdings > 0
        holdings = PortfolioHolding.query.filter(
            PortfolioHolding.quantity > 0
        ).join(BrokerAccount).filter(
            BrokerAccount.user_id == user_id
        ).all()
        
        unique_assets = {h.asset_id: h.asset for h in holdings}
        
        # Actualizar cada asset
        updated = 0
        failed = 0
        
        for asset in unique_assets.values():
            if self.update_asset_price(asset):
                updated += 1
            else:
                failed += 1
        
        # Commit una sola vez al final
        db.session.commit()
        
        return {
            'updated': updated,
            'failed': failed,
            'total': len(unique_assets)
        }
```

#### **B. Crear ruta para actualización**

```python
# app/routes/portfolio.py

@portfolio_bp.route('/prices/update', methods=['POST'])
@login_required
def update_prices():
    """Actualizar precios de todos los assets del usuario"""
    from app.services.market_data.price_updater import PriceUpdater
    
    updater = PriceUpdater()
    result = updater.update_all_prices(current_user.id)
    
    flash(
        f"✅ Precios actualizados: {result['updated']} exitosos, "
        f"{result['failed']} fallidos de {result['total']} assets",
        "success"
    )
    
    return redirect(url_for('portfolio.holdings_list'))
```

---

### **FASE 3: UI y Visualización (Días 4-5)**

#### **A. Dashboard con valores de mercado**

```html
<!-- app/templates/portfolio/dashboard.html -->

<div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
    <!-- Card: Valor Total -->
    <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center justify-between">
            <div>
                <p class="text-sm text-gray-600">Valor Total</p>
                <p class="text-2xl font-bold text-gray-900">
                    {{ total_market_value|decimal_eu(2) }} EUR
                </p>
                {% if total_change_percent %}
                <p class="text-sm {% if total_change_percent >= 0 %}text-green-600{% else %}text-red-600{% endif %}">
                    {% if total_change_percent >= 0 %}↑{% else %}↓{% endif %}
                    {{ total_change_percent|abs|decimal_eu(2) }}% hoy
                </p>
                {% endif %}
            </div>
            <div class="text-4xl">💰</div>
        </div>
    </div>
    
    <!-- Card: P&L No Realizado -->
    <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center justify-between">
            <div>
                <p class="text-sm text-gray-600">P&L No Realizado</p>
                <p class="text-2xl font-bold {% if unrealized_pl >= 0 %}text-green-600{% else %}text-red-600{% endif %}">
                    {{ unrealized_pl|decimal_eu(2) }} EUR
                </p>
                <p class="text-sm text-gray-600">
                    {{ unrealized_pl_percent|decimal_eu(2) }}%
                </p>
            </div>
            <div class="text-4xl">📊</div>
        </div>
    </div>
    
    <!-- Card: Costo Total -->
    <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center justify-between">
            <div>
                <p class="text-sm text-gray-600">Costo Total</p>
                <p class="text-2xl font-bold text-gray-900">
                    {{ total_cost|decimal_eu(2) }} EUR
                </p>
            </div>
            <div class="text-4xl">💵</div>
        </div>
    </div>
    
    <!-- Card: Rendimiento Total -->
    <div class="bg-white rounded-lg shadow p-6">
        <div class="flex items-center justify-between">
            <div>
                <p class="text-sm text-gray-600">Rendimiento Total</p>
                <p class="text-2xl font-bold {% if total_return_percent >= 0 %}text-green-600{% else %}text-red-600{% endif %}">
                    {{ total_return_percent|decimal_eu(2) }}%
                </p>
                <p class="text-sm text-gray-600">
                    {{ total_return|decimal_eu(2) }} EUR
                </p>
            </div>
            <div class="text-4xl">🎯</div>
        </div>
    </div>
</div>

<!-- Botón de actualización -->
<div class="mb-6">
    <form action="{{ url_for('portfolio.update_prices') }}" method="POST">
        {{ csrf_input }}
        <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg">
            🔄 Actualizar Precios
        </button>
        {% if last_update %}
        <span class="text-sm text-gray-600 ml-4">
            Última actualización: {{ last_update.strftime('%d/%m/%Y %H:%M') }}
        </span>
        {% endif %}
    </form>
</div>
```

#### **B. Tabla de holdings mejorada**

```html
<!-- Tabla con precios actuales y P&L -->
<table class="min-w-full divide-y divide-gray-200">
    <thead class="bg-gray-50">
        <tr>
            <th>Asset</th>
            <th>Cantidad</th>
            <th>Precio Actual</th>
            <th>Cambio Hoy</th>
            <th>Valor Mercado</th>
            <th>Costo Total</th>
            <th>P&L No Realizado</th>
        </tr>
    </thead>
    <tbody>
        {% for holding in holdings %}
        <tr>
            <!-- Asset -->
            <td>
                <div>
                    <span class="font-semibold">{{ holding.asset.symbol }}</span>
                    <div class="text-sm text-gray-600">
                        {{ holding.asset.name or holding.asset.symbol }}
                    </div>
                    {% if holding.asset.sector %}
                    <div class="text-xs text-gray-500">
                        {{ holding.asset.sector }} • {{ holding.asset.industry }}
                    </div>
                    {% endif %}
                </div>
            </td>
            
            <!-- Cantidad -->
            <td>{{ holding.quantity|number_eu }}</td>
            
            <!-- Precio Actual -->
            <td>
                {% if holding.asset.current_price %}
                    {{ holding.asset.current_price|decimal_eu(2) }} {{ holding.asset.currency }}
                    <div class="text-xs text-gray-500">
                        {{ holding.average_buy_price|decimal_eu(2) }} avg
                    </div>
                {% else %}
                    <span class="text-gray-400">-</span>
                {% endif %}
            </td>
            
            <!-- Cambio Hoy -->
            <td>
                {% if holding.asset.day_change_percent %}
                    <span class="{% if holding.asset.day_change_percent >= 0 %}text-green-600{% else %}text-red-600{% endif %}">
                        {% if holding.asset.day_change_percent >= 0 %}↑{% else %}↓{% endif %}
                        {{ holding.asset.day_change_percent|abs|decimal_eu(2) }}%
                    </span>
                {% else %}
                    <span class="text-gray-400">-</span>
                {% endif %}
            </td>
            
            <!-- Valor Mercado -->
            <td>
                {% if holding.current_market_value_eur %}
                    <span class="font-semibold">
                        {{ holding.current_market_value_eur|decimal_eu(2) }} EUR
                    </span>
                {% else %}
                    <span class="text-gray-400">-</span>
                {% endif %}
            </td>
            
            <!-- Costo Total -->
            <td>{{ holding.total_cost|decimal_eu(2) }} EUR</td>
            
            <!-- P&L No Realizado -->
            <td>
                {% if holding.unrealized_pl %}
                    <span class="font-semibold {% if holding.unrealized_pl >= 0 %}text-green-600{% else %}text-red-600{% endif %}">
                        {{ holding.unrealized_pl|decimal_eu(2) }} EUR
                        <div class="text-xs">
                            ({{ holding.unrealized_pl_percent|decimal_eu(2) }}%)
                        </div>
                    </span>
                {% else %}
                    <span class="text-gray-400">-</span>
                {% endif %}
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
```

---

### **FASE 4: Página de Detalles de Asset (Día 6)**

```html
<!-- app/templates/portfolio/asset_detail.html -->

<div class="bg-white rounded-lg shadow p-6 mb-6">
    <!-- Header con nombre y precio -->
    <div class="flex items-center justify-between mb-6">
        <div>
            <h1 class="text-3xl font-bold">{{ asset.symbol }}</h1>
            <p class="text-lg text-gray-600">{{ asset.name }}</p>
            <p class="text-sm text-gray-500">
                {{ asset.sector }} • {{ asset.industry }} • {{ asset.country }}
            </p>
        </div>
        <div class="text-right">
            <p class="text-3xl font-bold">
                {{ asset.current_price|decimal_eu(2) }} {{ asset.currency }}
            </p>
            <p class="{% if asset.day_change_percent >= 0 %}text-green-600{% else %}text-red-600{% endif %}">
                {% if asset.day_change_percent >= 0 %}↑{% else %}↓{% endif %}
                {{ asset.day_change_percent|abs|decimal_eu(2) }}%
            </p>
        </div>
    </div>
    
    <!-- Grid de métricas -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <!-- Market Cap -->
        <div>
            <p class="text-sm text-gray-600">Market Cap</p>
            <p class="text-lg font-semibold">{{ asset.market_cap_formatted }}</p>
            <p class="text-xs text-gray-500">{{ asset.market_cap_eur|decimal_eu(0) }} EUR</p>
        </div>
        
        <!-- P/E Ratio -->
        <div>
            <p class="text-sm text-gray-600">P/E Ratio</p>
            <p class="text-lg font-semibold">
                {{ asset.trailing_pe|decimal_eu(2) if asset.trailing_pe else '-' }}
            </p>
            <p class="text-xs text-gray-500">
                Forward: {{ asset.forward_pe|decimal_eu(2) if asset.forward_pe else '-' }}
            </p>
        </div>
        
        <!-- Beta -->
        <div>
            <p class="text-sm text-gray-600">Beta (riesgo)</p>
            <p class="text-lg font-semibold">
                {{ asset.beta|decimal_eu(2) if asset.beta else '-' }}
            </p>
        </div>
        
        <!-- Dividend Yield -->
        <div>
            <p class="text-sm text-gray-600">Dividend Yield</p>
            <p class="text-lg font-semibold">
                {% if asset.dividend_yield %}
                    {{ (asset.dividend_yield * 100)|decimal_eu(2) }}%
                {% else %}
                    -
                {% endif %}
            </p>
            <p class="text-xs text-gray-500">
                {{ asset.dividend_rate|decimal_eu(2) if asset.dividend_rate else '-' }} anual
            </p>
        </div>
    </div>
    
    <!-- Recomendación de analistas -->
    {% if asset.recommendation_key %}
    <div class="border-t pt-4">
        <div class="flex items-center justify-between">
            <div>
                <p class="text-sm text-gray-600">Recomendación</p>
                <span class="inline-block px-3 py-1 {{ asset.recommendation_badge_color }} text-white rounded-full text-sm font-medium">
                    {{ asset.recommendation_key|upper }}
                </span>
            </div>
            <div class="text-right">
                <p class="text-sm text-gray-600">Precio Objetivo</p>
                <p class="text-lg font-semibold">
                    {{ asset.target_mean_price|decimal_eu(2) if asset.target_mean_price else '-' }} {{ asset.currency }}
                </p>
                <p class="text-xs text-gray-500">
                    {{ asset.number_of_analyst_opinions }} analistas
                </p>
            </div>
        </div>
    </div>
    {% endif %}
</div>
```

---

## 📅 CRONOGRAMA

```
┌─────────────────────────────────────────────────────────────┐
│ SPRINT 3 - FASE FINAL (1-2 semanas)                        │
├─────────────────────────────────────────────────────────────┤
│ Día 1:  Migración BD + Actualizar modelos                  │
│ Día 2-3: PriceUpdater service + ruta de actualización      │
│ Día 4-5: Dashboard mejorado + tabla de holdings            │
│ Día 6:   Página de detalles de asset                       │
│ Día 7:   Testing y ajustes                                 │
│ Día 8:   Deploy a producción + Tag v3.4.0                  │
└─────────────────────────────────────────────────────────────┘
```

---

## ✅ CRITERIOS DE ACEPTACIÓN

1. ✅ Botón "🔄 Actualizar Precios" funcional
2. ✅ Precios actuales mostrados en holdings
3. ✅ Valor de mercado calculado correctamente
4. ✅ P&L No Realizado calculado y mostrado
5. ✅ Dashboard con cards de resumen
6. ✅ Tabla de holdings con todos los campos nuevos
7. ✅ MarketCap formateado (K/M/B) y convertido a EUR
8. ✅ Colores indicadores (verde/rojo) funcionando
9. ✅ Página de detalles de asset con todas las métricas
10. ✅ Sin errores en producción

---

## 🚀 DESPUÉS DE ESTA FASE

Una vez completado Sprint 3 Final:
- ✅ Tag: `v3.4.0`
- ✅ Actualizar `TU_PLAN_MAESTRO.md`
- ✅ Documentar en `SPRINT3_DISEÑO_BD.md`
- 🎯 Continuar con **Sprint 4: Calculadora de Métricas Avanzadas**

---

**Última actualización:** 3 Noviembre 2025  
**Estado:** 📝 PLANIFICADO - Listo para implementar

