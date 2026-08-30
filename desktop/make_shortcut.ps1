<#
.SYNOPSIS
    Put Gridiron on the Desktop and in the Start Menu.

.DESCRIPTION
    Both shortcuts set their WORKING DIRECTORY to the repository, not to the
    bundle. That is what keeps the record and the access token outside dist/:
    the launcher resolves `var/gridiron.db` and `.env` relative to where it was
    started, so a rebuild that replaces dist/ wholesale cannot touch either.

    The shortcuts do not touch the scheduled tasks and are not needed by them.
    `Gridiron-Resolve` and the three predict tasks call the CLI directly against
    the database; the record is kept whether anybody opens a window or not.

.PARAMETER Remove
    Delete both shortcuts. The bundle, the database and the token stay.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File desktop\make_shortcut.ps1
    powershell -ExecutionPolicy Bypass -File desktop\make_shortcut.ps1 -Remove
#>

[CmdletBinding()]
param([switch]$Remove)

$ErrorActionPreference = "Stop"

$Repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Exe = Join-Path $Repo "dist\Gridiron\Gridiron.exe"
$Icon = Join-Path $Repo "desktop\gridiron.ico"

$Desktop = Join-Path ([Environment]::GetFolderPath("Desktop")) "Gridiron.lnk"
$StartMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "Gridiron.lnk"

if ($Remove) {
    foreach ($path in @($Desktop, $StartMenu)) {
        if (Test-Path $path) { Remove-Item $path -Force; Write-Host "  removed $path" }
    }
    Write-Host "Done. The bundle, the database and the token are untouched."
    exit 0
}

if (-not (Test-Path $Exe)) {
    Write-Host "No build found at $Exe"
    Write-Host ""
    Write-Host "Build it first:"
    Write-Host "    .venv\Scripts\pyinstaller.exe desktop\gridiron.spec --noconfirm"
    Write-Host ""
    Write-Host "Nothing was changed."
    exit 1
}

$shell = New-Object -ComObject WScript.Shell
foreach ($path in @($Desktop, $StartMenu)) {
    $link = $shell.CreateShortcut($path)
    $link.TargetPath = $Exe
    # The repository, NOT dist\Gridiron. This is the line that keeps the record
    # and the token outside the bundle.
    $link.WorkingDirectory = $Repo
    $link.IconLocation = $Icon
    $link.Description = "Gridiron - a multi-sport forecaster that grades itself"
    $link.Save()
    Write-Host "  created $path"
}

Write-Host ""
Write-Host "Working directory is $Repo, so the record in var\ and the token in"
Write-Host ".env stay outside the bundle and survive every rebuild."
