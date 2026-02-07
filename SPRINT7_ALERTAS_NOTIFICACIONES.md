# 🔔 SPRINT 7 - ALERTAS Y NOTIFICACIONES
## 🚧 EN PROGRESO

**Versión**: v7.0.0  
**Inicio**: Febrero 2026  
**Duración estimada**: 2 semanas  
**Estado**: 🚧 PLANIFICACIÓN

**Última actualización**: Febrero 2026  
**Progreso**: 0%

---

## 🎯 OBJETIVOS DEL SPRINT

Implementar un sistema de alertas y notificaciones para mantener al usuario informado de eventos relevantes en su portfolio y watchlist.

---

## 📋 HITOS PLANIFICADOS

### **HITO 1: Alertas de Precio**
**Prioridad**: 🔴 ALTA  
**Estado**: ⏳ PENDIENTE

**Objetivos**:
- Alertas cuando un asset alcanza un precio objetivo
- Configuración de umbrales por asset (precio superior/inferior)
- Notificaciones en la aplicación

**Tareas**:
- [ ] Modelo de configuración de alertas de precio por usuario/asset
- [ ] Sistema de evaluación (comparar precio actual vs umbral)
- [ ] UI para configurar alertas
- [ ] Visualización de alertas activas

---

### **HITO 2: Calendario de Dividendos**
**Prioridad**: 🟡 MEDIA  
**Estado**: ⏳ PENDIENTE

**Objetivos**:
- Alertas de próximos dividendos
- Integración con datos de Yahoo Finance (ex-dividend date, payment date)

**Tareas**:
- [ ] Obtener fechas de dividendos (Yahoo Finance o similar)
- [ ] Modelo/configuración de alertas de dividendos
- [ ] UI para visualizar calendario
- [ ] Notificaciones antes del ex-dividend date

---

### **HITO 3: Eventos Corporativos**
**Prioridad**: 🟢 BAJA  
**Estado**: ⏳ PENDIENTE

**Objetivos**:
- Alertas de resultados trimestrales (earnings)
- Alertas de próximas presentaciones de resultados

**Tareas**:
- [ ] Integración con datos de earnings (Yahoo Finance, etc.)
- [ ] Campo `next_earnings_date` ya existe en Watchlist
- [ ] Extender para alertas configurables

---

## 🛠️ TECNOLOGÍAS

- Reutilizar servicios existentes (Yahoo Finance, Watchlist)
- Considerar sistema de notificaciones en-app (toast, badges)

---

## 📝 NOTAS

- El watchlist ya tiene `next_earnings_date` y colores por proximidad
- Definir alcance exacto en reunión de planificación

---

*Documento creado al finalizar Sprint 6. Actualizar conforme se avance en la planificación.*
