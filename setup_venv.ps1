$ErrorActionPreference = "Stop"

$VenvPath = ".venv"
$Python = Join-Path $VenvPath "Scripts\python.exe"
$Pip = Join-Path $VenvPath "Scripts\pip.exe"

if (-not (Test-Path $Python)) {
  python -m venv $VenvPath
}

& $Pip install -r requirements.txt

Write-Host "Venv ready: .venv"
