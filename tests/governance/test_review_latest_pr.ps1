#Requires -Version 5.1
<#
.SYNOPSIS
    Governance regression tests for scripts/captain/review_latest_pr.ps1 helpers.

.DESCRIPTION
    Covers PowerShell 5.1-safe JSON/text boundaries without calling real merge/review
    and without printing secret-shaped content. Uses synthetic fixtures and a fake gh
    on PATH for selected integration checks.

.NOTES
    Exit 0 on success; non-zero on failure. Does not read .env.
    This file must be saved as UTF-8 with BOM for Windows PowerShell 5.1.
#>

$ErrorActionPreference = "Continue"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ScriptPath = Join-Path $RepoRoot "scripts\captain\review_latest_pr.ps1"

if (-not (Test-Path -LiteralPath $ScriptPath)) {
    Write-Error "Missing review_latest_pr.ps1"
    exit 1
}

# Dot-source helpers only (main flow is gated by IsDotSourced).
. $ScriptPath

$script:FailCount = 0
$script:PassCount = 0

function Assert-True {
    param([bool]$Condition, [string]$Name)
    if ($Condition) {
        Write-Host "PASS: $Name" -ForegroundColor Green
        $script:PassCount++
    } else {
        Write-Host "FAIL: $Name" -ForegroundColor Red
        $script:FailCount++
    }
}

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

function New-FixtureBody {
    <#
    .SYNOPSIS
        Build a challenging PR body covering required edge cases (no real secrets).
    #>
    $dq = [char]34
    $sq = [char]39
    $bs = [char]92
    $lf = [char]10
    $crlf = ([char]13).ToString() + ([char]10).ToString()
    $tab = [char]9

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("# Chinese title and body")
    $lines.Add(("Mixed EN/Chinese quotes: {0}double{0} and {1}single{1}." -f $dq, $sq))
    $lines.Add(("Backslash path: D:{0}SAGE125-AI-Scientist{0}scripts{0}captain" -f $bs))
    $lines.Add(("Windows path: D:{0}SAGE125-AI-Scientist" -f $bs))
    $fence = ([char]96).ToString() * 3
    $lines.Add(($fence + "powershell"))
    $lines.Add(("Write-Host {0}hello{0}" -f $dq))
    $lines.Add($fence)
    $jsonShape = "JSON-shaped text: " + ([char]123).ToString() + ([char]34).ToString() + "status" + ([char]34).ToString() + ":" + ([char]34).ToString() + "planned" + ([char]34).ToString() + ([char]125).ToString()
    $lines.Add($jsonShape)
    $lines.Add("- list item one")
    $lines.Add("- list item two")
    $lines.Add("Emoji: OK")
    $lines.Add(("Tabs:{0}here{0}between" -f $tab))
    $lines.Add("Angle chars: less-than tag greater-than and ampersand")
    $lines.Add("Trigger-like text: @codex review (not a secret)")
    $lines.Add("CRLF block follows:")

    $bodyLf = [string]::Join($lf.ToString(), $lines)
    $bodyCrlf = [string]::Join($crlf, $lines)

    # Inject angle/ampersand characters via char codes (avoid parser edge cases).
    $angle = ([char]60).ToString() + "tag" + ([char]62).ToString() + " " + ([char]38).ToString() + " amp"
    $bodyLf = $bodyLf.Replace("less-than tag greater-than and ampersand", $angle)
    $bodyCrlf = $bodyCrlf.Replace("less-than tag greater-than and ampersand", $angle)

    # Chinese markers (kept as unicode escapes constructed at runtime to avoid parser edge cases)
    $zh = [string]::Concat([char]0x4E2D, [char]0x6587)
    $bodyLf = $bodyLf.Replace("Chinese", $zh)
    $bodyCrlf = $bodyCrlf.Replace("Chinese", $zh)

    $longLine = $zh + " line " + ("x" * 200) + $lf
    $longBody = ($longLine * 80)

    return @{
        Lf    = $bodyLf
        Crlf  = $bodyCrlf
        Empty = ""
        Long  = $longBody
    }
}

Write-Host "==== Helper unit tests ===="

$joined = Convert-GhOutputToSingleString -Raw @('{"a":1}', '{"b":2}')
Assert-True ($joined -match '"a"') "array output joins to single string"

$single = Convert-GhOutputToSingleString -Raw '{"ok":true}'
Assert-Equal '{"ok":true}' $single "string output preserved"

$bodies = New-FixtureBody
$tmpJson = New-CaptainTempPath -Extension ".json"
try {
    $machine = [ordered]@{
        number = 3
        title  = "[GOVERNANCE] zh and English"
        path_sample = ("D:{0}SAGE125-AI-Scientist" -f [char]92)
        json_shape = '{"status":"planned"}'
        labels = @(@{ name = "T09" })
    }
    $jsonText = ($machine | ConvertTo-Json -Depth 5 -Compress)
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($tmpJson, $jsonText, $utf8)
    $parsed = Read-Utf8JsonFile -Path $tmpJson -CommandCategory "fixture_machine" -PrNumber 3
    Assert-Equal 3 $parsed.number "machine number parsed"
    Assert-True ($parsed.title -match "GOVERNANCE") "machine title parsed"
    Assert-True ($parsed.path_sample -match "SAGE125") "windows path field parsed"
} finally {
    if (Test-Path $tmpJson) { Remove-Item -LiteralPath $tmpJson -Force }
}

Assert-True ($bodies.Lf.Length -gt 50) "fixture LF body non-trivial"
Assert-True ($bodies.Crlf.Contains([char]13)) "fixture CRLF body has CR"
Assert-equal 0 $bodies.Empty.Length "empty body allowed"
Assert-True ($bodies.Long.Length -gt 10000) "long body fixture"

foreach ($caseName in @("Lf", "Crlf", "Empty", "Long")) {
    $original = $bodies[$caseName]
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($original)
    $b64 = [Convert]::ToBase64String($bytes)
    if ($caseName -eq "Empty") {
        $decoded = ""
    } else {
        $decoded = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b64))
    }
    Assert-Equal $original.Length $decoded.Length ("body base64 roundtrip length: $caseName")
    Assert-True ($decoded -eq $original) ("body base64 roundtrip content: $caseName")
}

$cls0 = Get-CheckClassification -Checks @()
Assert-equal 0 $cls0.Total "checks 0 total"
Assert-equal 0 $cls0.SuccessCount "checks 0 success"
Assert-equal "missing" $cls0.BugbotStatus "bugbot missing when absent"

$clsMixed = Get-CheckClassification -Checks @(
    [pscustomobject]@{ name = "pytest"; bucket = "fail"; state = "FAILURE" },
    [pscustomobject]@{ name = "lint"; bucket = "pass"; state = "SUCCESS" },
    [pscustomobject]@{ name = "Cursor Bugbot"; bucket = "pending"; state = "PENDING" },
    [pscustomobject]@{ name = "old"; bucket = "skipping"; state = "SKIPPED" },
    [pscustomobject]@{ name = "x"; bucket = "cancel"; state = "CANCELLED" }
)
Assert-equal 5 $clsMixed.Total "mixed checks total"
Assert-equal 1 $clsMixed.SuccessCount "only pass counts as success"
Assert-equal 4 $clsMixed.NonPassing.Count "non-pass includes fail/pending/skipping/cancel"
Assert-equal "pending" $clsMixed.BugbotStatus "bugbot pending not success"

$map = Get-TaskOwnerMap
$own = Test-PathOwnership -TaskOwnerMap $map -TaskCode "UNKNOWN" -ChangedFiles @(
    [pscustomobject]@{ path = ".cursor/BUGBOT.md" },
    [pscustomobject]@{ path = "docs/governance/pr-review-policy.yaml" },
    [pscustomobject]@{ path = "scripts/captain/review_latest_pr.ps1" }
)
Assert-equal 3 $own.CaptainOnlyHits.Count "governance files are captain-only"
Assert-equal 0 $own.OutOfScopeFiles.Count "no out-of-scope among captain-only set"

$probe = New-CaptainTempPath -Extension ".json"
$tempRoot = [System.IO.Path]::GetTempPath().TrimEnd('\')
Assert-True ($probe.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) "temp path outside repo"
Assert-True ($probe.IndexOf($RepoRoot, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) "temp path not under repo"

$bad = New-CaptainTempPath -Extension ".json"
try {
    [System.IO.File]::WriteAllText($bad, "{not-json-payload}", (New-Object System.Text.UTF8Encoding $false))
    $threw = $false
    $msg = ""
    try {
        $null = Read-Utf8JsonFile -Path $bad -CommandCategory "bad_json" -PrNumber 3
    } catch {
        $threw = $true
        $msg = $_.Exception.Message
    }
    Assert-True $threw "invalid JSON throws"
    Assert-True ($msg -match "category=bad_json") "error includes category"
    Assert-True ($msg -match "chars=") "error includes char count"
    Assert-True ($msg -match "exception=") "error includes exception type"
    Assert-True ($msg -notmatch "not-json-payload") "error message does not echo fixture payload"
} finally {
    if (Test-Path $bad) { Remove-Item -LiteralPath $bad -Force }
}

Write-Host "==== Fake gh DryRun side-effect guard ===="

$fakeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("sage125-fake-gh-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $fakeRoot -Force | Out-Null
$fakeGh = Join-Path $fakeRoot "gh.cmd"
$logFile = Join-Path $fakeRoot "calls.log"
$machineFixture = Join-Path $fakeRoot "machine.json"
$bodyB64Fixture = Join-Path $fakeRoot "body.b64"
$checksFixture = Join-Path $fakeRoot "checks.json"

$machineObj = @{
    number = 303
    title = "[GOVERNANCE] fake body stress"
    author = @{ login = "liuyanbo12" }
    url = "https://example.invalid/pr/303"
    isDraft = $true
    baseRefName = "integration/2026-08-10"
    headRefName = "captain/cursor-pr-review-automation"
    headRepositoryOwner = @{ login = "sage125-ai-scientist-team" }
    headRefOid = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    mergeable = "MERGEABLE"
    mergeStateStatus = "UNSTABLE"
    changedFiles = 1
    additions = 10
    deletions = 0
    files = @(@{ path = "docs/governance/CURSOR_PR_REVIEW_RUNBOOK.md"; additions = 10; deletions = 0 })
    updatedAt = "2026-07-26T00:00:00Z"
    labels = @()
}
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($machineFixture, ($machineObj | ConvertTo-Json -Depth 6 -Compress), $utf8)
$stressBody = $bodies.Lf + ([char]13 + [char]10) + $bodies.Crlf
$bodyTextFixture = Join-Path $fakeRoot "body.txt"
[System.IO.File]::WriteAllText($bodyTextFixture, $stressBody, $utf8)
[System.IO.File]::WriteAllText($bodyB64Fixture, [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($stressBody)), $utf8)
[System.IO.File]::WriteAllText($checksFixture, "[]", $utf8)

# Write fake gh.cmd line-by-line to avoid PowerShell parsing batch syntax.
$cmdLines = @(
    "@echo off",
    ('echo %%*>>"{0}"' -f $logFile),
    "setlocal EnableDelayedExpansion",
    'set "ARGS=%*"',
    'echo !ARGS! | findstr /C:"auth status" >nul',
    "if not errorlevel 1 (",
    "  echo github.com",
    "  echo   Logged in to github.com account liuyanbo12",
    "  exit /b 0",
    ")",
    'echo !ARGS! | findstr /C:"repo view" >nul',
    "if not errorlevel 1 (",
    '  echo {"name":"SAGE125-AI-Scientist"}',
    "  exit /b 0",
    ")",
    'echo !ARGS! | findstr /C:"pr checks" >nul',
    "if not errorlevel 1 (",
    ('  type "{0}"' -f $checksFixture),
    "  exit /b 0",
    ")",
    'echo !ARGS! | findstr /C:"api graphql" >nul',
    "if not errorlevel 1 (",
    '  echo {"data":{"repository":{"pullRequest":{"reviewThreads":{"nodes":[]}}}}}',
    "  exit /b 0",
    ")",
    'echo !ARGS! | findstr /C:".body" >nul',
    "if not errorlevel 1 (",
    ('  type "{0}"' -f $bodyTextFixture),
    "  exit /b 0",
    ")",
    'echo !ARGS! | findstr /C:"pr view" >nul',
    "if not errorlevel 1 (",
    ('  type "{0}"' -f $machineFixture),
    "  exit /b 0",
    ")",
    'echo !ARGS! | findstr /C:"pr review" >nul',
    "if not errorlevel 1 (",
    ('  echo REVIEW_CALLED>>"{0}"' -f $logFile),
    "  exit /b 0",
    ")",
    'echo !ARGS! | findstr /C:"pr merge" >nul',
    "if not errorlevel 1 (",
    ('  echo MERGE_CALLED>>"{0}"' -f $logFile),
    "  exit /b 0",
    ")",
    'echo {"ok":true}',
    "exit /b 0"
)
[System.IO.File]::WriteAllLines($fakeGh, $cmdLines, [System.Text.Encoding]::ASCII)

$oldPath = $env:PATH
try {
    $env:PATH = $fakeRoot + ";" + $oldPath

    $bundle = Get-PrMachineDetail -PrNumber 303
    Assert-Equal 303 $bundle.Machine.number "fake gh machine number"
    Assert-True ($bundle.BodyCharCount -gt 100) "fake gh body loaded with stress content"
    Assert-True ($bundle.BodyText -match "planned") "body retains JSON-shaped text"
    Assert-True ($bundle.BodyText -match "SAGE125-AI-Scientist") "body retains windows path"
    Assert-True ($bundle.BodyText.IndexOf([string]::Concat([char]0x4E2D, [char]0x6587)) -ge 0) "body retains Chinese"

    $cls = Get-CheckClassification -Checks $bundle.Checks
    Assert-equal 0 $cls.Total "fake checks empty => total 0 (WAIT semantics for caller)"

    $log = Get-Content -LiteralPath $logFile -ErrorAction SilentlyContinue
    $logText = if ($log) { $log -join "`n" } else { "" }
    Assert-True ($logText -notmatch "REVIEW_CALLED") "no review call during helper tests"
    Assert-True ($logText -notmatch "MERGE_CALLED") "no merge call during helper tests"
} finally {
    $env:PATH = $oldPath
    if (Test-Path $fakeRoot) { Remove-Item -LiteralPath $fakeRoot -Recurse -Force -ErrorAction SilentlyContinue }
}

Write-Host ""
Write-Host ("Summary: pass={0} fail={1}" -f $script:PassCount, $script:FailCount)
if ($script:FailCount -gt 0) { exit 1 }
exit 0
