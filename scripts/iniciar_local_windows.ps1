$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "El entorno local no existe. Ejecuta primero scripts\configurar_local_windows.ps1."
}
if (-not (Test-Path ".env")) {
    throw "Falta el archivo .env. Ejecuta primero scripts\configurar_local_windows.ps1."
}

Write-Host "NexuStock disponible en http://127.0.0.1:5000" -ForegroundColor Green
& $Python -m flask --app run.py run --host 127.0.0.1 --port 5000 --debug

