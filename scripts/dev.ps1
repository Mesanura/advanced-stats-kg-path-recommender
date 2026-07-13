$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

$backend = Start-Process -PassThru -NoNewWindow -WorkingDirectory $Root -FilePath "$Root\.venv\Scripts\python.exe" -ArgumentList '-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--reload', '--host', '127.0.0.1', '--port', '8000'
$frontend = Start-Process -PassThru -NoNewWindow -WorkingDirectory "$Root\frontend" -FilePath 'pnpm.cmd' -ArgumentList 'dev'

try {
    Write-Host '后端：http://127.0.0.1:8000  前端：http://127.0.0.1:5173'
    Wait-Process -Id $backend.Id, $frontend.Id
} finally {
    Stop-Process -Id $backend.Id, $frontend.Id -Force -ErrorAction SilentlyContinue
}

