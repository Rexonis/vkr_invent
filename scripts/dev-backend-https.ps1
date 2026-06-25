$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Cert = Join-Path $Root ".certs\vkr-dev.crt"
$Key = Join-Path $Root ".certs\vkr-dev.key"

$env:DJANGO_HTTPS = "1"
& $Python -m uvicorn config.asgi:application `
  --app-dir (Join-Path $Root "backend") `
  --host 0.0.0.0 `
  --port 5500 `
  --ssl-certfile $Cert `
  --ssl-keyfile $Key
