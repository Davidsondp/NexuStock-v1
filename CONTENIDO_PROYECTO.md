# Contenido del proyecto NexuStock

Este paquete contiene el proyecto completo de NexuStock preparado para ejecución local y posterior despliegue en Render. No incluye el entorno virtual `.venv`, cachés de pruebas, bases de datos locales ni secretos.

## Archivos principales

| Ruta | Contenido |
| --- | --- |
| `run.py` | Punto de entrada de Flask. |
| `config.py` | Configuración de desarrollo, pruebas y producción. |
| `requirements.txt` | Dependencias de producción. |
| `requirements-dev.txt` | Dependencias para pruebas y desarrollo. |
| `render.yaml` | Configuración de despliegue en Render. |
| `Procfile` y `gunicorn.conf.py` | Arranque del servidor de producción. |
| `.env.example` | Variables de entorno requeridas, sin credenciales reales. |
| `README.md` | Documentación general del sistema. |
| `pyproject.toml` y `pytest.ini` | Calidad de código y configuración de pruebas. |

## Aplicación `app/`

- `models.py`: modelos SQLAlchemy, restricciones, relaciones y estados financieros.
- `__init__.py`: fábrica y registro de la aplicación Flask.
- `extensions.py`: base de datos, migraciones, correo, CSRF y extensiones.
- `permisos.py`: autorización empresarial y control por roles.
- `seguridad.py`: protecciones transversales de producción.
- `validaciones.py`: validaciones compartidas.
- `commands.py`: comandos administrativos de Flask.

### Blueprints

El proyecto incluye 28 módulos de rutas, incorporando la suite comercial:

- alertas, API pública, asistente IA y auditoría;
- autenticación, ayuda, claves API y clientes;
- compras, configuración, contexto empresarial y estado;
- importaciones, inventario, notificaciones y panel;
- productos, proveedores, reportes y reportes personalizados;
- seriales, superadministración y suscripciones;
- transferencias, ubicaciones, usuarios y ventas.
- multiempresa corporativa, POS, WMS, DTE e integraciones.

### Servicios

Incluye la lógica empresarial para inventario, productos, proveedores, compras, ventas, transferencias, reportes, usuarios, alertas, importaciones, exportaciones, imágenes, planes, suscripciones y seguridad de cuenta.

El flujo financiero corregido se encuentra principalmente en:

- `app/services/suscripciones.py`
- `app/services/pagos_webpay.py`
- `app/services/pagos_mercadopago.py`
- `app/services/conciliacion_pagos.py`
- `app/blueprints/suscripciones/routes.py`
- `app/static/js/planes.js`
- `app/services/suite_comercial.py`
- `app/blueprints/suite_comercial/routes.py`

### Interfaz

- `app/templates/`: páginas de autenticación, contexto, panel y superadministración.
- `app/static/css/`: estilos del sistema.
- `app/static/js/`: comportamiento del panel y sus módulos.
- `app/static/img/`: recursos gráficos incluidos en el proyecto original.

## Base de datos y migraciones

La carpeta `migrations/` contiene Alembic completo y 14 migraciones versionadas. Las migraciones comerciales nuevas son:

`migrations/versions/f9a2c4d6e8b0_flujo_pagos_seguro.py`

`migrations/versions/c4c508486ee1_agrega_suite_comercial_prioritaria.py`

Esta migración:

- normaliza estados antiguos de pago;
- incorpora los estados seguros de solicitud y pago;
- agrega proveedor preferido y vencimiento del pago;
- congela plan y ciclo dentro de cada pago;
- mantiene una sola solicitud financiera abierta por empresa;
- permite downgrade seguro.

## Pruebas

La carpeta `tests/` contiene 54 archivos de pruebas para autenticación, permisos, seguridad, producción, PostgreSQL, inventario, compras, ventas, reportes, paneles, planes, Webpay, Mercado Pago y la suite comercial.

Resultado de la validación final:

```text
476 passed, 3 skipped
```

Los tres casos omitidos dependen de condiciones de infraestructura que no están presentes en la ejecución local; no corresponden a fallos.

## Documentación incluida

- `docs/DESPLIEGUE_RENDER.md`: despliegue del sistema.
- `docs/FLUJO_PAGOS_SEGURO.md`: reglas financieras, prueba local y migración.
- `docs/RUTA_COMERCIAL_PRIORITARIA.md`: capacidades, seguridad y operación comercial.
- `CONTENIDO_PROYECTO.md`: este inventario del paquete.

## Elementos excluidos intencionalmente

- `.venv/` y paquetes instalados localmente;
- `.pytest_cache/` y `__pycache__/`;
- archivos `.db` locales;
- `.env` y credenciales reales;
- tokens Webpay, claves Mercado Pago o contraseñas.

Estas exclusiones son necesarias para que el paquete sea limpio y seguro. Todo lo necesario para reconstruir el entorno está en los archivos de dependencias y en `.env.example`.
