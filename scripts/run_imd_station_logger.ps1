# Wrapper for Windows Task Scheduler: runs one IMD station poll and appends its
# output, with a timestamp, to a log file -- so a gap (e.g. the IP-bound key
# breaking after the ISP rotates the address, which has happened several times)
# is visible later instead of silently missing data for weeks.
$root = "C:\Users\kilar\Landslide ai"
# app/config.py reads .env by relative path, and Task Scheduler starts this in
# C:\Windows\System32 -- without this, every scheduled run fails "not configured".
Set-Location $root
$log = Join-Path $root "data\interim\imd_station_logger.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
Add-Content -Path $log -Value "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" -Encoding utf8
& (Join-Path $root ".venv\Scripts\python.exe") (Join-Path $root "scripts\imd_station_logger.py") 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
# Pass the logger's exit code on. Without this the task always ended "0 = success" -- even
# through 24 days of IMD HTTP 403s (the IP-bound key rejecting a changed public IP) -- so Task
# Scheduler's "Last Run Result" could never show a failure.
$code = $LASTEXITCODE
if ($code -ne 0) {
    Add-Content -Path $log -Value "=== FAILED (exit code $code). An IMD HTTP 403 usually means this machine's public IP changed: see docs/imd_station_logging.md ===" -Encoding utf8
}
exit $code
