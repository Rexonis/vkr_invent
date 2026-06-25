$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Frontend = Join-Path $Root "frontend"
$Vite = Join-Path $Frontend "node_modules\vite\bin\vite.js"

$env:VITE_HTTPS = "1"
Set-Location $Frontend
& node.exe $Vite --host 0.0.0.0 --port 5173
