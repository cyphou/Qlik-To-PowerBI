Param(
    [string]$OutputRoot = "output\\real_qlik_selfheal_runs",
    [switch]$UseLargeSample = $true
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    $downloadDir = Join-Path "examples\\qlik" "downloaded"
    New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null

    $sampleUrl = "https://raw.githubusercontent.com/cyphou/Qlik-To-PowerBI/main/examples/qlik/qlik_exports/sample_sales_from_qvf.json"
    $downloaded = Join-Path $downloadDir "sample_sales_from_qvf_downloaded.json"

    Write-Host "[1/3] Downloading public Qlik example..."
    Invoke-WebRequest -Uri $sampleUrl -OutFile $downloaded

    $run1Out = Join-Path $OutputRoot "downloaded_sample"
    New-Item -ItemType Directory -Force -Path $run1Out | Out-Null

    Write-Host "[2/3] Running migration + self-healing on downloaded sample..."
    py -3 migrate.py $downloaded `
        --output-dir $run1Out `
        --self-heal-v3 `
        --repair-strategies `
        --full-lineage `
        --script-lineage `
        --validate `
        --post-check

    if ($UseLargeSample) {
        $largeSample = "examples\\qlik\\test_samples\\large\\large_enterprise_sales.json"
        $run2Out = Join-Path $OutputRoot "large_sample"
        New-Item -ItemType Directory -Force -Path $run2Out | Out-Null

        Write-Host "[3/3] Running migration + self-healing on large realistic sample..."
        py -3 migrate.py $largeSample `
            --output-dir $run2Out `
            --self-heal-v3 `
            --repair-strategies `
            --full-lineage `
            --script-lineage `
            --validate `
            --post-check

        Write-Host "Large sample artifacts:" -ForegroundColor Green
        Write-Host "  - $(Join-Path $run2Out 'self_healing_v3.jsonl')"
        Write-Host "  - $(Join-Path $run2Out 'comparison_report.html')"
    }

    Write-Host "Done. Key artifacts:" -ForegroundColor Green
    Write-Host "  - $(Join-Path $run1Out 'self_healing_v3.jsonl')"
    Write-Host "  - $(Join-Path $run1Out 'comparison_report.html')"
}
finally {
    Pop-Location
}
