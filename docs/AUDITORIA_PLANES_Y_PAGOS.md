# Auditoría de planes y pagos

## Contrato comercial

- La prueba gratuita es una oferta de adquisición de 30 días, no un plan facturable.
- Los planes públicos facturables son Avanzado, Ultra, Profesional y Empresarial.
- La solicitud registra el plan, ciclo, proveedor, monto pactado y moneda que el
  proveedor deberá devolver; no existe una «congelación de precio» al iniciar pago.
- El plan vigente no cambia al crear la solicitud ni al iniciar el checkout.
- Cada intento crea una referencia y un registro de pago diferentes.
- Sólo las consultas directas a Webpay o Mercado Pago pueden confirmar dinero.
- El plan efectivo es exclusivamente la suscripción confirmada en PostgreSQL.

## Matriz verificada

| Caso | Pago | Solicitud | Suscripción | Acción permitida |
|---|---|---|---|---|
| Solicitud sin intento | — | pendiente | sin cambios | pagar, cambiar, cancelar |
| Creación en proveedor | iniciado | pago_en_proceso | sin cambios | esperar, volver |
| Proveedor pendiente | procesando | pago_en_proceso | sin cambios | consultar, solicitar cancelación |
| Rechazado confirmado | rechazado | pendiente | sin cambios | reintentar, cambiar proveedor/plan, cancelar |
| Cancelado confirmado | cancelado | pendiente | sin cambios | reintentar, cambiar proveedor/plan, cancelar |
| Aprobado y coincidente | pagado | aprobada | nuevo plan | ir al panel |
| Proveedor sin respuesta | iniciado/incidencia | cancelacion_en_revision | sin cambios | volver; conciliación continúa |
| Aprobado durante revisión | pagado | aprobada | plan del pago | ir al panel |
| Aprobado tras cancelación confirmada | incidencia | cancelada | sin cambios | revisión/reembolso |
| Aprobado con identidad, monto o moneda distintos | incidencia o reembolsado | cancelacion_en_revision o pendiente | sin cambios | revisión/reembolso |
| Reembolso/contracargo | reembolsado | resuelta | suspendida si corresponde | regularizar |

## Controles de dinero

1. Referencia local única por proveedor.
2. Token/preferencia únicos por proveedor en PostgreSQL.
3. ID de transacción remota único por proveedor.
4. Precio y moneda derivados exclusivamente del plan almacenado.
5. Webpay valida token, orden, sesión, monto, moneda, autorización y código de respuesta.
6. Mercado Pago valida firma, consulta el pago, referencia, metadata de empresa/solicitud/pago,
   monto, moneda, estado e ID remoto no procesado.
7. Un resultado aprobado inconsistente nunca se registra como simple rechazo.
8. Si Mercado Pago admite el reembolso automático de un aprobado inconsistente, se intenta;
   si no puede confirmarse, queda como incidencia.
9. Un timeout al crear un checkout conserva el intento y bloquea cobros paralelos.
10. El conciliador programado sólo consulta; no vence ni cancela por reloj local.
11. La cancelación expresa sí consulta al proveedor y sólo libera cuando el resultado es seguro.
12. No existe un webhook genérico interno capaz de activar planes.

## Migración

Las revisiones vigentes `f6a7b8c9d0e1` y `f7a8b9c0d1e2` alinean la clave
foránea de documentos y las capacidades multisucursal con sus límites. La cadena completa fue
probada desde una base vacía y `flask db check` no detecta deriva.

## Validación ejecutada

- 505 pruebas aprobadas.
- 3 pruebas PostgreSQL condicionadas a `TEST_POSTGRESQL_DATABASE_URL`.
- Migración `c4c508486ee1 -> d5e6f7a8b9c0` aprobada en la base local.
- Ruff sin errores.

## Validaciones externas pendientes

Ninguna prueba local sustituye la certificación o respuesta productiva de Transbank,
Mercado Pago y PostgreSQL en Render. Antes de cobrar dinero real se debe ejecutar el mismo
conjunto con PostgreSQL de staging, casos oficiales de integración, webhooks reales, backup y
restauración comprobada. No se debe usar `WEBPAY_ENV=production` ni
`MERCADOPAGO_ENV=production` hasta completar esas validaciones.
