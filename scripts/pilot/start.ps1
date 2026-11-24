# Bật lại bản pilot (sau khi tắt máy / tắt Docker). Thường KHÔNG cần: container và
# Tailscale Funnel đều tự bật lại khi máy khởi động. Dùng khi lần đầu dựng (-Build)
# hoặc khi link không vào được.
#   powershell -ExecutionPolicy Bypass -File scripts\pilot\start.ps1 [-Build]
param([switch]$Build)
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..\..")
if (-not (Test-Path ".env.pilot")) { throw "Thiếu file .env.pilot (copy từ .env.pilot.example)" }

$dc = @("compose", "-p", "learninghub-pilot", "--env-file", ".env.pilot", "up", "-d")
if ($Build) { $dc += "--build" }
Write-Host "==> Khởi động các container..." -ForegroundColor Cyan
docker @dc
if ($LASTEXITCODE -ne 0) { throw "docker compose lỗi" }

Write-Host "==> Chờ backend sẵn sàng..." -ForegroundColor Cyan
for ($i = 0; $i -lt 60; $i++) {
  try { if ((Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8090/health -TimeoutSec 3).StatusCode -eq 200) { break } } catch {}
  Start-Sleep -Seconds 3
}

# Link công khai cố định qua Tailscale Funnel (chạy nền, tự bật lại khi khởi động máy)
$ts = "C:\Program Files\Tailscale\tailscale.exe"
& $ts funnel --bg http://127.0.0.1:8090
& $ts funnel status
Write-Host "XONG." -ForegroundColor Green
