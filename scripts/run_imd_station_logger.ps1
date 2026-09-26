# Wrapper for Windows Task Scheduler: runs one IMD station poll and appends its
# output, with a timestamp, to a log file -- so a gap (e.g. the IP-bound key
# breaking after the ISP rotates the address, which has happened several times)
# is visible later instead of silently missing data for weeks.
$root = "C:\Users\kilar\Landslide ai"
$log = Join-Path $root "data\interim\imd_station_logger.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
Add-Content -Path $log -Value "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" -Encoding utf8
& (Join-Path $root ".venv\Scripts\python.exe") (Join-Path $root "scripts\imd_station_logger.py") 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
