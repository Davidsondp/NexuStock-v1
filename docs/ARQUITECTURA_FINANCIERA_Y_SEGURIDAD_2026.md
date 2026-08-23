# Arquitectura financiera y seguridad 2026

## Planes

La oferta pública tiene exactamente cuatro planes: Avanzado, Ultra,
Profesional y Empresarial. La prueba gratuita no es un quinto plan: es el
primer período de 30 días del plan elegido. En los tres planes de autoservicio
se exige autorizar una tarjeta, no se cobra al comenzar y la renovación queda
programada automáticamente. Avanzado incluye 500 productos y dos usuarios; Ultra incluye
2.000 productos y cinco usuarios; Profesional incluye 5.000 productos y diez
usuarios; Empresarial incluye 10.000 productos y 12 usuarios. Empresarial se
activa solamente mediante contrato; su prueba y forma de cobro quedan
formalizadas en ese contrato.

`prueba`, `basico` y `corporativo` son registros inactivos conservados sólo por
compatibilidad referencial. No aparecen en la portada, no pueden seleccionarse
mediante URL y no admiten checkout de autoservicio. Los límites y capacidades
se resuelven en el servidor; el navegador nunca puede habilitar funciones por
sí solo.

## Ciclo financiero

La solicitud de plan, el intento de pago y la suscripción son entidades
separadas. Webpay o Mercado Pago debe confirmar el monto autorizado, moneda, referencia y
estado. La activación es idempotente y auditable. Cada pago confirmado abre un
período mensual o anual, registra proveedor de cobro y una ventana de gracia de
siete días. La cancelación se programa al fin del período; no elimina acceso ya
pagado y puede revertirse antes del vencimiento. Cada pago confirmado genera de
forma idempotente una factura o recibo comercial consultable por la empresa.

La prueba registra la intención de contratar el plan elegido y bloquea la operación hasta
que el proveedor confirma un mandato tokenizado. El primer cobro se programa al
final de los 30 días. NexuStock no almacena
números de tarjeta, CVV ni credenciales bancarias. Un checkout de pago único no
se considera autorización para cargos futuros.

La fecha de inicio de la prueba no se fija al crear la cuenta. Se establece de
forma atómica cuando Mercado Pago o Oneclick confirman el mandato; en ese mismo
momento se calculan el vencimiento, el período vigente y la fecha del primer
cobro. Una autorización pendiente, fallida o revocada no concede acceso a los
módulos empresariales.

Empresarial utiliza un flujo separado de oportunidad comercial. La solicitud
queda almacenada para el Super Admin y puede avanzar por los estados nueva,
contactada, cotizada, contratada o descartada. No se transforma en checkout ni
renovación automática sin las condiciones expresas del contrato.

La versión incluida implementa inscripción Oneclick Mall, preapproval de Mercado
Pago, tarea programada, avisos, reintentos y gracia. Está validada con proveedores
simulados; no debe anunciarse como operativa con dinero real hasta completar una
inscripción y una renovación controladas con credenciales y contratos productivos.
La factura tributaria
electrónica requiere además un proveedor DTE configurado; el documento interno
no sustituye por sí solo una factura fiscal ante el SII.

## Control del propietario

El Super Admin global controla empresas, estado y cierre de sesiones; catálogo
de planes, precios, límites y capacidades; suscripciones y correcciones
excepcionales auditadas; pagos y documentos; usuarios, bloqueos y cobertura
2FA; analítica global; auditoría y estado técnico. No puede entrar a operar el
inventario privado de una empresa. Los respaldos, restauraciones, secretos,
rotación de claves y despliegues permanecen en infraestructura, no en el panel
web, para reducir el riesgo de una toma total de la cuenta administrativa.

## Seguridad exigida en producción

- PostgreSQL y migraciones Alembic aplicadas.
- TLS, cookies Secure/HttpOnly/SameSite, HSTS, CSP y hosts confiables.
- CSRF en formularios y JSON obligatorio para escrituras API.
- Contraseñas de 12 o más caracteres para nuevas cuentas.
- 2FA TOTP obligatorio para Super Admin y jefaturas antes de operar.
- Bloqueo por intentos, rate limiting persistente y revocación de sesiones.
- Separación por `empresa_id`, roles/permisos y capacidades del plan.
- Webhooks firmados, referencias únicas, idempotencia y conciliación.
- Auditoría append-only de accesos, cambios de plan, pagos y cancelaciones.

## Puerta de producción

`flask --app run.py verificar-produccion` debe pasar después de migrar y sembrar
planes. Además se requieren credenciales productivas, SMTP, dominio HTTPS,
copias de seguridad verificadas, monitoreo, pruebas de restauración y un
pentest independiente. El software no debe anunciar certificación SOC 2 o ISO
27001 hasta completar una auditoría externa.
