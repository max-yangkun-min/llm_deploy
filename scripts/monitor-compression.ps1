# Docker VHDX 压缩进度监控
# 每 30 秒显示一次进度

Write-Host "=== Docker VHDX 压缩进度监控 ===" -ForegroundColor Cyan
Write-Host "按 Ctrl+C 停止监控" -ForegroundColor Yellow
Write-Host ""

$initialFree = (Get-PSDrive C).Free / 1GB
Write-Host "初始 C 盘剩余: $($initialFree.ToString('F2')) GB" -ForegroundColor Green
Write-Host ""

while ($true) {
    $process = Get-Process -Name compact -ErrorAction SilentlyContinue
    if (-not $process) {
        Write-Host "`n✅ 压缩完成！compact.exe 进程已结束。" -ForegroundColor Green
        break
    }

    $currentFree = (Get-PSDrive C).Free / 1GB
    $gained = $currentFree - $initialFree
    $elapsed = (Get-Date) - $process.StartTime

    Clear-Host
    Write-Host "=== Docker VHDX 压缩进度监控 ===" -ForegroundColor Cyan
    Write-Host "按 Ctrl+C 停止监控" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "📊 当前状态:" -ForegroundColor White
    Write-Host "  进程运行时间: $($elapsed.Hours)小时 $($elapsed.Minutes)分钟"
    Write-Host "  C 盘剩余: $($currentFree.ToString('F2')) GB"
    Write-Host "  已释放空间: $($gained.ToString('F2')) GB"
    Write-Host ""
    Write-Host "⏳ 压缩中... (每 30 秒更新)" -ForegroundColor Yellow

    Start-Sleep -Seconds 30
}

# 最终状态
$finalFree = (Get-PSDrive C).Free / 1GB
$totalGained = $finalFree - $initialFree
Write-Host ""
Write-Host "📊 压缩完成总结:" -ForegroundColor Green
Write-Host "  最终 C 盘剩余: $($finalFree.ToString('F2')) GB"
Write-Host "  总计释放空间: $($totalGained.ToString('F2')) GB"
Write-Host ""
Write-Host "✅ 压缩完成！现在可以重启 Docker Desktop。" -ForegroundColor Green
