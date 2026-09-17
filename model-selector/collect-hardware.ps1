[CmdletBinding()]
param(
    [string]$Output = "hardware.json"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    # 昇腾机器没有 nvidia-smi,这里如实指路,不去猜 npu-smi 的输出格式。
    if (Get-Command npu-smi -ErrorAction SilentlyContinue) {
        Write-Error @"
本机是昇腾(NPU)环境:本脚本只采集 NVIDIA 卡(nvidia-smi)。
昇腾请走部署台账的「现场登记」路径提交硬件,并在 JSON 里写明:
  ecosystem=cann,不填 compute_capability(昇腾没有 sm 号),
  vram_per_gpu_gib 按厂商产品页的显存容量填写。
对照条目见 deploy-portal/data/gpu-catalog.json 里的 ascend-* 条目。
"@
        exit 2
    }
    throw "nvidia-smi was not found. Install or repair the NVIDIA driver first."
}

$rows = @(nvidia-smi --query-gpu=name,memory.total,compute_cap,driver_version --format=csv,noheader,nounits)
if ($LASTEXITCODE -ne 0 -or $rows.Count -eq 0) {
    throw "nvidia-smi query failed."
}

$gpus = foreach ($row in $rows) {
    $parts = $row -split '\s*,\s*'
    [pscustomobject]@{
        name = $parts[0]
        memory_mib = [double]$parts[1]
        compute_capability = [double]$parts[2]
        driver_version = $parts[3]
    }
}

$groups = $gpus | Group-Object name, memory_mib, compute_capability, driver_version
if ($groups.Count -gt 1) {
    Write-Warning "Heterogeneous GPUs detected. The largest homogeneous group is exported; query each GPU group separately for model selection."
}
$group = $groups | Sort-Object Count -Descending | Select-Object -First 1
$gpu = $group.Group[0]

$ramGib = 0
try {
    $ramGib = [math]::Floor((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
} catch {
    if (Get-Command free -ErrorAction SilentlyContinue) {
        $ramGib = [math]::Floor(([double]((free -b | Select-String '^Mem:') -split '\s+')[1]) / 1GB)
    }
}

$diskGib = 0
try {
    $diskGib = [math]::Floor((Get-PSDrive -Name (Get-Location).Drive.Name).Free / 1GB)
} catch {}

$result = [ordered]@{
    gpu_name = $gpu.name
    gpu_count = $group.Count
    vram_per_gpu_gib = [math]::Round($gpu.memory_mib / 1024, 0)
    compute_capability = $gpu.compute_capability
    driver_version = $gpu.driver_version
    host_ram_gib = $ramGib
    disk_free_gib = $diskGib
    interconnect = "UNKNOWN - update this after running nvidia-smi topo -m"
    nodes = 1
    workload = "coding,agent"
    require_multimodal = $false
    require_permissive_license = $false
    min_context_k = 32
}

$json = $result | ConvertTo-Json
$json | Set-Content -LiteralPath $Output -Encoding utf8
$json
Write-Host "`nSaved to $Output. Review interconnect, nodes, workload, context, and disk fields."
