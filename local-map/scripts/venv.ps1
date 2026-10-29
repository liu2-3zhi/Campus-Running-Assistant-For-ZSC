function Get-ProjectPythonInfo {
    param([string]$PythonExe)
    if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { return $null }
    try {
        $result = & $PythonExe -c 'import json,sys; print(json.dumps(dict(version=list(sys.version_info[:2]),prefix=sys.prefix,base_prefix=sys.base_prefix)))' 2>&1
        if ($LASTEXITCODE -ne 0) { return $null }
        return ($result | ConvertFrom-Json -ErrorAction Stop)
    } catch { return $null }
}

function Get-ProjectRuntimePython {
    param([string]$ProjectDir)
    $runtimeDir = Join-Path $ProjectDir '.runtime/python'
    for ($attempt = 0; $attempt -lt 2; $attempt++) {
        $candidates = Get-ChildItem -LiteralPath $runtimeDir -Directory -Filter 'cpython-3.12.*-windows-x86_64-none' -ErrorAction SilentlyContinue |
            Sort-Object { [version]($_.Name -replace '^cpython-([0-9.]+)-.*$', '$1') } -Descending
        foreach ($candidate in $candidates) {
            $executable = Join-Path $candidate.FullName 'python.exe'
            $info = Get-ProjectPythonInfo $executable
            if ($info -and $info.version[0] -eq 3 -and $info.version[1] -eq 12) { return $executable }
        }
        if ($attempt -eq 0) {
            if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'Install uv or run setup.ps1 to prepare Python 3.12.' }
            uv python install 3.12 --install-dir $runtimeDir --no-bin --no-registry
            if ($LASTEXITCODE -ne 0) { throw 'Python installation failed.' }
        }
    }
    throw 'A usable local Python 3.12 runtime was not found.'
}

function Initialize-ProjectVenv {
    param([string]$ProjectDir, [string]$PythonExe)
    $projectRoot = (Resolve-Path -LiteralPath $ProjectDir -ErrorAction Stop).Path
    $runtimeInfo = Get-ProjectPythonInfo $PythonExe
    if (-not $runtimeInfo -or $runtimeInfo.version[0] -ne 3 -or $runtimeInfo.version[1] -ne 12) {
        throw 'The selected runtime must be a working Python 3.12 interpreter.'
    }
    $venvDir = Join-Path $projectRoot '.venv'
    $venvPython = Join-Path $venvDir 'Scripts/python.exe'
    $markerFile = Join-Path $venvDir '.campus-environment.json'
    $info = Get-ProjectPythonInfo $venvPython
    $marker = $null
    if (Test-Path -LiteralPath $markerFile) {
        try { $marker = Get-Content -LiteralPath $markerFile -Raw | ConvertFrom-Json -ErrorAction Stop } catch {}
    }
    if ($info -and $info.version[0] -eq 3 -and $info.version[1] -eq 12 -and
        $info.prefix -eq $venvDir -and $info.base_prefix -eq $runtimeInfo.base_prefix -and
        $marker -and $marker.project_dir -eq $projectRoot) {
        return @{ PythonExe = $venvPython; Rebuilt = $false }
    }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'uv is required to repair the moved or invalid virtual environment.' }
    if (Test-Path -LiteralPath $venvDir) {
        $backupRoot = Join-Path $projectRoot '.runtime/venv-backups'
        $backupDir = Join-Path $backupRoot ('venv-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
        $allowedRoot = $projectRoot.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
        if (-not ([IO.Path]::GetFullPath($venvDir).StartsWith($allowedRoot, [StringComparison]::OrdinalIgnoreCase)) -or
            -not ([IO.Path]::GetFullPath($backupDir).StartsWith($allowedRoot, [StringComparison]::OrdinalIgnoreCase))) {
            throw 'Virtual environment backup paths must stay inside the project directory.'
        }
        New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
        Move-Item -LiteralPath $venvDir -Destination $backupDir -ErrorAction Stop
        Write-Host "Preserved the previous virtual environment at $backupDir"
    }
    uv venv --python $PythonExe $venvDir
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed; the previous environment remains backed up.' }
    $info = Get-ProjectPythonInfo $venvPython
    if (-not $info -or $info.prefix -ne $venvDir -or $info.base_prefix -ne $runtimeInfo.base_prefix) {
        throw 'The new virtual environment could not be verified.'
    }
    @{ project_dir = $projectRoot; runtime = $PythonExe } | ConvertTo-Json | Set-Content -LiteralPath $markerFile -Encoding UTF8
    return @{ PythonExe = $venvPython; Rebuilt = $true }
}
