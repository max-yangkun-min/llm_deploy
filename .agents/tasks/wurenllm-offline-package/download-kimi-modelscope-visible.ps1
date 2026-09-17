$ErrorActionPreference = 'Stop'

$destination = 'E:\wurenllm\kimi-k2.6\models\Kimi-K2.6'
$logDirectory = 'E:\llm_models\kimi-k2.6-download'
$statusLog = Join-Path $logDirectory 'modelscope-status.log'
$curl = 'C:\Windows\System32\curl.exe'
$baseUrl = 'https://modelscope.cn/models/moonshotai/Kimi-K2.6/resolve/master'
$maxParallel = 8

$Host.UI.RawUI.WindowTitle = 'Kimi-K2.6 - ModelScope IPv4 accelerated download'
New-Item -ItemType Directory -Force -Path $destination, $logDirectory | Out-Null

function Write-Status {
    param([string]$Message)
    $line = "$(Get-Date -Format s) $Message"
    Write-Host $line -ForegroundColor Cyan
    $line | Add-Content -LiteralPath $statusLog -Encoding UTF8
}

function Get-ExpectedSize {
    param([int]$Index)
    if ($Index -eq 1) { return [int64]995001888 }
    if ($Index -le 10) { return [int64]9809047464 }
    if ($Index -le 61) { return [int64]9809050936 }
    if ($Index -eq 62) { return [int64]4697635160 }
    if ($Index -eq 63) { return [int64]108556344 }
    return [int64]833769904
}

function Convert-CurlRateToBytes {
    param([string]$Text)
    if ($Text -notmatch '^([0-9.]+)([kMGT]?)$') { return [double]0 }
    $value = [double]$Matches[1]
    $multiplier = switch ($Matches[2]) {
        'k' { 1KB }
        'M' { 1MB }
        'G' { 1GB }
        'T' { 1TB }
        default { 1 }
    }
    return $value * $multiplier
}

$items = @()
for ($index = 1; $index -le 64; $index++) {
    $name = 'model-{0:D5}-of-000064.safetensors' -f $index
    $items += [pscustomobject]@{
        Index = $index
        Name = $name
        Size = Get-ExpectedSize -Index $index
        Final = Join-Path $destination $name
        Part = Join-Path $destination ($name + '.modelscope.part')
        Url = "$baseUrl/$name"
    }
}

$queue = New-Object System.Collections.Queue
foreach ($item in $items) {
    if ((Test-Path -LiteralPath $item.Final) -and
        ((Get-Item -LiteralPath $item.Final).Length -eq $item.Size)) {
        continue
    }

    if (Test-Path -LiteralPath $item.Final) {
        if (-not (Test-Path -LiteralPath $item.Part)) {
            Move-Item -LiteralPath $item.Final -Destination $item.Part
        } else {
            throw "Both an invalid final file and a part file exist for $($item.Name)"
        }
    }
    if (Test-Path -LiteralPath $item.Part) {
        $partLength = (Get-Item -LiteralPath $item.Part).Length
        if ($partLength -gt $item.Size) {
            throw "Oversized part file requires manual inspection: $($item.Part)"
        }
        if ($partLength -eq $item.Size) {
            Move-Item -LiteralPath $item.Part -Destination $item.Final -Force
            continue
        }
    }
    $queue.Enqueue($item)
}

$alreadyComplete = $items.Count - $queue.Count
Write-Host ''
Write-Host 'Kimi-K2.6 ModelScope accelerated downloader' -ForegroundColor Green
Write-Host 'Source:      ModelScope official moonshotai/Kimi-K2.6 (master)'
Write-Host 'Validation:  shard names, sizes and SHA-256 match the pinned HF artifact'
Write-Host "Transport:   forced IPv4, $maxParallel concurrent resumable curl transfers"
Write-Host "Destination: $destination"
Write-Host "Status log:  $statusLog"
Write-Host "Existing:    $alreadyComplete / 64 shards reused"
Write-Host ''
Write-Status "START source=modelscope ipv4=true parallel=$maxParallel reused=$alreadyComplete remaining=$($queue.Count)"

$active = @{}
$completedThisRun = 0
$lastReport = Get-Date

while (($queue.Count -gt 0) -or ($active.Count -gt 0)) {
    foreach ($processId in @($active.Keys)) {
        $entry = $active[$processId]
        if (-not $entry.Process.HasExited) { continue }

        $exitCode = $entry.Process.ExitCode
        $partOkay = (Test-Path -LiteralPath $entry.Item.Part) -and
            ((Get-Item -LiteralPath $entry.Item.Part).Length -eq $entry.Item.Size)
        if ($partOkay) {
            Move-Item -LiteralPath $entry.Item.Part -Destination $entry.Item.Final -Force
            $completedThisRun++
            Write-Status "COMPLETE file=$($entry.Item.Name) bytes=$($entry.Item.Size) curl_exit=$exitCode"
        } else {
            $partBytes = if (Test-Path -LiteralPath $entry.Item.Part) {
                (Get-Item -LiteralPath $entry.Item.Part).Length
            } else { 0 }
            Write-Status "RETRY file=$($entry.Item.Name) exit=$exitCode part_bytes=$partBytes"
            $queue.Enqueue($entry.Item)
        }
        $entry.Process.Dispose()
        $active.Remove($processId)
    }

    while (($active.Count -lt $maxParallel) -and ($queue.Count -gt 0)) {
        $item = $queue.Dequeue()
        $progressLog = Join-Path $logDirectory ($item.Name + '.curl.log')
        $arguments = @(
            '--noproxy', '*',
            '-4', '-L', '--fail',
            '--retry', '5', '--retry-delay', '5', '--retry-all-errors',
            '--connect-timeout', '20',
            '--speed-limit', '1048576', '--speed-time', '120',
            '--continue-at', '-',
            '--output', $item.Part,
            $item.Url
        )
        $process = Start-Process -FilePath $curl -ArgumentList $arguments `
            -NoNewWindow -PassThru -RedirectStandardError $progressLog
        $initialBytes = if (Test-Path -LiteralPath $item.Part) {
            (Get-Item -LiteralPath $item.Part).Length
        } else { 0 }
        $active[$process.Id] = [pscustomobject]@{
            Process = $process
            Item = $item
            ProgressLog = $progressLog
            LastBytes = [int64]$initialBytes
            LastTime = Get-Date
        }
        Write-Status "TRANSFER pid=$($process.Id) file=$($item.Name) resume_bytes=$initialBytes"
    }

    if (((Get-Date) - $lastReport).TotalSeconds -ge 5) {
        $rate = [double]0
        $activeText = @()
        foreach ($entry in $active.Values) {
            $receivedText = '?'
            $currentRateText = '?'
            $lines = @(Get-Content -LiteralPath $entry.ProgressLog -Tail 20 -ErrorAction SilentlyContinue)
            for ($lineIndex = $lines.Count - 1; $lineIndex -ge 0; $lineIndex--) {
                $fields = @($lines[$lineIndex].Trim() -split '\s+')
                if (($fields.Count -ge 12) -and ($fields[0] -match '^\d+$')) {
                    $receivedText = $fields[3]
                    $currentRateText = $fields[-1]
                    $rate += Convert-CurlRateToBytes -Text $currentRateText
                    break
                }
            }
            $activeText += "$($entry.Item.Index):$receivedText@$currentRateText/s"
        }
        $done = $alreadyComplete + $completedThisRun
        Write-Host ("Progress {0}/64 | active [{1}] | recent {2:N1} MB/s" -f `
            $done, ($activeText -join ', '), ($rate / 1MB)) -ForegroundColor Yellow
        $lastReport = Get-Date
    }
    Start-Sleep -Seconds 1
}

Write-Status 'ALL_SHARDS_COMPLETE verify inventory and SHA-256 before cache cleanup'
Write-Host ''
Write-Host 'All 64 model shards are present with the expected byte sizes.' -ForegroundColor Green
Write-Host 'Keep this window open until the final SHA-256 inventory check is run.' -ForegroundColor Green
