# T05 Wave B failure-injection evidence

The focused failure matrix was executed on 2026-08-05:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q `
  tests/execution/test_actual_execution.py::test_T05_A_INTEGRITY_008_timeout_is_not_actual `
  tests/execution/test_actual_execution.py::test_T05_A_INTEGRITY_013_unimplemented_resource_limits_are_not_enforced `
  tests/execution/test_security.py::test_t05_a_path_002_rejects_plain_and_encoded_traversal `
  tests/execution/test_flagship_baseline.py::test_dataset_pin_and_schema_fail_closed_before_artifacts `
  tests/execution/test_manifests.py::test_T05_A_PROV_004_actual_requires_complete_dependency_versions `
  tests/execution/test_flagship_baseline.py::test_baseline_is_deterministic_and_writes_complete_artifacts `
  tests/execution/test_actual_execution.py::test_T05_A_INTEGRITY_009_missing_required_artifact_fails `
  tests/execution/test_actual_execution.py::test_T05_A_INTEGRITY_010_checksum_mismatch_fails_closed `
  tests/execution/test_runner.py::test_T05_A_RUN_006_cleanup_failure_cannot_masquerade_as_success
```

Result: **17 passed, 0 failed, 0 skipped in 2.96 seconds**.

The corresponding machine-readable report is
`experiments/flagship/failure_injection_report.json`. The memory-limit case is
intentionally a capability-honesty test: this process backend must report a
memory limit as unsupported/not enforced rather than claim that it simulated a
real OOM sandbox. This preserves the original safety assertion and does not
turn an unavailable host capability into a silent pass.

The full WDBC adapter/baseline regression run separately reported 180 passed
and 2 skipped. Both skips were Windows symlink privilege probes (WinError 1314);
no test or assertion was removed, weakened, or newly skipped.
