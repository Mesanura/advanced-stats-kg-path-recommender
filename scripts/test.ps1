$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$VenvRoot = Join-Path $Root '.venv'

$UnixVenvPython = Join-Path $VenvRoot 'bin/python'
$WindowsVenvPython = Join-Path $VenvRoot 'Scripts\python.exe'
if (Test-Path -LiteralPath $UnixVenvPython -PathType Leaf) {
    $VenvPython = $UnixVenvPython
} elseif (Test-Path -LiteralPath $WindowsVenvPython -PathType Leaf) {
    $VenvPython = $WindowsVenvPython
} else {
    throw '请先运行 scripts/setup.ps1。'
}

$PnpmCommand = Get-Command pnpm.cmd -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $PnpmCommand) {
    $PnpmCommand = Get-Command pnpm -ErrorAction SilentlyContinue | Select-Object -First 1
}
if ($null -eq $PnpmCommand) {
    throw '需要 pnpm 11。'
}
$Pnpm = $PnpmCommand.Source

Push-Location (Join-Path $Root 'backend')
try {
    & $VenvPython -m pytest --cov=app --cov-report=term-missing
    if ($LASTEXITCODE -ne 0) { throw "后端测试失败，退出码：$LASTEXITCODE" }
} finally {
    Pop-Location
}

Push-Location (Join-Path $Root 'frontend')
$PreviousCI = $env:CI
try {
    $env:CI = 'true'
    & $Pnpm test:coverage
    if ($LASTEXITCODE -ne 0) { throw "前端测试失败，退出码：$LASTEXITCODE" }
    & $Pnpm build
    if ($LASTEXITCODE -ne 0) { throw "前端构建失败，退出码：$LASTEXITCODE" }
} finally {
    if ($null -eq $PreviousCI) {
        Remove-Item Env:CI -ErrorAction SilentlyContinue
    } else {
        $env:CI = $PreviousCI
    }
    Pop-Location
}
