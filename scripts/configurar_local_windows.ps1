$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function New-UrlSafeSecret([int]$Bytes = 48) {
    $buffer = New-Object byte[] $Bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($buffer)
    return [Convert]::ToBase64String($buffer).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

$PythonLauncher = $null
$PythonArguments = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonLauncher = "py"
    $PythonArguments = @("-3.12")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonLauncher = "python"
} else {
    throw "Python no está instalado. Instala Python 3.12 de 64 bits."
}

$PythonVersion = & $PythonLauncher @PythonArguments -c "import sys; print('.'.join(map(str, sys.version_info[:2])))" 2>$null
if ($LASTEXITCODE -ne 0 -or $PythonVersion -ne "3.12") {
    throw "NexuStock requiere Python 3.12. Instálalo antes de continuar."
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $PythonLauncher @PythonArguments -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        throw "No fue posible crear .venv. Elimina la carpeta .venv incompleta y vuelve a ejecutar este script."
    }
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt
& $Python -m pip install -r requirements-dev.txt

if (-not (Test-Path ".env")) {
    $SecretKey = New-UrlSafeSecret 64
    $RateLimitSecret = New-UrlSafeSecret 48
    $TwoFactorKey = New-UrlSafeSecret 48
    $EnvContent = @"
FLASK_ENV=desarrollo
SECRET_KEY=$SecretKey
DATABASE_URL=sqlite:///nexustock-local.db
DATABASE_POOL_RECYCLE=300
BASE_URL=http://127.0.0.1:5000
REQUIRE_EMAIL_VERIFICATION=false
MAIL_SERVER=localhost
MAIL_PORT=1025
MAIL_USE_TLS=false
MAIL_DEFAULT_SENDER=no-responder@nexustock.local
SOPORTE_EMAIL=soporte@nexustock.local
WEBPAY_ENV=integration
MERCADOPAGO_ENV=sandbox
OPENAI_MODEL=gpt-5.6-luna
IA_LIMITE_DIARIO_EMPRESA=100
IA_TIMEOUT_SEGUNDOS=30
IMPORTACION_MAX_BYTES=10485760
IMPORTACION_MAX_FILAS=2000
LIMITE_SOLICITUDES_SECRET=$RateLimitSecret
TWO_FACTOR_ENCRYPTION_KEYS=$TwoFactorKey
TRUSTED_HOSTS=localhost,127.0.0.1
TRUST_PROXY_HEADERS=false
"@
    Set-Content -Path ".env" -Value $EnvContent -Encoding UTF8
    Write-Host "Archivo .env local creado con secretos aleatorios." -ForegroundColor Green
} else {
    Write-Host "Se conserva el archivo .env existente." -ForegroundColor Yellow
}

& $Python -m flask --app run.py db upgrade
& $Python -m flask --app run.py seed-planes
& $Python -m flask --app run.py db current
& $Python -m pytest -q

Write-Host ""
Write-Host "NexuStock quedó configurado localmente." -ForegroundColor Green
Write-Host "Inícialo con: powershell -ExecutionPolicy Bypass -File scripts\iniciar_local_windows.ps1"
