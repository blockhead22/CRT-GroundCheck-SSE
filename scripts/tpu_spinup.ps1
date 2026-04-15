# D2 — TPU spin-up with automatic zone/accelerator fallback.
# Tries each candidate in order; first one that succeeds wins.
# Writes the resolved config to scripts/tpu_active.json for downstream scripts.

$ErrorActionPreference = "Continue"

$Project    = "aeteros"
$TpuName    = "aether-tpu-1"
$ServePort  = 8000

# Ordered list of attempts. Each entry is: Zone, Accelerator, Runtime, Spot, TP (tensor-parallel size).
# Priority: try spot v5e/v6e first (cheapest), fall through to on-demand v4 as reliable floor.
$Candidates = @(
    @{ Zone="us-central2-b";    Accel="v4-8";        Runtime="tpu-ubuntu2204-base"; Spot=$false; TP=4 },
    @{ Zone="us-central2-b";    Accel="v4-8";        Runtime="tpu-ubuntu2204-base"; Spot=$true;  TP=4 },
    @{ Zone="us-east1-d";       Accel="v6e-4";       Runtime="v2-alpha-tpuv6e";     Spot=$true;  TP=4 },
    @{ Zone="europe-west4-a";   Accel="v6e-4";       Runtime="v2-alpha-tpuv6e";     Spot=$true;  TP=4 },
    @{ Zone="europe-west4-b";   Accel="v5litepod-4"; Runtime="v2-alpha-tpuv5-lite"; Spot=$true;  TP=4 },
    @{ Zone="us-central1-a";    Accel="v5litepod-4"; Runtime="v2-alpha-tpuv5-lite"; Spot=$true;  TP=4 }
)

$MyIp = (Invoke-WebRequest -Uri "https://ifconfig.me/ip" -UseBasicParsing).Content.Trim()
Write-Host ">>> Local IP: $MyIp"
gcloud config set project $Project | Out-Null

$Resolved = $null
foreach ($c in $Candidates) {
    $spotFlag = if ($c.Spot) { "SPOT" } else { "ON-DEMAND" }
    Write-Host ""
    Write-Host "=== Trying $($c.Zone) / $($c.Accel) / $spotFlag ===" -ForegroundColor Cyan

    if ($c.Spot) {
        $out = gcloud compute tpus tpu-vm create $TpuName `
            --zone=$($c.Zone) `
            --accelerator-type=$($c.Accel) `
            --version=$($c.Runtime) `
            --spot 2>&1 | Out-String
    } else {
        $out = gcloud compute tpus tpu-vm create $TpuName `
            --zone=$($c.Zone) `
            --accelerator-type=$($c.Accel) `
            --version=$($c.Runtime) 2>&1 | Out-String
    }
    Write-Host $out

    if ($LASTEXITCODE -eq 0) {
        Write-Host ">>> SUCCESS on $($c.Zone) / $($c.Accel)" -ForegroundColor Green
        $Resolved = $c
        break
    }

    # Classify the failure. If it's quota/capacity -> try next. Anything else (auth,
    # bad args, permission) -> stop and show the user.
    if ($out -match "RESOURCE_EXHAUSTED|no more capacity|Quota limit|429|does not have permission|PERMISSION_DENIED|""code"": 7") {
        Write-Host ">>> Capacity/quota/permission issue, trying next candidate..." -ForegroundColor Yellow
        continue
    }
    Write-Host ">>> Non-recoverable failure. Stopping." -ForegroundColor Red
    exit 1
}

if ($null -eq $Resolved) {
    Write-Host ""
    Write-Host ">>> All candidates exhausted. Options:" -ForegroundColor Red
    Write-Host "  - Wait 10-30 min and rerun (spot capacity cycles)"
    Write-Host "  - Use queued-resources (fire-and-forget):"
    Write-Host "      gcloud compute tpus queued-resources create aether-qr-1 ``"
    Write-Host "        --node-id=$TpuName --zone=us-central1-a ``"
    Write-Host "        --accelerator-type=v5litepod-4 --runtime-version=v2-alpha-tpuv5-lite --spot"
    exit 1
}

$Zone = $Resolved.Zone

# Firewall + tag (idempotent, ignore errors if rule/tag already exists).
Write-Host ""
Write-Host ">>> Whitelisting $MyIp -> port $ServePort"
gcloud compute firewall-rules create aether-tpu-serve `
    --direction=INGRESS --action=ALLOW --rules=tcp:$ServePort `
    --source-ranges="$MyIp/32" --target-tags=aether-tpu 2>$null | Out-Null
gcloud compute tpus tpu-vm add-tags $TpuName --zone=$Zone --tags=aether-tpu 2>$null | Out-Null

# External IP
$ExtIp = (gcloud compute tpus tpu-vm describe $TpuName --zone=$Zone `
    --format="value(networkEndpoints[0].accessConfig.externalIp)").Trim()

# Persist resolved config so tpu_serve.sh + harness can read it.
$Active = @{
    tpu_name    = $TpuName
    zone        = $Zone
    accelerator = $Resolved.Accel
    runtime     = $Resolved.Runtime
    spot        = $Resolved.Spot
    tp          = $Resolved.TP
    external_ip = $ExtIp
    serve_port  = $ServePort
    resolved_at = (Get-Date).ToString("o")
}
$Active | ConvertTo-Json | Set-Content "scripts/tpu_active.json" -Encoding utf8
Write-Host ""
Write-Host ">>> Wrote scripts/tpu_active.json"
Write-Host ">>> External IP: $ExtIp"
Write-Host ">>> Tensor-parallel size: $($Resolved.TP)"

# Update tpu_serve.sh inline to match the resolved TP value.
$ServePath = "scripts/tpu_serve.sh"
if (Test-Path $ServePath) {
    # Write UTF-8 *without* BOM and with LF-only line endings; Linux bash chokes on BOM/CRLF.
    $content = (Get-Content $ServePath -Raw) -replace '--tensor-parallel-size \d+', "--tensor-parallel-size $($Resolved.TP)"
    $content = $content -replace "`r`n", "`n"
    [System.IO.File]::WriteAllText((Resolve-Path $ServePath), $content, (New-Object System.Text.UTF8Encoding $false))
    Write-Host ">>> Patched tpu_serve.sh with --tensor-parallel-size $($Resolved.TP)"
}

Write-Host ""
Write-Host ">>> Next steps (copy-paste):" -ForegroundColor Cyan
Write-Host "  gcloud compute tpus tpu-vm scp scripts/tpu_serve.sh ${TpuName}:~/ --zone=$Zone"
Write-Host "  gcloud compute tpus tpu-vm ssh $TpuName --zone=$Zone --command='bash ~/tpu_serve.sh'"
Write-Host "  `$env:TPU_BRAIN_URL = 'http://${ExtIp}:${ServePort}/v1'"
Write-Host "  python -m labs.aether_bench.harness --brain tpu_qwen7b --arm both --tasks all"
Write-Host ""
Write-Host ">>> Teardown:"
Write-Host "  gcloud compute tpus tpu-vm delete $TpuName --zone=$Zone"
