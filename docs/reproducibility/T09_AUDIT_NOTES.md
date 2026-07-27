# T09 PR-A audit notes

## Scope and final-tree status

This note describes the final T09 PR-A implementation after synchronising the current `upstream/integration/2026-08-10` baseline (`1642ea05e88b853f18d24739d9d2134c3448eb7b`). The code candidate exercised locally was `013f9c843c1347ce8f9b32fab7cdcf0a53e67485`, the merge commit that contains that integration baseline and the semantic CI conflict resolution.

The PR changes these T09-owned areas:

- `.github/workflows/ci.yml`: six real, separately named GitHub Actions jobs.
- `tests/integration/test_wave_a_offline_contract.py`: the offline integration fixture.
- `scripts/eval/wave_a_quality.py` and `scripts/eval/benchmark_skeleton.py`: lint/type contracts and deterministic dry-run schema validation.
- `docs/reproducibility/**`: audit evidence and required-check contract.

All jobs use Python 3.12, `MOCK_LLM=true`, `PYTHONUTF8=1`, and `PYTHONIOENCODING=utf-8`. They do not read production secrets, invoke a live model, or use `continue-on-error`. A non-zero command exit fails its job.

## CI implementation

`ci.yml` runs on pushes and on pull requests targeting `integration/2026-08-10` for `opened`, `synchronize`, `reopened`, and `edited` events. Permissions are limited to `contents: read`.

The six fixed jobs are `lint`, `type`, `unit`, `integration`, `security`, and `build`. The upstream Windows UTF-8 repair is preserved globally and all Python test or potentially Chinese-output commands use `python -X utf8`. `unit` runs the offline suite excluding `tests/integration`; `integration` runs that fixture independently. Their union preserves the upstream full pytest coverage while retaining distinct check names.

## Evidence status

### Executed locally

On 2026-07-28 with the repository's Python 3.12.10 virtual environment:

- `lint`: exit 0; 3 owned Python files; no failures.
- `type`: exit 0; no annotation-contract failures.
- `unit`: exit 0; 272 passed in 14.14 s.
- `integration`: exit 0; 1 passed in 0.16 s.
- `security`: exit 0; `critical=0`, `warnings=0`.
- `build`: exit 0; compilation, dry-run generation, and schema validation succeeded.
- Full offline pytest: exit 0; 273 passed in 10.18 s.

The benchmark JSON and CSV were written only below the system temporary directory; no benchmark output, audit report, cache, or `.env` file is part of the intended commit.

### Awaiting GitHub Actions

At the time this note was written, the repaired branch has not yet been pushed after the P1 fix commit. Therefore no GitHub Actions job is represented as passed here and there are no run URLs yet. The next normal push must trigger all six jobs. This PR remains Draft and is not ready to merge.

## P1 disposition

The local implementation addresses the CI conflict, UTF-8 regression, stale audit claims, missing fixed-job contract, and stale baseline evidence. Remote P1 closure remains conditional on the post-push six-job GitHub Actions run and captain review; neither condition is claimed complete in this document.
