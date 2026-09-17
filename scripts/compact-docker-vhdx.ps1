# Docker VHDX 压缩脚本
# 使用前请先：
# 1. 手动停止 Docker Desktop
# 2. 以管理员身份运行此脚本

Write-Host "=== Docker VHDX 压缩工具 ===" -ForegroundColor Cyan
Write-Host ""

# 检查是否以管理员身份运行
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "❌ 请以管理员身份运行此脚本" -ForegroundColor Red
    exit 1
}

# VHDX 路径
$vhdxPath = "C:\Users\11984\AppData\Local\Docker\wsl\disk\docker_data.vhdx"

# 检查 VHDX 是否存在
if (-not (Test-Path $vhdxPath)) {
    Write-Host "❌ 找不到 Docker VHDX 文件: $vhdxPath" -ForegroundColor Red
    exit 1
}

# 显示当前状态
$currentSize = (Get-Item $vhdxPath).Length / 1GB
Write-Host "📊 当前 VHDX 大小: $($currentSize.ToString('F2')) GB" -ForegroundColor Yellow
Write-Host ""

# 确认 Docker Desktop 已停止
Write-Host "⚠️  请确认 Docker Desktop 已完全停止！" -ForegroundColor Yellow
Write-Host "   在 Docker Desktop 界面点击 'Quit Docker Desktop' 后按回车继续..."
Read-Host

# 关闭 WSL
Write-Host "🔄 关闭 WSL..." -ForegroundColor Cyan
wsl --shutdown
Start-Sleep -Seconds 3

# 压缩 VHDX
Write-Host "🔄 压缩 VHDX（这可能需要几分钟）..." -ForegroundColor Cyan
try {
    & compact /C /F "$vhdxPath" | Out-Null
    Write-Host "✅ VHDX 压缩完成" -ForegroundColor Green
} catch {
    Write-Host "❌ 压缩失败: $_" -ForegroundColor Red
    exit 1
}

# 显示新大小
$newSize = (Get-Item $vhdxPath).Length / 1GB
$saved = $currentSize - $newSize
Write-Host ""
Write-Host "📊 压缩后 VHDX 大小: $($newSize.ToString('F2')) GB" -ForegroundColor Green
Write-Host "💾 释放空间: $($saved.ToString('F2')) GB" -ForegroundColor Green

Write-Host ""
Write-Host "✅ 压缩完成！现在可以重启 Docker Desktop。" -ForegroundColor Green
