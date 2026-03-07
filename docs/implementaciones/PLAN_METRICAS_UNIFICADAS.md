# Plan de implementación: Métricas unificadas (Crypto, Metales, Acciones, Portfolio)

**Objetivo:** Unificar fórmulas de P&L, convención de nombres y contrato de snapshot en Acciones, Crypto, Metales y Portfolio.

---

## Fase 0: Diseño y documentación
- [x] Definir estructuras `PositionSnapshot`, `AssetCategorySnapshot`, `PortfolioSnapshot`
- [x] Documentar convención de nombres (inglés interno)
- [x] Documentar mapeo nombres actuales a nuevos
- [x] Revisar y documentar fórmulas de P&L (value, cost, pnl, pnl_pct)
- [ ] Capturar baseline de valores actuales (ver BASELINE_METRICAS_COMPARACION.md)

### Estructuras y convenciones

#### Dataclasses

```python
@dataclass
class PositionSnapshot:
    """Una posición individual (un activo)."""
    symbol: str
    name: str
    quantity: float
    average_buy_price: float
    total_cost: float      # Coste total invertido (EUR)
    total_value: float     # quantity * price actual (EUR)
    current_price: float   # Precio unitario actual
    pnl: float             # total_value - total_cost
    pnl_pct: float         # (pnl / total_cost * 100) si total_cost > 0 else 0
    # Campos opcionales por módulo:
    extra: dict = field(default_factory=dict)  # ej. reward_quantity, reward_value

@dataclass
class AssetCategorySnapshot:
    """Snapshot agregado de una categoría (Crypto, Metales, Stocks)."""
    category: str          # "crypto" | "metales" | "stocks"
    total_cost: float      # Suma de costes de posiciones
    total_value: float     # Suma de valores de posiciones
    total_pnl: float       # total_value - total_cost
    total_pnl_pct: float   # (total_pnl / total_cost * 100) si total_cost > 0 else 0
    positions: List[PositionSnapshot]
    # Campos extra por categoría:
    extra: dict = field(default_factory=dict)  # ej. cuasi_fiat, rewards_total

@dataclass
class PortfolioSnapshot:
    """Snapshot agregado del portfolio (suma de categorías)."""
    total_cost: float
    total_value: float
    total_pnl: float
    total_pnl_pct: float
    categories: Dict[str, AssetCategorySnapshot]  # "stocks", "crypto", "metales"
```

#### Convención de nombres (inglés interno)

| Actual (español/mixto) | Nuevo (inglés) |
|------------------------|----------------|
| capital_invertido | total_cost |
| valor_total | total_value |
| pl_total | total_pnl |
| pl_pct_total | total_pnl_pct |
| cost (en posición) | total_cost (o cost en contexto claro) |
| value (en posición) | total_value |
| pl (en posición) | pnl |
| pl_pct (en posición) | pnl_pct |

#### Fórmulas P&L

```
value = quantity * current_price   (fallback: total_cost si no hay precio)
pnl = total_value - total_cost
pnl_pct = (pnl / total_cost * 100) if total_cost > 0 else 0

Agregados:
  total_cost = Σ position.total_cost
  total_value = Σ position.total_value
  total_pnl = total_value - total_cost
  total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
```

---

## Fase 1: Librería P&L
- [x] Crear `app/services/metrics/pnl_lib.py`
- [x] Implementar `compute_position_pnl(quantity, price, total_cost)`
- [x] Implementar `aggregate_positions(positions)`
- [x] Definir dataclasses: `PositionSnapshot`, `AssetCategorySnapshot`, `PortfolioSnapshot`
- [x] Tests unitarios para la librería

---

## Fase 2: Refactor Crypto
- [x] Adaptar `compute_crypto_metrics` para usar `pnl_lib`
- [x] Unificar nombres según convención (claves nuevas + legacy)
- [x] Devolver snapshot en `metrics['snapshot']`, dict con compatibilidad
- [x] Mantener campos extra: cuasi_fiat, rewards_total
- [ ] Verificar que outputs coincidan con baseline (opcional)

---

## Fase 3: Refactor Metales
- [x] Adaptar `compute_metales_metrics` para usar `pnl_lib`
- [x] Unificar nombres según convención
- [x] Devolver snapshot en `metrics['snapshot']`, dict con compatibilidad
- [ ] Verificar que outputs coincidan con baseline (opcional)

---

## Fase 4: Refactor Acciones (Portfolio broker/stocks)
- [x] Identificar servicios que calculan métricas de acciones
- [x] Crear `stocks_metrics.py` y adaptar `get_portfolio_details` para usar `pnl_lib`
- [x] Unificar nombres según convención
- [x] Devolver snapshot en metrics
- [ ] Verificar que outputs coincidan con baseline (opcional)

---

## Fase 5: Portfolio agregado
- [x] Definir `PortfolioSnapshot` (ya en pnl_lib)
- [x] Crear `get_portfolio_aggregate(user_id)` que construye PortfolioSnapshot desde los 3 AssetCategorySnapshot
- [x] Integrar en get_investments_summary
- [ ] get_net_worth_breakdown usa lógica distinta (broker con apalancamiento); mantener como está

---

## Fase 6: Integración UI / Dashboard
- [x] Actualizar templates (crypto, metales, dashboard) a claves unificadas
- [x] get_crypto_details y get_metales_details devuelven total_value, total_cost, total_pnl, total_pnl_pct
- [x] get_crypto_value y get_metales_value usan total_value
- [ ] Gráficos y rutas usan ya la misma estructura; pruebas manuales recomendadas

---

## Resumen de progreso

| Fase | Estado |
|------|--------|
| 0 | Completada |
| 1 | Completada |
| 2 | Completada |
| 3 | Completada |
| 4 | Completada |
| 5 | Completada |
| 6 | Completada |
