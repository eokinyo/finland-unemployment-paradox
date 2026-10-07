<#
.SYNOPSIS
    Frees disk space after a run of this project.

.DESCRIPTION
    Deletes rebuildable local items:
      - the venv at %LOCALAPPDATA%\venvs\<project>
      - the download cache at %LOCALAPPDATA%\project-data\<project>
      - inside the project folder: .venv, every __pycache__, .pytest_cache,
        .mypy_cache, .ruff_cache, .ipynb_checkpoints and data/ (if any were created by mistake)
    Keeps outputs/ (the deliverables) and every other file.
    In a git clone, any path that contains a file tracked by git is skipped.
    Prints the MB freed. Safe to rerun (missing paths are skipped).

    Rebuild the venv with:
        py -m venv $env:LOCALAPPDATA\venvs\<project>; & $env:LOCALAPPDATA\venvs\<project>\Scripts\pip install -r requirements.txt

.PARAMETER DryRun
    List what would be removed and how many MB it would free, without deleting.

.EXAMPLE
    .\clean.ps1
.EXAMPLE
    .\clean.ps1 -DryRun
#>
[CmdletBinding()]
param([switch]$DryRun)

# Project name: also the venv and cache folder name under %LOCALAPPDATA%.
$Project = 'finland-unemployment-paradox'

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
if (-not $root) { $root = Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not (Test-Path -LiteralPath (Join-Path $root 'requirements.txt'))) {
    Write-Error "Refusing to run: no requirements.txt next to clean.ps1 in $root."
    exit 1
}
if (-not $env:LOCALAPPDATA) {
    Write-Error 'Refusing to run: LOCALAPPDATA is not set (this script is for Windows).'
    exit 1
}
$isGit = Test-Path -LiteralPath (Join-Path $root '.git')
$haveGit = [bool](Get-Command git -ErrorAction SilentlyContinue)

function Get-Bytes([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { return [int64]0 }
    $item = Get-Item -LiteralPath $path -Force
    if (-not $item.PSIsContainer) { return [int64]$item.Length }
    $sum = (Get-ChildItem -LiteralPath $path -Recurse -Force -File -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum).Sum
    if ($sum) { return [int64]$sum } else { return [int64]0 }
}

function Test-HasTrackedFiles([string]$path) {
    if (-not $path.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) { return $false }
    if (-not $isGit) { return $false }
    if (-not $haveGit) { return $true }   # git clone but no git: be safe and skip
    $tracked = & git -C $root ls-files -- $path 2>$null
    return [bool]$tracked
}

# Outside the project folder
$targets = @(
    (Join-Path $env:LOCALAPPDATA "venvs\$Project"),
    (Join-Path $env:LOCALAPPDATA "project-data\$Project")
)
# Inside the project folder (outputs/ is kept)
$targets += @('.venv', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'data') | ForEach-Object { Join-Path $root $_ }
$sep = [IO.Path]::DirectorySeparatorChar
$skipUnder = @((Join-Path $root '.venv') + $sep, (Join-Path $root '.git') + $sep)
$targets += @(Get-ChildItem -LiteralPath $root -Recurse -Force -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq '__pycache__' -or $_.Name -eq '.ipynb_checkpoints' } |
    Where-Object { $p = $_.FullName; -not ($skipUnder | Where-Object { $p.StartsWith($_, [StringComparison]::OrdinalIgnoreCase) }) } |
    ForEach-Object { $_.FullName })
$targets = @($targets | Where-Object { Test-Path -LiteralPath $_ })

$freed = [int64]0
$failed = @()
if (-not $targets) { Write-Host 'Nothing to clean.' }

foreach ($t in $targets) {
    if (Test-HasTrackedFiles $t) {
        Write-Warning "Skipping $t (contains files tracked by git)."
        continue
    }
    $bytes = Get-Bytes $t
    if ($DryRun) {
        Write-Host ('Would remove {0,10:N1} MB  {1}' -f ($bytes / 1MB), $t)
        $freed += $bytes
        continue
    }
    try {
        Remove-Item -LiteralPath $t -Recurse -Force
        Write-Host ('Removed      {0,10:N1} MB  {1}' -f ($bytes / 1MB), $t)
        $freed += $bytes
    } catch {
        $left = Get-Bytes $t
        $freed += ($bytes - $left)
        $failed += $t
        Write-Warning "Could not fully remove $t (a file may be in use): $($_.Exception.Message)"
    }
}

$folder = Get-Bytes $root
if ($DryRun) {
    Write-Host ('Dry run: would free {0:N1} MB. Project folder: {1:N1} MB.' -f ($freed / 1MB), ($folder / 1MB))
} else {
    Write-Host ('Freed {0:N1} MB. Project folder now {1:N1} MB.' -f ($freed / 1MB), ($folder / 1MB))
    Write-Host "Rebuild the venv with: py -m venv `$env:LOCALAPPDATA\venvs\$Project; & `$env:LOCALAPPDATA\venvs\$Project\Scripts\pip install -r requirements.txt"
}
if ($failed) { exit 1 }
exit 0
