# Ruta comercial prioritaria de NexuStock

Esta versión incorpora cinco capacidades orientadas a problemas por los que empresas chilenas pagan: control corporativo, venta en caja, operación de bodega, emisión tributaria integrada y sincronización con terceros.

## Capacidades

### Multiempresa corporativa

- Grupos empresariales y filiales.
- Accesos explícitos de usuarios a empresas del grupo.
- Consolidación limitada exclusivamente a empresas autorizadas.
- Totales de unidades y valorización por empresa y grupo.

Endpoint: `GET /api/comercial/multiempresa/resumen`.

### POS y cajas

- Cajas por sucursal y un solo turno abierto por caja.
- Apertura, venta, pagos divididos, cierre y arqueo.
- Venta, reserva, salida de stock, pagos y auditoría en una transacción.
- `Idempotency-Key` obligatorio contra ventas duplicadas.

Endpoints bajo `/api/comercial/pos`.

### WMS

Flujo estricto:

`pendiente → picking → pickeada → packing → empacada → despachada`

El despacho exige transportista y seguimiento. La venta y el stock se confirman en el despacho final.

Endpoints bajo `/api/comercial/wms`.

### Documentos tributarios

Se implementa un adaptador HTTPS neutral para integrar un proveedor certificado por el SII. NexuStock no afirma estar certificado por sí mismo.

```text
DTE_PROVIDER_URL=https://api.proveedor-certificado.cl
DTE_API_KEY=...
```

La emisión exige una venta confirmada e `Idempotency-Key`. Guarda folio, referencia y estado, pero excluye XML/PDF del JSON operacional.

Endpoint: `POST /api/comercial/dte`.

### Integraciones

- Conexiones por empresa para Shopify, WooCommerce, Mercado Libre, contabilidad u otro adaptador.
- Secreto de webhook almacenado como hash.
- Eventos idempotentes mediante `X-Event-ID`.
- Registro de payload, resultado y momento de procesamiento.

Endpoints bajo `/api/comercial/integraciones` y `/webhooks/integraciones`.

## Seguridad

- Todas las consultas operativas filtran por empresa.
- Los recursos se resuelven del lado servidor.
- Los webhooks son idempotentes.
- Los secretos no se devuelven en respuestas.
- Las operaciones relevantes generan auditoría.
- Las capacidades dependen de permisos y funciones del plan.

## Migración y prueba

```bash
flask --app run.py db upgrade
pytest -q
```

Migración: `c4c508486ee1_agrega_suite_comercial_prioritaria.py`.

Antes de Render, usar una copia de PostgreSQL, configurar un proveedor DTE certificado en sandbox y probar POS/WMS con una venta controlada.
