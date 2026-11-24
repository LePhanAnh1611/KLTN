# Sao lưu DB pilot ra thư mục backups\ (đặt Task Scheduler chạy mỗi ngày).
#   .\scripts\pilot\backup.ps1
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..\..")
$envs = @{}
Get-Content ".env.pilot" | Where-Object { $_ -match "^\s*([A-Z_]+)=(.*)$" } | ForEach-Object { $envs[$Matches[1]] = $Matches[2] }
New-Item -ItemType Directory -Force -Path backups | Out-Null
$file = "backups\pilot_{0}.dump" -f (Get-Date -Format "yyyy-MM-dd_HHmm")
docker exec dkt_postgres pg_dump -U $envs["POSTGRES_USER"] -Fc $envs["POSTGRES_DB"] -f /tmp/pilot.dump
docker cp dkt_postgres:/tmp/pilot.dump $file
Write-Host "Đã sao lưu: $file ($((Get-Item $file).Length) bytes)"
