param(
    [string]$OutRoot = "E:\offline-xt\system",
    [string]$Proxy = "http://127.0.0.1:7897",
    [string]$DriverVersion = "570.172.08"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$DockerPackages = @(
    "containerd.io",
    "docker-ce-cli",
    "docker-buildx-plugin",
    "docker-compose-plugin",
    "docker-ce"
)
$UbuntuTargets = [ordered]@{
    focal = "20.04"
    jammy = "22.04"
    noble = "24.04"
}
$NvidiaPackages = @(
    "libnvidia-container1",
    "libnvidia-container-tools",
    "nvidia-container-toolkit-base",
    "nvidia-container-toolkit"
)

function Get-CurlArgs {
    param([switch]$Head)
    $args = @("-L", "--fail", "--retry", "5", "--retry-all-errors", "--connect-timeout", "30")
    if ($Head) { $args += "-I" } else { $args += @("--max-time", "1800") }
    if ($Proxy) { $args += @("--proxy", $Proxy) }
    return $args
}

function Get-IndexText {
    param([string]$Uri)
    $args = Get-CurlArgs
    $text = & curl.exe @args -sS $Uri
    if ($LASTEXITCODE -ne 0) { throw "download index failed: $Uri" }
    return ($text -join "`n")
}

function Get-LatestPackage {
    param([string]$IndexText, [string]$PackageName)
    $escaped = [regex]::Escape($PackageName)
    $blocks = [regex]::Matches($IndexText, "(?ms)^Package: ${escaped}`n.*?(?=`n`n|\z)")
    if ($blocks.Count -eq 0) { throw "package missing from index: $PackageName" }
    $candidates = foreach ($match in $blocks) {
        $block = $match.Value
        $version = [regex]::Match($block, '(?m)^Version: (.+)$').Groups[1].Value.Trim()
        $filename = [regex]::Match($block, '(?m)^Filename: (.+)$').Groups[1].Value.Trim()
        $sha256 = [regex]::Match($block, '(?m)^SHA256: (.+)$').Groups[1].Value.Trim().ToLowerInvariant()
        $arch = [regex]::Match($block, '(?m)^Architecture: (.+)$').Groups[1].Value.Trim()
        $withoutEpoch = $version -replace '^\d+:', ''
        $numeric = [regex]::Match($withoutEpoch, '^\d+(?:\.\d+){1,3}').Value
        if (-not $version -or -not $filename -or $sha256.Length -ne 64 -or $arch -ne "amd64" -or -not $numeric) {
            throw "invalid package metadata: $PackageName"
        }
        [pscustomobject]@{
            Name=$PackageName
            Version=$version
            Filename=$filename
            Sha256=$sha256
            VersionKey=[version]$numeric
        }
    }
    return $candidates | Sort-Object VersionKey, Version -Descending | Select-Object -First 1
}

function Save-VerifiedFile {
    param([string]$Uri, [string]$Destination, [string]$ExpectedSha256 = "")
    $parent = Split-Path -Parent $Destination
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    if (Test-Path -LiteralPath $Destination) {
        $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Destination).Hash.ToLowerInvariant()
        if (-not $ExpectedSha256 -or $actual -eq $ExpectedSha256) {
            Write-Host "reuse: $Destination"
            return $actual
        }
    }
    $partial = "$Destination.partial"
    if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force }
    $args = Get-CurlArgs
    & curl.exe @args -sS -o $partial $Uri
    if ($LASTEXITCODE -ne 0) { throw "download failed: $Uri" }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $partial).Hash.ToLowerInvariant()
    if ($ExpectedSha256 -and $actual -ne $ExpectedSha256) {
        Remove-Item -LiteralPath $partial -Force
        throw "sha256 mismatch: $Uri"
    }
    Move-Item -LiteralPath $partial -Destination $Destination -Force
    Write-Host "saved: $Destination"
    return $actual
}

$resolvedOut = [IO.Path]::GetFullPath($OutRoot)
New-Item -ItemType Directory -Force -Path $resolvedOut | Out-Null

foreach ($entry in $UbuntuTargets.GetEnumerator()) {
    $codename = $entry.Key
    $release = $entry.Value
    $indexUri = "https://download.docker.com/linux/ubuntu/dists/$codename/stable/binary-amd64/Packages"
    $index = Get-IndexText $indexUri
    $destDir = Join-Path $resolvedOut "docker\$codename"
    $lock = @("ubuntu=$release", "codename=$codename", "architecture=amd64", "source=$indexUri")
    $selectedFiles = @()
    foreach ($name in $DockerPackages) {
        $pkg = Get-LatestPackage $index $name
        $leaf = Split-Path -Leaf $pkg.Filename
        $uri = "https://download.docker.com/linux/ubuntu/$($pkg.Filename)"
        Save-VerifiedFile $uri (Join-Path $destDir $leaf) $pkg.Sha256 | Out-Null
        $selectedFiles += $leaf
        $lock += "$($pkg.Name)|$($pkg.Version)|$leaf|$($pkg.Sha256)"
    }
    Get-ChildItem -LiteralPath $destDir -File -Filter '*.deb' -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notin $selectedFiles } |
        Remove-Item -Force
    [IO.File]::WriteAllText((Join-Path $destDir "PACKAGES.lock"), (($lock -join "`n") + "`n"), (New-Object Text.UTF8Encoding($false)))
}

$nvidiaIndexUri = "https://nvidia.github.io/libnvidia-container/stable/deb/amd64/Packages"
$nvidiaBase = "https://nvidia.github.io/libnvidia-container/stable/deb/amd64/"
$nvidiaIndex = Get-IndexText $nvidiaIndexUri
$nvidiaDir = Join-Path $resolvedOut "nvidia-container-toolkit"
$nvidiaLock = @("architecture=amd64", "source=$nvidiaIndexUri")
$nvidiaSelectedFiles = @()
foreach ($name in $NvidiaPackages) {
    $pkg = Get-LatestPackage $nvidiaIndex $name
    $leaf = Split-Path -Leaf $pkg.Filename
    $uri = $nvidiaBase + $pkg.Filename.TrimStart('.', '/')
    Save-VerifiedFile $uri (Join-Path $nvidiaDir $leaf) $pkg.Sha256 | Out-Null
    $nvidiaSelectedFiles += $leaf
    $nvidiaLock += "$($pkg.Name)|$($pkg.Version)|$leaf|$($pkg.Sha256)"
}
Get-ChildItem -LiteralPath $nvidiaDir -File -Filter '*.deb' -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notin $nvidiaSelectedFiles } |
    Remove-Item -Force
[IO.File]::WriteAllText((Join-Path $nvidiaDir "PACKAGES.lock"), (($nvidiaLock -join "`n") + "`n"), (New-Object Text.UTF8Encoding($false)))

$driverName = "NVIDIA-Linux-x86_64-${DriverVersion}.run"
$driverUri = "https://download.nvidia.com/XFree86/Linux-x86_64/${DriverVersion}/${driverName}"
$driverDir = Join-Path $resolvedOut "driver"
$driverSha = Save-VerifiedFile $driverUri (Join-Path $driverDir $driverName)
Get-ChildItem -LiteralPath $driverDir -File -Filter '*.run' -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne $driverName } |
    Remove-Item -Force
$driverLock = @(
    "version=$DriverVersion",
    "architecture=x86_64",
    "source=$driverUri",
    "sha256=$driverSha",
    "policy=backup-only-never-auto-install",
    "requires=matching-linux-headers-gcc-make-secure-boot-review-maintenance-window"
)
[IO.File]::WriteAllText((Join-Path $driverDir "DRIVER.lock"), (($driverLock -join "`n") + "`n"), (New-Object Text.UTF8Encoding($false)))

Write-Output "SYSTEM_BUNDLE_READY=$resolvedOut"
