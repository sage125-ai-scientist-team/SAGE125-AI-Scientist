param(
    [string]$Worktree = "D:\SAGE125_Local_Worktrees\formal_125_fast_review_rc_20260822-201733",
    [string]$Python = "C:\SAGE125_py\python.exe"
)
$ErrorActionPreference = "Stop"
$Stamp = "20260822-201733"
$Out = "D:\SAGE125_Local_Runs\formal_125_fast_review_rc_$Stamp"
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$script = Join-Path $Worktree "scripts\batch_125\run_review_rc.py"
$log = Join-Path $Out "supervisor.log"
$err = Join-Path $Out "supervisor.err.log"
$proc = Start-Process -FilePath $Python -ArgumentList @("-u", $script, "--mode", "supervisor") -WorkingDirectory $Worktree -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError $err -PassThru
$proc.Id | Set-Content (Join-Path $Out "launcher.pid") -Encoding ascii
Write-Output "SUPERVISOR_PID=$($proc.Id)"
Write-Output "LOG=$log"
exit 0
