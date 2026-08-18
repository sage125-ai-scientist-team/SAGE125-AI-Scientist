# Browser evidence

This directory contains only synthetic browser rehearsal screenshots bound to
the current working tree. They are not production E2E evidence.

Expected committed screenshot:

- `synthetic_rehearsal_full_page.png`

The browser rehearsal observed:

```text
job_id=7fbc2b9b-2709-45ff-a475-1037b0ac52f5
feedback_id=feedback-45613e4f386d46a7ba07810131e55a0e
correlation_id=d744112d-fd0c-4fe0-9a69-43a6f2bc6ff9
SYNTHETIC_REHEARSAL=PASS
PRODUCTION_E2E=WAIT
```

Temporary browser-agent screenshots are not treated as release artifacts until
copied into this controlled directory and checked for secrets and local paths.
