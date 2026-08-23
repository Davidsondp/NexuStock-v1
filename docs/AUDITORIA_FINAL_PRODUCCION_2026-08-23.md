# Auditoría final de producción — 23 de agosto de 2026

## Resultado ejecutivo

La aplicación, las migraciones, el aislamiento multiempresa y los flujos de
inventario y pago único quedan validados por pruebas automatizadas. La oferta
pública queda limitada a cuatro planes: Avanzado, Ultra, Profesional y
Empresarial. La prueba gratuita es un período de 30 días del plan elegido, no
un plan separado. Los registros técnicos heredados no son comprables ni seleccionables
por URL.

No se declara producción total hasta completar los requisitos externos de la
sección «Bloqueos externos». Esta distinción evita confundir código probado con
servicios de terceros todavía no certificados.

## Revisión módulo por módulo

| Módulo | Flujo revisado | Resultado |
|---|---|---|
| Autenticación | Registro, correo, ingreso, bloqueo, sesión y 2FA | Validado |
| Super Admin | Empresas, planes, suscripciones, pagos, documentos y seguridad | Validado; cambios auditados |
| Panel empresarial | Navegación, contexto y métricas | Validado |
| Productos | Catálogo, variantes, campos y límites | Validado |
| Inventario | Entradas, salidas, ajustes, stock y concurrencia | Validado |
| Ubicaciones | Sucursales, bodegas y ámbito empresarial | Validado |
| Transferencias | Solicitud, despacho, recepción y trazabilidad | Validado |
| Seriales y lotes | Asociación, venta y trazabilidad | Validado |
| Compras | Órdenes, recepción y proveedores | Validado |
| Ventas | Pedido, líneas, stock y clientes | Validado |
| Clientes | CRUD y aislamiento por empresa | Validado |
| Proveedores | CRUD y aislamiento por empresa | Validado |
| Alertas | Stock, vencimiento y ejecución programada | Validado |
| Reportes | Inventario, ventas, compras y exportación | Validado |
| Reportes personalizados | Definición, ejecución y propiedad | Validado |
| Importaciones | CSV/XLSX/PDF, límites y sanitización | Validado |
| API pública | Claves hash, permisos, ámbito y límites | Validado |
| Claves API | Creación, exposición única y revocación | Validado |
| Auditoría | Eventos, actor, empresa y trazabilidad | Validado |
| Notificaciones | Consulta y estado de lectura | Validado |
| Configuración | Empresa, preferencias y permisos | Validado |
| Usuarios | Roles, sucursales, límites y revocación de sesión | Validado |
| Suscripciones | Mandato, renovación, reintentos, gracia y cancelación al período | Validado con dobles; falta prueba productiva |
| Onboarding | Cuatro pasos, selección conservada, verificación y activación posterior al mandato | Validado |
| Contrato Empresarial | Captura, seguimiento del propietario y separación de checkout | Validado |
| Webpay | Checkout y Oneclick Mall recurrente | Validado con dobles; falta contrato/credencial real |
| Mercado Pago | Checkout y Suscripciones/preapproval | Validado con dobles; falta credencial real |
| Facturación SaaS | Documento automático e idempotente | Validado como documento comercial |
| Suite comercial | Cotizaciones, pedidos, despacho e integraciones | Validado |
| Asistente IA | Permiso, cuota, timeout y registro | Validado; depende de credencial externa |
| Estado técnico | Vida, preparación y base de datos | Validado |

## Correcciones finales incorporadas

- Se alineó el tipo de `documento_facturacion_saas.pago_id` mediante una nueva
  migración; una base creada desde cero ya no presenta deriva de esquema.
- Se alinearon las capacidades multisucursal, multibodega y transferencias de
  Ultra y Profesional con los límites que esos planes publican.
- Se centralizó la clasificación de planes para cerrar la selección indirecta
  de niveles internos mediante parámetros de URL.
- Se impidió que el Super Admin marque renovación automática sin un mandato
  recurrente verificado y se sincronizó cancelación al fin del período.
- Se añadieron cookies persistentes `Secure`, `HttpOnly` y `SameSite` en
  producción y confianza limitada a un único proxy de Render.
- El instalador de Windows acepta tanto `py` como `python`, valida Python 3.12 y
  explica cómo recuperar una carpeta `.venv` incompleta.
- Se repararon los símbolos visuales dañados de planes, beneficios y preguntas.
- Render ejecuta migraciones, sincroniza planes y bloquea el despliegue si falla
  `verificar-produccion`.

## Bloqueos externos antes de tráfico real

1. Configurar y probar credenciales productivas de Webpay y Mercado Pago.
2. Contratar/certificar Oneclick Mall y Suscripciones/preapproval, y completar
   una inscripción más una renovación controlada en producción.
3. Configurar proveedor DTE y validar emisión tributaria ante el SII. El recibo
   interno automático no sustituye una factura electrónica fiscal.
4. Configurar SMTP, dominio HTTPS, `TRUSTED_HOSTS`, secretos y rotación de claves.
5. Probar respaldo/restauración de PostgreSQL y ejecutar un pentest externo.

## Comandos de aceptación

```powershell
.\scripts\configurar_local_windows.ps1
.\scripts\iniciar_local_windows.ps1
```

```bash
flask --app run.py db upgrade
flask --app run.py seed-planes
flask --app run.py verificar-produccion
pytest -q
```
