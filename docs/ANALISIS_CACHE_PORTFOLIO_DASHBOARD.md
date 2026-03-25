# Análisis: Carga del Portfolio Dashboard y viabilidad de cache HIST+NOW

**Objetivo**: Identificar los datos que más tardan en cargarse en `/portfolio/` y valorar aplicar el patrón HIST+NOW (como en Performance e Index Comparison).

---

## 1. Flujo actual de datos (orden de ejecución)

| # | Componente | Qué hace | Dependencias externas | Coste estimado |
|---|------------|----------|------------------------|----------------|
| 1 | **Holdings base** | BrokerAccount, Transaction (last_sync), get_delisted_asset_ids, PortfolioHolding | DB | Bajo (0.1–0.3 s) |
| 2 | **Loop holdings** | convert_to_eur por cada holding, total_value, total_cost, P&L, distribuciones (país, sector, broker…) | ECB (cache 24 h) | Bajo |
| 3 | **metrics** | MetricsCacheService.get → si miss: BasicMetrics.get_all_metrics + StocksEtfMetrics | DB, FIFO sobre todas las TX | **Alto si cache miss** (1–3 s) |
| 4 | **yearly_returns** | ModifiedDietzCalculator.get_yearly_returns | PortfolioValuation (FIFO) × 2 por año | **Medio-alto** (0.5–2 s) |
| 5 | **DividendMetrics** | 3 llamadas: monthly, annualized, yearly | DB (Transaction DIVIDEND) | Medio (0.2–0.5 s) |
| 6 | **benchmark_annualized** | BenchmarkComparisonService.get_annualized_returns_summary | **4× Yahoo Finance API** + Modified Dietz | **Muy alto** (2–10 s) |

---

## 2. Componentes más lentos (prioridad)

### 1) `benchmark_annualized` — más crítico

- **Problema**: Llama a `get_annualized_returns_summary()` en cada carga, que hace **4 peticiones HTTP a Yahoo Finance** (S&P 500, NASDAQ 100, MSCI World, EuroStoxx 50).
- **Observación**: Existe `PortfolioBenchmarksCacheService` y `get_annualized_summary()` que devuelven exactamente lo que necesita el dashboard, pero el portfolio **no lo usa**; llama directamente a `BenchmarkComparisonService`.
- **Acción propuesta**: Usar `PortfolioBenchmarksCacheService.get_annualized_summary(user_id)` en lugar de `benchmark_comparison.get_annualized_returns_summary()`. Reutiliza el cache HIST+NOW ya existente para index-comparison.
- **Viabilidad HIST+NOW**: Ya está implementado. Solo falta cambiar la llamada en el dashboard.

### 2) `metrics` (BasicMetrics + StocksEtfMetrics) — ya con cache, pero sin invalidación fina

- **Problema**: MetricsCacheService hace cache “todo o nada” (TTL ~24 h). Si expira o se invalida, el recálculo es pesado (FIFO, P&L realizado, deposits, withdrawals, dividendos, fees).
- **Observación**: No distingue “cambio hoy” vs “cambio en el pasado”. Siempre invalida por completo.
- **Viabilidad HIST+NOW**: Media. Habría que separar:
  - **HIST**: Métricas que dependen de transacciones históricas (P&L realizado, dividendos históricos, etc.).
  - **NOW**: Métricas que dependen de precios actuales y transacciones de hoy (valor actual, P&L no realizado, apalancamiento).
- **Complejidad**: Alta (refactor de BasicMetrics y StocksEtfMetrics).

### 3) `yearly_returns` — Modified Dietz año a año

- **Problema**: Por cada año llama a `PortfolioValuation.get_value_at_date()` 2 veces (inicio y fin de año), más queries de cash flows. Cada `get_value_at_date` recorre todas las transacciones con FIFO.
- **Observación**: Histórico por años. Solo el último año (YTD) cambia con “hoy”.
- **Viabilidad HIST+NOW**: Alta. Patrón similar a evolution: cache con serie histórica (años completos) y recálculo solo del último año (YTD).
- **Complejidad**: Media (nuevo servicio de cache).

### 4) `DividendMetrics` (3 llamadas)

- **Problema**: Tres queries sobre Transaction (DIVIDEND) con distintos rangos.
- **Observación**: Coste moderado, sobre todo si hay muchos dividendos.
- **Viabilidad HIST+NOW**: Media. Los dividendos históricos no cambian; solo los de “hoy” o YTD podrían actualizarse.
- **Prioridad**: Menor que benchmark, metrics y yearly_returns.

### 5) Holdings + distribuciones

- **Problema**: Loop sobre holdings y `convert_to_eur`. Currency service usa cache de 24 h.
- **Observación**: Rápido con pocos holdings; puede subir con muchos.
- **Viabilidad HIST+NOW**: Baja prioridad; el coste actual suele ser aceptable.

---

## 3. Resumen de oportunidades

| Componente | Impacto | Esfuerzo | Recomendación |
|------------|---------|----------|---------------|
| **benchmark_annualized** | Muy alto (2–10 s) | Bajo | Usar `PortfolioBenchmarksCacheService.get_annualized_summary` en el dashboard. Cambio puntual en `dashboard.py`. |
| **yearly_returns** | Medio-alto (0.5–2 s) | Medio | Nuevo cache HIST+NOW: histórico de años completos + recálculo solo YTD. |
| **metrics** | Alto (1–3 s si miss) | Alto | Ampliar cache con invalidación fina (HIST vs NOW). Refactor significativo. |
| **DividendMetrics** | Medio | Medio | Cache con lógica HIST/NOW; prioridad secundaria. |
| **Holdings** | Bajo | Bajo | Mantener como está de momento. |

---

## 4. Implementación recomendada por fases

### Fase 1 — Rápida (1 cambio de llamada)

- En `app/routes/portfolio/dashboard.py`, sustituir:
  ```python
  benchmark_comparison = BenchmarkComparisonService(current_user.id)
  benchmark_annualized = benchmark_comparison.get_annualized_returns_summary()
  ```
  por:
  ```python
  from app.services.portfolio_benchmarks_cache import PortfolioBenchmarksCacheService
  benchmark_annualized = PortfolioBenchmarksCacheService.get_annualized_summary(current_user.id)
  ```
- El dashboard usará el mismo cache que Index Comparison. Si el usuario ha visitado Index Comparison o Performance, el cache ya estará caliente.
- Reducción estimada: 2–10 s en la primera carga; cargas siguientes casi instantáneas hasta que el cache expire o se invalide.

### Fase 2 — Medio plazo

- Cache HIST+NOW para `yearly_returns`.
- Nuevo modelo/servicio similar a `portfolio_evolution_cache` para “rentabilidades anuales”.

### Fase 3 — Largo plazo

- Invalidación fina en MetricsCacheService (HIST vs NOW).
- Cache opcional para DividendMetrics.

---

## 5. Archivos relevantes

- `app/routes/portfolio/dashboard.py` — Llamada actual a `benchmark_annualized`
- `app/services/portfolio_benchmarks_cache.py` — `get_annualized_summary` (ya implementado)
- `app/services/metrics/benchmark_comparison.py` — `get_annualized_returns_summary` (llamadas directas a Yahoo)
- `app/services/metrics/cache.py` — MetricsCacheService (cache actual de métricas)
- `app/services/metrics/modified_dietz.py` — `get_yearly_returns`
- `app/services/metrics/dividend_metrics.py` — 3 funciones de dividendos
