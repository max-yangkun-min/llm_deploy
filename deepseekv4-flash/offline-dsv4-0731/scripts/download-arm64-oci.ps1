param(
    [string]$Stage = "$PSScriptRoot\..\images\arm64-oci-stage",
    [int]$ChunkMiB = 16,
    [int]$Parallel = 8,
    [string]$Proxy = "http://127.0.0.1:7897",
    [string]$Registry = "quay.io",
    [string]$Repository = "ascend/vllm-ascend"
)

$ErrorActionPreference = "Stop"

$manifestDigest = "sha256:8dd01aa0e0e5c4b04d3d715f483351af24c626c30373215e74238cf389fc2a93"
$tokenUrl = if ($Registry -eq "m.daocloud.io") {
    "https://m.daocloud.io/auth/token?service=m.daocloud.io&scope=repository%3A$Repository%3Apull&nonce=$([guid]::NewGuid())"
} else {
    "https://$Registry/v2/auth?service=$Registry&scope=repository%3A$Repository%3Apull"
}
$registryBase = "https://$Registry/v2/$Repository"
$blobRoot = Join-Path $Stage "blobs\sha256"
$partRoot = Join-Path $Stage "parts"

function Get-SignedBlobUrl {
    param([string]$BlobUrl, [string]$Token)
    $headerPath = Join-Path $env:TEMP ("dsv4-location-{0}.headers" -f ([guid]::NewGuid()))
    try {
        $freshTokenUrl = if ($Registry -eq "m.daocloud.io") {
            "https://m.daocloud.io/auth/token?service=m.daocloud.io&scope=repository%3A$Repository%3Apull&nonce=$([guid]::NewGuid())"
        } else {
            $tokenUrl
        }
        $freshToken = ((curl.exe --proxy $Proxy -L --fail --silent --show-error --max-time 60 $freshTokenUrl) | ConvertFrom-Json).token
        if (-not $freshToken) {
            throw "registry token refresh returned empty token"
        }
        & curl.exe --proxy $Proxy -sS --fail --max-time 60 -D $headerPath -o NUL `
            -H "Authorization: Bearer $freshToken" $BlobUrl
        if ($LASTEXITCODE -ne 0) {
            throw "failed to obtain signed blob URL"
        }
        $location = (Get-Content $headerPath | Where-Object { $_ -match '^Location:' } | Select-Object -First 1)
        $location = $location -replace '^Location:\s*', ''
        if (-not $location) {
            throw "registry did not return a signed blob URL"
        }
        return $location.Trim()
    } finally {
        Remove-Item -LiteralPath $headerPath -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-Curl {
    param([string[]]$Arguments)
    & curl.exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "curl failed with exit code $LASTEXITCODE"
    }
}

function Get-Blob {
    param(
        [string]$Digest,
        [long]$Size,
        [string]$Kind,
        [string]$Token
    )

    $hex = $Digest.Substring(7)
    $outputPath = Join-Path $blobRoot $hex
    if (Test-Path $outputPath) {
        $existingSize = (Get-Item $outputPath).Length
        if ($existingSize -eq $Size) {
            $existingHash = (Get-FileHash $outputPath -Algorithm SHA256).Hash.ToLower()
            if ($existingHash -eq $hex) {
                Write-Output "cached $Kind $hex ($Size bytes)"
                return
            }
        }
        Remove-Item -LiteralPath $outputPath -Force
    }

    $blobUrl = "$registryBase/blobs/$Digest"
    $signedBlobUrl = Get-SignedBlobUrl -BlobUrl $blobUrl -Token $Token
    $chunkBytes = [long]$ChunkMiB * 1MB
    $chunkCount = [int][math]::Ceiling($Size / [double]$chunkBytes)
    $blobPartRoot = Join-Path $partRoot $hex
    New-Item -ItemType Directory -Force -Path $blobPartRoot | Out-Null
    Write-Output "downloading $Kind $hex ($Size bytes, $chunkCount chunks)"

    for ($first = 0; $first -lt $chunkCount; $first += $Parallel) {
        $workers = @()
        $last = [math]::Min($first + $Parallel - 1, $chunkCount - 1)
        for ($index = $first; $index -le $last; $index++) {
            $start = [long]$index * $chunkBytes
            $end = [math]::Min($Size - 1, $start + $chunkBytes - 1)
            $partPath = Join-Path $blobPartRoot ("{0:D6}.part" -f $index)
            if ((Test-Path $partPath) -and ((Get-Item $partPath).Length -eq ($end - $start + 1))) {
                continue
            }
            if (Test-Path $partPath) {
                Remove-Item -LiteralPath $partPath -Force
            }
            $arguments = @(
                '-L', '--fail', '--silent', '--show-error',
                '--retry', '10', '--retry-delay', '5', '--retry-all-errors',
                '--connect-timeout', '30', '--max-time', '600',
                '--range', "$start-$end", '--output', $partPath, $signedBlobUrl
            )
            $workers += Start-Process -FilePath 'curl.exe' -ArgumentList $arguments -WindowStyle Hidden -PassThru
        }
        if ($workers.Count -gt 0) {
            foreach ($worker in $workers) {
                $worker.WaitForExit()
                if ($worker.ExitCode -ne 0) {
                    throw "curl failed for chunk batch $first-$last of $hex"
                }
            }
        }
        Write-Output ("  chunks {0}-{1}/{2} complete" -f $first, $last, $chunkCount)
    }

    $stream = [IO.File]::Open($outputPath, [IO.FileMode]::Create, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        for ($index = 0; $index -lt $chunkCount; $index++) {
            $partPath = Join-Path $blobPartRoot ("{0:D6}.part" -f $index)
            $partSize = (Get-Item $partPath).Length
            $start = [long]$index * $chunkBytes
            $end = [math]::Min($Size - 1, $start + $chunkBytes - 1)
            if ($partSize -ne ($end - $start + 1)) {
                throw "chunk size mismatch for $hex chunk $index"
            }
            $partStream = [IO.File]::OpenRead($partPath)
            try {
                $partStream.CopyTo($stream)
            } finally {
                $partStream.Dispose()
            }
        }
    } finally {
        $stream.Dispose()
    }
    Remove-Item -LiteralPath $blobPartRoot -Recurse -Force

    $actualSize = (Get-Item $outputPath).Length
    $actualHash = (Get-FileHash $outputPath -Algorithm SHA256).Hash.ToLower()
    if ($actualSize -ne $Size -or $actualHash -ne $hex) {
        throw ("verification failed for {0}: size={1} hash={2}" -f $hex, $actualSize, $actualHash)
    }
    Write-Output "verified $Kind $hex"
}

New-Item -ItemType Directory -Force -Path $blobRoot | Out-Null
New-Item -ItemType Directory -Force -Path $partRoot | Out-Null
$token = ((curl.exe --proxy $Proxy -L --fail --silent --show-error --max-time 60 $tokenUrl) | ConvertFrom-Json).token
if (-not $token) {
    throw "registry token is empty"
}

$manifestUrl = "$registryBase/manifests/$manifestDigest"
$manifestBytes = [Text.Encoding]::UTF8.GetBytes((& curl.exe --proxy $Proxy -L --fail --silent --show-error --max-time 60 `
    -H "Authorization: Bearer $token" -H "Accept: application/vnd.oci.image.manifest.v1+json" $manifestUrl | Out-String))
$manifestPath = Join-Path $Stage "manifest.json"
[IO.File]::WriteAllBytes($manifestPath, $manifestBytes)
$manifest = [Text.Encoding]::UTF8.GetString($manifestBytes) | ConvertFrom-Json

$blobs = @([pscustomobject]@{
        Digest = $manifest.config.digest
        Size = [long]$manifest.config.size
        Kind = "config"
    })
$blobs += @($manifest.layers | ForEach-Object {
        [pscustomobject]@{
            Digest = $_.digest
            Size = [long]$_.size
            Kind = "layer"
        }
    })

$index = 0
foreach ($blob in $blobs) {
    $index++
    Write-Output "[$index/$($blobs.Count)]"
    Get-Blob -Digest $blob.Digest -Size $blob.Size -Kind $blob.Kind -Token $token
}
Write-Output "ALL ARM64 BLOBS VERIFIED"
