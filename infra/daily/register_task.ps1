# Registers (or replaces) the Windows scheduled task "DORA experimento diario": every day at 10:00, and as soon as
# the PC is on if it was off at that time, it runs eval/daily/run_daily.py from the daily-experiments worktree.
# Run once: powershell -ExecutionPolicy Bypass -File infra/daily/register_task.ps1
$wt = "D:\projects\dora-hackathon\.claude\worktrees\daily-experiments"
$py = "D:\projects\dora-hackathon\.venv\Scripts\python.exe"
$log = "D:\projects\tools\daily-experiment.log"
$action = New-ScheduledTaskAction -Execute "cmd.exe" `
  -Argument "/c `"`"$py`" -I eval\daily\run_daily.py >> `"$log`" 2>&1`"" -WorkingDirectory $wt
$trigger = New-ScheduledTaskTrigger -Daily -At 10:00
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 6) `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "DORA experimento diario" -Action $action -Trigger $trigger -Settings $settings `
  -Description "Un experimento nuevo por día en el proxy de Kaggle (cola en eval/daily/queue.json)" -Force | Out-Null
Get-ScheduledTask -TaskName "DORA experimento diario" | Select-Object TaskName, State
