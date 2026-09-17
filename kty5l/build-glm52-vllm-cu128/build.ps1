param(
    [string]$Image = "glm52-vllm:0.24.0-pr38476-cu128-clean-r570-a100-v2",
    [int]$MaxJobs = 8,
    [int]$NvccThreads = 2
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

docker build --pull=false --progress=plain `
    --build-arg "MAX_JOBS=$MaxJobs" `
    --build-arg "NVCC_THREADS=$NvccThreads" `
    --tag $Image `
    $Root

if ($LASTEXITCODE -ne 0) {
    throw "Docker build failed with exit code $LASTEXITCODE"
}
