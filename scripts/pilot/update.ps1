# Cập nhật bản pilot sang code MỚI NHẤT trong thư mục dự án — dữ liệu người dùng GIỮ NGUYÊN.
# Cách dùng: nhấp đúp file update-pilot.bat ở thư mục gốc dự án.
#
# Làm gì:
#   1. Sao lưu DB (phòng hờ) vào backups\
#   2. Dựng lại image từ code hiện có trong thư mục (kể cả phần chưa commit)
#      và thay container cũ. Dữ liệu nằm trong volume riêng nên không bị đụng tới;
#      nếu code mới có migration, backend tự nâng cấp DB khi khởi động.
#      Dựng lỗi -> container cũ vẫn chạy tiếp, không ai bị ảnh hưởng.
#   3. Chờ hệ thống trả lời, kiểm tra link công khai (Tailscale Funnel).
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..\..")
$compose = @("compose", "-p", "learninghub-pilot", "--env-file", ".env.pilot")

Write-Host ""
Write-Host "==> 1/3 Sao lưu dữ liệu trước khi cập nhật..." -ForegroundColor Cyan
& "$PSScriptRoot\backup.ps1"

Write-Host ""
Write-Host "==> 2/3 Dựng lại từ code hiện tại (vài phút)..." -ForegroundColor Cyan
$commit = (git log -1 --format="%h %s" 2>$null)
if ($commit) { Write-Host "    Commit hiện tại: $commit" }
$dirty = (git status --short 2>$null | Where-Object { $_ -notmatch '\.claude_tmp|backups' })
if ($dirty) { Write-Host "    Lưu ý: có thay đổi CHƯA commit — vẫn được đưa vào bản cập nhật." -ForegroundColor Yellow }
docker @compose up -d --build
if ($LASTEXITCODE -ne 0) {
  Write-Host "CẬP NHẬT THẤT BẠI. Bản cũ vẫn đang chạy, dữ liệu không bị ảnh hưởng." -ForegroundColor Red
  exit 1
}

Write-Host ""
Write-Host "==> 3/3 Kiểm tra hệ thống..." -ForegroundColor Cyan
$ok = $false
for ($i = 0; $i -lt 40; $i++) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8090/health -TimeoutSec 3
    if ($r.StatusCode -eq 200 -and $r.Content -match '"db":"ok"') { $ok = $true; break }
  } catch {}
  Start-Sleep -Seconds 3
}
if (-not $ok) {
  Write-Host "Backend chưa trả lời sau 2 phút. Xem log: docker logs dkt_backend --tail 50" -ForegroundColor Red
  exit 1
}
docker @compose ps --format "table {{.Name}}\t{{.Status}}"
# Bug #2: /health của backend chỉ kiểm DB — ml-serve (PyTorch) chết thì backend vẫn
# "ok" và mọi mastery lặng lẽ rơi về cold-start. Kiểm riêng đường backend -> ml-serve.
$ml = (docker exec dkt_backend curl -fsS -m 30 http://ml-serve:8001/health 2>&1) -join " "
if ($LASTEXITCODE -eq 0) { Write-Host "    DKT (ml-serve): $ml" -ForegroundColor Green }
else { Write-Host "    CANH BAO: backend KHONG goi duoc ml-serve -> DKT khong cham diem. Chay check-dkt.bat de xem chi tiet." -ForegroundColor Red }
$ts = "C:\Program Files\Tailscale\tailscale.exe"
if (Test-Path $ts) { & $ts funnel status }
Write-Host ""
Write-Host "XONG. Bản mới đang chạy, dữ liệu giữ nguyên." -ForegroundColor Green
