param(
    [int]$PollSeconds = 30,
    [int]$ObservedPullPid = 37048
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BaseImage = "docker.1panel.live/nvidia/cuda:12.8.1-devel-ubuntu22.04"
$ExpectedImageId = "sha256:a99a1860ba8e2916e5c3e73b72ec4c4301653a84586e05bfc9a2aa2d58027e97"
$ExpectedPlatform = "linux/amd64"
$OutputImage = "glm52-vllm:0.24.0-pr38476-cu128-clean-r570-a100-v2"
$Log = Join-Path $Root "resume-clean-v2.log"
$PidFile = Join-Path $Root "resume-clean-v2.pid"

Set-Content -LiteralPath $PidFile -Value $PID -Encoding ascii
Start-Transcript -LiteralPath $Log -Append | Out-Null
try {
    Write-Output "Waiting for pinned CUDA base image: $BaseImage"
    while ($true) {
        $savedErrorAction = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $imageId = docker image inspect $BaseImage --format '{{.Id}}' 2>$null
        $inspectExit = $LASTEXITCODE
        $ErrorActionPreference = $savedErrorAction
        if ($inspectExit -eq 0) {
            $platform = docker image inspect $BaseImage --format '{{.Os}}/{{.Architecture}}'
            if ($LASTEXITCODE -ne 0) {
                throw "Unable to inspect CUDA base platform"
            }
            if ($imageId.Trim() -ne $ExpectedImageId) {
                throw "CUDA base index digest mismatch: $imageId"
            }
            if ($platform.Trim() -ne $ExpectedPlatform) {
                throw "CUDA base platform mismatch: $platform"
            }
            break
        }
        if ($ObservedPullPid -and -not (Get-Process -Id $ObservedPullPid -ErrorAction SilentlyContinue)) {
            Write-Output "Observed pull process ended before the image became visible; resuming pull"
            $savedErrorAction = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            docker pull $BaseImage
            $pullExit = $LASTEXITCODE
            $ErrorActionPreference = $savedErrorAction
            if ($pullExit -ne 0) {
                throw "CUDA base pull failed with exit code $pullExit"
            }
            $ObservedPullPid = 0
            continue
        }
        Start-Sleep -Seconds $PollSeconds
    }

    Write-Output "Pinned CUDA base verified; starting clean-v2 build"
    & (Join-Path $Root "build.ps1") -Image $OutputImage
    if ($LASTEXITCODE -ne 0) {
        throw "clean-v2 build failed with exit code $LASTEXITCODE"
    }
    Write-Output "BUILD_COMPLETE=$OutputImage"
}
finally {
    Stop-Transcript | Out-Null
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}
