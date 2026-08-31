<#
.SYNOPSIS
    Register (or remove) Gridiron's scheduled tasks with the Windows scheduler.

.DESCRIPTION
    Uses the OS scheduler, not an in-process timer. A timer dies with the window
    that started it, and a forecaster that silently stops running is worse than
    one that was never installed: the record simply stops growing and nothing
    says so. Windows Task Scheduler survives reboots, logoffs and closed
    terminals, and the SCHEDULE panel in the app reports what actually ran.

    Four tasks:

      Gridiron-Refresh      every 4 hours, on the hour. Re-reads each sport's
                            CURRENT season so a game that finished in the world
                            is marked finished here. Without it the resolver has
                            nothing to find and the record never moves.

      Gridiron-Resolve      every 4 hours, twenty minutes after Refresh.
                            Idempotent and cheap: `resolve_all`
                            only touches rows whose resolved_utc is NULL, so a
                            second run in the same hour settles nothing.
                            Baseball finishes games all evening, so four-hourly
                            keeps the record within hours of the sport.

      Gridiron-Predict-MLB  daily 11:00 local, after most probable starters have
                            posted. Each run records how many forecasts were
                            made without a named starter, so this time can be
                            revisited with evidence rather than opinion.

      Gridiron-Predict-NFL  weekly, Wednesday 11:00 local. Inside the 21-day
                            forecast horizon and after the week's injury reports
                            begin.

      Gridiron-Predict-NBA  daily 11:00 local. A no-op with a logged line until
                            the season starts, which is deliberate: the log
                            shows the appliance is alive during the off-season.

      Gridiron-CatchUp      at logon. `resolve` runs unconditionally; each
                            `predict` runs ONLY if its slate has not started.
                            A slate that has begun is recorded MISSED with its
                            reason and is never forecast late.

.PARAMETER Remove
    Unregister all Gridiron tasks and exit. Leaves the database untouched.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools\schedule_install.ps1
    powershell -ExecutionPolicy Bypass -File tools\schedule_install.ps1 -Remove
#>

[CmdletBinding()]
param(
    [switch]$Remove,
    [string]$Time = "11:00"
)

$ErrorActionPreference = "Stop"

$Repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $Repo ".venv\Scripts\python.exe"
$Prefix = "Gridiron-"

$TaskNames = @(
    "$($Prefix)Refresh",
    "$($Prefix)Resolve",
    "$($Prefix)Predict-MLB",
    "$($Prefix)Predict-NFL",
    "$($Prefix)Predict-NBA",
    "$($Prefix)CatchUp"
)

function Remove-GridironTasks {
    foreach ($name in $TaskNames) {
        $existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if ($null -ne $existing) {
            Unregister-ScheduledTask -TaskName $name -Confirm:$false
            Write-Host "  removed $name"
        }
    }
}

if ($Remove) {
    Write-Host "Removing Gridiron scheduled tasks..."
    Remove-GridironTasks
    Write-Host "Done. The database and its record are untouched."
    exit 0
}

if (-not (Test-Path $Python)) {
    Write-Error "No interpreter at $Python. Create the venv first."
    exit 1
}

Write-Host "Installing Gridiron scheduled tasks from $Repo"
# Idempotent: registering twice must not leave two copies firing.
Remove-GridironTasks

function New-GridironTask {
    param(
        [string]$Name,
        [string]$TaskArg,
        [Microsoft.Management.Infrastructure.CimInstance[]]$Trigger,
        [string]$Description
    )
    $action = New-ScheduledTaskAction -Execute $Python `
        -Argument "-m gridiron.cli task $TaskArg" -WorkingDirectory $Repo
    # Run whether or not the user is logged on would need stored credentials;
    # this runs as the logged-on user, which is what a personal appliance wants.
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $Trigger `
        -Settings $settings -Description $Description | Out-Null
    Write-Host "  registered $Name"
}

# refresh — every four hours, ON THE HOUR, twenty minutes AHEAD of resolve.
#
# THE ORDER IS THE WHOLE POINT AND ITS ABSENCE STALLED THE RECORD. The resolver
# settles against `games.status`; nothing else updates `games.status`. With no
# refresh task at all, `resolve` ran every four hours for two days, reported
# "no prediction had a finished game waiting" truthfully every time, and the
# record sat at six settled while 27 predictions waited on games that had
# finished in the world and were still marked `scheduled` here.
#
# Twenty minutes of gap, not zero: a refresh that is still fetching when the
# resolver starts leaves the resolver reading the table mid-write.
New-GridironTask -Name "$($Prefix)Refresh" -TaskArg "refresh" `
    -Trigger (New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours((Get-Date).Hour + 1) `
              -RepetitionInterval (New-TimeSpan -Hours 4)) `
    -Description "Re-read each sport's current season so finished games are marked finished. Runs before Resolve."

# resolve — every four hours, twenty minutes after the refresh.
New-GridironTask -Name "$($Prefix)Resolve" -TaskArg "resolve" `
    -Trigger (New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours((Get-Date).Hour + 1).AddMinutes(20) `
              -RepetitionInterval (New-TimeSpan -Hours 4)) `
    -Description "Settle every Gridiron prediction whose game has finished. Idempotent. Runs after Refresh."

New-GridironTask -Name "$($Prefix)Predict-MLB" -TaskArg "predict:mlb" `
    -Trigger (New-ScheduledTaskTrigger -Daily -At $Time) `
    -Description "Forecast today's MLB slate, blind, after probable starters post."

New-GridironTask -Name "$($Prefix)Predict-NFL" -TaskArg "predict:nfl" `
    -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Wednesday -At $Time) `
    -Description "Forecast this week's NFL slate, blind."

New-GridironTask -Name "$($Prefix)Predict-NBA" -TaskArg "predict:nba" `
    -Trigger (New-ScheduledTaskTrigger -Daily -At $Time) `
    -Description "Forecast today's NBA slate, blind. A logged no-op out of season."

# The logon trigger is scoped to THIS user on purpose. Without -User it applies
# to every account on the machine, which Windows treats as a system-wide change
# and refuses without elevation - the install got four tasks in and then failed
# with Access Denied. A personal appliance wants the current user anyway.
New-GridironTask -Name "$($Prefix)CatchUp" -TaskArg "catch-up" `
    -Trigger (New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME") `
    -Description "After a sleep: resolve unconditionally, predict only slates that have not started."

Write-Host ""
Write-Host "Installed. Check what has actually run with:"
Write-Host "    .venv\Scripts\python.exe -m gridiron.cli schedule"
Write-Host "or the SCHEDULE panel in the app. A task silent past its window says so."
Write-Host ""
Write-Host "To remove:  powershell -ExecutionPolicy Bypass -File tools\schedule_install.ps1 -Remove"
