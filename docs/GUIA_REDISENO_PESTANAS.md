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

## Checklist rapido antes de dar por cerrada una pestana

- [ ] Titulo en formato `emoji + titulo`.
- [ ] KPIs con estilo unificado.
- [ ] Grafica con filtros custom debajo.
- [ ] Leyenda antigua eliminada si aplica.
- [ ] Tabla/lista con estilo unificado y hover.
- [ ] Empty state con CTA.
- [ ] Formularios compactos y proporcionados.
- [ ] Modales integrados visualmente.
- [ ] Revisado en desktop y en resolucion intermedia.

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
