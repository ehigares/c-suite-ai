# Run all LLM Council tests.
# Usage: powershell -ExecutionPolicy Bypass -File run_tests.ps1

Write-Host "========================================"
Write-Host "  LLM Council - Test Suite"
Write-Host "========================================"

$failed = $false

Write-Host ""
Write-Host "[1/3] Pipeline tests..."
python -m tests.test_pipeline
if ($LASTEXITCODE -ne 0) { $failed = $true }

Write-Host ""
Write-Host "[2/3] Config tests..."
python -m tests.test_config
if ($LASTEXITCODE -ne 0) { $failed = $true }

Write-Host ""
Write-Host "[3/3] Ranking tests..."
python -m tests.test_ranking
if ($LASTEXITCODE -ne 0) { $failed = $true }

Write-Host ""
Write-Host "========================================"
if ($failed) {
    Write-Host "  SOME TESTS FAILED - see output above"
    exit 1
} else {
    Write-Host "  ALL TEST SUITES PASSED"
}
Write-Host "========================================"
