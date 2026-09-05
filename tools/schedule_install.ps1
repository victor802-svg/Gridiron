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
    [string]$Time = "11:00",
    # College football gets its own hour: its slates start earlier in the day
    # than baseball's, and 09:00 is the operator's ruling of 2026-09-02.
    [string]$CfbTime = "09:00"
)

$ErrorActionPreference = "Stop"

$Repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
# NO CONSOLE WINDOW (ruling 2 on the audit, 2026-09-05). Two tasks died with
# exit 0xC000013A -- STATUS_CONTROL_C_EXIT -- which is what a console process
# gets when its window is closed or the session it belongs to ends. pythonw
# has no console to close. Nothing is lost: every task records its own row
# in task_runs and prints nothing anyone was reading.
$Python = Join-Path $Repo ".venv\Scripts\pythonw.exe"
$Prefix = "Gridiron-"

$TaskNames = @(
    "$($Prefix)Refresh",
    "$($Prefix)Resolve",
    "$($Prefix)Predict-MLB",
    "$($Prefix)Predict-NFL",
    "$($Prefix)Predict-NBA",
    "$($Prefix)Predict-CFB",
    "$($Prefix)Final-MLB",
    "$($Prefix)Final-NFL",
    "$($Prefix)Final-NBA",
    "$($Prefix)Final-CFB",
    "$($Prefix)Predict-UFC",
    "$($Prefix)Final-UFC",
    "$($Prefix)Recalibrate",
    "$($Prefix)Capture",
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

# predict:cfb — DAILY, and the reason is the shape of a college week.
#
# The operator's ruling of 2026-09-02 says "Friday 09:00". The hour is kept;
# the WEEKLY part is not, and this is the note saying why rather than a silent
# substitution.
#
# A college week is three different slates. September 2026, as stored:
#
#     Thu 03 Sep    6 games
#     Fri 04 Sep    8 games
#     Sat 05 Sep   60 games      <-- the week
#     Sun 06 Sep   16 games
#
# A Friday-only task forecasts the eight and misses the seventy-six. It cannot
# pick them up later either: `predict` refuses a slate that has already
# started, records it MISSED with its reason, and never forecasts late -- which
# is correct, and which would mean Saturday was recorded MISSED every week of
# the season.
#
# `tasks.TASKS["predict:cfb"]` also declares `every_hours=24, silent_after=36`,
# so a weekly trigger would leave the health panel reporting the task silent
# six days in seven and the failure channel firing on it. The two would
# disagree permanently.
#
# The same conclusion is already recorded in docs/closeouts/2026-09-01-cfb.md:
# "a weekly task would ask one question of three different cards."
#
# A day with no college football is a logged no-op, exactly as Predict-NBA is
# out of season. To make it Friday-only anyway, change -Daily to
# `-Weekly -DaysOfWeek Friday`.
New-GridironTask -Name "$($Prefix)Predict-CFB" -TaskArg "predict:cfb" `
    -Trigger (New-ScheduledTaskTrigger -Daily -At $CfbTime) `
    -Description "Forecast today's college football slate, blind. A logged no-op on a day with no games."

# ---------------------------------------------------------------------------
# THE SECOND, LATER PASS (2026-09-03)
# ---------------------------------------------------------------------------
#
# Every sport is forecast twice: once when the slate is first seen, and again
# close to start on what is known by then. The LATER row is the one the record
# is graded on; the early row is kept and labelled.
#
# WHY THIS MATTERS ENOUGH TO ADD FOUR TASKS. Measured lead times before this
# existed: MLB 7.7h, CFB 108h, NFL 371h, and NBA 1,325 HOURS -- 55 days. A
# forecast written 55 days out is made before rosters settle and before any
# injury is known. Whether forecasting later actually scores better is NOT
# assumed: `early_vs_final` measures it, gated at 50 paired games.
#
# ONLY ONE OF THESE TIMES WAS MEASURED. docs/TIMING_FEASIBILITY.md records
# why the other three could not be -- the NFL injuries table carries no
# timestamp at all, no college injury data is stored, and the NBA table holds
# about 75 rows. MLB's T-1h30m comes from 39 real lineup captures: 85% were up
# by then against 46% at the 2h30m originally proposed.
#
# 14:30 LOCAL, AND IT SERVES THE EVENING CARD ONLY. Measured first pitches,
# on this machine's clock (UTC-7): 16:00 local carries 2,382 games and 15:00
# local 1,288 -- the two biggest clusters by a distance. T-1h30m before 16:00
# is 14:30.
#
# THE DAY GAMES ARE NOT COVERED BY IT, and saying so is the point. A baseball
# night spreads 7.47 hours from first pitch to last (docs/TIMING_FEASIBILITY
# section 6), so ONE daily pass cannot sit close to every game: at 14:30 the
# 10:00 local games have been under way for four hours, and the final pass
# correctly writes nothing for them -- their early forecast stands and is
# labelled as the only one they got.
#
# Fixing that properly means a per-game trigger rather than a daily one, which
# is a bigger change than this brief asked for and is recorded as such.
New-GridironTask -Name "$($Prefix)Final-MLB" -TaskArg "final:mlb" `
    -Trigger (New-ScheduledTaskTrigger -Daily -At "14:30") `
    -Description "Re-forecast today's baseball slate close to first pitch, on what is known then."

New-GridironTask -Name "$($Prefix)Final-NFL" -TaskArg "final:nfl" `
    -Trigger (New-ScheduledTaskTrigger -Daily -At "08:00") `
    -Description "Re-forecast the football slate on the morning of the games."

New-GridironTask -Name "$($Prefix)Final-NBA" -TaskArg "final:nba" `
    -Trigger (New-ScheduledTaskTrigger -Daily -At "15:00") `
    -Description "Re-forecast tonight's basketball slate after the league's injury report window."

New-GridironTask -Name "$($Prefix)Final-CFB" -TaskArg "final:cfb" `
    -Trigger (New-ScheduledTaskTrigger -Daily -At "08:00") `
    -Description "Re-forecast the college football slate on the morning of the games."

# THE FIGHTS (audit 2026-09-05). `predict:ufc` and `final:ufc` were declared
# in the app on 2026-09-03 and never registered here, so every UFC forecast in
# the record was run by hand. Daily, like baseball: about 4.3 cards a month
# with no season shape, and a day with no card is a logged no-op.
#
# Final-UFC at 12:00 local. `config.FINAL_PASS["ufc"]` asks for three hours
# before the first bout and says it is NOT measured; the 2026 record puts the
# first bout at 14:00 local on the early cards and 16:00 on most. 12:00 is
# three hours before the early ones. Change it when the timing is measured.
New-GridironTask -Name "$($Prefix)Predict-UFC" -TaskArg "predict:ufc" `
    -Trigger (New-ScheduledTaskTrigger -Daily -At "11:00") `
    -Description "Forecast the next UFC card, blind. A logged no-op on a day with no card."

New-GridironTask -Name "$($Prefix)Final-UFC" -TaskArg "final:ufc" `
    -Trigger (New-ScheduledTaskTrigger -Daily -At "12:00") `
    -Description "Re-forecast the fights close to the first bout, on what is known then."

# THE WEEKLY RE-FIT (audit 2026-09-05). `recalibrate` has declared a weekly
# cadence since 2026-08-31 and nothing ever registered it, so the claim
# corrections were refitted twice, both times by hand. Monday morning, after
# the weekend's slates have settled.
New-GridironTask -Name "$($Prefix)Recalibrate" -TaskArg "recalibrate" `
    -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "06:00") `
    -Description "Re-fit each category's claim correction against its settled record, once a week."

# ---------------------------------------------------------------------------
# WHAT WAS KNOWABLE, WHEN (S1, 2026-09-03)
# ---------------------------------------------------------------------------
#
# Every four hours, stamping the injury report and any posted lineup into
# append-only tables. The point is the SEQUENCE: a player appearing as
# questionable and later as out is the thing a timing probe needs, and a daily
# capture would record the end of that story and none of it.
#
# WHY IT EXISTS AT ALL. The timing probe of 2026-09-02 could not measure three
# sports out of four -- not because the data was missing, but because it
# carried no capture time. 55,554 injury rows, not one dated; 6,902 of 6,958
# lineups from a single backfill. Averaging those said lineups post "10,592
# hours before first pitch", which is 441 days AFTER the game.
New-GridironTask -Name "$($Prefix)Capture" -TaskArg "capture" `
    -Trigger (New-ScheduledTaskTrigger -Once -At "00:15" `
        -RepetitionInterval (New-TimeSpan -Hours 4)) `
    -Description "Stamp the injury report and tonight's lineups, so what was knowable when becomes data."

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
