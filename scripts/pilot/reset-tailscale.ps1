# Lam lai Tailscale Funnel cho ban pilot (giu nguyen ten may -> link ts.net khong doi)
# va ghi chan doan ra pilot_reports\tailscale-reset.log. Chay qua reset-tailscale.bat.
$ErrorActionPreference = "Continue"
Set-Location (Resolve-Path "$PSScriptRoot\..\..")
$log = Join-Path (Get-Location) "pilot_reports\tailscale-reset.log"
Start-Transcript -Path $log -Force | Out-Null
$ts = "C:\Program Files\Tailscale\tailscale.exe"
function Step($m) { Write-Host ""; Write-Host "==> $m" -ForegroundColor Cyan }

Step "0. Truoc khi lam lai"
& $ts status
& $ts funnel status

Step "1. Xoa cau hinh Funnel/Serve cu"
& $ts serve reset

Step "2. Khoi dong lai dich vu Tailscale"
Restart-Service Tailscale -Force
Start-Sleep -Seconds 20

Step "3. Bat lai Funnel -> http://127.0.0.1:8090"
& $ts funnel --bg http://127.0.0.1:8090
Start-Sleep -Seconds 10

Step "4. Trang thai sau khi lam lai"
& $ts status
& $ts funnel status

Step "5. Chan doan mang"
& $ts netcheck
Write-Host "--- DNS derp3f"
Resolve-DnsName derp3f.tailscale.com -ErrorAction Continue | Format-Table -AutoSize | Out-String | Write-Host
foreach ($u in "https://derp3f.tailscale.com/", "https://login.tailscale.com/", "https://www.google.com/") {
  Write-Host "--- curl $u"
  cmd /c "curl.exe -sv --max-time 15 $u -o NUL 2>&1" | Select-String -Pattern "Trying|Connected|issuer|subject|SSL|error|timed out|reset|HTTP/" | ForEach-Object { Write-Host $_.Line }
}
Write-Host "--- Card mang dang dung"
Get-NetRoute -DestinationPrefix 0.0.0.0/0 | Select-Object InterfaceAlias, NextHop, RouteMetric | Format-Table -AutoSize | Out-String | Write-Host
Get-NetConnectionProfile | Select-Object InterfaceAlias, Name | Format-Table -AutoSize | Out-String | Write-Host
Write-Host "--- App local"
try { (Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8090/ -TimeoutSec 5).StatusCode } catch { Write-Host "LOI: $_" }

Stop-Transcript | Out-Null
Write-Host ""
Write-Host "XONG. Ket qua da ghi vao pilot_reports\tailscale-reset.log - bao Claude doc." -ForegroundColor Green
