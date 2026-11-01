$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$localRuntime = Join-Path $PSScriptRoot '.python'
$venvConfig = Join-Path $PSScriptRoot '.venv\pyvenv.cfg'

# Keep the environment tied to this project's Python, even if the folder moves.
if ((Test-Path (Join-Path $localRuntime 'python.exe')) -and (Test-Path $venvConfig)) {
    $config = Get-Content -LiteralPath $venvConfig
    $config = $config -replace '^home = .*$', ('home = ' + $localRuntime)
    Set-Content -LiteralPath $venvConfig -Value $config -Encoding UTF8
}
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Missing .venv\Scripts\python.exe. Restore the project Python environment first.'
}
& $python -c 'import fastapi, uvicorn, cv2, numpy, insightface'
if ($LASTEXITCODE -ne 0) {
    throw 'Python or project dependencies could not start. Check .python and .venv.'
}

Set-Location (Join-Path $PSScriptRoot 'backend')
& $python -m uvicorn app:app --host 127.0.0.1 --port 8000
