# Đổi mô hình DKT của pilot sang bản fine-tune trên dữ liệu pilot (27/10), hoặc quay lại bản gốc.
# Cách dùng: nhấp đúp switch-dkt-model.bat (đổi sang bản mới) hoặc rollback-dkt-model.bat (quay lại).
#
# Làm gì:
#   1. Sao lưu DB vào backups\
#   2. Giữ bản gốc: ml\models\dkt_feat_slam_original.pt (chỉ tạo một lần, không bao giờ ghi đè)
#   3. Chép mô hình cần dùng thành ml\models\dkt_feat_best.pt (file ml-serve nạp)
#   4. Đặt ngưỡng cho khớp thang xác suất của mô hình (qua đúng hàm Admin dùng, có kiểm tra)
#   5. Khởi động lại ml-serve + backend (vài giây), kiểm tra cả hai trả lời
#   6. Ghi mốc giờ đổi vào pilot_reports\model_switch.log — dùng để tách dữ liệu
#      "trước" / "sau" khi viết chương thực nghiệm.
# KHÔNG dựng lại image: các thay đổi code chưa commit không bị đưa lên pilot.
param([switch]$Rollback)
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..\..")
$models = "ml\models"
$orig = "$models\dkt_feat_slam_original.pt"
if ($Rollback) {
  $src = $orig; $name = "GỐC (SLAM)"
  # Ngưỡng mặc định ban đầu: vừa sức 0.6-0.8, cần ôn / điểm yếu < 0.6
  $th = @("0.6", "0.8", "0.6", "0.6")
} else {
  $src = "$models\dkt_feat_pilot_ft.pt"; $name = "FINE-TUNE PILOT (27/10)"
  # Dự đoán đã calibrate của bản mới nằm khoảng 0.82-0.91 (trắc nghiệm 4 đáp án):
  # vừa sức = khoảng 1/3 từ khó nhất 0.82-0.87; cần ôn / điểm yếu < 0.80.
  $th = @("0.82", "0.87", "0.8", "0.8")
}

Write-Host ""
Write-Host "==> Đổi mô hình DKT sang: $name" -ForegroundColor Cyan
Write-Host "==> 1/5 Sao lưu DB" -ForegroundColor Cyan
& "$PSScriptRoot\backup.ps1"

Write-Host "==> 2/5 Giữ bản gốc + chép mô hình" -ForegroundColor Cyan
if (-not (Test-Path $orig)) {
  Copy-Item "$models\dkt_feat_best.pt" $orig
  Write-Host "    Đã lưu bản gốc: $orig"
}
if (-not (Test-Path $src)) { Write-Host "Không thấy $src. Chưa đổi gì." -ForegroundColor Red; exit 1 }
Copy-Item $src "$models\dkt_feat_best.pt" -Force
Write-Host "    ml\models\dkt_feat_best.pt <- $src"

Write-Host "==> 3/5 Đặt ngưỡng: vừa sức $($th[0])-$($th[1]), cần ôn < $($th[2]), điểm yếu < $($th[3])" -ForegroundColor Cyan
$py = @"
import sys
from app.core.database import SessionLocal
from app.services import config_service
keys = ["band_low", "band_high", "review_threshold", "weak_mastery_threshold"]
vals = dict(zip(keys, map(float, sys.argv[1:5])))
with SessionLocal() as db:
    # dat ca 4 gia tri trong MOT lan goi: rang buoc band_low < band_high kiem tren gia tri moi
    changes = config_service.set_values(db, vals)
print("    " + ("; ".join(changes) if changes else "nguong da dung san, khong doi"))
"@
$py | docker exec -i -e PYTHONIOENCODING=utf-8 dkt_backend python - $th[0] $th[1] $th[2] $th[3]
if ($LASTEXITCODE -ne 0) { Write-Host "Đặt ngưỡng lỗi (mô hình đã chép). Chạy lại file này." -ForegroundColor Red; exit 1 }

Write-Host "==> 4/5 Khởi động lại ml-serve + backend" -ForegroundColor Cyan
docker restart dkt_ml_serve dkt_backend | Out-Null
$ok = $false
for ($i = 0; $i -lt 40; $i++) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8090/health -TimeoutSec 3
    if ($r.StatusCode -eq 200 -and $r.Content -match '"db":"ok"') { $ok = $true; break }
  } catch {}
  Start-Sleep -Seconds 3
}
if (-not $ok) { Write-Host "Backend chưa trả lời sau 2 phút. Xem: docker logs dkt_backend --tail 50" -ForegroundColor Red; exit 1 }
$ml = ""
$mlOk = $false
for ($i = 0; $i -lt 20; $i++) {
  # ml-serve cần vài giây để nạp PyTorch: lỗi ở các lần đầu là bình thường, không dừng script
  try {
    $ml = (docker exec dkt_backend curl -fsS -m 30 http://ml-serve:8001/health 2>$null) -join " "
    if ($LASTEXITCODE -eq 0 -and $ml) { $mlOk = $true; break }
  } catch {}
  Start-Sleep -Seconds 3
}
if (-not $mlOk) { Write-Host "CẢNH BÁO: ml-serve chưa trả lời -> DKT không chấm. Chạy check-dkt.bat." -ForegroundColor Red; exit 1 }
Write-Host "    DKT (ml-serve): $ml" -ForegroundColor Green

Write-Host "==> 5/5 Ghi mốc giờ đổi mô hình" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path pilot_reports | Out-Null
$line = "{0}`t{1}`tnguong={2}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz"), $name, ($th -join "/")
Add-Content -Path "pilot_reports\model_switch.log" -Value $line -Encoding UTF8
Write-Host "    $line"
Write-Host ""
Write-Host "XONG. Pilot đang dùng mô hình: $name" -ForegroundColor Green
