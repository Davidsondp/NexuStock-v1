# Despliegue de NexuStock en Render

## 1. Crear el servicio

Conecta el repositorio en Render y selecciona **New Blueprint**. El archivo `render.yaml`
creará el servicio web y una base PostgreSQL privada. No copies credenciales al repositorio.
También crea `nexustock-alertas`, una tarea horaria que ejecuta el motor idempotente de alertas.

## 2. Completar variables secretas

En el panel del servicio configura:

- `TRUSTED_HOSTS`: dominio público exacto de Render, por ejemplo
  `nexustock.onrender.com`. Agrega el dominio propio separado por coma si corresponde.
- `MAIL_SERVER`, `MAIL_USERNAME`, `MAIL_PASSWORD` y `MAIL_DEFAULT_SENDER`.
- `SOPORTE_EMAIL`: destinatario del Centro de Ayuda; por defecto `equipos@nexustock.cl`.
- `BASE_URL`: URL pública HTTPS sin barra final, por ejemplo
  `https://nexustock.onrender.com`.
- `WEBPAY_COMMERCE_CODE` y `WEBPAY_API_KEY`: credenciales de producción
  entregadas por Transbank. Nunca uses las credenciales de integración en producción.
- `WEBPAY_ENV`: debe mantenerse en `production` para el servicio productivo.
- `WEBPAY_ONECLICK_PARENT_COMMERCE_CODE`, `WEBPAY_ONECLICK_CHILD_COMMERCE_CODE` y
  `WEBPAY_ONECLICK_API_KEY`: contrato y credenciales productivas de Oneclick Mall.
- `MERCADOPAGO_ACCESS_TOKEN`: credencial privada productiva de Checkout Pro.
- `MERCADOPAGO_WEBHOOK_SECRET`: firma secreta configurada al crear la notificación
  `https://TU-DOMINIO/webhooks/pagos/mercadopago` en Mercado Pago.
- `MERCADOPAGO_ENV`: debe mantenerse en `production` para el servicio productivo.
- `REQUIRE_TRIAL_PAYMENT_METHOD=true`: obliga a autorizar tarjeta antes de usar la prueba.
- `RENOVACION_MAX_REINTENTOS=3` y `RENOVACION_GRACIA_DIAS=7`: política de rechazo.
- `OPENAI_API_KEY`: clave secreta del proyecto OpenAI usada por Nexu IA. El Blueprint
  configura `OPENAI_MODEL=gpt-5.6-luna`, un límite diario de 100 consultas por empresa
  y 30 segundos de timeout; ajusta esos valores según el presupuesto y uso real.
- `IMPORTACION_MAX_BYTES` e `IMPORTACION_MAX_FILAS`: límites defensivos para documentos
  importados. Los valores predeterminados son 10 MiB y 2.000 filas.
- Los secretos generados (`SECRET_KEY` y
  `LIMITE_SOLICITUDES_SECRET`) deben conservarse entre despliegues.
- En los cron, incluido `nexustock-renovaciones`, configura los mismos valores de `SECRET_KEY`,
  `LIMITE_SOLICITUDES_SECRET`, `TRUSTED_HOSTS`, `MAIL_SERVER`
  y `MAIL_DEFAULT_SENDER`. La conexión PostgreSQL se enlaza automáticamente.

El cron `nexustock-renovaciones` ejecuta el cobro recurrente cada seis horas, respeta la fecha
de reintento y suspende solamente cuando se agotan los intentos y termina el período de gracia.
Antes de habilitar tráfico real, completa en staging una inscripción y una renovación controlada
con cada proveedor. La presencia de variables no demuestra que el contrato productivo esté activo.

`DATABASE_URL` se obtiene automáticamente de la base administrada. Nunca la publiques ni la
pegues en incidencias o conversaciones.

## 3. Primera publicación

El paso previo al despliegue ejecuta, en este orden:

```bash
flask --app run.py db upgrade
flask --app run.py seed-planes
flask --app run.py verificar-produccion
```

La migración inicial está diseñada para una base vacía. Si ya existe una base con tablas de
una versión anterior, no ejecutes `stamp` ni `upgrade` a ciegas: primero exporta únicamente su
esquema y compara cada tabla con la migración.

## 4. Crear y comprobar la administración

Después de que la puerta automática termine, desde **Shell** crea la cuenta propietaria:

```bash
flask --app run.py crear-super-admin
flask --app run.py verificar-produccion
```

Comprueba también:

- `GET /estado` devuelve `200` y `estado: correcto`.
- `GET /estado/preparacion` devuelve `200` y `estado: preparado`.
- El registro del despliegue muestra una sola revisión de Alembic aplicada.

## 5. Cambios futuros de base de datos

Genera la migración localmente después de modificar los modelos:

```bash
flask --app run.py db migrate -m "descripción breve"
flask --app run.py db upgrade
pytest -q
```

Revisa manualmente `upgrade()` y `downgrade()` y pruébalos en PostgreSQL de staging. SQLite
no sustituye esa prueba porque su emulación de cambios de esquema tiene restricciones distintas.
Versiona la migración junto con el código. No edites una revisión ya aplicada en producción;
crea una revisión nueva.

## 6. Recuperación

Antes de una migración destructiva crea un respaldo de PostgreSQL. Para volver atrás, publica
el código anterior y usa `flask --app run.py db downgrade <revision>` solamente si ese
`downgrade()` fue probado sobre PostgreSQL y no elimina información necesaria. Cuando exista riesgo de pérdida,
restaura el respaldo en una base nueva y cambia la conexión después de validarla.
