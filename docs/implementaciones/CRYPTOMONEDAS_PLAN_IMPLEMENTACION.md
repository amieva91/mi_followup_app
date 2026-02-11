# Plan de Implementación — Módulo Cryptomonedas (FollowUp)

**Versión**: 1.1  
**Fecha**: 29 Enero 2026  
**Estado**: ✅ Fases 1-5 implementadas (Parser, Importer, Métricas, UI)

---

## 1. Resumen ejecutivo

Nuevo módulo **Cryptomonedas** en FollowUp, situado en la navegación entre Portfolio y el nombre de usuario. Fuente de datos única: extracto **Revolut X** (revx-account-statement).

### Alcance acordado

| Requisito | Descripción |
|-----------|-------------|
| **Fiat** | Dinero bancario en EUR |
| **Cuasi-fiat** | Stablecoins (USDT, etc.) tratadas como “cuasi-fiat” |
| **Fiat total** | Suma fiat + cuasi-fiat en EUR, con desglose opcional |
| **Posiciones** | Cantidad invertida (EUR) y unidades por activo |
| **Precios** | Yahoo Finance al pulsar “Actualizar” |
| **Fees** | Incluidas en costes y rentabilidad |
| **Solo inversión** | Excluir pagos en comercios, Card Payment, ATM |
| **Rewards** | Tipo dividendo (coste 0), rentabilidad total incluyendo rewards, desglose por activo |

---

## 2. Formato CSV Revolut X (revx)

### Estructura

```
Symbol,Type,Quantity,Price,Value,Fees,Date
XRP,Buy,16.975237,€0.40,€6.76,€0.00,"21 Jun 2019, 20:52:02"
ADA,Staking reward,0.147455,,,,"22 Nov 2024, 13:47:40"
USDT,Receive,39,€0.85,€33.08,€0.00,"3 Feb 2026, 00:00:43"
```

### Tipos de transacción

| Type | Descripción | Mapeo interno |
|------|-------------|---------------|
| Buy | Compra de crypto | BUY |
| Sell | Venta de crypto | SELL |
| Receive | Entrada (ej. USDT) | RECEIVE / BUY coste 0 |
| Staking reward | Reward | STAKING_REWARD (coste 0) |

### Campos

| Columna | Tipo | Notas |
|---------|------|-------|
| Symbol | string | BTC, ETH, ADA, XRP, USDT, etc. |
| Type | string | Buy, Sell, Receive, Staking reward |
| Quantity | float | Unidades |
| Price | string | Ej. €0.40 — puede ir vacío en rewards |
| Value | string | Ej. €6.76 — importe en EUR |
| Fees | string | Ej. €0.00 |
| Date | string | "21 Jun 2019, 20:52:02" |

---

## 3. Arquitectura y modelo de datos

### 3.1 Reutilización de modelos existentes

El módulo aprovecha la estructura actual de Portfolio:

| Modelo | Uso en Cryptomonedas |
|--------|----------------------|
| **BrokerAccount** | Cuenta Revolut (broker predefinido) |
| **Asset** | Crypto (BTC, ETH, ADA, USDT...) con `asset_type='Crypto'` |
| **Transaction** | Buy, Sell, Staking reward; `source='CSV_REVOLUT_X'` |
| **PortfolioHolding** | Posiciones actuales por asset |
| **AssetRegistry** | Cache global de activos |
| **MappingRegistry** | Mapeo de símbolos a Yahoo (ej. ADA → ADA-EUR) |

### 3.2 Consideraciones específicas para crypto

1. **Asset sin ISIN**: Criptomonedas usan solo `symbol`. ISIN puede ser `null` o derivado (ej. `CRYPTO:BTC`).
2. **Stablecoins = cuasi-fiat**: USDT, USDC, BUSD, DAI → se agrupan y valoran en EUR.
3. **Rewards**: `transaction_type='STAKING_REWARD'`, coste 0, `amount` = valor en EUR (precio actual en fecha reward, o 0 si no aplica).
4. **Broker Revolut**: Crear registro en `brokers` si no existe (ej. name="Revolut", full_name="Revolut X - Criptomonedas").

### 3.3 Extensiones opcionales (futuras)

- Tabla `CryptoReward` para desglose detallado de rewards por asset.
- Campo `is_stablecoin` en Asset para identificar cuasi-fiat automáticamente.
- Vista materializada o métricas cacheadas para rendimiento.

---

## 4. Fases de implementación

### Fase 1 — Parser y detección (Semana 1)

| Tarea | Descripción | Archivos |
|-------|-------------|----------|
| 1.1 | Extender `CSVDetector` para formato REVOLUT_X | `app/services/csv_detector.py` |
| 1.2 | Crear `RevolutXParser` | `app/services/parsers/revolut_x_parser.py` |
| 1.3 | Normalizar fechas ("21 Jun 2019, 20:52:02" → datetime) | Parser |
| 1.4 | Normalizar montos (€6.76 → 6.76 float) | Parser |
| 1.5 | Mapear tipos: Buy, Sell, Receive, Staking reward | Parser |
| 1.6 | Tests unitarios del parser | `tests/unit/test_revolut_x_parser.py` |

**Criterio de detección revx**: Primera fila con columnas `Symbol,Type,Quantity,Price,Value,Fees,Date`.

### Fase 2 — Importer e integración con BD (Semana 2)

| Tarea | Descripción | Archivos |
|-------|-------------|----------|
| 2.1 | Extender `CSVImporterV2` o crear `CryptoImporter` | `app/services/crypto_importer.py` |
| 2.2 | Crear cuenta Revolut si no existe | Importer + `Broker` |
| 2.3 | Crear/obtener Assets crypto (sin ISIN) | Importer + `AssetRegistry` |
| 2.4 | Insertar Transactions (BUY, SELL, STAKING_REWARD) | Importer |
| 2.5 | Detección de duplicados (fecha + symbol + type + quantity + amount) | Importer |
| 2.6 | Integrar con flujo de subida CSV existente | `app/routes/portfolio.py` |

**Lógica de duplicados**: Hash de `(transaction_date, symbol, type, quantity, amount)` para comparar con transacciones existentes del usuario en la misma cuenta.

### Fase 3 — Lógica de negocio (Semana 2-3)

| Tarea | Descripción | Archivos |
|-------|-------------|----------|
| 3.1 | Cálculo de posiciones (Buy - Sell + Rewards) | Reutilizar FIFO / `PortfolioHolding` |
| 3.2 | Fiat total = capital invertido (suma Buy + Fees) | Servicio |
| 3.3 | Cuasi-fiat = posición en USDT/stablecoins valorada en EUR | Servicio |
| 3.4 | Rentabilidad total incluyendo rewards | Servicio |
| 3.5 | Desglose “cuánto viene de rewards” | Servicio |
| 3.6 | Yield de reward por activo | Servicio |

**Servicio propuesto**: `app/services/crypto_metrics.py` — funciones para fiat, cuasi-fiat, rentabilidad, rewards.

### Fase 4 — Yahoo Finance y mapeo (Semana 3)

| Tarea | Descripción | Archivos |
|-------|-------------|----------|
| 4.1 | Mapeo por defecto: ADA→ADA-EUR, BTC→BTC-EUR, ETH→ETH-EUR, etc. | `MappingRegistry` / seed |
| 4.2 | Integración con flujo “Actualizar Precios” | Reutilizar lógica actual |
| 4.3 | Sección de mapeo en UI para corregir símbolos Yahoo | Extender vista de mapeos |
| 4.4 | USDT: 1:1 USD, conversión USD→EUR | `currency_service` |

### Fase 5 — UI del módulo Cryptomonedas (Semana 4)

| Tarea | Descripción | Archivos |
|-------|-------------|----------|
| 5.1 | Blueprint `crypto_bp` y rutas | `app/routes/crypto.py` |
| 5.2 | Entry en navbar (entre Portfolio y usuario) | `base/layout.html` |
| 5.3 | Dashboard: fiat total, cuasi-fiat, posiciones, rentabilidad | `templates/crypto/dashboard.html` |
| 5.4 | Subida CSV (reutilizar componente de Portfolio) | `templates/crypto/import.html` |
| 5.5 | Lista de posiciones con desglose rewards | `templates/crypto/holdings.html` |
| 5.6 | Botón “Actualizar Precios” | Reutilizar lógica Portfolio |
| 5.7 | Desglose fiat / cuasi-fiat (opcional) | Dashboard |

### Fase 6 — Refinamiento y pruebas (Semana 5)

| Tarea | Descripción |
|-------|-------------|
| 6.1 | Tests de integración (subida CSV → holdings correctos) |
| 6.2 | Verificación de duplicados |
| 6.3 | Verificación de rentabilidad con rewards |
| 6.4 | Documentación de usuario |

---

## 5. Diseño técnico detallado

### 5.1 Parser Revolut X

```python
# Pseudocódigo RevolutXParser.parse(file_path)
def parse(file_path):
    rows = csv.DictReader(...)
    transactions = []
    for row in rows:
        tx = {
            'symbol': row['Symbol'],
            'type': normalize_type(row['Type']),  # 'BUY'|'SELL'|'RECEIVE'|'STAKING_REWARD'
            'quantity': float(row['Quantity']),
            'price': parse_amount(row['Price']),   # €0.40 → 0.40
            'value': parse_amount(row['Value']),   # €6.76 → 6.76
            'fees': parse_amount(row['Fees']),
            'date': parse_date(row['Date'])        # "21 Jun 2019, 20:52:02"
        }
        transactions.append(tx)
    return {'transactions': transactions, 'format': 'REVOLUT_X'}
```

### 5.2 Mapeo de tipos

| CSV Type | transaction_type | Observaciones |
|----------|------------------|---------------|
| Buy | BUY | amount = -abs(value), quantity > 0 |
| Sell | SELL | amount = +abs(value), quantity > 0 |
| Receive | BUY | amount = -abs(value), coste 0 (o RECEIVE si se añade tipo) |
| Staking reward | STAKING_REWARD | amount = 0 (coste 0), quantity > 0 |

### 5.3 Detección de duplicados

```python
def _tx_signature(tx):
    return (
        tx['date'].isoformat(),
        tx['symbol'],
        tx['type'],
        round(tx['quantity'], 8),
        round(tx.get('value', 0), 2)
    )
```

### 5.4 Cálculo fiat y cuasi-fiat

- **Capital invertido (aproximación fiat)**: Suma de `abs(amount)` de BUY + `fees` en EUR.
- **Cuasi-fiat**: Posición actual en USDT (y otras stablecoins) × precio EUR (1 USDT ≈ 1 USD → conversión BCE).
- **Fiat total**: Capital invertido + valor cuasi-fiat en EUR (o definir si fiat = solo capital, según requisito final).

---

## 6. Rutas propuestas

| Ruta | Método | Descripción |
|------|--------|-------------|
| `/crypto` | GET | Dashboard principal |
| `/crypto/import` | GET, POST | Subida CSV Revolut X |
| `/crypto/holdings` | GET | Lista de posiciones |
| `/crypto/transactions` | GET | Histórico de transacciones |
| `/crypto/update-prices` | POST | Actualizar precios Yahoo |
| `/crypto/mapping` | GET, POST | Mapeo símbolos Yahoo |

---

## 7. Dependencias y consideraciones

### Dependencias existentes

- Flask, Flask-Login
- SQLAlchemy
- `csv_detector`, `importer_v2`, `fifo_calculator`
- `asset_registry_service`, `currency_service`
- Yahoo Finance (yfinance o API propia)

### Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Cambio de formato RevX | Validar headers y columnas; mensaje claro si falla |
| Rate limit Yahoo | Cache de precios; botón manual de actualización |
| Stablecoins sin ticker Yahoo | USDT-USD, conversión a EUR; fallback a 1:1 |

---

## 8. Criterios de aceptación

1. Subir CSV revx y crear/actualizar cuenta Revolut automáticamente.
2. Posiciones correctas por crypto (Buy - Sell + Staking reward).
3. Fiat total y cuasi-fiat mostrados en EUR con desglose opcional.
4. Rentabilidad total incluyendo rewards, con desglose “de rewards”.
5. Actualización de precios vía Yahoo Finance.
6. Duplicados no se importan dos veces.
7. Mapeo de símbolos editable (ADA → ADA-EUR, etc.).
8. UI coherente con el resto de FollowUp (Tailwind, Alpine.js).

---

## 9. Changelog

| Fecha | Cambio |
|-------|--------|
| 29 Ene 2026 | Módulo inicial: parser, importer, métricas, dashboard |
| 29 Ene 2026 | Columna **Precio medio** en tabla de posiciones |
| 29 Ene 2026 | Script `docs/scripts/ajuste_ada_revolut.py` para ajuste manual ADA (coincidencia con saldo Revolut) |
| 29 Ene 2026 | Guía **Revolut X** en página Importar CSV (Documentos y extractos → Extracto de cuenta) |

---

## 10. Referencias

- CSV de ejemplo: `revx-account-statement_2018-10-18_2026-02-08_es-es_1442ce.csv`
- Especificación funcional: conversaciones previas (resumen en contexto)
- Código de referencia: `app/services/parsers/degiro_transactions_parser.py`, `ibkr_parser.py`
- Diseño: `DESIGN_SYSTEM.md`
