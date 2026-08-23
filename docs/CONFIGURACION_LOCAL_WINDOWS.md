# Configuración local de NexuStock en Windows

## Requisito

Instala Python 3.12 de 64 bits y activa la opción para agregar Python al PATH.
No instales todavía credenciales productivas de Webpay, Mercado Pago o DTE.

## Configuración automática

Abre PowerShell dentro de la carpeta del proyecto y ejecuta:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\configurar_local_windows.ps1
```

El script crea `.venv`, instala dependencias, genera secretos aleatorios en
`.env`, crea una base SQLite local, aplica todas las migraciones, carga los
planes y ejecuta las pruebas.

## Iniciar

```powershell
.\scripts\iniciar_local_windows.ps1
```

Abre `http://127.0.0.1:5000`. El archivo `.env` y la base local están excluidos
del paquete y del control de versiones.

## Crear el propietario global

En otra ventana de PowerShell, con el servidor detenido o activo:

```powershell
.\.venv\Scripts\python.exe -m flask --app run.py crear-super-admin
```

Usa una contraseña única de al menos 12 caracteres. Después de ingresar, activa
2FA en la sección de seguridad.

## Paso PostgreSQL antes de Render

SQLite sirve para validar la interfaz y los flujos. Antes de publicar se debe
instalar PostgreSQL 16, crear una base `nexustock_local` y reemplazar en `.env`:

```dotenv
DATABASE_URL=postgresql://nexustock:CONTRASENA@localhost:5432/nexustock_local
```

Después ejecuta nuevamente:

```powershell
.\.venv\Scripts\python.exe -m flask --app run.py db upgrade
.\.venv\Scripts\python.exe -m flask --app run.py seed-planes
.\.venv\Scripts\python.exe -m pytest -q
```

No copies la base SQLite a PostgreSQL ni uses `db.create_all()`. PostgreSQL debe
crearse mediante Alembic desde una base vacía.
