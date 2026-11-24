# Kiểm tra service DKT (PyTorch) của bản pilot — bug #2.
# Cách dùng: nhấp đúp check-dkt.bat ở thư mục gốc dự án.
# Kết quả ghi ra pilot_reports\dkt-check.txt để Claude đọc được.
$ErrorActionPreference = "Continue"
Set-Location (Resolve-Path "$PSScriptRoot\..\..")
$out = "pilot_reports\dkt-check.txt"
$compose = @("compose", "-p", "learninghub-pilot", "--env-file", ".env.pilot")

function Section($title, [scriptblock]$cmd) {
  "`n===== $title =====" | Out-File $out -Append -Encoding utf8
  try { & $cmd 2>&1 | Out-String -Width 200 | Out-File $out -Append -Encoding utf8 }
  catch { "LOI: $_" | Out-File $out -Append -Encoding utf8 }
}

"Kiem tra DKT luc $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File $out -Encoding utf8
Section "Tat ca container dang co" { docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Label `"com.docker.compose.project`"}}" }
Section "Container cua project pilot" { docker @compose ps -a }
Section "ml-serve /health tu trong backend (duong backend that su goi)" {
  docker exec dkt_backend curl -sS -m 20 http://ml-serve:8001/health
}
Section "ml-serve /predict thu 1 tu" {
  docker exec dkt_backend curl -sS -m 30 -X POST http://ml-serve:8001/predict -H "Content-Type: application/json" -d '{\"history\":[[\"apple\",1]],\"targets\":[\"book\"],\"pos\":{},\"history_formats\":[\"quiz\"],\"target_format\":\"quiz\"}'
}
Section "File trong ml\models va ml\data\processed tren may" { Get-ChildItem ml\models, ml\data\processed | Select-Object Name, Length }
Section "File ml-serve nhin thay trong container" { docker exec dkt_ml_serve ls -la /app/models /app/data/processed }
Section "Phien ban torch trong container" { docker exec dkt_ml_serve python -c "import torch,sys; print(sys.version); print(torch.__version__)" }
Section "Log ml-serve (80 dong cuoi)" { docker logs dkt_ml_serve --tail 80 }
Section "Log backend lien quan DKT" { docker logs dkt_backend --tail 400 2>&1 | Select-String -Pattern "DKT|ml-serve|predict" | Select-Object -Last 40 }

Write-Host "Xong. Ket qua o $out" -ForegroundColor Green
