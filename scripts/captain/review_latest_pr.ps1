#Requires -Version 5.1
<#
.SYNOPSIS
    SAGE125 队长 PR 审核与受控合并辅助脚本。

.DESCRIPTION
    本脚本是「队长一句话触发 PR 审核」工作流的技术执行层：负责选定目标 PR、
    抓取只读元数据（不写入仓库目录）、按 task-owner-map.yaml 做路径所有权检查、
    解析 GitHub Checks / Bugbot 状态、以及（仅当显式传入 -AllowMerge 时）执行
    Approve + Squash Merge。

    语义层面的科学真实性 / P0-P1 判定由 Cursor Agent（LLM）完成，本脚本只做
    确定性、可复核的机械检查（分支、Draft、Checks 结论、SHA 一致性、路径归属）。

.PARAMETER PrNumber
    指定要审核的 PR 编号；优先于 -Latest。

.PARAMETER Latest
    未指定 -PrNumber 时的默认行为：选择目标仓库中 base=integration/2026-08-10
    （或 -ReleaseMode 下 base=main）、state=open、按 updatedAt 降序排序的第一个 PR。

.PARAMETER DryRun
    仅打印将要执行的操作（包括 Review / Merge 命令），不产生任何真实的
    gh pr review / gh pr merge 调用。

.PARAMETER InspectOnly
    仅做检查与报告，不提交 Review、不合并。这是脚本的默认行为；显式传入该开关
    只是让意图更清晰，效果与「不传 -AllowMerge」相同。

.PARAMETER AllowMerge
    显式请求在全部合并门禁满足时执行 Approve + Squash Merge。
    必须同时提供 -ReviewedHeadSha，用于校验合并前 head SHA 未被替换。

.PARAMETER ReleaseMode
    发布模式：目标从「base=integration/2026-08-10 的任务 PR」切换为
    「base=main 且 head=integration/2026-08-10 且标题以 [RELEASE] 开头」的发布 PR。

.PARAMETER ReviewedHeadSha
    Agent 在审核开始时记录的 head SHA。仅在 -AllowMerge 时必需；合并前脚本会
    重新拉取当前 head SHA 并与此值比对，不一致立即中止（退出码 40）。

.PARAMETER ApproveBody
    -AllowMerge 且门禁通过时使用的 Approve 评论正文；提供默认文案。

.PARAMETER RequestChangesBodyFile
    包含 Request Changes 评论正文的文件路径（Markdown）。提供时脚本会执行
    gh pr review --request-changes --body-file <file>（DryRun 下只打印）。

.PARAMETER OutDir
    保存本次审核只读元数据/报告的临时目录（脚本外部，不进入仓库）。
    默认：$env:TEMP\sage125-captain-pr-review\pr-<number>-<timestamp>\

.OUTPUTS
    退出码：
        0  前置检查通过（InspectOnly 完成，无致命错误）
        10 未找到匹配的 PR
        20 存在阻断性问题，需要队员修改（不合并）
        30 等待中（Draft / CI pending / Bugbot 未完成 / 分支落后 / 未解决讨论）
        40 安全阻断（分支策略违规、SHA 不一致、试图绕过门禁等）
        50 合并已完成
        60 命令或环境错误（gh 未登录、仓库不可访问、参数错误等）

.NOTES
    绝不使用 --admin；绝不 force push；绝不打印任何密钥/Token 值。
    仓库：sage125-ai-scientist-team/SAGE125-AI-Scientist
    队长账号：liuyanbo12
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
    [string]$ApproveBody = "Cursor 队长审核通过：无阻断性 P0/P1；路径所有权、科学真实性、安全、本地测试和 GitHub Checks 均符合要求，允许 Squash Merge 到 integration/2026-08-10。 ",
    [string]$RequestChangesBodyFile = "",
    [string]$OutDir = ""
)

# 注意：不能设为 "Stop"。本脚本大量调用外部 gh.exe，PowerShell 5.1 会把
# 外部进程 stderr 的每一行转成错误记录；一旦 $ErrorActionPreference="Stop"，
# 一次预期内的失败（如 PR 编号不存在）就会被升级成终止性异常，绕过下面
# 显式的 $LASTEXITCODE 判断逻辑。真正需要中止的地方本脚本都用 throw 显式处理。
$ErrorActionPreference = "Continue"

# ============================================================
# 常量：仓库与分支策略（与 docs/governance/*.yaml 保持一致）
# ============================================================
$RepoSlug              = "sage125-ai-scientist-team/SAGE125-AI-Scientist"
$CaptainAccount        = "liuyanbo12"
$OrdinaryBaseBranch    = "integration/2026-08-10"
$ReleaseBaseBranch     = "main"
$ReleaseHeadBranch     = "integration/2026-08-10"
$RepoRoot              = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$TaskOwnerMapPath      = Join-Path $RepoRoot "docs\governance\task-owner-map.yaml"
$PrReviewPolicyPath    = Join-Path $RepoRoot "docs\governance\pr-review-policy.yaml"

# 退出码字典（与 pr-review-policy.yaml 的 exit_codes 保持一致，供人读）。
$ExitCodes = @{
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
        打印一个带分隔线的小节标题，便于在终端输出中定位审核阶段。
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
        统一的退出出口：打印退出码含义后调用 exit，确保调用方（Agent/人）
        能立刻看懂本次运行的结论，而不是只看到一个数字。
    #>
    param([int]$Code, [string]$Reason)
    Write-Host ""
    Write-Host ("[EXIT $Code] $Reason") -ForegroundColor Yellow
    exit $Code
}

# ============================================================
# 极简 YAML 读取器（仅覆盖本项目 governance YAML 用到的子集：
# 标量、字符串、布尔、整数、块映射、块列表）。不追求通用 YAML 兼容性。
# ============================================================
function ConvertFrom-SimpleYaml {
    <#
    .SYNOPSIS
        将 docs/governance/*.yaml 这类「缩进一致、无复杂锚点/多行字符串」的
        简单 YAML 解析为嵌套的 [ordered] hashtable / 数组结构。

    .PARAMETER Lines
        YAML 文件的逐行文本（Get-Content 的输出）。

    .OUTPUTS
        [ordered] hashtable，键为顶层字段名。
    #>
    # 注意：不能用 [Parameter(Mandatory)][string[]]$Lines —— PowerShell 对
    # Mandatory 的 string[] 参数会自动校验"数组内无空字符串元素"，而 YAML 文件里
    # 的空行在 Get-Content 结果中就是空字符串，会被误判为"参数为空"而报错。
    param([string[]]$Lines)

    # 第一步：去掉整行注释与行内注释（本项目 YAML 内容本身不含 '#' 字符）。
    $filtered = New-Object System.Collections.Generic.List[string]
    foreach ($raw in $Lines) {
        if ($raw.TrimStart().StartsWith('#')) { continue }
        $noInlineComment = $raw -replace '(?<=\s)#.*$', ''
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
                # 无法识别的行：跳过，避免死循环。
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
    .OUTPUTS
        解析后的 hashtable；文件缺失时抛出终止性错误（治理配置本身是刚性依赖）。
    #>
    if (-not (Test-Path $TaskOwnerMapPath)) {
        throw "task-owner-map.yaml 缺失：$TaskOwnerMapPath"
    }
    return ConvertFrom-SimpleYaml -Lines (Get-Content -LiteralPath $TaskOwnerMapPath -Encoding UTF8)
}

function Get-ReviewPolicy {
    <#
    .SYNOPSIS
        加载并解析 docs/governance/pr-review-policy.yaml。
    .OUTPUTS
        解析后的 hashtable；文件缺失时抛出终止性错误。
    #>
    if (-not (Test-Path $PrReviewPolicyPath)) {
        throw "pr-review-policy.yaml 缺失：$PrReviewPolicyPath"
    }
    return ConvertFrom-SimpleYaml -Lines (Get-Content -LiteralPath $PrReviewPolicyPath -Encoding UTF8)
}

function Convert-GlobToRegex {
    <#
    .SYNOPSIS
        将 task-owner-map.yaml 中的 glob 路径模式（如 "app/rag/**"）转换为
        锚定的 .NET 正则表达式，用于匹配 GitHub 返回的正斜杠路径。
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
        校验当前 gh CLI 登录账号是否为队长账号（liuyanbo12）。
        不打印 Token；只解析账号名。
    .OUTPUTS
        [bool] 是否匹配。
    #>
    param([string]$ExpectedAccount)
    $authOutput = & gh auth status 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        Write-Host "gh auth status 执行失败（未登录或 gh 未安装）。 " -ForegroundColor Red
        return $false
    }
    if ($authOutput -match "account\s+(\S+)") {
        $account = $Matches[1]
        Write-Host "gh 当前登录账号：$account"
        return ($account -eq $ExpectedAccount)
    }
    Write-Host "无法从 gh auth status 输出中解析账号名。 " -ForegroundColor Red
    return $false
}

function Test-RepoAccessible {
    <#
    .SYNOPSIS
        校验中央仓库是否可访问。
    .OUTPUTS
        [bool]
    #>
    param([string]$Repo)
    & gh repo view $Repo --json name 1>$null 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Select-TargetPr {
    <#
    .SYNOPSIS
        选定本次审核的目标 PR：-PrNumber 优先；否则按策略选择「最新更新的
        open PR」。ReleaseMode 下改为搜索 base=main 的候选并进一步校验
        head/标题条件。

    .OUTPUTS
        单个 PR 摘要对象；如果无法唯一确定，返回 $null 并把候选打印到控制台。
    #>
    param(
        [int]$PrNumber,
        [switch]$ReleaseMode
    )

    if ($PrNumber -gt 0) {
        $json = & gh pr view $PrNumber --repo $RepoSlug --json number,title,author,updatedAt,isDraft,baseRefName,headRefName 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $json) {
            return $null
        }
        return ($json | ConvertFrom-Json)
    }

    $baseFilter = if ($ReleaseMode) { $ReleaseBaseBranch } else { $OrdinaryBaseBranch }
    $listJson = & gh pr list --repo $RepoSlug --state open --base $baseFilter `
        --json number,title,author,updatedAt,isDraft,baseRefName,headRefName --limit 50 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $listJson) {
        return $null
    }
    $prs = $listJson | ConvertFrom-Json
    if ($ReleaseMode) {
        $prs = $prs | Where-Object {
            $_.headRefName -eq $ReleaseHeadBranch -and $_.title -like '[RELEASE]*'
        }
    }
    if (-not $prs -or $prs.Count -eq 0) {
        return $null
    }

    $sorted = $prs | Sort-Object -Property @{ Expression = { [datetime]$_.updatedAt } } -Descending
    $top = $sorted[0]
    $ties = $sorted | Where-Object { $_.updatedAt -eq $top.updatedAt }
    if ($ties.Count -gt 1) {
        Write-Host "无法唯一确定「最新 PR」，以下候选的 updatedAt 相同： " -ForegroundColor Yellow
        $ties | ForEach-Object {
            Write-Host ("  #{0} [{1}] {2} (updatedAt={3})" -f $_.number, $_.author.login, $_.title, $_.updatedAt)
        }
        return $null
    }
    return $top
}

function Get-PrFullDetail {
    <#
    .SYNOPSIS
        拉取目标 PR 的完整只读元数据（不写入仓库目录）。
    .OUTPUTS
        PR 详情对象（含 files/reviews/statusCheckRollup/comments 等字段）。
    #>
    param([int]$PrNumber)
    $fields = "number,title,author,url,isDraft,baseRefName,headRefName,headRepositoryOwner," +
              "headRefOid,mergeable,mergeStateStatus,changedFiles,additions,deletions," +
              "files,reviews,statusCheckRollup,updatedAt,body,comments,labels"
    $json = & gh pr view $PrNumber --repo $RepoSlug --json $fields 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $json) {
        throw "gh pr view 获取 PR #$PrNumber 详情失败。 "
    }
    return ($json | ConvertFrom-Json)
}

function Get-UnresolvedThreadCount {
    <#
    .SYNOPSIS
        通过 gh api graphql 查询该 PR 的未解决 Review Thread 数量。
        查询失败（如权限不足）时返回 -1，代表「未知」，调用方应视为
        「不能确认已解决」而不是「已解决」。
    #>
    param([int]$PrNumber)
    $ownerRepo = $RepoSlug.Split('/')
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
    $result = & gh api graphql -f query=$query -F owner=$owner -F repo=$repo -F number=$PrNumber 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $result) {
        return -1
    }
    try {
        $data = $result | ConvertFrom-Json
        $nodes = $data.data.repository.pullRequest.reviewThreads.nodes
        if (-not $nodes) { return 0 }
        return ($nodes | Where-Object { -not $_.isResolved } | Measure-Object).Count
    } catch {
        return -1
    }
}

function Get-CheckClassification {
    <#
    .SYNOPSIS
        将 statusCheckRollup 数组分类为 success / non_passing / total，并单独
        标出 Cursor Bugbot 检查的状态。non_passing 集合覆盖
        failure/cancelled/pending/skipped/neutral/queued/in_progress 等一切非
        success 结论 —— 这些绝不能被当作「通过」。

    .OUTPUTS
        hashtable：Total / SuccessCount / NonPassing(list) / BugbotStatus
    #>
    param([array]$StatusCheckRollup)

    $total = 0
    $successCount = 0
    $nonPassing = New-Object System.Collections.Generic.List[string]
    $bugbotStatus = "missing"

    if ($StatusCheckRollup) {
        foreach ($chk in $StatusCheckRollup) {
            $total++
            $name = $chk.name
            if (-not $name) { $name = $chk.context }
            $conclusion = $chk.conclusion
            if (-not $conclusion) { $conclusion = $chk.state }
            $isSuccess = ($conclusion -in @("SUCCESS", "success"))
            if ($isSuccess) {
                $successCount++
            } else {
                $nonPassing.Add(('{0}: {1}' -f $name, $conclusion))
            }
            if ($name -match "Cursor Bugbot") {
                $bugbotStatus = if ($conclusion) { $conclusion.ToString().ToLower() } else { "unknown" }
            }
        }
    }

    return @{
        Total         = $total
        SuccessCount  = $successCount
        NonPassing    = $nonPassing.ToArray()
        BugbotStatus  = $bugbotStatus
    }
}

function Get-InferredTask {
    <#
    .SYNOPSIS
        从 PR 标题 / 分支名 / 标签中推断 T01-T09 任务编号。
    .OUTPUTS
        "T01".."T09" 或 "UNKNOWN"。
    #>
    param([string]$Title, [string]$HeadRef, [array]$Labels)
    $haystack = "$Title $HeadRef " + (($Labels | ForEach-Object { $_.name }) -join ' ')
    if ($haystack -match 'T0([1-9])') {
        return "T0$($Matches[1])"
    }
    return "UNKNOWN"
}

function Test-PathOwnership {
    <#
    .SYNOPSIS
        对照 task-owner-map.yaml，检查改动文件是否全部落在推断任务的
        allowed_paths 内；命中 captain_only_paths 或落在
        shared_change_required_paths 之外的越界路径都记为违规。

    .OUTPUTS
        hashtable：OwnedFiles / CaptainOnlyHits / SharedChangeHits / OutOfScopeFiles
    #>
    param(
        [array]$ChangedFiles,
        [hashtable]$TaskOwnerMap,
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

    foreach ($f in $ChangedFiles) {
        $path = $f.path
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
        把本次审核的只读元数据写入仓库外部的临时目录，绝不落入仓库工作区。
    .OUTPUTS
        实际使用的输出目录路径。
    #>
    param([string]$OutDir, [int]$PrNumber, [object]$PrDetail, [hashtable]$Checks, [hashtable]$Ownership)

    if (-not $OutDir) {
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $OutDir = Join-Path $env:TEMP "sage125-captain-pr-review\pr-$PrNumber-$stamp"
    }
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

    $PrDetail | ConvertTo-Json -Depth 10 | Out-File -Encoding utf8 (Join-Path $OutDir "pr_detail.json")
    $Checks | ConvertTo-Json -Depth 5 | Out-File -Encoding utf8 (Join-Path $OutDir "checks.json")
    $Ownership | ConvertTo-Json -Depth 5 | Out-File -Encoding utf8 (Join-Path $OutDir "path_ownership.json")

    Write-Host "审核元数据已保存到仓库外部临时目录：$OutDir" -ForegroundColor DarkGray
    return $OutDir
}

# ============================================================
# 主流程
# ============================================================

Write-Section "步骤 1/6：环境与身份校验"

if (-not (Test-GhAuth -ExpectedAccount $CaptainAccount)) {
    Exit-WithCode $ExitCodes.ENV_ERROR "gh 当前登录账号不是 $CaptainAccount，或 gh 未登录。 "
}
if (-not (Test-RepoAccessible -Repo $RepoSlug)) {
    Exit-WithCode $ExitCodes.ENV_ERROR "无法访问中央仓库 $RepoSlug（权限或网络问题）。 "
}
Write-Host "身份与仓库校验通过：账号=$CaptainAccount，仓库=$RepoSlug" -ForegroundColor Green

if ($AllowMerge -and -not $ReviewedHeadSha) {
    Exit-WithCode $ExitCodes.ENV_ERROR "-AllowMerge 必须同时提供 -ReviewedHeadSha。 "
}

Write-Section "步骤 2/6：选定目标 PR"

$targetSummary = Select-TargetPr -PrNumber $PrNumber -ReleaseMode:$ReleaseMode
if (-not $targetSummary) {
    $mode = if ($ReleaseMode) { "ReleaseMode（base=main, head=$ReleaseHeadBranch, 标题以 [RELEASE] 开头） " } else { "普通模式（base=$OrdinaryBaseBranch） " }
    Exit-WithCode $ExitCodes.NO_PR "未找到符合条件的 Open PR（$mode），或候选不唯一（见上方输出）。 "
}

$targetNumber = $targetSummary.number
Write-Host "已选定 PR #$targetNumber：$($targetSummary.title)" -ForegroundColor Green

Write-Section "步骤 3/6：拉取 PR 完整只读元数据"

$prDetail = Get-PrFullDetail -PrNumber $targetNumber
$reviewedHeadShaAtStart = $prDetail.headRefOid
$isFork = ($prDetail.headRepositoryOwner.login -ne $RepoSlug.Split('/')[0])

Write-Host ("PR 编号        : #{0}" -f $prDetail.number)
Write-Host ("标题           : {0}" -f $prDetail.title)
Write-Host ("作者           : {0}" -f $prDetail.author.login)
Write-Host ("Draft?         : {0}" -f $prDetail.isDraft)
Write-Host ("Base           : {0}" -f $prDetail.baseRefName)
Write-Host ("Head           : {0} (fork={1})" -f $prDetail.headRefName, $isFork)
Write-Host ("Head SHA       : {0}" -f $reviewedHeadShaAtStart)
Write-Host ("更新时间       : {0}" -f $prDetail.updatedAt)
Write-Host ("Changed files  : {0}" -f $prDetail.changedFiles)
Write-Host ("+{0} / -{1}" -f $prDetail.additions, $prDetail.deletions)
Write-Host ("URL            : {0}" -f $prDetail.url)

Write-Section "步骤 4/6：路径所有权 + Checks + Bugbot + 未解决讨论"

$taskOwnerMap = Get-TaskOwnerMap
$reviewPolicy = Get-ReviewPolicy

$inferredTask = Get-InferredTask -Title $prDetail.title -HeadRef $prDetail.headRefName -Labels $prDetail.labels
Write-Host "推断任务编号：$inferredTask"

$ownership = Test-PathOwnership -ChangedFiles $prDetail.files -TaskOwnerMap $taskOwnerMap -TaskCode $inferredTask
Write-Host ("Owner 路径内改动     : {0}" -f $ownership.OwnedFiles.Count)
Write-Host ("命中队长专属路径     : {0}" -f $ownership.CaptainOnlyHits.Count)
Write-Host ("命中共享变更路径     : {0}" -f $ownership.SharedChangeHits.Count)
Write-Host ("越界（无归属）路径   : {0}" -f $ownership.OutOfScopeFiles.Count)
if ($ownership.CaptainOnlyHits.Count -gt 0) {
    Write-Host "  队长专属路径： " -ForegroundColor Yellow
    $ownership.CaptainOnlyHits | ForEach-Object { Write-Host "    - $_" }
}
if ($ownership.OutOfScopeFiles.Count -gt 0) {
    Write-Host "  越界路径（无 owner，也不在 shared_change 列表）： " -ForegroundColor Yellow
    $ownership.OutOfScopeFiles | ForEach-Object { Write-Host "    - $_" }
}

$checks = Get-CheckClassification -StatusCheckRollup $prDetail.statusCheckRollup
Write-Host ("GitHub Checks 总数   : {0}" -f $checks.Total)
Write-Host ("成功（success）       : {0}" -f $checks.SuccessCount)
Write-Host ("非通过（阻断）        : {0}" -f $checks.NonPassing.Count)
if ($checks.NonPassing.Count -gt 0) {
    $checks.NonPassing | ForEach-Object { Write-Host "    - $_" -ForegroundColor Yellow }
}
Write-Host ("Cursor Bugbot 状态    : {0}" -f $checks.BugbotStatus)

$unresolvedThreads = Get-UnresolvedThreadCount -PrNumber $targetNumber
if ($unresolvedThreads -lt 0) {
    Write-Host "未解决 Review Thread 数：未知（GraphQL 查询失败，按「不能确认已解决」处理） " -ForegroundColor Yellow
} else {
    Write-Host ("未解决 Review Thread 数 : {0}" -f $unresolvedThreads)
}

$outDirUsed = Save-ReviewArtifacts -OutDir $OutDir -PrNumber $targetNumber -PrDetail $prDetail -Checks $checks -Ownership $ownership

Write-Section "步骤 5/6：机械合并门禁判定"

$isUpToDate = ($prDetail.mergeStateStatus -notin @("BEHIND", "DIRTY", "BLOCKED", "DRAFT", "UNSTABLE"))
$isMergeableRaw = ($prDetail.mergeable -eq "MERGEABLE")
$hasNonPassingChecks = ($checks.NonPassing.Count -gt 0)
$hasZeroChecks = ($checks.Total -eq 0)
$bugbotBlocking = ($checks.BugbotStatus -notin @("missing", "success"))
$unresolvedBlocking = ($unresolvedThreads -ne 0)  # -1（未知）或 >0 都视为未满足
$baseOk = if ($ReleaseMode) {
    ($prDetail.baseRefName -eq $ReleaseBaseBranch) -and
    ($prDetail.headRefName -eq $ReleaseHeadBranch) -and
    ($prDetail.title -like '[RELEASE]*')
} else {
    ($prDetail.baseRefName -eq $OrdinaryBaseBranch)
}

Write-Host ("Base 分支策略通过        : {0}" -f $baseOk)
Write-Host ("非 Draft                 : {0}" -f (-not $prDetail.isDraft))
Write-Host ("GitHub mergeable=MERGEABLE : {0}" -f $isMergeableRaw)
Write-Host ("分支未落后/未冲突         : {0}" -f $isUpToDate)
Write-Host ("无非通过 Checks           : {0}" -f (-not $hasNonPassingChecks))
Write-Host ("Checks 数量非零           : {0}" -f (-not $hasZeroChecks))
Write-Host ("Bugbot 非阻断             : {0}" -f (-not $bugbotBlocking))
Write-Host ("讨论线程已全部解决        : {0}" -f (-not $unresolvedBlocking))
Write-Host ("越界路径为零              : {0}" -f ($ownership.OutOfScopeFiles.Count -eq 0))
Write-Host ("未命中队长专属路径        : {0}" -f ($ownership.CaptainOnlyHits.Count -eq 0))

$mechanicalGatesPass = $baseOk -and (-not $prDetail.isDraft) -and $isMergeableRaw -and $isUpToDate -and
    (-not $hasNonPassingChecks) -and (-not $hasZeroChecks) -and (-not $bugbotBlocking) -and
    (-not $unresolvedBlocking) -and ($ownership.OutOfScopeFiles.Count -eq 0) -and ($ownership.CaptainOnlyHits.Count -eq 0)

Write-Section "步骤 6/6：结果与（可选）合并动作"

if (-not $baseOk) {
    Exit-WithCode $ExitCodes.SECURITY_ABORT "Base 分支策略不满足（普通模式要求 base=$OrdinaryBaseBranch；ReleaseMode 要求 base=$ReleaseBaseBranch 且 head=$ReleaseHeadBranch 且标题以 [RELEASE] 开头）。已拒绝执行合并相关操作。 "
}

if (-not $AllowMerge) {
    if ($prDetail.isDraft -or $hasZeroChecks -or $hasNonPassingChecks -or $bugbotBlocking -or (-not $isUpToDate) -or $unresolvedBlocking) {
        Exit-WithCode $ExitCodes.WAITING "InspectOnly 完成：存在等待项（Draft/Checks/Bugbot/分支同步/讨论线程），详见上方输出与 $outDirUsed。 "
    }
    Exit-WithCode $ExitCodes.OK "InspectOnly 完成：机械门禁检查已就绪；语义审核（P0/P1、科学真实性）仍需由 Agent 完成后再决定是否调用 -AllowMerge。 "
}

# ---- 以下逻辑仅在显式传入 -AllowMerge 时执行 ----

Write-Host "正在重新拉取最新 head SHA 以防止审核后内容被替换 ..." -ForegroundColor DarkGray
$freshDetail = Get-PrFullDetail -PrNumber $targetNumber
$currentHeadSha = $freshDetail.headRefOid

if ($currentHeadSha -ne $ReviewedHeadSha) {
    Exit-WithCode $ExitCodes.SECURITY_ABORT "Head SHA 已变化（审核时=$ReviewedHeadSha，当前=$currentHeadSha）。已中止合并，不得使用旧审核结论合并新内容。 "
}

if (-not $mechanicalGatesPass) {
    Exit-WithCode $ExitCodes.NEEDS_CHANGES "机械合并门禁未全部满足，拒绝合并。请先解决上方列出的问题（Checks / Bugbot / 路径归属 / 讨论线程 / 分支同步）。 "
}

$approveCmd = "gh pr review $targetNumber --repo $RepoSlug --approve --body " + '"' + $ApproveBody + '"'
$mergeCmd   = "gh pr merge $targetNumber --repo $RepoSlug --squash --match-head-commit $currentHeadSha"

if ($DryRun) {
    Write-Host "[DRYRUN] 不会真实提交 Review 或执行合并。将会执行的命令： " -ForegroundColor Magenta
    Write-Host "  $approveCmd"
    Write-Host "  $mergeCmd"
    Exit-WithCode $ExitCodes.OK "DryRun 完成：所有门禁满足，但按 -DryRun 要求未实际提交 Review / 未合并。 "
}

Write-Host "正在提交 Approve ..." -ForegroundColor Green
& gh pr review $targetNumber --repo $RepoSlug --approve --body $ApproveBody
if ($LASTEXITCODE -ne 0) {
    Exit-WithCode $ExitCodes.ENV_ERROR "gh pr review --approve 执行失败。 "
}

Write-Host "正在执行 Squash Merge（--match-head-commit 锁定审核时的 SHA）..." -ForegroundColor Green
& gh pr merge $targetNumber --repo $RepoSlug --squash --match-head-commit $currentHeadSha
if ($LASTEXITCODE -ne 0) {
    Exit-WithCode $ExitCodes.ENV_ERROR "gh pr merge 执行失败（可能是 head SHA 在最后一刻发生变化，或权限问题）。 "
}

Exit-WithCode $ExitCodes.MERGED "PR #$targetNumber 已 Squash Merge 到 $($prDetail.baseRefName)（reviewed head SHA=$currentHeadSha）。 "
