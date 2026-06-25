$ErrorActionPreference = "Stop"

# Local host name for the VKR inventory app.
$HostName = "vkrinvent"
$IpAddress = "192.168.157.249"
$HostsPath = Join-Path $env:SystemRoot "System32\drivers\etc\hosts"
$Entry = "$IpAddress $HostName"
$BackupPath = Join-Path (Split-Path $HostsPath) "hosts.vkr-backup"

$Lines = Get-Content -LiteralPath $HostsPath -ErrorAction Stop
$Found = $false
$UpdatedLines = foreach ($Line in $Lines) {
    if ($Line -match "^\s*#") {
        $Line
    } elseif ($Line -match "(^|\s)$HostName(\s|$)") {
        $Found = $true
        $Entry
    } else {
        $Line
    }
}

if (-not $Found) {
    $UpdatedLines += $Entry
}

Copy-Item -LiteralPath $HostsPath -Destination $BackupPath -Force
Set-Content -LiteralPath $HostsPath -Value $UpdatedLines -Encoding ASCII
ipconfig /flushdns | Out-Null

Write-Host "Done: $Entry"
