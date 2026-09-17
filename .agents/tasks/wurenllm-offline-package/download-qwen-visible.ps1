$ErrorActionPreference = 'Continue'

$repository = 'QuantTrio/Qwen3.5-397B-A17B-AWQ'
$revision = '536f95520cb5202283f828e76fdc86afda581e43'
$destination = 'E:\wurenllm\qwen3.5-397b-a17b-awq\models\Qwen3.5-397B-A17B-AWQ'
$logDirectory = 'E:\llm_models\qwen3.5-397b-download'
$log = Join-Path $logDirectory 'download.log'
$statusLog = Join-Path $logDirectory 'status.log'
$hf = 'C:\Users\11984\AppData\Local\Programs\Python\Python38\Scripts\hf.exe'

$Host.UI.RawUI.WindowTitle = 'Qwen3.5-397B-A17B-AWQ - downloading to E:\wurenllm'
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
Write-Host 'Qwen3.5-397B-A17B-AWQ background downloader' -ForegroundColor Green
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
