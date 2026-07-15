param(
    [Parameter(Mandatory = $true)]
    [string]$SourceFolder,

    [Parameter(Mandatory = $true)]
    [string]$TargetFolder,

    [switch]$Lineage,
    [switch]$SharedSemantic,
    [switch]$Fusion,
    [switch]$DeployOnline,

    [string]$WorkspaceId,

    [switch]$Recursive,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Assert-PathExists {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label not found: $Path"
    }
}

Set-Location (Join-Path $PSScriptRoot "..")

Assert-PathExists -Path $SourceFolder -Label "Source folder"

if (-not (Test-Path -LiteralPath $TargetFolder)) {
    New-Item -ItemType Directory -Path $TargetFolder -Force | Out-Null
}

if ($DeployOnline -and [string]::IsNullOrWhiteSpace($WorkspaceId)) {
    throw "WorkspaceId is required when -DeployOnline is used."
}

$excludeNamePatterns = @(
    '^migration_report_.*\.json$',
    '^openability_batch_report\.json$',
    '^policy_benchmark_.*\.json$',
    '^batch_report\.json$'
)

$scanRecursive = $true
if ($Recursive.IsPresent) {
    $scanRecursive = $true
}

$candidates = if ($scanRecursive) {
    Get-ChildItem -Path $SourceFolder -Recurse -File
}
else {
    Get-ChildItem -Path $SourceFolder -File
}

$inputs = foreach ($file in $candidates) {
    if ($file.Extension -notin @('.qvf', '.json')) {
        continue
    }

    $isExcluded = $false
    foreach ($pattern in $excludeNamePatterns) {
        if ($file.Name -match $pattern) {
            $isExcluded = $true
            break
        }
    }

    if (-not $isExcluded) {
        $file.FullName
    }
}

if (-not $inputs -or $inputs.Count -eq 0) {
    throw "No valid source files found (.qvf/.json exports)."
}

Write-Host "Running migration on $($inputs.Count) file(s)..." -ForegroundColor Cyan
$failed = 0

foreach ($inputFile in $inputs) {
    $runArgs = @(
        "migrate.py",
        $inputFile,
        "--output-dir", $TargetFolder,
        "--simple-mode", "balanced"
    )

    if ($Lineage) {
        $runArgs += "--compare"
        $runArgs += "--data-prep-lineage"
    }

    if ($DeployOnline) {
        $runArgs += @("--deploy", $WorkspaceId, "--deploy-refresh")
    }

    if ($DryRun) {
        $runArgs += "--dry-run"
    }

    Write-Host ("python " + ($runArgs -join " ")) -ForegroundColor DarkGray
    python @runArgs

    if ($LASTEXITCODE -ne 0) {
        $failed += 1
    }
}

if ($failed -gt 0) {
    throw "$failed migration run(s) failed."
}

if (-not ($SharedSemantic -or $Fusion)) {
    Write-Host "Done." -ForegroundColor Green
    exit 0
}

# Build shared semantic model from source files if requested.
# Reuse filtered inputs for shared semantic/fusion step.

if (-not $inputs -or $inputs.Count -lt 2) {
    throw "Shared semantic/fusion requires at least 2 source files (.qvf or .json)."
}

$sharedArgs = @(
    "migrate.py",
    "--shared-model"
)
$sharedArgs += $inputs
$sharedArgs += @(
    "--model-name", "SharedModel",
    "--output-dir", $TargetFolder
)

if ($Fusion) {
    $sharedArgs += "--force-merge"
}

if ($DeployOnline) {
    $sharedArgs += @("--deploy-bundle", $WorkspaceId, "--bundle-refresh")
}

if ($DryRun) {
    $sharedArgs += "--dry-run"
}

Write-Host "Running shared semantic/fusion step..." -ForegroundColor Cyan
Write-Host ("python " + ($sharedArgs -join " ")) -ForegroundColor DarkGray
python @sharedArgs

if ($LASTEXITCODE -ne 0) {
    throw "Shared semantic/fusion step failed with exit code $LASTEXITCODE"
}

Write-Host "Done." -ForegroundColor Green
