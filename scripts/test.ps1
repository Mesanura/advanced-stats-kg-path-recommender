$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

Push-Location "$Root\backend"
try {
    & "$Root\.venv\Scripts\python.exe" -m pytest --cov=app --cov-report=term-missing
    if ($LASTEXITCODE -ne 0) { throw "后端测试失败，退出码：$LASTEXITCODE" }
} finally {
    Pop-Location
}

Push-Location "$Root\frontend"
try {
    $env:CI = 'true'
    pnpm test:coverage
    if ($LASTEXITCODE -ne 0) { throw "前端测试失败，退出码：$LASTEXITCODE" }
    pnpm build
    if ($LASTEXITCODE -ne 0) { throw "前端构建失败，退出码：$LASTEXITCODE" }
} finally {
    Pop-Location
}
