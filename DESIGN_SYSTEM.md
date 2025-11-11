# 🎨 DESIGN SYSTEM - Followup Financial App

**Filosofía**: Elegante, Profesional, Financiero, Minimalista

**Última actualización**: 10 Noviembre 2025  
**Estado**: ✅ Sprint 3 COMPLETADO v3.6.0 | 🚧 Sprint 4 EN PROGRESO v4.2.0-beta (HITO 1 ✅ | HITO 2 ✅ | Refinements ✅ | UX Avanzadas ✅)

---

## ✅ COMPONENTES IMPLEMENTADOS (Sprint 1)

**Templates Base**
- ✅ Layout principal (`base/layout.html`) con Tailwind CSS
- ✅ Navbar dinámica (muestra usuario logueado)
- ✅ Sistema de flash messages con colores
- ✅ Footer profesional

**Páginas de Autenticación**
- ✅ Login (diseño azul)
- ✅ Registro (diseño verde)
- ✅ Solicitar reset (diseño naranja)
- ✅ Resetear contraseña (diseño morado)

**Dashboard**
- ✅ Cards de KPIs placeholder
- ✅ Sección de información de usuario
- ✅ Sección de próximos pasos

**Componentes UI Usados**
- ✅ Formularios con validación y estados de error
- ✅ Botones con colores semánticos
- ✅ Cards con sombras
- ✅ Íconos Heroicons (SVG inline)
- ✅ Badges y tags

## ✅ COMPONENTES IMPLEMENTADOS (Sprint 2)

**Gastos e Ingresos**
- ✅ Tablas jerárquicas con subcategorías indentadas
- ✅ Emoji picker interactivo
- ✅ Formularios de recurrencia (daily/weekly/monthly/yearly)
- ✅ Modal de confirmación para eliminación de series
- ✅ KPI cards con iconos y porcentajes de cambio
- ✅ Badges de estado para recurrencias

## ✅ COMPONENTES IMPLEMENTADOS (Sprint 3)

**Portfolio Manager**
- ✅ Dropdown de navegación en navbar (con link a "Importar CSV")
- ✅ Dashboard de portfolio con métricas
- ✅ Tablas de holdings y transacciones
- ✅ Formularios multi-step para transacciones
- ✅ Modal de confirmación destructiva (con Alpine.js)
- ✅ Cards de cuentas con acciones de editar/eliminar
- ✅ Badges de divisa y tipo de activo
- ✅ Formularios con selects dinámicos

**CSV Processor (HITO 3-6)**
- ✅ Formulario de subida de CSV con drag & drop
- ✅ Selector de archivo con preview de nombre
- ✅ Validación de extensión .csv
- ✅ Flash messages con estadísticas de importación
- ✅ Cards informativas con instrucciones
- ✅ Select de cuenta de broker
- ✅ Feedback visual de proceso de importación
- ✅ Mensajes diferenciados por tipo (success, error, info)

**Mejoras Finales Sprint 3 (v3.2.0)**
- ✅ **Formato Europeo**: Números con punto como separador de miles y coma como decimal (1.234,56)
- ✅ **Filtros Jinja2 personalizados**: `number_eu` y `decimal_eu(2)` para formateo consistente
- ✅ **Visualización de Assets**: Línea gris con formato `Type • Currency • ISIN` en lugar de nombre duplicado
- ✅ **Jerarquía visual mejorada**: Símbolos en bold, información secundaria en gris claro
- ✅ **Búsqueda avanzada**: Filtros real-time sin botón "Buscar"
- ✅ **Tablas ordenables**: Click en encabezados para ordenar columnas
- ✅ **Visualización de moneda**: Mostrada junto a precios y costes totales
- ✅ **Iconos de advertencia**: ⚠️ en dividendos no-EUR que requieren revisión

**AssetRegistry - Sistema Global (v3.3.0-3.3.4)**
- ✅ **Interfaz de Gestión** (`/portfolio/asset-registry`):
  - Panel de estadísticas con 4 cards (Total, Enriquecidos, Pendientes, Completitud %)
  - Búsqueda en tiempo real por ISIN, Symbol, Nombre
  - Filtro: "Solo sin enriquecer" (checkbox con auto-submit)
  - Tabla completa con 10 columnas **TODAS ORDENABLES** (incluyendo "Uso" con tooltip)
  - Badges de estado: Verde (✓ Enriquecido) / Naranja (⚠️ Pendiente)
  - **Estado inteligente**: Solo requiere `symbol` (MIC opcional, mejora precisión)
  - Fuentes monoespaciadas para ISIN y símbolos
  - Truncamiento de nombres largos con tooltip
  - **Modal de edición mejorado**: 
    - Formulario con 6 campos (Symbol, Exchange, MIC, Yahoo Suffix, Tipo, Nombre)
    - **Botón de enriquecimiento integrado**: "🔍 Enriquecer con OpenFIGI" dentro del modal
    - **Campo de Yahoo URL**: Input + botón "🔗 Desde URL" para corrección manual
    - Feedback visual en tiempo real con estados (loading/success/error)
  - Botones de acción: "✏️ Editar" (azul) y "🗑️" (rojo) por fila
  - Confirmación para eliminación
  - **Link a Mappings**: Botón "🗺️ Gestionar Mapeos" para acceso rápido
- ✅ **Banner de acceso en Transacciones**:
  - Card destacado en morado (`bg-purple-50 border-purple-200`)
  - Título: "🗄️ Registro Global de Assets"
  - Descripción breve
  - Botón call-to-action: "📊 Ver Registro Global →"
- ✅ **Botones de Enriquecimiento Manual** (en edición de transacciones - FUNCIONALES v3.3.4):
  - Sección separada con borde superior (`border-t border-purple-300`)
  - Dos botones: "🤖 Enriquecer con OpenFIGI" y "🌐 Desde URL de Yahoo"
  - **Validación de campos**: JavaScript verifica existencia antes de actualizar
  - **Banners detallados**: Feedback con información completa (Symbol, Exchange, MIC, Yahoo)
  - JavaScript async/await para llamadas AJAX con manejo de errores

**MappingRegistry - Sistema de Mapeos Editables (v3.3.2 - NUEVO)**
- ✅ **Interfaz de Gestión** (`/portfolio/mappings`):
  - Panel de estadísticas con 4 cards (Total, Activos, Inactivos, Tipos)
  - Búsqueda en tiempo real por tipo o clave
  - Filtro por tipo de mapeo (MIC_TO_YAHOO, EXCHANGE_TO_YAHOO, DEGIRO_TO_IBKR)
  - Tabla con 7 columnas ordenables
  - Badges de tipo: Azul (MIC→Yahoo) / Verde (Exchange→Yahoo) / Morado (DeGiro→IBKR)
  - Toggle de estado: Activar/Desactivar sin eliminar
  - **Modal de creación**: Formulario con 5 campos (Tipo, Clave, Valor, País, Descripción)
  - **Modal de edición**: Permite modificar todos los campos excepto el tipo
  - Confirmación para eliminación
  - **Acceso desde AssetRegistry**: Link bidireccional
- ✅ **Mappers Dinámicos**:
  - `YahooSuffixMapper` lee de BD (tabla `mapping_registry`)
  - `ExchangeMapper` lee de BD (tabla `mapping_registry`)
  - Cache en memoria para performance
  - Recarga automática si se detectan cambios

**Fixes de Estabilidad (v3.3.4)**
- ✅ **Progreso de Importación**:
  - Primer archivo ahora visible en "Completados" (fix de índices 0-based)
  - Conteo correcto: "5/5 archivos" en lugar de "4/5"
  - Archivos procesados mostrados en tiempo real
  - Estimación de tiempo más precisa
- ✅ **Botones de Enriquecimiento**:
  - JavaScript validado: No intenta actualizar campos inexistentes
  - Feedback visual mejorado con banners tipo "card"
  - Estados de loading claros ("⏳ Consultando OpenFIGI...")
  - Manejo de errores más robusto

## ✅ SPRINT 3 FINAL - PRECIOS Y DIVISAS (v3.4.0 - v3.5.0)

**Precios en Tiempo Real (v3.4.0)**
- ✅ **Integración Yahoo Finance**:
  - Autenticación completa (cookie + crumb)
  - 15 métricas por asset: precio, cambio %, market cap, P/E, beta, dividend yield, etc.
  - Actualización manual con botón "🔄 Actualizar Precios"
  - Progress bar en tiempo real (modal no-bloqueante)
  - Manejo de assets fallidos (suspendidos, delisted)
- ✅ **Dashboard Mejorado**:
  - Valores actuales en tiempo real
  - P&L no realizado calculado automáticamente
  - Cambio % del día por holding
  - Última actualización timestamp
- ✅ **Modal de Progreso**:
  - Título dinámico: "Actualizando..." → "✅ Actualización Completa" / "⚠️ Completado con errores"
  - Progreso X/Y assets procesados
  - Spinner animado (se detiene al completar)
  - Botón "Cerrar" (sin reload automático)
  - Estados: idle → updating → success/partial/error

**Conversión de Divisas (v3.5.0)**
- ✅ **Servicio de Divisas** (`app/services/currency_service.py`):
  - API: `exchangerate-api.com` (gratis, sin API key)
  - Cache de 24 horas thread-safe
  - 166 monedas soportadas
  - Fallback rates integrados
  - Manejo especial de GBX (British Pence = GBP/100)
- ✅ **Página de Divisas** (`/portfolio/currencies`):
  - Tabla con tasas de conversión a EUR
  - Filtrado por monedas del portfolio
  - Información de cache (última actualización, edad)
  - Botón "🔄 Actualizar Tasas" con CSRF token
  - Flags de países + nombres de divisas
  - Tasa directa (X → EUR) e inversa (EUR → X)
- ✅ **Display Dual Currency**:
  - Valor Actual: **Cantidad EUR** (principal, bold)
  - Debajo: Cantidad local en gris (si ≠ EUR)
  - Ejemplo: "4.623 EUR" / "31,51 USD"
- ✅ **Holdings Page Ampliada**:
  - Ancho: `max-w-7xl` → `max-w-[95%]` (más espacio para columnas futuras)
  - Columna P&L con colores: verde (positivo), rojo (negativo)
  - P&L % calculado: `(current_value - cost) / cost * 100`
- ✅ **FIX CRÍTICO - Coste Total**:
  - **BUG**: Sumaba costes SIN conversión a EUR (ej: 31.600 GBX + 5.000 USD = 36.600 ❌)
  - **FIX**: Convierte cada holding a EUR ANTES de sumar (ej: 382 EUR + 4.600 EUR = 4.982 EUR ✅)
  - **Impacto**: Dashboard mostraba 957K EUR en lugar de ~96K EUR (error 10x)

---

## 🎯 PRINCIPIOS DE DISEÑO

```
1. CLARIDAD SOBRE TODO
   → La información financiera debe ser inmediatamente comprensible

2. JERARQUÍA VISUAL CLARA
   → Lo más importante destaca, lo secundario pasa a segundo plano

3. CONSISTENCIA
   → Mismos componentes, mismos comportamientos

4. ACCESIBILIDAD
   → Contraste suficiente, tamaños legibles, mobile-first

5. PERFORMANCE
   → Carga rápida, animaciones sutiles, sin bloat
```

---

## 🎨 PALETA DE COLORES

### Colores Principales

```css
/* Azul Corporativo - Principal */
--primary-50:  #eff6ff;
--primary-100: #dbeafe;
--primary-200: #bfdbfe;
--primary-300: #93c5fd;
--primary-400: #60a5fa;
--primary-500: #3b82f6;  /* Principal */
--primary-600: #2563eb;
--primary-700: #1d4ed8;  /* Hover */
--primary-800: #1e40af;  /* Active */
--primary-900: #1e3a8a;

/* Verde Finanzas - Positivo */
--success-50:  #f0fdf4;
--success-100: #dcfce7;
--success-500: #22c55e;  /* Ganancias, positivo */
--success-700: #15803d;

/* Rojo - Negativo/Alertas */
--danger-50:  #fef2f2;
--danger-100: #fee2e2;
--danger-500: #ef4444;   /* Pérdidas, negativo */
--danger-700: #b91c1c;

/* Ámbar - Advertencias */
--warning-50:  #fffbeb;
--warning-100: #fef3c7;
--warning-500: #f59e0b;  /* Advertencias */
--warning-700: #b45309;
```

### Grises (Neutros)

```css
/* Escala de grises */
--gray-50:  #f9fafb;
--gray-100: #f3f4f6;  /* Fondo secundario */
--gray-200: #e5e7eb;  /* Bordes sutiles */
--gray-300: #d1d5db;  /* Bordes normales */
--gray-400: #9ca3af;  /* Texto deshabilitado */
--gray-500: #6b7280;  /* Texto secundario */
--gray-600: #4b5563;  /* Texto normal */
--gray-700: #374151;  /* Texto oscuro */
--gray-800: #1f2937;  /* Encabezados */
--gray-900: #111827;  /* Texto muy oscuro */
```

### Uso de Colores

```
TEXTOS:
- Encabezados: gray-900
- Texto normal: gray-700
- Texto secundario: gray-500
- Texto deshabilitado: gray-400

FONDOS:
- Fondo principal: white
- Fondo secundario: gray-50
- Cards elevadas: white con shadow

BORDES:
- Bordes sutiles: gray-200
- Bordes definidos: gray-300

NÚMEROS FINANCIEROS:
- Positivos (ganancias): success-600
- Negativos (pérdidas): danger-600
- Neutros: gray-700
```

---

## 📝 TIPOGRAFÍA

### Font Stack

```css
font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 
             'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
```

**Instalar Inter**: Incluir en `<head>`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

### Escalas de Tamaño

```css
/* Headings */
.text-4xl { font-size: 2.25rem; line-height: 2.5rem; }    /* H1 */
.text-3xl { font-size: 1.875rem; line-height: 2.25rem; }  /* H2 */
.text-2xl { font-size: 1.5rem; line-height: 2rem; }       /* H3 */
.text-xl  { font-size: 1.25rem; line-height: 1.75rem; }   /* H4 */
.text-lg  { font-size: 1.125rem; line-height: 1.75rem; }  /* Subtítulos */

/* Body */
.text-base { font-size: 1rem; line-height: 1.5rem; }      /* Texto normal */
.text-sm   { font-size: 0.875rem; line-height: 1.25rem; } /* Texto pequeño */
.text-xs   { font-size: 0.75rem; line-height: 1rem; }     /* Labels */
```

### Pesos de Fuente

```css
.font-normal   { font-weight: 400; }  /* Texto normal */
.font-medium   { font-weight: 500; }  /* Énfasis sutil */
.font-semibold { font-weight: 600; }  /* Headings, botones */
.font-bold     { font-weight: 700; }  /* Títulos principales */
```

### Números Financieros

```css
/* Para números, usar números tabulares */
.tabular-nums {
  font-feature-settings: 'tnum';
  font-variant-numeric: tabular-nums;
}

/* Ejemplo de uso */
<span class="text-2xl font-semibold tabular-nums text-gray-900">
  12,345.67 €
</span>
```

---

## 🧱 COMPONENTES BASE

### 1. Cards

```html
<!-- Card básica -->
<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
  <h3 class="text-lg font-semibold text-gray-900 mb-2">Título</h3>
  <p class="text-sm text-gray-600">Contenido</p>
</div>

<!-- Card con hover -->
<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 
            hover:shadow-md transition-shadow duration-200 cursor-pointer">
  <!-- Contenido -->
</div>

<!-- Card de métrica (KPI) -->
<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
  <div class="flex items-center justify-between">
    <div>
      <p class="text-sm font-medium text-gray-600">Ahorro Mensual</p>
      <p class="text-3xl font-bold tabular-nums text-gray-900 mt-2">
        1,250.50 €
      </p>
    </div>
    <div class="w-12 h-12 bg-primary-100 rounded-full flex items-center justify-center">
      <!-- Icono -->
      <svg class="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    </div>
  </div>
  <div class="mt-4 flex items-center text-sm">
    <span class="text-success-600 font-medium">+12.5%</span>
    <span class="text-gray-500 ml-2">vs mes anterior</span>
  </div>
</div>
```

### 2. Botones

```html
<!-- Botón primario -->
<button class="px-4 py-2 bg-primary-600 text-white font-medium rounded-lg
               hover:bg-primary-700 active:bg-primary-800
               focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2
               transition-colors duration-150">
  Guardar
</button>

<!-- Botón secundario -->
<button class="px-4 py-2 bg-white text-gray-700 font-medium rounded-lg border border-gray-300
               hover:bg-gray-50 active:bg-gray-100
               focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2
               transition-colors duration-150">
  Cancelar
</button>

<!-- Botón de peligro -->
<button class="px-4 py-2 bg-danger-600 text-white font-medium rounded-lg
               hover:bg-danger-700 active:bg-danger-800
               focus:outline-none focus:ring-2 focus:ring-danger-500 focus:ring-offset-2
               transition-colors duration-150">
  Eliminar
</button>

<!-- Botón deshabilitado -->
<button disabled class="px-4 py-2 bg-gray-300 text-gray-500 font-medium rounded-lg
                        cursor-not-allowed opacity-60">
  Guardando...
</button>

<!-- Botón pequeño -->
<button class="px-3 py-1.5 text-sm bg-primary-600 text-white font-medium rounded
               hover:bg-primary-700 transition-colors duration-150">
  Ver más
</button>
```

### 3. Formularios

```html
<!-- Input de texto -->
<div class="mb-4">
  <label for="amount" class="block text-sm font-medium text-gray-700 mb-1">
    Cantidad
  </label>
  <input 
    type="text" 
    id="amount" 
    name="amount"
    class="w-full px-3 py-2 border border-gray-300 rounded-lg
           focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent
           placeholder-gray-400"
    placeholder="0.00 €"
  >
</div>

<!-- Input con error -->
<div class="mb-4">
  <label for="email" class="block text-sm font-medium text-gray-700 mb-1">
    Email
  </label>
  <input 
    type="email" 
    id="email" 
    name="email"
    class="w-full px-3 py-2 border border-danger-300 rounded-lg
           focus:outline-none focus:ring-2 focus:ring-danger-500 focus:border-transparent
           bg-danger-50"
    value="correo-invalido"
  >
  <p class="mt-1 text-sm text-danger-600">Email no válido</p>
</div>

<!-- Select -->
<div class="mb-4">
  <label for="category" class="block text-sm font-medium text-gray-700 mb-1">
    Categoría
  </label>
  <select 
    id="category" 
    name="category"
    class="w-full px-3 py-2 border border-gray-300 rounded-lg
           focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
  >
    <option value="">Seleccionar categoría</option>
    <option value="1">Alimentación</option>
    <option value="2">Transporte</option>
  </select>
</div>

<!-- Checkbox -->
<div class="flex items-center">
  <input 
    type="checkbox" 
    id="recurring" 
    name="recurring"
    class="w-4 h-4 text-primary-600 border-gray-300 rounded
           focus:ring-2 focus:ring-primary-500"
  >
  <label for="recurring" class="ml-2 text-sm text-gray-700">
    Es un gasto recurrente
  </label>
</div>

<!-- Radio buttons -->
<div class="space-y-2">
  <div class="flex items-center">
    <input 
      type="radio" 
      id="monthly" 
      name="frequency" 
      value="monthly"
      class="w-4 h-4 text-primary-600 border-gray-300
             focus:ring-2 focus:ring-primary-500"
    >
    <label for="monthly" class="ml-2 text-sm text-gray-700">Mensual</label>
  </div>
  <div class="flex items-center">
    <input 
      type="radio" 
      id="quarterly" 
      name="frequency" 
      value="quarterly"
      class="w-4 h-4 text-primary-600 border-gray-300
             focus:ring-2 focus:ring-primary-500"
    >
    <label for="quarterly" class="ml-2 text-sm text-gray-700">Trimestral</label>
  </div>
</div>
```

### 4. Tablas

```html
<div class="overflow-x-auto">
  <table class="min-w-full divide-y divide-gray-200">
    <thead class="bg-gray-50">
      <tr>
        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
          Fecha
        </th>
        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
          Descripción
        </th>
        <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
          Cantidad
        </th>
        <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
          Acciones
        </th>
      </tr>
    </thead>
    <tbody class="bg-white divide-y divide-gray-200">
      <tr class="hover:bg-gray-50 transition-colors duration-150">
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
          05/10/2025
        </td>
        <td class="px-6 py-4 text-sm text-gray-900">
          Supermercado Mercadona
        </td>
        <td class="px-6 py-4 whitespace-nowrap text-sm text-right tabular-nums text-gray-900">
          85.42 €
        </td>
        <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
          <button class="text-primary-600 hover:text-primary-900 mr-3">Editar</button>
          <button class="text-danger-600 hover:text-danger-900">Eliminar</button>
        </td>
      </tr>
    </tbody>
  </table>
</div>
```

### 5. Badges y Tags

```html
<!-- Badge de estado -->
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
             bg-success-100 text-success-800">
  Activo
</span>

<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
             bg-danger-100 text-danger-800">
  Vencido
</span>

<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
             bg-warning-100 text-warning-800">
  Pendiente
</span>

<!-- Badge con icono -->
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
             bg-primary-100 text-primary-800">
  <svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
    <path d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"/>
  </svg>
  Verificado
</span>
```

### 6. Alertas/Mensajes Flash

```html
<!-- Éxito -->
<div class="bg-success-50 border-l-4 border-success-500 p-4 mb-4" role="alert">
  <div class="flex">
    <div class="flex-shrink-0">
      <svg class="h-5 w-5 text-success-400" viewBox="0 0 20 20" fill="currentColor">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
      </svg>
    </div>
    <div class="ml-3">
      <p class="text-sm text-success-700">
        ¡Gasto guardado correctamente!
      </p>
    </div>
  </div>
</div>

<!-- Error -->
<div class="bg-danger-50 border-l-4 border-danger-500 p-4 mb-4" role="alert">
  <div class="flex">
    <div class="flex-shrink-0">
      <svg class="h-5 w-5 text-danger-400" viewBox="0 0 20 20" fill="currentColor">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
      </svg>
    </div>
    <div class="ml-3">
      <p class="text-sm text-danger-700">
        Error al guardar. Por favor, inténtalo de nuevo.
      </p>
    </div>
  </div>
</div>

<!-- Advertencia -->
<div class="bg-warning-50 border-l-4 border-warning-500 p-4 mb-4" role="alert">
  <div class="flex">
    <div class="flex-shrink-0">
      <svg class="h-5 w-5 text-warning-400" viewBox="0 0 20 20" fill="currentColor">
        <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
      </svg>
    </div>
    <div class="ml-3">
      <p class="text-sm text-warning-700">
        Tu ratio de deuda es alto. Revisa tus gastos.
      </p>
    </div>
  </div>
</div>
```

---

## 📐 ESPACIADO Y LAYOUT

### Sistema de Espaciado (Tailwind)

```
p-1  = 0.25rem = 4px
p-2  = 0.5rem  = 8px
p-3  = 0.75rem = 12px
p-4  = 1rem    = 16px   ← Padding estándar de cards
p-6  = 1.5rem  = 24px   ← Padding generoso
p-8  = 2rem    = 32px
p-12 = 3rem    = 48px
```

### Gaps entre Elementos

```
gap-2  = 8px   ← Entre elementos muy relacionados
gap-4  = 16px  ← Gap estándar
gap-6  = 24px  ← Gap generoso
gap-8  = 32px  ← Secciones diferentes
```

### Márgenes

```
mb-2  = 8px   ← Separación entre label e input
mb-4  = 16px  ← Separación entre inputs de formulario
mb-6  = 24px  ← Separación entre secciones de formulario
mb-8  = 32px  ← Separación entre secciones de página
```

---

## 🎭 ICONOS

### Librería: Heroicons

```html
<!-- Incluir desde CDN -->
<script src="https://unpkg.com/heroicons@2.0.18/24/outline/index.js"></script>

<!-- O instalar -->
npm install @heroicons/react
```

### Iconos Comunes

```html
<!-- Dinero/Finanzas -->
<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
        d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
</svg>

<!-- Gráfico/Chart -->
<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
        d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
</svg>

<!-- Tendencia arriba -->
<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
        d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
</svg>
```

---

## ✨ ANIMACIONES

### Transiciones Sutiles

```css
/* Hover en cards */
.card-hover {
  transition: shadow 200ms ease-in-out;
}

/* Botones */
.btn {
  transition: background-color 150ms ease-in-out, 
              transform 100ms ease-in-out;
}
.btn:active {
  transform: scale(0.98);
}

/* Inputs focus */
.input {
  transition: border-color 150ms ease-in-out,
              box-shadow 150ms ease-in-out;
}
```

### Loading Spinner

```html
<div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-gray-300 border-t-primary-600"></div>
```

### Skeleton Loading

```html
<div class="animate-pulse">
  <div class="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
  <div class="h-4 bg-gray-200 rounded w-1/2"></div>
</div>
```

---

## 📱 RESPONSIVIDAD

### Breakpoints (Tailwind)

```
sm: 640px   → Móvil grande / Tablet pequeña
md: 768px   → Tablet
lg: 1024px  → Desktop pequeño
xl: 1280px  → Desktop
2xl: 1536px → Desktop grande
```

### Mobile-First

```html
<!-- Stack en móvil, lado a lado en desktop -->
<div class="flex flex-col md:flex-row gap-4">
  <div class="w-full md:w-1/2">Columna 1</div>
  <div class="w-full md:w-1/2">Columna 2</div>
</div>

<!-- Ocultar en móvil -->
<div class="hidden md:block">Solo en desktop</div>

<!-- Mostrar solo en móvil -->
<div class="block md:hidden">Solo en móvil</div>
```

---

## 🎨 GRÁFICOS

### Librería: Chart.js

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
```

### Configuración de Colores

```javascript
const chartColors = {
  primary: 'rgb(59, 130, 246)',    // primary-500
  success: 'rgb(34, 197, 94)',     // success-500
  danger: 'rgb(239, 68, 68)',      // danger-500
  warning: 'rgb(245, 158, 11)',    // warning-500
  gray: 'rgb(107, 114, 128)',      // gray-500
};

// Configuración base
const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: true,
      position: 'bottom',
      labels: {
        font: {
          family: 'Inter, sans-serif',
          size: 12
        }
      }
    }
  }
};
```

---

## 📦 TEMPLATE BASE

```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Followup{% endblock %}</title>
  
  <!-- Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  
  <!-- TailwindCSS -->
  <link href="{{ url_for('static', filename='css/output.css') }}" rel="stylesheet">
  
  <!-- Alpine.js -->
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
  
  {% block extra_head %}{% endblock %}
</head>
<body class="bg-gray-50 font-sans antialiased">
  
  <!-- Navbar -->
  <nav class="bg-white shadow-sm border-b border-gray-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-16">
        <div class="flex">
          <div class="flex-shrink-0 flex items-center">
            <span class="text-2xl font-bold text-primary-600">Followup</span>
          </div>
        </div>
      </div>
    </div>
  </nav>

  <!-- Main Content -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    
    <!-- Flash Messages -->
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <!-- Usar alertas del design system -->
        {% endfor %}
      {% endif %}
    {% endwith %}
    
    <!-- Page Content -->
    {% block content %}{% endblock %}
  </main>

  <!-- Footer -->
  <footer class="bg-white border-t border-gray-200 mt-12">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <p class="text-center text-sm text-gray-500">
        © 2025 Followup. Todos los derechos reservados.
      </p>
    </div>
  </footer>

  {% block extra_js %}{% endblock %}
</body>
</html>
```

---

## ✅ CHECKLIST DE DISEÑO

Al crear un nuevo componente/página, verificar:

- [ ] Usa la paleta de colores definida
- [ ] Tipografía consistente (Inter)
- [ ] Espaciado correcto (sistema de 4px/8px)
- [ ] Responsivo (mobile-first)
- [ ] Contraste suficiente (accesibilidad)
- [ ] Estados hover/active/disabled
- [ ] Transiciones sutiles
- [ ] Iconos de Heroicons
- [ ] Números con tabular-nums

---

## 🆕 COMPONENTES AVANZADOS (Sprints 2-3)

### 7. Modal de Confirmación (Alpine.js)

```html
<!-- Botón que abre el modal -->
<button @click="$refs.confirmModal.showModal()" 
        class="px-3 py-1 bg-danger-600 text-white text-sm rounded hover:bg-danger-700">
  🗑️ Eliminar
</button>

<!-- Modal -->
<dialog x-ref="confirmModal" class="rounded-lg shadow-xl p-0 backdrop:bg-gray-900 backdrop:bg-opacity-50">
  <div class="bg-white rounded-lg p-6 max-w-md">
    <h3 class="text-lg font-semibold text-gray-900 mb-2">
      Confirmar eliminación
    </h3>
    <p class="text-sm text-gray-600 mb-4">
      ¿Estás seguro de que deseas eliminar esta cuenta? Esta acción es irreversible.
    </p>
    <div class="flex justify-end gap-3">
      <button @click="$refs.confirmModal.close()" 
              class="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50">
        Cancelar
      </button>
      <button @click="$refs.confirmModal.close(); submitDelete()" 
              class="px-4 py-2 bg-danger-600 text-white rounded-lg hover:bg-danger-700">
        Sí, eliminar
      </button>
    </div>
  </div>
</dialog>
```

### 8. Dropdown de Navegación

```html
<!-- En navbar -->
<div class="relative" x-data="{ open: false }">
  <button @click="open = !open" 
          class="flex items-center gap-1 px-3 py-2 text-gray-700 hover:text-gray-900">
    📊 Portfolio
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
    </svg>
  </button>
  
  <div x-show="open" @click.away="open = false"
       class="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1">
    <a href="/portfolio/" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
      Dashboard
    </a>
    <a href="/portfolio/holdings" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
      Posiciones
    </a>
    <a href="/portfolio/transactions" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
      Transacciones
    </a>
  </div>
</div>
```

### 9. Emoji Picker

```html
<div class="mb-4">
  <label class="block text-sm font-medium text-gray-700 mb-1">
    Icono
  </label>
  <div class="flex gap-2 items-center">
    <input type="text" 
           id="icon-input"
           class="w-20 px-3 py-2 border border-gray-300 rounded-lg text-center text-2xl"
           placeholder="💰"
           maxlength="2">
    <div class="flex gap-1">
      <button type="button" 
              onclick="document.getElementById('icon-input').value = '💸'"
              class="px-2 py-1 text-2xl hover:bg-gray-100 rounded">
        💸
      </button>
      <button type="button" 
              onclick="document.getElementById('icon-input').value = '🏦'"
              class="px-2 py-1 text-2xl hover:bg-gray-100 rounded">
        🏦
      </button>
      <!-- Más emojis... -->
    </div>
  </div>
  <p class="text-xs text-gray-500 mt-1">Haz clic en un emoji para usarlo</p>
</div>
```

### 10. Tabla Jerárquica

```html
<table class="min-w-full">
  <thead class="bg-gray-50">
    <tr>
      <th class="px-4 py-3 text-left text-sm font-semibold text-gray-700">Categoría</th>
      <th class="px-4 py-3 text-right text-sm font-semibold text-gray-700">Acciones</th>
    </tr>
  </thead>
  <tbody class="divide-y divide-gray-200">
    <!-- Categoría padre -->
    <tr class="hover:bg-gray-50">
      <td class="px-4 py-3">
        <span class="text-2xl mr-2">🏠</span>
        <span class="font-medium text-gray-900">Hogar</span>
      </td>
      <td class="px-4 py-3 text-right">
        <button class="text-primary-600 hover:text-primary-900">Editar</button>
      </td>
    </tr>
    <!-- Subcategoría (indentada) -->
    <tr class="hover:bg-gray-50 bg-gray-25">
      <td class="px-4 py-3 pl-12">
        <span class="text-gray-400 mr-2">↳</span>
        <span class="text-2xl mr-2">💡</span>
        <span class="text-gray-700">Electricidad</span>
      </td>
      <td class="px-4 py-3 text-right">
        <button class="text-primary-600 hover:text-primary-900">Editar</button>
      </td>
    </tr>
  </tbody>
</table>
```

### 11. Badge de Recurrencia

```html
<!-- Badge simple -->
<span class="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-800">
  📅 Mensual
</span>

<!-- Badge con cantidad -->
<span class="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-purple-100 text-purple-800">
  🔄 Recurrente (12 entradas)
</span>
```

---

## ✅ SPRINT 3 MEJORAS FINALES - OPTIMIZACIÓN Y UX (v3.6.0 - 7 Nov)

**Ancho Unificado 92%**
- ✅ **Consistencia visual total**:
  - Ancho `max-w-[92%]` aplicado a **16 páginas** + navbar
  - Portfolio: dashboard, holdings, transactions, import_csv, asset_registry, currencies, asset_detail, mappings
  - Gastos: list, categories, form, category_form
  - Ingresos: list, categories, form, category_form
  - General: dashboard, index
  - Navbar alineado con el contenido
- ✅ **Mejor aprovechamiento del espacio** sin sacrificar legibilidad
- ✅ **Responsive** en todos los dispositivos

**Columnas Ordenables**
- ✅ **Dashboard + Holdings**: Click en headers para ordenar
- ✅ **Indicadores visuales**: ⇅ (sin orden) → ↑ (asc) → ↓ (desc)
- ✅ **JavaScript puro**: Sin recarga de página
- ✅ **Funciona con números y texto**: Parsing inteligente

**Columna Peso %**
- ✅ **Dashboard**: Nueva columna con % de cada posición
- ✅ **Cálculo automático**: `(valor_holding / total_portfolio) × 100`
- ✅ **Formato europeo**: 12,34%

**Guías Dinámicas CSV**
- ✅ **DeGiro**: Guía naranja con 2 archivos (Estado de Cuenta + Transacciones)
- ✅ **IBKR**: Guía azul con Activity Statement (límite 1 año)
- ✅ **Detección automática**: Según broker seleccionado
- ✅ **Diseño atractivo**: Gradientes, iconos, pasos numerados

**Optimizaciones de Rendimiento**
- ✅ **Timeouts**: 10s/request, 180s máximo total
- ✅ **Paginación**: 100 transacciones por página con controles
- ✅ **Búsqueda en tiempo real**: Debounce 300ms sin submit
- ✅ **Limpieza**: 15 scripts temporales eliminados

**Indicadores**
- ✅ **Última sincronización**: Fecha/hora de última transacción importada
- ✅ **Última actualización de precios**: Ya existente, mantenido

---

## 🚧 SPRINT 4 - MÉTRICAS AVANZADAS (v4.0.0-beta - EN PROGRESO)

### ✅ HITO 1: Métricas Básicas (COMPLETADO - 8 Nov)

**Dashboard Reorganizado**
- ✅ **Sección "Métricas Globales e Históricas"** (primero):
  - Card 🏦 **Valor Total Cuenta** (indigo):
    - Valor principal en grande
    - Desglose detallado: Depósitos, Retiradas, P&L Realizado, P&L No Realizado, Dividendos, Comisiones
    - Indicador de Cash disponible o Apalancamiento (condicional)
    - Tooltip explicativo
  - Card 📊 **P&L Total** (verde/rojo según valor):
    - Valor principal con signo
    - Desglose: P&L Realizado, P&L No Realizado, Dividendos, Comisiones
    - Link a "Ver detalle por asset"
    - Tooltip con fórmula
  - Card 📈 **ROI** (azul/rojo según valor):
    - Porcentaje con signo
    - Desglose de cálculo: Valor Actual Cartera, Retiradas, Depósitos, Retorno absoluto
    - Tooltip con fórmula completa
- ✅ **Sección "Métricas del Portfolio Actual"** (segundo):
  - Card 💰 **Valor Total Cartera** (azul):
    - Valor principal
    - Desglose: Nº Posiciones abiertas, Coste Total
    - Tooltip: "Valor actual de todas las posiciones"
  - Card 📊 **P&L No Realizado** (verde/rojo):
    - Ganancias/pérdidas de posiciones abiertas
    - Tooltip explicativo
  - Card 📉 **Retorno %** (azul/rojo):
    - Porcentaje de retorno actual
    - Tooltip con fórmula
  - Card ⚡ **Dinero Prestado / 💵 Cash en Cuenta** (rojo/cyan dinámico):
    - Título cambia según valor (positivo = apalancamiento, negativo = cash)
    - Desglose: Valor Total Cartera, Dinero usuario (con sub-desglose de componentes)
    - Fórmula visible: `Valor Cartera - Dinero Usuario = Resultado`
    - Ratio de apalancamiento (solo si > 0)
    - Tooltip explicativo
  - Card 📦 **Posiciones** (amarillo):
    - Número de posiciones abiertas
    - Link a holdings
    - Tooltip

**Página P&L by Asset** (`/portfolio/pl-by-asset`)
- ✅ **Búsqueda en tiempo real**: Input con debounce 300ms
- ✅ **Tabla ordenable**: Todas las columnas con flechas ↑↓⇅
- ✅ **Columnas**:
  - Asset (nombre + símbolo en gris)
  - Invertido (rojo)
  - Recuperado (verde)
  - Dividendos (verde)
  - **Nº Dividendos** (verde, al lado de Dividendos) ← NUEVO
  - Comisiones (naranja)
  - P&L Total (verde/rojo según valor, bold)
  - Estado (badge: "En cartera" verde / "Cerrada" gris)
- ✅ **Ordenación numérica correcta**: Formato europeo (1.234,56) convertido antes de ordenar
- ✅ **P&L para posiciones en cartera**: Muestra P&L No Realizado en lugar de solo el coste negativo
- ✅ **Contador de dividendos**: Por cada asset

**Ordenación Numérica Universal**
- ✅ **Dashboard holdings**: JavaScript `sortTableHoldings()` con formato europeo
- ✅ **Holdings page** (`/portfolio/holdings`): JavaScript con formato europeo
- ✅ **PL by Asset**: JavaScript con formato europeo
- ✅ **Transactions** (`/portfolio/transactions`): JavaScript NUEVO
  - Ordenación por fecha (DD/MM/YYYY → YYYY-MM-DD)
  - Ordenación por texto (tipo, activo, cuenta)
  - Ordenación por números (cantidad, precio, total, P&L) con formato europeo
  - Flechas ↑↓⇅ indicando dirección
  - Sin recarga de página

**Holdings Table (Dashboard y Holdings Page)**
- ✅ **Límite eliminado**: Muestra TODAS las posiciones (antes: solo 15)
- ✅ **Columna "Peso %"**: Porcentaje de cada posición en el portfolio total
- ✅ **P&L pre-calculado**: Backend calcula `cost_eur` y `pl_eur` (no filtros en template)
- ✅ **Brokers correctos**: Holdings unificadas muestran todos los brokers correctamente

**Colores y Estilos**
- ✅ **Cards con border-left**: Colores según tipo (indigo, green, blue, red, cyan, yellow)
- ✅ **Tooltips**: Icono ⓘ en gris claro, hover muestra explicación
- ✅ **Desgloses**: Fuente xs, gris, con puntos bullets, border-top separador
- ✅ **Valores dinámicos**: Verde para positivos (+), Rojo para negativos (-)
- ✅ **Badge condicional**: "⚡ Dinero Prestado" rojo o "💵 Cash en Cuenta" cyan

**Fixes Críticos**
- ✅ **P&L Realizado**: Reescrito con `FIFOCalculator` (antes: 5% arbitrario ❌)
- ✅ **P&L Total**: Fórmula corregida `pl_realized + pl_unrealized + dividends - fees`
- ✅ **Leverage**: Incluye P&L Realizado + P&L No Realizado en dinero usuario
- ✅ **Cash disponible**: Solo se suma al total si `leverage < 0`
- ✅ **Logs simplificados**: Cache hits de `currency_service` eliminados

**Archivos Clave**
- `app/services/metrics/basic_metrics.py`: 5 métodos (calculate_leverage, calculate_roi, calculate_pl_realized, calculate_total_pl, calculate_total_account_value)
- `app/routes/portfolio.py`: Pre-cálculo de cost_eur y pl_eur
- `app/templates/portfolio/dashboard.html`: Reorganización + desgloses + tooltips
- `app/templates/portfolio/pl_by_asset.html`: Reordenación + búsqueda + sorting
- `app/templates/portfolio/holdings.html`: Sorting numérico corregido
- `app/templates/portfolio/transactions.html`: Sorting JavaScript completo

---

### ✅ HITO 2: Modified Dietz Method (COMPLETADO - 9 Nov)

**Nueva Card en Dashboard: 💎 Rentabilidad (Modified Dietz)**

**Ubicación**: Sección "Métricas Globales e Históricas" (primera sección)

**Diseño de la Card**:
- ✅ **Border-left**: Morado (`border-purple-500`) si rentabilidad ≥ 0, Rojo (`border-red-500`) si < 0
- ✅ **Título**: "💎 Rentabilidad (Modified Dietz)" con tooltip explicativo
- ✅ **Valor principal** (grande, destacado): Rentabilidad Anualizada en %
  - Color: Morado (`text-purple-600`) si ≥ 0, Rojo (`text-red-600`) si < 0
  - Con signo (+/-)
- ✅ **Subtítulo**: "Anualizada (X años)" en texto pequeño gris
- ✅ **Desglose detallado** (text-xs, gris, border-top separador):
  - 📅 **Año Actual (YTD)**: Rentabilidad % con color dinámico
  - 📊 **Rentabilidad Total**: Rentabilidad % acumulada desde el inicio
  - 💰 **Ganancia absoluta**: Valor en EUR con color dinámico
  - 📆 **Días de inversión**: Número de días (en gris)
- ✅ **Tooltip**: Explicación del método Modified Dietz y ventajas (estándar GIPS, elimina efecto de timing, etc.)

**Valores de Ejemplo (Portfolio Real)**:
```
💎 Rentabilidad (Modified Dietz)
+16,28%
Anualizada (7.85 años)

📅 Año Actual (YTD):     +17,86%
📊 Rentabilidad Total:  +226,94%
💰 Ganancia absoluta: +52.472,87 EUR
📆 2.867 días de inversión
```

**Colores**:
- Border: `border-purple-500` (positivo) / `border-red-500` (negativo)
- Valor principal: `text-purple-600` (positivo) / `text-red-600` (negativo)
- Métricas del desglose:
  - YTD: `text-green-600` (positivo) / `text-red-600` (negativo)
  - Total: `text-green-600` (positivo) / `text-red-600` (negativo)
  - Ganancia: `text-green-600` (positivo) / `text-red-600` (negativo)
  - Días: `text-gray-400` (neutral)

**Tooltip Content**:
```
"Rentabilidad usando Modified Dietz Method (estándar GIPS). 
Elimina el efecto de los flujos de caja (deposits/withdrawals) 
para medir la performance real de tu estrategia."
```

**Arquitectura**:
- ✅ **Backend**: `app/services/metrics/modified_dietz.py` (nuevo)
- ✅ **Integración**: `app/services/metrics/basic_metrics.py` llama a `ModifiedDietzCalculator.get_all_returns()`
- ✅ **Frontend**: `app/templates/portfolio/dashboard.html` (nueva card en "Métricas Globales")

**Fórmula Modified Dietz**:
```
R = (VF - VI - CF) / (VI + Σ(CF_i × W_i))

Donde:
  R  = Rentabilidad del período
  VF = Valor Final del portfolio
  VI = Valor Inicial del portfolio
  CF = Suma de cash flows externos (deposits/withdrawals)
  W_i = Peso temporal del cash flow i = (D - d_i) / D
```

**Cash Flows Externos**:
- ✅ DEPOSIT (depósitos del usuario)
- ✅ WITHDRAWAL (retiradas del usuario)
- ❌ DIVIDEND (son ingresos internos)
- ❌ FEE (son gastos internos)

**Validación**:
- Ganancia Modified Dietz: 52.472,87 EUR
- P&L Total del sistema:   52.562,87 EUR
- **Error: 0,17%** ✅ VALIDADO

---

---

### ✅ Refinements: Performance & UX (COMPLETADO - 10 Nov)

**1. Badge "⚡ Cache"**
- ✅ **Ubicación**: Dashboard, al lado del botón "♻️ Recalcular"
- ✅ **Diseño**:
  - Fuente: `text-sm font-medium`
  - Color: `text-purple-700`
  - Background: `bg-purple-100 border border-purple-300`
  - Padding: `px-3 py-1`
  - Border-radius: `rounded-full`
- ✅ **Condicional**: Solo visible si `metrics._from_cache == True`
- ✅ **Texto**: "⚡ Cache"
- ✅ **Propósito**: Indicador visual de que las métricas se cargaron desde cache (instantáneo)

**2. Botón "♻️ Recalcular"**
- ✅ **Ubicación**: Dashboard, debajo del título "Portfolio"
- ✅ **Diseño**:
  - Formulario POST con CSRF token
  - Botón: `inline-flex items-center px-3 py-1 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition`
  - Icono: ♻️
  - Texto: "Recalcular"
- ✅ **Acción**: POST a `/portfolio/cache/invalidate`
- ✅ **Flash message**: "✅ Cache invalidado. Las métricas se recalcularán en la próxima visita."
- ✅ **Propósito**: Permitir invalidar manualmente el cache de métricas

**3. Botón "🗑️ Eliminar" en Transacciones**
- ✅ **Ubicación**: Tabla de transacciones (`/portfolio/transactions`), columna "Acciones"
- ✅ **Diseño**:
  - Botón: `inline-flex items-center px-3 py-1 bg-red-50 text-red-700 rounded-lg hover:bg-red-100 transition text-sm font-medium`
  - Icono: 🗑️
  - Texto: "Eliminar"
  - Al lado del botón "✏️ Editar" (azul)
- ✅ **Funcionalidad**:
  - `onclick="confirmDelete(txn_id, asset_symbol)"`
  - Modal de confirmación JavaScript: "¿Estás seguro de eliminar esta transacción de [ASSET]? Esta acción no se puede deshacer."
  - Si confirma: POST a `/portfolio/transactions/<id>/delete` con CSRF token
  - Recalcula holdings automáticamente
  - Invalida cache de métricas
- ✅ **Flash message**: "✅ Transacción de [ASSET] eliminada correctamente. Holdings recalculados."

**4. Campo integrado para Yahoo URL**
- ✅ **Ubicación**: Formulario de edición de transacciones, sección "Identificadores de Mercado"
- ✅ **Diseño antiguo** (reemplazado): `prompt()` nativo de JavaScript
- ✅ **Diseño nuevo**:
  - Label: `🌐 URL de Yahoo Finance (opcional)` (`text-xs font-medium text-gray-700`)
  - Input: `type="url"`, placeholder: "https://finance.yahoo.com/quote/AAPL/"
  - Clases: `flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-orange-500 focus:border-transparent`
  - Botón "Enriquecer": `px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 text-sm whitespace-nowrap`
  - Layout: Flex row (input + botón en la misma línea)
- ✅ **Validación**:
  - Si campo vacío: Muestra error "❌ Por favor, pega una URL de Yahoo Finance primero"
  - Si éxito: Limpia el campo automáticamente
- ✅ **Feedback visual**:
  - Botón deshabilitado + texto "⏳ Procesando..." durante la petición
  - Mensaje de éxito con datos actualizados
  - Mensaje de error si falla
- ✅ **Propósito**: Permitir corrección manual de datos de assets usando URL de Yahoo Finance (más intuitivo que prompt nativo)

**5. Meta Tag CSRF Global**
- ✅ **Ubicación**: `app/templates/base/layout.html`, dentro de `<head>`
- ✅ **Código**: `<meta name="csrf-token" content="{{ csrf_token() }}">`
- ✅ **Propósito**: Disponibilizar el CSRF token para todos los fetch JavaScript sin necesidad de incluirlo manualmente en cada página
- ✅ **Uso**: JavaScript puede obtenerlo con `document.querySelector('meta[name="csrf-token"]')?.content`

**6. Mejoras de Rendimiento**
- ✅ **Cache de métricas**: Reducción de 85% en tiempo de carga del dashboard (2-3s → 0.3s)
- ✅ **Tabla `MetricsCache`**: TTL de 24 horas, almacena resultados pre-calculados en JSON
- ✅ **Invalidación inteligente**: Automática en transacciones/precios/imports + manual con botón

**Archivos Modificados**:
- ✅ `app/models/metrics_cache.py` (NUEVO)
- ✅ `app/services/metrics/cache.py` (NUEVO)
- ✅ `app/routes/portfolio.py` (integración cache + ruta delete + ruta invalidate)
- ✅ `app/templates/base/layout.html` (meta CSRF)
- ✅ `app/templates/portfolio/dashboard.html` (badge cache + botón recalcular)
- ✅ `app/templates/portfolio/transaction_form.html` (campo Yahoo URL)
- ✅ `app/templates/portfolio/transactions.html` (botón eliminar + función JS)

---

### ✅ UX Avanzadas: Transacciones Manuales (COMPLETADO - 10 Nov)

**Objetivo**: Mejorar la experiencia de usuario al registrar transacciones BUY/SELL manuales.

**1. Dropdown de Auto-selección en SELL**
- ✅ **Ubicación**: `/portfolio/transactions/new`, Tipo = SELL
- ✅ **Diseño**:
  - Label: "🎯 Seleccionar posición a vender" (`text-sm font-medium text-gray-700`)
  - Select: `w-full px-3 py-2 border border-gray-300 rounded-lg` con opciones dinámicas
  - Opción por defecto: "-- Seleccione un activo a vender --"
  - Formato de opción: `[Broker] Symbol - Name (Quantity)`
  - Ejemplo: `[IBKR] AAPL - Apple Inc (50)` o `[DeGiro] GRF - Grifols SA (1200)`
- ✅ **Filtro por cuenta**:
  - Campo "Cuenta" con opción "-- Todas las cuentas --" por defecto
  - Si se selecciona un broker específico, solo muestra activos de ese broker
- ✅ **Botón "Máximo"**:
  - Ubicación: Al lado del campo "Cantidad"
  - Diseño: `px-3 py-2 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 text-sm`
  - Funcionalidad: Auto-completa la cantidad con el máximo disponible
- ✅ **Auto-completado**: Al seleccionar un activo, rellena: Symbol, ISIN, Currency, Name, Asset Type, Exchange, MIC, Yahoo Suffix, y actualiza "Cuenta" automáticamente

**2. Autocompletado en BUY**
- ✅ **Ubicación**: `/portfolio/transactions/new`, Tipo = BUY
- ✅ **Diseño**:
  - Input de búsqueda en "Symbol o ISIN"
  - Sugerencias aparecen debajo en div: `absolute z-10 w-full mt-1 bg-white border rounded-lg shadow-lg max-h-60 overflow-auto`
  - Cada sugerencia: `px-4 py-2 hover:bg-gray-100 cursor-pointer transition`
  - Formato: `Symbol - Name (ISIN)` en texto normal + gris para ISIN
- ✅ **Funcionalidad**:
  - Búsqueda en tiempo real desde `AssetRegistry` global
  - Tolerante a errores (búsqueda fuzzy)
  - No bloquea la escritura del usuario
  - Auto-fill completo al seleccionar

**3. Soporte para Venta por Quiebra (Precio 0€)**
- ✅ **Validación actualizada**:
  - `price >= 0` (antes: `price > 0`)
  - Validador WTForms: `InputRequired()` + `NumberRange(min=0)`
  - HTML input: `min="0"` explícito
- ✅ **UX sin cambios**: El campo de precio sigue siendo normal, simplemente acepta 0

**4. Botones de Enriquecimiento Inteligentes**
- ✅ **"Enriquecer con OpenFIGI"**:
  - **Modo NEW**: Deshabilitado con `opacity-50 cursor-not-allowed`
  - Tooltip: "Solo disponible al editar transacciones existentes"
  - **Modo EDIT**: Habilitado, color naranja
- ✅ **"Desde URL de Yahoo"**:
  - Siempre habilitado (NEW y EDIT)
  - Input + botón inline (campo ya descrito en Refinements)

**5. Redirección Mejorada**
- ✅ **BUY/SELL → `/portfolio/holdings`** (antes: `/portfolio/transactions`)
- ✅ **Lógica**: `return redirect(url_for('portfolio.holdings_list'))`
- ✅ **Propósito**: Ver inmediatamente el cambio en el portfolio tras la transacción

**6. Modal de Actualización de Precios**
- ✅ **Fix crítico**: Cambiar `data.updated` → `data.success` en JavaScript
- ✅ **Ubicación**: `app/templates/portfolio/dashboard.html`, función `onUpdateComplete()`
- ✅ **Resultado**: Modal ahora muestra correctamente "✅ 29 activos actualizados"

**Archivos Modificados**:
- ✅ `app/routes/portfolio.py` (lógica transacciones + API holdings + redirect)
- ✅ `app/forms/portfolio_forms.py` (validadores `InputRequired`, `NumberRange(min=0)`)
- ✅ `app/templates/portfolio/transaction_form.html` (dropdown SELL, autocompletado BUY, botones)
- ✅ `app/templates/portfolio/dashboard.html` (modal de precios corregido)

---

**Última actualización**: 10 Noviembre 2025
**Próxima revisión**: Después de Sprint 4 - HITO 3

