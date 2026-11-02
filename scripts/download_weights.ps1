param(
    [string]$Endpoint = "https://hf-mirror.com"
)

$Root = Split-Path -Parent $PSScriptRoot
$Repo = Join-Path $Root "third_party\Seed-VC"
$VenvPython = Join-Path $Root "third_party\seedvc-venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "ERROR: virtualenv not found at $VenvPython" -ForegroundColor Red
    Write-Host "Run scripts\setup_seedvc.ps1 first." -ForegroundColor Red
    exit 1
}

$env:HF_ENDPOINT = $Endpoint
Set-Location $Repo

Write-Host "Downloading Seed-VC weights (resumable)..." -ForegroundColor Yellow
Write-Host "If it is interrupted, re-run this same script and it will continue." -ForegroundColor Yellow

& $VenvPython (Join-Path $PSScriptRoot "download_weights.py") (Join-Path $Repo "checkpoints")
if ($LASTEXITCODE -ne 0) {
    Write-Host "Download failed. Re-run this script to resume." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Done. Neural voice conversion weights are cached." -ForegroundColor Green
