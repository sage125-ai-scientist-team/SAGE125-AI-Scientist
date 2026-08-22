param(
    [string]$Worktree = "D:\SAGE125_Local_Worktrees\formal_125_fast_20260822-155218",
    [string]$Python = "C:\SAGE125_py\python.exe"
)

$ErrorActionPreference = "Stop"
$Stamp = "20260822-155218"
$OutputRoot = "D:\SAGE125_Local_Runs\formal_125_fast_remaining_$Stamp"
$Runtime = Join-Path $OutputRoot "runtime"
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
$Log = Join-Path $Runtime "supervisor.log"
$PidFile = Join-Path $Runtime "launcher.pid"

$existing = Join-Path $Runtime "supervisor.pid"
if (Test-Path $existing) {
    $oldPid = (Get-Content $existing -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
        Write-Output "SUPERVISOR_ALREADY_RUNNING pid=$oldPid"
        Write-Output "RESUME=True"
        exit 0
    }
}

$script = Join-Path $Worktree "scripts\batch_125\run_continuous_fast.py"
$proc = Start-Process -FilePath $Python -ArgumentList @($script, "--mode", "supervisor") -WorkingDirectory $Worktree -WindowStyle Hidden -RedirectStandardOutput $Log -RedirectStandardError (Join-Path $Runtime "supervisor.err.log") -PassThru
$proc.Id | Set-Content $PidFile -Encoding ascii
Write-Output "SUPERVISOR_STARTED pid=$($proc.Id)"
Write-Output "LOG=$Log"
Write-Output "STOP_COMMAND=Stop-Process -Id $($proc.Id)"
exit 0
