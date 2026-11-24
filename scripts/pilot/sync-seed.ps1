# Đồng bộ NỘI DUNG bộ từ nền (nghĩa / từ loại / ví dụ) vào DB pilot đang chạy — bug #9.
# Cách dùng: nhấp đúp file sync-data-pilot.bat ở thư mục gốc dự án.
#
# Vì sao phải dựng lại image TRƯỚC: Dockerfile COPY data/ và app/ vào image, nên
# container đang chạy vẫn giữ vocab_seed_core.json CŨ. Chạy sync_seed_content ngay
# thì nó đọc file cũ -> "không có gì thay đổi". Thứ tự đúng:
#   1. update.ps1  : sao lưu DB + dựng lại image từ code/dữ liệu mới (dữ liệu người dùng giữ nguyên)
#   2. chạy thử    : in ra số trường sẽ đổi, CHƯA ghi gì
#   3. hỏi xác nhận -> ghi thật (--apply). Cập nhật tại chỗ, giữ Interaction/mastery/lịch ôn.
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..\..")

Write-Host ""
Write-Host "==> Bước 1/3: Sao lưu + dựng lại bản pilot với dữ liệu mới" -ForegroundColor Cyan
& "$PSScriptRoot\update.ps1"
# Không dựa vào $LASTEXITCODE: update.ps1 kết thúc bằng lệnh tailscale/ml-serve, mã
# thoát của chúng không nói gì về việc dựng image. Kiểm thẳng: backend sống + DB ok.
$ok = $false
try {
  $r = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8090/health -TimeoutSec 5
  $ok = ($r.StatusCode -eq 200 -and $r.Content -match '"db":"ok"')
} catch {}
if (-not $ok) {
  Write-Host "Dừng lại: backend chưa chạy sau bước cập nhật (xem thông báo đỏ ở trên). Chưa đụng gì tới dữ liệu." -ForegroundColor Red
  exit 1
}

Write-Host ""
Write-Host "==> Bước 2/3: Chạy thử đồng bộ (chưa ghi gì)" -ForegroundColor Cyan
docker exec -e PYTHONIOENCODING=utf-8 dkt_backend python -m app.scripts.sync_seed_content
if ($LASTEXITCODE -ne 0) {
  Write-Host "Chạy thử lỗi. Xem log: docker logs dkt_backend --tail 50" -ForegroundColor Red
  exit 1
}

Write-Host ""
$ans = Read-Host "==> Bước 3/3: Ghi thật các thay đổi trên vào DB? Gõ Y rồi Enter (Enter trống = thôi)"
if ($ans -notmatch '^[Yy]') {
  Write-Host "Đã bỏ qua, DB không đổi. Chạy lại file này bất cứ lúc nào." -ForegroundColor Yellow
  exit 0
}
docker exec -e PYTHONIOENCODING=utf-8 dkt_backend python -m app.scripts.sync_seed_content --apply
if ($LASTEXITCODE -ne 0) {
  Write-Host "Ghi lỗi. DB đã được sao lưu ở bước 1 trong thư mục backups\." -ForegroundColor Red
  exit 1
}
Write-Host ""
Write-Host "XONG. Tải lại trang web (Ctrl+F5) để thấy nghĩa mới." -ForegroundColor Green
