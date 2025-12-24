# 🎯 SPRINT 6 - DIVERSIFICACIÓN Y WATCHLIST
## 🚧 EN PROGRESO

**Versión**: v6.0.0  
**Inicio**: 24 Diciembre 2025  
**Duración estimada**: 2 semanas  
**Estado**: 🚧 PLANIFICADO

---

## 🎯 OBJETIVOS DEL SPRINT

Implementar funcionalidades avanzadas de análisis de diversificación y gestión de watchlist para mejorar la toma de decisiones de inversión.

---

## 📋 HITOS PLANIFICADOS

### **HITO 1: Análisis de Concentración** 
**Prioridad**: 🔴 ALTA  
**Duración estimada**: 3-4 días

**Objetivos**:
- Identificar concentración de riesgo en el portfolio
- Alertas automáticas cuando un asset supera un umbral (% del portfolio)
- Análisis de diversificación por sector, país, industria
- Métricas de concentración (índice de Herfindahl-Hirschman)

**Tareas**:
- [ ] Calcular métricas de concentración por asset
- [ ] Calcular métricas de concentración por sector/país/industria
- [ ] Sistema de alertas configurables (ej: alerta si un asset > 10% del portfolio)
- [ ] Visualización de concentración en dashboard
- [ ] Página dedicada de análisis de diversificación

---

### **HITO 2: Watchlist con Comparación**
**Prioridad**: 🟡 MEDIA  
**Duración estimada**: 3-4 días

**Objetivos**:
- Crear lista de assets a seguir (watchlist)
- Comparar performance de watchlist vs portfolio actual
- Alertas de precio para assets en watchlist
- Integración con AssetRegistry existente

**Tareas**:
- [ ] Modelo Watchlist (relación many-to-many User-Asset)
- [ ] CRUD de watchlist (añadir/eliminar assets)
- [ ] Página dedicada de watchlist
- [ ] Comparación visual watchlist vs portfolio (gráficos)
- [ ] Alertas de precio para assets en watchlist
- [ ] Integración con página de detalle de asset

---

### **HITO 3: Alertas de Diversificación**
**Prioridad**: 🟡 MEDIA  
**Duración estimada**: 2-3 días

**Objetivos**:
- Sistema de alertas configurables para diversificación
- Alertas cuando el portfolio está demasiado concentrado
- Recomendaciones de diversificación
- Configuración de umbrales personalizados

**Tareas**:
- [ ] Sistema de configuración de alertas por usuario
- [ ] Alertas de concentración por asset (ej: > 10%)
- [ ] Alertas de concentración por sector (ej: > 30%)
- [ ] Alertas de concentración por país (ej: > 40%)
- [ ] Panel de configuración de alertas
- [ ] Notificaciones en dashboard cuando se activan alertas

---

## 🛠️ TECNOLOGÍAS Y LIBRERÍAS

- **Gráficos**: Chart.js (ya implementado)
- **BD**: SQLite (actual)
- **Modelos**: Nuevo modelo Watchlist, expansión de métricas existentes

---

## 📊 MÉTRICAS DE ÉXITO

- ✅ Sistema de alertas de concentración funcionando
- ✅ Watchlist completo con comparación vs portfolio
- ✅ Métricas de diversificación calculadas correctamente
- ✅ Visualizaciones claras y útiles para toma de decisiones
- ✅ Configuración de umbrales flexible y fácil de usar

---

## 📝 NOTAS Y CONSIDERACIONES

- **Reutilización**: Aprovechar métricas y gráficos existentes del Sprint 4
- **Performance**: Considerar cache para cálculos de diversificación
- **UX**: Hacer las alertas visibles pero no intrusivas
- **Escalabilidad**: Watchlist debería soportar muchos assets sin problemas de rendimiento

---

## 🔗 REFERENCIAS

- Métricas existentes: `app/services/metrics/basic_metrics.py`
- Gráficos de distribución: `app/templates/portfolio/dashboard.html`
- AssetRegistry: `app/models/asset.py`, `app/routes/portfolio.py`
- Sistema de alertas: Considerar integración futura con notificaciones (Sprint 7)

---

## 📋 CHECKLIST DE IMPLEMENTACIÓN

### HITO 1: Análisis de Concentración
- [ ] Modelo/estrutura para almacenar métricas de concentración
- [ ] Cálculo de concentración por asset (porcentaje del portfolio)
- [ ] Cálculo de concentración por sector/país/industria
- [ ] Visualización en dashboard
- [ ] Página dedicada de análisis

### HITO 2: Watchlist
- [ ] Modelo Watchlist (tabla de relación)
- [ ] Migración de BD
- [ ] Endpoints API para CRUD
- [ ] Interfaz para gestionar watchlist
- [ ] Comparación watchlist vs portfolio
- [ ] Integración en páginas relevantes

### HITO 3: Alertas
- [ ] Modelo de configuración de alertas
- [ ] Sistema de evaluación de alertas
- [ ] Visualización de alertas activas
- [ ] Panel de configuración
- [ ] Logging de alertas activadas

