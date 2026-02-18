# Collecte Automatique Exemples Qlik
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "COLLECTE EXEMPLES QLIK POUR TESTS" -ForegroundColor Yellow
Write-Host "========================================`n" -ForegroundColor Cyan

# Chemins
$qlikApps = "$env:USERPROFILE\Documents\Qlik\Sense\Apps"
$testSamples = "test_samples"
$cloudDemo = "C:\Users\pidoudet\Downloads\ReportingExampleMaterials\ReportingExampleMaterials\Demo App - Qlik Cloud Reporting.qvf"

# Cr?er structure
Write-Host "Creation dossiers..." -ForegroundColor Green
@("small", "medium", "large", "cloud_format") | ForEach-Object {
    $path = Join-Path $testSamples $_
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
}

$total = 0

# Copier depuis Qlik Desktop
Write-Host "`nRecherche Qlik Sense Desktop..." -ForegroundColor Green
if (Test-Path $qlikApps) {
    $qvfs = Get-ChildItem "$qlikApps\*.qvf" -ErrorAction SilentlyContinue
    Write-Host "Trouve: $($qvfs.Count) fichier(s)`n" -ForegroundColor White
    
    foreach ($qvf in $qvfs) {
        $sizeMB = [math]::Round($qvf.Length / 1MB, 2)
        $category = if ($sizeMB -lt 1) { "small" } elseif ($sizeMB -lt 10) { "medium" } else { "large" }
        Copy-Item $qvf.FullName -Destination "$testSamples\$category\" -Force
        Write-Host "OK $($qvf.Name) -> $category/ ($sizeMB MB)" -ForegroundColor Green
        $total++
    }
} else {
    Write-Host "Qlik Desktop non trouve" -ForegroundColor Yellow
}

# Copier Demo Cloud
Write-Host "`nRecherche Demo App Cloud..." -ForegroundColor Green
if (Test-Path $cloudDemo) {
    Copy-Item $cloudDemo -Destination "$testSamples\cloud_format\" -Force
    Write-Host "OK Demo App Cloud -> cloud_format/" -ForegroundColor Green
    $total++
} else {
    Write-Host "Demo App Cloud non trouve" -ForegroundColor Yellow
}

# R?sum?
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "R?SUM?" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

$small = (Get-ChildItem "$testSamples\small\*.qvf" -ErrorAction SilentlyContinue).Count
$medium = (Get-ChildItem "$testSamples\medium\*.qvf" -ErrorAction SilentlyContinue).Count
$large = (Get-ChildItem "$testSamples\large\*.qvf" -ErrorAction SilentlyContinue).Count
$cloud = (Get-ChildItem "$testSamples\cloud_format\*.qvf" -ErrorAction SilentlyContinue).Count
$total = $small + $medium + $large + $cloud

Write-Host "Small  : $small fichier(s)"
Write-Host "Medium : $medium fichier(s)"
Write-Host "Large  : $large fichier(s)"
Write-Host "Cloud  : $cloud fichier(s)"
Write-Host "TOTAL  : $total fichier(s)`n"

if ($total -ge 5) {
    Write-Host "OK Suffisant pour tests!" -ForegroundColor Green
    Write-Host "`nLancer tests:" -ForegroundColor Yellow
    Write-Host "python test_migration_suite.py --input test_samples`n" -ForegroundColor Cyan
} else {
    Write-Host "Besoin de plus d exemples (5 minimum)" -ForegroundColor Yellow
}
