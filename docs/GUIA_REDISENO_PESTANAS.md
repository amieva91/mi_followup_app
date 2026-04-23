# Guia de rediseno de pestanas (FollowUp)

> **Estado:** plantilla de referencia para nuevas pestañas, ampliaciones y patrones (modales, avisos, listados). **Versión:** 1.1 (abril 2026). Cualquier patrón nuevo debe reflejarse aquí o en la bitácora al final.

Este documento sirve como **referencia única** para mantener consistencia visual y funcional al rediseñar pantallas o crear contenido nuevo dentro de la aplicación.

## Indice

1. [Objetivo](#objetivo) · [Cómo usar este documento](#cómo-usar-este-documento)
2. [Principios de diseno acordados](#principios-de-diseno-acordados)
3. [Plantilla: nueva pestaña o pantalla](#plantilla-nueva-pestaña-o-pantalla)
4. [Avisos, notificaciones y feedback](#avisos-notificaciones-y-feedback)
5. [Reglas de graficas y filtros](#reglas-de-graficas-y-filtros) · [tablas](#reglas-para-tablas-y-listados) · [navegacion](#reglas-para-navegacion)
6. [Paleta visual](#paleta-visual-decision-actual) · [aplicacion de color](#reglas-de-aplicacion-de-color)
7. [Modales (superficie global)](#reglas-para-modales-superficie-global) · [integracion / CRUD](#reglas-para-modales-de-integracionreconciliacion) (legado)
8. [KPI Tendencia (gastos)](#significado-del-kpi-tendencia-en-gastos)
9. [Checklist unificada](#checklist-unificada-usar-en-cada-pestaña-que-se-rediseñe) · [resumen rapido](#checklist-rapido-resumen)
10. [Pestañas ya tocadas](#pestanas-ya-tocadas-iteracion-actual) · [Bitacora](#bitacora-de-cambios-ir-ampliando)

## Cómo usar este documento

- **Nueva pestaña o sección:** seguir [Plantilla: nueva pestaña o pantalla](#plantilla-nueva-pestaña-o-pantalla) y pasar la [checklist](#checklist-unificada-usar-en-cada-pestaña-que-se-rediseñe) antes de dar por cerrada la tarea.
- **Cambio solo de copy o avisos:** revisar [Avisos, notificaciones y feedback](#avisos-notificaciones-y-feedback) (flash vs toast) y no introducir `alert`/`confirm` nativos en flujos de producto.
- **Nuevo patrón visual** (p. ej. componente, clase CSS, variante de modal): documentar en **Bitácora** y, si es transversal, añadir viñeta bajo **Principios** o la sección de modales / feedback correspondiente.
- **Coherencia con código:** la superficie de modal global es `.followup-modal-surface` (definida en `app/templates/base/layout.html`); no duplicar “superficies de modal” solo bajo un `#id` de página si el nodo del modal vive **fuera** de ese contenedor (los estilos no aplicarían).

## Objetivo

- Unificar la experiencia visual (look & feel moderno, limpio y consistente).
- Mantener jerarquia clara de informacion (KPI -> grafica -> tabla/acciones).
- Evitar regresiones de usabilidad (interacciones, filtros, modales, formularios).
- Documentar decisiones para que se apliquen en nuevas pantanas.

Este documento concentra **principios, paleta, checklist y bitácora**: las reglas concretas (títulos `emoji + título`, `portfolio-card`, `pf-info`, superficies `chart-surface*`, `evo-toggle`, modales con overlay `bg-black/55`, toasts, tablas con cabecera slate, botones `teal` / `slate`, etc.) deben alinearse aquí al rediseñar cualquier pestaña. Si añades un patrón nuevo, amplía una viñeta bajo **Principios** o **Bitácora** para que el inventario siga completo.

## Principios de diseno acordados

- Estilo general `3D suave`: superficies elevadas, sombras sutiles, gradientes ligeros.
- Titulos homogeneos: formato `emoji + titulo`, alineados a la izquierda.
- Contenedores en tarjetas reutilizables:
  - fondo degradado suave,
  - borde sutil,
  - radio generoso,
  - sombra exterior + brillo interior.
- KPIs con borde lateral de color y lectura rapida.
- Etiquetas KPI en formato frase (sin `UPPERCASE` forzado), con jerarquia como referencia de `Deudas` (`text-sm`, `font-medium`, `text-gray-600`).
- Tonalidades KPI recomendadas (agradables y consistentes):
  - negativos: gama `rose` (`rose-400/500/600` + texto `rose-700/800`),
  - positivos: gama `emerald` (`emerald-400/500/600` + texto `emerald-700/800`),
  - neutros/auxiliares: `slate`,
  - tendencia/info: `sky`.
- Formularios mas realistas:
  - ancho acotado (`max-w-5xl` en formularios largos),
  - columnas equilibradas,
  - grupos visuales por bloques,
  - botones de accion prominentes.
- Modales integrados al sistema visual (no aspecto browser por defecto).

## Plantilla: nueva pestaña o pantalla

Checklist mínima al **añadir** una ruta o pantalla (no sustituye la [checklist detallada](#checklist-unificada-usar-en-cada-pestaña-que-se-rediseñe)):

1. **Envoltorio de página**  
   Contenedor con márgenes coherentes con el módulo (`max-w-[92%]` o `container` / `max-w-5xl` en formularios largos, según corresponda al resto del sitio).
2. **Cabecera**  
   `emoji + título` (mismo peso que pestañas hermanas del módulo), subtítulo opcional `text-slate-600` / `text-sm` o `text-base`.
3. **Bloque de KPIs (si aplica)**  
   Filas de tarjetas con `border-l-4` semántico, gradiente y sombra según [paleta y tarjetas](#reglas-de-aplicacion-de-color). Evitar reglas genéricas que pisen el borde izquierdo (caso `portfolio-metric-card` / `:not(.portfolio-metric-card)` en dashboard).
4. **Filtros y gráficos**  
   Criterios en [Reglas de gráficas y filtros](#reglas-de-graficas-y-filtros) (leyendas, `pf-info`, posición de filtros).
5. **Tabla o listado**  
   [Reglas para tablas](#reglas-para-tablas-y-listados), `overflow-x-auto`, acciones con prioridad cromática (teal = principal, `sky` = secundario, `amber` = advertencia, `rose` = destructivo).
6. **Formularios**  
   `rounded-xl`, `focus:ring-teal-500`, bloque de acciones `flex-col sm:flex-row`, `w-full` en móvil; **Volver** con `history.back()` + `href` de respaldo si aplica ([navegación](#reglas-para-navegacion)).
7. **Modales**  
   Overlay `bg-black/55`, panel con [`.followup-modal-surface`](#reglas-para-modales-superficie-global); cierre con cancelar, clic fuera y (opcional) Escape.
8. **Feedback**  
   Mensajes vía [flash o toast](#avisos-notificaciones-y-feedback), no `alert` para flujos de producto.
9. **Vacío y carga**  
   Empty state con mensaje + CTA `teal`; estados de error discretos (`rose` suave), no bloquear la cabecera con párrafos metodológicos largos (usar `i` + modal).
10. **Cierre**  
    Pasar [checklist unificada](#checklist-unificada-usar-en-cada-pestaña-que-se-rediseñe) y añadir la ruta en [Pestañas ya tocadas](#pestanas-ya-tocadas-iteracion-actual) cuando se mergee.

**Notificaciones “de producto”** (recordatorios, difusiones, novedades): si no son flash de acción inmediata, preferir toasts o un bloque fijo bajo la barra con la misma familia cromática (no mezclar cinta neón aislada); documentar en bitácora si se introduce un canal nuevo (email, push, etc.).

## Avisos, notificaciones y feedback

| Mecanismo | Uso recomendado | Dónde / notas |
|-----------|-----------------|----------------|
| **Flash de Flask** (`get_flashed_messages`) | Resultado de POST (guardado, error de validación, borrado, logout informativo) | `base/layout.html`: contenedor `js-flash-message`; en portada (`main.index`) flotante `fixed` y z-index alto; en resto, bajo ancho de contenido. Categorías: `success` (esmeralda), `error` (rose), `warning` (ámbar), otras/`info` (recuadro con borde y **banda interior clara** para mensajes neutros). Cierre manual con ×; auto-cierre con transición. |
| **Toast in-page (JS)** | Acciones en la misma pantalla sin recargar (API OK/KO, copiar, preview) | Patrón en watchlist: `#toastContainer` fijo `top-4 right-4`, `z-[70]`, cápsula con borde sutil; en otras plantillas (p. ej. ficha de activo) reutilizar el mismo criterio de posición y z-index. Evitar duplicar lógica con estilos completamente distintos. |
| **Banners bajo el nav** | Poco frecuente; anuncios globales | Misma paleta B; no tapar el contenido principal en móvil. |

- No usar `alert()` / `confirm()` del navegador para flujos que el usuario deba completar con contexto: sustituir por **modal** con [superficie global](#reglas-para-modales-superficie-global).
- Tras acciones críticas, un flash **una sola frase** + icono/emoji coherente con el tono; evitar muros de texto en el flash.
- **Accesibilidad mínima:** `role`/`aria-modal` en modales; botones con nombre visible; contraste de texto en toasts (texto claro sobre fondo `emerald/rose/slate` ya usados en el código).

## Reglas de graficas y filtros

- Quitar leyendas antiguas por defecto de Chart.js cuando exista filtro custom.
- Mostrar filtros/toggles custom **debajo de la grafica** (nunca encima).
- **Una sola serie** por grafico: desactivar leyenda Chart.js (no aporta y duplica ruido visual).
- **Selector de frecuencia / periodo** (diaria, semanal, … o 1A/3A/…): usar el **mismo patron segmentado** que en **Evolucion del Patrimonio** del dashboard principal (`contenedor bg-gray-100 rounded-lg p-1`, boton activo `bg-white shadow text-indigo-600`, inactivo `text-gray-600`).
- **Varias series** en un mismo lienzo (p. ej. valor real + capital): toggles estilo `evo-toggle` (pastillas con check, como *Mostrar* bajo Evolucion del Patrimonio o tipo en posiciones de cartera), nunca leyenda superior por defecto.
- Textos explicativos largos del tipo *«calculada segun Modified Dietz (GIPS)»* **no** van como parrafo bajo el titulo: van en el icono **i** (`pf-info`) con modal o panel breve, para no recargar la jerarquia visual.
- Tooltips claros con formato monetario local (`es-ES`).
- Escalas legibles y coherentes con el dato representado.
- En pestañas redisenadas, mantener acabado visual `3D suave` en las graficas (superficie con relieve sutil, sin saturar el color de fondo), alineada a la familia de tarjetas (degradado teal-slate, sin parches blancos sueltos en el contenedor del canvas).
- **Gráficos de reparto** (doughnut/pie, varias porciones en un solo lienzo): usar **paleta amplia y distinguible** (tonos agradables, armónicos entre sí) para leer la leyenda; si se repite el patrón de color al superar *N* porciones, explicar en el modal **i** que el color **no** implica prioridad, solo distinción. No usar una franja casi monocromática si dificulta asociar leyenda ↔ porción.

## Reglas para tablas y listados

- Filas con fondo suave y hover visible.
- Cabeceras compactas, legibles y consistentes entre pestañas.
- Empty state amigable y accionable (CTA directo).
- Acciones con iconos y prioridad visual clara.

## Reglas para navegacion

- Orden de desplegables segun prioridad de flujo:
  - primero `Ingresos`,
  - despues `Gastos`.
- Mantener nomenclatura y accesos consistentes entre modulos.
- En formularios a los que se accede desde varias rutas (p. ej. **nueva transacción** en portfolio), el enlace de **«Volver»** debe comportarse como **vuelta atrás** (`history.back()`), no como destino fijo a un solo listado. Conservar `href` como **fallback** (p. ej. listado de transacciones) si no hay historial o por accesibilidad.

## Paleta visual (decision actual)

- Variante elegida para navegacion superior y pantallas de acceso: **B**.
- Base navbar/top bars:
  - gradiente principal: `#2f4858 -> #3f5f73`,
  - hover de enlaces: tonos claros `teal/slate` (sin saturacion fuerte),
  - badge/acento: `emerald` suave.
- Principio de color:
  - priorizar tonos frios desaturados (teal-slate) para reducir fatiga visual,
  - reservar colores intensos para estados semanticos (error, warning, exito),
  - evitar fondos excesivamente electricos en barras y cabeceras.

## Reglas de aplicacion de color

- Barra superior global: siempre paleta B.
- Portada + login/registro + recuperacion de clave: coherentes con la misma familia cromatica.
- Cabecera principal del dashboard (Patrimonio Neto Total): usar gradiente de familia B.
- Tarjetas y recuadros (fondo estandar recomendado):
  - `background: linear-gradient(145deg, #f8fbfc 0%, #f1f7f8 100%)`,
  - `border: 1px solid rgba(63, 95, 115, 0.14)`,
  - version para bloques internos: `background: linear-gradient(145deg, rgba(248,251,252,0.96), rgba(241,247,248,0.9))` y `border: 1px solid rgba(63, 95, 115, 0.13)`.
- Botones primarios de formularios en pestañas redisenadas:
  - preferencia `teal-600/700`,
  - focus ring en `teal-500`.
- Graficas/toggles:
  - filtros bajo grafica,
  - color activo coherente con la paleta de cada modulo (evitar mezcla aleatoria de acentos).

## Reglas para modales (superficie global)

- Clase reutilizable **`.followup-modal-surface`**: gradiente, borde y sombra alineados a la guía (misma lógica que el panel de modales de watchlist; definición en `layout.html`).
- El **nodo** del modal (overlay a pantalla completa) debe ser hijo de `body` o de un contenedor que no tenga `overflow: hidden` que recorte; el **panel** interior lleva además `relative z-10` frente al overlay para evitar solapamientos con la tabla.
- **Anti-patrón:** no definir la superficie del modal **solo** con selectores del tipo `#mi-pestaña .mi-modal-surface` si el HTML del modal está **renderizado fuera** del `#mi-pestaña` (p. ej. al final de la plantilla). Los estilos no se aplican y el modal parece “transparente” o con botones sueltos; usar la clase **global** citada o duplicar la definición a nivel de utilidad, no bajo un id de página aislado.
- Contenido: título; mensaje de confirmación o cuerpo en caja con fondo claro legible; acciones con `portfolio-touch-btn` o equivalente, primario + secundario; icono opcional en círculo (como en confirmar borrado de transacción).
- Watchlist mantiene nombres propios de clase en su plantilla por histórico; el **criterio visual** es el mismo que `.followup-modal-surface`.

## Reglas para modales de integracion/reconciliacion

(Integración, reconciliación, importación: además de lo anterior.)

- Modal con estilo del sistema (borde + gradiente + sombra profunda).
- Titulo explicito y contexto del impacto.
- CTA principal destacado y boton secundario neutro.
- Cierre por click fuera + boton cancelar.
- Aplicar este patron tambien a modales CRUD de listas (eliminar, terminar contrato, alcance de recurrencia, creacion rapida de categoria).

## Significado del KPI "Tendencia" en gastos

- Se compara el ultimo mes contra la media de 12 meses.
- Umbral:
  - `↑` si el ultimo mes > media * 1.05,
  - `↓` si el ultimo mes < media * 0.95,
  - `≈` en rango intermedio.
- En gastos, `↑` implica que el ultimo mes fue superior a la media del periodo.

## Checklist unificada (usar en cada pestaña que se rediseñe)

Marcar cada ítem al cerrar el redisño. Sirve para homogeneizar con el resto del producto (Deudas, Gastos, Ingresos, Bancos, Portfolio, dashboard, auth).

### Estructura y jerarquía
- [ ] Título principal: `emoji + título`, peso y tamaño coherentes con otras pestañas del mismo módulo.
- [ ] Subtítulos y textos de ayuda (`text-sm` / `text-xs`, `text-slate-500/600`) sin ruido innecesario.
- [ ] Contenedor de página: `max-w-*` y márgenes laterales alineados con el resto del sitio.

### Superficies y tarjetas (3D suave)
- [ ] Tarjetas/KPIs: gradiente suave, borde sutil, radio generoso, sombra + brillo interior según reglas de paleta B.
- [ ] KPIs con borde lateral de color semántico (emerald/rose/slate/sky) sin que el CSS genérico pise `border-l-*`.
- [ ] Gráficas: superficie tipo `chart-surface` o equivalente; sin saturar el fondo.

### Color y tipografía
- [ ] Paleta B (teal-slate) en barras, primarios y fondos; reservar rojo/verde fuerte solo a semántica (P&L, error/éxito).
- [ ] Importes y porcentajes: `tabular-nums` donde aplique; formato monetario EU coherente.

### Tablas y listados
- [ ] Cabecera `slate`, cuerpo con hover de fila; `overflow-x-auto` en contenedor.
- [ ] Columna de acciones con ancho estable; en móvil, iconos o textos según reglas responsive del documento.
- [ ] Estados vacíos con mensaje claro y CTA (teal).

### Formularios
- [ ] Inputs `rounded-xl`, `border-slate-300`, `focus:ring-teal-500`.
- [ ] Acciones: primario `teal-600`, secundario `slate-200/300`; bloque `flex-col sm:flex-row` y botones `w-full sm:w-auto` en móvil.

### Botones, iconos de ayuda y feedback táctil
- [ ] Botones con `portfolio-touch-btn` / `bank-touch-btn` / `modal-touch-btn` o patrón equivalente del módulo.
- [ ] Icono de información tipo Bancos: círculo `teal` con `i` (clase `pf-info` en Portfolio, o equivalente documentado).
- [ ] Estado `:active` visible en controles principales.

### Modales y ventanas emergentes
- [ ] Overlay `bg-black/55` o similar; panel con **`.followup-modal-surface`** (o equivalente documentado), no solo CSS scoped bajo `#id` si el modal está fuera de ese nodo.
- [ ] CTA primario y secundario distinguibles; cierre con botón, Escape y clic fuera si aplica.
- [ ] Sin `alert`/`confirm` nativos para flujos de producto (sustituir por modales del sistema).

### Avisos y feedback
- [ ] Resultados de POST: flash con categoría correcta (`success` / `error` / `warning` / info); en portada, flotante según layout.
- [ ] Toasts en pantalla (si aplica): contenedor fijo coherente (`z-[70]` aprox.) y estilo alineado a watchlist, sin cajas ajenas a la paleta B.
- [ ] No depender de `alert` para mensajes que deban leerse con contexto.

### Comportamiento y datos
- [ ] Desplegables filas de KPIs sincronizados si el diseño lo pide (una fila = un estado compartido).
- [ ] Listas largas: compactar o modal con scroll en lugar de páginas interminables.

### Gráficos
- [ ] Chart.js: leyenda duplicada eliminada si hay filtro custom; tooltips legibles.
- [ ] “3D fuerte” = relieve simulado (gradiente en barras + bordes/highlight), no motor 3D real, salvo que se acuerde lo contrario.

### Otros dispositivos y pruebas
- [ ] Revisión en ancho intermedio y móvil (tablas, modales a pantalla completa abajo).
- [ ] **Validación visual**: contraste, solapamientos, scroll horizontal no bloqueante.
- [ ] **Regresión funcional**: envíos de formularios, ordenación de tablas, enlaces, modales que escriben en API.

## Checklist rapido (resumen)

- [ ] Título `emoji + título`, KPIs y tablas alineados a esta guía.
- [ ] Gráfica con filtros debajo; modales (`.followup-modal-surface`) y formularios al patrón del sistema; flash/toasts coherentes.
- [ ] Revisado en desktop y en resolución intermedia/móvil.
- [ ] Si es pantalla **nueva**: añadida a [Pestañas ya tocadas](#pestanas-ya-tocadas-iteracion-actual) y, si aplica, bitácora con el patrón introducido.

## Pestanas ya tocadas (iteracion actual)

- Deudas dashboard (`/debts`)
- Deudas nuevo/editar (`/debts/new`, `/debts/<id>/edit`)
- Gastos listado (`/expenses`)
- Gastos categorias (`/expenses/categories`)
- Gastos categoria nueva/editar (`/expenses/categories/new`, edit)
- Gastos nuevo/editar (`/expenses/new`, edit)
- Ingresos listado (`/incomes`)
- Ingresos categorias (`/incomes/categories`)
- Ingresos categoria nueva/editar (`/incomes/categories/new`, edit)
- Ingresos nuevo/editar (`/incomes/new`, edit)
- Bancos dashboard (`/banks`)
- Bancos nuevo/editar (`/banks/new`, edit)
- Portfolio dashboard (`/portfolio`)
- Portfolio performance (`/portfolio/performance`)
- Portfolio dividendos (`/portfolio/dividendos`)
- Portfolio index comparison (`/portfolio/index-comparison`)
- Portfolio diversificacion (`/portfolio/diversificacion`)
- Portfolio currencies (`/portfolio/currencies`)
- Portfolio cartera / holdings (`/portfolio/holdings`)
- Portfolio watchlist (`/portfolio/watchlist`)
- Portfolio ficha de activo (`/portfolio/asset/<id>`)
- Portfolio P&L por activo (`/portfolio/pl-by-asset`)
- Planificación de gastos (`/planificacion/`)
- Simulador vivienda (`/planificacion/vivienda`)

## Bitacora de cambios (ir ampliando)

- Se fija criterio de filtros de graficas debajo del lienzo.
- Se unifica estilo 3D en cards principales de gastos y deudas.
- Se adapta modal "Integrar" al sistema visual.
- Se documenta semantica de KPI "Tendencia" para evitar ambiguedad.
- Se fija oficialmente la variante de color B y su regla de aplicacion transversal.
- Se estandariza el fondo de tarjetas/recuadros para gastos y deudas con gradiente suave teal-slate.
- Se unifica tipografia/jerarquia de etiquetas KPI de gastos e ingresos con el estilo base de deudas.
- Se redisenan modales de ingresos, gastos y deudas con plantilla visual unificada (gradiente, borde suave, CTA principal y secundario consistentes).
- Ajuste fino cross-modulo: headers y botones primarios/acciones de paginacion en ingresos, gastos y deudas alineados al mismo patron visual (teal primario + slate secundario + radios/sombras consistentes).
- Estandar de acciones en tablas: `Editar` en `teal`, acciones secundarias de flujo (ej. `Reestructurar`) en `sky`, advertencias en `amber` y destructivas en `rose/red`.
- Estandar de micro-interaccion en acciones de tabla: mismo peso (`font-semibold`), espaciado homogeneo entre icono/texto y estado hover con ligera elevacion visual.
- Estandar de layout en tablas redisenadas: fijar ancho consistente de la columna `Acciones` para evitar saltos visuales entre filas y modulos.
- Regla responsive para tablas: en anchos reducidos, mantener `overflow-x-auto` en contenedor y reducir ancho minimo de `Acciones` para conservar legibilidad sin romper layout.
- Ajuste movil recomendado (<=640px): compactar padding horizontal de celdas (`th/td`) en tablas de listados para mejorar densidad y lectura.
- Ajuste movil extra (<=480px): priorizar iconos en acciones de tabla (ocultar texto en acciones largas con tooltip) para preservar espacio util.
- En dispositivos tactiles (`pointer: coarse`), ampliar el area clicable de acciones de tabla para mejorar precision de toque.
- Añadir estado `:active` visible en acciones tactiles (ligera escala/contraste) para confirmar interacción al pulsar.
- Extender el estado tactil `:active` a botones de modales (confirmar/cancelar/crear) para una respuesta uniforme en mobile.
- Aplicar el mismo patron tactil `:active` en botones de formularios principales (guardar/crear/actualizar/cancelar) para coherencia global.
- Aplicar el patron tactil tambien en CTAs de dashboard/onboarding (hitos, popup, empty state y FAB) para continuidad completa de interacción.
- La tarjeta de bienvenida del dashboard y modales de primera visita (ej. Bancos) deben usar la misma superficie 3D suave y paleta teal-slate que el resto del sistema.
- Rediseno de `Bancos` completado: tarjetas de registro/total/evolucion/listado y empty state migradas a superficie 3D suave, con acciones primarias en `teal` y foco de inputs/selects unificado.
- Formularios de `Bancos` (`new/edit`) alineados al patron de formularios de modulos (`card + sections + CTA tactiles`) manteniendo dropdown visual para color con muestras.
- Ajuste de `Bancos` (`new/edit`): cabecera compacta y titulo centrado visualmente sobre la tarjeta para reforzar eje unico de lectura en desktop.
- Modal `Eliminar banco` estandarizado al patron CRUD de `Gastos/Ingresos` (overlay, panel 3D, CTA destructiva principal y cancelar secundario full-width).
- Ajuste de coherencia cross-modulo en formularios: se elimina `← Volver` en `Bancos new/edit` y la cabecera pasa al mismo formato simple `emoji + titulo` usado en `Gastos/Ingresos`.
- Ajuste responsive en `Bancos new/edit`: cabecera `text-2xl -> sm:text-3xl`, separaciones compactas y bloque de acciones en columna en movil (`w-full`) con retorno a fila en `sm+`.
- Regla responsive unificada en formularios (`Ingresos`, `Gastos`, `Deudas`, `Bancos`): bloque de acciones `flex-col sm:flex-row` y botones `w-full sm:w-auto` para mantener touch targets amplios en movil y layout compacto en desktop.
- Consistencia de secundarios en formularios: boton `Cancelar` normalizado a paleta `slate` (`bg-slate-200/hover:bg-slate-300/text-slate-700`) en `Gastos` y `Deudas`, alineado con `Ingresos/Bancos`.
- Rediseño de `Portfolio` (dashboard/performance/dividendos/index-comparison/diversificacion/currencies): cards y contenedores migrados a superficie 3D suave, headers en formato `emoji + titulo`, tablas/chart-surface homogeneizadas y botones primarios/secundarios alineados a paleta teal-slate.
- Modales y flujos de soporte en portfolio (actualización de precios + fix Yahoo URL) alineados al patrón visual CRUD/modales del sistema con overlay oscuro, panel 3D y acciones táctiles consistentes.
- Ajuste fino en `Portfolio dashboard`: KPIs de "Métricas Globales e Históricas" y sus desgloses internos pasan a superficie 3D más marcada para evitar apariencia de fondo blanco plano.
- `Portfolio dashboard` KPIs (globales y "Portfolio Actual"): el selector CSS de tarjetas blancas (`border` en shorthand) pisaba el `border-l-4` de Tailwind; se acota la regla a `:not(.portfolio-metric-card)` y en `.portfolio-metric-card` solo bordes superior/derecho/inferior para conservar el rizado lateral de color.
- Ficha de activo del portfolio: superficie 3D en KPIs y bloque de pestañas, acentos `teal/slate`, tablas y modal de plantillas de informes alineados al resto de `Portfolio`; informes Markdown con cabeceras/tablas en familia teal en lugar de azul intenso.
- `Portfolio` dashboard: desglose de KPIs por fila sincronizado (Alpine `globalMetricsOpen` / `currentMetricsOpen`); cuatro métricas “Portfolio actual” en una fila en `xl`; icono `i` unificado (`pf-info` como en Bancos); posiciones en cartera con cabecera y filas más legibles (banda lateral por P&L); rentabilidades año a año compactas + modal con scroll para años antiguos; gráfico de barras con gradiente y trazo de relieve (3D simulado); checklist ampliada en esta guía.
- `Portfolio` P&L por activo (`/portfolio/pl-by-asset`): redisño a `portfolio-card`, tabla slate/teal, tipografía y KPIs resumen alineados a la guía.
- Formulario nueva/editar transacción (`/portfolio/transactions/new` y edición): contenedor `max-w-5xl`, tarjeta principal y secciones internas con gradiente paleta B, inputs `rounded-xl` y anillo de foco `teal`, bloque venta con acento lateral teal, botones de enriquecimiento y envío alineados a primario teal / secundario slate; sin cambiar IDs/names usados por JS.
- `Portfolio` análisis de performance (`/portfolio/performance`): cabecera y badges de sync en familia teal-slate, lienzo de cada gráfico con `chart-surface` coherente con el dashboard, pie informativo en rail degradado teal/slate y mensaje de error en `rose` suave.
- `Portfolio` diversificación: doughnut con paleta multicolor armónica (leyenda legible), superficie `chart-surface-divers`, modales `pf-info` por gráfico.
- `Portfolio` holdings: KPIs en rizado semántico (sky/teal/rose/emerald), tabla con envoltorio tipo listados portfolio, enlace a ficha en teal, modal corregir Yahoo al patrón de modales (sin `alert` nativo; toast embebido), primarios `teal`.
- `Portfolio` watchlist: cabecera y tabla alineados a `portfolio-card` + `watchlist-thead`, modales (ajustes, añadir, informe, editar, confirmar) con `pf-modal` / overlay unificado, tabs y CTAs en `teal`, toasts en `emerald/rose/slate`, cierre con scroll bloqueado en `body` al abrir modal.
- `Watchlist` modales: los paneles están **fuera** del wrapper `#portfolio-watch`; la clase de superficie debe ser **global** (p. ej. `watchlist-modal-surface`) para que el fondo opaco y el gradiente se apliquen (evitar panel “transparente”).
- Módulos **Crypto**, **Metales** e **Inmuebles** (listado, detalle, formularios, modales de precios / eliminar): superficies 3D suaves, tablas con cabecera slate, KPIs con rizado semántico, botones `teal`/`slate`, modales con `bg-black/55` y panel con `re-modal-panel` / `app-modal-panel` + `background-color` de respaldo.
- Formulario transacción: **Volver** con `history.back()` + fallback; performance: frecuencia con segmentos como «Evolución del Patrimonio», toggles `evo-toggle` para valor real / capital invertido, leyendas Chart desactivadas en series únicas, textos metodológicos en `pf-info`; **Mi Portfolio** — bloque rentabilidades año a año: tarjeta y contenedor del gráfico de barras con degradado teal-slate (sin caja blanca suelta).
- **Guía v1.1 (cierre plantilla):** índice navegable, sección *Cómo usar*, plantilla numerada para nuevas pestañas, tabla de **avisos / flash / toasts**, reglas explícitas de **modales globales** (`.followup-modal-surface`, anti-patrón CSS solo bajo `#id`); checklist ampliada con feedback y cierre con ruta en “Pestañas ya tocadas”.
- **Planificación** (`/planificacion/`) y **simulador vivienda** (`/planificacion/vivienda`): cabecera `emoji + título`, tarjetas 3D locales (`sp-plan-card` / `mg-plan-card`), inputs `rounded-xl` + foco `teal`, tablas con cabecera tipo slate, KPIs con `border-l-4` semántico, primarios `teal` y secundarios `slate`, modales con overlay `bg-black/55` y panel **`.followup-modal-surface`**.
