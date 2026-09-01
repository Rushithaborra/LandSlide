# Stops the FastAPI backend, cloudflared tunnel, and local Postgres started
# by run_public_dev_server.ps1.

$root = Split-Path -Parent $PSScriptRoot
$pgdata = Join-Path $root "bin\pgdata"
$pgctl = Join-Path $root "bin\pgsql\bin\pg_ctl.exe"

Write-Host "Stopping cloudflared..."
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "Stopping uvicorn..."
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object { $_.CommandLine -like "*uvicorn*app.main*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Write-Host "Stopping Postgres..."
& $pgctl -D $pgdata stop -m fast

Write-Host "Stopped."
