# Motor de estrategia global (Global Strategy Engine) — especificación v1

Documento de referencia para implementación. Alcance inicial: **cuenta bróker (acciones/ETF/ADR en el módulo de bolsa)**, indicadores macro vía **Yahoo Finance** en el flujo de precios por minuto; Asia por defecto **precio vs MA200** sobre **3188.HK**. **Sin notificaciones email/push**: solo entradas en la lista de recomendaciones del dashboard (`RecommendationService`).

---

## 1. Objetivos

1. **Score global continuo** \(SG \in [0, 3]\): suma de tres contribuciones \(s_{US}, s_{EU}, s_{AS} \in [0,1]\).
2. **Ratio objetivo** \(RO(SG)\) por interpolación lineal entre nodos fijos.
3. **Umbral objetivo de mercado** \(UOM = CO \times RO(SG)\) usando **Capital operativo (CO)** del bróker.
4. **Inversión real (IR)** como exposición bruta a mercado (valor mercado posiciones).
5. **Recomendaciones** condicionadas a márgenes 50% / 30% y a tendencia del score (riesgo).
6. **Visualización** (fases posteriores): cuenta‑kilómetros \(SG\) 0.0–3.0; gráficos de umbrales con paleta monocromática por bloque filtrado.

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

### 3.1 Bloque USA — curva de tipos (spread 10Y − 2Y)

Tickers Yahoo sugeridos: **^TNX** (10Y), **^IRX** (13 week como proxy 2Y corto; si se prefiere otro 2Y explícito, documentar el par elegido en código).

Sea \(x\) el spread en **puntos porcentuales** (ej. \(x = 0.35\) significa +0,35 %).

\[
s_{US} = \begin{cases}
1.0 & x \ge 0.5 \\
0.0 & x \le -0.5 \\
(x + 0.5) / 1.0 & \text{en otro caso (lineal entre } -0.5 \text{ y } 0.5\text{)}
\end{cases}
\]

Comprobar en implementación que \(x\) y los umbrales `0.5` estén en las **mismas unidades** (todos en % o todos en fracción).

### 3.2 Bloque Europa — volatilidad (VSTOXX)

Ticker Yahoo: **^V2TX**. Sea \(v\) el valor actual y \(v_{ma}\) la media móvil de **200** sesiones sobre cierres diarios cacheados.

\[
s_{EU} = \begin{cases}
1.0 & v \le 0.8\,v_{ma} \\
0.0 & v \ge 1.5\,v_{ma} \\
\text{lineal entre } (0.8\,v_{ma},\,1.0) \text{ y } (1.5\,v_{ma},\,0.0) & \text{en otro caso}
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

**Punto de integración:** `app/services/recommendation_service.py` → `build_for_dashboard`, inyectando entradas con `source` p. ej. `global_strategy` para poder filtrar o ponderar.

---

## 6. Datos, caché y actualización

### 6.1 Yahoo (USA, Europa, Asia por defecto)

Tickers: **^TNX**, **^IRX**, **^V2TX**, **3188.HK**.

- Integración: **mismo flujo** que la actualización periódica de precios de activos (lista de símbolos a refrescar; en el minuto que corresponda se actualiza el último precio/cierre según el diseño actual de `PriceUpdater` / colas en `app/__init__.py` y servicios relacionados).
- Para **MA200** y spreads: persistir **cierres diarios** (o serie diaria derivada) en caché/BD para no recalcular MA contra APIs en cada request.

### 6.2 FRED / modo Asia alternativo

- **v1:** solo **Asia = precio vs MA200 vía Yahoo** (`3188.HK`).
- Modo **Credit Impulse vía FRED** queda como **opción futura** conmutada por configuración; **no** combinar CI FRED y precio Yahoo simultáneamente para el mismo bloque Asia.

### 6.3 Historial de \(SG\) para “score bajando”

Persistir serie temporal de \(SG\) (p. ej. un valor al cierre o tras cada job de macro) con al menos **5** puntos recientes para calcular media móvil simple de 5 y la diferencia \(SG_{\text{actual}} - \text{media}_5\).

---

## 7. Visualización (fase UI; depende de widget en dashboard)

- **Cuenta‑kilómetros:** muestra \(SG\) con decimales (ej. 2.74) en \([0, 3]\).
- **Gráfico de umbrales:** bandas o líneas de referencia en tonalidades del **mismo matiz** que el bloque seleccionado (USA / Europa / Asia) en el filtro activo.
- **Widgets:** reutilizar el sistema de tarjetas/widgets del dashboard existente (`UserDashboardConfig`, layout en `dashboard.html`); no introducir un diseño de tarjeta nuevo salvo extensión mínima.

---

## 8. Checklist de implementación (orden sugerido)

1. Servicio puro de scores \(s_{US}, s_{EU}, s_{AS}\) y \(SG\) + tests unitarios con entradas mockeadas.
2. Función \(RO(SG)\) por tramos + tests de nodos y bordes.
3. Lectura de CO/IR desde la capa bróker ya alineada con §2.2.
4. Persistencia de series diarias de indicadores y de \(SG\).
5. Integración de tickers en el job de precios Yahoo existente.
6. Reglas 5.1–5.3 en `RecommendationService` (y, si aplica, payload en `dashboard_summary_cache` para el widget de dial cuando exista).

---

## 9. Revisiones posteriores

- Ampliar **IR** a más clases de activos si el producto lo exige.
- Sustituir **^IRX** por un 2Y explícito si se acuerda otro ticker.
- Modo Asia **FRED CI** con cron diario y flag exclusivo frente a Yahoo.
- Tabla de **liquidez ideal** en % (fase anterior del diseño) si se reintroduce como objetivo explícito además de \(RO(SG)\).

---

*Versión definitiva acordada para cierre de especificación antes de codificación. Commit de referencia en repo: etiqueta `snapshot/dashboard-pre-change-2026-05-14` (o el HEAD vigente al iniciar desarrollo).*
