# Guia de rediseno de pestanas (FollowUp)

Este documento sirve como referencia viva para mantener consistencia visual y funcional mientras se redisenan las pestanas del producto.

## Objetivo

- Unificar la experiencia visual (look & feel moderno, limpio y consistente).
- Mantener jerarquia clara de informacion (KPI -> grafica -> tabla/acciones).
- Evitar regresiones de usabilidad (interacciones, filtros, modales, formularios).
- Documentar decisiones para que se apliquen en nuevas pantanas.

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

## Reglas de graficas y filtros

- Quitar leyendas antiguas por defecto de Chart.js cuando exista filtro custom.
- Mostrar filtros/toggles custom **debajo de la grafica** (nunca encima).
- Tooltips claros con formato monetario local (`es-ES`).
- Escalas legibles y coherentes con el dato representado.
- En pestañas redisenadas, mantener acabado visual `3D suave` en las graficas (superficie con relieve sutil, sin saturar el color de fondo).

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

## Reglas para modales de integracion/reconciliacion

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
- [ ] Overlay `bg-black/55` o similar; panel con gradiente 3D, `rounded-2xl`, sombra profunda.
- [ ] CTA primario y secundario distinguibles; cierre con botón, Escape y clic fuera si aplica.
- [ ] Sin `alert`/`confirm` nativos para flujos de producto (sustituir por modales del sistema).

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
- [ ] Gráfica con filtros debajo; modales y formularios al patrón del sistema.
- [ ] Revisado en desktop y en resolución intermedia/móvil.

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
- Portfolio ficha de activo (`/portfolio/asset/<id>`)
- Portfolio P&L por activo (`/portfolio/pl-by-asset`)

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
