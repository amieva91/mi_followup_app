# Implementación Acciones, Cryptomonedas y Metales - Febrero 2026

**Versión**: v9.0.0  
**Fecha**: 29 Enero 2026  
**Plan**: `docs/implementaciones/PLAN_ACCIONES_Y_METALES.md`

---

## Resumen ejecutivo

Implementación completa del plan de restructuración del Portfolio: nueva pestaña **Acciones** (Stock+ETF), módulo **Metales** (commodities) y consolidación de **Cryptomonedas**. Incluye fix crítico en valoración PortfolioValuation para commodities.

---

## Cambios implementados

### 1. Nueva pestaña Acciones (Stock + ETF)

- **Dropdown Acciones** en navbar con Cartera y Watchlist
- **Cartera**: vista de posiciones filtrada solo Stock + ETF
- **Indicadores**: Valor Cartera, Dinero Prestado/Cash, Dinero Usuario, B/P Total
- **Servicio** `stocks_etf_metrics.py` para métricas filtradas (apalancamiento excluye crypto)
- Portfolio dropdown: eliminados Posiciones y Watchlist (pasados a Acciones)

### 2. Módulo Metales (Commodity)

- **Blueprint** `metales` con dashboard y formulario compra/venta
- **Metales**: Oro (GC=F), Plata (SI=F), Platino (PL=F), Paladio (PA=F)
- **Unidad interna**: gramos (1 oz troy = 31,1035 g)
- **Precios**: Yahoo futuros USD/oz → conversión EUR
- **Formulario**: precio total EUR, entrada en gramos o oz
- **Dashboard**: precios €/oz, P&L, botón Actualizar precios
- **Cuenta Commodities** creada automáticamente en primera compra
- **asset_type** `Commodity` añadido al modelo Asset

### 3. Cryptomonedas

- Sin cambios de funcionalidad (ya existía)
- Integrado en Portfolio global (vista unificada)
- Filtro por asset_type en Transacciones incluye Crypto

### 4. Portfolio global

- **Dashboard**: incluye Stock, ETF, Crypto, Commodity
- **Transacciones**: filtro por tipo (Stock, ETF, Crypto, Commodity)
- **Gráficos**: distribución por tipo de activo incluye todos
- **Peso %**: corregida asignación de `current_value_eur` en holdings

### 5. Fix crítico: valoración Commodity en PortfolioValuation

- **Problema**: Metales almacenan cantidad en **gramos**; Yahoo devuelve precios en **USD/oz**
- **Bug**: `value = gramos × precio_USD/oz` inflaba el valor ~31×
- **Fix**: Conversión correcta `(gramos / 31,1035) × precio_USD/oz` → EUR
- **Archivos**: `app/services/metrics/portfolio_valuation.py` (get_value_at_date, get_detailed_value_at_date, get_user_money_at_date)
- **Impacto**: Rentabilidad Modified Dietz corregida (ej. 23% → ~13% cuando commodities mal valorados)

### 6. Correcciones menores

- Transacción plata ID 2593: corregido amount -1 EUR → -8,50 EUR (valor realista ene 2018)
- Botón Actualizar precios en dashboard Metales (modal + script)
- Columna peso % en Portfolio (current_value_eur ahora se asigna correctamente)

---

## Navegación final

```
Portfolio (dropdown)     Acciones (dropdown)     Cryptomonedas    Metales
├─ Dashboard             ├─ Cartera              [directo]        [directo]
├─ Performance           └─ Watchlist
├─ Divisas
├─ Transacciones
├─ Cuentas
├─ Nueva transacción
└─ Importar CSV
```

---

## Referencias

- Plan: `docs/implementaciones/PLAN_ACCIONES_Y_METALES.md`
- Cryptomonedas: `docs/implementaciones/CRYPTOMONEDAS_PLAN_IMPLEMENTACION.md`
