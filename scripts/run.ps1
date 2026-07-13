$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

Push-Location "$Root\frontend"
try {
    pnpm build
    if ($LASTEXITCODE -ne 0) { throw "前端构建失败，退出码：$LASTEXITCODE" }
} finally {
    Pop-Location
}

Set-Location $Root
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
