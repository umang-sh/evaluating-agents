param(
    [string]$Python = "py"
)

$ErrorActionPreference = "Stop"

Write-Host "=== Evaluating Agents: Windows setup ==="

# Must be run from the cloned repository.
if (-not (Test-Path ".\requirements.txt") -or -not (Test-Path ".\evalkit.py")) {
    throw "Run this script from inside the cloned evaluating-agents repository."
}

# Prefer the Python launcher. User currently has Python 3.13, which satisfies 3.11+.
if ($Python -eq "py") {
    & py -3.13 --version
    & py -3.13 -m venv .venv
} else {
    & $Python --version
    & $Python -m venv .venv
}

$venvPython = Join-Path $PWD ".venv\Scripts\python.exe"

Write-Host "`n=== Installing pinned requirements ==="
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt

if (-not (Test-Path ".\.env")) {
    if (Test-Path ".\.env.example") {
        Copy-Item ".\.env.example" ".\.env"
        Write-Host "`nCreated .env from .env.example. Fill in your API keys, then rerun check_env.py."
    } else {
        throw ".env is missing and .env.example was not found."
    }
}

Write-Host "`n=== Environment check ==="
& $venvPython check_env.py

Write-Host "`n=== Done ==="
Write-Host "In VS Code/Jupyter select this kernel:"
Write-Host $venvPython
Write-Host ""
Write-Host "Then restart the notebook kernel and click Run All."
