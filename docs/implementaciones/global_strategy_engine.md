# Motor de estrategia global (Global Strategy Engine) — especificación v1

Documento de referencia para implementación. Alcance inicial: **cuenta bróker (acciones/ETF/ADR en el módulo de bolsa)**, indicadores macro vía **Yahoo Finance**. Los **cierres diarios** y la MA200 para los índices macro se persisten con el job **`global-strategy-macro-daily-once`** (cron diario tras cierre US; ver §6.1), independiente del polling intradía de precios de cartera. **Jerarquía de tickers v1:** USA **^VIX** (volatilidad vs MA200) *o* **SPY** (precio vs MA200), Europa **FEZ** (precio vs MA200), Asia **3188.HK** (precio vs MA200). **Sin notificaciones email/push**: solo entradas en la lista de recomendaciones del dashboard (`RecommendationService`).

---

## 1. Objetivos

1. **Score global continuo** \(SG \in [0, 3]\): suma de tres contribuciones \(s_{US}, s_{EU}, s_{AS} \in [0,1]\).
2. **Ratio objetivo** \(RO(SG)\) por interpolación lineal entre nodos fijos.
3. **Umbral objetivo de mercado** \(UOM = CO \times RO(SG)\) usando **Capital operativo (CO)** del bróker.
4. **Inversión real (IR)** como exposición bruta a mercado (valor mercado posiciones).
5. **Recomendaciones** condicionadas a márgenes 50% / 30% y a tendencia del score (riesgo).
6. **Visualización (v1 en dashboard):** cuenta‑kilómetros \(SG\) en \([0,3]\) (gauge en canvas), gráfico de cierre vs **MA200** y líneas **95% / 105%** de la MA con pestañas **USA / Europa / Asia** (`dashboard.html` + payload `global_strategy_snapshot.regions` desde `dashboard_snapshot.py`).

---

## 2. Capital operativo (CO) e inversión real (IR)

### 2.1 Definiciones (producto)

| Símbolo | Definición |
|--------|------------|
| **CO** | Capital propio real **dentro del bróker**: efectivo de cuenta + valor de mercado de las posiciones abiertas − deuda/margen usado (préstamo del bróker). |
| **IR** | Exposición total al mercado: \(\displaystyle IR = \sum_i (P_i \times Q_i)\) sobre posiciones abiertas (precio actual × cantidad). |

### 2.2 Adaptación a FollowUp (origen de datos)

En el código actual, el valor agregado del bróker se obtiene con **`_get_broker_value_at_date(user_id, now, use_current_prices=True)`** en `app/services/net_worth_service.py`, que devuelve al menos:

- `holdings_value` — suma en EUR del valor de mercado de posiciones **Stock / ETF / ADR** según el universo que recorre esa función.
- `cash_balance` — efectivo neto de la cuenta de bolsa tras el recorrido de transacciones (puede ser **negativo** si hay apalancamiento/margen).
- `total_value` — `cash_balance + holdings_value`; en el desglose de patrimonio se documenta como *dinero real del usuario en el bróker*.

**Implementación v1 recomendada**

- **IR:** usar **`holdings_value`** del mismo cálculo que el dashboard usa para “portfolio” bróker a fecha actual, **o** la suma de `total_value` por posición en el snapshot de `compute_stocks_metrics` / `create_portfolio_snapshot`, **siempre el mismo universo** que para IR en todo el motor (evitar mezclar crypto/metales salvo que se amplíe el spec).
- **CO:** en la práctica del modelo FIFO + cash del bróker, **`total_value`** de esa misma ruta coincide con *efectivo + valor mercado − margen implícito* cuando el margen se refleja en `cash_balance` negativo. **Regla de implementación:**  
  `CO = broker_data["total_value"]`  
  Si más adelante se expone un campo explícito “margen/deuda”, sustituir solo la parte correspondiente manteniendo la definición de producto.

**Fuera de alcance v1 (salvo que se amplíe el spec):** patrimonio total fuera del bróker (bancos, crypto, inmuebles) **no** entra en CO/IR de este motor.

---

## 3. Score por bloque (0.0 – 1.0 cada uno)

### 3.1 Bloque USA — **^VIX** (volatilidad) *o* **SPY** (precio vs MA200)

**Elección de producto (una sola ruta activa para \(s_{US}\)):**

| Modo | Ticker Yahoo | Cálculo |
|------|----------------|---------|
| **VIX** | **^VIX** | VIX **bajo** respecto a su MA200 → entorno más calmado → \(s_{US}\) alto; VIX **alto** → miedo → \(s_{US}\) bajo. Misma banda relativa que el precio (95%–105% de \(MA_{200}\)) pero **invertida**: \(s_{US} = 1 - s_{\text{band}}(\text{VIX}, MA_{200})\) acotada a \([0,1]\), donde \(s_{\text{band}}\) es la misma función lineal a tramos que en §3.3 con \(P = \text{VIX}\). Implementación: `score_usa_vix_vs_ma200`. |
| **SPY** | **SPY** | Igual que §3.3 con \(P\) = cierre SPY y \(MA_{200}\) sobre SPY. Implementación: `score_usa_spy_vs_ma200` / `score_price_vs_ma200`. |

**Alternativa legacy (curva de tipos):** spread **10Y − 2Y** con **^TNX** y **^IRX** (u otro par documentado); función `score_usa_yield_curve_spread_pct` en código. No mezclar con el modo VIX/SPY en el mismo \(s_{US}\) sin flag explícito.

Comprobar cotización + histórico diario (MA200) con `scripts/verify_yahoo_global_strategy_tickers.py` antes de integrar en jobs.

### 3.2 Bloque Europa — **FEZ** (precio vs MA200)

Ticker Yahoo: **FEZ** (SPDR Euro Stoxx 50 ETF, NYSE). Misma lógica que Asia (§3.3): por **encima** de la banda alta vs \(MA_{200}\) → Europa en “verde”; por **debajo** de la banda baja → cautela. Implementación: `score_eu_price_vs_ma200` (alias de `score_price_vs_ma200`).

**Nota:** VSTOXX (**^V2TX** / **V2TX.DE**) se **descarta** para MA200 vía Chart v8 en las pruebas previas; **FEZ** cierra el bloque europeo con datos estables y la **misma** rutina numérica que Asia.

Sea \(P\) el último cierre de FEZ y \(MA_{200}\) la media móvil de 200 cierres.

\[
s_{EU} = \begin{cases}
1.0 & P \ge 1.05\,MA_{200} \\
0.0 & P \le 0.95\,MA_{200} \\
\text{lineal entre } (0.95\,MA_{200},\,0.0) \text{ y } (1.05\,MA_{200},\,1.0) & \text{en otro caso}
\end{cases}
\]

### 3.3 Bloque Asia — modo por defecto (precio vs MA200)

Ticker Yahoo: **3188.HK**. Modo por defecto: **precio vs MA200** (alternativa CI vía FRED queda desactivada en v1 salvo flag explícito).

Sea \(P\) el último cierre y \(MA_{200}\) la media móvil de 200 cierres.

\[
s_{AS} = \begin{cases}
1.0 & P \ge 1.05\,MA_{200} \\
0.0 & P \le 0.95\,MA_{200} \\
\text{lineal entre } (0.95\,MA_{200},\,0.0) \text{ y } (1.05\,MA_{200},\,1.0) & \text{en otro caso}
\end{cases}
\]

**Score global:** \(SG = s_{US} + s_{EU} + s_{AS}\) (acotado a \([0,3]\) por construcción si cada sumando está en \([0,1]\)).

---

## 4. Ratio objetivo \(RO(SG)\) y umbral \(UOM\)

### 4.1 Nodos (interpolación lineal a tramos)

| Nodo | SG | RO | Exposición objetivo (interpretación) |
|------|-----|-----|--------------------------------------|
| A | 0.0 | 0.0 | 0 % |
| B | 0.5 | 0.6 | 60 % |
| C | 1.0 | 0.8 | 80 % |
| D | 2.0 | 1.3 | 130 % |
| E | 3.0 | 2.0 | 200 % |

Entre nodos consecutivos en el eje SG, **RO** es la recta que une los dos puntos. Tramos: \([0, 0.5]\), \([0.5, 1]\), \([1, 2]\), \([2, 3]\). Fuera de \([0,3]\) se satura: \(SG < 0 \Rightarrow RO(0)\), \(SG > 3 \Rightarrow RO(3)\).

### 4.2 Umbral objetivo de mercado

\[
UOM = CO \times RO(SG)
\]

con **CO** según §2.2. **Moneda:** EUR (mismo criterio que el resto del dashboard tras conversiones del bróker).

### 4.3 Métrica opcional de desviación

\[
\text{desviación\_relativa} = \frac{IR - UOM}{UOM} \quad (\text{si } UOM > 0\text{; si } UOM = 0\text{, tratar aparte para evitar división por cero})
\]

---

## 5. Lógica de recomendaciones (solo lista; sin email/push)

Condiciones evaluadas **después** de calcular \(SG\), \(RO\), \(UOM\), \(IR\) y disponer de **histórico reciente de SG** (al menos 5 valores diarios o la misma granularidad que se persista; ver §6).

### 5.1 A — Alerta de oportunidad (apalancamiento / subir exposición)

- **Trigger:** \(SG > 2.0\) **y** \(IR < 0.5 \times UOM\).
- **Mensaje (plantilla):**  
  *"[Fuerte viento a favor]. Tu exposición está un 50% por debajo del umbral recomendado. Puedes aumentar tu posición en (UOM - IR) € adicionales para optimizar tu ratio según el Capital Operativo actual."*  
  Sustituir `(UOM - IR)` por el valor numérico redondeado coherente con el resto de la app.

### 5.2 B — Alerta de riesgo (desapalancamiento)

- **Score bajando:** la caída de \(SG\) respecto a la **media de los últimos 5 valores** almacenados de \(SG\) es **> 0.3** (en unidades de score, no en %).
- **Trigger:** (score bajando) **y** \(IR > 1.30 \times UOM\).
- **Mensaje (plantilla):**  
  *"[Alerta de deterioro macro]. Tu nivel de apalancamiento supera el límite de seguridad (margen del 30% sobre el objetivo). Debes reducir posiciones por valor de (IR - (UOM × 1.1)) € para proteger tu Capital Operativo."*  
  Ajustar el texto si el resultado es negativo o nulo (no mostrar recomendación absurda).

### 5.3 C — Confirmación

- **Trigger:** no se cumple A ni B **y** el usuario está “entre márgenes” respecto a los umbrales anteriores (es decir, no está en zona de oportunidad ni en zona de riesgo según 5.1 y 5.2).

- **Mensaje (plantilla):**  
  *"[Situación actual del mercado]. Tus ratios de inversión y liquidez actuales con respecto a tu Capital Operativo son adecuados."*

**Prioridad sugerida en `RecommendationService`:** riesgo > oportunidad > confirmación (o solo riesgo/oportunidad si se quiere evitar ruido de confirmación diaria; configurable).

**Punto de integración:** `app/services/recommendation_service.py` → `build_for_dashboard`, inyectando entradas con `source` **`global_strategy`** (`app/services/global_strategy/global_recommendations.py`; prioridad riesgo > oportunidad > confirmación).

---

## 6. Datos, caché y actualización

### 6.1 Yahoo (USA, Europa, Asia — tickers v1)

Tickers del gate por defecto en `scripts/verify_yahoo_global_strategy_tickers.py`: **^VIX**, **SPY**, **FEZ**, **3188.HK** (cotización ligera + ≥200 cierres diarios con `range=2y`, `interval=1d`). Flag **`--include-us-yields`** añade **^TNX** y **^IRX** si se mantiene el modo legacy de curva de tipos.

- **v1 (implementado):** persistencia **diaria** de cierres en **`global_strategy_macro_daily`** mediante el comando **`global-strategy-macro-daily-once`** (no depende del ciclo intraminuto de `PriceUpdater`). Opcional futuro: acoplar refresco intradía de cotizaciones de índices al mismo pipeline que los activos de cartera si el producto lo exige.
- Para **MA200**: los cierres diarios en BD cubren **SPY**, **FEZ**, **3188.HK** y **^VIX** según el modo USA elegido (`GLOBAL_STRATEGY_USA_SCORE_MODE` / `GlobalStrategyMacroState.usa_score_mode`).

**Job de persistencia (implementado):** comando Flask **`global-strategy-macro-daily-once`** (`GlobalStrategyMacroService` en `app/services/global_strategy/macro_daily_service.py`). Tablas **`global_strategy_macro_daily`** (una fila por serie: `vix`, `spy`, `fez`, `asia_hk`, JSON `data_points` con `{date, price}`) y **`global_strategy_macro_state`** (singleton `data_version`, **`usa_score_mode`** por defecto **`vix`** alineado con `GLOBAL_STRATEGY_USA_SCORE_MODE` en `config.py`). Cron: **`scripts/install_global_strategy_macro_cron.sh`** — **22:35** hora **Europe/Madrid** (tras cierre habitual US); log `logs/global_strategy_macro_daily_cron.log`. Primer arranque: backfill de **`GLOBAL_STRATEGY_MACRO_BACKFILL_CALENDAR_DAYS`** (defecto **450**) días de calendario hacia atrás para asegurar **≥ ~250** sesiones; el CLI imprime **WARN** si `n_closes` cae por debajo de **`GLOBAL_STRATEGY_MACRO_MIN_CLOSES`** (250). Lectura agregada: `GlobalStrategyMacroService.snapshot_for_scores()` (close, MA200, `as_of_date` por serie). **SG diario:** en la misma ejecución, `upsert_sg_daily_for_all_stock_users` (`sg_from_macro.py`) calcula \(s_{US}, s_{EU}, s_{AS}\) y \(SG\) con `score_math` y hace `upsert_sg_daily_atomic` para cada usuario activo con módulo **`stock`**; `indicator_as_of` = mínimo de las fechas de cierre de las series usadas (`indicator_as_of_minimum`); `snapshot_date` = día **UTC** actual.

### 6.2 FRED / modo Asia alternativo

- **v1:** **Asia = precio vs MA200** (`3188.HK`); **Europa = precio vs MA200** (`FEZ`); **USA = ^VIX o SPY** según §3.1.
- Modo **Credit Impulse vía FRED** queda como **opción futura** conmutada por configuración; **no** combinar CI FRED y precio Yahoo simultáneamente para el mismo bloque Asia.

### 6.3 Historial de \(SG\) para “score bajando”

Persistir serie temporal de \(SG\) (p. ej. un valor al cierre o tras cada job de macro) con al menos **5** puntos recientes para calcular media móvil simple de 5 y la diferencia \(SG_{\text{actual}} - \text{media}_5\).

#### 6.3.1 Persistencia atómica y fines de semana (obligatorio)

- **Transacción única:** cada escritura de la serie (fila diaria por usuario, o un lote de días si se rellena fin de semana) debe hacerse en **una sola transacción** (`commit` único tras fijar `sg`, componentes \(s_{US}, s_{EU}, s_{AS}\) y metadatos). Nunca dejar la fila a medias (p. ej. `sg` actualizado sin `indicator_as_of` o sin componentes si el job los calcula juntos).
- **Fecha de cierre de indicadores (`indicator_as_of`):** guardar explícitamente la **fecha de negocio / cierre** de los subyacentes usados (**^VIX** o **SPY**, **FEZ**, **3188.HK**, y si aplica **^TNX**/**^IRX** en modo legacy). En sábado y domingo los mercados cash suelen estar cerrados, pero **índices y ETFs** pueden seguir mostrando el **último cierre hábil**; sin esta columna parece un “hueco” o un salto artificial en la serie.
- **Sin huecos en la serie para la media de 5 días:** si la política del producto es **una fila por día natural (UTC)**, en fin de semana se puede **replicar el mismo \(SG\)** del viernes (mismo `indicator_as_of`) para sábado y domingo **en el mismo `commit`** que consolida el viernes, o bien calcular la media sobre los **últimos 5 registros no nulos** (sin exigir día calendario consecutivo). La implementación debe elegir una y documentarla; la referencia en código usa **forward-fill opcional** sábado/domingo en la misma transacción que el upsert del viernes cuando proceda (`upsert_sg_daily_atomic(..., fill_weekend_from_friday=True)` en `app/services/global_strategy/sg_history.py`).

---

## 7. Visualización (dashboard)

- **Cuenta‑kilómetros:** arco semicircular en **canvas** coloreado de rojo (0) a verde (3) con lectura numérica de \(SG\) en \([0,3]\).
- **Gráfico de umbrales:** pestañas **USA / Europa / Asia**; en cada una, línea de **cierre** (últimos ~100 puntos de la serie persistida), **MA200** horizontal a fecha actual y trazas **95% / 105%** de esa MA como referencia de banda. Paleta por bloque (índigo / ámbar / teal) coherente con el matiz del tab activo.
- **Barra de posición del cierre:** debajo del gráfico, marcador del último cierre sobre un eje que abarca banda y recientes cierres (leyenda con cierre, ticker y rango 95–105% MA200).
- **Layout:** tarjeta `data-card-id="global_strategy"` en `dashboard.html`, reordenable con el resto; **sin** panel de “configurar indicadores” en el producto actual: la tarjeta **solo** se muestra con módulo **`stock`** y payload `global_strategy_snapshot` válido (véase §7.1).

### 7.1 Visibilidad: módulo acciones y datos obligatorios

Estas tarjetas (cuenta‑kilómetros, indicadores macro, filtros por bloque) **solo aplican al módulo de acciones / bolsa** (`stock` en `User.enabled_modules`, misma convención que `MODULES` en `app/models/user.py`).

Reglas de producto (obligatorias en implementación):

1. **Módulo activo:** si el usuario **no** tiene el módulo **`stock`** habilitado, **no** se muestran las tarjetas ni entran en el layout (no ocupar hueco; no depender solo del toggle de widget si el módulo está apagado).
2. **Datos disponibles:** si no hay datos suficientes para pintar el widget (p. ej. sin cierres de indicadores, sin \(SG\) calculable, sin CO/IR del bróker cuando hagan falta), **no** se renderiza la tarjeta (evitar cajas vacías o placeholders permanentes). Opcional: mostrar un estado “sin datos” **solo** si el producto lo pide; por defecto: **ocultar**.
3. **Usuarios nuevos / futuros:** la tarjeta sigue las mismas reglas (1) y (2). No hay en la UI actual un panel de toggles por widget; si en el futuro se reintroduce configuración granular, debe respetar (1)–(2) y no mostrar bloques vacíos.

La lógica de recomendaciones macro (§5) puede seguir otras reglas de disparo, pero **las tarjetas visuales** quedan acotadas a **módulo `stock` + datos**.

---

## 8. Checklist de implementación (orden sugerido)

**Jerarquía Yahoo v1 (recordatorio):** USA = **^VIX** *o* **SPY** (exclusivo por configuración); Europa = **FEZ**; Asia = **3188.HK**. Verificar Chart v8 con `scripts/verify_yahoo_global_strategy_tickers.py` (exit 0) antes del job de precios / caché diaria.

1. ~~Servicio puro de scores \(s_{US}, s_{EU}, s_{AS}\) y \(SG\) + tests unitarios con entradas mockeadas.~~ **Hecho** (`score_price_vs_ma200` + aliases USA/EU/Asia, `score_usa_vix_vs_ma200`, legacy `score_usa_yield_curve_spread_pct`; tests en `tests/global_strategy_score_math_test.py`).
2. ~~Función \(RO(SG)\) por tramos + tests de nodos y bordes.~~ **Incluido** en el mismo módulo (`ratio_objetivo`, `umbral_objetivo_mercado`).
3. ~~Lectura de CO/IR desde la capa bróker ya alineada con §2.2.~~ **Hecho** (`_get_broker_value_at_date` en `global_recommendations.py`).
4. ~~Persistencia macro Yahoo + serie diaria \(SG\) por usuario.~~ **Hecho** (job `global-strategy-macro-daily-once`, tablas macro, `sg_from_macro.py` → `upsert_sg_daily_atomic` para usuarios activos con módulo `stock`). Pendiente opcional: spot intradía en job de precios.
5. ~~Reglas 5.1–5.3 en `RecommendationService`.~~ **Hecho** (`global_recommendations.py`, `source=global_strategy`, prioridad B>A>C; confirmación con `GLOBAL_STRATEGY_INCLUDE_CONFIRMATION_RECOMMENDATION`).
6. ~~UI: tarjeta de estrategia global según **§7.1** (módulo `stock` + datos; gauge, pestañas macro, gráfico Chart.js; payload `global_strategy_snapshot` en `get_dashboard_summary` / caché del dashboard).~~ **Hecho** (`dashboard.html`, `app/services/global_strategy/dashboard_snapshot.py`).

---

## 9. Revisiones posteriores

- Ampliar **IR** a más clases de activos si el producto lo exige.
- Sustituir **^IRX** por un 2Y explícito si se acuerda otro ticker.
- Modo Asia **FRED CI** con cron diario y flag exclusivo frente a Yahoo.
- Tabla de **liquidez ideal** en % (fase anterior del diseño) si se reintroduce como objetivo explícito además de \(RO(SG)\).

---

*Versión definitiva acordada para cierre de especificación antes de codificación. Commit de referencia en repo: etiqueta `snapshot/dashboard-pre-change-2026-05-14` (o el HEAD vigente al iniciar desarrollo).*
