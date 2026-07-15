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

$Backend = $null
$Frontend = $null

function Stop-ManagedProcess {
    param([System.Diagnostics.Process]$ManagedProcess)

    if ($null -eq $ManagedProcess) { return }
    if ($env:OS -eq 'Windows_NT') {
        Start-Process -FilePath 'taskkill.exe' -ArgumentList '/PID', $ManagedProcess.Id, '/T', '/F' -WindowStyle Hidden -Wait -ErrorAction SilentlyContinue | Out-Null
        return
    }

    $ManagedProcess.Refresh()
    if (-not $ManagedProcess.HasExited) {
        Stop-Process -Id $ManagedProcess.Id -Force -ErrorAction SilentlyContinue
    }
}

try {
    $Backend = Start-Process -PassThru -NoNewWindow -WorkingDirectory $Root -FilePath $VenvPython -ArgumentList '-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--reload', '--host', '127.0.0.1', '--port', '8000'
    $Frontend = Start-Process -PassThru -NoNewWindow -WorkingDirectory (Join-Path $Root 'frontend') -FilePath $Pnpm -ArgumentList 'dev'

    Write-Host '后端：http://127.0.0.1:8000  前端：http://127.0.0.1:5173'
    while ($true) {
        $Backend.Refresh()
        $Frontend.Refresh()
        if ($Backend.HasExited -or $Frontend.HasExited) { break }
        Start-Sleep -Seconds 1
    }

    $ExitedServices = @()
    if ($Backend.HasExited) { $ExitedServices += "后端（退出码 $($Backend.ExitCode)）" }
    if ($Frontend.HasExited) { $ExitedServices += "前端（退出码 $($Frontend.ExitCode)）" }
    throw "开发服务意外退出：$($ExitedServices -join '、')"
} finally {
    foreach ($Process in @($Backend, $Frontend)) {
        Stop-ManagedProcess $Process
    }
}
