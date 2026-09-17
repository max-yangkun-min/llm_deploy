param(
    [string]$Stage = "$PSScriptRoot\..\images\arm64-oci-stage",
    [string]$Output = "$PSScriptRoot\..\images\vllm-ascend-nightly-main-20260804-arm64.tar"
)

$ErrorActionPreference = "Stop"

$manifest = Get-Content (Join-Path $Stage "manifest.json") -Raw | ConvertFrom-Json
$manifestPath = Join-Path $Stage "manifest.json"
$manifestHash = (Get-FileHash $manifestPath -Algorithm SHA256).Hash.ToLower()
$manifestSize = (Get-Item $manifestPath).Length
$configDigest = $manifest.config.digest.Substring(7)
$layerDigests = @($manifest.layers | ForEach-Object { $_.digest.Substring(7) })
$blobRoot = Join-Path $Stage "blobs\sha256"

$index = [ordered]@{
    schemaVersion = 2
    mediaType = "application/vnd.oci.image.index.v1+json"
    manifests = @([ordered]@{
        mediaType = "application/vnd.oci.image.manifest.v1+json"
        digest = "sha256:" + $manifestHash
        size = $manifestSize
        annotations = [ordered]@{
            "io.containerd.image.name" = "deepseek-v4-flash/vllm-ascend:20260804-arm64"
            "org.opencontainers.image.ref.name" = "20260804-arm64"
        }
    })
}

$dockerManifest = @([ordered]@{
    Config = "blobs/sha256/$configDigest"
    RepoTags = @("deepseek-v4-flash/vllm-ascend:20260804-arm64")
    Layers = @($layerDigests | ForEach-Object { "blobs/sha256/$_" })
})

$layout = [ordered]@{ imageLayoutVersion = "1.0.0" }
$utf8 = [Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllText((Join-Path $Stage "index.json"), ($index | ConvertTo-Json -Depth 20 -Compress), $utf8)
[IO.File]::WriteAllText((Join-Path $Stage "manifest.json.docker"), ($dockerManifest | ConvertTo-Json -Depth 20 -Compress), $utf8)
[IO.File]::WriteAllText((Join-Path $Stage "oci-layout"), ($layout | ConvertTo-Json -Compress), $utf8)

$tarStage = Join-Path $Stage "tar-root"
if (Test-Path $tarStage) { Remove-Item $tarStage -Recurse -Force }
New-Item -ItemType Directory -Force -Path (Join-Path $tarStage "blobs\sha256") | Out-Null
Copy-Item (Join-Path $Stage "blobs\sha256\*") (Join-Path $tarStage "blobs\sha256") -Force
Copy-Item $manifestPath (Join-Path $tarStage "blobs\sha256\$manifestHash") -Force
Copy-Item (Join-Path $Stage "index.json") $tarStage -Force
Copy-Item (Join-Path $Stage "manifest.json.docker") (Join-Path $tarStage "manifest.json") -Force
Copy-Item (Join-Path $Stage "oci-layout") $tarStage -Force

if (Test-Path $Output) { Remove-Item $Output -Force }
tar.exe -cf $Output -C $tarStage .
if ($LASTEXITCODE -ne 0) { throw "tar failed" }

$size = (Get-Item $Output).Length
$hash = (Get-FileHash $Output -Algorithm SHA256).Hash.ToLower()
Write-Output "archive=$Output"
Write-Output "bytes=$size"
Write-Output "sha256=$hash"
Write-Output "architecture=linux/arm64"
