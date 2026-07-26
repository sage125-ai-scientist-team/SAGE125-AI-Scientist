#Requires -Version 5.1
<#
.SYNOPSIS
    SAGE125 队长 PR 审核与受控合并辅助脚本。

.DESCRIPTION
    本脚本是「队长一句话触发 PR 审核」工作流的技术执行层：负责选定目标 PR、
    抓取只读元数据（不写入仓库目录）、按 task-owner-map.yaml 做路径所有权检查、
    解析 GitHub Checks / Bugbot 状态、以及（仅当显式传入 -AllowMerge 时）执行
    Approve + Squash Merge。

    设计约束（PowerShell 5.1 兼容）：
    - 机器合并门禁字段与 PR body / 评论正文分离读取；
    - 绝不把完整 PR body 混入同一 ConvertFrom-Json 输入；
    - gh JSON 输出先落盘为 UTF-8 再解析；
    - Checks 使用 gh pr checks --json 的 bucket 字段。

.PARAMETER PrNumber
    指定要审核的 PR 编号；优先于 -Latest。

.PARAMETER Latest
    未指定 -PrNumber 时的默认行为：选择目标仓库中 base=integration/2026-08-10
    （或 -ReleaseMode 下 base=main）、state=open、按 updatedAt 降序排序的第一个 PR。

.PARAMETER DryRun
    仅打印将要执行的操作（包括 Review / Merge 命令），不产生任何真实的
    gh pr review / gh pr merge 调用。

.PARAMETER InspectOnly
    仅做检查与报告，不提交 Review、不合并。这是脚本的默认行为。

.PARAMETER AllowMerge
    显式请求在全部合并门禁满足时执行 Approve + Squash Merge。
    必须同时提供 -ReviewedHeadSha。

.PARAMETER ReleaseMode
    发布模式：目标为 base=main 且 head=integration/2026-08-10 且标题以 [RELEASE] 开头。

.PARAMETER ReviewedHeadSha
    Agent 在审核开始时记录的 head SHA。仅在 -AllowMerge 时必需。

.PARAMETER ApproveBody
    -AllowMerge 且门禁通过时使用的 Approve 评论正文。

.PARAMETER RequestChangesBodyFile
    包含 Request Changes 评论正文的文件路径（Markdown）。

.PARAMETER OutDir
    保存本次审核只读元数据/报告的临时目录（脚本外部，不进入仓库）。

.NOTES
    绝不使用 --admin；绝不 force push；绝不打印任何密钥/Token 值或完整 PR body。
    仓库：sage125-ai-scientist-team/SAGE125-AI-Scientist
    队长账号：liuyanbo12
    本文件必须保存为 UTF-8 with BOM，以便 Windows PowerShell 5.1 正确解析中文。
#>

[CmdletBinding()]
param(
    [int]$PrNumber = 0,
    [switch]$Latest,
    [switch]$DryRun,
    [switch]$InspectOnly,
    [switch]$AllowMerge,
    [switch]$ReleaseMode,
    [string]$ReviewedHeadSha = "",
    [string]$ApproveBody = "Cursor captain review approved: no blocking P0/P1; path ownership, scientific integrity, security, local tests and GitHub Checks are acceptable for squash merge into integration/2026-08-10.",
    [string]$RequestChangesBodyFile = "",
    [string]$OutDir = ""
)

# 注意：不能设为 "Stop"。本脚本大量调用外部 gh.exe，PowerShell 5.1 会把
# 外部进程 stderr 的每一行转成错误记录；一旦 $ErrorActionPreference="Stop"，
# 一次预期内的失败（如 PR 编号不存在）就会被升级成终止性异常。
$ErrorActionPreference = "Continue"

# ============================================================
# 常量：仓库与分支策略（与 docs/governance/*.yaml 保持一致）
# ============================================================
$script:RepoSlug           = "sage125-ai-scientist-team/SAGE125-AI-Scientist"
$script:CaptainAccount     = "liuyanbo12"
$script:OrdinaryBaseBranch = "integration/2026-08-10"
$script:ReleaseBaseBranch  = "main"
$script:ReleaseHeadBranch  = "integration/2026-08-10"
$script:RepoRoot           = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$script:TaskOwnerMapPath   = Join-Path $script:RepoRoot "docs\governance\task-owner-map.yaml"
$script:PrReviewPolicyPath = Join-Path $script:RepoRoot "docs\governance\pr-review-policy.yaml"

# 机器门禁字段：故意不包含 body / comments / reviews[].body
$script:PrMachineJsonFields = @(
    "number", "title", "author", "url", "isDraft",
    "baseRefName", "headRefName", "headRepositoryOwner", "headRefOid",
    "mergeable", "mergeStateStatus", "changedFiles", "additions", "deletions",
    "files", "updatedAt", "labels"
)

$script:ExitCodes = @{
    OK              = 0
    NO_PR           = 10
    NEEDS_CHANGES   = 20
    WAITING         = 30
    SECURITY_ABORT  = 40
    MERGED          = 50
    ENV_ERROR       = 60
}

function Write-Section {
    <#
    .SYNOPSIS
        打印一个带分隔线的小节标题。
    #>
    param([string]$Title)
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor DarkCyan
    Write-Host $Title -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor DarkCyan
}

function Exit-WithCode {
    <#
    .SYNOPSIS
        统一退出出口：打印退出码含义后 exit。
    #>
    param([int]$Code, [string]$Reason)
    Write-Host ""
    Write-Host ("[EXIT $Code] $Reason") -ForegroundColor Yellow
    exit $Code
}

function Convert-GhOutputToSingleString {
    <#
    .SYNOPSIS
        将 gh 命令捕获结果规范为单个完整字符串。
        PowerShell 5.1 在输出含换行时可能返回 Object[]，不能隐式拼接进 ConvertFrom-Json。
    #>
    param($Raw)
    if ($null -eq $Raw) { return "" }
    if ($Raw -is [System.Array]) {
        return (($Raw | ForEach-Object { [string]$_ }) -join "`n")
    }
    return [string]$Raw
}

function New-CaptainTempPath {
    <#
    .SYNOPSIS
        在系统 TEMP 下生成随机临时文件路径（绝不写入仓库目录）。
    #>
    param([string]$Extension = ".json")
    $name = "sage125-captain-" + [guid]::NewGuid().ToString("N") + $Extension
    return (Join-Path $env:TEMP $name)
}

function ConvertTo-GhArgumentString {
    <#
    .SYNOPSIS
        将参数数组安全拼接为 ProcessStartInfo.Arguments 字符串。
        含空格、引号、管道符的参数会被双引号包裹。
    #>
    param([string[]]$GhArgs)
    $parts = New-Object System.Collections.Generic.List[string]
    foreach ($a in $GhArgs) {
        if ($null -eq $a) { continue }
        $s = [string]$a
        if ($s -match '[\s\|"]') {
            $escaped = $s.Replace('"', '\"')
            $parts.Add('"' + $escaped + '"')
        } else {
            $parts.Add($s)
        }
    }
    return ($parts -join ' ')
}

function Invoke-GhCaptureUtf8 {
    <#
    .SYNOPSIS
        通过 System.Diagnostics.Process 以 UTF-8 捕获 gh stdout/stderr。
        避免 PowerShell 5.1 把含换行的输出拆成 Object[]，也避免 & gh 调用 .cmd 时
        对 jq 表达式中管道符的错误拆分。
    .OUTPUTS
        hashtable: ExitCode / StdOut / StdErr
    #>
    param(
        [Parameter(Mandatory)][string[]]$GhArgs,
        [Parameter(Mandatory)][string]$CommandCategory,
        [int]$PrNumber = 0
    )
    # Resolve via Get-Command so a PATH-precedent gh.cmd (tests) wins over a
    # later gh.exe. CreateProcess("gh") alone prefers *.exe via PATHEXT and would
    # skip a fake gh.cmd even when it is earlier on PATH.
    $ghCmd = Get-Command gh -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $ghCmd) {
        throw ("gh executable not found category={0} pr={1}" -f $CommandCategory, $PrNumber)
    }
    $argString = ConvertTo-GhArgumentString -GhArgs $GhArgs
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    # .cmd/.bat cannot be started directly with UseShellExecute=false; wrap via cmd.exe.
    if ($ghCmd.Source -match '\.(cmd|bat)$') {
        $psi.FileName = $env:ComSpec
        $psi.Arguments = '/d /c ""' + $ghCmd.Source + '" ' + $argString + '"'
    } else {
        $psi.FileName = $ghCmd.Source
        $psi.Arguments = $argString
    }
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $utf8 = New-Object System.Text.UTF8Encoding $false
    $psi.StandardOutputEncoding = $utf8
    $psi.StandardErrorEncoding = $utf8

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    try {
        [void]$proc.Start()
        $stdout = $proc.StandardOutput.ReadToEnd()
        $stderr = $proc.StandardError.ReadToEnd()
        $proc.WaitForExit()
        return @{
            ExitCode = $proc.ExitCode
            StdOut   = $stdout
            StdErr   = $stderr
        }
    } catch {
        $exType = $_.Exception.GetType().FullName
        throw ("Invoke-GhCaptureUtf8 failed category={0} pr={1} exception={2}" -f `
            $CommandCategory, $PrNumber, $exType)
    } finally {
        if ($null -ne $proc) { $proc.Dispose() }
    }
}

function Read-Utf8JsonFile {
    <#
    .SYNOPSIS
        以 UTF-8 读取临时 JSON 文件并 ConvertFrom-Json。
        失败时只报告命令类别、PR 编号、字符数与异常类型，不输出正文。
    #>
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$CommandCategory,
        [int]$PrNumber = 0
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        throw ("Read-Utf8JsonFile missing file category={0} pr={1}" -f $CommandCategory, $PrNumber)
    }
    $text = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
    $charCount = $text.Length
    if ($charCount -eq 0) {
        throw ("Read-Utf8JsonFile empty JSON category={0} pr={1} chars=0" -f $CommandCategory, $PrNumber)
    }
    try {
        return ($text | ConvertFrom-Json)
    } catch {
        $exType = $_.Exception.GetType().FullName
        throw ("ConvertFrom-Json failed category={0} pr={1} chars={2} exception={3}" -f `
            $CommandCategory, $PrNumber, $charCount, $exType)
    }
}

function Invoke-GhJson {
    <#
    .SYNOPSIS
        Call gh, write UTF-8 stdout to a temp file, then ConvertFrom-Json.
        Checks exit code; empty output fails; temp files cleaned in finally.
    #>
    param(
        [Parameter(Mandatory)][string]$CommandCategory,
        [Parameter(Mandatory)][string[]]$GhArgs,
        [int]$PrNumber = 0
    )
    $tmp = New-CaptainTempPath -Extension ".json"
    try {
        $cap = Invoke-GhCaptureUtf8 -GhArgs $GhArgs -CommandCategory $CommandCategory -PrNumber $PrNumber
        if ($cap.ExitCode -ne 0) {
            throw ("gh failed category={0} pr={1} exit={2}" -f $CommandCategory, $PrNumber, $cap.ExitCode)
        }
        $text = [string]$cap.StdOut
        if ([string]::IsNullOrWhiteSpace($text)) {
            throw ("gh empty output category={0} pr={1}" -f $CommandCategory, $PrNumber)
        }
        $utf8NoBom = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($tmp, $text, $utf8NoBom)
        return (Read-Utf8JsonFile -Path $tmp -CommandCategory $CommandCategory -PrNumber $PrNumber)
    } finally {
        if (Test-Path -LiteralPath $tmp) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-GhText {
    <#
    .SYNOPSIS
        Call gh for plain text (PR body etc). Supports jq @base64.
        Never feeds body text into ConvertFrom-Json.
    #>
    param(
        [Parameter(Mandatory)][string]$CommandCategory,
        [Parameter(Mandatory)][string[]]$GhArgs,
        [int]$PrNumber = 0,
        [switch]$Base64Utf8
    )
    $tmp = New-CaptainTempPath -Extension ".txt"
    try {
        $cap = Invoke-GhCaptureUtf8 -GhArgs $GhArgs -CommandCategory $CommandCategory -PrNumber $PrNumber
        if ($cap.ExitCode -ne 0) {
            throw ("gh failed category={0} pr={1} exit={2}" -f $CommandCategory, $PrNumber, $cap.ExitCode)
        }
        $text = [string]$cap.StdOut
        if ($Base64Utf8) {
            $text = $text.Trim()
            if ([string]::IsNullOrEmpty($text)) {
                return ""
            }
            try {
                $bytes = [Convert]::FromBase64String($text)
                return [System.Text.Encoding]::UTF8.GetString($bytes)
            } catch {
                $exType = $_.Exception.GetType().FullName
                throw ("Base64 decode failed category={0} pr={1} chars={2} exception={3}" -f `
                    $CommandCategory, $PrNumber, $text.Length, $exType)
            }
        }
        if ($text.EndsWith("`n")) { $text = $text.Substring(0, $text.Length - 1) }
        if ($text.EndsWith("`r")) { $text = $text.Substring(0, $text.Length - 1) }
        $utf8NoBom = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($tmp, $text, $utf8NoBom)
        return [System.IO.File]::ReadAllText($tmp, [System.Text.Encoding]::UTF8)
    } finally {
        if (Test-Path -LiteralPath $tmp) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        }
    }
}

function ConvertFrom-SimpleYaml {
    <#
    .SYNOPSIS
        将 docs/governance/*.yaml 简单子集解析为嵌套 hashtable。
    #>
    param([string[]]$Lines)

    $filtered = New-Object System.Collections.Generic.List[string]
    foreach ($rawLine in $Lines) {
        if ($null -eq $rawLine) { continue }
        if ($rawLine.TrimStart().StartsWith('#')) { continue }
        $noInlineComment = $rawLine -replace '(?<=\s)#.*$', ''
        $trimmedEnd = $noInlineComment.TrimEnd()
        if ($trimmedEnd.Trim() -eq '') { continue }
        $filtered.Add($trimmedEnd)
    }

    $script:__yamlIndex = 0

    function Get-Indent([string]$line) {
        return ($line.Length - $line.TrimStart(' ').Length)
    }

    function Parse-ScalarValue([string]$text) {
        $t = $text.Trim()
        if ($t.Length -ge 2 -and $t.StartsWith('"') -and $t.EndsWith('"')) {
            return $t.Substring(1, $t.Length - 2)
        }
        if ($t -eq 'true') { return $true }
        if ($t -eq 'false') { return $false }
        if ($t -match '^-?\d+$') { return [int]$t }
        return $t
    }

    function Parse-ListBlock([int]$parentIndent) {
        $items = New-Object System.Collections.Generic.List[object]
        while ($script:__yamlIndex -lt $filtered.Count) {
            $line = $filtered[$script:__yamlIndex]
            $indent = Get-Indent $line
            if ($indent -le $parentIndent) { break }
            $content = $line.Trim()
            if (-not $content.StartsWith('- ')) { break }
            $itemText = $content.Substring(2).Trim()
            $script:__yamlIndex++
            $items.Add((Parse-ScalarValue $itemText))
        }
        return $items.ToArray()
    }

    function Parse-MapBlock([int]$parentIndent) {
        $result = [ordered]@{}
        while ($script:__yamlIndex -lt $filtered.Count) {
            $line = $filtered[$script:__yamlIndex]
            $indent = Get-Indent $line
            if ($indent -le $parentIndent -and $result.Count -gt 0) { break }
            if ($indent -lt $parentIndent) { break }

            $content = $line.Trim()
            if ($content.StartsWith('- ')) { break }

            if ($content -match '^([A-Za-z0-9_\.\*\-/]+):\s*(.*)$') {
                $key = $Matches[1]
                $rest = $Matches[2]
                $script:__yamlIndex++
                if ($rest -eq '') {
                    if ($script:__yamlIndex -lt $filtered.Count) {
                        $nextLine = $filtered[$script:__yamlIndex]
                        $nextIndent = Get-Indent $nextLine
                        $nextContent = $nextLine.Trim()
                        if ($nextIndent -gt $indent -and $nextContent.StartsWith('- ')) {
                            $result[$key] = Parse-ListBlock $indent
                        } elseif ($nextIndent -gt $indent) {
                            $result[$key] = Parse-MapBlock $indent
                        } else {
                            $result[$key] = $null
                        }
                    } else {
                        $result[$key] = $null
                    }
                } else {
                    $result[$key] = Parse-ScalarValue $rest
                }
            } else {
                $script:__yamlIndex++
            }
        }
        return $result
    }

    return (Parse-MapBlock -1)
}

function Get-TaskOwnerMap {
    <#
    .SYNOPSIS
        加载并解析 docs/governance/task-owner-map.yaml。
    #>
    if (-not (Test-Path $script:TaskOwnerMapPath)) {
        throw "task-owner-map.yaml missing: $script:TaskOwnerMapPath"
    }
    return ConvertFrom-SimpleYaml -Lines (Get-Content -LiteralPath $script:TaskOwnerMapPath -Encoding UTF8)
}

function Get-ReviewPolicy {
    <#
    .SYNOPSIS
        加载并解析 docs/governance/pr-review-policy.yaml。
    #>
    if (-not (Test-Path $script:PrReviewPolicyPath)) {
        throw "pr-review-policy.yaml missing: $script:PrReviewPolicyPath"
    }
    return ConvertFrom-SimpleYaml -Lines (Get-Content -LiteralPath $script:PrReviewPolicyPath -Encoding UTF8)
}

function Convert-GlobToRegex {
    <#
    .SYNOPSIS
        将 glob 路径模式转换为锚定正则。
    #>
    param([Parameter(Mandatory)][string]$Glob)
    $escaped = [Regex]::Escape($Glob)
    $escaped = $escaped -replace '\\\*\\\*', '.*'
    $escaped = $escaped -replace '\\\*', '[^/]*'
    return ('^' + $escaped + '$')
}

function Test-GhAuth {
    <#
    .SYNOPSIS
        校验 gh 登录账号是否为队长账号。不打印 Token。
    #>
    param([string]$ExpectedAccount)
    $authOutput = & gh auth status 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        Write-Host "gh auth status failed (not logged in or gh missing)." -ForegroundColor Red
        return $false
    }
    if ($authOutput -match "account\s+(\S+)") {
        $account = $Matches[1]
        Write-Host "gh account: $account"
        return ($account -eq $ExpectedAccount)
    }
    Write-Host "Unable to parse account from gh auth status." -ForegroundColor Red
    return $false
}

function Test-RepoAccessible {
    <#
    .SYNOPSIS
        校验中央仓库是否可访问。
    #>
    param([string]$Repo)
    & gh repo view $Repo --json name 1>$null 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Select-TargetPr {
    <#
    .SYNOPSIS
        选定目标 PR：-PrNumber 优先；否则选最新更新的 open PR。
    #>
    param(
        [int]$PrNumber,
        [switch]$ReleaseMode
    )

    if ($PrNumber -gt 0) {
        try {
            return Invoke-GhJson -CommandCategory "pr_view_summary" -PrNumber $PrNumber -GhArgs @(
                "pr", "view", "$PrNumber",
                "--repo", $script:RepoSlug,
                "--json", "number,title,author,updatedAt,isDraft,baseRefName,headRefName"
            )
        } catch {
            return $null
        }
    }

    $baseFilter = if ($ReleaseMode) { $script:ReleaseBaseBranch } else { $script:OrdinaryBaseBranch }
    try {
        $prs = Invoke-GhJson -CommandCategory "pr_list" -GhArgs @(
            "pr", "list",
            "--repo", $script:RepoSlug,
            "--state", "open",
            "--base", $baseFilter,
            "--json", "number,title,author,updatedAt,isDraft,baseRefName,headRefName",
            "--limit", "50"
        )
    } catch {
        return $null
    }

    if ($ReleaseMode) {
        $prs = @($prs | Where-Object {
            $_.headRefName -eq $script:ReleaseHeadBranch -and $_.title.StartsWith("[RELEASE]")
        })
    } else {
        $prs = @($prs)
    }

    if ($prs.Count -eq 0) {
        return $null
    }

    $sorted = $prs | Sort-Object -Property @{ Expression = { [datetime]$_.updatedAt } } -Descending
    $top = $sorted[0]
    $ties = @($sorted | Where-Object { $_.updatedAt -eq $top.updatedAt })
    if ($ties.Count -gt 1) {
        Write-Host "Cannot uniquely determine latest PR; candidates share updatedAt:" -ForegroundColor Yellow
        $ties | ForEach-Object {
            Write-Host ("  #{0} [{1}] {2} (updatedAt={3})" -f $_.number, $_.author.login, $_.title, $_.updatedAt)
        }
        return $null
    }
    return $top
}

function Get-PrBodyText {
    <#
    .SYNOPSIS
        单独获取 PR body 纯文本（方案 A + Process UTF-8 捕获）。
        不把正文嵌入外层 JSON，也不打印正文内容，不送入 ConvertFrom-Json。
    #>
    param([int]$PrNumber)
    return Invoke-GhText -CommandCategory "pr_body_text" -PrNumber $PrNumber -GhArgs @(
        "pr", "view", "$PrNumber",
        "--repo", $script:RepoSlug,
        "--json", "body",
        "--jq", ".body"
    )
}

function Get-PrMachineDetail {
    <#
    .SYNOPSIS
        拉取机器门禁所需元数据（不含 body/评论正文），并附带 body 字符数与可选落盘。
    .OUTPUTS
        PSCustomObject：Machine / BodyCharCount / BodyText / Checks
    #>
    param([int]$PrNumber)

    $fieldArg = ($script:PrMachineJsonFields -join ",")
    $machine = Invoke-GhJson -CommandCategory "pr_view_machine" -PrNumber $PrNumber -GhArgs @(
        "pr", "view", "$PrNumber",
        "--repo", $script:RepoSlug,
        "--json", $fieldArg
    )

    $bodyText = ""
    try {
        $bodyText = Get-PrBodyText -PrNumber $PrNumber
    } catch {
        Write-Host ("WARNING: failed to load PR body as text: {0}" -f $_.Exception.Message) -ForegroundColor Yellow
        $bodyText = ""
    }

    $checks = @()
    try {
        $checksRaw = Invoke-GhJson -CommandCategory "pr_checks" -PrNumber $PrNumber -GhArgs @(
            "pr", "checks", "$PrNumber",
            "--repo", $script:RepoSlug,
            "--json", "name,state,bucket,link,workflow"
        )
        if ($null -eq $checksRaw) {
            $checks = @()
        } elseif ($checksRaw -is [System.Array]) {
            $checks = @($checksRaw)
        } else {
            # 单元素时 ConvertFrom-Json 可能返回单个对象而非数组
            $checks = @($checksRaw)
        }
    } catch {
        # gh pr checks 在完全没有 check 时也可能非零；按 Checks=0 处理
        Write-Host ("WARNING: gh pr checks unavailable; treating as zero checks ({0})" -f $_.Exception.Message) -ForegroundColor Yellow
        $checks = @()
    }

    return [pscustomobject]@{
        Machine       = $machine
        BodyText      = $bodyText
        BodyCharCount = $bodyText.Length
        Checks        = $checks
    }
}

function Get-UnresolvedThreadCount {
    <#
    .SYNOPSIS
        GraphQL 查询未解决 Review Thread 数量。失败返回 -1。
    #>
    param([int]$PrNumber)
    $ownerRepo = $script:RepoSlug.Split('/')
    $owner = $ownerRepo[0]
    $repo = $ownerRepo[1]
    $query = @'
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100) {
        nodes { isResolved }
      }
    }
  }
}
'@
    try {
        $data = Invoke-GhJson -CommandCategory "graphql_review_threads" -PrNumber $PrNumber -GhArgs @(
            "api", "graphql",
            "-f", "query=$query",
            "-F", "owner=$owner",
            "-F", "repo=$repo",
            "-F", "number=$PrNumber"
        )
        $nodes = $data.data.repository.pullRequest.reviewThreads.nodes
        if (-not $nodes) { return 0 }
        return @($nodes | Where-Object { -not $_.isResolved }).Count
    } catch {
        return -1
    }
}

function Get-CheckClassification {
    <#
    .SYNOPSIS
        基于 gh pr checks --json 的 bucket 分类。
        仅 bucket=pass 视为通过；fail/pending/skipping/cancel 均非通过。
        Checks 总数为 0 由调用方按 WAIT 处理。
    #>
    param([array]$Checks)

    $total = 0
    $successCount = 0
    $nonPassing = New-Object System.Collections.Generic.List[string]
    $bugbotStatus = "missing"

    if ($Checks) {
        foreach ($chk in $Checks) {
            $total++
            $name = $chk.name
            if (-not $name) { $name = "(unnamed)" }
            $bucket = [string]$chk.bucket
            if (-not $bucket) { $bucket = "unknown" }
            $bucket = $bucket.ToLowerInvariant()
            $state = [string]$chk.state

            if ($bucket -eq "pass") {
                $successCount++
            } else {
                $nonPassing.Add(('{0}: bucket={1} state={2}' -f $name, $bucket, $state))
            }

            if ($name -match "Cursor Bugbot") {
                if ($bucket -eq "pass") {
                    $bugbotStatus = "success"
                } else {
                    $bugbotStatus = $bucket
                }
            }
        }
    }

    return @{
        Total        = $total
        SuccessCount = $successCount
        NonPassing   = $nonPassing.ToArray()
        BugbotStatus = $bugbotStatus
    }
}

function Get-InferredTask {
    <#
    .SYNOPSIS
        从标题 / 分支名 / 标签推断 T01-T09。
    #>
    param([string]$Title, [string]$HeadRef, [array]$Labels)
    $labelNames = @()
    if ($Labels) {
        $labelNames = @($Labels | ForEach-Object { $_.name })
    }
    $haystack = "$Title $HeadRef " + ($labelNames -join ' ')
    if ($haystack -match 'T0([1-9])') {
        return "T0$($Matches[1])"
    }
    return "UNKNOWN"
}

function Test-PathOwnership {
    <#
    .SYNOPSIS
        对照 task-owner-map.yaml 检查改动路径归属。
    #>
    param(
        [array]$ChangedFiles,
        $TaskOwnerMap,
        [string]$TaskCode
    )

    $captainOnlyPatterns = @($TaskOwnerMap.captain_only_paths) | ForEach-Object { Convert-GlobToRegex $_ }
    $sharedPatterns      = @($TaskOwnerMap.shared_change_required_paths) | ForEach-Object { Convert-GlobToRegex $_ }

    $allowedPatterns = @()
    if ($TaskCode -ne "UNKNOWN" -and $TaskOwnerMap.tasks.Contains($TaskCode)) {
        $allowedPatterns = @($TaskOwnerMap.tasks[$TaskCode].allowed_paths) | ForEach-Object { Convert-GlobToRegex $_ }
    }

    $owned = New-Object System.Collections.Generic.List[string]
    $captainHits = New-Object System.Collections.Generic.List[string]
    $sharedHits = New-Object System.Collections.Generic.List[string]
    $outOfScope = New-Object System.Collections.Generic.List[string]

    foreach ($f in @($ChangedFiles)) {
        $path = $f.path
        if (-not $path) { continue }

        $isCaptainOnly = $false
        foreach ($p in $captainOnlyPatterns) { if ($path -match $p) { $isCaptainOnly = $true; break } }
        if ($isCaptainOnly) { $captainHits.Add($path); continue }

        $isAllowed = $false
        foreach ($p in $allowedPatterns) { if ($path -match $p) { $isAllowed = $true; break } }
        if ($isAllowed) { $owned.Add($path); continue }

        $isShared = $false
        foreach ($p in $sharedPatterns) { if ($path -match $p) { $isShared = $true; break } }
        if ($isShared) { $sharedHits.Add($path); continue }

        $outOfScope.Add($path)
    }

    return @{
        OwnedFiles       = $owned.ToArray()
        CaptainOnlyHits  = $captainHits.ToArray()
        SharedChangeHits = $sharedHits.ToArray()
        OutOfScopeFiles  = $outOfScope.ToArray()
    }
}

function Save-ReviewArtifacts {
    <#
    .SYNOPSIS
        把机器元数据与 body 文本分别写入仓库外部临时目录。
        控制台只报告路径与 body 字符数，不打印 body。
    #>
    param(
        [string]$OutDir,
        [int]$PrNumber,
        [object]$Machine,
        [string]$BodyText,
        [hashtable]$Checks,
        [hashtable]$Ownership
    )

    if (-not $OutDir) {
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $OutDir = Join-Path $env:TEMP "sage125-captain-pr-review\pr-$PrNumber-$stamp"
    }
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    $machineJson = $Machine | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText((Join-Path $OutDir "pr_machine.json"), $machineJson, $utf8NoBom)
    [System.IO.File]::WriteAllText((Join-Path $OutDir "checks.json"), ($Checks | ConvertTo-Json -Depth 5), $utf8NoBom)
    [System.IO.File]::WriteAllText((Join-Path $OutDir "path_ownership.json"), ($Ownership | ConvertTo-Json -Depth 5), $utf8NoBom)
    [System.IO.File]::WriteAllText((Join-Path $OutDir "pr_body.txt"), [string]$BodyText, $utf8NoBom)
    [System.IO.File]::WriteAllText(
        (Join-Path $OutDir "pr_body_meta.json"),
        (@{ char_count = ([string]$BodyText).Length } | ConvertTo-Json),
        $utf8NoBom
    )

    Write-Host ("Review artifacts saved outside repo: {0} (body_chars={1})" -f $OutDir, ([string]$BodyText).Length) -ForegroundColor DarkGray
    return $OutDir
}

function Invoke-CaptainReviewMain {
    <#
    .SYNOPSIS
        主流程。抽成函数以便测试 dot-source 本脚本时不自动执行。
    #>

    Write-Section "Step 1/6: Environment and identity"

    if (-not (Test-GhAuth -ExpectedAccount $script:CaptainAccount)) {
        Exit-WithCode $script:ExitCodes.ENV_ERROR "gh account is not $script:CaptainAccount, or gh is not logged in."
    }
    if (-not (Test-RepoAccessible -Repo $script:RepoSlug)) {
        Exit-WithCode $script:ExitCodes.ENV_ERROR "Cannot access central repo $script:RepoSlug."
    }
    Write-Host ("Identity OK: account={0} repo={1}" -f $script:CaptainAccount, $script:RepoSlug) -ForegroundColor Green

    if ($AllowMerge -and -not $ReviewedHeadSha) {
        Exit-WithCode $script:ExitCodes.ENV_ERROR "-AllowMerge requires -ReviewedHeadSha."
    }

    Write-Section "Step 2/6: Select target PR"

    $targetSummary = Select-TargetPr -PrNumber $PrNumber -ReleaseMode:$ReleaseMode
    if (-not $targetSummary) {
        $mode = if ($ReleaseMode) {
            "ReleaseMode (base=main, head=$script:ReleaseHeadBranch, title starts with [RELEASE])"
        } else {
            "ordinary (base=$script:OrdinaryBaseBranch)"
        }
        Exit-WithCode $script:ExitCodes.NO_PR "No matching open PR ($mode), or latest PR is not unique."
    }

    $targetNumber = [int]$targetSummary.number
    Write-Host ("Selected PR #{0}: {1}" -f $targetNumber, $targetSummary.title) -ForegroundColor Green

    Write-Section "Step 3/6: Load machine metadata (body separated)"

    $bundle = Get-PrMachineDetail -PrNumber $targetNumber
    $prDetail = $bundle.Machine
    $reviewedHeadShaAtStart = $prDetail.headRefOid
    $isFork = ($prDetail.headRepositoryOwner.login -ne $script:RepoSlug.Split('/')[0])

    Write-Host ("PR number       : #{0}" -f $prDetail.number)
    Write-Host ("Title           : {0}" -f $prDetail.title)
    Write-Host ("Author          : {0}" -f $prDetail.author.login)
    Write-Host ("Draft?          : {0}" -f $prDetail.isDraft)
    Write-Host ("Base            : {0}" -f $prDetail.baseRefName)
    Write-Host ("Head            : {0} (fork={1})" -f $prDetail.headRefName, $isFork)
    Write-Host ("Head SHA        : {0}" -f $reviewedHeadShaAtStart)
    Write-Host ("Updated at      : {0}" -f $prDetail.updatedAt)
    Write-Host ("Changed files   : {0}" -f $prDetail.changedFiles)
    Write-Host ("+{0} / -{1}" -f $prDetail.additions, $prDetail.deletions)
    Write-Host ("URL             : {0}" -f $prDetail.url)
    Write-Host ("Body char count : {0} (content not printed)" -f $bundle.BodyCharCount)

    Write-Section "Step 4/6: Path ownership + Checks + Bugbot + threads"

    $taskOwnerMap = Get-TaskOwnerMap
    $null = Get-ReviewPolicy

    $inferredTask = Get-InferredTask -Title $prDetail.title -HeadRef $prDetail.headRefName -Labels $prDetail.labels
    Write-Host "Inferred task: $inferredTask"

    $ownership = Test-PathOwnership -ChangedFiles $prDetail.files -TaskOwnerMap $taskOwnerMap -TaskCode $inferredTask
    Write-Host ("Owned paths              : {0}" -f $ownership.OwnedFiles.Count)
    Write-Host ("Captain-only path hits   : {0}" -f $ownership.CaptainOnlyHits.Count)
    Write-Host ("Shared-change path hits  : {0}" -f $ownership.SharedChangeHits.Count)
    Write-Host ("Out-of-scope paths       : {0}" -f $ownership.OutOfScopeFiles.Count)
    if ($ownership.CaptainOnlyHits.Count -gt 0) {
        Write-Host "  Captain-only paths:" -ForegroundColor Yellow
        $ownership.CaptainOnlyHits | ForEach-Object { Write-Host "    - $_" }
    }
    if ($ownership.OutOfScopeFiles.Count -gt 0) {
        Write-Host "  Out-of-scope paths:" -ForegroundColor Yellow
        $ownership.OutOfScopeFiles | ForEach-Object { Write-Host "    - $_" }
    }

    $checks = Get-CheckClassification -Checks $bundle.Checks
    Write-Host ("GitHub Checks total      : {0}" -f $checks.Total)
    Write-Host ("Pass (bucket=pass)       : {0}" -f $checks.SuccessCount)
    Write-Host ("Non-pass (blocking)      : {0}" -f $checks.NonPassing.Count)
    if ($checks.NonPassing.Count -gt 0) {
        $checks.NonPassing | ForEach-Object { Write-Host "    - $_" -ForegroundColor Yellow }
    }
    Write-Host ("Cursor Bugbot status     : {0}" -f $checks.BugbotStatus)

    $unresolvedThreads = Get-UnresolvedThreadCount -PrNumber $targetNumber
    if ($unresolvedThreads -lt 0) {
        Write-Host "Unresolved review threads: unknown (GraphQL failed; treat as unresolved)" -ForegroundColor Yellow
    } else {
        Write-Host ("Unresolved review threads: {0}" -f $unresolvedThreads)
    }

    $outDirUsed = Save-ReviewArtifacts -OutDir $OutDir -PrNumber $targetNumber `
        -Machine $prDetail -BodyText $bundle.BodyText -Checks $checks -Ownership $ownership

    Write-Section "Step 5/6: Mechanical merge-gate evaluation"

    $isBehindOrConflict = ($prDetail.mergeStateStatus -in @("BEHIND", "DIRTY"))
    $isMergeableRaw = ($prDetail.mergeable -eq "MERGEABLE")
    $hasNonPassingChecks = ($checks.NonPassing.Count -gt 0)
    $hasZeroChecks = ($checks.Total -eq 0)
    $bugbotBlocking = ($checks.BugbotStatus -notin @("missing", "success"))
    $unresolvedBlocking = ($unresolvedThreads -ne 0)
    $baseOk = if ($ReleaseMode) {
        ($prDetail.baseRefName -eq $script:ReleaseBaseBranch) -and
        ($prDetail.headRefName -eq $script:ReleaseHeadBranch) -and
        ($prDetail.title.StartsWith("[RELEASE]"))
    } else {
        ($prDetail.baseRefName -eq $script:OrdinaryBaseBranch)
    }

    Write-Host ("Base branch policy OK         : {0}" -f $baseOk)
    Write-Host ("Not Draft                     : {0}" -f (-not $prDetail.isDraft))
    Write-Host ("mergeable=MERGEABLE           : {0}" -f $isMergeableRaw)
    Write-Host ("Not behind / no conflicts     : {0}" -f (-not $isBehindOrConflict))
    Write-Host ("No non-pass Checks            : {0}" -f (-not $hasNonPassingChecks))
    Write-Host ("Checks count non-zero         : {0}" -f (-not $hasZeroChecks))
    Write-Host ("Bugbot not blocking           : {0}" -f (-not $bugbotBlocking))
    Write-Host ("All review threads resolved   : {0}" -f (-not $unresolvedBlocking))
    Write-Host ("Out-of-scope paths == 0       : {0}" -f ($ownership.OutOfScopeFiles.Count -eq 0))
    Write-Host ("Captain-only hits == 0        : {0}" -f ($ownership.CaptainOnlyHits.Count -eq 0))

    $mechanicalGatesPass = $baseOk -and (-not $prDetail.isDraft) -and $isMergeableRaw -and (-not $isBehindOrConflict) -and
        (-not $hasNonPassingChecks) -and (-not $hasZeroChecks) -and (-not $bugbotBlocking) -and
        (-not $unresolvedBlocking) -and ($ownership.OutOfScopeFiles.Count -eq 0) -and ($ownership.CaptainOnlyHits.Count -eq 0)

    Write-Section "Step 6/6: Result and optional merge action"

    if (-not $baseOk) {
        Exit-WithCode $script:ExitCodes.SECURITY_ABORT "Base branch policy failed. Ordinary PRs require base=$script:OrdinaryBaseBranch; ReleaseMode requires base=$script:ReleaseBaseBranch, head=$script:ReleaseHeadBranch, title starting with [RELEASE]."
    }

    if (-not $AllowMerge) {
        if ($prDetail.isDraft -or $hasZeroChecks -or $hasNonPassingChecks -or $bugbotBlocking -or $isBehindOrConflict -or $unresolvedBlocking) {
            Exit-WithCode $script:ExitCodes.WAITING ("InspectOnly done: waiting on Draft/Checks/Bugbot/branch sync/threads. See output and {0}." -f $outDirUsed)
        }
        Exit-WithCode $script:ExitCodes.OK "InspectOnly done: mechanical gates ready; semantic review (P0/P1) still required before -AllowMerge."
    }

    Write-Host "Re-fetching head SHA to prevent post-review content swap ..." -ForegroundColor DarkGray
    $freshBundle = Get-PrMachineDetail -PrNumber $targetNumber
    $currentHeadSha = $freshBundle.Machine.headRefOid

    if ($currentHeadSha -ne $ReviewedHeadSha) {
        Exit-WithCode $script:ExitCodes.SECURITY_ABORT ("Head SHA changed (reviewed={0}, current={1}). Merge aborted." -f $ReviewedHeadSha, $currentHeadSha)
    }

    if (-not $mechanicalGatesPass) {
        Exit-WithCode $script:ExitCodes.NEEDS_CHANGES "Mechanical merge gates not fully satisfied; refuse merge."
    }

    $approveCmd = "gh pr review $targetNumber --repo $script:RepoSlug --approve --body " + '"' + $ApproveBody + '"'
    $mergeCmd   = "gh pr merge $targetNumber --repo $script:RepoSlug --squash --match-head-commit $currentHeadSha"

    if ($DryRun) {
        Write-Host "[DRYRUN] Will NOT submit Review or Merge. Commands that would run:" -ForegroundColor Magenta
        Write-Host "  $approveCmd"
        Write-Host "  $mergeCmd"
        Exit-WithCode $script:ExitCodes.OK "DryRun complete: gates satisfied, but no Review/Merge executed."
    }

    Write-Host "Submitting Approve ..." -ForegroundColor Green
    & gh pr review $targetNumber --repo $script:RepoSlug --approve --body $ApproveBody
    if ($LASTEXITCODE -ne 0) {
        Exit-WithCode $script:ExitCodes.ENV_ERROR "gh pr review --approve failed."
    }

    Write-Host "Squash merging with --match-head-commit ..." -ForegroundColor Green
    & gh pr merge $targetNumber --repo $script:RepoSlug --squash --match-head-commit $currentHeadSha
    if ($LASTEXITCODE -ne 0) {
        Exit-WithCode $script:ExitCodes.ENV_ERROR "gh pr merge failed."
    }

    Exit-WithCode $script:ExitCodes.MERGED ("PR #{0} squash-merged into {1} (reviewed head SHA={2})." -f $targetNumber, $prDetail.baseRefName, $currentHeadSha)
}

# 仅在直接执行时跑主流程；被测试 dot-source 时只加载函数。
$script:IsDotSourced = ($MyInvocation.InvocationName -eq '.')
if (-not $script:IsDotSourced) {
    Invoke-CaptainReviewMain
}
