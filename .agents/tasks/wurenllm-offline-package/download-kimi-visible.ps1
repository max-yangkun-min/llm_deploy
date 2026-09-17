$ErrorActionPreference = 'Continue'

$repository = 'moonshotai/Kimi-K2.6'
$revision = '7eb5002f6aadc958aed6a9177b7ed26bb94011bb'
$destination = 'E:\wurenllm\kimi-k2.6\models\Kimi-K2.6'
$logDirectory = 'E:\llm_models\kimi-k2.6-download'
$statusLog = Join-Path $logDirectory 'status.log'
$hf = 'C:\Users\11984\AppData\Local\Programs\Python\Python38\Scripts\hf.exe'

$Host.UI.RawUI.WindowTitle = 'Kimi-K2.6 - downloading to E:\wurenllm'
$env:HF_ENDPOINT = 'https://hf-mirror.com'
$env:HF_HUB_ETAG_TIMEOUT = '60'
$env:HF_HUB_DOWNLOAD_TIMEOUT = '900'
$env:HF_XET_HIGH_PERFORMANCE = '1'
$env:PYTHONUNBUFFERED = '1'

New-Item -ItemType Directory -Force -Path $destination, $logDirectory | Out-Null

function Write-Status {
    param([string]$Message)
    $line = "$(Get-Date -Format s) $Message"
    Write-Host $line -ForegroundColor Cyan
    $line | Add-Content -LiteralPath $statusLog -Encoding UTF8
}

Write-Host ''
Write-Host 'Kimi-K2.6 background downloader' -ForegroundColor Green
Write-Host "Mirror:      $env:HF_ENDPOINT"
Write-Host "Repository:  $repository"
Write-Host "Revision:    $revision"
Write-Host "Destination: $destination"
Write-Host "State log:   $statusLog"
Write-Host 'Workers:     2 (stable resumable mode)'
Write-Host 'Progress:    native hf interactive display (bytes, rate and ETA when provided)'
Write-Host ''

$attempt = 0
while ($true) {
    $attempt++
    Write-Status "START attempt=$attempt repository=$repository revision=$revision"

    $arguments = @(
        'download', $repository,
        '--revision', $revision,
        '--local-dir', $destination,
        '--max-workers', '2'
    )
    & $hf @arguments
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
        Write-Status 'COMPLETE download finished successfully'
        Write-Host ''
        Write-Host 'Download complete. This window may now be closed.' -ForegroundColor Green
        break
    }

    Write-Status "RETRY exit_code=$exitCode; keeping all completed and .incomplete files"
    Write-Host 'Network transfer failed. Retrying in 20 seconds (Ctrl+C to stop)...' -ForegroundColor Yellow
    Start-Sleep -Seconds 20
}
