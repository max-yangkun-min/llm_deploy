<#
.SYNOPSIS
    把项目 CI 注册成 Windows 定时任务,让检查在后台自己跑。

.DESCRIPTION
    只是把「已经跑通的命令」交给任务计划程序,没有任何新逻辑:
    任务动作 = scripts/ci/run-ci.ps1,检查规则仍然只有 tools/ci.py 一份。

    默认注册两个任务:
      llm-ci-daily   每天一次,离线检查(秒级,不联网)
      llm-ci-weekly  每周一次,带 --online(核实厂商页与权威文档链接)

    为什么默认建在当前用户下(而不是 SYSTEM):CI 要读仓库文件、写 output/ci/,
    用当前用户身份跑权限最简单,也不需要提权注册。代价是只在用户登录后才触发;
    需要「未登录也跑」时用 -RunWhetherLoggedOn,那一步要提权。

.PARAMETER Name
    任务名前缀,默认 llm-ci。最终任务名为 <前缀>-daily / <前缀>-weekly。

.PARAMETER DailyAt
    每日任务的触发时间,默认 09:30。

.PARAMETER WeeklyDay
    每周任务的星期,默认 Sunday。

.PARAMETER WeeklyAt
    每周任务的触发时间,默认 10:00。

.PARAMETER RunWhetherLoggedOn
    即使未登录也运行。需要管理员权限,且会要求输入该账户密码。

.PARAMETER Unregister
    删除本脚本创建的两个任务,不做别的清理。

.EXAMPLE
    pwsh -File scripts/ci/register-scheduled-task.ps1
    pwsh -File scripts/ci/register-scheduled-task.ps1 -DailyAt 08:00 -WeeklyDay Monday
    pwsh -File scripts/ci/register-scheduled-task.ps1 -Unregister
#>
[CmdletBinding()]
param(
    [string]$Name = 'llm-ci',
    [string]$DailyAt = '09:30',
    [ValidateSet('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')]
    [string]$WeeklyDay = 'Sunday',
    [string]$WeeklyAt = '10:00',
    [switch]$RunWhetherLoggedOn,
    [switch]$Unregister
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$runner = Join-Path $root 'scripts\ci\run-ci.ps1'
$dailyName = "$Name-daily"
$weeklyName = "$Name-weekly"

if ($Unregister) {
    foreach ($taskName in @($dailyName, $weeklyName)) {
        if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
            Write-Host ("已删除任务:{0}" -f $taskName) -ForegroundColor Yellow
        } else {
            Write-Host ("任务不存在,跳过:{0}" -f $taskName)
        }
    }
    exit 0
}

if (-not (Test-Path -LiteralPath $runner)) {
    throw "找不到 $runner"
}

# 触发前先看 C: 余量:AGENTS.md 规定低于 20 GiB 要停掉会写盘的工作。
# 这里只报告,不阻断——CI 本身是只读的,真正需要拦的是构建和下载。
$freeC = (Get-PSDrive -Name C).Free / 1GB
Write-Host ("C: 可用 {0:N1} GiB" -f $freeC)
if ($freeC -lt 20) {
    Write-Warning ("C: 可用空间低于 20 GiB；CI 只读,可以跑,但不要在此状态下开始镜像/权重相关工作。")
}

$powershellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

function New-CiTask {
    param(
        [string]$TaskName,
        [object]$Trigger,
        [string]$Description,
        [string]$ExtraArguments = ''
    )
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$runner`" $ExtraArguments".Trim()
    $action = New-ScheduledTaskAction -Execute $powershellExe -Argument $arguments -WorkingDirectory $root
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
        -MultipleInstances IgnoreNew
    $principalArgs = @{ UserId = "$env:USERDOMAIN\$env:USERNAME"; LogonType = 'Interactive' }
    if ($RunWhetherLoggedOn) {
        $principalArgs['LogonType'] = 'S4U'
    }
    $principal = New-ScheduledTaskPrincipal @principalArgs

    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $Trigger `
        -Settings $settings -Principal $principal -Description $Description | Out-Null
    Write-Host ("已注册任务:{0}" -f $TaskName) -ForegroundColor Green
}

$dailyTrigger = New-ScheduledTaskTrigger -Daily -At $DailyAt
New-CiTask -TaskName $dailyName -Trigger $dailyTrigger `
    -Description '大模型部署管理台:每日离线 CI(语法/冒烟/实测值/GPU 目录自洽)'

$weeklyTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $WeeklyDay -At $WeeklyAt
# 每周那次多一个 --online:额外核实厂商页与权威文档链接。两个任务共用同一个
# 注册函数,免得两条注册逻辑各写一遍、日后只改一处。
New-CiTask -TaskName $weeklyName -Trigger $weeklyTrigger -ExtraArguments '-Online' `
    -Description '大模型部署管理台:每周联网 CI(额外核实厂商页与权威文档链接)'

Write-Host ''
Write-Host '现在可以这样用:'
Write-Host ("  立即跑一次    : Start-ScheduledTask -TaskName {0}" -f $dailyName)
Write-Host ("  看上次结果    : Get-ScheduledTaskInfo -TaskName {0}" -f $dailyName)
Write-Host ("  手动前台跑    : pwsh -File {0}" -f $runner)
Write-Host ("  取消定时      : pwsh -File {0} -Unregister" -f $PSCommandPath)
Write-Host '  结果留痕      : output/ci/ci-latest.log 与 ci-latest.json'
