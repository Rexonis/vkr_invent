$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$CaCert = Join-Path $Root ".certs\vkr-dev-ca.crt"

if (-not (Test-Path $CaCert)) {
  throw "CA certificate not found: $CaCert. Run scripts\make-dev-cert.sh first."
}

certutil.exe -user -addstore Root $CaCert
Write-Host "Trusted VKR Local Dev CA for the current Windows user."
Write-Host "Restart your browser, then open https://vkrinvent:5173"
