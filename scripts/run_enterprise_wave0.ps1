param(
    [ValidateSet("dev", "test", "prod")]
    [string]$Gate = "test",
    [switch]$MakeReady,
    [switch]$ForceDeployment
)

$ErrorActionPreference = "Stop"
$portfolio = "examples/waves/enterprise_wave0_portfolio.csv"
$outputDir = "examples/waves/generated_wave0"
$python = ".\venv\Scripts\python"

Write-Host "[Enterprise Wave 0] Building manifests" -ForegroundColor Cyan
& $python scripts/build_wave_manifests.py --input $portfolio --output-dir $outputDir --include-profiles-template --output-root output/waves/enterprise_wave0/staging @($(if($MakeReady){'--make-ready'}))

$manifest = Join-Path $outputDir "wave_Wave-0_manifest.json"
if ($MakeReady) {
    $readyManifest = Join-Path $outputDir "wave_Wave-0_manifest_ready.json"
    if (Test-Path $readyManifest) {
        $manifest = $readyManifest
    }
}

$forceArg = ""
if ($ForceDeployment) {
    $forceArg = "--force-deployment"
}

Write-Host "[Enterprise Wave 0] Dry run" -ForegroundColor Yellow
& $python migrate.py --migration-manifest $manifest --gate $Gate --dry-run

Write-Host "[Enterprise Wave 0] Execute" -ForegroundColor Yellow
& $python migrate.py --migration-manifest $manifest --gate $Gate $forceArg

Write-Host "[Enterprise Wave 0] Complete" -ForegroundColor Green
Write-Host "Manifest used: $manifest"
