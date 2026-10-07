<#
.SYNOPSIS
  Remove the virtual environment and caches for finland-unemployment-paradox.

.DESCRIPTION
  Removes:
    - the venv outside the project: %LOCALAPPDATA%\venvs\finland-unemployment-paradox
    - a .venv inside the project folder, if one was ever created
    - __pycache__, .pytest_cache, .mypy_cache, .ruff_cache, .ipynb_checkpoints and *.pyc
      anywhere in the project folder
    - the download cache data\ (the script downloads it again on the next run)
  Keeps outputs\ (CSVs and charts) unless you pass -IncludeOutputs.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\clean.ps1
  powershell -ExecutionPolicy Bypass -File .\clean.ps1 -KeepData
  powershell -ExecutionPolicy Bypass -File .\clean.ps1 -IncludeOutputs
#>
param(
    [switch]$KeepData,        # keep the data\ download cache
    [switch]$IncludeOutputs   # also delete outputs\ (charts and CSVs)
)

$ErrorActionPreference = "Stop"
$project = "finland-unemployment-paradox"
$root = $PSScriptRoot

function Remove-IfExists([string]$path) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
        Write-Host "Removed $path"
    }
}

# 1. Virtual environments
if ($env:LOCALAPPDATA) {
    Remove-IfExists (Join-Path $env:LOCALAPPDATA "venvs\$project")
}
Remove-IfExists (Join-Path $root ".venv")

# 2. Python and tool caches inside the project folder
$cacheDirs = "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".ipynb_checkpoints"
Get-ChildItem -LiteralPath $root -Recurse -Force -Directory -ErrorAction SilentlyContinue |
    Where-Object { $cacheDirs -contains $_.Name } |
    Sort-Object { $_.FullName.Length } -Descending |
    ForEach-Object { Remove-IfExists $_.FullName }
Get-ChildItem -LiteralPath $root -Recurse -Force -File -Filter "*.pyc" -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-IfExists $_.FullName }

# 3. Download cache (re-created on the next run)
if (-not $KeepData) { Remove-IfExists (Join-Path $root "data") }

# 4. Outputs only when asked
if ($IncludeOutputs) { Remove-IfExists (Join-Path $root "outputs") }

Write-Host "Clean done. Outputs kept: $(-not $IncludeOutputs)"
