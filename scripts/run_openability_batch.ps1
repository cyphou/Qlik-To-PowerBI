param(
    [string]$InputRoot = "c:\QlikToPowerBI",
    [string]$OutputRoot = "c:\QlikToPowerBI\migrated_output_batch_openability",
    [switch]$Recursive,
    [switch]$SkipExtraction,
    [switch]$StrictMode,
    [ValidateSet("conservative", "balanced", "aggressive")]
    [string]$RewritePolicy = "balanced",
    [switch]$FailOnNonOpenable
)

$ErrorActionPreference = "Stop"

function Get-JsonFromRawOutput {
    param([string]$Raw)

    $idx = $Raw.IndexOf("{")
    if ($idx -lt 0) {
        return $null
    }

    try {
        return ($Raw.Substring($idx) | ConvertFrom-Json)
    }
    catch {
        return $null
    }
}

Set-Location "c:\GitHub Project\QlikToPowerBI"

if (-not (Test-Path $InputRoot)) {
    throw "Input root not found: $InputRoot"
}

$search = if ($Recursive) { "-Recurse" } else { "" }
if ($Recursive) {
    $apps = Get-ChildItem $InputRoot -File -Filter *.qvf -Recurse
}
else {
    $apps = Get-ChildItem $InputRoot -File -Filter *.qvf
}

if (-not $apps -or $apps.Count -eq 0) {
    Write-Output "No .qvf files found in $InputRoot"
    exit 0
}

New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null

$results = @()

foreach ($app in $apps) {
    $args = @(
        "migrate.py",
        $app.FullName,
        "--output-dir", $OutputRoot,
        "--verify-open",
        "--json",
        "--quiet"
    )

    if ($SkipExtraction) {
        $args += "--skip-extraction"
    }

    if ($StrictMode) {
        $args += "--ensure-open-strict"
    }

    if ($RewritePolicy) {
        $args += @("--rewrite-policy", $RewritePolicy)
    }

    $rawLines = python @args
    $raw = [string]::Join("`n", $rawLines)
    $obj = Get-JsonFromRawOutput -Raw $raw

    if ($null -eq $obj) {
        $results += [pscustomobject]@{
            app = $app.Name
            path = $app.FullName
            status = "parse_error"
            openable = $false
            stage = "none"
            blocking = -1
            warnings = -1
            duration_seconds = -1
            output_dir = ""
            error_message = "Unable to parse JSON output"
        }
        continue
    }

    $ensure = $obj.ensure_open
    $final = $ensure.final
    $taxonomyInitial = $ensure.root_cause_taxonomy.initial
    $taxonomyFinal = $ensure.root_cause_taxonomy.final
    $autohealMetrics = $ensure.autoheal_metrics
    $strictViolation = $ensure.strict_violation

    $initialChecksSummary = ""
    if ($taxonomyInitial -and $taxonomyInitial.by_check) {
        $initialChecksSummary = (([hashtable]$taxonomyInitial.by_check).GetEnumerator() |
            Sort-Object Name |
            ForEach-Object { "$($_.Name):$($_.Value)" }) -join ";"
    }

    $finalChecksSummary = ""
    if ($taxonomyFinal -and $taxonomyFinal.by_check) {
        $finalChecksSummary = (([hashtable]$taxonomyFinal.by_check).GetEnumerator() |
            Sort-Object Name |
            ForEach-Object { "$($_.Name):$($_.Value)" }) -join ";"
    }

    $autohealArtifactSummary = ""
    if ($autohealMetrics -and $autohealMetrics.by_artifact) {
        $autohealArtifactSummary = (([hashtable]$autohealMetrics.by_artifact).GetEnumerator() |
            Sort-Object Name |
            ForEach-Object { "$($_.Name):$($_.Value)" }) -join ";"
    }

    $results += [pscustomobject]@{
        app = $app.Name
        path = $app.FullName
        status = $obj.status
        openable = [bool]$final.openable
        stage = $ensure.stage
        blocking = [int]$final.blocking_count
        warnings = [int]$final.warning_count
        duration_seconds = [double]$obj.duration_seconds
        output_dir = $obj.output_dir
        initial_blocking_total = [int]$taxonomyInitial.total_blocking
        final_blocking_total = [int]$taxonomyFinal.total_blocking
        initial_blocking_by_check = $initialChecksSummary
        final_blocking_by_check = $finalChecksSummary
        autoheal_action_count = [int]$autohealMetrics.action_count
        autoheal_by_artifact = $autohealArtifactSummary
        strict_violation = [bool]($null -ne $strictViolation)
        strict_reason = if ($strictViolation) { [string]$strictViolation.reason } else { "" }
        error_message = ""
    }
}

$jsonPath = Join-Path $OutputRoot "openability_batch_report.json"
$csvPath = Join-Path $OutputRoot "openability_batch_report.csv"

$results | ConvertTo-Json -Depth 8 | Out-File -FilePath $jsonPath -Encoding utf8
$results | Export-Csv -Path $csvPath -NoTypeInformation -Encoding utf8

$okCount = ($results | Where-Object { $_.openable -eq $true }).Count
$koCount = $results.Count - $okCount

$results | Sort-Object app | Format-Table app,status,openable,stage,blocking,warnings,duration_seconds -AutoSize
Write-Output ""
Write-Output "Total: $($results.Count) | Openable: $okCount | Not openable: $koCount"
Write-Output "JSON_REPORT=$jsonPath"
Write-Output "CSV_REPORT=$csvPath"

if ($FailOnNonOpenable -and $koCount -gt 0) {
    Write-Error "Openability gate failed: $koCount app(s) are not openable."
    exit 1
}
