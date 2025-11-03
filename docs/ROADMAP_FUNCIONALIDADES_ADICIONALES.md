# 🗺️ ROADMAP: Funcionalidades Adicionales

**Fecha:** 3 Noviembre 2025  
**Organización de funcionalidades sugeridas en sprints**

---

## 📊 SPRINT 4: Calculadora de Métricas Avanzadas

**Objetivo:** Análisis financiero profundo con métricas de rendimiento y riesgo

### **✅ Funcionalidades Core (Ya contempladas):**
1. P&L Realizado y No Realizado
2. ROI Simple y Anualizado
3. Time-Weighted Return (TWR)
4. Money-Weighted Return (IRR)
5. Sharpe Ratio
6. Max Drawdown
7. Volatilidad (Std Dev)

### **🆕 Funcionalidades Adicionales a Incluir:**

#### **A. Gráficos de Evolución**
- **Gráfico de Evolución del Portfolio** (line chart)
  - Eje X: Tiempo (seleccionable: 1M, 3M, 6M, 1Y, Todo)
  - Eje Y: Valor del portfolio en EUR
  - Líneas: Valor de mercado + Costo (para ver P&L visual)
  - Área sombreada: P&L (verde si positivo, rojo si negativo)

- **Gráfico de P&L Acumulado** (area chart)
  - P&L Realizado (área verde fija)
  - P&L No Realizado (área azul variable)
  - Línea total (suma de ambos)

#### **B. Top Ganadores/Perdedores**
- **Gráfico de Barras Horizontales**
  - Top 5 assets con mejor P&L %
  - Top 5 assets con peor P&L %
  - Colores: Verde para ganadores, Rojo para perdedores

#### **C. Comparación con Benchmarks**
- Comparar rendimiento del portfolio con:
  - S&P 500
  - NASDAQ
  - IBEX 35
  - EURO STOXX 50
- Gráfico de líneas comparativo
- % de outperformance/underperformance

**Librerías recomendadas:** ApexCharts para todos los gráficos

---

## 📈 SPRINT 5: Actualización Automática de Precios

**Objetivo:** Automatizar actualización de precios y mantener histórico

### **✅ Funcionalidades Core (Ya contempladas):**
1. Cron job para actualización diaria
2. Tabla `price_history` para histórico
3. Gráfico de precio histórico por asset

### **🆕 Funcionalidades Adicionales a Incluir:**

#### **A. Histórico de Precios**
- **Tabla `PriceHistory`:**
  ```python
  class PriceHistory(db.Model):
      id = db.Column(db.Integer, primary_key=True)
      asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'))
      date = db.Column(db.Date, nullable=False, index=True)
      open = db.Column(db.Float)
      high = db.Column(db.Float)
      low = db.Column(db.Float)
      close = db.Column(db.Float)
      volume = db.Column(db.BigInteger)
      created_at = db.Column(db.DateTime, default=datetime.utcnow)
  ```

- **Gráfico Candlestick** (ApexCharts)
  - Mostrar OHLC (Open, High, Low, Close)
  - Volumen en barras debajo
  - Rangos: 1M, 3M, 6M, 1Y

#### **B. Automatización**
- **Cron Job con Flask-APScheduler**
  ```python
  from flask_apscheduler import APScheduler
  
  scheduler = APScheduler()
  
  @scheduler.task('cron', id='update_prices', hour=18, minute=0)
  def scheduled_price_update():
      """Actualizar precios diariamente a las 18:00 UTC"""
      users = User.query.all()
      for user in users:
          updater = PriceUpdater()
          updater.update_all_prices(user.id)
  ```

- **Configuración en UI:**
  - Activar/desactivar auto-update
  - Elegir hora preferida
  - Notificación email al completar

#### **C. Cache de Precios**
- **Implementar Redis** para cachear precios
  - TTL: 15 minutos
  - Evitar llamadas excesivas a Yahoo Finance
  - Mejorar performance

---

## 🎯 SPRINT 6: Análisis de Diversificación y Visualización

**Objetivo:** Análisis de distribución y riesgo del portfolio

### **🆕 Funcionalidades a Implementar:**

#### **A. Gráficos de Distribución**

1. **Distribución por Asset** (Pie Chart / Donut Chart)
   - % del valor total por cada asset
   - Colores diferenciados
   - Click para ver detalles del asset

2. **Distribución por Sector** (Pie Chart)
   - Technology, Healthcare, Finance, Consumer, etc.
   - Identificar concentración sectorial
   - Colores temáticos por sector

3. **Distribución por País** (Pie Chart o Mapa)
   - USA, España, Hong Kong, etc.
   - Geografía de riesgo
   - Mapa interactivo (opcional con D3.js)

4. **Distribución por Tipo de Asset** (Donut Chart)
   - Acciones individuales
   - ETFs
   - REITs
   - Otros

#### **B. Análisis de Concentración**

- **Indicador de Concentración de Riesgo:**
  ```
  Concentración Alta:    >30% en un solo asset
  Concentración Media:   20-30% en un solo asset
  Bien Diversificado:    <20% en cada asset
  ```

- **Recomendaciones Automáticas:**
  - "Tu portfolio está muy concentrado en Technology (60%)"
  - "Considera reducir exposición a ASTS (35% del portfolio)"
  - "Bien diversificado por sectores ✓"

#### **C. Watchlist (Lista de Seguimiento)**

**Tabla `Watchlist`:**
```python
class Watchlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'))
    target_price = db.Column(db.Float)  # Precio objetivo
    notes = db.Column(db.Text)          # Notas personales
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

**Funcionalidades:**
- Añadir assets sin tener que comprarlos
- Ver precios actuales de assets watchlist
- Alertas cuando alcancen precio objetivo
- Notas sobre por qué estás vigilando ese asset

---

## 🔔 SPRINT 7: Alertas y Notificaciones

**Objetivo:** Sistema de alertas para eventos importantes

### **🆕 Funcionalidades a Implementar:**

#### **A. Alertas de Precio**

**Tabla `PriceAlert`:**
```python
class PriceAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'))
    condition = db.Column(db.String(10))  # 'above', 'below'
    price = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)
    notification_method = db.Column(db.String(20))  # 'email', 'app', 'both'
    triggered_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

**Funcionalidades:**
- "Notificarme si ASTS sube de $20"
- "Notificarme si GRF.MC baja de 9€"
- Email automático cuando se dispara
- Notificación en app (badge)

#### **B. Calendario de Dividendos**

**Tabla `DividendCalendar`:**
```python
class DividendCalendar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'))
    ex_dividend_date = db.Column(db.Date)
    payment_date = db.Column(db.Date)
    dividend_amount = db.Column(db.Float)
    frequency = db.Column(db.String(20))  # 'quarterly', 'annual', etc.
```

**Vista de Calendario:**
- Vista mensual/anual
- Destacar próximos dividendos (7 días)
- Estimación de ingresos por dividendos
- Histórico de dividendos recibidos

#### **C. Alertas de Eventos Corporativos**

**Eventos a notificar:**
- Cambio en recomendación de analistas
- Publicación de resultados trimestrales
- Dividendo anunciado
- Stock splits
- Cambios significativos en precio (±10% en un día)

#### **D. Conversión Automática de Divisas**

**API de Forex recomendada: ExchangeRate-API (gratis)**
- https://www.exchangerate-api.com/
- Gratis: 1,500 requests/mes
- Actualización diaria

**Implementación:**
```python
import requests

def get_forex_rate(from_currency, to_currency='EUR'):
    """Obtener tasa de cambio actual"""
    url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
    response = requests.get(url)
    data = response.json()
    return data['rates'].get(to_currency, 1.0)

# Ejemplo de uso:
usd_to_eur = get_forex_rate('USD', 'EUR')  # 0.92
market_value_eur = market_value_usd * usd_to_eur
```

**Tabla `ForexRate` (cache):**
```python
class ForexRate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_currency = db.Column(db.String(3))
    to_currency = db.Column(db.String(3))
    rate = db.Column(db.Float)
    date = db.Column(db.Date, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

**Funcionalidades:**
- Conversión automática de todos los valores a EUR
- Actualización diaria de tasas
- Histórico de tasas de cambio
- Mostrar valor en moneda original + EUR

---

## 🧪 SPRINT 8: Testing y Optimización

**Objetivo:** Asegurar calidad, performance y estabilidad

### **🆕 Funcionalidades a Implementar:**

#### **A. Testing Completo**
- **Tests Unitarios** (pytest)
  - Modelos (Asset, PortfolioHolding, Transaction, etc.)
  - Servicios (PriceUpdater, Importer, FIFO)
  - Utilidades (formatters, converters)

- **Tests de Integración**
  - Rutas completas (login → import CSV → view holdings)
  - Flujos críticos (compra → venta → P&L)

- **Cobertura Objetivo: 80%+**
  ```bash
  pytest --cov=app --cov-report=html
  ```

#### **B. Optimización de Performance**

1. **Database Query Optimization**
   - Añadir índices a columnas frecuentemente consultadas
   - Usar `joinedload()` para evitar N+1 queries
   - Implementar paginación en listas largas

2. **Caching con Redis**
   - Cachear precios de Yahoo Finance (15 min TTL)
   - Cachear totales del dashboard (5 min TTL)
   - Cachear tasas de forex (1 día TTL)

3. **Lazy Loading de Imágenes**
   - Usar `loading="lazy"` en tags `<img>`
   - Placeholder mientras carga

4. **Minificación de Assets**
   - Minificar CSS/JS en producción
   - Comprimir imágenes
   - Usar CDN para librerías

#### **C. Logging y Monitoring**

1. **Sistema de Logs**
   ```python
   import logging
   
   # Configurar logging
   logging.basicConfig(
       level=logging.INFO,
       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
       handlers=[
           logging.FileHandler('logs/app.log'),
           logging.StreamHandler()
       ]
   )
   ```

2. **Métricas a Monitorear:**
   - Tiempo de respuesta de endpoints
   - Errores de Yahoo Finance API
   - Tasas de éxito/fallo en imports
   - Uso de memoria y CPU

3. **Alertas de Sistema:**
   - Error rate > 5%
   - Response time > 2s
   - Disco > 80% full

---

## 📅 CRONOGRAMA GLOBAL

```
┌────────────────────────────────────────────────────────────┐
│ ROADMAP COMPLETO                                           │
├────────────────────────────────────────────────────────────┤
│ ✅ Sprint 0:  Setup Inicial (COMPLETADO)                  │
│ ✅ Sprint 1:  Autenticación (COMPLETADO)                  │
│ ✅ Sprint 2:  Gastos e Ingresos (COMPLETADO)              │
│ ✅ Sprint 3:  CSV Processor + Portfolio (COMPLETADO)      │
│ 🔄 Sprint 3F: Precios en Tiempo Real (EN CURSO - 1-2 sem) │
│ ⏳ Sprint 4:  Métricas Avanzadas (3 semanas)              │
│ ⏳ Sprint 5:  Actualización Automática (2 semanas)        │
│ ⏳ Sprint 6:  Diversificación y Watchlist (2 semanas)     │
│ ⏳ Sprint 7:  Alertas y Notificaciones (2 semanas)        │
│ ⏳ Sprint 8:  Testing y Optimización (2 semanas)          │
└────────────────────────────────────────────────────────────┘

TOTAL: ~14 semanas (3.5 meses)
```

---

## 🎯 PRIORIZACIÓN

### **🔴 ALTA PRIORIDAD (Implementar primero):**
1. Sprint 3F: Precios en Tiempo Real
2. Sprint 4: Métricas Avanzadas (P&L, ROI, gráficos básicos)
3. Sprint 5: Actualización Automática (cron + histórico)

### **🟡 MEDIA PRIORIDAD (Después de core):**
4. Sprint 6: Diversificación y Watchlist
5. Sprint 7: Alertas básicas de precio
6. Conversión automática EUR

### **🟢 BAJA PRIORIDAD (Cuando todo lo demás funcione):**
7. Sprint 7: Calendario de dividendos
8. Sprint 7: Eventos corporativos
9. Sprint 8: Testing exhaustivo
10. Sprint 8: Optimización avanzada

---

## 📊 MÉTRICAS DE ÉXITO

Al completar todo el roadmap, deberías tener:

- ✅ Portfolio con precios en tiempo real
- ✅ Métricas de rendimiento completas (P&L, ROI, Sharpe, etc.)
- ✅ Gráficos interactivos de evolución y distribución
- ✅ Actualización automática diaria de precios
- ✅ Sistema de alertas funcional
- ✅ Análisis de diversificación
- ✅ Cobertura de tests > 80%
- ✅ Performance optimizado (< 1s response time)
- ✅ Sistema estable en producción

---

**Última actualización:** 3 Noviembre 2025  
**Próximo paso:** Implementar Sprint 3 Final - Precios en Tiempo Real

