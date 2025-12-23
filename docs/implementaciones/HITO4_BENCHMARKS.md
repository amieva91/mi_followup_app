# HITO 4 - Comparación con Índices de Referencia

## Descripción

Implementación de la funcionalidad para comparar el rendimiento del portfolio del usuario con índices de referencia: S&P 500, NASDAQ 100, MSCI World y EuroStoxx 50.

## Fecha de Implementación

23 de Diciembre de 2025

## Componentes Implementados

### 1. Servicio Backend: `BenchmarkComparisonService`

**Ubicación:** `app/services/metrics/benchmark_comparison.py`

**Responsabilidades:**
- Obtener datos históricos de los índices desde Yahoo Finance Chart API
- Calcular rentabilidades mensuales del portfolio usando Modified Dietz
- Normalizar todos los datos a una base de 100 desde el inicio
- Calcular rentabilidades anuales y totales
- Proporcionar datos para gráficos y tablas comparativas

**Índices Soportados:**
```python
BENCHMARKS = {
    'S&P 500': '^GSPC',
    'NASDAQ 100': '^NDX',
    'MSCI World': 'URTH',
    'EuroStoxx 50': '^STOXX50E'
}
```

### 2. API Endpoints

#### `/portfolio/api/benchmarks`
**Método:** GET  
**Autenticación:** Requerida (`@login_required`)  
**Respuesta:** JSON con datos para gráfico y tabla comparativa

**Estructura de respuesta:**
```json
{
  "labels": ["2018-01", "2018-02", ...],
  "datasets": {
    "portfolio": [100, 102.5, ...],
    "S&P 500": [100, 98.2, ...],
    "NASDAQ 100": [100, 99.1, ...],
    ...
  },
  "annual_returns": {
    "annual": [
      {
        "year": 2018,
        "portfolio": 7.41,
        "benchmarks": {
          "S&P 500": -11.22,
          "NASDAQ 100": -8.92,
          ...
        },
        "differences": {
          "S&P 500": 18.63,
          "NASDAQ 100": 16.33,
          ...
        }
      },
      ...
    ],
    "total": {
      "portfolio": 155.51,
      "benchmarks": {...},
      "differences": {...}
    }
  }
}
```

#### Dashboard: Integración en `dashboard()`
Se calculan las rentabilidades anualizadas usando `get_annualized_returns_summary()` y se muestran en la sección "🌍 Métricas Globales e Históricas".

### 3. Frontend

**Ubicación:** `app/static/js/charts.js`

**Funciones principales:**
- `loadBenchmarkData()`: Carga datos desde el API
- `createBenchmarkChart()`: Crea el gráfico comparativo usando Chart.js
- `renderBenchmarkTable()`: Renderiza la tabla comparativa anual

**Ubicación:** `app/templates/portfolio/performance.html`

Incluye:
- Gráfico comparativo (`<canvas id="benchmarkChart">`)
- Tabla comparativa anual (`<table id="benchmarkTable">`)

**Ubicación:** `app/templates/portfolio/dashboard.html`

Incluye:
- Tarjeta resumen con rentabilidades anualizadas en "🌍 Métricas Globales e Históricas"

## Funcionamiento: Obtención de Datos

### ⚠️ IMPORTANTE: Sin Caché - Llamadas en Tiempo Real

**El sistema NO implementa caché para los datos de benchmarks.** Cada vez que se carga la pestaña:

1. **Dashboard (`/portfolio`):**
   - Se llama a `BenchmarkComparisonService.get_annualized_returns_summary()`
   - Se realizan 4 llamadas HTTP a la API de Yahoo Finance (una por cada índice)
   - Se calculan las rentabilidades anualizadas en tiempo real

2. **Performance (`/portfolio/performance`):**
   - Se llama al endpoint `/portfolio/api/benchmarks`
   - Se realizan 4 llamadas HTTP a la API de Yahoo Finance (una por cada índice)
   - Se calculan todas las rentabilidades mensuales y anuales en tiempo real

### Flujo de Datos

```
Usuario abre página
    ↓
JavaScript: loadBenchmarkData()
    ↓
GET /portfolio/api/benchmarks
    ↓
BenchmarkComparisonService.get_comparison_data()
    ↓
Para cada benchmark (4 índices):
    ├─→ get_benchmark_historical_data()
    │   └─→ HTTP GET a Yahoo Finance Chart API
    │       URL: https://query1.finance.yahoo.com/v8/finance/chart/{TICKER}
    │       Params: period1, period2, interval=1d
    │
    ├─→ Procesar datos históricos
    ├─→ Agrupar por mes
    └─→ Calcular rentabilidades
    ↓
Calcular rentabilidades del portfolio (Modified Dietz mensual)
    ↓
Normalizar todos a base 100
    ↓
Calcular rentabilidades anuales
    ↓
Retornar JSON al frontend
    ↓
Renderizar gráfico y tabla
```

### Consideraciones de Rendimiento

1. **Tiempo de respuesta:**
   - Cada llamada a Yahoo Finance puede tardar 1-3 segundos
   - Con 4 índices, el tiempo total puede ser de 4-12 segundos
   - El cálculo del portfolio también puede tardar varios segundos dependiendo de la cantidad de transacciones

2. **Límites de la API de Yahoo Finance:**
   - No hay límites oficiales documentados
   - Se recomienda no hacer más de 2000 requests/hora por IP
   - El sistema actual hace ~4 requests por carga de página

3. **Recomendaciones futuras para optimización:**
   - Implementar caché de datos históricos de benchmarks (ej: Redis, base de datos)
   - Actualizar caché diariamente en lugar de en cada request
   - Cachear por 24 horas los datos históricos (que no cambian)
   - Mantener datos en tiempo real solo para el último día

## API de Yahoo Finance

### Endpoint Utilizado

```
GET https://query1.finance.yahoo.com/v8/finance/chart/{TICKER}
```

### Parámetros

- `period1`: Timestamp Unix de fecha inicio
- `period2`: Timestamp Unix de fecha fin
- `interval`: `1d` (diario)

### Headers

```python
CHART_API_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
```

### Respuesta

```json
{
  "chart": {
    "result": [{
      "timestamp": [1234567890, ...],
      "indicators": {
        "quote": [{
          "close": [100.5, 102.3, ...]
        }]
      }
    }]
  }
}
```

## Cálculo de Rentabilidades

### Portfolio (Modified Dietz)

Se calcula la rentabilidad mensual del portfolio usando el método Modified Dietz para cada mes, y luego se compone para obtener la rentabilidad anual y total.

### Benchmarks

Para cada benchmark:
1. Se obtienen precios diarios históricos desde la fecha de inicio del usuario
2. Se agrupan por mes (tomando el último precio de cada mes)
3. Se calcula rentabilidad mensual: `(Precio_final - Precio_inicial) / Precio_inicial`
4. Se compone para obtener rentabilidad anual y total

### Normalización a Base 100

Todos los datos (portfolio y benchmarks) se normalizan para empezar en 100 desde la fecha de inicio del usuario, permitiendo comparación visual directa en el gráfico.

## Archivos Modificados/Creados

### Nuevos Archivos
- `app/services/metrics/benchmark_comparison.py`

### Archivos Modificados
- `app/routes/portfolio.py`: Añadido endpoint `/api/benchmarks` e integración en dashboard
- `app/static/js/charts.js`: Funciones para gráfico y tabla de benchmarks
- `app/templates/portfolio/performance.html`: Sección de comparación con benchmarks
- `app/templates/portfolio/dashboard.html`: Tarjeta resumen de rentabilidades anualizadas

## Testing

### Validación de Datos

Se creó `test_benchmarks_validation.py` para validar que:
1. La API de Yahoo Finance responde correctamente
2. Se pueden obtener datos históricos para todos los índices
3. Los datos tienen el formato esperado

**Resultado:** ✅ Todos los índices validados correctamente usando Chart API directamente (sin `yfinance`).

## Notas Técnicas

1. **Cambio de NASDAQ Composite a NASDAQ 100:**
   - Inicialmente se usaba `^IXIC` (NASDAQ Composite)
   - Se cambió a `^NDX` (NASDAQ 100) que es más común como benchmark
   - Todos los nombres en el código y templates fueron actualizados a "NASDAQ 100"

2. **Problema de Caché del Navegador:**
   - Durante el desarrollo se encontró que cambios en JavaScript requerían hard refresh (Ctrl+Shift+R)
   - Cambios en Python requieren reinicio del servidor Flask

3. **Formato de Fechas:**
   - Las fechas se normalizan al primer día de cada mes para agrupación
   - El gráfico muestra fechas en formato "YYYY-MM"

## Referencias

- [Yahoo Finance Chart API](https://query1.finance.yahoo.com/v8/finance/chart/)
- [Modified Dietz Method](https://en.wikipedia.org/wiki/Modified_Dietz_method)
- [Chart.js Documentation](https://www.chartjs.org/docs/latest/)

