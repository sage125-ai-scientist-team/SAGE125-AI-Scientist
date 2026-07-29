# SAGE125 Bugbot Review Rules

These rules apply to every pull request in
`sage125-ai-scientist-team/SAGE125-AI-Scientist`, for both Cursor Bugbot and the
Cursor Agent captain review workflow described in
`.cursor/rules/sage125-captain-pr-review.mdc` and
`docs/governance/CURSOR_PR_REVIEW_RUNBOOK.md`.

Machine-readable versions of the path ownership and merge-gate policy live in
`docs/governance/task-owner-map.yaml` and `docs/governance/pr-review-policy.yaml`.
This document is the human-readable rulebook; the YAML files are the source of truth
that review tooling parses. Keep them in sync.

## 1. Branch policy

- Ordinary teammate pull requests must target `integration/2026-08-10`.
- An ordinary task PR targeting `main` is blocking (**P1**).
- Only the final release PR may use: `integration/2026-08-10` → `main`.
- The final release PR requires explicit captain instruction:
  "审核最终发布PR并在全部发布门禁通过后合并到main". Title must start with `[RELEASE]`.

## 2. Task and path ownership

Identify T01–T09 from the PR title, branch name, or labels.

The following paths are the **sole owner paths** for each task. A PR under a given task
should only touch its own owner paths (plus, when unavoidable, paths explicitly listed
as `shared_change_required_paths` in `task-owner-map.yaml`, with a recorded captain
approval).

**T01 — Evidence**
- `app/evidence/**`
- `app/contracts/evidence.py`
- `tests/evidence/**`
- `docs/modules/T01/**`
- `docs/contracts/T01.md`

**T02 — Workflow / Revision**
- `app/workflow/**`
- `app/contracts/revision.py`
- `tests/workflow/**`
- `docs/modules/T02/**`
- `docs/contracts/T02.md`

**T03 — Feedback / Validation / Quality**
- `app/feedback/**`
- `app/validation/**`
- `app/quality/**`
- `app/contracts/validation.py`
- `tests/validation/**`
- `docs/modules/T03/**`
- `docs/contracts/T03.md`

**T04 — RAG**
- `app/rag/**`
- `app/contracts/rag.py`
- `tests/rag/**`
- `docs/modules/T04/**`
- `docs/contracts/T04.md`

**T05 — Execution**
- `app/execution/**`
- `app/contracts/execution.py`
- `tests/execution/**`
- `experiments/flagship/**`
- `docs/modules/T05/**`
- `docs/contracts/T05.md`

**T06 — Multimodal**
- `app/multimodal/**`
- `app/contracts/multimodal.py`
- `tests/multimodal/**`
- `docs/modules/T06/**`
- `docs/contracts/T06.md`

**T07 — Batch**
- `app/batch/**`
- `scripts/batch_125/**`
- `app/contracts/batch.py`
- `tests/batch/**`
- `docs/modules/T07/**`
- `docs/contracts/T07.md`

**T08 — API / Frontend / Deployment**
- `app/api/**`
- `frontend/**`
- `app/export/**`
- `Dockerfile`
- `compose.yaml`
- `tests/api/**`
- `docs/deployment/**`
- `docs/contracts/T08.md`

**T09 — CI / Reproducibility / Dependencies**
- `.github/workflows/**`
- `tests/integration/**`
- `scripts/eval/**`
- `docs/reproducibility/**`
- `docs/contracts/T09.md`
- `pyproject.toml`
- `requirements*.txt`
- dependency lock files
- `LICENSE`
- SBOM files

### Captain-only or shared high-risk files

The following require captain approval regardless of who opens the PR:

- `main` and `integration` branch configuration/protection rules
- `.github/CODEOWNERS`
- Root `AGENTS.md`
- Root `README.md`
- `.github/PULL_REQUEST_TEMPLATE/**`
- `.github/ISSUE_TEMPLATE/**`
- `app/contracts/base.py`
- Repository Secrets
- Releases and tags
- `.cursor/rules/**`
- `.cursor/BUGBOT.md`
- `scripts/captain/**`
- `docs/governance/**`

**Rule:** if a PR modifies files outside its task's owner paths (and outside the
captain-only list, which teammates should never touch at all), there must be a
verifiable, captain-approved `shared-change` record (e.g. a linked issue/comment where
the captain explicitly approved the cross-path change). Without that record, this is
**P1**.

## 3. Security — blocking

Any of the following is **P0**:

- API keys, tokens, passwords, or private keys anywhere in the diff.
- `.env` file additions or modifications.
- Personal/private data.
- `data/index/` content committed.
- Private uploaded files committed.
- Old `exports/` committed.
- Virtual environments (`.venv/`, `venv/`) committed.
- `node_modules/` committed.
- Large caches or unlicensed datasets committed.
- Unsafely executing fork PR code with elevated tokens exposed to it.
- `pull_request_target` combined with untrusted PR head code (a classic secret-leak
  pattern) — must be flagged even if it "works".
- Force push present in the PR history.
- Any attempt at admin bypass of required checks.
- Unrestricted dynamic code execution (`eval`, `exec`, unpickling untrusted data, etc.)
  introduced without a strong justification.

## 4. Scientific integrity — blocking

At minimum **P1**; outright fabrication is **P0**:

- `planned`, `expected`, `mock`, or `synthetic` results relabeled as `actual`.
- `actual_execution=false` while the output still reports real-looking metrics.
- Fabricated AUROC, accuracy, cost, latency, or other experiment results.
- Fabricated papers, citations, or evidence.
- The 125-question booklet used as if it were peer-reviewed evidence for a scientific
  claim.
- A fact supported only by a title, DOI, or OpenAlex metadata record (no real quoted
  content).
- Any "established fact" lacking a `source_id`, an original quote, and a
  page/section locator.
- Cross-domain conclusions extrapolated unconditionally with no supporting evidence.

## 5. Reviewer, human feedback, and execution feedback loops

**P1** if any of the following occur:

- Reviewer comments are only recorded but never fed into the next generation round.
- Human feedback is only appended to history but never changes the next round's input.
- An `ExecutionResult` never makes it back into the next round's research plan.
- The PR claims a revision was made, but the relevant prompt/input hash is unchanged
  with no explanation.
- A `required_revision` is marked resolved without evidence it was actually addressed.
- `validation_status=passed` while known P0/P1 issues remain open.

## 6. Batch isolation (125-question run isolation)

**P1** if any of the following occur:

- `question_id` is missing from the cache key.
- `question_id` is missing from the workspace path, output path, manifest, or state.
- One question's run reuses another question's hypotheses, literature, report body,
  or results.
- Mock output is presented as an official result for one of the 125 questions.
- The manifest's reported total does not match the real output count.
- Any evidence of cross-question report contamination.

## 7. CI and tests

Blocking (severity depends on context, default **P1**, escalate to **P0** for
deliberate CI-gaming):

- A required job is missing from the workflow run.
- `continue-on-error: true` added to a job that used to be required.
- `if: false` or an unconditional skip added to bypass a check.
- Vacuous tests such as bare `assert True` with no real verification.
- Deletion or weakening of pre-existing assertions.
- New behavior introduced with no test coverage at all.
- Missing failure-path / edge-case tests for risky new logic.
- A job renamed specifically to dodge a required-status-check name.
- `skipped` status treated as if it were `success`.
- Workflow does not respond to `pull_request` `synchronize` events (so re-pushes never
  re-run CI).
- A fork PR workflow configuration that would hand production secrets to untrusted fork
  code.

This project's required check families are:

- `lint`
- `type`
- `unit`
- `integration`
- `security`
- `build`

> Current state note (keep updated as CI evolves): as of this policy's creation, the
> repository's `.github/workflows/ci.yml` runs a single `pytest` job (offline test
> suite with `MOCK_LLM=true`). Until T09 adds dedicated `lint` / `type` / `integration`
> / `security` / `build` jobs, reviewers must treat any of those missing families as
> **"not yet available"**, not as **"passed"** — see `pr-review-policy.yaml`'s
> `required_check_families` and the runbook's CI section for how to handle this
> transitional state without ever treating missing checks as green.

## 8. Finding format

Every blocking finding must include:

- **Severity**: P0 or P1.
- **File path**.
- **Exact line number(s)**.
- **Problem**: what is wrong.
- **Consequence**: what breaks or what risk this creates.
- **Required fix**: what must change.
- **Verification command**: the exact command the author (or reviewer) should run to
  confirm the fix.

When there are no blocking findings, the review must say exactly:

```
No blocking SAGE125 findings.
```

It must never say only "looks good" or similar vague approval language with no
structured checklist behind it.

## 9. Task content / Wave acceptance (supplementary)

Bugbot / Agent supplementary review MUST load the machine-readable V3.0 task spec for
the PR's task:

`docs/governance/task-requirements/T0X.yaml`

Rules:

1. Identify task/wave from title → branch → labels → body. On conflict: WAIT, do not guess.
2. Check **current Wave** requirements; cite `Requirement ID` (e.g. `T09-A-003`) in findings.
3. "Code runs" ≠ "task complete". "A test file exists" ≠ "tests are effective".
4. PR description claims are never sufficient evidence of completion.
5. Quantitative thresholds without full evidence (data/manifest, script, raw+aggregate
   results, command, model/prompt versions, seed when applicable, commit, time, env,
   checksum, repro notes) are `UNVERIFIED` — never `PASS` from a screenshot alone.
6. Future-wave-only gaps are `DEFERRED` and must not wrongly block an earlier Wave.
7. Emit `P2` / `AWARD_QUALITY_RECOMMENDATION` when the current Wave hard bar is met but
   award quality can still improve (does not block).
8. Bugbot findings are **supplementary**. Final merge judgment is owned by the Cursor
   Agent captain workflow and `scripts/captain/review_latest_pr.ps1`, which require both
   `ENGINEERING_COMPLIANCE=PASS` and `CONTENT_COMPLIANCE=PASS`.

Do **not** paste the full T01–T09 YAML bodies into Bugbot comments; reference IDs and
short excerpts only.
