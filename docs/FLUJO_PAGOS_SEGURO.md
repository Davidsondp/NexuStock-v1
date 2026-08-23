# Flujo seguro de planes y pagos

## Garantías implementadas

- El plan vigente no cambia al crear una solicitud ni al iniciar un checkout.
- Cada intento crea una referencia y credencial nueva; solo se reutiliza un checkout que el proveedor aún informa activo.
- Solo puede existir un pago activo por solicitud.
- El precio, moneda, plan y ciclo quedan congelados también en el pago.
- La activación valida referencia, empresa, monto, moneda, plan, ciclo e idempotencia.
- Pago, solicitud, suscripción y auditoría se confirman en una transacción.
- Una cancelación incierta queda en `cancelacion_en_revision`; el usuario puede salir del flujo.
- Una aprobación durante la revisión activa exactamente el plan pagado.
- Una aprobación posterior a una cancelación confirmada queda como `incidencia` y no cambia el plan.
- El reloj local no declara vencido un checkout; el estado remoto es la fuente financiera.

## Prueba local antes de Render

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/pytest -q
```

En Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python -m pytest -q
```

Para probar la migración sobre una copia de la base local:

```powershell
$env:FLASK_ENV = "desarrollo"
$env:DATABASE_URL = "sqlite:///nexustock-prueba.db"
.\.venv\Scripts\flask --app run.py db upgrade
```

## Despliegue

1. Crear un respaldo de PostgreSQL.
2. Desplegar el código sin ejecutar cobros manuales durante la ventana.
3. Ejecutar `flask --app run.py db upgrade` una sola vez.
4. Confirmar `/estado`, abrir la pantalla de planes y realizar una compra de prueba controlada.
5. Revisar auditoría y verificar que el plan solo cambió después de la confirmación del proveedor.

La migración incluida es `f9a2c4d6e8b0_flujo_pagos_seguro.py` y fue validada con upgrade, downgrade y upgrade en SQLite local.
