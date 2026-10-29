param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ServerArgs)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
. (Join-Path $PSScriptRoot 'scripts/venv.ps1')
$runtimePython = Get-ProjectRuntimePython -ProjectDir $PSScriptRoot
$environment = Initialize-ProjectVenv -ProjectDir $PSScriptRoot -PythonExe $runtimePython
$dependenciesReady = $false
try {
    & $environment.PythonExe -c 'import fastapi,uvicorn,valhalla' 2>$null
    $dependenciesReady = $LASTEXITCODE -eq 0
} catch {}
if (-not $dependenciesReady) {
    uv pip sync --python $environment.PythonExe (Join-Path $PSScriptRoot 'requirements.lock.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Python dependencies could not be installed. Run setup.ps1.' }
}
& $environment.PythonExe (Join-Path $PSScriptRoot 'main.py') serve @ServerArgs
exit $LASTEXITCODE
