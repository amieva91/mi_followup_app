# 📊 Sprint 3 - Diseño de Base de Datos y Arquitectura

**Fecha**: 6 Octubre 2025  
**Objetivo**: Portfolio Manager con CSV Processor (IBKR + DeGiro)

---

## 🗄️ MODELOS DE BASE DE DATOS

### 1. **Broker** (Catálogo de Brokers)

```python
class Broker(db.Model):
    __tablename__ = 'brokers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # 'IBKR', 'DeGiro', 'Manual'
    full_name = db.Column(db.String(100))  # 'Interactive Brokers'
    is_active = db.Column(db.Boolean, default=True)
    
    # Relaciones
    accounts = db.relationship('BrokerAccount', backref='broker', lazy=True)
```

**Datos iniciales**:
- IBKR - Interactive Brokers
- DeGiro
- Manual

---

### 2. **BrokerAccount** (Cuentas de usuario en brokers)

```python
class BrokerAccount(db.Model):
    __tablename__ = 'broker_accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    broker_id = db.Column(db.Integer, db.ForeignKey('brokers.id'), nullable=False)
    
    account_number = db.Column(db.String(50), nullable=True)  # 'U12722327'
    account_name = db.Column(db.String(100))  # Nombre descriptivo
    base_currency = db.Column(db.String(3), default='EUR')  # Divisa base
    
    # Control de margen/apalancamiento
    margin_enabled = db.Column(db.Boolean, default=False)
    current_cash = db.Column(db.Float, default=0.0)  # Efectivo disponible
    margin_used = db.Column(db.Float, default=0.0)  # Margen utilizado
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relaciones
    user = db.relationship('User', backref=db.backref('broker_accounts', lazy=True))
    holdings = db.relationship('PortfolioHolding', backref='account', lazy=True)
    transactions = db.relationship('Transaction', backref='account', lazy=True)
```

---

### 3. **Asset** (Catálogo de Activos)

```python
class Asset(db.Model):
    __tablename__ = 'assets'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Identificadores
    symbol = db.Column(db.String(20), nullable=False, index=True)  # 'AAPL', '9997'
    isin = db.Column(db.String(12), unique=True, index=True)  # 'US0378331005'
    name = db.Column(db.String(200), nullable=False)  # 'Apple Inc.'
    
    # Clasificación
    asset_type = db.Column(db.String(20), nullable=False)  # 'Stock', 'ETF', 'Bond', 'Crypto'
    sector = db.Column(db.String(50))  # 'Technology', 'Finance'
    exchange = db.Column(db.String(10))  # 'NASDAQ', 'HKG', 'WSE'
    currency = db.Column(db.String(3), nullable=False)  # 'USD', 'EUR', 'HKD'
    
    # Para actualización de precios
    yahoo_symbol = db.Column(db.String(20))  # Símbolo para Yahoo Finance API
    last_price = db.Column(db.Float)  # Último precio conocido
    last_price_update = db.Column(db.DateTime)  # Última actualización
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    holdings = db.relationship('PortfolioHolding', backref='asset', lazy=True)
    transactions = db.relationship('Transaction', backref='asset', lazy=True)
    price_history = db.relationship('PriceHistory', backref='asset', lazy=True)
```

**Índices**:
- `symbol` (búsqueda rápida)
- `isin` (único, búsqueda por CSV)

---

### 4. **PortfolioHolding** (Posiciones Actuales)

```python
class PortfolioHolding(db.Model):
    __tablename__ = 'portfolio_holdings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('broker_accounts.id'), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    
    # Datos de la posición
    quantity = db.Column(db.Float, nullable=False)  # Cantidad actual
    average_buy_price = db.Column(db.Float, nullable=False)  # Precio medio de compra
    total_cost = db.Column(db.Float, nullable=False)  # Coste total (base de coste)
    
    # Información adicional
    first_purchase_date = db.Column(db.Date, nullable=False)
    last_transaction_date = db.Column(db.Date)
    
    # P&L Calculadas (actualizables)
    current_price = db.Column(db.Float)  # Precio actual de mercado
    current_value = db.Column(db.Float)  # Valor actual (quantity * current_price)
    unrealized_pl = db.Column(db.Float)  # P&L no realizadas (latentes)
    unrealized_pl_pct = db.Column(db.Float)  # % de retorno no realizado
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    user = db.relationship('User', backref=db.backref('holdings', lazy=True))
    
    # Constraint: Una sola posición por activo-cuenta
    __table_args__ = (
        db.UniqueConstraint('account_id', 'asset_id', name='unique_account_asset'),
    )
```

---

### 5. **Transaction** (Todas las Transacciones)

```python
class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('broker_accounts.id'), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=True)  # Null para cash ops
    
    # Información básica
    transaction_type = db.Column(db.String(20), nullable=False)
    # Tipos: 'BUY', 'SELL', 'DIVIDEND', 'FEE', 'INTEREST', 'TAX', 'DEPOSIT', 'WITHDRAWAL'
    
    transaction_date = db.Column(db.DateTime, nullable=False, index=True)
    settlement_date = db.Column(db.Date)  # Fecha valor
    
    # Detalles financieros
    quantity = db.Column(db.Float)  # Para compra/venta (null para dividendos/comisiones)
    price = db.Column(db.Float)  # Precio por unidad
    amount = db.Column(db.Float, nullable=False)  # Monto total (+ ingreso, - gasto)
    currency = db.Column(db.String(3), nullable=False)
    
    # Costes asociados
    commission = db.Column(db.Float, default=0.0)  # Comisión
    fees = db.Column(db.Float, default=0.0)  # Otros gastos
    tax = db.Column(db.Float, default=0.0)  # Impuestos/retenciones
    
    # P&L (para ventas)
    realized_pl = db.Column(db.Float)  # P&L realizada en esta transacción
    realized_pl_pct = db.Column(db.Float)  # % de retorno realizado
    
    # Identificadores externos
    external_id = db.Column(db.String(100))  # ID de orden del broker
    
    # Metadata
    description = db.Column(db.String(500))  # Descripción de la transacción
    notes = db.Column(db.Text)  # Notas del usuario
    source = db.Column(db.String(20), default='MANUAL')  # 'CSV_IBKR', 'CSV_DEGIRO', 'MANUAL'
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    user = db.relationship('User', backref=db.backref('transactions', lazy=True))
```

**Índices**:
- `transaction_date` (búsquedas por fecha)
- `user_id, transaction_date` (consultas de usuario)
- `asset_id, transaction_type` (análisis por activo)

---

### 6. **CashFlow** (Depósitos y Retiradas)

```python
class CashFlow(db.Model):
    __tablename__ = 'cash_flows'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('broker_accounts.id'), nullable=False)
    
    flow_type = db.Column(db.String(20), nullable=False)  # 'DEPOSIT', 'WITHDRAWAL'
    amount = db.Column(db.Float, nullable=False)  # + para depósito, - para retirada
    currency = db.Column(db.String(3), nullable=False)
    
    flow_date = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.String(500))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    user = db.relationship('User', backref=db.backref('cash_flows', lazy=True))
```

---

### 7. **PriceHistory** (Histórico de Precios)

```python
class PriceHistory(db.Model):
    __tablename__ = 'price_history'
    
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    
    date = db.Column(db.Date, nullable=False, index=True)
    open_price = db.Column(db.Float)
    high_price = db.Column(db.Float)
    low_price = db.Column(db.Float)
    close_price = db.Column(db.Float, nullable=False)
    volume = db.Column(db.BigInteger)
    
    source = db.Column(db.String(20), default='YAHOO')  # 'YAHOO', 'MANUAL'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Constraint: Un precio por día por activo
    __table_args__ = (
        db.UniqueConstraint('asset_id', 'date', name='unique_asset_date'),
    )
```

---

### 8. **PortfolioMetrics** (Métricas Calculadas - MTD/YTD)

```python
class PortfolioMetrics(db.Model):
    __tablename__ = 'portfolio_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('broker_accounts.id'))  # Null = todas las cuentas
    
    # Período
    metric_date = db.Column(db.Date, nullable=False, index=True)
    metric_type = db.Column(db.String(20), nullable=False)  # 'DAILY', 'MONTHLY', 'YEARLY'
    
    # Valores del portfolio
    total_value = db.Column(db.Float, nullable=False)  # Valor total
    total_cost = db.Column(db.Float, nullable=False)  # Coste total invertido
    cash_balance = db.Column(db.Float, default=0.0)  # Efectivo disponible
    
    # P&L
    realized_pl = db.Column(db.Float, default=0.0)  # P&L realizadas acumuladas
    unrealized_pl = db.Column(db.Float, default=0.0)  # P&L no realizadas actuales
    total_pl = db.Column(db.Float, default=0.0)  # Total P&L
    
    # Retornos
    total_return_pct = db.Column(db.Float)  # Retorno total %
    mtd_return_pct = db.Column(db.Float)  # Retorno del mes %
    ytd_return_pct = db.Column(db.Float)  # Retorno del año %
    
    # Apalancamiento
    margin_used = db.Column(db.Float, default=0.0)
    leverage_ratio = db.Column(db.Float)  # Ratio de apalancamiento
    
    # Métricas de riesgo (para fase 3)
    sharpe_ratio = db.Column(db.Float)
    max_drawdown = db.Column(db.Float)
    volatility = db.Column(db.Float)
    
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    user = db.relationship('User', backref=db.backref('metrics', lazy=True))
```

---

## 🏗️ ARQUITECTURA DEL CSV PROCESSOR

### Flujo de Procesamiento

```
1. Usuario sube CSV
   ↓
2. CSVDetector identifica formato (IBKR vs DeGiro)
   ↓
3. Parser correspondiente procesa el archivo
   ↓
4. Normalizer convierte a formato estándar
   ↓
5. Importer guarda en BD
   ↓
6. Calculator actualiza métricas
```

### Componentes

#### **1. CSVDetector** (`app/services/csv_detector.py`)
```python
def detect_format(file_path):
    """
    Detecta si es IBKR o DeGiro
    Returns: 'IBKR', 'DEGIRO', o 'UNKNOWN'
    """
```

#### **2. Parsers** (`app/services/parsers/`)
- `ibkr_parser.py` - Parser para IBKR Activity Statement
- `degiro_parser.py` - Parser para DeGiro Account Statement

Cada parser devuelve:
```python
{
    'account_info': {...},
    'holdings': [...],
    'transactions': [...],
    'cash_flows': [...],
    'metrics': {...}
}
```

#### **3. Normalizer** (`app/services/normalizer.py`)
Convierte datos de cualquier parser a formato estándar para BD

#### **4. Importer** (`app/services/importer.py`)
Guarda datos normalizados en la base de datos, manejando:
- Deduplicación (evitar importar dos veces)
- Actualización de holdings
- Cálculo de P&L

#### **5. PriceUpdater** (`app/services/price_updater.py`)
- Actualiza precios desde Yahoo Finance
- Calcula P&L no realizadas

#### **6. MetricsCalculator** (`app/services/metrics_calculator.py`)
Calcula todas las métricas:
- Retornos (total, MTD, YTD)
- P&L realizadas vs no realizadas
- Apalancamiento
- Métricas de riesgo (Sharpe, drawdown)

---

## 📁 ESTRUCTURA DE DIRECTORIOS

```
app/
├── models/
│   ├── __init__.py
│   ├── broker.py
│   ├── asset.py
│   ├── portfolio.py
│   ├── transaction.py
│   └── metrics.py
│
├── services/
│   ├── __init__.py
│   ├── csv_detector.py
│   ├── normalizer.py
│   ├── importer.py
│   ├── price_updater.py
│   ├── metrics_calculator.py
│   └── parsers/
│       ├── __init__.py
│       ├── ibkr_parser.py
│       └── degiro_parser.py
│
├── routes/
│   ├── portfolio.py  (CRUD manual de holdings)
│   ├── transactions.py  (Lista de transacciones)
│   └── csv_upload.py  (Upload de CSVs)
│
├── forms/
│   └── portfolio_forms.py
│
└── templates/
    └── portfolio/
        ├── dashboard.html
        ├── holdings.html
        ├── transactions.html
        ├── upload_csv.html
        └── manual_entry.html
```

---

## 🔄 FLUJO DE CÁLCULO DE P&L

### P&L Realizadas (al vender)
Método: **FIFO (First In, First Out)**

1. Al vender N acciones:
   - Obtener las N primeras compras (por fecha)
   - Calcular coste de esas N acciones
   - P&L = Precio venta - Coste medio de esas N acciones

2. Actualizar holding:
   - Reducir cantidad
   - Recalcular precio medio de compra

### P&L No Realizadas (actuales)
```python
unrealized_pl = (current_price - average_buy_price) * quantity
unrealized_pl_pct = (unrealized_pl / total_cost) * 100
```

---

## 📊 ÍNDICES Y OPTIMIZACIONES

### Índices Principales
```sql
-- Búsquedas frecuentes
CREATE INDEX idx_transactions_user_date ON transactions(user_id, transaction_date);
CREATE INDEX idx_transactions_asset_type ON transactions(asset_id, transaction_type);
CREATE INDEX idx_holdings_user ON portfolio_holdings(user_id);
CREATE INDEX idx_assets_isin ON assets(isin);
CREATE INDEX idx_assets_symbol ON assets(symbol);
CREATE INDEX idx_price_history_asset_date ON price_history(asset_id, date);
```

### Constraints
- **Unique**: `isin` en Assets
- **Unique**: `(account_id, asset_id)` en PortfolioHolding
- **Unique**: `(asset_id, date)` en PriceHistory
- **Check**: `quantity > 0` en PortfolioHolding

---

## 🧪 ESTRATEGIA DE TESTING

### Unit Tests
- Parsers (IBKR, DeGiro)
- Normalizer
- P&L Calculator (FIFO)
- Metrics Calculator

### Integration Tests
- Upload CSV completo → verificar BD
- Cálculo de portfolio completo
- Actualización de precios

### Test Data
- CSVs reales proporcionados (4 archivos)
- Casos edge: ventas parciales, dividendos, comisiones

---

## ⏱️ ESTIMACIÓN DE IMPLEMENTACIÓN

**HITO 1**: Fundamentos (Base de Datos + Arquitectura)
- Modelos de BD: 2 horas
- Migraciones: 1 hora
- Documentación: 1 hora (este archivo)
- **Total**: ~4 horas / 1 día

---

## ✅ CRITERIOS DE ACEPTACIÓN

- [ ] Todos los modelos creados con sus relaciones
- [ ] Migraciones ejecutadas en desarrollo
- [ ] Arquitectura documentada
- [ ] Sin errores de sintaxis o linting
- [ ] Aprobación del usuario

---

**Siguiente paso**: Crear los archivos de modelos e implementar

