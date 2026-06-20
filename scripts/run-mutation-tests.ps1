# Mutation Testing Script for WOS Quality Enhancement
# Issue: #69
# Minimum mutation score threshold: 70%

Write-Host "=== WOS Mutation Testing ===" -ForegroundColor Cyan
Write-Host "Running mutation tests to verify test quality..."
Write-Host

# Check if mutmut is installed
$mutmutInstalled = Get-Command mutmut -ErrorAction SilentlyContinue
if (-not $mutmutInstalled) {
    Write-Host "Installing mutmut..." -ForegroundColor Yellow
    pip install mutmut
}

# Run mutation testing
Write-Host "Starting mutation testing..." -ForegroundColor Cyan
mutmut run --paths-to-mutate=src/workspace_os/ --tests-dir=tests/
if ($LASTEXITCODE -ne 0) {
    Write-Host "Mutation testing encountered some mutations (expected)" -ForegroundColor Yellow
}

# Generate results
Write-Host ""
Write-Host "=== Mutation Testing Results ===" -ForegroundColor Cyan
mutmut results

# Generate HTML report
Write-Host ""
Write-Host "Generating HTML report..." -ForegroundColor Cyan
mutmut html

# Parse mutation score
$results = mutmut results 2>&1 | Out-String
$survivedMatch = [regex]::Match($results, 'Survived:\s+(\d+)')
$totalMatch = [regex]::Match($results, 'Total:\s+(\d+)')

if ($survivedMatch.Success -and $totalMatch.Success) {
    $survived = [int]$survivedMatch.Groups[1].Value
    $total = [int]$totalMatch.Groups[1].Value

    if ($total -gt 0) {
        $killed = $total - $survived
        $scorePercent = [math]::Floor(($killed * 100) / $total)
    } else {
        $scorePercent = 0
    }

    Write-Host ""
    Write-Host "=== Mutation Score ===" -ForegroundColor Cyan
    Write-Host "Killed mutations: $killed / $total"
    Write-Host "Mutation Score: $scorePercent%"
    Write-Host "Threshold: 70%"
    Write-Host ""

    # Enforce minimum threshold
    if ($scorePercent -lt 70) {
        Write-Host "ERROR: Mutation score ($scorePercent%) is below threshold (70%)" -ForegroundColor Red
        Write-Host "Please improve test quality to meet the minimum requirement." -ForegroundColor Red
        exit 1
    } else {
        Write-Host "SUCCESS: Mutation score ($scorePercent%) meets threshold (70%)" -ForegroundColor Green
    }
} else {
    Write-Host "WARNING: Could not parse mutation score" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "View detailed results: html/index.html" -ForegroundColor Cyan
