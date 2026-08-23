# NexuStock — entrega candidata a producción

## Contenido

El proyecto incluye aplicación Flask, modelos SQLAlchemy, 16 migraciones Alembic,
plantillas y activos web, configuración Render, comandos operativos, documentación y
54 archivos de pruebas automatizadas.

## 28 módulos funcionales

1. Autenticación y recuperación de cuenta
2. Seguridad de cuenta, verificación de correo y 2FA
3. Usuarios, roles y permisos
4. Multiempresa y consolidación autorizada
5. Suscripciones y planes
6. Webpay
7. Mercado Pago
8. Conciliación automática de pagos
9. Productos y catálogo
10. Imágenes de productos
11. Inventario
12. Lotes y vencimientos farmacéuticos
13. Seriales
14. Unidades y presentaciones
15. Sucursales, bodegas y ubicaciones
16. Transferencias
17. Proveedores
18. Compras y recepción
19. Clientes
20. Ventas
21. POS, cajas y turnos
22. WMS: picking, packing y despacho verificado
23. DTE mediante proveedor certificado
24. Integraciones comerciales y webhooks firmados
25. Alertas y notificaciones
26. Reportes, exportaciones y reportes personalizados
27. Asistente de IA
28. Superadministración, auditoría y estado del sistema

## Modernización 2026 orientada a pequeños negocios

- Sistema visual transversal unificado con mayor contraste, jerarquía y adaptación móvil.
- Catálogo organizado visualmente por colecciones/categorías, calculadas desde los productos de la empresa.
- Consulta de productos mediante cámara trasera, código escrito o lector USB.
- Compatibilidad con EAN-8, EAN-13, UPC, Code 39, Code 128 y QR en navegadores compatibles.
- Contingencia manual cuando la cámara, HTTPS o `BarcodeDetector` no están disponibles.
- El escaneo sólo consulta y filtra; no modifica existencias ni confirma movimientos.
- Se conserva la separación total entre operación empresarial y Super Administración.
- Campos personalizados seguros por producto.
- Etiquetas imprimibles con QR autocontenido.
- Aplicación web instalable mediante manifest y service worker.
- Contingencia offline que excluye APIs y bloquea escrituras sin servidor.

La modernización toma como referencia patrones generales de facilidad de uso de aplicaciones
de inventario modernas. No incorpora código, marca, textos ni recursos propietarios de terceros.

## Correcciones de seguridad y operación

- El plan sólo cambia después de confirmar el pago directamente con el proveedor.
- Cada reintento conserva su propio pago, referencia y token; la idempotencia evita dobles cobros.
- Se agregó conciliación programada cada cinco minutos para pagos iniciados/procesando.
- El acceso se registra únicamente después de completar 2FA.
- La verificación de correo es obligatoria en producción.
- 2FA usa una clave independiente, versionada y rotatable, con lectura compatible del formato anterior.
- Los webhooks de integraciones exigen HMAC-SHA256, timestamp de cinco minutos e ID idempotente.
- Los payloads de integración eliminan secretos y datos personales comunes y tienen límite de tamaño.
- WMS exige cantidades escaneadas exactas en picking y packing.
- DTE envía emisor, receptor, totales, impuestos, detalle y referencia de notas.
- Las imágenes externas se restringen a `IMAGE_ALLOWED_HOSTS`.
- POS recupera de forma idempotente una venta ante carreras de concurrencia.
- Los endpoints sensibles nuevos tienen límites persistentes de solicitudes.

## Verificaciones ejecutadas

- Suite automatizada completa: 487 aprobadas y 3 condicionadas a PostgreSQL externo.
- Ruff: sin errores.
- Compilación Python: correcta.
- Migración desde base vacía hasta la revisión final: correcta en SQLite local.
- `seed-planes`: correcto después de migrar.

Las pruebas PostgreSQL se ejecutan únicamente cuando se configura
`TEST_POSTGRESQL_DATABASE_URL`; no deben omitirse en el pipeline previo a producción.

## Activación externa obligatoria

El código no puede sustituir contratos, credenciales ni certificaciones de terceros.
Antes de cobrar en producción se deben configurar y probar Webpay y Mercado Pago con
credenciales productivas. Antes de emitir documentos tributarios se debe contratar un
proveedor certificado por el SII y completar los datos tributarios del emisor. La ruta
`flask --app run.py verificar-produccion` bloquea una configuración incompleta.

## Despliegue recomendado

1. Restaurar una copia anonimizada de producción en PostgreSQL de staging.
2. Ejecutar `flask --app run.py db upgrade`.
3. Ejecutar la suite con `TEST_POSTGRESQL_DATABASE_URL`.
4. Ejecutar `flask --app run.py verificar-produccion`.
5. Probar pagos reales controlados, webhook, cancelación y confirmación tardía.
6. Validar emisión DTE en certificación del proveedor.
7. Crear backup y probar restauración antes del despliegue de Render.

No se presenta esta entrega como “certificada SII” ni como validada contra proveedores
productivos mientras esas pruebas externas no hayan sido realizadas.
