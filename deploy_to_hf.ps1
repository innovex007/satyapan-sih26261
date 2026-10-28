# Uploads this project to a Hugging Face Space (it rebuilds and goes live automatically).
# Usage:  .\deploy_to_hf.ps1 <hf-username>/satyapan
param([Parameter(Mandatory=$true)][string]$Space)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = ".\backend\.venv\Scripts\python.exe"
$hf = ".\backend\.venv\Scripts\hf.exe"
& $py -m pip install -q -U huggingface_hub
& $hf auth whoami *> $null
if ($LASTEXITCODE -ne 0) { & $hf auth login }
& $hf upload $Space . . --repo-type space --commit-message "Deploy prototype" --exclude "**/node_modules/**" "**/.venv/**" "**/__pycache__/**" "frontend/dist/**" "storage/**" "*.db" "prof.out" "*.log" ".git/**"
Write-Host "Uploaded. Watch the build: https://huggingface.co/spaces/$Space  ->  live link: https://$($Space.Replace('/','-')).hf.space" -ForegroundColor Green
