# Baseline de métricas: Comparación pre/post refactor

**Propósito:** Registrar la estructura y valores actuales de las métricas antes del refactor, para comparar con los resultados posteriores y detectar diferencias (y su causa).

---

## Cómo usar este documento

1. **Antes del refactor:** Ejecutar los servicios con datos reales (o de prueba) y anotar aquí estructura y valores representativos.
2. **Después de cada fase:** Repetir las mismas consultas y comparar.
3. **Si hay diferencias:** Documentar la causa (cambio de fórmula, redondeo, convención de nombre, etc.).

---

## Servicios y funciones a capturar

| # | Servicio / Función | Ubicación | Descripción |
|---|-------------------|-----------|-------------|
| 1 | `compute_crypto_metrics(user_id)` | `crypto_metrics.py` | Métricas crypto |
| 2 | `compute_metales_metrics(user_id)` | `metales_metrics.py` | Métricas metales |
| 3 | `get_portfolio_details(user_id)` | `net_worth_service.py` | Detalles portfolio/acciones |
| 4 | `get_crypto_details(user_id)` | `net_worth_service.py` | Detalles crypto (usa 1) |
| 5 | `get_metales_details(user_id)` | `net_worth_service.py` | Detalles metales (usa 2) |
| 6 | `get_investments_summary(user_id)` | `net_worth_service.py` | Resumen inversiones agregado |
| 7 | `get_net_worth_breakdown(user_id)` | `net_worth_service.py` | Desglose patrimonio |
| 8 | `get_dashboard_summary(user_id)` | `net_worth_service.py` | Resumen completo dashboard |

---

## Estructura de salida actual (baseline)

### 1. `compute_crypto_metrics` / `get_crypto_details`

```
Claves: capital_invertido, cuasi_fiat, fiat_total, valor_total, total_cost,
        pl_total, pl_pct_total, rewards_total, posiciones
Posiciones[].keys: symbol, name, quantity, average_buy_price, cost, value,
                   price, pl, pl_pct, reward_quantity, reward_value
```

**Valores de ejemplo (user_id=___):**

```
capital_invertido: ___
valor_total: ___
pl_total: ___
pl_pct_total: ___
(completar al capturar)
```

---

### 2. `compute_metales_metrics` / `get_metales_details`

```
Claves: capital_invertido, valor_total, pl_total, pl_pct_total, posiciones
Posiciones[].keys: symbol, name, quantity, average_buy_price, cost, value,
                   price, pl, pl_pct
```

**Valores de ejemplo (user_id=___):**

```
capital_invertido: ___
valor_total: ___
pl_total: ___
pl_pct_total: ___
(completar al capturar)
```

---

### 3. `get_portfolio_details`

```
Claves: total_value, total_cost, total_pnl, total_pnl_pct, ...
```

**Valores de ejemplo (user_id=___):**

```
total_value: ___
total_cost: ___
total_pnl: ___
total_pnl_pct: ___
(completar al capturar)
```

---

### 4. `get_investments_summary`

```
Claves: total_value, total_cost, total_pnl, total_pnl_pct,
        by_type: [{name, value, pnl, pnl_pct}, ...]
```

**Fórmula actual:** `total_value = portfolio.total_value + crypto.valor_total + metales.valor_total`  
**Fórmula actual:** `total_cost = portfolio.total_cost + crypto.capital_invertido + metales.capital_invertido`

**Valores de ejemplo (user_id=___):**

```
total_value: ___
total_cost: ___
total_pnl: ___
total_pnl_pct: ___
(completar al capturar)
```

---

### 5. `get_net_worth_breakdown`

```
Claves: cash, portfolio, crypto, metales, assets_total, debt, net_worth,
        breakdown_pct
```

**Valores de ejemplo (user_id=___):**

```
cash: ___
portfolio: ___
crypto: ___
metales: ___
assets_total: ___
net_worth: ___
(completar al capturar)
```

---

## Comparación post-refactor

| Función | ¿Coincide? | Notas / Causa de diferencia |
|---------|------------|-----------------------------|
| crypto_metrics | | |
| metales_metrics | | |
| portfolio_details | | |
| investments_summary | | |
| net_worth_breakdown | | |

---

## Script opcional para captura

Para automatizar la captura, se puede añadir un script:

```
scripts/capture_metrics_baseline.py
```

Que reciba `user_id` y escriba en un JSON la salida de las funciones anteriores. Así la comparación post-refactor puede hacerse por diff de archivos.

---

## Notas

- Los valores numéricos pueden diferir ligeramente por redondeo si se cambia el orden de operaciones; documentar si ocurre.
- Si cambia la estructura de claves (p. ej. `valor_total`→`total_value`), la comparación debe hacerse por equivalente conceptual, no por nombre de clave.
