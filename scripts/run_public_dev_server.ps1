# Starts the full local rehearsal stack: local Postgres+PostGIS, the FastAPI
# backend, and a public Cloudflare quick tunnel -- so a teammate on another
# device/network (E's reporting frontend) can hit a real URL.
#
# The tunnel URL is EPHEMERAL: it's a free, account-less "quick tunnel"
# (trycloudflare.com) and gets a NEW random URL every time this script runs.
# Whoever needs the URL (E) has to be told the new one after each restart --
# see the printed URL at the end, or bin/tunnel.log.
#
# Run this from the project root: powershell -ExecutionPolicy Bypass -File scripts\run_public_dev_server.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pgdata = Join-Path $root "bin\pgdata"
$pgctl = Join-Path $root "bin\pgsql\bin\pg_ctl.exe"
$pglog = Join-Path $root "bin\pg.log"
$cloudflared = Join-Path $root "bin\cloudflared.exe"
$tunnelLog = Join-Path $root "bin\tunnel.log"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"

Write-Host "Starting Postgres..."
$pgStatus = & $pgctl -D $pgdata status 2>&1
if ($LASTEXITCODE -ne 0) {
    & $pgctl -D $pgdata -l $pglog start
    Start-Sleep -Seconds 2
} else {
    Write-Host "Postgres already running."
}

Write-Host "Starting FastAPI backend on port 8000..."
Start-Process -FilePath $venvPython -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000" `
    -WorkingDirectory $root -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $root "bin\uvicorn.out.log") `
    -RedirectStandardError (Join-Path $root "bin\uvicorn.err.log")
Start-Sleep -Seconds 3

Write-Host "Starting Cloudflare quick tunnel..."
Start-Process -FilePath $cloudflared -ArgumentList "tunnel", "--url", "http://localhost:8000" `
    -WindowStyle Hidden -RedirectStandardError $tunnelLog
Start-Sleep -Seconds 8

Write-Host ""
Write-Host "=== Public URL (share this with E) ==="
Select-String -Path $tunnelLog -Pattern "https://.*\.trycloudflare\.com" | Select-Object -Last 1
Write-Host ""
Write-Host "Health check once you have the URL: <url>/health"
Write-Host "To stop: scripts\stop_public_dev_server.ps1"
