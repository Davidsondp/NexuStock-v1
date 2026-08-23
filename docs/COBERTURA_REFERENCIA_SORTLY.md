# Cobertura funcional de referencia Sortly

Esta matriz compara capacidades públicas, no código ni arquitectura privada de terceros.
NexuStock conserva su modelo más estricto de empresa, sucursal, bodega, permisos y auditoría.

| Capacidad de referencia | Implementación NexuStock | Estado |
|---|---|---|
| Artículos y detalles | Productos, categorías, marca, costos, precios e impuestos | Disponible |
| Fotografías | Galería y principal por producto | Disponible |
| Importación | CSV, XLSX y tablas PDF con vista previa | Disponible |
| Código de barras y QR | Cámara, lector USB, consulta y etiquetas QR | Disponible |
| Etiquetas | Formato imprimible 62 × 30 mm sin servicios externos | Disponible |
| Campos personalizados | Hasta 20 pares simples por producto, validados y multiempresa | Disponible |
| Carpetas y ubicaciones | Categorías visuales más sucursal, bodega y ubicación estructurada | Disponible con modelo NexuStock |
| Check-in/check-out | Entradas, salidas, devoluciones, transferencias y auditoría | Disponible con modelo NexuStock |
| Stock bajo | Alertas y reportes de reposición | Disponible |
| Alertas por fecha | Lotes, vencimientos y notificaciones | Disponible |
| Sincronización | Estado central transaccional en PostgreSQL | Disponible con conexión |
| Aplicación instalable | Manifest, service worker y shell seguro | Disponible |
| Contingencia offline | Shell y recursos estáticos; escrituras bloqueadas sin servidor | Disponible segura |
| Conteos físicos | Ajustes auditados y movimientos; flujo dedicado pendiente de UX | Parcial |
| Órdenes de compra | Ciclo completo y recepción parcial/total | Disponible |
| Listas de picking | WMS con picking, packing y verificación por escaneo | Disponible |
| Trabajos/proyectos | Puede representarse con ubicaciones y referencias; módulo dedicado pendiente | Parcial |
| Historial de actividad | Auditoría append-only y movimientos | Disponible |
| Resumen de inventario | Cantidad, disponibilidad y valorización | Disponible |
| Actividad por usuario | Auditoría empresarial | Disponible |
| Reportes de movimiento y flujo | Reportes, exportaciones y filtros | Disponible |
| Reportes guardados | Reportes personalizados | Disponible |
| Envíos programados de reportes | Motor de correo existe; programador dedicado pendiente | Parcial |
| Roles personalizados | Roles y permisos especiales limitados por plan | Disponible |
| API y webhooks | Claves API, API pública y webhooks HMAC idempotentes | Disponible |
| QuickBooks, Slack y Teams | Proveedores reconocidos; OAuth y pruebas reales requieren credenciales | Preparado, no activado |

## Regla de producción

La palabra «Disponible» significa que existe implementación verificable en el repositorio.
«Parcial» no debe venderse como paridad completa. «Preparado, no activado» significa que el
dominio admite la integración, pero todavía faltan credenciales, consentimiento OAuth,
pruebas contractuales y monitoreo con la cuenta real del proveedor.

El modo offline no procesa ventas, ajustes ni movimientos sin conexión. Esa decisión evita
conflictos de stock, doble confirmación y pérdida de trazabilidad. Una futura cola offline
deberá usar identificadores idempotentes, detección de conflictos y confirmación humana.
