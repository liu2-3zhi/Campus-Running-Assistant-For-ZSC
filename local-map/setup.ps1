param([switch]$SkipWebBuild)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/'
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw 'Node.js 24 is required for preparing the offline web and map assets.'
}

. (Join-Path $PSScriptRoot 'scripts/venv.ps1')
$runtimePython = Get-ProjectRuntimePython -ProjectDir $PSScriptRoot
$environment = Initialize-ProjectVenv -ProjectDir $PSScriptRoot -PythonExe $runtimePython
uv pip sync --python .venv/Scripts/python.exe requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }

$npmCmd = (Get-Command npm.cmd -ErrorAction Stop).Source
& $npmCmd ci --prefix tools
if ($LASTEXITCODE -ne 0) { throw 'Map build dependency installation failed.' }

if (-not $SkipWebBuild) {
    & $npmCmd ci --ignore-scripts --prefix web
    if ($LASTEXITCODE -ne 0) { throw 'Web dependency installation failed.' }
    & $npmCmd run build --prefix web
    if ($LASTEXITCODE -ne 0) { throw 'Web build failed.' }
}
. (Join-Path $PSScriptRoot '.venv/Scripts/Activate.ps1')
Write-Output 'Setup complete. Run ./start.ps1 or python main.py. prepare/build/validate/serve commands are also available.'
