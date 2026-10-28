# Restore a clean demo state: no flags accepted / dismissed, audit log back to the pipeline's own events.
#   .\reset_demo.ps1           quick (a second)
#   .\reset_demo.ps1 -Reseed   full: regenerate the dataset and re-run the pipeline (about 8 minutes)
param([switch]$Reseed)
$root = $PSScriptRoot
$py = Join-Path $root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { Write-Error "Run the setup steps in README.md first (backend\.venv not found)."; exit 1 }
if ($Reseed) {
    & $py -m data.generator.seed --seed 42
    & $py (Join-Path $root 'eval\evaluate.py')
} else {
    & $py (Join-Path $root 'data\reset_demo.py')
}
exit $LASTEXITCODE
