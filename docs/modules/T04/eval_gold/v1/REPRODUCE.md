# T04 Wave B Reproduction Guide

## Controlled Artifact Acquisition

Obtain `sjtu-booklet.zip` through the project's internal controlled-artifact
channel and place the unchanged archive at:

```text
data/raw/sjtu-booklet.zip
```

No public source URI is claimed. Do not commit the archive or extracted PDF.
The acquisition source type is `INTERNAL_CONTROLLED_ARTIFACT`.

## Expected Identities

| Artifact | Size (bytes) | SHA-256 |
|---|---:|---|
| `sjtu-booklet.zip` | 7405356 | `f2cc232d0f40ec125593ddbcecede98dc55093e7ce4c9e29f2bef16e64c1a185` |
| `sjtu-booklet.pdf` | 8422081 | `4bda50e8e3c90f8968f1bfd72ded4d9587ae80cd40ba66656a12c93abcf8e576` |

Archive member path: `sjtu-booklet.pdf`.

## Windows Reproduction

Run from the repository root in PowerShell. The archive is expanded into a new
temporary directory so an existing PDF is never overwritten.

```powershell
$archive = Resolve-Path -LiteralPath "data/raw/sjtu-booklet.zip"
$expectedArchiveSize = 7405356
$expectedArchiveSha256 = "f2cc232d0f40ec125593ddbcecede98dc55093e7ce4c9e29f2bef16e64c1a185"
$expectedPdfSize = 8422081
$expectedPdfSha256 = "4bda50e8e3c90f8968f1bfd72ded4d9587ae80cd40ba66656a12c93abcf8e576"

$archiveItem = Get-Item -LiteralPath $archive
if ($archiveItem.Length -ne $expectedArchiveSize) {
    throw "Archive size mismatch: $($archiveItem.Length)"
}
$archiveSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
if ($archiveSha256 -ne $expectedArchiveSha256) {
    throw "Archive SHA-256 mismatch: $archiveSha256"
}

$staging = Join-Path ([System.IO.Path]::GetTempPath()) ("sage125-booklet-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $staging | Out-Null
Expand-Archive -LiteralPath $archive -DestinationPath $staging

$pdf = Join-Path $staging "sjtu-booklet.pdf"
$pdfItem = Get-Item -LiteralPath $pdf
if ($pdfItem.Length -ne $expectedPdfSize) {
    throw "PDF size mismatch: $($pdfItem.Length)"
}
$pdfSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $pdf).Hash.ToLowerInvariant()
if ($pdfSha256 -ne $expectedPdfSha256) {
    throw "PDF SHA-256 mismatch: $pdfSha256"
}

Write-Output "ARCHIVE_SHA256=$archiveSha256"
Write-Output "PDF_SHA256=$pdfSha256"
Write-Output "VERIFIED_MEMBER=$pdf"
exit 0
```

For an independent display-only check, use:

```powershell
certutil -hashfile data/raw/sjtu-booklet.zip SHA256
certutil -hashfile data/raw/sjtu-booklet.pdf SHA256
```

Exit code `0` confirms the archive and extracted-member byte identities only.
Formal corpus inclusion remains `NOT_CLAIMED_IN_FORMAL_CORPUS` pending T09
validation and captain approval.
