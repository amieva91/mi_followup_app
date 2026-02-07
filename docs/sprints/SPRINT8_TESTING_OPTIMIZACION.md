# 🧪 SPRINT 8 - TESTING Y OPTIMIZACIÓN
## 🚧 EN PROGRESO

**Versión**: v8.0.0  
**Inicio**: Febrero 2026  
**Duración estimada**: 2 semanas  
**Estado**: ❌ SIN HITOS ACTIVOS (todos pospuestos al final del proyecto)

**Última actualización**: Febrero 2026  
**Progreso**: —

---

## 🎯 OBJETIVOS DEL SPRINT

Asegurar calidad, cobertura de tests y performance óptimo del sistema.

---

## 📋 HITOS PLANIFICADOS

### **HITO 1: Tests Unitarios** ⏸️ POSPUESTO
**Prioridad**: —  
**Estado**: Se hará al final del proyecto (no en este sprint)

**Objetivos** (para referencia futura):
- Cobertura > 80% con pytest
- Modelos: Asset, PortfolioHolding, Transaction, etc.
- Servicios: PriceUpdater, Importer, FIFO, Metrics
- Utilidades: formatters, converters, date helpers

**Tareas**:
- [ ] Configurar pytest y coverage
- [ ] Tests de modelos
- [ ] Tests de servicios críticos
- [ ] Tests de utilidades

---

### **HITO 2: Tests de Integración** ⏸️ POSPUESTO
**Prioridad**: —  
**Estado**: Se hará al final del proyecto (no en este sprint)

**Objetivos** (para referencia futura):
- Flujos completos end-to-end
- Login → Import CSV → View Holdings → Update Prices
- Flujo compra/venta (Buy → Sell → P&L)
- Flujo dividendos

**Tareas**:
- [ ] Tests de integración con base de datos de prueba
- [ ] Flujos críticos cubiertos

---

### **HITO 3: Optimización de Base de Datos** ⏸️ POSPUESTO
**Prioridad**: —  
**Estado**: Se hará al final del proyecto (no en este sprint)

**Objetivos** (para referencia futura):
- Índices en columnas frecuentes
- Analizar query plans (EXPLAIN)
- Optimizar queries lentas

**Tareas**:
- [ ] Añadir índices (assets.symbol, transactions.transaction_date, etc.)
- [ ] Revisar N+1 queries
- [ ] Benchmarking de queries críticas

---

### **HITO 4: Logging y Monitoring** ⏸️ POSPUESTO
**Prioridad**: —  
**Estado**: Se hará al final del proyecto (no en este sprint)

**Objetivos** (para referencia futura):
- Logging estructurado (logs/app.log)
- Rotación de logs
- Niveles INFO, WARNING, ERROR

**Tareas**:
- [ ] Configurar logging centralizado
- [ ] Log rotation
- [ ] Documentar troubleshooting

---

## 🛠️ TECNOLOGÍAS

- pytest, pytest-cov
- SQLite (testing con :memory:)
- logging (Python standard library)

---

## 📝 ENTREGABLES OBJETIVO

- ✅ Cobertura de tests > 80%
- ✅ Performance < 1s response time en endpoints críticos
- ✅ Logging y monitoring activo
- ✅ Documentación técnica actualizada

---

## 📝 NOTAS

- **HITOS 1-4**: Todos pospuestos al final del proyecto.

---

*Documento creado al pasar a Sprint 8. Actualizar conforme se avance.*
