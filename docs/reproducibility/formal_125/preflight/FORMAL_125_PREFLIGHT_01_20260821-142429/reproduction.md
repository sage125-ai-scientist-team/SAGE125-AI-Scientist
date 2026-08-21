# Formal 125 Preflight Reproduction

This package freezes the official 125-question catalog, locks, and offline dry-run.
It does not contain provider responses or official question results.

```text
python -m compileall app tests scripts
python -m pytest tests/formal125 -q
python -m pytest -q
```
