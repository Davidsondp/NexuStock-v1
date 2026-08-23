# NexuStock v2

Reconstrucción limpia del SaaS de inventario según el Prompt Maestro.

## Desarrollo

En Windows utiliza [la guía de configuración local](docs/CONFIGURACION_LOCAL_WINDOWS.md):

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\configurar_local_windows.ps1
.\scripts\iniciar_local_windows.ps1
```

En Linux o macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask --app run.py db upgrade
flask --app run.py seed-planes
flask --app run.py run
```

No uses `db.create_all()` como reemplazo de migraciones.

## Calidad y pruebas

Instala las herramientas de desarrollo y ejecuta los mismos controles de CI:

```bash
pip install -r requirements-dev.txt
ruff check app tests config.py run.py scripts
black --check app tests config.py run.py scripts
pytest --cov=app --cov-report=term-missing --cov-fail-under=75
```

El workflow `.github/workflows/ci.yml` aplica las migraciones sobre PostgreSQL 16,
comprueba índices y bloqueos propios de PostgreSQL y después ejecuta la suite completa.
La cobertura actual supera el mínimo obligatorio del 75 %.

## Paquete distribuible

Genera el ZIP sin `.env`, `.git`, bases locales, cachés ni archivos temporales:

```bash
python scripts/empaquetar.py
```

No comprimas directamente la carpeta de trabajo: el script es la fuente autorizada
para crear entregables compartibles.

La carpeta `migrations/` ya forma parte del proyecto. `db init` y la migración inicial no se
repiten. Cuando cambien los modelos, genera una revisión nueva, revísala y pruébala antes de
aplicarla:

```bash
flask --app run.py db migrate -m "descripción del cambio"
flask --app run.py db upgrade
```

## Producción en Render

El archivo `render.yaml` provisiona PostgreSQL y el servicio web. Antes de cada despliegue,
Render ejecuta las migraciones y configura idempotentemente los planes. La sonda de vida es
`/estado`; `/estado/preparacion` además verifica la conexión a PostgreSQL.

Consulta [docs/DESPLIEGUE_RENDER.md](docs/DESPLIEGUE_RENDER.md) para configurar secretos,
crear el primer Super Admin, verificar el despliegue y recuperar una versión anterior.

## Flujo de compras

Las órdenes siguen el ciclo `borrador → creada → enviada → parcialmente_recibida → recibida`.
También pueden cancelarse antes de la primera recepción. Cada recepción confirmada actualiza
inventario y costo promedio en una única transacción, registra movimientos y auditoría, y
valida lotes, vencimientos y números de serie cuando el producto los exige.

## Flujo de ventas

Las ventas siguen `borrador → reservada → confirmada`. La reserva reduce la disponibilidad
sin alterar el stock físico; la confirmación libera la reserva y genera la salida definitiva.
Cancelar una venta reservada devuelve inmediatamente la disponibilidad.

## Escaneo móvil de productos

El formulario de movimientos puede seleccionar productos con la cámara trasera mediante QR,
EAN-8, EAN-13, UPC, Code 39, Code 128 e ITF. El código se compara dentro de la empresa con el
código de barras o código interno del producto; el escaneo sólo completa la selección y nunca
confirma por sí mismo una entrada o salida. La cámara requiere HTTPS y permiso del usuario. Cuando
el navegador no ofrece detección automática, el panel conserva el ingreso directo del código.

## Catálogo visual, campos y etiquetas

Los productos admiten hasta 20 campos personalizados simples, validados en servidor y
aislados por empresa. El catálogo ofrece colecciones visuales por categoría y genera etiquetas
imprimibles de 62 × 30 mm con QR autocontenido, sin enviar datos a un generador externo.

## Aplicación instalable y contingencia offline

El panel principal y el catálogo publican un manifiesto instalable y registran un service
worker bajo HTTPS. Sólo se almacenan el shell y recursos estáticos; las rutas API y las
escrituras nunca se responden desde caché. Cuando no hay conexión se muestra una pantalla
segura y se bloquean ventas, movimientos y ajustes hasta recuperar el servidor.

Consulta [la matriz de cobertura funcional](docs/COBERTURA_REFERENCIA_SORTLY.md) antes de
presentar equivalencias comerciales con otros productos.

## Motor de alertas

El motor evalúa por producto y bodega el stock bajo, sobrestock, riesgo de agotamiento,
falta de movimientos y recomendaciones de compra. Las reglas usan stock disponible,
umbrales configurados, consumo real de 30 días y plazo de entrega del proveedor. Mantiene
una sola alerta activa por regla y conserva el historial de alertas resueltas o ignoradas.

## Reportes y analítica

Los reportes básicos exponen productos, stock y movimientos dentro de las bodegas autorizadas.
La analítica avanzada calcula ventas confirmadas, ingresos, costo de ventas, margen bruto,
productos más vendidos, sobrestock, productos sin movimiento, valor actual y cobertura.
Un cron diario conserva snapshots de inventario. La rotación usa el inventario promedio de los
cortes disponibles y declara explícitamente cuando debe recurrir temporalmente al stock actual.
El plan Empresa también permite guardar y ejecutar configuraciones de reportes personalizados.

## Nexu IA

El plan Empresa incluye un asesor de inventario con consultas de compras, ventas, riesgos y
resumen ejecutivo. El contexto se arma en el servidor únicamente con las sucursales autorizadas,
sin datos de otras empresas, y las respuestas usan un esquema JSON estricto. Las recomendaciones
nunca modifican inventario automáticamente: toda acción operativa requiere confirmación humana.

Configura `OPENAI_API_KEY` para usar la API de Responses. `OPENAI_MODEL`,
`IA_LIMITE_DIARIO_EMPRESA` e `IA_TIMEOUT_SEGUNDOS` permiten controlar modelo, costo y latencia.
Sin una clave válida, Nexu conserva un modo local de contingencia basado en reglas para que el
panel siga entregando alertas y recomendaciones básicas.

## Centro de Ayuda

`/panel/ayuda` reúne búsqueda de respuestas, guías rápidas por módulo y contacto con el equipo.
Las solicitudes se envían a `equipos@nexustock.cl` usando el SMTP configurado, con el correo del
usuario como dirección de respuesta. El sistema agrega empresa, rol y página de origen, pero no
incluye contraseñas, tokens ni datos del inventario. Cada envío se audita sin almacenar el texto
del mensaje y se limita a cinco solicitudes por usuario y hora.

## Exportaciones

Los reportes autorizados pueden descargarse en CSV UTF-8 o Excel XLSX. La exportación reutiliza
los filtros multiempresa y por bodega del servicio de reportes, exige la función comercial
correspondiente, registra auditoría y neutraliza entradas que una hoja de cálculo podría
interpretar como fórmulas.

## Importación de documentos

El Centro de importación admite catálogos en CSV, Excel XLSX y tablas textuales PDF. La carga se
procesa en memoria y genera una vista previa firmada antes de modificar datos. Los encabezados
reconocen variantes como `codigo`, `sku`, `nombre`, `ean`, `costo`, `precio` y `stock_inicial`.
La confirmación crea o actualiza productos por código y registra el stock inicial mediante el
servicio de inventario, con movimientos y auditoría dentro de una sola transacción.

Los archivos se limitan por tamaño y cantidad de filas. Los PDF escaneados como imagen no se
interpretan sin OCR: se rechazan con un mensaje explícito para evitar datos inventados. Configura
`IMPORTACION_MAX_BYTES` e `IMPORTACION_MAX_FILAS` según los recursos del despliegue.

## Gestión de usuarios

Las jefaturas empresariales crean y gestionan usuarios dentro del límite del plan, asignan
sucursales y aplican permisos especiales validados por el catálogo central. No pueden crear
Super Admin ni habilitar funciones ausentes del plan. Los cambios sensibles incrementan la
versión de sesión para cerrar accesos existentes y siempre se conserva una jefatura activa.

## Configuración empresarial

La empresa administra su identidad comercial, ubicación, moneda, idioma, zona horaria,
personalización y preferencias de alertas mediante campos validados. El plan, los límites,
el estado comercial y la facturación se muestran como información de solo lectura y no pueden
modificarse desde la configuración empresarial.

## Pagos y suscripciones

Una empresa solicita un plan y ciclo con un monto pactado verificable, inicia un pago con referencia única
y espera la confirmación firmada del proveedor. El webhook verifica firma y antigüedad, valida
monto y moneda, procesa idempotentemente el evento y activa la suscripción en una sola
transacción. La capa de permisos únicamente consulta el resultado de esa suscripción.

## Super Administración

El Super Admin es el propietario global de NexuStock y usa un panel completamente separado.
Consulta indicadores globales, empresas, planes, suscripciones, pagos y auditoría.
Puede suspender o reactivar empresas y editar planes con validaciones, pero no elimina empresas,
modifica pagos confirmados ni opera inventarios empresariales. Cada cambio global queda auditado
y la suspensión de una empresa revoca las sesiones existentes de sus usuarios.

## Seguridad transversal

La aplicación aplica CSRF a formularios y APIs basadas en sesión, exige JSON en operaciones API,
limita rutas de autenticación mediante contadores persistentes anonimizados, genera identificadores
de solicitud y devuelve errores sin detalles internos. Todas las respuestas incorporan CSP,
protección contra marcos, `nosniff`, política de referente y restricciones de capacidades. En
producción también se exige HSTS, hosts autorizados y secretos independientes para webhooks y límites.
