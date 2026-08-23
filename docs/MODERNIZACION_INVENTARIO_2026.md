# NexuStock — arquitectura moderna de inventario 2026

## Principio del producto

NexuStock está diseñado para que una farmacia, botillería, minimarket, ferretería,
librería o bodega pueda comenzar con un catálogo simple y crecer sin cambiar de
plataforma. La interfaz prioriza consulta visual, búsqueda inmediata, escaneo,
alertas accionables y trazabilidad.

## Estructura funcional

1. **Catálogo visual:** productos, imágenes, categorías, marcas, unidades,
   presentaciones, proveedor principal y datos tributarios.
2. **Consulta móvil:** cámara, lector USB o ingreso manual de códigos.
3. **Inventario por ubicación:** empresa, sucursal y bodega con stock físico,
   reservado y disponible.
4. **Operación:** entradas, salidas, ajustes, compras, ventas, transferencias,
   picking, packing y despacho.
5. **Control:** lotes, vencimientos, seriales, permisos, auditoría y alertas.
6. **Decisión:** valorización, rotación, sobrestock, riesgo de agotamiento,
   recomendaciones de compra y asistente IA.
7. **Plataforma SaaS:** planes, límites, pagos confirmados, conciliación,
   multiempresa y Super Administración separada.

## Decisiones de seguridad

- Una consulta de catálogo siempre se limita a `empresa_id`.
- La ubicación activa se valida en servidor.
- El escaneo nunca ejecuta automáticamente un movimiento.
- La cámara se abre sólo por acción explícita y se detiene al cerrar el diálogo.
- Existe una alternativa manual para navegadores sin detección nativa.
- Los permisos de lectura y escritura continúan evaluándose en servidor.

## Criterios de aceptación

- La interfaz funciona desde 320 px de ancho.
- Los controles táctiles conservan un alto mínimo de 44 px en móvil.
- La navegación por teclado mantiene indicadores de foco visibles.
- La reducción de movimiento del sistema operativo es respetada.
- El catálogo puede consultarse por nombre, SKU o código de barras.
- Las categorías visibles se obtienen únicamente del catálogo autorizado.
- La operación existente y el panel Super Admin no cambian de ámbito.

## Evolución recomendada

La próxima etapa comercial debe priorizar pruebas con negocios reales, telemetría
de tareas sin contenido sensible, importación asistida inicial, etiquetas imprimibles,
modo conteo cíclico y una aplicación instalable. Cada función debe incorporarse con
migración, permisos, auditoría y pruebas antes de habilitarse en producción.
