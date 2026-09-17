$ErrorActionPreference = 'Stop'
$env:HF_ENDPOINT = 'https://hf-mirror.com'
$env:HF_XET_HIGH_PERFORMANCE = '1'

$log = 'E:\llm_models\wurenllm-download.log'
$hf = 'C:\Users\11984\AppData\Local\Programs\Python\Python38\Scripts\hf.exe'

function Run-Download {
    param(
        [string]$Repository,
        [string]$Revision,
        [string]$Destination
    )

    "$(Get-Date -Format s) START $Repository@$Revision -> $Destination" | Add-Content -LiteralPath $log -Encoding UTF8
    $safeName = $Repository.Replace('/', '-').Replace('\\', '-')
    $stdout = "E:\llm_models\$safeName.out.log"
    $stderr = "E:\llm_models\$safeName.err.log"
    $process = Start-Process -FilePath $hf -ArgumentList @(
        'download', $Repository,
        '--revision', $Revision,
        '--local-dir', $Destination,
        '--max-workers', '8'
    ) -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "hf download failed: $Repository ($($process.ExitCode)); see $stderr"
    }
    "$(Get-Date -Format s) COMPLETE $Repository@$Revision" | Add-Content -LiteralPath $log -Encoding UTF8
}

try {
    Run-Download `
        -Repository 'QuantTrio/MiniMax-M2.7-AWQ' `
        -Revision 'c9f2192c7b81f26f9a257ce73d92122fff0aea3d' `
        -Destination 'E:\wurenllm\models\MiniMax-M2.7-AWQ'

    Run-Download `
        -Repository 'QuantTrio/Qwen3.5-397B-A17B-AWQ' `
        -Revision '536f95520cb5202283f828e76fdc86afda581e43' `
        -Destination 'E:\wurenllm\models\Qwen3.5-397B-A17B-AWQ'

    Run-Download `
        -Repository 'moonshotai/Kimi-K2.6' `
        -Revision '7eb5002f6aadc958aed6a9177b7ed26bb94011bb' `
        -Destination 'E:\wurenllm\models\Kimi-K2.6'

    "$(Get-Date -Format s) ALL_COMPLETE" | Add-Content -LiteralPath $log -Encoding UTF8
}
catch {
    "$(Get-Date -Format s) FAILED $($_.Exception.Message)" | Add-Content -LiteralPath $log -Encoding UTF8
    throw
}
