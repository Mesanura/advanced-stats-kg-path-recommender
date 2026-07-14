$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

Set-Location $Root
if (-not (Test-Path '.venv')) {
    python -m venv .venv
}

& '.\.venv\Scripts\python.exe' -m pip install --upgrade pip
& '.\.venv\Scripts\python.exe' -m pip install -r backend\requirements.txt -r backend\requirements-dev.txt

Push-Location frontend
try {
    $env:CI = 'true'
    pnpm install
    if ($LASTEXITCODE -ne 0) { throw "pnpm install 失败，退出码：$LASTEXITCODE" }
} finally {
    Pop-Location
}

if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
}

Push-Location backend
try {
    & "$Root\.venv\Scripts\python.exe" -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "数据库迁移失败，退出码：$LASTEXITCODE" }
    & "$Root\.venv\Scripts\python.exe" -m app.cli seed
    if ($LASTEXITCODE -ne 0) { throw "演示数据初始化失败，退出码：$LASTEXITCODE" }
} finally {
    Pop-Location
}

Write-Host '依赖安装完成。'
