param(
    [ValidateSet("download-first", "generate-first", "hybrid")]
    [string]$Mode = "hybrid",
    [ValidateSet("dev", "test", "prod")]
    [string]$Gate = "test",
    [string]$ManifestPath = "examples/waves/enterprise_complex_wave_manifest.template.json",
    [switch]$ForceDeployment
)

$ErrorActionPreference = "Stop"
$python = "."
if (Test-Path "venv\Scripts\python.exe") {
    $python = ".\venv\Scripts\python"
} elseif (Test-Path ".\venv\Scripts\python") {
    $python = ".\venv\Scripts\python"
}

Write-Host "[Enterprise Complex Flow] Mode: $Mode | Gate: $Gate" -ForegroundColor Cyan
Write-Host "[Enterprise Complex Flow] Manifest: $ManifestPath" -ForegroundColor Cyan
Write-Host "[Enterprise Complex Flow] Python: $python" -ForegroundColor DarkGray

if (-not (Test-Path $ManifestPath)) {
    throw "Manifest not found: $ManifestPath"
}

$forceArg = ""
if ($ForceDeployment) {
    $forceArg = "--force-deployment"
}

if ($Mode -eq "download-first" -or $Mode -eq "hybrid") {
    Write-Host "[1/4] Source diagnostics and pre-assessment" -ForegroundColor Yellow
    Write-Host "Run server diagnostics if needed:" -ForegroundColor DarkGray
    Write-Host "  & $python migrate.py --server-url https://qlik.example.com --server-test" -ForegroundColor DarkGray
    Write-Host ""
}

Write-Host "[2/4] Dry run manifest validation" -ForegroundColor Yellow
& $python migrate.py --migration-manifest $ManifestPath --gate $Gate --dry-run

Write-Host "[3/4] Execute migration wave" -ForegroundColor Yellow
& $python migrate.py --migration-manifest $ManifestPath --gate $Gate $forceArg

Write-Host "[4/4] Rollback readiness checkpoint" -ForegroundColor Yellow
Write-Host "Use: docs/guides/ROLLBACK_PLAYBOOK.md and docs/guides/PILOT_WAVE_STAGING_DRILL.md"

Write-Host "[Enterprise Complex Flow] Done" -ForegroundColor Green
