param(
    [ValidateSet("dev", "test", "prod")]
    [string]$Gate = "test",
    [switch]$ForceDeployment,
    [string]$ManifestPath = "examples/waves/wave1_staging_manifest.json"
)

$ErrorActionPreference = "Stop"
$python = "."
if (Test-Path "venv\Scripts\python.exe") {
    $python = ".\venv\Scripts\python"
} elseif (Test-Path ".\venv\Scripts\python") {
    $python = ".\venv\Scripts\python"
}

Write-Host "[Pilot Wave] Starting staging run" -ForegroundColor Cyan
Write-Host "  Manifest: $ManifestPath"
Write-Host "  Gate:     $Gate"
Write-Host "  Python:   $python" -ForegroundColor DarkGray
Write-Host ""

if (-not (Test-Path $ManifestPath)) {
    throw "Manifest not found: $ManifestPath"
}

$forceArg = ""
if ($ForceDeployment) {
    $forceArg = "--force-deployment"
}

Write-Host "[1/3] Dry run validation" -ForegroundColor Yellow
& $python migrate.py --migration-manifest $ManifestPath --gate $Gate --dry-run

Write-Host "[2/3] Execute staging wave" -ForegroundColor Yellow
& $python migrate.py --migration-manifest $ManifestPath --gate $Gate $forceArg

Write-Host "[3/3] Rollback drill reminder" -ForegroundColor Yellow
Write-Host "  Run procedure from docs/guides/PILOT_WAVE_STAGING_DRILL.md"
Write-Host ""
Write-Host "[Pilot Wave] Completed" -ForegroundColor Green
