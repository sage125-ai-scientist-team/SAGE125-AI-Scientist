# T04 Wave B Reproduction Guide

## Artifact Retrieval

The artifact must be obtained from an authorized source.

Current retrieval information: `PENDING_CONFIRMATION`.

## Local Verification

Expected SHA-256:

```text
4bda50e8e3c90f8968f1bfd72ded4d9587ae80cd40ba66656a12c93abcf8e576
```

Verify on Windows:

```powershell
certutil -hashfile data/raw/sjtu-booklet.pdf SHA256
```

Verify portably and fail on mismatch:

```bash
python -c "import hashlib, pathlib; p=pathlib.Path('data/raw/sjtu-booklet.pdf'); actual=hashlib.sha256(p.read_bytes()).hexdigest(); expected='4bda50e8e3c90f8968f1bfd72ded4d9587ae80cd40ba66656a12c93abcf8e576'; print(actual); raise SystemExit(0 if actual == expected else 1)"
```

Exit code `0` confirms byte identity only. It does not establish source URI,
version, license, authorization, or formal-corpus approval.
