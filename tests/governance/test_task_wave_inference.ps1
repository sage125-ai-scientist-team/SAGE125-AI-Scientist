#Requires -Version 5.1
<#
.SYNOPSIS
    PowerShell 5.1 tests for task/wave inference and content-review gate wiring.

.NOTES
    UTF-8 with BOM required. No real merge/review calls.
#>
$ErrorActionPreference = "Continue"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ScriptPath = Join-Path $RepoRoot "scripts\captain\review_latest_pr.ps1"
. $ScriptPath

$script:FailCount = 0
$script:PassCount = 0

function Assert-Equal {
    param($Expected, $Actual, [string]$Name)
    if ("$Expected" -eq "$Actual") {
        Write-Host "PASS: $Name" -ForegroundColor Green
        $script:PassCount++
    } else {
        Write-Host ("FAIL: {0} expected=[{1}] actual=[{2}]" -f $Name, $Expected, $Actual) -ForegroundColor Red
        $script:FailCount++
    }
}

Write-Host "==== Task/Wave inference ===="
Assert-Equal "T09" (Get-InferredTask -Title "[T09-A] Establish quality gates" -HeadRef "t09/a-quality-contract" -Labels @() -BodyText "") "title+branch T09"
Assert-Equal "A" (Get-InferredWave -Title "[T09-A] Establish quality gates" -HeadRef "t09/a-quality-contract" -Labels @() -BodyText "") "title+branch Wave A"
Assert-Equal "CONFLICT" (Get-InferredTask -Title "[T09-A] x" -HeadRef "t02/a-foo" -Labels @() -BodyText "") "task conflict"
Assert-Equal "CONFLICT" (Get-InferredWave -Title "[T09-A] x" -HeadRef "t09/b-quality-core" -Labels @() -BodyText "") "wave conflict"
Assert-Equal "UNKNOWN" (Get-InferredTask -Title "no task here" -HeadRef "feature/foo" -Labels @() -BodyText "") "task unknown"
Assert-Equal "UNKNOWN" (Get-InferredWave -Title "no wave here" -HeadRef "feature/foo" -Labels @() -BodyText "") "wave unknown"

$stressBody = @"
# Chinese title
Task: T09
Wave: A
Path: D:\SAGE125-AI-Scientist\docs\governance
Emoji: OK
JSON-shaped: {"status":"planned"}
"@
Assert-Equal "T09" (Get-InferredTask -Title "hello" -HeadRef "x" -Labels @() -BodyText $stressBody) "body task despite chinese/markdown"
Assert-Equal "A" (Get-InferredWave -Title "hello" -HeadRef "x" -Labels @() -BodyText $stressBody) "body wave despite chinese/markdown"

Write-Host "==== ContentReviewPath gate (missing => WAIT reason) ===="
$gate = Test-ContentReviewGate -ContentReviewPath "" -PrNumber 2 -TaskId "T09" -Wave "A" -HeadSha ("a"*40) -SourceSpecPath (Join-Path $RepoRoot "docs\governance\task-requirements\T09.yaml")
Assert-Equal "False" "$($gate.Ok)" "missing content review not ok"
Assert-Equal "missing ContentReviewPath" $gate.Reason "missing path reason"

Write-Host "==== Spec path exists for T09 ===="
$spec = Get-TaskRequirementPath -TaskId "T09"
Assert-Equal "True" ("$([bool]$spec)") "T09 spec found"

Write-Host ""
Write-Host ("Summary: pass={0} fail={1}" -f $script:PassCount, $script:FailCount)
if ($script:FailCount -gt 0) { exit 1 }
exit 0
