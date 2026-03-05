# Estrategia de caché - FollowUp

## Resumen

La aplicación usa caché en memoria para reducir llamadas a APIs externas y cálculos costosos.

## Componentes con caché

### 1. MetricsCache (`app/services/metrics/cache.py`)

- **Qué cachea**: Métricas pre-calculadas del portfolio (ROI, P&L, Modified Dietz, etc.)
- **TTL**: 24 horas
- **Almacenamiento**: Tabla `metrics_cache` (SQLite)
- **Invalidación**:
  - Automática: en transacciones nuevas/eliminadas, import CSV, actualización de precios
  - Manual: botón "♻️ Recalcular" en dashboard de portfolio

### 2. CurrencyService (`app/services/currency_service.py`)

- **Qué cachea**: Tasas de cambio a EUR (API ECB)
- **TTL**: 24 horas
- **Almacenamiento**: Variable global thread-safe (`_exchange_rates_cache`)
- **Invalidación**: Manual vía `get_exchange_rates(force_refresh=True)` o botón "🔄 Actualizar Tasas"

### 3. Mappers (Yahoo, Exchange)

- **Qué cachean**: Mapeos MIC→Yahoo, Exchange→Yahoo leídos de BD
- **TTL**: Hasta recarga de app o cambios en tabla `mapping_registry`
- **Almacenamiento**: Memoria en clases `YahooSuffixMapper`, `ExchangeMapper`

## Directrices

1. **Cache por capa**: Caché en servicios, no en rutas.
2. **Invalidación explícita**: Cada caché debe tener criterio claro de invalidación.
3. **Fallback**: Si API externa falla, usar cache antiguo o tasas/datos por defecto.
