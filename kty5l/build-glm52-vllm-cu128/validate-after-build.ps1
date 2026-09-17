param(
    [int]$PollSeconds = 30,
    [int]$BuildOrchestratorPid = 27536
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Image = "glm52-vllm:0.24.0-pr38476-cu128-clean-r570-a100-v2"
$ValidationScript = Join-Path $Root "validate-image.sh"
$Log = Join-Path $Root "independent-validation.log"
$PidFile = Join-Path $Root "independent-validation.pid"
$PassedFile = Join-Path $Root "INDEPENDENT-VALIDATION-PASSED.txt"

Set-Content -LiteralPath $PidFile -Value $PID -Encoding ascii
Start-Transcript -LiteralPath $Log -Append | Out-Null
try {
    Write-Output "Waiting for completed image: $Image"
    while ($true) {
        $savedErrorAction = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        docker image inspect $Image *> $null
        $inspectExit = $LASTEXITCODE
        $ErrorActionPreference = $savedErrorAction
        if ($inspectExit -eq 0) {
            break
        }
        if ($BuildOrchestratorPid -and -not (Get-Process -Id $BuildOrchestratorPid -ErrorAction SilentlyContinue)) {
            throw "build process ended without producing image $Image"
        }
        Start-Sleep -Seconds $PollSeconds
    }

    $imageId = docker image inspect $Image --format '{{.Id}}'
    $labels = docker image inspect $Image --format '{{json .Config.Labels}}'
    Write-Output "IMAGE_ID=$imageId"
    Write-Output "LABELS=$labels"

    docker run --rm --entrypoint bash `
        --mount "type=bind,source=$ValidationScript,target=/opt/independent-validate.sh,readonly" `
        $Image /opt/independent-validate.sh
    if ($LASTEXITCODE -ne 0) {
        throw "independent image validation failed with exit code $LASTEXITCODE"
    }

    @(
        "validated_at=$(Get-Date -Format o)"
        "image=$Image"
        "image_id=$imageId"
    ) | Set-Content -LiteralPath $PassedFile -Encoding utf8
    Write-Output "VALIDATION_COMPLETE=$PassedFile"
}
finally {
    Stop-Transcript | Out-Null
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}
