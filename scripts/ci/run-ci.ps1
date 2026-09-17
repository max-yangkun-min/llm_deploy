<#
.SYNOPSIS
    跑项目持续集成门禁,并把结果留痕到 output/ci/。

.DESCRIPTION
    这个脚本只做三件事:把环境准备好、调用 tools/ci.py、把输出写进日志文件。
    检查逻辑全部在 tools/ci.py 里,这样命令行、定时任务和 CI 服务跑的是同一套
    判定,不会出现「本地过了、CI 挂了」这种两套规则的问题。

    为什么要在开头清空代理:本机环境变量里带着 HTTP_PROXY 时,
    --online 模式的厂商页与文档核实会走代理,拿到的可能是缓存或错误页,
    于是核实结果不可信。清空后直连。

.PARAMETER Online
    额外联网核实厂商产品页与权威文档链接。慢(分钟级),适合每天或每周一次。

.PARAMETER Quiet
    不打印检查明细,只在日志里留全量输出。

.EXAMPLE
    pwsh -File scripts/ci/run-ci.ps1
    pwsh -File scripts/ci/run-ci.ps1 -Online
#>
[CmdletBinding()]
param(
    [switch]$Online,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'

# 仓库根目录 = 本脚本上溯两级。
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath $root

# 清空代理,避免 --online 拿到代理缓存页。
foreach ($name in 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY',
                  'http_proxy', 'https_proxy', 'all_proxy') {
    Set-Item -Path "Env:$name" -Value '' -ErrorAction SilentlyContinue
}
$env:PYTHONIOENCODING = 'utf-8'
# PowerShell 5.1 默认用 ANSI 代码页解码子进程输出,而 python 按 UTF-8 写。
# 不对齐这两端,日志里的中文会变成「閫氳繃」这样的乱码。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$logDir = Join-Path $root 'output\ci'
if (-not (Test-Path -LiteralPath $logDir)) {
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
}
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logPath = Join-Path $logDir "ci-$stamp.log"
$reportPath = Join-Path $logDir "ci-$stamp.json"
# 最新一次的结果固定放在这两个名字下,免得到处找时间戳。
$latestLog = Join-Path $logDir 'ci-latest.log'
$latestReport = Join-Path $logDir 'ci-latest.json'

$ciArgs = @('tools/ci.py', '--json', $reportPath)
if ($Online) { $ciArgs += '--online' }
if ($Quiet) { $ciArgs += '--quiet' }

$output = & python @ciArgs 2>&1
$code = $LASTEXITCODE
$output | Out-File -LiteralPath $logPath -Encoding utf8
# 用 -LiteralPath 复制文件本身。写成 `$output | Copy-Item` 会把每一行文本
# 当成路径去解析,于是报「找不到名为 项目 CI · ... 的驱动器」。
Copy-Item -LiteralPath $logPath -Destination $latestLog -Force
if (Test-Path -LiteralPath $reportPath) {
    Copy-Item -LiteralPath $reportPath -Destination $latestReport -Force
}

if (-not $Quiet) { $output | Write-Host }

# 「跳过」和「通过」是两回事,单独提出来,不能让它看起来像跑过了。
$skipped = @($output | Select-String -Pattern '^\s+跳过:')
if ($skipped.Count -gt 0) {
    Write-Host ''
    Write-Host ("注意:有 {0} 项被跳过,不算通过。" -f $skipped.Count) -ForegroundColor Yellow
}

Write-Host ("日志:{0}" -f $logPath)
if ($code -eq 0) {
    Write-Host 'CI 全部通过。' -ForegroundColor Green
} else {
    Write-Host ("CI 失败 {0} 项。" -f $code) -ForegroundColor Red
}
exit $code
