# Aceptación: correo y renovación recurrente

## Resultado verificable

- El panel financiero utiliza un flujo guiado de cuatro etapas: perfil del negocio,
  selección del plan, autorización del pago y activación. La pantalla de autorización
  presenta proveedor, precio, ciclo, límites y fecha de primer cobro en un resumen único.
- Durante la prueba se ofrece exclusivamente el mandato recurrente elegido; ya no se
  mezcla ese flujo con botones de checkout único. No existen campos propios para PAN o CVV.
- El registro genera un enlace de verificación de uso limitado y el ingreso queda
  bloqueado hasta confirmarlo cuando `REQUIRE_EMAIL_VERIFICATION=true`.
- Si SMTP falla, la interfaz no afirma que el mensaje fue enviado y permite pedir
  otro enlace sin revelar si una cuenta existe.
- La prueba dura 30 días, admite 500 productos y dos usuarios, exige autorizar una
  tarjeta y programa el primer cobro del plan Avanzado al terminar la prueba.
- Webpay usa una inscripción Oneclick Mall; Mercado Pago usa una suscripción
  `preapproval`. NexuStock conserva referencias tokenizadas, no PAN ni CVV.
- El cron de renovación notifica antes del cobro, registra cada intento, reintenta
  en fechas explícitas, mantiene siete días de gracia y suspende al agotarse la
  política sin cobro confirmado.
- La migración completa desde una base vacía alcanza `f8a9b0c1d2e3`.
- Validación local: 508 pruebas de la suite completa más una prueba Oneclick
  enfocada aprobadas; tres pruebas PostgreSQL se omiten fuera de ese motor.

## Bloqueo externo

No se certificó ningún cobro productivo porque este entorno no contiene contratos
ni credenciales productivas. Antes de abrir tráfico, deben ejecutarse en staging
una verificación SMTP real, una inscripción y una renovación controlada con
Oneclick Mall, y el equivalente con Mercado Pago Suscripciones. Los secretos se
configuran directamente en Render; nunca se incorporan al ZIP ni se envían por chat.
