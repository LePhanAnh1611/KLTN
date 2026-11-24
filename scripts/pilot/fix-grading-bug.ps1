# Sửa triệt để dữ liệu bị chấm sai trong sự cố 26/10 (18:00) -> 27/10 (08:00:20) trên DB pilot.
# Cách dùng: nhấp đúp file fix-grading-bug-pilot.bat ở thư mục gốc dự án.
#
# KHÔNG dựng lại image (thư mục đang có thay đổi chưa commit, dựng lại sẽ đưa cả
# chúng lên pilot). Chỉ chép ĐÚNG một file script vào container đang chạy:
#   1. sao lưu DB vào backups\
#   2. chép backend\app\scripts\fix_grading_bug_20261026.py vào container
#   3. chạy thử (chưa ghi gì) -> in số lượt sẽ sửa / loại
#   4. hỏi xác nhận -> ghi thật (--apply), trong MỘT giao dịch
# Chạy lại an toàn: lần sau không đổi gì nữa.
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..\..")
$until = "2026-10-27T08:00:20+07:00"
$script = "backend\app\scripts\fix_grading_bug_20261026.py"

Write-Host ""
Write-Host "==> Bước 1/4: Sao lưu DB" -ForegroundColor Cyan
& "$PSScriptRoot\backup.ps1"

Write-Host ""
Write-Host "==> Bước 2/4: Chép script sửa lỗi vào container backend" -ForegroundColor Cyan
docker cp $script dkt_backend:/app/app/scripts/fix_grading_bug_20261026.py
if ($LASTEXITCODE -ne 0) {
  Write-Host "Không chép được. Pilot có đang chạy không? (docker ps). Chưa đụng gì tới dữ liệu." -ForegroundColor Red
  exit 1
}

Write-Host ""
Write-Host "==> Bước 3/4: Chạy thử (chưa ghi gì)" -ForegroundColor Cyan
docker exec -e PYTHONIOENCODING=utf-8 dkt_backend python -m app.scripts.fix_grading_bug_20261026 --until $until
if ($LASTEXITCODE -ne 0) {
  Write-Host "Chạy thử lỗi. Xem log: docker logs dkt_backend --tail 50. Chưa đụng gì tới dữ liệu." -ForegroundColor Red
  exit 1
}

Write-Host ""
$ans = Read-Host "==> Bước 4/4: Ghi thật các thay đổi trên vào DB? Gõ Y rồi Enter (Enter trống = thôi)"
if ($ans -notmatch '^[Yy]') {
  Write-Host "Đã bỏ qua, DB không đổi. Chạy lại file này bất cứ lúc nào." -ForegroundColor Yellow
  exit 0
}
docker exec -e PYTHONIOENCODING=utf-8 dkt_backend python -m app.scripts.fix_grading_bug_20261026 --until $until --apply
if ($LASTEXITCODE -ne 0) {
  Write-Host "Ghi lỗi -> giao dịch đã hủy, DB không đổi. Bản sao lưu ở bước 1 nằm trong backups\." -ForegroundColor Red
  exit 1
}
Write-Host ""
Write-Host "XONG. Dòng 'Mastery tính lại' phải có số lớn; nếu 'DKT không chấm được' gần bằng tổng thì chạy check-dkt.bat rồi chạy lại file này." -ForegroundColor Green
