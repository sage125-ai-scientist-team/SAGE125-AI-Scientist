# Browser Rehearsal Evidence

状态：

```text
SYNTHETIC_REHEARSAL=PASS
PRODUCTION_E2E=WAIT
```

Environment:

```text
UI=http://127.0.0.1:18510
API=http://127.0.0.1:18010
source=tests/api fixtures + planned synthetic runner
```

Identity:

```text
job_id=7fbc2b9b-2709-45ff-a475-1037b0ac52f5
feedback_id=feedback-45613e4f386d46a7ba07810131e55a0e
correlation_id=d744112d-fd0c-4fe0-9a69-43a6f2bc6ff9
```

Observed in a real browser:

1. Streamlit rendered without traceback.
2. Q001 job completed and persisted in URL state.
3. Evidence displayed quote, locator, source, author/year, and confidence 0.91.
4. V1/V2, Reviewer issue, scores, lineage, and structured diff displayed.
5. Gate displayed.
6. Execution displayed `NOT ACTUAL`, status `planned`, and explicit warning.
7. Multimodal displayed source, confidence 0.72, and human-review warning.
8. Feedback submit returned a feedback ID.
9. Feedback decision read honestly returned
   `UPSTREAM_CONTRACT_UNAVAILABLE`; no resulting version was fabricated.
10. JSON, Markdown, and PDF exports were registered for the same job.
11. Refresh restored the same job without cross-job contamination.

Export observations:

```text
report.json  canonical_report_json      planned  2132 bytes
report.md    canonical_report_markdown  planned  1459 bytes
report.pdf   canonical_report_pdf       planned  39807 bytes
```

Screenshot handling:

- Six browser-agent screenshots were generated in temporary controlled storage.
- The browser tool could not persist them directly into the repository path.
- `screenshots_or_traces/README.md` records the intended controlled filename.
- Screenshot packaging therefore remains `WAIT` until copied and scanned through an approved binary-file workflow.

Production blockers:

- T01/T02/T05 production read ports;
- T03 decision/resulting-version/Gate read port;
- actual T05 execution;
- Docker clean environment;
- final clean SHA;
- T07 and T09 signatures.
