$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$VenvRoot = Join-Path $Root '.venv'

Set-Location $Root

if (-not [string]::IsNullOrWhiteSpace($env:PYTHON_BIN)) {
    $BootstrapPython = $env:PYTHON_BIN
} else {
    $PythonCommand = Get-Command python3 -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $PythonCommand) {
        $PythonCommand = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    if ($null -eq $PythonCommand) {
        throw '需要 Python 3.13。'
    }
    $BootstrapPython = $PythonCommand.Source
}

$PnpmCommand = Get-Command pnpm.cmd -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $PnpmCommand) {
    $PnpmCommand = Get-Command pnpm -ErrorAction SilentlyContinue | Select-Object -First 1
}
if ($null -eq $PnpmCommand) {
    throw '需要 pnpm 11。'
}
$Pnpm = $PnpmCommand.Source

if (-not (Test-Path -LiteralPath $VenvRoot -PathType Container)) {
    & $BootstrapPython -m venv $VenvRoot
    if ($LASTEXITCODE -ne 0) { throw "创建虚拟环境失败，退出码：$LASTEXITCODE" }
}

$UnixVenvPython = Join-Path $VenvRoot 'bin/python'
$WindowsVenvPython = Join-Path $VenvRoot 'Scripts\python.exe'
if (Test-Path -LiteralPath $UnixVenvPython -PathType Leaf) {
    $VenvPython = $UnixVenvPython
} elseif (Test-Path -LiteralPath $WindowsVenvPython -PathType Leaf) {
    $VenvPython = $WindowsVenvPython
} else {
    throw '虚拟环境中没有 Python 可执行文件。'
}

& $VenvPython -m pip --version
if ($LASTEXITCODE -ne 0) { throw "pip 不可用，退出码：$LASTEXITCODE" }

$Requirements = Join-Path $Root 'backend\requirements.txt'
$DevRequirements = Join-Path $Root 'backend\requirements-dev.txt'
& $VenvPython -m pip install --no-index -r $Requirements -r $DevRequirements *> $null
$DependenciesReady = $LASTEXITCODE -eq 0
if (-not $DependenciesReady) {
    & $VenvPython -m pip install --disable-pip-version-check --timeout 30 --retries 2 -r $Requirements -r $DevRequirements
    if ($LASTEXITCODE -ne 0) { throw "Python 依赖安装失败，退出码：$LASTEXITCODE" }
}

Push-Location (Join-Path $Root 'frontend')
$PreviousCI = $env:CI
try {
    $env:CI = 'true'
    & $Pnpm install
    if ($LASTEXITCODE -ne 0) { throw "pnpm install 失败，退出码：$LASTEXITCODE" }
} finally {
    if ($null -eq $PreviousCI) {
        Remove-Item Env:CI -ErrorAction SilentlyContinue
    } else {
        $env:CI = $PreviousCI
    }
    Pop-Location
}

$EnvFile = Join-Path $Root '.env'
if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    Copy-Item -LiteralPath (Join-Path $Root '.env.example') -Destination $EnvFile
}

Push-Location (Join-Path $Root 'backend')
try {
    & $VenvPython -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "数据库迁移失败，退出码：$LASTEXITCODE" }
    & $VenvPython -m app.cli seed
    if ($LASTEXITCODE -ne 0) { throw "演示数据初始化失败，退出码：$LASTEXITCODE" }
    & $VenvPython -m app.cli diagnose --algorithm rule
    if ($LASTEXITCODE -ne 0) { throw "规则法诊断失败，退出码：$LASTEXITCODE" }
    & $VenvPython -m app.cli diagnose --algorithm bkt
    if ($LASTEXITCODE -ne 0) { throw "BKT 诊断失败，退出码：$LASTEXITCODE" }
} finally {
    Pop-Location
}

Write-Host '依赖和演示数据已准备完成。'
